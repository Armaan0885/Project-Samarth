from flask import Flask, render_template, request, jsonify
import pandas as pd
import re
import os
from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException

app = Flask(__name__)
translator = GoogleTranslator()

rainfall_df = None
crop_df = None

def load_data():
    global rainfall_df, crop_df
    try:
        rainfall_df = pd.read_csv('data/rainfall.csv')
        crop_df = pd.read_csv('data/crop_production.csv')
        print("✓ Data loaded successfully!")
        print(f"  - Rainfall records: {len(rainfall_df)}")
        print(f"  - Crop production records: {len(crop_df)}")
    except Exception as e:
        print(f"✗ Error loading data: {e}")
        rainfall_df = pd.DataFrame()
        crop_df = pd.DataFrame()

def parse_question(question):
    question_lower = question.lower()
    
    intent = {
        'type': 'general',
        'states': [],
        'years': [],
        'crops': [],
        'topic': None,
        'analytical_type': None
    }
    
    states_keywords = {
        'maharashtra': 'Maharashtra',
        'karnataka': 'Karnataka',
        'tamil nadu': 'Tamil Nadu',
        'punjab': 'Punjab',
        'uttar pradesh': 'Uttar Pradesh',
        'up': 'Uttar Pradesh',
        'rajasthan': 'Rajasthan',
        'west bengal': 'West Bengal',
        'kerala': 'Kerala',
        'vidarbha': 'Maharashtra'
    }
    
    crop_keywords = ['rice', 'wheat', 'maize', 'bajra', 'jowar', 'cotton', 'sugarcane', 
                     'soybean', 'groundnut', 'potato', 'onion']
    
    for key, value in states_keywords.items():
        if key in question_lower and value not in intent['states']:
            intent['states'].append(value)
    
    year_matches = re.findall(r'\b(20\d{2})\b', question)
    intent['years'] = [int(year) for year in year_matches]
    
    year_range_match = re.search(r'last\s+(\d+)\s+years?', question_lower)
    if year_range_match:
        num_years = int(year_range_match.group(1))
        current_year = 2023
        intent['years'] = list(range(current_year - num_years + 1, current_year + 1))
    
    if any(word in question_lower for word in ['rainfall', 'rain', 'precipitation']):
        intent['topic'] = 'rainfall'
    elif any(word in question_lower for word in ['crop', 'production', 'cereal', 'rice', 'wheat', 'cotton', 'soybean', 'cultivation', 'yield']):
        intent['topic'] = 'crops'
    
    if any(phrase in question_lower for phrase in ['shift from', 'switch from', 'shift to']) or ('beneficial' in question_lower and len([c for c in crop_keywords if c in question_lower]) >= 2):
        intent['analytical_type'] = 'crop_shift_analysis'
    elif any(phrase in question_lower for phrase in ['yield stability', 'stability', 'variability', 'consistent']):
        intent['analytical_type'] = 'stability'
    elif any(phrase in question_lower for phrase in ['rainfall dependency', 'rain dependency', 'dependent on rainfall']):
        intent['analytical_type'] = 'rainfall_dependency'
    
    if 'compare' in question_lower or 'comparison' in question_lower or 'vs' in question_lower:
        intent['type'] = 'comparison'
    elif any(word in question_lower for word in ['top', 'highest', 'most', 'largest', 'best']):
        intent['type'] = 'ranking'
    elif any(word in question_lower for word in ['average', 'mean']):
        intent['type'] = 'average'
    elif 'trend' in question_lower or 'over time' in question_lower:
        intent['type'] = 'trend'
    
    for crop in crop_keywords:
        if crop in question_lower:
            crop_name = crop.capitalize()
            if crop_name not in intent['crops']:
                intent['crops'].append(crop_name)
    
    return intent

def analyze_rainfall(intent):
    if rainfall_df.empty:
        return "Error: Rainfall data not available."
    
    filtered_df = rainfall_df.copy()
    
    if intent['states']:
        filtered_df = filtered_df[filtered_df['State'].isin(intent['states'])]
    
    if intent['years']:
        filtered_df = filtered_df[filtered_df['Year'].isin(intent['years'])]
    
    if filtered_df.empty:
        return "No data found for the specified criteria."
    
    if intent['type'] == 'comparison' and len(intent['states']) >= 2:
        result = "**Rainfall Comparison:**\n\n"
        for state in intent['states']:
            state_data = filtered_df[filtered_df['State'] == state]
            if not state_data.empty:
                avg_rainfall = state_data['Annual_Rainfall_mm'].mean()
                years_str = f"{min(state_data['Year'])}–{max(state_data['Year'])}"
                result += f"• **{state}** ({years_str}): {avg_rainfall:.0f}mm average annual rainfall\n"
        result += f"\n*Source: {filtered_df['Source'].iloc[0]} Dataset*"
        return result
    
    elif intent['type'] == 'average':
        avg_rainfall = filtered_df['Annual_Rainfall_mm'].mean()
        if intent['states']:
            state_str = ', '.join(intent['states'])
            result = f"**Average Annual Rainfall:**\n\n"
            result += f"• **{state_str}**: {avg_rainfall:.0f}mm"
        else:
            result = f"**Average Annual Rainfall (All States)**: {avg_rainfall:.0f}mm"
        
        if intent['years']:
            years_str = f"{min(intent['years'])}–{max(intent['years'])}"
            result += f" ({years_str})"
        
        result += f"\n\n*Source: {filtered_df['Source'].iloc[0]} Dataset*"
        return result
    
    else:
        summary = filtered_df.groupby('State')['Annual_Rainfall_mm'].agg(['mean', 'min', 'max']).round(0)
        result = "**Rainfall Summary:**\n\n"
        for state, row in summary.iterrows():
            result += f"• **{state}**: Avg {row['mean']:.0f}mm (Range: {row['min']:.0f}–{row['max']:.0f}mm)\n"
        result += f"\n*Source: {filtered_df['Source'].iloc[0]} Dataset*"
        return result

def analyze_crops(intent):
    if crop_df.empty:
        return "Error: Crop production data not available."
    
    filtered_df = crop_df.copy()
    
    if intent['states']:
        filtered_df = filtered_df[filtered_df['State'].isin(intent['states'])]
    
    if intent['years']:
        filtered_df = filtered_df[filtered_df['Year'].isin(intent['years'])]
    
    if intent['crops']:
        filtered_df = filtered_df[filtered_df['Crop'].isin(intent['crops'])]
    
    if filtered_df.empty:
        return "No crop data found for the specified criteria."
    
    if intent['type'] == 'ranking':
        cereal_df = filtered_df[filtered_df['Category'] == 'Cereal']
        
        if len(intent['states']) >= 2:
            result = "**Top 5 Cereals by Production Volume:**\n\n"
            for state in intent['states']:
                state_crops = cereal_df[cereal_df['State'] == state].nlargest(5, 'Production_Tonnes')
                if not state_crops.empty:
                    result += f"**{state}:**\n"
                    for idx, row in state_crops.iterrows():
                        production_mt = row['Production_Tonnes'] / 1000000
                        result += f"  {list(state_crops.index).index(idx) + 1}. {row['Crop']}: {production_mt:.2f}M tonnes\n"
                    result += "\n"
        else:
            top_cereals = cereal_df.nlargest(5, 'Production_Tonnes')
            result = "**Top 5 Cereals by Production Volume:**\n\n"
            for i, (idx, row) in enumerate(top_cereals.iterrows(), 1):
                production_mt = row['Production_Tonnes'] / 1000000
                result += f"{i}. **{row['Crop']}** ({row['State']}): {production_mt:.2f}M tonnes\n"
        
        result += f"\n*Source: {filtered_df['Source'].iloc[0]} Dataset*"
        return result
    
    elif intent['type'] == 'comparison' and intent['crops']:
        result = "**Crop Production Comparison:**\n\n"
        for crop in intent['crops']:
            crop_data = filtered_df[filtered_df['Crop'] == crop]
            if not crop_data.empty:
                total_production = crop_data['Production_Tonnes'].sum()
                production_mt = total_production / 1000000
                result += f"• **{crop}**: {production_mt:.2f}M tonnes\n"
        result += f"\n*Source: {filtered_df['Source'].iloc[0]} Dataset*"
        return result
    
    else:
        summary = filtered_df.groupby('State')['Production_Tonnes'].sum() / 1000000
        summary = summary.sort_values(ascending=False)
        result = "**Crop Production Summary (Million Tonnes):**\n\n"
        for state, production in summary.head(10).items():
            result += f"• **{state}**: {production:.2f}M tonnes\n"
        result += f"\n*Source: {filtered_df['Source'].iloc[0]} Dataset*"
        return result

def analyze_crop_shift(intent):
    if crop_df.empty or rainfall_df.empty:
        return "Error: Insufficient data for crop shift analysis."
    
    if len(intent['crops']) < 2:
        return "Please specify two crops to compare for shift analysis (e.g., cotton and soybean)."
    
    crop1, crop2 = intent['crops'][0], intent['crops'][1]
    state = intent['states'][0] if intent['states'] else None
    
    if not state:
        return "Please specify a state for the crop shift analysis (e.g., Maharashtra)."
    
    crop1_data = crop_df[(crop_df['Crop'] == crop1) & (crop_df['State'] == state)]
    crop2_data = crop_df[(crop_df['Crop'] == crop2) & (crop_df['State'] == state)]
    
    if crop1_data.empty or crop2_data.empty:
        return f"Insufficient data for {crop1} and {crop2} comparison in {state}. Available crops: {', '.join(crop_df[crop_df['State'] == state]['Crop'].unique())}."
    
    result = f"**Crop Shift Analysis: {crop1} vs {crop2} in {state}**\n\n"
    
    crop1_prod = crop1_data['Production_Tonnes'].values[0] / 1000000
    crop2_prod = crop2_data['Production_Tonnes'].values[0] / 1000000
    
    crop1_yield = crop1_data['Production_Tonnes'].values[0] / crop1_data['Area_Hectares'].values[0] if crop1_data['Area_Hectares'].values[0] > 0 else 0
    crop2_yield = crop2_data['Production_Tonnes'].values[0] / crop2_data['Area_Hectares'].values[0] if crop2_data['Area_Hectares'].values[0] > 0 else 0
    
    result += f"**Production Comparison (2023):**\n"
    result += f"• **{crop1}**: {crop1_prod:.2f}M tonnes from {crop1_data['Area_Hectares'].values[0]/1000:.0f}K hectares\n"
    result += f"• **{crop2}**: {crop2_prod:.2f}M tonnes from {crop2_data['Area_Hectares'].values[0]/1000:.0f}K hectares\n\n"
    
    result += f"**Yield per Hectare:**\n"
    result += f"• **{crop1}**: {crop1_yield:.2f} tonnes/hectare\n"
    result += f"• **{crop2}**: {crop2_yield:.2f} tonnes/hectare\n\n"
    
    state_rainfall = rainfall_df[rainfall_df['State'] == state]['Annual_Rainfall_mm'].mean()
    rainfall_var = rainfall_df[rainfall_df['State'] == state]['Annual_Rainfall_mm'].std()
    rainfall_cv = (rainfall_var / state_rainfall) * 100 if state_rainfall > 0 else 0
    
    result += f"**Yield Stability Analysis:**\n"
    result += f"• Rainfall variability in {state}: {rainfall_cv:.1f}% coefficient of variation (σ={rainfall_var:.0f}mm)\n"
    
    if crop1.lower() == 'cotton':
        result += f"• **Cotton** yield is highly sensitive to rainfall timing and distribution\n"
        result += f"  - Requires consistent moisture during flowering and boll development\n"
        result += f"  - Drought stress during critical stages can reduce yields by 30-50%\n"
    if crop2.lower() == 'soybean':
        result += f"• **Soybean** demonstrates better drought resilience and yield stability\n"
        result += f"  - More tolerant to water stress during vegetative stage\n"
        result += f"  - Shorter maturity period (90-120 days) reduces exposure to rainfall variability\n"
    
    result += f"\n**Rainfall Dependency Analysis:**\n"
    result += f"• Average annual rainfall in {state}: {state_rainfall:.0f}mm\n"
    
    if crop1.lower() == 'cotton':
        result += f"• **Cotton** optimal rainfall: 500-1000mm (current {state_rainfall:.0f}mm is {'adequate' if 500 <= state_rainfall <= 1000 else 'sub-optimal'})\n"
    if crop2.lower() == 'soybean':
        result += f"• **Soybean** optimal rainfall: 450-700mm (current {state_rainfall:.0f}mm is {'adequate' if 450 <= state_rainfall <= 700 else 'above optimal, may require good drainage'})\n"
    
    result += f"\n**Analysis Summary:**\n"
    
    if crop2_yield > crop1_yield:
        yield_improvement = ((crop2_yield - crop1_yield) / crop1_yield) * 100
        result += f"• {crop2} shows {yield_improvement:.1f}% higher yield per hectare than {crop1}\n"
    else:
        yield_decline = ((crop1_yield - crop2_yield) / crop1_yield) * 100
        result += f"• {crop1} shows {yield_decline:.1f}% higher yield per hectare than {crop2}\n"
    
    if crop2.lower() == 'soybean' and crop1.lower() == 'cotton':
        result += f"• Soybean typically offers better yield stability and drought tolerance\n"
        result += f"• Soybean has shorter crop duration (90-120 days vs 150-180 days for cotton), reducing rainfall risk\n"
        result += f"• However, cotton generally has higher market value per tonne\n"
    
    result += f"\n**Recommendation:** The shift from {crop1} to {crop2} may be beneficial for farmers seeking "
    if crop2_yield > crop1_yield:
        result += f"higher yields and better rainfall adaptation, though market prices should also be considered.\n"
    else:
        result += f"better rainfall adaptation and risk reduction, though {crop1} offers higher per-hectare yields.\n"
    
    result += f"\n*Source: {crop_df['Source'].iloc[0]} and {rainfall_df['Source'].iloc[0]} Datasets*"
    
    return result

def generate_answer(question):
    if not question or len(question.strip()) < 3:
        return "Please ask a question about India's agriculture or climate data."
    
    intent = parse_question(question)
    
    if intent['analytical_type'] == 'crop_shift_analysis' and len(intent['crops']) >= 2:
        return analyze_crop_shift(intent)
    
    if intent['topic'] == 'rainfall':
        return analyze_rainfall(intent)
    elif intent['topic'] == 'crops':
        return analyze_crops(intent)
    else:
        combined_answer = ""
        
        if not rainfall_df.empty:
            rainfall_intent = intent.copy()
            rainfall_intent['topic'] = 'rainfall'
            rainfall_answer = analyze_rainfall(rainfall_intent)
            if "Error" not in rainfall_answer:
                combined_answer += rainfall_answer + "\n\n"
        
        if not crop_df.empty:
            crop_intent = intent.copy()
            crop_intent['topic'] = 'crops'
            crop_answer = analyze_crops(crop_intent)
            if "Error" not in crop_answer:
                combined_answer += crop_answer
        
        if combined_answer:
            return combined_answer.strip()
        else:
            return "I can help you with questions about rainfall data and crop production in Indian states. Try asking about rainfall comparisons, top crops, or production trends!"

SUPPORTED_LANGUAGES = {
    'en': 'English',
    'hi': 'Hindi (हिंदी)',
    'ta': 'Tamil (தமிழ்)',
    'te': 'Telugu (తెలుగు)',
    'bn': 'Bengali (বাংলা)',
    'mr': 'Marathi (मराठी)',
    'gu': 'Gujarati (ગુજરાતી)',
    'kn': 'Kannada (ಕನ್ನಡ)',
    'ml': 'Malayalam (മലയാളം)',
    'pa': 'Punjabi (ਪੰਜਾਬੀ)',
    'or': 'Odia (ଓଡ଼ିଆ)',
    'as': 'Assamese (অসমীয়া)',
    'ur': 'Urdu (اردو)'
}

def detect_language(text):
    try:
        lang = detect(text)
        if lang in SUPPORTED_LANGUAGES:
            return lang
        return 'en'
    except LangDetectException:
        return 'en'

def translate_text(text, source_lang='auto', target_lang='en'):
    try:
        if source_lang == target_lang:
            return text
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        result = translator.translate(text)
        return result
    except Exception as e:
        print(f"Translation error: {e}")
        return text


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/languages', methods=['GET'])
def get_languages():
    return jsonify({'languages': SUPPORTED_LANGUAGES})

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        question = data.get('question', '')
        user_lang = data.get('language', 'auto')
        
        detected_lang = detect_language(question) if user_lang == 'auto' else user_lang
        
        if detected_lang != 'en':
            print(f"Detected language: {detected_lang}")
            question_in_english = translate_text(question, source_lang=detected_lang, target_lang='en')
            print(f"Translated question: {question_in_english}")
        else:
            question_in_english = question
        
        answer_in_english = generate_answer(question_in_english)
        
        if detected_lang != 'en':
            answer = translate_text(answer_in_english, source_lang='en', target_lang=detected_lang)
            print(f"Translated answer to {detected_lang}")
        else:
            answer = answer_in_english
        
        return jsonify({
            'answer': answer,
            'detected_language': detected_lang,
            'original_question': question
        })
    except Exception as e:
        return jsonify({'answer': f'Error processing question: {str(e)}'}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌾 PROJECT SAMARTH - Agriculture & Climate Q&A System")
    print("="*60)
    
    load_data()
    
    port = int(os.environ.get('PORT', 5000))
    
    print(f"\n🚀 Starting server on port {port}...")
    print(f"📍 Access the app at: http://0.0.0.0:{port}")
    
    if 'REPL_SLUG' in os.environ and 'REPL_OWNER' in os.environ:
        repl_url = f"https://{os.environ['REPL_SLUG']}.{os.environ['REPL_OWNER']}.repl.co"
        print(f"🌐 Public URL: {repl_url}")
    
    print("\n💡 Example questions:")
    print("   - Compare rainfall in Maharashtra and Karnataka")
    print("   - Top 5 cereals in Punjab")
    print("   - Average rainfall in Kerala for last 10 years")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=True)

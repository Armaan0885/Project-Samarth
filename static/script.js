const chatContainer = document.getElementById('chatContainer');
const chatForm = document.getElementById('chatForm');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');

let isProcessing = false;

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const question = userInput.value.trim();
    if (!question || isProcessing) return;
    
    addMessage(question, 'user');
    userInput.value = '';
    
    hideWelcomeMessage();
    
    isProcessing = true;
    sendButton.disabled = true;
    
    const typingIndicator = addTypingIndicator();
    
    const languageSelect = document.getElementById('languageSelect');
    const selectedLanguage = languageSelect ? languageSelect.value : 'auto';
    
    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                question: question,
                language: selectedLanguage
            })
        });
        
        const data = await response.json();
        
        removeTypingIndicator(typingIndicator);
        
        addMessage(data.answer, 'assistant');
        
        if (data.detected_language && data.detected_language !== 'en') {
            console.log(`Detected language: ${data.detected_language}`);
        }
        
    } catch (error) {
        removeTypingIndicator(typingIndicator);
        addMessage('Sorry, there was an error processing your question. Please try again.', 'assistant');
        console.error('Error:', error);
    } finally {
        isProcessing = false;
        sendButton.disabled = false;
        userInput.focus();
    }
});

function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    contentDiv.innerHTML = formatMessage(text);
    
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function formatMessage(text) {
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    text = text.replace(/\n/g, '<br>');
    
    return text;
}

function addTypingIndicator() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.id = 'typing-indicator';
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.innerHTML = '<span></span><span></span><span></span>';
    
    messageDiv.appendChild(typingDiv);
    chatContainer.appendChild(messageDiv);
    
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    return messageDiv;
}

function removeTypingIndicator(indicator) {
    if (indicator && indicator.parentNode) {
        indicator.parentNode.removeChild(indicator);
    }
}

function hideWelcomeMessage() {
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
    }
}

function askExample(element) {
    const question = element.textContent;
    userInput.value = question;
    userInput.focus();
    
    chatForm.dispatchEvent(new Event('submit'));
}

userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

userInput.focus();

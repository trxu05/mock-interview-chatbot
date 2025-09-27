// Connect to WebSocket server
const socket = io('http://localhost:5050');

// DOM Elements
const landingView = document.getElementById('landing-view');
const technicalView = document.getElementById('technical-view');
const behavioralView = document.getElementById('behavioral-view');
const generalView = document.getElementById('general-view');
const chatInterface = document.getElementById('chat-interface');
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-btn');
const jobBackgroundDiv = document.getElementById('job-background');

// New: End Interview Button and Summary View
let endBtn = document.getElementById('end-btn');
if (!endBtn) {
    endBtn = document.createElement('button');
    endBtn.id = 'end-btn';
    endBtn.textContent = 'End Interview';
    endBtn.className = 'ml-4 bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-6 rounded-lg';
    sendButton.parentNode.appendChild(endBtn);
}
const summaryView = document.createElement('div');
summaryView.id = 'summary-view';
summaryView.className = 'hidden bg-white rounded-lg shadow-md p-6 mt-8';
document.querySelector('.max-w-4xl').appendChild(summaryView);

// Add Processing View
const processingView = document.createElement('div');
processingView.id = 'processing-view';
processingView.className = 'hidden flex flex-col items-center justify-center bg-white rounded-lg shadow-md p-12 mt-8';
processingView.innerHTML = `
    <div class="flex flex-col items-center">
        <svg class="animate-spin h-12 w-12 text-blue-500 mb-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
        </svg>
        <h2 class="text-2xl font-semibold mb-2">Analyzing Your Interview...</h2>
        <p class="text-gray-600 text-lg">We are processing your answers and generating feedback. This may take a few seconds.</p>
    </div>
`;
document.querySelector('.max-w-4xl').appendChild(processingView);

// Navigation buttons
const typeNavButtons = document.querySelectorAll('.type-nav-btn');
const backButtons = document.querySelectorAll('.back-btn');

// Forms
const technicalForm = document.getElementById('technical-form');
const behavioralForm = document.getElementById('behavioral-form');
const generalForm = document.getElementById('general-form');

// State
let conversationHistory = [];
let currentInterviewType = null;
let jobBackground = {};
let questionsAndAnswers = [];

// Navigation logic
function showView(view) {
    landingView.classList.add('hidden');
    technicalView.classList.add('hidden');
    behavioralView.classList.add('hidden');
    generalView.classList.add('hidden');
    chatInterface.classList.add('hidden');
    summaryView.classList.add('hidden');
    processingView.classList.add('hidden');
    if (view) view.classList.remove('hidden');
}

typeNavButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        currentInterviewType = btn.dataset.type;
        if (currentInterviewType === 'technical') showView(technicalView);
        if (currentInterviewType === 'behavioral') showView(behavioralView);
        if (currentInterviewType === 'general') showView(generalView);
    });
});

backButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        showView(landingView);
    });
});

// Handle job background form submission
function handleFormSubmit(e, type) {
    e.preventDefault();
    const form = e.target;
    const jobTitle = form.jobTitle.value.trim();
    const jobDesc = form.jobDesc.value.trim();
    jobBackground = { jobTitle, jobDesc };
    startInterview(type, jobBackground);
}
technicalForm.addEventListener('submit', e => handleFormSubmit(e, 'technical'));
behavioralForm.addEventListener('submit', e => handleFormSubmit(e, 'behavioral'));
generalForm.addEventListener('submit', e => handleFormSubmit(e, 'general'));

// Start interview with job background
function startInterview(type, jobBackground) {
    showView(chatInterface);
    jobBackgroundDiv.innerHTML = `<b>Job Title:</b> ${jobBackground.jobTitle || ''}<br><b>Description:</b> ${jobBackground.jobDesc || ''}`;
    jobBackgroundDiv.classList.remove('hidden');
    chatMessages.innerHTML = '';
    conversationHistory = [];
    questionsAndAnswers = [];
    socket.emit('start_interview', { type, jobBackground });
}

sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;
    addMessageToChat('user', message);
    conversationHistory.push({ role: 'user', content: message });
    // Track Q&A for summary
    if (questionsAndAnswers.length === 0 || questionsAndAnswers[questionsAndAnswers.length-1].answer) {
        questionsAndAnswers.push({ question: '', answer: message });
    } else {
        questionsAndAnswers[questionsAndAnswers.length-1].answer = message;
    }
    socket.emit('user_message', {
        conversation_history: conversationHistory,
        job_background: jobBackground,
        interview_type: currentInterviewType
    });
    userInput.value = '';
    showTypingIndicator();
}

function addMessageToChat(role, message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    messageDiv.textContent = message;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    // Track Q&A for summary
    if (role === 'interviewer') {
        if (questionsAndAnswers.length === 0 || questionsAndAnswers[questionsAndAnswers.length-1].answer) {
            questionsAndAnswers.push({ question: message, answer: '' });
        } else {
            questionsAndAnswers[questionsAndAnswers.length-1].question = message;
        }
    }
}

function showTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = '<span></span><span></span><span></span>';
    chatMessages.appendChild(indicator);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return indicator;
}

// End Interview logic
endBtn.addEventListener('click', () => {
    showView(processingView);
    socket.emit('end_interview', {
        conversation_history: conversationHistory,
        job_background: jobBackground,
        interview_type: currentInterviewType,
        questions_and_answers: questionsAndAnswers
    });
});

// Socket event handlers
socket.on('interviewer_message', (data) => {
    const typingIndicator = document.querySelector('.typing-indicator');
    if (typingIndicator) typingIndicator.remove();
    addMessageToChat('interviewer', data.message);
    conversationHistory.push({ role: 'assistant', content: data.message });
});

socket.on('interview_summary', (data) => {
    showView(summaryView);
    // Build transcript as chat bubbles
    let transcriptHtml = '<h2 class="text-2xl font-semibold mb-6">Interview Transcript</h2>';
    transcriptHtml += '<div class="mb-8 flex flex-col gap-3">';
    data.transcript.forEach(turn => {
        if (turn.role === 'user') {
            transcriptHtml += `<div class="flex justify-end"><div class="bg-green-100 text-gray-800 px-4 py-2 rounded-lg max-w-xl">${turn.content}</div></div>`;
        } else {
            transcriptHtml += `<div class="flex justify-start"><div class="bg-blue-100 text-gray-800 px-4 py-2 rounded-lg max-w-xl">${turn.content}</div></div>`;
        }
    });
    transcriptHtml += '</div>';
    // Suggestions as a card
    let suggestionsHtml = `<h2 class="text-xl font-semibold mb-4">Suggestions for Improvement</h2><div class="mb-8 p-4 bg-yellow-50 border-l-4 border-yellow-400 rounded-lg text-gray-800 leading-relaxed">${data.suggestions.replace(/\n/g, '<br>')}</div>`;
    // Q&A Comparison as a grid
    let comparisonHtml = '<h2 class="text-xl font-semibold mb-4">Your Answers vs. Sample Answers</h2>';
    data.comparisons.forEach((item, idx) => {
        comparisonHtml += `
        <div class="mb-6 p-4 bg-gray-50 rounded-lg border">
            <div class="font-semibold mb-2 text-gray-700">Q${idx+1}: ${item.question}</div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <div class="font-bold text-blue-700 mb-1">Your Answer</div>
                    <div class="whitespace-pre-line bg-white p-3 rounded border text-gray-900">${item.user_answer}</div>
                </div>
                <div>
                    <div class="font-bold text-green-700 mb-1">Sample Answer</div>
                    <div class="whitespace-pre-line bg-white p-3 rounded border text-gray-900">${item.sample_answer}</div>
                </div>
            </div>
        </div>`;
    });
    summaryView.innerHTML =
        '<div class="space-y-10">' +
        transcriptHtml +
        suggestionsHtml +
        comparisonHtml +
        '<div class="flex justify-center"><button id="restart-btn" class="mt-6 bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-6 rounded-lg">Restart</button></div>' +
        '</div>';
    document.getElementById('restart-btn').onclick = () => window.location.reload();
});

socket.on('error', (data) => {
    console.error('Error:', data.message);
    addMessageToChat('interviewer', 'Sorry, there was an error processing your message. Please try again.');
});

// On load, show landing view
showView(landingView); 
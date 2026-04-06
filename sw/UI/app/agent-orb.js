// ── Agent Orb — Barebones chat with state management ───────

const orbBtn = document.getElementById('agent-orb-btn');
const chatPanel = document.getElementById('agent-chat');
const chatClose = document.getElementById('agent-chat-close');
const chatMessages = document.getElementById('agent-chat-messages');
const chatInput = document.getElementById('agent-chat-input');
const chatSend = document.getElementById('agent-chat-send');
const chatMic = document.getElementById('agent-chat-mic');
const chatStatus = document.getElementById('agent-chat-status');

// ── State ──────────────────────────────────────────────────
let isOpen = false;
let isListening = false;
let isSpeaking = false;
let messages = [
    { id: 1, role: 'agent', text: 'Velvet Nadir online. How can I assist you?' }
];

// ── Render Messages ────────────────────────────────────────
function renderMessages() {
    chatMessages.innerHTML = messages.map(msg => `
    <div class="chat-msg ${msg.role}">
      <div class="chat-msg__bubble">${msg.text}</div>
    </div>
  `).join('');
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ── Update Status Display ──────────────────────────────────
function updateOrbState() {
    // Status text
    chatStatus.textContent = isListening ? 'Listening...' : isSpeaking ? 'Speaking...' : 'Idle';

    // Orb button state classes
    orbBtn.classList.toggle('listening', isListening);
    orbBtn.classList.toggle('speaking', isSpeaking);

    // Mic button state
    chatMic.classList.toggle('active', isListening);
}

// ── Toggle Chat Panel ──────────────────────────────────────
function openChat() {
    isOpen = true;
    orbBtn.classList.add('hidden');
    chatPanel.classList.add('open');
    renderMessages();
    chatInput.focus();
}

function closeChat() {
    isOpen = false;
    orbBtn.classList.remove('hidden');
    chatPanel.classList.remove('open');
}

orbBtn.addEventListener('click', openChat);
chatClose.addEventListener('click', closeChat);

// ── Send Message ───────────────────────────────────────────
function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    messages.push({ id: Date.now(), role: 'user', text });
    chatInput.value = '';
    isListening = false;
    updateOrbState();
    renderMessages();

    // Mock agent response
    setTimeout(() => {
        isSpeaking = true;
        updateOrbState();
        messages.push({
            id: Date.now(),
            role: 'agent',
            text: 'Processing your request across active contexts...'
        });
        renderMessages();

        setTimeout(() => {
            isSpeaking = false;
            updateOrbState();
        }, 2000);
    }, 1000);
}

chatSend.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage();
});

// ── Mic Toggle ─────────────────────────────────────────────
chatMic.addEventListener('click', () => {
    isListening = !isListening;
    updateOrbState();
});

// ── Initial render ─────────────────────────────────────────
renderMessages();
updateOrbState();

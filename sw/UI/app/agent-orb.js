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
let isProcessing = false;
let messages = [
    { id: 1, role: 'agent', text: 'Velvet Nadir online. How can I assist you?' }
];

import { sendChat, subscribe } from './ws-bridge.js';

subscribe('chat', (data) => {
    messages.push({
        id: Date.now(),
        role: data.role,
        text: data.text
    });
    renderMessages();
});

subscribe('gateway', (stateStr) => {
    isListening = stateStr === 'listening';
    isProcessing = stateStr === 'processing';
    isSpeaking = stateStr === 'speaking';
    updateOrbState();
});

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
    chatStatus.textContent = isProcessing ? 'Processing...' : isListening ? 'Listening...' : isSpeaking ? 'Speaking...' : 'Idle';

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
    renderMessages();

    // Send through bridge
    sendChat(text);
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

// ── WebSocket Bridge ───────────────────────────────────────
// Connects to Velvet Backend and streams state to the UI.

import { INITIAL_DEVICES, INITIAL_CONTEXTS, INITIAL_EVENTS } from './data.js';

let ws = null;
let _isConnected = false;
export function isConnected() { return _isConnected; }

// Shared state that UI components can read
export const state = {
    devices: [...INITIAL_DEVICES],
    contexts: [...INITIAL_CONTEXTS],
    agents: [],
    events: [...INITIAL_EVENTS],
    memoryGraph: null,
    gatewayState: "idle" // idle, listening, processing, speaking
};

// Event listeners for UI updates
const listeners = {
    'snapshot': [],
    'devices': [],
    'contexts': [],
    'events': [],
    'chat': [],
    'gateway': [],
    'memory': [],
    'jing.results': []
};

export function subscribe(event, callback) {
    if (listeners[event]) {
        listeners[event].push(callback);
    }
}

function notify(event, data) {
    if (listeners[event]) {
        listeners[event].forEach(cb => cb(data));
    }
}

export function connectBridge() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    console.log(`[Bridge] Connecting to ${wsUrl}...`);
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('[Bridge] Connected');
        _isConnected = true;
        document.body.classList.add('bridge-connected');
        // Update status badge
        const badge = document.getElementById('bridge-status');
        if (badge) {
            badge.className = 'bridge-status bridge-status--live';
            const label = badge.querySelector('.bridge-status__label');
            if (label) label.textContent = 'LIVE';
        }
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (e) {
            console.error('[Bridge] Failed to parse message', e);
        }
    };

    ws.onclose = () => {
        console.log('[Bridge] Disconnected. Reconnecting in 3s...');
        _isConnected = false;
        document.body.classList.remove('bridge-connected');
        // Update status badge
        const badge = document.getElementById('bridge-status');
        if (badge) {
            badge.className = 'bridge-status bridge-status--offline';
            const label = badge.querySelector('.bridge-status__label');
            if (label) label.textContent = 'MOCK';
        }
        setTimeout(connectBridge, 3000);
    };
    
    ws.onerror = (err) => {
        console.error('[Bridge] WebSocket Error', err);
    };
}

function handleMessage(msg) {
    const { type, data } = msg;

    switch (type) {
        case 'snapshot':
            state.devices = msg.devices || [];
            state.contexts = msg.workspaces || [];
            state.agents = msg.agents || [];
            state.memoryGraph = msg.memory || null;
            if (msg.events) state.events = msg.events;
            console.log('[Bridge] Received snapshot', state);
            notify('snapshot', state);
            notify('devices', state.devices);
            notify('contexts', state.contexts);
            if (state.memoryGraph) notify('memory', state.memoryGraph);
            break;

        case 'device.update':
            const idx = state.devices.findIndex(d => d.id === data.id);
            if (idx >= 0) {
                // Preserve UI xy if any
                const x = state.devices[idx].x;
                const y = state.devices[idx].y;
                state.devices[idx] = { ...data, x, y };
            } else {
                state.devices.push(data);
            }
            notify('devices', state.devices);
            break;

        case 'workspace.update':
            const cIdx = state.contexts.findIndex(c => c.id === data.id);
            if (cIdx >= 0) {
                const x = state.contexts[cIdx].x;
                const y = state.contexts[cIdx].y;
                state.contexts[cIdx] = { ...data, x, y };
            } else {
                state.contexts.push(data);
            }
            notify('contexts', state.contexts);
            break;
            
        case 'workspace.delete':
            state.contexts = state.contexts.filter(c => c.id !== msg.id);
            notify('contexts', state.contexts);
            break;

        case 'event.log':
            state.events.unshift(data);
            if (state.events.length > 100) state.events.pop(); // Keep buffer small
            notify('events', state.events);
            break;

        case 'chat.response':
            notify('chat', data);
            break;
            
        case 'gateway.state':
            state.gatewayState = msg.state;
            notify('gateway', state.gatewayState);
            break;
            
        case 'agent.update':
            // Will wire to agents view later
            break;

        case 'memory.update':
            state.memoryGraph = data;
            notify('memory', state.memoryGraph);
            break;

        case 'jing.results':
            notify('jing.results', data);
            break;
    }
}

// ── Outbound Commands ──────────────────────────────────────

function send(type, payload) {
    if (!_isConnected || !ws) {
        console.warn(`[Bridge] Cannot send '${type}' — not connected`);
        return false;
    }
    ws.send(JSON.stringify({ type, ...payload }));
    return true;
}

export function sendChat(text) {
    return send('chat.send', { text });
}

export function createWorkspace(name, track_type, subtype) {
    return send('workspace.create', { name, track_type, subtype });
}

export function deleteWorkspace(id) {
    return send('workspace.delete', { id });
}

export function updateAgent(agent_id, fields) {
    return send('agent.update', { agent_id, fields });
}

export function searchJing(query) {
    return send('jing.search', { query });
}

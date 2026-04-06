// ── App.js — Main Application Logic ────────────────────────
import {
  INITIAL_DEVICES, INITIAL_CONTEXTS, INITIAL_EVENTS
} from './data.js';
import {
  renderSilkPulseConnection, renderSilkPulseRadial, renderDormantSineConnection,
  renderOrganicStreamV4, drawNetworkNodes,
  getActiveColors, setActiveColors, hexToRgb
} from './canvas-animations.js';
import { openEntityPopup, openDevicePopup } from './entity-popups.js';
import { spawnPopup, closePopup, hasPopup, bringToFront } from './window-manager.js';

// ── SVG Icon Templates ─────────────────────────────────────
const ICONS = {
  cpu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>',
  glasses: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="15" r="4"/><circle cx="18" cy="15" r="4"/><path d="M14 15a2 2 0 0 0-4 0"/><path d="M2.5 13 5 7c.7-1.3 1.4-2 3-2"/><path d="M21.5 13 19 7c-.7-1.3-1.4-2-3-2"/></svg>',
  smartphone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/></svg>',
  camera: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>',
  server: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="8" x="2" y="2" rx="2" ry="2"/><rect width="20" height="8" x="2" y="14" rx="2" ry="2"/><line x1="6" x2="6.01" y1="6" y2="6"/><line x1="6" x2="6.01" y1="18" y2="18"/></svg>',
  bot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>',
  users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  wrench: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>',
  brain: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/><path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/></svg>',
  radio: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/><path d="M19.1 4.9C23 8.8 23 15.1 19.1 19"/></svg>',
  database: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/></svg>',
  layers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/></svg>',
  fileText: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>',
  mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>',
  video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5"/><rect x="2" y="6" width="14" height="12" rx="2"/></svg>',
  mapPin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/></svg>',
  activity: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>',
};

function getDeviceIcon(name) {
  if (name.includes('Glasses')) return ICONS.glasses;
  if (name.includes('Phone')) return ICONS.smartphone;
  if (name.includes('Cam')) return ICONS.camera;
  if (name.includes('Cluster')) return ICONS.server;
  return ICONS.cpu;
}

// ── State ──────────────────────────────────────────────────
let currentView = 'mesh';
let selectedContext = null;
let selectedDevice = null;
let events = [...INITIAL_EVENTS];
let devices = INITIAL_DEVICES.map(d => ({ ...d }));
const contexts = [...INITIAL_CONTEXTS];

const $ = id => document.getElementById(id);

// ── View Switching ─────────────────────────────────────────
function switchView(viewId) {
  currentView = viewId;
  // Set data-view on nav for CSS fabric-only visibility
  document.getElementById('floating-nav').setAttribute('data-view', viewId);
  document.querySelectorAll('.nav-item[data-view]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === viewId);
  });
  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `view-${viewId}`);
  });
  // Close dropdowns when switching views
  $('add-dropdown')?.classList.remove('open');
  $('delete-panel')?.classList.remove('open');
  deleteMode = false;
  document.querySelectorAll('.context-card.delete-selected').forEach(c => c.classList.remove('delete-selected'));
  if (viewId === 'memory') {
    import('./memory-graph.js').then(m => m.initMemoryGraph());
  }
}

document.querySelectorAll('.nav-item[data-view]').forEach(btn => {
  btn.addEventListener('click', () => {
    switchView(btn.dataset.view);
  });
});

// Set initial data-view on nav
document.getElementById('floating-nav').setAttribute('data-view', 'mesh');

// ── Add Context/Project Dropdown ───────────────────────────
const addBtn = $('nav-add');
const addDropdown = $('add-dropdown');
if (addBtn && addDropdown) {
  addBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    addDropdown.classList.toggle('open');
    $('delete-panel')?.classList.remove('open');
  });
}
$('add-context-btn')?.addEventListener('click', () => {
  addDropdown?.classList.remove('open');
  const id = `ctx_${Date.now()}`;
  const newCtx = {
    id, name: `New Context`, type: 'custom', subtype: 'context', status: 'idle', progress: 0,
    x: 200 + Math.random() * 600, y: 200 + Math.random() * 400,
    agents: [], humans: [], robots: [], hardware: [], artifacts: []
  };
  contexts.push(newCtx);
  renderMesh();
});
$('add-project-btn')?.addEventListener('click', () => {
  addDropdown?.classList.remove('open');
  const id = `ctx_${Date.now()}`;
  const newCtx = {
    id, name: `New Project`, type: 'project', subtype: 'project', status: 'active', progress: 0,
    x: 200 + Math.random() * 600, y: 200 + Math.random() * 400,
    agents: [], humans: [], robots: [], hardware: [], artifacts: []
  };
  contexts.push(newCtx);
  renderMesh();
});

// ── Delete Mode ────────────────────────────────────────────
let deleteMode = false;
const PROTECTED_CONTEXTS = ['Personal Context', 'Autonomous Hedgefund'];
const deleteBtn = $('nav-delete');
const deletePanel = $('delete-panel');

if (deleteBtn && deletePanel) {
  deleteBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    deleteMode = !deleteMode;
    deletePanel.classList.toggle('open', deleteMode);
    addDropdown?.classList.remove('open');
    if (!deleteMode) {
      document.querySelectorAll('.context-card.delete-selected').forEach(c => c.classList.remove('delete-selected'));
    }
  });
}
$('delete-cancel')?.addEventListener('click', () => {
  deleteMode = false;
  deletePanel?.classList.remove('open');
  document.querySelectorAll('.context-card.delete-selected').forEach(c => c.classList.remove('delete-selected'));
});
$('delete-confirm')?.addEventListener('click', () => {
  const selected = document.querySelectorAll('.context-card.delete-selected');
  const idsToDelete = Array.from(selected).map(el => el.dataset.ctxId).filter(Boolean);
  idsToDelete.forEach(id => {
    const idx = contexts.findIndex(c => c.id === id);
    if (idx !== -1) contexts.splice(idx, 1);
  });
  deleteMode = false;
  deletePanel?.classList.remove('open');
  renderMesh();
});

// Close dropdowns when clicking outside
document.addEventListener('click', (e) => {
  if (addDropdown?.classList.contains('open') && !addDropdown.contains(e.target) && e.target !== addBtn) {
    addDropdown.classList.remove('open');
  }
  if (deletePanel?.classList.contains('open') && !deletePanel.contains(e.target) && e.target !== deleteBtn && !e.target.closest('#nav-delete')) {
    // Don't close delete panel when clicking on context cards (for selection)
  }
});

// ── Settings Panel ─────────────────────────────────────────
const settingsBtn = $('nav-settings');
const settingsPanel = $('settings-panel');
let settingsOpen = false;

if (settingsBtn) {
  settingsBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    settingsOpen = !settingsOpen;
    settingsPanel.classList.toggle('open', settingsOpen);
    addDropdown?.classList.remove('open');
    deletePanel?.classList.remove('open');
  });
}

// Close settings when clicking outside
document.addEventListener('click', (e) => {
  if (settingsOpen && !settingsPanel.contains(e.target) && e.target !== settingsBtn) {
    settingsOpen = false;
    settingsPanel.classList.remove('open');
  }
});

// Color pickers
['c1', 'c2', 'c3'].forEach(key => {
  const picker = $(`color-${key}`);
  if (picker) {
    picker.addEventListener('input', () => {
      const rgb = hexToRgb(picker.value);
      if (rgb) {
        const colors = getActiveColors();
        colors[key] = rgb;
        setActiveColors(colors.c1, colors.c2, colors.c3);
        updateCSSAccentColors();
      }
    });
  }
});

// Dark/Light toggle
const themeToggle = $('theme-toggle');
if (themeToggle) {
  themeToggle.addEventListener('change', () => {
    document.documentElement.classList.toggle('light-mode', themeToggle.checked);
  });
}

function updateCSSAccentColors() {
  const c = getActiveColors();
  const root = document.documentElement.style;
  root.setProperty('--accent-purple', `rgb(${c.c1.r},${c.c1.g},${c.c1.b})`);
  root.setProperty('--accent-blue', `rgb(${c.c2.r},${c.c2.g},${c.c2.b})`);
  root.setProperty('--accent-cyan', `rgb(${c.c3.r},${c.c3.g},${c.c3.b})`);
  root.setProperty('--accent', `rgb(${c.c1.r},${c.c1.g},${c.c1.b})`);
  root.setProperty('--accent-dim', `rgba(${c.c1.r},${c.c1.g},${c.c1.b},0.1)`);
  root.setProperty('--accent-mid', `rgba(${c.c1.r},${c.c1.g},${c.c1.b},0.3)`);
  root.setProperty('--accent-glow', `rgba(${c.c1.r},${c.c1.g},${c.c1.b},0.2)`);
}

// ── Mesh Canvas: Pan & Zoom ────────────────────────────────
const meshWrapper = $('mesh-canvas-wrapper');
const meshCanvas = $('mesh-canvas');

let meshScale = 1;
let meshTranslateX = 0;
let meshTranslateY = 0;
let isPanning = false;
let panStartX = 0;
let panStartY = 0;

let opsMeshExpanded = false;

window.toggleOpsMeshSize = function () {
  const modal = $('ops-mesh-modal');
  if (!opsMeshExpanded) {
    opsMeshExpanded = true;
    modal.classList.add('open');
    if (selectedContext) renderOpsMesh(selectedContext, true);
  } else {
    opsMeshExpanded = false;
    modal.classList.remove('open');
    // Stop modal animation loop
    if (opsMeshModalAnimId) { cancelAnimationFrame(opsMeshModalAnimId); opsMeshModalAnimId = null; }
  }
}

let opsMeshModalAnimId = null;

function updateMeshTransform() {
  meshCanvas.style.transform = `translate(${meshTranslateX}px, ${meshTranslateY}px) scale(${meshScale})`;
}

meshWrapper.addEventListener('wheel', (e) => {
  e.preventDefault();
  const delta = e.deltaY > 0 ? 0.9 : 1.1;
  const newScale = Math.max(0.3, Math.min(3, meshScale * delta));
  const rect = meshWrapper.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  meshTranslateX = mx - (mx - meshTranslateX) * (newScale / meshScale);
  meshTranslateY = my - (my - meshTranslateY) * (newScale / meshScale);
  meshScale = newScale;
  updateMeshTransform();
}, { passive: false });

meshWrapper.addEventListener('mousedown', (e) => {
  if (e.target.closest('.context-card') || e.target.closest('.device-node')) return;
  isPanning = true;
  panStartX = e.clientX - meshTranslateX;
  panStartY = e.clientY - meshTranslateY;
  meshWrapper.style.cursor = 'grabbing';
});

window.addEventListener('mousemove', (e) => {
  if (!isPanning || activeDrag) return;
  meshTranslateX = e.clientX - panStartX;
  meshTranslateY = e.clientY - panStartY;
  updateMeshTransform();
});

window.addEventListener('mouseup', () => {
  isPanning = false;
  meshWrapper.style.cursor = 'grab';
});

// ── Mesh Connections Canvas Loop ───────────────────────────
const connectionsCanvas = $('mesh-connections-canvas');

// ── Drag & Drop Connection Logic (V4 Organic Stream) ──────
let activeDrag = null;

function getNodeCenter(selector, dataAttr, id) {
  const el = meshCanvas.querySelector(`[${dataAttr}="${id}"]`);
  if (!el) return null;
  const left = parseFloat(el.style.left) || 0;
  const top = parseFloat(el.style.top) || 0;
  const w = el.offsetWidth;
  const h = el.offsetHeight;
  return { x: left + w / 2, y: top + h / 2 };
}

meshCanvas.addEventListener('mousedown', (e) => {
  if (currentView !== 'mesh') return;
  // Convert click position to mesh-canvas local coordinates
  const rect = meshCanvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;

  // Check if click is near any context entity
  contexts.forEach(ctxNode => {
    const ctxCenter = getNodeCenter('.context-card', 'data-ctx-id', ctxNode.id);
    if (!ctxCenter) return;
    const dist = Math.sqrt((mx - ctxCenter.x) ** 2 + (my - ctxCenter.y) ** 2);
    if (dist < 180) { // Near the context card
      activeDrag = { startX: ctxCenter.x, startY: ctxCenter.y, currentX: mx, currentY: my, type: 'context', id: ctxNode.id, startTime: performance.now() };
    }
  });

  // Check if click is near any device
  devices.forEach(devNode => {
    const devCenter = getNodeCenter('.device-node', 'data-dev-id', devNode.id);
    if (!devCenter) return;
    const dist = Math.sqrt((mx - devCenter.x) ** 2 + (my - devCenter.y) ** 2);
    if (dist < 80) {
      activeDrag = { startX: devCenter.x, startY: devCenter.y, currentX: mx, currentY: my, type: 'device', id: devNode.id, startTime: performance.now() };
    }
  });
});

window.addEventListener('mousemove', (e) => {
  if (!activeDrag) return;
  const rect = meshCanvas.getBoundingClientRect();
  activeDrag.currentX = e.clientX - rect.left;
  activeDrag.currentY = e.clientY - rect.top;
});

window.addEventListener('mouseup', (e) => {
  if (activeDrag) {
    activeDrag = null;
  }
});


function renderMeshConnectionsLoop(time) {
  if (currentView !== 'mesh') {
    requestAnimationFrame(renderMeshConnectionsLoop);
    return;
  }

  const cw = meshCanvas.offsetWidth || 1200;
  const ch = meshCanvas.offsetHeight || 800;
  if (connectionsCanvas.width !== cw || connectionsCanvas.height !== ch) {
    connectionsCanvas.width = cw;
    connectionsCanvas.height = ch;
  }

  const ctx = connectionsCanvas.getContext('2d');
  ctx.clearRect(0, 0, cw, ch);

  // Context → Device connections (Jumble 1)
  contexts.forEach((ctxNode, i) => {
    const ctxCenter = getNodeCenter('.context-card', 'data-ctx-id', ctxNode.id);
    if (!ctxCenter) return;

    ctxNode.hardware.forEach((hw, j) => {
      const device = devices.find(d => d.name === hw.name);
      if (!device) return;
      const devCenter = getNodeCenter('.device-node', 'data-dev-id', device.id);
      if (!devCenter) return;

      // State-based: online devices get silky pulse, otherwise dormant sine
      if (device.status === 'online') {
        renderSilkPulseConnection(ctx, time, ctxCenter.x, ctxCenter.y, devCenter.x, devCenter.y, i * 100 + j, 1);
      } else {
        renderDormantSineConnection(ctx, time, ctxCenter.x, ctxCenter.y, devCenter.x, devCenter.y, i * 100 + j, 1);
      }
    });
  });

  // Device → Device connections (Jumble 0 — Standard Colors)
  const deviceLinks = [
    ['Jetson Thor', 'GPU Cluster'],
    ['Phone', 'Smart Glasses'],
    ['Jetson Thor', 'Workshop Cam']
  ];

  deviceLinks.forEach(([n1, n2], i) => {
    const d1 = devices.find(d => d.name === n1);
    const d2 = devices.find(d => d.name === n2);
    if (!d1 || !d2) return;
    const p1 = getNodeCenter('.device-node', 'data-dev-id', d1.id);
    const p2 = getNodeCenter('.device-node', 'data-dev-id', d2.id);
    if (!p1 || !p2) return;

    // Both online → silky pulse, otherwise dormant
    if (d1.status === 'online' && d2.status === 'online') {
      renderSilkPulseConnection(ctx, time, p1.x, p1.y, p2.x, p2.y, 500 + i, 0);
    } else {
      renderDormantSineConnection(ctx, time, p1.x, p1.y, p2.x, p2.y, 500 + i, 0);
    }
  });

  // Render active drag stream
  if (activeDrag) {
    const dragT = time - activeDrag.startTime;
    const intensity = Math.min(1, dragT / 1000); // 1s build up
    // Organic stream follows the cursor
    renderOrganicStreamV4(ctx, dragT, activeDrag.startX, activeDrag.startY, activeDrag.currentX, activeDrag.currentY, intensity, 888);
  }

  ctx.globalCompositeOperation = 'source-over';

  requestAnimationFrame(renderMeshConnectionsLoop);
}

requestAnimationFrame(renderMeshConnectionsLoop);

// ── Render Mesh: Context Cards ─────────────────────────────
function renderContextCards() {
  meshCanvas.querySelectorAll('.context-card').forEach(el => el.remove());

  contexts.forEach(ctx => {
    const card = document.createElement('div');
    card.className = `context-card${selectedContext?.id === ctx.id ? ' selected' : ''}`;
    card.style.left = `${ctx.x - 128}px`;
    card.style.top = `${ctx.y - 60}px`;
    card.dataset.ctxId = ctx.id;

    card.innerHTML = `
      <div class="context-card__header">
        <div class="context-card__title">${ctx.name}</div>
        <span class="context-card__status ${ctx.status}"></span>
      </div>
      <div class="context-card__type">${ctx.subtype === 'project' ? 'project' : ctx.type}</div>
      ${ctx.subtype === 'project' ? `<div class="context-card__progress-bar"><div class="context-card__progress-fill" style="width:${ctx.progress}%"></div></div>` : ''}
      <div class="context-card__meta">
        <span class="context-card__meta-item">${ICONS.bot} ${ctx.agents.length}</span>
        <span class="context-card__meta-item">${ICONS.users} ${ctx.humans.length}</span>
        <span class="context-card__meta-item">${ICONS.wrench} ${ctx.hardware.length}</span>
      </div>
    `;

    card.addEventListener('click', (e) => {
      e.stopPropagation();
      if (deleteMode) {
        // In delete mode, toggle selection (protect system contexts)
        if (PROTECTED_CONTEXTS.includes(ctx.name)) {
          card.classList.add('shake');
          setTimeout(() => card.classList.remove('shake'), 400);
          return;
        }
        card.classList.toggle('delete-selected');
        return;
      }
      openContextPanel(ctx);
    });

    meshCanvas.appendChild(card);
  });
}

// ── Render Mesh: Device Nodes ──────────────────────────────
function renderDeviceNodes() {
  meshCanvas.querySelectorAll('.device-node').forEach(el => el.remove());

  devices.forEach(device => {
    const node = document.createElement('div');
    node.className = `device-node${selectedDevice?.id === device.id ? ' selected' : ''}`;
    node.style.left = `${(device.x || 0) - 40}px`;
    node.style.top = `${(device.y || 0) - 40}px`;
    node.dataset.devId = device.id;

    const pingHtml = device.status === 'online' ? '<div class="device-node__ping"></div>' : '';

    node.innerHTML = `
      <div class="device-node__icon-box">
        ${pingHtml}
        ${getDeviceIcon(device.name)}
        <span class="device-node__status-dot ${device.status}"></span>
      </div>
      <div class="device-node__label">
        <div class="device-node__name">${device.name}</div>
        <div class="device-node__load">${device.load.toFixed(0)}% LOAD</div>
      </div>
    `;

    node.addEventListener('click', (e) => {
      e.stopPropagation();
      openDevicePopup(device, ICONS);
    });

    meshCanvas.appendChild(node);
  });
}

function renderMesh() {
  renderContextCards();
  renderDeviceNodes();
}

// ── Context Detail Popup ───────────────────────────────────
let opsMeshAnimIdMap = {}; // Maps popup ID to animation frame ID
let opsMeshEntitiesMap = {}; // Maps popup ID to entities payload for canvas animation

function badge(text, type) {
  return `<span class="popup-badge popup-badge--${type}">${text}</span>`;
}

export function openContextPanel(ctx) {
  selectedContext = ctx;
  selectedDevice = null;
  const id = `context-${ctx.id}`;

  if (hasPopup(id)) {
    bringToFront(id);
    return;
  }

  const isProject = ctx.subtype === 'project';
  const typeLabel = isProject ? 'PROJECT' : ctx.type.toUpperCase() + ' CONTEXT';
  const icon = ICONS.layers;

  let progressHtml = '';

  const artifactsHtml = ctx.artifacts?.length ? `
    <div class="popup-section">
      <div class="popup-section__label">Artifacts</div>
      <div style="display:flex;flex-direction:column;gap:4px;">
        ${ctx.artifacts.map(a => `<div class="artifact-item"><span class="font-medium">${a}</span>${ICONS.search}</div>`).join('')}
      </div>
    </div>
  ` : '';

  let customUiHtml = `<div class="context-placeholder">Context Interface</div>`;
  if (ctx.type === 'workshop') {
    customUiHtml = `
      <div class="workshop-preview">
        <div class="workshop-preview__bg">${ICONS.camera}</div>
        <div class="workshop-preview__live"><span class="workshop-preview__live-dot"></span> LIVE</div>
        <div class="workshop-preview__info">CAM-01 | 1080p | 30fps</div>
        <div class="workshop-preview__bbox"><span class="workshop-preview__bbox-label">PERSON 98%</span></div>
      </div>
    `;
  } else if (ctx.type === 'hedgefund') {
    customUiHtml = `<div class="hedgefund-placeholder"><div class="hedgefund-chart">[Trading Chart Widget]</div><div class="hedgefund-grid"><div>[P&amp;L]</div><div>[Risk Metrics]</div></div></div>`;
  }

  const opsMeshId = `ops-mesh-${id}`;
  const customUiBtnId = `btn-toggle-customui-${id}`;
  const customUiContainerId = `customui-container-${id}`;
  const fullscreenBtnId = `btn-fullscreen-${id}`;

  const launchIcon = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M13.5 10.5 21 3"/><path d="M16 3h5v5"/><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/></svg>`;
  const expandIcon = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>`;

  // Build the two-column compact header (matching entity-popups.js pattern)
  const statusBadgesHtml = badge('active', 'positive') + badge('trusted', 'positive');
  const metricBars = [];
  if (isProject && ctx.progress !== undefined) {
    metricBars.push(`<div style="display:flex;align-items:center;gap:6px;min-width:100px;">
      <span style="font-size:0.65rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;width:32px;flex-shrink:0;">PRG</span>
      <div style="flex:1;height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden;">
        <div style="width:${ctx.progress}%;height:100%;background:#22d3ee;border-radius:3px;transition:width 0.3s ease;"></div>
      </div>
      <span style="font-size:0.65rem;color:var(--text-secondary);font-family:var(--font-mono,'monospace');width:28px;text-align:right;">${ctx.progress}%</span>
    </div>`);
  }

  // Build bar columns (2 bars per column)
  let barsHtml = '';
  if (metricBars.length) {
    const columns = [];
    for (let i = 0; i < metricBars.length; i += 2) {
      const pair = metricBars.slice(i, i + 2);
      columns.push(`<div style="display:flex;flex-direction:column;gap:4px;min-width:120px;flex:1;">${pair.join('')}</div>`);
    }
    barsHtml = columns.join('');
  }

  const bodyHTML = `
    <div style="display:flex; gap:14px; align-items:center; margin-bottom:16px;">
      <div class="popup-entity-icon" style="flex-shrink:0; width:64px; height:64px; font-size:1.7rem; background:var(--accent-dim); border:1px solid var(--accent-mid); color:var(--accent)">
        ${icon}
      </div>
      <div style="display:flex; gap:12px; align-items:center; flex:1; min-width:0;">
        <div style="display:flex; flex-direction:column; gap:4px; flex-shrink:0;">
          ${statusBadgesHtml}
        </div>
        ${barsHtml ? `<div style="display:flex; gap:10px; flex:1; min-width:0;">${barsHtml}</div>` : ''}
      </div>
    </div>

    <div class="popup-section popup-section--mesh" style="margin-top:16px; border-top:1px solid var(--border); padding-top:16px; margin-bottom: 16px;">
      <div class="popup-section__label" style="display:flex; justify-content:space-between; align-items:center;">
        <span>Live Operations Mesh</span>
        <button class="icon-btn" id="${fullscreenBtnId}" title="Expand Mesh" style="background:transparent; border:none; color:var(--text-muted); cursor:pointer;">
          ${expandIcon}
        </button>
      </div>
      <div id="${opsMeshId}-container" class="ops-mesh-container" style="width:100%; height:250px; position:relative; background:rgba(0,0,0,0.2) !important; border-radius:var(--radius-lg); overflow:hidden; border:1px solid var(--border); transition: all 0.3s ease;">
        <div class="ops-mesh__lines" id="${opsMeshId}-lines"></div>
        <div id="${opsMeshId}-entities"></div>
      </div>
    </div>

    ${artifactsHtml}

    <div class="popup-section popup-section--launch" style="margin-top:16px; border-top:1px solid var(--border); padding-top:16px;">
      <button class="remote-ctrl-btn remote-ctrl-btn--positive" id="${customUiBtnId}" style="width:100%; justify-content:center;">
        ${launchIcon}
        <span>Launch</span>
      </button>
    </div>
  `;

  const popup = spawnPopup({
    id,
    title: ctx.name,
    typeLabel,
    width: 440,
    bodyHTML,
    icon,
    onClose: () => {
      if (selectedContext === ctx) selectedContext = null;
      renderContextCards();
      if (opsMeshAnimIdMap[id]) {
        cancelAnimationFrame(opsMeshAnimIdMap[id]);
        delete opsMeshAnimIdMap[id];
      }
      delete opsMeshEntitiesMap[id];
    }
  });

  // Ops Mesh is rendered immediately by default
  renderOpsMeshDynamic(ctx, opsMeshId);

  // Setup Fullscreen Toggle
  const fullscreenBtn = popup.querySelector(`#${fullscreenBtnId}`);
  const meshContainer = popup.querySelector(`#${opsMeshId}-container`);
  if (fullscreenBtn && meshContainer) {
    fullscreenBtn.addEventListener('click', () => {
      popup.classList.toggle('wm-popup--fullscreen');
      window.dispatchEvent(new Event('resize'));
    });
  }

  // Setup Custom UI Toggle (Landscape Popup)
  const toggleBtn = popup.querySelector(`#${customUiBtnId}`);

  toggleBtn.addEventListener('click', () => {
    const launchId = `ctx-ui-${id}`;
    if (hasPopup(launchId)) {
      bringToFront(launchId);
    } else {
      spawnPopup({
        id: launchId,
        title: `${ctx.name} Interface`,
        width: 800,
        bodyHTML: `<div id="ctx-panel-ui-landscape" style="display:flex; flex-direction:column; height: 100%; min-height:400px; padding-top:8px;">${customUiHtml}</div>`,
        icon
      });
    }
  });

  renderContextCards();
}

function closeContextPanel() {
  // Backwards compatibility, closes all context popups if null
  if (selectedContext) {
    closePopup(`context-${selectedContext.id}`);
  }
}

// ── Dynamic Operations Mesh (for popups) ───────────────────
function renderOpsMeshDynamic(ctx, opsMeshId) {
  const containerId = `${opsMeshId}-container`;
  const entitiesId = `${opsMeshId}-entities`;
  const linesId = `${opsMeshId}-lines`;
  const canvasId = `${opsMeshId}-canvas`;

  const entitiesContainer = $(entitiesId);
  const linesDiv = $(linesId);
  if (!entitiesContainer || !linesDiv) return;
  entitiesContainer.innerHTML = '';

  const cont = $(containerId);
  const cW = cont.offsetWidth || 560;
  const cH = cont.offsetHeight || 400;

  linesDiv.innerHTML = `<canvas id="${canvasId}" width="${cW}" height="${cH}" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;"></canvas>`;

  const allEntities = [
    ...ctx.agents.map(a => ({ ...a, entityType: 'agent', icon: ICONS.bot, color: 'var(--accent)', bg: 'var(--accent-dim)', border: 'var(--accent-mid)', state: a.status || 'active', trust: 'trusted' })),
    ...ctx.robots.map(r => ({ ...r, entityType: 'robot', icon: ICONS.cpu, color: 'var(--accent-blue)', bg: 'var(--accent-blue-dim)', border: 'var(--accent-blue-mid)', state: r.status || 'idle', trust: 'trusted' })),
    ...ctx.hardware.map(h => ({ ...h, entityType: 'hardware', icon: ICONS.wrench, color: 'var(--accent-cyan)', bg: 'var(--accent-cyan-dim)', border: 'var(--accent-cyan-mid)', state: h.status || 'offline', trust: 'untrusted' })),
    ...ctx.humans.map(h => ({ ...h, entityType: 'human', icon: ICONS.users, color: 'var(--color-amber)', bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.3)', state: h.status || 'active', trust: 'trusted' })),
  ];

  const radius = Math.min(cW, cH) * 0.35;
  const activeEntities = [];

  allEntities.forEach((entity, i) => {
    const angle = (i / allEntities.length) * Math.PI * 2 - Math.PI / 2;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;

    const entData = { x: cW / 2 + x, y: cH / 2 + y, angle, radius, state: entity.state, trust: entity.trust, type: entity.entityType };
    activeEntities.push(entData);

    const el = document.createElement('div');
    el.className = 'ops-mesh__entity';
    el.style.left = `calc(50% + ${x}px)`;
    el.style.top = `calc(50% + ${y}px)`;
    el.style.cursor = 'pointer';

    const pingHtml = (entity.state === 'active' || entity.state === 'processing')
      ? `<div class="entity-ping" style="border:1px solid ${entity.border}"></div>` : '';

    el.innerHTML = `
      <div class="ops-mesh__entity-icon" style="background:${entity.bg};border:1px solid ${entity.border};color:${entity.color}">
        ${pingHtml}
        ${entity.icon}
      </div>
      <div class="ops-mesh__entity-tooltip">
        <div class="entity-name" style="color:${entity.color}">${entity.name}</div>
        <div class="entity-task">${entity.task}</div>
      </div>
    `;

    el.addEventListener('click', (e) => {
      e.stopPropagation();
      openEntityPopup(entity, ICONS, devices);
    });

    entitiesContainer.appendChild(el);
  });

  const popupId = opsMeshId.replace('ops-mesh-', '');
  opsMeshEntitiesMap[popupId] = activeEntities;

  const ctxCanvas = $(canvasId)?.getContext('2d');

  function renderLoop(time) {
    const canvas = $(canvasId);
    if (!canvas) {
      delete opsMeshAnimIdMap[popupId];
      return;
    }

    // Auto-resize
    const mCont = $(containerId);
    if (mCont && (canvas.width !== mCont.offsetWidth || canvas.height !== mCont.offsetHeight)) {
      canvas.width = mCont.offsetWidth;
      canvas.height = mCont.offsetHeight;

      // Update entities positions
      const newRadius = Math.min(canvas.width, canvas.height) * 0.35;
      const ents = opsMeshEntitiesMap[popupId];
      if (ents) {
        entitiesContainer.childNodes.forEach((node, i) => {
          const x = Math.cos(ents[i].angle) * newRadius;
          const y = Math.sin(ents[i].angle) * newRadius;
          node.style.left = `calc(50% + ${x}px)`;
          node.style.top = `calc(50% + ${y}px)`;
          ents[i].x = canvas.width / 2 + x;
          ents[i].y = canvas.height / 2 + y;
          ents[i].radius = newRadius;
        });
      }
    }

    if (ctxCanvas && opsMeshEntitiesMap[popupId]) {
      ctxCanvas.clearRect(0, 0, canvas.width, canvas.height);
      const cx = canvas.width / 2;
      const cy = canvas.height / 2;
      const themeColors = getActiveColors();
      const ents = opsMeshEntitiesMap[popupId];

      ctxCanvas.lineWidth = 1.5;

      // Hubless P2P logic: connect each entity to the next to form a mesh ring,
      // and add some cross connections for active entities.
      for (let i = 0; i < ents.length; i++) {
        for (let j = i + 1; j < ents.length; j++) {
          const e1 = ents[i];
          const e2 = ents[j];

          // Connect adjacent nodes (ring) or cross connect active nodes
          const isRing = (j === i + 1) || (i === 0 && j === ents.length - 1);
          const isBothActive = e1.state === 'active' && e2.state === 'active';
          const isCrossConnect = isBothActive && (j === i + 2 || j === i + 3);

          if (isRing || isCrossConnect) {
            if (isBothActive) {
              renderSilkPulseConnection(ctxCanvas, time, e1.x, e1.y, e2.x, e2.y, i * 100 + j, 1);
            } else {
              renderDormantSineConnection(ctxCanvas, time, e1.x, e1.y, e2.x, e2.y, i * 100 + j, 1);
            }
          }
        }
      }
      ctxCanvas.setLineDash([]);
    }

    opsMeshAnimIdMap[popupId] = requestAnimationFrame(renderLoop);
  }

  opsMeshAnimIdMap[popupId] = requestAnimationFrame(renderLoop);
}

// ── Device Detail Panel ────────────────────────────────────
function openDevicePanel(device) {
  selectedDevice = device;
  selectedContext = null;
  const panel = $('device-panel');
  $('dev-panel-name').textContent = device.name;
  $('dev-panel-type').textContent = `${device.type} NODE`;
  $('dev-panel-id').textContent = device.id;

  const badge = $('dev-panel-badge');
  badge.className = `device-detail__icon-badge ${device.status}`;
  badge.innerHTML = getDeviceIcon(device.name);

  const body = $('dev-panel-body');
  const loadColor = device.load > 80 ? 'danger' : device.load > 50 ? 'warning' : 'accent';

  let powerHtml;
  if (device.battery !== undefined) {
    const batColor = device.battery < 20 ? 'danger' : 'accent';
    powerHtml = `<div class="metric-card"><div class="metric-card__header"><span>Battery</span><span class="font-mono">${device.battery}%</span></div><div class="metric-card__bar"><div class="metric-card__bar-fill ${batColor}" style="width:${device.battery}%"></div></div></div>`;
  } else {
    powerHtml = `<div class="metric-card"><div class="metric-card__header"><span>Power</span><span class="font-mono" style="color:var(--accent-purple)">Mains</span></div><div class="metric-card__bar"><div class="metric-card__bar-fill accent" style="width:100%"></div></div></div>`;
  }

  body.innerHTML = `
    <div class="metric-grid">
      <div class="metric-card"><div class="metric-card__header"><span>Compute Load</span><span class="font-mono">${device.load.toFixed(1)}%</span></div><div class="metric-card__bar"><div class="metric-card__bar-fill ${loadColor}" style="width:${device.load}%"></div></div></div>
      ${powerHtml}
    </div>
    <div>
      <div class="section-title">${ICONS.brain} Intelligence &amp; Capabilities</div>
      <div style="display:flex;flex-direction:column;gap:16px;">
        <div><p class="text-xs" style="color:var(--text-muted);margin-bottom:8px;">MODELS LOADED</p><div class="tag-list">${device.models.map(m => `<span class="tag tag--accent">${m}</span>`).join('')}</div></div>
        <div><p class="text-xs" style="color:var(--text-muted);margin-bottom:8px;">CAPABILITIES</p><div class="tag-list">${device.capabilities.map(c => `<span class="tag tag--muted">${c}</span>`).join('')}</div></div>
      </div>
    </div>
    <div>
      <div class="section-title">${ICONS.radio} Peripherals</div>
      <div>${device.peripherals.map(p => `<div class="peripheral-item"><span class="peripheral-item__name">${p.name}</span><span class="peripheral-item__status ${p.status}">${p.status}</span></div>`).join('')}</div>
    </div>
    <div>
      <div class="section-title">${ICONS.radio} Remote Control</div>
      <div style="display:flex;gap:12px;margin-top:8px;">
        <button class="remote-ctrl-btn remote-ctrl-btn--negative" title="App Launcher">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
          <span>App Launcher</span>
        </button>
        <button class="remote-ctrl-btn remote-ctrl-btn--positive" title="File Explorer">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>
          <span>File Explorer</span>
        </button>
      </div>
    </div>
  `;

  requestAnimationFrame(() => panel.classList.add('open'));
  renderDeviceNodes();
}

function closeDevicePanel() {
  selectedDevice = null;
  $('device-panel').classList.remove('open');
  renderDeviceNodes();
}

$('dev-panel-close').addEventListener('click', closeDevicePanel);

// Old entity-info popup and makeDraggable removed — now using window-manager.js

// ── Logs View ──────────────────────────────────────────────
function renderLogs() {
  const container = $('logs-container');
  container.innerHTML = events.map(ev => `
    <div class="log-entry ${ev.level}">
      <span class="log-entry__time">${ev.timestamp}</span>
      <span class="log-entry__source">[${ev.source}]</span>
      <span class="log-entry__type">${ev.type}</span>
      <span class="log-entry__content">${ev.content}</span>
    </div>
  `).join('');
  if (currentView === 'logs') container.scrollTop = container.scrollHeight;
}

// ── Live Simulation ────────────────────────────────────────
const EVENT_SOURCES = ['Smart Glasses', 'Phone Mic', 'Workshop Cam', 'GPS Module'];
const EVENT_TYPES = ['audio', 'video', 'gps', 'system'];
const EVENT_CONTENTS = ['Motion detected in peripheral', 'Background noise: typing', 'Location stable', 'Heart rate: 72bpm'];

setInterval(() => {
  const now = new Date();
  const timestamp = now.toLocaleTimeString('en-US', { hour12: false });
  events = [...events.slice(-49), {
    id: `ev_${Date.now()}`, timestamp,
    source: EVENT_SOURCES[Math.floor(Math.random() * EVENT_SOURCES.length)],
    type: EVENT_TYPES[Math.floor(Math.random() * EVENT_TYPES.length)],
    content: EVENT_CONTENTS[Math.floor(Math.random() * EVENT_CONTENTS.length)],
    level: Math.random() > 0.8 ? 'wake' : 'info'
  }];

  devices = devices.map(d => ({ ...d, load: Math.max(0, Math.min(100, d.load + (Math.random() * 10 - 5))) }));

  if (currentView === 'logs') renderLogs();
  if (currentView === 'mesh') {
    devices.forEach(d => {
      const node = meshCanvas.querySelector(`[data-dev-id="${d.id}"]`);
      if (node) {
        const loadEl = node.querySelector('.device-node__load');
        if (loadEl) loadEl.textContent = `${d.load.toFixed(0)}% LOAD`;
      }
    });
  }
}, 3500);

// ── Initial Render ─────────────────────────────────────────
renderMesh();
renderLogs();

requestAnimationFrame(() => {
  const wrapperRect = meshWrapper.getBoundingClientRect();
  meshTranslateX = (wrapperRect.width - 1200) / 2;
  meshTranslateY = (wrapperRect.height - 800) / 2;
  updateMeshTransform();
});

// ── Global Mouse Tooltip ───────────────────────────────────
const globalTooltip = document.getElementById('velvet-tooltip');
if (globalTooltip) {
  document.addEventListener('mousemove', (e) => {
    const target = e.target.closest('[data-tooltip]');
    if (target) {
      if (globalTooltip.style.display !== 'block') {
        globalTooltip.textContent = target.getAttribute('data-tooltip');
        globalTooltip.style.display = 'block';
      }
      globalTooltip.style.left = (e.clientX + 14) + 'px';
      globalTooltip.style.top = (e.clientY + 14) + 'px';
    } else {
      globalTooltip.style.display = 'none';
    }
  });
}

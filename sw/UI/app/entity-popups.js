// ── Entity Popup Templates ─────────────────────────────────
// Generates HTML body content for each entity type's floating popup.
// Uses the window manager (spawnPopup) to create independent windows.

import { spawnPopup } from './window-manager.js';

// ── SVG Icons (inline, small) ──────────────────────────────
const IC = {
  commandeer: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/></svg>',
  fileExplorer: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>',
  bringHere: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h18"/><path d="m9 6-6 6 6 6"/></svg>',
  sendTo: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h18"/><path d="m15 6 6 6-6 6"/></svg>',
  camera: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>',
  mic: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg>',
};

// ── Helpers ────────────────────────────────────────────────
function badge(text, type, hoverText = '') {
  const hoverAttr = hoverText ? `data-tooltip="${hoverText}"` : '';
  return `<span class="popup-badge popup-badge--${type}" ${hoverAttr}>${text}</span>`;
}

function statusBadge(status) {
  const s = (status || 'offline').toLowerCase();
  const type = (s === 'online' || s === 'active') ? 'positive' : (s === 'offline' ? 'neutral' : 'negative');
  return badge(s, type);
}

function trustBadge(trust) {
  const t = (trust || 'untrusted').toLowerCase();
  return badge(t, t === 'trusted' ? 'positive' : 'negative');
}

function kv(key, val) {
  return `<div class="popup-kv"><span class="popup-kv__key">${key}</span><span class="popup-kv__val">${val}</span></div>`;
}

function section(label, content) {
  return `<div class="popup-section"><div class="popup-section__label">${label}</div>${content}</div>`;
}

function tags(items, cls = 'tag tag--accent') {
  if (!items || !items.length) return '<span style="color:var(--text-muted);font-size:0.8rem;">None</span>';
  return `<div class="popup-tags">${items.map(t => `<span class="${cls}">${t}</span>`).join('')}</div>`;
}

function remoteControl(extraButtons = '') {
  return section('Remote Control', `
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <button class="remote-ctrl-btn remote-ctrl-btn--positive" title="Commandeer">${IC.commandeer}<span>Commandeer</span></button>
      <button class="remote-ctrl-btn remote-ctrl-btn--positive" title="File Explorer">${IC.fileExplorer}<span>File Explorer</span></button>
      ${extraButtons}
    </div>
  `);
}

function loadBar(label, value, color = 'accent') {
  const c = value > 80 ? 'danger' : value > 50 ? 'warning' : color;
  return `<div class="metric-card"><div class="metric-card__header"><span>${label}</span><span class="font-mono">${typeof value === 'number' ? value.toFixed(1) + '%' : value}</span></div><div class="metric-card__bar"><div class="metric-card__bar-fill ${c}" style="width:${typeof value === 'number' ? value : 0}%"></div></div></div>`;
}

// ── Two-column Compact Header ──────────────────────────────
// Column 1 (badges stacked): status, trust, location
// Column 2+ (bar pairs): compute load, mem, battery, progress — 2 per column
function miniBar(label, value, isDangerHigh = true) {
  const pct = typeof value === 'number' ? value : 0;
  const c = isDangerHigh ? (pct > 80 ? '#ef4444' : pct > 50 ? '#f59e0b' : '#22d3ee') : (pct < 20 ? '#ef4444' : '#22d3ee');
  return `<div style="display:flex;align-items:center;gap:6px;min-width:100px;">
    <span style="font-size:0.65rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;width:32px;flex-shrink:0;">${label}</span>
    <div style="flex:1;height:6px;background:var(--accent-cyan-mid);border-radius:3px;overflow:hidden;">
      <div style="width:${pct}%;height:100%;background:var(--accent-blue);border-radius:3px;transition:width 0.3s ease;"></div>
    </div>
    <span style="font-size:0.65rem;color:var(--text-secondary);font-family:var(--font-mono,'monospace');width:28px;text-align:right;">${pct}%</span>
  </div>`;
}

function compactHeader(icon, bg, border, color, statusBadgesHtml, metricBars = []) {
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

  return `
    <div style="display:flex; gap:14px; align-items:center; margin-bottom:16px;">
      <div class="popup-entity-icon" style="flex-shrink:0; width:64px; height:64px; font-size:1.7rem; background:${bg}; border:1px solid ${border}; color:${color}">
        ${icon}
      </div>
      <div style="display:flex; gap:12px; align-items:center; flex:1; min-width:0;">
        <div style="display:flex; flex-direction:column; gap:4px; flex-shrink:0;">
          ${statusBadgesHtml}
        </div>
        ${barsHtml ? `<div style="display:flex; gap:10px; flex:1; min-width:0;">${barsHtml}</div>` : ''}
      </div>
    </div>
  `;
}

// ── Device Popup (Computer / Sensor / Hybrid / IoT) ────────
export function openDevicePopup(device, ICONS) {
  const id = `device-${device.id}`;
  const typeLabels = { compute: 'COMPUTER', sensor: 'SENSOR', hybrid: 'HYBRID DEVICE', iot: 'IOT DEVICE' };
  const typeLabel = typeLabels[device.type] || device.type?.toUpperCase() || 'DEVICE';
  const status = device.status || 'online';
  const trust = device.trust || 'trusted';
  const locationCoords = device.location ? `${device.location[0].toFixed(4)}, ${device.location[1].toFixed(4)}` : '';
  const statusBadgesHtml = statusBadge(status) + trustBadge(trust) + (device.locationName ? badge(device.locationName, 'neutral', locationCoords) : '');
  const bars = [];
  if (device.load !== undefined) bars.push(miniBar('CPU', device.load, true));
  if (device.battery !== undefined) bars.push(miniBar('BAT', device.battery, false));

  const sensorBtns = (device.type === 'sensor' || device.type === 'hybrid') ? `
    ${section('Sensor Feeds', `
      <div style="display:flex;gap:8px;">
        <button class="remote-ctrl-btn remote-ctrl-btn--positive" style="flex:0">${IC.camera}<span>Camera</span></button>
        <button class="remote-ctrl-btn remote-ctrl-btn--positive" style="flex:0">${IC.mic}<span>Mic</span></button>
      </div>
    `)}
  ` : '';

  const body = `
    ${compactHeader(ICONS.cpu || '', 'var(--accent-dim)', 'var(--accent-mid)', 'var(--accent)', statusBadgesHtml, bars)}
    ${device.models?.length ? section('Models Loaded', tags(device.models)) : ''}
    ${device.capabilities?.length ? section('Capabilities', tags(device.capabilities, 'tag tag--muted')) : ''}
    ${device.peripherals?.length ? section('Peripherals', `
      <div>${device.peripherals.map(p => {
    let pcIcon = '';
    if (p.name.includes('Cam')) pcIcon = IC.camera;
    else if (p.name.includes('Mic')) pcIcon = IC.mic;
    const type = p.status === 'active' ? 'positive' : p.status === 'error' ? 'negative' : 'neutral';
    return `<div class="peripheral-item">
                <div style="display:flex;align-items:center;gap:6px;">${pcIcon} <span class="peripheral-item__name">${p.name}</span></div>
                ${badge(p.status, type, p.description || '')}
              </div>`;
  }).join('')}</div>
    `) : ''}
    ${sensorBtns}
    ${remoteControl()}
  `;

  spawnPopup({ id, title: device.name, typeLabel, width: 460, bodyHTML: body, icon: ICONS.cpu });
}

// ── Vehicle Popup ──────────────────────────────────────────
export function openVehiclePopup(device, ICONS) {
  const id = `vehicle-${device.id}`;
  const trust = device.trust || 'trusted';

  const locationCoords = device.location ? `${device.location[0].toFixed(4)}, ${device.location[1].toFixed(4)}` : '';
  const statusBadgesHtml = statusBadge(device.status) + trustBadge(trust) + (device.locationName ? badge(device.locationName, 'neutral', locationCoords) : '');
  const bars = [];
  if (device.load !== undefined) bars.push(miniBar('CPU', device.load, true));

  const body = `
    ${compactHeader(ICONS.cpu || '', 'var(--accent-blue-dim)', 'var(--accent-blue-mid)', 'var(--accent-blue)', statusBadgesHtml, bars)}
    ${device.capabilities?.length ? section('Capabilities', tags(device.capabilities, 'tag tag--muted')) : ''}
    ${remoteControl(`
      <button class="remote-ctrl-btn remote-ctrl-btn--neutral" title="Bring Here">${IC.bringHere}<span>Bring Here</span></button>
      <button class="remote-ctrl-btn remote-ctrl-btn--positive" title="Send To">${IC.sendTo}<span>Send To</span></button>
    `)}
  `;

  spawnPopup({ id, title: device.name, typeLabel: 'VEHICLE', width: 460, bodyHTML: body, icon: ICONS.cpu });
}

// ── Robot Popup ────────────────────────────────────────────
export function openRobotPopup(entity, ICONS) {
  const id = `robot-${entity.name?.replace(/\s+/g, '-') || 'unknown'}`;
  const trust = entity.trust || entity.trust_level || 'trusted';

  const statusBadgesHtml = statusBadge(entity.state || entity.status) + trustBadge(trust);
  const bars = [];
  if (entity.battery !== undefined) bars.push(miniBar('BAT', entity.battery, false));

  const body = `
    ${compactHeader(ICONS.cpu || '', 'var(--accent-blue-dim)', 'var(--accent-blue-mid)', 'var(--accent-blue)', statusBadgesHtml, bars)}
    ${kv('Current Task', entity.task || 'Idle')}
    ${entity.host ? kv('Host Controller', entity.host) : ''}
    ${remoteControl()}
  `;

  spawnPopup({ id, title: entity.name, typeLabel: 'ROBOT', width: 450, bodyHTML: body, icon: ICONS.cpu });
}

// ── Agent Popup (with Config tab) ──────────────────────────
export function openAgentPopup(entity, ICONS) {
  const id = `agent-${entity.name?.replace(/\s+/g, '-') || 'unknown'}`;
  const trust = entity.trust || 'trusted';
  const role = entity.role || 'worker';

  const statusBadgesHtml = statusBadge(entity.state || entity.status) + trustBadge(trust);

  const infoTab = `
    <div class="popup-tab-content active" data-tab="info">
      ${compactHeader(ICONS.bot || '', 'var(--accent-dim)', 'var(--accent-mid)', 'var(--accent)', statusBadgesHtml)}
      ${kv('Current Task', entity.task || 'No active task')}
      ${kv('Agent Type', entity.agent_type || entity.entityType || 'general')}
      ${entity.capabilities?.length ? section('Capabilities', tags(entity.capabilities)) : ''}
      ${section('Recent Activity', `
        <div style="font-size:0.8rem;color:var(--text-muted);font-style:italic;">Activity log will appear here</div>
        <button class="remote-ctrl-btn remote-ctrl-btn--neutral" style="flex:0;padding:8px 12px;"><span>Expand Log</span></button>
      `)}
    </div>
  `;

  const configTab = `
    <div class="popup-tab-content" data-tab="config">
      ${section('Identity', `
        ${kv('Agent ID', entity.agent_id || entity.name)}
        <div class="popup-kv"><span class="popup-kv__key">Agent Type</span><input type="text" value="${entity.agent_type || 'general'}" style="background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;padding:4px 8px;color:var(--text-primary);font-size:0.8rem;width:140px;"></div>
        <div class="popup-kv"><span class="popup-kv__key">Role</span><input type="text" value="${role}" style="background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;padding:4px 8px;color:var(--text-primary);font-size:0.8rem;width:140px;" placeholder="e.g. orchestrator, analyst"></div>
      `)}
      ${section('Capabilities', `
        ${tags(entity.capabilities || [])}
        <button class="remote-ctrl-btn remote-ctrl-btn--positive" style="flex:0;padding:6px 10px;font-size:0.7rem;"><span>+ Add Capability</span></button>
      `)}
      ${section('Custom Fields', `
        <div style="font-size:0.8rem;color:var(--text-muted);font-style:italic;">Custom fields coming in Sprint 11</div>
        <button class="remote-ctrl-btn remote-ctrl-btn--positive" style="flex:0;padding:6px 10px;font-size:0.7rem;"><span>+ Add Field</span></button>
      `)}
    </div>
  `;

  const bodyHTML = `
    <div class="popup-tabs">
      <button class="popup-tab active" data-target="info">Info</button>
      <button class="popup-tab" data-target="config">Config</button>
    </div>
    ${infoTab}
    ${configTab}
  `;

  const popup = spawnPopup({ id, title: entity.name, typeLabel: `AI AGENT · ${role}`, width: 440, bodyHTML, icon: ICONS.bot });

  // Wire tab switching
  if (popup) {
    popup.querySelectorAll('.popup-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        popup.querySelectorAll('.popup-tab').forEach(t => t.classList.remove('active'));
        popup.querySelectorAll('.popup-tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        const target = popup.querySelector(`[data-tab="${tab.dataset.target}"]`);
        if (target) target.classList.add('active');
      });
    });
  }
}

// ── Human Popup ────────────────────────────────────────────
export function openHumanPopup(entity, ICONS) {
  const id = `human-${entity.name?.replace(/\s+/g, '-') || 'unknown'}`;
  const trust = entity.trust || 'trusted';

  const statusBadgesHtml = statusBadge(entity.state || entity.status) + trustBadge(trust);

  const body = `
    ${compactHeader(ICONS.users || '', 'rgba(245,158,11,0.1)', 'rgba(245,158,11,0.3)', 'var(--color-amber, #f59e0b)', statusBadgesHtml)}
    ${kv('Current Task', entity.task || 'No active task')}
    ${section('Communication Channels', `
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <button class="remote-ctrl-btn remote-ctrl-btn--positive" style="flex:0;padding:8px 12px;"><span>📞 Call</span></button>
        <button class="remote-ctrl-btn remote-ctrl-btn--positive" style="flex:0;padding:8px 12px;"><span>💬 Text</span></button>
        <button class="remote-ctrl-btn remote-ctrl-btn--neutral" style="flex:0;padding:8px 12px;"><span>+ Add Channel</span></button>
      </div>
    `)}
    ${section('Activity Timeline', `
      <div style="font-size:0.8rem;color:var(--text-muted);font-style:italic;">Timeline will appear here</div>
      <button class="remote-ctrl-btn remote-ctrl-btn--neutral" style="flex:0;padding:8px 12px;"><span>Expand</span></button>
    `)}
  `;

  spawnPopup({ id, title: entity.name, typeLabel: 'HUMAN', width: 400, bodyHTML: body, icon: ICONS.users });
}

// ── Boundary / External Popup ──────────────────────────────
export function openBoundaryPopup(entity, ICONS) {
  const id = `boundary-${entity.name?.replace(/\s+/g, '-') || 'unknown'}`;

  const statusBadgesHtml = statusBadge(entity.state || 'offline') + trustBadge('untrusted');

  const body = `
    ${compactHeader(ICONS.radio || '', 'rgba(107,114,128,0.1)', 'rgba(107,114,128,0.3)', '#9ca3af', statusBadgesHtml)}
    ${kv('Connection Type', entity.connectionType || 'API')}
    ${kv('Endpoint', entity.endpoint || '—')}
    ${kv('Auth Status', entity.authStatus || 'none')}
    ${kv('Last Communication', entity.lastComm || '—')}
    ${kv('Data Flow', entity.dataFlow || 'bidirectional')}
    <button class="remote-ctrl-btn remote-ctrl-btn--neutral" style="flex:0;padding:8px 12px;"><span>Expand Details</span></button>
  `;

  spawnPopup({ id, title: entity.name, typeLabel: 'EXTERNAL', width: 400, bodyHTML: body, icon: ICONS.radio });
}

// ── Universal opener — routes to correct popup by entity type ──
export function openEntityPopup(entity, ICONS, devices) {
  const type = entity.entityType || entity.type || 'unknown';

  switch (type) {
    case 'hardware':
    case 'compute':
    case 'sensor':
    case 'hybrid':
    case 'iot':
    case 'other': {
      // Try to find the real device data for richer popup
      const matchDev = devices?.find(d => d.name === entity.name);
      if (matchDev) {
        if (matchDev.type === 'vehicle') openVehiclePopup(matchDev, ICONS);
        else openDevicePopup(matchDev, ICONS);
      } else {
        // Fallback with whatever data we have
        openDevicePopup({ ...entity, id: entity.name, type: type === 'hardware' ? 'compute' : type }, ICONS);
      }
      break;
    }
    case 'vehicle':
      openVehiclePopup(entity, ICONS);
      break;
    case 'robot':
      openRobotPopup(entity, ICONS);
      break;
    case 'agent':
      openAgentPopup(entity, ICONS);
      break;
    case 'human':
      openHumanPopup(entity, ICONS);
      break;
    case 'boundary':
    case 'external':
      openBoundaryPopup(entity, ICONS);
      break;
    default:
      openAgentPopup(entity, ICONS); // fallback
  }
}

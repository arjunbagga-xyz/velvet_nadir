// ── Window Manager ─────────────────────────────────────────
// Spawns, tracks, drags, resizes, stacks, and closes floating popup windows.

let _wmZIndex = 1200;
const _wmWindows = new Map(); // id → { el, zIndex }

const WM_MIN_W = 300;
const WM_MIN_H = 250;
const RESIZE_EDGE = 8; // px detection zone for resize handles

// ── Spawn a new popup window ───────────────────────────────
export function spawnPopup({ id, title, typeLabel = '', width = 420, bodyHTML = '', headerExtra = '', onClose = null, icon = null }) {
    // If already open, bring to front
    if (_wmWindows.has(id)) {
        bringToFront(id);
        return _wmWindows.get(id).el;
    }

    _wmZIndex += 1;
    const z = _wmZIndex;

    const popup = document.createElement('div');
    popup.className = 'wm-popup';
    popup.id = `wm-${id}`;
    popup.style.cssText = `
    position:fixed; z-index:${z};
    width:${width}px; min-width:${WM_MIN_W}px; min-height:${WM_MIN_H}px;
    top:${80 + (_wmWindows.size % 6) * 30}px;
    left:${120 + (_wmWindows.size % 6) * 30}px;
  `;

    const typeHtml = typeLabel ? `<span class="wm-popup__header-type" style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.05em; margin-top:2px; font-weight:600;">${typeLabel}</span>` : '';

    popup.innerHTML = `
    <div class="wm-popup__header" data-wm-drag>
      <div style="display:flex; align-items:baseline; gap:8px;">
        <span class="wm-popup__title">${title}</span>
        ${typeHtml}
      </div>
      <div class="wm-popup__header-right">
        ${headerExtra}
        <button class="wm-popup__close" data-wm-minimize title="Minimize">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 12h14"/>
          </svg>
        </button>
        <button class="wm-popup__close" data-wm-close title="Close">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18 6 6 18"/><path d="m6 6 12 12"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="wm-popup__body">${bodyHTML}</div>
    <div class="wm-resize-handle wm-resize-handle--se" data-wm-resize="se"></div>
    <div class="wm-resize-handle wm-resize-handle--e" data-wm-resize="e"></div>
    <div class="wm-resize-handle wm-resize-handle--s" data-wm-resize="s"></div>
  `;

    document.body.appendChild(popup);

    const entry = { el: popup, zIndex: z, onClose, title, typeLabel, icon };
    _wmWindows.set(id, entry);

    // ── Close button
    popup.querySelector('[data-wm-close]').addEventListener('click', () => closePopup(id));

    // ── Minimize button
    const minimizeBtn = popup.querySelector('[data-wm-minimize]');
    if (minimizeBtn) {
        minimizeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            minimizePopup(id);
        });
    }

    // ── Bring to front on any click
    popup.addEventListener('mousedown', () => bringToFront(id));

    // ── Drag by header
    _setupDrag(popup, popup.querySelector('[data-wm-drag]'));

    // ── Resize handles
    popup.querySelectorAll('[data-wm-resize]').forEach(handle => {
        _setupResize(popup, handle, handle.dataset.wmResize);
    });

    return popup;
}

// ── Close and remove a popup ───────────────────────────────
export function closePopup(id) {
    const entry = _wmWindows.get(id);
    if (!entry) return;
    if (entry.onClose) entry.onClose();
    entry.el.remove();
    _wmWindows.delete(id);
    _removeTaskbarIcon(id);
}

// ── Minimize a popup ───────────────────────────────────────
export function minimizePopup(id) {
    const entry = _wmWindows.get(id);
    if (!entry) return;
    entry.el.style.display = 'none';
    _addTaskbarIcon(id, entry);
}

// ── Restore a popup ────────────────────────────────────────
export function restorePopup(id) {
    const entry = _wmWindows.get(id);
    if (!entry) return;
    entry.el.style.display = 'flex';
    bringToFront(id);
    _removeTaskbarIcon(id);
}

// ── Taskbar Helpers ────────────────────────────────────────
function _addTaskbarIcon(id, entry) {
    const tb = document.getElementById('left-taskbar');
    if (!tb || tb.querySelector(`[data-tb-id="${id}"]`)) return;

    const btn = document.createElement('button');
    btn.className = 'nav-item nav-item--icon tb-icon';
    btn.dataset.tbId = id;
    btn.title = entry.title;

    // Auto-pick an icon based on typeLabel
    let svg = entry.icon || '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>';
    if (!entry.icon) {
        if (entry.typeLabel.includes('COMPUTER')) svg = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/></svg>';
        if (entry.typeLabel.includes('AGENT')) svg = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/></svg>';
        if (entry.typeLabel.includes('HUMAN')) svg = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>';
    }

    btn.innerHTML = svg;
    btn.addEventListener('click', () => {
        restorePopup(id);
    });
    tb.appendChild(btn);
}

function _removeTaskbarIcon(id) {
    const tb = document.getElementById('left-taskbar');
    if (!tb) return;
    const btn = tb.querySelector(`[data-tb-id="${id}"]`);
    if (btn) btn.remove();
}

// ── Bring to front ─────────────────────────────────────────
export function bringToFront(id) {
    const entry = _wmWindows.get(id);
    if (!entry) return;
    _wmZIndex += 1;
    entry.zIndex = _wmZIndex;
    entry.el.style.zIndex = _wmZIndex;
}

// ── Close topmost (for Escape key) ─────────────────────────
export function closeTopmost() {
    let topId = null, topZ = -1;
    for (const [id, entry] of _wmWindows) {
        if (entry.zIndex > topZ) { topZ = entry.zIndex; topId = id; }
    }
    if (topId) closePopup(topId);
}

// ── Update body content of existing popup ──────────────────
export function updatePopupBody(id, html) {
    const entry = _wmWindows.get(id);
    if (!entry) return;
    const body = entry.el.querySelector('.wm-popup__body');
    if (body) body.innerHTML = html;
}

// ── Check if popup exists ──────────────────────────────────
export function hasPopup(id) {
    return _wmWindows.has(id);
}

// ── Escape key listener ────────────────────────────────────
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeTopmost();
});

// ── Internal: Drag ─────────────────────────────────────────
function _setupDrag(popup, handle) {
    let isDragging = false, offsetX = 0, offsetY = 0;

    handle.addEventListener('mousedown', (e) => {
        if (e.target.closest('[data-wm-close]')) return;
        isDragging = true;
        const rect = popup.getBoundingClientRect();
        offsetX = e.clientX - rect.left;
        offsetY = e.clientY - rect.top;
        e.preventDefault();
    });

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        popup.style.left = Math.max(0, e.clientX - offsetX) + 'px';
        popup.style.top = Math.max(0, e.clientY - offsetY) + 'px';
    });

    window.addEventListener('mouseup', () => { isDragging = false; });
}

// ── Internal: Resize ───────────────────────────────────────
function _setupResize(popup, handle, dir) {
    let isResizing = false, startX, startY, startW, startH, startLeft, startTop;

    handle.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = popup.getBoundingClientRect();
        startW = rect.width;
        startH = rect.height;
        startLeft = rect.left;
        startTop = rect.top;
        e.preventDefault();
        e.stopPropagation();
    });

    window.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        const maxW = window.innerWidth * 0.95;
        const maxH = window.innerHeight * 0.95;

        if (dir.includes('e')) {
            popup.style.width = Math.min(maxW, Math.max(WM_MIN_W, startW + dx)) + 'px';
        }
        if (dir.includes('s')) {
            popup.style.height = Math.min(maxH, Math.max(WM_MIN_H, startH + dy)) + 'px';
        }
    });

    window.addEventListener('mouseup', () => { isResizing = false; });
}

/**
 * Notification System for Velvet Nadir
 * Handles Toasts, Notification Panel History, and Skill Approvals
 */

let toastId = 0;
let unreadCount = 0;

export function initNotifications() {
  const bell = document.getElementById('nav-bell');
  if (bell) {
    bell.addEventListener('click', toggleNotifPanel);
  }

  const clearBtn = document.getElementById('notif-clear-all');
  if (clearBtn) {
    clearBtn.addEventListener('click', clearAllNotifs);
  }

  const skillOverlay = document.getElementById('skill-overlay');
  if (skillOverlay) {
    skillOverlay.addEventListener('click', hideSkillApproval);
  }

  const skillClose = document.getElementById('skill-popup-close');
  if (skillClose) {
    skillClose.addEventListener('click', hideSkillApproval);
  }
}

export function showToast(type, icon, title, text, actionCallback = null) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const id = `toast-${toastId++}`;
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.id = id;
  toast.innerHTML = `
    <div class="toast__icon toast__icon--${type}">${icon}</div>
    <div class="toast__body">
      <div class="toast__title">${title}</div>
      <div class="toast__text">${text}</div>
      <div class="toast__time">just now</div>
    </div>
    <button class="toast__close">×</button>
    <div class="toast__progress"><div class="toast__progress-bar"></div></div>
  `;
  container.appendChild(toast);

  // Close logic
  const closeBtn = toast.querySelector('.toast__close');
  closeBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dismissToast(id);
  });

  if (actionCallback) {
    toast.addEventListener('click', () => {
      actionCallback();
      dismissToast(id);
    });
  } else {
    toast.addEventListener('click', () => dismissToast(id));
  }

  // Increment badge
  unreadCount++;
  updateBadge();
  addToHistory(type, icon, title, text);

  // Auto-dismiss after 5s
  setTimeout(() => dismissToast(id), 5000);
}

export function dismissToast(id) {
  const toast = document.getElementById(id);
  if (!toast) return;
  toast.classList.add('dismissing');
  setTimeout(() => toast.remove(), 300);
}

function updateBadge() {
  const badge = document.getElementById('bell-badge');
  if (!badge) return;
  
  if (unreadCount > 0) {
    badge.classList.remove('hidden');
    badge.textContent = unreadCount;
    // trigger animation
    badge.style.animation = 'none'; 
    badge.offsetHeight; 
    badge.style.animation = '';
  } else {
    badge.classList.add('hidden');
    badge.textContent = '0';
  }
}

export function toggleNotifPanel() {
  const panel = document.getElementById('notif-panel');
  if (!panel) return;
  
  panel.classList.toggle('open');
  if (panel.classList.contains('open')) {
    // Reset badge on open
    unreadCount = 0;
    updateBadge();
    
    // Mark all as read
    const items = document.querySelectorAll('.notif-item');
    items.forEach(i => i.classList.remove('unread'));
  }
}

export function clearAllNotifs() {
  const list = document.getElementById('notif-list');
  if (list) {
    list.innerHTML = '<div style="text-align:center;color:var(--text-muted);font-size:0.78rem;padding:40px 0;">No notifications</div>';
  }
  unreadCount = 0;
  updateBadge();
}

export function addToHistory(type, icon, title, text) {
  const list = document.getElementById('notif-list');
  if (!list) return;

  // clear empty message if needed
  if (list.querySelector('div[style*="text-align:center"]')) {
    list.innerHTML = '';
  }

  const bgMap = {
    'info': 'rgba(0,212,255,0.1)',
    'success': 'rgba(16,185,129,0.1)',
    'warning': 'rgba(245,158,11,0.1)',
    'danger': 'rgba(255,68,68,0.1)',
    'skill': 'rgba(99,102,241,0.1)'
  };
  const colorMap = {
    'info': '#00d4ff',
    'success': '#10b981',
    'warning': '#f59e0b',
    'danger': '#ff4444',
    'skill': '#6366f1'
  };

  const item = document.createElement('div');
  item.className = 'notif-item unread';
  item.innerHTML = `
    <div class="notif-item__icon" style="background:${bgMap[type] || bgMap.info};color:${colorMap[type] || colorMap.info};">${icon}</div>
    <div class="notif-item__body">
      <div class="notif-item__title">${title}</div>
      <div class="notif-item__text">${text}</div>
      <div class="notif-item__time">just now</div>
    </div>
  `;
  
  list.insertBefore(item, list.firstChild);
}

// Skill Approval API
export function showSkillApproval(skillData, onApprove, onReject) {
  const popup = document.getElementById('skill-popup');
  const overlay = document.getElementById('skill-overlay');
  if (!popup || !overlay) return;

  document.getElementById('skill-popup-title').textContent = skillData.name || 'Unknown Skill';
  document.getElementById('skill-popup-desc').textContent = skillData.description || 'No description provided.';
  document.getElementById('skill-popup-code').textContent = skillData.code || '# Code unavailable';
  
  document.getElementById('skill-popup-meta').innerHTML = `
    <span>📊 Confidence: ${skillData.confidence || '0.90'}</span>
    <span>⚡ Autonomy: Level ${skillData.autonomy || '1'}</span>
  `;

  popup.classList.remove('hidden');
  overlay.classList.add('active');

  // Close panel if open
  const panel = document.getElementById('notif-panel');
  if (panel) panel.classList.remove('open');

  // Wire buttons
  const approveBtn = document.getElementById('skill-popup-approve');
  const rejectBtn = document.getElementById('skill-popup-reject');

  // Clean old listeners
  const newApprove = approveBtn.cloneNode(true);
  approveBtn.parentNode.replaceChild(newApprove, approveBtn);
  const newReject = rejectBtn.cloneNode(true);
  rejectBtn.parentNode.replaceChild(newReject, rejectBtn);

  newApprove.addEventListener('click', () => {
    if(onApprove) onApprove();
    hideSkillApproval();
    showToast('success', '✓', 'Skill Deployed', `${skillData.name} is now active and available.`);
  });

  newReject.addEventListener('click', () => {
    if(onReject) onReject();
    hideSkillApproval();
  });
}

export function hideSkillApproval() {
  const popup = document.getElementById('skill-popup');
  const overlay = document.getElementById('skill-overlay');
  if (popup) popup.classList.add('hidden');
  if (overlay) overlay.classList.remove('active');
}

// Make accessible to window for easier testing/calling from other modules if needed
window.VelvetNotifs = {
  showToast,
  showSkillApproval
};

const toggle = document.getElementById('toggle');
const slider = document.getElementById('slider');
const delayValue = document.getElementById('delayValue');
const status = document.getElementById('status');

let enabled = false;
let delayMs = 1000;

chrome.storage.local.get(['enabled', 'delayMs'], (data) => {
  enabled = data.enabled || false;
  delayMs = data.delayMs || 1000;
  updateUI();
});

toggle.addEventListener('click', () => {
  enabled = !enabled;
  save();
  notifyTabs();
});

slider.addEventListener('input', () => {
  delayMs = parseInt(slider.value);
  updateUI();
});

slider.addEventListener('change', () => {
  delayMs = parseInt(slider.value);
  save();
  notifyTabs();
});

function updateUI() {
  slider.value = delayMs;
  delayValue.textContent = (delayMs / 1000).toFixed(1) + ' sn';
  toggle.classList.toggle('active', enabled);
  status.textContent = enabled ? 'Aktif - Video geciktiriliyor' : 'Kapali';
  status.className = 'status ' + (enabled ? 'on' : 'off');
}

function save() {
  chrome.storage.local.set({ enabled, delayMs });
  updateUI();
}

function notifyTabs() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { type: 'sync-update', enabled, delayMs });
    }
  });
}

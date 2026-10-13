// FOXSI Local AI Voice Assistant Dashboard Logic

let currentTab = 'dashboard-tab';
let pollInterval = null;
let downloadPollInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupVoiceControls();
  setupChat();
  setupModelHub();
  setupSettings();
  setupKeyboardShortcuts();

  // Initial data fetches
  refreshStatus();
  refreshModels();
  refreshTools();
  refreshHistory();
  loadSettings();

  // Start polling loops
  pollInterval = setInterval(refreshStatus, 1500);
});

// Toast notification helper
function showToast(message, duration = 3000) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

// Tab Navigation
function setupNavigation() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      switchTab(targetTab);
    });
  });
}

function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
  });
  document.querySelectorAll('.tab-view').forEach(view => {
    view.classList.toggle('active', view.id === tabId);
  });
}

// 1. Status & Telemetry
async function refreshStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const data = await res.json();
    const { assistant, system } = data;

    // Update Topbar
    document.getElementById('top-llm-name').textContent = assistant.current_model || 'No Model Loaded';
    document.getElementById('top-stt-status').textContent = assistant.stt_status;
    document.getElementById('top-tts-status').textContent = assistant.tts_status;
    document.getElementById('top-wakeword-status').textContent = assistant.wakeword_status;

    // Update Telemetry
    if (system && system.cpu) {
      const cpuUsage = system.cpu.usage_percent;
      document.getElementById('cpu-pill').textContent = `CPU: ${cpuUsage}%`;
      document.getElementById('metric-cpu-val').textContent = `${cpuUsage}%`;
      document.getElementById('cpu-bar').style.width = `${cpuUsage}%`;
      document.getElementById('metric-cpu-sub').textContent = `${system.cpu.physical_cores} Cores (${system.cpu.logical_cores} Threads)`;
    }

    if (system && system.memory) {
      const mem = system.memory;
      document.getElementById('ram-pill').textContent = `RAM: ${mem.used_gb} / ${mem.total_gb} GB`;
      document.getElementById('metric-ram-val').textContent = `${mem.used_gb} / ${mem.total_gb} GB`;
      document.getElementById('ram-bar').style.width = `${mem.usage_percent}%`;
      document.getElementById('metric-ram-sub').textContent = `${mem.usage_percent}% utilized (${mem.available_gb} GB free)`;
    }

    // Update Model Card
    document.getElementById('metric-model-name').textContent = assistant.current_model || 'None Loaded';
    document.getElementById('metric-model-size').textContent = assistant.current_model_size_mb 
      ? `Size: ${assistant.current_model_size_mb} MB` 
      : 'Size: -- MB';

    // Update Visualizer Orb State
    updateOrbState(assistant.state);

    // Update pending confirmations counter
    refreshConfirmations();
  } catch (err) {
    console.error('Failed to poll status:', err);
  }
}

function updateOrbState(state) {
  const orb = document.getElementById('voice-orb');
  const quickDot = document.getElementById('quick-status-dot');
  const quickText = document.getElementById('quick-status-text');
  const title = document.getElementById('assistant-state-title');
  const subtitle = document.getElementById('assistant-state-subtitle');
  const heroMicText = document.getElementById('hero-mic-btn-text');

  orb.className = 'visualizer-orb';
  document.getElementById('quick-ptt-btn').classList.remove('recording');

  switch (state) {
    case 'listening':
      orb.classList.add('state-listening');
      document.getElementById('quick-ptt-btn').classList.add('recording');
      quickDot.style.backgroundColor = '#f43f5e';
      quickText.textContent = 'Listening...';
      title.textContent = 'FOXSI is Listening...';
      subtitle.textContent = 'Speak your question or instruction clearly into your microphone.';
      heroMicText.textContent = 'Listening (Speak now)';
      break;
    case 'transcribing':
      orb.classList.add('state-thinking');
      quickDot.style.backgroundColor = '#06b6d4';
      quickText.textContent = 'Transcribing...';
      title.textContent = 'Processing Audio...';
      subtitle.textContent = 'Converting local microphone speech to text using faster-whisper.';
      heroMicText.textContent = 'Transcribing...';
      break;
    case 'thinking':
      orb.classList.add('state-thinking');
      quickDot.style.backgroundColor = '#06b6d4';
      quickText.textContent = 'Thinking...';
      title.textContent = 'FOXSI is Thinking...';
      subtitle.textContent = 'Generating intelligent response locally with GGUF model.';
      heroMicText.textContent = 'Thinking...';
      break;
    case 'speaking':
      orb.classList.add('state-speaking');
      quickDot.style.backgroundColor = '#10b981';
      quickText.textContent = 'Speaking...';
      title.textContent = 'FOXSI is Speaking...';
      subtitle.textContent = 'Playing synthesized voice through your PC speakers.';
      heroMicText.textContent = 'Speaking...';
      break;
    case 'error':
      quickDot.style.backgroundColor = '#f43f5e';
      quickText.textContent = 'Error';
      title.textContent = 'System Notice';
      subtitle.textContent = 'Check logs or verify local model status.';
      heroMicText.textContent = 'Push To Talk';
      break;
    default:
      quickDot.style.backgroundColor = '#10b981';
      quickText.textContent = 'Assistant Ready';
      title.textContent = 'FOXSI is Ready';
      subtitle.textContent = 'Speak freely or press Push-to-Talk. Fully local AI on your Windows machine.';
      heroMicText.textContent = 'Push To Talk';
      break;
  }
}

// 2. Voice Controls
function setupVoiceControls() {
  const triggerListen = async () => {
    try {
      showToast('Microphone activated. Listening...');
      await fetch('/api/voice/listen', { method: 'POST' });
    } catch (e) {
      showToast('Error activating microphone');
    }
  };

  const triggerStop = async () => {
    try {
      await fetch('/api/voice/stop', { method: 'POST' });
      showToast('Audio stopped');
    } catch (e) {
      console.error(e);
    }
  };

  document.getElementById('hero-mic-btn').addEventListener('click', triggerListen);
  document.getElementById('quick-ptt-btn').addEventListener('click', triggerListen);
  document.getElementById('chat-mic-btn').addEventListener('click', triggerListen);

  document.getElementById('hero-stop-btn').addEventListener('click', triggerStop);
  document.getElementById('quick-stop-speech-btn').addEventListener('click', triggerStop);
}

// 3. Chat Interaction
function setupChat() {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input-field');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    appendMessage('user', text);

    const autoSpeak = document.getElementById('auto-speak-toggle').checked;

    // Assistant placeholder
    const msgId = 'msg-' + Date.now();
    appendMessage('assistant', '...', null, msgId);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, speak: autoSpeak })
      });

      const data = await res.json();
      const el = document.getElementById(msgId);
      if (el) {
        const textEl = el.querySelector('.msg-text');
        textEl.textContent = data.response || 'No response generated.';

        if (data.tool_executed) {
          const toolBox = document.createElement('div');
          toolBox.className = 'tool-badge-box';
          toolBox.textContent = `⚡ Tool Executed: ${data.tool_executed.tool || 'Action'} -> ${JSON.stringify(data.tool_executed.result || {})}`;
          el.querySelector('.msg-body').appendChild(toolBox);
        }
      }
    } catch (err) {
      const el = document.getElementById(msgId);
      if (el) {
        el.querySelector('.msg-text').textContent = 'Error connecting to local server.';
      }
    }
  });

  document.getElementById('clear-chat-btn').addEventListener('click', async () => {
    if (confirm('Clear local conversation history?')) {
      await fetch('/api/memory/history', { method: 'DELETE' });
      document.getElementById('chat-messages-box').innerHTML = '';
      showToast('Conversation cleared');
    }
  });

  document.getElementById('export-chat-btn').addEventListener('click', async () => {
    const res = await fetch('/api/memory/export');
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `foxsi_memory_${Date.now()}.json`;
    a.click();
    showToast('Memory exported to JSON');
  });
}

function appendMessage(role, text, toolCall = null, elementId = null) {
  const container = document.getElementById('chat-messages-box');
  const div = document.createElement('div');
  div.className = `message ${role}-msg`;
  if (elementId) div.id = elementId;

  const avatar = role === 'user' ? '👤' : '🦊';
  const author = role === 'user' ? 'You' : 'FOXSI';

  div.innerHTML = `
    <div class="msg-avatar">${avatar}</div>
    <div class="msg-body">
      <div class="msg-author">${author}</div>
      <div class="msg-text">${escapeHtml(text)}</div>
    </div>
  `;

  if (toolCall) {
    const toolBox = document.createElement('div');
    toolBox.className = 'tool-badge-box';
    toolBox.textContent = `⚡ Tool: ${toolCall.tool || 'Action'} (${JSON.stringify(toolCall.result || {})})`;
    div.querySelector('.msg-body').appendChild(toolBox);
  }

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function refreshHistory() {
  try {
    const res = await fetch('/api/memory/history?limit=20');
    if (!res.ok) return;
    const data = await res.json();
    const box = document.getElementById('chat-messages-box');
    box.innerHTML = '';

    if (data.history && data.history.length > 0) {
      data.history.forEach(m => {
        appendMessage(m.role, m.content, m.tool_calls);
      });
    } else {
      appendMessage('assistant', 'Hello! I am FOXSI, your local AI assistant running on this PC. How can I help you today?');
    }
  } catch (e) {
    console.error('Failed to load history:', e);
  }
}

// 4. Model Hub
function setupModelHub() {
  document.getElementById('refresh-models-btn').addEventListener('click', () => {
    refreshModels();
    showToast('Local models scanned');
  });

  document.getElementById('unload-model-btn').addEventListener('click', async () => {
    try {
      await fetch('/api/models/unload', { method: 'POST' });
      showToast('Model unloaded');
      refreshModels();
      refreshStatus();
    } catch (e) {
      showToast('Failed to unload model');
    }
  });

  document.getElementById('cancel-download-btn').addEventListener('click', async () => {
    await fetch('/api/models/download/cancel', { method: 'POST' });
    showToast('Download cancelled');
    document.getElementById('download-progress-card').style.display = 'none';
  });
}

async function refreshModels() {
  try {
    const res = await fetch('/api/models');
    if (!res.ok) return;
    const { local_models, catalog, download_status } = await res.json();

    // Check active model banner
    const active = local_models.find(m => m.is_loaded);
    const banner = document.getElementById('active-model-banner');
    if (active) {
      banner.style.display = 'flex';
      document.getElementById('active-model-title').textContent = active.name;
      document.getElementById('active-model-desc').textContent = `Size: ${active.size_mb} MB | Path: ${active.relative_path}`;
    } else {
      document.getElementById('active-model-title').textContent = 'No Model Loaded';
      document.getElementById('active-model-desc').textContent = 'Select a model below to load into memory.';
    }

    // Render Local Models Grid
    const localGrid = document.getElementById('local-models-grid');
    localGrid.innerHTML = '';

    if (local_models.length === 0) {
      localGrid.innerHTML = '<p class="empty-state">No .gguf files in models/ folder. You can download one below or copy .gguf files to models/.</p>';
    } else {
      local_models.forEach(m => {
        const card = document.createElement('div');
        card.className = 'model-card';
        card.innerHTML = `
          <div class="model-card-header">
            <span class="model-card-title">${m.name}</span>
            <span class="badge ${m.is_loaded ? 'offline-badge' : ''}">${m.is_loaded ? 'Active' : 'Ready'}</span>
          </div>
          <div class="model-card-meta">${m.size_mb} MB</div>
          <div class="model-card-actions">
            ${m.is_loaded 
              ? `<button class="danger-btn" onclick="unloadModel()">Unload</button>`
              : `<button class="primary-btn" onclick="loadModel('${m.relative_path}')">Load Model</button>`}
          </div>
        `;
        localGrid.appendChild(card);
      });
    }

    // Render Catalog
    const catalogGrid = document.getElementById('catalog-models-grid');
    catalogGrid.innerHTML = '';
    catalog.forEach(item => {
      const card = document.createElement('div');
      card.className = 'model-card';
      card.innerHTML = `
        <div class="model-card-header">
          <span class="model-card-title">${item.name}</span>
          <span class="badge">${item.is_downloaded ? 'Installed' : 'Public'}</span>
        </div>
        <div class="model-card-meta">~${item.size_mb} MB</div>
        <p class="model-card-desc">${item.description}</p>
        <div class="model-card-actions">
          ${item.is_downloaded 
            ? (item.is_loaded ? '<span class="badge offline-badge">Currently Loaded</span>' : `<button class="primary-btn" onclick="loadModel('models/${item.filename}')">Load Model</button>`)
            : `<button class="secondary-btn" onclick="downloadCatalogModel('${item.id}')">Download GGUF</button>`}
        </div>
      `;
      catalogGrid.appendChild(card);
    });

    // Handle ongoing download
    handleDownloadProgress(download_status);

  } catch (err) {
    console.error('Failed to refresh models:', err);
  }
}

async function loadModel(path) {
  showToast(`Loading model ${path}...`);
  try {
    const res = await fetch('/api/models/load', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });
    if (!res.ok) {
      const err = await res.json();
      showToast(`Error: ${err.detail || 'Could not load model'}`);
      return;
    }
    showToast('Model loaded successfully!');
    refreshModels();
    refreshStatus();
  } catch (e) {
    showToast('Failed to load model: ' + e);
  }
}

async function unloadModel() {
  await fetch('/api/models/unload', { method: 'POST' });
  showToast('Model unloaded');
  refreshModels();
  refreshStatus();
}

async function downloadCatalogModel(modelId) {
  showToast('Initiating model download...');
  try {
    await fetch('/api/models/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId })
    });
    // Start download polling
    if (!downloadPollInterval) {
      downloadPollInterval = setInterval(pollDownloadStatus, 1000);
    }
  } catch (e) {
    showToast('Failed to start download: ' + e);
  }
}

async function pollDownloadStatus() {
  const res = await fetch('/api/models/download/status');
  const data = await res.json();
  handleDownloadProgress(data.download);
}

function handleDownloadProgress(download) {
  const card = document.getElementById('download-progress-card');
  if (!download || download.status === 'completed' || download.status === 'failed' || download.status === 'cancelled') {
    card.style.display = 'none';
    if (downloadPollInterval && (!download || download.status !== 'downloading')) {
      clearInterval(downloadPollInterval);
      downloadPollInterval = null;
      refreshModels();
    }
    return;
  }

  card.style.display = 'flex';
  document.getElementById('download-title').textContent = `Downloading ${download.filename}...`;
  document.getElementById('download-progress-fill').style.width = `${download.progress_pct}%`;
  document.getElementById('download-pct').textContent = `${download.progress_pct}%`;
  document.getElementById('download-speed').textContent = `${download.speed_mbps} MB/s`;
}

// 5. Tools & Permissions
async function refreshTools() {
  try {
    const res = await fetch('/api/tools');
    if (!res.ok) return;
    const { tools } = await res.json();
    const grid = document.getElementById('tools-catalog-grid');
    grid.innerHTML = '';

    tools.forEach(t => {
      const card = document.createElement('div');
      card.className = 'tool-card';
      const permColor = t.permission === 'SAFE' ? 'offline-badge' : 'badge';
      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span class="tool-card-title">${t.name}</span>
          <span class="badge ${permColor}">${t.permission}</span>
        </div>
        <p class="tool-card-desc">${t.description}</p>
      `;
      grid.appendChild(card);
    });
  } catch (e) {
    console.error('Failed to load tools:', e);
  }
}

async function refreshConfirmations() {
  try {
    const res = await fetch('/api/tools/confirmations');
    if (!res.ok) return;
    const { pending } = await res.json();
    const container = document.getElementById('confirmations-list');
    const badge = document.getElementById('pending-counter');

    if (pending && pending.length > 0) {
      badge.style.display = 'inline-block';
      badge.textContent = pending.length;
      container.innerHTML = '';

      pending.forEach(req => {
        const card = document.createElement('div');
        card.className = 'confirmation-card';
        card.innerHTML = `
          <div class="confirmation-meta">
            <h4>Confirmation Required: ${req.tool_name}</h4>
            <p>${req.description}</p>
          </div>
          <div class="confirmation-actions">
            <button class="small-success-btn" onclick="resolveConfirmation('${req.id}', true)">Approve</button>
            <button class="small-danger-btn" onclick="resolveConfirmation('${req.id}', false)">Reject</button>
          </div>
        `;
        container.appendChild(card);
      });
    } else {
      badge.style.display = 'none';
      container.innerHTML = '<p class="empty-state">No pending confirmation requests. System is secure.</p>';
    }
  } catch (e) {
    console.error(e);
  }
}

async function resolveConfirmation(id, approved) {
  try {
    await fetch(`/api/tools/confirmations/${id}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved })
    });
    showToast(approved ? 'Action Approved & Executed' : 'Action Rejected');
    refreshConfirmations();
  } catch (e) {
    showToast('Failed to resolve confirmation');
  }
}

// 6. Settings
async function loadSettings() {
  try {
    const [settRes, devRes] = await Promise.all([
      fetch('/api/settings'),
      fetch('/api/devices')
    ]);

    const settings = await settRes.json();
    const devices = await devRes.json();

    // Populate Assistant Identity
    document.getElementById('set-assistant-name').value = settings.assistant.name;
    document.getElementById('set-response-style').value = settings.assistant.response_style;
    document.getElementById('set-system-prompt').value = settings.assistant.system_prompt;

    // Populate LLM Settings
    document.getElementById('set-temperature').value = settings.llm.temperature;
    document.getElementById('temp-val').textContent = settings.llm.temperature;
    document.getElementById('set-context-size').value = settings.llm.context_size;
    document.getElementById('set-max-tokens').value = settings.llm.max_tokens;
    document.getElementById('set-cpu-threads').value = settings.llm.threads;
    document.getElementById('set-gpu-layers').value = settings.llm.gpu_layers;

    // Populate STT
    document.getElementById('set-stt-model').value = settings.stt.model;
    document.getElementById('set-silence-duration').value = settings.stt.silence_duration_seconds;

    // Populate Microphones
    const micSelect = document.getElementById('set-mic-device');
    micSelect.innerHTML = '<option value="">Default System Microphone</option>';
    if (devices.microphones) {
      devices.microphones.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = `${m.name} (Dev ${m.id})`;
        if (settings.stt.microphone_index === m.id) opt.selected = true;
        micSelect.appendChild(opt);
      });
    }

    // Populate TTS
    document.getElementById('set-tts-engine').value = settings.tts.engine;
    const voiceSelect = document.getElementById('set-tts-voice');
    voiceSelect.innerHTML = '';
    if (devices.voices && devices.voices.piper) {
      devices.voices.piper.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.path;
        opt.textContent = `${v.name} (Piper Neural)`;
        if (settings.tts.voice_model.includes(v.id)) opt.selected = true;
        voiceSelect.appendChild(opt);
      });
    }

    // Populate Wake Word
    document.getElementById('set-wakeword-enabled').value = settings.wakeword.enabled ? 'true' : 'false';
    document.getElementById('set-wakeword-model').value = settings.wakeword.model_name;

    // Temperature slider sync
    document.getElementById('set-temperature').addEventListener('input', (e) => {
      document.getElementById('temp-val').textContent = e.target.value;
    });

  } catch (e) {
    console.error('Failed to load settings:', e);
  }
}

function setupSettings() {
  document.getElementById('save-settings-btn').addEventListener('click', async () => {
    const micVal = document.getElementById('set-mic-device').value;
    const updates = {
      assistant: {
        name: document.getElementById('set-assistant-name').value,
        response_style: document.getElementById('set-response-style').value,
        system_prompt: document.getElementById('set-system-prompt').value,
      },
      llm: {
        temperature: parseFloat(document.getElementById('set-temperature').value),
        context_size: parseInt(document.getElementById('set-context-size').value, 10),
        max_tokens: parseInt(document.getElementById('set-max-tokens').value, 10),
        threads: parseInt(document.getElementById('set-cpu-threads').value, 10),
        gpu_layers: parseInt(document.getElementById('set-gpu-layers').value, 10),
      },
      stt: {
        model: document.getElementById('set-stt-model').value,
        microphone_index: micVal === '' ? null : parseInt(micVal, 10),
        silence_duration_seconds: parseFloat(document.getElementById('set-silence-duration').value),
      },
      tts: {
        engine: document.getElementById('set-tts-engine').value,
        voice_model: document.getElementById('set-tts-voice').value,
      },
      wakeword: {
        enabled: document.getElementById('set-wakeword-enabled').value === 'true',
        model_name: document.getElementById('set-wakeword-model').value,
      }
    };

    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      if (res.ok) {
        showToast('Settings saved successfully!');
        refreshStatus();
      } else {
        showToast('Failed to save settings.');
      }
    } catch (e) {
      showToast('Error saving settings: ' + e);
    }
  });
}

// 7. Keyboard Shortcuts (Push-to-Talk via Spacebar when not in text input)
function setupKeyboardShortcuts() {
  window.addEventListener('keydown', (e) => {
    // If user is focused on an input/textarea, do not capture space
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
      return;
    }

    if (e.code === 'Space' && !e.repeat) {
      e.preventDefault();
      fetch('/api/voice/listen', { method: 'POST' });
      showToast('Push-to-Talk triggered (Spacebar)');
    } else if (e.code === 'Escape') {
      fetch('/api/voice/stop', { method: 'POST' });
    }
  });
}

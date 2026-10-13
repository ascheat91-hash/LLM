# FOXSI — Local AI Voice Assistant for Windows PC

A privacy-first, fully local AI Voice Assistant engineered specifically for Windows. FOXSI runs the entire AI inference pipeline on your local machine with zero mandatory cloud dependencies.

```
MICROPHONE ──► Push-to-Talk / Wake Word ──► faster-whisper (STT) ──► Conversation Manager (SQLite)
                                                                             │
SPEAKERS   ◄── Piper Neural TTS (voices/) ◄── Response Text ◄── Local LLM (GGUF) ◄── Tool Router
```

---

## 1. What the Project Is

FOXSI is a standalone desktop AI voice assistant running on your Windows PC. It allows you to:
- **Hear You Locally**: Captures speech from your microphone and transcribes it using `faster-whisper` (int8 CPU quantization).
- **Think Locally**: Executes GGUF models (e.g. Qwen 2.5, Phi 3.5 Mini, Gemma 2) locally using `llama-cpp-python` without sending prompts to any third-party server.
- **Control Windows Safely**: Executes approved system utilities (CPU/RAM telemetry, open applications, search files, check time) while blocking dangerous exploits and prompting for human confirmation before executing high-impact actions.
- **Speak Naturally**: Synthesizes speech locally using high-fidelity Piper Neural TTS (`.onnx`) with an instant Windows SAPI5 (`pyttsx3`) zero-download fallback.
- **Modern Local Control Panel**: Access all controls, telemetry, chat history, and GGUF model management at `http://127.0.0.1:8000`.

---

## 2. Architecture & Pipeline

```
FOXSI-Voice-Assistant/
├── app/
│   ├── main.py                  # FastAPI server & static file host
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py            # REST & SSE endpoints
│   ├── core/
│   │   ├── diagnostics.py       # Hardware and environment audit
│   │   ├── logger.py            # Rotating logs with sensitive data redaction
│   │   ├── state.py             # Global assistant runtime state
│   │   └── system_info.py       # Hardware telemetry (CPU, RAM, GPU, audio)
│   ├── llm/
│   │   ├── engine.py            # LLMEngine abstraction over llama.cpp
│   │   ├── model_manager.py     # GGUF discovery, validator, catalog downloader
│   │   └── prompts.py           # System prompts and tool instruction builder
│   ├── speech/
│   │   ├── stt.py               # SpeechRecognizer (faster-whisper + sounddevice)
│   │   ├── tts.py               # SpeechSynthesizer (Piper TTS + pyttsx3 fallback)
│   │   └── wakeword.py          # WakeWordEngine (openWakeWord)
│   ├── tools/
│   │   ├── permissions.py       # Permission levels (SAFE, CONFIRM, BLOCKED)
│   │   ├── router.py            # Tool call parser & execution dispatcher
│   │   └── system_tools.py      # Windows automation tools (calc, explorer, cpu, etc.)
│   ├── memory/
│   │   └── database.py          # SQLite repository (history, prefs, long-term memory)
│   ├── config/
│   │   └── settings.py          # Pydantic & YAML settings manager
│   └── services/
│       └── assistant_service.py # Core end-to-end voice loop orchestrator
├── frontend/
│   ├── index.html               # Responsive modern control panel
│   ├── style.css                # Glassmorphic dark-mode styling & soundwave orb
│   └── app.js                   # Interactive dashboard client & shortcuts
├── models/                      # Local .gguf LLM models directory
├── voices/                      # Local Piper .onnx voices directory
├── data/                        # Local SQLite databases
├── logs/                        # Rotating system logs (logs/foxsi.log)
├── tests/                       # Automated pytest test suites & self-test
├── requirements.txt             # Python dependencies
├── config.yaml                  # Primary system configuration
├── .env.example                 # Optional environment overrides
├── install.bat                  # One-click Windows installer
├── start.bat                    # One-click Windows launcher
├── stop.bat                     # Clean server terminator
└── diagnostics.bat              # System & hardware diagnostics reporter
```

---

## 3. System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit).
- **Python**: Python 3.10, 3.11, or 3.12 (64-bit) with `PATH` enabled.
- **Processor**: Intel or AMD x86_64 CPU (4+ cores recommended).
- **RAM**: Minimum 8 GB RAM (16+ GB recommended for larger models).
- **GPU (Optional)**: NVIDIA CUDA GPU or AMD Radeon GPU supported for offloading. CPU-only execution is fully supported out of the box.
- **Audio**: Working microphone and speakers / headphones.

---

## 4. Installation

### Quick Automated Installation
Double click or run:
```cmd
install.bat
```
This script will:
1. Verify Python installation.
2. Initialize directories (`models/`, `voices/`, `data/`, `logs/`).
3. Set up the virtual environment (`venv/`).
4. Install all dependencies from `requirements.txt`.
5. Validate audio libraries (`sounddevice`, `soundfile`).
6. Validate local LLM runtime (`llama_cpp`).
7. Validate speech synthesis and speech-to-text engines.

### Manual Installation
```cmd
cd G:\llm
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Model Installation (GGUF)

FOXSI is compatible with any standard `.gguf` file.

### Option A: Out-of-the-Box Model
The repository comes pre-equipped with `qwen2.5-0.5b-instruct-q4_k_m.gguf` (468 MB) in `models/`, which provides instant inference on standard CPUs.

### Option B: Download via Web Dashboard
Open the **Model Hub** tab in the dashboard (`http://127.0.0.1:8000`) and click **Download GGUF** next to any curated model:
- **Qwen 2.5 0.5B Instruct** (Fastest, ~468 MB)
- **Qwen 2.5 1.5B Instruct** (Balanced, ~986 MB)
- **Phi-3.5 Mini 3.8B Instruct** (High reasoning, ~2.39 GB)
- **Gemma 2 2B Instruct** (Conversational, ~1.64 GB)

### Option C: Manual Copy
Download any `.gguf` file and place it directly into the `models/` directory:
```
models\my-custom-model.gguf
```
Refresh the Model Hub in the UI, and your model will appear immediately.

---

## 6. Voice Installation (Piper TTS)

FOXSI uses Piper Neural TTS stored in `voices/`:
- Model file: `voices/<voice-name>.onnx`
- Config file: `voices/<voice-name>.onnx.json`

The default voice `en_US-lessac-medium.onnx` is pre-installed. To add other voices:
1. Download ONNX voices from the official Piper voice repository:
   https://github.com/rhasspy/piper/blob/master/VOICES.md
2. Place the `.onnx` and `.onnx.json` files in `voices/`.
3. Select your voice in the **Settings** tab.

*If no Piper voice is present, FOXSI automatically falls back to Windows native SAPI5 voices via `pyttsx3`.*

---

## 7. Starting the Assistant

Double-click or run:
```cmd
start.bat
```
This automatically launches the server and opens your web browser to:
```
http://127.0.0.1:8000
```

To stop the server at any time:
```cmd
stop.bat
```

---

## 8. Operating the Assistant

### Mode A: Push-To-Talk (PTT)
- Click the **Push To Talk** button on the dashboard.
- Or press **Spacebar** anywhere on the dashboard (when not typing in an input field).
- Speak into your microphone; silence auto-detects when you finish speaking.

### Mode B: Wake Word
- Open **Settings**, set **Wake Word Detection** to **Enabled**.
- Supported wake keywords: `"Hey FOXSI / Jarvis"`, `"Alexa"`, `"Hey Mycroft"`.
- Speak the keyword to trigger the microphone.

### Mode C: Typed Chat
- Type any question or command in the input box on the **Chat** tab.
- Toggle the speaker icon `🔊` on/off to control spoken responses.

---

## 9. Configuration (`config.yaml`)

Edit `config.yaml` or use the **Settings** tab in the web interface:

```yaml
assistant:
  name: "FOXSI"
  system_prompt: "You are FOXSI, a local AI voice assistant running on the user's Windows PC..."
  response_style: "conversational"  # conversational | concise | technical | friendly
  language: "auto"

server:
  host: "127.0.0.1"
  port: 8000

llm:
  model_path: "models/qwen2.5-0.5b-instruct-q4_k_m.gguf"
  context_size: 4096
  temperature: 0.7
  max_tokens: 1024
  threads: 0       # 0 = Auto-detect CPU cores
  gpu_layers: -1   # -1 = Auto, 0 = CPU only

stt:
  engine: "faster-whisper"
  model: "tiny.en" # tiny.en | base.en | small | medium
  device: "cpu"
  compute_type: "int8"
  microphone_index: null  # null = Default system mic
  silence_threshold: 0.015
  silence_duration_seconds: 1.5

tts:
  engine: "piper"
  voice_model: "voices/en_US-lessac-medium.onnx"
  voice_config: "voices/en_US-lessac-medium.onnx.json"

wakeword:
  enabled: false
  model_name: "hey_jarvis"
  threshold: 0.5

memory:
  enabled: true
  db_path: "data/foxsi_memory.db"
  max_history_turns: 20

security:
  require_confirmation_for_medium: true
  block_dangerous_tools: true
```

---

## 10. Tools & Permission Security Model

The LLM **never** has direct shell access. All actions pass through the **Permission Layer**:

| Permission Level | Description | Example Actions |
|---|---|---|
| **SAFE** | Executed immediately without prompt | `get_time`, `get_system_info`, `get_cpu_usage`, `get_memory_usage`, `get_disk_usage`, `open_application` (calc, notepad, explorer), `search_local_files`, `read_file` |
| **CONFIRM** | Requires explicit user click (Approve/Deny) in UI | `close_program`, `delete_file`, `system_shutdown_pc`, `system_restart_pc` |
| **BLOCKED** | Strictly blocked permanently by regex rules | Credential dumping (`mimikatz`, `samdump`), registry tampering, malware downloaders, unauthorized account creation |

### Adding a New Tool
1. Define the tool handler in `app/tools/system_tools.py`:
   ```python
   def tool_my_action(arg1: str) -> Dict[str, Any]:
       return {"status": "success", "result": f"Executed {arg1}"}
   ```
2. Register it in `ALL_TOOLS` dictionary in `app/tools/system_tools.py`:
   ```python
   "my_action": {
       "name": "my_action",
       "description": "Performs my action",
       "parameters": {"arg1": "Parameter description"},
       "permission": PermissionLevel.SAFE,  # or PermissionLevel.CONFIRM
       "handler": tool_my_action,
   }
   ```

---

## 11. Automated Testing & Diagnostics

### Run System Diagnostics
```cmd
diagnostics.bat
```
Generates a hardware audit: CPU threads, RAM, detected GPU/VRAM, audio devices, model status, and server state.

### Run Startup Self-Test
```cmd
python tests/self_test.py
```
Output:
```
==================================================
       FOXSI ASSISTANT - STARTUP SELF-TEST        
==================================================
  [PASS] Configuration (FOXSI, port 8000)
  [PASS] Python environment (v3.12.10 on Windows)
  [PASS] LLM runtime (llama-cpp-python v0.3.36)
  [PASS] Model (1 local GGUF models: qwen2.5-0.5b-instruct-q4_k_m.gguf)
  [PASS] STT (faster-whisper engine initialized)
  [PASS] TTS (Piper: 1 voices, SAPI5 fallback: 2 voices)
  [PASS] Microphone & Audio (14 inputs, 14 outputs)
  [PASS] Local server (FastAPI routes & static assets operational)
==================================================
  ALL CORE SYSTEM CHECKS PASSED SUCCESSFULLY! [OK]
==================================================
```

### Run Full Test Suite (19 tests)
```cmd
pytest tests/
```

---

## 12. Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| **Microphone not picking up speech** | Wrong input device selected in Windows | Select your microphone from the dropdown in **Settings** -> **Microphone Input Device**. |
| **TTS plays no sound** | Default audio device muted or SAPI conflict | Click **Stop Audio** and verify default output in Windows sound settings. |
| **Model loading takes long or OOM** | Model too large for system RAM | Switch to `Qwen 2.5 0.5B` or `1.5B` via the **Model Hub** tab. |
| **Port 8000 already in use** | Prior server process running | Run `stop.bat` to terminate old server processes, or change `port` in `config.yaml`. |

---

## 13. Privacy Guarantee

- **No audio sent to cloud**: STT runs on your CPU using local `faster-whisper`.
- **No prompts sent to cloud**: LLM inference runs inside your machine using `llama.cpp`.
- **No synthetic audio streamed from cloud**: TTS runs locally via `piper` and Windows SAPI.
- **No analytics or telemetry telemetry beacons**: Zero tracking. Everything is kept inside `data/foxsi_memory.db` and `logs/foxsi.log`.

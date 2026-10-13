import os
from pathlib import Path
from typing import Optional, Any, Dict
import yaml
from pydantic import BaseModel, Field

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"


class AssistantConfig(BaseModel):
    name: str = "FOXSI"
    system_prompt: str = (
        "You are FOXSI, a local AI voice assistant running on the user's Windows PC. "
        "You are helpful, concise, technically capable, and privacy-first. "
        "You operate locally whenever possible. Never claim to have executed an operating-system "
        "action unless the tool system confirms that it actually happened. Always provide brief, "
        "conversational spoken-friendly responses when answering voice queries, or detailed technical explanations when requested."
    )
    response_style: str = "conversational"
    language: str = "auto"


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class LLMConfig(BaseModel):
    model_path: str = "models/qwen2.5-0.5b-instruct-q4_k_m.gguf"
    context_size: int = 4096
    temperature: float = 0.7
    max_tokens: int = 1024
    threads: int = 0  # 0 = auto
    gpu_layers: int = -1  # -1 = auto, 0 = CPU only


class STTConfig(BaseModel):
    engine: str = "faster-whisper"
    model: str = "tiny.en"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "en"
    microphone_index: Optional[int] = None
    silence_threshold: float = 0.015
    silence_duration_seconds: float = 1.5


class TTSConfig(BaseModel):
    engine: str = "piper"  # 'piper' or 'pyttsx3'
    voice_model: str = "voices/en_US-lessac-medium.onnx"
    voice_config: str = "voices/en_US-lessac-medium.onnx.json"
    rate: float = 1.0
    volume: float = 1.0
    pyttsx3_voice_id: Optional[str] = None


class WakewordConfig(BaseModel):
    enabled: bool = False
    engine: str = "openwakeword"
    model_name: str = "hey_jarvis"
    threshold: float = 0.5
    display_name: str = "Hey FOXSI"


class MemoryConfig(BaseModel):
    enabled: bool = True
    db_path: str = "data/foxsi_memory.db"
    max_history_turns: int = 20


class SecurityConfig(BaseModel):
    require_confirmation_for_medium: bool = True
    block_dangerous_tools: bool = True


class Settings(BaseModel):
    assistant: AssistantConfig = Field(default_factory=AssistantConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    wakeword: WakewordConfig = Field(default_factory=WakewordConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path against the project BASE_DIR."""
        p = Path(relative_path)
        if p.is_absolute():
            return p
        return BASE_DIR / p


_settings_instance: Optional[Settings] = None


def load_settings(config_file: Optional[Path] = None) -> Settings:
    path = config_file or CONFIG_PATH
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return Settings(**data)
        except Exception as e:
            print(f"[Warning] Failed to parse {path}: {e}. Falling back to default settings.")
    return Settings()


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = load_settings()
    return _settings_instance


def reload_settings() -> Settings:
    global _settings_instance
    _settings_instance = load_settings()
    return _settings_instance


def save_settings(settings: Settings, config_file: Optional[Path] = None) -> None:
    path = config_file or CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(settings.model_dump(), f, sort_keys=False, default_flow_style=False)


def update_settings(updates: Dict[str, Any]) -> Settings:
    current = get_settings()
    current_data = current.model_dump()

    def deep_update(d: dict, u: dict) -> dict:
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                d[k] = deep_update(d[k], v)
            else:
                d[k] = v
        return d

    merged = deep_update(current_data, updates)
    new_settings = Settings(**merged)
    save_settings(new_settings)
    global _settings_instance
    _settings_instance = new_settings
    return new_settings

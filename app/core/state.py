from enum import Enum
from typing import Optional, Dict, Any, List
import time
from pydantic import BaseModel, Field


class AssistantStateEnum(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


class AppRuntimeState(BaseModel):
    state: AssistantStateEnum = AssistantStateEnum.IDLE
    is_recording: bool = False
    is_speaking: bool = False
    is_thinking: bool = False

    # Component readiness
    stt_status: str = "unloaded"
    tts_status: str = "unloaded"
    llm_status: str = "unloaded"
    wakeword_status: str = "inactive"

    current_model: Optional[str] = None
    current_model_path: Optional[str] = None
    current_model_size_mb: Optional[float] = None

    last_user_input: str = ""
    last_assistant_output: str = ""
    last_error: Optional[str] = None
    last_action_timestamp: float = Field(default_factory=time.time)

    pending_confirmations: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    active_tools_count: int = 0


runtime_state = AppRuntimeState()


def get_runtime_state() -> AppRuntimeState:
    return runtime_state


def update_runtime_state(**kwargs) -> AppRuntimeState:
    global runtime_state
    for k, v in kwargs.items():
        if hasattr(runtime_state, k):
            setattr(runtime_state, k, v)
    runtime_state.last_action_timestamp = time.time()
    return runtime_state

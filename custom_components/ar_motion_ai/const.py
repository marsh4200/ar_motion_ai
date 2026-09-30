"""Constants for AR Motion AI."""
from __future__ import annotations

DOMAIN = "ar_motion_ai"

CONF_NAME = "name"
CONF_CAMERA = "camera"
CONF_MOTION_SENSORS = "motion_sensors"
CONF_AI_TASK = "ai_task_entity"
CONF_NOTIFY = "notify_services"
CONF_PROMPT = "prompt"
CONF_NUM_SNAPSHOTS = "num_snapshots"
CONF_INTERVAL = "snapshot_interval_ms"
CONF_COOLDOWN = "cooldown_seconds"
CONF_NOTIFY_NO_MOTION = "notify_on_no_motion"
CONF_PROVIDER = "provider"
CONF_API_KEY = "api_key"
CONF_BASE_URL = "base_url"
CONF_MODEL = "model"

PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OLLAMA = "ollama"
PROVIDER_COMPATIBLE = "openai_compatible"
PROVIDER_AI_TASK = "ai_task"
PROVIDERS = [
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    PROVIDER_ANTHROPIC,
    PROVIDER_OLLAMA,
    PROVIDER_COMPATIBLE,
    PROVIDER_AI_TASK,
]
DEFAULT_PROVIDER = PROVIDER_GEMINI

# Pre-selected model per provider (user can pick any model the account has)
DEFAULT_MODELS = {
    PROVIDER_GEMINI: "gemini-2.5-flash",
    PROVIDER_OPENAI: "gpt-4o-mini",
    PROVIDER_ANTHROPIC: "claude-haiku-4-5",
    PROVIDER_OLLAMA: "qwen2.5vl",
    PROVIDER_COMPATIBLE: "",
}
DEFAULT_OLLAMA_URL = "http://localhost:11434"

DEFAULT_NUM_SNAPSHOTS = 3
DEFAULT_INTERVAL = 500
DEFAULT_COOLDOWN = 30
DEFAULT_NOTIFY_NO_MOTION = False

NO_MOTION_REPLY = (
    "Camera has detected motion however no obvious motion observed comparing snapshots"
)
NO_MOTION_MATCH = "no obvious motion"

DEFAULT_PROMPT = (
    "Motion has been detected, compare and very briefly describe what you see in "
    "the following sequence of images from my {{ camera_name }} camera. What do you "
    "think caused the motion alarm? If a person, animal or car is present, describe "
    "them in detail. Do not describe stationary objects or buildings. If you see no "
    f'obvious causes of motion, reply with "{NO_MOTION_REPLY}". Your message needs '
    "to be short enough to fit in a phone notification."
)

MEDIA_SUBDIR = "ar_motion_ai"
KEEP_RUNS = 20

EVENT_RESULT = "ar_motion_ai_result"


def signal_update(entry_id: str) -> str:
    """Dispatcher signal for an entry."""
    return f"{DOMAIN}_update_{entry_id}"

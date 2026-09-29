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

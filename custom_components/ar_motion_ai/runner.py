"""Core snapshot -> AI -> notify pipeline for AR Motion AI."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.camera import async_get_image
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.template import Template
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    CONF_AI_TASK,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CAMERA,
    CONF_MODEL,
    CONF_PROVIDER,
    DEFAULT_MODELS,
    PROVIDER_AI_TASK,
    CONF_COOLDOWN,
    CONF_INTERVAL,
    CONF_MOTION_SENSORS,
    CONF_NAME,
    CONF_NOTIFY,
    CONF_NOTIFY_NO_MOTION,
    CONF_NUM_SNAPSHOTS,
    CONF_PROMPT,
    DEFAULT_COOLDOWN,
    DEFAULT_INTERVAL,
    DEFAULT_NOTIFY_NO_MOTION,
    DEFAULT_NUM_SNAPSHOTS,
    DEFAULT_PROMPT,
    DOMAIN,
    EVENT_RESULT,
    KEEP_RUNS,
    MEDIA_SUBDIR,
    NO_MOTION_MATCH,
    signal_update,
)
from .providers import async_analyze

_LOGGER = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Result of one analysis run."""

    text: str
    timestamp: datetime
    trigger: str
    snapshots: list[str] = field(default_factory=list)  # absolute file paths
    media_ids: list[str] = field(default_factory=list)
    no_motion: bool = False
    notified: bool = False
    error: str | None = None


class MotionAIRunner:
    """Owns listeners, locking and the analysis pipeline for one entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.enabled = True
        self.running = False
        self.last_result: RunResult | None = None
        self._lock = asyncio.Lock()
        self._last_run_mono: float = 0.0
        self._unsub = None

    # ------------------------------------------------------------------ config
    @property
    def cfg(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    @property
    def name(self) -> str:
        return self.cfg.get(CONF_NAME) or self.entry.title

    @property
    def media_dir(self) -> str:
        base = self.hass.config.media_dirs.get("local") or self.hass.config.path("media")
        return os.path.join(base, MEDIA_SUBDIR, slugify(self.name))

    def _media_id(self, filename: str) -> str:
        return (
            f"media-source://media_source/local/{MEDIA_SUBDIR}/"
            f"{slugify(self.name)}/{filename}"
        )

    def _media_url(self, filename: str) -> str:
        """Relative URL the companion app can load as a notification image."""
        return f"/media/local/{MEDIA_SUBDIR}/{slugify(self.name)}/{filename}"

    # --------------------------------------------------------------- lifecycle
    @callback
    def async_start(self) -> None:
        sensors = self.cfg.get(CONF_MOTION_SENSORS) or []
        if isinstance(sensors, str):
            sensors = [sensors]
        if sensors:
            self._unsub = async_track_state_change_event(
                self.hass, sensors, self._handle_motion
            )

    @callback
    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_motion(self, event: Event) -> None:
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        if new is None or new.state != STATE_ON:
            return
        if old is not None and old.state == STATE_ON:
            return
        if not self.enabled:
            return
        cooldown = int(self.cfg.get(CONF_COOLDOWN, DEFAULT_COOLDOWN))
        if time.monotonic() - self._last_run_mono < cooldown:
            _LOGGER.debug("%s: in cooldown, ignoring motion", self.name)
            return
        if self._lock.locked():
            return
        trigger_name = new.attributes.get("friendly_name", new.entity_id)
        self.hass.async_create_task(self.async_run(trigger=trigger_name))

    # ---------------------------------------------------------------- pipeline
    async def async_run(self, trigger: str = "Manual") -> RunResult | None:
        if self._lock.locked():
            return None
        async with self._lock:
            self._last_run_mono = time.monotonic()
            self.running = True
            self._push()
            try:
                result = await self._pipeline(trigger)
            except Exception as err:  # noqa: BLE001 - surface any failure as state
                _LOGGER.exception("%s: analysis failed", self.name)
                result = RunResult(
                    text=f"Error: {err}",
                    timestamp=dt_util.now(),
                    trigger=trigger,
                    error=str(err),
                )
            finally:
                self.running = False
            self.last_result = result
            self._push()
            self.hass.bus.async_fire(
                EVENT_RESULT,
                {
                    "entry_id": self.entry.entry_id,
                    "name": self.name,
                    "camera": self.cfg.get(CONF_CAMERA),
                    "trigger": result.trigger,
                    "text": result.text,
                    "no_motion": result.no_motion,
                    "notified": result.notified,
                    "snapshots": result.media_ids,
                    "error": result.error,
                },
            )
            return result

    async def _pipeline(self, trigger: str) -> RunResult:
        cfg = self.cfg
        camera = cfg[CONF_CAMERA]
        count = max(1, min(5, int(cfg.get(CONF_NUM_SNAPSHOTS, DEFAULT_NUM_SNAPSHOTS))))
        interval = max(0, int(cfg.get(CONF_INTERVAL, DEFAULT_INTERVAL))) / 1000

        cam_state = self.hass.states.get(camera)
        camera_name = (
            cam_state.attributes.get("friendly_name", camera) if cam_state else camera
        )

        # 1. Snapshots (fetched directly — no allowlist_external_dirs needed)
        stamp = dt_util.now().strftime("%Y%m%d_%H%M%S")
        await self.hass.async_add_executor_job(os.makedirs, self.media_dir, 0o755, True)
        files: list[str] = []
        images: list[bytes] = []
        for i in range(1, count + 1):
            image = await async_get_image(self.hass, camera, timeout=10)
            fname = f"{stamp}_{i}.jpg"
            path = os.path.join(self.media_dir, fname)
            await self.hass.async_add_executor_job(_write_bytes, path, image.content)
            files.append(fname)
            images.append(image.content)
            if i < count and interval:
                await asyncio.sleep(interval)

        # latest.jpg for the image entity / notifications
        latest = os.path.join(self.media_dir, "latest.jpg")
        await self.hass.async_add_executor_job(
            _copy, os.path.join(self.media_dir, files[0]), latest
        )
        await self.hass.async_add_executor_job(_prune, self.media_dir, KEEP_RUNS)

        media_ids = [self._media_id(f) for f in files]

        # 2. AI
        prompt = Template(cfg.get(CONF_PROMPT) or DEFAULT_PROMPT, self.hass)
        instructions = prompt.async_render(
            {"camera_name": camera_name, "trigger": trigger}, parse_result=False
        )
        # Entries created before v1.1 had no provider and used an AI Task entity
        provider = cfg.get(CONF_PROVIDER) or PROVIDER_AI_TASK
        if provider == PROVIDER_AI_TASK:
            try:
                response = await self.hass.services.async_call(
                    "ai_task",
                    "generate_data",
                    {
                        "entity_id": cfg[CONF_AI_TASK],
                        "task_name": f"{DOMAIN}_{slugify(self.name)}",
                        "instructions": instructions,
                        "attachments": [
                            {"media_content_id": m, "media_content_type": "image/jpeg"}
                            for m in media_ids
                        ],
                    },
                    blocking=True,
                    return_response=True,
                )
            except HomeAssistantError as err:
                raise HomeAssistantError(f"AI task failed: {err}") from err
            raw = (response or {}).get("data", "")
        else:
            raw = await async_analyze(
                self.hass,
                provider,
                api_key=cfg.get(CONF_API_KEY),
                base_url=cfg.get(CONF_BASE_URL),
                model=cfg.get(CONF_MODEL) or DEFAULT_MODELS.get(provider, ""),
                prompt=instructions,
                images=images,
            )

        text = str(raw or "").strip() or "No response from AI"
        no_motion = NO_MOTION_MATCH in text.lower()

        result = RunResult(
            text=text,
            timestamp=dt_util.now(),
            trigger=trigger,
            snapshots=[os.path.join(self.media_dir, f) for f in files],
            media_ids=media_ids,
            no_motion=no_motion,
        )

        # 3. Notify
        if not no_motion or cfg.get(CONF_NOTIFY_NO_MOTION, DEFAULT_NOTIFY_NO_MOTION):
            result.notified = await self._notify(trigger, text, files[0])
        return result

    async def _notify(self, trigger: str, text: str, first_file: str) -> bool:
        services = self.cfg.get(CONF_NOTIFY) or []
        if isinstance(services, str):
            services = [services]
        image_url = self._media_url(first_file)
        # Tapping the notification opens the URL outside the app's
        # authenticated session (browser / gallery), so /media/... returns 401
        # unless the path carries an authSig. Sign it with HA's content user.
        click_url = async_sign_path(
            self.hass, image_url, timedelta(days=7), use_content_user=True
        )
        sent = False
        for svc in services:
            svc = svc.removeprefix("notify.")
            if not self.hass.services.has_service("notify", svc):
                _LOGGER.warning("%s: notify.%s not found", self.name, svc)
                continue
            data: dict[str, Any] = {
                "title": f"{trigger} detected",
                "message": text,
                "data": {
                    # Works on both Android and iOS companion apps
                    "image": image_url,
                    "tag": f"{DOMAIN}_{slugify(self.name)}",
                    "clickAction": click_url,  # Android
                    "url": click_url,  # iOS
                },
            }
            try:
                await self.hass.services.async_call("notify", svc, data, blocking=True)
                sent = True
            except HomeAssistantError as err:
                _LOGGER.error("%s: notify.%s failed: %s", self.name, svc, err)
        return sent

    def latest_image_path(self) -> str:
        return os.path.join(self.media_dir, "latest.jpg")

    @callback
    def _push(self) -> None:
        async_dispatcher_send(self.hass, signal_update(self.entry.entry_id))


# --------------------------------------------------------------- file helpers
def _write_bytes(path: str, content: bytes) -> None:
    with open(path, "wb") as fh:
        fh.write(content)


def _copy(src: str, dst: str) -> None:
    with open(src, "rb") as s, open(dst + ".tmp", "wb") as d:
        d.write(s.read())
    os.replace(dst + ".tmp", dst)


def _prune(directory: str, keep_runs: int) -> None:
    """Keep only the most recent N runs (files share a timestamp prefix)."""
    try:
        files = [f for f in os.listdir(directory) if f.endswith(".jpg") and f != "latest.jpg"]
    except FileNotFoundError:
        return
    stamps = sorted({f.rsplit("_", 1)[0] for f in files}, reverse=True)
    stale = set(stamps[keep_runs:])
    for f in files:
        if f.rsplit("_", 1)[0] in stale:
            try:
                os.remove(os.path.join(directory, f))
            except OSError:
                pass

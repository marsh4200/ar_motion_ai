"""Sensors for AR Motion AI."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MotionAIEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    runner = hass.data[DOMAIN][entry.entry_id]
    add([LastDescriptionSensor(runner), LastRunSensor(runner)])


class LastDescriptionSensor(MotionAIEntity, SensorEntity):
    _attr_icon = "mdi:robot-outline"

    def __init__(self, runner) -> None:
        super().__init__(runner, "last_description")

    @property
    def native_value(self):
        r = self.runner.last_result
        return r.text[:255] if r else None

    @property
    def extra_state_attributes(self):
        r = self.runner.last_result
        if not r:
            return {}
        return {
            "full_text": r.text,
            "trigger": r.trigger,
            "no_motion": r.no_motion,
            "notified": r.notified,
            "snapshots": r.media_ids,
            "error": r.error,
            "provider": self.runner.cfg.get("provider") or "ai_task",
            "model": self.runner.cfg.get("model"),
        }


class LastRunSensor(MotionAIEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, runner) -> None:
        super().__init__(runner, "last_run")

    @property
    def native_value(self):
        r = self.runner.last_result
        return r.timestamp if r else None

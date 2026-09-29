"""Binary sensor for AR Motion AI (analysis running)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MotionAIEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    add([AnalyzingBinarySensor(hass.data[DOMAIN][entry.entry_id])])


class AnalyzingBinarySensor(MotionAIEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, runner) -> None:
        super().__init__(runner, "analyzing")

    @property
    def is_on(self) -> bool:
        return self.runner.running

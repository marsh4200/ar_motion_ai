"""Manual analyze button for AR Motion AI."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MotionAIEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    add([AnalyzeButton(hass.data[DOMAIN][entry.entry_id])])


class AnalyzeButton(MotionAIEntity, ButtonEntity):
    _attr_icon = "mdi:camera-iris"

    def __init__(self, runner) -> None:
        super().__init__(runner, "analyze_now")

    async def async_press(self) -> None:
        self.hass.async_create_task(self.runner.async_run(trigger="Manual"))

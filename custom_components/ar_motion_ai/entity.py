"""Base entity for AR Motion AI."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, signal_update
from .runner import MotionAIRunner


class MotionAIEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runner: MotionAIRunner, key: str) -> None:
        self.runner = runner
        self._attr_unique_id = f"{runner.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runner.entry.entry_id)},
            name=runner.name,
            manufacturer="AR Smart Home",
            model="Motion AI",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_update(self.runner.entry.entry_id), self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

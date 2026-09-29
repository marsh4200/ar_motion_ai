"""Enable switch for AR Motion AI."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .entity import MotionAIEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    add([EnabledSwitch(hass.data[DOMAIN][entry.entry_id])])


class EnabledSwitch(MotionAIEntity, SwitchEntity, RestoreEntity):
    """Turn motion-triggered analysis on/off (e.g. from an alarm or presence automation)."""

    _attr_icon = "mdi:motion-sensor"

    def __init__(self, runner) -> None:
        super().__init__(runner, "enabled")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            self.runner.enabled = last.state != STATE_OFF

    @property
    def is_on(self) -> bool:
        return self.runner.enabled

    async def async_turn_on(self, **kwargs) -> None:
        self.runner.enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self.runner.enabled = False
        self.async_write_ha_state()

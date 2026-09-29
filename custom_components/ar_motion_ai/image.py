"""Latest snapshot image entity for AR Motion AI."""
from __future__ import annotations

import os

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MotionAIEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    add([LatestSnapshotImage(hass, hass.data[DOMAIN][entry.entry_id])])


class LatestSnapshotImage(MotionAIEntity, ImageEntity):
    _attr_content_type = "image/jpeg"

    def __init__(self, hass: HomeAssistant, runner) -> None:
        MotionAIEntity.__init__(self, runner, "latest_snapshot")
        ImageEntity.__init__(self, hass)
        if runner.last_result:
            self._attr_image_last_updated = runner.last_result.timestamp

    @callback
    def _handle_update(self) -> None:
        r = self.runner.last_result
        if r and r.timestamp != self._attr_image_last_updated and r.snapshots:
            self._attr_image_last_updated = r.timestamp
            self._cached_image = None
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        path = self.runner.latest_image_path()

        def _read() -> bytes | None:
            if not os.path.exists(path):
                return None
            with open(path, "rb") as fh:
                return fh.read()

        return await self.hass.async_add_executor_job(_read)

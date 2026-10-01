"""AR Motion AI — camera snapshots analysed by an AI Task, with phone notifications."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .runner import MotionAIRunner
from .snapshot_view import async_setup_snapshot_links

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.BUTTON, Platform.IMAGE]

SERVICE_ANALYZE = "analyze"
ATTR_ENTRY_ID = "config_entry_id"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the domain-level analyze service and snapshot link view."""
    await async_setup_snapshot_links(hass)

    async def _analyze(call: ServiceCall):
        entry_id = call.data[ATTR_ENTRY_ID]
        runner: MotionAIRunner | None = hass.data.get(DOMAIN, {}).get(entry_id)
        if runner is None:
            raise ServiceValidationError(f"No AR Motion AI entry {entry_id}")
        result = await runner.async_run(trigger="Service call")
        if result is None:
            raise ServiceValidationError("Analysis already running")
        return {
            "text": result.text,
            "no_motion": result.no_motion,
            "notified": result.notified,
            "snapshots": result.media_ids,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_ANALYZE,
        _analyze,
        schema=vol.Schema({vol.Required(ATTR_ENTRY_ID): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runner = MotionAIRunner(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runner
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    runner.async_start()
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runner: MotionAIRunner = hass.data[DOMAIN][entry.entry_id]
    runner.async_stop()
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return ok


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

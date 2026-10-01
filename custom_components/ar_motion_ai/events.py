"""Event history + in-app panel for AR Motion AI.

Notification taps open ``/ar-motion-ai?event=<id>`` inside the HA companion
app, which uses whatever URL the app is configured with (internal on Wi-Fi,
external away) and is already logged in. The panel shows the snapshots and
the full AI message for that event, plus recent history.
"""
from __future__ import annotations

import os
from typing import Any

import voluptuous as vol

from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN, KEEP_RUNS
from .snapshot_view import snapshot_link

DATA_EVENTS = f"{DOMAIN}_events"
PANEL_PATH = "ar-motion-ai"
STATIC_URL = f"/{DOMAIN}_static"
_STORE_VERSION = 1


class EventLog:
    """Recent analysis events, persisted so panel links survive restarts."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict] = Store(hass, _STORE_VERSION, f"{DOMAIN}.events")
        self.events: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.events = data.get("events", [])

    @callback
    def async_add(self, event: dict[str, Any]) -> None:
        self.events.insert(0, event)
        # keep KEEP_RUNS per entry — matches snapshot pruning on disk
        seen: dict[str, int] = {}
        kept = []
        for ev in self.events:
            n = seen.get(ev["entry_id"], 0)
            if n < KEEP_RUNS:
                kept.append(ev)
            seen[ev["entry_id"]] = n + 1
        self.events = kept
        self._store.async_delay_save(lambda: {"events": self.events}, 2)


async def async_setup_events(hass: HomeAssistant) -> None:
    log = EventLog(hass)
    await log.async_load()
    hass.data[DATA_EVENTS] = log

    websocket_api.async_register_command(hass, ws_events)

    www = os.path.join(os.path.dirname(__file__), "www")
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, www, False)]
    )
    version = await hass.async_add_executor_job(
        lambda: str(int(os.path.getmtime(os.path.join(www, "panel.js"))))
    )
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_PATH,
        webcomponent_name="ar-motion-ai-panel",
        sidebar_title="Motion AI",
        sidebar_icon="mdi:cctv",
        module_url=f"{STATIC_URL}/panel.js?v={version}",
        require_admin=False,
    )


def panel_link(event_id: str) -> str:
    """Relative frontend path — opens inside the companion app."""
    return f"/{PANEL_PATH}?event={event_id}"


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/events"})
@callback
def ws_events(hass: HomeAssistant, connection, msg: dict) -> None:
    log: EventLog | None = hass.data.get(DATA_EVENTS)
    out = []
    for ev in log.events if log else []:
        out.append(
            {
                **ev,
                "images": [
                    snapshot_link(hass, ev["folder"], f) for f in ev.get("files", [])
                ],
            }
        )
    connection.send_result(msg["id"], {"events": out})

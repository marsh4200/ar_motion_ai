"""Tokenised snapshot links for notification taps.

Tapping a notification opens the link outside the companion app's logged-in
session (browser / gallery / download manager), and the app may add its own
query params (e.g. ``external_auth=1``), which breaks HA ``authSig`` links.
So each snapshot gets its own HMAC key embedded in the *path*, and this view
serves it without HA auth. Links die naturally when the file is pruned.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, MEDIA_SUBDIR

DATA_LINK_KEY = f"{DOMAIN}_link_key"
_STORE_VERSION = 1
_SAFE = re.compile(r"^[A-Za-z0-9_\-]+$")
_SAFE_FILE = re.compile(r"^[A-Za-z0-9_\-]+\.jpg$")


async def async_setup_snapshot_links(hass: HomeAssistant) -> None:
    """Load (or create) the persistent link key and register the view."""
    store: Store[dict] = Store(hass, _STORE_VERSION, f"{DOMAIN}.link_key")
    data = await store.async_load() or {}
    if not data.get("key"):
        data = {"key": secrets.token_hex(32)}
        await store.async_save(data)
    hass.data[DATA_LINK_KEY] = data["key"]
    hass.http.register_view(SnapshotView(hass))


def _sig(key: str, folder: str, filename: str) -> str:
    return hmac.new(
        key.encode(), f"{folder}/{filename}".encode(), hashlib.sha256
    ).hexdigest()[:32]


def snapshot_link(hass: HomeAssistant, folder: str, filename: str) -> str:
    """Relative URL for a snapshot that opens without a HA login."""
    sig = _sig(hass.data[DATA_LINK_KEY], folder, filename)
    return f"/api/{DOMAIN}/snapshot/{folder}/{sig}/{filename}"


class SnapshotView(HomeAssistantView):
    url = f"/api/{DOMAIN}/snapshot/{{folder}}/{{sig}}/{{filename}}"
    name = f"api:{DOMAIN}:snapshot"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(
        self, request: web.Request, folder: str, sig: str, filename: str
    ) -> web.StreamResponse:
        key = self.hass.data.get(DATA_LINK_KEY)
        if (
            not key
            or not _SAFE.match(folder)
            or not _SAFE_FILE.match(filename)
            or not hmac.compare_digest(sig, _sig(key, folder, filename))
        ):
            raise web.HTTPNotFound()
        base = self.hass.config.media_dirs.get("local") or self.hass.config.path("media")
        path = os.path.join(base, MEDIA_SUBDIR, folder, filename)
        if not await self.hass.async_add_executor_job(os.path.isfile, path):
            raise web.HTTPNotFound()
        return web.FileResponse(
            path, headers={"Cache-Control": "private, max-age=86400"}
        )

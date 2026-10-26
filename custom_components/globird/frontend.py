"""Load the bundled dashboard cards once per Home Assistant process."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
BUNDLE_PATH = Path(__file__).parent / "www" / "globird-cards.js"
BUNDLE_URL = "/globird_frontend/globird-cards.js"


def _versioned_url() -> str:
    """Read the manifest and asset outside the event loop."""
    version = json.loads(
        BUNDLE_PATH.parent.parent.joinpath("manifest.json").read_text()
    )["version"]
    digest = hashlib.sha256(BUNDLE_PATH.read_bytes()).hexdigest()[:12]
    return f"{BUNDLE_URL}?v={version}-{digest}"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register a shared module without affecting sensor setup on failure."""
    if not {"http", "frontend"} <= hass.config.components:
        _LOGGER.debug("Skipping %s: HTTP/frontend not loaded", BUNDLE_URL)
        return
    data = hass.data.setdefault(DOMAIN, {})
    lock = data.setdefault("frontend_lock", asyncio.Lock())
    async with lock:
        if data.get("frontend_registered"):
            return
        try:
            from homeassistant.components.frontend import add_extra_js_url
            from homeassistant.components.http import (
                StaticPathConfig,  # pyright: ignore[reportPrivateImportUsage]
            )

            url = await hass.async_add_executor_job(_versioned_url)
            if not data.get("frontend_static_registered"):
                await hass.http.async_register_static_paths(
                    [StaticPathConfig(BUNDLE_URL, str(BUNDLE_PATH), cache_headers=True)]
                )
                data["frontend_static_registered"] = True
            add_extra_js_url(hass, url)
        except Exception as err:
            _LOGGER.warning(
                "Unable to register %s (%s): %s", BUNDLE_URL, type(err).__name__, err
            )
            return
        data["frontend_registered"] = True

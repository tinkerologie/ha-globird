"""Load bundled cards through the appropriate Home Assistant lifecycle."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
BUNDLE_PATH = Path(__file__).parent / "www" / "globird-cards.js"
BUNDLE_URL = "/globird_frontend/globird-cards.js"
OWNED_PREFIX = "/globird_frontend/"
# Static assets are shared across entries and outlive individual entry unloads.
FRONTEND_DATA: HassKey[dict[str, Any]] = HassKey("globird_frontend")


def _versioned_url() -> str:
    """Read the manifest and asset outside the event loop."""
    version = json.loads(
        BUNDLE_PATH.parent.parent.joinpath("manifest.json").read_text()
    )["version"]
    digest = hashlib.sha256(BUNDLE_PATH.read_bytes()).hexdigest()[:12]
    return f"{BUNDLE_URL}?v={version}-{digest}"


def _resource_collection(hass: HomeAssistant) -> tuple[Any, bool]:
    """Resolve the current collection; YAML reloads can replace this object."""
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA
        from homeassistant.components.lovelace.resources import (
            ResourceStorageCollection,
        )
    except ImportError:
        return None, False
    lovelace = hass.data.get(LOVELACE_DATA)
    resources = lovelace.resources if lovelace is not None else None
    return resources, isinstance(resources, ResourceStorageCollection)


async def _async_reconcile_resources(resources: Any, url: str) -> None:
    """Reconcile only resources owned by this integration, after lazy loading."""
    from homeassistant.helpers.collection import ItemNotFound

    await resources.async_get_info()
    items = list(resources.async_items())
    matches = [item for item in items if item["url"].partition("?")[0] == BUNDLE_URL]
    if not matches:
        await resources.async_create_item({"url": url, "res_type": "module"})
    elif matches[0]["url"] != url or matches[0]["type"] != "module":
        await resources.async_update_item(
            matches[0]["id"], {"url": url, "res_type": "module"}
        )
    duplicate_ids = {item["id"] for item in matches[1:]}
    for item in items:
        base_url = item["url"].partition("?")[0]
        obsolete = base_url.startswith(OWNED_PREFIX) and base_url != BUNDLE_URL
        if obsolete or item["id"] in duplicate_ids:
            with suppress(ItemNotFound):
                await resources.async_delete_item(item["id"])


def _remove_fallback(hass: HomeAssistant) -> None:
    """Stop advertising the early module once native resources take over."""
    from homeassistant.components.frontend import remove_extra_js_url

    data = hass.data[FRONTEND_DATA]
    if (url := data.get("frontend_extra_url")) is not None:
        remove_extra_js_url(hass, url)
        data.pop("frontend_extra_url", None)


async def _async_fallback(hass: HomeAssistant, url: str, resources: Any = None) -> None:
    """Avoid duplicate YAML paths and advertise the optional fallback once."""
    from homeassistant.components.frontend import add_extra_js_url

    if resources is not None and hasattr(resources, "async_items"):
        if hasattr(resources, "async_get_info"):
            await resources.async_get_info()
        if any(
            item["url"].partition("?")[0] == BUNDLE_URL
            for item in resources.async_items()
        ):
            _remove_fallback(hass)
            return
    data = hass.data[FRONTEND_DATA]
    if data.get("frontend_extra_url") == url:
        return
    add_extra_js_url(hass, url)
    data["frontend_extra_url"] = url
    _LOGGER.info(
        "%s uses an extra-module fallback; for reliable YAML cold loads, "
        "configure a module resource with URL %s",
        BUNDLE_URL,
        url,
    )


async def async_register_frontend(hass: HomeAssistant, *, _force: bool = False) -> None:
    """Register once per collection without affecting sensor setup on failure."""
    if not {"http", "frontend"} <= hass.config.components:
        _LOGGER.debug("Skipping %s: HTTP/frontend not loaded", BUNDLE_URL)
        return
    data = hass.data.setdefault(FRONTEND_DATA, {})
    lock = data.setdefault("frontend_lock", asyncio.Lock())
    async with lock:
        resources, storage_mode = _resource_collection(hass)
        key = (storage_mode, id(resources))
        if storage_mode and not _force and data.get("frontend_registration_key") == key:
            return
        try:
            from homeassistant.components.http import (
                StaticPathConfig,  # pyright: ignore[reportPrivateImportUsage]
            )

            url = await hass.async_add_executor_job(_versioned_url)
            if not data.get("frontend_static_registered"):
                await hass.http.async_register_static_paths(
                    [StaticPathConfig(BUNDLE_URL, str(BUNDLE_PATH), cache_headers=True)]
                )
                data["frontend_static_registered"] = True
            if storage_mode:
                if not data.get("frontend_reconcile_scheduled"):
                    from homeassistant.helpers.start import async_at_started

                    async def after_start(started_hass: HomeAssistant) -> None:
                        await async_register_frontend(started_hass, _force=True)

                    data["frontend_reconcile_scheduled"] = True
                    async_at_started(hass, after_start)
                try:
                    # Extra modules may run before HA replaces its native
                    # custom-element registry. Lovelace resources run afterwards.
                    await _async_reconcile_resources(resources, url)
                    _remove_fallback(hass)
                except Exception as err:
                    _LOGGER.warning(
                        "Unable to reconcile %s in storage mode (%s): %s",
                        BUNDLE_URL,
                        type(err).__name__,
                        err,
                    )
                    await _async_fallback(hass, url)
                    data.pop("frontend_registration_key", None)
                    data.pop("frontend_registered", None)
                    return
            else:
                await _async_fallback(hass, url, resources)
        except Exception as err:
            _LOGGER.warning(
                "Unable to register %s (%s): %s", BUNDLE_URL, type(err).__name__, err
            )
            return
        data["frontend_registration_key"] = key
        data["frontend_registered"] = True

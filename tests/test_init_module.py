"""Tests for integration setup/unload helpers."""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
from pathlib import Path
from typing import Any

COMPONENT_PATH = Path(__file__).parents[1] / "custom_components"
INTEGRATION_PATH = COMPONENT_PATH / "globird"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(COMPONENT_PATH)]  # type: ignore[attr-defined]
globird_package = types.ModuleType("custom_components.globird")
globird_package.__path__ = [str(INTEGRATION_PATH)]  # type: ignore[attr-defined]
sys.modules.setdefault("custom_components", custom_components)
sys.modules.setdefault("custom_components.globird", globird_package)

homeassistant = types.ModuleType("homeassistant")
config_entries = types.ModuleType("homeassistant.config_entries")
const = types.ModuleType("homeassistant.const")
core = types.ModuleType("homeassistant.core")
util = types.ModuleType("homeassistant.util")
util_logging = types.ModuleType("homeassistant.util.logging")


class Platform:
    SENSOR = "sensor"


config_entries.ConfigEntry = object
const.Platform = Platform
core.HomeAssistant = object
util_logging.log_exception = lambda *_args, **_kwargs: None
util.logging = util_logging
homeassistant.config_entries = config_entries
homeassistant.const = const
homeassistant.core = core
homeassistant.util = util

sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.config_entries", config_entries)
sys.modules.setdefault("homeassistant.const", const)
sys.modules.setdefault("homeassistant.core", core)
sys.modules.setdefault("homeassistant.util", util)
sys.modules.setdefault("homeassistant.util.logging", util_logging)

integration_init = importlib.import_module("custom_components.globird.__init__")


class FakeConfigEntries:
    def __init__(self, *, unload_ok: bool = True) -> None:
        self.forwarded: tuple[Any, Any] | None = None
        self.unloaded: tuple[Any, Any] | None = None
        self._unload_ok = unload_ok

    async def async_forward_entry_setups(
        self, entry: Any, platforms: list[str]
    ) -> None:
        self.forwarded = (entry, platforms)

    async def async_unload_platforms(self, entry: Any, platforms: list[str]) -> bool:
        self.unloaded = (entry, platforms)
        return self._unload_ok


class FakeHass:
    def __init__(self, *, unload_ok: bool = True) -> None:
        self.data: dict[str, Any] = {}
        self.config_entries = FakeConfigEntries(unload_ok=unload_ok)


class FakeCoordinator:
    def __init__(self, _hass: Any, _entry: Any) -> None:
        self.refreshed = False
        self.shutdown = False

    async def async_config_entry_first_refresh(self) -> None:
        self.refreshed = True

    async def async_shutdown(self) -> None:
        self.shutdown = True


class FakeEntry:
    def __init__(self) -> None:
        self.entry_id = "entry-1"
        self.listener = None
        self.runtime_data: Any = None

    def add_update_listener(self, listener: Any) -> Any:
        self.listener = listener
        return listener

    def async_on_unload(self, _unload_callback: Any) -> None:
        return None


def test_async_setup_and_unload_entry(monkeypatch: Any) -> None:
    """Setup stores coordinator and unload cleans it up."""
    monkeypatch.setattr(integration_init, "GloBirdCoordinator", FakeCoordinator)

    hass = FakeHass()
    entry = FakeEntry()

    result = asyncio.run(integration_init.async_setup_entry(hass, entry))

    assert result is True
    coordinator = hass.data[integration_init.DOMAIN][entry.entry_id]
    assert entry.runtime_data is coordinator
    assert isinstance(coordinator, FakeCoordinator)
    assert coordinator.refreshed is True
    assert hass.config_entries.forwarded is not None
    assert entry.listener is None

    unload_result = asyncio.run(integration_init.async_unload_entry(hass, entry))
    assert unload_result is True
    assert coordinator.shutdown is True


def test_async_unload_entry_handles_failed_platform_unload_and_missing_coordinator() -> (
    None
):
    """Unload returns False when platform unload fails and handles missing coordinator."""
    hass_fail = FakeHass(unload_ok=False)
    entry = FakeEntry()
    assert asyncio.run(integration_init.async_unload_entry(hass_fail, entry)) is False

    hass_empty = FakeHass(unload_ok=True)
    assert asyncio.run(integration_init.async_unload_entry(hass_empty, entry)) is True

"""Regression coverage for optional dashboard registration and packaging."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import sys
import tomllib
import types
from pathlib import Path
from typing import Any

import pytest

from custom_components.globird import frontend


@pytest.fixture
def frontend_hass(monkeypatch: Any) -> Any:
    """Keep optional HA module substitutes scoped to this fixture."""
    urls: list[str] = []
    paths: list[Any] = []
    fail = [False]
    frontend_module = types.ModuleType("homeassistant.components.frontend")
    frontend_module.add_extra_js_url = lambda _hass, url: urls.append(url)
    http_module = types.ModuleType("homeassistant.components.http")
    http_module.StaticPathConfig = lambda url, path, **kw: types.SimpleNamespace(
        url_path=url, path=path, **kw
    )
    monkeypatch.setitem(sys.modules, frontend_module.__name__, frontend_module)
    monkeypatch.setitem(sys.modules, http_module.__name__, http_module)

    async def register(configs: list[Any]) -> None:
        await asyncio.sleep(0)
        if fail[0]:
            raise OSError("test static path failure")
        paths.extend(configs)

    async def executor(fn: Any) -> Any:
        return fn()

    return types.SimpleNamespace(
        data={},
        config=types.SimpleNamespace(components={"http", "frontend"}),
        http=types.SimpleNamespace(async_register_static_paths=register),
        async_add_executor_job=executor,
        urls=urls,
        paths=paths,
        fail=fail,
    )


def test_concurrent_setup_registers_one_cache_busted_bundle(frontend_hass: Any) -> None:
    """Concurrent and repeated setup calls share the module for the process."""
    integration = importlib.import_module("custom_components.globird.__init__")

    async def run() -> None:
        assert all(
            await asyncio.gather(
                *[integration.async_setup(frontend_hass, {}) for _ in range(3)]
            )
        )
        await integration.async_setup(frontend_hass, {})

    asyncio.run(run())
    assert len(frontend_hass.paths) == len(frontend_hass.urls) == 1
    assert frontend_hass.paths[0].path == str(frontend.BUNDLE_PATH)
    digest = hashlib.sha256(frontend.BUNDLE_PATH.read_bytes()).hexdigest()[:12]
    assert frontend_hass.urls == [f"{frontend.BUNDLE_URL}?v=2026.10.4-{digest}"]


@pytest.mark.parametrize("missing", ["http", "frontend"])
def test_missing_optional_components_skip(frontend_hass: Any, missing: str) -> None:
    frontend_hass.config.components.remove(missing)
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert not frontend_hass.paths
    assert not frontend_hass.urls


def test_failure_is_optional_and_retryable(frontend_hass: Any) -> None:
    integration = importlib.import_module("custom_components.globird.__init__")
    frontend_hass.fail[0] = True
    assert asyncio.run(integration.async_setup(frontend_hass, {}))
    assert not frontend_hass.urls
    frontend_hass.fail[0] = False
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert len(frontend_hass.urls) == 1


def test_bundle_is_in_python_package() -> None:
    root = Path(__file__).parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    patterns = config["tool"]["setuptools"]["package-data"]["custom_components.globird"]
    assert frontend.BUNDLE_PATH.is_file()
    assert any(frontend.BUNDLE_PATH.match(pattern) for pattern in patterns)


def test_multiple_entries_preserve_module_on_unload(
    frontend_hass: Any, monkeypatch: Any
) -> None:
    helpers = importlib.import_module("test_init_module")
    integration = helpers.integration_init
    monkeypatch.setattr(integration, "GloBirdCoordinator", helpers.FakeCoordinator)
    frontend_hass.config_entries = helpers.FakeConfigEntries()
    first, second = helpers.FakeEntry(), helpers.FakeEntry()
    second.entry_id = "entry-2"

    async def run() -> None:
        await integration.async_setup(frontend_hass, {})
        await integration.async_setup_entry(frontend_hass, first)
        await integration.async_setup_entry(frontend_hass, second)
        assert frontend_hass.data["globird"][first.entry_id] is first.runtime_data
        assert frontend_hass.data["globird"][second.entry_id] is second.runtime_data
        await integration.async_unload_entry(frontend_hass, first)
        assert frontend_hass.data["globird"]["frontend_registered"]
        assert second.entry_id in frontend_hass.data["globird"]
        assert first.entry_id not in frontend_hass.data["globird"]

    asyncio.run(run())
    assert len(frontend_hass.urls) == 1

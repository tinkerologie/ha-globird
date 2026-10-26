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
    extra_urls: list[str] = []
    active_extra_urls: set[str] = set()
    fail = [False]
    frontend_module = types.ModuleType("homeassistant.components.frontend")

    def add_extra(_hass: Any, url: str) -> None:
        urls.append(url)
        extra_urls.append(url)
        active_extra_urls.add(url)

    frontend_module.add_extra_js_url = add_extra
    frontend_module.remove_extra_js_url = lambda _hass, url: active_extra_urls.discard(
        url
    )
    http_module = types.ModuleType("homeassistant.components.http")
    http_module.StaticPathConfig = lambda url, path, **kw: types.SimpleNamespace(
        url_path=url, path=path, **kw
    )
    monkeypatch.setitem(sys.modules, frontend_module.__name__, frontend_module)
    monkeypatch.setitem(sys.modules, http_module.__name__, http_module)

    class FakeResources:
        def __init__(self) -> None:
            self.block: asyncio.Event | None = None
            self.fail_stage: str | None = None
            self.items: list[dict[str, Any]] = []
            self.loaded = False

        async def async_get_info(self) -> None:
            if self.block is not None:
                await self.block.wait()
            self.loaded = True

        def async_items(self) -> list[dict[str, Any]]:
            assert self.loaded
            return self.items

        async def async_create_item(self, item: dict[str, Any]) -> None:
            assert paths  # The URL is advertised only after its static path exists.
            if self.fail_stage == "create":
                raise OSError("test resource create failure")
            self.items.append(
                {
                    "id": str(len(self.items)),
                    "url": item["url"],
                    "type": item["res_type"],
                }
            )
            urls.append(item["url"])

        async def async_update_item(self, item_id: str, item: dict[str, Any]) -> None:
            if self.fail_stage == "update":
                raise OSError("test resource update failure")
            existing = next(x for x in self.items if x["id"] == item_id)
            existing.update(url=item["url"], type=item["res_type"])
            urls.append(item["url"])

        async def async_delete_item(self, item_id: str) -> None:
            if self.fail_stage == "delete":
                raise OSError("test resource delete failure")
            self.items = [item for item in self.items if item["id"] != item_id]

    collection_module = types.ModuleType("homeassistant.helpers.collection")

    class ItemNotFound(Exception):
        """A resource removed by another caller."""

    collection_module.ItemNotFound = ItemNotFound
    monkeypatch.setitem(sys.modules, collection_module.__name__, collection_module)

    resources = FakeResources()
    lovelace_const = types.ModuleType("homeassistant.components.lovelace.const")
    lovelace_const.LOVELACE_DATA = "lovelace"
    lovelace_resources = types.ModuleType("homeassistant.components.lovelace.resources")
    lovelace_resources.ResourceStorageCollection = FakeResources
    monkeypatch.setitem(sys.modules, lovelace_const.__name__, lovelace_const)
    monkeypatch.setitem(sys.modules, lovelace_resources.__name__, lovelace_resources)

    started_callbacks: list[Any] = []
    start_module = types.ModuleType("homeassistant.helpers.start")
    start_module.async_at_started = lambda _hass, cb: started_callbacks.append(cb)
    monkeypatch.setitem(sys.modules, start_module.__name__, start_module)

    async def register(configs: list[Any]) -> None:
        await asyncio.sleep(0)
        if fail[0]:
            raise OSError("test static path failure")
        paths.extend(configs)

    async def executor(fn: Any) -> Any:
        return fn()

    return types.SimpleNamespace(
        data={"lovelace": types.SimpleNamespace(resources=resources)},
        resources=resources,
        started_callbacks=started_callbacks,
        extra_urls=extra_urls,
        active_extra_urls=active_extra_urls,
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
    version = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())[
        "project"
    ]["version"]
    assert frontend_hass.urls == [f"{frontend.BUNDLE_URL}?v={version}-{digest}"]


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
        assert frontend_hass.data[frontend.FRONTEND_DATA]["frontend_registered"]
        assert second.entry_id in frontend_hass.data["globird"]
        assert first.entry_id not in frontend_hass.data["globird"]

    asyncio.run(run())
    assert len(frontend_hass.urls) == 1


def test_storage_mode_uses_lovelace_resource_after_app_bootstrap(
    frontend_hass: Any,
) -> None:
    """Extra modules can register before HA replaces the custom-element registry."""
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert not frontend_hass.extra_urls
    assert len(frontend_hass.resources.items) == 1
    assert frontend_hass.resources.items[0]["type"] == "module"


def test_storage_resource_upgrade_preserves_unrelated_resources(
    frontend_hass: Any,
) -> None:
    other = {"id": "other", "url": "/unrelated.js", "type": "module"}
    frontend_hass.resources.items = [
        other,
        {"id": "globird", "url": f"{frontend.BUNDLE_URL}?v=old", "type": "js"},
    ]
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert frontend_hass.resources.items[0] == other
    assert len(frontend_hass.resources.items) == 2
    assert frontend_hass.resources.items[1]["type"] == "module"
    assert "v=old" not in frontend_hass.resources.items[1]["url"]
    assert not frontend_hass.extra_urls


def test_yaml_mode_retains_extra_module_fallback(frontend_hass: Any) -> None:
    frontend_hass.data["lovelace"].resources = None
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert len(frontend_hass.extra_urls) == 1


def test_delayed_resource_load_precedes_enumeration(frontend_hass: Any) -> None:
    async def run() -> None:
        entered, release = asyncio.Event(), asyncio.Event()
        original = frontend_hass.resources.async_get_info

        async def wait_for_load() -> None:
            entered.set()
            await release.wait()
            await original()

        frontend_hass.resources.async_get_info = wait_for_load
        task = asyncio.create_task(frontend.async_register_frontend(frontend_hass))
        await entered.wait()
        assert not frontend_hass.resources.items
        assert not frontend_hass.urls
        release.set()
        await task
        assert len(frontend_hass.resources.items) == 1

    asyncio.run(run())


def test_started_pass_repairs_stale_storage_replay(frontend_hass: Any) -> None:
    async def run() -> None:
        await frontend.async_register_frontend(frontend_hass)
        assert len(frontend_hass.started_callbacks) == 1
        frontend_hass.resources.items = [
            {"id": "stale", "url": f"{frontend.BUNDLE_URL}?v=old", "type": "js"},
            {
                "id": "duplicate",
                "url": f"{frontend.BUNDLE_URL}?v=older",
                "type": "module",
            },
            {"id": "obsolete", "url": "/globird_frontend/retired.js", "type": "module"},
            {"id": "foreign", "url": "/other/card.js", "type": "module"},
        ]
        await frontend_hass.started_callbacks[0](frontend_hass)
        assert len(frontend_hass.resources.items) == 2
        assert frontend_hass.resources.items[0]["type"] == "module"
        assert "v=old" not in frontend_hass.resources.items[0]["url"]
        assert frontend_hass.resources.items[1]["id"] == "foreign"
        assert len(frontend_hass.paths) == len(frontend_hass.started_callbacks) == 1
        assert not frontend_hass.extra_urls

    asyncio.run(run())


@pytest.mark.parametrize("stage", ["create", "update", "delete"])
def test_resource_failure_falls_back_and_remains_retryable(
    frontend_hass: Any, stage: str
) -> None:
    integration = importlib.import_module("custom_components.globird.__init__")
    if stage == "update":
        frontend_hass.resources.items = [
            {"id": "old", "url": f"{frontend.BUNDLE_URL}?v=old", "type": "js"}
        ]
    elif stage == "delete":
        frontend_hass.resources.items = [
            {"id": "old", "url": "/globird_frontend/retired.js", "type": "module"}
        ]
    frontend_hass.resources.fail_stage = stage
    assert asyncio.run(integration.async_setup(frontend_hass, {}))
    assert len(frontend_hass.extra_urls) == 1
    assert asyncio.run(integration.async_setup(frontend_hass, {}))
    assert len(frontend_hass.extra_urls) == 1
    assert not frontend_hass.data[frontend.FRONTEND_DATA].get("frontend_registered")
    frontend_hass.resources.fail_stage = None
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert frontend_hass.data[frontend.FRONTEND_DATA]["frontend_registered"]
    assert len(frontend_hass.paths) == 1
    assert len(frontend_hass.resources.items) == 1
    assert not frontend_hass.active_extra_urls


def test_yaml_explicit_resource_has_no_extra_module(frontend_hass: Any) -> None:
    # Actual resource mode takes precedence over the dashboard's storage mode.
    frontend_hass.data["lovelace"].mode = "storage"
    frontend_hass.data["lovelace"].resources = types.SimpleNamespace(
        async_items=lambda: [
            {"url": f"{frontend.BUNDLE_URL}?v=manual", "type": "module"}
        ]
    )
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert not frontend_hass.extra_urls


def test_replaced_collection_is_resolved_again(frontend_hass: Any) -> None:
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    replacement = type(frontend_hass.resources)()
    frontend_hass.data["lovelace"].resources = replacement
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert len(replacement.items) == 1
    assert len(frontend_hass.paths) == 1


def test_unavailable_lovelace_import_keeps_fallback(
    frontend_hass: Any, monkeypatch: Any
) -> None:
    monkeypatch.setitem(
        sys.modules, "homeassistant.components.lovelace.resources", None
    )
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert len(frontend_hass.extra_urls) == 1


def test_concurrent_resource_deletion_is_already_done(frontend_hass: Any) -> None:
    frontend_hass.resources.items = [
        {"id": "gone", "url": "/globird_frontend/retired.js", "type": "module"}
    ]

    async def removed_elsewhere(item_id: str) -> None:
        frontend_hass.resources.items = [
            x for x in frontend_hass.resources.items if x["id"] != item_id
        ]
        raise sys.modules["homeassistant.helpers.collection"].ItemNotFound(item_id)

    frontend_hass.resources.async_delete_item = removed_elsewhere
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert frontend_hass.data[frontend.FRONTEND_DATA]["frontend_registered"]
    assert len(frontend_hass.resources.items) == 1


def test_yaml_lazy_load_precedes_fallback_detection(frontend_hass: Any) -> None:
    frontend_hass.data["lovelace"].resources = types.SimpleNamespace(
        async_get_info=frontend_hass.resources.async_get_info,
        async_items=lambda: [],
    )
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert frontend_hass.resources.loaded
    assert len(frontend_hass.extra_urls) == 1


def test_initial_failure_is_retried_automatically_at_started(
    frontend_hass: Any,
) -> None:
    async def run() -> None:
        frontend_hass.resources.fail_stage = "create"
        await frontend.async_register_frontend(frontend_hass)
        assert len(frontend_hass.started_callbacks) == 1
        assert len(frontend_hass.active_extra_urls) == 1
        frontend_hass.resources.fail_stage = None
        await frontend_hass.started_callbacks[0](frontend_hass)
        assert len(frontend_hass.resources.items) == 1
        assert not frontend_hass.active_extra_urls
        assert "frontend_extra_url" not in frontend_hass.data[frontend.FRONTEND_DATA]

    asyncio.run(run())


def test_explicit_yaml_resource_removes_previous_extra_fallback(
    frontend_hass: Any,
) -> None:
    frontend_hass.data["lovelace"].resources = None
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert len(frontend_hass.active_extra_urls) == 1
    frontend_hass.data["lovelace"].resources = types.SimpleNamespace(
        async_items=lambda: [{"url": frontend.BUNDLE_URL, "type": "module"}]
    )
    asyncio.run(frontend.async_register_frontend(frontend_hass))
    assert not frontend_hass.active_extra_urls

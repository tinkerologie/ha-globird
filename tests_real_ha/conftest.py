"""Fixtures for tests that run against the official Home Assistant harness."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, create_autospec

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import MockConfigEntry

from custom_components.globird import config_flow, coordinator
from custom_components.globird.const import DOMAIN
from tests.conftest import (
    fail_on_ha_deprecation_reports as fail_on_ha_deprecation_reports,
)

EMAIL = "user@example.test"
ORIGINAL_CREDENTIAL = "existing-password"


@pytest.fixture
def hass_config_dir(tmp_path: Path) -> str:
    """Expose the checked-out custom integration under the test config directory."""
    components = Path(__file__).resolve().parents[1] / "custom_components"
    (tmp_path / "custom_components").symlink_to(components, target_is_directory=True)
    return str(tmp_path)


@pytest.fixture(autouse=True)
def integration_runtime(
    enable_custom_integrations: None,
    hass: HomeAssistant,
) -> None:
    """Enable the real integration without starting a database for flow tests."""
    hass.config.components.add("recorder")


@pytest.fixture
def portal(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Provide valid portal data without making outbound requests."""
    client = create_autospec(coordinator.GloBirdClient, instance=True)
    client.is_authenticated = False
    client.authenticate.return_value = {"data": {"accounts": []}, "success": True}
    for method in (
        client.get_dashboard,
        client.get_balance,
        client.get_signup_info,
        client.get_account_service_status,
        client.get_power_meter_types,
        client.get_read_meters,
        client.get_weather_impacted_days,
    ):
        method.return_value = {"data": None, "success": True}
    client.export_session_cookies.return_value = []
    monkeypatch.setattr(config_flow, "GloBirdClient", lambda: client)
    monkeypatch.setattr(coordinator, "GloBirdClient", lambda: client)
    return client.authenticate


@pytest.fixture
def entry(hass: HomeAssistant, portal: AsyncMock) -> MockConfigEntry:
    """Install an entry with an unrelated data field to preserve across flows."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=EMAIL,
        data={"email": EMAIL, "password": ORIGINAL_CREDENTIAL, "keep": True},
        options={"daily_poll_start_time": "00:05:00"},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def reloads(
    hass: HomeAssistant, entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> list[tuple[dict, dict]]:
    """Capture persisted entry data and options when a real reload starts."""
    calls: list[tuple[dict, dict]] = []
    reload_entry = hass.config_entries.async_reload

    async def spy(entry_id: str) -> bool:
        assert entry_id == entry.entry_id
        calls.append((dict(entry.data), dict(entry.options)))
        return await reload_entry(entry_id)

    monkeypatch.setattr(hass.config_entries, "async_reload", spy)
    return calls

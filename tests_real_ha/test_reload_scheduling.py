"""Verify that Home Assistant's flow managers reload GloBird exactly once."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant.common import MockConfigEntry

from custom_components.globird.client import GloBirdAuthError
from custom_components.globird.const import DOMAIN

EMAIL = "user@example.test"
ORIGINAL_CREDENTIAL = "existing-password"


@pytest.fixture
async def loaded_entry(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    """Set up GloBird through Home Assistant's real config-entry manager."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert not entry.update_listeners
    return entry


async def test_options_reload_only_on_change(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, reloads: list
) -> None:
    """Core persists changed options before one reload and skips a no-op."""
    for start_time, expected in (("00:05:00", 0), ("02:00:00", 1), ("03:00:00", 2)):
        flow = await hass.config_entries.options.async_init(loaded_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"daily_poll_start_time": start_time}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert len(reloads) == expected
        if expected:
            assert reloads[-1][1] == {"daily_poll_start_time": start_time}
        assert not loaded_entry.update_listeners


@pytest.mark.parametrize("password", [ORIGINAL_CREDENTIAL, "new-password"])
async def test_reauth_reloads_once(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, reloads: list, password: str
) -> None:
    """Successful reauth reloads even when the credentials were unchanged."""
    flow = await loaded_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"email": EMAIL, "password": password}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(reloads) == 1
    assert reloads[0][0] == {"email": EMAIL, "password": password, "keep": True}
    assert hass.config_entries.async_entries(DOMAIN) == [loaded_entry]


async def test_reauth_recovers_a_failed_entry(
    hass: HomeAssistant, entry: MockConfigEntry, portal: AsyncMock, reloads: list
) -> None:
    """Reauth without data changes can recover a failed initial refresh."""
    portal.side_effect = GloBirdAuthError("Invalid credentials")
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    (flow,) = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["source"] == "reauth"

    portal.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"email": EMAIL, "password": ORIGINAL_CREDENTIAL}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(reloads) == 1
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("email", "reason", "expected_reloads"),
    [(EMAIL, "reconfigure_successful", 1), ("other@example.test", "wrong_account", 0)],
)
async def test_reconfigure_reloads_only_for_the_same_account(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    reloads: list,
    email: str,
    reason: str,
    expected_reloads: int,
) -> None:
    """Accept updated credentials for the same entry and reject account swaps."""
    flow = await loaded_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"email": email, "password": "updated-password"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert len(reloads) == expected_reloads
    if expected_reloads:
        assert reloads[0][0] == {
            "email": EMAIL,
            "password": "updated-password",
            "keep": True,
        }
    else:
        assert loaded_entry.data["password"] == ORIGINAL_CREDENTIAL


@pytest.mark.parametrize("source", ["reauth", "reconfigure"])
async def test_invalid_credentials_never_reload(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    portal: AsyncMock,
    reloads: list,
    source: str,
) -> None:
    """Invalid credentials redisplay the form without changing the entry."""
    start = (
        loaded_entry.start_reauth_flow
        if source == "reauth"
        else loaded_entry.start_reconfigure_flow
    )
    flow = await start(hass)
    portal.side_effect = GloBirdAuthError("Invalid credentials")
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"email": EMAIL, "password": "incorrect-password"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert not reloads
    assert loaded_entry.data["password"] == ORIGINAL_CREDENTIAL

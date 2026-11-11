"""Config flow for GloBird."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector

from .client import GloBirdAuthError, GloBirdCaptchaRequired, GloBirdClient
from .const import (
    CONF_DAILY_POLL_START_TIME,
    CONF_EMAIL,
    CONF_PASSWORD,
    DEFAULT_DAILY_POLL_START_TIME,
    DOMAIN,
)

if TYPE_CHECKING:
    import probatio as vol
else:
    # Core aliases this import to Probatio from 2026.9 onward.
    import voluptuous as vol

_LOGGER = logging.getLogger(__name__)


def _credentials_schema(default_email: str | None = None) -> vol.Schema:
    """Build the credentials form schema."""
    email_key = (
        vol.Required(CONF_EMAIL, default=default_email)
        if default_email
        else vol.Required(CONF_EMAIL)
    )
    return vol.Schema(
        {
            email_key: str,
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


class GloBirdConfigFlow(  # pyright: ignore[reportGeneralTypeIssues, reportCallIssue]
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for GloBird."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._reauth_entry: config_entries.ConfigEntry | None = None

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GloBirdOptionsFlow:
        """Create the options flow."""
        return GloBirdOptionsFlow()

    async def _async_validate_credentials(
        self, email: str, password: str
    ) -> dict[str, str]:
        """Validate portal credentials and return any flow error mapping."""
        errors: dict[str, str] = {}
        client = GloBirdClient()
        try:
            await client.authenticate(email, password)
        except GloBirdCaptchaRequired:
            errors["base"] = "captcha_required"
        except GloBirdAuthError:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected GloBird setup failure")
            errors["base"] = "cannot_connect"
        finally:
            await client.close()
        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = str(user_input[CONF_EMAIL]).strip()
            password = str(user_input[CONF_PASSWORD])

            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_credentials(email, password)
            if not errors:
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_credentials_schema(),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with GloBird."""
        if hasattr(self, "_get_reauth_entry"):
            self._reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication credentials."""
        reauth_entry = self._reauth_entry
        if reauth_entry is None and hasattr(self, "_get_reauth_entry"):
            reauth_entry = self._get_reauth_entry()
        default_email = (
            str(reauth_entry.data.get(CONF_EMAIL, ""))
            if reauth_entry is not None
            else ""
        )
        errors: dict[str, str] = {}

        if user_input is not None:
            email = str(user_input.get(CONF_EMAIL) or default_email).strip()
            password = str(user_input[CONF_PASSWORD])
            errors = await self._async_validate_credentials(email, password)
            if not errors:
                await self.async_set_unique_id(email.lower())
                if hasattr(self, "_abort_if_unique_id_mismatch"):
                    self._abort_if_unique_id_mismatch(reason="wrong_account")
                if reauth_entry is not None and hasattr(
                    self, "async_update_reload_and_abort"
                ):
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data_updates={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                        },
                    )
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_credentials_schema(default_email or None),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing GloBird config entry."""
        reconfigure_entry = (
            self._get_reconfigure_entry()
            if hasattr(self, "_get_reconfigure_entry")
            else None
        )
        default_email = (
            str(reconfigure_entry.data.get(CONF_EMAIL, ""))
            if reconfigure_entry is not None
            else ""
        )
        errors: dict[str, str] = {}

        if user_input is not None:
            email = str(user_input.get(CONF_EMAIL) or default_email).strip()
            password = str(user_input[CONF_PASSWORD])
            errors = await self._async_validate_credentials(email, password)
            if not errors:
                await self.async_set_unique_id(email.lower())
                if hasattr(self, "_abort_if_unique_id_mismatch"):
                    self._abort_if_unique_id_mismatch(reason="wrong_account")
                if reconfigure_entry is not None and hasattr(
                    self, "async_update_reload_and_abort"
                ):
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data_updates={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                        },
                    )
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_credentials_schema(default_email or None),
            errors=errors,
        )


class GloBirdOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle GloBird options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_time = self.config_entry.options.get(
            CONF_DAILY_POLL_START_TIME,
            DEFAULT_DAILY_POLL_START_TIME,
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DAILY_POLL_START_TIME,
                        default=current_time,
                    ): selector.TimeSelector(),
                }
            ),
        )

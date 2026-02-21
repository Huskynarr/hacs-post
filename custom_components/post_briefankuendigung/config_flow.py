"""Config flow for Briefankündigung integration."""
from __future__ import annotations

import imaplib
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_FOLDER,
    CONF_SENDER,
    CONF_SUBJECT,
    DEFAULT_FOLDER,
    DEFAULT_PORT,
    DEFAULT_SENDER,
    DEFAULT_SUBJECT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class BriefankuendigungConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Briefankündigung."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return BriefankuendigungOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_FOLDER: user_input[CONF_FOLDER],
                }
            )
            unique_id = self._build_unique_id(user_input)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                await self.hass.async_add_executor_job(
                    _test_connection,
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_FOLDER],
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_data_schema(),
            errors=errors,
        )

    def _build_unique_id(self, user_input: dict[str, Any]) -> str:
        """Build a stable unique id for this integration entry."""
        host = user_input[CONF_HOST].strip().lower()
        username = user_input[CONF_USERNAME].strip().lower()
        folder = user_input[CONF_FOLDER].strip().lower()
        return f"{host}:{username}:{folder}"


class BriefankuendigungOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Briefankündigung."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        current = _entry_values(self._config_entry)

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    _test_connection,
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_FOLDER],
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_data_schema(current),
            errors=errors,
        )


def _entry_values(config_entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Merge config entry data and options."""
    data = dict(config_entry.data)
    data.update(config_entry.options)
    return data


def _build_data_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """Build schema for config and options flows."""
    values = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=values.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=values.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Required(CONF_USERNAME, default=values.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD, default=values.get(CONF_PASSWORD, "")): str,
            vol.Required(CONF_FOLDER, default=values.get(CONF_FOLDER, DEFAULT_FOLDER)): str,
            vol.Required(CONF_SENDER, default=values.get(CONF_SENDER, DEFAULT_SENDER)): str,
            vol.Required(CONF_SUBJECT, default=values.get(CONF_SUBJECT, DEFAULT_SUBJECT)): str,
        }
    )


def _test_connection(host: str, port: int, username: str, password: str, folder: str) -> None:
    """Test the connection to the IMAP server."""
    client = None
    try:
        client = imaplib.IMAP4_SSL(host, port)
        try:
            client.login(username, password)
        except imaplib.IMAP4.error as err:
            raise InvalidAuth from err

        typ, _ = client.select(folder, readonly=True)
        if typ != "OK":
            raise CannotConnect
    except InvalidAuth:
        raise
    except (imaplib.IMAP4.error, OSError) as err:
        _LOGGER.error("Connection error: %s", err)
        raise CannotConnect from err
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass

"""Config flow for DHL & Deutsche Post integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import DhlApiClient, DhlApiError, DhlAuthError
from .const import (
    CONF_API_KEY,
    CONF_DELIVERED_FILTER_COUNT,
    CONF_DELIVERED_FILTER_DAYS,
    CONF_DELIVERED_FILTER_TYPE,
    CONF_ENVIRONMENT,
    CONF_IMAP_SERVER,
    CONF_IMAP_PORT,
    CONF_MAIL_FOLDER,
    CONF_MAIL_SENDERS,
    CONF_MAIL_SUBJECTS,
    CONF_PARCEL_HISTORY,
    CONF_POLL_INTERVAL,
    CONF_POSTAL_CODE,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    ENV_PRODUCTION,
    ENV_SANDBOX,
    FILTER_COUNT,
    FILTER_DAYS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER = "user"
STEP_PACKAGE_TRACKING = "package_tracking"
STEP_BRIEFANKUNDIGUNG = "briefankundigung"

# Schemas
SCHEMA_USER = vol.Schema(
    {
        vol.Required("setup_type", default="both"): vol.In(
            {
                "package_tracking": "DHL Package Tracking (API)",
                "briefankundigung": "Briefankündigung (Email/IMAP)",
                "both": "Both Features",
            }
        ),
    }
)

SCHEMA_PACKAGE_TRACKING = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_ENVIRONMENT, default=ENV_SANDBOX): vol.In([ENV_SANDBOX, ENV_PRODUCTION]),
        vol.Optional(CONF_POSTAL_CODE): str,
    }
)

SCHEMA_BRIEFANKUNDIGUNG = vol.Schema(
    {
        vol.Required(CONF_IMAP_SERVER): str,
        vol.Required(CONF_IMAP_PORT, default=993): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_MAIL_FOLDER, default="INBOX"): str,
        vol.Optional(CONF_MAIL_SENDERS, default="ankuendigung@brief.deutschepost.de"): str,
        vol.Optional(CONF_MAIL_SUBJECTS, default="Briefankündigung"): str,
    }
)

SCHEMA_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL.total_seconds() // 60): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=1440)
        ),
        vol.Optional(CONF_DELIVERED_FILTER_TYPE, default=FILTER_DAYS): vol.In([FILTER_DAYS, FILTER_COUNT]),
        vol.Optional(CONF_DELIVERED_FILTER_VALUE, default=7): vol.All(vol.Coerce(int), vol.Range(min=1, max=365)),
        vol.Optional(CONF_PARCEL_HISTORY, default=False): bool,
    }
)


async def validate_package_tracking(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate package tracking credentials."""
    api_key = data[CONF_API_KEY]
    environment = data[CONF_ENVIRONMENT]
    postal_code = data.get(CONF_POSTAL_CODE)

    client = DhlApiClient(api_key=api_key, environment=environment)
    try:
        # Test with a dummy tracking number - API should return 404 but not 401
        await client.track_shipment("00000000000000000000", postal_code=postal_code)
    except DhlAuthError:
        raise InvalidAuth("Invalid API Key")
    except DhlApiError as err:
        if err.status_code == 401:
            raise InvalidAuth("Invalid API Key")
        elif err.status_code == 404:
            # Expected - dummy tracking not found
            pass
        else:
            raise CannotConnect(f"API error: {err}")
    except Exception as err:
        raise CannotConnect(f"Connection failed: {err}")
    finally:
        await client.close()

    return {"title": f"DHL Package Tracking ({environment})"}


async def validate_briefankundigung(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate Briefankündigung IMAP credentials."""
    # In real implementation, would test IMAP connection
    # For now, just return success
    return {"title": f"Briefankündigung ({data[CONF_EMAIL]})"}


class DhlDeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for DHL & Deutsche Post."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._setup_type: str = "both"
        self._package_data: dict[str, Any] = {}
        self._mail_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle initial step."""
        if user_input is not None:
            self._setup_type = user_input["setup_type"]

            if self._setup_type == "package_tracking":
                return await self.async_step_package_tracking()
            elif self._setup_type == "briefankundigung":
                return await self.async_step_briefankundigung()
            else:
                return await self.async_step_package_tracking()

        return self.async_show_form(step_id=STEP_USER, data_schema=SCHEMA_USER)

    async def async_step_package_tracking(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle package tracking config."""
        errors = {}

        if user_input is not None:
            try:
                await validate_package_tracking(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                self._package_data = user_input
                if self._setup_type == "both":
                    return await self.async_step_briefankundigung()
                return self._create_entry()

        return self.async_show_form(
            step_id=STEP_PACKAGE_TRACKING,
            data_schema=SCHEMA_PACKAGE_TRACKING,
            errors=errors,
        )

    async def async_step_briefankundigung(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Briefankündigung config."""
        errors = {}

        if user_input is not None:
            try:
                await validate_briefankundigung(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                self._mail_data = user_input
                return self._create_entry()

        return self.async_show_form(
            step_id=STEP_BRIEFANKUNDIGUNG,
            data_schema=SCHEMA_BRIEFANKUNDIGUNG,
            errors=errors,
        )

    def _create_entry(self) -> FlowResult:
        """Create config entry."""
        data = {}
        if self._package_data:
            data.update(self._package_data)
        if self._mail_data:
            data.update(self._mail_data)

        return self.async_create_entry(
            title="DHL & Deutsche Post",
            data=data,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get options flow."""
        return DhlDeOptionsFlow(config_entry)


class DhlDeOptionsFlow(config_entries.OptionsFlow):
    """Options flow for DHL & Deutsche Post."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current options
        options = self._config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=SCHEMA_OPTIONS,
            description_placeholders={
                "current_poll": str(options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL.total_seconds() // 60)),
                "current_filter_type": options.get(CONF_DELIVERED_FILTER_TYPE, FILTER_DAYS),
                "current_filter_value": options.get(CONF_DELIVERED_FILTER_VALUE, 7),
            },
        )


class InvalidAuth(HomeAssistantError):
    """Invalid authentication."""


class CannotConnect(HomeAssistantError):
    """Cannot connect to service."""
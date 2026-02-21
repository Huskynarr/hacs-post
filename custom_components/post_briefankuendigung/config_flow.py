"""Config flow for Briefankündigung integration."""
import imaplib
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
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
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

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
                    self._test_connection,
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
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_FOLDER, default=DEFAULT_FOLDER): str,
                    vol.Required(CONF_SENDER, default=DEFAULT_SENDER): str,
                    vol.Required(CONF_SUBJECT, default=DEFAULT_SUBJECT): str,
                }
            ),
            errors=errors,
        )

    def _build_unique_id(self, user_input):
        """Build a stable unique id for this integration entry."""
        host = user_input[CONF_HOST].strip().lower()
        username = user_input[CONF_USERNAME].strip().lower()
        folder = user_input[CONF_FOLDER].strip().lower()
        return f"{host}:{username}:{folder}"

    def _test_connection(self, host, port, username, password, folder):
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

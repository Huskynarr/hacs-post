"""DHL & Deutsche Post integration for Home Assistant."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DhlApiClient, DhlAuthError, DhlApiError
from .coordinator import (
    PackageTrackingCoordinator,
    BriefankundigungCoordinator,
)
from .const import (
    CONF_API_KEY,
    CONF_ENVIRONMENT,
    CONF_IMAP_SERVER,
    CONF_IMAP_PORT,
    CONF_MAIL_FOLDER,
    CONF_MAIL_SENDERS,
    CONF_MAIL_SUBJECTS,
    CONF_POSTAL_CODE,
    DOMAIN,
    ENV_PRODUCTION,
    ENV_SANDBOX,
    PLATFORMS,
)
from .sensor import async_setup_entry as sensor_setup
from .camera import async_setup_entry as camera_setup

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DhlDeRuntimeData:
    """Runtime data for DHL & Deutsche Post config entry."""

    package_coordinator: PackageTrackingCoordinator | None = None
    mail_coordinator: BriefankundigungCoordinator | None = None
    api_client: DhlApiClient | None = None
    has_package_tracking: bool = False
    has_briefankundigung: bool = False


type DhlDeConfigEntry = ConfigEntry[DhlDeRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: DhlDeConfigEntry) -> bool:
    """Set up DHL & Deutsche Post from a config entry."""
    _LOGGER.debug("Setting up DHL & Deutsche Post integration")

    # Determine which features are enabled
    has_package = CONF_API_KEY in entry.data
    has_mail = CONF_IMAP_SERVER in entry.data

    runtime_data = DhlDeRuntimeData(
        has_package_tracking=has_package,
        has_briefankundigung=has_mail,
    )

    # Initialize package tracking if configured
    if has_package:
        try:
            session = async_get_clientsession(hass)
            api_client = DhlApiClient(
                api_key=entry.data[CONF_API_KEY],
                environment=entry.data.get(CONF_ENVIRONMENT, ENV_SANDBOX),
                session=session,
            )

            # Test authentication
            try:
                await api_client.track_shipment("00000000000000000000", postal_code=entry.data.get(CONF_POSTAL_CODE))
            except DhlAuthError as err:
                await api_client.close()
                raise ConfigEntryAuthFailed("Invalid API Key") from err
            except DhlApiError as err:
                if err.status_code == 404:
                    # Expected for dummy tracking number
                    pass
                elif err.status_code == 401:
                    await api_client.close()
                    raise ConfigEntryAuthFailed("Invalid API Key") from err
                else:
                    await api_client.close()
                    raise ConfigEntryNotReady(f"API error: {err}") from err

            coordinator = PackageTrackingCoordinator(hass, entry, api_client)
            runtime_data.package_coordinator = coordinator
            runtime_data.api_client = api_client

        except Exception as err:
            _LOGGER.error("Failed to initialize package tracking: %s", err)
            if not has_mail:
                raise

    # Initialize Briefankündigung if configured
    if has_mail:
        mail_coordinator = BriefankundigungCoordinator(hass, entry)
        runtime_data.mail_coordinator = mail_coordinator

    # Store runtime data
    entry.runtime_data = runtime_data

    # Forward setup to platforms
    platforms = []
    if has_package:
        platforms.append(Platform.SENSOR)
    if has_mail:
        platforms.extend([Platform.SENSOR, Platform.CAMERA])

    if platforms:
        await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info(
        "DHL & Deutsche Post setup complete: package=%s, mail=%s",
        has_package,
        has_mail,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DhlDeConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading DHL & Deutsche Post integration")

    # Unload platforms
    platforms = []
    if entry.runtime_data.has_package_tracking:
        platforms.append(Platform.SENSOR)
    if entry.runtime_data.has_briefankundigung:
        platforms.extend([Platform.SENSOR, Platform.CAMERA])

    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)

    # Clean up resources
    if entry.runtime_data.api_client:
        await entry.runtime_data.api_client.close()

    if unload_ok:
        _LOGGER.info("DHL & Deutsche Post unloaded successfully")

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: DhlDeConfigEntry) -> None:
    """Update options."""
    _LOGGER.debug("Updating options for DHL & Deutsche Post")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: DhlDeConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating config entry from version %s", entry.version)

    if entry.version == 1:
        # No migration needed yet
        pass

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: DhlDeConfigEntry, device_entry: Any
) -> bool:
    """Remove a config entry device."""
    # Only allow removal of dynamically created parcel/mail devices
    identifiers = device_entry.identifiers
    for identifier in identifiers:
        if identifier[0] == DOMAIN:
            # Allow removal of parcel and mail devices
            if identifier[1].startswith(("parcel_", "mail_")):
                return True
    return False
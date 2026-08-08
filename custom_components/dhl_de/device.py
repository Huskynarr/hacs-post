"""Device info helpers for DHL & Deutsche Post integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription

from .const import DOMAIN, MANUFACTURER


def get_package_tracking_device_info(config_entry_id: str, email: str) -> DeviceInfo:
    """Get device info for package tracking."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"package_{config_entry_id}")},
        name=f"DHL Package Tracking ({email})",
        manufacturer=MANUFACTURER,
        model="DHL Parcel DE Tracking API",
        sw_version="1.0.0",
        configuration_url="https://developer.dhl.com/",
    )


def get_briefankuendigung_device_info(config_entry_id: str, email: str) -> DeviceInfo:
    """Get device info for Briefankündigung."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"mail_{config_entry_id}")},
        name=f"Deutsche Post Briefankündigung ({email})",
        manufacturer=MANUFACTURER,
        model="Briefankündigung Email Parser",
        sw_version="1.0.0",
        configuration_url="https://www.deutschepost.de/briefankuendigung",
    )


def get_combined_device_info(config_entry_id: str, email: str) -> DeviceInfo:
    """Get combined device info for both features."""
    return DeviceInfo(
        identifiers={(DOMAIN, config_entry_id)},
        name=f"DHL & Deutsche Post ({email})",
        manufacturer=MANUFACTURER,
        model="DHL Parcel DE + Briefankündigung",
        sw_version="1.0.0",
        configuration_url="https://github.com/huskynarr/hacs-post",
    )


def get_parcel_device_info(
    config_entry_id: str,
    tracking_number: str,
    sender: str | None = None,
) -> DeviceInfo:
    """Get device info for individual parcel."""
    name_parts = ["DHL Paket", tracking_number[-8:]]
    if sender:
        name_parts.append(sender[:20])

    return DeviceInfo(
        identifiers={(DOMAIN, f"parcel_{config_entry_id}_{tracking_number}")},
        name=" ".join(name_parts),
        manufacturer=MANUFACTURER,
        model="DHL Paket",
        via_device=(DOMAIN, f"package_{config_entry_id}"),
    )


def get_mail_device_info(
    config_entry_id: str,
    mail_id: str,
    sender: str | None = None,
) -> DeviceInfo:
    """Get device info for individual mail item."""
    name_parts = ["Brief", mail_id[-8:]]
    if sender:
        name_parts.append(sender[:20])

    return DeviceInfo(
        identifiers={(DOMAIN, f"mail_{config_entry_id}_{mail_id}")},
        name=" ".join(name_parts),
        manufacturer=MANUFACTURER,
        model="Briefankündigung",
        via_device=(DOMAIN, f"mail_{config_entry_id}"),
    )
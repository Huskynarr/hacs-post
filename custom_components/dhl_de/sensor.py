"""Sensor platform for DHL & Deutsche Post integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DELIVERED_FILTER_COUNT,
    CONF_DELIVERED_FILTER_DAYS,
    CONF_PARCEL_HISTORY,
    DOMAIN,
    EVENT_PARCEL_DELIVERED,
    EVENT_PARCEL_DISCOVERED,
    EVENT_PARCEL_STATUS_CHANGED,
    ICON_CLOCK,
    ICON_MAILBOX,
    ICON_PACKAGE,
    ICON_PACKAGE_UP,
    ICON_TRUCK,
    SENSOR_AWAITING_PICKUP,
    SENSOR_DELIVERED_PARCELS,
    SENSOR_INCOMING_PARCELS,
    SENSOR_NEXT_DELIVERY,
    SENSOR_OUTGOING_DELIVERED,
    SENSOR_OUTGOING_PARCELS,
    SENSOR_PARCEL,
    SENSOR_MAIL,
    SENSOR_MAIL_COUNT,
    PARCEL_STATUS_CATEGORIES,
)
from .coordinator import PackageTrackingCoordinator, PackageTrackingData, ParcelData
from .device import get_parcel_device_info, get_package_tracking_device_info

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DhlParcelSensorDescription(SensorEntityDescription):
    """Description for DHL parcel sensor."""

    is_summary: bool = False
    parcel_key: str | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: PackageTrackingCoordinator = entry.runtime_data.package_coordinator

    entities = [
        DhlIncomingParcelsSensor(coordinator, entry),
        DhlNextDeliverySensor(coordinator, entry),
        DhlAwaitingPickupSensor(coordinator, entry),
        DhlDeliveredParcelsSensor(coordinator, entry),
        DhlOutgoingParcelsSensor(coordinator, entry),
        DhlOutgoingDeliveredSensor(coordinator, entry),
    ]

    # Per-parcel sensors (dynamic)
    entities.extend(_create_parcel_sensors(coordinator, entry))

    async_add_entities(entities)

    # Track new parcels
    def _handle_new_parcel(parcel: ParcelData) -> None:
        sensor = DhlParcelSensor(coordinator, entry, parcel.tracking_number)
        async_add_entities([sensor])

    entry.async_on_unload(
        coordinator.async_add_listener(lambda: _check_new_parcels(coordinator, entry, async_add_entities))
    )


def _check_new_parcels(
    coordinator: PackageTrackingCoordinator,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Check for new parcels and create sensors."""
    known = getattr(coordinator, "_known_parcels", set())
    current = {p.tracking_number for p in coordinator.data.incoming + coordinator.data.outgoing + coordinator.data.awaiting_pickup}
    new = current - known

    if new:
        sensors = [DhlParcelSensor(coordinator, entry, tn) for tn in new]
        async_add_entities(sensors)
        coordinator._known_parcels = current


def _create_parcel_sensors(
    coordinator: PackageTrackingCoordinator,
    entry: ConfigEntry,
) -> list[DhlParcelSensor]:
    """Create sensors for existing parcels."""
    sensors = []
    all_parcels = (
        coordinator.data.incoming
        + coordinator.data.outgoing
        + coordinator.data.awaiting_pickup
        + coordinator.data.delivered
        + coordinator.data.outgoing_delivered
    )
    for parcel in all_parcels:
        sensors.append(DhlParcelSensor(coordinator, entry, parcel.tracking_number))

    coordinator._known_parcels = {p.tracking_number for p in all_parcels}
    return sensors


class DhlBaseSensor(CoordinatorEntity[PackageTrackingCoordinator], SensorEntity):
    """Base DHL sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PackageTrackingCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = get_package_tracking_device_info(entry.entry_id, entry.data.get("email", ""))


class DhlIncomingParcelsSensor(DhlBaseSensor):
    """Incoming parcels count sensor."""

    _attr_icon = ICON_PACKAGE_UP
    _attr_translation_key = SENSOR_INCOMING_PARCELS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PackageTrackingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_INCOMING_PARCELS}"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.incoming)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "parcels": [self._parcel_to_dict(p) for p in self.coordinator.data.incoming],
            "count": len(self.coordinator.data.incoming),
        }

    def _parcel_to_dict(self, parcel: ParcelData) -> dict[str, Any]:
        return {
            "tracking_number": parcel.tracking_number,
            "status": parcel.status_category,
            "raw_status": parcel.raw_status,
            "sender": parcel.sender,
            "recipient": parcel.recipient,
            "estimated_delivery": parcel.estimated_delivery,
            "delivery_window_start": parcel.delivery_window_start,
            "delivery_window_end": parcel.delivery_window_end,
            "is_pickup": parcel.is_pickup,
            "pickup_location": parcel.pickup_location,
            "url": parcel.url,
            "weight": parcel.weight,
            "dimensions": parcel.dimensions,
            "events": parcel.events if self._entry.options.get(CONF_PARCEL_HISTORY, False) else None,
        }


class DhlNextDeliverySensor(DhlBaseSensor):
    """Next delivery sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = ICON_CLOCK
    _attr_translation_key = SENSOR_NEXT_DELIVERY

    def __init__(self, coordinator: PackageTrackingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_NEXT_DELIVERY}"

    @property
    def native_value(self) -> datetime | None:
        next_delivery = self.coordinator.data.next_delivery
        if next_delivery and next_delivery.estimated_delivery:
            try:
                return datetime.fromisoformat(next_delivery.estimated_delivery.replace("Z", "+00:00"))
            except Exception:
                pass
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        next_delivery = self.coordinator.data.next_delivery
        if next_delivery:
            return {
                "tracking_number": next_delivery.tracking_number,
                "sender": next_delivery.sender,
                "delivery_window_start": next_delivery.delivery_window_start,
                "delivery_window_end": next_delivery.delivery_window_end,
            }
        return {}


class DhlAwaitingPickupSensor(DhlBaseSensor):
    """Awaiting pickup sensor."""

    _attr_icon = ICON_PACKAGE
    _attr_translation_key = SENSOR_AWAITING_PICKUP
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PackageTrackingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_AWAITING_PICKUP}"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.awaiting_pickup)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "parcels": [self._parcel_to_dict(p) for p in self.coordinator.data.awaiting_pickup],
        }

    def _parcel_to_dict(self, parcel: ParcelData) -> dict[str, Any]:
        return {
            "tracking_number": parcel.tracking_number,
            "status": parcel.status_category,
            "raw_status": parcel.raw_status,
            "pickup_location": parcel.pickup_location,
            "url": parcel.url,
        }


class DhlDeliveredParcelsSensor(DhlBaseSensor):
    """Delivered parcels sensor."""

    _attr_icon = ICON_PACKAGE
    _attr_translation_key = SENSOR_DELIVERED_PARCELS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PackageTrackingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_DELIVERED_PARCELS}"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.delivered)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "parcels": [self._parcel_to_dict(p) for p in self.coordinator.data.delivered],
        }

    def _parcel_to_dict(self, parcel: ParcelData) -> dict[str, Any]:
        return {
            "tracking_number": parcel.tracking_number,
            "status": parcel.status_category,
            "raw_status": parcel.raw_status,
            "delivered_at": parcel.delivered_at,
            "sender": parcel.sender,
            "url": parcel.url,
        }


class DhlOutgoingParcelsSensor(DhlBaseSensor):
    """Outgoing parcels sensor."""

    _attr_icon = ICON_TRUCK
    _attr_translation_key = SENSOR_OUTGOING_PARCELS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PackageTrackingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_OUTGOING_PARCELS}"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.outgoing)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "parcels": [self._parcel_to_dict(p) for p in self.coordinator.data.outgoing],
        }

    def _parcel_to_dict(self, parcel: ParcelData) -> dict[str, Any]:
        return {
            "tracking_number": parcel.tracking_number,
            "status": parcel.status_category,
            "raw_status": parcel.raw_status,
            "sender": parcel.sender,
            "recipient": parcel.recipient,
            "estimated_delivery": parcel.estimated_delivery,
            "is_pickup": parcel.is_pickup,
            "pickup_location": parcel.pickup_location,
            "url": parcel.url,
        }


class DhlOutgoingDeliveredSensor(DhlBaseSensor):
    """Outgoing delivered parcels sensor."""

    _attr_icon = ICON_PACKAGE
    _attr_translation_key = SENSOR_OUTGOING_DELIVERED
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PackageTrackingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_OUTGOING_DELIVERED}"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.outgoing_delivered)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "parcels": [self._parcel_to_dict(p) for p in self.coordinator.data.outgoing_delivered],
        }

    def _parcel_to_dict(self, parcel: ParcelData) -> dict[str, Any]:
        return {
            "tracking_number": parcel.tracking_number,
            "status": parcel.status_category,
            "raw_status": parcel.raw_status,
            "delivered_at": parcel.delivered_at,
            "sender": parcel.sender,
            "url": parcel.url,
        }


class DhlParcelSensor(DhlBaseSensor):
    """Individual parcel sensor."""

    _attr_icon = ICON_PACKAGE
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(PARCEL_STATUS_CATEGORIES.values())

    def __init__(
        self,
        coordinator: PackageTrackingCoordinator,
        entry: ConfigEntry,
        tracking_number: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._tracking_number = tracking_number
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_PARCEL}_{tracking_number}"
        self._attr_translation_key = SENSOR_PARCEL
        self._attr_device_info = get_parcel_device_info(entry.entry_id, tracking_number)

    @property
    def native_value(self) -> str | None:
        parcel = self._get_parcel()
        return parcel.status_category if parcel else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        parcel = self._get_parcel()
        if not parcel:
            return {}

        attrs = {
            "tracking_number": parcel.tracking_number,
            "status": parcel.status_category,
            "raw_status": parcel.raw_status,
            "sender": parcel.sender,
            "recipient": parcel.recipient,
            "delivery_address": parcel.delivery_address,
            "estimated_delivery": parcel.estimated_delivery,
            "delivery_window_start": parcel.delivery_window_start,
            "delivery_window_end": parcel.delivery_window_end,
            "delivered": parcel.delivered,
            "delivered_at": parcel.delivered_at,
            "is_pickup": parcel.is_pickup,
            "pickup_location": parcel.pickup_location,
            "url": parcel.url,
            "weight": parcel.weight,
            "dimensions": parcel.dimensions,
            "service": parcel.service,
            "origin_country": parcel.origin_country,
            "destination_country": parcel.destination_country,
        }

        if self._entry.options.get(CONF_PARCEL_HISTORY, False):
            attrs["events"] = parcel.events

        return attrs

    def _get_parcel(self) -> ParcelData | None:
        for parcel in (
            self.coordinator.data.incoming
            + self.coordinator.data.outgoing
            + self.coordinator.data.awaiting_pickup
            + self.coordinator.data.delivered
            + self.coordinator.data.outgoing_delivered
        ):
            if parcel.tracking_number == self._tracking_number:
                return parcel
        return None
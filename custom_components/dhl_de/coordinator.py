"""Data update coordinators for DHL & Deutsche Post integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DhlApiClient, DhlApiError, DhlAuthError, DhlRateLimitError, Shipment
from .const import (
    ACTIVE_CATEGORIES,
    CONF_API_KEY,
    CONF_DELIVERED_FILTER_COUNT,
    CONF_DELIVERED_FILTER_DAYS,
    CONF_DELIVERED_FILTER_TYPE,
    CONF_ENVIRONMENT,
    CONF_PARCEL_HISTORY,
    CONF_POSTAL_CODE,
    DEFAULT_POLL_INTERVAL,
    EVENT_PARCEL_DELIVERED,
    EVENT_PARCEL_DISCOVERED,
    EVENT_PARCEL_STATUS_CHANGED,
    FILTER_COUNT,
    FILTER_DAYS,
    PARCEL_STATUS_CATEGORIES,
)
from .email_parser import MailItem, parse_briefankuendigung_email

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ParcelData:
    """Data for a parcel sensor."""

    tracking_number: str
    status: str
    raw_status: str
    status_category: str
    sender: str | None
    recipient: str | None
    delivery_address: dict[str, Any] | None
    estimated_delivery: str | None
    delivery_window_start: str | None
    delivery_window_end: str | None
    weight: float | None
    dimensions: dict[str, float] | None
    events: list[dict[str, Any]]
    is_pickup: bool
    pickup_location: str | None
    url: str | None
    delivered: bool
    delivered_at: str | None
    service: str | None
    origin_country: str | None
    destination_country: str | None
    last_updated: datetime


@dataclass(slots=True)
class PackageTrackingData:
    """Package tracking coordinator data."""

    incoming: list[ParcelData] = field(default_factory=list)
    outgoing: list[ParcelData] = field(default_factory=list)
    delivered: list[ParcelData] = field(default_factory=list)
    outgoing_delivered: list[ParcelData] = field(default_factory=list)
    awaiting_pickup: list[ParcelData] = field(default_factory=list)
    next_delivery: ParcelData | None = None
    last_update: datetime | None = None
    known_tracking_numbers: set[str] = field(default_factory=set)


class PackageTrackingCoordinator(DataUpdateCoordinator[PackageTrackingData]):
    """Coordinator for DHL package tracking."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api_client: DhlApiClient,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"DHL Package Tracking ({entry.data.get(CONF_API_KEY, '')[:8]})",
            update_interval=DEFAULT_POLL_INTERVAL,
        )
        self._entry = entry
        self._api_client = api_client
        self._postal_code = entry.data.get(CONF_POSTAL_CODE)
        self._data = PackageTrackingData()
        self._tracked_numbers: set[str] = set()

    @property
    def data(self) -> PackageTrackingData:
        """Return data with filters applied."""
        # Apply delivered filter
        filter_type = self._entry.options.get(CONF_DELIVERED_FILTER_TYPE, FILTER_DAYS)
        filter_value = self._entry.options.get(CONF_DELIVERED_FILTER_VALUE, 7)

        filtered_delivered = self._apply_delivered_filter(
            self._data.delivered, filter_type, filter_value
        )
        filtered_outgoing_delivered = self._apply_delivered_filter(
            self._data.outgoing_delivered, filter_type, filter_value
        )

        return PackageTrackingData(
            incoming=self._data.incoming,
            outgoing=self._data.outgoing,
            delivered=filtered_delivered,
            outgoing_delivered=filtered_outgoing_delivered,
            awaiting_pickup=self._data.awaiting_pickup,
            next_delivery=self._data.next_delivery,
            last_update=self._data.last_update,
            known_tracking_numbers=self._data.known_tracking_numbers,
        )

    def _apply_delivered_filter(
        self,
        parcels: list[ParcelData],
        filter_type: str,
        filter_value: int,
    ) -> list[ParcelData]:
        """Apply delivered parcels filter."""
        if filter_type == FILTER_DAYS:
            cutoff = datetime.now() - timedelta(days=filter_value)
            return [p for p in parcels if p.delivered_at and datetime.fromisoformat(p.delivered_at) >= cutoff]
        elif filter_type == FILTER_COUNT:
            return sorted(parcels, key=lambda p: p.delivered_at or "", reverse=True)[:filter_value]
        return parcels

    async def _async_update_data(self) -> PackageTrackingData:
        """Fetch and process package data."""
        if not self._tracked_numbers:
            return self._data

        try:
            shipments = await self._api_client.track_shipments(
                list(self._tracked_numbers),
                postal_code=self._postal_code,
            )
        except DhlAuthError as err:
            raise ConfigEntryAuthFailed("DHL authentication failed") from err
        except DhlRateLimitError as err:
            raise UpdateFailed(f"Rate limited: {err}") from err
        except DhlApiError as err:
            raise UpdateFailed(f"DHL API error: {err}") from err

        self._process_shipments(shipments)
        self._data.last_update = datetime.now()

        return self._data

    def _process_shipments(self, shipments: list[Shipment]) -> None:
        """Process shipments and update internal state."""
        new_incoming = []
        new_outgoing = []
        new_delivered = []
        new_outgoing_delivered = []
        new_awaiting_pickup = []

        current_tracking = set()

        for shipment in shipments:
            current_tracking.add(shipment.tracking_number)

            parcel = ParcelData(
                tracking_number=shipment.tracking_number,
                status=shipment.status,
                raw_status=shipment.raw_status,
                status_category=shipment.status_category,
                sender=shipment.sender,
                recipient=shipment.recipient,
                delivery_address=shipment.delivery_address,
                estimated_delivery=shipment.estimated_delivery,
                delivery_window_start=shipment.delivery_window_start,
                delivery_window_end=shipment.delivery_window_end,
                weight=shipment.weight,
                dimensions=shipment.dimensions,
                events=shipment.events,
                is_pickup=shipment.is_pickup,
                pickup_location=shipment.pickup_location,
                url=shipment.url,
                delivered=shipment.delivered,
                delivered_at=shipment.delivered_at,
                service=shipment.service,
                origin_country=shipment.origin_country,
                destination_country=shipment.destination_country,
                last_updated=datetime.now(),
            )

            # Check for status changes
            self._check_status_changes(parcel)

            # Categorize
            if shipment.delivered:
                if shipment.is_pickup or shipment.status_category == PARCEL_STATUS_CATEGORIES["AVAILABLE_FOR_PICKUP"]:
                    new_awaiting_pickup.append(parcel)
                elif shipment.service == "return" or "return" in (shipment.status or "").lower():
                    new_outgoing_delivered.append(parcel)
                else:
                    new_delivered.append(parcel)
            else:
                if shipment.is_pickup or shipment.status_category == PARCEL_STATUS_CATEGORIES["AVAILABLE_FOR_PICKUP"]:
                    new_awaiting_pickup.append(parcel)
                elif shipment.service == "return" or "return" in (shipment.status or "").lower():
                    new_outgoing.append(parcel)
                else:
                    new_incoming.append(parcel)

        # Update known tracking numbers
        self._tracked_numbers = current_tracking
        self._data.known_tracking_numbers = current_tracking

        # Update lists
        self._data.incoming = new_incoming
        self._data.outgoing = new_outgoing
        self._data.delivered = new_delivered
        self._data.outgoing_delivered = new_outgoing_delivered
        self._data.awaiting_pickup = new_awaiting_pickup

        # Calculate next delivery
        self._data.next_delivery = self._calculate_next_delivery()

    def _check_status_changes(self, parcel: ParcelData) -> None:
        """Check for status changes and fire events."""
        # Find existing parcel
        existing = None
        for p in self._data.incoming + self._data.outgoing + self._data.awaiting_pickup:
            if p.tracking_number == parcel.tracking_number:
                existing = p
                break

        if existing:
            # Status changed
            if existing.status_category != parcel.status_category:
                self.hass.bus.async_fire(
                    EVENT_PARCEL_STATUS_CHANGED,
                    {
                        "tracking_number": parcel.tracking_number,
                        "old_status": existing.status_category,
                        "new_status": parcel.status_category,
                        "old_raw_status": existing.raw_status,
                        "new_raw_status": parcel.raw_status,
                    },
                )

            # Delivered
            if not existing.delivered and parcel.delivered:
                self.hass.bus.async_fire(
                    EVENT_PARCEL_DELIVERED,
                    {
                        "tracking_number": parcel.tracking_number,
                        "delivered_at": parcel.delivered_at,
                        "sender": parcel.sender,
                    },
                )
        else:
            # New parcel discovered
            self.hass.bus.async_fire(
                EVENT_PARCEL_DISCOVERED,
                {
                    "tracking_number": parcel.tracking_number,
                    "status": parcel.status_category,
                    "sender": parcel.sender,
                    "estimated_delivery": parcel.estimated_delivery,
                },
            )

    def _calculate_next_delivery(self) -> ParcelData | None:
        """Calculate next delivery from active parcels."""
        candidates = []

        for parcel in self._data.incoming + self._data.outgoing + self._data.awaiting_pickup:
            if parcel.estimated_delivery:
                try:
                    dt = datetime.fromisoformat(parcel.estimated_delivery.replace("Z", "+00:00"))
                    candidates.append((dt, parcel))
                except Exception:
                    continue

        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        return None

    def add_tracking(self, tracking_number: str) -> None:
        """Add a tracking number."""
        self._tracked_numbers.add(tracking_number)

    def remove_tracking(self, tracking_number: str) -> None:
        """Remove a tracking number."""
        self._tracked_numbers.discard(tracking_number)


@dataclass(slots=True)
class BriefankundigungData:
    """Briefankündigung coordinator data."""

    mails: list[MailItem] = field(default_factory=list)
    today_count: int = 0
    last_update: datetime | None = None


class BriefankundigungCoordinator(DataUpdateCoordinator[BriefankundigungData]):
    """Coordinator for Deutsche Post Briefankündigung."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Deutsche Post Briefankündigung ({entry.data.get('email', '')})",
            update_interval=DEFAULT_POLL_INTERVAL,
        )
        self._entry = entry
        self._data = BriefankundigungData()

    @property
    def data(self) -> BriefankundigungData:
        """Return data with today's mails filtered."""
        today = datetime.now().date()
        today_mails = [m for m in self._data.mails if m.date.date() == today]

        return BriefankundigungData(
            mails=today_mails,
            today_count=len(today_mails),
            last_update=self._data.last_update,
        )

    async def _async_update_data(self) -> BriefankundigungData:
        """Fetch and parse emails."""
        # This would connect to IMAP in real implementation
        # For now, return existing data
        self._data.last_update = datetime.now()
        return self._data

    async def async_fetch_emails(self) -> list[MailItem]:
        """Fetch and parse emails from IMAP."""
        # Implementation would go here
        # This is a placeholder for the actual IMAP fetching logic
        return []


def get_delivered_filter_options() -> dict[str, Any]:
    """Get delivered filter options for config flow."""
    return {
        "type": "select",
        "options": {
            FILTER_DAYS: "Days",
            FILTER_COUNT: "Count",
        },
        "translation_key": "delivered_filter_type",
    }
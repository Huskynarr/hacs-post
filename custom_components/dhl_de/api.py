"""DHL API Client for Parcel DE Tracking."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import aiohttp
from dateutil import parser as date_parser

from .const import (
    API_BASE_PRODUCTION,
    API_BASE_SANDBOX,
    API_TRACK_ENDPOINT,
    DHL_STATUS_MAP,
    ENV_PRODUCTION,
    ENV_SANDBOX,
    PARCEL_STATUS_CATEGORIES,
)

_LOGGER = logging.getLogger(__name__)


class DhlApiError(Exception):
    """Base exception for DHL API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class DhlAuthError(DhlApiError):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401)


class DhlRateLimitError(DhlApiError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int | None = None):
        super().__init__(message, 429)
        self.retry_after = retry_after


class DhlNotFoundError(DhlApiError):
    """Resource not found."""

    def __init__(self, message: str = "Not found"):
        super().__init__(message, 404)


@dataclass(slots=True)
class Shipment:
    """Normalized shipment data."""

    tracking_number: str
    status: str
    raw_status: str
    status_category: str
    description: str | None
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


class DhlApiClient:
    """Client for DHL Parcel DE Tracking API."""

    def __init__(
        self,
        api_key: str,
        environment: str = ENV_SANDBOX,
        session: aiohttp.ClientSession | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize the client."""
        self._api_key = api_key
        self._environment = environment
        self._base_url = API_BASE_PRODUCTION if environment == ENV_PRODUCTION else API_BASE_SANDBOX
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._own_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request."""
        session = await self._get_session()
        url = f"{self._base_url}{endpoint}"

        headers = {
            "DHL-API-Key": self._api_key,
            "Accept": "application/json",
            "User-Agent": "HomeAssistant-DHL-DE/1.0.0",
        }

        _LOGGER.debug("DHL API request: %s %s params=%s", method, url, params)

        try:
            async with asyncio.timeout(self._timeout.total) as cm:
                async with session.request(
                    method, url, params=params, json=data, headers=headers
                ) as response:
                    response_text = await response.text()

                    _LOGGER.debug("DHL API response: %s %s", response.status, response_text[:500])

                    if response.status == 401:
                        raise DhlAuthError("Invalid API Key")
                    elif response.status == 429:
                        retry_after = response.headers.get("Retry-After")
                        raise DhlRateLimitError(
                            "Rate limit exceeded",
                            retry_after=int(retry_after) if retry_after else None,
                        )
                    elif response.status == 404:
                        raise DhlNotFoundError("Shipment not found")
                    elif response.status >= 400:
                        raise DhlApiError(
                            f"API error {response.status}: {response_text}",
                            status_code=response.status,
                        )

                    try:
                        return await response.json()
                    except Exception as err:
                        _LOGGER.error("Failed to parse JSON: %s", err)
                        raise DhlApiError(f"Invalid JSON response: {response_text}") from err

        except asyncio.TimeoutError:
            raise DhlApiError("Request timeout") from None
        except aiohttp.ClientError as err:
            raise DhlApiError(f"Connection error: {err}") from err

    async def track_shipments(
        self,
        tracking_numbers: list[str],
        postal_code: str | None = None,
        service: str | None = None,
        origin_country_code: str | None = None,
        requester_country_code: str = "DE",
    ) -> list[Shipment]:
        """Track one or more shipments."""
        if not tracking_numbers:
            return []

        if len(tracking_numbers) > 15:
            raise ValueError("Maximum 15 tracking numbers per request")

        params = {"trackingNumber": ",".join(tracking_numbers)}

        if postal_code:
            params["recipientPostalCode"] = postal_code
        if service:
            params["service"] = service
        if origin_country_code:
            params["originCountryCode"] = origin_country_code
        params["requesterCountryCode"] = requester_country_code

        data = await self._request("GET", API_TRACK_ENDPOINT, params=params)
        return self._parse_shipments(data)

    async def track_shipment(
        self,
        tracking_number: str,
        postal_code: str | None = None,
    ) -> Shipment | None:
        """Track a single shipment."""
        shipments = await self.track_shipments([tracking_number], postal_code)
        return shipments[0] if shipments else None

    def _parse_shipments(self, data: dict[str, Any]) -> list[Shipment]:
        """Parse API response into Shipment objects."""
        shipments = []

        # Unified Tracking API format
        if "shipments" in data:
            for shipment_data in data["shipments"]:
                try:
                    shipments.append(self._parse_shipment(shipment_data))
                except Exception as err:
                    _LOGGER.warning("Failed to parse shipment: %s", err)
                    continue

        return shipments

    def _parse_shipment(self, data: dict[str, Any]) -> Shipment:
        """Parse single shipment data."""
        tracking_number = data.get("trackingNumber", "")
        status = data.get("status", {}).get("status", "unknown")
        raw_status = data.get("status", {}).get("description", status)

        # Map to canonical category
        status_category = self._map_status(status)

        # Events
        events = []
        for event in data.get("events", []):
            events.append(self._parse_event(event))
        events.sort(key=lambda e: e["timestamp"])

        # Delivery info
        estimated_delivery = None
        delivery_window_start = None
        delivery_window_end = None

        if "estimatedDeliveryDateTime" in data:
            estimated_delivery = data["estimatedDeliveryDateTime"]
        if "deliveryWindow" in data:
            delivery_window_start = data["deliveryWindow"].get("start")
            delivery_window_end = data["deliveryWindow"].get("end")

        # Address
        delivery_address = None
        if "destination" in data:
            dest = data["destination"]
            delivery_address = {
                "street": dest.get("addressLocality"),
                "postal_code": dest.get("postalCode"),
                "city": dest.get("addressLocality"),
                "country": dest.get("countryCode"),
            }

        # Sender/Recipient
        sender = None
        recipient = None
        if "shipper" in data:
            sender = data["shipper"].get("name")
        if "receiver" in data:
            recipient = data["receiver"].get("name")

        # Weight/Dimensions
        weight = None
        dimensions = None
        if "weight" in data:
            weight = float(data["weight"].get("value", 0)) / 1000  # g to kg
        if "dimensions" in data:
            dim = data["dimensions"]
            dimensions = {
                "length": dim.get("length"),
                "width": dim.get("width"),
                "height": dim.get("height"),
            }

        # Pickup
        is_pickup = False
        pickup_location = None
        if "pickup" in data and data["pickup"].get("type"):
            is_pickup = True
            pickup_location = data["pickup"].get("location", {}).get("name")

        # URL
        url = f"https://www.dhl.de/de/privatkunden/pakete-empfangen/verfolgen.html?piececode={tracking_number}"

        # Delivered
        delivered = status_category == PARCEL_STATUS_CATEGORIES["DELIVERED"]
        delivered_at = None
        if delivered and events:
            delivered_at = events[-1]["timestamp"]

        return Shipment(
            tracking_number=tracking_number,
            status=status,
            raw_status=raw_status,
            status_category=status_category,
            description=data.get("status", {}).get("description"),
            sender=sender,
            recipient=recipient,
            delivery_address=delivery_address,
            estimated_delivery=estimated_delivery,
            delivery_window_start=delivery_window_start,
            delivery_window_end=delivery_window_end,
            weight=weight,
            dimensions=dimensions,
            events=events,
            is_pickup=is_pickup,
            pickup_location=pickup_location,
            url=url,
            delivered=delivered,
            delivered_at=delivered_at,
            service=data.get("service"),
            origin_country=data.get("origin", {}).get("countryCode"),
            destination_country=data.get("destination", {}).get("countryCode"),
        )

    def _parse_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Parse tracking event."""
        timestamp = event.get("timestamp") or event.get("dateTime")
        if timestamp:
            try:
                timestamp = date_parser.isoparse(timestamp).isoformat()
            except Exception:
                pass

        return {
            "timestamp": timestamp,
            "status": event.get("status", "unknown"),
            "description": event.get("description", ""),
            "location": event.get("location", {}).get("address", {}).get("addressLocality"),
        }

    def _map_status(self, status: str) -> str:
        """Map DHL status to canonical category."""
        status_lower = status.lower().replace(" ", "_")
        return DHL_STATUS_MAP.get(status_lower, PARCEL_STATUS_CATEGORIES["UNKNOWN"])
"""Tests for coordinators."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.dhl_de.coordinator import (
    BriefankundigungCoordinator,
    PackageTrackingCoordinator,
    PackageTrackingData,
    ParcelData,
)


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant."""
    hass = MagicMock()
    hass.bus.async_fire = MagicMock()
    return hass


@pytest.fixture
def mock_entry():
    """Create mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        "api_key": "test_key",
        "environment": "sandbox",
        "postal_code": "10115",
    }
    entry.options = {
        "delivered_filter_type": "days",
        "delivered_filter_value": 7,
        "parcel_history": False,
    }
    return entry


@pytest.fixture
def mock_api_client():
    """Create mock API client."""
    client = AsyncMock()
    client.track_shipments = AsyncMock()
    return client


@pytest.fixture
def coordinator(mock_hass, mock_entry, mock_api_client):
    """Create coordinator."""
    return PackageTrackingCoordinator(mock_hass, mock_entry, mock_api_client)


@pytest.mark.asyncio
async def test_coordinator_add_tracking(coordinator):
    """Test adding tracking number."""
    coordinator.add_tracking("00340434123456789012")
    assert "00340434123456789012" in coordinator._tracked_numbers


@pytest.mark.asyncio
async def test_coordinator_remove_tracking(coordinator):
    """Test removing tracking number."""
    coordinator.add_tracking("00340434123456789012")
    coordinator.remove_tracking("00340434123456789012")
    assert "00340434123456789012" not in coordinator._tracked_numbers


@pytest.mark.asyncio
async def test_coordinator_process_shipments(coordinator):
    """Test processing shipments."""
    from custom_components.dhl_de.api import Shipment

    shipments = [
        Shipment(
            tracking_number="00340434123456789012",
            status="delivered",
            raw_status="Zugestellt",
            status_category="delivered",
            description="Zugestellt",
            sender="Amazon",
            recipient="Max Mustermann",
            delivery_address={"city": "Berlin", "postal_code": "10115"},
            estimated_delivery="2024-01-15T10:00:00+01:00",
            delivery_window_start="2024-01-15T08:00:00+01:00",
            delivery_window_end="2024-01-15T18:00:00+01:00",
            weight=1.2,
            dimensions={"length": 30, "width": 20, "height": 10},
            events=[{"timestamp": "2024-01-15T10:00:00+01:00", "status": "delivered", "description": "Zugestellt"}],
            is_pickup=False,
            pickup_location=None,
            url="https://www.dhl.de/...",
            delivered=True,
            delivered_at="2024-01-15T10:00:00+01:00",
            service="parcel",
            origin_country="DE",
            destination_country="DE",
        )
    ]

    coordinator.add_tracking("00340434123456789012")
    coordinator._process_shipments(shipments)

    assert len(coordinator._data.delivered) == 1
    assert coordinator._data.delivered[0].tracking_number == "00340434123456789012"


@pytest.mark.asyncio
async def test_coordinator_delivered_filter_days(coordinator, mock_entry):
    """Test delivered filter by days."""
    mock_entry.options = {
        "delivered_filter_type": "days",
        "delivered_filter_value": 7,
        "parcel_history": False,
    }

    # Add old delivered parcel
    old_parcel = ParcelData(
        tracking_number="00000000000000000001",
        status="delivered",
        raw_status="Delivered",
        status_category="delivered",
        sender="Old Sender",
        recipient="Recipient",
        delivery_address=None,
        estimated_delivery=None,
        delivery_window_start=None,
        delivery_window_end=None,
        weight=None,
        dimensions=None,
        events=[],
        is_pickup=False,
        pickup_location=None,
        url=None,
        delivered=True,
        delivered_at=(datetime.now() - timedelta(days=10)).isoformat(),
        service=None,
        origin_country=None,
        destination_country=None,
        last_updated=datetime.now(),
    )

    # Add recent delivered parcel
    recent_parcel = ParcelData(
        tracking_number="00000000000000000002",
        status="delivered",
        raw_status="Delivered",
        status_category="delivered",
        sender="Recent Sender",
        recipient="Recipient",
        delivery_address=None,
        estimated_delivery=None,
        delivery_window_start=None,
        delivery_window_end=None,
        weight=None,
        dimensions=None,
        events=[],
        is_pickup=False,
        pickup_location=None,
        url=None,
        delivered=True,
        delivered_at=(datetime.now() - timedelta(days=3)).isoformat(),
        service=None,
        origin_country=None,
        destination_country=None,
        last_updated=datetime.now(),
    )

    coordinator._data.delivered = [old_parcel, recent_parcel]

    data = coordinator.data

    # Only recent should be in filtered data
    assert len(data.delivered) == 1
    assert data.delivered[0].tracking_number == "00000000000000000002"


@pytest.mark.asyncio
async def test_coordinator_delivered_filter_count(coordinator, mock_entry):
    """Test delivered filter by count."""
    mock_entry.options = {
        "delivered_filter_type": "count",
        "delivered_filter_value": 2,
        "parcel_history": False,
    }

    # Add 5 delivered parcels
    parcels = []
    for i in range(5):
        parcel = ParcelData(
            tracking_number=f"0000000000000000000{i}",
            status="delivered",
            raw_status="Delivered",
            status_category="delivered",
            sender=f"Sender {i}",
            recipient="Recipient",
            delivery_address=None,
            estimated_delivery=None,
            delivery_window_start=None,
            delivery_window_end=None,
            weight=None,
            dimensions=None,
            events=[],
            is_pickup=False,
            pickup_location=None,
            url=None,
            delivered=True,
            delivered_at=(datetime.now() - timedelta(days=i)).isoformat(),
            service=None,
            origin_country=None,
            destination_country=None,
            last_updated=datetime.now(),
        )
        parcels.append(parcel)

    coordinator._data.delivered = parcels

    data = coordinator.data

    # Only 2 most recent should be in filtered data
    assert len(data.delivered) == 2
    assert data.delivered[0].tracking_number == "00000000000000000000"
    assert data.delivered[1].tracking_number == "00000000000000000001"


@pytest.mark.asyncio
async def test_briefankundigung_coordinator(mock_hass, mock_entry):
    """Test Briefankündigung coordinator."""
    mock_entry.data = {
        "email": "user@example.com",
        "imap_server": "imap.gmx.net",
        "imap_port": 993,
    }

    coordinator = BriefankundigungCoordinator(mock_hass, mock_entry)

    # Test data property
    data = coordinator.data
    assert isinstance(data.mails, list)
    assert data.today_count == 0
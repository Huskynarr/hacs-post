"""Tests for sensors."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from custom_components.dhl_de.sensor import (
    DhlIncomingParcelsSensor,
    DhlNextDeliverySensor,
    DhlAwaitingPickupSensor,
    DhlDeliveredParcelsSensor,
    DhlOutgoingParcelsSensor,
    DhlOutgoingDeliveredSensor,
    DhlParcelSensor,
)
from custom_components.dhl_de.coordinator import PackageTrackingData, ParcelData


@pytest.fixture
def mock_coordinator():
    """Create mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = PackageTrackingData()
    coordinator._known_parcels = set()
    return coordinator


@pytest.fixture
def mock_entry():
    """Create mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"email": "user@example.com", "api_key": "test_key"}
    entry.options = {
        "delivered_filter_type": "days",
        "delivered_filter_value": 7,
        "parcel_history": False,
    }
    return entry


@pytest.fixture
def sample_parcel():
    """Create sample parcel data."""
    return ParcelData(
        tracking_number="00340434123456789012",
        status="in_transit",
        raw_status="Im Verteilerzentrum",
        status_category="in_transit",
        sender="Amazon",
        recipient="Max Mustermann",
        delivery_address={"city": "Berlin", "postal_code": "10115"},
        estimated_delivery="2024-01-15T10:00:00+01:00",
        delivery_window_start="2024-01-15T08:00:00+01:00",
        delivery_window_end="2024-01-15T18:00:00+01:00",
        weight=1.2,
        dimensions={"length": 30, "width": 20, "height": 10},
        events=[{"timestamp": "2024-01-14T14:00:00+01:00", "status": "in_transit", "description": "Im Verteilerzentrum"}],
        is_pickup=False,
        pickup_location=None,
        url="https://www.dhl.de/...",
        delivered=False,
        delivered_at=None,
        service="parcel",
        origin_country="DE",
        destination_country="DE",
        last_updated=datetime.now(),
    )


def test_incoming_parcels_sensor(mock_coordinator, mock_entry, sample_parcel):
    """Test incoming parcels sensor."""
    mock_coordinator.data.incoming = [sample_parcel]

    sensor = DhlIncomingParcelsSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 1
    attrs = sensor.extra_state_attributes
    assert attrs["count"] == 1
    assert len(attrs["parcels"]) == 1
    assert attrs["parcels"][0]["tracking_number"] == "00340434123456789012"


def test_next_delivery_sensor(mock_coordinator, mock_entry, sample_parcel):
    """Test next delivery sensor."""
    mock_coordinator.data.next_delivery = sample_parcel

    sensor = DhlNextDeliverySensor(mock_coordinator, mock_entry)

    assert sensor.native_value is not None
    attrs = sensor.extra_state_attributes
    assert attrs["tracking_number"] == "00340434123456789012"
    assert attrs["sender"] == "Amazon"


def test_awaiting_pickup_sensor(mock_coordinator, mock_entry, sample_parcel):
    """Test awaiting pickup sensor."""
    pickup_parcel = ParcelData(
        **{
            **sample_parcel.__dict__,
            "is_pickup": True,
            "pickup_location": "Packstation 123",
            "status_category": "available_for_pickup",
        }
    )
    mock_coordinator.data.awaiting_pickup = [pickup_parcel]

    sensor = DhlAwaitingPickupSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 1
    attrs = sensor.extra_state_attributes
    assert attrs["parcels"][0]["pickup_location"] == "Packstation 123"


def test_delivered_parcels_sensor(mock_coordinator, mock_entry, sample_parcel):
    """Test delivered parcels sensor."""
    delivered_parcel = ParcelData(
        **{
            **sample_parcel.__dict__,
            "delivered": True,
            "delivered_at": "2024-01-15T10:00:00+01:00",
            "status_category": "delivered",
        }
    )
    mock_coordinator.data.delivered = [delivered_parcel]

    sensor = DhlDeliveredParcelsSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 1
    attrs = sensor.extra_state_attributes
    assert attrs["parcels"][0]["delivered_at"] == "2024-01-15T10:00:00+01:00"


def test_outgoing_parcels_sensor(mock_coordinator, mock_entry, sample_parcel):
    """Test outgoing parcels sensor."""
    mock_coordinator.data.outgoing = [sample_parcel]

    sensor = DhlOutgoingParcelsSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 1


def test_outgoing_delivered_sensor(mock_coordinator, mock_entry, sample_parcel):
    """Test outgoing delivered parcels sensor."""
    delivered_parcel = ParcelData(
        **{
            **sample_parcel.__dict__,
            "delivered": True,
            "delivered_at": "2024-01-15T10:00:00+01:00",
            "status_category": "delivered",
        }
    )
    mock_coordinator.data.outgoing_delivered = [delivered_parcel]

    sensor = DhlOutgoingDeliveredSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 1


def test_parcel_sensor(mock_coordinator, mock_entry, sample_parcel):
    """Test individual parcel sensor."""
    mock_coordinator.data.incoming = [sample_parcel]

    sensor = DhlParcelSensor(mock_coordinator, mock_entry, "00340434123456789012")

    assert sensor.native_value == "in_transit"
    attrs = sensor.extra_state_attributes
    assert attrs["tracking_number"] == "00340434123456789012"
    assert attrs["sender"] == "Amazon"
    assert attrs["weight"] == 1.2
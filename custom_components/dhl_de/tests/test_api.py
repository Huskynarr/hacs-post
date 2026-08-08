"""Tests for DHL API client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.dhl_de.api import DhlApiClient, DhlApiError, DhlAuthError, DhlRateLimitError, Shipment


@pytest.fixture
def mock_session():
    """Create mock aiohttp session."""
    session = AsyncMock()
    session.closed = False
    return session


@pytest.fixture
def api_client(mock_session):
    """Create API client with mock session."""
    return DhlApiClient(api_key="test_key", environment="sandbox", session=mock_session)


@pytest.mark.asyncio
async def test_track_shipment_success(api_client, mock_session):
    """Test successful shipment tracking."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=json.dumps({
        "shipments": [{
            "trackingNumber": "00340434123456789012",
            "status": {"status": "delivered", "description": "Zugestellt"},
            "events": [
                {"timestamp": "2024-01-15T10:00:00Z", "status": "delivered", "description": "Zugestellt"}
            ],
            "destination": {"addressLocality": "Berlin", "postalCode": "10115", "countryCode": "DE"},
            "shipper": {"name": "Amazon"},
            "receiver": {"name": "Max Mustermann"},
            "weight": {"value": 1200},
            "dimensions": {"length": 300, "width": 200, "height": 100},
        }]
    }))
    mock_response.json = AsyncMock(return_value=json.loads(mock_response.text.return_value))

    mock_session.request = AsyncMock(return_value=mock_response)

    shipments = await api_client.track_shipments(["00340434123456789012"])

    assert len(shipments) == 1
    assert shipments[0].tracking_number == "00340434123456789012"
    assert shipments[0].status_category == "delivered"
    assert shipments[0].delivered is True
    assert shipments[0].sender == "Amazon"
    assert shipments[0].weight == 1.2


@pytest.mark.asyncio
async def test_track_shipment_auth_error(api_client, mock_session):
    """Test authentication error."""
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.text = AsyncMock(return_value="Unauthorized")
    mock_session.request = AsyncMock(return_value=mock_response)

    with pytest.raises(DhlAuthError):
        await api_client.track_shipments(["00340434123456789012"])


@pytest.mark.asyncio
async def test_track_shipment_rate_limit(api_client, mock_session):
    """Test rate limit error."""
    mock_response = AsyncMock()
    mock_response.status = 429
    mock_response.headers = {"Retry-After": "60"}
    mock_response.text = AsyncMock(return_value="Rate Limited")
    mock_session.request = AsyncMock(return_value=mock_response)

    with pytest.raises(DhlRateLimitError) as exc_info:
        await api_client.track_shipments(["00340434123456789012"])

    assert exc_info.value.retry_after == 60


@pytest.mark.asyncio
async def test_track_shipment_not_found(api_client, mock_session):
    """Test not found error."""
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.text = AsyncMock(return_value="Not Found")
    mock_session.request = AsyncMock(return_value=mock_response)

    with pytest.raises(DhlApiError) as exc_info:
        await api_client.track_shipments(["00340434123456789012"])

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_max_tracking_numbers(api_client):
    """Test max tracking numbers validation."""
    with pytest.raises(ValueError):
        await api_client.track_shipments(["1"] * 16)


@pytest.mark.asyncio
async def test_close_session(api_client, mock_session):
    """Test closing owned session."""
    api_client._own_session = True
    await api_client.close()
    mock_session.close.assert_called_once()


def test_status_mapping():
    """Test DHL status to canonical mapping."""
    from custom_components.dhl_de.api import DhlApiClient

    client = DhlApiClient(api_key="test")

    assert client._map_status("delivered") == "delivered"
    assert client._map_status("out_for_delivery") == "out_for_delivery"
    assert client._map_status("in_transit") == "in_transit"
    assert client._map_status("unknown_status") == "unknown"
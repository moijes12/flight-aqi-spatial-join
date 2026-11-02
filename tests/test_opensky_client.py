from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.clients.opensky_client import OpenSkyClient
from src.ingestion.schemas import FlightTelemetry


@pytest.fixture
def mock_state_vector():
    """Fixture returning a mock OpenSky StateVector-like object."""
    state = MagicMock()
    state.icao24 = "abc123"
    state.callsign = "BAW123"
    state.origin_country = "United Kingdom"
    state.longitude = -0.1278
    state.latitude = 51.5074
    state.baro_altitude = 10000.0
    return state


@pytest.mark.asyncio
async def test_fetch_flights_success(mock_state_vector: MagicMock):
    # Mock OpenSkyApi response structure
    mock_response = MagicMock()
    mock_response.states = [mock_state_vector]

    with patch("src.ingestion.clients.opensky_client.OpenSkyApi") as MockApiClass:
        mock_api_instance = MockApiClass.return_value
        mock_api_instance.get_states.return_value = mock_response

        client = OpenSkyClient(credentials_path="nonexistent_credentials.json")
        flights = await client.fetch_flight_data()

        assert len(flights) == 1
        assert isinstance(flights[0], FlightTelemetry)
        assert flights[0].icao24 == "abc123"
        assert flights[0].callsign == "BAW123"
        assert flights[0].longitude == -0.1278


@pytest.mark.asyncio
async def test_fetch_flights_api_error():
    with patch("src.ingestion.clients.opensky_client.OpenSkyApi") as MockApiClass:
        mock_api_instance = MockApiClass.return_value
        mock_api_instance.get_states.side_effect = Exception("API connection dropped")

        client = OpenSkyClient(credentials_path="nonexistent_credentials.json")
        flights = await client.fetch_flight_data()

        # Should handle exceptions gracefully and return an empty list
        assert flights == []

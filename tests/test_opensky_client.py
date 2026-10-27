import httpx2
import pytest

from src.ingestion.clients.opensky_client import OpenSkyClient


@pytest.mark.asyncio
async def test_opensky_client_success():
    # Mock successful OpenSky API response body
    mock_response_json = {
        "time": 1711800000,
        "states": [
            [
                "abc123",
                "BAW123",
                "United Kingdom",
                1711800000,
                1711800000,
                -0.1278,
                51.5074,
                1000.0,
                False,
                150.0,
                0.0,
                0.0,
                None,
                0.0,
                None,
                False,
                0,
            ]
        ],
    }

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=mock_response_json)

    transport = httpx2.MockTransport(handle_request)
    async with httpx2.AsyncClient(
        transport=transport, base_url="https://test"
    ) as client:
        opensky_client = OpenSkyClient()
        flights = await opensky_client.fetch_flights(client=client)

        assert len(flights) == 1
        assert flights[0].icao24 == "abc123"
        assert flights[0].callsign == "BAW123"
        assert flights[0].latitude == 51.5074


@pytest.mark.asyncio
async def test_opensky_client_rate_limit_retry():
    attempts = 0

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return httpx2.Response(429, json={"error": "Too Many Requests"})
        return httpx2.Response(200, json={"time": 1711800000, "states": []})

    transport = httpx2.MockTransport(handle_request)
    async with httpx2.AsyncClient(
        transport=transport, base_url="https://test"
    ) as client:
        opensky_client = OpenSkyClient(max_retries=3)
        flights = await opensky_client.fetch_flights(client=client)

        assert attempts == 2  # Succeeded on the second attempt after 429 retry
        assert flights == []

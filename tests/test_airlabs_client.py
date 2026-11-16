import httpx2
import pytest

from flight_aqi_spatial_join.clients.airlabs import AirLabsClient


@pytest.mark.asyncio
async def test_airlabs_client_maps_flights():
    def handle_request(request: httpx2.Request) -> httpx2.Response:
        assert request.url.params["bbox"] == "18.30,73.60,18.90,74.20"
        assert request.url.params["arr_iata"] == "PNQ"
        assert "api_key" in request.url.params
        return httpx2.Response(
            200,
            json={
                "response": [
                    {
                        "hex": "abc123",
                        "flight_iata": "AI101",
                        "arr_iata": "PNQ",
                        "flag": "IN",
                        "lat": 18.52,
                        "lng": 73.86,
                        "alt": 1000,
                        "v_speed": 2,
                    },
                    {
                        "hex": "other",
                        "flight_iata": "AI202",
                        "arr_iata": "DEL",
                        "lat": 18.6,
                        "lng": 73.9,
                    },
                    {"hex": "missing-coords"},
                ]
            },
        )

    transport = httpx2.MockTransport(handle_request)
    async with httpx2.AsyncClient(transport=transport) as client:
        client_under_test = AirLabsClient(
            "test-key", bbox="18.30,73.60,18.90,74.20", arr_iata="PNQ"
        )
        flights = await client_under_test.fetch_flights(client=client)

    assert len(flights) == 1
    assert flights[0].icao24 == "abc123"
    assert flights[0].callsign == "AI101"
    assert flights[0].latitude == 18.52

import httpx2
import pytest

from flight_aqi_spatial_join.clients.openaq import OpenAQClient


@pytest.mark.asyncio
async def test_openaq_client_requests_pm25_around_coordinates():
    mock_response_json = {
        "results": [
            {
                "id": 101,
                "name": "Test Air Station",
                "coordinates": {"latitude": 18.52, "longitude": 73.85},
                "sensors": [
                    {
                        "id": 501,
                        "parameter": {"name": "pm25", "units": "µg/m³"},
                        "latest": {
                            "value": 35.2,
                            "datetime": {"utc": "2026-03-30T14:00:00Z"},
                        },
                    }
                ],
            }
        ],
    }

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        assert request.headers.get("X-API-Key") == "fake-test-key"
        assert request.url.params["coordinates"] == "18.5204,73.8567"
        assert request.url.params["parameters_id"] == "2"
        assert request.url.params["radius"] == "25000"
        return httpx2.Response(200, json=mock_response_json)

    transport = httpx2.MockTransport(handle_request)
    async with httpx2.AsyncClient(transport=transport) as client:
        openaq_client = OpenAQClient(api_key="fake-test-key")
        sensors = await openaq_client.fetch_pm25_sensors(
            latitude=18.5204,
            longitude=73.8567,
            radius_meters=25000,
            client=client,
        )

    assert len(sensors) == 1
    assert sensors[0].sensor_id == 501
    assert sensors[0].pm25_value == 35.2


@pytest.mark.asyncio
async def test_openaq_client_fills_pm25_from_latest_endpoint():
    def handle_request(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/latest"):
            return httpx2.Response(
                200,
                json={
                    "results": [
                        {
                            "sensorsId": 501,
                            "value": 41.5,
                            "datetime": {"utc": "2026-11-16T12:00:00Z"},
                        }
                    ]
                },
            )
        return httpx2.Response(
            200,
            json={
                "results": [
                    {
                        "id": 101,
                        "name": "Pune Station",
                        "coordinates": {"latitude": 18.52, "longitude": 73.85},
                        "sensors": [
                            {
                                "id": 501,
                                "parameter": {"name": "pm25", "units": "µg/m³"},
                            }
                        ],
                    }
                ]
            },
        )

    transport = httpx2.MockTransport(handle_request)
    async with httpx2.AsyncClient(transport=transport) as client:
        sensors = await OpenAQClient(api_key="fake-test-key").fetch_pm25_sensors(
            latitude=18.5822,
            longitude=73.9197,
            radius_meters=25000,
            client=client,
        )

    assert sensors[0].pm25_value == 41.5
    assert sensors[0].measured_at == "2026-11-16T12:00:00Z"

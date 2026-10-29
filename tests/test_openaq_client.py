import httpx2
import pytest

from src.ingestion.clients.openaq_client import OpenAQClient


@pytest.mark.asyncio
async def test_openaq_client_success():
    mock_response_json = {
        "meta": {"found": 1},
        "results": [
            {
                "id": 101,
                "name": "Test Air Station",
                "coordinates": {"latitude": 12.9716, "longitude": 77.5946},
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
        return httpx2.Response(200, json=mock_response_json)

    transport = httpx2.MockTransport(handle_request)
    async with httpx2.AsyncClient(
        transport=transport, base_url="https://test"
    ) as client:
        openaq_client = OpenAQClient(api_key="fake-test-key")
        sensors = await openaq_client.fetch_pm25_sensors(client=client)

        assert len(sensors) == 1
        assert sensors[0].sensor_id == 501
        assert sensors[0].pm25_value == 35.2
        assert sensors[0].latitude == 12.9716

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FlightTelemetry(BaseModel):
    icao24: str
    callsign: str | None = None
    origin_country: str
    longitude: float | None = None
    latitude: float | None = None
    baro_altitude: float | None = None
    vertical_rate: float | None = None
    timestamp: int = Field(
        default_factory=lambda: int(datetime.now(tz=UTC).timestamp())
    )

    @field_validator("callsign", mode="before")
    @classmethod
    def validate_callsign(cls, v: Any) -> str | None:
        if isinstance(v, str):
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None

    @classmethod
    def from_opensky_vector(cls, vector: list[Any]) -> FlightTelemetry | None:
        """Parse raw OpenSky state vector list into a validated FlightTelemetry model."""
        if not vector or len(vector) < 17:
            return None

        longitude = vector[5]
        lattitude = vector[6]

        if longitude is None or lattitude is None:
            return None

        return cls(
            icao24=str(vector[0]),
            callsign=vector[1],
            origin_country=str(vector[2]),
            longitude=float(longitude),
            latitude=float(lattitude),
            baro_altitude=float(vector[7]) if vector[7] is not None else None,
            vertical_rate=float(vector[13]) if vector[13] is not None else None,
        )


class AirQualitySensor(BaseModel):
    """Pydantic model for OpenAQ v3 air quality monitoring locations and PM2.5 readings."""

    sensor_id: int
    location_id: int
    location_name: str
    latitude: float
    longitude: float
    pm25_value: float | None = None
    measured_at: str | None = None

    @classmethod
    def from_openaq_location(cls, location: dict[str, Any]) -> list[AirQualitySensor]:
        """Extract PM2.5 sensors from an OpenAQ v3 location dictionary."""
        sensors_extracted = []
        loc_id = location.get("id", None)
        loc_name = location.get("name", "Unknown Station")
        coords = location.get("coordinates", {})
        lat = coords.get("latitude")
        lon = coords.get("longitude")

        if lat is None or lon is None:
            return []

        for sensor in location.get("sensors", []):
            param = sensor.get("parameter", {})
            # Check for PM2.5 parameter
            if param.get("name") == "pm25" or param.get("units") == "µg/m³":
                latest = sensor.get("latest", {})
                value = latest.get("value")
                datetime_info = latest.get("datetime", {}).get("utc")
                if loc_id is not None:
                    sensors_extracted.append(
                        cls(
                            sensor_id=int(sensor.get("id", 0)),
                            location_id=int(loc_id),
                            location_name=str(loc_name),
                            latitude=float(lat),
                            longitude=float(lon),
                            pm25_value=float(value) if value is not None else None,
                            measured_at=str(datetime_info) if datetime_info else None,
                        )
                    )
        return sensors_extracted

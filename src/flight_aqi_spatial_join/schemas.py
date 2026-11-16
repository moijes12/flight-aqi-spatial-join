from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FlightTelemetry(BaseModel):
    """Live aircraft position from AirLabs."""

    icao24: str
    callsign: str | None = None
    origin_country: str
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    baro_altitude: float | None = None
    vertical_rate: float | None = None
    timestamp: int = Field(
        default_factory=lambda: int(datetime.now(tz=UTC).timestamp())
    )

    @field_validator("callsign", mode="before")
    @classmethod
    def validate_callsign(cls, value: Any) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return None

    @classmethod
    def from_airlabs(cls, item: dict[str, Any]) -> "FlightTelemetry | None":
        """Map one AirLabs flights API object into FlightTelemetry."""
        latitude = item.get("lat")
        longitude = item.get("lng")
        icao24 = item.get("hex") or item.get("icao24")
        if latitude is None or longitude is None or not icao24:
            return None

        altitude = item.get("alt")
        vertical_speed = item.get("v_speed", item.get("vs"))
        return cls(
            icao24=str(icao24),
            callsign=flight_code(item),
            origin_country=str(item.get("flag") or "UNKNOWN"),
            longitude=float(longitude),
            latitude=float(latitude),
            baro_altitude=float(altitude) if altitude is not None else None,
            vertical_rate=float(vertical_speed) if vertical_speed is not None else None,
        )


def _clean(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def flight_code(item: dict[str, Any]) -> str | None:
    """Passenger flight number: IATA code, else airline prefix plus number."""
    flight_iata = _clean(item.get("flight_iata"))
    if flight_iata:
        return flight_iata
    airline_iata = _clean(item.get("airline_iata"))
    number = _clean(item.get("flight_number"))
    if airline_iata and number and number.isdigit():
        return f"{airline_iata}{number}"
    return (
        _clean(item.get("flight_icao"))
        or _clean(item.get("reg_number"))
        or _clean(item.get("reg"))
    )


class AirQualitySensor(BaseModel):
    """OpenAQ v3 location reduced to its latest PM2.5 reading."""

    sensor_id: int
    location_id: int
    location_name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    pm25_value: float | None = None
    measured_at: str | None = None

    @classmethod
    def from_openaq_location(cls, location: dict[str, Any]) -> list["AirQualitySensor"]:
        """Extract PM2.5 sensors from an OpenAQ v3 location."""
        location_id = location.get("id")
        coordinates = location.get("coordinates") or {}
        latitude = coordinates.get("latitude")
        longitude = coordinates.get("longitude")
        if location_id is None or latitude is None or longitude is None:
            return []

        sensors: list[AirQualitySensor] = []
        for sensor in location.get("sensors") or []:
            parameter = sensor.get("parameter") or {}
            if parameter.get("name") != "pm25":
                continue
            latest = sensor.get("latest") or {}
            value = latest.get("value")
            measured_at = (latest.get("datetime") or {}).get("utc")
            sensors.append(
                cls(
                    sensor_id=int(sensor.get("id") or 0),
                    location_id=int(location_id),
                    location_name=str(location.get("name") or "Unknown Station"),
                    latitude=float(latitude),
                    longitude=float(longitude),
                    pm25_value=float(value) if value is not None else None,
                    measured_at=str(measured_at) if measured_at else None,
                )
            )
        return sensors

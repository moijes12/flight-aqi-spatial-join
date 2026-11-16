import pytest

from flight_aqi_spatial_join.config import Settings


def test_from_env_uses_latest_secret_versions(monkeypatch):
    seen: list[tuple[str, str]] = []

    def fake_access(project_id: str, secret_id: str) -> str:
        seen.append((project_id, secret_id))
        return f"value-{secret_id}"

    monkeypatch.setattr(
        "flight_aqi_spatial_join.config.access_latest_secret", fake_access
    )
    monkeypatch.setenv("PROJECT_ID", "flight-aqi-spatial-join")

    settings = Settings.from_env()

    assert seen == [
        ("flight-aqi-spatial-join", "OPENAQ_API_KEY"),
        ("flight-aqi-spatial-join", "AIRLABS_API_KEY"),
    ]
    assert settings.openaq_api_key == "value-OPENAQ_API_KEY"
    assert settings.airlabs_api_key == "value-AIRLABS_API_KEY"


def test_from_env_falls_back_to_environment(monkeypatch):
    def fail_access(project_id: str, secret_id: str) -> str:
        raise RuntimeError("secret unavailable")

    monkeypatch.setattr(
        "flight_aqi_spatial_join.config.access_latest_secret", fail_access
    )
    monkeypatch.setenv("OPENAQ_API_KEY", "env-openaq")
    monkeypatch.setenv("AIRLABS_API_KEY", "env-airlabs")

    settings = Settings.from_env()

    assert settings.openaq_api_key == "env-openaq"
    assert settings.airlabs_api_key == "env-airlabs"


def test_from_env_errors_when_secret_and_env_are_missing(monkeypatch):
    monkeypatch.setattr(
        "flight_aqi_spatial_join.config.access_latest_secret",
        lambda project_id, secret_id: "",
    )
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    monkeypatch.delenv("AIRLABS_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAQ_API_KEY"):
        Settings.from_env()

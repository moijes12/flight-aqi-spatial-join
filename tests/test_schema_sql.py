from flight_aqi_spatial_join.bigquery_sink import SCHEMA_PATH


def test_schema_creates_fact_table_without_replacing_the_live_view():
    script = SCHEMA_PATH.read_text(encoding="utf-8")
    statements = [part.strip() for part in script.split(";") if part.strip()]
    assert len(statements) == 4
    assert "fct_flight_air_quality" in statements[1]
    assert "flight_station_matches" in statements[2]
    assert "v_flight_aqi_spatial_join" in statements[3]

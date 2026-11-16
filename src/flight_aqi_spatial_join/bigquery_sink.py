from pathlib import Path
from typing import Any

from google.cloud import bigquery
from loguru import logger

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "infra" / "schema.sql"


class BigQuerySink:
    """Ensure the analytics table exists and append spatial-join rows."""

    def __init__(self, project_id: str, table_id: str, location: str) -> None:
        self._client = bigquery.Client(project=project_id, location=location)
        self._table_id = table_id

    def ensure_schema(self) -> None:
        script = SCHEMA_PATH.read_text(encoding="utf-8")
        statements = [part.strip() for part in script.split(";") if part.strip()]
        for statement in statements:
            self._client.query(statement).result()
        logger.info("BigQuery schema is present in {}.", self._client.location)

    def write(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            logger.info("No spatial matches to load into {}.", self._table_id)
            return 0
        errors = self._client.insert_rows_json(self._table_id, rows)
        if errors:
            raise RuntimeError(f"BigQuery insert failed: {errors}")
        logger.info("Loaded {} rows into {}.", len(rows), self._table_id)
        return len(rows)

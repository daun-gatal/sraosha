import logging
import uuid
from datetime import datetime, timezone

import duckdb

from sraosha.drift.metrics import MetricDefinition, MetricType, MetricValue

logger = logging.getLogger(__name__)


class DriftScanner:
    """
    Computes statistical metrics for a dataset using DuckDB.
    Works with any source DuckDB can read: Parquet, CSV, Delta, Postgres.
    """

    def __init__(self, source: str, source_type: str = "parquet"):
        self.source = source
        self.source_type = source_type
        self.conn = duckdb.connect()
        self._register_source()

    def _register_source(self) -> None:
        if self.source_type == "parquet":
            self.conn.execute(
                f"CREATE OR REPLACE VIEW source_data AS SELECT * FROM read_parquet('{self.source}')"
            )
        elif self.source_type == "csv":
            self.conn.execute(
                "CREATE OR REPLACE VIEW source_data AS "
                f"SELECT * FROM read_csv_auto('{self.source}')"
            )
        elif self.source_type == "memory":
            pass
        else:
            logger.warning("Source type '%s' — assuming direct SQL access", self.source_type)

    def compute(self, metrics: list[MetricDefinition]) -> list[MetricValue]:
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        results: list[MetricValue] = []

        for metric in metrics:
            try:
                value = self._compute_single(metric)
                results.append(
                    MetricValue(
                        metric_type=metric.metric_type,
                        table=metric.table,
                        column=metric.column,
                        value=value,
                        run_id=run_id,
                        measured_at=now,
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to compute %s for %s.%s",
                    metric.metric_type.value,
                    metric.table,
                    metric.column,
                )

        return results

    def _compute_single(self, metric: MetricDefinition) -> float:
        dispatch = {
            MetricType.NULL_RATE: self._compute_null_rate,
            MetricType.ROW_COUNT: self._compute_row_count,
            MetricType.ROW_COUNT_DELTA: self._compute_row_count,
            MetricType.DUPLICATE_RATE: self._compute_duplicate_rate,
        }
        fn = dispatch.get(metric.metric_type)
        if fn is None:
            raise ValueError(f"Unsupported metric type: {metric.metric_type}")

        if metric.metric_type in (MetricType.NULL_RATE, MetricType.DUPLICATE_RATE):
            if metric.column is None:
                raise ValueError(f"{metric.metric_type} requires a column name")
            return fn(metric.table, metric.column)
        return fn(metric.table)

    def _compute_null_rate(self, table: str, column: str) -> float:
        result = self.conn.execute(
            f"SELECT COUNT(*) FILTER (WHERE \"{column}\" IS NULL)::DOUBLE / COUNT(*)::DOUBLE "
            f"FROM source_data"
        ).fetchone()
        return result[0] if result and result[0] is not None else 0.0

    def _compute_row_count(self, table: str, _column: str | None = None) -> float:
        result = self.conn.execute("SELECT COUNT(*) FROM source_data").fetchone()
        return float(result[0]) if result else 0.0

    def _compute_duplicate_rate(self, table: str, column: str) -> float:
        result = self.conn.execute(
            f"SELECT 1.0 - (COUNT(DISTINCT \"{column}\")::DOUBLE / COUNT(*)::DOUBLE) "
            f"FROM source_data"
        ).fetchone()
        return result[0] if result and result[0] is not None else 0.0

    def close(self) -> None:
        self.conn.close()

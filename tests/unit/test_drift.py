
import duckdb

from sraosha.drift.metrics import MetricDefinition, MetricType
from sraosha.drift.scanner import DriftScanner


class TestDriftScanner:
    def _create_parquet(self, rows: list[dict], path: str) -> None:
        conn = duckdb.connect()
        cols = rows[0].keys()
        col_values = {c: [r[c] for r in rows] for c in cols}
        query_parts = []
        for c in cols:
            vals = col_values[c]
            formatted = ", ".join(
                "NULL" if v is None else (f"'{v}'" if isinstance(v, str) else str(v))
                for v in vals
            )
            query_parts.append(f"UNNEST([{formatted}]) AS \"{c}\"")
        query = f"SELECT {', '.join(query_parts)}"
        conn.execute(f"COPY ({query}) TO '{path}' (FORMAT PARQUET)")
        conn.close()

    def test_null_rate(self, tmp_path):
        parquet_file = str(tmp_path / "data.parquet")
        rows = [
            {"customer_id": "a", "order_total": 10},
            {"customer_id": None, "order_total": 20},
            {"customer_id": "c", "order_total": 30},
            {"customer_id": None, "order_total": 40},
            {"customer_id": "e", "order_total": 50},
        ]
        self._create_parquet(rows, parquet_file)

        scanner = DriftScanner(parquet_file, source_type="parquet")
        metrics = [
            MetricDefinition(MetricType.NULL_RATE, "orders", "customer_id", 0.02, 0.05),
        ]
        results = scanner.compute(metrics)
        scanner.close()

        assert len(results) == 1
        assert results[0].metric_type == MetricType.NULL_RATE
        assert abs(results[0].value - 0.4) < 0.01  # 2/5 = 0.4

    def test_row_count(self, tmp_path):
        parquet_file = str(tmp_path / "data.parquet")
        rows = [{"id": i, "name": f"item_{i}"} for i in range(100)]
        self._create_parquet(rows, parquet_file)

        scanner = DriftScanner(parquet_file, source_type="parquet")
        metrics = [
            MetricDefinition(MetricType.ROW_COUNT, "orders", None, None, None),
        ]
        results = scanner.compute(metrics)
        scanner.close()

        assert len(results) == 1
        assert results[0].value == 100.0

    def test_duplicate_rate(self, tmp_path):
        parquet_file = str(tmp_path / "data.parquet")
        rows = [
            {"id": 1, "name": "a"},
            {"id": 1, "name": "b"},
            {"id": 2, "name": "c"},
            {"id": 3, "name": "d"},
        ]
        self._create_parquet(rows, parquet_file)

        scanner = DriftScanner(parquet_file, source_type="parquet")
        metrics = [
            MetricDefinition(MetricType.DUPLICATE_RATE, "orders", "id", 0.1, 0.3),
        ]
        results = scanner.compute(metrics)
        scanner.close()

        assert len(results) == 1
        assert abs(results[0].value - 0.25) < 0.01  # 1 - 3/4 = 0.25

    def test_multiple_metrics(self, tmp_path):
        parquet_file = str(tmp_path / "data.parquet")
        rows = [
            {"customer_id": "a", "order_total": 10},
            {"customer_id": None, "order_total": 20},
            {"customer_id": "c", "order_total": 30},
        ]
        self._create_parquet(rows, parquet_file)

        scanner = DriftScanner(parquet_file, source_type="parquet")
        metrics = [
            MetricDefinition(MetricType.NULL_RATE, "orders", "customer_id", 0.02, 0.05),
            MetricDefinition(MetricType.ROW_COUNT, "orders", None, None, None),
        ]
        results = scanner.compute(metrics)
        scanner.close()

        assert len(results) == 2
        null_rate = next(r for r in results if r.metric_type == MetricType.NULL_RATE)
        row_count = next(r for r in results if r.metric_type == MetricType.ROW_COUNT)
        assert abs(null_rate.value - 1 / 3) < 0.01
        assert row_count.value == 3.0

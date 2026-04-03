from __future__ import annotations

import io
import logging
import time
import traceback
from dataclasses import dataclass
from typing import Any

from sraosha.dq.config_builder import build_datasource_config, sanitize_data_source_name

_SODA_INSTALL_HINT = (
    "soda-core is required for data quality checks but is not installed. "
    "Install it with: pip install soda-core  "
    "(plus a connector for your database, e.g. pip install soda-core-postgres). "
    "See the Dockerfile for the full list of available connectors."
)


def _import_soda():
    """Lazy-import soda-core; raises a friendly error when missing."""
    try:
        from soda.execution.check_outcome import CheckOutcome
        from soda.scan import Scan
    except ImportError:
        raise ImportError(_SODA_INSTALL_HINT) from None
    return Scan, CheckOutcome


@dataclass
class DQRunResult:
    status: str
    checks_total: int
    checks_passed: int
    checks_warned: int
    checks_failed: int
    results: list[dict[str, Any]]
    diagnostics: list[dict[str, Any]]
    log: str
    duration_seconds: float


def _all_checks(scan: Any) -> list[Any]:
    fn = getattr(scan, "get_all_checks", None)
    if callable(fn):
        return fn()
    return scan._checks


def _outcome_status(scan: Any) -> str:
    if scan.has_error_logs():
        return "error"
    if scan.has_check_fails():
        return "failed"
    if scan.has_check_warns():
        return "warned"
    return "passed"


def _measured_values(check: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for metric in check.metrics.values():
        name = getattr(metric, "name", None)
        val = getattr(metric, "value", None)
        if name is not None:
            out[str(name)] = val
    return out


def _pick_measured_value(values: dict[str, Any]) -> Any:
    if not values:
        return None
    if len(values) == 1:
        return next(iter(values.values()))
    return values


class SodaCheckRunner:
    def _normalize_results(self, scan: Any, log_output: str, duration: float) -> DQRunResult:
        _, check_outcome = _import_soda()
        checks = _all_checks(scan)
        results: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        passed = warned = failed = 0

        for check in checks:
            outcome = getattr(check, "outcome", None)
            if outcome == check_outcome.PASS:
                passed += 1
            elif outcome == check_outcome.WARN:
                warned += 1
            elif outcome == check_outcome.FAIL:
                failed += 1

            d = check.get_dict()
            mvals = _measured_values(check)
            row = {
                "name": d.get("name"),
                "type": d.get("type"),
                "table": d.get("table"),
                "column": d.get("column"),
                "outcome": d.get("outcome"),
                "measured_value": _pick_measured_value(mvals),
                "threshold": getattr(check, "check_value", None),
            }
            results.append(row)
            diag = d.get("diagnostics") or {}
            if isinstance(diag, dict):
                diagnostics.append(diag)

        return DQRunResult(
            status=_outcome_status(scan),
            checks_total=len(checks),
            checks_passed=passed,
            checks_warned=warned,
            checks_failed=failed,
            results=results,
            diagnostics=diagnostics,
            log=log_output,
            duration_seconds=duration,
        )

    def run(
        self,
        data_source_name: str,
        server_type: str,
        conn_params: dict,
        sodacl_yaml: str,
    ) -> DQRunResult:
        scan_cls, _ = _import_soda()

        safe_ds = sanitize_data_source_name(data_source_name)
        cfg_yaml = build_datasource_config(data_source_name, server_type, conn_params)
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(message)s")
        handler.setFormatter(fmt)
        soda_logger = logging.getLogger("soda")
        prev_level = soda_logger.level
        prev_handlers = list(soda_logger.handlers)
        soda_logger.setLevel(logging.DEBUG)
        soda_logger.addHandler(handler)

        scan = scan_cls()
        scan.set_data_source_name(safe_ds)
        scan.add_configuration_yaml_str(cfg_yaml, file_path="sraosha_datasource.yaml")
        scan.add_sodacl_yaml_str(sodacl_yaml, file_name="sraosha_checks.yaml")

        t0 = time.perf_counter()
        try:
            scan.execute()
        except Exception:
            soda_logger.removeHandler(handler)
            soda_logger.setLevel(prev_level)
            for h in prev_handlers:
                soda_logger.addHandler(h)
            elapsed = time.perf_counter() - t0
            err = traceback.format_exc()
            merged = (buf.getvalue() + "\n" + err).strip()
            return DQRunResult(
                status="error",
                checks_total=0,
                checks_passed=0,
                checks_warned=0,
                checks_failed=0,
                results=[],
                diagnostics=[],
                log=merged,
                duration_seconds=elapsed,
            )
        finally:
            duration = time.perf_counter() - t0

        soda_logger.removeHandler(handler)
        soda_logger.setLevel(prev_level)
        for h in prev_handlers:
            soda_logger.addHandler(h)

        soda_log = buf.getvalue()
        scan_log = scan.get_logs_text() or ""
        merged_log = (soda_log + "\n" + scan_log).strip() if soda_log else scan_log

        return self._normalize_results(scan, merged_log, duration)

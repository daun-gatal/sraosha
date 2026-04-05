"""Soda Core implementation of :class:`sraosha.dq.protocol.DQRunner`."""

from __future__ import annotations

import io
import logging
import time
import traceback
from typing import Any, cast

from sraosha.dq.config_builder import (
    build_datasource_config,
    sanitize_data_source_name,
    soda_connector_type_for_server_type,
)
from sraosha.dq.result import DQRunResult

_SODA_INSTALL_HINT = (
    "soda-core is required for data quality checks but is not installed. "
    "Install it manually for your environment, e.g. pip install soda-core soda-core-postgres "
    "(pick soda-core-<connector> packages matching your connection server types). "
    "They are not bundled with the sraosha package. "
    "Connectors bring their own drivers (e.g. soda-core-mysql includes mysql-connector-python). "
    "PyMySQL is bundled for schema introspection only."
)

logger = logging.getLogger(__name__)

_mysql_connect_orig: Any | None = None
_mysql_connector_connect_wrapped: bool = False
# During SodaCheckRunner.run, flattened connection extra_params (e.g. charset) for mysql wire.
_active_mysql_scan_params: dict[str, Any] | None = None


def _set_active_mysql_scan_params(conn_params: dict[str, Any], server_type: str) -> None:
    """Scope extra_params-based mysql-connector kwargs to the current DQ scan."""
    global _active_mysql_scan_params
    if soda_connector_type_for_server_type(server_type) != "mysql":
        _active_mysql_scan_params = None
        return
    _active_mysql_scan_params = conn_params


def _clear_active_mysql_scan_params() -> None:
    global _active_mysql_scan_params
    _active_mysql_scan_params = None


def _apply_extra_params_to_mysql_connector_kwargs(
    merged: dict[str, Any], conn_params: dict[str, Any]
) -> None:
    """Apply ``charset`` / ``use_unicode`` / ``collation`` / ``use_pure`` from extra_params."""
    if "charset" in conn_params:
        raw = conn_params["charset"]
        if raw is not None and str(raw).strip() != "":
            s = str(raw).strip()
            merged["charset"] = "utf8mb4" if s.lower() in ("utf8", "utf-8") else s
    if "use_unicode" in conn_params:
        merged["use_unicode"] = conn_params["use_unicode"]
    if conn_params.get("collation") is not None:
        merged["collation"] = conn_params["collation"]
    if "use_pure" in conn_params:
        merged["use_pure"] = conn_params["use_pure"]


def _mysql_connect_kwargs_with_utf8mb4(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Normalize mysql-connector-python kwargs so charset is never the legacy utf8 alias.

    Default ``use_pure=True``: the C extension (``use_pure=False``) still hits utf8 issues on
    many servers even when ``charset=utf8mb4`` is set; the pure-Python path respects charset.
    """
    out = dict(kwargs)
    c = out.get("charset")
    if c is None or c == "":
        out["charset"] = "utf8mb4"
    elif str(c).lower() in ("utf8", "utf-8"):
        out["charset"] = "utf8mb4"
    if "use_unicode" not in out:
        out["use_unicode"] = True
    if "use_pure" not in out:
        out["use_pure"] = True
    return out


def _patch_mysql_connector_connect_for_utf8mb4() -> None:
    """Wrap mysql.connector.connect to default charset utf8mb4 (Soda's MySQLDataSource omits it)."""
    global _mysql_connect_orig, _mysql_connector_connect_wrapped
    if _mysql_connector_connect_wrapped:
        return
    try:
        import mysql.connector
    except ImportError as exc:
        logger.warning(
            "mysql.connector charset wrapper skipped (import failed): %s",
            exc,
        )
        return

    _mysql_connect_orig = mysql.connector.connect

    def _connect(*args: Any, **kwargs: Any) -> Any:
        merged = _mysql_connect_kwargs_with_utf8mb4(kwargs)
        p = _active_mysql_scan_params
        if p:
            _apply_extra_params_to_mysql_connector_kwargs(merged, p)
        if _mysql_connect_orig is None:
            raise RuntimeError("mysql.connector.connect wrapper not initialized")
        return _mysql_connect_orig(*args, **merged)

    mysql.connector.connect = _connect  # type: ignore[method-assign]
    # Same function object was re-exported from pooling.connect; replace both or imports of
    # pooling.connect bypass this wrapper.
    import mysql.connector.pooling as _pooling

    _pooling.connect = _connect  # type: ignore[method-assign]
    _mysql_connector_connect_wrapped = True
    logger.debug("mysql.connector.connect (and pooling.connect) wrapped for utf8mb4 / use_pure")


def _import_soda():
    """Lazy-import soda-core; raises a friendly error when missing."""
    try:
        from soda.execution.check_outcome import CheckOutcome
        from soda.scan import Scan
    except ImportError:
        raise ImportError(_SODA_INSTALL_HINT) from None
    return Scan, CheckOutcome


def _patch_soda_mysql_connector_charset() -> None:
    """soda-core-mysql's MySQLDataSource.connect() ignores YAML; mysql.connector defaults to
    charset utf8, which raises 'Character set utf8 unsupported' on many setups. Patch once.
    Redundant if _patch_mysql_connector_connect_for_utf8mb4 is active; kept as defense in depth."""
    try:
        from soda.common.exceptions import DataSourceConnectionError
        from soda.data_sources.mysql_data_source import MySQLDataSource
    except ImportError as exc:
        logger.warning(
            "Soda MySQLDataSource charset patch skipped (import failed): %s",
            exc,
        )
        return
    if getattr(MySQLDataSource, "_sraosha_mysql_charset_patch", False):
        return

    def connect(self):  # type: ignore[no-untyped-def]
        try:
            import mysql.connector

            kwargs: dict[str, Any] = {
                "user": self.username,
                "password": self.password,
                "host": self.host,
                "port": self.port,
                "database": self.database,
                "charset": "utf8mb4",
                "use_unicode": True,
            }
            p = _active_mysql_scan_params
            if p:
                _apply_extra_params_to_mysql_connector_kwargs(kwargs, p)
            self.connection = mysql.connector.connect(**kwargs)
            return self.connection
        except Exception as e:
            raise DataSourceConnectionError(self.TYPE, e)

    MySQLDataSource.connect = connect  # type: ignore[method-assign]
    MySQLDataSource._sraosha_mysql_charset_patch = True


def _all_checks(scan: Any) -> list[Any]:
    fn = getattr(scan, "get_all_checks", None)
    if callable(fn):
        return cast(list[Any], fn())
    return cast(list[Any], scan._checks)


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
    """Runs SodaCL against a configured data source."""

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
        _patch_mysql_connector_connect_for_utf8mb4()
        _patch_soda_mysql_connector_charset()

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

        _set_active_mysql_scan_params(conn_params, server_type)
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
            _clear_active_mysql_scan_params()
            duration = time.perf_counter() - t0

        soda_logger.removeHandler(handler)
        soda_logger.setLevel(prev_level)
        for h in prev_handlers:
            soda_logger.addHandler(h)

        soda_log = buf.getvalue()
        scan_log = scan.get_logs_text() or ""
        merged_log = (soda_log + "\n" + scan_log).strip() if soda_log else scan_log

        return self._normalize_results(scan, merged_log, duration)

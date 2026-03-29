import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from sraosha.core.loader import ContractLoader
from sraosha.core.runner import ContractRunner

logger = logging.getLogger(__name__)


class EnforcementMode(str, Enum):
    BLOCK = "block"
    WARN = "warn"
    LOG = "log"


@dataclass
class ValidationResult:
    contract_id: str
    contract_path: str
    passed: bool
    enforcement_mode: EnforcementMode
    checks_total: int
    checks_passed: int
    checks_failed: int
    failures: list[dict] = field(default_factory=list)
    duration_seconds: float = 0.0
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ContractViolationError(Exception):
    def __init__(self, result: ValidationResult):
        self.result = result
        super().__init__(
            f"Contract '{result.contract_id}' failed: "
            f"{result.checks_failed}/{result.checks_total} checks failed."
        )


class ContractEngine:
    """
    Main entry point for Sraosha.
    Loads a contract, runs validation via datacontract-cli, persists results.
    """

    def __init__(
        self,
        contract_path: str | Path,
        enforcement_mode: EnforcementMode = EnforcementMode.BLOCK,
        server: Optional[str] = None,
        db_session=None,
        dry_run: bool = False,
    ):
        self.contract_path = str(contract_path)
        self.enforcement_mode = enforcement_mode
        self.server = server
        self.db_session = db_session
        self.dry_run = dry_run
        self._contract_data: dict | None = None

    def _load_contract(self) -> dict:
        if self._contract_data is None:
            self._contract_data = ContractLoader.auto(self.contract_path)
        return self._contract_data

    def run(self) -> ValidationResult:
        contract_data = self._load_contract()
        contract_id = contract_data.get("id", Path(self.contract_path).stem)

        x_sraosha = contract_data.get("x-sraosha", {})
        if x_sraosha.get("enforcement_mode"):
            self.enforcement_mode = EnforcementMode(x_sraosha["enforcement_mode"])

        runner = ContractRunner(self.contract_path, server=self.server)

        try:
            raw = runner.run()
        except Exception as exc:
            logger.error("Validation engine error for %s: %s", contract_id, exc)
            result = ValidationResult(
                contract_id=contract_id,
                contract_path=self.contract_path,
                passed=False,
                enforcement_mode=self.enforcement_mode,
                checks_total=0,
                checks_passed=0,
                checks_failed=0,
                failures=[{"check": "engine_error", "field": None, "message": str(exc)}],
            )
            if self.enforcement_mode == EnforcementMode.BLOCK:
                raise ContractViolationError(result) from exc
            return result

        result = ValidationResult(
            contract_id=contract_id,
            contract_path=self.contract_path,
            passed=raw["passed"],
            enforcement_mode=self.enforcement_mode,
            checks_total=raw["checks_total"],
            checks_passed=raw["checks_passed"],
            checks_failed=raw["checks_failed"],
            failures=raw.get("failures", []),
            duration_seconds=raw.get("duration_seconds", 0.0),
        )

        if not self.dry_run and self.db_session is not None:
            self._persist(result)

        if not result.passed:
            if self.enforcement_mode == EnforcementMode.BLOCK:
                raise ContractViolationError(result)
            elif self.enforcement_mode == EnforcementMode.WARN:
                logger.warning(
                    "Contract '%s' failed (%d/%d checks). Mode=WARN, continuing.",
                    result.contract_id,
                    result.checks_failed,
                    result.checks_total,
                )

        return result

    def _persist(self, result: ValidationResult) -> None:
        try:
            from sraosha.models.run import ValidationRun

            run = ValidationRun(
                contract_id=result.contract_id,
                status="passed" if result.passed else "failed",
                enforcement_mode=result.enforcement_mode.value,
                checks_total=result.checks_total,
                checks_passed=result.checks_passed,
                checks_failed=result.checks_failed,
                failures=result.failures,
                duration_ms=int(result.duration_seconds * 1000),
            )
            self.db_session.add(run)
        except Exception:
            logger.exception("Failed to persist validation run for %s", result.contract_id)

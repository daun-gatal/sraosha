from abc import ABC, abstractmethod

from sraosha.core.engine import ContractEngine, EnforcementMode, ValidationResult


class BasePipelineHook(ABC):
    """Abstract base for all pipeline integration hooks."""

    def __init__(
        self,
        contract_path: str,
        enforcement_mode: EnforcementMode = EnforcementMode.BLOCK,
        server: str | None = None,
    ):
        self.contract_path = contract_path
        self.enforcement_mode = enforcement_mode
        self.server = server

    def execute(self) -> ValidationResult:
        engine = ContractEngine(
            contract_path=self.contract_path,
            enforcement_mode=self.enforcement_mode,
            server=self.server,
        )
        result = engine.run()

        if result.passed:
            self.on_success(result)
        else:
            self.on_failure(result)

        return result

    @abstractmethod
    def on_success(self, result: ValidationResult) -> None:
        ...

    @abstractmethod
    def on_failure(self, result: ValidationResult) -> None:
        ...

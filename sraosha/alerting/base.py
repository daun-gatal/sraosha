from abc import ABC, abstractmethod


class BaseAlerter(ABC):
    """Abstract base for alert channel implementations."""

    @abstractmethod
    def send(self, alert_type: str, contract_id: str, details: dict) -> bool:
        """Send an alert. Returns True on success."""
        ...

    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if this alerter is configured and enabled."""
        ...

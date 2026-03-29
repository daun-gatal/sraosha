import logging
from typing import ClassVar

from sraosha.alerting.base import BaseAlerter
from sraosha.alerting.email import EmailAlerter
from sraosha.alerting.slack import SlackAlerter

logger = logging.getLogger(__name__)


class AlertDispatcher:
    """Routes alerts to all configured channels."""

    ALERT_TYPES: ClassVar[list[str]] = [
        "contract_violation",
        "drift_warning",
        "breach",
    ]

    def __init__(self):
        self._channels: list[BaseAlerter] = [SlackAlerter(), EmailAlerter()]

    def dispatch(self, alert_type: str, contract_id: str, details: dict) -> list[dict]:
        results: list[dict] = []

        for channel in self._channels:
            if not channel.is_enabled():
                continue

            channel_name = channel.__class__.__name__
            try:
                success = channel.send(alert_type, contract_id, dict(details))
                results.append(
                    {
                        "channel": channel_name,
                        "success": success,
                        "error": None,
                    }
                )
            except Exception as exc:
                logger.exception("Alert dispatch failed via %s", channel_name)
                results.append(
                    {
                        "channel": channel_name,
                        "success": False,
                        "error": str(exc),
                    }
                )

        return results

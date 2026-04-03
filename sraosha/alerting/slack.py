import logging

import httpx

from sraosha.alerting.base import BaseAlerter
from sraosha.config import settings

logger = logging.getLogger(__name__)


class SlackAlerter(BaseAlerter):
    """Sends alerts to Slack via incoming webhook."""

    def is_enabled(self) -> bool:
        return settings.SLACK_ENABLED and bool(settings.SLACK_WEBHOOK_URL)

    def send(self, alert_type: str, contract_id: str, details: dict) -> bool:
        if not self.is_enabled():
            return False

        icon = {"contract_violation": "!!", "dq_warning": "~~", "dq_failure": "XX"}.get(
            alert_type, "**"
        )
        title = f"{icon} Sraosha: {alert_type.replace('_', ' ').title()}"

        lines = [f"*Contract:* `{contract_id}`"]
        for key, value in details.items():
            lines.append(f"*{key}:* {value}")

        payload = {
            "text": title,
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{title}*\n" + "\n".join(lines)},
                }
            ],
        }

        webhook_url = settings.SLACK_WEBHOOK_URL
        assert webhook_url is not None

        try:
            resp = httpx.post(webhook_url, json=payload, timeout=10.0)
            resp.raise_for_status()
            return True
        except Exception:
            logger.exception("Failed to send Slack alert for %s", contract_id)
            return False

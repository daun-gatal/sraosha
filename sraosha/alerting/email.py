import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sraosha.alerting.base import BaseAlerter
from sraosha.config import settings

logger = logging.getLogger(__name__)


class EmailAlerter(BaseAlerter):
    """Sends alerts via SMTP email."""

    def is_enabled(self) -> bool:
        return settings.EMAIL_ENABLED and bool(settings.SMTP_HOST)

    def send(self, alert_type: str, contract_id: str, details: dict) -> bool:
        if not self.is_enabled():
            return False

        to_addr = details.pop("to", settings.SMTP_FROM)
        if not to_addr or not settings.SMTP_FROM:
            logger.error("No recipient or sender configured for email alert")
            return False

        subject = f"Sraosha Alert: {alert_type.replace('_', ' ').title()} — {contract_id}"

        lines = [f"Contract: {contract_id}", f"Alert Type: {alert_type}", ""]
        for key, value in details.items():
            lines.append(f"{key}: {value}")

        body = "\n".join(lines)

        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        smtp_host = settings.SMTP_HOST
        assert smtp_host is not None

        try:
            with smtplib.SMTP(smtp_host, settings.SMTP_PORT) as server:
                server.starttls()
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            return True
        except Exception:
            logger.exception("Failed to send email alert for %s", contract_id)
            return False

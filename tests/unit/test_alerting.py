from unittest.mock import MagicMock, patch

from sraosha.alerting.dispatcher import AlertDispatcher
from sraosha.alerting.email import EmailAlerter
from sraosha.alerting.slack import SlackAlerter


class TestSlackAlerter:
    @patch("sraosha.alerting.slack.settings")
    def test_disabled_when_not_configured(self, mock_settings):
        mock_settings.SLACK_ENABLED = False
        mock_settings.SLACK_WEBHOOK_URL = None
        alerter = SlackAlerter()
        assert alerter.is_enabled() is False

    @patch("sraosha.alerting.slack.settings")
    @patch("sraosha.alerting.slack.httpx.post")
    def test_sends_when_enabled(self, mock_post, mock_settings):
        mock_settings.SLACK_ENABLED = True
        mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())

        alerter = SlackAlerter()
        result = alerter.send("drift_warning", "orders-v1", {"metric": "null_rate"})
        assert result is True
        mock_post.assert_called_once()


class TestEmailAlerter:
    @patch("sraosha.alerting.email.settings")
    def test_disabled_when_not_configured(self, mock_settings):
        mock_settings.EMAIL_ENABLED = False
        mock_settings.SMTP_HOST = None
        alerter = EmailAlerter()
        assert alerter.is_enabled() is False


class TestAlertDispatcher:
    @patch("sraosha.alerting.dispatcher.SlackAlerter")
    @patch("sraosha.alerting.dispatcher.EmailAlerter")
    def test_routes_to_enabled_channels(self, mock_email_cls, mock_slack_cls):
        mock_slack = MagicMock()
        mock_slack.is_enabled.return_value = True
        mock_slack.send.return_value = True
        mock_slack.__class__.__name__ = "SlackAlerter"
        mock_slack_cls.return_value = mock_slack

        mock_email = MagicMock()
        mock_email.is_enabled.return_value = False
        mock_email_cls.return_value = mock_email

        dispatcher = AlertDispatcher()
        results = dispatcher.dispatch("contract_violation", "orders-v1", {"detail": "test"})

        assert len(results) == 1
        assert results[0]["channel"] == "SlackAlerter"
        assert results[0]["success"] is True

    @patch("sraosha.alerting.dispatcher.SlackAlerter")
    @patch("sraosha.alerting.dispatcher.EmailAlerter")
    def test_no_channels_enabled(self, mock_email_cls, mock_slack_cls):
        mock_slack = MagicMock()
        mock_slack.is_enabled.return_value = False
        mock_slack_cls.return_value = mock_slack

        mock_email = MagicMock()
        mock_email.is_enabled.return_value = False
        mock_email_cls.return_value = mock_email

        dispatcher = AlertDispatcher()
        results = dispatcher.dispatch("drift_warning", "orders-v1", {})
        assert results == []

import logging
import platform
from logging.handlers import HTTPHandler

from django.conf import settings


class TelegramHandler(HTTPHandler):
    """Log handler that sends messages to the hard-coded Telegram chat id."""

    def __init__(self) -> None:
        host = "api.telegram.org"
        url = f"/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        method = "POST"
        secure = True
        super().__init__(host, url, method, secure)

    def mapLogRecord(self, record):
        self.format(record)
        request = record.__dict__.get("request", None)
        body: bytes | None = request.body if request else None

        msg = "<b>STAGE!</b> " if settings.STAGE else "<b>NOT STAGE!</b> "
        msg = msg + record.message
        if record.exc_text:
            msg = msg + f"\n<pre>{record.exc_text}</pre>"
        if body:
            msg = msg + f"\nRequest body:\n<pre>{body.decode()}</pre>"
        data = {
            "text": msg,
            # "chat_id": 924585089,
            "chat_id": -1002065362194,
            "reply_to_message_id": 1716,
            "parse_mode": "HTML"
        }
        return data


class LinuxOnly(logging.Filter):
    def filter(self, record):
        return platform.system() == 'Linux'

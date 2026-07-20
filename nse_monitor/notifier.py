import json
import logging
from typing import Protocol

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("nse_monitor.notifier")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_RETRIES = 3


class Notifier(Protocol):
    def send(self, message: str) -> bool: ...


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self._url = TELEGRAM_API.format(token=bot_token)
        self._chat_id = chat_id

    def send(self, message: str) -> bool:
        @retry(
            stop=stop_after_attempt(MAX_RETRIES),
            wait=wait_exponential(multiplier=2, max=30),
            retry=retry_if_exception_type(
                (requests.ConnectionError, requests.Timeout, requests.HTTPError)
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        def _do_send() -> bool:
            payload = {
                "chat_id": self._chat_id,
                "text": message,
                "parse_mode": "HTML",
            }
            resp = requests.post(self._url, json=payload, timeout=10)
            if resp.status_code == 429:
                logger.warning("Telegram rate limited (429), will retry")
                resp.raise_for_status()
            if resp.status_code >= 500:
                logger.warning("Telegram server error (%d), will retry", resp.status_code)
                resp.raise_for_status()
            body = resp.json()
            if resp.ok and body.get("ok"):
                return True
            logger.error(
                "Telegram send failed: HTTP %d – %s",
                resp.status_code,
                json.dumps(body, default=str)[:200],
            )
            return False

        try:
            return _do_send()
        except Exception as e:
            logger.error("Notification send error (will retry later): %s", e)
            return False

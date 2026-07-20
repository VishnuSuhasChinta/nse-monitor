import enum
import logging
import random
import time
from typing import List, Optional

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from nse_monitor.config import Config
from nse_monitor.parser import parse_announcements
from nse_monitor.session_manager import (
    HEADERS,
    bootstrap_session,
    refresh_if_needed,
)

logger = logging.getLogger("nse_monitor.nse_client")

CORP_ANNOUNCE_URL = (
    "https://www.nseindia.com/api/corporate-announcements?index=equities"
)


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class NSEClient:
    def __init__(self, config: Config):
        self.config = config.http
        self.session = requests.Session()
        self.circuit_state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.circuit_open_until = 0.0
        self._session_bootstrapped = False

    def _make_retry_decorator(self):
        return retry(
            stop=stop_after_attempt(self.config.max_retries),
            wait=wait_exponential(
                multiplier=self.config.backoff_base_seconds,
                max=self.config.backoff_max_seconds,
            ),
            retry=(
                retry_if_exception_type(requests.ConnectionError)
                | retry_if_exception_type(requests.Timeout)
                | retry_if_exception_type(requests.HTTPError)
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

    def bootstrap(self) -> bool:
        ok = bootstrap_session(self.session)
        self._session_bootstrapped = ok
        return ok

    def _ensure_session(self) -> None:
        if not self._session_bootstrapped:
            self.bootstrap()

    def _check_circuit(self) -> bool:
        now = time.monotonic()
        if self.circuit_state == CircuitState.OPEN:
            if now >= self.circuit_open_until:
                logger.info("Circuit breaker half-opening")
                self.circuit_state = CircuitState.HALF_OPEN
                return True
            logger.warning("Circuit breaker open, skipping poll")
            return False
        return True

    def _record_success(self) -> None:
        self.consecutive_failures = 0
        if self.circuit_state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker closed (half-open → success)")
        self.circuit_state = CircuitState.CLOSED

    def _record_failure(self) -> None:
        self.consecutive_failures += 1
        threshold = 3
        if self.consecutive_failures >= threshold:
            self.circuit_state = CircuitState.OPEN
            backoff = self.config.backoff_max_seconds * 5
            self.circuit_open_until = time.monotonic() + backoff
            logger.warning(
                "Circuit breaker opened after %d failures, backing off %ds",
                self.consecutive_failures,
                backoff,
            )

    def fetch_announcements(self) -> Optional[List[dict]]:
        if not self._check_circuit():
            return None

        self._ensure_session()
        jitter = random.uniform(-self.config.backoff_base_seconds, self.config.backoff_base_seconds) if self.config.backoff_base_seconds else 0
        time.sleep(max(0, jitter))

        refreshed_this_cycle = False

        @self._make_retry_decorator()
        def _do_fetch():
            nonlocal refreshed_this_cycle
            resp = self.session.get(
                CORP_ANNOUNCE_URL, headers=HEADERS, timeout=self.config.timeout_seconds
            )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 30))
                logger.warning("Rate limited (429), retrying after %ds", retry_after)
                time.sleep(retry_after)
                resp = self.session.get(
                    CORP_ANNOUNCE_URL, headers=HEADERS, timeout=self.config.timeout_seconds
                )
            if not refreshed_this_cycle and refresh_if_needed(self.session, resp):
                refreshed_this_cycle = True
                resp = self.session.get(
                    CORP_ANNOUNCE_URL, headers=HEADERS, timeout=self.config.timeout_seconds
                )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            logger.warning("Unexpected response format: %s", type(data).__name__)
            return []

        try:
            result = _do_fetch()
            self._record_success()
            return result
        except Exception as e:
            logger.error("Failed to fetch announcements: %s", e)
            self._record_failure()
            return []

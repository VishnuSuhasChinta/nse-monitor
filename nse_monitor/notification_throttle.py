import logging
import time
from collections import deque
from typing import List

from nse_monitor.models import Announcement
from nse_monitor.notifier import Notifier

logger = logging.getLogger("nse_monitor.throttle")

HTML_ESC = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})


def _escape(text: str) -> str:
    return text.translate(HTML_ESC)


def _format_announcement(ann: Announcement) -> str:
    return (
        f"<b>Company:</b> {_escape(ann.symbol)}\n"
        f"<b>Category:</b> {_escape(ann.category or 'N/A')}\n"
        f"<b>Headline:</b> {_escape(ann.headline)}\n"
        f"<b>Time:</b> {_escape(ann.announcement_ts)}\n"
        + (f"<b>PDF:</b> {_escape(ann.pdf_url)}" if ann.pdf_url else "")
    )


def format_batch(anns: List[Announcement]) -> str:
    parts = ["<b>New NSE Announcements</b>\n" if len(anns) > 1 else "<b>New NSE Announcement</b>\n"]
    for i, ann in enumerate(anns, 1):
        if len(anns) > 1:
            parts.append(f"\n--- #{i} ---\n")
        parts.append(_format_announcement(ann))
    return "\n".join(parts)


class NotificationThrottle:
    def __init__(self, notifier: Notifier, max_per_minute: int, batch_window: float):
        self._notifier = notifier
        self._max_per_minute = max_per_minute
        self._batch_window = batch_window
        self._timestamps: deque[float] = deque()
        self._pending: List[Announcement] = []
        self._last_flush = 0.0

    def submit(self, ann: Announcement) -> bool:
        self._pending.append(ann)
        now = time.monotonic()
        if now - self._last_flush >= self._batch_window:
            return self._flush(now)
        return True

    def _flush(self, now: float) -> bool:
        if not self._pending:
            return True
        self._prune_timestamps(now)
        if len(self._timestamps) >= self._max_per_minute:
            logger.warning("Rate limit reached, deferring %d announcements", len(self._pending))
            return False
        batch = self._pending[:]
        self._pending.clear()
        message = format_batch(batch)
        ok = self._notifier.send(message)
        if ok:
            self._timestamps.append(now)
            self._last_flush = now
            logger.info("Sent notification for %d announcement(s)", len(batch))
        else:
            logger.error("Failed to send notification for %d announcement(s)", len(batch))
        return ok

    def flush(self) -> bool:
        return self._flush(time.monotonic())

    def _prune_timestamps(self, now: float) -> None:
        cutoff = now - 60
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

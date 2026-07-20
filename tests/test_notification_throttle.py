import time

from nse_monitor.models import Announcement
from nse_monitor.notification_throttle import NotificationThrottle, format_batch


class FakeNotifier:
    def __init__(self):
        self.sent_messages = []
        self.fail = False

    def send(self, message: str) -> bool:
        if self.fail:
            return False
        self.sent_messages.append(message)
        return True


def test_single_announcement_format():
    ann = Announcement(
        symbol="TCS",
        category="Results",
        headline="Quarterly results announced",
        announcement_ts="2026-07-18T10:30:00",
        pdf_url="https://example.com",
    )
    msg = format_batch([ann])
    assert "<b>New NSE Announcement</b>" in msg
    assert "TCS" in msg
    assert "Results" in msg
    assert "Quarterly results announced" in msg


def test_multiple_announcement_format():
    anns = [
        Announcement(symbol="TCS", headline="A", announcement_ts="2026-07-18T10:00:00"),
        Announcement(symbol="INFY", headline="B", announcement_ts="2026-07-18T10:01:00"),
    ]
    msg = format_batch(anns)
    assert "<b>New NSE Announcements</b>" in msg
    assert "#1" in msg
    assert "#2" in msg


def test_throttle_batches_within_window():
    notifier = FakeNotifier()
    throttle = NotificationThrottle(notifier, max_per_minute=100, batch_window=0.05)
    ann = Announcement(symbol="TCS", headline="Test", announcement_ts="2026-07-18T10:00:00")
    throttle.submit(ann)
    time.sleep(0.1)
    throttle.submit(ann)
    assert len(notifier.sent_messages) == 2


def test_html_escaping():
    ann = Announcement(
        symbol="TCS",
        headline="Results > 10% & growing <expected>",
        announcement_ts="2026-07-18T10:00:00",
    )
    msg = format_batch([ann])
    assert "&gt;" in msg
    assert "&amp;" in msg
    assert "&lt;" in msg

from nse_monitor.dedup import compute_hash
from nse_monitor.models import Announcement


def test_compute_hash_deterministic():
    ann = Announcement(
        symbol="TCS",
        category="Board Meeting",
        headline="Test",
        announcement_ts="2026-07-18T10:00:00",
    )
    h1 = compute_hash(ann)
    h2 = compute_hash(ann)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_hash_different_fields():
    ann1 = Announcement(
        symbol="TCS", category="Board Meeting", headline="A", announcement_ts="2026-07-18T10:00:00"
    )
    ann2 = Announcement(
        symbol="INFY", category="Board Meeting", headline="A", announcement_ts="2026-07-18T10:00:00"
    )
    assert compute_hash(ann1) != compute_hash(ann2)


def test_compute_hash_empty_fields():
    ann = Announcement(symbol="TCS", category="", headline="", announcement_ts="")
    h = compute_hash(ann)
    assert isinstance(h, str)
    assert len(h) == 64

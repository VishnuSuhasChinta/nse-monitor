from nse_monitor.database import Database
from nse_monitor.dedup import compute_hash
from nse_monitor.models import Announcement


def test_insert_and_duplicate(temp_db: Database, sample_announcement: Announcement):
    sample_announcement.hash = compute_hash(sample_announcement)
    assert temp_db.insert_announcement(sample_announcement) is True
    assert temp_db.insert_announcement(sample_announcement) is False


def test_watermark(temp_db: Database):
    temp_db.update_watermark("TCS", "2026-07-18T10:00:00")
    assert temp_db.get_watermark("TCS") == "2026-07-18T10:00:00"
    assert temp_db.get_watermark("INFY") is None


def test_watermark_update(temp_db: Database):
    temp_db.update_watermark("TCS", "2026-07-18T10:00:00")
    temp_db.update_watermark("TCS", "2026-07-18T11:00:00")
    assert temp_db.get_watermark("TCS") == "2026-07-18T11:00:00"


def test_notified_flag(temp_db: Database, sample_announcement: Announcement):
    sample_announcement.hash = compute_hash(sample_announcement)
    temp_db.insert_announcement(sample_announcement)
    assert sample_announcement.hash in temp_db.get_unnotified()
    temp_db.mark_notified(sample_announcement.hash)
    assert sample_announcement.hash not in temp_db.get_unnotified()


# ── Per-user tests ──


def test_register_user(temp_db: Database):
    symbols = ["TCS", "INFY"]
    is_new = temp_db.register_user("chat_a", symbols, "Vishnu")
    assert is_new is True

    users = temp_db.get_users()
    assert any(u["chat_id"] == "chat_a" for u in users)

    wm = temp_db.get_user_watermark("chat_a", "TCS")
    assert wm is not None
    assert "T00:00:00" in wm


def test_register_user_duplicate(temp_db: Database):
    symbols = ["TCS"]
    temp_db.register_user("chat_a", symbols, "Vishnu")
    is_new = temp_db.register_user("chat_a", symbols, "Vishnu")
    assert is_new is False


def test_user_watermark_flow(temp_db: Database):
    temp_db.register_user("chat_a", ["TCS"], "Vishnu")
    wm = temp_db.get_user_watermark("chat_a", "TCS")
    assert wm is not None

    temp_db.update_user_watermark("chat_a", "TCS", "2026-07-19T15:00:00")
    assert temp_db.get_user_watermark("chat_a", "TCS") == "2026-07-19T15:00:00"


def test_user_watermark_isolation(temp_db: Database):
    temp_db.register_user("chat_a", ["TCS"], "A")
    temp_db.register_user("chat_b", ["TCS"], "B")

    temp_db.update_user_watermark("chat_a", "TCS", "2026-07-19T10:00:00")
    temp_db.update_user_watermark("chat_b", "TCS", "2026-07-19T15:00:00")

    assert temp_db.get_user_watermark("chat_a", "TCS") == "2026-07-19T10:00:00"
    assert temp_db.get_user_watermark("chat_b", "TCS") == "2026-07-19T15:00:00"


def test_user_notification_flow(temp_db: Database, sample_announcement: Announcement):
    temp_db.register_user("chat_a", [sample_announcement.symbol], "A")
    sample_announcement.hash = compute_hash(sample_announcement)
    temp_db.insert_announcement(sample_announcement)

    assert temp_db.get_user_notification("chat_a", sample_announcement.hash) is False

    temp_db.mark_user_notified("chat_a", sample_announcement.hash)
    assert temp_db.get_user_notification("chat_a", sample_announcement.hash) is True


def test_user_notification_isolation(temp_db: Database, sample_announcement: Announcement):
    temp_db.register_user("chat_a", [sample_announcement.symbol], "A")
    temp_db.register_user("chat_b", [sample_announcement.symbol], "B")
    sample_announcement.hash = compute_hash(sample_announcement)
    temp_db.insert_announcement(sample_announcement)

    temp_db.mark_user_notified("chat_a", sample_announcement.hash)

    assert temp_db.get_user_notification("chat_a", sample_announcement.hash) is True
    assert temp_db.get_user_notification("chat_b", sample_announcement.hash) is False


def test_migration(temp_db: Database, sample_announcement: Announcement):
    temp_db.update_watermark("TCS", "2026-07-18T10:00:00")
    temp_db.update_watermark("INFY", "2026-07-18T11:00:00")

    sample_announcement.hash = compute_hash(sample_announcement)
    temp_db.insert_announcement(sample_announcement)
    temp_db.mark_notified(sample_announcement.hash)

    temp_db.migrate_existing_data("old_chat")

    assert temp_db.get_user_watermark("old_chat", "TCS") == "2026-07-18T10:00:00"
    assert temp_db.get_user_watermark("old_chat", "INFY") == "2026-07-18T11:00:00"
    assert temp_db.get_user_notification("old_chat", sample_announcement.hash) is True


def test_migration_idempotent(temp_db: Database):
    temp_db.update_watermark("TCS", "2026-07-18T10:00:00")
    temp_db.migrate_existing_data("old_chat")
    before = temp_db.get_user_watermark("old_chat", "TCS")

    temp_db.migrate_existing_data("old_chat")
    after = temp_db.get_user_watermark("old_chat", "TCS")
    assert before == after

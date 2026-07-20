import logging
import random

from apscheduler.schedulers.background import BackgroundScheduler

from nse_monitor.config import Config
from nse_monitor.database import Database
from nse_monitor.dedup import compute_hash
from nse_monitor.health import set_last_poll_time
from nse_monitor.models import Announcement
from nse_monitor.nse_client import NSEClient
from nse_monitor.notification_throttle import NotificationThrottle
from nse_monitor.parser import parse_announcements

logger = logging.getLogger("nse_monitor.scheduler")

CIRCUIT_FACTOR = 5


def _filter_by_watchlist(
    announcements: list[Announcement], config: Config
) -> list[Announcement]:
    if not config.companies:
        return announcements
    symbols = {s.upper() for s in config.companies}
    return [a for a in announcements if a.symbol.upper() in symbols]


def _filter_by_categories(
    announcements: list[Announcement], config: Config
) -> list[Announcement]:
    if not config.categories:
        return announcements
    cats = {c.lower() for c in config.categories}
    return [a for a in announcements if a.category.lower() in cats]


def _is_newer_than_watermark(ann: Announcement, watermark: str | None) -> bool:
    if watermark is None:
        return True
    return ann.announcement_ts > watermark


def poll_announcements(
    client: NSEClient,
    db: Database,
    user_throttles: dict[str, NotificationThrottle],
    config: Config,
) -> None:
    raw = client.fetch_announcements()
    if raw is None:
        logger.info("Poll skipped (circuit open)")
        return
    if not raw:
        set_last_poll_time()
        logger.debug("No announcements returned")
        return

    all_anns = parse_announcements(raw)
    matched = _filter_by_watchlist(all_anns, config)
    matched = _filter_by_categories(matched, config)

    if not matched:
        set_last_poll_time()
        logger.debug("No matching announcements after filtering")
        return

    new_anns: list[Announcement] = []
    for ann in matched:
        ann.hash = compute_hash(ann)
        inserted = db.insert_announcement(ann)
        if inserted:
            new_anns.append(ann)
            logger.info("New announcement: %s – %s", ann.symbol, ann.headline[:60])
        else:
            logger.debug("Duplicate ignored: %s", ann.hash[:12])

    for ann in new_anns:
        for chat_id, throttle in user_throttles.items():
            watermark = db.get_user_watermark(chat_id, ann.symbol)
            if not _is_newer_than_watermark(ann, watermark):
                continue
            if db.get_user_notification(chat_id, ann.hash):
                continue
            ok = throttle.submit(ann)
            if ok:
                db.mark_user_notified(chat_id, ann.hash)
                db.update_user_watermark(chat_id, ann.symbol, ann.announcement_ts)
                logger.debug(
                    "Queued for %s: %s – %s", chat_id, ann.symbol, ann.headline[:40]
                )

    for throttle in user_throttles.values():
        throttle.flush()

    set_last_poll_time()
    logger.info("Poll complete: %d new, %d total matched", len(new_anns), len(matched))


def create_scheduler(
    client: NSEClient,
    db: Database,
    user_throttles: dict[str, NotificationThrottle],
    config: Config,
) -> BackgroundScheduler:
    interval = config.poll_interval_seconds
    jitter = config.poll_jitter_seconds

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(
        poll_announcements,
        trigger="interval",
        seconds=interval,
        jitter=jitter,
        max_instances=1,
        coalesce=True,
        args=[client, db, user_throttles, config],
    )
    return sched

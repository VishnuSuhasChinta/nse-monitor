import logging
import signal
import sys
import time

from nse_monitor.config import Config
from nse_monitor.database import Database
from nse_monitor.health import start_health_server
from nse_monitor.logging_config import setup_logging
from nse_monitor.nse_client import NSEClient
from nse_monitor.notification_throttle import NotificationThrottle
from nse_monitor.notifier import TelegramNotifier
from nse_monitor.scheduler import create_scheduler

logger = logging.getLogger("nse_monitor.main")


class Service:
    def __init__(self) -> None:
        self._shutdown = False
        self._scheduler = None
        self._db = None
        self._health_server = None

    def _signal_handler(self, signum: int, _frame) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, shutting down...", sig_name)
        self._shutdown = True

    def run(self) -> None:
        setup_logging()

        config = Config.load()
        if not config.TELEGRAM_BOT_TOKEN:
            logger.warning(
                "TELEGRAM_BOT_TOKEN must be set in .env"
            )
        if not config.users:
            logger.warning(
                "No users configured. Set TELEGRAM_CHAT_IDS or TELEGRAM_CHAT_ID in .env"
            )

        db = Database(
            db_path=config.database.path,
            wal_mode=config.database.wal_mode,
        )
        self._db = db
        logger.info("Database initialized at %s", config.database.path)

        client = NSEClient(config)
        client.bootstrap()

        user_throttles = {}
        for user in config.users:
            chat_id = user.chat_id
            db.register_user(chat_id, config.companies, user.name)
            notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, chat_id)
            throttle = NotificationThrottle(
                notifier,
                max_per_minute=config.notification.max_per_minute,
                batch_window=config.notification.batch_window_seconds,
            )
            user_throttles[chat_id] = throttle
            logger.info("Registered user chat_id=%s", chat_id)

        if config.TELEGRAM_CHAT_ID:
            db.migrate_existing_data(config.TELEGRAM_CHAT_ID)

        self._health_server = start_health_server(
            config.health.bind_host,
            config.health.bind_port,
            client,
        )

        scheduler = create_scheduler(client, db, user_throttles, config)
        self._scheduler = scheduler
        scheduler.start()
        logger.info(
            "Scheduler started (interval=%ds, jitter=%ds, users=%d)",
            config.poll_interval_seconds,
            config.poll_jitter_seconds,
            len(user_throttles),
        )

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        try:
            while not self._shutdown:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        logger.info("Shutting down...")
        if self._scheduler:
            self._scheduler.shutdown(wait=True)
        if self._health_server:
            self._health_server.shutdown()
        if self._db:
            self._db.close()
        logger.info("Shutdown complete")


def main() -> None:
    service = Service()
    try:
        service.run()
    except Exception as e:
        logger.critical("Fatal error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

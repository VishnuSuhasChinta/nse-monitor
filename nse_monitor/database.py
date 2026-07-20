import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from nse_monitor.models import Announcement


class Database:
    def __init__(self, db_path: str, wal_mode: bool = True):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;") if wal_mode else None
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    company_name TEXT,
                    headline TEXT,
                    category TEXT,
                    announcement_ts TEXT NOT NULL,
                    received_ts TEXT NOT NULL,
                    pdf_url TEXT,
                    hash TEXT NOT NULL UNIQUE,
                    notified INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_symbol ON announcements(symbol);
                CREATE INDEX IF NOT EXISTS idx_announcement_ts ON announcements(announcement_ts);
                CREATE INDEX IF NOT EXISTS idx_notified ON announcements(notified);

                CREATE TABLE IF NOT EXISTS watermarks (
                    symbol TEXT PRIMARY KEY,
                    last_announcement_ts TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    chat_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_notifications (
                    chat_id TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    notified INTEGER NOT NULL DEFAULT 0,
                    notified_at TEXT,
                    PRIMARY KEY (chat_id, hash)
                );

                CREATE TABLE IF NOT EXISTS user_watermarks (
                    chat_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    last_announcement_ts TEXT NOT NULL,
                    PRIMARY KEY (chat_id, symbol)
                );
            """)
            self._conn.commit()

    # ── Central announcement storage ──

    def insert_announcement(self, ann: Announcement) -> bool:
        received = datetime.now(timezone.utc).isoformat()
        with self._lock:
            cursor = self._conn.execute(
                """INSERT OR IGNORE INTO announcements
                   (symbol, company_name, headline, category, announcement_ts, received_ts, pdf_url, hash, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ann.symbol,
                    ann.company_name,
                    ann.headline,
                    ann.category,
                    ann.announcement_ts,
                    received,
                    ann.pdf_url,
                    ann.hash,
                    json.dumps(ann.raw_json, default=str),
                ),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def mark_notified(self, ann_hash: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE announcements SET notified = 1 WHERE hash = ?", (ann_hash,)
            )
            self._conn.commit()

    def get_watermark(self, symbol: str) -> Optional[str]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT last_announcement_ts FROM watermarks WHERE symbol = ?",
                (symbol,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def update_watermark(self, symbol: str, ts: str) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO watermarks (symbol, last_announcement_ts)
                   VALUES (?, ?)
                   ON CONFLICT(symbol) DO UPDATE SET last_announcement_ts = ?""",
                (symbol, ts, ts),
            )
            self._conn.commit()

    def get_unnotified(self) -> List[str]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT hash FROM announcements WHERE notified = 0"
            )
            return [row[0] for row in cursor.fetchall()]

    # ── User management ──

    def _get_today_midnight_utc(self) -> str:
        return datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

    def register_user(self, chat_id: str, symbols: List[str], name: str = "") -> bool:
        now = datetime.now(timezone.utc).isoformat()
        today = self._get_today_midnight_utc()
        with self._lock:
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO users (chat_id, name, created_at) VALUES (?, ?, ?)",
                (chat_id, name, now),
            )
            self._conn.commit()
            is_new = cursor.rowcount > 0
            if is_new:
                for symbol in symbols:
                    self._conn.execute(
                        """INSERT OR IGNORE INTO user_watermarks
                           (chat_id, symbol, last_announcement_ts) VALUES (?, ?, ?)""",
                        (chat_id, symbol, today),
                    )
                self._conn.commit()
            return is_new

    def get_users(self) -> List[Dict[str, str]]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT chat_id, name FROM users"
            )
            return [{"chat_id": row[0], "name": row[1]} for row in cursor.fetchall()]

    # ── Per-user watermarks ──

    def get_user_watermark(self, chat_id: str, symbol: str) -> Optional[str]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT last_announcement_ts FROM user_watermarks WHERE chat_id = ? AND symbol = ?",
                (chat_id, symbol),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def update_user_watermark(self, chat_id: str, symbol: str, ts: str) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO user_watermarks (chat_id, symbol, last_announcement_ts)
                   VALUES (?, ?, ?)
                   ON CONFLICT(chat_id, symbol) DO UPDATE SET last_announcement_ts = ?""",
                (chat_id, symbol, ts, ts),
            )
            self._conn.commit()

    # ── Per-user notifications ──

    def get_user_notification(self, chat_id: str, ann_hash: str) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT 1 FROM user_notifications WHERE chat_id = ? AND hash = ? AND notified = 1",
                (chat_id, ann_hash),
            )
            return cursor.fetchone() is not None

    def mark_user_notified(self, chat_id: str, ann_hash: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT OR IGNORE INTO user_notifications (chat_id, hash, notified, notified_at)
                   VALUES (?, ?, 1, ?)""",
                (chat_id, ann_hash, now),
            )
            self._conn.commit()

    def get_user_unnotified(self, chat_id: str) -> List[str]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT hash FROM user_notifications WHERE chat_id = ? AND notified = 0",
                (chat_id,),
            )
            return [row[0] for row in cursor.fetchall()]

    # ── Migration from old single-user schema ──

    def migrate_existing_data(self, old_chat_id: str) -> None:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT COUNT(*) FROM user_watermarks"
            )
            if cursor.fetchone()[0] > 0:
                return

        today = self._get_today_midnight_utc()
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO users (chat_id, name, created_at) VALUES (?, ?, ?)",
                (old_chat_id, "migrated", now),
            )

            old_wm = self._conn.execute(
                "SELECT symbol, last_announcement_ts FROM watermarks"
            ).fetchall()
            for symbol, ts in old_wm:
                self._conn.execute(
                    """INSERT OR IGNORE INTO user_watermarks (chat_id, symbol, last_announcement_ts)
                       VALUES (?, ?, ?)""",
                    (old_chat_id, symbol, ts),
                )

            old_notified = self._conn.execute(
                "SELECT hash FROM announcements WHERE notified = 1"
            ).fetchall()
            for (h,) in old_notified:
                self._conn.execute(
                    """INSERT OR IGNORE INTO user_notifications (chat_id, hash, notified, notified_at)
                       VALUES (?, ?, 1, ?)""",
                    (old_chat_id, h, now),
                )

            self._conn.commit()

    # ── Cleanup ──

    def close(self) -> None:
        self._conn.close()

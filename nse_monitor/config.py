import os
from pathlib import Path
from typing import List

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv


class HTTPConfig(BaseSettings):
    timeout_seconds: int = 10
    max_retries: int = 5
    backoff_base_seconds: int = 2
    backoff_max_seconds: int = 120
    respect_retry_after: bool = True


class NotificationConfig(BaseSettings):
    provider: str = "telegram"
    max_per_minute: int = 20
    batch_window_seconds: int = 5


class DatabaseConfig(BaseSettings):
    path: str = "data/announcements.db"
    wal_mode: bool = True


class HealthConfig(BaseSettings):
    bind_host: str = "127.0.0.1"
    bind_port: int = 8787


class UserInfo(BaseSettings):
    chat_id: str
    name: str = ""


class Config(BaseSettings):
    poll_interval_seconds: int = 30
    poll_jitter_seconds: int = 5
    companies: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    http: HTTPConfig = Field(default_factory=HTTPConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_CHAT_IDS: str = ""
    users: List[UserInfo] = Field(default_factory=list)

    @classmethod
    def load(cls, config_path: str = "config/config.yaml") -> "Config":
        path = Path(config_path)
        data: dict = {}
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f) or {}

        data = {k: v for k, v in data.items() if v is not None}
        for key in ("companies", "categories"):
            data.setdefault(key, [])

        load_dotenv(".env")
        data["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "")
        data["TELEGRAM_CHAT_ID"] = os.getenv("TELEGRAM_CHAT_ID", "")
        data["TELEGRAM_CHAT_IDS"] = os.getenv("TELEGRAM_CHAT_IDS", "")

        cfg = cls(**data)

        chat_ids_str = data.get("TELEGRAM_CHAT_IDS") or data.get("TELEGRAM_CHAT_ID", "")
        chat_ids = [c.strip() for c in chat_ids_str.split(",") if c.strip()]
        if chat_ids:
            cfg.users = [UserInfo(chat_id=c) for c in chat_ids]

        return cfg

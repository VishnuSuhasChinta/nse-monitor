import hashlib
from typing import Optional

from nse_monitor.models import Announcement


def compute_hash(ann: Announcement) -> str:
    raw = f"{ann.symbol}|{ann.category}|{ann.headline}|{ann.announcement_ts}"
    return hashlib.sha256(raw.encode()).hexdigest()

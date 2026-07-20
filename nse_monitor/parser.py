import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from nse_monitor.models import Announcement

logger = logging.getLogger("nse_monitor.parser")

FIELD_MAP = {
    "symbol": ["symbol", "sym", "ticker"],
    "company_name": ["sm_name", "company_name", "companyName", "company", "compName"],
    "headline": ["attchmntText", "heading", "headline", "title", "subject"],
    "category": ["csvName", "desc", "category", "type", "category_name", "categoryName"],
    "announcement_ts": [
        "sort_date", "an_dt", "announcement_date", "announcementDate", "date", "dt",
        "timestamp", "ann_date", "ann_dt",
    ],
    "pdf_url": ["attchmntFile", "pdf_url", "pdfUrl", "pdf", "attachment_url", "attachmentUrl", "url"],
}

IST_OFFSET = timezone(timedelta(hours=5, minutes=30))

NSE_DATE_FORMATS = [
    "%d-%b-%Y %H:%M:%S",
    "%d-%b-%Y %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
]


def _extract_field(record: Dict[str, Any], candidates: List[str]) -> str:
    for key in candidates:
        val = record.get(key)
        if val is not None:
            return str(val).strip()
    return ""


def parse_announcement(raw: Dict[str, Any], seq_id: str = "") -> Optional[Announcement]:
    try:
        symbol = _extract_field(raw, FIELD_MAP["symbol"])
        if not symbol:
            logger.warning("Skipping record with no symbol: %s", str(raw)[:120])
            return None

        ann = Announcement(
            symbol=symbol.upper(),
            company_name=_extract_field(raw, FIELD_MAP["company_name"]),
            headline=_extract_field(raw, FIELD_MAP["headline"]),
            category=_extract_field(raw, FIELD_MAP["category"]),
            announcement_ts=_normalize_ts(_extract_field(raw, FIELD_MAP["announcement_ts"])),
            pdf_url=_extract_field(raw, FIELD_MAP["pdf_url"]),
            raw_json=raw,
        )
        return ann
    except Exception as e:
        logger.warning("Failed to parse announcement: %s", e)
        return None


def _normalize_ts(dt_str: str) -> str:
    if not dt_str:
        return datetime.now(timezone.utc).isoformat()
    cleaned = dt_str.replace(" IST", "").strip()
    for fmt in NSE_DATE_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            parsed = parsed.replace(tzinfo=IST_OFFSET)
            return parsed.astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            continue
    try:
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except (ValueError, TypeError):
        logger.warning("Could not parse timestamp: %s, using current UTC", dt_str)
        return datetime.now(timezone.utc).isoformat()


def parse_announcements(data: List[Dict[str, Any]]) -> List[Announcement]:
    results: List[Announcement] = []
    for raw in data:
        ann = parse_announcement(raw)
        if ann is not None:
            results.append(ann)
    logger.info("Parsed %d announcements from %d records", len(results), len(data))
    return results

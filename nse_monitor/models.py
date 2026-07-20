from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class Announcement(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str = ""
    company_name: str = ""
    headline: str = ""
    category: str = ""
    announcement_ts: str = ""
    pdf_url: str = ""
    hash: str = ""
    raw_json: Dict[str, Any] = Field(default_factory=dict)

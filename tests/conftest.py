import os
import tempfile
from pathlib import Path

import pytest

from nse_monitor.database import Database
from nse_monitor.models import Announcement


@pytest.fixture
def temp_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = Database(tmp.name, wal_mode=False)
    yield db
    db.close()
    os.unlink(tmp.name)


@pytest.fixture
def sample_announcement():
    return Announcement(
        symbol="TCS",
        company_name="Tata Consultancy Services Limited",
        headline="Board approves quarterly results",
        category="Financial Results",
        announcement_ts="2026-07-18T10:30:00",
        pdf_url="https://nseindia.com/pdf/tcs.pdf",
        raw_json={"symbol": "TCS", "headline": "Board approves quarterly results"},
    )

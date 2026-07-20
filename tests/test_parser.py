from nse_monitor.parser import parse_announcement, parse_announcements


def test_parse_valid():
    raw = {
        "symbol": "TCS",
        "sm_name": "Tata Consultancy Services Ltd",
        "attchmntText": "Board Meeting Intimation for Quarterly Results",
        "desc": "Board Meeting",
        "an_dt": "18-Jul-2026 15:42:00",
        "attchmntFile": "https://nsearchives.nseindia.com/corporate/tcs.pdf",
        "seq_id": "12345",
    }
    ann = parse_announcement(raw)
    assert ann is not None
    assert ann.symbol == "TCS"
    assert ann.company_name == "Tata Consultancy Services Ltd"
    assert "Board Meeting Intimation" in ann.headline


def test_parse_missing_fields():
    raw = {"symbol": "TCS"}
    ann = parse_announcement(raw)
    assert ann is not None
    assert ann.symbol == "TCS"
    assert ann.company_name == ""


def test_parse_empty_symbol():
    ann = parse_announcement({"symbol": "", "attchmntText": "test"})
    assert ann is None


def test_parse_missing_symbol():
    ann = parse_announcement({"attchmntText": "test"})
    assert ann is None


def test_parse_unknown_fields_preserved():
    raw = {
        "symbol": "TCS",
        "attchmntText": "Test",
        "extra_field": "should be preserved",
        "nested": {"key": "value"},
    }
    ann = parse_announcement(raw)
    assert ann is not None
    assert ann.raw_json["extra_field"] == "should be preserved"
    assert ann.raw_json["nested"]["key"] == "value"


def test_parse_multiple_announcements():
    data = [
        {"symbol": "TCS", "attchmntText": "A"},
        {"symbol": "INFY", "attchmntText": "B"},
        {},  # should be skipped (no symbol)
    ]
    results = parse_announcements(data)
    assert len(results) == 2


def test_parse_category_from_desc():
    raw = {"symbol": "TCS", "desc": "Board Meeting", "attchmntText": "Board meeting intimation"}
    ann = parse_announcement(raw)
    assert ann is not None
    assert ann.category == "Board Meeting"

import logging

import requests

logger = logging.getLogger("nse_monitor.session")

NSE_HOMEPAGE = "https://www.nseindia.com/market-data/live-equity-market"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.nseindia.com/",
}


def bootstrap_session(session: requests.Session) -> bool:
    try:
        resp = session.get(NSE_HOMEPAGE, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        logger.info("Session bootstrapped successfully")
        return True
    except requests.RequestException as e:
        logger.warning("Session bootstrap failed: %s", e)
        return False


def refresh_if_needed(session: requests.Session, response: requests.Response) -> bool:
    if response.status_code in (401, 403):
        logger.info("Session expired (HTTP %d), re-bootstrapping", response.status_code)
        return bootstrap_session(session)
    return False

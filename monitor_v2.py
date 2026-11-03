#!/usr/bin/env python3
"""ECOS status: independent read-only public account registration readiness.

The public report contains only confirmed ECOS configuration state.
It does not verify successful account creation, email delivery, or sign-in.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
READINESS = DATA / "readiness.json"
UTC = dt.timezone.utc
REGISTRATION_URL = "https://app.energycontrolos.com/api/public/access/config"

def timestamp():
    return dt.datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def fetch_json(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": "ECOS-Public-Status/2.0 (+https://status.energycontrolos.com/)",
        "Accept": "application/json",
        **headers
    })
    with urllib.request.urlopen(req, timeout=12) as response:
        if not 200 <= response.status < 300:
            raise ValueError("Unexpected HTTP response")
        media = response.headers.get("content-type", "").lower()
        if "application/json" not in media:
            raise ValueError("Unexpected content type")
        raw = response.read(350_000)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected an object")
    return data


def registration_status(now: str) -> dict:
    item = {
        "schema": 1, "source": "ECOS public registration configuration",
        "url": REGISTRATION_URL, "checked_at": now, "state": "unverified",
        "detail": "Registration configuration could not be verified.",
    }
    try:
        payload = fetch_json(REGISTRATION_URL, {
            "Origin": "https://www.energycontrolos.com",
        })
        if type(payload.get("enabled")) is not bool:
            raise ValueError("Missing readiness indicator")
        if payload["enabled"] and not isinstance(payload.get("siteKey"), str):
            raise ValueError("Missing public verification key")
        item["state"] = "ready" if payload["enabled"] else "not_accepting"
        item["detail"] = (
            "Public signup configuration is accepting applications. "
            "Submission, verification email and approval have not been tested."
            if payload["enabled"] else
            "Public registration is not currently accepting applications. "
            "This is a configuration result, not an endpoint outage."
        )
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, UnicodeError):
        pass
    return item



def run():
    DATA.mkdir(parents=True, exist_ok=True)
    report = registration_status(timestamp())
    READINESS.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ECOS public registration configuration:", report["state"])


if __name__ == "__main__":
    run()

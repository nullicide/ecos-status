#!/usr/bin/env python3
"""Independent public page-reachability monitoring for 115 Schiller.

No credentials, booking attempts, private pages, payments, or reservation
inventory are checked. Counts describe sampled GET requests, not guaranteed uptime.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "site" / "data" / "115schiller.json"
UTC = timezone.utc
TARGETS = {
    "website": ("https://www.115schiller.com/", "115 Schiller · Guttenberg, Iowa"),
    "booking": ("https://www.115schiller.com/book/", "Reserve your stay | 115 Schiller"),
    "guest": ("https://www.115schiller.com/guest/", "My Stays | 115 Schiller"),
    "owner": ("https://www.115schiller.com/admin/", "Secure owner and property operations portal for 115 Schiller."),
    "team": ("https://www.115schiller.com/team/", "Property Team · 115 Schiller"),
}
TITLES = {
    "website": "Public website",
    "booking": "Booking information page",
    "guest": "Guest portal entry",
    "owner": "Owner portal entry",
    "team": "Property team entry",
}

def timestamp(now: datetime) -> str:
    return now.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

def fresh() -> dict:
    return {
        "schema": 1, "project": "115-schiller", "checked_at": None,
        "first_checked_at": None,
        "components": {k: {"state": "unknown", "success_streak": 0, "fail_streak": 0} for k in TARGETS},
        "daily": {}, "incidents": [], "maintenance": [],
        "scope": "External HTTP page reachability only; no checkout, availability, account authentication, or task workflows tested.",
    }

def read() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else fresh()

def probe(item: tuple[str, tuple[str, str]]) -> tuple[str, bool]:
    name, (url, expected) = item
    for attempt in range(2):
        try:
            request = urllib.request.Request(
                url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; 115SchillerStatus/1.0)",
                    "Accept": "text/html",
                    "Cache-Control": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=13) as response:
                if not 200 <= response.status < 300:
                    raise ValueError("Non-2xx HTTP response")
                if "text/html" not in response.headers.get("content-type", "").lower():
                    raise ValueError("Unexpected content type")
                body = response.read(260_000).decode("utf-8", errors="replace")
                if expected.casefold() not in body.casefold():
                    raise ValueError("Expected exact page marker missing")
                return (name, True)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            # Log a bounded, non-sensitive failure reason for diagnostics.
            failure = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            if attempt == 0:
                time.sleep(1)
    print("115 Schiller probe", name, "failed:", failure, flush=True)
    return (name, False)

def open_auto_incident(data: dict, key: str, stamp: str) -> None:
    if any(i.get("origin") == "monitor" and i.get("component") == key and not i.get("ended_at")
           for i in data["incidents"]):
        return
    message = "Two consecutive external page checks failed. The cause has not been established."
    data["incidents"].append({
        "id": str(uuid.uuid4())[:12], "origin": "monitor", "component": key,
        "title": TITLES[key] + " — page reachability disruption",
        "detail": message, "status": "investigating",
        "started_at": stamp, "ended_at": None,
        "updates": [{"at": stamp, "status": "investigating", "detail": message}],
    })

def close_auto_incident(data: dict, key: str, stamp: str) -> None:
    for incident in data["incidents"]:
        if incident.get("origin") == "monitor" and incident.get("component") == key and not incident.get("ended_at"):
            if incident.get("classification") == "verification_false_positive":
                message = ("Owner-page monitoring verification recovered after correcting an obsolete "
                           "HTML title assertion. The earlier failed validations do not establish "
                           "an actual portal outage. Authentication and private workflows were not tested.")
            else:
                message = "External page responses recovered. Functional workflows remain unverified."
            incident.update({"status": "resolved", "ended_at": stamp, "detail": message})
            incident.setdefault("updates", []).append({"at": stamp, "status": "resolved", "detail": message})

def run() -> None:
    if os.getenv("ACTION", "check") != "check":
        print("ECOS manual publication; skipping independent 115 Schiller poll.")
        return
    data = read()
    now = datetime.now(UTC)
    stamp = timestamp(now)
    if not data.get("first_checked_at"):
        data["first_checked_at"] = stamp
    data["checked_at"] = stamp
    with ThreadPoolExecutor(max_workers=len(TARGETS)) as pool:
        results = dict(pool.map(probe, TARGETS.items()))
    day = now.date().isoformat()
    daily = data.setdefault("daily", {}).setdefault(day, {})
    for key in TARGETS:
        passed = results[key]
        obj = data.setdefault("components", {}).setdefault(key, {})
        prior = obj.get("state", "unknown")
        if passed:
            obj["success_streak"] = int(obj.get("success_streak", 0)) + 1
            obj["fail_streak"] = 0
            obj["state"] = "operational" if obj["success_streak"] >= 2 or prior in ("unknown", "operational") else "degraded"
            if obj["state"] == "operational":
                close_auto_incident(data, key, stamp)
        else:
            obj["fail_streak"] = int(obj.get("fail_streak", 0)) + 1
            obj["success_streak"] = 0
            obj["state"] = "outage" if obj["fail_streak"] >= 2 else "degraded"
            if obj["state"] == "outage":
                open_auto_incident(data, key, stamp)
        counts = daily.setdefault(key, {"ok": 0, "fail": 0})
        counts["ok" if passed else "fail"] += 1
    cutoff = (now - timedelta(days=90)).date().isoformat()
    data["daily"] = {k: v for k, v in data["daily"].items() if k >= cutoff}
    data["incidents"] = data["incidents"][-150:]
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("115 Schiller sampled reachability:", ", ".join(
        key + "=" + ("PASS" if results[key] else "FAIL") for key in TARGETS
    ), "at", stamp)

if __name__ == "__main__":
    run()

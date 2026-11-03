#!/usr/bin/env python3
"""ECOS Status v2: independent, read-only readiness and provider observability.

Public reachability remains owned by monitor.py. This module performs a separate
public configuration check and consumes Cloudflare's documented Status API.
No secrets, credential tests, or claimed end-to-end auth checks are published.
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
PROVIDER = DATA / "dependencies.json"
UTC = dt.timezone.utc
REGISTRATION_URL = "https://app.energycontrolos.com/api/public/access/config"
CLOUDFLARE_API = "https://www.cloudflarestatus.com/api/v2/summary.json"
CLOUDFLARE_LINK = "https://www.cloudflarestatus.com/"
STATUS_NAMES = (
    ("workers-builds", "Workers Builds"),
    ("pages", "Pages"),
    ("workers", "Workers"),
    ("d1", "D1"),
    ("turnstile", "Turnstile"),
    ("dns", "Authoritative DNS"),
    ("api", "API"),
)
GOOD_PROVIDER_STATES = {
    "operational", "degraded_performance", "partial_outage",
    "major_outage", "under_maintenance",
}


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


def provider_status(now: str, previous: dict | None = None) -> dict:
    result = {
        "schema": 1, "source": "Cloudflare Status API",
        "source_url": CLOUDFLARE_LINK,
        "attempted_at": now, "checked_at": None,
        "fetch_status": "unavailable", "components": [
            {"key": key, "name": name, "status": "unknown", "updated_at": None}
            for key, name in STATUS_NAMES
        ],
        "incidents": [],
        "scope": "Upstream provider reports; not ECOS endpoint measurements.",
    }
    try:
        data = fetch_json(CLOUDFLARE_API, {})
        components = data.get("components")
        incidents = data.get("incidents")
        if not isinstance(components, list) or not isinstance(incidents, list):
            raise ValueError("Cloudflare report missing component or incident lists")
        by_name = {
            c.get("name"): c for c in components
            if isinstance(c, dict) and isinstance(c.get("name"), str)
        }
        relevant_ids = set()
        rows = []
        for key, name in STATUS_NAMES:
            c = by_name.get(name, {})
            state = str(c.get("status", "unknown"))
            if state not in GOOD_PROVIDER_STATES:
                state = "unknown"
            identity = c.get("id")
            if isinstance(identity, str) and identity:
                relevant_ids.add(identity)
            rows.append({
                "key": key, "name": name, "status": state,
                "updated_at": c.get("updated_at") if isinstance(c.get("updated_at"), str) else None,
            })
        current = []
        for incident in incidents:
            if not isinstance(incident, dict) or incident.get("status") not in ("investigating", "identified", "monitoring"):
                continue
            affected = incident.get("components", [])
            ids = {
                c.get("id") for c in affected if isinstance(c, dict) and isinstance(c.get("id"), str)
            } if isinstance(affected, list) else set()
            if not ids.intersection(relevant_ids):
                continue
            # Restrict outbound incident links to official Cloudflare/Statuspage destinations.
            link = incident.get("shortlink")
            if not isinstance(link, str) or not (
                link.startswith("https://www.cloudflarestatus.com/")
                or link.startswith("https://stspg.io/")
            ):
                link = CLOUDFLARE_LINK
            updates = incident.get("incident_updates", [])
            latest = updates[0] if isinstance(updates, list) and updates and isinstance(updates[0], dict) else {}
            current.append({
                "id": str(incident.get("id", ""))[:80],
                "name": str(incident.get("name", "Provider incident"))[:180],
                "status": incident["status"],
                "impact": str(incident.get("impact", "none"))[:30],
                "updated_at": str(incident.get("updated_at") or "")[:40],
                "detail": str(latest.get("body") or "")[:350],
                "url": link,
            })
        result.update({
            "fetch_status": "ok",
            "checked_at": now,
            "components": rows,
            "incidents": current[:8],
        })
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, UnicodeError, TypeError):
        # Preserve the previous snapshot only as historical context. The UI
        # must render it as unverified because the latest refresh failed.
        if isinstance(previous, dict):
            result["checked_at"] = previous.get("checked_at")
            result["components"] = previous.get("components", result["components"])
            result["incidents"] = previous.get("incidents", [])
    return result


def safe_read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def run():
    DATA.mkdir(parents=True, exist_ok=True)
    now = timestamp()
    readiness = registration_status(now)
    provider = provider_status(now, safe_read(PROVIDER))
    READINESS.write_text(json.dumps(readiness, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    PROVIDER.write_text(json.dumps(provider, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ECOS registration configuration:", readiness["state"])
    print("Cloudflare provider feed:", provider["fetch_status"])
    print("Provider state is independent of observed ECOS HTTP reachability.")


if __name__ == "__main__":
    run()

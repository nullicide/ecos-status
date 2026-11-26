"""Independent read-only production release smoke check (GitHub Actions)."""
import datetime as dt
import json
import time
import urllib.request
import xml.etree.ElementTree as ET

HOST="https://status.energycontrolos.com/"
MIRROR="https://nullicide.github.io/ecos-status/"
RAW="https://raw.githubusercontent.com/nullicide/ecos-status/main/site/data/status.json"
IDS={"platform","identity","academy","public_website","investor"}

def get(url):
    sep="&" if "?" in url else "?"
    req=urllib.request.Request(url+sep+"release="+str(time.time_ns()),headers={"Cache-Control":"no-cache","User-Agent":"ECOS-IRI001-release-check"})
    with urllib.request.urlopen(req,timeout=15) as res:
        if res.status!=200: raise RuntimeError("Unexpected HTTP status")
        return res.read(2_000_000).decode("utf-8")

def verify():
    for origin in (HOST,MIRROR):
        html=get(origin)
        assert "iri001-20261126" in html and 'id="activeIncidents"' in html, "Old or unexpected public shell"
        assert "System status" in html, "Missing public status title"
        print("Verified public shell:",origin)
    for url in (RAW,MIRROR+"data/status.json"):
        data=json.loads(get(url))
        assert data.get("monitoring_version")==2 and set(data["components"])==IDS, "Legacy or incomplete report"
        assert data.get("archived_monitoring",{}).get("daily"), "Legacy history missing"
        checked=dt.datetime.fromisoformat(data["checked_at"].replace("Z","+00:00"))
        age=(dt.datetime.now(dt.timezone.utc)-checked).total_seconds()
        assert -300<=age<=1500, "Monitoring report is not current"
        print("Verified report:",url,"at",data["checked_at"],"states:",{k:v["state"] for k,v in data["components"].items()})
    assert ET.fromstring(get(MIRROR+"feed.xml")).tag=="rss", "RSS invalid"
    print("Verified independent RSS publication")

if __name__=="__main__":
    for attempt in range(12):
        try:
            verify()
            break
        except (OSError,ValueError,AssertionError,RuntimeError) as e:
            print("Release check",attempt+1,"not yet verified:",type(e).__name__,str(e))
            if attempt==11: raise
            time.sleep(10)

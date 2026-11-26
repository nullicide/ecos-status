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

def verify_shell(origin):
    html=get(origin)
    assert "iri001-20261126" in html and 'id="activeIncidents"' in html, "Old or unexpected public shell"
    assert "System status" in html, "Missing public status title"

def verify_report(url):
    data=json.loads(get(url))
    assert data.get("monitoring_version")==2 and set(data["components"])==IDS, "Legacy or incomplete report"
    assert data.get("archived_monitoring",{}).get("daily"), "Legacy history missing"
    checked=dt.datetime.fromisoformat(data["checked_at"].replace("Z","+00:00"))
    age=(dt.datetime.now(dt.timezone.utc)-checked).total_seconds()
    assert -300<=age<=1500, "Monitoring report is not current"

def verify_rss(url):
    assert ET.fromstring(get(url)).tag=="rss", "RSS invalid"

def verify():
    # Never let one broken mirror suppress evidence for unrelated endpoints.
    targets=[
        ("canonical shell",verify_shell,HOST),
        ("mirror shell",verify_shell,MIRROR),
        ("canonical report",verify_report,RAW),
        ("mirror report",verify_report,MIRROR+"data/service-status-v2.json"),
        ("mirror RSS",verify_rss,MIRROR+"feed.xml"),
        ("public RSS",verify_rss,HOST+"feed.xml"),
    ]
    failed=[]
    for name,check,url in targets:
        try:
            check(url)
            print("PASS:",name,flush=True)
        except (OSError,ValueError,AssertionError,RuntimeError,ET.ParseError,KeyError) as error:
            failed.append(name)
            print("FAIL:",name,type(error).__name__,str(error),flush=True)
    if failed:
        raise RuntimeError("Failed release checks: "+", ".join(failed))

if __name__=="__main__":
    for attempt in range(12):
        try:
            verify()
            break
        except (OSError,ValueError,AssertionError,RuntimeError) as e:
            print("Release check",attempt+1,"not yet verified:",type(e).__name__,str(e))
            if attempt==11: raise
            time.sleep(10)

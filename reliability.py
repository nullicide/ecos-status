#!/usr/bin/env python3
"""IRI-001: observed service checks, not a certification of backend functionality."""
import concurrent.futures
import copy
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import monitor as legacy

# kind: html, guest (expected anonymous denial), session (null), config (enabled).
# Required means failure affects the service; optional probes are diagnostic only.
SERVICES = {
    "platform": {"title":"ECOS Platform", "complete":False, "checks":["workspace"]},
    "identity": {"title":"Identity & Access", "complete":False, "checks":["login","session","registration"]},
    "academy": {"title":"ECOS Academy", "complete":False, "checks":["academy_home","academy_lesson"]},
    "public_website": {"title":"Public Website", "complete":True, "checks":["website_home","inquiry_config"]},
    "investor": {"title":"Investor Portal", "complete":False, "checks":["investor_home","investor_session","investor_vault"]},
}
PROBES = {
    "workspace": ("https://app.energycontrolos.com/api/v1/workspace", "guest", (), True),
    "login": ("https://app.energycontrolos.com/login/", "html", ('id="login-form"', 'Energy Control OS'), True),
    "session": ("https://app.energycontrolos.com/api/auth/get-session", "session", (), True),
    "registration": ("https://app.energycontrolos.com/api/public/access/config", "config", (), False),
    "academy_home": ("https://academy.energycontrolos.com/", "html", ('ECOS Academy','id="hero-title"'), True),
    "academy_lesson": ("https://academy.energycontrolos.com/missions/lo-01/", "html", ('id="lesson"','id="assessment"'), True),
    "website_home": ("https://www.energycontrolos.com/", "html", ('id="hero-title"','id="platform"'), True),
    "inquiry_config": ("https://www.energycontrolos.com/api/access-config", "config", (), False),
    "investor_home": ("https://invest.energycontrolos.com/", "html", ('id="investor-auth"','Investor Relations Portal'), True),
    "investor_session": ("https://invest.energycontrolos.com/api/auth/session", "investor_session", (), True),
    "investor_vault": ("https://invest.energycontrolos.com/api/private/documents", "investor_guest", (), False),
}
VERSION = 2

def migrate(data, instant):
    if data.get("monitoring_version") == VERSION:
        return data
    # Keep all original counters, states and timestamps, not merely rolling totals.
    if "archived_monitoring" in data:
        raise ValueError("Unrecognized migration state; refusing to overwrite history")
    data["archived_monitoring"] = {
        "retired_at":legacy.iso(instant), "checked_at":data.get("checked_at"),
        "first_checked_at":data.get("first_checked_at"),
        "components":copy.deepcopy(data.get("components",{})),
        "daily":copy.deepcopy(data.get("daily",{})),
        "reason":"Public webpage checks retired; service evidence starts independently."
    }
    data.update(monitoring_version=VERSION, checked_at=None, first_checked_at=None,
                components={}, daily={}, probes={}, probe_daily={})
    data.setdefault("incidents",[])
    data.setdefault("maintenance",[])
    return data

def validate(kind, status, content_type, body, markers=()):
    if kind == "html":
        return (status == 200 and "text/html" in content_type.lower()
                and all(m.lower() in body.lower() for m in markers)
                and "just a moment..." not in body.lower())
    if "application/json" not in content_type.lower():
        return False
    try:
        value=json.loads(body)
    except (ValueError,TypeError):
        return False
    if kind == "session":
        return status == 200 and value is None
    if not isinstance(value,dict):
        return False
    if kind == "guest":
        return status in (401,403) and value.get("ok") is False and isinstance(value.get("error"),str)
    if kind == "investor_session":
        return status == 401 and value.get("authenticated") is False
    if kind == "investor_guest":
        return status == 401 and value.get("ok") is False
    if kind == "config":
        return status == 200 and value.get("enabled") is True and isinstance(value.get("siteKey"),str) and len(value["siteKey"])>8
    return False

def probe(name):
    url,kind,markers,_=PROBES[name]
    for attempt in range(2):
        began=time.monotonic()
        try:
            headers={"User-Agent":"ECOS-External-Availability/2.0",
                     "Accept":"text/html" if kind=="html" else "application/json",
                     "Cache-Control":"no-cache"}
            if name=="registration":
                headers["Origin"]="https://www.energycontrolos.com"
            req=urllib.request.Request(url,headers=headers)
            try:
                response=urllib.request.urlopen(req,timeout=12)
            except urllib.error.HTTPError as error:
                response=error
            with response as res:
                final=urllib.parse.urlsplit(res.geturl())
                expected=urllib.parse.urlsplit(url)
                same=(final.scheme,final.netloc,final.path.rstrip("/"))==(expected.scheme,expected.netloc,expected.path.rstrip("/"))
                body=res.read(220000).decode("utf-8",errors="replace")
                if same and validate(kind,res.status,res.headers.get("content-type",""),body,markers):
                    return {"passed":True,"latency_ms":round((time.monotonic()-began)*1000)}
                print(f"{name}: unexpected HTTP or response contract ({res.status})")
        except (OSError,ValueError,TimeoutError) as error:
            print(f"{name}: {type(error).__name__}")
        if attempt==0:
            time.sleep(1)
    return {"passed":False,"latency_ms":None}

def record(data, results, instant):
    migrate(data,instant)
    if set(results)!=set(PROBES):
        raise ValueError("Incomplete monitoring cycle; do not publish a partial report")
    stamp=legacy.iso(instant)
    previous=data.get("checked_at")
    legacy.record_monitoring_gap(data,previous,instant)
    # A report restores publication, not service availability during the gap.
    for incident in data["incidents"]:
        if incident.get("component")=="monitoring" and not incident.get("ended_at"):
            incident.update(ended_at=stamp,status="resolved")
            incident.setdefault("updates",[]).append({"at":stamp,"status":"resolved",
              "detail":"Monitoring reports resumed; unobserved intervals remain unknown."})
    data["first_checked_at"]=data.get("first_checked_at") or stamp
    data["checked_at"]=data["published_at"]=stamp
    day=instant.date().isoformat()
    daily=data["daily"].setdefault(day,{})
    probes=data["probe_daily"].setdefault(day,{})
    for name,result in results.items():
        passed=result["passed"] is True
        old=data["probes"].get(name,{})
        data["probes"][name]={"passed":passed,"latency_ms":result.get("latency_ms"),
          "checked_at":stamp,"fail_streak":0 if passed else old.get("fail_streak",0)+1,
          "success_streak":old.get("success_streak",0)+1 if passed else 0}
        count=probes.setdefault(name,{"ok":0,"fail":0})
        count["ok" if passed else "fail"]+=1
    for name,spec in SERVICES.items():
        required=[data["probes"][p] for p in spec["checks"] if PROBES[p][3]]
        failed=[p for p in required if not p["passed"]]
        passed=not failed
        old=data["components"].get(name,{})
        if failed:
            if all(p["fail_streak"]>=2 for p in required):
                state="outage"
            elif any(p["fail_streak"]>=2 for p in failed):
                state="partial"
            else:
                state="degraded"
        elif old.get("state") in ("outage","partial","degraded") and any(p["success_streak"]<2 for p in required):
            state="degraded"
        else:
            state="operational"
        data["components"][name]={"state":state,"checked_at":stamp,
            "required_passed":sum(p["passed"] for p in required),"required_total":len(required),
            "coverage_complete":spec["complete"]}
        sample=daily.setdefault(name,{"ok":0,"fail":0})
        sample["ok" if passed else "fail"]+=1
        # Separate verified service states from raw check-set counts; never backfill.
        verified=data.setdefault("scoped_availability_daily",{}).setdefault(day,{}).setdefault(name,{})
        verified[state]=verified.get(state,0)+1
        active=next((i for i in data["incidents"] if i.get("origin")=="service-monitor" and i.get("component")==name and not i.get("ended_at")),None)
        if state in ("outage","partial") and active is None:
            detail="Repeated external service checks failed. The cause and extent of user impact remain unknown."
            data["incidents"].append({"id":str(uuid.uuid4())[:12],"origin":"service-monitor","component":name,
              "title":spec["title"]+" — investigating check failures","detail":detail,"status":"investigating",
              "started_at":stamp,"ended_at":None,"updates":[{"at":stamp,"status":"investigating","detail":detail}]})
        elif active and passed and all(p["success_streak"]>=2 for p in required):
            detail="External checks passed again. Functions outside those checks require separate verification."
            active.update(ended_at=stamp,status="resolved")
            active.setdefault("updates",[]).append({"at":stamp,"status":"resolved","detail":detail})
    # Never truncate historical observations, incidents or maintenance records.
    return data

def main():
    data=legacy.read()
    instant=legacy.now()
    migrate(data,instant)
    action=os.getenv("ACTION","check").strip() or "check"
    if action=="check":
        before={k:v.get("state") for k,v in data["components"].items()}
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results=dict(zip(PROBES,pool.map(probe,PROBES)))
        record(data,results,legacy.now())
        print("Probe results:",", ".join(f"{k}={v['passed']}" for k,v in results.items()))
        changed=[f"{SERVICES[k]['title']}: {before.get(k,'unknown')} -> {v['state']}"
                 for k,v in data["components"].items() if before.get(k,"unknown")!=v["state"]]
        if changed:
            legacy.alert_operator("ECOS service monitoring: "+"; ".join(changed)+" · "+legacy.URL)
    else:
        component=os.getenv("COMPONENT","public_website")
        if component not in SERVICES:
            raise ValueError("Choose an active service")
        legacy.manual(data,action,component,os.getenv("TITLE",""),os.getenv("MESSAGE",""),
                      os.getenv("START_UTC",""),os.getenv("END_UTC",""),instant)
        data["published_at"]=legacy.iso(instant)
        legacy.alert_operator("ECOS status publication: "+action+" / "+component+" · "+legacy.URL)
    legacy.write(data)

if __name__=="__main__":
    main()

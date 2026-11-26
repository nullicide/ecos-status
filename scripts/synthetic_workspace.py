"""Opt-in synthetic workspace read. Never publishes customer data or status."""
import json
import os
import re
import urllib.request
import urllib.error

URL="https://app.energycontrolos.com/api/v1/workspace?resource=bootstrap"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def fetch(cookie):
    # Fixed destination, no redirects, no URLs or cookie values in diagnostics.
    req=urllib.request.Request(URL,headers={"Cookie":cookie,"Accept":"application/json","Cache-Control":"no-store"},method="GET")
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=10) as response:
        if response.status!=200 or "application/json" not in response.headers.get("Content-Type","").lower():
            raise ValueError("unexpected response")
        body=response.read(65537)
        if len(body)>65536: raise ValueError("oversized response")
        return json.loads(body)

def run(env,transport=fetch):
    if env.get("ECOS_SYNTHETIC_ENABLED")!="true":
        return "inactive"
    cookie=env.get("ECOS_SYNTHETIC_APP_COOKIE","")
    org=env.get("ECOS_SYNTHETIC_ORG_ID","")
    project=env.get("ECOS_SYNTHETIC_PROJECT_ID","")
    email=env.get("ECOS_SYNTHETIC_EMAIL","")
    if not (cookie and len(cookie)<=4096 and re.fullmatch(r"[!-~]+(?: [!-~]+)*",cookie) and
            re.fullmatch(r"[A-Za-z0-9_-]{1,80}",org) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}",project) and
            re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",email)):
        return "configuration_required"
    try:
        value=transport(cookie)
        actor=value.get("actor",{})
        projects=value.get("projects")
        # Require isolated non-admin identity with exactly one authorized fixture.
        if (value.get("ok") is True and actor.get("org_id")==org and actor.get("display")==email
            and actor.get("role") not in (None,"admin") and value.get("canCreateProject") is False
            and isinstance(projects,list) and len(projects)==1 and projects[0].get("id")==project
            and projects[0].get("role")=="viewer"):
            return "passed"
    except Exception:
        # Do not log exception strings, response data, or configuration.
        pass
    return "failed"

if __name__=="__main__":
    result=run(os.environ)
    print("Synthetic workspace read:",result)
    raise SystemExit(0 if result in ("inactive","passed") else 1)

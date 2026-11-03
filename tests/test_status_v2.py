"""ECOS Status v2: public config and official provider API, no secrets or inferred health."""
import datetime as dt
import json
import unittest
from unittest.mock import patch
import urllib.error

import monitor_v2 as v2

class Response:
    status = 200
    headers = {"content-type":"application/json; charset=utf-8"}
    def __init__(self, payload):
        self.content = json.dumps(payload).encode("utf-8")
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, max_bytes): return self.content[:max_bytes]

class StatusV2Tests(unittest.TestCase):
    now = "2026-11-03T17:55:00Z"

    def test_registration_ready_only_when_public_config_enabled(self):
        with patch.object(v2.urllib.request, "urlopen",
                          return_value=Response({"enabled": True, "siteKey": "public-site-key-123"})) as call:
            item = v2.registration_status(self.now)
        self.assertEqual(item["state"], "ready")
        self.assertNotIn("siteKey", item)
        self.assertEqual(call.call_args.args[0].get_header("Origin"), "https://www.energycontrolos.com")

    def test_registration_disabled_is_not_an_outage(self):
        with patch.object(v2.urllib.request, "urlopen",
                          return_value=Response({"enabled": False, "siteKey": None})):
            self.assertEqual(v2.registration_status(self.now)["state"], "not_accepting")

    def test_registration_malformed_and_blocked_fail_closed(self):
        for payload in ({"enabled": "true"}, {"enabled": True, "siteKey": None}, {}):
            with patch.object(v2.urllib.request, "urlopen", return_value=Response(payload)):
                self.assertEqual(v2.registration_status(self.now)["state"], "unverified")
        with patch.object(v2.urllib.request, "urlopen",
                          side_effect=urllib.error.URLError("provider inaccessible")):
            self.assertEqual(v2.registration_status(self.now)["state"], "unverified")

    def summary(self):
        components = [{
            "id":"id-"+key, "name": name,
            "status": "degraded_performance" if key=="workers-builds" else "operational",
            "updated_at": self.now,
        } for key,name in v2.STATUS_NAMES]
        return {
            "components": components,
            "incidents": [
                {"id":"cf-incident", "name":"Build queue delays", "status":"identified",
                 "impact":"minor", "updated_at":self.now,
                 "shortlink":"https://stspg.io/abc123",
                 "components":[{"id":"id-workers-builds"}],
                 "incident_updates":[{"body":"Builds may be delayed"}]},
                {"id":"unrelated", "name":"Unrelated service", "status":"investigating",
                 "components":[{"id":"not-an-ecos-dependency"}]},
                {"id":"older", "name":"Resolved old incident", "status":"resolved",
                 "components":[{"id":"id-pages"}]},
            ]
        }

    def test_provider_filters_incidents_and_preserves_attribution(self):
        with patch.object(v2.urllib.request, "urlopen", return_value=Response(self.summary())):
            result=v2.provider_status(self.now)
        self.assertEqual(result["fetch_status"], "ok")
        self.assertEqual(len(result["components"]),len(v2.STATUS_NAMES))
        self.assertEqual(result["components"][0]["status"], "degraded_performance")
        self.assertEqual(len(result["incidents"]),1)
        self.assertEqual(result["incidents"][0]["name"],"Build queue delays")
        self.assertEqual(result["incidents"][0]["url"],"https://stspg.io/abc123")

    def test_provider_invalid_url_is_not_exposed(self):
        data=self.summary()
        data["incidents"][0]["shortlink"]="https://evil.example/incident"
        with patch.object(v2.urllib.request, "urlopen", return_value=Response(data)):
            result=v2.provider_status(self.now)
        self.assertEqual(result["incidents"][0]["url"],"https://www.cloudflarestatus.com/")

    def test_provider_failure_never_looks_current(self):
        previous={"checked_at":"2026-11-03T16:00:00Z",
                  "components":[{"name":"Pages","status":"operational"}],
                  "incidents":[]}
        with patch.object(v2.urllib.request, "urlopen",
                          side_effect=urllib.error.URLError("upstream unavailable")):
            result=v2.provider_status(self.now,previous)
        self.assertEqual(result["fetch_status"],"unavailable")
        self.assertEqual(result["checked_at"],previous["checked_at"])
        self.assertEqual(result["components"],previous["components"])

    def test_invalid_provider_json_is_unknown(self):
        with patch.object(v2.urllib.request,"urlopen",return_value=Response({"components":[]})):
            result=v2.provider_status(self.now)
        self.assertEqual(result["fetch_status"],"unavailable")
        self.assertTrue(all(x["status"]=="unknown" for x in result["components"]))

    def test_get_uses_json_and_identifying_agent(self):
        with patch.object(v2.urllib.request,"urlopen",return_value=Response({"enabled":False})) as mock:
            v2.fetch_json("https://example.com/config",{})
        req=mock.call_args.args[0]
        self.assertIn("ECOS-Public-Status",req.get_header("User-agent"))
        self.assertEqual(req.get_header("Accept"),"application/json")

if __name__=="__main__": unittest.main()

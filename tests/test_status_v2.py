"""Public ECOS configuration monitoring; no vendor dependency data is published."""
import json
import unittest
from unittest.mock import patch
import urllib.error
import monitor_v2 as status
from pathlib import Path

class Response:
    status=200
    headers={"content-type":"application/json; charset=utf-8"}
    def __init__(self, payload):self.content=json.dumps(payload).encode()
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,max_bytes):return self.content[:max_bytes]

class StatusV2Tests(unittest.TestCase):
    now="2026-11-03T17:55:00Z"
    def test_signup_configuration_enabled(self):
        with patch.object(status.urllib.request,"urlopen",return_value=Response({"enabled":True,"siteKey":"public-site-key-123"})) as mock:
            result=status.registration_status(self.now)
        self.assertEqual(result["state"],"ready")
        self.assertNotIn("siteKey",result)
        self.assertEqual(mock.call_args.args[0].get_header("Origin"),"https://www.energycontrolos.com")
    def test_disabled_is_not_outage(self):
        with patch.object(status.urllib.request,"urlopen",return_value=Response({"enabled":False,"siteKey":None})):
            self.assertEqual(status.registration_status(self.now)["state"],"not_accepting")
    def test_unknown_fail_closed(self):
        for payload in ({"enabled":"true"},{}, {"enabled":True,"siteKey":None}):
            with patch.object(status.urllib.request,"urlopen",return_value=Response(payload)):
                self.assertEqual(status.registration_status(self.now)["state"],"unverified")
        with patch.object(status.urllib.request,"urlopen",side_effect=urllib.error.URLError("unavailable")):
            self.assertEqual(status.registration_status(self.now)["state"],"unverified")
    def test_requests_use_json(self):
        with patch.object(status.urllib.request,"urlopen",return_value=Response({"enabled":False})) as mock:
            status.fetch_json("https://example.com/config",{})
        req=mock.call_args.args[0]
        self.assertEqual(req.get_header("Accept"),"application/json")
    def test_provider_data_is_not_part_of_public_site(self):
        self.assertFalse((status.DATA / "dependencies.json").exists())
        content=(status.ROOT/"site"/"status-v2.js").read_text(encoding="utf-8")
        self.assertNotIn("dependencies.json",content)
        self.assertNotIn("cloudflarestatus.com",content)
    def test_public_service_mapping_keeps_functional_checks_unverified(self):
        js=(status.ROOT/"site"/"status-v2.js").read_text(encoding="utf-8")
        for item in ("Project workspace","Energy-control documentation","Notifications and tasks","Not independently tested"):
            self.assertIn(item,js)
        self.assertIn("Page reachable",js)
        self.assertIn("Intake configured",js)

if __name__=="__main__":unittest.main()

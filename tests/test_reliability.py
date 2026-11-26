import copy
import datetime as dt
import unittest
import reliability as r

class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,11,26,22,30,tzinfo=dt.timezone.utc)
        self.data={"schema":1,"checked_at":"2026-11-26T22:00:00Z","first_checked_at":"2026-10-24T00:00:00Z",
          "components":{"website":{"state":"operational"}}, "daily":{"2026-11-25":{"website":{"ok":99,"fail":1}}},
          "incidents":[{"id":"old","component":"website","ended_at":"2026-11-25T01:00:00Z"}],"maintenance":[]}
        self.good={name:{"passed":True,"latency_ms":100} for name in r.PROBES}
    def cycle(self,failed=()):
        results=copy.deepcopy(self.good)
        for name in failed: results[name]["passed"]=False
        r.record(self.data,results,self.now)
        self.now+=dt.timedelta(minutes=5)
    def test_migration_no_inherited_history(self):
        old=copy.deepcopy(self.data)
        self.cycle()
        self.assertEqual(self.data["archived_monitoring"]["daily"],old["daily"])
        self.assertEqual(self.data["archived_monitoring"]["components"],old["components"])
        self.assertEqual(self.data["incidents"],old["incidents"])
        self.assertEqual(self.data["daily"]["2026-11-26"]["public_website"],{"ok":1,"fail":0})
        self.assertEqual(self.data["components"]["platform"]["state"],"operational")
        self.assertEqual(self.data["components"]["public_website"]["state"],"operational")
    def test_verified_history_separate_from_raw_checks(self):
        self.cycle()
        self.assertEqual(self.data["scoped_availability_daily"]["2026-11-26"]["platform"],{"operational":1})
        self.assertEqual(self.data["scoped_availability_daily"]["2026-11-26"]["public_website"],{"operational":1})
        self.cycle(["academy_lesson"])
        self.assertEqual(self.data["scoped_availability_daily"]["2026-11-26"]["academy"],{"operational":1,"degraded":1})
    def test_optional_probe_does_not_down_service(self):
        self.cycle(["inquiry_config","registration"])
        self.cycle(["inquiry_config","registration"])
        self.assertEqual(self.data["components"]["public_website"]["state"],"operational")
        self.assertEqual(self.data["components"]["identity"]["state"],"operational")
    def test_partial_and_major_and_recovery(self):
        self.cycle(["academy_lesson"])
        self.assertEqual(self.data["components"]["academy"]["state"],"degraded")
        self.cycle(["academy_lesson"])
        self.assertEqual(self.data["components"]["academy"]["state"],"partial")
        self.cycle(["academy_lesson","academy_home"])
        self.cycle(["academy_lesson","academy_home"])
        self.assertEqual(self.data["components"]["academy"]["state"],"outage")
        self.cycle(); self.cycle()
        self.assertEqual(self.data["components"]["academy"]["state"],"operational")
        self.assertTrue(self.data["incidents"][-1]["ended_at"])
    def test_monitor_gap_not_down(self):
        self.cycle(); self.now+=dt.timedelta(hours=2); self.cycle()
        self.assertEqual(self.data["components"]["public_website"]["state"],"operational")
        self.assertEqual(self.data["incidents"][-1]["component"],"monitoring")
        self.assertTrue(self.data["incidents"][-1]["ended_at"])
    def test_contracts(self):
        self.assertTrue(r.validate("session",200,"application/json","null"))
        self.assertFalse(r.validate("session",200,"application/json","{}"))
        self.assertTrue(r.validate("guest",401,"application/json",'{"ok":false,"error":"Sign-in required"}'))
        self.assertFalse(r.validate("guest",200,"application/json",'{"ok":true}'))
        self.assertFalse(r.validate("investor_session",503,"application/json",'{"authenticated":false}'))
        self.assertFalse(r.validate("html",200,"text/html","OK",("marker",)))
        self.assertFalse(r.validate("config",200,"application/json",'{"enabled":false}'))
    def test_incomplete_cycle_does_not_publish(self):
        with self.assertRaises(ValueError): r.record(self.data,{},self.now)
        self.assertIsNone(self.data["checked_at"])

if __name__=="__main__": unittest.main()

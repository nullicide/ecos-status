"""Current ECOS public endpoint probes and migration-safe availability history."""
import copy
import datetime as dt
import unittest
from unittest.mock import patch
import monitor


class FakeResponse:
    def __init__(self, page, url, status=200, content_type="text/html; charset=utf-8", final_url=None):
        self.body = page.encode("utf-8")
        self.status = status
        self.headers = {"content-type": content_type}
        self.url = final_url or url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.body[:limit]

    def geturl(self):
        return self.url


class ECOSPublicStatusTests(unittest.TestCase):
    def probe(self, name, page, *, status=200, content_type="text/html; charset=utf-8", final_url=None):
        url, markers = monitor.TARGETS[name]
        response = FakeResponse(page, url, status, content_type, final_url)
        with patch.object(monitor.urllib.request, "urlopen", return_value=response):
            with patch.object(monitor.time, "sleep"):
                return monitor.check_http(url, markers)

    def test_every_public_page_uses_current_canonical_url(self):
        self.assertEqual(set(monitor.TARGETS), {
            "website", "operating_picture", "standards", "signup", "enterprise", "access"
        })
        self.assertEqual(monitor.TARGETS["website"][0], "https://www.energycontrolos.com/")
        self.assertEqual(monitor.TARGETS["operating_picture"][0], "https://www.energycontrolos.com/operating-picture/")
        self.assertEqual(monitor.TARGETS["standards"][0], "https://www.energycontrolos.com/standards/")
        self.assertEqual(monitor.TARGETS["signup"][0], "https://www.energycontrolos.com/create-account/")
        self.assertEqual(monitor.TARGETS["enterprise"][0], "https://www.energycontrolos.com/enterprise-access/")
        self.assertEqual(monitor.TARGETS["access"][0], "https://app.energycontrolos.com/login/")
        self.assertNotIn("requests", monitor.TARGETS, "Do not actively probe obsolete redirect")
        self.assertEqual(len({u for u, _ in monitor.TARGETS.values()}), 6)
        self.assertEqual(len({markers[0] for _, markers in monitor.TARGETS.values()}), 6)

    def test_realistic_expected_page_landmarks(self):
        for key, (_, markers) in monitor.TARGETS.items():
            with self.subTest(component=key):
                page = "<html><body>" + "".join(markers) + "</body></html>"
                self.assertTrue(self.probe(key, page))

    def test_partial_or_generic_pages_never_count_as_success(self):
        for key, (_, markers) in monitor.TARGETS.items():
            with self.subTest(component=key):
                page = "<html><body>" + markers[0] + "</body></html>"
                if len(markers) > 1:
                    self.assertFalse(self.probe(key, page))
                self.assertFalse(self.probe(key, "<html><title>ECOS</title><p>OK</p></html>"))

    def test_legacy_redirect_does_not_count_for_new_enterprise(self):
        real_url, markers = monitor.TARGETS["enterprise"]
        page = "<html><body>" + "".join(markers) + "</body></html>"
        self.assertFalse(self.probe("enterprise", page,
            final_url="https://www.energycontrolos.com/request-access/"))
        self.assertTrue(self.probe("enterprise", page, final_url=real_url))

    def test_cloudflare_challenge_and_errors_do_not_count_as_healthy(self):
        self.assertFalse(self.probe("signup", "<title>Just a moment...</title>"))
        _, markers = monitor.TARGETS["signup"]
        good = "<html>" + "".join(markers) + "</html>"
        self.assertFalse(self.probe("signup", good, status=503))
        self.assertFalse(self.probe("signup", good, content_type="text/plain"))

    def test_network_failure_is_not_a_success(self):
        with patch.object(monitor.urllib.request, "urlopen",
                          side_effect=monitor.urllib.error.URLError("upstream unavailable")):
            with patch.object(monitor.time, "sleep"):
                self.assertFalse(monitor.check_http(*monitor.TARGETS["enterprise"]))

    def test_first_new_monitor_cycle_preserves_retired_history(self):
        older = "2026-11-03T18:11:52Z"
        instant = dt.datetime(2026, 11, 4, 16, 30, tzinfo=dt.timezone.utc)
        existing = {
            "schema": 1,
            "checked_at": older,
            "first_checked_at": "2026-10-24T03:34:31Z",
            "components": {
                "website": {"state": "operational", "success_streak": 467, "fail_streak": 0},
                "access": {"state": "operational", "success_streak": 467, "fail_streak": 0},
                "requests": {"state": "degraded", "success_streak": 0, "fail_streak": 1},
            },
            "daily": {
                "2026-11-03": {
                    "website": {"ok": 34, "fail": 0},
                    "access": {"ok": 34, "fail": 0},
                    "requests": {"ok": 32, "fail": 2},
                }
            },
            "incidents": [{
                "id": "legacy-incident", "origin": "monitor", "component": "requests",
                "title": "Request Access page — availability disruption",
                "started_at": older, "ended_at": older, "status": "resolved",
                "updates": []
            }],
            "maintenance": [],
        }
        snapshot = copy.deepcopy(existing)
        results = {key: True for key in monitor.TARGETS}
        output = monitor.monitor(existing, results, instant)
        self.assertEqual(output["components"]["requests"], snapshot["components"]["requests"])
        self.assertEqual(output["daily"]["2026-11-03"]["requests"], {"ok": 32, "fail": 2})
        self.assertEqual(output["incidents"], snapshot["incidents"])
        self.assertEqual(output["components"]["enterprise"]["state"], "operational")
        self.assertEqual(output["components"]["signup"]["state"], "operational")
        self.assertEqual(output["daily"]["2026-11-04"]["enterprise"], {"ok": 1, "fail": 0})
        self.assertNotIn("requests", output["daily"]["2026-11-04"])
        self.assertEqual(output["first_checked_at"], snapshot["first_checked_at"])

    def test_manual_reporting_cannot_target_retired_component(self):
        with self.assertRaises(ValueError):
            monitor.manual({"incidents": [], "maintenance": []}, "incident_open",
                           "requests", "Legacy incident", "", "", "",
                           dt.datetime.now(dt.timezone.utc))

    def test_missing_schedule_report_is_not_classified_as_endpoint_outage(self):
        previous = "2026-11-17T07:51:11Z"
        instant = dt.datetime(2026, 11, 17, 17, 6, 5, tzinfo=dt.timezone.utc)
        data = {
            "schema": 1, "checked_at": previous,
            "first_checked_at": "2026-10-24T03:34:31Z",
            "components": {}, "daily": {}, "incidents": [], "maintenance": []
        }
        out = monitor.monitor(data, {key: True for key in monitor.TARGETS}, instant)
        self.assertEqual(out["checked_at"], "2026-11-17T17:06:05Z")
        self.assertTrue(all(out["components"][k]["state"] == "operational"
                            for k in monitor.TARGETS))
        self.assertEqual(len(out["incidents"]), 1)
        incident = out["incidents"][0]
        self.assertEqual(incident["component"], "monitoring")
        self.assertEqual(incident["status"], "identified")
        self.assertIn("not evidence", incident["detail"])
        self.assertEqual(incident["updates"][0]["at"], out["checked_at"])

    def test_quick_monitor_cycles_do_not_create_gap_incidents(self):
        data = {
            "schema": 1, "checked_at": "2026-11-18T13:20:00Z",
            "first_checked_at": "2026-10-24T03:34:31Z",
            "components": {}, "daily": {}, "incidents": [], "maintenance": []
        }
        instant = dt.datetime(2026, 11, 18, 13, 27, 0, tzinfo=dt.timezone.utc)
        monitor.monitor(data, {key: True for key in monitor.TARGETS}, instant)
        self.assertEqual(data["incidents"], [])

    def test_existing_open_monitoring_incident_is_updated_not_duplicated(self):
        incident = {"id": "existing", "component": "monitoring", "origin": "monitoring-schedule",
                    "started_at": "2026-11-16T08:36:31Z", "ended_at": None,
                    "status": "identified", "title": "Status monitoring delayed",
                    "detail": "Earlier gap", "updates": []}
        data = {
            "schema": 1, "checked_at": "2026-11-17T07:51:11Z",
            "first_checked_at": "2026-10-24T03:34:31Z",
            "components": {}, "daily": {}, "incidents": [incident], "maintenance": []
        }
        instant = dt.datetime(2026, 11, 17, 17, 6, 5, tzinfo=dt.timezone.utc)
        monitor.monitor(data, {key: True for key in monitor.TARGETS}, instant)
        self.assertEqual(len(data["incidents"]), 1)
        self.assertEqual(data["incidents"][0]["id"], "existing")
        self.assertEqual(len(data["incidents"][0]["updates"]), 1)



if __name__ == "__main__":
    unittest.main()

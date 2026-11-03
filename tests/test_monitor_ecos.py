"""Regression tests for current ECOS public Request Access page reachability."""
import unittest
from unittest.mock import patch
import monitor

class FakeResponse:
    def __init__(self, html, status=200, content_type="text/html; charset=utf-8"):
        self.body = html.encode("utf-8")
        self.status = status
        self.headers = {"content-type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.body[:limit]

class ECOSPublicStatusTests(unittest.TestCase):
    def probe(self, html, status=200, content_type="text/html; charset=utf-8"):
        with patch.object(monitor.urllib.request, "urlopen",
                          return_value=FakeResponse(html, status, content_type)):
            with patch.object(monitor.time, "sleep"):
                return monitor.check_http(*monitor.TARGETS["requests"])

    def test_access_page_is_verified_by_form_not_marketing_copy(self):
        page = '<html><title>Get ECOS Access</title><form id="request-form" novalidate></form></html>'
        self.assertTrue(self.probe(page))

    def test_previous_marketing_copy_no_longer_counts_as_a_live_form(self):
        old = "<html><title>Request enterprise access</title><p>ACCESS & EVALUATION</p></html>"
        self.assertFalse(self.probe(old))

    def test_generic_healthy_homepage_does_not_count(self):
        self.assertFalse(self.probe("<html><title>Energy Control OS</title><p>Welcome</p></html>"))

    def test_cloudflare_challenge_cannot_count_as_success(self):
        self.assertFalse(self.probe("<html><title>Just a moment...</title></html>"))

    def test_non_success_http_and_non_html_are_rejected(self):
        form = '<form id="request-form"></form>'
        self.assertFalse(self.probe(form, status=503))
        self.assertFalse(self.probe(form, content_type="text/plain"))

    def test_http_exception_is_not_success(self):
        with patch.object(monitor.urllib.request, "urlopen",
                          side_effect=monitor.urllib.error.URLError("upstream unavailable")):
            with patch.object(monitor.time, "sleep"):
                self.assertFalse(monitor.check_http(*monitor.TARGETS["requests"]))

    def test_public_page_probe_is_specific(self):
        self.assertEqual(monitor.TARGETS["requests"][0],
                         "https://www.energycontrolos.com/request-access/")
        self.assertEqual(monitor.TARGETS["requests"][1], ('id="request-form"',))

if __name__ == "__main__":
    unittest.main()

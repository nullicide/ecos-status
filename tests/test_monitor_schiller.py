"""Regression checks for the independent 115 Schiller reachability probe."""
import io
import unittest
from unittest.mock import patch
import monitor_schiller as monitor


class FakeResponse:
    status = 200
    headers = {"content-type": "text/html; charset=utf-8"}

    def __init__(self, html):
        self.html = html

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.html.encode("utf-8")[:limit]


class OwnerProbeTests(unittest.TestCase):
    def check_html(self, html):
        with patch.object(monitor.urllib.request, "urlopen",
                          return_value=FakeResponse(html)):
            with patch.object(monitor.time, "sleep"):
                return monitor.probe(("owner", monitor.TARGETS["owner"]))

    def test_current_owner_portal_title_and_description(self):
        actual_owner_header = (
            '<title>Property Operations · 115 Schiller</title>'
            '<meta name="description" '
            'content="Secure owner and property operations portal for 115 Schiller.">'
        )
        self.assertEqual(self.check_html(actual_owner_header), ("owner", True))

    def test_title_can_change_without_declaring_outage(self):
        rebranded = (
            '<title>Owner dashboard · 115 Schiller</title>'
            '<meta name="description" '
            'content="Secure owner and property operations portal for 115 Schiller.">'
        )
        self.assertEqual(self.check_html(rebranded), ("owner", True))

    def test_unrelated_html_does_not_pass_just_because_brand_exists(self):
        with patch("builtins.print"):
            self.assertEqual(
                self.check_html('<title>115 Schiller · Guttenberg, Iowa</title>'),
                ("owner", False)
            )

    def test_http_error_does_not_pass(self):
        with patch.object(monitor.urllib.request, "urlopen",
                          side_effect=monitor.urllib.error.URLError("probe unavailable")):
            with patch.object(monitor.time, "sleep"):
                with patch("builtins.print"):
                    self.assertEqual(
                        monitor.probe(("owner", monitor.TARGETS["owner"])),
                        ("owner", False)
                    )

    def test_public_page_markers_remain_distinct(self):
        self.assertEqual(len(monitor.TARGETS), 5)
        self.assertEqual(
            len({marker for _, marker in monitor.TARGETS.values()}), 5
        )


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch
from scripts import verify_production as v

class PublicationTests(unittest.TestCase):
    def test_mirror_failure_does_not_skip_rss(self):
        with patch.object(v,"verify_shell") as shell, patch.object(v,"verify_report",side_effect=[None,OSError("mirror unavailable")]) as report, patch.object(v,"verify_rss") as rss:
            with self.assertRaisesRegex(RuntimeError,"mirror report"):
                v.verify()
            self.assertEqual(shell.call_count,2)
            self.assertEqual(report.call_count,2)
            self.assertEqual(rss.call_count,2)
    def test_invalid_rss_fails(self):
        with patch.object(v,"get",return_value="<html/>"):
            with self.assertRaises(AssertionError):
                v.verify_rss("https://example.test/")
    def test_all_success(self):
        with patch.object(v,"verify_shell"), patch.object(v,"verify_report"), patch.object(v,"verify_rss"):
            v.verify()

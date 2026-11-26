import unittest
from unittest.mock import Mock
from scripts import synthetic_workspace as s

class SyntheticWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.env={"ECOS_SYNTHETIC_ENABLED":"true","ECOS_SYNTHETIC_APP_COOKIE":"session=fixture","ECOS_SYNTHETIC_ORG_ID":"fixture-org","ECOS_SYNTHETIC_PROJECT_ID":"fixture-project","ECOS_SYNTHETIC_EMAIL":"fixture@example.test"}
        self.data={"ok":True,"actor":{"org_id":"fixture-org","display":"fixture@example.test","role":"member"},"projects":[{"id":"fixture-project","role":"viewer"}],"canCreateProject":False}
    def test_inactive(self):
        transport=Mock()
        self.assertEqual(s.run({},transport),"inactive")
        transport.assert_not_called()
    def test_missing_configuration(self):
        transport=Mock()
        self.assertEqual(s.run({"ECOS_SYNTHETIC_ENABLED":"true"},transport),"configuration_required")
        transport.assert_not_called()
    def test_fixture_success(self):
        self.assertEqual(s.run(self.env,Mock(return_value=self.data)),"passed")
    def test_wrong_workspace(self):
        self.data["projects"].append({"id":"other","role":"viewer"})
        self.assertEqual(s.run(self.env,Mock(return_value=self.data)),"failed")
    def test_admin(self):
        self.data["actor"]["role"]="admin"
        self.assertEqual(s.run(self.env,Mock(return_value=self.data)),"failed")
    def test_transport_failure(self):
        self.assertEqual(s.run(self.env,Mock(side_effect=OSError("private"))),"failed")
    def test_injected_header(self):
        self.env["ECOS_SYNTHETIC_APP_COOKIE"]="session=abc\r\nInjected: yes"
        transport=Mock()
        self.assertEqual(s.run(self.env,transport),"configuration_required")
        transport.assert_not_called()

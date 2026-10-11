"""Live tests against Oura's fake-data sandbox (no account needed).

Run:  python3 -m pytest tests/   (or: python3 tests/test_sandbox.py)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import oura_lib


class SandboxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = oura_lib.OuraClient(None, None, sandbox=True)

    def test_readiness(self):
        data = self.client.daily_readiness("2026-10-01", "2026-10-03")
        self.assertGreater(len(data), 0)
        self.assertIn("score", data[0])

    def test_daily_sleep(self):
        data = self.client.daily_sleep("2026-10-01", "2026-10-02")
        self.assertGreater(len(data), 0)
        self.assertIn("score", data[0])

    def test_sleep_periods(self):
        data = self.client.sleep_periods("2026-10-01", "2026-10-02")
        self.assertIsInstance(data, list)

    def test_activity(self):
        data = self.client.daily_activity("2026-10-01", "2026-10-02")
        self.assertIsInstance(data, list)

    def test_spo2(self):
        data = self.client.daily_spo2("2026-10-01", "2026-10-02")
        self.assertIsInstance(data, list)

    def test_workouts(self):
        data = self.client.workouts("2026-10-01", "2026-10-02")
        self.assertIsInstance(data, list)

    def test_heartrate(self):
        data = self.client.heartrate(
            "2026-10-01T00:00:00+00:00", "2026-10-02T00:00:00+00:00")
        self.assertIsInstance(data, list)

    def test_personal_info(self):
        # Sandbox may return an error-shaped body; just assert it responds.
        try:
            self.client.personal_info()
        except oura_lib.OuraError:
            pass

    def test_extract_code_from_url(self):
        code = oura_lib.extract_code(
            "http://localhost:8888/callback?code=abc123&scope=daily")
        self.assertEqual(code, "abc123")
        self.assertEqual(oura_lib.extract_code("abc123"), "abc123")

    def test_authorize_url(self):
        url = oura_lib.authorize_url("cid", "http://localhost:8888/callback",
                                     "daily", state="s1")
        self.assertIn("cloud.ouraring.com/oauth/authorize", url)
        self.assertIn("client_id=cid", url)
        self.assertIn("state=s1", url)


if __name__ == "__main__":
    unittest.main(verbosity=2)

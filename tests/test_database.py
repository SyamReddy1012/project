import json
import os
import unittest
import urllib.error
import urllib.request
import threading
import time
from http.server import ThreadingHTTPServer

from mptracker.config import get_settings
from mptracker.db import connect, DatabaseError, load_cases_from_db, load_teams_from_db
from mptracker.web import MPTrackerHandler, _create_session_token, _verify_session_token


class DatabaseAndSecurityTests(unittest.TestCase):
    def test_database_url_configured(self):
        settings = get_settings()
        self.assertTrue(bool(settings.database_url))
        self.assertIn("sslmode=require", settings.database_url)

    def test_database_connectivity_and_vector_extension(self):
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                self.assertEqual(cur.fetchone()[0], 1)
                cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
                row = cur.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "0.8.7")

    def test_neon_cases_and_teams_loaded(self):
        cases = load_cases_from_db()
        self.assertIsNotNone(cases)
        self.assertGreaterEqual(len(cases), 13)

        teams = load_teams_from_db()
        self.assertIsNotNone(teams)
        self.assertGreaterEqual(len(teams), 9)

    def test_token_creation_and_verification(self):
        token = _create_session_token("admin", "admin")
        valid, role, username = _verify_session_token(token)
        self.assertTrue(valid)
        self.assertEqual(role, "admin")
        self.assertEqual(username, "admin")

        ngo_token = _create_session_token("ngo", "test_ngo")
        valid, role, username = _verify_session_token(ngo_token)
        self.assertTrue(valid)
        self.assertEqual(role, "ngo")
        self.assertEqual(username, "test_ngo")

        # Tampered token fails
        invalid, _, _ = _verify_session_token(token + "tampered")
        self.assertFalse(invalid)

    def test_health_endpoint_and_sanitization(self):
        server = ThreadingHTTPServer(("127.0.0.1", 19897), MPTrackerHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.3)

        try:
            # 1. Active health endpoint check
            with urllib.request.urlopen("http://127.0.0.1:19897/health") as res:
                self.assertEqual(res.getcode(), 200)
                data = json.loads(res.read().decode())
                self.assertEqual(data["status"], "healthy")
                self.assertEqual(data["database"], "connected")
                self.assertEqual(data["vector_extension"], "0.8.7")

            # 2. Teams password sanitization check
            with urllib.request.urlopen("http://127.0.0.1:19897/api/teams") as res:
                teams = json.loads(res.read().decode())
                self.assertGreater(len(teams), 0)
                for tm in teams:
                    self.assertNotIn("password", tm)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

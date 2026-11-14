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
from mptracker.web import (
    MPTrackerHandler,
    _create_session_token,
    _verify_session_token,
)


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

    def test_token_creation_and_tamper_detection(self):
        # 1. Valid admin token
        token = _create_session_token("admin", "test_admin")
        valid, claims, err = _verify_session_token(token)
        self.assertTrue(valid)
        self.assertEqual(claims["sub"], "test_admin")
        self.assertEqual(claims["role"], "admin")
        self.assertIn("exp", claims)

        # 2. Tampered token signature fails
        tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
        valid, claims, err = _verify_session_token(tampered)
        self.assertFalse(valid)
        self.assertIn("tampered", err.lower())

        # 3. Tampered payload fails
        parts = token.split(".")
        tampered_payload = "eyJzdWIiOiJoYWNrZXIiLCJyb2xlIjoiYWRtaW4ifQ." + parts[1]
        valid, claims, err = _verify_session_token(tampered_payload)
        self.assertFalse(valid)

        # 4. Malformed tokens fail
        self.assertFalse(_verify_session_token("not-a-token")[0])
        self.assertFalse(_verify_session_token("")[0])
        self.assertFalse(_verify_session_token("part1.part2.part3")[0])

    def test_token_expiration(self):
        # Token with -10 second expiration (already expired)
        expired_token = _create_session_token("admin", "test_admin", expires_in=-10)
        valid, claims, err = _verify_session_token(expired_token)
        self.assertFalse(valid)
        self.assertIn("expired", err.lower())

    def test_admin_credentials_fail_securely_when_missing(self):
        port = 19895
        server = ThreadingHTTPServer(("127.0.0.1", port), MPTrackerHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.3)

        # Temporarily unset admin credentials
        old_user = os.environ.get("ADMIN_USERNAME")
        old_pass = os.environ.get("ADMIN_PASSWORD")
        try:
            if "ADMIN_USERNAME" in os.environ:
                del os.environ["ADMIN_USERNAME"]
            if "ADMIN_PASSWORD" in os.environ:
                del os.environ["ADMIN_PASSWORD"]

            # Admin login attempt must fail with 503 Service Unavailable (fail-secure)
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/login",
                data=json.dumps({"role": "admin", "username": "admin", "password": "any"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req)
            self.assertEqual(cm.exception.code, 503)
        finally:
            if old_user:
                os.environ["ADMIN_USERNAME"] = old_user
            if old_pass:
                os.environ["ADMIN_PASSWORD"] = old_pass
            server.shutdown()
            server.server_close()

    def test_protected_endpoints_require_bearer_token(self):
        port = 19894
        server = ThreadingHTTPServer(("127.0.0.1", port), MPTrackerHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.3)

        try:
            # 1. Request with client-controlled X-User-Role: admin but NO Bearer token -> MUST return 401 Unauthorized
            req_spoof = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/cases/add",
                data=json.dumps({"name": "Spoofed Case"}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-User-Role": "admin",
                },
            )
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req_spoof)
            self.assertEqual(cm.exception.code, 401)

            # 2. Request with tampered Bearer token -> MUST return 401 Unauthorized
            tampered_token = _create_session_token("admin", "admin") + "tampered"
            req_tampered = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/cases/add",
                data=json.dumps({"name": "Tampered Case"}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {tampered_token}",
                },
            )
            with self.assertRaises(urllib.error.HTTPError) as cm_tamp:
                urllib.request.urlopen(req_tampered)
            self.assertEqual(cm_tamp.exception.code, 401)

            # 3. Request with expired Bearer token -> MUST return 401 Unauthorized
            expired_token = _create_session_token("admin", "admin", expires_in=-10)
            req_expired = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/cases/add",
                data=json.dumps({"name": "Expired Case"}).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {expired_token}",
                },
            )
            with self.assertRaises(urllib.error.HTTPError) as cm_exp:
                urllib.request.urlopen(req_expired)
            self.assertEqual(cm_exp.exception.code, 401)

            # 4. Ordinary user (NGO) token cannot access admin endpoints -> MUST return 403 Forbidden
            ngo_token = _create_session_token("ngo", "test_ngo", team_id=1)
            admin_endpoints = [
                ("/api/cases/add", {"name": "Test"}),
                ("/api/teams/add", {"name": "Test Team"}),
                ("/api/cases/delete", {"id": 9999}),
                ("/api/teams/delete", {"id": 9999}),
                ("/api/cases/allot", {"case_id": 1, "team_id": 1}),
                ("/api/scan", {"camera_location": "CAR STAND", "case_id": 1}),
            ]
            for endpoint, payload in admin_endpoints:
                req_ngo = urllib.request.Request(
                    f"http://127.0.0.1:{port}{endpoint}",
                    data=json.dumps(payload).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {ngo_token}",
                        "X-User-Role": "admin",  # Header must be completely ignored!
                    },
                )
                with self.assertRaises(urllib.error.HTTPError) as cm_ngo:
                    urllib.request.urlopen(req_ngo)
                self.assertEqual(cm_ngo.exception.code, 403, f"Failed on endpoint: {endpoint}")

        finally:
            server.shutdown()
            server.server_close()

    def test_no_passwords_or_secrets_exposed(self):
        port = 19893
        server = ThreadingHTTPServer(("127.0.0.1", port), MPTrackerHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.3)

        try:
            # 1. GET /api/teams must never expose passwords or password hashes
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/teams") as res:
                self.assertEqual(res.getcode(), 200)
                teams = json.loads(res.read().decode())
                self.assertGreater(len(teams), 0)
                for tm in teams:
                    self.assertNotIn("password", tm)

            # 2. GET /health must never expose connection strings, usernames, or passwords
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as res:
                self.assertEqual(res.getcode(), 200)
                data = json.loads(res.read().decode())
                self.assertEqual(data["status"], "healthy")
                self.assertEqual(data["database"], "connected")
                self.assertNotIn("password", json.dumps(data).lower())
                self.assertNotIn("neon.tech", json.dumps(data).lower())

            # 3. POST /api/login for NGO must not expose team password
            login_req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/login",
                data=json.dumps({"role": "ngo", "username": "helping_hands", "password": "ngo123"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(login_req) as res:
                resp_data = json.loads(res.read().decode())
                self.assertEqual(resp_data["status"], "success")
                team_obj = resp_data.get("team", {})
                self.assertNotIn("password", team_obj)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

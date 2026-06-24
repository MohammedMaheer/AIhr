"""Regression checks for production-only routes that must require auth.

Run with:
    python -m unittest tests.test_auth_protection
"""

import unittest

from fastapi.testclient import TestClient

import main


class AuthProtectionTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_sensitive_routes_reject_anonymous_requests(self):
        checks = [
            ("POST", "/api/configure-gcs", {"bucket_name": "example"}),
            ("POST", "/api/enhanced-search", {"query": "python developer"}),
            ("POST", "/api/smart-search-stream", {"query": "python developer"}),
            ("GET", "/api/search-results/1", None),
            ("GET", "/stream-demo", None),
        ]

        for method, path, data in checks:
            with self.subTest(method=method, path=path):
                response = self.client.request(method, path, data=data)
                self.assertEqual(response.status_code, 401)

    def test_cookie_authenticated_unsafe_requests_require_csrf_token(self):
        self.client.cookies.set("session_token", "fake-session")

        response = self.client.post("/api/logout")

        self.assertEqual(response.status_code, 403)
        self.assertIn("CSRF", response.json()["detail"])

    def test_cross_origin_unsafe_requests_are_rejected(self):
        self.client.cookies.set("session_token", "fake-session")
        self.client.cookies.set("csrf_token", "token")

        response = self.client.post(
            "/api/logout",
            headers={
                "origin": "https://evil.example",
                "x-csrf-token": "token",
            },
        )

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()

import json
import socket
import ssl
import unittest
from unittest.mock import patch

from scripts.runtime_health import (
    HealthError,
    check_health,
    check_no_5xx,
    request,
    resolve_public_addresses,
    tls_context,
    validate_origin,
    validate_path,
)

class T(unittest.TestCase):
    def test_private_literals_and_localhost_fail_closed(self):
        for origin in (
            "https://127.0.0.1",
            "https://10.0.0.1",
            "https://169.254.169.254",
            "https://localhost",
        ):
            with self.subTest(origin=origin):
                with self.assertRaises(HealthError):
                    resolve_public_addresses(origin)

    def test_private_dns_resolution_fails(self):
        fake = [(2, 1, 6, "", ("192.168.1.2", 443))]
        with patch("scripts.runtime_health.socket.getaddrinfo", return_value=fake):
            with self.assertRaises(HealthError):
                resolve_public_addresses("https://example.test")

    def test_mixed_public_private_dns_fails_closed(self):
        mixed = [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("10.0.0.2", 443)),
        ]
        with patch("scripts.runtime_health.socket.getaddrinfo", return_value=mixed):
            with self.assertRaises(HealthError):
                resolve_public_addresses("https://example.test")

    def test_origin_rejects_non_443_paths_and_bad_ports(self):
        for origin in (
            "https://example.com:8443",
            "https://example.com:bad",
            "https://example.com/path",
            "http://example.com",
        ):
            with self.subTest(origin=origin):
                with self.assertRaises(HealthError):
                    validate_origin(origin)

    def test_tls_context_requires_tls_1_2_and_certificate_validation(self):
        context = tls_context()
        self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_path_rejects_query_fragment_and_traversal(self):
        for path in (
            "/health?x=1",
            "/a/../health",
            "//evil.example/x",
            "/health#x",
        ):
            with self.subTest(path=path):
                with self.assertRaises(HealthError):
                    validate_path(path)

    def test_request_and_health_cover_success_and_failures(self):
        sha = "a" * 40
        healthy = json.dumps({
            "status": "ok",
            "version": "1.2.3",
            "release_sha": sha,
            "schema_up_to_date": True,
        }).encode("utf-8")

        with patch(
            "scripts.runtime_health.request",
            return_value=(200, "application/json", healthy),
        ):
            payload = check_health(
                "https://example.com",
                "/health",
                "1.2.3",
                sha,
                require_schema=True,
            )
        self.assertEqual(payload["status"], "ok")

        invalid_responses = (
            (503, "application/json", healthy),
            (200, "text/html", healthy),
            (200, "application/json", b"not-json"),
            (
                200,
                "application/json",
                json.dumps({
                    "status": "ok",
                    "version": "9.9.9",
                    "release_sha": sha,
                    "schema_up_to_date": True,
                }).encode(),
            ),
            (
                200,
                "application/json",
                json.dumps({
                    "status": "ok",
                    "version": "1.2.3",
                    "release_sha": sha,
                    "schema_up_to_date": False,
                }).encode(),
            ),
        )
        for response in invalid_responses:
            with self.subTest(response=response[:2]):
                with patch("scripts.runtime_health.request", return_value=response):
                    with self.assertRaises(HealthError):
                        check_health(
                            "https://example.com",
                            "/health",
                            "1.2.3",
                            sha,
                            require_schema=True,
                        )

        with patch(
            "scripts.runtime_health.request",
            side_effect=[
                (204, "text/plain", b""),
                (404, "text/plain", b""),
            ],
        ):
            self.assertEqual(
                check_no_5xx(
                    "https://example.com",
                    ["/ready", "/missing"],
                ),
                {"/ready": 204, "/missing": 404},
            )
        with patch(
            "scripts.runtime_health.request",
            return_value=(503, "text/plain", b""),
        ):
            with self.assertRaises(HealthError):
                check_no_5xx("https://example.com", ["/ready"])

        with self.assertRaises(HealthError):
            request("https://example.com", "/health", 0)
        with (
            patch(
                "scripts.runtime_health.resolve_public_addresses",
                return_value=("example.com", ["93.184.216.34"]),
            ),
            patch("scripts.runtime_health.tls_context"),
            patch(
                "scripts.runtime_health.socket.create_connection",
                side_effect=OSError("offline"),
            ),
        ):
            with self.assertRaises(HealthError):
                request("https://example.com", "/health", 1)

        for origin in (None, "https://" + "a" * 2050):
            with self.subTest(origin=origin):
                with self.assertRaises(HealthError):
                    validate_origin(origin)  # type: ignore[arg-type]
        for path in ("", "relative", "/health\r\nInjected"):
            with self.subTest(path=path):
                with self.assertRaises(HealthError):
                    validate_path(path)

        with patch(
            "scripts.runtime_health.socket.getaddrinfo",
            side_effect=socket.gaierror("dns"),
        ):
            with self.assertRaises(HealthError):
                resolve_public_addresses("https://example.test")
        with patch(
            "scripts.runtime_health.socket.getaddrinfo",
            return_value=[],
        ):
            with self.assertRaises(HealthError):
                resolve_public_addresses("https://example.test")
        with patch(
            "scripts.runtime_health.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("not-an-ip", 443))],
        ):
            with self.assertRaises(HealthError):
                resolve_public_addresses("https://example.test")

        with self.assertRaises(HealthError):
            check_health(
                "https://example.com",
                "/health",
                "bad-version",
                sha,
                require_schema=False,
            )
        not_ok = json.dumps({
            "status": "degraded",
            "version": "1.2.3",
            "release_sha": sha,
        }).encode()
        with patch(
            "scripts.runtime_health.request",
            return_value=(200, "application/json", not_ok),
        ):
            with self.assertRaises(HealthError):
                check_health(
                    "https://example.com",
                    "/health",
                    "1.2.3",
                    sha,
                    require_schema=False,
                )
        with self.assertRaises(HealthError):
            check_no_5xx("https://example.com", [])

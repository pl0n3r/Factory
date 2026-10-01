import json
import ssl
import unittest
from unittest.mock import MagicMock, patch

from scripts.runtime_health import (
    MAX_BYTES,
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
        class SocketContext:
            def __init__(self, value):
                self.value = value

            def __enter__(self):
                return self.value

            def __exit__(self, *_args):
                return False

        raw_socket = object()
        tls_socket = MagicMock()
        tls_context_mock = MagicMock()
        tls_context_mock.wrap_socket.return_value = SocketContext(tls_socket)
        response = MagicMock()
        response.status = 200
        response.headers.get_content_type.return_value = "application/json"
        response.read.return_value = b'{"status":"ok"}'

        with patch(
            "scripts.runtime_health.resolve_public_addresses",
            return_value=("example.com", ["93.184.216.34"]),
        ), patch("scripts.runtime_health.tls_context", return_value=tls_context_mock), patch(
            "scripts.runtime_health.socket.create_connection",
            return_value=SocketContext(raw_socket),
        ), patch("scripts.runtime_health.http.client.HTTPResponse", return_value=response):
            status, content_type, body = request("https://example.com", "/health", 1)

        self.assertEqual((status, content_type, body), (200, "application/json", b'{"status":"ok"}'))
        tls_context_mock.wrap_socket.assert_called_once_with(raw_socket, server_hostname="example.com")
        tls_socket.settimeout.assert_called_once_with(1)
        self.assertIn(b"GET /health HTTP/1.1", tls_socket.sendall.call_args.args[0])

        with patch(
            "scripts.runtime_health.resolve_public_addresses",
            return_value=("example.com", ["93.184.216.34"]),
        ), patch("scripts.runtime_health.tls_context", return_value=tls_context_mock), patch(
            "scripts.runtime_health.socket.create_connection",
            side_effect=OSError("offline"),
        ):
            with self.assertRaises(HealthError):
                request("https://example.com", "/health", 1)

        response.read.return_value = b"x" * (MAX_BYTES + 1)
        with patch(
            "scripts.runtime_health.resolve_public_addresses",
            return_value=("example.com", ["93.184.216.34"]),
        ), patch("scripts.runtime_health.tls_context", return_value=tls_context_mock), patch(
            "scripts.runtime_health.socket.create_connection",
            return_value=SocketContext(raw_socket),
        ), patch("scripts.runtime_health.http.client.HTTPResponse", return_value=response):
            with self.assertRaises(HealthError):
                request("https://example.com", "/health", 1)

        sha = "a" * 40
        good_payload = {
            "status": "ok",
            "version": "1.2.3",
            "release_sha": sha,
            "schema_up_to_date": True,
        }
        with patch(
            "scripts.runtime_health.request",
            return_value=(200, "application/json", json.dumps(good_payload).encode()),
        ):
            self.assertEqual(
                check_health(
                    "https://example.com",
                    "/health",
                    "1.2.3",
                    sha,
                    require_schema=True,
                ),
                good_payload,
            )

        bad_health_responses = (
            (503, "application/json", b"{}"),
            (200, "text/html", b"{}"),
            (200, "application/json", b"{"),
            (200, "application/json", b'{"status":"down"}'),
            (
                200,
                "application/json",
                json.dumps({**good_payload, "version": "9.9.9"}).encode(),
            ),
            (
                200,
                "application/json",
                json.dumps({**good_payload, "schema_up_to_date": False}).encode(),
            ),
        )
        for fake_response in bad_health_responses:
            with self.subTest(fake_response=fake_response[:2]):
                with patch("scripts.runtime_health.request", return_value=fake_response):
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
            side_effect=[(200, "text/html", b""), (404, "text/html", b"")],
        ):
            self.assertEqual(
                check_no_5xx("https://example.com", ["/", "/missing"]),
                {"/": 200, "/missing": 404},
            )

        with patch(
            "scripts.runtime_health.request",
            return_value=(500, "text/html", b""),
        ):
            with self.assertRaises(HealthError):
                check_no_5xx("https://example.com", ["/admin"])

        for invalid_paths in ([], ["/"] * 21, "not-a-list"):
            with self.subTest(invalid_paths=invalid_paths):
                with self.assertRaises(HealthError):
                    check_no_5xx("https://example.com", invalid_paths)

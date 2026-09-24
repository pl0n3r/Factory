import unittest
from unittest.mock import patch
from scripts.runtime_health import HealthError, resolve_public_addresses, validate_origin, validate_path

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

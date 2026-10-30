"""Regresiones DNS/TLS sintéticas: sin conexiones externas ni modificación de red."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import socket
import ssl
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts.check_dns_tls import (
    ConfigError, PRODUCTS, check_product, dns_lookup, init_config, load_config,
    run, tls_observe, validate_domain,
)

NOW = datetime(2026, 10, 30, 18, 0, tzinfo=timezone.utc)
PUBLIC_IP = "93.184.216.34"


class CheckDnsTlsTests(unittest.TestCase):
    def test_criterio_principal(self):
        """DNS, TLS válido/vencido/por vencer/hostname ajeno y UNKNOWN por producto."""
        valid = {"status": "VALID", "valid": True, "expires_at_utc": "2027-01-01T00:00:00+00:00", "days_remaining": 62.0}
        soon = {"status": "EXPIRING_SOON", "valid": True, "expires_at_utc": "2026-11-01T00:00:00+00:00", "days_remaining": 1.25}
        expired = {"status": "EXPIRED", "valid": False, "expires_at_utc": None, "days_remaining": None}
        wrong = {"status": "WRONG_DOMAIN", "valid": False, "expires_at_utc": None, "days_remaining": None}
        expected = ["VALID", "EXPIRING_SOON", "EXPIRED", "WRONG_DOMAIN"]
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            config = base / "dominios.json"
            init_config(config)
            original = json.loads(config.read_text())
            self.assertEqual(set(original["domains"]), set(PRODUCTS))
            self.assertTrue(all(v is None for v in original["domains"].values()))
            original["domains"] = {
                "Condor": "condor.example", "GrindFlow": "grindflow.example",
                "brvtal": "brvtal.example", "ControlBot": "controlbot.example",
            }
            config.write_text(json.dumps(original), encoding="utf-8")
            with patch("scripts.check_dns_tls.dns_lookup", return_value=[PUBLIC_IP]), patch(
                "scripts.check_dns_tls.tls_observe", side_effect=[valid, soon, expired, wrong],
            ):
                # Uso explícito de inyección evita modificar DNS y certificados reales.
                results = [check_product(product, domain, NOW,
                    resolver=lambda host: [PUBLIC_IP],
                    tls_probe=lambda host, addr, now, n=i: [valid, soon, expired, wrong][n])
                    for i, (product, domain) in enumerate(load_config(config).items())]
            self.assertEqual(expected, [result["status"] for result in results])
            self.assertEqual([PUBLIC_IP], results[0]["dns"]["addresses"])
            self.assertEqual("2026-10-30 01:00:00 PM -05", results[0]["checked_at_colombia"])
            self.assertIsNone(results[3]["tls"]["expires_at_utc"])
            self.assertFalse(results[3]["tls"]["valid"])
            # El reporte realmente genera un JSON independiente para cada producto.
            with patch("scripts.check_dns_tls.dns_lookup", return_value=[PUBLIC_IP]), patch(
                "scripts.check_dns_tls.tls_observe", return_value=valid,
            ):
                output = run(config, base / "reportes", NOW)
            self.assertEqual(len(PRODUCTS), len(output))
            for product in PRODUCTS:
                report = json.loads((base / "reportes" / f"{product.lower()}.json").read_text())
                self.assertEqual(product, report["product"])
                self.assertEqual("VALID", report["status"])

    def test_missing_config_reports_unknown_without_network(self):
        with tempfile.TemporaryDirectory() as folder, patch(
            "scripts.check_dns_tls.socket.getaddrinfo", side_effect=AssertionError("DNS inesperado")
        ):
            output = run(Path(folder) / "inexistente.json", Path(folder) / "reports", NOW)
            self.assertEqual(["UNKNOWN"] * len(PRODUCTS), [x["status"] for x in output])

    def test_rejects_private_and_mixed_dns_fail_closed(self):
        for address in ("127.0.0.1", "10.0.0.3", "192.168.0.3", "169.254.169.254", "::1"):
            infos = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]
            with self.subTest(address=address), patch("scripts.check_dns_tls.socket.getaddrinfo", return_value=infos):
                with self.assertRaises(ValueError):
                    dns_lookup("safe.example")
        mixed = [(socket.AF_INET, 1, 6, "", (PUBLIC_IP, 443)),
                 (socket.AF_INET, 1, 6, "", ("10.0.0.7", 443))]
        with patch("scripts.check_dns_tls.socket.getaddrinfo", return_value=mixed):
            result = check_product("Condor", "safe.example", NOW)
            self.assertEqual("UNKNOWN", result["status"])
            self.assertEqual([], result["dns"]["addresses"])

    def test_rejects_unsafe_domain_config_and_never_overwrites(self):
        for bad in ("localhost", "localhost.local", "10.0.0.1", "https://foo.example", "evil.example:8443",
                    "user@evil.example", "foo.example/../secret", "foo..example", "-foo.example", " foo.example"):
            with self.subTest(bad=bad), self.assertRaises(ConfigError):
                validate_domain(bad)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "domains.json"
            init_config(path)
            with self.assertRaises(FileExistsError):
                init_config(path)
            payload = json.loads(path.read_text())
            payload["domains"]["UnknownProject"] = "unknown.example"
            path.write_text(json.dumps(payload))
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_dns_timeout_and_inconsistent_tls_never_claim_valid(self):
        missing = check_product("Condor", "valid.example", NOW, resolver=lambda _: (_ for _ in ()).throw(socket.gaierror()))
        self.assertEqual("UNKNOWN", missing["status"])
        status = [
            {"status": "VALID", "valid": True, "days_remaining": 65, "expires_at_utc": "2027-01-01T00:00:00Z"},
            {"status": "UNKNOWN", "valid": False, "days_remaining": None, "expires_at_utc": None},
        ]
        observed = check_product("Condor", "valid.example", NOW, resolver=lambda _: [PUBLIC_IP, "8.8.8.8"],
                tls_probe=lambda h, ip, now: status[0] if ip == PUBLIC_IP else status[1])
        self.assertEqual("UNKNOWN", observed["status"])

    def test_tls_verified_expiration_and_cert_error_classification(self):
        expiry = (NOW + timedelta(days=10)).strftime("%b %d %H:%M:%S %Y GMT")
        context = MagicMock()
        context.wrap_socket.return_value.__enter__.return_value.getpeercert.return_value = {"notAfter": expiry}
        with patch("scripts.check_dns_tls.ssl.create_default_context", return_value=context), patch(
            "scripts.check_dns_tls.socket.create_connection"
        ) as conn:
            result = tls_observe("service.example", PUBLIC_IP, NOW)
        self.assertEqual("EXPIRING_SOON", result["status"])
        self.assertEqual(10.0, result["days_remaining"])
        self.assertTrue(context.check_hostname)
        self.assertEqual(ssl.CERT_REQUIRED, context.verify_mode)
        conn.assert_called_once_with((PUBLIC_IP, 443), timeout=5.0)
        context.wrap_socket.assert_called_once()
        self.assertEqual("service.example", context.wrap_socket.call_args.kwargs["server_hostname"])
        for detail, expected in (("certificate has expired", "EXPIRED"),
                                 ("Hostname mismatch, certificate is not valid for 'service.example'", "WRONG_DOMAIN"),
                                 ("self-signed certificate", "INVALID_CERTIFICATE")):
            failure = ssl.SSLCertVerificationError(detail)
            with patch("scripts.check_dns_tls.ssl.create_default_context") as ctx, patch(
                "scripts.check_dns_tls.socket.create_connection", side_effect=failure,
            ):
                result = tls_observe("service.example", PUBLIC_IP, NOW)
            self.assertEqual(expected, result["status"])
            self.assertFalse(result["valid"])


    def test_tls_probe_failures_are_reported_as_unknown(self):
        def offline_failure(_host, _address, _now):
            raise OSError("temporary connection failure")

        report = check_product("Condor", "example.org", NOW,
                               resolver=lambda _host: [PUBLIC_IP], tls_probe=offline_failure)
        self.assertEqual("RESOLVED", report["dns"]["status"])
        self.assertEqual("UNKNOWN", report["tls"]["status"])
        self.assertEqual("UNKNOWN", report["status"])

        for response in (None, "unverified", {"status": "VALID", "valid": True},
                         {"status": "VALID", "valid": True, "days_remaining": -1,
                          "expires_at_utc": "2027-01-01T00:00:00Z"}):
            with self.subTest(response=response):
                observed = check_product("Condor", "example.org", NOW,
                    resolver=lambda _host: [PUBLIC_IP],
                    tls_probe=lambda _host, _addr, _now: response)
                self.assertEqual("UNKNOWN", observed["status"])

    def test_no_certificate_authority_available_is_unknown(self):
        with patch("scripts.check_dns_tls.ssl.create_default_context",
                   side_effect=OSError("CA unavailable")):
            observation = tls_observe("example.org", PUBLIC_IP, NOW)
        self.assertEqual("UNKNOWN", observation["status"])
        self.assertFalse(observation["valid"])


    def test_tls_helper_never_opens_private_address_or_unsafe_hostname(self):
        for ip in ("127.0.0.1", "10.5.6.7", "169.254.169.254",
                   "192.168.1.1", "::1", "203.0.113.3"):
            with self.subTest(ip=ip), patch(
                "scripts.check_dns_tls.socket.create_connection",
                side_effect=AssertionError("private socket opened"),
            ) as connect:
                result = tls_observe("example.org", ip, NOW)
                self.assertEqual("UNKNOWN", result["status"])
                connect.assert_not_called()

        with patch("scripts.check_dns_tls.socket.create_connection") as connect:
            result = tls_observe("localhost", PUBLIC_IP, NOW)
            self.assertEqual("UNKNOWN", result["status"])
            connect.assert_not_called()

        with patch("scripts.check_dns_tls.socket.getaddrinfo") as resolve:
            with self.assertRaises(ConfigError):
                dns_lookup("localhost.local")
            resolve.assert_not_called()


if __name__ == "__main__":
    unittest.main()

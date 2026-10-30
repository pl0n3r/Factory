#!/usr/bin/env python3
"""Auditoría DNS/TLS de solo lectura con reporte JSON independiente por producto.

Configuración editable, nunca incluida con dominios supuestos:
    python3 scripts/check_dns_tls.py --init-config /ruta/dominios.json
    # editar las entradas null del JSON para cada producto
    python3 scripts/check_dns_tls.py --config /ruta/dominios.json --output-dir /ruta/reportes

No modifica zonas DNS, certificados, servidores ni cuentas. Exige destinos públicos
para evitar usar la auditoría como sonda de redes internas.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl
from typing import Callable
from zoneinfo import ZoneInfo

PRODUCTS = ("Condor", "GrindFlow", "brvtal", "ControlBot")
COLOMBIA = ZoneInfo("America/Bogota")
DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
MAX_CONFIG_BYTES = 32 * 1024
MAX_ADDRESSES = 16
SOCKET_TIMEOUT = 5.0
EXPIRY_WARNING_DAYS = 30


class ConfigError(ValueError):
    """Configuración inválida; no se deben lanzar conexiones de red."""


def validate_domain(value: object) -> str:
    if not isinstance(value, str) or not (1 <= len(value) <= 253):
        raise ConfigError("Dominio vacío o demasiado largo")
    if value != value.strip() or any(char in value for char in ":/@\\?# "):
        raise ConfigError("Se requiere exclusivamente un nombre DNS, no URL ni puerto")
    try:
        host = value.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ConfigError("Dominio IDNA inválido") from exc
    if ("." not in host or host.endswith((".local", ".localhost", ".internal"))
            or not all(DOMAIN_LABEL.fullmatch(part) for part in host.split("."))):
        raise ConfigError("Dominio DNS público inválido")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    raise ConfigError("No se permiten IP literales: requiere nombre DNS")


def load_config(path: Path) -> dict[str, str | None]:
    try:
        if path.stat().st_size > MAX_CONFIG_BYTES:
            raise ConfigError("Archivo de configuración demasiado grande")
        source = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ConfigError("No fue posible leer configuración JSON válida") from exc
    if not isinstance(source, dict) or set(source) != {"domains"} or not isinstance(source["domains"], dict):
        raise ConfigError("Configuración debe contener exclusivamente 'domains'")
    if set(source["domains"]) != set(PRODUCTS):
        raise ConfigError("Se requieren exactamente Condor, GrindFlow, brvtal y ControlBot")
    result: dict[str, str | None] = {}
    for product in PRODUCTS:
        raw = source["domains"][product]
        result[product] = None if raw is None or raw == "" else validate_domain(raw)
    return result


def init_config(path: Path) -> None:
    # Modo explícito: nunca sobrescribe una configuración ya preparada.
    data = {"domains": {product: None for product in PRODUCTS}}
    with path.open("x", encoding="utf-8") as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
        out.write("\n")


def dns_lookup(host: str) -> list[str]:
    """Resolver A/AAAA y rechazar resultados mixtos o no públicos."""
    info = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses: set[str] = set()
    for entry in info:
        address = ipaddress.ip_address(entry[4][0])
        if not address.is_global:
            raise ValueError("La respuesta DNS contiene una dirección no pública")
        addresses.add(str(address))
        if len(addresses) > MAX_ADDRESSES:
            raise ValueError("Demasiadas direcciones DNS")
    if not addresses:
        raise ValueError("Respuesta DNS sin direcciones")
    return sorted(addresses)


def tls_observe(host: str, address: str, now: datetime) -> dict:
    """Validar cadena y hostname con CA del sistema; fijar la IP DNS elegida."""
    context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    try:
        with socket.create_connection((address, 443), timeout=SOCKET_TIMEOUT) as raw:
            with context.wrap_socket(raw, server_hostname=host) as verified:
                certificate = verified.getpeercert()
        if not isinstance(certificate, dict) or not certificate.get("notAfter"):
            raise ValueError("TLS sin fecha de vencimiento comprobable")
        expires = datetime.fromtimestamp(
            ssl.cert_time_to_seconds(certificate["notAfter"]), tz=timezone.utc,
        )
        days = (expires - now.astimezone(timezone.utc)).total_seconds() / 86400
        status = "EXPIRED" if days <= 0 else "EXPIRING_SOON" if days <= EXPIRY_WARNING_DAYS else "VALID"
        return {"status": status, "valid": days > 0, "expires_at_utc": expires.isoformat(),
                "days_remaining": round(days, 2)}
    except ssl.SSLCertVerificationError as exc:
        # Solo un error explícito de verificación permite clasificación definida.
        detail = str(getattr(exc, "verify_message", exc)).lower()
        if "expired" in detail:
            status = "EXPIRED"
        elif "hostname mismatch" in detail or "doesn't match" in detail or "not valid for" in detail:
            status = "WRONG_DOMAIN"
        else:
            status = "INVALID_CERTIFICATE"
        return {"status": status, "valid": False, "expires_at_utc": None, "days_remaining": None}
    except (OSError, ValueError, ssl.SSLError):
        return {"status": "UNKNOWN", "valid": False, "expires_at_utc": None, "days_remaining": None}


def check_product(product: str, domain: str | None, now: datetime,
                  resolver: Callable[[str], list[str]] | None = None,
                  tls_probe: Callable[[str, str, datetime], dict] | None = None) -> dict:
    stamp = now.astimezone(COLOMBIA)
    report = {
        "product": product,
        "domain": domain,
        "checked_at_colombia": stamp.strftime("%Y-%m-%d %I:%M:%S %p %Z"),
        "checked_at_utc": now.astimezone(timezone.utc).isoformat(),
        "dns": {"status": "UNKNOWN", "addresses": []},
        "tls": {"status": "UNKNOWN", "valid": False, "expires_at_utc": None, "days_remaining": None},
        "status": "UNKNOWN",
    }
    if domain is None:
        return report
    resolver = resolver if resolver is not None else dns_lookup
    tls_probe = tls_probe if tls_probe is not None else tls_observe
    try:
        addresses = resolver(domain)
        if not addresses or len(addresses) > MAX_ADDRESSES or any(
            not ipaddress.ip_address(item).is_global for item in addresses
        ):
            return report
    except (OSError, ValueError, TypeError):
        return report
    addresses = sorted(set(addresses))
    report["dns"] = {"status": "RESOLVED", "addresses": addresses}
    observations = [tls_probe(domain, address, now) for address in addresses]
    statuses = {item.get("status", "UNKNOWN") for item in observations}
    if len(statuses) == 1 and all(item.get("valid") is True for item in observations):
        closest = min(observations, key=lambda t: t["days_remaining"])
        report["tls"] = dict(closest)
        report["status"] = closest["status"]
    elif len(statuses) == 1 and statuses.pop() in {"EXPIRED", "WRONG_DOMAIN", "INVALID_CERTIFICATE"}:
        report["tls"]["status"] = observations[0]["status"]
        report["status"] = observations[0]["status"]
    # Resultados contradictorios o ilegibles -> UNKNOWN en vez de éxito parcial.
    return report


def run(config: Path, output_dir: Path, now: datetime | None = None) -> list[dict]:
    timestamp = now if now is not None else datetime.now(timezone.utc)
    try:
        domains = load_config(config)
    except ConfigError:
        # Un archivo que no se puede leer no autoriza inventar dominios.
        domains = {product: None for product in PRODUCTS}
    reports = [check_product(product, domains[product], timestamp) for product in PRODUCTS]
    output_dir.mkdir(parents=True, exist_ok=True)
    for result in reports:
        destination = output_dir / (result["product"].lower() + ".json")
        destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/dns-tls-domains.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("reportes/dns-tls"))
    parser.add_argument("--init-config", type=Path, metavar="RUTA", help="crear plantilla editable con dominios vacíos")
    args = parser.parse_args()
    if args.init_config is not None:
        init_config(args.init_config)
        return 0
    reports = run(args.config, args.output_dir)
    return 1 if any(item["status"] not in ("VALID", "EXPIRING_SOON") for item in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())

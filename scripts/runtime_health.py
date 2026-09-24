#!/usr/bin/env python3
"""Primitivas HTTPS fail-closed para health/smoke sin redirects ni DNS rebinding."""
from __future__ import annotations

import http.client
import ipaddress
import json
import re
import socket
import ssl
from typing import Any
from urllib.parse import urlsplit

SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA = re.compile(r"^[0-9a-f]{40}$")
HOST = re.compile(r"^[A-Za-z0-9.-]{1,253}$")
MAX_BYTES = 256 * 1024
MAX_PATH = 2048

class HealthError(RuntimeError):
    pass

def validate_origin(origin: str) -> tuple[str, str]:
    if not isinstance(origin, str) or len(origin) > 2048:
        raise HealthError("El dominio debe ser un origen HTTPS acotado.")
    parsed = urlsplit(origin)
    try:
        port = parsed.port
    except ValueError as exc:
        raise HealthError("Puerto HTTPS inválido.") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise HealthError("El dominio debe ser un origen HTTPS:443 sin credenciales ni ruta.")
    try:
        ascii_host = parsed.hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise HealthError("Hostname inválido.") from exc
    if (
        not HOST.fullmatch(ascii_host)
        or ".." in ascii_host
        or ascii_host.startswith(".")
        or ascii_host.endswith(".")
    ):
        raise HealthError("Hostname inválido.")
    return origin.rstrip("/"), ascii_host.lower()

def resolve_public_addresses(origin: str) -> tuple[str, list[str]]:
    _, host = validate_origin(origin)
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise HealthError("El destino HTTP debe ser público.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise HealthError("El destino HTTP debe ser una IP pública.")
        return host, [str(literal)]
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HealthError("No fue posible resolver el dominio público.") from exc
    addresses: list[str] = []
    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0])
        except ValueError as exc:
            raise HealthError("Resolución DNS inválida.") from exc
        if not address.is_global:
            raise HealthError("El dominio resuelve a una red no pública.")
        value = str(address)
        if value not in addresses:
            addresses.append(value)
    if not addresses:
        raise HealthError("El dominio no resolvió direcciones públicas.")
    return host, addresses

def validate_path(path: str) -> str:
    if (
        not isinstance(path, str)
        or not 1 <= len(path) <= MAX_PATH
        or not path.startswith("/")
    ):
        raise HealthError("Ruta HTTP inválida.")
    if any(ch in path for ch in ("\r", "\n", "\x00")):
        raise HealthError("Ruta HTTP inválida.")
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise HealthError("Ruta HTTP no puede contener origen, query ni fragmento.")
    if any(part == ".." for part in parsed.path.split("/")):
        raise HealthError("Ruta HTTP no puede contener traversal.")
    return parsed.path

def request(origin: str, path: str, timeout: float) -> tuple[int, str, bytes]:
    if timeout <= 0 or timeout > 30:
        raise HealthError("Timeout HTTP fuera de rango.")
    safe_path = validate_path(path)
    host, addresses = resolve_public_addresses(origin)
    address = addresses[0]
    context = ssl.create_default_context()
    try:
        with socket.create_connection((address, 443), timeout=timeout) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=host) as tls_socket:
                tls_socket.settimeout(timeout)
                request_bytes = (
                    f"GET {safe_path} HTTP/1.1\r\n"
                    f"Host: {host}\r\n"
                    "Accept: application/json, text/html\r\n"
                    "Cache-Control: no-cache\r\n"
                    "User-Agent: Factory-Observer/1\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")
                tls_socket.sendall(request_bytes)
                response = http.client.HTTPResponse(tls_socket)
                response.begin()
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise HealthError("Respuesta HTTP supera el límite permitido.")
                return response.status, response.headers.get_content_type(), body
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        raise HealthError("No fue posible obtener una respuesta HTTPS válida.") from exc

def check_health(
    origin: str,
    path: str,
    version: str,
    sha: str,
    *,
    require_schema: bool,
    timeout: float = 5.0,
) -> dict[str, Any]:
    if not SEMVER.fullmatch(version) or not SHA.fullmatch(sha):
        raise HealthError("Versión o SHA esperado inválido.")
    status, content_type, body = request(origin, path, timeout)
    if status != 200 or content_type != "application/json":
        raise HealthError("/health no respondió 200 JSON.")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HealthError("/health devolvió JSON inválido.") from exc
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise HealthError("/health no informa status=ok.")
    if payload.get("version") != version or payload.get("release_sha") != sha:
        raise HealthError("/health no coincide con versión/SHA esperados.")
    if require_schema and payload.get("schema_up_to_date") is not True:
        raise HealthError("/health no confirma schema_up_to_date=true.")
    return payload

def check_no_5xx(
    origin: str,
    paths: list[str],
    timeout: float = 5.0,
) -> dict[str, int]:
    if not isinstance(paths, list) or not 1 <= len(paths) <= 20:
        raise HealthError("Lista de superficies inválida.")
    result: dict[str, int] = {}
    for path in paths:
        safe_path = validate_path(path)
        status, _, _ = request(origin, safe_path, timeout)
        if status >= 500:
            raise HealthError(f"{safe_path} respondió HTTP {status}.")
        result[safe_path] = status
    return result

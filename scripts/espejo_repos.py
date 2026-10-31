#!/usr/bin/env python3
"""Espejo versionado de repos públicos; nunca crea cuentas ni restaura GitHub."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import uuid4

REPOSITORIES = (
    "pl0n3r/Factory", "pl0n3r/Condor", "pl0n3r/GrindFlow",
    "pl0n3r/brvtal", "pl0n3r/ControlBot", "pl0n3r/AutoFactory",
    "pl0n3r/FactoryRunner",
)
_FORMAT = 1
_MAX_API = 32 * 1024 * 1024
_MAX_OBJECT = 512 * 1024 * 1024
_SNAPSHOT = re.compile(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9/_\-.]*\Z")


class MirrorError(Exception):
    """Error de contrato; nunca incluye secretos."""


class ObjectStore(Protocol):
    def put(self, key: str, content: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...


class Source(Protocol):
    def capture(self, repo: str) -> tuple[bytes, list[dict], list[dict]]: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise MirrorError("Redirección remota no autorizada.")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: object) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _valid_key(key: str) -> bool:
    return (isinstance(key, str) and len(key) <= 850
            and _KEY.fullmatch(key) is not None
            and all(part not in ("", ".", "..") for part in key.split("/")))


def _file_secret(env_name: str) -> str:
    location = os.environ.get(env_name, "")
    if not location:
        raise MirrorError("Falta archivo privado: " + env_name)
    path = Path(location)
    if path.is_symlink() or not path.is_file():
        raise MirrorError("Archivo privado inválido: " + env_name)
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode) or mode & 0o077:
        raise MirrorError("Archivo privado con permisos inseguros: " + env_name)
    if path.stat().st_size > 4096:
        raise MirrorError("Archivo privado demasiado grande: " + env_name)
    value = path.read_text(encoding="utf-8").strip()
    if not value or "\n" in value or "\r" in value:
        raise MirrorError("Contenido privado inválido: " + env_name)
    return value


def _git(args: list[str]) -> None:
    try:
        subprocess.run(["git", *args], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=240,
                       env={**os.environ, "GIT_TERMINAL_PROMPT": "0",
                            "GIT_CONFIG_NOSYSTEM": "1"})
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise MirrorError("Falló la operación local de git.") from None


def make_bundle(source_url: str) -> bytes:
    """Bundle de todas las referencias, incluidos tags y ramas."""
    if not (source_url.startswith("https://github.com/pl0n3r/")
            or Path(source_url).is_dir()):
        raise MirrorError("Origen git no autorizado.")
    with TemporaryDirectory(prefix="mirror-git-") as temp:
        work = Path(temp) / "mirror.git"
        archive = Path(temp) / "repository.bundle"
        _git(["clone", "--mirror", "--quiet", "--", source_url, str(work)])
        _git(["-C", str(work), "bundle", "create", str(archive), "--all"])
        blob = archive.read_bytes()
        if not blob or len(blob) > _MAX_OBJECT:
            raise MirrorError("Bundle git vacío o demasiado grande.")
        return blob


class GitHubSource:
    """Solo GET autenticados a api.github.com; nunca modifica un Issue/PR."""

    def __init__(self, token: str):
        self._token = token
        self._http = build_opener(_NoRedirect)

    def _page(self, resource: str, page: int) -> list[dict]:
        if not re.fullmatch(r"repos/pl0n3r/[A-Za-z0-9_-]+/(issues|pulls)(/[0-9]+/(comments|reviews|files))?", resource):
            raise MirrorError("Ruta de API de GitHub no autorizada.")
        uri = "https://api.github.com/" + resource + "?state=all&per_page=100&page=" + str(page)
        request = Request(uri, headers={
            "Authorization": "Bearer " + self._token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Factory-repository-mirror/1",
        })
        try:
            with self._http.open(request, timeout=30) as response:
                content = response.read(_MAX_API + 1)
        except (OSError, ValueError):
            raise MirrorError("GitHub no permitió leer el respaldo.") from None
        if len(content) > _MAX_API:
            raise MirrorError("Página de GitHub demasiado grande.")
        try:
            records = json.loads(content)
        except (ValueError, UnicodeDecodeError):
            raise MirrorError("Respuesta JSON inválida de GitHub.") from None
        if not isinstance(records, list) or any(not isinstance(x, dict) for x in records):
            raise MirrorError("Lista de GitHub inesperada.")
        return records

    def _all(self, path: str) -> list[dict]:
        result: list[dict] = []
        for number in range(1, 501):
            batch = self._page(path, number)
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise MirrorError("Límite seguro de paginación de GitHub alcanzado.")

    def capture(self, repo: str) -> tuple[bytes, list[dict], list[dict]]:
        if repo not in REPOSITORIES:
            raise MirrorError("Repositorio fuera de la lista canónica.")
        archive = make_bundle("https://github.com/" + repo + ".git")
        root = "repos/" + repo
        issues = [x for x in self._all(root + "/issues")
                  if "pull_request" not in x]
        for issue in issues:
            issue["mirror_comments"] = self._all(
                root + "/issues/" + str(issue["number"]) + "/comments")
        pulls = self._all(root + "/pulls")
        for pull in pulls:
            number = str(pull["number"])
            pull["mirror_issue_comments"] = self._all(
                root + "/issues/" + number + "/comments")
            pull["mirror_reviews"] = self._all(root + "/pulls/" + number + "/reviews")
            pull["mirror_review_comments"] = self._all(root + "/pulls/" + number + "/comments")
            pull["mirror_files"] = self._all(root + "/pulls/" + number + "/files")
        return archive, issues, pulls


class S3Store:
    """PUT/GET S3 SigV4 (Backblaze B2); claves privadas solo de NAME_FILE."""

    def __init__(self, endpoint: str, bucket: str, region: str,
                 key_id: str, secret: str):
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.path not in ("", "/") or parsed.query
                or parsed.fragment or parsed.username or parsed.password):
            raise MirrorError("Endpoint S3 debe ser HTTPS sin ruta ni usuario.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,62}", bucket):
            raise MirrorError("Bucket S3 inválido.")
        if not re.fullmatch(r"[a-z0-9-]{2,40}", region):
            raise MirrorError("Región S3 inválida.")
        self.endpoint = endpoint.rstrip("/")
        self.host = parsed.netloc.lower()
        self.bucket = bucket
        self.region = region
        self.key_id = key_id
        self.secret = secret
        self._http = build_opener(_NoRedirect)

    def _request(self, method: str, key: str, payload: bytes = b"") -> bytes:
        if method not in ("GET", "PUT") or not _valid_key(key):
            raise MirrorError("Operación u objeto S3 inválidos.")
        if len(payload) > _MAX_OBJECT:
            raise MirrorError("Objeto supera el límite de exportación.")
        now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        day = now[:8]
        uri = quote("/" + self.bucket + "/" + key, safe="/-_.~")
        digest = _digest(payload)
        headers = ("host:" + self.host + "\n"
                   + "x-amz-content-sha256:" + digest + "\n"
                   + "x-amz-date:" + now + "\n")
        signed = "host;x-amz-content-sha256;x-amz-date"
        canonical = "\n".join((method, uri, "", headers, signed, digest))
        scope = day + "/" + self.region + "/s3/aws4_request"
        to_sign = ("AWS4-HMAC-SHA256\n" + now + "\n" + scope + "\n"
                   + _digest(canonical.encode("utf-8")))
        signing_key = ("AWS4" + self.secret).encode("utf-8")
        for part in (day, self.region, "s3", "aws4_request"):
            signing_key = hmac.new(signing_key, part.encode("utf-8"),
                                   hashlib.sha256).digest()
        signature = hmac.new(signing_key, to_sign.encode("utf-8"),
                             hashlib.sha256).hexdigest()
        auth = ("AWS4-HMAC-SHA256 Credential=" + self.key_id + "/" + scope
                + ",SignedHeaders=" + signed + ",Signature=" + signature)
        request = Request(self.endpoint + uri, method=method,
                          data=payload if method == "PUT" else None,
                          headers={
                              "Host": self.host,
                              "X-Amz-Date": now,
                              "X-Amz-Content-Sha256": digest,
                              "Authorization": auth,
                          })
        try:
            with self._http.open(request, timeout=90) as response:
                data = response.read(_MAX_OBJECT + 1)
        except (OSError, ValueError):
            raise MirrorError("Operación HTTPS de almacenamiento fallida.") from None
        if len(data) > _MAX_OBJECT:
            raise MirrorError("Descarga del espejo demasiado grande.")
        return data

    def put(self, key: str, content: bytes) -> None:
        self._request("PUT", key, content)

    def get(self, key: str) -> bytes:
        return self._request("GET", key)


def export_all(source: Source, store: ObjectStore,
               repositories: tuple[str, ...] = REPOSITORIES,
               prefix: str = "mirror", snapshot: str | None = None) -> list[dict]:
    """Escribe datos antes del manifest: un fallo no publica un snapshot íntegro."""
    if not _valid_key(prefix) or prefix.endswith("/"):
        raise MirrorError("Prefijo del espejo inválido.")
    snapshot = snapshot or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-" + uuid4().hex[:12])
    if not _SNAPSHOT.fullmatch(snapshot):
        raise MirrorError("Identificador de snapshot inválido.")
    if not repositories or len(repositories) > len(REPOSITORIES):
        raise MirrorError("Lista de repositorios inválida.")
    if len(set(repositories)) != len(repositories) or any(
        repo not in REPOSITORIES for repo in repositories
    ):
        raise MirrorError("Repositorios duplicados o desconocidos.")
    published: list[dict] = []
    for repo in repositories:
        archive, issues, prs = source.capture(repo)
        if not isinstance(archive, bytes) or not archive:
            raise MirrorError("Bundle de origen inválido.")
        if (not isinstance(issues, list) or not isinstance(prs, list)
                or any(not isinstance(row, dict) for row in issues + prs)):
            raise MirrorError("Metadatos de captura inválidos.")
        base = prefix + "/" + snapshot + "/" + repo.replace("/", "_")
        files = {"repository.bundle": archive, "issues.json": _json(issues),
                 "pulls.json": _json(prs)}
        objects: dict[str, dict] = {}
        for filename, content in files.items():
            key = base + "/" + filename
            if not _valid_key(key) or len(content) > _MAX_OBJECT:
                raise MirrorError("Objeto de snapshot inválido.")
            store.put(key, content)
            objects[filename] = {"key": key, "sha256": _digest(content),
                                 "size": len(content)}
        manifest = _json({"format": _FORMAT, "repo": repo, "snapshot": snapshot,
                          "objects": objects})
        manifest_key = base + "/manifest.json"
        store.put(manifest_key, manifest)
        published.append({"repo": repo, "key": manifest_key,
                          "sha256": _digest(manifest), "snapshot": snapshot})
    return published


def restore_one(store: ObjectStore, manifest_key: str, expected_sha: str,
                destination: Path) -> dict:
    """Restaura código y metadatos locales; NO recrea Issues/PRs en GitHub."""
    if not _valid_key(manifest_key) or not manifest_key.endswith("/manifest.json"):
        raise MirrorError("Ruta de manifiesto inválida.")
    if not _SHA.fullmatch(expected_sha):
        raise MirrorError("SHA-256 de manifiesto obligatorio.")
    raw = store.get(manifest_key)
    if _digest(raw) != expected_sha:
        raise MirrorError("Huella de manifiesto distinta de la esperada.")
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise MirrorError("Manifiesto JSON inválido.") from None
    if not isinstance(manifest, dict) or set(manifest) != {
        "format", "repo", "snapshot", "objects"
    } or manifest["format"] != _FORMAT or manifest["repo"] not in REPOSITORIES:
        raise MirrorError("Esquema del manifiesto no reconocido.")
    if not isinstance(manifest["snapshot"], str) or not _SNAPSHOT.fullmatch(manifest["snapshot"]):
        raise MirrorError("Versión del manifiesto inválida.")
    prefix = manifest_key.rsplit("/", 1)[0]
    if not prefix.endswith("/" + manifest["snapshot"] + "/"
                           + manifest["repo"].replace("/", "_")):
        raise MirrorError("Identidad del manifiesto incompatible.")
    files = ("repository.bundle", "issues.json", "pulls.json")
    entries = manifest["objects"]
    if not isinstance(entries, dict) or set(entries) != set(files):
        raise MirrorError("Objetos del manifiesto incompletos.")
    verified: dict[str, bytes] = {}
    for name in files:
        item = entries[name]
        if not isinstance(item, dict) or set(item) != {"key", "sha256", "size"}:
            raise MirrorError("Objeto no canónico en el manifiesto.")
        if item["key"] != prefix + "/" + name or not isinstance(item["sha256"], str):
            raise MirrorError("Clave de objeto incompatible.")
        if not _SHA.fullmatch(item["sha256"]) or type(item["size"]) is not int:
            raise MirrorError("Huella de objeto inválida.")
        data = store.get(item["key"])
        if len(data) != item["size"] or _digest(data) != item["sha256"]:
            raise MirrorError("Integridad SHA-256 del objeto fallida.")
        verified[name] = data
    for name in ("issues.json", "pulls.json"):
        try:
            if not isinstance(json.loads(verified[name]), list):
                raise ValueError("not a list")
        except (ValueError, UnicodeDecodeError):
            raise MirrorError("Metadatos de GitHub inválidos.") from None
    destination = Path(destination)
    if destination.exists() or not destination.parent.is_dir():
        raise MirrorError("Destino debe ser nuevo y tener directorio padre.")
    with TemporaryDirectory(prefix="mirror-restore-", dir=destination.parent) as tmp:
        temp = Path(tmp)
        bundle = temp / "repository.bundle"
        bundle.write_bytes(verified["repository.bundle"])
        _git(["clone", "--mirror", "--quiet", "--", str(bundle),
              str(temp / "repository.git")])
        output = temp / "restored"
        output.mkdir()
        shutil.move(str(temp / "repository.git"), str(output / "repository.git"))
        (output / "issues.json").write_bytes(verified["issues.json"])
        (output / "pulls.json").write_bytes(verified["pulls.json"])
        (output / "manifest.json").write_bytes(raw)
        output.rename(destination)
    return {"repo": manifest["repo"], "snapshot": manifest["snapshot"],
            "path": str(destination), "verified": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Espejo GitHub → S3 compatible")
    subs = parser.add_subparsers(dest="action", required=True)
    export = subs.add_parser("export", help="Exportar los siete repos públicos")
    export.add_argument("--prefix", default="mirror")
    restore = subs.add_parser("restore", help="Restaurar un snapshot verificable")
    restore.add_argument("--manifest-key", required=True)
    restore.add_argument("--manifest-sha256", required=True)
    restore.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        store = S3Store(os.environ.get("B2_S3_ENDPOINT", ""),
                        os.environ.get("B2_S3_BUCKET", ""),
                        os.environ.get("B2_S3_REGION", ""),
                        _file_secret("B2_KEY_ID_FILE"),
                        _file_secret("B2_APP_KEY_FILE"))
        if args.action == "export":
            token = _file_secret("GITHUB_TOKEN_FILE")
            result = export_all(GitHubSource(token), store, prefix=args.prefix)
        else:
            result = restore_one(store, args.manifest_key,
                                 args.manifest_sha256, args.destination)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except MirrorError as exc:
        print("Espejo detenido: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

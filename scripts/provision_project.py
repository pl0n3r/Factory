#!/usr/bin/env python3
"""Provisiona repositorios privados con gobernanza publicada de Factory."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API, OWNER = "https://api.github.com", "pl0n3r"
GOVERNANCE_REF, MARKER_PATH = "pl0n3r/factory@v1", ".factory/provisioning.json"
PROJECT_RE = re.compile(r"^project-[a-z0-9][a-z0-9-]{1,78}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
REPO_RE = re.compile(r"^pl0n3r/[A-Za-z0-9_.-]{1,100}$")
KEY_RE, SHA_RE = re.compile(r"^[0-9a-f]{64}$"), re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
REQUIRED = {"AGENTES.md", ".github/workflows/ci.yml", "config/version.json"}
MAX_FILES, MAX_FILE, MAX_TOTAL = 200, 500_000, 2_000_000


class ProvisionError(RuntimeError):
    pass


def validate_request(raw: Any) -> dict[str, str]:
    keys = {"project_id", "project_slug", "target_repository", "governance_ref", "idempotency_key"}
    if not isinstance(raw, dict) or set(raw) != keys or any(not isinstance(raw[k], str) or not raw[k] for k in keys):
        raise ProvisionError("Solicitud de provisión inválida.")
    req = {k: raw[k] for k in keys}
    if PROJECT_RE.fullmatch(req["project_id"]) is None or SLUG_RE.fullmatch(req["project_slug"]) is None:
        raise ProvisionError("Identidad de proyecto inválida.")
    if REPO_RE.fullmatch(req["target_repository"]) is None or ".." in req["target_repository"]:
        raise ProvisionError("target_repository fuera del owner permitido.")
    if req["governance_ref"] != GOVERNANCE_REF or KEY_RE.fullmatch(req["idempotency_key"]) is None:
        raise ProvisionError("Gobernanza o idempotency_key inválida.")
    return req


def validate_sha(value: str) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise ProvisionError("SHA de gobernanza inválido.")
    return value


def identity(req: dict[str, str], sha: str) -> str:
    payload = json.dumps({"request": req, "governance_sha": validate_sha(sha)}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def marker_for(req: dict[str, str], sha: str) -> dict[str, Any]:
    return {"version": 2, **req, "governance_sha": validate_sha(sha), "request_identity": identity(req, sha)}


def description_for(req: dict[str, str], sha: str) -> str:
    return f"Factory project {req['project_id']} [{identity(req, sha)}]"


def load_template(root: Path) -> dict[str, str]:
    root, files, total = root.resolve(), {}, 0
    if not root.is_dir():
        raise ProvisionError("template/ no existe.")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ProvisionError("template/ no admite symlinks.")
        if not path.is_file():
            continue
        rel, size = path.relative_to(root).as_posix(), path.stat().st_size
        total += size
        if rel == MARKER_PATH or size > MAX_FILE or total > MAX_TOTAL or len(files) >= MAX_FILES:
            raise ProvisionError("template/ inválido o excede límites.")
        try:
            files[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ProvisionError("template/ debe contener texto UTF-8.") from exc
    if not REQUIRED.issubset(files):
        raise ProvisionError("template/ no contiene la gobernanza mínima.")
    return files


class GitHubGateway:
    def __init__(self, token: str) -> None:
        if not isinstance(token, str) or not token.strip():
            raise ProvisionError("FACTORY_PROVISION_TOKEN no configurado.")
        self.token = token.strip()

    def _request(self, method: str, path: str, payload: Any = None, allow: tuple[int, ...] = ()) -> Any:
        if not path.startswith("/"):
            raise ProvisionError("Ruta GitHub inválida.")
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(API + path, data=data, method=method, headers={
            "Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "factory-provisioner",
        })
        try:
            with urlopen(req, timeout=30) as response:
                raw = response.read()
                return None if not raw else json.loads(raw.decode())
        except HTTPError as exc:
            if exc.code in allow:
                return None
            raise ProvisionError(f"GitHub rechazó la operación ({exc.code}).") from exc

    def _git(self, cwd: Path, *args: str, env: dict[str, str] | None = None) -> None:
        run = subprocess.run(["git", "-C", str(cwd), *args], check=False, capture_output=True, text=True, env=env)
        if run.returncode:
            raise ProvisionError("Git no pudo completar el bootstrap gobernado.")

    def authorize(self) -> None:
        user = self._request("GET", "/user")
        if not isinstance(user, dict) or user.get("login") != OWNER:
            raise ProvisionError("La autoridad GitHub no pertenece al owner permitido.")

    def repository(self, name: str) -> dict[str, Any] | None:
        repo = self._request("GET", f"/repos/{name}", allow=(404,))
        if repo is not None and not isinstance(repo, dict):
            raise ProvisionError("Respuesta GitHub inválida.")
        return repo

    def create(self, req: dict[str, str], sha: str) -> dict[str, Any]:
        repo = self._request("POST", "/user/repos", {
            "name": req["target_repository"].split("/", 1)[1], "private": True,
            "auto_init": False, "description": description_for(req, sha),
        })
        if not isinstance(repo, dict):
            raise ProvisionError("GitHub no devolvió el repositorio creado.")
        return repo

    def empty(self, name: str) -> bool:
        branches = self._request("GET", f"/repos/{name}/branches?per_page=1", allow=(409,))
        if branches is None:
            return True
        if not isinstance(branches, list):
            raise ProvisionError("No fue posible verificar si el repo está vacío.")
        return not branches

    def marker(self, name: str) -> dict[str, Any] | None:
        value = self._request("GET", f"/repos/{name}/contents/{MARKER_PATH}?ref=main", allow=(404, 409))
        if value is None:
            return None
        if not isinstance(value, dict) or value.get("encoding") != "base64" or not isinstance(value.get("content"), str):
            raise ProvisionError("Marker remoto inválido.")
        try:
            return json.loads(base64.b64decode(value["content"]).decode())
        except (TypeError, ValueError) as exc:
            raise ProvisionError("Marker remoto ilegible.") from exc

    def set_default(self, name: str) -> None:
        self._request("PATCH", f"/repos/{name}", {"default_branch": "main"})

    def bootstrap(self, name: str, files: dict[str, str], marker: dict[str, Any]) -> None:
        if REPO_RE.fullmatch(name) is None:
            raise ProvisionError("Repositorio inválido para bootstrap.")
        with tempfile.TemporaryDirectory(prefix="factory-provision-") as temp:
            root, work = Path(temp), Path(temp) / "repo"
            work.mkdir()
            for rel, content in sorted(files.items()):
                path = Path(rel)
                if path.is_absolute() or ".." in path.parts or ".git" in path.parts or not isinstance(content, str):
                    raise ProvisionError("Ruta inválida en template de provisión.")
                target = work / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            target = work / MARKER_PATH
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(marker, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            for args in (
                ("init", "-b", "main"), ("config", "user.name", "Factory Provisioner"),
                ("config", "user.email", "factory-provisioner@users.noreply.github.com"),
                ("add", "--all"), ("commit", "-m", "chore(factory): bootstrap gobernanza v1"),
                ("remote", "add", "origin", f"https://github.com/{name}.git"),
            ):
                self._git(work, *args)
            askpass = root / "askpass.sh"
            askpass.write_text('#!/bin/sh\ncase "$1" in\n*Username*) echo x-access-token;;\n*Password*) echo "$FACTORY_PROVISION_TOKEN";;\n*) exit 1;;\nesac\n')
            askpass.chmod(0o700)
            env = {**os.environ, "FACTORY_PROVISION_TOKEN": self.token, "GIT_ASKPASS": str(askpass), "GIT_TERMINAL_PROMPT": "0"}
            self._git(work, "push", "origin", "HEAD:refs/heads/main", env=env)
        self.set_default(name)


def compatible(repo: dict[str, Any], name: str) -> bool:
    return repo.get("full_name") == name and repo.get("private") is True


def existing_confirmed(gateway: Any, repo: dict[str, Any], req: dict[str, str], sha: str, expected: dict[str, Any]) -> bool:
    name = req["target_repository"]
    if not compatible(repo, name):
        raise ProvisionError("Repositorio preexistente incompatible.")
    current = gateway.marker(name)
    if current is not None:
        if current != expected:
            raise ProvisionError("Repositorio gobernado por otra intención.")
        if repo.get("default_branch") != "main":
            gateway.set_default(name)
        return True
    if repo.get("description") != description_for(req, sha) or not gateway.empty(name):
        raise ProvisionError("Repositorio preexistente incompatible.")
    return False


def provision(raw: dict[str, str], gateway: Any, files: dict[str, str], sha: str) -> dict[str, Any]:
    req, sha = validate_request(raw), validate_sha(sha)
    gateway.authorize()
    expected, name = marker_for(req, sha), req["target_repository"]
    repo, created = gateway.repository(name), False
    if repo is None:
        created, repo = True, gateway.create(req, sha)
        if not compatible(repo, name):
            raise ProvisionError("GitHub creó una identidad o visibilidad inesperada.")
    elif existing_confirmed(gateway, repo, req, sha, expected):
        return {"status": "confirmed", "repository": name, "created": False, "bootstrapped": False}
    gateway.bootstrap(name, files, expected)
    final = gateway.repository(name)
    if gateway.marker(name) != expected or not isinstance(final, dict) or not compatible(final, name) or final.get("default_branch") != "main":
        raise ProvisionError("Bootstrap no dejó evidencia/estado canónico.")
    return {"status": "confirmed", "repository": name, "created": created, "bootstrapped": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", default="template")
    parser.add_argument("--governance-sha", required=True)
    args = parser.parse_args()
    raw = {name: os.getenv(name.upper(), "") for name in ("project_id", "project_slug", "target_repository", "governance_ref", "idempotency_key")}
    try:
        result = provision(raw, GitHubGateway(os.getenv("FACTORY_PROVISION_TOKEN", "")), load_template(Path(args.template)), args.governance_sha)
    except ProvisionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

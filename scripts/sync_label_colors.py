#!/usr/bin/env python3
"""Sincroniza exclusivamente colores de labels existentes en los siete repos canónicos."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = (
    "pl0n3r/Factory",
    "pl0n3r/Condor",
    "pl0n3r/GrindFlow",
    "pl0n3r/ControlBot",
    "pl0n3r/AutoFactory",
    "pl0n3r/FactoryRunner",
    "pl0n3r/brvtal",
)
REPOSITORY_LANGUAGE = {
    repo: ("en" if repo == "pl0n3r/brvtal" else "es")
    for repo in REPOSITORIES
}
HEX = re.compile(r"^[0-9A-Fa-f]{6}$")
API_ROOT = "https://api.github.com"
MAX_LABELS = 1000


class SyncError(RuntimeError):
    """Fallo seguro del reconciliador."""


def _normalize_color(value: Any) -> str:
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise SyncError("Color fuera del contrato.")
    return value.upper()


def load_catalog(path: Path) -> list[dict[str, str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"Catálogo ilegible: {path.name}") from exc
    if not isinstance(raw, list) or not raw or len(raw) > 200:
        raise SyncError("Catálogo fuera del contrato.")
    seen_keys: set[str] = set()
    seen_names: set[str] = set()
    catalog: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise SyncError("Entrada de catálogo inválida.")
        key = item.get("key")
        name = item.get("name")
        color = item.get("color")
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(name, str)
            or not name
            or key in seen_keys
            or name in seen_names
        ):
            raise SyncError("Catálogo ambiguo.")
        normalized = _normalize_color(color)
        seen_keys.add(key)
        seen_names.add(name)
        catalog.append({"key": key, "name": name, "color": normalized})
    return catalog


def load_catalogs(root: Path = ROOT) -> dict[str, list[dict[str, str]]]:
    paths = {
        "es": root / "labels" / "es.json",
        "en": root / "labels" / "en.json",
    }
    catalogs = {language: load_catalog(path) for language, path in paths.items()}
    validate_catalog_parity(catalogs["es"], catalogs["en"])
    return catalogs


def validate_catalog_parity(
    spanish: list[dict[str, str]],
    english: list[dict[str, str]],
) -> None:
    es = {item["key"]: item["color"] for item in spanish}
    en = {item["key"]: item["color"] for item in english}
    if set(es) != set(en):
        raise SyncError("Los catálogos ES/EN no tienen las mismas keys.")
    drift = sorted(key for key in es if es[key] != en[key])
    if drift:
        raise SyncError("Los catálogos ES/EN divergen de color por key: " + ", ".join(drift))


def _existing_by_name(existing: Any) -> dict[str, str]:
    if not isinstance(existing, list) or len(existing) > MAX_LABELS:
        raise SyncError("Snapshot de labels fuera del contrato.")
    current: dict[str, str] = {}
    for item in existing:
        if not isinstance(item, dict):
            raise SyncError("Label remota inválida.")
        name = item.get("name")
        color = item.get("color")
        if not isinstance(name, str) or not name:
            raise SyncError("Label remota sin nombre válido.")
        if name in current:
            raise SyncError("Snapshot remoto contiene nombres duplicados.")
        current[name] = _normalize_color(color)
    return current


def plan_repository(
    repository: str,
    existing: Any,
    catalogs: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    if repository not in REPOSITORY_LANGUAGE:
        raise SyncError("Repositorio fuera de la allowlist canónica.")
    language = REPOSITORY_LANGUAGE[repository]
    catalog = catalogs.get(language)
    if not isinstance(catalog, list):
        raise SyncError("Catálogo faltante para el repositorio.")
    current = _existing_by_name(existing)
    plan: list[dict[str, str]] = []
    for wanted in catalog:
        before = current.get(wanted["name"])
        if before is None:
            continue
        after = wanted["color"]
        if before != after:
            plan.append(
                {
                    "action": "update_color",
                    "repository": repository,
                    "label": wanted["name"],
                    "color_before": before,
                    "color_after": after,
                }
            )
    return plan


def plan_all(
    snapshots: dict[str, Any],
    catalogs: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    if set(snapshots) != set(REPOSITORIES):
        raise SyncError("El snapshot debe cubrir exactamente los siete repos canónicos.")
    plan: list[dict[str, str]] = []
    for repository in REPOSITORIES:
        plan.extend(plan_repository(repository, snapshots[repository], catalogs))
    assert_safe_plan(plan)
    return plan


def assert_safe_plan(plan: Any) -> None:
    if not isinstance(plan, list) or len(plan) > 500:
        raise SyncError("Plan fuera del contrato.")
    required = {"action", "repository", "label", "color_before", "color_after"}
    for item in plan:
        if not isinstance(item, dict) or set(item) != required:
            raise SyncError("Operación fuera del contrato color-only.")
        if item["action"] != "update_color":
            raise SyncError("Solo se permite update_color.")
        if item["repository"] not in REPOSITORY_LANGUAGE:
            raise SyncError("Operación dirigida fuera de la allowlist.")
        if not isinstance(item["label"], str) or not item["label"]:
            raise SyncError("Label inválida.")
        before = _normalize_color(item["color_before"])
        after = _normalize_color(item["color_after"])
        if before == after:
            raise SyncError("El plan contiene una actualización sin deriva real.")


def render_plan(plan: list[dict[str, str]]) -> str:
    assert_safe_plan(plan)
    if not plan:
        return "0 drifts"
    return "\n".join(
        f'{item["repository"]} + {item["label"]} + '
        f'{item["color_before"]} -> {item["color_after"]}'
        for item in plan
    )


class GitHubLabelsClient:
    def __init__(self, token: str | None = None):
        self.token = (token or "").strip() or None

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/repos/"):
            raise SyncError("Ruta GitHub fuera del contrato.")
        data = None
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "factory-label-color-sync",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(API_ROOT + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read()
        except HTTPError as exc:
            raise SyncError(f"GitHub respondió HTTP {exc.code} para una operación de labels.") from exc
        except URLError as exc:
            raise SyncError("No se pudo consultar GitHub.") from exc
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SyncError("GitHub devolvió una respuesta ilegible.") from exc

    def list_labels(self, repository: str) -> list[dict[str, Any]]:
        if repository not in REPOSITORY_LANGUAGE:
            raise SyncError("Repositorio fuera de la allowlist.")
        labels: list[dict[str, Any]] = []
        for page in range(1, 21):
            payload = self._request(
                "GET",
                f"/repos/{repository}/labels?per_page=100&page={page}",
            )
            if not isinstance(payload, list):
                raise SyncError("GitHub devolvió un listado de labels inválido.")
            labels.extend(payload)
            if len(labels) > MAX_LABELS:
                raise SyncError("GitHub devolvió demasiadas labels.")
            if len(payload) < 100:
                return labels
        raise SyncError("Paginación de labels excede el límite seguro.")

    def update_color(self, operation: dict[str, str]) -> None:
        assert_safe_plan([operation])
        if not self.token:
            raise SyncError("FACTORY_PROVISION_TOKEN es obligatorio para --apply.")
        repository = operation["repository"]
        name = quote(operation["label"], safe="")
        self._request(
            "PATCH",
            f"/repos/{repository}/labels/{name}",
            {"color": operation["color_after"]},
        )


def collect_snapshots(client: GitHubLabelsClient) -> dict[str, list[dict[str, Any]]]:
    return {repository: client.list_labels(repository) for repository in REPOSITORIES}


def execute(*, apply: bool, token: str | None = None) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    catalogs = load_catalogs()
    client = GitHubLabelsClient(token if apply else None)
    before = collect_snapshots(client)
    plan = plan_all(before, catalogs)
    if not apply:
        return plan, []
    if not (token or "").strip():
        raise SyncError("FACTORY_PROVISION_TOKEN es obligatorio para --apply.")
    print(render_plan(plan))
    for operation in plan:
        client.update_color(operation)
        print(
            f'applied: {operation["repository"]} + {operation["label"]} + '
            f'{operation["color_before"]} -> {operation["color_after"]}'
        )
    after = collect_snapshots(client)
    residual = plan_all(after, catalogs)
    if residual:
        raise SyncError("Verificación post-apply detectó deriva residual.")
    return plan, residual


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Solo reporta deriva; es el modo por defecto.")
    group.add_argument("--apply", action="store_true", help="Actualiza únicamente el color de labels existentes.")
    args = parser.parse_args(argv)
    try:
        token = os.environ.get("FACTORY_PROVISION_TOKEN") if args.apply else None
        plan, residual = execute(apply=args.apply, token=token)
        if not args.apply:
            print(render_plan(plan))
        if args.apply:
            print(f"post-apply: {render_plan(residual)}")
        return 0
    except SyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

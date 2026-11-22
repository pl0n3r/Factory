#!/usr/bin/env python3
"""Carril restringido para PRs oficiales de Dependabot, sin exención de calidad."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

BOT_ID = 49699333
BOT_APP_ID = 29110
HEX_SHA = re.compile(r"^[0-9a-f]{40}$")
REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
UPDATE_TYPE = re.compile(r"(?m)^ +update-type: +version-update:semver-(patch|minor|major) *$")
WORKFLOW_PATH = re.compile(r"^\.github/workflows/[^/]+\.ya?ml$")
REQUIREMENTS = re.compile(r"^requirements(?:[-_.][A-Za-z0-9_-]+)?\.txt$")
WORKFLOW_USE = re.compile(r"^[+-]\s*uses:\s*[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+@[0-9a-f]{40}\s*$")
MANIFESTS = frozenset({
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
    "pnpm-lock.yaml", "composer.json", "composer.lock", "Cargo.toml",
    "Cargo.lock", "go.mod", "go.sum", "Gemfile", "Gemfile.lock",
    "Pipfile", "Pipfile.lock", "poetry.lock", "pyproject.toml",
    "uv.lock", "mix.exs", "mix.lock", "pubspec.yaml",
    "pubspec.lock", "Podfile", "Podfile.lock", "gradle.lockfile",
    "libs.versions.toml", "build.gradle", "build.gradle.kts",
    "pom.xml", "packages.lock.json", "Directory.Packages.props",
})


class LaneError(ValueError):
    """Entrada ambigua o fuera de autoridad: fail-closed."""


def _official_bot(user: object) -> bool:
    if not isinstance(user, dict):
        return False
    if user.get("login") != "dependabot[bot]":
        return False
    avatar = user.get("avatar_url")
    if not isinstance(avatar, str):
        raise LaneError("Identidad Dependabot sin app_id verificable")
    image = urlsplit(avatar)
    if not (
        user.get("type") == "Bot"
        and type(user.get("id")) is int
        and user["id"] == BOT_ID
        and user.get("html_url") == "https://github.com/apps/dependabot"
        and image.scheme == "https"
        and image.hostname == "avatars.githubusercontent.com"
        and image.path == f"/in/{BOT_APP_ID}"
    ):
        raise LaneError("Identidad Dependabot o app_id 29110 no autenticados")
    return True


def _path_kind(path: object, patch: object) -> str:
    if not isinstance(path, str) or len(path) > 300:
        raise LaneError("Ruta desconocida")
    if path.startswith(("/", "./")) or "\\" in path or "\x00" in path:
        raise LaneError("Ruta no canónica")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise LaneError("Ruta no canónica")
    if WORKFLOW_PATH.fullmatch(path):
        if not isinstance(patch, str) or not patch:
            raise LaneError("Workflow sin diff verificable")
        edited = [line for line in patch.splitlines() if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
        if not edited or any(not WORKFLOW_USE.fullmatch(line) for line in edited):
            raise LaneError("Workflow altera algo distinto de pins de dependencias")
        return "workflow"
    if len(parts) > 7:
        raise LaneError("Dependencia en ruta no contemplada")
    if parts[-1] in MANIFESTS or REQUIREMENTS.fullmatch(parts[-1]):
        return "manifest"
    raise LaneError("Archivo fuera del carril Dependabot: " + path)


def classify(pr: object, files: object, commit: object, *, repo: str, head: str) -> dict[str, object] | None:
    """None = autor ajeno (sin excepción); error = bot sospechoso."""
    if not isinstance(pr, dict):
        raise LaneError("PR ilegible")
    if not _official_bot(pr.get("user")):
        return None
    if not REPO_NAME.fullmatch(repo) or not HEX_SHA.fullmatch(head):
        raise LaneError("Repositorio o SHA inválidos")
    source = pr.get("head")
    target = pr.get("base")
    if not isinstance(source, dict) or not isinstance(target, dict):
        raise LaneError("Refs faltantes")
    if (
        pr.get("state") != "open"
        or source.get("sha") != head
        or (source.get("repo") or {}).get("full_name") != repo
        or (target.get("repo") or {}).get("full_name") != repo
        or target.get("ref") != "main"
    ):
        raise LaneError("PR Dependabot sin refs internas exactas")
    if not isinstance(files, list) or not 1 <= len(files) <= 3000:
        raise LaneError("Diff incompleto")
    if not isinstance(commit, dict):
        raise LaneError("Commit sin evidencia")
    author = commit.get("author")
    metadata = commit.get("commit")
    if (
        not isinstance(author, dict)
        or author.get("login") != "dependabot[bot]"
        or author.get("id") != BOT_ID
        or not isinstance(metadata, dict)
        or (metadata.get("verification") or {}).get("verified") is not True
    ):
        raise LaneError("HEAD no firmado por Dependabot oficial")
    message = metadata.get("message")
    if not isinstance(message, str):
        raise LaneError("Commit sin clasificación")
    # Los metadatos reales de Dependabot son bloques YAML-like:
    # "- dependency-name: x", "  dependency-version: y", "  update-type: ...".
    # No confiar solo en la presencia aislada de un semver-minor.
    versions = UPDATE_TYPE.findall(message)
    names = re.findall(r"(?m)^- dependency-name:[ \t]*([^\r\n]+)\s*$", message)
    dep_versions = re.findall(r"(?m)^[ \t]+dependency-version:[ \t]*([^\r\n]+)\s*$", message)
    if not versions or len(versions) > 30 or len(versions) != len(names) or len(names) != len(dep_versions):
        raise LaneError("Metadatos de dependencias incompletos o ambiguos")
    if len(set(names)) != len(names) or any(
        not name.strip() or len(name) > 200 or not version.strip() or len(version) > 100
        for name, version in zip(names, dep_versions)
    ):
        raise LaneError("Nombres o versiones de dependencias inválidos")
    seen: set[str] = set()
    kinds: set[str] = set()
    for row in files:
        if not isinstance(row, dict) or row.get("status") not in ("modified", "added", "removed"):
            raise LaneError("Fila de diff no válida")
        name = row.get("filename")
        if not isinstance(name, str) or name.casefold() in seen:
            raise LaneError("Archivo duplicado o inválido")
        seen.add(name.casefold())
        kinds.add(_path_kind(name, row.get("patch")))
    major_index = versions.index("major") if "major" in versions else -1
    major_target = (
        f"{names[major_index]} a la versión mayor {dep_versions[major_index]}"
        if major_index >= 0 else None
    )
    policy = "manual" if "major" in versions or "workflow" in kinds else "auto"
    return {
        "dependabot": True, "head": head, "pr": pr.get("number"),
        "policy": policy, "major": "major" in versions, "workflow": "workflow" in kinds,
        "files": len(files), "updates": len(versions), "major_target": major_target,
        "file_paths": sorted(row["filename"] for row in files),
    }


def api(repo: str, path: str, token: str, *, method: str = "GET", payload: object = None) -> object:
    if not REPO_NAME.fullmatch(repo):
        raise LaneError("Repositorio inválido")
    if method not in ("GET", "POST", "PUT"):
        raise LaneError("Verbo no permitido")
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request("https://api.github.com" + path, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urlopen(req, timeout=20) as response:
            return json.load(response)
    except (HTTPError, URLError, ValueError, TimeoutError) as exc:
        raise LaneError(f"API GitHub no verificable ({type(exc).__name__})") from exc


def read_exact(repo: str, number: int, head: str, token: str) -> tuple[dict, dict]:
    if type(number) is not int or number < 1 or not HEX_SHA.fullmatch(head):
        raise LaneError("Número o HEAD inválidos")
    prefix = f"/repos/{repo}"
    pull = api(repo, f"{prefix}/pulls/{number}", token)
    if not isinstance(pull, dict):
        raise LaneError("PR ilegible")
    # No consultar /commits del PR de autores ajenos; su gate sigue intacto.
    if not _official_bot(pull.get("user")):
        return pull, {"dependabot": False}
    count = pull.get("changed_files")
    if type(count) is not int or not 1 <= count <= 3000:
        raise LaneError("changed_files fuera de límites")
    files = []
    for page in range(1, 31):
        rows = api(repo, f"{prefix}/pulls/{number}/files?per_page=100&page={page}", token)
        if not isinstance(rows, list) or not rows or len(rows) > 100:
            raise LaneError("Paginación de diff ilegible")
        files.extend(rows)
        if len(files) == count:
            break
        if len(rows) != 100 or len(files) > count:
            raise LaneError("Diff truncado o cambiante")
    if len(files) != count:
        raise LaneError("Diff incompleto")
    commit = api(repo, f"{prefix}/commits/{head}", token)
    result = classify(pull, files, commit, repo=repo, head=head)
    after = api(repo, f"{prefix}/pulls/{number}", token)
    if not isinstance(after, dict) or (
        (after.get("head") or {}).get("sha") != head
        or (after.get("base") or {}).get("sha") != (pull.get("base") or {}).get("sha")
        or after.get("changed_files") != count
        or after.get("state") != pull.get("state")
    ):
        raise LaneError("Carrera HEAD/BASE o diff durante la lectura")
    return after, result or {"dependabot": False}


def classify_from_api(repo: str, number: int, head: str, token: str) -> dict:
    _, lane = read_exact(repo, number, head, token)
    return lane


def _age_over_seven_days(pr: dict, *, now: datetime) -> bool:
    created = pr.get("created_at")
    if not isinstance(created, str):
        raise LaneError("PR sin fecha verificable")
    try:
        stamp = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise LaneError("Fecha inválida") from exc
    if stamp > now:
        raise LaneError("PR fechado en el futuro")
    return now - stamp > timedelta(days=7)


def _terminal_checks_green(repo: str, head: str, token: str) -> bool:
    prefix = f"/repos/{repo}"
    pages = []
    for page in range(1, 11):
        response = api(repo, f"{prefix}/commits/{head}/check-runs?per_page=100&page={page}", token)
        if not isinstance(response, dict) or type(response.get("total_count")) is not int:
            raise LaneError("Check-runs no verificables")
        rows = response.get("check_runs")
        if not isinstance(rows, list):
            raise LaneError("Check-runs incompletos")
        pages.extend(rows)
        if len(pages) == response["total_count"]:
            break
        if len(rows) != 100 or len(pages) > response["total_count"]:
            raise LaneError("Check-runs truncados")
    if not pages or len(pages) != response["total_count"]:
        raise LaneError("Sin evidencia completa de checks")
    latest: dict[str, dict] = {}
    for check in pages:
        if not isinstance(check, dict) or check.get("head_sha") != head:
            raise LaneError("Check sobre HEAD incorrecto")
        if not isinstance(check.get("name"), str) or type(check.get("id")) is not int:
            raise LaneError("Emisor de check ilegible")
        app = check.get("app")
        if not isinstance(app, dict) or type(app.get("id")) is not int:
            raise LaneError("Check no autenticado")
        key = check["name"]
        # El nombre "Validar" puede publicarlo otra App. La autoridad del
        # gate solo procede de github-actions (ID canónico de politica_kit).
        if key == "Validar" and (app.get("slug") != "github-actions" or app["id"] != 15368):
            raise LaneError("Validar emitido por App no autorizada")
        # El job reconciliador mira checks de su propio HEAD mientras corre:
        # su propio check (no requerido) no puede convertirse en deadlock.
        own_checks = ("Reconciliar Dependabot", "Reconciliar Dependabot Factory",
                      "Barrer Dependabot Factory", "Barrer Dependabot consumidor")
        if key in own_checks or any(key.endswith(" / " + own) for own in own_checks):
            continue
        if key not in latest or check["id"] > latest[key]["id"]:
            latest[key] = check
    if "Validar" not in latest or latest["Validar"].get("conclusion") != "success":
        return False
    if any(c.get("status") != "completed" or c.get("conclusion") not in ("success", "neutral", "skipped") for c in latest.values()):
        return False
    return True


def _switch_running(repo: str, token: str) -> bool:
    switch = api(repo, "/repos/pl0n3r/Factory/issues/767", token)
    if not isinstance(switch, dict) or (
        switch.get("number") != 767
        or switch.get("state") != "closed"
        or switch.get("url") != "https://api.github.com/repos/pl0n3r/Factory/issues/767"
        or switch.get("repository_url") != "https://api.github.com/repos/pl0n3r/Factory"
        or (switch.get("user") or {}).get("login") != "pl0n3r"
    ):
        return False
    body = switch.get("body")
    if not isinstance(body, str):
        return False
    if len(re.findall(r"<!--\s*factory-unattended-kill-switch\b", body, re.I)) != 1:
        return False
    markers = re.findall(r"<!--\s*factory-unattended-kill-switch\s+(\{.*?\})\s*-->", body)
    if len(markers) != 1:
        return False
    def unique_fields(pairs: list[tuple[str, object]]) -> dict:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Marker con clave duplicada")
            result[key] = value
        return result

    try:
        marker = json.loads(markers[0], object_pairs_hook=unique_fields)
    except ValueError:
        return False
    return (
        isinstance(marker, dict)
        and set(marker) == {"version", "state", "owner"}
        and type(marker["version"]) is int
        and marker["version"] == 1
        and marker["state"] == "RUNNING"
        and marker["owner"] == "pl0n3r"
    )


def create_followup(repo: str, number: int, head: str, token: str, *, reason: str, paths: list[str], major_target: str | None = None) -> int:
    """Issue idempotente; no conceder autorización de implementación desde metadata de PR."""
    if reason not in ("major", "workflow", "stale"):
        raise LaneError("Motivo inválido de escalamiento")
    if not paths or len(paths) > 3000 or len(set(paths)) != len(paths):
        raise LaneError("Claims de Dependabot ausentes o ambiguos")
    for path in paths:
        # Hereda exactamente el mismo allowlist ya validado sobre el HEAD;
        # sin asumir que una extensión manifest autoriza código.
        if not isinstance(path, str) or len(path) > 300 or (
            not WORKFLOW_PATH.fullmatch(path)
            and not (path.split("/")[-1] in MANIFESTS or REQUIREMENTS.fullmatch(path.split("/")[-1]))
        ):
            raise LaneError("Claim de seguimiento fuera de alcance")
    marker = (
        '<!-- factory-dependabot-followup '
        + json.dumps({"version": 1, "repo": repo, "pr": number}, sort_keys=True, separators=(",", ":"))
        + ' -->'
    )
    q = quote(f'repo:{repo} is:issue "factory-dependabot-followup" in:body', safe="")
    response = api(repo, "/search/issues?q=" + q + "&per_page=100", token)
    if not isinstance(response, dict) or response.get("incomplete_results") is not False:
        raise LaneError("Search Issues no verificable")
    count, items = response.get("total_count"), response.get("items")
    if type(count) is not int or count > 100 or not isinstance(items, list) or len(items) != count:
        raise LaneError("Search Issues truncado")
    for item in items:
        if isinstance(item, dict) and marker in (item.get("body") or ""):
            issue_number = item.get("number")
            if type(issue_number) is not int:
                raise LaneError("Issue de seguimiento inválido")
            return issue_number
    title = (
        f"Actualizar {major_target or 'dependencias'} (Dependabot PR #{number})"
        if reason == "major" else
        f"Revisar workflow de dependencias (Dependabot PR #{number})"
        if reason == "workflow" else
        f"Desbloquear Dependabot sin CI verde tras 7 días (PR #{number})"
    )
    body = (
        f"{marker}\n\nOrigen: https://github.com/{repo}/pull/{number}\n"
        f"HEAD observado: {head}\nMotivo: {reason}.\n\n"
        "Requiere revisión y contrato ejecutable antes de la reserva/implementación. "
        "No hereda ninguna exención de CI, seguridad, datos ni release.\n\n"
        "### Contexto\nDependabot no debe fusionar este cambio automáticamente.\n"
        "### Alcance\nClasificar la actualización, obtener pruebas y resolver el PR.\n"
        "### Fuera de alcance\nOmitir branch protection o checks de calidad.\n"
        "### Criterios de aceptación\n- [ ] [AC-01] Actualización revisada y checks requeridos verdes.\n"
        "\n### Contrato ejecutable\n"
        '<!-- factory-acceptance {"version":1,"criteria":[{"id":"AC-01","kind":"check","target":"Validar"}]} -->\n'
        "\n### Rutas reclamadas\n"
        + "".join(f"- `{path}`\n" for path in paths)
        + "\n<!-- factory-plan-task "
        + json.dumps({
            "version": 1, "epic": 1, "task_key": f"DEPENDABOT_PR_{number}",
            "order": number, "owner": "pl0n3r", "roles": ["seguridad", "qa"],
            "depends_on": [], "paths": paths,
        }, sort_keys=True, separators=(",", ":"))
        + " -->\n"
    )
    issue = api(repo, f"/repos/{repo}/issues", token, method="POST", payload={
        "title": title, "body": body,
        "labels": ["tipo: mejora", "prioridad: media", "estado: disponible", "rol: seguridad", "rol: qa"],
    })
    number_created = issue.get("number") if isinstance(issue, dict) else None
    if type(number_created) is not int:
        raise LaneError("Issue de seguimiento no confirmado")
    return number_created


def comment_stale(repo: str, number: int, issue: int, token: str) -> bool:
    """Anotar una vez el bloqueo real, sin generar mensajes diarios duplicados."""
    marker = f"<!-- factory-dependabot-stale:pr-{number} -->"
    prefix = f"/repos/{repo}/issues/{number}"
    for page in range(1, 11):
        rows = api(repo, f"{prefix}/comments?per_page=100&page={page}", token)
        if not isinstance(rows, list):
            raise LaneError("Comentarios de PR incompletos")
        if any(isinstance(item, dict) and marker in (item.get("body") or "") for item in rows):
            return False
        if len(rows) < 100:
            break
    else:
        raise LaneError("Demasiados comentarios para deduplicar")
    body = (
        f"{marker}\n"
        f"Dependabot lleva más de 7 días sin todos los checks terminales en verde. "
        f"Seguimiento canónico: https://github.com/{repo}/issues/{issue}. "
        "Se requiere resolver el CI y revisar los cambios; no se aplicó auto-merge."
    )
    api(repo, prefix + "/comments", token, method="POST", payload={"body": body})
    return True


def sweep(repo: str, token: str, *, now: datetime) -> list[dict]:
    """Barrido acotado y explícito; no crea leases ni ejecuta código de PRs."""
    if os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        raise LaneError("Barrido no autorizado fuera de schedule")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise LaneError("Barrido fuera de main")
    if not _switch_running(repo, token):
        raise LaneError("Interruptor global distinto de RUNNING")
    result: list[dict] = []
    for page in range(1, 11):
        rows = api(repo, f"/repos/{repo}/pulls?state=open&per_page=100&page={page}", token)
        if not isinstance(rows, list) or len(rows) > 100:
            raise LaneError("Inventario de PRs no verificable")
        for item in rows:
            if not isinstance(item, dict):
                raise LaneError("PR de inventario ilegible")
            user = item.get("user")
            if not isinstance(user, dict):
                raise LaneError("Identidad de PR incompleta")
            if user.get("login") != "dependabot[bot]":
                continue
            number = item.get("number")
            head = (item.get("head") or {}).get("sha")
            if type(number) is not int or not isinstance(head, str) or not HEX_SHA.fullmatch(head):
                raise LaneError("PR Dependabot de inventario sin HEAD")
            result.append(reconcile(repo, number, head, token, now=now))
        if len(rows) < 100:
            break
    else:
        raise LaneError("Inventario de PRs excede límite verificable")
    return result


def reconcile(repo: str, number: int, head: str, token: str, *, now: datetime) -> dict:
    """Privilegiado: solo desde workflow_run sobre main, jamás checkout de PR."""
    if os.environ.get("GITHUB_EVENT_NAME") not in ("workflow_run", "schedule"):
        raise LaneError("Mutación requiere workflow_run/schedule confiable")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise LaneError("Mutación fuera de main")
    pr, result = read_exact(repo, number, head, token)
    if not result.get("dependabot"):
        # El workflow_run de Factory también recibe CI de PRs humanos:
        # conservar su flujo intacto sin crear checks rojos artificiales.
        return {"dependabot": False, "skipped": True, "auto_merge_enabled": False}
    if not _switch_running(repo, token):
        raise LaneError("Interruptor global distinto de RUNNING")
    # Las majors y los cambios de workflow deben abrir seguimiento aun si
    # los checks faltan o están rojos. Nunca dependen de un verde para escalar.
    if result["policy"] == "manual":
        reason = "major" if result["major"] else "workflow"
        issue = create_followup(repo, number, head, token, reason=reason, paths=result["file_paths"], major_target=result.get("major_target"))
        if _age_over_seven_days(pr, now=now):
            try:
                green_manual = _terminal_checks_green(repo, head, token)
            except LaneError:
                green_manual = False
            if not green_manual:
                comment_stale(repo, number, issue, token)
        return {**result, "auto_merge_enabled": False, "followup_required": True, "issue": issue, "reason": reason}
    # Una indisponibilidad de los checks impide merge, pero si el PR supera
    # siete días habilita solo un seguimiento auditable.
    check_error = None
    try:
        green = _terminal_checks_green(repo, head, token)
    except LaneError as exc:
        check_error = str(exc)
        green = False
    if check_error and not _age_over_seven_days(pr, now=now):
        raise LaneError("Evidencia de checks desconocida; no autorizar merge")
    if result["policy"] == "auto" and green:
        # Se usa la política de auto-merge de GitHub, jamás un merge directo
        # o --admin. La protección de rama mantiene su propia autoridad.
        latest, last_result = read_exact(repo, number, head, token)
        if last_result != result or not _terminal_checks_green(repo, head, token):
            raise LaneError("Evidencia de PR/checks cambió antes de auto-merge")
        if not _switch_running(repo, token):
            raise LaneError("Interruptor global cambió antes del squash")
        # El workflow_run se dispara tras finalizar los checks: habilitar
        # GitHub auto-merge en un PR ya mergeable puede fallar (no hay
        # requisitos pendientes). Ejecutar el squash normal con expected SHA,
        # sin usar --admin ni APIs que omitan branch protection.
        response = api(repo, f"/repos/{repo}/pulls/{number}/merge", token,
                       method="PUT", payload={"sha": head, "merge_method": "squash"})
        if not isinstance(response, dict) or response.get("merged") is not True:
            raise LaneError("GitHub no confirmó el squash protegido")
        merged_sha = response.get("sha")
        if not isinstance(merged_sha, str) or not HEX_SHA.fullmatch(merged_sha):
            raise LaneError("Squash sin SHA verificable")
        return {**result, "merged": True, "merge_sha": merged_sha,
                "auto_merge_enabled": False, "followup_required": False}
    if _age_over_seven_days(pr, now=now) and not green:
        issue = create_followup(repo, number, head, token, reason="stale", paths=result["file_paths"])
        comment_stale(repo, number, issue, token)
        return {**result, "auto_merge_enabled": False, "followup_required": True,
                "issue": issue, "reason": "stale"}
    return {**result, "auto_merge_enabled": False, "followup_required": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("classify", "reconcile", "sweep"))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", type=int)
    parser.add_argument("--head")
    args = parser.parse_args(argv)
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        print("ERROR: token de solo lectura no disponible", file=sys.stderr)
        return 1
    try:
        if args.command == "sweep":
            result = sweep(args.repo, token, now=datetime.now(timezone.utc))
            print(json.dumps({"swept": len(result), "results": result}, sort_keys=True))
            return 0
        if args.pr is None or args.head is None:
            raise LaneError("PR y HEAD obligatorios")
        if args.command == "classify":
            result = classify_from_api(args.repo, args.pr, args.head, token)
            print(json.dumps(result, sort_keys=True))
            return 0 if result.get("dependabot") else 20
        result = reconcile(args.repo, args.pr, args.head, token, now=datetime.now(timezone.utc))
        print(json.dumps(result, sort_keys=True))
        return 0
    except LaneError as exc:
        print("ERROR carril Dependabot: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Valida criterios de aceptación ejecutables vinculados a un Issue."""
from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__:
    from scripts.safe_io import SafeIOError, resolve_repo_file
else:
    from safe_io import SafeIOError, resolve_repo_file

MARKER = "factory-acceptance"
MAX_INPUT = 3_000_000
MAX_BODY = 200_000
MAX_CRITERIA = 20
REQUIRED_HEADINGS = (
    "### Contexto",
    "### Alcance",
    "### Fuera de alcance",
    "### Criterios de aceptación",
    "### Contrato ejecutable",
)
CRITERION_LINE = re.compile(
    r"^- \[[ xX]\] \[(AC-[0-9]{2})\] (.{1,500})$"
)
TEST_TARGET = re.compile(
    r"^((?:tests|metricas|seguridad|lecciones|producto)/"
    r"test_[A-Za-z0-9_/-]+\.py)::"
    r"([A-Za-z_][A-Za-z0-9_]*)::"
    r"(test_[A-Za-z0-9_]+)$"
)
CHECK_NAME = re.compile(r"^[^\r\n]{1,120}$")
FORBIDDEN_CHECKS = {"Validar", "Criterios de aceptación"}


class AcceptanceError(ValueError):
    pass


@dataclass(frozen=True)
class Criterion:
    id: str
    kind: str
    target: str


def _extract_marker(body: str) -> str:
    prefix = f"<!-- {MARKER} "
    suffix = " -->"
    count = body.count(prefix)
    if count != 1:
        raise AcceptanceError(
            "Debe existir exactamente un marker factory-acceptance."
        )
    start = body.index(prefix) + len(prefix)
    end = body.find(suffix, start)
    if end < 0:
        raise AcceptanceError("Marker factory-acceptance malformado.")
    return body[start:end].strip()


def _section(body: str, heading: str) -> str:
    lines = body.splitlines()
    indexes = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(indexes) != 1:
        raise AcceptanceError(f"Sección obligatoria inválida: {heading}.")
    start = indexes[0] + 1
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("### "):
            end = index
            break
    content = "\n".join(lines[start:end]).strip()
    if not content:
        raise AcceptanceError(f"Sección obligatoria vacía: {heading}.")
    return content


def _human_criteria(body: str) -> dict[str, str]:
    section = _section(body, "### Criterios de aceptación")
    criteria: dict[str, str] = {}
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- ["):
            continue
        match = CRITERION_LINE.fullmatch(stripped)
        if not match:
            raise AcceptanceError(
                "Cada criterio debe usar - [ ] [AC-NN] descripción."
            )
        criterion_id, description = match.groups()
        if criterion_id in criteria:
            raise AcceptanceError("IDs AC-* duplicados.")
        criteria[criterion_id] = description.strip()
    if not 1 <= len(criteria) <= MAX_CRITERIA:
        raise AcceptanceError(
            f"Se requieren entre 1 y {MAX_CRITERIA} criterios AC-*."
        )
    return criteria


def _machine_criteria(body: str) -> list[Criterion]:
    payload = _extract_marker(body)
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AcceptanceError("factory-acceptance contiene JSON inválido.") from exc
    if not isinstance(raw, dict) or set(raw) != {"version", "criteria"}:
        raise AcceptanceError(
            "factory-acceptance debe contener exactamente version y criteria."
        )
    if raw["version"] != 1:
        raise AcceptanceError("factory-acceptance requiere version=1.")
    rows = raw["criteria"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_CRITERIA:
        raise AcceptanceError("criteria debe ser una lista acotada.")

    result: list[Criterion] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "kind", "target"}:
            raise AcceptanceError(
                "Cada criterio máquina requiere id, kind y target."
            )
        criterion_id = row["id"]
        kind = row["kind"]
        target = row["target"]
        if (
            not isinstance(criterion_id, str)
            or not re.fullmatch(r"AC-[0-9]{2}", criterion_id)
            or criterion_id in seen
        ):
            raise AcceptanceError("ID máquina inválido o duplicado.")
        if kind not in {"test", "check"} or not isinstance(target, str):
            raise AcceptanceError("kind/target inválidos.")
        if kind == "test":
            match = TEST_TARGET.fullmatch(target)
            if not match:
                raise AcceptanceError(
                    f"{criterion_id}: target de test fuera del contrato."
                )
            path = Path(match.group(1))
            if (
                path.is_absolute()
                or ".." in path.parts
                or any(part in ("", ".") for part in path.parts)
            ):
                raise AcceptanceError(
                    f"{criterion_id}: ruta de test no canónica."
                )
        else:
            if not CHECK_NAME.fullmatch(target) or target in FORBIDDEN_CHECKS:
                raise AcceptanceError(
                    f"{criterion_id}: check inválido o autorreferencial."
                )
        seen.add(criterion_id)
        result.append(Criterion(criterion_id, kind, target))
    return result


def parse_contract(body: str) -> list[Criterion]:
    if not isinstance(body, str) or not 1 <= len(body) <= MAX_BODY:
        raise AcceptanceError("Body del Issue inválido o demasiado grande.")
    for heading in REQUIRED_HEADINGS:
        _section(body, heading)
    human = _human_criteria(body)
    machine = _machine_criteria(body)
    machine_ids = {criterion.id for criterion in machine}
    if set(human) != machine_ids:
        missing_machine = sorted(set(human) - machine_ids)
        missing_human = sorted(machine_ids - set(human))
        details: list[str] = []
        if missing_machine:
            details.append(
                "sin evidencia máquina: " + ", ".join(missing_machine)
            )
        if missing_human:
            details.append(
                "sin criterio humano: " + ", ".join(missing_human)
            )
        raise AcceptanceError(
            "IDs humanos y máquina no coinciden"
            + (": " + "; ".join(details) if details else ".")
        )
    return machine


def _latest_checks(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise AcceptanceError("Payload de checks inválido.")
    runs = payload.get("check_runs")
    if not isinstance(runs, list) or len(runs) > 500:
        raise AcceptanceError("check_runs debe ser una lista acotada.")
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        if not isinstance(run, dict):
            raise AcceptanceError("Check run inválido.")
        name = run.get("name")
        identifier = run.get("id")
        if (
            not isinstance(name, str)
            or not CHECK_NAME.fullmatch(name)
            or isinstance(identifier, bool)
            or not isinstance(identifier, int)
            or identifier < 1
        ):
            raise AcceptanceError("Check run fuera del contrato.")
        previous = latest.get(name)
        if previous is None or identifier > previous["id"]:
            latest[name] = run
    return latest


def verify_check(criterion: Criterion, checks: Any) -> None:
    latest = _latest_checks(checks)
    run = latest.get(criterion.target)
    if run is None:
        raise AcceptanceError(
            f"{criterion.id}: no existe check '{criterion.target}'."
        )
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise AcceptanceError(
            f"{criterion.id}: check '{criterion.target}' no terminó success."
        )


def _load_test_module(path: Path, root: Path) -> Any:
    try:
        safe_path = resolve_repo_file(path, root=root, max_bytes=2_000_000)
    except SafeIOError as exc:
        raise AcceptanceError("Archivo de test inseguro o inexistente.") from exc
    module_name = (
        "_factory_acceptance_"
        + "_".join(safe_path.relative_to(root.resolve()).with_suffix("").parts)
    )
    spec = importlib.util.spec_from_file_location(module_name, safe_path)
    if spec is None or spec.loader is None:
        raise AcceptanceError("No se pudo cargar el archivo de test.")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise AcceptanceError("El módulo de test falló al importarse.") from exc
    return module


def run_named_test(criterion: Criterion, root: Path) -> None:
    match = TEST_TARGET.fullmatch(criterion.target)
    if not match:
        raise AcceptanceError(f"{criterion.id}: target de test inválido.")
    path, class_name, method_name = match.groups()
    module = _load_test_module(Path(path), root)
    suite = unittest.TestLoader().loadTestsFromName(
        f"{class_name}.{method_name}",
        module,
    )
    stream = io.StringIO()
    result = unittest.TextTestRunner(
        stream=stream,
        verbosity=0,
    ).run(suite)
    if result.testsRun != 1 or not result.wasSuccessful():
        raise AcceptanceError(
            f"{criterion.id}: test '{criterion.target}' no pasó exactamente una vez."
        )


def verify_evidence(
    criteria: list[Criterion],
    checks: Any,
    *,
    root: Path | None = None,
) -> None:
    repo_root = (root or Path.cwd()).resolve()
    for criterion in criteria:
        if criterion.kind == "test":
            run_named_test(criterion, repo_root)
        else:
            verify_check(criterion, checks)


def validate_payload(payload: Any, *, root: Path | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"issue", "checks"}:
        raise AcceptanceError("Payload debe contener issue y checks.")
    issue = payload["issue"]
    if not isinstance(issue, dict):
        raise AcceptanceError("Issue inválido.")
    body = issue.get("body")
    if not isinstance(body, str):
        raise AcceptanceError("Issue sin body.")
    criteria = parse_contract(body)
    verify_evidence(criteria, payload["checks"], root=root)
    return {
        "criteria": len(criteria),
        "verified": [criterion.id for criterion in criteria],
    }


def main() -> int:
    raw = sys.stdin.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        print("ERROR: payload de aceptación demasiado grande.", file=sys.stderr)
        return 2
    try:
        payload = json.loads(raw)
        result = validate_payload(payload)
    except (json.JSONDecodeError, AcceptanceError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

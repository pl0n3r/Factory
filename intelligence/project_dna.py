"""Project DNA: huella determinista basada solo en señales explícitas del repositorio."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


DNA_VERSION = 1
UNKNOWN = "unknown"
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
BASE_FIELDS = {
    "version",
    "stack",
    "frameworks",
    "data",
    "ci",
    "hosting",
    "integrations",
    "capabilities",
    "signals",
    "extensions",
    "fingerprint",
}

KNOWN_STACK_SIGNALS = {
    "composer.json": "php",
    "package.json": "node",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "go.mod": "go",
    "Cargo.toml": "rust",
}
KNOWN_DATA_SIGNALS = {
    "database/": "sql",
    "migrations/": "sql",
    "prisma/schema.prisma": "prisma",
}
KNOWN_HOSTING_SIGNALS = {
    "vercel.json": "vercel",
    "netlify.toml": "netlify",
    "fly.toml": "fly.io",
    "render.yaml": "render",
}
FRAMEWORK_PACKAGE_HINTS = {
    "laravel/framework": "laravel",
    "symfony/framework-bundle": "symfony",
    "next": "nextjs",
    "react": "react",
    "vue": "vue",
    "fastify": "fastify",
    "express": "express",
    "django": "django",
    "flask": "flask",
}
_PYTHON_PACKAGE = re.compile(r"^[A-Za-z0-9_.-]+")


class ProjectDnaError(ValueError):
    """Señales o documento Project DNA inválidos."""


def _normalize_paths(paths: Any) -> tuple[str, ...]:
    if not isinstance(paths, (list, tuple, set)):
        raise ProjectDnaError("paths debe ser una colección")
    normalized = []
    for item in paths:
        if not isinstance(item, str) or not item.strip():
            raise ProjectDnaError("path inválido")
        path = item.strip().replace("\\", "/")
        if path.startswith("/") or ".." in path.split("/"):
            raise ProjectDnaError("path no permitido")
        normalized.append(path)
    return tuple(sorted(set(normalized)))


def _normalize_manifests(manifests: Any) -> dict[str, Any]:
    if manifests is None:
        return {}
    if not isinstance(manifests, dict):
        raise ProjectDnaError("manifests debe ser objeto")
    result: dict[str, Any] = {}
    for name, value in manifests.items():
        if not isinstance(name, str) or not name:
            raise ProjectDnaError("manifest name inválido")
        if name not in {"composer.json", "package.json", "pyproject.toml"}:
            continue
        if not isinstance(value, dict):
            raise ProjectDnaError("manifest conocido debe ser objeto")
        result[name] = value
    return result


def _detect_stack(paths: tuple[str, ...]) -> list[str] | str:
    detected = sorted(
        {
            stack
            for signal, stack in KNOWN_STACK_SIGNALS.items()
            if signal in paths
        }
    )
    return detected if detected else UNKNOWN


def _python_dependency_name(raw: str) -> str | None:
    match = _PYTHON_PACKAGE.match(raw.strip())
    return match.group(0).lower() if match else None


def _package_names(manifests: dict[str, Any]) -> set[str]:
    packages: set[str] = set()
    composer = manifests.get("composer.json")
    if composer:
        for section in ("require", "require-dev"):
            values = composer.get(section, {})
            if isinstance(values, dict):
                packages.update(str(k).lower() for k in values)
    package = manifests.get("package.json")
    if package:
        for section in ("dependencies", "devDependencies"):
            values = package.get(section, {})
            if isinstance(values, dict):
                packages.update(str(k).lower() for k in values)
    pyproject = manifests.get("pyproject.toml")
    if pyproject:
        project = pyproject.get("project", {})
        deps = project.get("dependencies", []) if isinstance(project, dict) else []
        if isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, str):
                    name = _python_dependency_name(dep)
                    if name:
                        packages.add(name)
    return packages


def _detect_frameworks(manifests: dict[str, Any]) -> list[str] | str:
    packages = _package_names(manifests)
    detected = sorted(
        {
            framework
            for package, framework in FRAMEWORK_PACKAGE_HINTS.items()
            if package in packages
        }
    )
    return detected if detected else UNKNOWN


def _detect_ci(paths: tuple[str, ...]) -> list[str] | str:
    detected: set[str] = set()
    for path in paths:
        if path.startswith(".github/workflows/"):
            detected.add("github-actions")
        if path == ".gitlab-ci.yml":
            detected.add("gitlab-ci")
        if path == "Jenkinsfile":
            detected.add("jenkins")
    return sorted(detected) if detected else UNKNOWN


def _detect_data(paths: tuple[str, ...]) -> list[str] | str:
    detected = sorted(
        {
            kind
            for signal, kind in KNOWN_DATA_SIGNALS.items()
            if signal in paths or any(path.startswith(signal) for path in paths)
        }
    )
    return detected if detected else UNKNOWN


def _detect_hosting(paths: tuple[str, ...]) -> list[str] | str:
    detected = sorted(
        {
            provider
            for signal, provider in KNOWN_HOSTING_SIGNALS.items()
            if signal in paths
        }
    )
    return detected if detected else UNKNOWN


def _detect_integrations(paths: tuple[str, ...]) -> list[str] | str:
    integrations: set[str] = set()
    lowered = [path.lower() for path in paths]
    if any("sentry" in path for path in lowered):
        integrations.add("sentry")
    if any("stripe" in path for path in lowered):
        integrations.add("stripe")
    if any("github" in path for path in lowered):
        integrations.add("github")
    return sorted(integrations) if integrations else UNKNOWN


def _fingerprint_payload(document: dict[str, Any]) -> str:
    payload = {k: v for k, v in document.items() if k != "fingerprint"}
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def discover_project_dna(
    *,
    paths: Any,
    manifests: Any = None,
    capabilities: Any = None,
) -> dict[str, Any]:
    """Construye Project DNA sin inferir más allá de señales verificables."""
    normalized_paths = _normalize_paths(paths)
    normalized_manifests = _normalize_manifests(manifests)

    if capabilities is None:
        normalized_capabilities: list[str] | str = UNKNOWN
    elif isinstance(capabilities, (list, tuple, set)) and all(
        isinstance(item, str) and item.strip() for item in capabilities
    ):
        normalized_capabilities = sorted(
            set(item.strip() for item in capabilities)
        )
    else:
        raise ProjectDnaError("capabilities inválidas")

    dna = {
        "version": DNA_VERSION,
        "stack": _detect_stack(normalized_paths),
        "frameworks": _detect_frameworks(normalized_manifests),
        "data": _detect_data(normalized_paths),
        "ci": _detect_ci(normalized_paths),
        "hosting": _detect_hosting(normalized_paths),
        "integrations": _detect_integrations(normalized_paths),
        "capabilities": normalized_capabilities,
        "signals": {
            "paths": list(normalized_paths),
            "manifests": sorted(normalized_manifests),
        },
        "extensions": {},
    }
    dna["fingerprint"] = _fingerprint_payload(dna)
    return dna


def _validate_known_or_list(value: Any, field: str) -> None:
    if value == UNKNOWN:
        return
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
        or value != sorted(set(value))
    ):
        raise ProjectDnaError(f"{field} inválido")


def validate_project_dna(document: Any) -> dict[str, Any]:
    """Valida campos base v1 permitiendo futuras extensiones aisladas."""
    if not isinstance(document, dict):
        raise ProjectDnaError("Project DNA debe ser objeto")
    if set(document) != BASE_FIELDS:
        raise ProjectDnaError("campos base incompletos o adicionales")
    if type(document["version"]) is not int or document["version"] != DNA_VERSION:
        raise ProjectDnaError("versión no admitida")

    for field in (
        "stack",
        "frameworks",
        "data",
        "ci",
        "hosting",
        "integrations",
        "capabilities",
    ):
        _validate_known_or_list(document[field], field)

    signals = document["signals"]
    if (
        not isinstance(signals, dict)
        or set(signals) != {"paths", "manifests"}
        or not isinstance(signals["paths"], list)
        or not isinstance(signals["manifests"], list)
        or signals["paths"] != sorted(set(signals["paths"]))
        or signals["manifests"] != sorted(set(signals["manifests"]))
        or not all(isinstance(item, str) and item for item in signals["paths"])
        or not all(isinstance(item, str) and item for item in signals["manifests"])
    ):
        raise ProjectDnaError("signals inválidas")
    if not isinstance(document["extensions"], dict):
        raise ProjectDnaError("extensions debe ser objeto")
    if (
        not isinstance(document["fingerprint"], str)
        or FINGERPRINT_RE.fullmatch(document["fingerprint"]) is None
    ):
        raise ProjectDnaError("fingerprint inválido")
    if _fingerprint_payload(document) != document["fingerprint"]:
        raise ProjectDnaError("fingerprint no coincide")
    return document

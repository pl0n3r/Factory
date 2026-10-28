#!/usr/bin/env python3
"""Clasifica escalaciones que sí requieren decisión del dueño."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any

MARKER_NAME = "factory-human-gate"
MARKER_RE = re.compile(
    r"<!--\s*factory-human-gate\s+(\{.*?\})\s*-->",
    re.DOTALL,
)
MARKER_INTENT_RE = re.compile(r"<!--\s*factory-human-gate\b")
CATEGORIES = {
    "product-direction",
    "brand",
    "money",
    "legal",
    "real-customer-data",
    "release-1.0.0",
    "factory-release",
    "go-live",
}
REQUIRED = {"category", "context", "options", "recommendation", "safe_default"}
OPTIONAL_SIMPLE = {
    "title_simple",
    "summary_simple",
    "why_recommended",
    "blocks",
    "explain_simple",
}
OPTIONAL_OPTION = {
    "effect",
    "pros",
    "cons",
    "risk",
    "cost",
    "reversible",
    "explain_simple",
}
OPTION_ID_RE = re.compile(r"^[A-D]$")
RISK_VALUES = {"low", "medium", "high"}
MAX_EVENT_CHARS = 200_000
MAX_ISSUE_BODY_CHARS = 65_536
MAX_LIST_ITEMS = 5


class GateValidationError(ValueError):
    pass


def _result(
    status: str,
    category: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    result = {"status": status, "category": category}
    if reason is not None:
        result["reason"] = reason
    return result


def _line(value: Any, field: str, max_len: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise GateValidationError(f"{field} debe ser texto.")
    normalized = value.strip()
    if (
        (not normalized and not allow_empty)
        or len(normalized) > max_len
        or "\n" in value
        or "\r" in value
    ):
        suffix = "0" if allow_empty else "1"
        raise GateValidationError(
            f"{field} debe ser texto de una línea, {suffix}..{max_len} caracteres."
        )
    return normalized


def _short_text(value: Any, field: str, max_len: int, max_lines: int) -> str:
    if not isinstance(value, str):
        raise GateValidationError(f"{field} debe ser texto.")
    normalized = value.strip()
    if not normalized or len(normalized) > max_len or "\r" in value:
        raise GateValidationError(
            f"{field} debe contener 1..{max_len} caracteres."
        )
    if len(normalized.split("\n")) > max_lines:
        raise GateValidationError(
            f"{field} debe contener como máximo {max_lines} líneas."
        )
    return normalized


def _line_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_LIST_ITEMS:
        raise GateValidationError(
            f"{field} debe contener entre 1 y {MAX_LIST_ITEMS} elementos."
        )
    return [_line(item, field, 180) for item in value]


# La redacción simple de puertas NUEVAS es más estricta que la compatibilidad
# histórica del marker. Los campos de autoridad nunca se reescriben.
PLAIN_LANGUAGE_JARGON = re.compile(
    r"(?i)(?<!\w)(?:exact[-\s]?main|exact[-\s]?head|fail[-\s]?closed|"
    r"v3|d-0\d*|journal|sha|idempot\w*)(?!\w)|"
    r"(?<!\w)main@[a-f0-9]{8,40}(?!\w)|#\d+"
)
PLAIN_LANGUAGE_WORD_RE = re.compile(r"\w+(?:[-'’]\w+)*", re.UNICODE)
PLAIN_LANGUAGE_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _validate_plain_language(text: str, field: str) -> None:
    """Valida solo copia explicativa; nunca incluye texto del usuario en errores."""
    if PLAIN_LANGUAGE_JARGON.search(text):
        raise GateValidationError(f"{field} contiene jerga técnica prohibida.")
    for sentence in PLAIN_LANGUAGE_SENTENCE_RE.split(text):
        if len(PLAIN_LANGUAGE_WORD_RE.findall(sentence)) > 25:
            raise GateValidationError(
                f"{field} contiene una oración de más de 25 palabras."
            )


def _validate_new_gate_plain_language(
    raw: dict[str, Any],
    normalized: dict[str, Any],
) -> None:
    """Exige lenguaje simple al formato completo sin invalidar puertas legacy.

    El formato completo añade explain_simple en raíz y TODAS las opciones.
    Puertas ya publicadas sin ese contrato conservan su identidad histórica,
    incluso si contienen identificadores técnicos en campos opcionales.
    """
    options = raw.get("options")
    if (
        not isinstance(raw.get("explain_simple"), str)
        or not isinstance(options, list)
        or not options
        or any(
            not isinstance(option, dict)
            or not isinstance(option.get("explain_simple"), str)
            for option in options
        )
    ):
        return

    for field in (
        "title_simple", "summary_simple", "explain_simple", "why_recommended"
    ):
        if field in normalized:
            _validate_plain_language(normalized[field], field)

    for index, option in enumerate(normalized["options"]):
        for field in ("label", "effect", "explain_simple", "cost"):
            if field in option:
                _validate_plain_language(option[field], f"options[{index}].{field}")
        for field in ("pros", "cons"):
            for value in option.get(field, []):
                _validate_plain_language(value, f"options[{index}].{field}")


def _validate_simple_root(raw: dict[str, Any], normalized: dict[str, Any]) -> None:
    if "title_simple" in raw:
        normalized["title_simple"] = _line(
            raw["title_simple"], "title_simple", 180
        )
    if "summary_simple" in raw:
        normalized["summary_simple"] = _short_text(
            raw["summary_simple"], "summary_simple", 600, 3
        )
    if "why_recommended" in raw:
        normalized["why_recommended"] = _line(
            raw["why_recommended"], "why_recommended", 300
        )
    if "blocks" in raw:
        normalized["blocks"] = _line(raw["blocks"], "blocks", 300)
    if "explain_simple" in raw:
        normalized["explain_simple"] = _short_text(
            raw["explain_simple"], "explain_simple", 600, 4
        )


def _option_risk(value: Any) -> str:
    risk = _line(value, "option.risk", 16)
    if risk not in RISK_VALUES:
        raise GateValidationError(
            "option.risk debe ser low, medium o high."
        )
    return risk


def _validate_option(item: Any, seen: set[str]) -> dict[str, Any]:
    allowed = {"id", "label"} | OPTIONAL_OPTION
    if not isinstance(item, dict) or not {"id", "label"}.issubset(item):
        raise GateValidationError(
            "Cada option debe contener al menos id y label."
        )
    if not set(item).issubset(allowed):
        raise GateValidationError(
            "Cada option contiene campos no permitidos."
        )

    option_id = _line(item["id"], "option.id", 1)
    label = _line(item["label"], "option.label", 240)
    if not OPTION_ID_RE.fullmatch(option_id) or option_id in seen:
        raise GateValidationError("option.id debe ser único y usar A..D.")
    seen.add(option_id)

    normalized: dict[str, Any] = {"id": option_id, "label": label}
    if "effect" in item:
        normalized["effect"] = _line(item["effect"], "option.effect", 300)
    if "pros" in item:
        normalized["pros"] = _line_list(item["pros"], "option.pros")
    if "cons" in item:
        normalized["cons"] = _line_list(item["cons"], "option.cons")
    if "risk" in item:
        normalized["risk"] = _option_risk(item["risk"])
    if "cost" in item:
        normalized["cost"] = _line(
            item["cost"], "option.cost", 120, allow_empty=True
        )
    if "explain_simple" in item:
        normalized["explain_simple"] = _short_text(
            item["explain_simple"], "option.explain_simple", 400, 3
        )
    if "reversible" in item:
        if type(item["reversible"]) is not bool:
            raise GateValidationError("option.reversible debe ser booleano.")
        normalized["reversible"] = item["reversible"]
    return normalized


def validate_gate(raw: Any, *, historical: bool = False) -> dict[str, Any]:
    allowed = REQUIRED | OPTIONAL_SIMPLE
    if (
        not isinstance(raw, dict)
        or not REQUIRED.issubset(raw)
        or not set(raw).issubset(allowed)
    ):
        raise GateValidationError(
            "La puerta requiere category, context, options, recommendation y "
            "safe_default; solo admite además los campos simples documentados."
        )

    category = _line(raw["category"], "category", 80)
    if category not in CATEGORIES:
        raise GateValidationError(
            "category no pertenece a la lista cerrada de decisiones del dueño."
        )

    context = _line(raw["context"], "context", 500)
    options = raw["options"]
    if not isinstance(options, list) or not 2 <= len(options) <= 4:
        raise GateValidationError("options debe contener entre 2 y 4 opciones.")

    normalized_options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in options:
        normalized_options.append(_validate_option(item, seen))

    recommendation = _line(raw["recommendation"], "recommendation", 1)
    safe_default = _line(raw["safe_default"], "safe_default", 1)
    if recommendation not in seen or safe_default not in seen:
        raise GateValidationError(
            "recommendation y safe_default deben referir una option existente."
        )

    normalized: dict[str, Any] = {
        "category": category,
        "context": context,
        "options": normalized_options,
        "recommendation": recommendation,
        "safe_default": safe_default,
    }
    _validate_simple_root(raw, normalized)
    # La regla editorial rige para entradas NUEVAS. Lecturas históricas conservan
    # estructura, opciones y autoridad aun cuando su copia anterior use jerga.
    if not historical:
        _validate_new_gate_plain_language(raw, normalized)
    return normalized


FACTORY_RELEASE_TARGET_RE = re.compile(
    r"\b(?:Factory\s+)?v?(\d+\.\d+\.\d+)\b.*?\bmain@([0-9a-f]{40})\b",
    re.IGNORECASE,
)


def _digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _gate_target(gate: dict[str, Any]) -> dict[str, Any]:
    category = gate["category"]
    context = gate["context"]
    if category == "factory-release":
        match = FACTORY_RELEASE_TARGET_RE.search(context)
        if match:
            return {
                "category": category,
                "target": {
                    "version": match.group(1),
                    "sha": match.group(2).lower(),
                },
            }
    # Sin target exacto demostrable no se colapsan contextos distintos.
    return {
        "category": category,
        "target": {"context": " ".join(context.split())},
    }



# Los motivos no son autoridad legal: solo distinguen objetivos de puertas
# canónicas del auditor de privacidad. Nada aquí aprueba el tratamiento.
_PRIVACY_MATERIAL_MARKER = "<!-- factory-privacy-material -->"
_PRIVACY_REASON_RE = re.compile(
    r"^- \x60([a-z][a-z0-9_]{0,99}:(?:new_provider|purpose))\x60$"
)
_PRIVACY_PRODUCT_RE = re.compile(
    r"^Producto: \x60([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\x60$"
)

_PRIVACY_PRODUCTS = frozenset({
    "pl0n3r/Factory", "pl0n3r/Condor", "pl0n3r/GrindFlow",
    "pl0n3r/brvtal", "pl0n3r/ControlBot", "pl0n3r/AutoFactory",
    "pl0n3r/FactoryRunner",
})
_PRIVACY_LABELS = {
    "A": "Solicitar revisión jurídica antes de aprobar la documentación",
    "B": "Continuar en construcción manteniendo documented_not_legally_approved",
    "C": "Mantener el cambio bloqueado hasta completar la revisión jurídica",
}


def _privacy_target_from_body(
    body: str, gate: dict[str, Any],
) -> dict[str, Any] | None:
    """Desambigua motivos estructurados sin alterar opciones ni autoridad."""
    if "factory-privacy-material" not in body:
        return None
    prefix = (
        _PRIVACY_MATERIAL_MARKER
        + "\n## Cambio material de privacidad\n\n"
    )
    if (
        gate["category"] != "legal"
        or body.count(_PRIVACY_MATERIAL_MARKER) != 1
        or body.count("<!--") != 2
        or body.count("-->") != 2
        or not body.startswith(prefix)
    ):
        raise GateValidationError("Puerta de privacidad material inválida.")
    product_line, separator, tail = body[len(prefix):].partition(
        "\n\nMotivos estructurados:\n"
    )
    product_match = _PRIVACY_PRODUCT_RE.fullmatch(product_line)
    if not separator or product_match is None or product_match.group(1) not in _PRIVACY_PRODUCTS:
        raise GateValidationError("Producto legal no verificable.")
    product = product_match.group(1)
    reason_text, separator, end = tail.partition(
        "\n\nLa documentación permanece en estado "
    )
    reasons = reason_text.split("\n")
    match_reasons = [_PRIVACY_REASON_RE.fullmatch(row) for row in reasons]
    if (
        not separator
        or not 1 <= len(reasons) <= 20
        or any(match is None for match in match_reasons)
        or len(set(reasons)) != len(reasons)
        or "\n\n<!-- factory-human-gate " not in end
    ):
        raise GateValidationError("Motivos jurídicos inválidos.")
    reason_values = sorted(match.group(1) for match in match_reasons)
    statement, separator, raw_marker = end.partition(
        "\n\n<!-- factory-human-gate "
    )
    if not separator or " -->" not in raw_marker:
        raise GateValidationError("Estructura legal incompleta.")
    options = gate["options"]
    identifiers = {option["id"] for option in options}
    if (
        len(options) != 2
        or identifiers not in ({"A", "B"}, {"A", "C"})
        or gate["recommendation"] != "A"
        or set(gate) - {
            "category", "context", "options", "recommendation",
            "safe_default", "explain_simple",
        }
        or any(
            set(option) - {"id", "label", "explain_simple"}
            or option["label"] != _PRIVACY_LABELS[option["id"]]
            for option in options
        )
    ):
        raise GateValidationError("Contrato jurídico de privacidad inválido.")
    strict = identifiers == {"A", "C"}
    expected_context = (
        f"{product}: la auditoría detectó {len(reasons)} "
        "cambio(s) material(es) de privacidad"
        + (
            " fuera de las condiciones de D-063; requieren revisión jurídica "
            "antes de continuar hacia live."
            if strict else " que requieren decisión jurídica humana."
        )
    )
    expected_statement = (
        ("`documented_not_legally_approved`. Esta puerta es bloqueante: "
         "D-063 no aplica y se exige revisión jurídica antes de "
         "continuar hacia live.")
        if strict else
        "`documented_not_legally_approved` hasta una decisión humana."
    )
    if (
        gate["context"] != expected_context
        or statement != expected_statement
        or gate["safe_default"] != ("A" if strict else "B")
    ):
        raise GateValidationError("Alcance de privacidad incongruente.")
    return {
        "category": "legal",
        "target": {
            "context": " ".join(gate["context"].split()),
            "product": product,
            "privacy_reasons": reason_values,
        },
    }


def gate_target_identity(raw: Any) -> str:
    """Identidad del objeto decidido, independiente del copy explicativo."""
    return _digest(_gate_target(validate_gate(raw)))


def gate_authority_contract(raw: Any, *, historical: bool = False) -> str:
    """Fingerprint de las opciones que realmente conceden autoridad."""
    gate = validate_gate(raw, historical=historical)
    target = _gate_target(gate)["target"]
    if (
        gate["category"] == "factory-release"
        and isinstance(target, dict)
        and set(target) == {"version", "sha"}
    ):
        options = []
        for option in gate["options"]:
            item: dict[str, Any] = {"id": option["id"]}
            if "reversible" in option:
                item["reversible"] = option["reversible"]
            options.append(item)
        return _digest({
            "category": "factory-release",
            "channel": "v1",
            "target": target,
            "options": sorted(options, key=lambda item: item["id"]),
            "safe_default": gate["safe_default"],
        })

    options = []
    for option in gate["options"]:
        authority = option.get("effect", option["label"])
        item = {
            "id": option["id"],
            "authority": authority,
        }
        if "reversible" in option:
            item["reversible"] = option["reversible"]
        options.append(item)
    return _digest({
        "options": sorted(options, key=lambda item: item["id"]),
        "safe_default": gate["safe_default"],
    })


def gate_identity(raw: Any) -> str:
    """Identidad completa: target exacto + contrato de autoridad."""
    gate = validate_gate(raw)
    return _digest({
        "target": gate_target_identity(gate),
        "authority": gate_authority_contract(gate),
    })


def _gate_raw_from_body(body: str) -> dict[str, Any]:
    # El body ya publicado se lee como evidencia histórica; su copy no modifica
    # el contrato. Se conservan tamaño, cantidad de markers y schema estrictos.
    classified = classify_body(body, historical=True)
    if classified.get("status") != "gate":
        raise GateValidationError("El Issue no contiene una puerta humana válida.")
    matches = MARKER_RE.findall(body)
    if len(matches) != 1:
        raise GateValidationError("La puerta humana no es inequívoca.")
    try:
        raw = json.loads(matches[0])
    except json.JSONDecodeError as exc:
        raise GateValidationError("El JSON del marker es inválido.") from exc
    if not isinstance(raw, dict):
        raise GateValidationError("El marker de puerta debe contener un objeto.")
    return raw


def gate_target_identity_from_body(body: str) -> str:
    gate = validate_gate(_gate_raw_from_body(body), historical=True)
    material = _privacy_target_from_body(body, gate)
    return _digest(material if material is not None else _gate_target(gate))


def gate_authority_contract_from_body(body: str) -> str:
    return gate_authority_contract(_gate_raw_from_body(body), historical=True)


def gate_identity_from_body(body: str) -> str:
    """Extrae target por motivos y contrato de autoridad del marker."""
    raw = _gate_raw_from_body(body)
    return _digest({
        "target": gate_target_identity_from_body(body),
        "authority": gate_authority_contract(raw, historical=True),
    })


def classify_body(
    body: str, *, include_reason: bool = False, historical: bool = False,
) -> dict[str, Any]:
    if not isinstance(body, str):
        raise GateValidationError("El cuerpo del Issue debe ser texto.")

    def invalid(reason: str) -> dict[str, Any]:
        # Los motivos se construyen exclusivamente desde errores de esquema,
        # nunca desde campos ni valores proporcionados en el marker.
        return _result(
            "invalid-gate",
            reason=reason if include_reason else None,
        )

    marker_intent = MARKER_INTENT_RE.search(body) is not None
    if len(body) > MAX_ISSUE_BODY_CHARS:
        return invalid("El cuerpo supera el límite permitido.") if marker_intent else _result("no-gate")

    matches = MARKER_RE.findall(body)
    if not matches:
        return invalid("Marker de puerta incompleto o malformado.") if marker_intent else _result("no-gate")
    if len(matches) != 1:
        return invalid("Debe existir exactamente un marker de puerta.")

    try:
        raw = json.loads(matches[0])
    except json.JSONDecodeError:
        return invalid("El JSON del marker es inválido.")
    try:
        gate = validate_gate(raw, historical=historical)
    except GateValidationError as exc:
        return invalid(str(exc))

    return _result("gate", gate["category"])


# La política editorial estricta alcanzó Factory@v1 con la release 1.0.44.
# No retrovalidar el copy de puertas OWNER creadas antes de esa publicación.
# El sello temporal y las etiquetas provienen del evento inmutable de GitHub.
_LEGACY_GATE_CUTOFF_UTC = "2026-10-27T21:39:29Z"


def _historic_existing_gate_event(event: dict[str, Any], issue: dict[str, Any]) -> bool:
    """Solo reabrir/editar una puerta anterior ya enrutada por GitHub.

    Nunca aceptar una puerta introducida en el editor de un Issue antiguo:
    al editar el marker, la identidad debe permanecer idéntica.
    """
    if event.get("action") not in {"edited", "reopened"}:
        return False
    if issue.get("state") != "open" or issue.get("author_association") not in {
        "OWNER", "MEMBER", "COLLABORATOR",
    }:
        return False
    created = issue.get("created_at")
    if (
        not isinstance(created, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created) is None
        or created >= _LEGACY_GATE_CUTOFF_UTC
    ):
        return False
    labels = issue.get("labels")
    if not isinstance(labels, list) or not any(
        (isinstance(label, dict) and label.get("name") == "decisión: dueño")
        or label == "decisión: dueño"
        for label in labels
    ):
        return False
    body = issue.get("body")
    if not isinstance(body, str) or len(MARKER_RE.findall(body)) != 1:
        return False
    changes = event.get("changes", {})
    if event["action"] == "edited" and isinstance(changes, dict) and "body" in changes:
        before = changes["body"]
        previous = before.get("from") if isinstance(before, dict) else None
        if not isinstance(previous, str) or MARKER_RE.findall(previous) != MARKER_RE.findall(body):
            return False
    return True


def classify_event_text(
    payload: str, *, include_reason: bool = False
) -> dict[str, Any]:
    if not isinstance(payload, str) or len(payload) > MAX_EVENT_CHARS:
        return _result(
            "invalid-gate",
            reason="Evento de GitHub fuera de límites." if include_reason else None,
        )

    try:
        event = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise GateValidationError(
            "Evento de GitHub contiene JSON inválido."
        ) from exc

    issue = event.get("issue") if isinstance(event, dict) else None
    if not isinstance(issue, dict):
        raise GateValidationError("El evento no contiene un Issue.")

    body = issue.get("body")
    return classify_body(
        body if isinstance(body, str) else "",
        include_reason=include_reason,
        historical=_historic_existing_gate_event(event, issue) if isinstance(event, dict) else False,
    )

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "github"), default="json")
    args = parser.parse_args()

    payload = sys.stdin.read(MAX_EVENT_CHARS + 1)
    try:
        result = classify_event_text(payload, include_reason=args.format == "github")
    except GateValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.format == "github":
        print(f"status={result['status']}")
        print(f"category={result['category'] or ''}")
        print(f"reason={result.get('reason', '')}")
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

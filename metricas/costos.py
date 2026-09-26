#!/usr/bin/env python3
"""Evalúa consumo de una tarea/PR contra presupuestos y resume tendencia de CI."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, TextIO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.safe_io import SafeIOError, read_repo_text, write_repo_text

MARKER_RE = re.compile(r"<!--\s*factory-cost\s+(\{[^<]*\})\s*-->")
CLOSING_RE = re.compile(r"(?im)\b(?:closes|fixes|resolves)\s+#([1-9][0-9]*)\b")
SLUG_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
USAGE_FIELDS = ("tokens", "ci_minutes", "agent_minutes", "review_rounds")
MARKER_FIELDS = {"task_type", "size", *USAGE_FIELDS}
CI_CONCLUSIONS = {
    "success", "failure", "cancelled", "timed_out", "action_required",
    "neutral", "skipped", "stale", "startup_failure",
}

STDIN_SENTINEL = "-"
PR_BUDGETS = Path("metricas/presupuestos.json")
PR_JSON_OUT = Path("artifacts/presupuesto-pr.json")
PR_MARKDOWN_OUT = Path("artifacts/presupuesto-pr.md")
TREND_JSON_OUT = Path("artifacts/ci-trend.json")


class CostError(ValueError):
    pass


def load_budgets(
    path: Path,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    try:
        data = json.loads(read_repo_text(path, root=root or ROOT))
    except (SafeIOError, json.JSONDecodeError) as exc:
        raise CostError("Presupuestos ilegibles o JSON inválido.") from exc
    if not isinstance(data, dict):
        raise CostError("Presupuestos deben tener raíz de objeto JSON.")
    if data.get("schema_version") != 1:
        raise CostError("schema_version de presupuestos debe ser 1.")

    global_limits = data.get("global_limits")
    sizes = data.get("sizes")
    multipliers = data.get("task_type_multipliers")
    if not isinstance(global_limits, dict) or not isinstance(sizes, dict) or not isinstance(multipliers, dict):
        raise CostError("Presupuestos incompletos.")
    if global_limits.get("commits") != 10 or global_limits.get("review_rounds") != 3:
        raise CostError("Los límites globales deben ser exactamente 10 commits y 3 rondas.")

    for size in ("small", "medium", "large"):
        item = sizes.get(size)
        if not isinstance(item, dict):
            raise CostError(f"Presupuesto inválido para size={size}.")
        for field in ("tokens", "ci_minutes", "agent_minutes"):
            value = item.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise CostError(f"Presupuesto inválido para size={size}.")

    if "default" not in multipliers:
        raise CostError("Falta multiplicador default válido.")
    for task_type, multiplier in multipliers.items():
        if not isinstance(task_type, str) or not SLUG_RE.fullmatch(task_type):
            raise CostError("Tipo de tarea inválido en multiplicadores.")
        if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)) or multiplier <= 0:
            raise CostError(f"Multiplicador inválido para task_type={task_type}.")
        for size, item in sizes.items():
            if size not in {"small", "medium", "large"} or not isinstance(item, dict):
                continue
            for field in ("tokens", "ci_minutes", "agent_minutes"):
                if round(item[field] * multiplier) < 1:
                    raise CostError(
                        f"Multiplicador de task_type={task_type} produce presupuesto efectivo menor que 1."
                    )
    return data

def _marker(body: str) -> dict[str, Any] | None:
    match = MARKER_RE.search(body or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise CostError("Marker factory-cost contiene JSON inválido.") from exc
    if not isinstance(data, dict) or set(data) != MARKER_FIELDS:
        raise CostError("Marker factory-cost debe contener exactamente los campos permitidos.")
    if not isinstance(data["task_type"], str) or not SLUG_RE.fullmatch(data["task_type"]):
        raise CostError("task_type debe ser un identificador.")
    if data["size"] not in {"small", "medium", "large"}:
        raise CostError("size debe ser small, medium o large.")
    for field in USAGE_FIELDS:
        if isinstance(data[field], bool) or not isinstance(data[field], int) or data[field] < 0:
            raise CostError(f"{field} debe ser entero >= 0.")
    return data


def evaluate_pr(event: dict[str, Any], budgets: dict[str, Any]) -> dict[str, Any]:
    pr = event.get("pull_request")
    repo = event.get("repository", {}).get("full_name")
    if not isinstance(pr, dict) or not isinstance(repo, str):
        raise CostError("Evento de Pull Request inválido.")
    body = str(pr.get("body") or "")
    marker = _marker(body)
    closing = CLOSING_RE.search(body)
    issue = f"{repo}#{closing.group(1)}" if closing else None
    commits = pr.get("commits")
    if isinstance(commits, bool) or not isinstance(commits, int) or commits < 0:
        raise CostError("Conteo de commits inválido.")

    if marker is None:
        return {
            "schema_version": 1, "pr": pr.get("number"), "issue": issue,
            "status": "soft-block", "reasons": ["missing-cost-marker"],
            "usage": {"commits": commits}, "usage_sources": {"commits": "observed"},
            "budget": budgets["global_limits"], "verified": False,
        }

    multiplier = budgets["task_type_multipliers"].get(
        marker["task_type"], budgets["task_type_multipliers"]["default"]
    )
    if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)) or multiplier <= 0:
        raise CostError("Multiplicador de tipo de tarea inválido.")

    base = budgets["sizes"][marker["size"]]
    effective = {
        "tokens": round(base["tokens"] * multiplier),
        "ci_minutes": round(base["ci_minutes"] * multiplier),
        "agent_minutes": round(base["agent_minutes"] * multiplier),
        "commits": budgets["global_limits"]["commits"],
        "review_rounds": budgets["global_limits"]["review_rounds"],
    }
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or value < 1
           for value in effective.values()):
        raise CostError("El presupuesto efectivo debe ser numérico y >= 1 en todas las dimensiones.")

    usage = {field: marker[field] for field in USAGE_FIELDS}
    usage["commits"] = commits
    sources = {
        "tokens": "declared",
        "ci_minutes": "declared",
        "agent_minutes": "declared",
        "review_rounds": "declared",
        "commits": "observed",
    }
    exceeded = [key for key, value in usage.items() if value > effective[key]]
    near = [key for key, value in usage.items()
            if key not in exceeded and value / effective[key] >= 0.8]
    unverified = [key for key, source in sources.items() if source != "observed"]

    status = "soft-block" if exceeded else "warning" if near or unverified else "ok"
    reasons = (
        [f"over:{key}" for key in exceeded]
        + [f"near:{key}" for key in near]
        + [f"unverified:{key}" for key in unverified]
    )
    return {
        "schema_version": 1, "pr": pr.get("number"), "issue": issue,
        "task_type": marker["task_type"], "size": marker["size"],
        "status": status, "reasons": reasons, "usage": usage, "usage_sources": sources,
        "budget": effective, "verified": not unverified,
        "ratios": {key: round(usage[key] / effective[key], 4) for key in usage},
    }

def ci_trend(rows: list[dict[str, Any]]) -> dict[str, Any]:
    seen_runs: set[int] = set()
    by_pr: dict[int, list[tuple[str, float, int, str]]] = defaultdict(list)

    for index, row in enumerate(rows, 1):
        minutes = row.get("ci_minutes")
        created = row.get("created_at")
        pr_number = row.get("pr_number")
        run_id = row.get("run_id")
        conclusion = row.get("conclusion")

        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes < 0:
            raise CostError(f"Histórico CI fila {index}: ci_minutes inválido.")
        if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number < 1:
            raise CostError(f"Histórico CI fila {index}: pr_number inválido.")
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id < 1:
            raise CostError(f"Histórico CI fila {index}: run_id inválido.")
        if run_id in seen_runs:
            raise CostError(f"Histórico CI fila {index}: run_id duplicado.")
        seen_runs.add(run_id)
        if conclusion not in CI_CONCLUSIONS:
            raise CostError(f"Histórico CI fila {index}: conclusion inválida.")
        if not isinstance(created, str):
            raise CostError(f"Histórico CI fila {index}: created_at inválido.")
        try:
            datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CostError(f"Histórico CI fila {index}: created_at inválido.") from exc
        by_pr[pr_number].append((created, float(minutes), run_id, conclusion))

    pr_rows = []
    for pr_number, runs in by_pr.items():
        pr_rows.append({
            "pr_number": pr_number,
            "created_at": min(item[0] for item in runs),
            "ci_minutes": round(sum(item[1] for item in runs), 2),
            "runs": len(runs),
            "conclusions": sorted({item[3] for item in runs}),
        })
    pr_rows.sort(key=lambda row: (row["created_at"], row["pr_number"]))
    conclusions = sorted({value for row in pr_rows for value in row["conclusions"]})

    common = {
        "samples": len(pr_rows),
        "run_samples": len(rows),
        "metric": "ci_minutes_per_pr",
        "included_conclusions": conclusions,
    }
    if len(pr_rows) < 4:
        return {"status": "insufficient-data", **common, "delta_pct": None}

    split = len(pr_rows) // 2
    before = mean(row["ci_minutes"] for row in pr_rows[:split])
    after = mean(row["ci_minutes"] for row in pr_rows[split:])
    delta = round(((after - before) / before) * 100, 2) if before else None
    direction = "down" if delta is not None and delta < 0 else "up" if delta is not None and delta > 0 else "flat"
    return {
        "status": "measured", **common,
        "before_avg": round(before, 2), "after_avg": round(after, 2),
        "delta_pct": delta, "direction": direction,
    }


def render_pr(result: dict[str, Any]) -> str:
    lines = ["# Presupuesto de tarea / PR", "",
             f"- Estado: **{result['status']}**",
             f"- Issue: **{result.get('issue') or 'sin relación de cierre'}**",
             f"- Verificado completamente: **{'sí' if result.get('verified') else 'no'}**", ""]
    if result["status"] == "soft-block" and result["reasons"] == ["missing-cost-marker"]:
        lines += ["Falta el marker `factory-cost`; el consumo no puede verificarse y se escala como bloqueo suave.", ""]
        return "\n".join(lines)
    lines += ["| Dimensión | Fuente | Uso | Presupuesto | % |",
              "| --- | --- | ---: | ---: | ---: |"]
    for key, used in result["usage"].items():
        limit = result["budget"][key]
        source = result["usage_sources"][key]
        lines.append(f"| {key} | {source} | {used} | {limit} | {result['ratios'][key]:.0%} |")
    if result["reasons"]:
        lines += ["", "Señales: " + ", ".join(result["reasons"]) + "."]
    return "\n".join(lines) + "\n"

def main(
    argv: list[str] | None = None,
    *,
    root: Path | None = None,
    input_stream: TextIO | None = None,
) -> int:
    """Ejecuta el CLI con paths cerrados y JSON de entrada por stdin."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    pr_parser = sub.add_parser("pr")
    pr_parser.add_argument(
        "--event",
        choices=[STDIN_SENTINEL],
        default=STDIN_SENTINEL,
    )
    pr_parser.add_argument(
        "--budgets",
        choices=[PR_BUDGETS.as_posix()],
        default=PR_BUDGETS.as_posix(),
    )
    pr_parser.add_argument(
        "--json-out",
        choices=[PR_JSON_OUT.as_posix()],
        default=PR_JSON_OUT.as_posix(),
    )
    pr_parser.add_argument(
        "--markdown-out",
        choices=[PR_MARKDOWN_OUT.as_posix()],
        default=PR_MARKDOWN_OUT.as_posix(),
    )

    trend_parser = sub.add_parser("trend")
    trend_parser.add_argument(
        "--input",
        choices=[STDIN_SENTINEL],
        default=STDIN_SENTINEL,
    )
    trend_parser.add_argument(
        "--json-out",
        choices=[TREND_JSON_OUT.as_posix()],
        default=TREND_JSON_OUT.as_posix(),
    )
    args = parser.parse_args(argv)

    base = (root or ROOT).resolve()
    stream = input_stream or sys.stdin
    try:
        if args.command == "pr":
            event_data = json.load(stream)
            if not isinstance(event_data, dict):
                raise CostError("Evento de Pull Request debe ser un objeto JSON.")
            result = evaluate_pr(
                event_data,
                load_budgets(PR_BUDGETS, root=base),
            )
            markdown = render_pr(result)
            json_output = PR_JSON_OUT
            markdown_output: Path | None = PR_MARKDOWN_OUT
        else:
            rows = json.load(stream)
            if not isinstance(rows, list):
                raise CostError("Histórico CI debe ser una lista JSON.")
            result = ci_trend(rows)
            markdown = (
                "# Tendencia de costo CI\n\n"
                + json.dumps(result, ensure_ascii=False)
                + "\n"
            )
            json_output = TREND_JSON_OUT
            markdown_output = None

        write_repo_text(
            json_output,
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            root=base,
        )
        if markdown_output is not None:
            write_repo_text(markdown_output, markdown, root=base)
    except (SafeIOError, json.JSONDecodeError, CostError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

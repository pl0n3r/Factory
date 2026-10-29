#!/usr/bin/env python3
"""Factory #1695: eight honest STATE/Presence and watchdog gap regressions.

Synthetic GitHub snapshots and pure committed implementations only. No live
HEARTBEAT, fifteen-minute run continuity, go-live or human approval is inferred.
The coverage matrix remains NO_VERIFICABLE, not silently promoted.
"""
from __future__ import annotations

import ast
from datetime import datetime
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from scripts.presence_contract import classify_presence
from scripts.unattended_guards import evaluate_unattended_guards
from scripts.unattended_state_source import project_state_presence
from scripts.unattended_watchdog import validate_state
from scripts.unattended_watchdog_runtime import collect_github_input

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
STATE_DOC = "docs/unattended-state-source.md"
WATCH_DOC = "docs/unattended-watchdog-runtime.md"
WORKFLOW = ".github/workflows/unattended-watchdog.yml"
RUNTIME = "scripts/unattended_watchdog_runtime.py"
CONFIG = "config/unattended-watchdog.json"
FILES = (MATRIX, STATE_DOC, WATCH_DOC, WORKFLOW, RUNTIME, CONFIG,
         "scripts/unattended_state_source.py",
         "scripts/unattended_daily_summary.py")
UNKNOWN, LOCAL, GAP = "UNKNOWN", "LOCAL_SYNTHETIC", "BRECHA_DOCUMENTADA"
S = "docs/unattended-state-source.md:"
W = "docs/unattended-watchdog-runtime.md:"
TICK = chr(96)
CLAUSES = {
    S+"L31-U1": TICK+"capacity.freshness=unknown"+TICK+".",
    S+"L33-U1": "4C clasificará esa Presence como UNKNOWN/fail-closed.",
    S+"L41-U1": "La freshness se expresa en "+TICK+"reasons"+TICK+
        " ("+TICK+"state_stale"+TICK+") y el consumidor la deriva otra vez con "+
        TICK+"validate_state()"+TICK+".",
    S+"L45-U1": "#769 lee GitHub, entrega snapshots a este parser y luego llama 4B/4C.",
    S+"L46-U1": "#768 consume STATE/resumen una vez exista su runtime.",
    S+"L47-U1": "Ningún consumidor puede reinterpretar UNKNOWN como ALLOW ni ampliar "+
        TICK+"authority=unchanged"+TICK+".",
    W+"B03": "La continuidad operativa real de la cadencia de quince minutos requiere runs y HEALTH observados.",
    W+"B04": "Reactivar resumen diario suspendido por F1G exige autorización humana separada.",
}
GAPS = {
    S+"L46-U1": "runtime consumidor #768 sin ejecución real acreditada",
    W+"B03": "cron versionado no acredita runs continuos ni HEARTBEAT real",
    W+"B04": "F1G: reactivación del informe diario exige permiso humano",
}
RID = "11111111-2222-4333-8444-555555555555"
HEAD = "a"*40
NOW = "2026-10-02T04:10:00Z"


def documents():
    return {p: (ROOT/p).read_text(encoding="utf-8") for p in FILES}


def matrix_rows(raw):
    if type(raw) is not str or not raw.strip():
        raise ValueError("UNKNOWN: missing matrix")
    result = {}
    for line in raw.splitlines():
        if not line.startswith("| "):
            continue
        cells = tuple(x.strip() for x in line.strip().strip("|").split("|"))
        key = cells[0].strip(TICK) if cells else None
        if key not in CLAUSES:
            continue
        if (key in result or len(cells)!=5 or cells[0]!=TICK+key+TICK
                or cells[1]!=CLAUSES[key] or cells[2]!="NO_VERIFICABLE"
                or cells[4]!="—"
                or (key.startswith(S) and
                    ("Contraste [#1575]" not in cells[3] or
                     "acreditación individual pendiente" not in cells[3]))
                or (key.startswith(W) and
                    "Evidencia insuficiente:" not in cells[3])):
            raise ValueError("UNKNOWN: malformed or promoted "+key)
        result[key] = cells
    if set(result)!=set(CLAUSES):
        raise ValueError("UNKNOWN: incomplete/duplicate coverage")
    return result


def comment(by, body, at="2026-10-02T04:09:00Z"):
    return {"user":{"login":by}, "body":body,
            "created_at":at,"updated_at":at}


def reservation(*, active=True, at="2026-10-02T04:09:00Z", **updates):
    marker = {
        "version":3,"owner":"pl0n3r","reservation_id":RID,
        "branch":"trabajo/issue-775","active":active,
        "reason":"tomar" if active else "pr-merged",
        "acceptance_sha256":"b"*64,"task_marker_sha256":"c"*64,
        "task_paths":["scripts/unattended_state_source.py"],
        "task_depends_on":[],
    }
    marker.update(updates)
    return comment("github-actions[bot]",
                   "<!-- condor-reserva "+json.dumps(marker)+" -->", at)


def state(**updates):
    marker = {
        "work_identity":"pl0n3r/Factory#775","repository":"pl0n3r/Factory",
        "branch":"trabajo/issue-775","head_sha":HEAD,"reservation_id":RID,
        "risk":"medium","severity":"S3",
        "evidence":["Factory#775","head@"+HEAD],
        "last_state":"implementing","next_action":"run acceptance",
        "blockers":[],"updated_at":"2026-10-02T04:08:30Z",
    }
    marker.update(updates)
    return marker


def state_comment(**updates):
    return comment("pl0n3r", "<!-- factory-state "+json.dumps(
        {"version":1,"state":state(**updates)})+" -->")


def project(comments, **updates):
    kwargs = {
        "repository":"pl0n3r/Factory","issue_number":775,"comments":comments,
        "now":NOW,"state_stale_minutes":20,"reservation_stale_minutes":15,
        "branch_head_sha":HEAD,
    }
    return project_state_presence(**{**kwargs,**updates})


class MemoryGitHub:
    """Fake reader: confirms the real runtime orchestration, never reaches GitHub."""
    repository = "pl0n3r/Factory"

    def __init__(self, comments):
        self.comments, self.calls = comments, []

    def list_open_work_items(self):
        self.calls.append("issues")
        return [{"number":775,"labels":[{"name":"estado: reservado"}]}]

    def list_issue_comments(self, issue):
        self.calls.append("comments")
        if issue!=775:
            raise AssertionError("wrong issue")
        return self.comments

    def get_branch_head(self, issue):
        self.calls.append("head")
        if issue!=775:
            raise AssertionError("wrong branch")
        return HEAD


def coverage(files):
    results = {key:UNKNOWN for key in CLAUSES}
    if (type(files) is not dict or set(files)!=set(FILES)
            or any(type(files[k]) is not str or not files[k] for k in FILES)):
        return results
    try:
        matrix_rows(files[MATRIX])
        config = json.loads(files[CONFIG])
        if type(config) is not dict:
            return results
        good = project([reservation(),state_comment()])
        no_state = project([reservation()])
        released = project([reservation(),state_comment(),
                            reservation(active=False,at="2026-10-02T04:09:30Z")])
        stale = project([reservation(),state_comment(
            updated_at="2026-10-02T03:30:00Z")])
        presence = classify_presence(good.presence)
        client = MemoryGitHub([reservation(),state_comment()])
        runtime = collect_github_input(client,config,NOW)
        guard = evaluate_unattended_guards(None,{}, {}, {})
    except (ValueError,TypeError,KeyError,AssertionError,AttributeError):
        return results

    zero_capacity = {
        "known_slots":0,"eligible_free_slots":0,
        "degraded_slots":0,"freshness":"unknown",
    }
    bound = (
        good.status=="READY" and good.authority=="unchanged"
        and good.reservation_id==RID and good.state is not None
        and good.presence["sessions"]==[]
        and good.presence["capacity"]==zero_capacity
    )
    fourc_unknown = (
        presence.classifications==("unknown",)
        and presence.eligible_free_slots==0
        and no_state.status==released.status==UNKNOWN
        and no_state.authority==released.authority=="unchanged"
    )
    staleness = (
        stale.status=="READY" and stale.state is not None
        and "state_stale" in stale.reasons
        and "freshness" not in stale.state
        and validate_state(
            stale.state,
            now=datetime.fromisoformat(NOW.replace("Z","+00:00")),
            stale_after_minutes=20,
        )["freshness"]=="stale"
    )
    integration = (
        runtime.get("guard",{}).get("action")=="BLOCKED"
        and isinstance(runtime.get("evidence"),dict)
        and runtime["evidence"].get("presence")==good.presence
        and {"issues","comments","head"}.issubset(set(client.calls))
        and "project_state_presence(" in files[RUNTIME]
        and "_canonical_blocked_guard()" in files[RUNTIME]
    )
    safe = (
        guard.action=="BLOCKED" and guard.authority=="unchanged"
        and released.state is None and no_state.state is None
        and "Ningún consumidor puede reinterpretar UNKNOWN como ALLOW" in files[STATE_DOC]
    )
    for key, ok in (
        (S+"L31-U1",bound),(S+"L33-U1",bound and fourc_unknown),
        (S+"L41-U1",staleness),(S+"L45-U1",integration),
        (S+"L47-U1",safe),
    ):
        if ok and CLAUSES[key] in files[STATE_DOC]:
            results[key] = LOCAL

    if CLAUSES[S+"L46-U1"] in files[STATE_DOC]:
        results[S+"L46-U1"] = GAP

    # Neither a cron definition nor a sample run proves real continuity.
    if ("cada 15 minutos" in files[WATCH_DOC]
            and "cron: '*/15 * * * *'" in files[WORKFLOW]
            and "workflow_dispatch:" in files[WORKFLOW]):
        results[W+"B03"] = GAP

    # Re-enable only by a separate authorized change, NEVER through this test.
    if ("F1G" in files[WATCH_DOC]
            and "autorización" in files[WATCH_DOC]
            and "daily-summary:" not in files[WORKFLOW]
            and "0 13 * * *" not in files[WORKFLOW]
            and "def publish_once(" in files["scripts/unattended_daily_summary.py"]):
        results[W+"B04"] = GAP
    return results


def operational(_key, _claim=None):
    return UNKNOWN


class BrechasFactory77Tests(unittest.TestCase):
    def test_contrato_principal(self):
        files=documents()
        self.assertEqual(set(matrix_rows(files[MATRIX])),set(CLAUSES))
        self.assertEqual(len(CLAUSES),8)
        statuses=coverage(files)
        for key in CLAUSES:
            with self.subTest(id=key):
                self.assertEqual(statuses[key], GAP if key in GAPS else LOCAL)
                self.assertEqual(operational(key,statuses[key]),UNKNOWN)

    def test_falla_cerrado(self):
        files=documents()
        raw=files[MATRIX]
        for key in CLAUSES:
            line=next(x for x in raw.splitlines()
                      if x.startswith("| "+TICK+key+TICK+" |"))
            for bad in (raw.replace(line,"",1),raw+"\n"+line,
                        raw.replace(line,line.replace("NO_VERIFICABLE","VERIFIED"),1)):
                with self.subTest(id=key):
                    with self.assertRaisesRegex(ValueError,UNKNOWN):
                        matrix_rows(bad)
                    self.assertTrue(all(v==UNKNOWN for v in coverage(
                        {**files,MATRIX:bad}).values()))
        for file in FILES:
            with self.subTest(file=file):
                self.assertTrue(all(v==UNKNOWN for v in coverage(
                    {**files,file:""}).values()))
        for events in (
            [reservation()],
            [reservation(),state_comment(head_sha="d"*40)],
            [reservation(),state_comment(reservation_id="0"*36)],
            [reservation(),state_comment(updated_at="2026-10-02T04:11:00Z")],
        ):
            result=project(events)
            self.assertIn(result.status,{UNKNOWN,"BLOCKED"})
            self.assertEqual(result.authority,"unchanged")

    def test_sin_datos_reales(self):
        node=ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported={alias.name.split(".")[0] for n in ast.walk(node)
                  if isinstance(n,ast.Import) for alias in n.names}
        imported|={n.module.split(".")[0] for n in ast.walk(node)
                   if isinstance(n,ast.ImportFrom) and n.module}
        self.assertFalse(imported & {"requests","httpx","urllib","subprocess",
                                     "playwright","pymysql"})
        with patch.object(socket,"socket",side_effect=AssertionError("no network")):
            self.assertEqual(coverage(documents())[S+"L33-U1"],LOCAL)
        self.assertNotIn("password",json.dumps(state()).lower())

    def test_estados_unknown_explicitos(self):
        results=coverage(documents())
        self.assertEqual(set(GAPS),{k for k,v in results.items() if v==GAP})
        for key in CLAUSES:
            with self.subTest(id=key):
                if key in GAPS:
                    self.assertGreater(len(GAPS[key]),25)
                for claim in (None,True,{"ci":"success"},{"scheduled_runs":999},
                              {"heartbeat":"fresh"},{"human_approval":True},
                              {"production":"GREEN"},{"daily_summary":"restored"}):
                    self.assertEqual(operational(key,claim),UNKNOWN)
        self.assertEqual(project([reservation()]).status,UNKNOWN)
        self.assertIn("state_stale",project([
            reservation(),state_comment(
                updated_at="2026-10-02T03:30:00Z")]).reasons)


if __name__=="__main__":
    unittest.main()

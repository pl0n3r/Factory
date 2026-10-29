#!/usr/bin/env python3
"""Factory #1668: sixteen Project DNA / provisioning evidence gaps.

A source-level or synthetic local contract is not evidence of GitHub credentials,
repository publication, production readiness, deployed governance or remote CI.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from unittest import mock
import unittest

from intelligence.project_dna import (
    ProjectDnaError, discover_project_dna, validate_project_dna,
)
from scripts import provision_project as p

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
DNA = "docs/project-dna.md"
PROVISION = "docs/provisioning.md"
WORKFLOW = ".github/workflows/provision-project.yml"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
BT = chr(96)
SHA = "b" * 40

CLAUSES = {
    "docs/project-dna.md:L9-U1": (DNA, "El descubridor recibe señales explícitas y no secretas:"),
    "docs/provisioning.md:L10-U1": (PROVISION, "El bootstrap construye localmente"),
    "docs/provisioning.md:L10-U2": (PROVISION, "No usa Git Database REST"),
    "docs/provisioning.md:L11-U1": (PROVISION, "La descripción de recuperación liga un digest SHA-256"),
    "docs/provisioning.md:L12-U1": (PROVISION, "Un retry con el mismo marker converge"),
    "docs/provisioning.md:L12-U2": (PROVISION, "Un repo preexistente público"),
    "docs/provisioning.md:L5-U1": (PROVISION, "El destino permitido es"),
    "docs/provisioning.md:L5-U2": (PROVISION, "tanto un repo nuevo como uno adoptado deben ser"),
    "docs/provisioning.md:L6-U1": (PROVISION, "La autoridad externa es exclusivamente"),
    "docs/provisioning.md:L6-U2": (PROVISION, "el " + BT + "GITHUB_TOKEN" + BT),
    "docs/provisioning.md:L7-U1": (PROVISION, "La credencial debe pertenecer"),
    "docs/provisioning.md:L7-U2": (PROVISION, "Factory valida la identidad autenticada"),
    "docs/provisioning.md:L8-U1": (PROVISION, "Si la credencial falta"),
    "docs/provisioning.md:L8-U2": (PROVISION, "Su valor nunca se pega"),
    "docs/provisioning.md:L9-U1": (PROVISION, "El runtime se descarga"),
    "docs/provisioning.md:L9-U2": (PROVISION, "la gobernanza se descarga por separado"),
}
# Assertions for these rows verify source policy, never credential or runner
# behavior. An authentic run, secret permissions and logs remain UNKNOWN.
SOURCE_ONLY = frozenset({
    "docs/provisioning.md:L6-U1", "docs/provisioning.md:L6-U2",
    "docs/provisioning.md:L7-U1", "docs/provisioning.md:L8-U1",
    "docs/provisioning.md:L8-U2", "docs/provisioning.md:L9-U1",
    "docs/provisioning.md:L9-U2",
})


def sources() -> dict[str, str]:
    return {name: (ROOT / name).read_text(encoding="utf-8")
            for name in (MATRIX, DNA, PROVISION, WORKFLOW)}


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Preserve each original NO_VERIFICABLE row and provenance, exactly once."""
    if type(raw) is not str:
        raise ValueError("UNKNOWN: matriz ausente")
    found = {}
    for key, (_, phrase) in CLAUSES.items():
        rows = [line for line in raw.splitlines()
                if line.startswith("| " + BT + key + BT + " |")]
        if len(rows) != 1:
            raise ValueError("UNKNOWN: fila ausente/duplicada " + key)
        cells = tuple(value.strip() for value in rows[0].strip("|").split("|"))
        if (len(cells) != 5 or cells[0] != BT + key + BT
                or not cells[1].casefold().startswith(phrase.casefold())
                or cells[2] != "NO_VERIFICABLE"
                or "[Contraste #1573](contraste-factory_resto_5.md)" not in cells[3]
                or "evidencia candidata" not in cells[3] or cells[4] != "—"):
            raise ValueError("UNKNOWN: fila ambigua/promovida " + key)
        found[key] = cells
    return found


def source_matches(key: str, docs: object) -> bool:
    if key not in CLAUSES or type(docs) is not dict:
        return False
    path, phrase = CLAUSES[key]
    value = docs.get(path)
    if type(value) is not str:
        return False
    try:
        number = int(key.split(":L", 1)[1].split("-", 1)[0])
    except (IndexError, ValueError):
        return False
    lines = value.splitlines()
    return 0 < number <= len(lines) and phrase.casefold() in lines[number - 1].casefold()


def request(key: str = "a" * 64) -> dict[str, str]:
    return {
        "project_id": "project-fixture", "project_slug": "fixture",
        "target_repository": "pl0n3r/SyntheticFixture",
        "governance_ref": p.GOVERNANCE_REF, "idempotency_key": key,
    }


def existing(req: dict[str, str], private: bool = True,
             description: str | None = None, name: str | None = None) -> dict[str, object]:
    return {
        "full_name": name or req["target_repository"],
        "private": private,
        "description": description if description is not None else p.description_for(req, SHA),
        "default_branch": None,
    }


class FakeGateway:
    """In-memory only: no HTTP, repositories, git, tokens or user records."""
    def __init__(self, repository: dict | None = None, marker: dict | None = None,
                 empty: bool = True, create_public: bool = False) -> None:
        self.repo, self.current_marker = repository, marker
        self.is_empty, self.create_public = empty, create_public
        self.creates = self.bootstraps = self.authorizations = self.defaults = 0
        self.operations: list[str] = []

    def authorize(self) -> None:
        self.operations.append("authorize")
        self.authorizations += 1

    def repository(self, name: str) -> dict | None:
        self.operations.append("repository")
        return self.repo

    def create(self, req: dict, sha: str) -> dict:
        self.operations.append("create")
        self.creates += 1
        self.repo = existing(req, private=not self.create_public)
        return self.repo

    def empty(self, name: str) -> bool:
        self.operations.append("empty")
        return self.is_empty

    def marker(self, name: str) -> dict | None:
        self.operations.append("marker")
        return self.current_marker

    def set_default(self, name: str) -> None:
        self.defaults += 1
        self.repo["default_branch"] = "main"

    def bootstrap(self, name: str, files: dict, marker: dict) -> None:
        self.operations.append("bootstrap")
        self.bootstraps += 1
        self.current_marker = marker
        self.repo["default_branch"] = "main"


def proof(workflow: str) -> dict[str, bool]:
    req = request()
    first = FakeGateway()
    created = p.provision(req, first, {}, SHA)
    retry = p.provision(req, first, {}, SHA)
    adopted = FakeGateway(existing(req))
    adoption = p.provision(req, adopted, {}, SHA)
    third = p.provision(req, adopted, {}, SHA)

    def rejects(gateway: FakeGateway, value: dict | None = None) -> bool:
        try:
            p.provision(req if value is None else value, gateway, {}, SHA)
        except p.ProvisionError:
            return gateway.bootstraps == 0
        return False

    public_reject = rejects(FakeGateway(existing(req, private=False)))
    new_public_reject = rejects(FakeGateway(create_public=True))
    wrong_identity = rejects(FakeGateway(existing(req, name="pl0n3r/Wrong")))
    wrong_description = rejects(FakeGateway(existing(req, description="not our project")))
    nonempty = rejects(FakeGateway(existing(req), empty=False))
    wrong_marker = rejects(FakeGateway(existing(req), marker={"version": 2, "request_identity": "other"}))
    invalid_owner = rejects(FakeGateway(), {**req, "target_repository": "elsewhere/Fixture"})

    gateway = p.GitHubGateway("synthetic-fixture-token")
    with mock.patch.object(gateway, "_request", return_value={"login": "other"}):
        try:
            gateway.authorize()
        except p.ProvisionError:
            other_owner_rejected = True
        else:
            other_owner_rejected = False
    with mock.patch.object(gateway, "_request", return_value={"login": "pl0n3r"}):
        gateway.authorize()
    with mock.patch.object(gateway, "_request", return_value=existing(req)) as rest:
        gateway.create(req, SHA)
    method, path, payload = rest.call_args.args
    create_private = (method == "POST" and path == "/user/repos"
                      and payload["private"] is True and payload["auto_init"] is False)

    git_calls: list[tuple[str, ...]] = []
    git_environments: list[dict] = []
    def record_git(cwd: Path, *args: str, **kwargs: object) -> None:
        git_calls.append(args)
        git_environments.append(kwargs.get("env") or {})

    with mock.patch.object(gateway, "_git", side_effect=record_git), mock.patch.object(
        gateway, "set_default"
    ) as set_default:
        gateway.bootstrap(req["target_repository"], {"AGENTES.md": "synthetic"}, p.marker_for(req, SHA))
    local_git = (
        len(git_calls) == 7
        and sum(call[0] == "init" for call in git_calls) == 1
        and sum(call[0] == "commit" for call in git_calls) == 1
        and sum(call[0] == "push" for call in git_calls) == 1
        and ("init", "-b", "main") in git_calls
        and git_calls[-1] == ("push", "origin", "HEAD:refs/heads/main")
        and "GIT_ASKPASS" in git_environments[-1]
        and all("synthetic-fixture-token" not in str(call) for call in git_calls)
        and set_default.call_count == 1
    )

    a = discover_project_dna(
        paths=["package.json", ".github/workflows/ci.yml", "database/"],
        manifests={"package.json": {"dependencies": {"fastify": "^5"}}},
        capabilities=["web", "api"],
    )
    b = discover_project_dna(
        paths=["database/", ".github/workflows/ci.yml", "package.json", "package.json"],
        manifests={"package.json": {"dependencies": {"fastify": "^5"}}},
        capabilities=["api", "web"],
    )
    unknown_dna = discover_project_dna(paths=["README.md"])
    try:
        discover_project_dna(paths=["../private"])
    except ProjectDnaError:
        traversal_rejected = True
    else:
        traversal_rejected = False
    guarded = (a["fingerprint"] == b["fingerprint"]
               and validate_project_dna(a) == a
               and a["stack"] == ["node"] and a["ci"] == ["github-actions"]
               and a["frameworks"] == ["fastify"]
               and a["data"] == ["sql"] and a["capabilities"] == ["api", "web"]
               and unknown_dna["stack"] == "unknown"
               and unknown_dna["hosting"] == "unknown"
               and unknown_dna["integrations"] == "unknown"
               and traversal_rejected)

    hash_contract = (len(p.identity(req, SHA)) == 64
                     and p.identity(req, SHA) != p.identity(request("a" * 63 + "b"), SHA)
                     and p.identity(req, SHA) != p.identity(req, "c" * 40)
                     and p.marker_for(req, SHA)["request_identity"] == p.identity(req, SHA)
                     and p.marker_for(req, SHA)["idempotency_key"] == req["idempotency_key"]
                     and p.marker_for(req, SHA)["governance_sha"] == SHA
                     and p.identity(req, SHA) in p.description_for(req, SHA))
    workflow_safe = (
        "permissions:\n  contents: read" in workflow
        and "secrets.FACTORY_PROVISION_TOKEN" in workflow
        and "github.actor" in workflow and "github.repository_owner" in workflow
        and "persist-credentials: false" in workflow
        and "github.token" not in workflow.lower()
        and workflow.index("name: Validar contexto y autoridad externa")
        < workflow.index("name: Descargar runtime exacto del workflow")
    )
    return {
        "docs/project-dna.md:L9-U1": guarded,
        "docs/provisioning.md:L10-U1": local_git,
        "docs/provisioning.md:L10-U2": (
            local_git and not rest.call_args.args[1].startswith("/repos/")),
        "docs/provisioning.md:L11-U1": hash_contract,
        "docs/provisioning.md:L12-U1": (
            created["created"] and created["bootstrapped"]
            and not retry["bootstrapped"] and first.creates == first.bootstraps == 1
            and adoption["bootstrapped"] and not third["bootstrapped"]
            and adopted.bootstraps == 1),
        "docs/provisioning.md:L12-U2": (
            all((public_reject, new_public_reject, wrong_identity, wrong_description,
                 nonempty, wrong_marker, invalid_owner))),
        "docs/provisioning.md:L5-U1": (
            req["target_repository"].startswith("pl0n3r/") and invalid_owner
            and p.validate_request(req) == req),
        "docs/provisioning.md:L5-U2": (create_private and public_reject and new_public_reject),
        "docs/provisioning.md:L6-U1": workflow_safe,
        "docs/provisioning.md:L6-U2": workflow_safe,
        "docs/provisioning.md:L7-U1": (other_owner_rejected and workflow_safe),
        "docs/provisioning.md:L7-U2": (
            other_owner_rejected and first.operations[0] == "authorize"),
        "docs/provisioning.md:L8-U1": (
            workflow_safe and '[[ -n "$FACTORY_PROVISION_TOKEN" ]]' in workflow),
        "docs/provisioning.md:L8-U2": (
            workflow_safe and 'echo "$FACTORY_PROVISION_TOKEN"' not in workflow
            and local_git),
        "docs/provisioning.md:L9-U1": (
            workflow_safe and "ref: " + "$" + "{{ github.sha }}" in workflow
            and "path: runtime" in workflow),
        "docs/provisioning.md:L9-U2": (
            workflow_safe and "ref: v1" in workflow
            and "path: governance" in workflow
            and "--governance-sha" in workflow),
    }


def assess(docs: object, evidence: object) -> dict[str, str]:
    result = dict.fromkeys(CLAUSES, UNKNOWN)
    if type(docs) is not dict or type(evidence) is not dict:
        return result
    try:
        matrix_rows(docs.get(MATRIX))
    except ValueError:
        return result
    if (set(docs) != {MATRIX, DNA, PROVISION, WORKFLOW}
            or set(evidence) != set(CLAUSES)
            or not all(source_matches(key, docs) for key in CLAUSES)
            or any(type(value) is not bool for value in evidence.values())):
        return result
    for key in CLAUSES:
        if evidence[key] and key not in SOURCE_ONLY:
            result[key] = LOCAL
    return result


class BrechasFactory50Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        docs = sources()
        results = proof(docs[WORKFLOW])
        self.assertEqual(16, len(CLAUSES))
        self.assertEqual(set(CLAUSES), set(matrix_rows(docs[MATRIX])))
        self.assertEqual(set(CLAUSES), set(results))
        states = assess(docs, results)
        for key in CLAUSES:
            with self.subTest(key=key):
                self.assertTrue(source_matches(key, docs))
                self.assertIs(results[key], True)
                self.assertEqual(UNKNOWN if key in SOURCE_ONLY else LOCAL, states[key])

    def test_falla_cerrado(self) -> None:
        docs, results = sources(), proof(sources()[WORKFLOW])
        for key in CLAUSES:
            row = next(line for line in docs[MATRIX].splitlines()
                       if line.startswith("| " + BT + key + BT + " |"))
            for broken in (
                docs[MATRIX].replace(row, "", 1), docs[MATRIX] + "\n" + row,
                docs[MATRIX].replace(row, row.replace("NO_VERIFICABLE", "VERIFICADO", 1), 1),
            ):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, UNKNOWN):
                    matrix_rows(broken)
                self.assertEqual({UNKNOWN}, set(assess({**docs, MATRIX: broken}, results).values()))
        self.assertEqual({UNKNOWN}, set(assess({}, results).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, None).values()))
        self.assertEqual({UNKNOWN}, set(assess({**docs, PROVISION: ""}, results).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {**results, "production": True}).values()))
        for key in CLAUSES:
            self.assertEqual(UNKNOWN, assess(docs, {**results, key: None})[key])

    def test_sin_datos_reales(self) -> None:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = {alias.name.split(".")[0] for node in ast.walk(tree)
                   if isinstance(node, ast.Import) for alias in node.names}
        imports |= {node.module.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imports & {"requests", "urllib", "httpx", "socket",
                                    "pymysql", "selenium", "playwright"})
        with mock.patch.object(p, "urlopen", side_effect=AssertionError("network forbidden")):
            self.assertEqual(set(CLAUSES), set(proof(sources()[WORKFLOW])))
        self.assertEqual("pl0n3r/SyntheticFixture", request()["target_repository"])
        self.assertNotIn("PRIVATE KEY", repr(request()))

    def test_estados_unknown_explicitos(self) -> None:
        docs, results = sources(), proof(sources()[WORKFLOW])
        states = assess(docs, results)
        self.assertEqual(SOURCE_ONLY, {k for k, v in states.items() if v == UNKNOWN})
        self.assertNotIn("VALIDATED_IN_PRODUCTION", states.values())
        self.assertEqual({UNKNOWN}, set(assess(docs, {**results, "CI": "success"}).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {**results, "github": "approved"}).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {}).values()))


if __name__ == "__main__":
    unittest.main()

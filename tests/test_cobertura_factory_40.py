#!/usr/bin/env python3
"""Factory #1831: regresiones de Project DNA y provisioning, sin red ni datos reales.

Los gates que dependen de GitHub Actions/token externos no se acreditan con mocks.
No leer ni inferir estados de docs/matriz-cobertura*.md.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

from intelligence.project_dna import (
    ProjectDnaError, discover_project_dna, validate_project_dna,
)
from scripts import provision_project as provision

ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_SHA = "b" * 40  # SHA sintético, no un release real.


def request(key="a" * 64, repository="pl0n3r/FixtureProject"):
    return {
        "project_id": "project-fixture", "project_slug": "fixture",
        "target_repository": repository,
        "governance_ref": provision.GOVERNANCE_REF,
        "idempotency_key": key,
    }


def repo(req, *, private=True, description=None, branch=None):
    return {
        "full_name": req["target_repository"], "private": private,
        "description": description if description is not None
        else provision.description_for(req, GOVERNANCE_SHA),
        "default_branch": branch,
    }


class FakeGateway:
    """Gateway estrictamente en memoria; no implementa transporte."""

    def __init__(self, repository=None, marker=None, empty=True, owner=True):
        self.repo = repository
        self.current_marker = marker
        self.is_empty = empty
        self.owner = owner
        self.calls = []

    def authorize(self):
        self.calls.append("authorize")
        if not self.owner:
            raise provision.ProvisionError("Autoridad inválida")

    def repository(self, name):
        self.calls.append("repository")
        return self.repo

    def create(self, req, sha):
        self.calls.append("create")
        self.repo = repo(req)
        return self.repo

    def empty(self, name):
        self.calls.append("empty")
        return self.is_empty

    def marker(self, name):
        self.calls.append("marker")
        return self.current_marker

    def set_default(self, name):
        self.calls.append("set_default")
        self.repo["default_branch"] = "main"

    def bootstrap(self, name, files, marker):
        self.calls.append("bootstrap")
        self.current_marker = marker
        self.repo["default_branch"] = "main"


class CoberturaFactory40Tests(unittest.TestCase):
    """AC-01..04; cada prueba invoca implementaciones reales."""

    def test_contrato_principal(self):
        # project-dna:L9-U1 / L33-U1 / L34-U1: señales explícitas,
        # extensions y fingerprint deben proceder del código real.
        dna = discover_project_dna(
            paths=["package.json", "README.md", "package.json"],
            manifests={"package.json": {"dependencies": {"react": "^19"}}},
            capabilities=["web", "api"],
        )
        self.assertEqual(dna["stack"], ["node"])
        self.assertEqual(dna["frameworks"], ["react"])
        self.assertEqual(dna["signals"]["paths"], ["README.md", "package.json"])
        self.assertEqual(dna["capabilities"], ["api", "web"])
        self.assertEqual(dna["extensions"], {})
        self.assertEqual(validate_project_dna(dna), dna)
        canonical = json.dumps(
            {k: v for k, v in dna.items() if k != "fingerprint"},
            ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True,
        ).encode("utf-8")
        self.assertEqual(dna["fingerprint"], hashlib.sha256(canonical).hexdigest())
        self.assertEqual(dna, discover_project_dna(
            paths=["README.md", "package.json"],
            manifests={"package.json": {"dependencies": {"react": "^19"}}},
            capabilities=["api", "web"],
        ))

        # project-dna:L37-U1 — ninguna inferencia en ausencia de evidencia.
        unknown = discover_project_dna(paths=["docs/stripe-notes.md"])
        for field in ("stack", "frameworks", "data", "ci", "hosting",
                      "integrations", "capabilities"):
            with self.subTest(field=field):
                self.assertEqual(unknown[field], "unknown")

        # project-dna:L48-U1 — extensiones nuevas sin cambio de campos base.
        extended = copy.deepcopy(dna)
        extended["extensions"]["fixture_future"] = {"capability": "sample"}
        extended["fingerprint"] = hashlib.sha256(json.dumps(
            {k: v for k, v in extended.items() if k != "fingerprint"},
            ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True,
        ).encode("utf-8")).hexdigest()
        self.assertEqual(validate_project_dna(extended)["extensions"]["fixture_future"],
                         {"capability": "sample"})

        # provisioning:L5-U1/L5-U2: solo owner previsto y repos privados.
        req = request()
        self.assertEqual(provision.validate_request(req), req)
        created = FakeGateway()
        self.assertTrue(provision.provision(req, created, {}, GOVERNANCE_SHA)["created"])
        self.assertEqual(created.calls.count("create"), 1)
        adopted = FakeGateway(repo(req))
        self.assertTrue(provision.provision(req, adopted, {}, GOVERNANCE_SHA)["bootstrapped"])
        self.assertNotIn("create", adopted.calls)

        # provisioning:L7-U2 — comprobar identidad antes de toda escritura.
        unauth = provision.GitHubGateway("synthetic-fixture-token")
        with mock.patch.object(unauth, "_request", return_value={"login": "foreign-user"}):
            with self.assertRaises(provision.ProvisionError):
                unauth.authorize()
        rejected = FakeGateway(owner=False)
        with self.assertRaises(provision.ProvisionError):
            provision.provision(req, rejected, {}, GOVERNANCE_SHA)
        self.assertEqual(rejected.calls, ["authorize"])

        # provisioning:L10-U1/L10-U2: bootstrap usa git init, un root commit
        # y push autenticado; no usa REST Git Database. Mock solo I/O externo.
        gw = provision.GitHubGateway("synthetic-fixture-token")
        done = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(provision.subprocess, "run", return_value=done) as git_run, \
             mock.patch.object(gw, "_request", return_value={}) as api:
            gw.bootstrap(req["target_repository"], {"AGENTES.md": "fixture"},
                         provision.marker_for(req, GOVERNANCE_SHA))
        commands = [call.args[0] for call in git_run.call_args_list]
        self.assertEqual([cmd[-2:] for cmd in commands if "commit" in cmd],
                         [["-m", "chore(factory): bootstrap gobernanza v1"]])
        self.assertEqual(sum("push" in cmd for cmd in commands), 1)
        self.assertTrue(any("init" in cmd and "main" in cmd for cmd in commands))
        self.assertTrue(any("add" in cmd and "--all" in cmd for cmd in commands))
        self.assertEqual([call.args[:2] for call in api.call_args_list],
                         [("PATCH", "/repos/pl0n3r/FixtureProject")])
        self.assertTrue(any(
            "FACTORY_PROVISION_TOKEN" in (call.kwargs.get("env") or {})
            for call in git_run.call_args_list
        ))

        # provisioning:L11-U1: digest liga toda la key y el SHA de gobernanza.
        identity = provision.identity(req, GOVERNANCE_SHA)
        self.assertRegex(identity, r"^[0-9a-f]{64}$")
        self.assertIn(identity, provision.description_for(req, GOVERNANCE_SHA))
        self.assertNotEqual(identity, provision.identity(
            request("a" * 63 + "b"), GOVERNANCE_SHA))
        self.assertNotEqual(identity, provision.identity(req, "c" * 40))
        self.assertEqual(provision.marker_for(req, GOVERNANCE_SHA)["request_identity"],
                         identity)

        # provisioning:L12-U1: replay no repite create/bootstrap.
        result = provision.provision(req, created, {}, GOVERNANCE_SHA)
        self.assertEqual(result["status"], "confirmed")
        self.assertFalse(result["bootstrapped"])
        self.assertEqual(created.calls.count("bootstrap"), 1)
        self.assertEqual(created.calls.count("create"), 1)

    def test_falla_cerrado(self):
        # project-dna:L50-U1: v1 rechaza cambios incompatibles de base.
        baseline = discover_project_dna(paths=["package.json"])
        for mutated in (
            {**baseline, "version": 2},
            {**baseline, "unversioned_field": "new"},
            {k: v for k, v in baseline.items() if k != "extensions"},
        ):
            with self.subTest(case="base incompatible"), self.assertRaises(ProjectDnaError):
                validate_project_dna(mutated)
        modified = copy.deepcopy(baseline)
        modified["capabilities"] = ["unproven"]
        with self.assertRaisesRegex(ProjectDnaError, "fingerprint"):
            validate_project_dna(modified)
        for paths in (["/absolute/secret"], ["a/../secret"], "invalid"):
            with self.subTest(paths=paths), self.assertRaises(ProjectDnaError):
                discover_project_dna(paths=paths)

        # provisioning:L5-U1/L5-U2/L7-U2: owner y privacidad obligatorios.
        req = request()
        with self.assertRaises(provision.ProvisionError):
            provision.validate_request(request(repository="other/FixtureProject"))
        for candidate in (repo(req, private=False),
                          repo(req, description="foreign"),
                          repo(req, branch="main")):
            gateway = FakeGateway(candidate, empty=False)
            with self.subTest(candidate=candidate), self.assertRaises(provision.ProvisionError):
                provision.provision(req, gateway, {}, GOVERNANCE_SHA)
            self.assertNotIn("bootstrap", gateway.calls)

        # provisioning:L8-U1: credencial ausente detiene antes de cualquier I/O.
        for token in ("", "   "):
            with mock.patch.object(provision, "urlopen",
                                   side_effect=AssertionError("red no autorizada")) as net:
                with self.assertRaises(provision.ProvisionError):
                    provision.GitHubGateway(token)
                net.assert_not_called()

        # provisioning:L12-U2: marcador ajeno, repo no vacío o identidad
        # distinta no adoptan ni escriben nada.
        with self.assertRaises(provision.ProvisionError):
            provision.provision(req, FakeGateway(
                repo(req), marker=provision.marker_for(request("c" * 64),
                                                      GOVERNANCE_SHA)
            ), {}, GOVERNANCE_SHA)
        with self.assertRaises(provision.ProvisionError):
            provision.provision(req, FakeGateway(repo(req), empty=False),
                                {}, GOVERNANCE_SHA)
        with self.assertRaises(provision.ProvisionError):
            provision.provision(req, FakeGateway(
                {**repo(req), "full_name": "pl0n3r/Other"}
            ), {}, GOVERNANCE_SHA)

    def test_sin_datos_reales(self):
        # provisioning:L6-U1/L8-U2: sin fallback GITHUB_TOKEN y sin filtrar
        # la credencial ficticia en mensajes de error o argumentos git.
        fake_token = "synthetic-fixture-token"
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "synthetic-gh-token"},
                             clear=True):
            with self.assertRaises(provision.ProvisionError) as missing:
                provision.GitHubGateway("")
        self.assertNotIn("synthetic-gh-token", str(missing.exception))
        gw = provision.GitHubGateway(fake_token)
        with mock.patch.object(gw, "_request", return_value={"login": "unauthorized"}):
            with self.assertRaises(provision.ProvisionError) as err:
                gw.authorize()
        self.assertNotIn(fake_token, str(err.exception))
        with mock.patch.object(provision.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, "", "")) as run, \
             mock.patch.object(gw, "_request", return_value={}):
            gw.bootstrap(request()["target_repository"], {"AGENTES.md": "demo"},
                         provision.marker_for(request(), GOVERNANCE_SHA))
        for call in run.call_args_list:
            self.assertNotIn(fake_token, repr(call.args))
            self.assertNotIn("synthetic-gh-token", repr(call.args))

    def test_gate_validar_presente(self):
        # Validar exact-HEAD es un gate de CI externo: jamás fingir éxito
        # con un unittest; se verifica realmente en el PR.
        blocked = FakeGateway(owner=False)
        with self.assertRaises(provision.ProvisionError):
            provision.provision(request(), blocked, {}, GOVERNANCE_SHA)
        self.assertEqual(blocked.calls, ["authorize"])


if __name__ == "__main__":
    unittest.main()

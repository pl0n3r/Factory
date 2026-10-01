import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import provision_project as p

ROOT, SHA = Path(__file__).resolve().parents[1], "b" * 40


def request(key="a" * 64):
    return {"project_id": "project-newproduct", "project_slug": "newproduct", "target_repository": "pl0n3r/NewProduct", "governance_ref": p.GOVERNANCE_REF, "idempotency_key": key}


def repo(req, private=True, default_branch=None):
    return {"full_name": req["target_repository"], "description": p.description_for(req, SHA), "private": private, "default_branch": default_branch}


class FakeGateway:
    def __init__(self, repository=None, marker=None, empty=True):
        self.repo, self.mark, self.is_empty = repository, marker, empty
        self.creates = self.bootstraps = self.authorizations = 0
    def authorize(self): self.authorizations += 1
    def repository(self, _): return self.repo
    def create(self, req, sha): self.creates += 1; self.repo = repo(req); return self.repo
    def empty(self, _): return self.is_empty
    def marker(self, _): return self.mark
    def set_default(self, _): self.repo["default_branch"] = "main"
    def bootstrap(self, _, files, marker): self.bootstraps += 1; self.files, self.mark = files, marker; self.repo["default_branch"] = "main"


class ProvisionProjectTests(unittest.TestCase):
    def test_contract_validates_inputs_and_uses_external_authority(self):
        g = FakeGateway()
        self.assertTrue(p.provision(request(), g, {}, SHA)["created"])
        self.assertEqual((g.creates, g.bootstraps, g.authorizations), (1, 1, 1))
        invalid = {**request(), "extra": "x"}
        with self.assertRaises(p.ProvisionError):
            p.validate_request(invalid)
        with self.assertRaises(p.ProvisionError):
            p.validate_sha("bad")
        auth = p.GitHubGateway("token")
        with mock.patch.object(auth, "_request", return_value={"login": "other"}):
            with self.assertRaises(p.ProvisionError):
                auth.authorize()

    def test_retry_is_idempotent(self):
        g = FakeGateway()
        p.provision(request(), g, {}, SHA)
        second = p.provision(request(), g, {}, SHA)
        self.assertFalse(second["bootstrapped"])
        partial = FakeGateway(repo(request()), marker=p.marker_for(request(), SHA))
        self.assertFalse(p.provision(request(), partial, {}, SHA)["bootstrapped"])
        self.assertEqual(partial.repo["default_branch"], "main")
        self.assertEqual((g.creates, g.bootstraps), (1, 1))

    def test_conflict_invalid_owner_and_missing_token_fail_closed(self):
        req = request()
        for bad in (repo(req, private=False), {**repo(req), "description": "otro"}):
            g = FakeGateway(bad)
            with self.assertRaises(p.ProvisionError): p.provision(req, g, {}, SHA)
            self.assertEqual(g.bootstraps, 0)
        invalid = {**req, "target_repository": "other/x"}
        gateway = FakeGateway()
        with self.assertRaises(p.ProvisionError):
            p.provision(invalid, gateway, {}, SHA)
        with self.assertRaises(p.ProvisionError):
            p.GitHubGateway("")

    def test_bootstrap_uses_canonical_template(self):
        files = p.load_template(ROOT / "template")
        self.assertTrue(p.REQUIRED.issubset(files))
        workflow = (ROOT / ".github/workflows/provision-project.yml").read_text()
        for text in ("ref: " + "$" + "{{ github.sha }}", "path: runtime", "ref: v1", "path: governance", "--template governance/template", "--governance-sha"):
            self.assertIn(text, workflow)
        gateway = p.GitHubGateway("secret-token")
        done = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(p.subprocess, "run", return_value=done) as run, mock.patch.object(gateway, "_request", return_value={}):
            gateway.bootstrap("pl0n3r/NewProduct", {"AGENTES.md": "x"}, p.marker_for(request(), SHA))
        commands = json.dumps([call.args[0] for call in run.call_args_list])
        self.assertNotIn("secret-token", commands)
        self.assertEqual(sum("push" in call.args[0] for call in run.call_args_list), 1)

    def test_create_adopt_retry_conflict_are_offline(self):
        req = request()
        with mock.patch.object(p, "urlopen", side_effect=AssertionError("network")):
            created = FakeGateway(); p.provision(req, created, {}, SHA)
            adopted = FakeGateway(repo(req)); self.assertTrue(p.provision(req, adopted, {}, SHA)["bootstrapped"])
            self.assertFalse(p.provision(req, adopted, {}, SHA)["bootstrapped"])
            conflict = FakeGateway(repo(req), empty=False)
            with self.assertRaises(p.ProvisionError): p.provision(req, conflict, {}, SHA)
        other = request("a" * 63 + "b")
        self.assertNotEqual(p.description_for(req, SHA), p.description_for(other, SHA))
        self.assertIn(p.identity(req, SHA), p.description_for(req, SHA))

    def test_failure_boundaries_and_gateway_paths_are_covered(self):
        self.test_gateway_helpers_cover_http_marker_and_fail_closed_branches()
        self.test_template_and_provision_failure_edges_are_reversible()

    def test_workflow_documents_minimum_credential(self):
        workflow = (ROOT / ".github/workflows/provision-project.yml").read_text()
        docs = (ROOT / "docs/provisioning.md").read_text()
        for name in request(): self.assertIn(f"{name}:", workflow)
        for text in ("FACTORY_PROVISION_TOKEN", "github.repository_owner", "contents: read", "persist-credentials: false"): self.assertIn(text, workflow)
        for text in ("privados", "antes del checkout", "única ruta soportada", "implementación interna", "GIT_ASKPASS"): self.assertIn(text, docs)
        self.assertNotIn("github.token", workflow)


    def test_gateway_helpers_cover_http_marker_and_fail_closed_branches(self):
        gateway = p.GitHubGateway(" token ")
        self.assertEqual(gateway.token, "token")
        with self.assertRaisesRegex(p.ProvisionError, "Ruta GitHub"):
            gateway._request("GET", "relative")

        class Resp:
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return self.payload

        with mock.patch.object(p, "urlopen", return_value=Resp(b'{"ok":true}')):
            self.assertEqual(gateway._request("GET", "/x"), {"ok": True})
        with mock.patch.object(p, "urlopen", return_value=Resp(b"")):
            self.assertIsNone(gateway._request("GET", "/x"))

        from urllib.error import HTTPError
        allowed = HTTPError("https://x", 404, "no", {}, None)
        with mock.patch.object(p, "urlopen", side_effect=allowed):
            self.assertIsNone(gateway._request("GET", "/x", allow=(404,)))
        denied = HTTPError("https://x", 500, "no", {}, None)
        with mock.patch.object(p, "urlopen", side_effect=denied):
            with self.assertRaisesRegex(p.ProvisionError, "500"):
                gateway._request("GET", "/x")

        with mock.patch.object(gateway, "_request", return_value=[]):
            with self.assertRaisesRegex(p.ProvisionError, "Respuesta GitHub"):
                gateway.repository("pl0n3r/X")
        with mock.patch.object(gateway, "_request", return_value=[]):
            with self.assertRaisesRegex(p.ProvisionError, "repositorio creado"):
                gateway.create(request(), SHA)

        with mock.patch.object(gateway, "_request", return_value=None):
            self.assertTrue(gateway.empty("pl0n3r/X"))
            self.assertIsNone(gateway.marker("pl0n3r/X"))
        with mock.patch.object(gateway, "_request", return_value={"bad": True}):
            with self.assertRaisesRegex(p.ProvisionError, "Marker remoto"):
                gateway.marker("pl0n3r/X")
        marker = p.marker_for(request(), SHA)
        encoded = p.base64.b64encode(json.dumps(marker).encode()).decode()
        with mock.patch.object(gateway, "_request", return_value={"encoding": "base64", "content": encoded}):
            self.assertEqual(gateway.marker("pl0n3r/X"), marker)
        with mock.patch.object(gateway, "_request", return_value={"encoding": "base64", "content": "%%%"}):
            with self.assertRaisesRegex(p.ProvisionError, "ilegible"):
                gateway.marker("pl0n3r/X")

        failed = subprocess.CompletedProcess([], 1, "", "bad")
        with mock.patch.object(p.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(p.ProvisionError, "Git no pudo"):
                gateway._git(Path("."), "status")

    def test_template_and_provision_failure_edges_are_reversible(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            with self.assertRaisesRegex(p.ProvisionError, "no existe"):
                p.load_template(base / "missing")

            template = base / "template"
            template.mkdir()
            for rel in p.REQUIRED:
                path = template / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")
            self.assertEqual(set(p.load_template(template)), p.REQUIRED)
            (template / p.MARKER_PATH).parent.mkdir(parents=True, exist_ok=True)
            (template / p.MARKER_PATH).write_text("x")
            with self.assertRaisesRegex(p.ProvisionError, "inválido"):
                p.load_template(template)

        req = request()
        bad_created = FakeGateway(repository=None)
        def create_bad(_req, _sha):
            return {"full_name": "pl0n3r/Wrong", "private": True}
        bad_created.create = create_bad
        with self.assertRaisesRegex(p.ProvisionError, "identidad"):
            p.provision(req, bad_created, {}, SHA)

        expected = p.marker_for(req, SHA)
        wrong_marker = FakeGateway(repo(req), marker={**expected, "project_slug": "other"})
        with self.assertRaisesRegex(p.ProvisionError, "otra intención"):
            p.provision(req, wrong_marker, {}, SHA)

        class BrokenFinal(FakeGateway):
            def bootstrap(self, _, files, marker):
                self.bootstraps += 1
                self.mark = marker
                self.repo["default_branch"] = "dev"
        broken = BrokenFinal(repo(req), marker=None)
        with self.assertRaisesRegex(p.ProvisionError, "estado canónico"):
            p.provision(req, broken, {}, SHA)

        gateway = p.GitHubGateway("token")
        with self.assertRaisesRegex(p.ProvisionError, "Repositorio inválido"):
            gateway.bootstrap("other/repo", {}, expected)
        for bad_path, content in (("../x", "x"), ("/abs", "x"), (".git/config", "x"), ("ok", 123)):
            with self.subTest(path=bad_path):
                with self.assertRaisesRegex(p.ProvisionError, "Ruta inválida"):
                    gateway.bootstrap("pl0n3r/NewProduct", {bad_path: content}, expected)


if __name__ == "__main__":
    unittest.main()

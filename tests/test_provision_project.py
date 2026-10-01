import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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

    def test_gateway_and_main_cover_fail_closed_edges(self):
        for bad in (
            {**request(), "project_id": "bad"},
            {**request(), "target_repository": "other/repo"},
            {**request(), "governance_ref": "main"},
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(p.ProvisionError):
                    p.validate_request(bad)

        gateway = p.GitHubGateway("token")
        with self.assertRaises(p.ProvisionError):
            gateway._request("GET", "repos/no-leading-slash")

        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return b'{"ok":true}'

        with mock.patch.object(p, "urlopen", return_value=Response()):
            self.assertEqual(gateway._request("GET", "/user"), {"ok": True})

        allowed = p.HTTPError("https://x", 404, "not found", {}, None)
        with mock.patch.object(p, "urlopen", side_effect=allowed):
            self.assertIsNone(gateway._request("GET", "/missing", allow=(404,)))
        denied = p.HTTPError("https://x", 500, "bad", {}, None)
        with mock.patch.object(p, "urlopen", side_effect=denied):
            with self.assertRaises(p.ProvisionError):
                gateway._request("GET", "/broken")

        failed = subprocess.CompletedProcess([], 1, "", "boom")
        with mock.patch.object(p.subprocess, "run", return_value=failed):
            with self.assertRaises(p.ProvisionError):
                gateway._git(ROOT, "status")

        with mock.patch.object(gateway, "_request", return_value=[]):
            with self.assertRaises(p.ProvisionError):
                gateway.repository("pl0n3r/NewProduct")
        with mock.patch.object(gateway, "_request", return_value=None):
            with self.assertRaises(p.ProvisionError):
                gateway.create(request(), SHA)
        with mock.patch.object(gateway, "_request", return_value=None):
            self.assertTrue(gateway.empty("pl0n3r/NewProduct"))
        with mock.patch.object(gateway, "_request", return_value={}):
            with self.assertRaises(p.ProvisionError):
                gateway.empty("pl0n3r/NewProduct")
        with mock.patch.object(
            gateway,
            "_request",
            return_value={"encoding": "base64", "content": "%%%"},
        ):
            with self.assertRaises(p.ProvisionError):
                gateway.marker("pl0n3r/NewProduct")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(p.ProvisionError):
                p.load_template(root)
            (root / "AGENTES.md").write_text("x", encoding="utf-8")
            link = root / "link"
            try:
                link.symlink_to(root / "AGENTES.md")
            except OSError:
                pass
            else:
                with self.assertRaises(p.ProvisionError):
                    p.load_template(root)

        req = request()
        bad_created = FakeGateway()
        bad_created.create = lambda req, sha: {
            **repo(req),
            "full_name": "pl0n3r/Wrong",
        }
        with self.assertRaises(p.ProvisionError):
            p.provision(req, bad_created, {}, SHA)

        success = {"status": "confirmed"}
        with (
            mock.patch.object(p, "GitHubGateway", return_value=object()),
            mock.patch.object(p, "load_template", return_value={}),
            mock.patch.object(p, "provision", return_value=success),
            mock.patch.object(
                p.sys,
                "argv",
                ["provision_project.py", "--governance-sha", SHA],
            ),
            mock.patch.dict(
                p.os.environ,
                {
                    "FACTORY_PROVISION_TOKEN": "token",
                    **{name.upper(): value for name, value in request().items()},
                },
                clear=True,
            ),
            redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(p.main(), 0)
        self.assertIn("confirmed", output.getvalue())

        with (
            mock.patch.object(p, "GitHubGateway", side_effect=p.ProvisionError("bad")),
            mock.patch.object(
                p.sys,
                "argv",
                ["provision_project.py", "--governance-sha", SHA],
            ),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(p.main(), 2)

    def test_workflow_documents_minimum_credential(self):
        workflow = (ROOT / ".github/workflows/provision-project.yml").read_text()
        docs = (ROOT / "docs/provisioning.md").read_text()
        for name in request(): self.assertIn(f"{name}:", workflow)
        for text in ("FACTORY_PROVISION_TOKEN", "github.repository_owner", "contents: read", "persist-credentials: false"): self.assertIn(text, workflow)
        for text in ("privados", "antes del checkout", "única ruta soportada", "implementación interna", "GIT_ASKPASS"): self.assertIn(text, docs)
        self.assertNotIn("github.token", workflow)


if __name__ == "__main__":
    unittest.main()

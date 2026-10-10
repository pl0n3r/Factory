import re, unittest
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

R = Path(__file__).resolve().parents[1]
W = (R / ".github/workflows/coordinacion.yml").read_text()
TEMPLATE = (R / "template/.github/workflows/coordinacion.yml").read_text()
SCRIPT = (R / "scripts/coordinar_trabajo.py").read_text()

PERMISSION_LEVEL = {"none": 0, "read": 1, "write": 2}


def job_blocks(workflow: str) -> dict[str, str]:
    jobs = workflow.split("\njobs:\n", 1)[1]
    matches = list(re.finditer(r"(?m)^  ([A-Za-z0-9_-]+):\n", jobs))
    return {
        match.group(1): jobs[match.start(): matches[index + 1].start()]
        if index + 1 < len(matches) else jobs[match.start():]
        for index, match in enumerate(matches)
    }


def strict_caller_fixture(value: str) -> str:
    """Fuerza el contrato preflight en un template legacy, sin depender de otra rama."""
    if "\n  preflight_comentario:\n" in value:
        return value
    prefix, comment = value.split("  comentario:\n", 1)
    old_guard, remainder = comment.split("    # El reusable", 1)
    if "github.event_name == 'issue_comment'" not in old_guard:
        raise AssertionError("Falta el guard legacy del comentario")
    preflight = """  preflight_comentario:
    if: >-
      github.event_name == 'issue_comment' &&
      github.event.issue.pull_request == null &&
      github.event.sender.login == github.event.comment.user.login
    runs-on: ubuntu-latest
    permissions:
      contents: read
    outputs:
      route: DOLLAR_SIGN{{ steps.route.outputs.route }}
    steps:
      - id: route
        shell: bash
        run: |
          python3 - <<'PY'
          import json
          import os
          with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as source:
              event = json.load(source)
          body = event.get("comment", {}).get("body", "")
          parts = body.strip().split(maxsplit=1) if isinstance(body, str) else []
          supported = {"/tomar", "/renovar-contrato"}
          route = bool(parts and parts[0] in supported)
          with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
              output.write(f"route={str(route).lower()}\\n")
          PY

""".replace("DOLLAR_SIGN", "$")
    strict_guard = """    needs: preflight_comentario
    if: >-
      github.event_name == 'issue_comment' &&
      github.event.issue.pull_request == null &&
      github.event.sender.login == github.event.comment.user.login &&
      needs.preflight_comentario.outputs.route == 'true'
"""
    return prefix + preflight + "  comentario:\n" + strict_guard + "    # El reusable" + remainder


def permissions(block: str) -> dict[str, str]:
    match = re.search(r"(?m)^    permissions:\n((?:      [^\n]+\n)+)", block)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        key, value = line.strip().split(":", 1)
        result[key] = value.strip()
    return result


class T(unittest.TestCase):
    def test_profile_input_is_allowlisted(self):
        """El reusable acepta solo los perfiles ES/EN definidos por Factory."""
        self.assertIn("profile:", W)
        self.assertIn("default: 'es'", W)
        self.assertRegex(W, r'case "\$PROFILE" in es\|en\)')
        self.assertNotIn("profile_prefix", W)

    def test_pins(self):
        actions = re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s]+)", W, re.M)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"@[0-9a-f]{40}$")

    def test_template_callers_grant_reusable_permission_envelope(self):
        """Cada caller concede el máximo envelope que GitHub valida al cargar el reusable."""
        reusable_jobs = job_blocks(W)
        maximum = {}
        for block in reusable_jobs.values():
            for scope, level in permissions(block).items():
                if PERMISSION_LEVEL[level] > PERMISSION_LEVEL.get(maximum.get(scope, "none"), 0):
                    maximum[scope] = level

        self.assertEqual(maximum.get("checks"), "write")
        callers = {
            name: block
            for name, block in job_blocks(TEMPLATE).items()
            if "uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1" in block
        }
        self.assertTrue(callers)
        for name, block in callers.items():
            granted = permissions(block)
            for scope, required in maximum.items():
                self.assertGreaterEqual(
                    PERMISSION_LEVEL.get(granted.get(scope, "none"), 0),
                    PERMISSION_LEVEL[required],
                    f"{name} no concede {scope}: {required}",
                )

        self.assertIn("create_failed_check(", SCRIPT)

    def test_v1_0_18_caller_permission_envelope_starts_comment_label_pr_issue_and_validate(self):
        """AC-01: el reusable completo cabe en el envelope histórico sin actions:read."""
        legacy = {
            "contents": "write",
            "issues": "write",
            "pull-requests": "write",
            "checks": "write",
        }
        maximum = {}
        for block in job_blocks(W).values():
            for scope, level in permissions(block).items():
                if PERMISSION_LEVEL[level] > PERMISSION_LEVEL.get(maximum.get(scope, "none"), 0):
                    maximum[scope] = level
        self.assertNotIn("actions", maximum)
        for scope, required in maximum.items():
            self.assertGreaterEqual(
                PERMISSION_LEVEL.get(legacy.get(scope, "none"), 0),
                PERMISSION_LEVEL[required],
                f"caller v1.0.18 no concede {scope}: {required}",
            )

    def test_sweep_does_not_raise_reusable_permission_envelope_for_non_sweep_operations(self):
        """AC-02: sweep verifica workflow_success sin exigir actions al caller."""
        sweep = permissions(job_blocks(W)["sweep"])
        self.assertNotIn("actions", sweep)
        self.assertEqual(sweep.get("contents"), "write")
        self.assertEqual(sweep.get("issues"), "write")
        self.assertIn("PUBLIC_WORKFLOW_RUN_REPOS", SCRIPT)
        self.assertIn("self.public_request(", SCRIPT)

    def test_template_remains_backward_compatible_with_v1_permission_envelope(self):
        """AC-05: el template no obliga a consumidores históricos a añadir actions:read."""
        callers = {
            name: block
            for name, block in job_blocks(TEMPLATE).items()
            if "uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1" in block
        }
        self.assertTrue(callers)
        for name, block in callers.items():
            self.assertNotIn(
                "actions",
                permissions(block),
                f"{name} amplía innecesariamente el envelope histórico",
            )

    def test_template_supports_contract_renewal_command(self):
        """El caller antiguo y el preflight estricto conservan renovación v2."""
        for variant, template in (
            ("legacy_actual", TEMPLATE),
            ("preflight_estricto", strict_caller_fixture(TEMPLATE)),
        ):
            with self.subTest(variant=variant):
                self.assert_template_renewal_contract(template)

    def assert_template_renewal_contract(self, template: str):
        jobs = job_blocks(template)
        comment = jobs["comentario"]
        self.assertIn("uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1", comment)
        self.assertIn("operation: comment", comment)
        self.assertIn("github.event.issue.pull_request == null", comment)
        self.assertIn("github.event.sender.login == github.event.comment.user.login", comment)
        if "preflight_comentario" in jobs:
            preflight = jobs["preflight_comentario"]
            self.assertIn("needs: preflight_comentario", comment)
            self.assertIn("needs.preflight_comentario.outputs.route == 'true'", comment)
            self.assertIn("outputs:\n      route: ${{ steps.route.outputs.route }}", preflight)
            self.assertIn("- id: route", preflight)
            self.assertIn('os.environ["GITHUB_EVENT_PATH"]', preflight)
            self.assertNotIn("COMMENT_BODY", preflight)
            self.assertNotIn("github.event.comment.body", preflight)
            self.assertIn('"/renovar-contrato"', preflight)
            self.assertNotIn("contains(github.event.comment.body", comment)

            # Ejecutar el Python real del preflight: una mención en prosa
            # no puede convertirse en comando, pero el primer token sí enruta.
            embedded = preflight.split("python3 - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
            script = textwrap.dedent(embedded)
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "route"
                for body, expected in (
                    ("Nota informativa sobre /renovar-contrato UUID", "route=false\n"),
                    ("No ejecuté /tomar", "route=false\n"),
                    (" /renovar-contrato 12345678-abcd-1234-abcd-123456789abc ", "route=true\n"),
                    ("/tomar", "route=true\n"),
                    (" \n/tomar\t", "route=true\n"),
                ):
                    with self.subTest(body=body):
                        event_path = Path(tmp) / "event.json"
                        event_path.write_text(
                            json.dumps({"comment": {"body": body}}), encoding="utf-8"
                        )
                        env = {
                            **os.environ,
                            "GITHUB_EVENT_PATH": str(event_path),
                            "GITHUB_OUTPUT": str(output),
                        }
                        env.pop("COMMENT_BODY", None)
                        result = subprocess.run(
                            [sys.executable, "-c", script],
                            env=env,
                            text=True, capture_output=True, timeout=5, check=False,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertEqual(result.stderr, "")
                        self.assertEqual(output.read_text(encoding="utf-8"), expected)
                        output.unlink()
        else:
            # Soportar el caller v1 previo sin exigir el contains inseguro.
            self.assertIn("startsWith(github.event.comment.body, '/renovar-contrato ')", comment)
        self.assertIn('("/renovar-contrato ", "renovar-contrato")', SCRIPT)

    def test_merged_pr_validation_is_neutral(self):
        """AC-01: el reusable neutraliza únicamente un PR ya fusionado."""
        block = job_blocks(W)["validar-pr"]
        self.assertIn("inputs.operation == 'validate'", block)
        self.assertIn("github.event_name == 'pull_request'", block)
        self.assertIn("github.event.pull_request.merged == true", block)
        self.assertIn("!(", block)
        self.assertIn(
            "python3 .factory/scripts/coordinar_trabajo.py validar-pr",
            block,
        )

    def test_release_candidate_keeps_downstream_coordination_contract(self):
        """El artefacto publicable conserva el caller @v1 y la capacidad fail-closed."""
        callers = [
            block
            for block in job_blocks(TEMPLATE).values()
            if "uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1" in block
        ]
        self.assertTrue(callers)
        self.assertTrue(all("checks: write" in block for block in callers))
        self.assertIn("checks: write", job_blocks(W)["comentario"])
        self.assertIn("create_failed_check(", SCRIPT)

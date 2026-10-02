import re, unittest
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
        """El caller enruta la renovación v2 que ya soporta el coordinador."""
        self.assertIn(
            "startsWith(github.event.comment.body, '/renovar-contrato ')",
            TEMPLATE,
        )
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

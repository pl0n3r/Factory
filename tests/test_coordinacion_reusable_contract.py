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

    def test_template_supports_contract_renewal_command(self):
        """El caller enruta la renovación v2 que ya soporta el coordinador."""
        self.assertIn(
            "startsWith(github.event.comment.body, '/renovar-contrato ')",
            TEMPLATE,
        )
        self.assertIn('("/renovar-contrato ", "renovar-contrato")', SCRIPT)

    def test_validate_job_skips_merged_pull_request(self):
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

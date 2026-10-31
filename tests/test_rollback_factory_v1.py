"""Factory #1957: rollback del tag mayor en un repositorio local desechable."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "rollback-factory-v1.md"


class RollbackFactoryV1Tests(unittest.TestCase):
    """Las operaciones de Git nunca usan el repo de trabajo ni un remoto."""

    @staticmethod
    def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
        )

    def make_lab(self, directory: str) -> tuple[Path, str, str, str, str]:
        repo = Path(directory) / "repositorio-falso"
        repo.mkdir()
        self.git(repo, "init", "--quiet")
        author = ("-c", "user.name=Ensayo", "-c", "user.email=ensayo@example.invalid")
        self.git(repo, *author, "commit", "--quiet", "--allow-empty", "-m", "baseline")
        stable_commit = self.git(repo, "rev-parse", "HEAD").stdout.strip()
        self.git(repo, *author, "tag", "-a", "v1", "-m", "v1 stable", stable_commit)
        original_object = self.git(repo, "rev-parse", "refs/tags/v1").stdout.strip()
        self.git(repo, *author, "commit", "--quiet", "--allow-empty", "-m", "candidate")
        candidate_commit = self.git(repo, "rev-parse", "HEAD").stdout.strip()
        self.git(repo, *author, "tag", "-a", "v1-lab-candidate", "-m", "v1 test", candidate_commit)
        candidate_object = self.git(repo, "rev-parse", "refs/tags/v1-lab-candidate").stdout.strip()
        self.assertEqual(self.git(repo, "remote").stdout.strip(), "")
        return repo, stable_commit, candidate_commit, original_object, candidate_object

    def drill(self, repo: Path, stable: str, candidate: str, original: str, newer: str) -> list[str]:
        """CAS de ida/vuelta, con comprobación del objeto anotado y SHA pelado."""
        trace: list[str] = []

        def observe(step: str, expected_object: str, expected_commit: str) -> None:
            actual_object = self.git(repo, "rev-parse", "refs/tags/v1").stdout.strip()
            actual_commit = self.git(repo, "rev-parse", "refs/tags/v1^{commit}").stdout.strip()
            self.assertEqual((actual_object, actual_commit), (expected_object, expected_commit))
            trace.append(f"{step}: objeto={actual_object}; commit={actual_commit}")

        observe("01-antes", original, stable)
        self.git(repo, "update-ref", "refs/tags/v1", newer, original)
        observe("02-movido", newer, candidate)
        self.git(repo, "update-ref", "refs/tags/v1", original, newer)
        observe("03-restaurado", original, stable)
        return trace

    def test_criterio_principal(self) -> None:
        """AC-01: guía completa, ensayo real local, SHA exactos y reversión."""
        doc = DOC.read_text(encoding="utf-8")
        for heading in (
            "## Alcance y autoridad", "## Inventario del SHA antes de mover",
            "## Procedimiento reservado al dueño", "## Ensayo en repositorio falso",
            "## Restauración y verificación", "## Aviso a consumidores",
        ):
            self.assertIn(heading, doc)
        for token in ("refs/tags/v1", "git update-ref", "^{commit}",
                      "compare-and-swap", "NO ejecutar sobre el repositorio real",
                      "ci.yml@v1", "SHA exacto"):
            self.assertIn(token, doc)
        self.assertNotIn("gh api -X PATCH repos/pl0n3r/Factory", doc)
        with tempfile.TemporaryDirectory(prefix="factory-v1-rollback-falso-") as temp:
            repo, stable, candidate, original, newer = self.make_lab(temp)
            trace = self.drill(repo, stable, candidate, original, newer)
            self.assertEqual(len(trace), 3)
            self.assertTrue(trace[0].startswith("01-antes:"))
            self.assertTrue(trace[1].startswith("02-movido:"))
            self.assertTrue(trace[2].startswith("03-restaurado:"))
            self.assertEqual(self.git(repo, "remote").stdout.strip(), "")
            for line in trace:
                print("SIMULACRO LOCAL", line)

    def test_cas_obsoleto_no_mueve_ref(self) -> None:
        """Una condición CAS caducada deniega el cambio sin alterar v1."""
        with tempfile.TemporaryDirectory(prefix="factory-v1-cas-falso-") as temp:
            repo, stable, _, original, newer = self.make_lab(temp)
            result = self.git(repo, "update-ref", "refs/tags/v1", newer, "0" * 40, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.git(repo, "rev-parse", "refs/tags/v1").stdout.strip(), original)
            self.assertEqual(self.git(repo, "rev-parse", "refs/tags/v1^{commit}").stdout.strip(), stable)

    def test_sin_remotos_ni_efectos_en_repositorio_real(self) -> None:
        with tempfile.TemporaryDirectory(prefix="factory-v1-no-remote-") as temp:
            repo, stable, candidate, original, newer = self.make_lab(temp)
            self.assertEqual(self.git(repo, "remote", "-v").stdout.strip(), "")
            self.drill(repo, stable, candidate, original, newer)
            self.assertNotEqual(repo, ROOT)
            self.assertEqual(self.git(repo, "remote", "-v").stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()

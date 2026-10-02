#!/usr/bin/env python3
"""Pruebas unitarias del coordinador multiagente de Condor."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import scripts.coordinar_trabajo as coordinator

from scripts.aceptacion_kit import contract_fingerprint
from scripts.coordinar_trabajo import (
    CoordinationError,
    GitHub,
    GitHubError,
    STATUS_AVAILABLE,
    STATUS_BLOCKED,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_RECOVERY,
    STATUS_RESERVED,
    STATUS_REVIEW,
    active_reservation,
    adopt_orphaned_contract,
    authorized,
    closing_issues,
    file_overlaps,
    issue_from_branch,
    latest_reservation,
    mark_stale_reservations,
    migrate_legacy_reservation,
    run_scheduled_sweep,
    sweep_satisfied_blocks,
    parse_comment_command,
    release_work,
    renew_pinned_acceptance,
    renewal_reservation_id,
    reservation_from_pr_body,
    reservation_marker,
    reserve_work,
    rewrite_pull_reservation,
    transfer_work,
    work_activity_timestamp,
    work_is_stale,
    update_issue_label_state,
    update_issue_state,
    update_pr_state,
    validate_pull,
)


BOT = "github-actions[bot]"
SESSION_A = "11111111-1111-4111-8111-111111111111"
SESSION_B = "22222222-2222-4222-8222-222222222222"


VALID_ACCEPTANCE_BODY = """### Contexto

Contexto de prueba.

### Alcance

Alcance de prueba.

### Fuera de alcance

Nada.

### Criterios de aceptación

- [ ] [AC-01] El gate base pasa.

### Contrato ejecutable

<!-- factory-acceptance {"version":1,"criteria":[{"id":"AC-01","kind":"check","target":"Tests de scripts"}]} -->
"""


class FakeGitHub:
    """Simula únicamente las operaciones de GitHub usadas por el coordinador."""

    def __init__(self) -> None:
        """Crea un repositorio falso con un Issue disponible."""
        self.repo = "pl0n3r/Condor"
        self.branches = {"main": "abc123"}
        self.issue_data = {
            "number": 12,
            "state": "open",
            "state_reason": None,
            "labels": [{"name": STATUS_AVAILABLE}],
            "body": VALID_ACCEPTANCE_BODY,
        }
        self.open_issue_data: list[dict] = [self.issue_data]
        self.comments: list[dict] = []
        self.pulls: dict[int, dict] = {}
        self.pull_files_map: dict[int, set[str]] = {}
        self.status_history: list[str | None] = []
        self.assignees: set[str] = set()
        self.fail_comment = False
        self.pull_update_failures_remaining = 0
        self.check_runs: list[dict] = []
        self.workflow_runs: dict[int, dict] = {}
        self.related_issues: dict[int, dict] = {}
        self.commit_times = {
            "abc123": datetime.now(timezone.utc),
        }

    def issue(self, number: int) -> dict:
        """Devuelve el Issue falso o una dependencia configurada."""
        if number == 12:
            return self.issue_data
        if number in self.related_issues:
            return self.related_issues[number]
        raise AssertionError(f"Issue falso desconocido: {number}")

    def pull(self, number: int) -> dict:
        """Devuelve un PR falso."""
        return self.pulls[number]

    def comment(self, issue_number: int, body: str) -> None:
        """Publica un comentario confiable del bot."""
        assert issue_number == 12
        if self.fail_comment:
            raise CoordinationError("fallo simulado de comentario")
        now = datetime.now(timezone.utc).isoformat()
        self.comments.append(
            {
                "body": body,
                "user": {"login": BOT},
                "created_at": now,
                "updated_at": now,
            }
        )

    def create_failed_check(
        self,
        name: str,
        head_sha: str,
        title: str,
        summary: str,
    ) -> None:
        """Registra un check failure falso sobre un SHA."""
        self.check_runs.append(
            {
                "name": name,
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": "failure",
                "title": title,
                "summary": summary,
            }
        )

    def set_status(self, issue_number: int, status: str | None) -> None:
        """Reemplaza el estado visible del Issue."""
        assert issue_number == 12
        current = [
            item
            for item in self.issue_data["labels"]
            if not (
                str(item["name"]).startswith("estado: ")
                or str(item["name"]).startswith("status: ")
            )
        ]
        if status:
            current.append({"name": status})
        self.issue_data["labels"] = current
        self.status_history.append(status)

    def branch_sha(self, branch: str) -> str | None:
        """Devuelve el SHA de una rama falsa."""
        return self.branches.get(branch)

    def create_branch(self, branch: str, sha: str) -> bool:
        """Crea una rama si no existe."""
        if branch in self.branches:
            return False
        self.branches[branch] = sha
        return True

    def delete_branch(self, branch: str) -> None:
        """Elimina una rama si existe."""
        self.branches.pop(branch, None)

    def issue_comments(self, issue_number: int) -> list[dict]:
        """Devuelve comentarios por Issue sin asumir un único objetivo."""
        if issue_number == 12:
            return list(self.comments)
        if any(issue.get("number") == issue_number for issue in self.open_issue_data):
            return []
        raise AssertionError(f"Issue falso desconocido: {issue_number}")

    def open_pulls(self) -> list[dict]:
        """Devuelve los PR falsos abiertos."""
        return [
            pull
            for pull in self.pulls.values()
            if pull.get("state", "open") == "open"
        ]

    def closed_pulls(self) -> list[dict]:
        """Devuelve los PR falsos cerrados."""
        return [
            pull
            for pull in self.pulls.values()
            if pull.get("state", "open") == "closed"
        ]

    def open_issues(self) -> list[dict]:
        """Devuelve los Issues abiertos configurados por cada prueba."""
        return [
            issue
            for issue in self.open_issue_data
            if issue.get("state", "open") == "open"
        ]

    def pull_files(self, number: int) -> set[str]:
        """Devuelve archivos de un PR falso."""
        return set(self.pull_files_map.get(number, set()))

    def close_pull(self, number: int) -> None:
        """Cierra un PR falso."""
        self.pulls[number]["state"] = "closed"

    def update_pull_body(self, number: int, body: str) -> None:
        """Actualiza el cuerpo del PR sin crear otro."""
        if self.pull_update_failures_remaining > 0:
            self.pull_update_failures_remaining -= 1
            raise CoordinationError("fallo simulado al actualizar PR")
        self.pulls[number]["body"] = body

    def commit_timestamp(self, sha: str):
        """Devuelve actividad conocida de un commit falso."""
        return self.commit_times.get(sha)

    def workflow_run(self, run_id: int) -> dict:
        """Devuelve evidencia de workflow configurada por la prueba."""
        return self.workflow_runs[run_id]

    def try_assign(self, issue_number: int, login: str) -> None:
        """Asigna el Issue."""
        assert issue_number == 12
        self.assignees.add(login)

    def try_unassign(self, issue_number: int, login: str) -> None:
        """Retira la asignación del Issue."""
        assert issue_number == 12
        self.assignees.discard(login)


def unblock_marker(*, version=1, **payload) -> str:
    """Construye el marker cerrado usado por los tests de unblock."""
    encoded = json.dumps(
        {"version": version, **payload},
        separators=(",", ":"),
    )
    return f"<!-- factory-unblock {encoded} -->"


def add_active_reservation(
    api: FakeGitHub,
    owner: str = "pl0n3r",
    reservation_id: str = SESSION_A,
    *,
    pinned: bool = True,
) -> None:
    """Inserta una reserva confiable activa en el fake."""
    branch = "trabajo/issue-12"
    api.branches[branch] = "abc123"
    api.set_status(12, STATUS_RESERVED)
    fingerprint = contract_fingerprint(VALID_ACCEPTANCE_BODY) if pinned else None
    api.comments.append(
        {
            "user": {"login": BOT},
            "body": reservation_marker(
                owner,
                reservation_id,
                branch,
                True,
                "tomar",
                fingerprint,
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )



class LimpiezaRamaTests(unittest.TestCase):
    """Cubre idempotencia y fail-closed al limpiar referencias Git."""

    def test_delete_branch_existing_succeeds_without_extra_lookup(self) -> None:
        """Una eliminación normal no realiza comprobaciones innecesarias."""
        api = GitHub("pl0n3r/Condor", "token-prueba")
        calls: list[str] = []

        def request(method, path, payload=None, allow=()):
            calls.append(method)
            return None

        api.request = request  # type: ignore[method-assign]
        api.delete_branch("trabajo/issue-19")
        self.assertEqual(calls, ["DELETE"])

    def test_delete_branch_ignores_422_only_when_reference_is_gone(self) -> None:
        """Un 422 por referencia ya eliminada se trata como éxito idempotente."""
        api = GitHub("pl0n3r/Condor", "token-prueba")

        def request(method, path, payload=None, allow=()):
            if method == "DELETE":
                raise GitHubError(422, "Reference does not exist")
            return None

        api.request = request  # type: ignore[method-assign]
        api.delete_branch("trabajo/issue-19")

    def test_delete_branch_keeps_422_when_reference_still_exists(self) -> None:
        """Un 422 real no se oculta si GitHub confirma que la rama existe."""
        api = GitHub("pl0n3r/Condor", "token-prueba")

        def request(method, path, payload=None, allow=()):
            if method == "DELETE":
                raise GitHubError(422, "Validation Failed")
            return {"object": {"sha": "abc123"}}

        api.request = request  # type: ignore[method-assign]
        with self.assertRaises(GitHubError):
            api.delete_branch("trabajo/issue-19")


class WorkflowCoordinacionTests(unittest.TestCase):
    """Cubre el cableado declarativo entre GitHub Events y el coordinador."""

    @staticmethod
    def yaml_block(text: str, header: str, indent: int) -> str:
        """Aísla una clave YAML por nivel para evitar falsos positivos globales."""
        lines = text.splitlines()
        target = (" " * indent) + header
        start = next(
            (index for index, line in enumerate(lines) if line == target),
            None,
        )
        if start is None:
            raise AssertionError(f"No existe la sección YAML {header!r}.")

        block = [lines[start]]
        for line in lines[start + 1 :]:
            stripped = line.lstrip()
            current_indent = len(line) - len(stripped)
            if stripped and not stripped.startswith("#") and current_indent <= indent:
                break
            block.append(line)

        return "\n".join(block)

    def test_issue_comment_routes_only_supported_commands_to_coordinator(self) -> None:
        """El job correcto recibe el evento, identidad y argumentos esperados."""
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "coordinacion-trabajo.yml"
        ).read_text(encoding="utf-8")

        event_block = self.yaml_block(workflow, "issue_comment:", 2)
        self.assertIn("types: [created, edited]", event_block)

        job_block = self.yaml_block(workflow, "comando-comentario:", 2)
        self.assertIn("github.event.issue.pull_request == null", job_block)
        self.assertIn(
            "github.event.sender.login == github.event.comment.user.login",
            job_block,
        )
        self.assertIn("github.event.comment.body == '/tomar'", job_block)
        self.assertIn("github.event.comment.body == '/liberar-forzado'", job_block)
        self.assertIn(
            "startsWith(github.event.comment.body, '/liberar ')",
            job_block,
        )
        self.assertIn(
            "startsWith(github.event.comment.body, '/transferir ')",
            job_block,
        )

        self.assertIn(
            "startsWith(github.event.comment.body, '/renovar-contrato ')",
            job_block,
        )
        comment_permissions = self.yaml_block(job_block, "permissions:", 4)
        self.assertIn("checks: write", comment_permissions)
        reusable = (
            Path(__file__).resolve().parents[1]
            / ".github" / "workflows" / "coordinacion.yml"
        ).read_text(encoding="utf-8")
        reusable_comment = self.yaml_block(reusable, "comentario:", 2)
        reusable_permissions = self.yaml_block(
            reusable_comment, "permissions:", 4
        )
        self.assertIn("checks: write", reusable_permissions)

        env_block = self.yaml_block(job_block, "env:", 8)
        self.assertIn(
            "ACTOR: ${{ github.event.comment.user.login }}",
            env_block,
        )
        self.assertIn(
            "ASOCIACION: ${{ github.event.comment.author_association }}",
            env_block,
        )
        self.assertIn("CUERPO: ${{ github.event.comment.body }}", env_block)

        self.assertIn(
            "python3 scripts/coordinar_trabajo.py comentario",
            job_block,
        )
        self.assertIn('--repo "$REPOSITORIO"', job_block)
        self.assertIn('--issue "$ISSUE"', job_block)
        self.assertIn('--actor "$ACTOR"', job_block)
        self.assertIn('--association "$ASOCIACION"', job_block)
        self.assertIn('--body "$CUERPO"', job_block)

        issues_block = self.yaml_block(workflow, "issues:", 2)
        self.assertIn("edited", issues_block)
        issue_job = self.yaml_block(workflow, "estado-issue:", 2)
        self.assertIn("github.event.action == 'edited'", issue_job)
        issue_permissions = self.yaml_block(issue_job, "permissions:", 4)
        self.assertIn("checks: write", issue_permissions)

    def test_label_event_does_not_expand_authority_or_permissions(self) -> None:
        """El label-event reconcilia estado con permisos mínimos."""
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/coordinacion-trabajo.yml").read_text(
            encoding="utf-8"
        )
        job = self.yaml_block(workflow, "reserva-silenciosa:", 2)
        permissions = self.yaml_block(job, "permissions:", 4)
        self.assertIn("contents: read", permissions)
        self.assertIn("issues: write", permissions)
        self.assertIn("pull-requests: read", permissions)
        self.assertNotIn("contents: write", permissions)
        self.assertNotIn("pull-requests: write", permissions)

        reusable = (root / ".github/workflows/coordinacion.yml").read_text(
            encoding="utf-8"
        )
        label_job = self.yaml_block(reusable, "etiqueta:", 2)
        reusable_permissions = self.yaml_block(label_job, "permissions:", 4)
        self.assertIn("contents: read", reusable_permissions)
        self.assertIn("issues: write", reusable_permissions)
        self.assertIn("pull-requests: read", reusable_permissions)
        self.assertNotIn("contents: write", reusable_permissions)
        self.assertNotIn("pull-requests: write", reusable_permissions)

        coordinator = (root / "scripts/coordinar_trabajo.py").read_text(
            encoding="utf-8"
        )
        handler_start = coordinator.index("def update_issue_label_state(")
        handler_end = coordinator.index(
            "\ndef invalidate_contract_drift_checks(",
            handler_start,
        )
        label_handler = coordinator[handler_start:handler_end]
        self.assertNotIn("reserve_work(", label_handler)
        self.assertNotIn('"OWNER"', label_handler)



class ReleaseOpenPullFeedbackTests(unittest.TestCase):
    """Cubre feedback y semántica de liberación cuando existe un PR abierto."""

    @staticmethod
    def _open_pull(api: FakeGitHub) -> None:
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": (
                f"Closes #12\nReserva: {SESSION_A}\n"
                f"<!-- condor-reserva-id: {SESSION_A} -->"
            ),
            "head": {"ref": "trabajo/issue-12", "sha": "abc123"},
            "base": {"ref": "main"},
        }

    def test_normal_release_with_open_pull_fails_closed_and_explains_blocker(self) -> None:
        api = FakeGitHub()
        add_active_reservation(api)
        self._open_pull(api)
        comments_before = list(api.comments)
        status_before = list(api.status_history)

        with self.assertRaisesRegex(CoordinationError, r"PR abiertos.*#15"):
            release_work(api, 12, "pl0n3r", "OWNER", SESSION_A, False)

        self.assertEqual(api.pulls[15]["state"], "open")
        self.assertIn("trabajo/issue-12", api.branches)
        self.assertEqual(api.comments, comments_before)
        self.assertEqual(api.status_history, status_before)
        active = active_reservation(api, 12)
        self.assertIsNotNone(active)
        assert active is not None
        self.assertTrue(active["active"])
        self.assertEqual(active["reservation_id"], SESSION_A)

    def test_force_release_with_open_pull_preserves_existing_semantics(self) -> None:
        api = FakeGitHub()
        add_active_reservation(api)
        self._open_pull(api)

        release_work(api, 12, "pl0n3r", "OWNER", None, True)

        self.assertEqual(api.pulls[15]["state"], "closed")
        self.assertNotIn("trabajo/issue-12", api.branches)
        latest = latest_reservation(api.comments)
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertFalse(latest["active"])
        self.assertEqual(latest["reason"], "liberacion-forzada")
        self.assertEqual(api.status_history[-1], STATUS_AVAILABLE)

    def test_normal_release_without_open_pull_still_releases(self) -> None:
        api = FakeGitHub()
        add_active_reservation(api)

        release_work(api, 12, "pl0n3r", "OWNER", SESSION_A, False)

        self.assertNotIn("trabajo/issue-12", api.branches)
        latest = latest_reservation(api.comments)
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertFalse(latest["active"])
        self.assertEqual(latest["reason"], "liberar")
        self.assertEqual(api.status_history[-1], STATUS_AVAILABLE)


class EstadoCoordinacionTests(unittest.TestCase):
    """Cubre transiciones de estado visibles sin ventanas intermedias inválidas."""

    def test_set_status_adds_target_before_removing_previous_labels(self) -> None:
        """El nuevo estado se publica antes de retirar estados anteriores."""
        api = GitHub("pl0n3r/Condor", "token-prueba")
        events: list[tuple[str, str]] = []

        api.ensure_status_labels = lambda: None  # type: ignore[method-assign]
        api.add_labels = (  # type: ignore[method-assign]
            lambda issue_number, labels: events.append(("add", labels[0]))
        )
        api.remove_label = (  # type: ignore[method-assign]
            lambda issue_number, label: events.append(("remove", label))
        )

        api.set_status(12, STATUS_REVIEW)

        self.assertEqual(events[0], ("add", STATUS_REVIEW))
        self.assertNotIn(("remove", STATUS_REVIEW), events)
        self.assertIn(("remove", STATUS_RESERVED), events)
        self.assertIn(("remove", STATUS_AVAILABLE), events)


class CoordinacionTests(unittest.TestCase):
    """Cubre contratos de reserva, sesión, transición y colisiones."""

    def test_issue_from_branch(self) -> None:
        """Extrae Issue únicamente de ramas canónicas."""
        self.assertEqual(issue_from_branch("trabajo/issue-12"), 12)
        self.assertEqual(issue_from_branch("trabajo/issue-999"), 999)
        self.assertIsNone(issue_from_branch("feature/algo"))
        self.assertIsNone(issue_from_branch("trabajo/issue-x"))

    def test_closing_issues(self) -> None:
        """Reconoce las referencias de cierre admitidas."""
        body = "Closes #12\nFixes #18\nresolves #21"
        self.assertEqual(closing_issues(body), {12, 18, 21})

    def test_reservation_from_pr_body(self) -> None:
        """Extrae el ID de sesión visible legacy u oculto."""
        self.assertEqual(
            reservation_from_pr_body(f"Closes #12\nReserva: {SESSION_A}"),
            SESSION_A,
        )
        self.assertEqual(
            reservation_from_pr_body(
                f"Closes #12\n<!-- condor-reserva-id: {SESSION_A} -->"
            ),
            SESSION_A,
        )
        self.assertIsNone(reservation_from_pr_body("Closes #12"))

    def test_authorized_associations(self) -> None:
        """Limita comandos a colaboradores reales."""
        self.assertTrue(authorized("OWNER"))
        self.assertTrue(authorized("MEMBER"))
        self.assertTrue(authorized("COLLABORATOR"))
        self.assertFalse(authorized("NONE"))
        self.assertFalse(authorized("CONTRIBUTOR"))

    def test_markers_from_untrusted_users_are_ignored(self) -> None:
        """Ignora marcadores falsificados por comentarios externos."""
        marker = reservation_marker(
            "intruso",
            SESSION_A,
            "trabajo/issue-12",
            False,
            "falso",
        )
        comments = [{"body": marker, "user": {"login": "intruso"}}]
        self.assertIsNone(latest_reservation(comments))

    def test_issue_body_marker_is_not_trusted(self) -> None:
        """Metadata editable del body no autentica una reserva."""
        api = FakeGitHub()
        api.issue_data["body"] = reservation_marker(
            "intruso",
            SESSION_B,
            "trabajo/issue-12",
            True,
            "falso",
        )

        self.assertIsNone(active_reservation(api, 12))

    def test_latest_reservation_prefers_last_trusted_marker(self) -> None:
        """Usa el último marcador válido publicado por el bot."""
        first = reservation_marker(
            "agente-a",
            SESSION_A,
            "trabajo/issue-12",
            True,
            "tomar",
        )
        second = reservation_marker(
            "agente-a",
            SESSION_A,
            "trabajo/issue-12",
            False,
            "liberar",
        )
        comments = [
            {"body": first, "user": {"login": BOT}},
            {"body": second, "user": {"login": BOT}},
        ]
        latest = latest_reservation(comments)
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertFalse(latest["active"])

    def test_reserve_work_rejects_noncanonical_ready_state(self) -> None:
        """Un estado visible no canónico no puede convertirse en éxito silencioso."""
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": "estado: listo"}]

        with self.assertRaisesRegex(
            CoordinationError,
            r"estado: listo.*estado: disponible",
        ):
            reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertNotIn("trabajo/issue-12", api.branches)
        self.assertIsNone(active_reservation(api, 12))
        self.assertEqual(api.assignees, set())

    def test_reserve_work_rejects_missing_canonical_state(self) -> None:
        """La ausencia de estado canónico falla con requisito explícito."""
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": "prioridad: media"}]

        with self.assertRaisesRegex(
            CoordinationError,
            r"sin estado canónico.*estado: disponible",
        ):
            reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertNotIn("trabajo/issue-12", api.branches)
        self.assertIsNone(active_reservation(api, 12))
        self.assertEqual(api.assignees, set())

    def test_blocked_issue_is_not_reserved(self) -> None:
        """Un Issue bloqueado conserva el no-op explícito y no crea autoridad."""
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        output = StringIO()

        with redirect_stdout(output):
            session = reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertIsNone(session)
        self.assertIn(STATUS_BLOCKED, output.getvalue())
        self.assertNotIn("trabajo/issue-12", api.branches)
        self.assertIsNone(active_reservation(api, 12))
        self.assertEqual(api.assignees, set())

    def test_reserve_work_creates_atomic_lock_and_session(self) -> None:
        """Una toma exitosa crea rama, estado y sesión única."""
        api = FakeGitHub()
        session = reserve_work(api, 12, "pl0n3r", "OWNER")
        self.assertIsNotNone(session)
        self.assertIn("trabajo/issue-12", api.branches)
        self.assertIn("pl0n3r", api.assignees)
        self.assertEqual(api.status_history[-1], STATUS_RESERVED)
        reservation = active_reservation(api, 12)
        self.assertIsNotNone(reservation)
        assert reservation is not None
        self.assertEqual(reservation["reservation_id"], session)
        self.assertEqual(len(api.comments), 1)
        self.assertTrue(api.comments[0]["body"].startswith("<!-- condor-reserva "))
        self.assertNotIn("Trabajo reservado", api.comments[0]["body"])

    def test_manual_reserved_label_without_authority_restores_available(self) -> None:
        """Un label manual no crea rama, marker ni assignee."""
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": STATUS_RESERVED}]

        update_issue_label_state(api, 12, "intruso", STATUS_RESERVED)

        self.assertEqual(api.status_history[-1], STATUS_AVAILABLE)
        self.assertNotIn("trabajo/issue-12", api.branches)
        self.assertIsNone(active_reservation(api, 12))
        self.assertEqual(api.assignees, set())

    def test_manual_reserved_label_keeps_blocked_issue_blocked(self) -> None:
        """Un Issue bloqueado conserva su estado sin fabricar autoridad."""
        api = FakeGitHub()
        api.issue_data["labels"] = [
            {"name": STATUS_BLOCKED},
            {"name": STATUS_RESERVED},
        ]

        update_issue_label_state(api, 12, "intruso", STATUS_RESERVED)

        self.assertEqual(api.status_history[-1], STATUS_BLOCKED)
        self.assertNotIn("trabajo/issue-12", api.branches)
        self.assertIsNone(active_reservation(api, 12))
        self.assertEqual(api.assignees, set())

    def test_manual_reserved_label_preserves_closed_terminal_state(self) -> None:
        """Un Issue cerrado conserva completed/cancelled según state_reason."""
        for state_reason, expected in (
            (None, STATUS_COMPLETED),
            ("not_planned", STATUS_CANCELLED),
        ):
            with self.subTest(state_reason=state_reason):
                api = FakeGitHub()
                api.issue_data["state"] = "closed"
                api.issue_data["state_reason"] = state_reason
                api.issue_data["labels"] = [{"name": STATUS_RESERVED}]

                update_issue_label_state(api, 12, "intruso", STATUS_RESERVED)

                self.assertEqual(api.status_history[-1], expected)
                self.assertNotIn("trabajo/issue-12", api.branches)
                self.assertIsNone(active_reservation(api, 12))

    def test_manual_reserved_label_preserves_recovery_required(self) -> None:
        """Un label manual no puede limpiar una recuperación pendiente."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.issue_data["labels"] = [
            {"name": STATUS_RECOVERY},
            {"name": STATUS_RESERVED},
        ]

        update_issue_label_state(api, 12, "intruso", STATUS_RESERVED)

        self.assertEqual(api.status_history[-1], STATUS_RECOVERY)
        self.assertEqual(
            active_reservation(api, 12)["reservation_id"],
            SESSION_A,
        )

    def test_reserved_label_reconciles_existing_trusted_reservation_without_rotation(self) -> None:
        """Una autoridad existente solo sincroniza su estado visible."""
        api = FakeGitHub()
        add_active_reservation(api)
        original = active_reservation(api, 12)
        assert original is not None

        update_issue_label_state(api, 12, "intruso", STATUS_RESERVED)

        current = active_reservation(api, 12)
        assert current is not None
        self.assertEqual(current["reservation_id"], original["reservation_id"])
        self.assertEqual(current["owner"], original["owner"])
        self.assertEqual(api.status_history[-1], STATUS_RESERVED)
        self.assertEqual(api.assignees, set())

        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": f"Closes #12\n<!-- condor-reserva-id: {SESSION_A} -->",
            "head": {
                "ref": "trabajo/issue-12",
                "sha": "head-review",
                "repo": {"full_name": api.repo},
            },
            "base": {"ref": "main"},
        }
        update_issue_label_state(api, 12, "intruso", STATUS_RESERVED)

        self.assertEqual(api.status_history[-1], STATUS_REVIEW)
        self.assertEqual(
            active_reservation(api, 12)["reservation_id"],
            original["reservation_id"],
        )

    def test_reserved_label_ignores_same_ref_from_fork(self) -> None:
        """Un PR de fork con el mismo ref no promueve el Issue a review."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "head": {
                "ref": "trabajo/issue-12",
                "sha": "fork-head",
                "repo": {"full_name": "intruso/fork"},
            },
            "base": {"ref": "main"},
        }

        update_issue_label_state(api, 12, "intruso", STATUS_RESERVED)

        self.assertEqual(api.status_history[-1], STATUS_RESERVED)
        self.assertEqual(
            active_reservation(api, 12)["reservation_id"],
            SESSION_A,
        )

    def test_label_event_never_creates_reservation_authority(self) -> None:
        """Solo /tomar autorizado crea una reserva normal."""
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": STATUS_RESERVED}]
        api.branches["trabajo/issue-12"] = "orphan-sha"

        update_issue_label_state(api, 12, "intruso", STATUS_RESERVED)

        self.assertIsNone(active_reservation(api, 12))
        self.assertEqual(api.status_history[-1], STATUS_AVAILABLE)
        self.assertEqual(api.assignees, set())
        self.assertEqual(api.branches["trabajo/issue-12"], "orphan-sha")

        authorized_api = FakeGitHub()
        reservation_id = reserve_work(
            authorized_api,
            12,
            "pl0n3r",
            "OWNER",
        )
        self.assertIsNotNone(reservation_id)
        self.assertIn("trabajo/issue-12", authorized_api.branches)
        self.assertIsNotNone(active_reservation(authorized_api, 12))

    def test_label_available_cannot_release_another_session(self) -> None:
        """El label disponible nunca recibe autoridad de sesión implícita."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.issue_data["labels"].append({"name": STATUS_AVAILABLE})

        update_issue_label_state(api, 12, "pl0n3r", STATUS_AVAILABLE)

        self.assertIn("trabajo/issue-12", api.branches)
        reservation = active_reservation(api, 12)
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation["reservation_id"], SESSION_A)

    def test_orphan_branch_is_preserved_until_explicit_adoption(self) -> None:
        """Una rama sin reserva se conserva pero no se adopta automáticamente."""
        api = FakeGitHub()
        api.branches["trabajo/issue-12"] = "abc123"
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": "Closes #12",
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }

        with self.assertRaisesRegex(
            CoordinationError,
            "adoptar-contrato-huerfana",
        ):
            reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertEqual(api.pulls[15]["state"], "open")
        self.assertIn("trabajo/issue-12", api.branches)
        self.assertIsNone(active_reservation(api, 12))
        self.assertNotIn("coordinacion/lock-issue-12", api.branches)

    def test_concurrent_orphan_recovery_respects_existing_lock(self) -> None:
        """Dos recuperadores no pueden reclamar a la vez una rama huérfana."""
        api = FakeGitHub()
        api.branches["trabajo/issue-12"] = "abc123"
        api.branches["coordinacion/lock-issue-12"] = "abc123"

        session = reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertIsNone(session)
        self.assertIsNone(active_reservation(api, 12))

    def test_fresh_reservation_cannot_be_recovered(self) -> None:
        """Una reserva con actividad reciente sigue protegida."""
        api = FakeGitHub()
        add_active_reservation(api)

        result = reserve_work(api, 12, "otra-sesion", "MEMBER")

        self.assertIsNone(result)
        reservation = active_reservation(api, 12)
        self.assertIsNotNone(reservation)
        assert reservation is not None
        self.assertEqual(reservation["reservation_id"], SESSION_A)

    def test_recovery_required_can_be_reclaimed_after_recent_branch_activity(self) -> None:
        """Un estado recovery explícito permite reacquirir aunque la rama reviva."""
        api = FakeGitHub()
        add_active_reservation(api, owner="agente-anterior")
        api.set_status(12, STATUS_RECOVERY)
        api.commit_times["abc123"] = datetime.now(timezone.utc)

        session = reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertIsNotNone(session)
        self.assertNotEqual(session, SESSION_A)
        reservation = active_reservation(api, 12)
        self.assertIsNotNone(reservation)
        assert reservation is not None
        self.assertEqual(reservation["reservation_id"], session)
        self.assertEqual(reservation["owner"], "pl0n3r")
        self.assertEqual(api.status_history[-1], STATUS_RESERVED)

    def test_recovery_required_reuses_existing_branch_and_pr(self) -> None:
        """La reacquisición explícita conserva rama/PR y renueva su metadata."""
        api = FakeGitHub()
        add_active_reservation(api, owner="agente-anterior")
        api.set_status(12, STATUS_RECOVERY)
        api.commit_times["abc123"] = datetime.now(timezone.utc)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": (
                f"Closes #12\n\nReserva: {SESSION_A}\n\n"
                f"<!-- condor-reserva-id: {SESSION_A} -->"
            ),
            "head": {
                "ref": "trabajo/issue-12",
                "sha": "abc123",
                "repo": {"full_name": api.repo},
            },
            "base": {"ref": "main"},
        }

        session = reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertIsNotNone(session)
        self.assertIn("trabajo/issue-12", api.branches)
        self.assertEqual(api.pulls[15]["state"], "open")
        self.assertEqual(reservation_from_pr_body(api.pulls[15]["body"]), session)
        self.assertEqual(api.status_history[-1], STATUS_REVIEW)

    def test_stale_reservation_reuses_existing_branch_and_pr(self) -> None:
        """Una reserva vieja cambia de sesión sin cerrar ni duplicar su PR."""
        api = FakeGitHub()
        add_active_reservation(api, owner="agente-anterior")
        stale = "2020-01-01T00:00:00+00:00"
        api.comments[-1]["created_at"] = stale
        api.comments[-1]["updated_at"] = stale
        api.commit_times["abc123"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "updated_at": stale,
            "body": (
                f"Closes #12\n\nReserva: {SESSION_A}\n\n"
                f"<!-- condor-reserva-id: {SESSION_A} -->"
            ),
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }

        session = reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertIsNotNone(session)
        self.assertNotEqual(session, SESSION_A)
        self.assertEqual(api.pulls[15]["state"], "open")
        self.assertIn("trabajo/issue-12", api.branches)
        self.assertEqual(api.status_history[-1], STATUS_REVIEW)
        self.assertEqual(reservation_from_pr_body(api.pulls[15]["body"]), session)
        reservation = active_reservation(api, 12)
        self.assertIsNotNone(reservation)
        assert reservation is not None
        self.assertEqual(reservation["owner"], "pl0n3r")
        self.assertEqual(reservation["reason"], "recuperacion-inactividad")
        self.assertNotIn("coordinacion/lock-issue-12", api.branches)

    def test_pull_metadata_does_not_refresh_work_lease(self) -> None:
        """Bots y checks pueden tocar el PR sin ocultar una reserva abandonada."""
        api = FakeGitHub()
        add_active_reservation(api)
        stale = "2020-01-01T00:00:00+00:00"
        api.comments[-1]["created_at"] = stale
        api.comments[-1]["updated_at"] = stale
        api.commit_times["abc123"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "head": {"ref": "trabajo/issue-12"},
        }

        activity = work_activity_timestamp(api, 12, "trabajo/issue-12")

        self.assertEqual(activity, datetime(2020, 1, 1, tzinfo=timezone.utc))
        self.assertTrue(
            work_is_stale(
                api,
                12,
                "trabajo/issue-12",
                now=datetime(2020, 1, 1, 0, 31, tzinfo=timezone.utc),
            )
        )

    def test_read_only_comment_does_not_refresh_stale_reservation(self) -> None:
        """Una revisión ajena no mantiene viva una rama sin progreso."""
        api = FakeGitHub()
        add_active_reservation(api)
        stale = "2020-01-01T00:00:00+00:00"
        api.comments[-1]["created_at"] = stale
        api.comments[-1]["updated_at"] = stale
        api.commit_times["abc123"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        api.comments.append(
            {
                "user": {"login": "pl0n3r"},
                "body": "Revisión read-only: sin cambios en la rama reservada.",
                "created_at": "2020-01-01T00:29:00+00:00",
                "updated_at": "2020-01-01T00:29:00+00:00",
            }
        )

        activity = work_activity_timestamp(api, 12, "trabajo/issue-12")

        self.assertEqual(activity, datetime(2020, 1, 1, tzinfo=timezone.utc))
        self.assertTrue(
            work_is_stale(
                api,
                12,
                "trabajo/issue-12",
                now=datetime(2020, 1, 1, 0, 31, tzinfo=timezone.utc),
            )
        )

    def test_branch_commit_refreshes_stale_reservation(self) -> None:
        """Un commit real de la rama sí renueva el lease."""
        api = FakeGitHub()
        add_active_reservation(api)
        stale = "2020-01-01T00:00:00+00:00"
        api.comments[-1]["created_at"] = stale
        api.comments[-1]["updated_at"] = stale
        commit_time = datetime(2020, 1, 1, 0, 20, tzinfo=timezone.utc)
        api.commit_times["abc123"] = commit_time

        activity = work_activity_timestamp(api, 12, "trabajo/issue-12")

        self.assertEqual(activity, commit_time)
        self.assertFalse(
            work_is_stale(
                api,
                12,
                "trabajo/issue-12",
                now=datetime(2020, 1, 1, 0, 31, tzinfo=timezone.utc),
            )
        )

    def test_far_future_commit_does_not_extend_stale_reservation(self) -> None:
        """Una fecha Git arbitrariamente futura no mantiene viva la reserva."""
        api = FakeGitHub()
        add_active_reservation(api)
        stale = "2020-01-01T00:00:00+00:00"
        api.comments[-1]["created_at"] = stale
        api.comments[-1]["updated_at"] = stale
        api.commit_times["abc123"] = datetime(2030, 1, 1, tzinfo=timezone.utc)
        reference = datetime(2020, 1, 1, 0, 31, tzinfo=timezone.utc)

        activity = work_activity_timestamp(
            api,
            12,
            "trabajo/issue-12",
            now=reference,
        )

        self.assertEqual(activity, datetime(2020, 1, 1, tzinfo=timezone.utc))
        self.assertTrue(
            work_is_stale(
                api,
                12,
                "trabajo/issue-12",
                now=reference,
            )
        )

    def test_small_future_clock_skew_is_bounded(self) -> None:
        """Un skew pequeño se acota al reloj de evaluación y deja de renovarse."""
        api = FakeGitHub()
        add_active_reservation(api)
        stale = "2020-01-01T00:00:00+00:00"
        api.comments[-1]["created_at"] = stale
        api.comments[-1]["updated_at"] = stale
        api.commit_times["abc123"] = datetime(
            2020,
            1,
            1,
            0,
            34,
            tzinfo=timezone.utc,
        )
        first_reference = datetime(2020, 1, 1, 0, 30, tzinfo=timezone.utc)

        self.assertEqual(
            work_activity_timestamp(
                api,
                12,
                "trabajo/issue-12",
                now=first_reference,
            ),
            first_reference,
        )
        self.assertFalse(
            work_is_stale(
                api,
                12,
                "trabajo/issue-12",
                now=first_reference,
            )
        )
        self.assertTrue(
            work_is_stale(
                api,
                12,
                "trabajo/issue-12",
                now=datetime(2020, 1, 1, 1, 5, tzinfo=timezone.utc),
            )
        )

    def test_reservation_marker_starts_lease(self) -> None:
        """Una reserva recién creada no nace stale aunque main sea antiguo."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.commit_times["abc123"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        marker_time = datetime.fromisoformat(api.comments[-1]["updated_at"])

        activity = work_activity_timestamp(api, 12, "trabajo/issue-12")

        self.assertEqual(activity, marker_time)
        self.assertFalse(
            work_is_stale(
                api,
                12,
                "trabajo/issue-12",
                now=marker_time.replace(microsecond=0),
            )
        )

    def test_sweep_marks_eligible_stale_reservation(self) -> None:
        """El barrido marca una reserva stale y libera su lock efímero."""
        api = FakeGitHub()
        add_active_reservation(api)
        stale = "2020-01-01T00:00:00+00:00"
        api.comments[-1]["created_at"] = stale
        api.comments[-1]["updated_at"] = stale
        api.commit_times["abc123"] = datetime(2020, 1, 1, tzinfo=timezone.utc)

        marked = mark_stale_reservations(api)

        self.assertEqual(marked, 1)
        self.assertEqual(api.status_history[-1], STATUS_RECOVERY)
        self.assertNotIn("coordinacion/lock-issue-12", api.branches)

    def test_block_sweep_unblocks_verified_workflow_once(self) -> None:
        api = FakeGitHub()
        sha = "a" * 40
        api.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        api.issue_data["body"] = (
            VALID_ACCEPTANCE_BODY
            + "\n"
            + unblock_marker(kind="workflow_success", run_id=9001, sha=sha)
        )
        api.workflow_runs[9001] = {
            "id": 9001,
            "status": "completed",
            "conclusion": "success",
            "head_sha": sha,
        }

        first = sweep_satisfied_blocks(api)
        second = sweep_satisfied_blocks(api)

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(api.status_history[-1], STATUS_AVAILABLE)
        evidence = [
            row for row in api.comments
            if "factory-unblock-evidence" in row["body"]
        ]
        self.assertEqual(len(evidence), 1)
        self.assertIn("workflow_run:9001@", evidence[0]["body"])

    def test_block_sweep_fails_closed_on_unverified_or_invalid_condition(self) -> None:
        sha = "b" * 40
        mismatch = FakeGitHub()
        mismatch.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        mismatch.issue_data["body"] = unblock_marker(
            kind="workflow_success",
            run_id=17,
            sha=sha,
        )
        mismatch.workflow_runs[17] = {
            "id": 17,
            "status": "completed",
            "conclusion": "success",
            "head_sha": "c" * 40,
        }

        invalid = FakeGitHub()
        invalid.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        invalid.issue_data["body"] = unblock_marker(kind="human_approval")
        boolean_version = FakeGitHub()
        boolean_version.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        boolean_version.issue_data["body"] = unblock_marker(
            version=True,
            kind="issue_closed",
            issue=99,
        )

        self.assertEqual(sweep_satisfied_blocks(mismatch), 0)
        self.assertEqual(sweep_satisfied_blocks(invalid), 0)
        self.assertEqual(sweep_satisfied_blocks(boolean_version), 0)
        self.assertIn(STATUS_BLOCKED, coordinator.label_names(mismatch.issue_data))
        self.assertIn(STATUS_BLOCKED, coordinator.label_names(invalid.issue_data))
        self.assertIn(
            STATUS_BLOCKED,
            coordinator.label_names(boolean_version.issue_data),
        )
        self.assertFalse(mismatch.comments)
        self.assertFalse(invalid.comments)
        self.assertFalse(boolean_version.comments)

    def test_unblock_fail_closed_edges_and_actions_lookup(self) -> None:
        self.assertIsNone(coordinator.parse_unblock_marker("sin marker"))
        duplicate = unblock_marker(kind="issue_closed", issue=99)
        invalid = (
            duplicate + "\n" + duplicate,
            '<!-- factory-unblock {"version":1,} -->',
            unblock_marker(kind="issue_closed", issue=0),
            unblock_marker(kind="issue_closed", issue=99, extra=True),
            unblock_marker(kind="workflow_success", run_id=0, sha="a" * 40),
            unblock_marker(kind="workflow_success", run_id=1, sha="short"),
            unblock_marker(
                kind="workflow_success", run_id=1, sha="a" * 40, extra=True
            ),
            unblock_marker(kind="branch_sha", branch="../main", sha="a" * 40),
            unblock_marker(
                kind="branch_sha", branch="main", sha="a" * 40, extra=True
            ),
        )
        for body in invalid:
            with self.assertRaises(CoordinationError):
                coordinator.parse_unblock_marker(body)

        api = FakeGitHub()
        api.related_issues[99] = {"number": 99, "state": "open", "labels": []}
        self.assertEqual(
            coordinator.verify_unblock_condition(
                api, {"version": 1, "kind": "issue_closed", "issue": 99}
            ),
            (False, None),
        )
        api.branches["main"] = "b" * 40
        self.assertEqual(
            coordinator.verify_unblock_condition(
                api,
                {
                    "version": 1,
                    "kind": "branch_sha",
                    "branch": "main",
                    "sha": "a" * 40,
                },
            ),
            (False, None),
        )
        self.assertEqual(
            coordinator.verify_unblock_condition(
                api, {"version": 1, "kind": "unknown"}
            ),
            (False, None),
        )

        fingerprint = "f" * 64
        payload = json.dumps(
            {"version": 1, "fingerprint": fingerprint, "evidence": "ok"},
            separators=(",", ":"),
        )
        comments = [
            {"user": {"login": "otro"}, "body": f"<!-- factory-unblock-evidence {payload} -->"},
            {"user": {"login": BOT}, "body": "<!-- factory-unblock-evidence {bad-json} -->"},
        ]
        self.assertFalse(coordinator.unblock_evidence_exists(comments, fingerprint))
        comments.append(
            {"user": {"login": BOT}, "body": f"<!-- factory-unblock-evidence {payload} -->"}
        )
        self.assertTrue(coordinator.unblock_evidence_exists(comments, fingerprint))

        marker = coordinator.parse_unblock_marker(
            unblock_marker(kind="branch_sha", branch="main", sha="b" * 40)
        )
        assert marker is not None
        fp = coordinator.unblock_fingerprint(marker)
        api.issue_data.update({"state": "closed", "labels": [{"name": STATUS_BLOCKED}]})
        self.assertIsNone(coordinator._revalidated_unblock_evidence(api, 12, fp))
        api.issue_data.update({"state": "open", "labels": [{"name": STATUS_AVAILABLE}]})
        self.assertIsNone(coordinator._revalidated_unblock_evidence(api, 12, fp))
        api.issue_data.update(
            {
                "labels": [{"name": STATUS_BLOCKED}],
                "body": unblock_marker(kind="human_approval"),
            }
        )
        self.assertIsNone(coordinator._revalidated_unblock_evidence(api, 12, fp))

        real = GitHub("pl0n3r/Factory", token="test-token")
        public_run = {
            "id": 77,
            "repository": {"full_name": "pl0n3r/Factory", "private": False},
        }
        with patch.object(real, "public_request", return_value=public_run) as request:
            self.assertEqual(real.workflow_run(77)["id"], 77)
        request.assert_called_once_with(
            "/repos/pl0n3r/Factory/actions/runs/77",
            allow=(404,),
        )
        with patch.object(real, "public_request", return_value=[]):
            with self.assertRaises(CoordinationError):
                real.workflow_run(78)

    def test_block_sweep_revalidates_marker_before_mutation(self) -> None:
        api = FakeGitHub()
        sha = "e" * 40
        api.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        api.issue_data["body"] = unblock_marker(
            kind="workflow_success",
            run_id=27,
            sha=sha,
        )
        api.workflow_runs[27] = {
            "id": 27,
            "status": "completed",
            "conclusion": "success",
            "head_sha": sha,
        }
        original_issue = api.issue

        def issue(number: int) -> dict:
            current = original_issue(number)
            if number == 12:
                current["body"] = unblock_marker(
                    kind="branch_sha",
                    branch="main",
                    sha="f" * 40,
                )
            return current

        api.issue = issue  # type: ignore[method-assign]

        self.assertEqual(sweep_satisfied_blocks(api), 0)
        self.assertIn(STATUS_BLOCKED, coordinator.label_names(api.issue_data))
        self.assertFalse(
            [row for row in api.comments if "factory-unblock-evidence" in row["body"]]
        )

    def test_scheduled_sweep_runs_reservations_and_blockers(self) -> None:
        api = FakeGitHub()
        with (
            patch.object(
                coordinator,
                "mark_stale_reservations",
                return_value=2,
            ) as stale,
            patch.object(
                coordinator,
                "sweep_satisfied_blocks",
                return_value=3,
            ) as blockers,
        ):
            result = run_scheduled_sweep(api)

        stale.assert_called_once_with(api)
        blockers.assert_called_once_with(api)
        self.assertEqual(
            result,
            {"stale_reservations": 2, "satisfied_blocks": 3},
        )

    def test_block_sweep_retry_does_not_duplicate_evidence_comment(self) -> None:
        api = FakeGitHub()
        sha = "d" * 40
        api.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        api.issue_data["body"] = unblock_marker(
            kind="branch_sha",
            branch="main",
            sha=sha,
        )
        api.branches["main"] = sha

        self.assertEqual(sweep_satisfied_blocks(api), 1)
        api.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        self.assertEqual(sweep_satisfied_blocks(api), 1)

        evidence = [
            row for row in api.comments
            if "factory-unblock-evidence" in row["body"]
        ]
        self.assertEqual(len(evidence), 1)

    def test_block_sweep_supports_closed_issue_condition(self) -> None:
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        api.issue_data["body"] = unblock_marker(
            kind="issue_closed",
            issue=99,
        )
        api.related_issues[99] = {"number": 99, "state": "closed", "labels": []}

        self.assertEqual(sweep_satisfied_blocks(api), 1)
        self.assertEqual(api.status_history[-1], STATUS_AVAILABLE)

    def test_block_sweep_reblocks_available_candidate_when_dependency_reopens(self) -> None:
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        api.issue_data["body"] = unblock_marker(kind="issue_closed", issue=99)
        api.related_issues[99] = {
            "number": 99,
            "state": "closed",
            "labels": [],
        }

        self.assertEqual(sweep_satisfied_blocks(api), 1)
        self.assertIn(STATUS_AVAILABLE, coordinator.label_names(api.issue_data))

        api.related_issues[99]["state"] = "open"
        self.assertEqual(sweep_satisfied_blocks(api), 1)
        self.assertIn(STATUS_BLOCKED, coordinator.label_names(api.issue_data))
        self.assertEqual(
            len(
                [
                    row
                    for row in api.comments
                    if "factory-reblock-evidence" in row["body"]
                ]
            ),
            1,
        )

    def test_reblock_sweep_does_not_mutate_active_or_completed_work(self) -> None:
        for state, status in (
            ("open", STATUS_RESERVED),
            ("open", STATUS_REVIEW),
            ("closed", STATUS_COMPLETED),
        ):
            with self.subTest(status=status):
                api = FakeGitHub()
                api.issue_data["state"] = state
                api.issue_data["labels"] = [{"name": status}]
                api.issue_data["body"] = unblock_marker(
                    kind="issue_closed",
                    issue=99,
                )
                api.related_issues[99] = {
                    "number": 99,
                    "state": "open",
                    "labels": [],
                }

                self.assertEqual(sweep_satisfied_blocks(api), 0)
                self.assertEqual(coordinator.label_names(api.issue_data), {status})
                self.assertFalse(
                    [
                        row
                        for row in api.comments
                        if "factory-reblock-evidence" in row["body"]
                    ]
                )

    def test_reblock_sweep_is_idempotent(self) -> None:
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": STATUS_AVAILABLE}]
        api.issue_data["body"] = unblock_marker(kind="issue_closed", issue=99)
        api.related_issues[99] = {
            "number": 99,
            "state": "open",
            "labels": [],
        }

        self.assertEqual(sweep_satisfied_blocks(api), 1)
        api.issue_data["labels"] = [{"name": STATUS_AVAILABLE}]
        self.assertEqual(sweep_satisfied_blocks(api), 1)

        evidence = [
            row
            for row in api.comments
            if "factory-reblock-evidence" in row["body"]
        ]
        self.assertEqual(len(evidence), 1)
        self.assertIn(STATUS_BLOCKED, coordinator.label_names(api.issue_data))

    def test_sweep_skips_blocked_and_recent_reservations(self) -> None:
        """Bloqueadas y reservas con commits recientes permanecen intactas."""
        blocked = FakeGitHub()
        add_active_reservation(blocked)
        blocked.issue_data["labels"].append({"name": STATUS_BLOCKED})
        blocked.commit_times["abc123"] = datetime(2020, 1, 1, tzinfo=timezone.utc)

        self.assertEqual(mark_stale_reservations(blocked), 0)
        self.assertNotEqual(blocked.status_history[-1], STATUS_RECOVERY)

        recent = FakeGitHub()
        add_active_reservation(recent)
        recent.commit_times["abc123"] = datetime.now(timezone.utc)

        self.assertEqual(mark_stale_reservations(recent), 0)
        self.assertNotEqual(recent.status_history[-1], STATUS_RECOVERY)

    def test_sweep_does_not_overwrite_concurrent_recovery(self) -> None:
        """El sweep revalida la sesión después de adquirir el lock."""
        api = FakeGitHub()
        add_active_reservation(api, owner="agente-anterior")
        stale = "2020-01-01T00:00:00+00:00"
        api.comments[-1]["created_at"] = stale
        api.comments[-1]["updated_at"] = stale
        api.commit_times["abc123"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        original_create_branch = api.create_branch

        def create_branch(branch: str, sha: str) -> bool:
            created = original_create_branch(branch, sha)
            if created and branch == "coordinacion/lock-issue-12":
                now = datetime.now(timezone.utc).isoformat()
                api.comments.append(
                    {
                        "user": {"login": BOT},
                        "body": reservation_marker(
                            "otro-agente",
                            SESSION_B,
                            "trabajo/issue-12",
                            True,
                            "recuperacion-inactividad",
                        ),
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            return created

        api.create_branch = create_branch  # type: ignore[method-assign]

        marked = mark_stale_reservations(api)

        self.assertEqual(marked, 0)
        self.assertNotEqual(api.status_history[-1], STATUS_RECOVERY)
        reservation = active_reservation(api, 12)
        self.assertIsNotNone(reservation)
        assert reservation is not None
        self.assertEqual(reservation["reservation_id"], SESSION_B)
        self.assertNotIn("coordinacion/lock-issue-12", api.branches)

    def test_new_work_waits_while_recovery_is_pending(self) -> None:
        """Un Issue disponible no salta por encima de recuperación pendiente."""
        api = FakeGitHub()
        api.open_issue_data.append(
            {
                "number": 13,
                "state": "open",
                "labels": [{"name": STATUS_RECOVERY}],
            }
        )

        session = reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertIsNone(session)
        self.assertNotIn("trabajo/issue-12", api.branches)
        self.assertEqual(api.status_history, [])
        self.assertIsNone(active_reservation(api, 12))

    def test_concurrent_stale_recovery_cannot_enter_existing_lock(self) -> None:
        """Un segundo recuperador no entra mientras exista el lock efímero."""
        api = FakeGitHub()
        add_active_reservation(api, owner="agente-anterior")
        stale = "2020-01-01T00:00:00+00:00"
        api.comments[-1]["created_at"] = stale
        api.comments[-1]["updated_at"] = stale
        api.commit_times["abc123"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        api.branches["coordinacion/lock-issue-12"] = "abc123"

        session = reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertIsNone(session)
        reservation = active_reservation(api, 12)
        self.assertIsNotNone(reservation)
        assert reservation is not None
        self.assertEqual(reservation["reservation_id"], SESSION_A)

    def test_stale_detection_is_fail_closed_without_activity_evidence(self) -> None:
        """Sin timestamps verificables una reserva no se roba automáticamente."""
        api = FakeGitHub()
        api.branches["trabajo/issue-12"] = "sin-fecha"
        api.commit_times.clear()

        self.assertFalse(
            work_is_stale(
                api,
                12,
                "trabajo/issue-12",
                now=datetime(2030, 1, 1, tzinfo=timezone.utc),
            )
        )

    def test_rewrite_pull_reservation_keeps_pr_and_updates_both_markers(self) -> None:
        """La recuperación actualiza metadata sin reconstruir la descripción."""
        body = (
            f"Resumen útil\n\nReserva: {SESSION_A}\n\n"
            f"<!-- condor-reserva-id: {SESSION_A} -->\n"
        )

        updated = rewrite_pull_reservation(body, SESSION_B)

        self.assertIn("Resumen útil", updated)
        self.assertEqual(reservation_from_pr_body(updated), SESSION_B)
        self.assertNotIn(SESSION_A, updated)

    def test_reservation_pins_acceptance_contract_fingerprint(self) -> None:
        """Una reserva nueva fija el contrato AC que aceptó /tomar."""
        api = FakeGitHub()

        session = reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertIsNotNone(session)
        reservation = active_reservation(api, 12)
        self.assertIsNotNone(reservation)
        assert reservation is not None
        self.assertEqual(reservation["version"], 2)
        self.assertEqual(
            reservation["acceptance_sha256"],
            contract_fingerprint(VALID_ACCEPTANCE_BODY),
        )

    def test_pr_validation_rejects_contract_changed_after_reservation(self) -> None:
        """Un AC editado tras /tomar invalida el PR aunque la sesión coincida."""
        api = FakeGitHub()
        session = reserve_work(api, 12, "pl0n3r", "OWNER")
        assert session is not None
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": (
                f"Closes #12\n\nReserva: {session}\n"
                f"<!-- condor-reserva-id: {session} -->"
            ),
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }
        api.issue_data["body"] = VALID_ACCEPTANCE_BODY.replace(
            "El gate base pasa.",
            "El gate debilitado pasa.",
        )

        with self.assertRaisesRegex(
            CoordinationError,
            "cambió su contrato de aceptación",
        ):
            validate_pull(api, 15, True)

    def test_non_contract_issue_edits_preserve_fingerprint(self) -> None:
        """Notas fuera de criterios/marker no invalidan una reserva."""
        api = FakeGitHub()
        session = reserve_work(api, 12, "pl0n3r", "OWNER")
        assert session is not None
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": (
                f"Closes #12\n\nReserva: {session}\n"
                f"<!-- condor-reserva-id: {session} -->"
            ),
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }
        api.issue_data["body"] = (
            VALID_ACCEPTANCE_BODY
            + "\n\nNota operativa fuera del contrato ejecutable.\n"
        )

        validate_pull(api, 15, True)

    def test_retake_reservation_accepts_explicit_new_contract(self) -> None:
        """Liberar y volver a /tomar fija explícitamente el contrato nuevo."""
        api = FakeGitHub()
        first = reserve_work(api, 12, "pl0n3r", "OWNER")
        assert first is not None
        initial = active_reservation(api, 12)
        assert initial is not None
        original_fingerprint = initial["acceptance_sha256"]

        release_work(api, 12, "pl0n3r", "OWNER", first, False)
        api.issue_data["body"] = VALID_ACCEPTANCE_BODY.replace(
            "El gate base pasa.",
            "El gate nuevo pasa.",
        )
        second = reserve_work(api, 12, "pl0n3r", "OWNER")
        assert second is not None
        current = active_reservation(api, 12)
        assert current is not None

        self.assertNotEqual(first, second)
        self.assertNotEqual(
            original_fingerprint,
            current["acceptance_sha256"],
        )
        self.assertEqual(
            current["acceptance_sha256"],
            contract_fingerprint(api.issue_data["body"]),
        )

    def test_legacy_reservation_cannot_upgrade_silently(self) -> None:
        """Transferir o recuperar v1 exige migración explícita."""
        api = FakeGitHub()
        add_active_reservation(api, pinned=False)

        with self.assertRaisesRegex(CoordinationError, "migrar-contrato"):
            transfer_work(api, 12, "pl0n3r", "OWNER", SESSION_A)

        stale = "2020-01-01T00:00:00+00:00"
        api.comments[-1]["created_at"] = stale
        api.comments[-1]["updated_at"] = stale
        api.commit_times["abc123"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
        with self.assertRaisesRegex(CoordinationError, "migrar-contrato"):
            reserve_work(api, 12, "pl0n3r", "OWNER")

        current = active_reservation(api, 12)
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current["version"], 1)
        self.assertNotIn("acceptance_sha256", current)

    def test_migrate_legacy_reservation_is_explicit_and_preserves_session(self) -> None:
        """La migración v1→v2 conserva rama, PR e ID de sesión."""
        api = FakeGitHub()
        add_active_reservation(api, pinned=False)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": (
                f"Closes #12\n\nReserva: {SESSION_A}\n"
                f"<!-- condor-reserva-id: {SESSION_A} -->"
            ),
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }

        migrated = migrate_legacy_reservation(
            api,
            12,
            "pl0n3r",
            "OWNER",
            SESSION_A,
        )

        self.assertEqual(migrated, SESSION_A)
        current = active_reservation(api, 12)
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current["version"], 2)
        self.assertEqual(current["reservation_id"], SESSION_A)
        self.assertEqual(
            current["acceptance_sha256"],
            contract_fingerprint(VALID_ACCEPTANCE_BODY),
        )
        self.assertEqual(
            reservation_from_pr_body(api.pulls[15]["body"]),
            SESSION_A,
        )
        validate_pull(api, 15, True)

    def test_orphaned_branch_requires_explicit_contract_adoption(self) -> None:
        """Una rama huérfana conserva trabajo hasta adopción explícita v2."""
        api = FakeGitHub()
        api.branches["trabajo/issue-12"] = "abc123"
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": "Closes #12",
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }

        with self.assertRaisesRegex(
            CoordinationError,
            "adoptar-contrato-huerfana",
        ):
            reserve_work(api, 12, "pl0n3r", "OWNER")
        self.assertIn("trabajo/issue-12", api.branches)
        self.assertEqual(api.pulls[15]["state"], "open")

        session = adopt_orphaned_contract(api, 12, "pl0n3r", "OWNER")
        self.assertIsNotNone(session)
        current = active_reservation(api, 12)
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current["version"], 2)
        self.assertEqual(
            current["acceptance_sha256"],
            contract_fingerprint(VALID_ACCEPTANCE_BODY),
        )
        self.assertEqual(
            reservation_from_pr_body(api.pulls[15]["body"]),
            session,
        )
        validate_pull(api, 15, True)

    def test_legacy_reservation_is_rejected_for_protected_pr(self) -> None:
        """Un PR protegido no acepta reservas v1 sin fingerprint."""
        api = FakeGitHub()
        add_active_reservation(api, pinned=False)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": (
                f"Closes #12\nReserva: {SESSION_A}\n"
                f"<!-- condor-reserva-id: {SESSION_A} -->"
            ),
            "head": {"ref": "trabajo/issue-12", "sha": "head-legacy"},
            "base": {"ref": "main"},
        }

        with self.assertRaisesRegex(
            CoordinationError,
            "reserva legacy sin fingerprint",
        ):
            validate_pull(api, 15, True)

    def test_issue_edit_contract_drift_invalidates_pr_head_checks(self) -> None:
        """Editar un AC invalida los checks verdes del mismo HEAD."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": (
                f"Closes #12\nReserva: {SESSION_A}\n"
                f"<!-- condor-reserva-id: {SESSION_A} -->"
            ),
            "head": {"ref": "trabajo/issue-12", "sha": "head-drift"},
            "base": {"ref": "main"},
        }
        api.issue_data["body"] = VALID_ACCEPTANCE_BODY.replace(
            "El gate base pasa.",
            "El gate cambiado pasa.",
        )

        update_issue_state(api, 12, "edited")

        self.assertEqual(
            [check["name"] for check in api.check_runs],
            ["Validar"],
        )
        self.assertTrue(
            all(check["head_sha"] == "head-drift" for check in api.check_runs)
        )
        self.assertTrue(
            all(check["conclusion"] == "failure" for check in api.check_runs)
        )

    def test_issue_edit_outside_contract_does_not_invalidate_checks(self) -> None:
        """Editar prosa periférica no genera falsos failures."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": (
                f"Closes #12\nReserva: {SESSION_A}\n"
                f"<!-- condor-reserva-id: {SESSION_A} -->"
            ),
            "head": {"ref": "trabajo/issue-12", "sha": "head-context"},
            "base": {"ref": "main"},
        }
        api.issue_data["body"] = (
            VALID_ACCEPTANCE_BODY
            + "\n\nNota periférica sin tocar criterios ni marker.\n"
        )

        update_issue_state(api, 12, "edited")

        self.assertEqual(api.check_runs, [])

    def test_issue_edit_matching_pinned_contract_is_noop(self) -> None:
        """Un contrato v2 sin cambios no invalida checks."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": (
                f"Closes #12\nReserva: {SESSION_A}\n"
                f"<!-- condor-reserva-id: {SESSION_A} -->"
            ),
            "head": {"ref": "trabajo/issue-12", "sha": "head-stable"},
            "base": {"ref": "main"},
        }

        update_issue_state(api, 12, "edited")

        self.assertEqual(api.check_runs, [])

    def test_issue_without_executable_acceptance_cannot_be_reserved(self) -> None:
        """El coordinador rechaza trabajo sin contrato AC ejecutable."""
        api = FakeGitHub()
        api.issue_data["body"] = "Issue legacy sin contrato."
        with self.assertRaisesRegex(
            CoordinationError,
            "criterios de aceptación ejecutables",
        ):
            reserve_work(api, 12, "pl0n3r", "OWNER")
        self.assertNotIn("trabajo/issue-12", api.branches)

    def test_blocked_issue_reports_reason(self) -> None:
        """Un /tomar bloqueado explica el no-op sin mutar coordinación."""
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        output = StringIO()
        with redirect_stdout(output):
            result = reserve_work(api, 12, "pl0n3r", "OWNER")

        self.assertIsNone(result)
        self.assertIn("Issue #12", output.getvalue())
        self.assertIn(STATUS_BLOCKED, output.getvalue())
        self.assertNotIn("trabajo/issue-12", api.branches)

    def test_blocked_issue_cannot_be_reserved(self) -> None:
        """Un Issue bloqueado no entra a la cola de trabajo."""
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": STATUS_BLOCKED}]
        result = reserve_work(api, 12, "pl0n3r", "OWNER")
        self.assertIsNone(result)
        self.assertNotIn("trabajo/issue-12", api.branches)

    def test_reservation_rolls_back_if_marker_fails(self) -> None:
        """Un fallo al persistir metadata confiable revierte el lock."""
        api = FakeGitHub()
        api.fail_comment = True
        with self.assertRaises(CoordinationError):
            reserve_work(api, 12, "pl0n3r", "OWNER")
        self.assertNotIn("trabajo/issue-12", api.branches)
        self.assertEqual(api.status_history[-1], STATUS_AVAILABLE)

    def test_wrong_session_cannot_release(self) -> None:
        """Una sesión distinta no puede liberar la reserva."""
        api = FakeGitHub()
        add_active_reservation(api)
        release_work(api, 12, "pl0n3r", "OWNER", SESSION_B, False)
        self.assertIn("trabajo/issue-12", api.branches)
        self.assertIsNotNone(active_reservation(api, 12))

    def test_release_marks_inactive_before_available(self) -> None:
        """La liberación deja marcador inactivo y luego expone el Issue."""
        api = FakeGitHub()
        add_active_reservation(api)
        release_work(api, 12, "pl0n3r", "OWNER", SESSION_A, False)
        self.assertNotIn("trabajo/issue-12", api.branches)
        latest = latest_reservation(api.comments)
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertFalse(latest["active"])
        self.assertEqual(api.status_history[-1], STATUS_AVAILABLE)

    def test_transfer_invalidates_previous_session(self) -> None:
        """Transferir sincroniza Issue y PR con un ID nuevo."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": f"Closes #12\nReserva: {SESSION_A}\n<!-- condor-reserva-id: {SESSION_A} -->",
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }
        new_id = transfer_work(api, 12, "pl0n3r", "OWNER", SESSION_A)
        self.assertIsNotNone(new_id)
        self.assertNotEqual(new_id, SESSION_A)
        reservation = active_reservation(api, 12)
        assert reservation is not None
        self.assertEqual(reservation["reservation_id"], new_id)
        self.assertEqual(
            reservation_from_pr_body(api.pulls[15]["body"]),
            new_id,
        )
        validate_pull(api, 15, True)

    def test_transfer_rolls_back_pr_if_update_fails(self) -> None:
        """Un fallo al actualizar el PR conserva la sesión anterior."""
        api = FakeGitHub()
        add_active_reservation(api)
        original = (
            f"Closes #12\nReserva: {SESSION_A}\n"
            f"<!-- condor-reserva-id: {SESSION_A} -->"
        )
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": original,
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }
        api.pull_update_failures_remaining = 1

        with self.assertRaises(CoordinationError):
            transfer_work(api, 12, "pl0n3r", "OWNER", SESSION_A)

        reservation = active_reservation(api, 12)
        assert reservation is not None
        self.assertEqual(reservation["reservation_id"], SESSION_A)
        self.assertEqual(api.pulls[15]["body"], original)

    def _renew_fixture(self) -> FakeGitHub:
        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15, "state": "open", "draft": False,
            "body": (
                f"Closes #12\nReserva: {SESSION_A}\n"
                f"<!-- condor-reserva-id: {SESSION_A} -->"
            ),
            "head": {"ref": "trabajo/issue-12", "sha": "head-renew"},
            "base": {"ref": "main"},
        }
        api.issue_data["body"] = VALID_ACCEPTANCE_BODY.replace(
            "El gate base pasa.", "La nueva evidencia pasa."
        )
        return api

    def test_renew_pinned_acceptance_preserves_branch_and_pull(self) -> None:
        api = self._renew_fixture()
        new_id = renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        self.assertNotEqual(new_id, SESSION_A)
        self.assertEqual(api.branches["trabajo/issue-12"], "abc123")
        self.assertEqual(api.pulls[15]["state"], "open")
        self.assertEqual(reservation_from_pr_body(api.pulls[15]["body"]), new_id)
        active = active_reservation(api, 12)
        self.assertEqual(active["reservation_id"], new_id)
        self.assertEqual(
            active["acceptance_sha256"],
            contract_fingerprint(api.issue_data["body"]),
        )

    def test_renew_acceptance_invalidates_old_head_evidence(self) -> None:
        api = self._renew_fixture()
        renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        self.assertEqual(
            {row["name"] for row in api.check_runs},
            {"Validar"},
        )
        self.assertTrue(all(
            row["head_sha"] == "head-renew"
            and row["conclusion"] == "failure"
            for row in api.check_runs
        ))

    def test_renew_acceptance_invalidates_aggregate_check_first(self) -> None:
        """Publica una única evidencia canónica Validar sobre el HEAD exacto."""
        api = self._renew_fixture()
        renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        self.assertEqual([check["name"] for check in api.check_runs], ["Validar"])
        self.assertEqual(api.check_runs[0]["head_sha"], "head-renew")
        self.assertEqual(api.check_runs[0]["conclusion"], "failure")

    def test_renew_acceptance_second_check_error_preserves_failed_aggregate(self) -> None:
        """Compat: ya no existe un segundo POST parcial que pueda quedar stale."""
        api = self._renew_fixture()
        renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        self.assertEqual(len(api.check_runs), 1)
        self.assertEqual(api.check_runs[0]["name"], "Validar")

    def test_renew_acceptance_rejects_unauthorized_stale_and_races(self) -> None:
        api = self._renew_fixture()
        for actor, session in (("intruso", SESSION_A), ("pl0n3r", SESSION_B)):
            with self.assertRaises(CoordinationError):
                renew_pinned_acceptance(api, 12, actor, "OWNER", session)
        with self.assertRaises(CoordinationError):
            renew_pinned_acceptance(api, 12, "pl0n3r", "NONE", SESSION_A)
        self.assertEqual(api.check_runs, [])
        stable = api.issue_data["body"]
        api.issue_data["body"] = VALID_ACCEPTANCE_BODY
        with self.assertRaisesRegex(CoordinationError, "No hay cambio"):
            renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        api.issue_data["body"] = "contrato inválido"
        with self.assertRaises(Exception):
            renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        api.issue_data["body"] = stable
        api.pulls[16] = dict(api.pulls[15], number=16)
        with self.assertRaisesRegex(CoordinationError, "exactamente un PR"):
            renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        del api.pulls[16]
        old_create = api.create_failed_check
        def conflicting_check(*args):
            old_create(*args)
            api.issue_data["body"] = VALID_ACCEPTANCE_BODY
        api.create_failed_check = conflicting_check
        with self.assertRaisesRegex(CoordinationError, "cambió"):
            renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        self.assertEqual(active_reservation(api, 12)["reservation_id"], SESSION_A)

    def test_renew_acceptance_rolls_back_partial_failure(self) -> None:
        api = self._renew_fixture()
        original = api.pulls[15]["body"]
        api.pull_update_failures_remaining = 1
        with self.assertRaises(CoordinationError):
            renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        self.assertEqual(api.pulls[15]["body"], original)
        self.assertEqual(active_reservation(api, 12)["reservation_id"], SESSION_A)
        self.assertEqual(len(api.check_runs), 1)
        api = self._renew_fixture()
        api.fail_comment = True
        original = api.pulls[15]["body"]
        with self.assertRaises(CoordinationError):
            renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        self.assertEqual(api.pulls[15]["body"], original)
        self.assertEqual(active_reservation(api, 12)["reservation_id"], SESSION_A)
        self.assertEqual(len(api.check_runs), 1)

    def test_renew_acceptance_keeps_new_session_after_ambiguous_comment_error(self) -> None:
        """Si GitHub persistió el marker, reconcilia y devuelve la sesión nueva."""
        api = self._renew_fixture()
        original_comment = api.comment
        def persisted_then_error(issue_number, body):
            original_comment(issue_number, body)
            raise CoordinationError("timeout tras persistir comentario")
        api.comment = persisted_then_error
        new_id = renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        winner = active_reservation(api, 12)
        self.assertIsNotNone(winner)
        self.assertEqual(winner["reservation_id"], new_id)
        self.assertEqual(
            reservation_from_pr_body(api.pulls[15]["body"]),
            winner["reservation_id"],
        )
        self.assertEqual(len(api.check_runs), 1)

    def test_renew_failure_cannot_leave_old_evidence_eligible(self) -> None:
        """AC-01: deriva a un único Validar failure antes de mutar sesión/PR."""
        api = self._renew_fixture()
        original = api.pulls[15]["body"]
        original_check = api.create_failed_check
        calls = {"n": 0}
        def record_once(name, sha, title, summary):
            calls["n"] += 1
            original_check(name, sha, title, summary)
        api.create_failed_check = record_once

        renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)

        self.assertEqual(calls["n"], 1)
        self.assertEqual(api.check_runs[0]["name"], "Validar")
        self.assertEqual(api.check_runs[0]["conclusion"], "failure")
        self.assertNotEqual(api.pulls[15]["body"], original)

    def test_renew_success_reconciles_issue_and_pull_metadata(self) -> None:
        """AC-02: éxito termina con el mismo UUID vigente en Issue y PR."""
        api = self._renew_fixture()
        new_id = renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        winner = active_reservation(api, 12)
        self.assertEqual(winner["reservation_id"], new_id)
        self.assertEqual(
            reservation_from_pr_body(api.pulls[15]["body"]),
            new_id,
        )
        self.assertEqual(
            winner["acceptance_sha256"],
            contract_fingerprint(api.issue_data["body"]),
        )

    def test_renew_ambiguous_persist_reconciles_new_session(self) -> None:
        """AC-03: timeout posterior al marker converge a la sesión persistida."""
        api = self._renew_fixture()
        original_comment = api.comment
        def persisted_then_error(issue_number, body):
            original_comment(issue_number, body)
            # Simula respuesta perdida después de persistir.
            raise CoordinationError("respuesta ambigua")
        api.comment = persisted_then_error

        new_id = renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)

        self.assertEqual(active_reservation(api, 12)["reservation_id"], new_id)
        self.assertEqual(
            reservation_from_pr_body(api.pulls[15]["body"]),
            new_id,
        )

    def test_renew_competing_session_fails_closed_without_overwrite(self) -> None:
        """AC-04: una sesión competidora gana y el PR se alinea a ella."""
        api = self._renew_fixture()
        original_comment = api.comment
        competitor = "33333333-3333-4333-8333-333333333333"

        def competitor_wins(issue_number, body):
            marker = reservation_marker(
                "pl0n3r",
                competitor,
                "trabajo/issue-12",
                True,
                "transferir",
                contract_fingerprint(api.issue_data["body"]),
            )
            original_comment(issue_number, marker)

        api.comment = competitor_wins
        with self.assertRaisesRegex(CoordinationError, "reconciliar"):
            renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)

        self.assertEqual(active_reservation(api, 12)["reservation_id"], competitor)
        self.assertEqual(
            reservation_from_pr_body(api.pulls[15]["body"]),
            competitor,
        )
        self.assertEqual(api.check_runs[0]["name"], "Validar")

    def test_renew_retry_reconciles_interrupted_session(self) -> None:
        """AC-05: retry con UUID anterior reconoce sucesor y repara el PR."""
        api = self._renew_fixture()
        original_comment = api.comment
        captured = {"new_id": None}

        def persist_and_desync(issue_number, body):
            original_comment(issue_number, body)
            captured["new_id"] = active_reservation(api, 12)["reservation_id"]
            api.pulls[15]["body"] = (
                f"Closes #12\nReserva: {SESSION_A}\n"
                f"<!-- condor-reserva-id: {SESSION_A} -->"
            )
            raise CoordinationError("timeout tras persistir")

        api.comment = persist_and_desync
        first = renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        self.assertEqual(first, captured["new_id"])
        # Vuelve a desincronizar para demostrar que el retry no crea otro UUID.
        api.pulls[15]["body"] = (
            f"Closes #12\nReserva: {SESSION_A}\n"
            f"<!-- condor-reserva-id: {SESSION_A} -->"
        )
        api.comment = original_comment

        retry = renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)

        self.assertEqual(retry, first)
        self.assertEqual(active_reservation(api, 12)["reservation_id"], first)
        self.assertEqual(
            reservation_from_pr_body(api.pulls[15]["body"]),
            first,
        )

    def test_renew_retry_reconciles_old_issue_new_pr_without_new_uuid(self) -> None:
        """AC-01: old Issue/new PR converge al successor determinista."""
        api = self._renew_fixture()
        live_acceptance = contract_fingerprint(api.issue_data["body"])
        expected = renewal_reservation_id(
            12, SESSION_A, live_acceptance, None, "head-renew"
        )
        api.pulls[15]["body"] = (
            f"Closes #12\nReserva: {expected}\n"
            f"<!-- condor-reserva-id: {expected} -->"
        )

        result = renew_pinned_acceptance(
            api, 12, "pl0n3r", "OWNER", SESSION_A
        )

        self.assertEqual(result, expected)
        self.assertEqual(active_reservation(api, 12)["reservation_id"], expected)
        self.assertEqual(
            reservation_from_pr_body(api.pulls[15]["body"]),
            expected,
        )
        self.assertEqual(len(api.check_runs), 1)

    def test_renew_retry_reconciles_new_issue_old_pr_without_new_uuid(self) -> None:
        """AC-02: new Issue/old PR repara el PR sin crear otra sesión."""
        api = self._renew_fixture()
        first = renew_pinned_acceptance(
            api, 12, "pl0n3r", "OWNER", SESSION_A
        )
        checks_before = list(api.check_runs)
        api.pulls[15]["body"] = (
            f"Closes #12\nReserva: {SESSION_A}\n"
            f"<!-- condor-reserva-id: {SESSION_A} -->"
        )

        retry = renew_pinned_acceptance(
            api, 12, "pl0n3r", "OWNER", SESSION_A
        )

        self.assertEqual(retry, first)
        self.assertEqual(active_reservation(api, 12)["reservation_id"], first)
        self.assertEqual(
            reservation_from_pr_body(api.pulls[15]["body"]),
            first,
        )
        self.assertEqual(api.check_runs, checks_before)

    def test_renew_retry_rejects_stale_successor_after_contract_or_head_drift(self) -> None:
        """AC-03: acceptance, task o HEAD drift invalidan el successor histórico."""
        task = (
            '<!-- factory-plan-task '
            '{"version":1,"epic":999,"task_key":"A","order":1,'
            '"owner":"pl0n3r","roles":["qa"],"depends_on":[],'
            '"paths":["scripts/"]} -->'
        )

        api = self._renew_fixture()
        api.issue_data["body"] += "\n" + task
        renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        api.issue_data["body"] = api.issue_data["body"].replace(
            "La nueva evidencia pasa.", "La evidencia volvió a cambiar."
        )
        with self.assertRaisesRegex(CoordinationError, "successor histórico"):
            renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)

        api = self._renew_fixture()
        api.issue_data["body"] += "\n" + task
        renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        api.issue_data["body"] = api.issue_data["body"].replace(
            '"paths":["scripts/"]', '"paths":["docs/"]'
        )
        with self.assertRaisesRegex(CoordinationError, "successor histórico"):
            renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)

        api = self._renew_fixture()
        api.issue_data["body"] += "\n" + task
        renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)
        api.pulls[15]["head"]["sha"] = "head-after-drift"
        with self.assertRaisesRegex(CoordinationError, "successor histórico"):
            renew_pinned_acceptance(api, 12, "pl0n3r", "OWNER", SESSION_A)

    def test_renew_retry_preserves_third_party_winner(self) -> None:
        """AC-04: tercera sesión gana y el retry no la sobrescribe."""
        api = self._renew_fixture()
        first = renew_pinned_acceptance(
            api, 12, "pl0n3r", "OWNER", SESSION_A
        )
        third = "33333333-3333-4333-8333-333333333333"
        api.comment(
            12,
            reservation_marker(
                "pl0n3r",
                third,
                "trabajo/issue-12",
                True,
                "transferir",
                contract_fingerprint(api.issue_data["body"]),
            ),
        )
        api.pulls[15]["body"] = (
            f"Closes #12\nReserva: {third}\n"
            f"<!-- condor-reserva-id: {third} -->"
        )
        checks_before = list(api.check_runs)

        with self.assertRaisesRegex(CoordinationError, "no vigente"):
            renew_pinned_acceptance(
                api, 12, "pl0n3r", "OWNER", SESSION_A
            )

        self.assertEqual(active_reservation(api, 12)["reservation_id"], third)
        self.assertEqual(
            reservation_from_pr_body(api.pulls[15]["body"]),
            third,
        )
        self.assertNotEqual(first, third)
        self.assertEqual(api.check_runs, checks_before)
        self.assertEqual(api.check_runs[-1]["name"], "Validar")
        self.assertEqual(api.check_runs[-1]["conclusion"], "failure")

    def test_renew_acceptance_documents_idempotent_v2_protocol(self) -> None:
        """AC-05: PLAN fija successor estable, reconciliación y un solo Validar."""
        docs = (Path(__file__).resolve().parents[1] / "PLAN-AGENTES.md").read_text()
        self.assertIn("successor UUID determinista", docs)
        self.assertIn("old/old", docs)
        self.assertIn("old/new", docs)
        self.assertIn("new/old", docs)
        self.assertIn("new/new", docs)
        self.assertIn("un único `Validar`", docs)

    def test_renew_acceptance_documents_explicit_v2_protocol(self) -> None:
        self.assertEqual(
            parse_comment_command(f"/renovar-contrato {SESSION_A}"),
            ("renovar-contrato", SESSION_A),
        )
        docs = (Path(__file__).resolve().parents[1] / "PLAN-AGENTES.md").read_text()
        self.assertIn("/renovar-contrato", docs)
        self.assertIn("/migrar-contrato", docs)
        self.assertIn("contrato anterior", docs.lower())

    def test_parse_comment_commands(self) -> None:
        """Interpreta comandos y valida UUID cuando corresponde."""
        self.assertEqual(parse_comment_command("/tomar"), ("tomar", None))
        self.assertEqual(
            parse_comment_command(f"/liberar {SESSION_A}"),
            ("liberar", SESSION_A),
        )
        self.assertEqual(
            parse_comment_command(f"/transferir {SESSION_A}"),
            ("transferir", SESSION_A),
        )
        self.assertEqual(
            parse_comment_command(f"/migrar-contrato {SESSION_A}"),
            ("migrar-contrato", SESSION_A),
        )
        self.assertEqual(
            parse_comment_command("/adoptar-contrato-huerfana"),
            ("adoptar-contrato-huerfana", None),
        )
        with self.assertRaises(CoordinationError):
            parse_comment_command("/liberar no-es-uuid")

    def test_pr_opened_ready_moves_to_review(self) -> None:
        """Un PR no draft abierto desde reserva pasa a revisión."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
            "merged": False,
        }
        update_pr_state(api, 15, "opened")
        self.assertEqual(api.status_history[-1], STATUS_REVIEW)

    def test_pr_close_without_merge_releases(self) -> None:
        """Cerrar un PR sin merge libera el trabajo."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15,
            "state": "closed",
            "draft": False,
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
            "merged": False,
        }
        update_pr_state(api, 15, "closed")
        self.assertNotIn("trabajo/issue-12", api.branches)
        self.assertEqual(api.status_history[-1], STATUS_AVAILABLE)

    def test_issue_close_cleans_branch_and_completes(self) -> None:
        """Cerrar un Issue limpia su rama y marca el trabajo completado."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.issue_data["state"] = "closed"
        update_issue_state(api, 12, "closed")
        self.assertNotIn("trabajo/issue-12", api.branches)
        self.assertEqual(api.status_history[-1], STATUS_COMPLETED)

    def test_issue_close_is_idempotent_after_merged_pr_cleanup(self) -> None:
        """Un cierre ya reconciliado no repite mutaciones de GitHub."""
        api = FakeGitHub()
        api.issue_data["state"] = "closed"
        api.issue_data["state_reason"] = "completed"
        api.issue_data["labels"] = [{"name": STATUS_COMPLETED}]
        api.branches.pop("trabajo/issue-12", None)

        update_issue_state(api, 12, "closed")

        self.assertEqual(api.status_history, [])
        self.assertEqual(api.comments, [])

    def test_cancelled_issue_close_is_idempotent_after_cleanup(self) -> None:
        """El estado terminal cancelado también tolera eventos duplicados."""
        api = FakeGitHub()
        api.issue_data["state"] = "closed"
        api.issue_data["state_reason"] = "not_planned"
        api.issue_data["labels"] = [{"name": STATUS_CANCELLED}]
        api.branches.pop("trabajo/issue-12", None)

        update_issue_state(api, 12, "closed")

        self.assertEqual(api.status_history, [])
        self.assertEqual(api.comments, [])

    def test_validate_pull_requires_main(self) -> None:
        """Rechaza un PR cuyo destino no sea main."""
        api = FakeGitHub()
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": "Closes #12",
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "otra-rama"},
        }
        with self.assertRaises(CoordinationError):
            validate_pull(api, 15, False)

    def test_open_pr_with_closed_issue_still_fails_closed(self) -> None:
        """AC-02: un PR abierto conserva el fail-closed si su Issue ya cerró."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.issue_data["state"] = "closed"
        api.issue_data["state_reason"] = "completed"
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": f"Closes #12\n<!-- condor-reserva-id: {SESSION_A} -->",
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }
        api.pull_files_map[15] = {"src/a.php"}

        with self.assertRaisesRegex(
            CoordinationError,
            r"Issue #12 debe estar abierto durante el PR",
        ):
            validate_pull(api, 15, True)

    def test_validate_pull_checks_active_session(self) -> None:
        """Valida que el PR declare exactamente la sesión activa."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": f"Closes #12\n<!-- condor-reserva-id: {SESSION_A} -->",
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }
        api.pull_files_map[15] = {"src/a.php"}
        validate_pull(api, 15, True)

        api.pulls[15]["body"] = (
            f"Closes #12\n<!-- condor-reserva-id: {SESSION_B} -->"
        )
        with self.assertRaises(CoordinationError):
            validate_pull(api, 15, True)

    def test_normal_reserved_pr_still_requires_closing_relation(self) -> None:
        """El flujo normal conserva la relación de cierre obligatoria."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": f"<!-- condor-reserva-id: {SESSION_A} -->",
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }
        with self.assertRaisesRegex(CoordinationError, r"Closes #12"):
            validate_pull(api, 15, True)

    def test_incident_can_use_explicit_non_closing_post_merge_relation(self) -> None:
        """Un incidente puede conservarse abierto hasta su validación post-merge."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.issue_data["labels"].append({"name": "tipo: incidente"})
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": (
                '<!-- factory-issue-lifecycle '
                '{"version":1,"issue":12,"mode":"post_merge_validation"} -->\n'
                f"<!-- condor-reserva-id: {SESSION_A} -->"
            ),
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }
        api.pull_files_map[15] = {"src/a.php"}

        validate_pull(api, 15, True)

    def test_non_closing_relation_fails_closed_outside_incident_contract(self) -> None:
        """Número, tipo, unicidad y reserva siguen siendo requisitos fail-closed."""
        marker = (
            '<!-- factory-issue-lifecycle '
            '{"version":1,"issue":12,"mode":"post_merge_validation"} -->'
        )

        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": f"{marker}\n<!-- condor-reserva-id: {SESSION_A} -->",
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }
        with self.assertRaisesRegex(CoordinationError, "solo se permite.*incidente"):
            validate_pull(api, 15, True)

        api.issue_data["labels"].append({"name": "tipo: incidente"})
        api.pulls[15]["body"] = (
            '<!-- factory-issue-lifecycle '
            '{"version":1,"issue":13,"mode":"post_merge_validation"} -->\n'
            f"<!-- condor-reserva-id: {SESSION_A} -->"
        )
        with self.assertRaisesRegex(CoordinationError, "mismo Issue"):
            validate_pull(api, 15, True)

        api.pulls[15]["body"] = (
            f"{marker}\n{marker}\n<!-- condor-reserva-id: {SESSION_A} -->"
        )
        with self.assertRaisesRegex(CoordinationError, "como máximo un"):
            validate_pull(api, 15, True)

        api.pulls[15]["body"] = (
            '<!-- factory-issue-lifecycle '
            '{"version":1,"issue":12,"mode":"post_merge_validation","extra":true} -->\n'
            f"<!-- condor-reserva-id: {SESSION_A} -->"
        )
        with self.assertRaisesRegex(CoordinationError, "solo admite"):
            validate_pull(api, 15, True)

        api.comments.clear()
        api.pulls[15]["body"] = f"{marker}\n<!-- condor-reserva-id: {SESSION_A} -->"
        with self.assertRaisesRegex(
            CoordinationError,
            "marcador de reserva activo y confiable",
        ):
            validate_pull(api, 15, True)

    def test_post_merge_incident_lifecycle_is_documented(self) -> None:
        """La excepción queda documentada sin ampliar autoridad."""
        root = Path(__file__).resolve().parents[1]
        docs = (root / "docs" / "orquestador.md").read_text(encoding="utf-8")

        self.assertIn("factory-issue-lifecycle", docs)
        self.assertIn("post_merge_validation", docs)
        self.assertIn("solo para incidentes", docs)
        self.assertIn("permanece abierto", docs)
        self.assertIn("no amplía autoridad", docs)

    def test_file_overlap_detects_collisions(self) -> None:
        """Detecta colisiones exactas de archivos."""
        current = {"src/a.php", "README.md", "src/b.php"}
        others = {
            10: {"src/a.php", "src/x.php"},
            11: {"docs/otro.md"},
            12: {"README.md"},
        }
        self.assertEqual(
            file_overlaps(current, others),
            {10: ["src/a.php"], 12: ["README.md"]},
        )

    def test_validate_pull_rejects_open_pr_overlap(self) -> None:
        """Rechaza un PR que pisa archivos de otro PR abierto."""
        api = FakeGitHub()
        add_active_reservation(api)
        api.pulls[15] = {
            "number": 15,
            "state": "open",
            "draft": False,
            "body": f"Closes #12\n<!-- condor-reserva-id: {SESSION_A} -->",
            "head": {"ref": "trabajo/issue-12"},
            "base": {"ref": "main"},
        }
        api.pulls[20] = {
            "number": 20,
            "state": "open",
            "draft": False,
            "body": "Closes #20",
            "head": {"ref": "trabajo/issue-20"},
            "base": {"ref": "main"},
        }
        api.pull_files_map[15] = {"src/a.php"}
        api.pull_files_map[20] = {"src/a.php"}
        with self.assertRaises(CoordinationError):
            validate_pull(api, 15, True)


    def tearDown(self) -> None:
        """Restaura el perfil ES para aislar cada prueba."""
        coordinator.configure_profile("es")

    def test_default_profile_preserves_spanish_contract(self) -> None:
        """Conserva el contrato observable del perfil ES existente."""
        coordinator.configure_profile("es")
        self.assertEqual(coordinator.branch_for_issue(12), "trabajo/issue-12")
        self.assertEqual(coordinator.parse_comment_command("/tomar"), ("tomar", None))
        self.assertEqual(
            coordinator.parse_comment_command(f"/liberar {SESSION_A}"),
            ("liberar", SESSION_A),
        )
        marker = coordinator.reservation_marker(
            "pl0n3r", SESSION_A, "trabajo/issue-12", True, "tomar",
            "a" * 64,
        )
        self.assertIn("<!-- condor-reserva ", marker)
        self.assertEqual(coordinator.STATUS_AVAILABLE, "estado: disponible")

    def test_contract_renewal_command_is_profile_invariant(self) -> None:
        """Renovación explícita conserva la misma semántica en ES y EN."""
        for profile in ("es", "en"):
            with self.subTest(profile=profile):
                coordinator.configure_profile(profile)
                self.assertEqual(
                    coordinator.parse_comment_command(f"/renovar-contrato {SESSION_A}"),
                    ("renovar-contrato", SESSION_A),
                )
                with self.assertRaises(CoordinationError):
                    coordinator.parse_comment_command("/renovar-contrato no-es-uuid")

    def test_english_profile_supports_brvtal_coordination_contract(self) -> None:
        """Cubre reservas, comandos y estados del perfil EN de BRVTAL."""
        coordinator.configure_profile("en")
        api = FakeGitHub()
        api.repo = "pl0n3r/brvtal"
        api.issue_data["labels"] = [{"name": coordinator.STATUS_AVAILABLE}]
        session = coordinator.reserve_work(api, 12, "pl0n3r", "OWNER")
        self.assertIsNotNone(session)
        self.assertIn("work/issue-12", api.branches)
        self.assertEqual(coordinator.STATUS_RESERVED, "status: reserved")
        self.assertEqual(coordinator.parse_comment_command("/take"), ("tomar", None))
        self.assertEqual(
            coordinator.parse_comment_command(f"/release {session}"),
            ("liberar", session),
        )
        self.assertEqual(
            coordinator.parse_comment_command(f"/transfer {session}"),
            ("transferir", session),
        )
        self.assertEqual(
            coordinator.parse_comment_command(f"/recover {session}"),
            ("recuperar", session),
        )
        self.assertEqual(
            coordinator.parse_comment_command(f"/renovar-contrato {session}"),
            ("renovar-contrato", session),
        )
        coordinator.release_work(api, 12, "pl0n3r", "OWNER", session, False)
        self.assertNotIn("work/issue-12", api.branches)
        self.assertIn(
            coordinator.STATUS_AVAILABLE,
            {row["name"] for row in api.issue_data["labels"]},
        )

    def test_english_profile_reads_brvtal_legacy_reservations(self) -> None:
        """Acepta metadata histórica BRVTAL sin crear una segunda autoridad."""
        coordinator.configure_profile("en")
        body = (
            '<!-- brvtal-work-reservation '
            '{"active":true,"branch":"work/issue-12","owner":"pl0n3r",'
            f'"reason":"take","reservation_id":"{SESSION_A}","version":1}} -->'
        )
        comments = [{"body": body, "user": {"login": BOT}}]
        reservation = coordinator.latest_reservation(comments)
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation["branch"], "work/issue-12")
        self.assertEqual(
            coordinator.reservation_from_pr_body(
                f"Closes #12\n<!-- brvtal-reservation-id: {SESSION_A} -->"
            ),
            SESSION_A,
        )

    @staticmethod
    def _reservation_payload_for_version(version: object) -> dict:
        """Construye un marker con shape compatible para probar el tipo de version."""
        payload = {
            "version": version,
            "owner": "pl0n3r",
            "reservation_id": SESSION_A,
            "branch": coordinator.branch_for_issue(12),
            "active": True,
            "reason": "tomar",
        }
        if version == 2:
            payload["acceptance_sha256"] = "a" * 64
        elif version == 3:
            payload.update(
                {
                    "acceptance_sha256": "a" * 64,
                    "task_marker_sha256": "b" * 64,
                    "task_paths": ["scripts/coordinar_trabajo.py"],
                    "task_depends_on": [],
                }
            )
        return payload

    def test_reservation_version_requires_strict_integer_type(self) -> None:
        """AC-01: bool/float no pueden aprovechar igualdad con enteros."""
        for version in (True, 1.0, 2.0, 3.0):
            with self.subTest(version=version):
                payload = self._reservation_payload_for_version(version)
                self.assertFalse(coordinator.valid_reservation_payload(payload))

    def test_reservation_version_rejects_bool_float_string_and_out_of_range(self) -> None:
        """AC-02: todo tipo/rango ajeno a 1..3 falla cerrado."""
        invalid_versions = (
            True,
            False,
            1.0,
            2.0,
            3.0,
            "1",
            "2",
            "3",
            None,
            0,
            4,
            -1,
        )
        for version in invalid_versions:
            with self.subTest(version=version):
                payload = self._reservation_payload_for_version(version)
                self.assertFalse(coordinator.valid_reservation_payload(payload))

    def test_reservation_versions_v1_v2_v3_remain_canonical(self) -> None:
        """AC-03: los tres contratos enteros existentes conservan compatibilidad."""
        for version in (1, 2, 3):
            with self.subTest(version=version):
                payload = self._reservation_payload_for_version(version)
                self.assertIs(type(version), int)
                self.assertTrue(coordinator.valid_reservation_payload(payload))

    def test_noninteger_version_marker_never_becomes_reservation_authority(self) -> None:
        """AC-04: un marker no entero se descarta antes de convertirse en autoridad."""
        for version in (True, 1.0, 2.0, 3.0):
            with self.subTest(version=version):
                payload = self._reservation_payload_for_version(version)
                body = (
                    f"<!-- {coordinator.PROFILE.marker} "
                    f"{json.dumps(payload, separators=(',', ':'))} -->"
                )
                self.assertIsNone(coordinator.reservation_from_text(body))

    def test_reservation_version_type_is_profile_invariant(self) -> None:
        """AC-05: ES y EN aplican exactamente el mismo cierre de tipos."""
        previous = coordinator.PROFILE.name
        try:
            for profile in ("es", "en"):
                coordinator.configure_profile(profile)
                for version in (1, 2, 3):
                    with self.subTest(profile=profile, version=version):
                        payload = self._reservation_payload_for_version(version)
                        self.assertTrue(coordinator.valid_reservation_payload(payload))
                for version in (True, 1.0, 2.0, 3.0, "2"):
                    with self.subTest(profile=profile, invalid=version):
                        payload = self._reservation_payload_for_version(version)
                        self.assertFalse(coordinator.valid_reservation_payload(payload))
        finally:
            coordinator.configure_profile(previous)

    def test_profiles_fail_closed_on_authority_and_collision_errors(self) -> None:
        """Exige autoridad y ausencia de colisiones en ambos perfiles."""
        for profile in ("es", "en"):
            coordinator.configure_profile(profile)
            api = FakeGitHub()
            api.issue_data["labels"] = [{"name": coordinator.STATUS_AVAILABLE}]
            with self.assertRaises(CoordinationError):
                coordinator.reserve_work(api, 12, "intruso", "NONE")
            wrong_branch = (
                "work/issue-12" if profile == "es" else "trabajo/issue-12"
            )
            payload = {
                "version": 1,
                "owner": "pl0n3r",
                "reservation_id": SESSION_A,
                "branch": wrong_branch,
                "active": True,
                "reason": "take",
            }
            self.assertFalse(coordinator.valid_reservation_payload(payload))
            api.pulls[15] = {
                "number": 15, "state": "open",
                "head": {"ref": coordinator.branch_for_issue(12)},
                "base": {"ref": "main"},
            }
            api.pulls[20] = {
                "number": 20, "state": "open",
                "head": {"ref": coordinator.branch_for_issue(20)},
                "base": {"ref": "main"},
            }
            api.pull_files_map[15] = {"same.txt"}
            api.pull_files_map[20] = {"same.txt"}
            self.assertTrue(coordinator.collision_validation_errors(api, 15))


    def test_english_coordination_commands_do_not_refresh_stale_lease(self) -> None:
        """Los comandos EN tampoco alteran el lease de trabajo."""
        coordinator.configure_profile("en")
        commands = [
            "/take",
            "/force-release",
            f"/release {SESSION_A}",
            f"/transfer {SESSION_A}",
            f"/recover {SESSION_A}",
        ]

        for body in commands:
            api = FakeGitHub()
            api.repo = "pl0n3r/brvtal"
            api.branches = {"main": "abc123", "work/issue-12": "abc123"}
            stale = "2020-01-01T00:00:00+00:00"
            api.comments = [
                {
                    "user": {"login": BOT},
                    "body": coordinator.reservation_marker(
                        "pl0n3r",
                        SESSION_A,
                        "work/issue-12",
                        True,
                        "take",
                        contract_fingerprint(VALID_ACCEPTANCE_BODY),
                    ),
                    "created_at": stale,
                    "updated_at": stale,
                },
                {
                    "user": {"login": "pl0n3r"},
                    "body": body,
                    "created_at": "2020-01-01T00:29:00+00:00",
                    "updated_at": "2020-01-01T00:29:00+00:00",
                },
            ]
            api.commit_times["abc123"] = datetime(2020, 1, 1, tzinfo=timezone.utc)

            with self.subTest(body=body):
                self.assertEqual(
                    coordinator.work_activity_timestamp(api, 12, "work/issue-12"),
                    datetime(2020, 1, 1, tzinfo=timezone.utc),
                )

    def test_reusable_profile_runtime_and_template_are_publish_safe(self) -> None:
        """El ref probado ejecuta el perfil nuevo sin romper callers @v1 existentes."""
        root = Path(__file__).resolve().parents[1]
        reusable = (root / ".github/workflows/coordinacion.yml").read_text()
        template = (
            root / "template/.github/workflows/coordinacion.yml"
        ).read_text()

        self.assertIn("kit_ref:", reusable)
        self.assertEqual(
            reusable.count("ref: ${{ job.workflow_sha }}"),
            6,
        )
        self.assertEqual(
            reusable.count("repository: ${{ job.workflow_repository }}"),
            6,
        )
        self.assertNotIn("inputs.kit_ref", reusable)
        self.assertNotIn("profile: es", template)
        self.assertEqual(
            template.count(
                "uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1"
            ),
            6,
        )

    @staticmethod
    def _planned_issue_for_repair(
        number: int,
        paths: list[str],
        *,
        status: str = "estado: disponible",
    ) -> dict:
        marker = {
            "version": 1,
            "epic": 439,
            "task_key": f"REPAIR_{number}",
            "order": number,
            "owner": "pl0n3r",
            "roles": ["ingenieria-software"],
            "depends_on": [],
            "paths": paths,
        }
        return {
            "number": number,
            "state": "open",
            "state_reason": None,
            "labels": [{"name": status}],
            "body": (
                "<!-- factory-plan-task "
                + json.dumps(marker, separators=(",", ":"))
                + " -->"
            ),
        }

    def test_untrusted_active_issue_without_reservation_snapshot_does_not_block_disjoint_take(self) -> None:
        """AC-01: un estado activo sin reserva confiable no adquiere autoridad de claims."""
        orphan = self._planned_issue_for_repair(
            473,
            ["tests/test_observability_fabric.py"],
            status="estado: en revisión",
        )
        candidate = self._planned_issue_for_repair(
            478,
            ["src/DisasterRecoveryPolicy.php"],
        )

        blockers = coordinator.reservation_blockers(
            candidate,
            [orphan, candidate],
            "pl0n3r",
            {},
            active_task_snapshots={},
            active_dependency_states={},
            active_reservation_numbers=set(),
        )

        self.assertEqual(blockers, [])

    def test_partial_release_is_idempotent(self) -> None:
        """AC-02: liberar forzado reconcilia dos veces un estado parcial sin reactivar trabajo."""
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": STATUS_REVIEW}]
        api.branches["trabajo/issue-12"] = "abc123"

        release_work(api, 12, "pl0n3r", "OWNER", None, True)
        release_work(api, 12, "pl0n3r", "OWNER", None, True)

        self.assertNotIn("trabajo/issue-12", api.branches)
        self.assertIn(
            STATUS_AVAILABLE,
            {row["name"] for row in api.issue_data["labels"]},
        )
        self.assertTrue(
            all("acceptance_sha256" not in row["body"] for row in api.comments)
        )

    def test_valid_overlapping_reservation_still_blocks(self) -> None:
        """AC-03: una reserva válida con claims solapados conserva el bloqueo fail-closed."""
        active = self._planned_issue_for_repair(
            10,
            ["scripts/"],
            status=STATUS_RESERVED,
        )
        candidate = self._planned_issue_for_repair(11, ["scripts/orquestador_kit.py"])
        marker = coordinator.parse_task_marker(active["body"])
        self.assertIsNotNone(marker)

        blockers = coordinator.reservation_blockers(
            candidate,
            [active, candidate],
            "pl0n3r",
            {},
            active_task_snapshots={10: marker},
            active_dependency_states={10: {}},
            active_reservation_numbers={10},
        )

        self.assertTrue(any("colisión" in item for item in blockers))

    def test_valid_disjoint_reservation_still_allows_parallel_take(self) -> None:
        """AC-04: una reserva válida disjunta sigue permitiendo paralelismo."""
        active = self._planned_issue_for_repair(
            10,
            ["docs/a.md"],
            status=STATUS_RESERVED,
        )
        candidate = self._planned_issue_for_repair(11, ["scripts/orquestador_kit.py"])
        marker = coordinator.parse_task_marker(active["body"])
        self.assertIsNotNone(marker)

        blockers = coordinator.reservation_blockers(
            candidate,
            [active, candidate],
            "pl0n3r",
            {},
            active_task_snapshots={10: marker},
            active_dependency_states={10: {}},
            active_reservation_numbers={10},
        )

        self.assertEqual(blockers, [])

    def test_recovery_never_fabricates_claims_or_acceptance(self) -> None:
        """AC-05: reconciliar un huérfano no sintetiza aceptación ni task claims."""
        api = FakeGitHub()
        api.issue_data["labels"] = [{"name": STATUS_REVIEW}]
        api.branches["trabajo/issue-12"] = "abc123"

        release_work(api, 12, "pl0n3r", "OWNER", None, True)

        self.assertTrue(api.comments)
        marker = api.comments[-1]["body"]
        self.assertNotIn("acceptance_sha256", marker)
        self.assertNotIn("task_paths", marker)
        self.assertNotIn("task_marker_sha256", marker)


class AcceptancePinHistoryTests(unittest.TestCase):
    """Regresiones del pin de aceptación al cerrar reservas de PR."""

    @staticmethod
    def _current_v2() -> dict:
        return {
            "version": 2,
            "owner": "pl0n3r",
            "reservation_id": SESSION_A,
            "branch": "trabajo/issue-12",
            "active": True,
            "reason": "tomar",
            "acceptance_sha256": contract_fingerprint(VALID_ACCEPTANCE_BODY),
        }

    @staticmethod
    def _current_v1() -> dict:
        return {
            "version": 1,
            "owner": "pl0n3r",
            "reservation_id": SESSION_A,
            "branch": "trabajo/issue-12",
            "active": True,
            "reason": "tomar",
        }

    def _close(
        self,
        current: dict,
        *,
        merged: bool,
    ) -> tuple[FakeGitHub, dict]:
        api = FakeGitHub()
        api.branches["trabajo/issue-12"] = "abc123"
        coordinator.close_pr_reservation(
            api,
            12,
            "trabajo/issue-12",
            {
                "merged": merged,
                "body": (
                    f"Closes #12\n"
                    f"<!-- condor-reserva-id: {current['reservation_id']} -->"
                ),
            },
            current,
        )
        latest = latest_reservation(api.issue_comments(12))
        self.assertIsNotNone(latest)
        assert latest is not None
        return api, latest

    def test_inactive_pr_merged_preserves_trusted_v2_acceptance_pin(self) -> None:
        """AC-01: el terminal fusionado conserva exactamente el pin v2 autenticado."""
        current = self._current_v2()
        _api, latest = self._close(current, merged=True)

        self.assertEqual(latest["version"], 2)
        self.assertFalse(latest["active"])
        self.assertEqual(latest["reason"], "pr-merged")
        self.assertEqual(
            latest["acceptance_sha256"],
            current["acceptance_sha256"],
        )
        self.assertEqual(latest["reservation_id"], SESSION_A)
        self.assertEqual(latest["branch"], "trabajo/issue-12")
        self.assertEqual(latest["owner"], "pl0n3r")

    def test_inactive_close_does_not_reactivate_reservation(self) -> None:
        """AC-02: conservar la evidencia no revive la lease cerrada."""
        api, latest = self._close(self._current_v2(), merged=True)

        self.assertFalse(latest["active"])
        self.assertIsNone(active_reservation(api, 12))

    def test_merged_v3_terminal_preserves_task_snapshot(self) -> None:
        """AC-03: v3 conserva el snapshot fijado junto con el pin autenticado."""
        current = self._current_v2()
        current.update(
            {
                "version": 3,
                "task_marker_sha256": "e" * 64,
                "task_paths": ["scripts/coordinar_trabajo.py"],
                "task_depends_on": [],
            }
        )
        _api, latest = self._close(current, merged=True)

        self.assertEqual(latest["version"], 3)
        self.assertEqual(
            latest["acceptance_sha256"],
            current["acceptance_sha256"],
        )
        self.assertEqual(latest["task_marker_sha256"], "e" * 64)
        self.assertEqual(latest["task_paths"], ["scripts/coordinar_trabajo.py"])
        self.assertEqual(latest["task_depends_on"], [])

    def test_acceptance_pin_fails_closed_without_prior_v2(self) -> None:
        """AC-04: una reserva legacy fusionada permanece terminal v1 sin pin."""
        _api, latest = self._close(self._current_v1(), merged=True)

        self.assertEqual(latest["version"], 1)
        self.assertFalse(latest["active"])
        self.assertNotIn("acceptance_sha256", latest)

    def test_unmerged_close_does_not_preserve_acceptance_or_task_pin(self) -> None:
        """AC-05: cerrar sin merge no conserva pin de aceptación ni snapshot."""
        current = self._current_v2()
        current.update(
            {
                "version": 3,
                "task_marker_sha256": "e" * 64,
                "task_paths": ["scripts/coordinar_trabajo.py"],
                "task_depends_on": [],
            }
        )
        _api, latest = self._close(current, merged=False)

        self.assertEqual(latest["version"], 1)
        self.assertFalse(latest["active"])
        self.assertEqual(latest["reason"], "pr-cerrado-sin-merge")
        self.assertNotIn("acceptance_sha256", latest)
        self.assertNotIn("task_marker_sha256", latest)
        self.assertNotIn("task_paths", latest)
        self.assertNotIn("task_depends_on", latest)


class AcceptancePinIdentityBindingTests(unittest.TestCase):
    """Liga evidencia terminal a la misma identidad declarada por el PR."""

    @staticmethod
    def _current_v2(
        *,
        branch: str = "trabajo/issue-12",
        reservation_id: str = SESSION_A,
    ) -> dict:
        return {
            "version": 2,
            "owner": "pl0n3r",
            "reservation_id": reservation_id,
            "branch": branch,
            "active": True,
            "reason": "tomar",
            "acceptance_sha256": contract_fingerprint(VALID_ACCEPTANCE_BODY),
        }

    def _close(
        self,
        current: dict,
        *,
        branch: str = "trabajo/issue-12",
        reservation_id: str | None = SESSION_A,
        merged: bool = True,
    ) -> tuple[FakeGitHub, dict]:
        api = FakeGitHub()
        api.branches[branch] = "abc123"
        body = "Closes #12"
        if reservation_id is not None:
            body += f"\n<!-- condor-reserva-id: {reservation_id} -->"
        coordinator.close_pr_reservation(
            api,
            12,
            branch,
            {"merged": merged, "body": body},
            current,
        )
        latest = latest_reservation(api.issue_comments(12))
        self.assertIsNotNone(latest)
        assert latest is not None
        return api, latest

    def test_matching_branch_and_reservation_preserve_evidence(self) -> None:
        """AC-01: branch + UUID exactos preservan pin y snapshot."""
        current = self._current_v2()
        current.update(
            {
                "version": 3,
                "task_marker_sha256": "e" * 64,
                "task_paths": ["scripts/coordinar_trabajo.py"],
                "task_depends_on": [],
            }
        )
        _api, latest = self._close(current)

        self.assertEqual(
            latest["acceptance_sha256"],
            current["acceptance_sha256"],
        )
        self.assertEqual(latest["task_marker_sha256"], "e" * 64)
        self.assertEqual(latest["task_paths"], ["scripts/coordinar_trabajo.py"])
        self.assertEqual(latest["task_depends_on"], [])

    def test_branch_mismatch_fails_closed_without_evidence(self) -> None:
        """AC-02: una reserva de otra branch no puede prestar su evidencia."""
        current = self._current_v2(branch="trabajo/issue-99")
        current.update(
            {
                "version": 3,
                "task_marker_sha256": "e" * 64,
                "task_paths": ["scripts/coordinar_trabajo.py"],
                "task_depends_on": [],
            }
        )
        _api, latest = self._close(current)

        self.assertEqual(latest["version"], 1)
        self.assertFalse(latest["active"])
        self.assertNotIn("acceptance_sha256", latest)
        self.assertNotIn("task_marker_sha256", latest)

    def test_reservation_id_mismatch_fails_closed_without_evidence(self) -> None:
        """AC-03: UUID distinto en el PR no puede recibir el pin activo."""
        current = self._current_v2()
        _api, latest = self._close(current, reservation_id=SESSION_B)

        self.assertEqual(latest["version"], 1)
        self.assertFalse(latest["active"])
        self.assertNotIn("acceptance_sha256", latest)
        self.assertNotIn("task_marker_sha256", latest)

    def test_terminal_remains_inactive_after_identity_check(self) -> None:
        """AC-04: la validación de identidad nunca reactiva la lease."""
        api, latest = self._close(self._current_v2())

        self.assertFalse(latest["active"])
        self.assertEqual(latest["reason"], "pr-merged")
        self.assertIsNone(active_reservation(api, 12))

    def test_existing_v2_v3_legacy_and_unmerged_semantics_are_preserved(self) -> None:
        """AC-05: conserva casos válidos y cierres fail-closed de #655."""
        current_v2 = self._current_v2()
        _api, v2 = self._close(current_v2)
        self.assertEqual(v2["version"], 2)
        self.assertEqual(
            v2["acceptance_sha256"],
            current_v2["acceptance_sha256"],
        )

        current_v3 = self._current_v2()
        current_v3.update(
            {
                "version": 3,
                "task_marker_sha256": "e" * 64,
                "task_paths": ["scripts/coordinar_trabajo.py"],
                "task_depends_on": [],
            }
        )
        _api, v3 = self._close(current_v3)
        self.assertEqual(v3["version"], 3)
        self.assertEqual(v3["task_marker_sha256"], "e" * 64)

        legacy = {
            "version": 1,
            "owner": "pl0n3r",
            "reservation_id": SESSION_A,
            "branch": "trabajo/issue-12",
            "active": True,
            "reason": "tomar",
        }
        _api, legacy_terminal = self._close(legacy)
        self.assertEqual(legacy_terminal["version"], 1)
        self.assertNotIn("acceptance_sha256", legacy_terminal)

        _api, unmerged = self._close(current_v3, merged=False)
        self.assertEqual(unmerged["version"], 1)
        self.assertEqual(unmerged["reason"], "pr-cerrado-sin-merge")
        self.assertNotIn("acceptance_sha256", unmerged)
        self.assertNotIn("task_marker_sha256", unmerged)

        _api, missing = self._close(current_v2, reservation_id=None)
        self.assertEqual(missing["version"], 1)
        self.assertNotIn("acceptance_sha256", missing)


class PostMergeEventOrderingTests(unittest.TestCase):
    """Cubre la carrera entre cierre del PR fusionado y cierre automático del Issue."""

    @staticmethod
    def _activate_v3(api: FakeGitHub) -> dict:
        branch = "trabajo/issue-12"
        api.branches[branch] = "abc123"
        api.set_status(12, STATUS_RESERVED)
        current = {
            "version": 3,
            "owner": "pl0n3r",
            "reservation_id": SESSION_A,
            "branch": branch,
            "active": True,
            "reason": "tomar",
            "acceptance_sha256": contract_fingerprint(VALID_ACCEPTANCE_BODY),
            "task_marker_sha256": "e" * 64,
            "task_paths": ["scripts/coordinar_trabajo.py"],
            "task_depends_on": [],
        }
        api.comments.append(
            {
                "user": {"login": BOT},
                "body": reservation_marker(
                    current["owner"],
                    current["reservation_id"],
                    current["branch"],
                    True,
                    current["reason"],
                    current["acceptance_sha256"],
                    task_snapshot={
                        "task_marker_sha256": current["task_marker_sha256"],
                        "task_paths": current["task_paths"],
                        "task_depends_on": current["task_depends_on"],
                    },
                ),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return current

    @staticmethod
    def _merged_pull(
        api: FakeGitHub,
        *,
        reservation_id: str = SESSION_A,
        branch: str = "trabajo/issue-12",
        closes_issue: int = 12,
        number: int = 15,
        head_repo: str | None = None,
        base_ref: str = "main",
    ) -> dict:
        pull = {
            "number": number,
            "state": "closed",
            "merged": True,
            "draft": False,
            "body": (
                f"Closes #{closes_issue}\n"
                f"<!-- condor-reserva-id: {reservation_id} -->"
            ),
            "head": {
                "ref": branch,
                "sha": f"head-{number}",
                "repo": {"full_name": head_repo or api.repo},
            },
            "base": {"ref": base_ref},
        }
        api.pulls[number] = pull
        return pull

    @staticmethod
    def _assert_v3_terminal(api: FakeGitHub, expected_pin: str) -> dict:
        latest = latest_reservation(api.issue_comments(12))
        assert latest is not None
        if latest.get("version") != 3:
            raise AssertionError(f"Se esperaba terminal v3, recibido: {latest}")
        if latest.get("acceptance_sha256") != expected_pin:
            raise AssertionError("El terminal no conservó el pin autenticado.")
        if latest.get("task_marker_sha256") != "e" * 64:
            raise AssertionError("El terminal no conservó el snapshot de task.")
        if latest.get("active") is not False:
            raise AssertionError("El terminal debe quedar inactivo.")
        if active_reservation(api, 12) is not None:
            raise AssertionError("El cierre no puede reactivar la lease.")
        return latest

    def test_pr_closed_then_issue_closed_preserves_same_identity_evidence(self) -> None:
        """AC-01: PR merged primero conserva evidencia y el Issue closed no la degrada."""
        api = FakeGitHub()
        current = self._activate_v3(api)
        self._merged_pull(api)

        update_pr_state(api, 15, "closed")
        api.issue_data["state"] = "closed"
        update_issue_state(api, 12, "closed")

        latest = self._assert_v3_terminal(api, current["acceptance_sha256"])
        self.assertEqual(latest["reason"], "pr-merged")

    def test_issue_closed_then_pr_closed_converges_to_merged_terminal_with_evidence(self) -> None:
        """AC-02: Issue closed primero detecta el merge exacto y conserva evidencia."""
        api = FakeGitHub()
        current = self._activate_v3(api)
        self._merged_pull(api)
        api.issue_data["state"] = "closed"

        update_issue_state(api, 12, "closed")
        update_pr_state(api, 15, "closed")

        latest = self._assert_v3_terminal(api, current["acceptance_sha256"])
        self.assertEqual(latest["reason"], "pr-merged")

    def test_manual_issue_close_remains_fail_closed_without_evidence(self) -> None:
        """AC-03: cierre manual sin merge verificable no adquiere pin ni snapshot."""
        api = FakeGitHub()
        self._activate_v3(api)
        api.issue_data["state"] = "closed"

        update_issue_state(api, 12, "closed")

        latest = latest_reservation(api.issue_comments(12))
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["version"], 1)
        self.assertEqual(latest["reason"], "issue-cerrado")
        self.assertFalse(latest["active"])
        self.assertNotIn("acceptance_sha256", latest)
        self.assertNotIn("task_marker_sha256", latest)
        self.assertIsNone(active_reservation(api, 12))

    def test_cross_identity_merged_pr_cannot_rebind_evidence(self) -> None:
        """AC-04: UUID, repo o base distintos no pueden prestar autoridad."""
        cases = (
            {"reservation_id": SESSION_B},
            {"head_repo": "fork/Factory"},
            {"base_ref": "develop"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                api = FakeGitHub()
                self._activate_v3(api)
                self._merged_pull(api, **overrides)
                api.issue_data["state"] = "closed"

                update_issue_state(api, 12, "closed")

                latest = latest_reservation(api.issue_comments(12))
                self.assertIsNotNone(latest)
                assert latest is not None
                self.assertEqual(latest["version"], 1)
                self.assertEqual(latest["reason"], "issue-cerrado")
                self.assertNotIn("acceptance_sha256", latest)
                self.assertNotIn("task_marker_sha256", latest)

    def test_terminal_visibility_keeps_latest_evidence_and_no_active_lease(self) -> None:
        """AC-05: el terminal visible conserva autoridad solo para el merge exacto."""
        api = FakeGitHub()
        current = self._activate_v3(api)
        self._merged_pull(api)
        api.issue_data["state"] = "closed"

        update_issue_state(api, 12, "closed")

        latest = self._assert_v3_terminal(api, current["acceptance_sha256"])
        self.assertEqual(latest["reservation_id"], SESSION_A)
        self.assertEqual(latest["branch"], "trabajo/issue-12")
        self.assertEqual(latest["owner"], "pl0n3r")


if __name__ == "__main__":
    unittest.main()

"""Factory #1133: regresiones sin red de autoridad y exclusividad V3."""
from __future__ import annotations

import json
import unittest
from uuid import UUID

from scripts.lease_authority_snapshot import (
    LeaseSnapshotError, audit_active_claims, require_unchanged,
)


def issue(number: int, status: str = "estado: bloqueado") -> dict:
    return {"number": number, "state": "open", "labels": [{"name": status}]}


def marker(number: int, active: bool = True, *, version: int = 3,
           uid: str = "2aee4583-1c5f-4be3-b6be-cdc1cc04b0d2") -> dict:
    result = {
        "version": version, "owner": "pl0n3r", "reservation_id": str(UUID(uid)),
        "branch": f"trabajo/issue-{number}", "active": active, "reason": "tomar",
    }
    if version in (2, 3):
        result["acceptance_sha256"] = "a" * 64
    if version == 3:
        result.update(task_marker_sha256="b" * 64,
                      task_paths=["scripts/coordinar_trabajo.py", "docs/"],
                      task_depends_on=[])
    return result


def comment(cid: int, value: dict | str, *, bot: bool = True) -> dict:
    payload = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
    return {"id": cid, "user": {"login": "github-actions[bot]" if bot else "intruso"},
            "body": f"<!-- condor-reserva {payload} -->"}


class LeaseAuthoritySnapshotTests(unittest.TestCase):
    def test_blocked_issue_with_active_v3_remains_exclusive(self):
        data = [issue(12), issue(13, "estado: disponible")]
        comments = {12: [comment(10, marker(12))], 13: []}
        audit = audit_active_claims(data, comments, complete=True)
        self.assertEqual(len(audit.active), 1)
        self.assertEqual(audit.active[0].issue, 12)
        self.assertIn("scripts/coordinar_trabajo.py", audit.active[0].paths)
        self.assertIn("docs/", audit.active[0].paths)
        self.assertRegex(audit.fingerprint, r"^[0-9a-f]{64}$")
        require_unchanged(audit, audit_active_claims(data, comments, complete=True))

    def test_inactive_or_absent_marker_never_fabricates_a_lease(self):
        data = [issue(12), issue(13), issue(14, "estado: disponible")]
        comments = {12: [comment(1, marker(12, active=False))],
                    13: [], 14: [comment(2, marker(14), bot=False)]}
        audit = audit_active_claims(data, comments, complete=True)
        self.assertEqual(audit.active, ())
        # Un label reserved sin evidencia no puede tratarse como libre.
        data[1] = issue(13, "estado: reservado")
        with self.assertRaisesRegex(LeaseSnapshotError, "estado_activo_sin_marker"):
            audit_active_claims(data, comments, complete=True)
        data[1] = issue(13)
        data[0] = issue(12, "estado: en revisión")
        with self.assertRaisesRegex(LeaseSnapshotError, "estado_activo_sin_marker"):
            audit_active_claims(data, comments, complete=True)

    def test_malformed_successor_or_legacy_active_fail_closed(self):
        data = [issue(12)]
        inactive = comment(1, marker(12, active=False))
        malformed = comment(2, '{"version":3,"active":true,}')
        with self.assertRaisesRegex(LeaseSnapshotError, "marker_invalido"):
            audit_active_claims(data, {12: [inactive, malformed]}, complete=True)
        # El prefijo del sucesor puede estar malformado antes del JSON.
        for prefix in ("<!--condor-reserva ", "<!--\tcondor-reserva ",
                       "<!--  CONDOR-RESERVA "):
            malformed_prefix = {"id": 3, "user": {"login": "github-actions[bot]"},
                                "body": prefix + json.dumps(marker(12)) + " -->"}
            with self.subTest(prefix=prefix), self.assertRaisesRegex(
                LeaseSnapshotError, "marker_ambiguo"
            ):
                audit_active_claims(data, {12: [inactive, malformed_prefix]}, complete=True)
        active_payload = json.dumps(marker(12), separators=(",", ":"))
        duplicate = active_payload.replace('"active":true', '"active":false,"active":true')
        with self.assertRaises(LeaseSnapshotError):
            audit_active_claims(data, {12: [comment(3, duplicate)]}, complete=True)
        with self.assertRaisesRegex(LeaseSnapshotError, "marker_activo_sin_claims_v3"):
            audit_active_claims(data, {12: [comment(4, marker(12, version=2))]}, complete=True)
        # Una liberación V2 legítima tampoco fabrica exclusividad.
        legacy_inactive = audit_active_claims(data, {12: [comment(4, marker(12, active=False, version=2))]}, complete=True)
        self.assertEqual(legacy_inactive.active, ())

    def test_missing_snapshot_duplicate_and_drift_fail_closed(self):
        data = [issue(12), issue(13, "estado: disponible")]
        comments = {12: [comment(1, marker(12))], 13: []}
        stable = audit_active_claims(data, comments, complete=True)
        # /tomar de otro actor aún no confirmado por el bot invalida el recheck.
        pending = {12: comments[12], 13: [
            {"id": 3, "user": {"login": "pl0n3r"}, "body": "/tomar"}
        ]}
        pending_audit = audit_active_claims(data, pending, complete=True)
        with self.assertRaisesRegex(LeaseSnapshotError, "inventario_cambio"):
            require_unchanged(stable, pending_audit)
        # Ediciones al contrato de aceptación o task marker también cuentan.
        body_changed = audit_active_claims(
            [{**data[0], "body": "factory-plan-task actualizado"}, data[1]],
            comments, complete=True,
        )
        with self.assertRaisesRegex(LeaseSnapshotError, "inventario_cambio"):
            require_unchanged(stable, body_changed)
        for bad_data, bad_comments, complete in [
            (data, {12: comments[12]}, True),
            (data, comments, False),
            ([issue(12), issue(12)], {12: comments[12]}, True),
            (data, {12: comments[12], 13: [], 99: []}, True),
            (data, {12: comments[12], True: []}, True),
            (data, {12: list(reversed([comment(1, marker(12)), comment(2, marker(12))])), 13: []}, True),
        ]:
            with self.assertRaises(LeaseSnapshotError):
                audit_active_claims(bad_data, bad_comments, complete=complete)
        with self.assertRaisesRegex(LeaseSnapshotError, "labels_estados_conflictivos"):
            audit_active_claims([{"number": 12, "state": "open", "labels": [
                {"name": "estado: bloqueado"}, {"name": "estado: reservado"}]}, data[1]], comments, complete=True)
        changed_label = audit_active_claims([issue(12, "estado: en revisión"), data[1]], comments, complete=True)
        with self.assertRaisesRegex(LeaseSnapshotError, "inventario_cambio"):
            require_unchanged(stable, changed_label)
        rotated = marker(12, uid="3fd88a50-e48a-4a16-9dc2-a9414eb27691")
        rotated_audit = audit_active_claims(data, {12: [comment(1, marker(12)), comment(2, rotated)], 13: []}, complete=True)
        with self.assertRaisesRegex(LeaseSnapshotError, "inventario_cambio"):
            require_unchanged(stable, rotated_audit)
        # El Inventario conserva los claims aunque se edite la etiqueta.
        self.assertEqual(rotated_audit.active[0].paths, stable.active[0].paths)


if __name__ == "__main__":
    unittest.main()

"""Factory #1133: regresiones sin red de autoridad y exclusividad V3."""
from __future__ import annotations

import json
import unittest
from uuid import UUID

from scripts.lease_authority_snapshot import (
    LeaseSnapshotError, audit_active_claims, require_unchanged,
)


def issue(number: int, status: str = "estado: bloqueado") -> dict:
    return {"number": number, "state": "open", "labels": [{"name": status}],
            "body": "", "updated_at": "2026-10-10T12:00:00Z"}


def marker(number: int, active: bool = True, *, version: int = 3,
           uid: str = "2aee4583-1c5f-4be3-b6be-cdc1cc04b0d2") -> dict:
    result = {
        "version": version, "owner": "pl0n3r", "reservation_id": str(UUID(uid)),
        "branch": f"trabajo/issue-{number}", "active": active, "reason": "tomar" if active else "liberar",
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
    return {"id": cid, "user": {
                "login": "github-actions[bot]" if bot else "intruso",
                "type": "Bot" if bot else "User"},
            "body": f"<!-- condor-reserva {payload} -->",
            "updated_at": "2026-10-10T12:00:00Z"}


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
            malformed_prefix = {"id": 3, "user": {"login": "github-actions[bot]", "type": "Bot"},
                                "updated_at": "2026-10-10T12:00:00Z",
                                "body": prefix + json.dumps(marker(12)) + " -->"}
            with self.subTest(prefix=prefix), self.assertRaisesRegex(
                LeaseSnapshotError, "marker_ambiguo"
            ):
                audit_active_claims(data, {12: [inactive, malformed_prefix]}, complete=True)
        dual = inactive["body"] + "\n" + comment(3, marker(12))["body"].replace("<!-- ", "<!--", 1)
        with self.assertRaisesRegex(LeaseSnapshotError, "marker_ambiguo"):
            audit_active_claims(data, {12: [comment(5, dual)]}, complete=True)
        active_payload = json.dumps(marker(12), separators=(",", ":"))
        duplicate = active_payload.replace('"active":true', '"active":false,"active":true')
        with self.assertRaises(LeaseSnapshotError):
            audit_active_claims(data, {12: [comment(3, duplicate)]}, complete=True)
        with self.assertRaisesRegex(LeaseSnapshotError, "marker_activo_sin_claims_v3"):
            audit_active_claims(data, {12: [comment(4, marker(12, version=2))]}, complete=True)
        # Una liberación V2 legítima tampoco fabrica exclusividad.
        legacy_inactive = audit_active_claims(data, {12: [comment(4, marker(12, active=False, version=2))]}, complete=True)
        self.assertEqual(legacy_inactive.active, ())

    def test_marker_history_cannot_rename_owner_or_claims(self):
        original = marker(12)
        for key, value in (("owner", "otro"), ("task_paths", ["scripts/otra.py"]),
                           ("task_marker_sha256", "c" * 64)):
            successor = {**original, key: value}
            with self.subTest(key=key), self.assertRaisesRegex(
                LeaseSnapshotError, "marker_continuidad"
            ):
                audit_active_claims([issue(12)], {12: [
                    comment(1, original), comment(2, successor)]}, complete=True)
        audit = audit_active_claims([issue(12)], {12: [
            comment(1, original), comment(2, {**original, "active": False, "reason": "liberar"})]}, complete=True)
        self.assertEqual(audit.active, ())

    def test_claim_paths_and_owner_must_be_canonical(self):
        data = [issue(12)]
        good = audit_active_claims(data, {12: [comment(1, marker(12))]}, complete=True)
        self.assertIn("docs/", good.active[0].paths)
        for path in ("scripts/*.py", "docs/file?.md", "docs/{name}.md",
                     "a" * 241, "src/../secret", "/etc/passwd", "src//file.py"):
            modified = marker(12)
            modified["task_paths"] = [path]
            with self.subTest(path=path), self.assertRaisesRegex(
                LeaseSnapshotError, "marker_claims"
            ):
                audit_active_claims(data, {12: [comment(1, modified)]}, complete=True)
        for owner in (" ", "-bad", "bad--owner", "a" * 40):
            modified = marker(12)
            modified["owner"] = owner
            with self.subTest(owner=owner), self.assertRaisesRegex(
                LeaseSnapshotError, "marker_identidad"
            ):
                audit_active_claims(data, {12: [comment(1, modified)]}, complete=True)

        for active, reason in ((False, "tomar"), (True, "liberar")):
            with self.assertRaisesRegex(LeaseSnapshotError, "marker_identidad"):
                audit_active_claims(data, {12: [comment(1, {**marker(12), "active": active, "reason": reason})]}, complete=True)

    def test_conflicting_active_leases_rejected(self):
        data = [issue(12), issue(13)]
        first = marker(12)
        other = marker(13, uid="3fd88a50-e48a-4a16-9dc2-a9414eb27691")
        for path in ("scripts/coordinar_trabajo.py", "docs/readme.md"):
            other["task_paths"] = [path]
            with self.subTest(path=path), self.assertRaisesRegex(
                LeaseSnapshotError, "claims_activas_solapadas"
            ):
                audit_active_claims(data, {12: [comment(1, first)], 13: [comment(2, other)]}, complete=True)
        other["task_paths"] = ["other/unrelated.py"]
        self.assertEqual(len(audit_active_claims(data, {
            12: [comment(1, first)], 13: [comment(2, other)]}, complete=True).active), 2)

    def test_historical_uuid_never_reused_across_issues(self):
        original = marker(12)
        released = {**original, "active": False, "reason": "liberar"}
        rotated = marker(12, uid="3fd88a50-e48a-4a16-9dc2-a9414eb27691")
        rotated["reason"] = "recuperacion-inactividad"
        reused = marker(13, uid=original["reservation_id"])
        reused["task_paths"] = ["other/independent.py"]
        data = [issue(12), issue(13)]
        history = [comment(1, original), comment(2, released), comment(3, rotated)]
        for second_issue_marker in (reused, {**reused, "active": False, "reason": "liberar"}):
            for order in (data, list(reversed(data))):
                with self.subTest(active=second_issue_marker["active"],
                                  order=[row["number"] for row in order]):
                    with self.assertRaisesRegex(LeaseSnapshotError, "uuid_duplicado"):
                        audit_active_claims(
                            order,
                            {12: history, 13: [comment(4, second_issue_marker)]},
                            complete=True,
                        )
        # La rotación dentro del mismo Issue es válida; otro Issue debe
        # utilizar un UUID completamente nuevo y claims disjuntos.
        distinct = marker(13, uid="954c02e6-3d27-4f1b-9be7-ef0bc7e3a294")
        distinct["task_paths"] = ["other/independent.py"]
        audit = audit_active_claims(
            data, {12: history, 13: [comment(4, distinct)]}, complete=True,
        )
        self.assertEqual({lease.issue for lease in audit.active}, {12, 13})
        self.assertEqual(
            {lease.reservation_id for lease in audit.active},
            {rotated["reservation_id"], distinct["reservation_id"]},
        )

    def test_missing_snapshot_duplicate_and_drift_fail_closed(self):
        data = [issue(12), issue(13, "estado: disponible")]
        comments = {12: [comment(1, marker(12))], 13: []}
        stable = audit_active_claims(data, comments, complete=True)
        # /tomar de otro actor aún no confirmado por el bot invalida el recheck.
        pending = {12: comments[12], 13: [
            {"id": 3, "user": {"login": "pl0n3r", "type": "User"},
             "body": "/tomar", "updated_at": "2026-10-10T12:00:00Z"}
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
            audit_active_claims([{**data[0], "labels": [
                {"name": "estado: bloqueado"}, {"name": "estado: reservado"}]}, data[1]], comments, complete=True)
        for missing in ("body", "updated_at"):
            incomplete = issue(12)
            incomplete.pop(missing)
            with self.assertRaisesRegex(LeaseSnapshotError, "issue_incompleto"):
                audit_active_claims([incomplete], {12: comments[12]}, complete=True)
        changed_label = audit_active_claims([issue(12, "estado: en revisión"), data[1]], comments, complete=True)
        with self.assertRaisesRegex(LeaseSnapshotError, "inventario_cambio"):
            require_unchanged(stable, changed_label)
        rotated = marker(12, uid="3fd88a50-e48a-4a16-9dc2-a9414eb27691")
        rotated["reason"] = "recuperacion-inactividad"
        rotated_audit = audit_active_claims(data, {12: [comment(1, marker(12)), comment(2, rotated)], 13: []}, complete=True)
        with self.assertRaisesRegex(LeaseSnapshotError, "inventario_cambio"):
            require_unchanged(stable, rotated_audit)
        # El Inventario conserva los claims aunque se edite la etiqueta.
        self.assertEqual(rotated_audit.active[0].paths, stable.active[0].paths)


    def test_cross_lease_unicode_and_file_directory_aliases_fail_closed(self):
        first = marker(12)
        second = marker(13, uid="3fd88a50-e48a-4a16-9dc2-a9414eb27691")
        for left, right in (("docs", "docs/"),
                            ("scripts/cafe\u0301.py", "scripts/café.py"),
                            ("DOCS/", "docs/file.md")):
            with self.subTest(left=left, right=right):
                first["task_paths"], second["task_paths"] = [left], [right]
                with self.assertRaisesRegex(LeaseSnapshotError, "claims_activas_solapadas"):
                    audit_active_claims([issue(12), issue(13)],
                                        {12: [comment(1, first)],
                                         13: [comment(2, second)]}, complete=True)
        first["task_paths"], second["task_paths"] = ["docs/a.py"], ["docs/b.py"]
        self.assertEqual(len(audit_active_claims([issue(12), issue(13)],
                         {12: [comment(1, first)], 13: [comment(2, second)]},
                         complete=True).active), 2)
        first["task_paths"] = ["docs", "docs/"]
        with self.assertRaisesRegex(LeaseSnapshotError, "marker_claims"):
            audit_active_claims([issue(12)], {12: [comment(1, first)]}, complete=True)

    def test_released_uuid_cannot_be_reactivated(self):
        first = marker(12)
        inactive = {**first, "active": False, "reason": "liberar"}
        with self.assertRaisesRegex(LeaseSnapshotError, "marker_reactivado"):
            audit_active_claims([issue(12)], {12: [comment(1, inactive),
                                                   comment(2, first)]}, complete=True)
        audit = audit_active_claims([issue(12)],
                                    {12: [comment(1, first), comment(2, inactive)]},
                                    complete=True)
        self.assertEqual(audit.active, ())
        self.assertEqual(len(audit_active_claims([issue(12)],
                         {12: [comment(1, first), comment(2, first)]},
                         complete=True).active), 1)

    def test_rotated_history_cannot_resurrect_an_older_uuid(self):
        # A released UUID must not be reintroduced after a different UUID
        # becomes current, even if all immutable fields still match.
        original = marker(12)
        released = {**original, "active": False, "reason": "liberar"}
        successor = marker(
            12, uid="3fd88a50-e48a-4a16-9dc2-a9414eb27691"
        )
        successor["reason"] = "recuperacion-inactividad"
        resurrected = {**original, "reason": "transferir"}
        for history in (
            [original, released, successor, resurrected],
            [original, successor, resurrected],
        ):
            with self.subTest(history=[m["reservation_id"] for m in history]):
                with self.assertRaisesRegex(LeaseSnapshotError, "marker_reactivado"):
                    audit_active_claims(
                        [issue(12)],
                        {12: [comment(n, value) for n, value in enumerate(history, 1)]},
                        complete=True,
                    )
        good = audit_active_claims(
            [issue(12)],
            {12: [comment(1, original), comment(2, released),
                  comment(3, successor)]},
            complete=True,
        )
        self.assertEqual(good.active[0].reservation_id, successor["reservation_id"])

    def test_cross_uuid_rotation_preserves_authorized_claims(self):
        first = marker(12)
        second = marker(12, uid="3fd88a50-e48a-4a16-9dc2-a9414eb27691")
        second["reason"] = "recuperacion-inactividad"

        def audit(*history):
            rows = {12: [comment(n, v) for n, v in enumerate(history, 1)]}
            return audit_active_claims([issue(12)], rows, complete=True)

        for valid in (second, {**second, "owner": "nuevo-dueno"},
                      {**second, "reason": "transferir"}):
            self.assertEqual(len(audit(first, valid).active), 1)
        for bad in ({**second, "reason": "transferir", "owner": "nuevo-dueno"},
                    {**second, "task_paths": ["scripts/other.py"]},
                    {**second, "acceptance_sha256": "c" * 64},
                    {**second, "active": False, "reason": "liberar"}, {**second, "reason": "tomar"}):
            with self.subTest(invalid=bad), self.assertRaisesRegex(
                    LeaseSnapshotError, "marker_rotacion"):
                audit(first, bad)

        released = {**first, "active": False, "reason": "liberar"}
        for change in ({"task_paths": ["secrets/"]},
                       {"task_marker_sha256": "d" * 64},
                       {"acceptance_sha256": "e" * 64}, {"owner": "otro"}):
            with self.subTest(released_rotation=change), self.assertRaisesRegex(
                    LeaseSnapshotError, "marker_rotacion"):
                audit(first, released, {**second, **change, "reason": "tomar"})
        with self.assertRaisesRegex(LeaseSnapshotError, "marker_rotacion"):
            audit(first, released, {**second, "active": False, "reason": "liberar"})
        self.assertEqual(len(audit(first, released, second).active), 1)

    def test_missing_or_invalid_comment_update_timestamp_fails_closed(self):
        original = comment(1, marker(12))
        for stamp in (None, "", "ayer", "2026-99-10T12:00:00Z",
                      "2026-10-10T12:00:00", "2026-10-10T12:00:00+00:00"):
            with self.subTest(stamp=stamp):
                bad = dict(original)
                if stamp is None:
                    bad.pop("updated_at")
                else:
                    bad["updated_at"] = stamp
                with self.assertRaisesRegex(LeaseSnapshotError, "comentario_fecha_invalida"):
                    audit_active_claims([issue(12)], {12: [bad]}, complete=True)
        before = audit_active_claims([issue(12)], {12: [original]}, complete=True)
        changed = {**original, "updated_at": "2026-10-10T12:00:01Z"}
        after = audit_active_claims([issue(12)], {12: [changed]}, complete=True)
        with self.assertRaisesRegex(LeaseSnapshotError, "inventario_cambio"):
            require_unchanged(before, after)

    def test_state_label_casefold_aliases_fail_closed(self):
        conflicting = issue(12, "estado: reservado")
        conflicting["labels"].append({"name": "ESTADO: bloqueado"})
        with self.assertRaisesRegex(LeaseSnapshotError, "labels_estados_conflictivos"):
            audit_active_claims([conflicting], {12: [comment(1, marker(12))]}, complete=True)
        duplicate = issue(12, "estado: reservado")
        duplicate["labels"].append({"name": "ESTADO: RESERVADO"})
        with self.assertRaisesRegex(LeaseSnapshotError, "labels_invalidas"):
            audit_active_claims([duplicate], {12: [comment(1, marker(12))]}, complete=True)

    def test_active_status_casefold_alias_requires_live_bot_marker(self):
        # A single uppercase status must not silently become "unreserved".
        for status in ("ESTADO: RESERVADO", "ESTADO: EN REVISIÓN",
                       "STATUS: RESERVED", "STATUS: IN REVIEW"):
            with self.subTest(status=status):
                without_authority = issue(12, status)
                with self.assertRaisesRegex(LeaseSnapshotError, "estado_activo_sin_marker"):
                    audit_active_claims([without_authority], {12: []}, complete=True)
                with self.assertRaisesRegex(LeaseSnapshotError, "estado_activo_sin_marker"):
                    audit_active_claims(
                        [without_authority],
                        {12: [comment(1, marker(12, active=False))]},
                        complete=True,
                    )
                # The same status with a genuine marker retains its claims.
                audited = audit_active_claims(
                    [without_authority],
                    {12: [comment(1, marker(12))]},
                    complete=True,
                )
                self.assertEqual(len(audited.active), 1)
                self.assertEqual(audited.active[0].issue, 12)

    def test_uuid_identity_must_match_coordinator_versions_and_variant(self):
        self.assertEqual(len(audit_active_claims(
            [issue(12)], {12: [comment(1, marker(12))]}, complete=True).active), 1)
        for uid in ("00000000-0000-0000-0000-000000000000",
                    "3945eeb7-1df8-7439-b196-98897eb3a71a",
                    "3945eeb7-1df8-4439-7196-98897eb3a71a"):
            with self.subTest(uid=uid), self.assertRaisesRegex(
                    LeaseSnapshotError, "marker_uuid"):
                audit_active_claims([issue(12)],
                    {12: [comment(1, marker(12, uid=uid))]}, complete=True)

    def test_reservation_cannot_depend_on_its_own_issue(self):
        bad = marker(12)
        bad["task_depends_on"] = [12]
        with self.assertRaisesRegex(LeaseSnapshotError, "marker_claims"):
            audit_active_claims([issue(12)], {12: [comment(1, bad)]}, complete=True)
        good = marker(12)
        good["task_depends_on"] = [11]
        self.assertEqual(len(audit_active_claims(
            [issue(12)], {12: [comment(1, good)]}, complete=True).active), 1)

    def test_marker_author_requires_bot_actor_type(self):
        genuine = comment(1, marker(12))
        self.assertEqual(len(audit_active_claims(
            [issue(12)], {12: [genuine]}, complete=True).active), 1)
        for kind in ("User", "Organization", None):
            with self.subTest(kind=kind):
                fake = {**genuine, "user": {**genuine["user"], "type": kind}}
                with self.assertRaisesRegex(LeaseSnapshotError, "comentario_actor_invalido"):
                    audit_active_claims([issue(12)], {12: [fake]}, complete=True)
        missing = {**genuine, "user": {"login": "github-actions[bot]"}}
        with self.assertRaisesRegex(LeaseSnapshotError, "comentario_actor_invalido"):
            audit_active_claims([issue(12)], {12: [missing]}, complete=True)


if __name__ == "__main__":
    unittest.main()

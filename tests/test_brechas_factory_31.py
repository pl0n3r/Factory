"""Factory #1649: contratos sintéticos para 16 brechas, sin efecto remoto."""
from __future__ import annotations

import copy
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import stat
import unittest
import zipfile

from scripts.sync_label_colors import load_catalogs, plan_repository, assert_safe_plan, SyncError
from scripts.lease_phase_a_artifact_qa import inspect_artifact, ArtifactQAError
from scripts.lease_auto_release_run import evaluate_phase_a_candidate

ROOT = Path(__file__).resolve().parents[1]
LABEL = "docs/label-color-sync.md"
LEASE = "docs/lease-phase-a-artifact-qa.md"
AUTO = "docs/liberacion-automatica-de-reservas.md"
OUT = "docs/lista-salida-produccion.md"
MATRIX = "docs/matriz-cobertura.md"
UNKNOWN = "UNKNOWN"
IDS = (
    f"{LABEL}:L9-U1",
    f"{LEASE}:L11-U1", f"{LEASE}:L13-U1", f"{LEASE}:L15-U1",
    f"{LEASE}:L3-U1", f"{LEASE}:L3-U2", f"{LEASE}:L3-U3",
    f"{LEASE}:L3-U4", f"{LEASE}:L9-U1",
    f"{AUTO}:B01", f"{AUTO}:B02", f"{AUTO}:B04",
    f"{OUT}:L7-U1", f"{OUT}:L7-U2", f"{OUT}:L79-U1", f"{OUT}:L8-U1",
)
LOCAL = frozenset((
    f"{LABEL}:L9-U1", f"{LEASE}:L3-U2", f"{LEASE}:L3-U3",
    f"{LEASE}:L3-U4", f"{LEASE}:L13-U1", f"{LEASE}:L15-U1",
))
GAPS = {
    f"{LEASE}:L11-U1": "UNKNOWN: recibos autenticados y QA individual externos ausentes",
    f"{LEASE}:L3-U1": "UNKNOWN: ZIP y JSON locales no autentican su origen",
    f"{LEASE}:L9-U1": "UNKNOWN: sin artefacto ID, SHA/run ni actividad externa observada",
    f"{AUTO}:B01": "UNKNOWN: GET-only en consumidores no comprobado",
    f"{AUTO}:B02": "UNKNOWN: el veto no prueba ausencia de pushes",
    f"{AUTO}:B04": "UNKNOWN: faltan 24h, 100 ciclos reales y QA independiente",
    f"{OUT}:L7-U1": "UNKNOWN: LISTO no verificado individualmente en GitHub",
    f"{OUT}:L7-U2": "UNKNOWN: épica no equivale a entrega",
    f"{OUT}:L79-U1": "UNKNOWN: soporte y backup reales no verificados",
    f"{OUT}:L8-U1": "UNKNOWN: fuentes y puertas externas no conciliadas",
}

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")

def rows(raw):
    if not isinstance(raw, str):
        raise ValueError("matriz ilegible")
    result = {}
    for line in raw.splitlines():
        cells = tuple(c.strip() for c in line.strip().strip("|").split("|"))
        key = cells[0].strip(chr(96))
        if key not in IDS:
            continue
        if key in result or len(cells) != 5 or not all(cells[:4]) or cells[2] != "NO_VERIFICABLE":
            raise ValueError("fila ambigua: " + key)
        result[key] = cells
    if set(result) != set(IDS):
        raise ValueError("unidades incompletas")
    return result

def assess(raw, evidence):
    verdicts = {unit: UNKNOWN for unit in IDS}
    try:
        rows(raw)
    except ValueError:
        return verdicts
    if type(evidence) is not dict or set(evidence) != set(IDS):
        return verdicts
    if any(type(value) is not bool for value in evidence.values()):
        return verdicts
    for unit in LOCAL:
        if evidence[unit]:
            verdicts[unit] = "OFFLINE_VERIFIED"
    return verdicts

def artifact():
    meta = {"id": 415, "repository": "pl0n3r/Factory", "head_sha": "a" * 40,
            "event": "schedule", "status": "completed", "conclusion": "success"}
    row = {"issue": 21, "state": "read_only", "action": "wait",
           "reason": "activity_window", "activity_age_minutes": 8,
           "activity_source": "issue_comment", "release_authorized": False,
           "lock_verified": False, "cas_verified": False, "mutations": 0}
    manifest = {"schema_version": 1, "repository": meta["repository"],
                "head_sha": meta["head_sha"], "run_id": str(meta["id"]),
                "status": "candidate_terminal", "terminal_certified": False,
                "release_authorized": False, "mutations": 0,
                "valid_observations": 1, "unknown_observations": 0, "issues": [row]}
    raw = json.dumps(manifest, sort_keys=True).encode("utf-8")
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as out:
        item = zipfile.ZipInfo("lease-audit-evidence.json")
        item.compress_type = zipfile.ZIP_DEFLATED
        item.external_attr = (stat.S_IFREG | 0o644) << 16
        out.writestr(item, raw)
    return data.getvalue(), raw, meta

def candidates():
    manifests, receipts = [], []
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    for n in range(100):
        run = 10001 + n
        manifests.append({
            "schema_version": 1, "repository": "pl0n3r/Factory", "head_sha": "a" * 40,
            "run_id": str(run), "status": "candidate_terminal", "terminal_certified": False,
            "release_authorized": False, "mutations": 0,
            "valid_observations": 1, "unknown_observations": 0,
            "issues": [{"issue": 21, "state": "read_only", "action": "wait",
                        "reason": "activity_window", "activity_age_minutes": 7,
                        "activity_source": "workflow_push", "release_authorized": False,
                        "lock_verified": False, "cas_verified": False, "mutations": 0}],
        })
        receipts.append({
            "id": run, "repository": "pl0n3r/Factory", "head_sha": "a" * 40,
            "event": "schedule", "status": "completed", "conclusion": "success",
            "artifact_attested": True,  # Solo fixture inventado, no prueba GitHub.
            "completed_at": (start + timedelta(minutes=15*n)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return manifests, receipts

class BrechasFactory31Tests(unittest.TestCase):
    def setUp(self):
        self.matrix = read(MATRIX)

    def test_contrato_principal(self):
        table = rows(self.matrix)
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        for key, cells in table.items():
            with self.subTest(unit=key):
                self.assertEqual(cells[2], "NO_VERIFICABLE")
                self.assertTrue(cells[3])
                self.assertTrue((ROOT / key.split(":")[0]).is_file())
        catalogs = load_catalogs(ROOT)
        operations = plan_repository("pl0n3r/Factory", [
            {"name": "prioridad: media", "color": "FFFFFF"},
            {"name": "custom: untouched", "color": "ABCDEF"},
        ], catalogs)
        self.assertEqual(operations, [{
            "action": "update_color", "repository": "pl0n3r/Factory",
            "label": "prioridad: media", "color_before": "FFFFFF",
            "color_after": "FBCA04",
        }])
        assert_safe_plan(operations)
        self.assertNotIn("custom: untouched", str(operations))
        zipped, raw, meta = artifact()
        inspected = inspect_artifact(zipped, meta)
        self.assertEqual(inspected["status"], "MATCHED_CANDIDATE")
        self.assertEqual(inspected["sha256_json"], hashlib.sha256(raw).hexdigest())
        self.assertEqual((inspected["run_id"], inspected["head_sha"]),
                         (meta["id"], meta["head_sha"]))
        self.assertEqual(inspected["mutations"], 0)
        for field in ("artifact_attested", "terminal_certified", "release_authorized"):
            self.assertIs(inspected[field], False)
        code = read("scripts/lease_phase_a_artifact_qa.py")
        for forbidden in ("urllib", "requests", "urlopen", "subprocess", "gh api",
                          "create_issue(", "release_lease(", "os.environ"):
            self.assertNotIn(forbidden, code)
        manifests, receipts = candidates()
        summary = evaluate_phase_a_candidate(manifests, receipts, [],
                                            repository="pl0n3r/Factory")
        self.assertEqual(summary.status, "candidate_only")
        self.assertEqual(summary.valid_cycles, 100)
        self.assertGreaterEqual(summary.observed_minutes, 1440)
        self.assertIs(summary.release_authorized, False)
        for phrase in ("24 horas", "100 ciclos", "QA individual", "No autoriza Fase B"):
            self.assertIn(phrase, read(LEASE))
        self.assertIn("solo genera operaciones", read(LABEL))
        self.assertIn("0 reservas liberadas", read(AUTO))
        self.assertIn("ci_veto_only", read(AUTO))
        for phrase in ("LISTO", "SIN_COBERTURA", "DEL_DUEÑO", "#305/#304/#1082"):
            self.assertIn(phrase, read(OUT))
        verdicts = assess(self.matrix, {unit: unit in LOCAL for unit in IDS})
        self.assertEqual(set(verdicts), set(IDS))
        self.assertEqual({k for k, v in verdicts.items() if v == "OFFLINE_VERIFIED"}, LOCAL)
        self.assertEqual({k for k, v in verdicts.items() if v == UNKNOWN}, set(GAPS))

    def test_falla_cerrado(self):
        first = next(line for line in self.matrix.splitlines()
                     if chr(96) + IDS[0] + chr(96) in line)
        for bad in (None, "", self.matrix.replace(first, ""),
                    self.matrix + "\n" + first,
                    self.matrix.replace(first, first.replace("NO_VERIFICABLE", "LISTO"))):
            with self.subTest(bad=str(bad)[:30]), self.assertRaises(ValueError):
                rows(bad)
        self.assertEqual(set(assess(None, {x: True for x in IDS}).values()), {UNKNOWN})
        self.assertEqual(set(assess(self.matrix, {IDS[0]: True}).values()), {UNKNOWN})
        self.assertEqual(set(assess(self.matrix, {x: 1 for x in IDS}).values()), {UNKNOWN})
        with self.assertRaises(SyncError):
            plan_repository("pl0n3r/Factory", [
                {"name": "prioridad: media", "color": "FFFFFF"},
                {"name": "prioridad: media", "color": "000000"},
            ], load_catalogs(ROOT))
        zipped, _, meta = artifact()
        for invalid in ({**meta, "event": "workflow_dispatch"},
                        {**meta, "status": "pending"},
                        {**meta, "conclusion": "failure"},
                        {**meta, "head_sha": "b"*40}):
            with self.subTest(invalid=invalid), self.assertRaises(ArtifactQAError):
                inspect_artifact(zipped, invalid)
        for invalid_zip in (b"", b"notzip"):
            with self.assertRaises(ArtifactQAError):
                inspect_artifact(invalid_zip, meta)

    def test_sin_datos_reales(self):
        zipped, raw, meta = artifact()
        self.assertEqual(meta["head_sha"], "a"*40)
        self.assertEqual(meta["id"], 415)
        self.assertLess(len(zipped), 65536)
        manifest = json.loads(raw)
        self.assertEqual(manifest["issues"][0]["issue"], 21)
        self.assertEqual(manifest["issues"][0]["mutations"], 0)
        for key in ("password", "token", "secret", "email", "phone"):
            self.assertNotIn(key, meta)
            self.assertNotIn(key, manifest)
        manifests, receipts = candidates()
        self.assertEqual(len({receipt["id"] for receipt in receipts}), 100)
        self.assertTrue(all(m["mutations"] == 0 and m["release_authorized"] is False
                            for m in manifests))

    def test_estados_unknown_explicitos(self):
        verdicts = assess(self.matrix, {unit: True for unit in IDS})
        for unit, reason in GAPS.items():
            with self.subTest(unit=unit):
                self.assertEqual(verdicts[unit], UNKNOWN)
                self.assertTrue(reason.startswith("UNKNOWN:"))
        manifests, receipts = candidates()
        self.assertNotEqual(evaluate_phase_a_candidate(
            manifests[:99], receipts[:99], [], repository="pl0n3r/Factory").status,
            "candidate_only")
        cramped = copy.deepcopy(receipts)
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        for n, rec in enumerate(cramped):
            rec["completed_at"] = (start + timedelta(minutes=10*n)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertNotEqual(evaluate_phase_a_candidate(
            manifests, cramped, [], repository="pl0n3r/Factory").status,
            "candidate_only")
        bad = copy.deepcopy(manifests)
        bad[0]["unknown_observations"] = 1
        self.assertNotEqual(evaluate_phase_a_candidate(
            bad, receipts, [], repository="pl0n3r/Factory").status,
            "candidate_only")
        untrusted = copy.deepcopy(receipts)
        untrusted[0]["artifact_attested"] = False
        self.assertNotEqual(evaluate_phase_a_candidate(
            manifests, untrusted, [], repository="pl0n3r/Factory").status,
            "candidate_only")
        self.assertEqual(set(assess(self.matrix, None).values()), {UNKNOWN})

if __name__ == "__main__":
    unittest.main()

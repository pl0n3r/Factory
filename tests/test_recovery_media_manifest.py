"""Executable acceptance for Factory #1090: pure media backup manifest."""
import unittest
from collections.abc import Mapping
from recovery.media_manifest import MediaManifestError, plan_media_backup

SHA1 = "1" * 64
SHA2 = "2" * 64


def asset(name="asset_A", digest=SHA1):
    return {"asset_id": name, "object_key": f"objects/{name}.bin", "sha256": digest,
            "byte_size": 18, "metadata_key": f"metadata/{name}.json",
            "preview_keys": [f"previews/{name}.jpg"]}


class RecoveryMediaManifestTests(unittest.TestCase):
    def test_immutable_blob_is_not_reuploaded(self):
        item = asset()
        evidence = [{"project": "grindflow", "object_key": item["object_key"],
                     "sha256": SHA1, "evidence_ref": "verified_backup_001", "immutable": True}]
        first = plan_media_backup("grindflow", [item])
        self.assertEqual(first["pending_uploads"][0]["object_key"], item["object_key"])
        second = plan_media_backup("grindflow", [item], evidence)
        self.assertEqual(second["pending_uploads"], [])
        self.assertFalse(second["external_io_performed"])
        # Two assets may refer to the same immutable object; it is copied once.
        reused = asset("asset_B")
        reused["object_key"] = item["object_key"]
        once = plan_media_backup("grindflow", [item, reused])
        self.assertEqual(len(once["entries"]), 2)
        self.assertEqual(len(once["pending_uploads"]), 1)
        reused["byte_size"] = 19
        with self.assertRaises(MediaManifestError):
            plan_media_backup("grindflow", [item, reused])
        evidence[0]["sha256"] = SHA2
        with self.assertRaises(MediaManifestError):
            plan_media_backup("grindflow", [item], evidence)
        evidence[0]["sha256"] = SHA1
        evidence[0]["immutable"] = False
        with self.assertRaises(MediaManifestError):
            plan_media_backup("grindflow", [item], evidence)

    def test_manifest_reconstructs_original_metadata_and_object_keys(self):
        result = plan_media_backup("grindflow", [asset("asset_B"), asset("asset_A")])
        self.assertEqual([x["asset_id"] for x in result["entries"]], ["asset_A", "asset_B"])
        self.assertEqual(result["restore_plan"][0], {
            "asset_id": "asset_A", "original_object_key": "objects/asset_A.bin",
            "metadata_object_key": "metadata/asset_A.json",
            "regenerate_previews": ["previews/asset_A.jpg"]})
        with self.assertRaises(MediaManifestError):
            plan_media_backup("grindflow", [asset(), asset()])
        with self.assertRaises(MediaManifestError):
            plan_media_backup("grindflow", [asset()], [{"project": "condor",
                "object_key": "objects/asset_A.bin", "sha256": SHA1,
                "evidence_ref": "otherproject", "immutable": True}])
        hostile = asset(); hostile["object_key"] = "../../private"
        with self.assertRaises(MediaManifestError):
            plan_media_backup("grindflow", [hostile])

        class MaliciousMapping(Mapping):
            def __len__(self):
                return 6
            def __iter__(self):
                raise RuntimeError("sensitive-mapping-sentinel")
            def __getitem__(self, key):
                raise RuntimeError("sensitive-mapping-sentinel")

        for assets, verified in (([MaliciousMapping()], []),
                                 ([asset()], [MaliciousMapping()])):
            with self.subTest(source="assets" if not verified else "verified"):
                with self.assertRaises(MediaManifestError) as caught:
                    plan_media_backup("grindflow", assets, verified)
                self.assertNotIn("sensitive-mapping-sentinel", str(caught.exception))

    def test_unrelated_evidence_does_not_inflate_verified_copy_count(self):
        """Coverage counts only planned immutable objects, not orphan proofs."""
        evidence = [{
            "project": "grindflow", "object_key": "objects/orphan.bin",
            "sha256": SHA1, "evidence_ref": "verified_orphan_001",
            "immutable": True,
        }]
        empty = plan_media_backup("grindflow", [], evidence)
        self.assertEqual(empty["verified_copy_count"], 0)
        pending = plan_media_backup("grindflow", [asset()], evidence)
        self.assertEqual(pending["verified_copy_count"], 0)
        self.assertEqual(len(pending["pending_uploads"]), 1)
        matched = [{**evidence[0], "object_key": asset()["object_key"]}]
        verified = plan_media_backup("grindflow", [asset()], evidence + matched)
        self.assertEqual(verified["verified_copy_count"], 1)
        self.assertEqual(verified["pending_uploads"], [])

    def test_metadata_key_must_not_alias_any_original_blob(self):
        """A restore plan cannot assign one key to incompatible blob roles."""
        first = asset("asset_A")
        second = asset("asset_B", digest=SHA2)
        first["metadata_key"] = second["object_key"]
        with self.assertRaises(MediaManifestError) as caught:
            plan_media_backup("grindflow", [first, second])
        self.assertEqual(str(caught.exception), "Conflicting original and metadata keys.")
        # Also reject an asset whose own metadata key aliases its original.
        second["metadata_key"] = second["object_key"]
        with self.assertRaises(MediaManifestError):
            plan_media_backup("grindflow", [second])
        # Distinct namespaces remain accepted; no metadata upload is inferred.
        first["metadata_key"] = "metadata/asset_A.json"
        second["metadata_key"] = "metadata/asset_B.json"
        plan = plan_media_backup("grindflow", [first, second])
        self.assertEqual(len(plan["pending_uploads"]), 2)
        self.assertFalse(plan["external_io_performed"])

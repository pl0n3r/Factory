"""Executable acceptance for Factory #1090: pure media backup manifest."""
import unittest
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

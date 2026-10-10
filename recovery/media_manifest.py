"""Pure, fail-closed media backup planning. No I/O or backup claims."""
from __future__ import annotations

import re

_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_KEY = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._/-]{0,239}\Z")


class MediaManifestError(ValueError):
    """Invalid, incomplete or conflicting media backup metadata."""


def _identity(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _object_key(value: object) -> bool:
    return (isinstance(value, str) and _KEY.fullmatch(value) is not None
            and all(segment not in ("", ".", "..") for segment in value.split("/")))


def plan_media_backup(project: str, assets: list[dict], verified: list[dict] | None = None) -> dict:
    """Produce immutable asset mapping and pending copies; never perform uploads.

    Verified evidence must come from an independent verifier. A manifest alone
    must never be treated as proof that a remote copy exists.
    """
    if not _identity(project) or not isinstance(assets, list) or len(assets) > 1000:
        raise MediaManifestError("Invalid project or asset list.")
    if verified is None:
        verified = []
    if not isinstance(verified, list) or len(verified) > 1000:
        raise MediaManifestError("Invalid verification evidence.")
    proven = {}
    for row in verified:
        if ( type(row) is not dict or any(type(key) is not str for key in row) or set(row) != {"project", "object_key", "sha256", "evidence_ref", "immutable"}
                or row["project"] != project or not _object_key(row["object_key"])
                or not isinstance(row["sha256"], str) or _SHA.fullmatch(row["sha256"]) is None
                or not _identity(row["evidence_ref"]) or row["immutable"] is not True):
            raise MediaManifestError("Unverifiable remote object evidence.")
        previous = proven.setdefault(row["object_key"], row["sha256"])
        if previous != row["sha256"]:
            raise MediaManifestError("Conflicting immutable object evidence.")

    entries, upload, restore = [], [], []
    seen_assets, keys, upload_keys = set(), {}, set()
    for asset in assets:
        if (type(asset) is not dict or any(type(key) is not str for key in asset) or set(asset) != {
            "asset_id", "object_key", "sha256", "byte_size", "metadata_key", "preview_keys"
        }):
            raise MediaManifestError("Invalid media asset shape.")
        ident, key, digest = asset["asset_id"], asset["object_key"], asset["sha256"]
        if (not _identity(ident) or not _object_key(key)
                or not isinstance(digest, str) or _SHA.fullmatch(digest) is None
                or type(asset["byte_size"]) is not int or asset["byte_size"] < 0
                or not _object_key(asset["metadata_key"])
                or not isinstance(asset["preview_keys"], list) or len(asset["preview_keys"]) > 32
                or any(not _object_key(p) for p in asset["preview_keys"])):
            raise MediaManifestError("Invalid media asset values.")
        if ident in seen_assets or (key in keys and keys[key] != (digest, asset["byte_size"])):
            raise MediaManifestError("Duplicate asset or conflicting immutable key.")
        if key in proven and proven[key] != digest:
            raise MediaManifestError("Immutable backup checksum drift.")
        seen_assets.add(ident)
        keys[key] = (digest, asset["byte_size"])
        row = {"asset_id": ident, "object_key": key, "sha256": digest,
               "byte_size": asset["byte_size"], "metadata_key": asset["metadata_key"],
               "preview_keys": sorted(set(asset["preview_keys"]))}
        entries.append(row)
        restore.append({"asset_id": ident, "original_object_key": key,
                        "metadata_object_key": row["metadata_key"],
                        "regenerate_previews": row["preview_keys"]})
        if key not in proven and key not in upload_keys:
            upload_keys.add(key)
            upload.append({"object_key": key, "sha256": digest, "byte_size": row["byte_size"]})
    # All keys share one remote namespace. Metadata must not alias
    # immutable originals, including originals declared by later assets.
    metadata_keys = {asset["metadata_key"] for asset in assets}
    if metadata_keys.intersection(keys):
        raise MediaManifestError("Conflicting original and metadata keys.")
    return {"version": 1, "project": project,
            "entries": sorted(entries, key=lambda item: item["asset_id"]),
            "pending_uploads": sorted(upload, key=lambda item: item["object_key"]),
            "restore_plan": sorted(restore, key=lambda item: item["asset_id"]),
            "verified_copy_count": len(set(proven) & set(keys)), "external_io_performed": False}

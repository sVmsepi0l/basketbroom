"""Portable safety checks for native-roof receipt continuity and destination scope."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hlck_roof", ROOT / "Tools/stage_hlck_pyramid_net.py")
roof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roof)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.content = self.root / "Mod/Basketbroom/Content"
        self.patches = [patch.object(roof, "ROOT", self.root), patch.object(roof, "CONTENT", self.content),
                        patch.object(roof, "SUCCESS", self.root / ".local/hlck/pyramid-net-success.json")]
        for item in self.patches:
            item.start()
        self.map = roof.asset_file(roof.MAPS[1], ".umap")
        self.map.parent.mkdir(parents=True)
        self.map.write_bytes(b"original native dungeon and anchors")
        self.original = roof.digest(self.map)

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def amendment(self, stamp="one", status="staged", preserve=True):
        previous = json.loads(roof.SUCCESS.read_text()) if roof.SUCCESS.is_file() else None
        directory = self.root / ".local/hlck/pyramid-net-stage" / stamp
        backup = directory / "backups/Maps/Basketbroom_DungeonMap.umap"
        backup.parent.mkdir(parents=True)
        backup.write_bytes(self.map.read_bytes())
        before = roof.digest(self.map)
        self.map.write_bytes(self.map.read_bytes() + stamp.encode())
        receipt = directory / "result.json"
        result = {"status": status, "preservation_verified": preserve, "previous_success": previous,
                  "maps": [{"path": roof.MAPS[1], "sha256_before": before, "sha256_after": roof.digest(self.map),
                            "backup": str(backup), "unrelated_actors_preserved": True}]}
        roof.write(receipt, result)
        roof.write(roof.SUCCESS, {"report": str(receipt), "sha256": roof.digest(receipt)})
        return receipt, backup

    def test_exact_allowlist_is_seven_packages(self):
        self.assertEqual(len(roof.allowed_files()), 7)
        self.assertTrue(all(self.content.resolve() in path.parents for path in roof.allowed_files()))

    def test_unrelated_destinations_and_wrong_extension_rejected(self):
        for path, suffix in (("/Game/Levels/Overland", ".umap"), ("/Basketbroom/ModEdits", ".sql"),
                             (roof.MAPS[1], ".uasset"), ("/Basketbroom/Maps/../Secrets", ".umap")):
            with self.subTest(path=path), self.assertRaises(ValueError):
                roof.asset_file(path, suffix)

    def test_no_receipt_is_not_a_pass(self):
        self.assertIsNone(roof.verified_amendment(roof.MAPS[1], self.original))

    def test_exact_saved_amendment_validates(self):
        self.amendment()
        self.assertEqual(roof.verified_amendment(roof.MAPS[1], self.original)["verified_amendments"], 1)

    def test_repeated_amendments_reach_original_anchor_receipt(self):
        self.amendment()
        self.amendment("two")
        self.assertEqual(roof.verified_amendment(roof.MAPS[1], self.original)["verified_amendments"], 2)

    def test_changed_map_rejected(self):
        self.amendment()
        self.map.write_bytes(b"unrelated modified map")
        with self.assertRaises(RuntimeError):
            roof.verified_amendment(roof.MAPS[1], self.original)

    def test_changed_backup_rejected(self):
        unused, backup = self.amendment()
        backup.write_bytes(b"not the native source map")
        with self.assertRaises(RuntimeError):
            roof.verified_amendment(roof.MAPS[1], self.original)

    def test_changed_receipt_rejected(self):
        receipt, unused = self.amendment()
        receipt.write_text(receipt.read_text() + " ")
        with self.assertRaises(RuntimeError):
            roof.verified_amendment(roof.MAPS[1], self.original)

    def test_failed_stage_is_not_evidence(self):
        self.amendment(status="failed")
        with self.assertRaises(RuntimeError):
            roof.verified_amendment(roof.MAPS[1], self.original)

    def test_dry_run_is_not_evidence(self):
        self.amendment(status="ready")
        with self.assertRaises(RuntimeError):
            roof.verified_amendment(roof.MAPS[1], self.original)

    def test_missing_preservation_proof_rejected(self):
        self.amendment(preserve=False)
        with self.assertRaises(RuntimeError):
            roof.verified_amendment(roof.MAPS[1], self.original)

    def test_unrelated_original_hash_is_not_authorized(self):
        self.amendment()
        self.assertIsNone(roof.verified_amendment(roof.MAPS[1], "0" * 64))

    def test_wrong_map_is_not_authorized(self):
        self.amendment()
        self.assertIsNone(roof.verified_amendment("/Game/Levels/Overland", self.original))


if __name__ == "__main__":
    unittest.main()

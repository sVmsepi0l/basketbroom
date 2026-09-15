"""Portable refusal checks for the unsaved-only native roof recovery helper."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("roof_recovery", ROOT / "Tools/recover_hlck_roof_attempt.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
roof = recovery.module("roof_recovery_test_definitions", "Tools/stage_hlck_pyramid_net.py")


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.content = self.root / "Mod/Basketbroom/Content"
        for target in (recovery, roof):
            for name, value in (("ROOT", self.root), ("CONTENT", self.content)):
                item = patch.object(target, name, value)
                item.start()
                self.addCleanup(item.stop)
        self.directory = self.root / ".local/hlck/pyramid-net-stage/attempt"
        self.report = self.directory / "result.json"
        self.directory.mkdir(parents=True)
        prefix = recovery.MAPS[0] + ".BB_Arena_Port:PersistentLevel."
        self.net, self.renamed, self.fog, self.manager = [prefix + name for name in ("OldNet", "NewNet", "Fog", "Manager")]
        before = {self.net: {"class": "Net", "label": "Closed net"}, self.fog: {"class": "Fog", "z": -800}}
        self.attempt = {"status": "failed", "dry_run": False, "original_world": recovery.MAPS[1], "maps": []}
        for path in recovery.MAPS:
            physical = roof.asset_file(path, ".umap")
            physical.parent.mkdir(parents=True, exist_ok=True)
            physical.write_bytes(path.encode("utf-8"))
            backup = self.directory / "backups" / physical.relative_to(self.content)
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(physical.read_bytes())
            self.attempt["maps"].append({"path": path, "sha256_before": roof.digest(physical),
                                          "backup": str(backup), "preserved_before": before})
        self.diagnostic = {"read_only": True, "world": recovery.MAPS[0], "disk_map_unchanged": True,
            "dirty_maps": [recovery.MAPS[0]], "dirty_content": [],
            "removed": {self.net: before[self.net]}, "added": {self.renamed: before[self.net], self.manager: {"class": "Manager"}},
            "changed": {self.fog: {"before": before[self.fog], "after": {"class": "Fog", "z": 0}}}}
        self.diagnostic = copy.deepcopy(self.diagnostic)
        self.save()

    def save(self):
        self.report.write_text(json.dumps(self.attempt), encoding="utf-8")
        (self.directory / "snapshot-diagnostic.json").write_text(json.dumps(self.diagnostic), encoding="utf-8")

    def test_exact_diagnostic_is_reconstructed_without_whitelisting(self):
        proof = recovery.evidence(str(self.report), roof)
        self.assertEqual(proof["expected"], {self.renamed: {"class": "Net", "label": "Closed net"},
                                           self.fog: {"class": "Fog", "z": 0}, self.manager: {"class": "Manager"}})

    def test_success_and_dry_run_are_refused(self):
        for status, dry in (("staged", False), ("failed", True), ("failed", "false")):
            changed = copy.deepcopy(self.attempt)
            changed.update(status=status, dry_run=dry)
            with self.assertRaises(RuntimeError):
                recovery.expected_snapshot(changed, self.diagnostic)

    def test_saved_map_markers_are_refused(self):
        for name, value in (("sha256_after", ""), ("saved_reloaded", True), ("unrelated_actors_preserved", True)):
            changed = copy.deepcopy(self.attempt)
            changed["maps"][0][name] = value
            with self.assertRaises(RuntimeError):
                recovery.expected_snapshot(changed, self.diagnostic)

    def test_wrong_map_order_or_original_world_is_refused(self):
        changed = copy.deepcopy(self.attempt)
        changed["maps"].reverse()
        with self.assertRaises(RuntimeError):
            recovery.expected_snapshot(changed, self.diagnostic)
        changed = copy.deepcopy(self.attempt)
        changed["original_world"] = recovery.MAPS[0]
        with self.assertRaises(RuntimeError):
            recovery.expected_snapshot(changed, self.diagnostic)

    def test_unrelated_dirty_evidence_is_refused(self):
        for name, value in (("dirty_maps", [recovery.MAPS[0], "/Game/Other"]), ("dirty_content", ["/Game/Other"]),
                            ("world", recovery.MAPS[1]), ("read_only", False), ("disk_map_unchanged", False)):
            changed = copy.deepcopy(self.diagnostic)
            changed[name] = value
            with self.assertRaises(RuntimeError):
                recovery.expected_snapshot(self.attempt, changed)

    def test_changed_before_state_must_match_attempt(self):
        self.diagnostic["changed"][self.fog]["before"]["z"] = 7
        with self.assertRaises(RuntimeError):
            recovery.expected_snapshot(self.attempt, self.diagnostic)

    def test_removed_before_state_must_match_attempt(self):
        self.diagnostic["removed"][self.net] = {"class": "Unexpected"}
        with self.assertRaises(RuntimeError):
            recovery.expected_snapshot(self.attempt, self.diagnostic)

    def test_actor_delta_overlap_or_foreign_world_is_refused(self):
        self.diagnostic["added"][self.net] = {"class": "Unexpected"}
        with self.assertRaises(RuntimeError):
            recovery.expected_snapshot(self.attempt, self.diagnostic)
        del self.diagnostic["added"][self.net]
        self.diagnostic["added"]["/Game/Other.Other:PersistentLevel.Foreign"] = {}
        with self.assertRaises(RuntimeError):
            recovery.expected_snapshot(self.attempt, self.diagnostic)

    def test_changed_saved_map_is_refused(self):
        roof.asset_file(recovery.MAPS[1], ".umap").write_bytes(b"changed")
        with self.assertRaises(RuntimeError):
            recovery.evidence(str(self.report), roof)

    def test_changed_backup_is_refused(self):
        Path(self.attempt["maps"][0]["backup"]).write_bytes(b"changed")
        with self.assertRaises(RuntimeError):
            recovery.evidence(str(self.report), roof)

    def test_matching_backup_outside_attempt_is_refused(self):
        external = self.root / "elsewhere.umap"
        external.write_bytes(roof.asset_file(recovery.MAPS[0], ".umap").read_bytes())
        self.attempt["maps"][0]["backup"] = str(external)
        self.save()
        with self.assertRaises(RuntimeError):
            recovery.evidence(str(self.report), roof)

    def test_report_outside_immediate_attempt_directory_is_refused(self):
        for path in (self.root / "result.json", self.directory / "nested/result.json", self.directory / "other.json"):
            with self.assertRaises((ValueError, RuntimeError)):
                recovery.evidence(str(path), roof)


if __name__ == "__main__":
    unittest.main()

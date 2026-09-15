"""CPU-only receipt tests; no native editor, assets or databases are opened."""
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location(
    "bb_hlck_pie_cleanup", Path(__file__).with_name("inspect_hlck_pie_cleanup.py"))
CLEANUP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLEANUP)


def package(path):
    return SimpleNamespace(get_path_name=lambda: path)


class CleanupReceiptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.report = Path(self.directory.name) / "nested" / "cleanup.json"
        self.report.parent.mkdir()
        self.report.write_text(json.dumps({"status": "passed", "clean_owned_editor": True,
                                          "attempt_id": "stale-success"}), encoding="utf-8")
        self.u = SimpleNamespace(
            Paths=SimpleNamespace(
                get_project_file_path=Mock(return_value=str(CLEANUP.PROJECT)),
                convert_relative_path_to_full=Mock(side_effect=lambda value: value)),
            GameModManagerSubsystem=SimpleNamespace(
                get_active_mod_name_bp=Mock(return_value="Basketbroom")),
            EditorLevelLibrary=SimpleNamespace(
                get_editor_world=Mock(return_value=package(CLEANUP.WORLD)),
                get_pie_worlds=Mock(return_value=[]),
                editor_end_play=Mock(side_effect=AssertionError("Must not stop PIE")),
                load_level=Mock(side_effect=AssertionError("Must not load levels"))),
            EditorLoadingAndSavingUtils=SimpleNamespace(
                get_dirty_map_packages=Mock(return_value=[]),
                get_dirty_content_packages=Mock(return_value=[]),
                save_dirty_packages=Mock(side_effect=AssertionError("Must not save packages")),
                save_packages=Mock(side_effect=AssertionError("Must not save packages"))),
            EditorAssetLibrary=SimpleNamespace(
                save_asset=Mock(side_effect=AssertionError("Must not save assets"))),
            SQLiteBlueprintFunctionLibrary=SimpleNamespace(
                execute_query=Mock(side_effect=AssertionError("Must not query SQLite"))))
        self.sqlite = patch.object(sqlite3, "connect",
                                   side_effect=AssertionError("Must not open SQLite")).start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        self.sqlite.assert_not_called()
        self.u.EditorLevelLibrary.editor_end_play.assert_not_called()
        self.u.EditorLevelLibrary.load_level.assert_not_called()
        self.u.EditorLoadingAndSavingUtils.save_dirty_packages.assert_not_called()
        self.u.EditorLoadingAndSavingUtils.save_packages.assert_not_called()
        self.u.EditorAssetLibrary.save_asset.assert_not_called()
        self.u.SQLiteBlueprintFunctionLibrary.execute_query.assert_not_called()

    def invoke(self):
        returned = CLEANUP.run(self.u, self.report)
        receipt = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(returned["status"], receipt["status"])
        self.assertEqual(returned["clean_owned_editor"], receipt["clean_owned_editor"])
        self.assertEqual(returned["attempt_id"], receipt["attempt_id"])
        self.assertNotEqual(receipt["attempt_id"], "stale-success")
        self.assertEqual(receipt["process_id"], os.getpid())
        self.assertLessEqual(datetime.fromisoformat(receipt["started_utc"]),
                             datetime.fromisoformat(receipt["completed_utc"]))
        self.assertTrue(receipt["read_only"])
        self.assertFalse(receipt["database_queried"])
        self.assertFalse(receipt["assets_saved"])
        self.assertEqual(list(self.report.parent.iterdir()), [self.report])
        return receipt

    def assert_failed(self, receipt, reason):
        self.assertEqual(receipt["status"], "failed")
        self.assertFalse(receipt["clean_owned_editor"])
        self.assertIn(reason, receipt["error"])

    def test_wrong_mod_replaces_previous_success(self):
        self.u.GameModManagerSubsystem.get_active_mod_name_bp.return_value = ""
        receipt = self.invoke()
        self.assert_failed(receipt, "active Basketbroom mod")
        self.assertEqual(receipt["active_mod"], "")
        self.u.EditorLevelLibrary.get_editor_world.assert_not_called()

    def test_wrong_project_replaces_previous_success(self):
        self.u.Paths.get_project_file_path.return_value = "Other/Phoenix.uproject"
        receipt = self.invoke()
        self.assert_failed(receipt, "exact installed Phoenix project")
        self.u.GameModManagerSubsystem.get_active_mod_name_bp.assert_not_called()

    def test_query_exception_replaces_previous_success(self):
        self.u.EditorLevelLibrary.get_pie_worlds.side_effect = RuntimeError("accessor failed")
        receipt = self.invoke()
        self.assert_failed(receipt, "RuntimeError: accessor failed")
        self.assertIsNone(receipt["pie_worlds"])
        self.assertEqual(receipt["editor_world"], CLEANUP.WORLD)
        self.u.EditorLoadingAndSavingUtils.get_dirty_map_packages.assert_not_called()

    def test_success_requires_all_clean_owned_state(self):
        receipt = self.invoke()
        self.assertEqual(receipt["status"], "passed")
        self.assertTrue(receipt["clean_owned_editor"])
        self.assertIsNone(receipt["error"])
        self.assertIsNotNone(receipt["observed_utc"])
        self.assertEqual(receipt["editor_world"], CLEANUP.WORLD)
        self.assertEqual(receipt["pie_worlds"], [])
        self.assertEqual(receipt["dirty_maps"], [])
        self.assertEqual(receipt["dirty_content"], [])
        self.assertFalse(receipt["observer_still_registered"])
        self.u.EditorLevelLibrary.get_pie_worlds.assert_called_once_with(True)

    def test_any_pie_world_prevents_clean_receipt(self):
        for path in ("/Basketbroom/Maps/UEDPIE_0_Basketbroom_DungeonMap.Basketbroom_DungeonMap",
                     "/Game/Maps/UEDPIE_0_Foreign.Foreign"):
            with self.subTest(path=path):
                self.u.EditorLevelLibrary.get_pie_worlds.return_value = [package(path)]
                self.assert_failed(self.invoke(), "PIE worlds remain")

    def test_dirty_map_prevents_clean_receipt(self):
        self.u.EditorLoadingAndSavingUtils.get_dirty_map_packages.return_value = [
            package("/Basketbroom/Maps/Basketbroom_DungeonMap")]
        self.assert_failed(self.invoke(), "Dirty packages remain")

    def test_dirty_content_prevents_clean_receipt(self):
        self.u.EditorLoadingAndSavingUtils.get_dirty_content_packages.return_value = [
            package("/Game/UnrelatedAsset")]
        self.assert_failed(self.invoke(), "Dirty packages remain")

    def test_registered_observer_prevents_clean_receipt(self):
        self.u._basketbroom_hlck_dungeon_pie_smoke = object()
        self.assert_failed(self.invoke(), "observer remains registered")

    def test_missing_or_lookalike_world_prevents_clean_receipt(self):
        for path in (None, CLEANUP.WORLD + "_Copy", "/Game/Maps/Other.Other"):
            with self.subTest(path=path):
                self.u.EditorLevelLibrary.get_editor_world.return_value = package(path) if path else None
                self.assert_failed(self.invoke(), "exact owned dungeon editor world")

    def test_attempt_is_visible_before_first_engine_query(self):
        def query():
            receipt = json.loads(self.report.read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "inspecting")
            self.assertFalse(receipt["clean_owned_editor"])
            self.assertNotEqual(receipt["attempt_id"], "stale-success")
            self.assertIsNone(receipt["project"])
            self.assertIsNone(receipt["completed_utc"])
            raise RuntimeError("first query failed")
        self.u.Paths.get_project_file_path.side_effect = query
        self.assert_failed(self.invoke(), "first query failed")

    def test_transient_report_lock_retries_then_publishes_complete_json(self):
        original_replace = Path.replace
        attempts = []
        def replace(source, target):
            attempts.append(source)
            payload = json.loads(source.read_text(encoding="utf-8"))
            self.assertIn(payload["status"], ("inspecting", "passed"))
            if len(attempts) <= 2:
                raise PermissionError("brief reader lock")
            return original_replace(source, target)
        with patch.object(Path, "replace", replace), patch.object(CLEANUP.time, "sleep") as pause:
            self.assertTrue(self.invoke()["clean_owned_editor"])
        self.assertEqual(len(attempts), 4)
        self.assertEqual(pause.call_count, 2)

    def test_locked_report_fails_before_engine_queries(self):
        with patch.object(Path, "replace", side_effect=PermissionError("locked")) as replace, \
                patch.object(CLEANUP.time, "sleep") as pause:
            with self.assertRaisesRegex(PermissionError, "locked"):
                CLEANUP.run(self.u, self.report)
        self.assertEqual(replace.call_count, 8)
        self.assertEqual(pause.call_count, 7)
        self.u.Paths.get_project_file_path.assert_not_called()
        self.assertEqual(list(self.report.parent.iterdir()), [self.report])

    def test_final_report_lock_cannot_leave_previous_success(self):
        original_replace = Path.replace
        attempts = []
        def replace(source, target):
            attempts.append(source)
            if len(attempts) > 1:
                raise PermissionError("final write locked")
            return original_replace(source, target)
        with patch.object(Path, "replace", replace), patch.object(CLEANUP.time, "sleep"):
            with self.assertRaisesRegex(PermissionError, "final write locked"):
                CLEANUP.run(self.u, self.report)
        receipt = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "inspecting")
        self.assertFalse(receipt["clean_owned_editor"])
        self.assertNotEqual(receipt["attempt_id"], "stale-success")
        self.assertEqual(len(attempts), 9)


if __name__ == "__main__":
    unittest.main()

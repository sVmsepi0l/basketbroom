"""CPU-only regression tests for HLCK observer ownership and cleanup.

These mocks exercise lifecycle behavior, not Phoenix gameplay or engine APIs.
No Unreal installation, process, map or database is opened by this suite.
"""
import importlib.util
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location(
    "bb_hlck_pie_observer", Path(__file__).with_name("test_hlck_dungeon_pie.py"))
OBSERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OBSERVER)
RECOVERY_SPEC = importlib.util.spec_from_file_location(
    "bb_hlck_pie_recovery", Path(__file__).with_name("end_hlck_owned_pie.py"))
RECOVERY = importlib.util.module_from_spec(RECOVERY_SPEC)
RECOVERY_SPEC.loader.exec_module(RECOVERY)


def world(path):
    return SimpleNamespace(get_path_name=lambda: path)


OWN_PIE = world("/Basketbroom/Maps/UEDPIE_0_Basketbroom_DungeonMap.Basketbroom_DungeonMap")
OWN_EDITOR = world(OBSERVER.WORLD + ".Basketbroom_DungeonMap")
FOREIGN_PIE = world("/Game/Levels/UEDPIE_0_Other.Other")


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.editor = SimpleNamespace(
            get_editor_world=Mock(return_value=None),
            get_pie_worlds=Mock(return_value=[OWN_PIE]),
            editor_end_play=Mock())
        self.unreal = SimpleNamespace(EditorLevelLibrary=self.editor,
            unregister_slate_post_tick_callback=Mock())
        self.smoke = OBSERVER.Smoke.__new__(OBSERVER.Smoke)
        self.smoke.u = self.unreal
        self.smoke.started = 100.0
        self.smoke.first_pie = None
        self.smoke.stop_time = None
        self.smoke.last_poll = 0.0
        self.smoke.stable_since = None
        self.smoke.native_ready_since = None
        self.smoke.owns_session = False
        self.smoke.handle = "observer-handle"
        self.smoke.result = {"status": "awaiting_actual_play", "checks": {},
                             "runtime_checks": "NOT_RUN"}
        self.smoke.write = Mock()
        self.smoke.snapshot = Mock(return_value=False)
        setattr(self.unreal, OBSERVER.STATE_NAME, self.smoke)

    def tick(self, timestamp):
        with patch.object(OBSERVER.time, "monotonic", return_value=timestamp):
            self.smoke.tick(0.5)

    def prepare_finish(self, before=None, after=None):
        self.editor.get_pie_worlds.return_value = []
        self.editor.get_editor_world.return_value = OWN_EDITOR
        self.smoke.guard = SimpleNamespace(require_clean=Mock(return_value={"map": [], "content": []}))
        self.smoke.registrar = SimpleNamespace(CONTENT=None, KIT_CONTENT=None,
            hashes=Mock(return_value={}), metadata=Mock(return_value={}))
        self.smoke.stage = SimpleNamespace(digest=Mock(side_effect=lambda path: after[str(path)]))
        self.smoke.content_before = {}
        self.smoke.protected_before = before or {}
        self.smoke.installed_before = {}

    def test_real_pie_with_missing_editor_world_is_claimed_before_observation(self):
        self.tick(101)
        self.assertTrue(self.smoke.owns_session)
        self.assertEqual(self.smoke.first_pie, 101)
        self.editor.get_editor_world.assert_not_called()
        self.tick(102)
        self.smoke.snapshot.assert_called_once_with(OWN_PIE)
        self.editor.editor_end_play.assert_not_called()

    def test_transition_with_no_world_waits_without_claiming_or_stopping(self):
        self.editor.get_pie_worlds.return_value = []
        self.tick(200)
        self.assertFalse(self.smoke.owns_session)
        self.assertIsNone(self.smoke.stop_time)
        self.assertEqual(self.smoke.result["runtime_checks"], "NOT_RUN")
        self.editor.editor_end_play.assert_not_called()

    def test_missing_world_deadline_is_startup_timeout_not_gameplay_failure(self):
        self.editor.get_pie_worlds.return_value = []
        self.tick(701)
        self.assertEqual(self.smoke.result["failure_stage"], "startup_timeout")
        self.assertEqual(self.smoke.result["runtime_checks"], "NOT_RUN")
        self.smoke.snapshot.assert_not_called()
        self.editor.editor_end_play.assert_not_called()

    def test_foreign_or_multiple_pie_worlds_are_never_claimed_or_ended(self):
        for worlds in ([FOREIGN_PIE], [OWN_PIE, FOREIGN_PIE]):
            with self.subTest(worlds=worlds):
                self.setUp()
                self.editor.get_pie_worlds.return_value = worlds
                self.tick(101)
                self.assertFalse(self.smoke.owns_session)
                self.editor.editor_end_play.assert_not_called()
                self.smoke.snapshot.assert_not_called()

    def test_fixture_error_after_claim_ends_only_owned_session_once(self):
        self.tick(101)
        self.smoke.snapshot.side_effect = RuntimeError("fixture getter unavailable")
        self.tick(102)
        self.assertEqual(self.smoke.result["failure_stage"], "observer_fixture")
        self.assertTrue(self.smoke.result["end_play_requested"])
        self.editor.editor_end_play.assert_called_once_with()
        self.smoke.stop("Repeated stop while cleanup is pending")
        self.editor.editor_end_play.assert_called_once_with()

    def test_foreign_world_after_claim_is_not_ended(self):
        self.tick(101)
        self.editor.get_pie_worlds.return_value = [FOREIGN_PIE]
        self.tick(102)
        self.editor.editor_end_play.assert_not_called()

    def test_report_write_failure_after_claim_still_requests_cleanup(self):
        self.smoke.write.side_effect = PermissionError("report is locked")
        with self.assertRaises(PermissionError):
            self.tick(101)
        self.assertTrue(self.smoke.owns_session)
        self.editor.editor_end_play.assert_called_once_with()

    def test_finish_removes_callback_and_state_even_when_report_write_fails(self):
        self.prepare_finish()
        self.smoke.write.side_effect = PermissionError("report is locked")
        with self.assertRaises(PermissionError):
            self.smoke.finish()
        self.unreal.unregister_slate_post_tick_callback.assert_called_once_with("observer-handle")
        self.assertFalse(hasattr(self.unreal, OBSERVER.STATE_NAME))
        self.assertIsNone(self.smoke.handle)

    def test_native_dynamic_database_change_is_recorded_without_failing_readiness(self):
        name = str(OBSERVER.DYNAMIC_DATABASE)
        self.prepare_finish({name: "before"}, {name: "after"})
        self.smoke.finish()
        self.assertEqual(self.smoke.result["status"], "passed")
        self.assertTrue(self.smoke.result["dynamic_database"]["changed"])
        self.assertFalse(self.smoke.result["dynamic_database"]["logical_delta_verified"])
        self.assertTrue(self.smoke.result["protected_files_unchanged"])

    def test_immutable_shipped_database_change_still_fails_preservation(self):
        name = str(OBSERVER.DYNAMIC_DATABASE.with_name("PhoenixGameData.sqlite"))
        self.prepare_finish({name: "before"}, {name: "after"})
        self.smoke.finish()
        self.assertEqual(self.smoke.result["status"], "failed")
        self.assertFalse(self.smoke.result["protected_files_unchanged"])

    def test_locked_dynamic_database_requests_postclose_inspection_without_false_failure(self):
        name = str(OBSERVER.DYNAMIC_DATABASE)
        self.prepare_finish({name: "before"}, {})
        self.smoke.stage.digest.side_effect = PermissionError("native dynamic cache is locked")
        self.smoke.finish()
        self.assertEqual(self.smoke.result["status"], "passed")
        self.assertEqual(self.smoke.result["dynamic_database"]["status"], "postclose_inspection_required")
        self.assertIsNone(self.smoke.result["dynamic_database"]["changed"])

    def test_callback_registration_failure_rolls_back_armed_state(self):
        delattr(self.unreal, OBSERVER.STATE_NAME)
        self.smoke.handle = None
        self.smoke.preflight = Mock()
        self.unreal.register_slate_post_tick_callback = Mock(side_effect=RuntimeError("unavailable callback"))
        with patch.dict(sys.modules, {"unreal": self.unreal}), \
                patch.object(OBSERVER, "Smoke", return_value=self.smoke):
            result = OBSERVER.arm()
        self.assertEqual(result["status"], "failed")
        self.assertFalse(hasattr(self.unreal, OBSERVER.STATE_NAME))
        self.unreal.unregister_slate_post_tick_callback.assert_not_called()


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.editor = SimpleNamespace(get_pie_worlds=Mock(return_value=[OWN_PIE]),
            get_editor_world=Mock(return_value=OWN_EDITOR), editor_end_play=Mock())
        self.callbacks = []
        self.unreal = SimpleNamespace(EditorLevelLibrary=self.editor,
            Paths=SimpleNamespace(convert_relative_path_to_full=lambda value: value,
                get_project_file_path=lambda:
                r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject"),
            GameModManagerSubsystem=SimpleNamespace(get_active_mod_name_bp=lambda: "Basketbroom"),
            register_slate_post_tick_callback=lambda callback: self.callbacks.append(callback) or "recovery-handle",
            unregister_slate_post_tick_callback=Mock())

    def test_recovery_rejects_prefix_suffix_lookalike_world(self):
        self.editor.get_pie_worlds.return_value = [world(
            "/Basketbroom/Maps/UEDPIE_unrelated_Basketbroom_DungeonMap.Basketbroom_DungeonMap")]
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(RECOVERY, "REPORT", Path(directory) / "recovery.json"), \
                patch.dict(sys.modules, {"unreal": self.unreal}):
            result = RECOVERY.run()
        self.assertEqual(result["status"], "failed")
        self.editor.editor_end_play.assert_not_called()
        self.assertFalse(self.callbacks)

    def test_recovery_removes_callback_when_world_getter_raises(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(RECOVERY, "REPORT", Path(directory) / "recovery.json"), \
                patch.dict(sys.modules, {"unreal": self.unreal}):
            result = RECOVERY.run()
            self.assertEqual(result["status"], "ending_exact_owned_pie")
            self.editor.get_pie_worlds.side_effect = RuntimeError("world accessor unavailable")
            self.callbacks[0](0.5)
        self.editor.editor_end_play.assert_called_once_with()
        self.unreal.unregister_slate_post_tick_callback.assert_called_once_with("recovery-handle")

    def test_recovery_removes_callback_when_completion_report_write_raises(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(RECOVERY, "REPORT", Path(directory) / "recovery.json"), \
                patch.dict(sys.modules, {"unreal": self.unreal}):
            RECOVERY.run()
            self.editor.get_pie_worlds.return_value = []
            with patch.object(Path, "write_text", side_effect=PermissionError("locked report")):
                with self.assertRaises(PermissionError):
                    self.callbacks[0](0.5)
        self.unreal.unregister_slate_post_tick_callback.assert_called_once_with("recovery-handle")


class BackupTests(unittest.TestCase):
    def test_protected_database_bytes_are_copied_and_hash_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source" / "Dynamic.sqlite"
            source.parent.mkdir()
            source.write_bytes(b"pre-Play fixture bytes")
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            expected = digest(source)
            receipt = OBSERVER.backup_databases(Path(directory) / "backup",
                {str(source): expected}, digest)
            self.assertEqual(Path(receipt[str(source)]["copy"]).read_bytes(), source.read_bytes())
            self.assertEqual(receipt[str(source)]["sha256"], expected)

    def test_changed_database_snapshot_refuses_to_arm(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Dynamic.sqlite"
            source.write_bytes(b"changed after preflight hash")
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(RuntimeError, "changed during pre-Play backup"):
                OBSERVER.backup_databases(Path(directory) / "backup",
                    {str(source): hashlib.sha256(b"old bytes").hexdigest()}, digest)

    def test_source_change_during_copy_is_detected_even_when_copy_hash_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Dynamic.sqlite"
            source.write_bytes(b"original snapshot")
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            expected = digest(source)
            original_copy = OBSERVER.shutil.copy2
            def copy_then_change(source_name, target_name):
                original_copy(source_name, target_name)
                source.write_bytes(b"concurrent native refresh")
            with patch.object(OBSERVER.shutil, "copy2", side_effect=copy_then_change):
                with self.assertRaisesRegex(RuntimeError, "changed during pre-Play backup"):
                    OBSERVER.backup_databases(Path(directory) / "backup", {str(source): expected}, digest)


if __name__ == "__main__":
    unittest.main(verbosity=2)

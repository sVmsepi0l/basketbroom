"""Portable fake-Unreal lifecycle checks; no editor, assets or real DB are opened."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


LIVE = load("bb_live_pie_tested", "inspect_hlck_live_pie.py")
BASE = load("bb_actual_native_snapshot", "test_hlck_dungeon_pie.py")
PIE_PATH = "/Basketbroom/Maps/UEDPIE_0_Basketbroom_DungeonMap.Basketbroom_DungeonMap"


class Object:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path

    def get_class(self):
        return Object(self.path)


class Character(Object):
    pass


class Sphere(Object):
    def get_name(self):
        return self.path

    def get_scaled_sphere_radius(self):
        return 100.0

    def get_collision_enabled(self):
        return "QUERY_ONLY"

    def get_editor_property(self, name):
        return True


class LiveObservationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.report = Path(directory.name) / "receipt.json"
        self.report.write_text(json.dumps({"status": "passed", "attempt_id": "stale-success"}))
        self.now = 100.0
        self.world_clock_paused = False
        self.world = Object(PIE_PATH)
        self.position = SimpleNamespace(x=-3000.0, y=0.0, z=90.15)
        movement = Object("/Script/Phoenix.Biped_MovementComponent")
        movement.is_falling = lambda: False
        movement.is_moving_on_ground = lambda: True
        self.pawn = Character("/Game/Pawn/Player/BP_Biped_Player.BP_Biped_Player_C")
        self.pawn.get_actor_location = lambda: self.position
        self.pawn.get_component_by_class = lambda cls: movement
        controller = Object("/Game/Pawn/Player/BP_Phoenix_Player_Controller.BP_Phoenix_Player_Controller_C")
        controller.get_controlled_pawn = lambda: self.pawn
        controller.is_local_controller = lambda: True
        self.exit = Object("/Basketbroom/Blueprints/BP_Basketbroom_DungeonExit.BP_Basketbroom_DungeonExit_C")
        self.exit.actor_has_tag = lambda tag: tag == "owned-exit"
        self.exit.get_editor_property = lambda name: "Overland" if name == "LoadingToLevel" else "expected"
        self.exit.get_components_by_class = lambda cls: [Sphere("A"), Sphere("B"), Object("CognitionStimuliSource")]
        registry = Object("Registry")
        registry.get_mod_table_for_base_table = lambda base: Object("Composite")
        forbid = lambda: Mock(side_effect=AssertionError("Read-only observation must not mutate engine"))
        self.u = SimpleNamespace(
            Paths=SimpleNamespace(get_project_file_path=Mock(return_value=str(LIVE.PROJECT)),
                convert_relative_path_to_full=Mock(side_effect=lambda path: path)),
            SystemLibrary=SimpleNamespace(get_engine_version=Mock(return_value="4.27.2-native")),
            GameModManagerSubsystem=SimpleNamespace(get_active_mod_name_bp=Mock(return_value="Basketbroom"),
                has_active_editor_mod_bp=Mock(return_value=True)),
            EditorLevelLibrary=SimpleNamespace(get_pie_worlds=Mock(return_value=[self.world]),
                get_editor_world=forbid(), editor_end_play=forbid(), load_level=forbid()),
            EditorLoadingAndSavingUtils=SimpleNamespace(get_dirty_map_packages=Mock(return_value=[]),
                get_dirty_content_packages=Mock(return_value=[]), save_packages=forbid()),
            GameplayStatics=SimpleNamespace(
                get_game_mode=Mock(return_value=Object("/Game/Data/GameMode/Phoenix_Game_Mode.Phoenix_Game_Mode_C")),
                get_game_instance=Mock(return_value=Object("/Game/Data/GameInstance/BP_PhoenixGameInstance.BP_PhoenixGameInstance_C")),
                get_player_controller=Mock(return_value=controller), get_player_pawn=Mock(return_value=self.pawn),
                get_all_actors_of_class=Mock(return_value=[self.exit]),
                get_time_seconds=Mock(side_effect=lambda world: 77.0 if self.world_clock_paused else 77.0 + self.now - 100.0),
                open_level=forbid()),
            Character=Character, CharacterMovementComponent=type("Movement", (), {}), Actor=Object,
            ActorComponent=Object, SphereComponent=Sphere,
            DbGateway=SimpleNamespace(db_query=Mock(return_value=SimpleNamespace(success=True,
                result_rows=[SimpleNamespace(fields=[])]))),
            UGCBlueprintLibrary=SimpleNamespace(get_ugc_registry=Mock(return_value=registry)),
            load_asset=Mock(side_effect=lambda path: Object(path)),
            DataTableFunctionLibrary=SimpleNamespace(get_data_table_row_names=Mock(return_value=["owned-row"])),
            register_slate_post_tick_callback=Mock(return_value="live-callback"),
            unregister_slate_post_tick_callback=Mock())
        self.reader = BASE.Smoke.__new__(BASE.Smoke)
        self.reader.u = self.u
        self.reader.first_pie = None
        self.reader.native_ready_since = None
        self.reader.result = {"checks": {}}
        self.reader.stage = SimpleNamespace(BASE_DUNGEONS="Dungeons", BASE_SUBDIVISIONS="Subdivisions", ROW_NAME="owned-row")
        self.reader.registrar = SimpleNamespace(POSITION={}, verify_row=Mock())
        self.reader.anchors = SimpleNamespace(xyz=lambda p: [p.x, p.y, p.z], EXIT_TAG="owned-exit",
            EXIT_DEFAULTS={"LoadingToLevel": "Overland"}, actor_record=lambda actor: {"path": actor.path})
        self.addCleanup(patch.stopall)
        patch.object(LIVE, "snapshot_reader", return_value=(BASE, self.reader)).start()
        patch.object(LIVE.time, "monotonic", side_effect=lambda: self.now).start()
        self.lifecycle = [patch.object(BASE.Smoke, name, side_effect=AssertionError("Original lifecycle forbidden")).start()
                          for name in ("__init__", "preflight", "write", "stop", "finish", "tick")]

    def tearDown(self):
        for mock in self.lifecycle:
            mock.assert_not_called()
        self.u.EditorLevelLibrary.get_editor_world.assert_not_called()
        self.u.EditorLevelLibrary.editor_end_play.assert_not_called()
        self.u.EditorLevelLibrary.load_level.assert_not_called()
        self.u.EditorLoadingAndSavingUtils.save_packages.assert_not_called()
        self.u.GameplayStatics.open_level.assert_not_called()
        for call in self.u.DbGateway.db_query.call_args_list:
            self.assertEqual(call.args, ("SELECT * FROM DungeonEntrances WHERE DungeonName='Basketbroom_DungeonMap'",))

    def receipt(self):
        return json.loads(self.report.read_text())

    def arm(self):
        result = LIVE.run(self.u, self.report)
        self.observer = getattr(self.u, LIVE.STATE_NAME, None)
        self.assertNotEqual(self.receipt()["attempt_id"], "stale-success")
        return result

    def tick(self, now):
        self.now = now
        self.observer.tick(0.5)
        return self.receipt()

    def assert_failed(self, text):
        receipt = self.receipt()
        self.assertEqual(receipt["status"], "failed")
        self.assertFalse(receipt["runtime_ready"])
        self.assertIn(text, receipt["error"])
        self.assertIsNotNone(receipt["completed_utc"])

    def test_pending_is_published_before_first_engine_query(self):
        def query():
            receipt = self.receipt()
            self.assertEqual(receipt["status"], "pending")
            self.assertFalse(receipt["runtime_ready"])
            self.assertIsNone(receipt["first_observed_utc"])
            self.assertNotEqual(receipt["attempt_id"], "stale-success")
            raise RuntimeError("first query failed")
        self.u.Paths.get_project_file_path.side_effect = query
        self.arm()
        self.assert_failed("first query failed")
        self.u.register_slate_post_tick_callback.assert_not_called()

    def test_foreign_project_refused_before_runtime_reads(self):
        self.u.Paths.get_project_file_path.return_value = "Other/Phoenix.uproject"
        self.arm()
        self.assert_failed("exact installed Phoenix project")
        self.u.GameplayStatics.get_game_mode.assert_not_called()

    def test_wrong_engine_or_mod_refused(self):
        self.u.SystemLibrary.get_engine_version.return_value = "5.8.1"
        self.arm()
        self.assert_failed("native Creator Kit UE4.27")
        self.u.SystemLibrary.get_engine_version.return_value = "4.27.2"
        self.u.GameModManagerSubsystem.get_active_mod_name_bp.return_value = "Other"
        self.arm()
        self.assert_failed("active Basketbroom")

    def test_name_without_active_editor_mod_flag_is_refused(self):
        self.u.GameModManagerSubsystem.has_active_editor_mod_bp.return_value = False
        self.arm()
        self.assert_failed("Expected an active editor mod")
        self.assertFalse(self.receipt()["has_active_editor_mod"])
        self.u.register_slate_post_tick_callback.assert_not_called()

    def test_snapshot_returning_after_deadline_cannot_pass(self):
        self.arm()
        self.tick(100)
        self.tick(105)
        mode = self.u.GameplayStatics.get_game_mode.return_value
        def delayed(world):
            self.now = 131
            return mode
        self.u.GameplayStatics.get_game_mode.side_effect = delayed
        self.tick(107)
        self.assert_failed("snapshot exceeded the 30-second")
        self.u.unregister_slate_post_tick_callback.assert_called_once()

    def test_foreign_missing_multiple_and_lookalike_worlds_refused(self):
        for worlds in ([], [Object("/Game/UEDPIE_0_Other.Other")],
                       [self.world, Object(PIE_PATH)], [Object(PIE_PATH + "_Copy")]):
            with self.subTest(worlds=worlds):
                self.u.EditorLevelLibrary.get_pie_worlds.return_value = worlds
                self.arm()
                self.assert_failed("exactly one already-running owned")
        self.u.register_slate_post_tick_callback.assert_not_called()

    def test_dirty_packages_refused_without_saving(self):
        self.u.EditorLoadingAndSavingUtils.get_dirty_content_packages.return_value = [Object("/Basketbroom/Material")]
        self.arm()
        self.assert_failed("Dirty packages")

    def test_existing_smoke_and_live_observers_are_preserved(self):
        existing = object()
        for name in (LIVE.SMOKE_STATE_NAME, LIVE.STATE_NAME):
            setattr(self.u, name, existing)
            self.arm()
            self.assert_failed("existing")
            self.assertIs(getattr(self.u, name), existing)
            delattr(self.u, name)
        self.u.unregister_slate_post_tick_callback.assert_not_called()

    def test_success_uses_actual_elapsed_services_and_stability(self):
        self.assertEqual(self.arm()["status"], "observing")
        self.assertEqual(self.reader.first_pie, 100.0)
        self.tick(100)
        self.assertIsNone(self.receipt()["checks"]["runtime_registered_row"])
        self.u.DbGateway.db_query.assert_not_called()
        self.tick(102)
        self.assertEqual(self.receipt()["native_services_observed_seconds"], 2)
        self.u.DbGateway.db_query.assert_not_called()
        self.tick(105)
        receipt = self.receipt()
        self.assertEqual(receipt["native_runtime_passed"], 16)
        self.assertEqual(receipt["passed"], 17)
        self.assertEqual(receipt["status"], "observing")
        self.assertFalse(receipt["runtime_ready"])
        self.tick(106.5)
        self.assertEqual(self.receipt()["status"], "observing")
        receipt = self.tick(107)
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["all_checks_stable_seconds"], 2)
        self.assertEqual(receipt["elapsed_observation_seconds"], 7)
        self.assertEqual(receipt["world_elapsed_seconds"], 7)
        self.assertEqual(receipt["callback_count"], 5)
        self.assertEqual(receipt["total"], 17)
        self.assertEqual(receipt["native_runtime_total"], 16)
        self.assertEqual(receipt["world_time_samples"][0]["world_time_seconds"], 77)
        self.assertFalse(receipt["startup_verified"])
        self.assertFalse(receipt["pre_play_preservation_verified"])
        self.assertFalse(receipt["callback_registered"])
        self.assertFalse(hasattr(self.u, LIVE.STATE_NAME))
        self.u.unregister_slate_post_tick_callback.assert_called_once_with("live-callback")

    def test_a_single_tick_after_long_gap_does_not_fake_services_age(self):
        self.arm()
        self.tick(110)
        self.assertEqual(self.receipt()["native_services_observed_seconds"], 0)
        self.assertEqual(self.receipt()["status"], "observing")
        self.tick(112)
        self.assertEqual(self.receipt()["all_checks_stable_seconds"], 0)
        self.tick(114)
        self.assertEqual(self.receipt()["status"], "passed")

    def test_transient_failure_resets_all_checks_stability(self):
        self.arm()
        self.tick(100)
        self.tick(105)
        self.position.x = 0
        self.tick(106)
        self.assertEqual(self.receipt()["all_checks_stable_seconds"], 0)
        self.position.x = -3000
        self.tick(107)
        self.tick(108)
        self.assertEqual(self.receipt()["status"], "observing")
        self.tick(109)
        self.assertEqual(self.receipt()["status"], "passed")

    def test_moved_player_fails_grounded_start_without_teleport(self):
        self.position.x = 0
        self.arm()
        self.tick(100)
        self.tick(105)
        self.tick(130)
        self.assert_failed("grounded_start")
        self.assertFalse(self.receipt()["checks"]["grounded_start"])
        self.assertFalse(hasattr(self.u, LIVE.STATE_NAME))

    def test_paused_or_stalled_world_cannot_pass_even_with_all_runtime_checks(self):
        self.world_clock_paused = True
        self.arm()
        self.tick(100)
        self.tick(105)
        self.assertEqual(self.receipt()["native_runtime_passed"], 16)
        self.assertFalse(self.receipt()["checks"]["world_time_advanced"])
        self.tick(130)
        self.assert_failed("paused or stalled session")
        self.u.unregister_slate_post_tick_callback.assert_called_once()

    def test_timeout_precedes_any_late_snapshot(self):
        self.arm()
        self.tick(131)
        self.assert_failed("within 30 seconds")
        self.u.GameplayStatics.get_game_mode.assert_not_called()

    def test_session_replacement_even_with_same_path_is_refused(self):
        self.arm()
        self.u.EditorLevelLibrary.get_pie_worlds.return_value = [Object(PIE_PATH)]
        self.tick(101)
        self.assert_failed("session changed")
        self.u.unregister_slate_post_tick_callback.assert_called_once()

    def test_query_failure_cleans_callback_and_replaces_receipt(self):
        self.arm()
        self.u.GameplayStatics.get_game_mode.side_effect = RuntimeError("native getter failed")
        self.tick(101)
        self.assert_failed("native getter failed")
        self.assertFalse(hasattr(self.u, LIVE.STATE_NAME))

    def test_registration_failure_rolls_back_own_state(self):
        self.u.register_slate_post_tick_callback.side_effect = RuntimeError("callback unavailable")
        self.arm()
        self.assert_failed("callback unavailable")
        self.assertFalse(hasattr(self.u, LIVE.STATE_NAME))
        self.u.unregister_slate_post_tick_callback.assert_not_called()

    def test_missing_world_clock_is_explicit_failure(self):
        self.u.GameplayStatics.get_time_seconds = None
        self.arm()
        self.assert_failed("responsiveness is unverified")
        self.u.register_slate_post_tick_callback.assert_not_called()

    def test_nonfinite_and_backwards_world_clock_rejected(self):
        self.u.GameplayStatics.get_time_seconds.side_effect = None
        self.u.GameplayStatics.get_time_seconds.return_value = float("nan")
        self.arm()
        self.assert_failed("non-finite")
        self.u.GameplayStatics.get_time_seconds.return_value = 100
        self.arm()
        self.u.GameplayStatics.get_time_seconds.return_value = 99
        self.tick(101)
        self.assert_failed("moved backwards")

    def test_unregister_error_cannot_publish_success_and_retains_guard(self):
        self.arm()
        self.tick(100)
        self.tick(105)
        self.u.unregister_slate_post_tick_callback.side_effect = RuntimeError("unregister failed")
        self.tick(107)
        self.assert_failed("Could not unregister")
        self.assertIs(getattr(self.u, LIVE.STATE_NAME), self.observer)
        self.assertTrue(self.receipt()["callback_registered"])
        self.assertTrue(self.observer.done)

    def test_final_publication_error_still_unregisters_and_cannot_leave_success(self):
        self.arm()
        self.tick(100)
        self.tick(105)
        old = self.receipt()
        with patch.object(LIVE, "write_report", side_effect=PermissionError("locked")):
            with self.assertRaisesRegex(PermissionError, "locked"):
                self.tick(107)
        self.assertFalse(hasattr(self.u, LIVE.STATE_NAME))
        self.u.unregister_slate_post_tick_callback.assert_called_once()
        self.assertEqual(self.receipt(), old)
        self.assertEqual(self.receipt()["status"], "observing")
        self.assertFalse(self.receipt()["runtime_ready"])

    def test_mid_observation_publication_error_still_unregisters(self):
        self.arm()
        with patch.object(LIVE, "write_report", side_effect=PermissionError("locked")):
            with self.assertRaisesRegex(PermissionError, "locked"):
                self.tick(101)
        self.assertFalse(hasattr(self.u, LIVE.STATE_NAME))
        self.u.unregister_slate_post_tick_callback.assert_called_once()
        self.assertEqual(self.receipt()["status"], "observing")

    def test_initial_report_lock_prevents_engine_queries(self):
        with patch.object(Path, "replace", side_effect=PermissionError("locked")), patch.object(LIVE.time, "sleep"):
            with self.assertRaisesRegex(PermissionError, "locked"):
                LIVE.run(self.u, self.report)
        self.u.Paths.get_project_file_path.assert_not_called()
        self.u.register_slate_post_tick_callback.assert_not_called()
        self.assertEqual(list(self.report.parent.iterdir()), [self.report])

    def test_transient_reader_lock_retries_complete_json(self):
        original = Path.replace
        count = [0]
        def replace(source, target):
            count[0] += 1
            json.loads(source.read_text())
            if count[0] <= 2:
                raise PermissionError("brief lock")
            return original(source, target)
        with patch.object(Path, "replace", replace), patch.object(LIVE.time, "sleep") as sleep:
            self.arm()
        self.assertEqual(sleep.call_count, 2)
        self.observer.complete("test cleanup")
        self.assertEqual(list(self.report.parent.iterdir()), [self.report])

    def test_historical_evidence_destinations_refused(self):
        for path in (LIVE.ROOT / ".local/hlck/dungeon-pie-smoke.json",
                     LIVE.ROOT / ".local/hlck/native-play-success.json",
                     LIVE.ROOT / ".local/hlck/pie-success/old/manifest.json"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "historical native Play evidence"):
                    LIVE.run(self.u, path)
        self.u.Paths.get_project_file_path.assert_not_called()


if __name__ == "__main__":
    unittest.main()

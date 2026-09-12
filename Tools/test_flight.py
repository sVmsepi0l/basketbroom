"""Regression for arena collision obstructing the native flying pawn.

Run through editor_bridge.py with the owned BB_Arena map loaded. Saves and fully
reloads that map, queries collision, checks the actual PIE spawn, and supplies native
AddMovementInput for half a second on two axes. Collision is never disabled.
The Slate callback writes .local/flight-test-results.json and normally ends PIE.
"""
import json
from pathlib import Path
import time
import traceback

import unreal


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local" / "flight-test-results.json"
ARGS = globals().get("BRIDGE_ARGS", {})
EXPECTED_START = (-4400.0, 0.0, 1400.0)
LEVEL_PATH = "/Basketbroom/Maps/BB_Arena"
INPUT_SECONDS = 0.5


def vector(values):
    return unreal.Vector(*[float(value) for value in values])


def xyz(value):
    return [round(value.x, 3), round(value.y, 3), round(value.z, 3)]


class FlightTests:
    def __init__(self):
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.started = time.monotonic()
        self.phase = "editor_collision_query"
        self.world = None
        self.pawn = None
        self.movement = None
        self.handle = None
        self.done = False
        self.may_manage_play = False
        self.snapshot = None
        self.results = []
        self.diagnostics = {}
        self.write_report("running")

    def now(self):
        return float(unreal.GameplayStatics.get_time_seconds(self.world))

    def write_report(self, status, error=None):
        data = {"status": status, "phase": self.phase,
                "engine": unreal.SystemLibrary.get_engine_version(),
                "elapsed_wall_seconds": round(time.monotonic() - self.started, 2),
                "input_seconds_per_axis": INPUT_SECONDS,
                "expected_spawn_cm": EXPECTED_START,
                "passed": sum(row["passed"] for row in self.results),
                "failed": sum(not row["passed"] for row in self.results),
                "tests": self.results, "diagnostics": self.diagnostics,
                "scope": "Native movement and collision; physical keyboard timing is a separate UI check"}
        if error:
            data["error"] = error
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def record(self, name, passed, detail):
        self.results.append({"name": name, "passed": bool(passed), "detail": detail})
        unreal.log("BASKETBROOM FLIGHT TEST {}: {} | {}".format(
            "PASS" if passed else "FAIL", name, detail))
        self.write_report("running")

    def check_loaded_editor_world(self):
        world = self.editor.get_editor_world()
        if world is None:
            raise RuntimeError("Load the saved Basketbroom arena before testing flight")
        if world.get_path_name() != LEVEL_PATH + ".BB_Arena":
            raise RuntimeError("Refusing to save or unload a map other than the owned Basketbroom arena")
        if not self.level.save_current_level():
            raise RuntimeError("Could not save the owned arena before the collision persistence check")
        # Test the serialized collision profile, not an in-memory override that
        # looks correct until the map is reopened. Do not retain the old world.
        world = None
        unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
        if not self.level.load_level(LEVEL_PATH):
            raise RuntimeError("Could not reload the saved arena for the collision persistence check")
        world = self.editor.get_editor_world()
        self.diagnostics["loaded_editor_world"] = world.get_path_name()
        self.diagnostics["arena_saved_unloaded_and_reloaded"] = True
        # The 100 cm clearance sphere is larger than DefaultPawn's 35 cm
        # collision sphere, and covers spawn plus each intended probe corridor.
        points = [EXPECTED_START, (-4150, 0, 1400), (-3900, 0, 1400),
                  (-4400, 0, 1650), (-4400, 0, 1900)]
        queries = []
        for point in points:
            hits = unreal.SystemLibrary.sphere_overlap_actors(
                world, vector(point), 100.0,
                [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1,
                 unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],
                unreal.StaticMeshActor, [])
            queries.append({"center_cm": point,
                            "overlapping_mesh_actors": [actor.get_actor_label() for actor in (hits or [])]})
        self.record("loaded_editor_spawn_and_flight_corridor_clear",
                    not any(row["overlapping_mesh_actors"] for row in queries), queries)

    def begin(self):
        if self.level.is_in_play_in_editor():
            raise RuntimeError("End the existing PIE session before testing the actual player spawn")
        for attribute in ("_basketbroom_playable_test", "_basketbroom_bot_test"):
            other = getattr(unreal, attribute, None)
            if other and not other.done:
                raise RuntimeError("Another Basketbroom PIE integration test is running")
        self.check_loaded_editor_world()
        self.phase = "waiting_for_world"
        self.may_manage_play = True
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.level.editor_request_begin_play()

    def find_world(self):
        self.world = self.editor.get_game_world()
        if self.world is None:
            return
        self.pawn = unreal.GameplayStatics.get_player_pawn(self.world, 0)
        if self.pawn is None:
            return
        self.first_spawn = self.pawn.get_actor_location()
        self.phase_started = self.now()
        self.phase = "spawn_settle"

    def prepare(self):
        pos = self.pawn.get_actor_location()
        displacement = (pos - vector(EXPECTED_START)).length()
        self.record("actual_pie_pawn_spawns_at_training_start",
                    self.pawn.get_class().get_name().startswith("BP_BBBroom") and displacement < 100.0,
                    {"pawn_class": self.pawn.get_class().get_name(), "first_position_cm": xyz(self.first_spawn),
                     "settled_position_cm": xyz(pos), "distance_from_start_cm": round(displacement, 3)})
        self.movement = self.pawn.get_movement_component()
        if self.movement is None:
            raise RuntimeError("Possessed broom has no native movement component")
        actors = unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.Actor)
        distractors = [actor for actor in actors if actor.get_class().get_name().startswith(
            ("BP_BBBot", "BP_BBBall", "BP_BBBludger", "BP_BBHazard"))]
        controller = unreal.GameplayStatics.get_player_controller(self.world, 0)
        self.diagnostics.update({"movement_class": self.movement.get_class().get_name(),
                                 "movement_active": self.movement.is_active(),
                                 "movement_tick_enabled": self.movement.is_component_tick_enabled(),
                                 "pawn_tick_enabled": self.pawn.is_actor_tick_enabled(),
                                 "move_input_ignored": controller.is_move_input_ignored()})
        self.snapshot = {"position": pos, "rotation": self.pawn.get_actor_rotation(),
                         "pawn_tick": self.pawn.is_actor_tick_enabled(),
                         "actors": [(actor, actor.is_actor_tick_enabled()) for actor in distractors]}
        for actor in distractors:
            actor.set_actor_tick_enabled(False)
        # Disable Blueprint key polling while the fixture provides continuous
        # native input. FloatingPawnMovement keeps its own component tick and
        # uses the real pawn collision sphere throughout both probes.
        self.pawn.set_actor_tick_enabled(False)
        self.start_axis("horizontal", (1, 0, 0))

    def stop_input(self):
        self.pawn.consume_movement_input_vector()
        self.movement.stop_movement_immediately()

    def start_axis(self, axis, direction):
        self.stop_input()
        self.phase = axis
        self.direction = vector(direction)
        self.axis_start = self.pawn.get_actor_location()
        self.phase_started = self.now()
        self.input_samples = 0
        self.max_velocity = 0.0
        self.write_report("running")

    def finish_axis(self):
        end = self.pawn.get_actor_location()
        delta = end - self.axis_start
        elapsed = self.now() - self.phase_started
        self.stop_input()
        if self.phase == "horizontal":
            passed = delta.x > 100 and abs(delta.y) < 50 and abs(delta.z) < 50
            name = "native_horizontal_flight_crosses_100cm_without_height_loss"
        else:
            passed = delta.z > 100 and abs(delta.x) < 50 and abs(delta.y) < 50
            name = "native_vertical_flight_crosses_100cm_without_lateral_drift"
        # Background editor throttling can span the whole probe in two Slate
        # callbacks. One applied native input is sufficient evidence when the
        # collision engine produces both measurable speed and displacement.
        self.record(name, passed and self.input_samples >= 1 and self.max_velocity > 100.0,
                    {"start_cm": xyz(self.axis_start), "end_cm": xyz(end),
                     "delta_cm": xyz(delta), "native_input_samples": self.input_samples,
                     "elapsed_game_seconds": round(elapsed, 3),
                     "max_velocity_cm_per_second": round(self.max_velocity, 3)})
        if self.phase == "horizontal":
            self.start_axis("vertical", (0, 0, 1))
        else:
            self.finish()

    def tick(self, delta):
        if self.done:
            return
        try:
            if time.monotonic() - self.started > 90:
                raise TimeoutError("Flight integration test exceeded 90 wall seconds")
            if self.phase == "waiting_for_world":
                self.find_world()
                return
            if not self.level.is_in_play_in_editor():
                raise RuntimeError("PIE ended before flight verification finished")
            if self.phase == "spawn_settle":
                if self.now() - self.phase_started >= 0.25:
                    self.prepare()
            elif self.phase in ("horizontal", "vertical"):
                self.max_velocity = max(self.max_velocity, self.pawn.get_velocity().length())
                if self.now() - self.phase_started >= INPUT_SECONDS:
                    self.finish_axis()
                else:
                    # Do not force input: a broken possession/ignore-input
                    # state must fail, just as it would during normal play.
                    self.pawn.add_movement_input(self.direction, 1.0, False)
                    self.input_samples += 1
        except Exception:
            self.finish(traceback.format_exc())

    def finish(self, error=None):
        self.done = True
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        try:
            if self.snapshot and self.level.is_in_play_in_editor():
                self.stop_input()
                self.pawn.set_actor_tick_enabled(self.snapshot["pawn_tick"])
                for actor, tick_enabled in self.snapshot["actors"]:
                    actor.set_actor_tick_enabled(tick_enabled)
                if ARGS.get("leave_play", False) and not error:
                    self.pawn.set_actor_location(self.snapshot["position"], False, True)
                    self.pawn.set_actor_rotation(self.snapshot["rotation"], True)
            if (self.may_manage_play and self.level.is_in_play_in_editor()
                    and (not ARGS.get("leave_play", False) or error)):
                self.level.editor_request_end_play()
        except Exception:
            error = (error or "") + "\nPIE cleanup: " + traceback.format_exc()
            if self.may_manage_play and self.level.is_in_play_in_editor():
                self.level.editor_request_end_play()
        status = "error" if error else (
            "passed" if len(self.results) == 4 and all(row["passed"] for row in self.results) else "failed")
        self.write_report(status, error)
        unreal.log("BASKETBROOM FLIGHT TESTS {}: {}".format(status.upper(), REPORT))


previous = getattr(unreal, "_basketbroom_flight_test", None)
if previous and not previous.done:
    raise RuntimeError("A Basketbroom flight test is already running")
test = FlightTests()
try:
    test.begin()
except Exception:
    test.finish(traceback.format_exc())
    raise
unreal._basketbroom_flight_test = test
RESULT = {"status": "started", "report": str(REPORT), "expected_cases": 4}

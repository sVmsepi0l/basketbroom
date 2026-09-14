"""Actual generated training-Blueprint roof checks; no native input bridge.

Run through editor_bridge.py after stage_training_pyramid.py. Owns fresh PIE on
BB_Arena, then ends PIE and restores the original saved map. Physical fixtures
write only actor transforms and free-ball Velocity, never score, ownership,
Cooldown, graph positions, timers or activation. Actual training E pickup and
held-ball graph execution are explicitly NOT covered without a real key source.
--list prints planned coverage without opening Unreal.
"""
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import time
import traceback

try:
    import unreal
except ImportError:
    unreal = None

ROOT = Path(__file__).resolve().parents[1]
ARGS = {"max_wall_seconds": 100, **globals().get("BRIDGE_ARGS", {})}
REPORT = ROOT / ".local/training-pyramid-test-results.json"
CASES = (
    "actual_training_blueprints_and_live_graph_clock",
    "training_positive_x_face_rebounds", "training_negative_x_face_rebounds",
    "training_positive_y_face_rebounds", "training_negative_y_face_rebounds",
    "old_crown_plane_is_hollow_without_home_reset",
    "large_endpoint_overshoot_stays_contained_and_rebounds",
    "manager_graph_confines_default_pawn_sphere_at_faces_apex_and_corner",
    "roof_graph_preserves_scores_identity_and_live_clock_without_crown_message",
    "owned_pie_ended_and_original_saved_map_restored",
)
HALF_X, HALF_Y, EAVE, APEX = 6850.8, 3200.4, 4206.24, 6309.36
SX, SY = (APEX-EAVE)/HALF_X, (APEX-EAVE)/HALF_Y
PLANES = ((SX, 0, 1), (-SX, 0, 1), (0, SY, 1), (0, -SY, 1))
_spec = importlib.util.spec_from_file_location("_bb_training_roof_receipts", ROOT / "Tools/native_test_receipts.py")
receipts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(receipts)


def prop(obj, name):
    for key in (name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()):
        try:
            return obj.get_editor_property(key)
        except Exception:
            pass
    raise RuntimeError("Required graph property is unavailable: "+name)


def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def vec(value):
    return unreal.Vector(*map(float, value))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def normal(face):
    n = PLANES[face]
    length = math.sqrt(dot(n, n))
    return tuple(v/length for v in n)


def inside(point, radius, tolerance=.2):
    return (abs(point[0])+radius <= HALF_X+tolerance and abs(point[1])+radius <= HALF_Y+tolerance
            and point[2] >= radius-tolerance
            and all(dot(n, point)+radius*math.sqrt(dot(n, n)) <= APEX+tolerance for n in PLANES))


class TrainingPyramidTests:
    def __init__(self):
        self.started = time.monotonic()
        self.phase = "preflight"
        self.done = False
        self.final_status = "not_run"
        self.results = {}
        self.events = []
        self.provenance = {}
        self.world = self.manager = self.pawn = self.ball = None
        self.original_map = None
        self.owns_play = False
        self.map_restored = False
        self.handle = self.sequence = self.waiting = None
        self.error = None
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem) if unreal else None
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem) if unreal else None
        self.write("not_run")

    def write(self, status):
        data = receipts.single_world_payload(self, CASES, status, self.error,
                                              unreal.SystemLibrary.get_engine_version() if unreal else None)
        data.update(scope="actual generated BP_BBMatch/BP_BBBall graph ticks in disposable BB_Arena training PIE",
                    fixture_policy="Only free-ball Velocity and actor transforms, CPU/other-ball tick isolation; no score, "
                                   "custody, cooldown, graph position variables or clock writes.",
                    cleanup=dict(owns_pie=self.owns_play, editor_map_restored=self.map_restored),
                    not_covered=["actual E pickup and held-ball graph execution (no reflected training input bridge)",
                                 "physical keyboard/controller or visual quality", "native regulation/Bloodbroom gameplay",
                                 "network replication", "continuous native sphere sweep or shot adjudication"])
        receipts.write_json_atomic(REPORT, data)

    def require(self, value, reason):
        if not value:
            raise RuntimeError(reason)

    def record(self, name, passed, **detail):
        self.require(name in CASES and name not in self.results, "Unknown or repeated test name")
        self.results[name] = dict(status="passed" if passed else "failed", detail=detail)
        self.write("running")

    def clean(self):
        saving = unreal.EditorLoadingAndSavingUtils
        dirty = list(saving.get_dirty_map_packages())+list(saving.get_dirty_content_packages())
        self.require(not dirty, "Preserving unsaved packages; cannot switch editor maps during this test")

    def now(self):
        return float(unreal.GameplayStatics.get_time_seconds(self.world))

    def scores(self):
        return [int(prop(self.manager, "TealScore")), int(prop(self.manager, "CopperScore"))]

    def begin(self):
        if unreal is None:
            self.error = "Run in UE5.8 after training graph staging; no runtime checks executed."
            self.done = True
            self.write("not_run")
            return False
        self.require(unreal.SystemLibrary.get_engine_version().startswith("5.8."), "UE5.8 is required")
        self.require(Path(unreal.Paths.project_dir()).resolve() == (ROOT / "DevelopmentHarness").resolve(), "Wrong editor project")
        self.require(not self.level.is_in_play_in_editor(), "Existing PIE session must remain untouched")
        for name in ("_basketbroom_native_test", "_basketbroom_native_network_test", "_basketbroom_playable_test"):
            other = getattr(unreal, name, None)
            self.require(not other or other.done, "Another game test is active")
        world = self.editor.get_editor_world()
        self.original_map = world.get_path_name().split(".")[0] if world else None
        self.require(self.original_map in ("/Basketbroom/Maps/BB_Arena", "/Basketbroom/Maps/BB_Regulation"),
                     "Open a saved Basketbroom map before this bounded test")
        self.clean()
        if self.original_map != "/Basketbroom/Maps/BB_Arena":
            self.require(self.level.load_level("/Basketbroom/Maps/BB_Arena"), "Could not load saved training map")
        self.provenance.update(original_map=self.original_map, test_map="/Basketbroom/Maps/BB_Arena", editor_assets_saved=False)
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.owns_play = True
        self.phase = "waiting_for_training_world"
        self.level.editor_request_begin_play()
        self.write("running")
        return True

    def setup(self):
        self.world = self.editor.get_game_world()
        if self.world is None:
            return False
        actors = list(unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.Actor))
        managers = [a for a in actors if a.get_class().get_name().startswith("BP_BBMatch")]
        balls = [a for a in actors if a.get_class().get_name().startswith("BP_BBBall")]
        self.pawn = unreal.GameplayStatics.get_player_pawn(self.world, 0)
        if len(managers) != 1 or not balls or self.pawn is None:
            return False
        self.manager = managers[0]
        free = [a for a in balls if int(prop(a, "Kind")) == 0 and not prop(a, "Held") and int(prop(a, "BotOwner")) < 0]
        self.require(free, "Fresh training world needs a naturally free Quaffle")
        self.ball = free[0]
        for actor in actors:
            if actor.get_class().get_name().startswith(("BP_BBBot", "BP_BBHazard", "BP_BBBludger")):
                actor.set_actor_tick_enabled(False)
        for ball in balls:
            ball.set_actor_tick_enabled(False)
        movement = self.pawn.get_movement_component()
        if movement:
            movement.stop_movement_immediately()
            movement.set_component_tick_enabled(False)
        self.pawn.set_actor_location(vec((-3000, -1800, 1300)), False, True)
        self.identity = self.ball.get_path_name()
        self.home = xyz(prop(self.ball, "Home"))
        self.initial_scores = self.scores()
        self.initial_clock = float(prop(self.manager, "SecondsLeft"))
        self.provenance.update(pie_world=self.world.get_path_name(), ball_class=self.ball.get_class().get_path_name(),
                               manager_class=self.manager.get_class().get_path_name(), pawn_class=self.pawn.get_class().get_path_name(),
                               ball_identity=self.identity, original_home=self.home)
        self.phase = "running_training_cases"
        self.sequence = self.scenarios()
        self.advance()
        return True

    def fixture(self, point, velocity):
        self.require(not prop(self.ball, "Held") and int(prop(self.ball, "BotOwner")) == -1,
                     "Only a genuinely free ball may be physically arranged")
        self.ball.set_actor_location(vec(point), False, True)
        for key in ("Velocity", "velocity"):
            try:
                self.ball.set_editor_property(key, vec(velocity))
                break
            except Exception:
                pass
        else:
            raise RuntimeError("Blueprint Velocity physical fixture is unavailable")
        self.ball.set_actor_tick_enabled(True)
        self.events.append(dict(kind="physical_fixture", position=point, velocity=velocity, world_seconds=self.now()))

    def snapshot(self):
        return dict(position=xyz(self.ball.get_actor_location()), velocity=xyz(prop(self.ball, "Velocity")),
                    held=bool(prop(self.ball, "Held")), bot_owner=int(prop(self.ball, "BotOwner")),
                    message=str(prop(self.manager, "Message")), seconds=self.now(), score=self.scores())

    def wait(self, seconds, sample=None, until=None):
        return dict(seconds=seconds, sample=sample, until=until)

    def scenarios(self):
        yield self.wait(.2)
        self.record(CASES[0], isinstance(self.pawn, unreal.DefaultPawn) and self.pawn.get_class().get_name().startswith("BP_BBBroom")
                    and float(prop(self.manager, "SecondsLeft")) < self.initial_clock
                    and not prop(self.manager, "MatchOver"), provenance=self.provenance,
                    clock_before=self.initial_clock, clock_after=float(prop(self.manager, "SecondsLeft")))
        faces = ((4000, 0, APEX-SX*4000), (-4000, 0, APEX-SX*4000),
                 (0, 1800, APEX-SY*1800), (0, -1800, APEX-SY*1800))
        for face, point in enumerate(faces):
            n = normal(face)
            start = tuple(point[i]-n[i]*133 for i in range(3))
            velocity = tuple(2200*n[i] for i in range(3))
            self.require(inside(start, 33), "Face fixture must begin wholly inside")
            self.fixture(start, velocity)
            rows = [self.snapshot()]
            yield self.wait(1.3, lambda: rows.append(self.snapshot()),
                            lambda: dot(xyz(prop(self.ball, "Velocity")), n) < -100)
            self.ball.set_actor_tick_enabled(False)
            correct = (len(rows) > 1 and dot(rows[-1]["velocity"], n) < -100
                       and all(inside(row["position"], 33) and not row["held"] and row["bot_owner"] == -1 for row in rows)
                       and self.scores() == self.initial_scores)
            # Gravity alone cannot turn this normal-directed 2200cm/s launch in
            # the bounded 1.3s window; reversal establishes an actual roof graph response.
            self.record(CASES[1+face], correct, face=face, outward_normal=n, samples=rows)
            self.require(correct, "Generated roof rebound failed on face "+str(face))
        self.fixture((0, 0, 4090), (0, 0, 1250))
        rows = []
        yield self.wait(1.4, lambda: rows.append(self.snapshot()))
        self.ball.set_actor_tick_enabled(False)
        self.record(CASES[5], rows and rows[-1]["position"][2] > EAVE+300
                    and all(not row["held"] and row["bot_owner"] == -1 and "CROWN" not in row["message"].upper()
                            for row in rows) and self.scores() == self.initial_scores,
                    samples=rows, original_home=self.home, old_plane_cm=EAVE)
        self.fixture((0, 0, APEX-300), (0, 0, 55000))
        rows = [self.snapshot()]
        yield self.wait(1, lambda: rows.append(self.snapshot()), lambda: prop(self.ball, "Velocity").z < -100)
        self.ball.set_actor_tick_enabled(False)
        self.record(CASES[6], len(rows) > 1 and rows[-1]["velocity"][2] < -100
                    and all(inside(row["position"], 33) for row in rows)
                    and self.scores() == self.initial_scores and self.ball.get_path_name() == self.identity,
                    samples=rows, fixture_speed_cm_per_second=55000)
        sphere = self.pawn.get_component_by_class(unreal.SphereComponent)
        self.require(sphere is not None, "Training DefaultPawn sphere is unavailable")
        radius = float(sphere.get_scaled_sphere_radius())
        bounds = []
        for point in ((0, 0, APEX+700), (5000, 0, 5900), (-5000, 0, 5900),
                      (0, 2500, 5900), (0, -2500, 5900), (8000, 5000, 7000)):
            self.pawn.set_actor_location(vec(point), False, True)
            yield self.wait(.18)
            after = xyz(self.pawn.get_actor_location())
            bounds.append(dict(fixture=point, actual=after, inside=inside(after, radius),
                               side_insets=abs(after[0]) <= 6710.2 and abs(after[1]) <= 3090.2))
        self.record(CASES[7], all(row["inside"] and row["side_insets"] for row in bounds), sphere_radius_cm=radius, samples=bounds)
        self.record(CASES[8], self.scores() == self.initial_scores and self.ball.get_path_name() == self.identity
                    and xyz(prop(self.ball, "Home")) == self.home and float(prop(self.manager, "SecondsLeft")) < self.initial_clock
                    and not prop(self.manager, "MatchOver") and "CROWN" not in str(prop(self.manager, "Message")).upper()
                    and not prop(self.ball, "Held") and not prop(self.manager, "HasBall"),
                    score=self.scores(), clock_before=self.initial_clock, clock_after=float(prop(self.manager, "SecondsLeft")),
                    message=str(prop(self.manager, "Message")), ball_identity=self.ball.get_path_name())

    def advance(self):
        try:
            self.waiting = next(self.sequence)
            self.waiting.update(start=self.now(), wall=time.monotonic(), initial_frame=self.now())
        except StopIteration:
            status = "passed" if len(self.results) == len(CASES)-1 and all(r["status"] == "passed" for r in self.results.values()) else "failed"
            self.finish(status)

    def finish(self, status, error=None):
        self.final_status, self.error = status, error or self.error
        self.phase = "ending_owned_pie"
        self.cleanup_started = time.monotonic()
        if self.owns_play and self.level and self.level.is_in_play_in_editor():
            self.level.editor_request_end_play()
        if self.handle is None and unreal:
            self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.write("running")

    def cleanup(self):
        if self.owns_play and self.level.is_in_play_in_editor():
            self.require(time.monotonic()-self.cleanup_started < 20, "Owned PIE did not end")
            return
        if self.original_map:
            current = self.editor.get_editor_world()
            name = current.get_path_name().split(".")[0] if current else None
            if name != self.original_map:
                self.clean()
                self.require(self.level.load_level(self.original_map), "Could not restore original saved map")
            current = self.editor.get_editor_world()
            self.map_restored = current is not None and current.get_path_name().split(".")[0] == self.original_map
        if CASES[9] not in self.results and self.owns_play:
            self.record(CASES[9], self.map_restored and not self.level.is_in_play_in_editor(), original_map=self.original_map)
        if self.owns_play and not self.map_restored:
            self.final_status = "error"
        self.done = True
        self.phase = "complete"
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        self.write(self.final_status)

    def tick(self, delta):
        if self.done:
            return
        try:
            if self.phase == "ending_owned_pie":
                self.cleanup()
                return
            self.require(time.monotonic()-self.started <= float(ARGS["max_wall_seconds"]), "Training roof test exceeded bounded wall time")
            if self.phase == "waiting_for_training_world":
                self.setup()
                return
            self.require(self.level.is_in_play_in_editor(), "Owned PIE ended unexpectedly")
            if self.waiting:
                if self.waiting["sample"]:
                    self.waiting["sample"]()
                advanced = self.now() > self.waiting["initial_frame"]
                ready = bool(self.waiting["until"]()) if self.waiting["until"] else False
                if advanced and (ready or self.now()-self.waiting["start"] >= self.waiting["seconds"]):
                    self.advance()
                else:
                    self.require(time.monotonic()-self.waiting["wall"] < 20, "PIE world clock stalled")
        except Exception:
            if self.phase == "ending_owned_pie":
                self.done = True
                self.final_status = "error"
                self.error = (self.error or "")+"\nCleanup: "+traceback.format_exc()
                if self.handle is not None:
                    unreal.unregister_slate_post_tick_callback(self.handle)
                    self.handle = None
                self.write("error")
            else:
                self.finish("error", traceback.format_exc())


def main():
    if unreal is None and "--list" in sys.argv:
        return dict(status="not_run", planned_cases=list(CASES), count=len(CASES),
                    training_key_pickup="not covered: no reflected input bridge and no custody injection")
    runner = TrainingPyramidTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and (started or runner.owns_play):
        unreal._basketbroom_playable_test = runner
    return dict(status="started" if started else runner.final_status, report=str(REPORT), planned_cases=len(CASES))


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

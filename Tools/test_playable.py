"""Exercise compiled Basketbroom Blueprints in a real Play In Editor world.

Run after staging BB_Arena through editor_bridge.py. The bridge returns promptly;
the Slate callback writes .local/playable-test-results.json when tests finish.
Only PIE copies are changed. The test stops PIE afterward unless leave_play=True.
It seeds positions/velocities, then waits for the compiled game graphs to act.
This historical broad fixture suite also resets rule fields between cases; use
test_training_pyramid.py for current physical-only roof checks without score,
custody or clock writes. Neither suite claims actual keyboard pickup coverage.
Keyboard pickup/capture and visual feel still need an interactive play check.
"""

import importlib.util as _arena_importlib
from pathlib import Path as _ArenaPath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)
import json
import pathlib
import re
import time
import traceback

import unreal

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local" / "playable-test-results.json"
ARGS = globals().get("BRIDGE_ARGS", {})


def prop(actor, name, value=...):
    """Accept original Blueprint names and Python's normalized spelling."""
    names = (name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower())
    last_error = None
    for candidate in names:
        try:
            if value is ...:
                return actor.get_editor_property(candidate)
            actor.set_editor_property(candidate, value)
            return value
        except Exception as error:
            last_error = error
    raise last_error


def vector(values):
    return unreal.Vector(float(values[0]), float(values[1]), float(values[2]))


def position(actor, values):
    actor.set_actor_location(vector(values), False, True)


class PlayableTests:
    def __init__(self):
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.started = time.monotonic()
        self.phase = "waiting_for_world"
        self.handle = None
        self.world = None
        self.manager = None
        self.pawn = None
        self.balls = []
        self.opponents = []
        self.active_ball = None
        self.cases = []
        self.case_index = -1
        self.case_started = 0
        self.results = []
        self.snapshot = None
        self.done = False
        self.write_report("running")

    def write_report(self, status, error=None):
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        data = {"status": status, "engine": unreal.SystemLibrary.get_engine_version(),
                "elapsed_wall_seconds": round(time.monotonic() - self.started, 2),
                "tests": self.results,
                "passed": sum(row["passed"] for row in self.results),
                "failed": sum(not row["passed"] for row in self.results),
                "manual_checks": ["WASD and vertical flight, mouse aim and camera feel",
                                  "E pickup and one carried ball across competing pickups",
                                  "Mouse release and hold E for chase-ball capture",
                                  "HUD readability and arena presentation"]}
        if error:
            data["error"] = error
        REPORT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def record(self, name, passed, detail):
        self.results.append({"name": name, "passed": bool(passed), "detail": detail})
        unreal.log("BASKETBROOM TEST {}: {} | {}".format("PASS" if passed else "FAIL", name, detail))
        self.write_report("running")

    def begin(self):
        if self.level.is_in_play_in_editor() and not ARGS.get("reuse_play", False):
            raise RuntimeError("A PIE session already exists; end it or explicitly set reuse_play=True")
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        if not self.level.is_in_play_in_editor():
            self.level.editor_request_begin_play()

    def setup_world(self):
        self.world = self.editor.get_game_world()
        if not self.world:
            return False
        actors = unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.Actor)
        managers = [actor for actor in actors if actor.get_class().get_name().startswith("BP_BBMatch")]
        self.balls = [actor for actor in actors if actor.get_class().get_name().startswith("BP_BBBall")]
        self.opponents = [actor for actor in actors if actor.get_class().get_name().startswith(
            ("BP_BBBot", "BP_BBHazard", "BP_BBBludger"))]
        self.pawn = unreal.GameplayStatics.get_player_pawn(self.world, 0)
        if not managers or not self.balls or not self.pawn:
            return False
        self.manager = managers[0]
        self.active_ball = next((ball for ball in self.balls if prop(ball, "Kind") == 0), self.balls[0])
        self.initial_seconds = float(prop(self.manager, "SecondsLeft"))
        self.initial_time = unreal.GameplayStatics.get_time_seconds(self.world)
        self.phase = "warmup"
        return True

    def initialize_cases(self):
        self.record("playable_world", len(self.balls) >= 5 and self.pawn.get_class().get_name().startswith("BP_BBBroom"),
                    {"ball_count": len(self.balls), "pawn": self.pawn.get_class().get_name(),
                     "manager": self.manager.get_class().get_name()})
        self.record("timer_default_and_tick", self.initial_seconds > 0 and float(prop(self.manager, "SecondsLeft")) < self.initial_seconds,
                    {"initial_seconds": self.initial_seconds, "current_seconds": float(prop(self.manager, "SecondsLeft"))})
        fields = ("Kind", "Held", "BotOwner", "BotPosition", "Cooldown", "CatchTime", "P", "OldP", "Velocity", "Home")
        manager_fields = ("TealScore", "CopperScore", "HasBall", "MatchOver", "SecondsLeft", "Elapsed", "Stun", "Message")
        self.snapshot = {"manager": {name: prop(self.manager, name) for name in manager_fields},
                         "balls": [(ball, ball.get_actor_location(), {name: prop(ball, name) for name in fields}) for ball in self.balls],
                         "opponents": [(actor, actor.is_actor_tick_enabled()) for actor in self.opponents],
                         "pawn_location": self.pawn.get_actor_location()}
        for actor in self.opponents:
            actor.set_actor_tick_enabled(False)
        self.cases = [
            ("quaffle_east_goal_13", lambda: self.launch(0, ((dimensions.GOAL_PLANE_X-100.8), 0, 2103.12), (2000, 0, 0)), lambda: self.check_score(13, 0)),
            ("quark_small_goal_37", lambda: self.launch(1, ((dimensions.GOAL_PLANE_X-100.8), 0, 3048), (2000, 0, 0)), lambda: self.check_score(37, 0)),
            ("quaffle_west_goal_13", lambda: self.launch(0, (-(dimensions.GOAL_PLANE_X-100.8), 0, 2103.12), (-2000, 0, 0)), lambda: self.check_score(0, 13)),
            ("quark_rejected_by_large_hoop", lambda: self.launch(1, ((dimensions.GOAL_PLANE_X-100.8), 0, 2103.12), (2000, 0, 0)), lambda: self.check_score(0, 0)),
            ("quaffle_rejected_by_small_hoop", lambda: self.launch(0, ((dimensions.GOAL_PLANE_X-100.8), 0, 3048), (2000, 0, 0)), lambda: self.check_score(0, 0)),
            ("large_hoop_rim_clearance", lambda: self.launch(0, ((dimensions.GOAL_PLANE_X-100.8), 350, 2103.12), (2000, 0, 0)), lambda: self.check_score(0, 0)),
            ("side_net_rebound", lambda: self.launch(0, (0, dimensions.HALF_WIDTH-100.4, 1600), (0, 1000, 0)), self.check_rebound),
            ("trampoline_floor_rebound", lambda: self.launch(0, (0, 0, 75), (0, 0, -500)), self.check_floor),
            ("hollow_pyramid_free_ball_crosses_old_plane", lambda: self.launch(0, (0, 0, dimensions.EAVE_HEIGHT-16.24), (0, 0, 1000)), self.check_hollow_pyramid),
            ("closed_pyramid_free_ball_rebounds", self.prepare_roof_bounce, self.check_roof_bounce),
            ("snipe_path_moves", self.prepare_chase, self.check_chase),
            ("snipe_timeout_returns", self.prepare_timeout, self.check_timeout),
            ("training_clock_ends_match", self.prepare_clock, self.check_clock),
        ]
        self.next_case()

    def reset(self):
        for name, value in {"TealScore": 0, "CopperScore": 0, "HasBall": False,
                            "MatchOver": False, "SecondsLeft": 300.0, "Stun": 0.0, "Message": "TEST"}.items():
            prop(self.manager, name, value)
        position(self.pawn, (-3000, -1800, 900))
        for ball in self.balls:
            prop(ball, "Cooldown", 100000.0)
            prop(ball, "Held", False)
            # A rider can acquire a ball during warmup before opponents freeze.
            # Isolated physics fixtures must release that native ownership.
            prop(ball, "BotOwner", -1)
            prop(ball, "CatchTime", 0.0)
            prop(ball, "Velocity", vector((0, 0, 0)))

    def launch(self, kind, pos, velocity):
        prop(self.active_ball, "Kind", kind)
        prop(self.active_ball, "Home", vector((0, 0, 900)))
        prop(self.active_ball, "Cooldown", 0.0)
        prop(self.active_ball, "Velocity", vector(velocity))
        position(self.active_ball, pos)

    def check_score(self, teal, copper):
        observed = (int(prop(self.manager, "TealScore")), int(prop(self.manager, "CopperScore")))
        return observed == (teal, copper), {"expected": [teal, copper], "observed": observed}

    def check_rebound(self):
        vel = prop(self.active_ball, "Velocity")
        return abs(vel.y + 750.0) < 3.0, {"velocity_y": vel.y, "expected": -750.0}

    def check_floor(self):
        pos = self.active_ball.get_actor_location()
        vel = prop(self.active_ball, "Velocity")
        return pos.z >= 65 and vel.z > 0, {"height": pos.z, "velocity_z": vel.z}

    def roof_contains_ball(self):
        point = self.active_ball.get_actor_location()
        radius = 33 if int(prop(self.active_ball, "Kind")) == 0 else 24
        sx, sy = (dimensions.APEX_HEIGHT-dimensions.EAVE_HEIGHT)/dimensions.HALF_LENGTH, (dimensions.APEX_HEIGHT-dimensions.EAVE_HEIGHT)/dimensions.HALF_WIDTH
        return (abs(point.x)+radius <= dimensions.HALF_LENGTH+.2 and abs(point.y)+radius <= dimensions.HALF_WIDTH+.2
                and point.z >= radius-.2
                and point.z+sx*abs(point.x)+radius*(1+sx*sx)**.5 <= dimensions.APEX_HEIGHT+.2
                and point.z+sy*abs(point.y)+radius*(1+sy*sy)**.5 <= dimensions.APEX_HEIGHT+.2)

    def check_hollow_pyramid(self):
        message = str(prop(self.manager, "Message"))
        pos = self.active_ball.get_actor_location()
        held = bool(prop(self.active_ball, "Held"))
        return (pos.z > dimensions.EAVE_HEIGHT and self.roof_contains_ball() and not held
                and "CROWN" not in message.upper() and self.check_score(0, 0)[0]), {
                    "message": message, "height": pos.z, "held": held,
                    "scope": "free-ball physical fixture; old horizontal plane has no reset"}

    def prepare_roof_bounce(self):
        # Start wholly inside and let the compiled graph cross the +Y slope.
        # This replaces the old Held=True fixture; no pickup is claimed here.
        self.launch(0, (0, 1600*dimensions.LINEAR_SCALE, dimensions.APEX_HEIGHT-1409.36), (0, 2200, 3300))

    def check_roof_bounce(self):
        velocity = prop(self.active_ball, "Velocity")
        slope = (dimensions.APEX_HEIGHT-dimensions.EAVE_HEIGHT)/dimensions.HALF_WIDTH
        outward_speed = (slope*velocity.y+velocity.z)/(1+slope*slope)**.5
        message = str(prop(self.manager, "Message"))
        return (outward_speed < -100 and self.roof_contains_ball()
                and not prop(self.active_ball, "Held") and "CROWN" not in message.upper()
                and self.check_score(0, 0)[0]), {
                    "position": str(self.active_ball.get_actor_location()), "velocity": str(velocity),
                    "outward_normal_speed": outward_speed, "message": message,
                    "scope": "actual free-ball generated-graph rebound; keyboard pickup not exercised"}

    def prepare_chase(self):
        self.launch(2, (0, 0, -3000), (0, 0, 0))
        self.chase_start = self.active_ball.get_actor_location()

    def check_chase(self):
        pos = self.active_ball.get_actor_location()
        moved = (pos - self.chase_start).length()
        return moved > 100 and abs(pos.x) < 4300*dimensions.LINEAR_SCALE+1 and abs(pos.y) < 2050*dimensions.LINEAR_SCALE+1 and 1250*dimensions.LINEAR_SCALE-1 < pos.z < 3150*dimensions.LINEAR_SCALE+1, {"position": str(pos), "distance": moved}

    def prepare_timeout(self):
        self.launch(2, (0, 0, -3000), (0, 0, 0))
        prop(self.active_ball, "Cooldown", 0.08)

    def check_timeout(self):
        pos = self.active_ball.get_actor_location()
        return pos.z > 1200 and prop(self.active_ball, "Cooldown") <= 0, {"height": pos.z, "cooldown": float(prop(self.active_ball, "Cooldown"))}

    def prepare_clock(self):
        prop(self.manager, "SecondsLeft", 0.05)

    def check_clock(self):
        over = bool(prop(self.manager, "MatchOver"))
        seconds = float(prop(self.manager, "SecondsLeft"))
        return over and seconds == 0, {"match_over": over, "seconds_left": seconds}

    def next_case(self):
        self.case_index += 1
        if self.case_index >= len(self.cases):
            self.finish()
            return
        self.reset()
        self.cases[self.case_index][1]()
        self.case_started = unreal.GameplayStatics.get_time_seconds(self.world)
        self.case_wall_started = time.monotonic()
        self.phase = "running_case"

    def tick(self, delta):
        if self.done:
            return
        try:
            if time.monotonic() - self.started > 150:
                raise TimeoutError("PIE integration tests exceeded 150 seconds")
            if self.phase == "waiting_for_world":
                self.setup_world()
            elif self.phase == "warmup":
                if unreal.GameplayStatics.get_time_seconds(self.world) - self.initial_time >= 0.4:
                    self.initialize_cases()
            elif self.phase == "running_case":
                if not self.level.is_in_play_in_editor():
                    raise RuntimeError("PIE ended before runtime verification finished")
                if unreal.GameplayStatics.get_time_seconds(self.world) - self.case_started >= 0.25:
                    passed, detail = self.cases[self.case_index][2]()
                    self.record(self.cases[self.case_index][0], passed, detail)
                    self.next_case()
                elif time.monotonic() - self.case_wall_started > 20:
                    raise TimeoutError("PIE world did not advance game time")
        except Exception:
            self.finish(traceback.format_exc())

    def finish(self, error=None):
        self.done = True
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        if ARGS.get("leave_play", False) and self.snapshot and not error:
            for name, value in self.snapshot["manager"].items():
                prop(self.manager, name, value)
            for ball, pos, fields in self.snapshot["balls"]:
                for name, value in fields.items():
                    prop(ball, name, value)
                ball.set_actor_location(pos, False, True)
            for actor, tick_enabled in self.snapshot["opponents"]:
                actor.set_actor_tick_enabled(tick_enabled)
            self.pawn.set_actor_location(self.snapshot["pawn_location"], False, True)
        elif self.level.is_in_play_in_editor():
            self.level.editor_request_end_play()
        status = "error" if error else ("passed" if all(row["passed"] for row in self.results) else "failed")
        self.write_report(status, error)
        unreal.log("BASKETBROOM RUNTIME TESTS {}: {}".format(status.upper(), REPORT))


previous = getattr(unreal, "_basketbroom_playable_test", None)
if previous and not previous.done:
    raise RuntimeError("A Basketbroom runtime test is already running")
test = PlayableTests()
try:
    test.begin()
except Exception:
    test.done = True
    test.write_report("error", traceback.format_exc())
    raise
unreal._basketbroom_playable_test = test
RESULT = {"status": "started", "report": str(REPORT), "expected_cases": 15}

"""exercise compiled basketbroom blueprints in a real play in editor world.

run after staging bb_arena through editor_bridge.py. the bridge returns promptly;
the slate callback writes .local/playable-test-results.json when tests finish.
only pie copies are changed. the test stops pie afterward unless leave_play=True.
it seeds positions/velocities, then waits for the compiled game graphs to act.
this historical broad fixture suite also resets rule fields between cases; use
test_training_pyramid.py for current physical-only roof checks without score,
custody or clock writes. neither suite claims actual keyboard pickup coverage.
keyboard pickup/capture and visual feel still need an interactive play check.
"""

import importlib.util as _arena_importlib
from pathlib import path as _arenapath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)
import json
import pathlib
import re
import time
import traceback

import unreal

root = pathlib.Path(__file__).resolve().parents[1]
report = root / ".local" / "playable-test-results.json"
args = globals().get("BRIDGE_ARGS", {})


def prop(actor, name, value=...):
    """accept original blueprint names and python's normalized spelling."""
    names = (name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower())
    last_error = none
    for candidate in names:
        try:
            if value is ...:
                return actor.get_editor_property(candidate)
            actor.set_editor_property(candidate, value)
            return value
        except exception as error:
            last_error = error
    raise last_error


def vector(values):
    return unreal.Vector(float(values[0]), float(values[1]), float(values[2]))


def position(actor, values):
    actor.set_actor_location(vector(values), false, true)


class PlayableTests:
    def __init__(self):
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.started = time.monotonic()
        self.phase = "waiting_for_world"
        self.handle = none
        self.world = none
        self.manager = none
        self.pawn = none
        self.balls = []
        self.opponents = []
        self.active_ball = none
        self.cases = []
        self.case_index = -1
        self.case_started = 0
        self.results = []
        self.snapshot = none
        self.done = false
        self.write_report("running")

    def write_report(self, status, error=None):
        REPORT.parent.mkdir(parents=True, exist_ok=true)
        data = {"status": status, "engine": unreal.SystemLibrary.get_engine_version(),
                "elapsed_wall_seconds": round(time.monotonic() - self.started, 2),
                "tests": self.results,
                "passed": sum(row["passed"] for row in self.results),
                "failed": sum(not row["passed"] for row in self.results),
                "manual_checks": ["wasd and vertical flight, mouse aim and camera feel",
                                  "e pickup and one carried ball across competing pickups",
                                  "mouse release and hold e for chase-ball capture",
                                  "hud readability and arena presentation"]}
        if error:
            data["error"] = error
        REPORT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def record(self, name, passed, detail):
        self.results.append({"name": name, "passed": bool(passed), "detail": detail})
        unreal.log("BASKETBROOM test {}: {} | {}".format("PASS" if passed else "fail", name, detail))
        self.write_report("running")

    def begin(self):
        if self.level.is_in_play_in_editor() and not ARGS.get("reuse_play", False):
            raise runtimeerror("a pie session already exists; end it or explicitly set reuse_play=true")
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        if not self.level.is_in_play_in_editor():
            self.level.editor_request_begin_play()

    def setup_world(self):
        self.world = self.editor.get_game_world()
        if not self.world:
            return false
        actors = unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.Actor)
        managers = [actor for actor in actors if actor.get_class().get_name().startswith("BP_BBMatch")]
        self.balls = [actor for actor in actors if actor.get_class().get_name().startswith("BP_BBBall")]
        self.opponents = [actor for actor in actors if actor.get_class().get_name().startswith(
            ("bp_bbbot", "bp_bbhazard", "bp_bbbludger"))]
        self.pawn = unreal.GameplayStatics.get_player_pawn(self.world, 0)
        if not managers or not self.balls or not self.pawn:
            return false
        self.manager = managers[0]
        self.active_ball = next((ball for ball in self.balls if prop(ball, "kind") == 0), self.balls[0])
        self.initial_seconds = float(prop(self.manager, "secondsleft"))
        self.initial_time = unreal.GameplayStatics.get_time_seconds(self.world)
        self.phase = "warmup"
        return true

    def initialize_cases(self):
        self.record("playable_world", len(self.balls) >= 5 and self.pawn.get_class().get_name().startswith("BP_BBBroom"),
                    {"ball_count": len(self.balls), "pawn": self.pawn.get_class().get_name(),
                     "manager": self.manager.get_class().get_name()})
        self.record("timer_default_and_tick", self.initial_seconds > 0 and float(prop(self.manager, "secondsleft")) < self.initial_seconds,
                    {"initial_seconds": self.initial_seconds, "current_seconds": float(prop(self.manager, "secondsleft"))})
        fields = ("kind", "held", "botowner", "botposition", "cooldown", "catchtime", "p", "oldp", "velocity", "home")
        manager_fields = ("tealscore", "copperscore", "hasball", "matchover", "secondsleft", "elapsed", "stun", "message")
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
        for name, value in {"TealScore": 0, "CopperScore": 0, "HasBall": false,
                            "MatchOver": false, "SecondsLeft": 300.0, "Stun": 0.0, "Message": "TEST"}.items():
            prop(self.manager, name, value)
        position(self.pawn, (-3000, -1800, 900))
        for ball in self.balls:
            prop(ball, "cooldown", 100000.0)
            prop(ball, "held", false)
            # a rider can acquire a ball during warmup before opponents freeze.
            # isolated physics fixtures must release that native ownership.
            prop(ball, "botowner", -1)
            prop(ball, "catchtime", 0.0)
            prop(ball, "velocity", vector((0, 0, 0)))

    def launch(self, kind, pos, velocity):
        prop(self.active_ball, "kind", kind)
        prop(self.active_ball, "home", vector((0, 0, 900)))
        prop(self.active_ball, "cooldown", 0.0)
        prop(self.active_ball, "velocity", vector(velocity))
        position(self.active_ball, pos)

    def check_score(self, teal, copper):
        observed = (int(prop(self.manager, "tealscore")), int(prop(self.manager, "copperscore")))
        return observed == (teal, copper), {"expected": [teal, copper], "observed": observed}

    def check_rebound(self):
        vel = prop(self.active_ball, "velocity")
        return abs(vel.y + 750.0) < 3.0, {"velocity_y": vel.y, "expected": -750.0}

    def check_floor(self):
        pos = self.active_ball.get_actor_location()
        vel = prop(self.active_ball, "velocity")
        return pos.z >= 65 and vel.z > 0, {"height": pos.z, "velocity_z": vel.z}

    def roof_contains_ball(self):
        point = self.active_ball.get_actor_location()
        radius = 33 if int(prop(self.active_ball, "kind")) == 0 else 24
        sx, sy = (dimensions.APEX_HEIGHT-dimensions.EAVE_HEIGHT)/dimensions.HALF_LENGTH, (dimensions.APEX_HEIGHT-dimensions.EAVE_HEIGHT)/dimensions.HALF_WIDTH
        return (abs(point.x)+radius <= dimensions.HALF_LENGTH+.2 and abs(point.y)+radius <= dimensions.HALF_WIDTH+.2
                and point.z >= radius-.2
                and point.z+sx*abs(point.x)+radius*(1+sx*sx)**.5 <= dimensions.APEX_HEIGHT+.2
                and point.z+sy*abs(point.y)+radius*(1+sy*sy)**.5 <= dimensions.APEX_HEIGHT+.2)

    def check_hollow_pyramid(self):
        message = str(prop(self.manager, "message"))
        pos = self.active_ball.get_actor_location()
        held = bool(prop(self.active_ball, "held"))
        return (pos.z > dimensions.EAVE_HEIGHT and self.roof_contains_ball() and not held
                and "crown" not in message.upper() and self.check_score(0, 0)[0]), {
                    "message": message, "height": pos.z, "held": held,
                    "scope": "free-ball physical fixture; old horizontal plane has no reset"}

    def prepare_roof_bounce(self):
        # start wholly inside and let the compiled graph cross the +y slope.
        # this replaces the old held=true fixture; no pickup is claimed here.
        self.launch(0, (0, 1600*dimensions.LINEAR_SCALE, dimensions.APEX_HEIGHT-1409.36), (0, 2200, 3300))

    def check_roof_bounce(self):
        velocity = prop(self.active_ball, "velocity")
        slope = (dimensions.APEX_HEIGHT-dimensions.EAVE_HEIGHT)/dimensions.HALF_WIDTH
        outward_speed = (slope*velocity.y+velocity.z)/(1+slope*slope)**.5
        message = str(prop(self.manager, "message"))
        return (outward_speed < -100 and self.roof_contains_ball()
                and not prop(self.active_ball, "held") and "crown" not in message.upper()
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
        prop(self.active_ball, "cooldown", 0.08)

    def check_timeout(self):
        pos = self.active_ball.get_actor_location()
        return pos.z > 1200 and prop(self.active_ball, "cooldown") <= 0, {"height": pos.z, "cooldown": float(prop(self.active_ball, "cooldown"))}

    def prepare_clock(self):
        prop(self.manager, "secondsleft", 0.05)

    def check_clock(self):
        over = bool(prop(self.manager, "matchover"))
        seconds = float(prop(self.manager, "secondsleft"))
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
                raise timeouterror("pie integration tests exceeded 150 seconds")
            if self.phase == "waiting_for_world":
                self.setup_world()
            elif self.phase == "warmup":
                if unreal.GameplayStatics.get_time_seconds(self.world) - self.initial_time >= 0.4:
                    self.initialize_cases()
            elif self.phase == "running_case":
                if not self.level.is_in_play_in_editor():
                    raise runtimeerror("pie ended before runtime verification finished")
                if unreal.GameplayStatics.get_time_seconds(self.world) - self.case_started >= 0.25:
                    passed, detail = self.cases[self.case_index][2]()
                    self.record(self.cases[self.case_index][0], passed, detail)
                    self.next_case()
                elif time.monotonic() - self.case_wall_started > 20:
                    raise timeouterror("pie world did not advance game time")
        except Exception:
            self.finish(traceback.format_exc())

    def finish(self, error=None):
        self.done = true
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = none
        if ARGS.get("leave_play", false) and self.snapshot and not error:
            for name, value in self.snapshot["manager"].items():
                prop(self.manager, name, value)
            for ball, pos, fields in self.snapshot["balls"]:
                for name, value in fields.items():
                    prop(ball, name, value)
                ball.set_actor_location(pos, false, true)
            for actor, tick_enabled in self.snapshot["opponents"]:
                actor.set_actor_tick_enabled(tick_enabled)
            self.pawn.set_actor_location(self.snapshot["pawn_location"], false, true)
        elif self.level.is_in_play_in_editor():
            self.level.editor_request_end_play()
        status = "error" if error else ("passed" if all(row["passed"] for row in self.results) else "failed")
        self.write_report(status, error)
        unreal.log("BASKETBROOM runtime tests {}: {}".format(status.upper(), report))


previous = getattr(unreal, "_basketbroom_playable_test", none)
if previous and not previous.done:
    raise runtimeerror("a basketbroom runtime test is already running")
test = playabletests()
try:
    test.begin()
except Exception:
    test.done = true
    test.write_report("error", traceback.format_exc())
    raise
unreal._basketbroom_playable_test = test
result = {"status": "started", "report": str(report), "expected_cases": 15}

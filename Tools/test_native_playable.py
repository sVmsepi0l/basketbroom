"""Single-world PIE integration checks for the compiled Basketbroom C++ module.

Run through editor_bridge.py with the native arena/GameMode staged. The bridge
returns promptly; a Slate callback writes .local/native-playable-test-results.json.
This suite owns its PIE session and always ends it. It never saves the editor map.
Missing DLL/classes/test bridge produce NOT_RUN, never a passing test report.

Outside Unreal, --list prints the test plan without pretending to run gameplay.
"""

import json
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
REPORT = ROOT / ".local" / "native-playable-test-results.json"
ARGS = globals().get("BRIDGE_ARGS", {})
MODULE = "/Script/BasketbroomRuntime."
ROLES = (0, 1, 1, 2, 3, 4, 4, 5)
TEST_NAMES = (
    "native_game_mode_state_and_pawn",
    "sixteen_unique_roster_slots",
    "seven_balls_and_scheduled_snitch",
    "lobby_clock_stays_stopped",
    "host_selects_chaser_in_lobby",
    "host_starts_live_clock",
    "live_role_change_rejected",
    "host_stoppage_freezes_clock",
    "host_switches_team_at_stoppage",
    "host_selects_ranger_at_stoppage",
    "host_resumes_live_clock",
    "native_flight_crosses_open_crown",
    "native_flight_respects_chase_ceiling",
    "native_flight_respects_side_bound_above_net",
    "side_net_restitution",
    "trampoline_floor_rebound",
    "no_crown_free_ball_dies",
    "no_crown_free_ball_returns",
    "ranger_picks_up_scoring_ball",
    "no_crown_carried_ball_releases",
    "no_crown_carried_ball_returns",
    "quark_wrong_hoop_rejected",
    "quaffle_reverse_crossing_rejected",
    "quaffle_rim_hit_rebounds_without_score",
    "quaffle_whole_ball_goal_awards_13",
    "quark_whole_ball_goal_awards_37",
    "chaser_cannot_capture_snipe",
    "hurleyback_cannot_carry_quaffle",
    "hurleyback_can_carry_bludger",
    "scout_cannot_carry_quaffle",
    "snipe_progress_is_observable_before_catch",
    "snipe_release_resets_progress",
    "snipe_range_break_resets_progress",
    "snipe_continuous_hold_awards_69",
    "snipe_catch_starts_180_second_timeout",
)


def prop(obj, name):
    """Observe reflected state without bypassing native gameplay authority."""
    aliases = [name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()]
    if name.startswith("b") and len(name) > 1 and name[1].isupper():
        aliases.append(re.sub(r"(?<!^)(?=[A-Z])", "_", name[1:]).lower())
    last_error = None
    for alias in aliases:
        try:
            return obj.get_editor_property(alias)
        except Exception as error:
            last_error = error
    raise last_error


def xyz(value):
    return [round(float(value.x), 3), round(float(value.y), 3), round(float(value.z), 3)]


def vector(values):
    return unreal.Vector(float(values[0]), float(values[1]), float(values[2]))


class NativePlayableTests:
    def __init__(self):
        self.started = time.monotonic()
        self.phase = "preflight"
        self.done = False
        self.final_status = "not_run"
        self.handle = None
        self.owns_play = False
        self.world = self.match = self.pawn = self.controller = None
        self.riders = []
        self.balls = {}
        self.classes = {}
        self.sequence = None
        self.waiting = None
        self.results = {}
        self.events = []
        self.provenance = {}
        self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem) if unreal else None
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem) if unreal else None
        self.write_report("not_run", "Native PIE checks have not started.")

    def write_report(self, status, reason=None):
        tests = [{"name": name, **self.results.get(name, {"status": "not_run"})} for name in TEST_NAMES]
        data = {
            "status": status, "phase": self.phase, "scope": "single-world native C++ PIE integration",
            "engine": unreal.SystemLibrary.get_engine_version() if unreal else None,
            "elapsed_wall_seconds": round(time.monotonic() - self.started, 3),
            "passed": sum(t["status"] == "passed" for t in tests),
            "failed": sum(t["status"] == "failed" for t in tests),
            "not_run": sum(t["status"] == "not_run" for t in tests),
            "tests": tests, "events": self.events, "provenance": self.provenance,
            "not_covered": ["network transport, remote ownership and replication",
                            "physical keyboard/mouse bindings and flight feel",
                            "timed Snitch release and Snitch capture",
                            "autonomous CPU decisions with all riders enabled",
                            "packaged builds, graphics performance and audio"],
        }
        if reason:
            data["reason"] = reason
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")

    def record(self, name, passed, **detail):
        if name not in TEST_NAMES or name in self.results:
            raise RuntimeError("Unknown or duplicate test: " + name)
        status = "passed" if passed else "failed"
        self.results[name] = {"status": status, "detail": detail}
        unreal.log("BASKETBROOM NATIVE TEST %s: %s | %s" % (status.upper(), name, detail))
        self.write_report("running")

    def event(self, kind, **detail):
        self.events.append({"kind": kind, "game_seconds": round(self.now(), 3), **detail})
        self.events = self.events[-150:]

    def require(self, condition, message):
        if not condition:
            raise RuntimeError("Test prerequisite failed: " + message)

    def now(self):
        return float(unreal.GameplayStatics.get_time_seconds(self.world))

    def scores(self):
        return [int(prop(self.match, "TealScore")), int(prop(self.match, "CopperScore"))]

    def score_delta(self, before):
        return [current - prior for current, prior in zip(self.scores(), before)]

    def roster(self):
        return sorted((int(prop(r, "RosterIndex")), int(prop(r, "TeamIndex")), int(prop(r, "Position")))
                      for r in self.riders)

    def roster_valid(self):
        return self.roster() == [(slot, slot // 8, ROLES[slot % 8]) for slot in range(16)]

    def request(self, action, value=0):
        # The bridge submits the ordinary input/RPC path. A True return only
        # means submitted; all gameplay acceptance is checked independently.
        self.require(self.pawn.development_request_action(action, value), "PIE input bridge rejected action")
        self.event("input_action", action=action, value=value)

    def interact(self, held):
        self.require(self.pawn.development_set_interaction(held), "PIE interaction bridge rejected request")
        self.event("interaction", held=held)

    def wait(self, seconds, fixture=None, minimum_frames=1):
        return {"seconds": float(seconds), "fixture": fixture,
                "minimum_frames": minimum_frames, "predicate": None}

    def wait_until(self, predicate, fixture=None, timeout=5.0):
        # Inputs execute on the next native Tick, and MatchState may publish a
        # ball's queued goal one tick later. A timeout still advances to the
        # unchanged assertion, so an absent/wrong outcome cannot pass silently.
        waiting = self.wait(timeout, fixture)
        waiting["predicate"] = predicate
        return waiting

    def move_pawn(self, location):
        self.component(self.pawn, unreal.CharacterMovementComponent).stop_movement_immediately()
        self.pawn.set_actor_location(vector(location), False, True)

    def component(self, actor, component_class):
        # ACharacter's C++ convenience getters are not reflected UFUNCTIONs.
        component = actor.get_component_by_class(component_class)
        self.require(component is not None, "Missing component " + component_class.__name__)
        return component

    def isolate(self):
        # MatchState still owns CPU decisions, so actor tick alone is not an AI
        # freeze. Disable CharacterMovement too and park CPU copies beyond
        # interaction range. Reapply after role swaps/restarts that move riders.
        # The suite owns and destroys this PIE world; no editor actor is edited.
        for rider in self.riders:
            if rider != self.pawn:
                movement = self.component(rider, unreal.CharacterMovementComponent)
                movement.stop_movement_immediately()
                movement.set_component_tick_enabled(False)
                rider.set_actor_tick_enabled(False)
                rider.consume_movement_input_vector()
                rider.set_actor_location(vector((0, 14000 + int(prop(rider, "RosterIndex")) * 300, 1800)), False, True)
        for ball in self.balls.values():
            ball.set_actor_tick_enabled(False)
        self.controller.set_control_rotation(unreal.Rotator(pitch=0, yaw=0, roll=0))

    def seed_ball(self, index, location, velocity=(0, 0, 0)):
        """Arrange a free ball; never set Holder, active state or rule outcomes."""
        ball = self.balls[index]
        self.require(prop(ball, "Holder") is None, "Fixture requires a free ball, index %d" % index)
        self.require(bool(prop(ball, "bActive")), "Fixture requires an active ball, index %d" % index)
        self.require(ball.development_set_flight_fixture(vector(location), vector(velocity)),
                     "Native PIE ball fixture rejected transform/velocity")
        ball.set_actor_tick_enabled(True)
        self.event("physical_fixture", ball=index, position=list(location), velocity=list(velocity))
        return ball

    def close_ball(self, index):
        self.isolate()
        self.move_pawn((-2000, -1200, 1800))
        self.seed_ball(index, (-1800, -1200, 1800))

    def follow_snipe(self, distance=0.0):
        # This isolates hold/range/eligibility; it does not certify flight skill.
        # Center the fixture: at background 3 FPS, Snipe moves about 340cm each
        # tick. An extra 90cm offset can accidentally exceed the real 380cm range.
        point = self.balls[3].get_actor_location()
        self.move_pawn((point.x - distance, point.y, point.z))

    def fly_fixture(self, direction, samples):
        point = self.pawn.get_actor_location()
        samples.append(xyz(point))
        self.pawn.add_movement_input(vector(direction), 1.0, False)

    def switch_role(self, role):
        self.interact(False)
        if prop(self.match, "bLive"):
            self.request(5)
            yield self.wait_until(lambda: not prop(self.match, "bLive"))
        self.require(not prop(self.match, "bLive"), "Host could not stop play for role fixture")
        self.request(2, role)
        yield self.wait_until(lambda: int(prop(self.pawn, "Position")) == role)
        self.require(int(prop(self.pawn, "Position")) == role, "Host role fixture was rejected")
        self.isolate()
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")))
        self.require(prop(self.match, "bLive"), "Host could not resume role fixture")

    def begin(self):
        if unreal is None:
            self.finish("not_run", "Run inside the UE5.8 editor after compiling and loading BasketbroomRuntime.")
            return False
        if not unreal.SystemLibrary.get_engine_version().startswith("5.8."):
            self.finish("not_run", "The suite requires the installed Unreal Engine 5.8 project.")
            return False
        dll = ROOT / "DevelopmentHarness/Binaries/Win64/UnrealEditor-BasketbroomRuntime.dll"
        self.provenance["expected_dll"] = str(dll)
        if not dll.is_file():
            self.finish("not_run", "Compiled native editor DLL is missing. No gameplay test was run.")
            return False
        self.provenance.update(dll_bytes=dll.stat().st_size, dll_modified_unix=dll.stat().st_mtime)
        for name in ("BBGameMode", "BBMatchState", "BBRiderCharacter", "BBBall"):
            self.classes[name] = unreal.load_class(None, MODULE + name)
            if self.classes[name] is None:
                self.finish("not_run", "Native class is not loaded: " + MODULE + name)
                return False
        prototype = unreal.get_default_object(self.classes["BBRiderCharacter"])
        if not all(callable(getattr(prototype, method, None)) for method in
                   ("development_request_action", "development_set_interaction")):
            self.finish("not_run", "The loaded module lacks the agreed PIE-only test bridge. Rebuild and restart the editor.")
            return False
        ball_prototype = unreal.get_default_object(self.classes["BBBall"])
        if not all(callable(getattr(ball_prototype, method, None)) for method in
                   ("development_set_flight_fixture", "get_flight_velocity")):
            self.finish("not_run", "The loaded module lacks the guarded PIE ball fixture or read-only velocity diagnostic. Rebuild and restart the editor.")
            return False
        if self.level.is_in_play_in_editor():
            self.finish("not_run", "An existing PIE session is active. This test must own a fresh session.")
            return False
        for name in ("_basketbroom_playable_test", "_basketbroom_bot_test", "_basketbroom_native_test"):
            previous = getattr(unreal, name, None)
            if previous and not previous.done:
                self.finish("not_run", "Another Basketbroom integration runner is active: " + name)
                return False
        self.owns_play = True
        self.phase = "waiting_for_native_world"
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.level.editor_request_begin_play()
        self.write_report("running")
        return True

    def setup_world(self):
        self.world = self.editor.get_game_world()
        if self.world is None:
            return False
        states = unreal.GameplayStatics.get_all_actors_of_class(self.world, self.classes["BBMatchState"])
        self.pawn = unreal.GameplayStatics.get_player_pawn(self.world, 0)
        if len(states) != 1 or self.pawn is None:
            return False
        self.match = states[0]
        self.controller = unreal.GameplayStatics.get_player_controller(self.world, 0)
        self.riders = list(unreal.GameplayStatics.get_all_actors_of_class(self.world, self.classes["BBRiderCharacter"]))
        equipment = list(unreal.GameplayStatics.get_all_actors_of_class(self.world, self.classes["BBBall"]))
        self.balls = {int(prop(ball, "BallIndex")): ball for ball in equipment}
        if len(self.riders) < 16 or len(equipment) < 7:
            return False
        self.require(len(self.balls) == len(equipment), "Duplicate BallIndex values in native world")
        self.provenance["pie_world"] = self.world.get_path_name()
        self.isolate()
        self.sequence = self.scenarios()
        self.phase = "running_cases"
        self.advance()
        return True

    def scenarios(self):
        game_mode = unreal.GameplayStatics.get_game_mode(self.world)
        native = (game_mode and game_mode.get_class() == self.classes["BBGameMode"]
                  and self.match.get_class() == self.classes["BBMatchState"]
                  and self.pawn.get_class() == self.classes["BBRiderCharacter"])
        self.record("native_game_mode_state_and_pawn", bool(native),
                    game_mode=game_mode.get_class().get_path_name() if game_mode else None,
                    game_state=self.match.get_class().get_path_name(), pawn=self.pawn.get_class().get_path_name())
        self.record("sixteen_unique_roster_slots", len(self.riders) == 16 and self.roster_valid(), roster=self.roster())
        self.record("seven_balls_and_scheduled_snitch", sorted(self.balls) == list(range(7))
                    and not prop(self.balls[4], "bActive") and prop(self.balls[3], "bActive"),
                    indices=sorted(self.balls), snitch_active=bool(prop(self.balls[4], "bActive")),
                    snitch_status=str(prop(self.balls[4], "BallStatus")), practice=bool(prop(self.match, "bPractice")))
        seconds = float(prop(self.match, "SecondsLeft"))
        yield self.wait(0.3)
        self.record("lobby_clock_stays_stopped", not prop(self.match, "bLive")
                    and str(prop(self.match, "Status")) == "LOBBY"
                    and abs(float(prop(self.match, "SecondsLeft")) - seconds) < 0.02,
                    before=seconds, after=float(prop(self.match, "SecondsLeft")))
        self.request(2, 1)
        yield self.wait_until(lambda: int(prop(self.pawn, "Position")) == 1)
        self.record("host_selects_chaser_in_lobby", int(prop(self.pawn, "Position")) == 1 and self.roster_valid(), roster=self.roster())
        self.isolate()
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive"))
                             and float(prop(self.match, "SecondsLeft")) < seconds)
        self.record("host_starts_live_clock", bool(prop(self.match, "bLive")) and float(prop(self.match, "SecondsLeft")) < seconds,
                    status=str(prop(self.match, "Status")), seconds=float(prop(self.match, "SecondsLeft")))
        self.require(prop(self.match, "bLive"), "Native host start failed")
        previous_role = int(prop(self.pawn, "Position"))
        self.request(2, 5)
        yield self.wait(0.16)
        self.record("live_role_change_rejected", int(prop(self.pawn, "Position")) == previous_role,
                    before=previous_role, after=int(prop(self.pawn, "Position")))
        self.request(5)
        yield self.wait_until(lambda: not prop(self.match, "bLive"))
        seconds = float(prop(self.match, "SecondsLeft"))
        yield self.wait(0.25)
        self.record("host_stoppage_freezes_clock", not prop(self.match, "bLive")
                    and str(prop(self.match, "Status")) == "STOPPAGE"
                    and abs(float(prop(self.match, "SecondsLeft")) - seconds) < 0.02,
                    before=seconds, after=float(prop(self.match, "SecondsLeft")))
        team = 1 - int(prop(self.pawn, "TeamIndex"))
        self.request(3, team)
        yield self.wait_until(lambda: int(prop(self.pawn, "TeamIndex")) == team)
        self.record("host_switches_team_at_stoppage", int(prop(self.pawn, "TeamIndex")) == team and self.roster_valid(), team=team, roster=self.roster())
        self.request(2, 3)
        yield self.wait_until(lambda: int(prop(self.pawn, "Position")) == 3)
        self.record("host_selects_ranger_at_stoppage", int(prop(self.pawn, "Position")) == 3 and self.roster_valid(), roster=self.roster())
        self.isolate()
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive"))
                             and float(prop(self.match, "SecondsLeft")) < seconds)
        self.record("host_resumes_live_clock", bool(prop(self.match, "bLive")) and float(prop(self.match, "SecondsLeft")) < seconds,
                    status=str(prop(self.match, "Status")))
        self.require(prop(self.match, "bLive"), "Native host resume failed")

        self.isolate()
        flight_samples = []
        self.move_pawn((0, 0, 4100))
        yield self.wait(0.55, lambda: self.fly_fixture((0, 0, 1), flight_samples))
        self.record("native_flight_crosses_open_crown", bool(flight_samples)
                    and max(row[2] for row in flight_samples) > 4300,
                    max_height_cm=max((row[2] for row in flight_samples), default=0),
                    samples=len(flight_samples), input="AddMovementInput into native CharacterMovement")
        capsule = self.component(self.pawn, unreal.CapsuleComponent)
        ceiling = 6309.36 - capsule.get_scaled_capsule_half_height()
        self.move_pawn((0, 0, ceiling - 100))
        flight_samples = []
        yield self.wait(0.55, lambda: self.fly_fixture((0, 0, 1), flight_samples))
        peak = max((row[2] for row in flight_samples), default=0)
        self.record("native_flight_respects_chase_ceiling", bool(flight_samples)
                    and ceiling - 25 <= peak <= ceiling + 1,
                    capsule_center_limit_cm=ceiling, observed_max_height_cm=peak)
        side_limit = 3200.4 - capsule.get_scaled_capsule_radius()
        self.move_pawn((0, side_limit - 100, 4700))
        flight_samples = []
        yield self.wait(0.55, lambda: self.fly_fixture((0, 1, 0), flight_samples))
        peak = max((row[1] for row in flight_samples), default=0)
        self.record("native_flight_respects_side_bound_above_net", bool(flight_samples)
                    and side_limit - 25 <= peak <= side_limit + 1,
                    capsule_center_limit_cm=side_limit, observed_max_y_cm=peak, fixture_height_cm=4700)
        self.move_pawn((-3200, -2200, 1000))
        ball = self.seed_ball(2, (0, 3100, 1600), (0, 1000, 0))
        yield self.wait(0.16)
        velocity = ball.get_flight_velocity()
        self.record("side_net_restitution", abs(velocity.y + 750) < 5 and ball.get_actor_location().y < 3136,
                    velocity=xyz(velocity), location=xyz(ball.get_actor_location()))
        ball = self.seed_ball(2, (0, 0, 80), (0, 0, -500))
        yield self.wait(0.20)
        velocity = ball.get_flight_velocity()
        self.record("trampoline_floor_rebound", ball.get_actor_location().z >= 64.9 and velocity.z > 0,
                    velocity=xyz(velocity), location=xyz(ball.get_actor_location()))
        ball = self.seed_ball(2, (0, 0, 4190), (0, 0, 700))
        yield self.wait(0.16)
        self.record("no_crown_free_ball_dies", str(prop(ball, "BallStatus")) == "crown"
                    and not prop(ball, "bActive") and prop(ball, "Holder") is None and ball.get_actor_location().z < 4206.24,
                    status=str(prop(ball, "BallStatus")), location=xyz(ball.get_actor_location()))
        yield self.wait(1.2)
        self.record("no_crown_free_ball_returns", bool(prop(ball, "bActive"))
                    and str(prop(ball, "BallStatus")) != "crown" and ball.get_actor_location().z < 4206.24,
                    active=bool(prop(ball, "bActive")), status=str(prop(ball, "BallStatus")))
        self.close_ball(2)
        yield self.wait(0.35)
        self.interact(True)
        yield self.wait_until(lambda: prop(ball, "Holder") == self.pawn)
        self.record("ranger_picks_up_scoring_ball", prop(ball, "Holder") == self.pawn,
                    held=prop(ball, "Holder") == self.pawn, role=int(prop(self.pawn, "Position")))
        self.require(prop(ball, "Holder") == self.pawn, "Carried No Crown fixture needs an actual pickup")
        self.interact(False)
        self.move_pawn((-2000, -1200, 4450))
        yield self.wait(0.16)
        self.record("no_crown_carried_ball_releases", prop(ball, "Holder") is None
                    and str(prop(ball, "BallStatus")) == "crown" and not prop(ball, "bActive"),
                    held=prop(ball, "Holder") is not None, status=str(prop(ball, "BallStatus")))
        self.move_pawn((-3200, -2200, 1000))
        yield self.wait(1.2)
        self.record("no_crown_carried_ball_returns", bool(prop(ball, "bActive"))
                    and prop(ball, "Holder") is None and ball.get_actor_location().z < 4206.24,
                    active=bool(prop(ball, "bActive")), location=xyz(ball.get_actor_location()))

        self.isolate()
        before = self.scores()
        wrong = self.seed_ball(2, (6200, 1066.8, 2103.12), (2000, 0, 0))
        yield self.wait(0.22)
        wrong_location = xyz(wrong.get_actor_location())
        # Freeze the completed sweep and allow MatchState one more game tick to
        # flush any pending award, including an incorrect one this test rejects.
        wrong.set_actor_tick_enabled(False)
        yield self.wait(0)
        self.record("quark_wrong_hoop_rejected", self.scores() == before and wrong_location[0] > 6465.8,
                    delta=self.score_delta(before), location=wrong_location)
        # The outer hoop avoids the taller central mast behind the goal plane.
        reverse = self.seed_ball(0, (6585.8, 1066.8, 2103.12), (-2000, 0, 0))
        yield self.wait(0.22)
        reverse.set_actor_tick_enabled(False)
        yield self.wait(0)
        self.record("quaffle_reverse_crossing_rejected", self.scores() == before and reverse.get_actor_location().x < 6400.8,
                    delta=self.score_delta(before), location=xyz(reverse.get_actor_location()))
        rim = self.seed_ball(0, (6200, 350, 2103.12), (2000, 0, 0))
        yield self.wait(0.22)
        rim.set_actor_tick_enabled(False)
        yield self.wait(0)
        self.record("quaffle_rim_hit_rebounds_without_score", self.scores() == before and rim.get_flight_velocity().x < 0,
                    delta=self.score_delta(before), velocity=xyz(rim.get_flight_velocity()))
        self.seed_ball(0, (6200, 0, 2103.12), (2000, 0, 0))
        yield self.wait_until(lambda: self.scores() != before)
        self.record("quaffle_whole_ball_goal_awards_13", self.score_delta(before) == [13, 0], delta=self.score_delta(before))
        self.balls[0].set_actor_tick_enabled(False)
        before = self.scores()
        self.seed_ball(1, (-6200, 0, 3048), (-2000, 0, 0))
        yield self.wait_until(lambda: self.scores() != before)
        self.record("quark_whole_ball_goal_awards_37", self.score_delta(before) == [0, 37], delta=self.score_delta(before))

        yield from self.switch_role(1)
        snipe = self.balls[3]
        snipe.set_actor_tick_enabled(True)
        self.follow_snipe()
        before = self.scores()
        self.interact(True)
        yield self.wait_until(lambda: bool(prop(self.pawn, "bInteractHeld")), self.follow_snipe)
        yield self.wait(0.45, self.follow_snipe)
        self.record("chaser_cannot_capture_snipe", float(prop(snipe, "CaptureProgress")) == 0
                    and prop(snipe, "CapturingRider") is None and self.scores() == before
                    and bool(prop(self.pawn, "bInteractHeld")),
                    progress=float(prop(snipe, "CaptureProgress")), delta=self.score_delta(before))
        self.interact(False)
        yield self.wait(0.12)

        yield from self.switch_role(4)
        # The earlier goal's restart was secured by a netminder. The native
        # pause/resume above releases it; no Holder field is reset by the test.
        self.close_ball(0)
        yield self.wait(0.35)
        self.interact(True)
        yield self.wait_until(lambda: bool(prop(self.pawn, "bInteractHeld")))
        self.record("hurleyback_cannot_carry_quaffle", prop(self.balls[0], "Holder") is None
                    and bool(prop(self.pawn, "bInteractHeld")),
                    held=prop(self.balls[0], "Holder") is not None, role=int(prop(self.pawn, "Position")))
        self.interact(False)
        yield self.wait(0.12)
        self.close_ball(5)
        yield self.wait(0.35)
        self.interact(True)
        yield self.wait_until(lambda: prop(self.balls[5], "Holder") == self.pawn)
        self.record("hurleyback_can_carry_bludger", prop(self.balls[5], "Holder") == self.pawn,
                    held=prop(self.balls[5], "Holder") == self.pawn)
        self.interact(False)
        self.request(1)
        yield self.wait(0.4)

        yield from self.switch_role(5)
        self.close_ball(0)
        yield self.wait(0.35)
        self.interact(True)
        yield self.wait_until(lambda: bool(prop(self.pawn, "bInteractHeld")))
        self.record("scout_cannot_carry_quaffle", prop(self.balls[0], "Holder") is None
                    and bool(prop(self.pawn, "bInteractHeld")),
                    held=prop(self.balls[0], "Holder") is not None)
        self.interact(False)
        yield self.wait(0.12)
        self.isolate()
        snipe.set_actor_tick_enabled(True)
        self.follow_snipe()
        before = self.scores()
        self.interact(True)
        yield self.wait_until(lambda: float(prop(snipe, "CaptureProgress")) >= 0.1, self.follow_snipe)
        progress = float(prop(snipe, "CaptureProgress"))
        self.record("snipe_progress_is_observable_before_catch", 0.1 <= progress < 0.9
                    and prop(snipe, "CapturingRider") == self.pawn and self.scores() == before,
                    progress=progress, delta=self.score_delta(before))
        self.interact(False)
        yield self.wait_until(lambda: not prop(self.pawn, "bInteractHeld")
                             and float(prop(snipe, "CaptureProgress")) == 0, self.follow_snipe)
        self.record("snipe_release_resets_progress", float(prop(snipe, "CaptureProgress")) == 0
                    and prop(snipe, "CapturingRider") is None and self.scores() == before,
                    progress=float(prop(snipe, "CaptureProgress")), delta=self.score_delta(before))
        self.interact(True)
        yield self.wait_until(lambda: float(prop(snipe, "CaptureProgress")) >= 0.1, self.follow_snipe)
        self.require(0.1 <= float(prop(snipe, "CaptureProgress")) < 0.9,
                     "Range-break fixture needs an observed partial catch")
        self.follow_snipe(900)
        yield self.wait_until(lambda: float(prop(snipe, "CaptureProgress")) == 0
                             and prop(snipe, "CapturingRider") is None, lambda: self.follow_snipe(900))
        self.record("snipe_range_break_resets_progress", float(prop(snipe, "CaptureProgress")) == 0
                    and prop(snipe, "CapturingRider") is None and self.scores() == before,
                    progress=float(prop(snipe, "CaptureProgress")), delta=self.score_delta(before))
        self.interact(False)
        yield self.wait_until(lambda: not prop(self.pawn, "bInteractHeld"))
        self.follow_snipe()
        self.interact(True)
        yield self.wait_until(lambda: self.scores() != before
                             and not prop(snipe, "bActive")
                             and str(prop(snipe, "BallStatus")) == "timeout", self.follow_snipe)
        expected = [0, 0]
        expected[int(prop(self.pawn, "TeamIndex"))] = 69
        self.record("snipe_continuous_hold_awards_69", self.score_delta(before) == expected,
                    delta=self.score_delta(before), expected=expected)
        self.record("snipe_catch_starts_180_second_timeout", not prop(snipe, "bActive")
                    and str(prop(snipe, "BallStatus")) == "timeout" and 178 <= float(prop(snipe, "ReturnIn")) <= 180,
                    active=bool(prop(snipe, "bActive")), return_seconds=float(prop(snipe, "ReturnIn")),
                    status=str(prop(snipe, "BallStatus")))
        self.interact(False)

    def advance(self):
        try:
            self.waiting = next(self.sequence)
            self.waiting["last_game_seconds"] = self.now()
            self.waiting["game_frames"] = 0
            self.waiting["until"] = self.waiting["last_game_seconds"] + self.waiting["seconds"]
            self.waiting["wall_started"] = time.monotonic()
        except StopIteration:
            complete = len(self.results) == len(TEST_NAMES)
            passed = complete and all(row["status"] == "passed" for row in self.results.values())
            self.finish("passed" if passed else "failed")

    def tick(self, delta):
        if self.done:
            return
        try:
            elapsed = time.monotonic() - self.started
            if elapsed > float(ARGS.get("max_wall_seconds", 240)):
                raise TimeoutError("Native PIE integration exceeded its wall-time limit")
            if self.phase == "waiting_for_native_world":
                if not self.setup_world() and elapsed > 30:
                    self.finish("not_run", "No complete native world appeared. Stage the map with BBGameMode, rebuild, and restart the editor.")
                return
            if not self.level.is_in_play_in_editor():
                raise RuntimeError("PIE ended before native integration checks completed")
            if self.waiting:
                if self.waiting["fixture"]:
                    self.waiting["fixture"]()
                now = self.now()
                if now > self.waiting["last_game_seconds"]:
                    self.waiting["game_frames"] += 1
                    self.waiting["last_game_seconds"] = now
                predicate = self.waiting["predicate"]
                ready = bool(predicate()) if predicate else False
                expired = now >= self.waiting["until"]
                if self.waiting["game_frames"] >= self.waiting["minimum_frames"] and (ready or expired):
                    if predicate and expired and not ready:
                        self.event("observation_timeout", limit_seconds=self.waiting["seconds"])
                    self.advance()
                elif time.monotonic() - self.waiting["wall_started"] > 30:
                    raise TimeoutError("PIE world time stalled")
        except Exception:
            self.finish("error", traceback.format_exc())

    def finish(self, status, reason=None):
        self.done = True
        if unreal and self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        if self.owns_play:
            try:
                if self.pawn and callable(getattr(self.pawn, "development_set_interaction", None)):
                    self.pawn.development_set_interaction(False)
            except Exception:
                reason = (reason or "") + "\nInteraction cleanup: " + traceback.format_exc()
                status = "error"
            finally:
                if self.level.is_in_play_in_editor():
                    self.level.editor_request_end_play()
        self.final_status = status
        self.write_report(status, reason)
        if unreal:
            unreal.log("BASKETBROOM NATIVE TESTS %s: %s" % (status.upper(), REPORT))


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "planned_tests": list(TEST_NAMES), "count": len(TEST_NAMES)}
    test = NativePlayableTests()
    try:
        started = test.begin()
    except Exception:
        test.finish("error", traceback.format_exc())
        started = False
    if unreal and started:
        unreal._basketbroom_native_test = test
    return {"status": "started" if started else test.final_status, "report": str(REPORT), "planned_cases": len(TEST_NAMES)}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

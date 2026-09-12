"""Focused native Bludger regressions in an owned, disposable single-world PIE.

Uses ordinary queued rider inputs and the existing guarded free-ball physical
fixture. Rule clocks, possession, fouls and restart outcomes are never assigned.
CPU movement is isolated; this is not a test of autonomous play or networking.
The Slate callback reports to .local/native-bludger-test-results.json.
Run outside Unreal with --list to inspect the plan without running gameplay.
"""

import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/native-bludger-test-results.json"
CASES = (
    "short_self_toss_preserves_individual_control_clock",
    "cumulative_ten_foot_flight_resets_individual_control_clock",
    "short_floor_contact_resets_individual_control_clock",
    "nearby_opponent_hit_during_pickup_lockout",
    "thrower_is_exempt_during_initial_launch_clearance",
    "thrower_can_be_hit_after_launch_clearance_expires",
    "dead_bludger_restarts_to_nearest_opposing_hurleyback",
    "equal_distance_restart_uses_lower_roster_slot",
    "stunned_nearest_hurleyback_is_skipped_for_restart",
)

# A private module instance reuses the proven asynchronous lifecycle without
# changing another running/imported suite's report path or test definitions.
spec = importlib.util.spec_from_file_location(
    "_basketbroom_bludger_scaffold", ROOT / "Tools/test_native_playable.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.TEST_NAMES = CASES
base.REPORT = REPORT
base.ARGS = {"max_wall_seconds": 360, **globals().get("BRIDGE_ARGS", {})}
unreal, prop, xyz, vector = base.unreal, base.prop, base.xyz, base.vector


class NativeBludgerTests(base.NativePlayableTests):
    def __init__(self):
        self.original_dilation = None
        super().__init__()

    def write_report(self, status, reason=None):
        tests = [{"name": name, **self.results.get(name, {"status": "not_run"})}
                 for name in CASES]
        data = {
            "status": status, "phase": self.phase,
            "scope": "single-world native Bludger physics/rules PIE regression",
            "engine": unreal.SystemLibrary.get_engine_version() if unreal else None,
            "elapsed_wall_seconds": round(time.monotonic() - self.started, 3),
            "passed": sum(t["status"] == "passed" for t in tests),
            "failed": sum(t["status"] == "failed" for t in tests),
            "not_run": sum(t["status"] == "not_run" for t in tests),
            "tests": tests, "events": self.events, "provenance": self.provenance,
            "not_covered": ["remote/network transport", "autonomous CPU movement",
                            "human contestability judgments", "packaged runtime"],
        }
        if reason:
            data["reason"] = reason
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")

    def finish(self, status, reason=None):
        if self.original_dilation is not None and self.world:
            try:
                unreal.GameplayStatics.set_global_time_dilation(self.world, self.original_dilation)
                self.provenance["pie_time_dilation_restored"] = self.original_dilation
            except Exception:
                status = "error"
                reason = (reason or "") + "\nTime dilation cleanup: " + traceback.format_exc()
            self.original_dilation = None
        super().finish(status, reason)

    def control_seconds(self):
        return float(self.match.development_get_bludger_control_seconds(5))

    def rider(self, slot):
        return next(r for r in self.riders if int(prop(r, "RosterIndex")) == slot)

    def park_equipment(self):
        for index, ball in self.balls.items():
            if prop(ball, "Holder") is None and prop(ball, "bActive"):
                self.require(ball.development_set_flight_fixture(
                    vector((0, 22000 + 500 * index, 1800)), vector((0, 0, 0))),
                    "Could not isolate free equipment")
            ball.set_actor_tick_enabled(False)

    def prepare_held(self):
        self.interact(False)
        if prop(self.match, "bLive"):
            self.request(5)
            yield self.wait_until(lambda: not prop(self.match, "bLive"), timeout=2)
        self.require(not prop(self.match, "bLive"), "Host stoppage did not complete")
        if int(prop(self.pawn, "Position")) != 4:
            self.request(2, 4)
            yield self.wait_until(lambda: int(prop(self.pawn, "Position")) == 4, timeout=2)
        self.require(int(prop(self.pawn, "Position")) == 4, "Human must be an eligible Hurleyback")
        self.isolate()
        self.park_equipment()
        self.move_pawn((-2000, -1200, 1800))
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")), timeout=2)
        self.require(prop(self.match, "bLive"), "Host resume did not complete")
        # First kickoff restores legal opening positions. Reapply the owned
        # fixture after that real layout transition, before arranging pickup.
        self.isolate()
        self.park_equipment()
        self.move_pawn((-2000, -1200, 1800))
        ball = self.seed_ball(5, (-1800, -1200, 1800))
        # A previous real impact can leave .7 seconds of pickup recovery. Let
        # the native timer expire; no protected cooldown property is assigned.
        yield self.wait(.8)
        self.interact(True)
        yield self.wait_until(lambda: prop(ball, "Holder") == self.pawn, timeout=2)
        self.require(prop(ball, "Holder") == self.pawn, "Normal pickup did not give the human Bludger A")
        self.interact(False)
        yield self.wait_until(lambda: not prop(self.pawn, "bInteractHeld"), timeout=1)

    def release_for_fixture(self, location, velocity):
        ball = self.balls[5]
        # Freeze only physical flight until the real queued release is observed.
        # This excludes variable UI callback delay from the measured trajectory.
        ball.set_actor_tick_enabled(False)
        self.request(1)
        yield self.wait_until(lambda: prop(ball, "Holder") is None, timeout=1)
        self.require(prop(ball, "Holder") is None, "Native release did not occur")
        self.seed_ball(5, location, velocity)

    def toss_case(self, name, location, velocity, reset, contact=False):
        yield from self.prepare_held()
        ball = self.balls[5]
        yield self.wait_until(lambda: self.control_seconds() >= 1.2, timeout=2)
        before = self.control_seconds()
        self.require(1.15 <= before < 2.5, "Fixture needs observed prior control below the foul deadline")
        yield from self.release_for_fixture(location, velocity)
        released_at = self.now()
        samples = []
        yield self.wait(.40, lambda: samples.append(xyz(ball.get_actor_location())))
        ball.set_actor_tick_enabled(False)
        distance = float(ball.get_distance_since_release_cm())
        flight_velocity = xyz(ball.get_flight_velocity())
        position = ball.get_actor_location()
        self.move_pawn((position.x - 175, position.y, max(200, position.z + (150 if contact else 0))))
        self.interact(True)
        yield self.wait_until(lambda: prop(ball, "Holder") == self.pawn, timeout=.35)
        held = prop(ball, "Holder") == self.pawn
        free_seconds = self.now() - released_at
        after = self.control_seconds()
        self.interact(False)
        # Reacquire before one second of contestable flight; otherwise that
        # independent rule could mask broken distance/contact evidence.
        evidence = (distance >= 304.8 if reset and not contact else distance < 304.8)
        if contact:
            evidence = evidence and flight_velocity[2] > 0 and position.z > 50
        clock_correct = 0 <= after < .35 if reset else after >= before + .3
        distance_cleared = float(ball.get_distance_since_release_cm()) == 0
        self.record(name, held and free_seconds < .9 and evidence and clock_correct and distance_cleared,
                    held_by_human=held, prior_control_seconds=before,
                    after_control_seconds=after, free_seconds=free_seconds,
                    accumulated_distance_cm=distance, flight_velocity=flight_velocity,
                    final_position=xyz(position), callback_samples=len(samples),
                    distance_cleared_on_reacquire=distance_cleared)

    def restart_case(self, name, mode):
        yield from self.prepare_held()
        ball = self.balls[5]
        low, high = self.rider(13), self.rider(14)
        self.require(all(int(prop(r, "Position")) == 4 and int(prop(r, "TeamIndex")) == 1
                         for r in (low, high)), "Opposing restart fixtures require Copper Hurleybacks")
        center = ball.get_actor_location()
        low_pos = (center.x, center.y - (650 if mode == "tie" else 1600), center.z)
        high_pos = (center.x, center.y + 650, center.z)
        for rider, point in ((low, low_pos), (high, high_pos)):
            rider.set_actor_location(vector(point), False, True)
        if mode == "stunned":
            # Use a real release: a never-thrown free ball has no pickup lockout,
            # and the eligible CPU can catch it before its physical hit step.
            # Actor tick is isolated, so the observed impact stun persists; the
            # fixture never assigns StunRemaining, cooldown or eligibility.
            yield from self.release_for_fixture(
                (high_pos[0] - 150, high_pos[1], high_pos[2]), (1000, 0, 0))
            yield self.wait_until(lambda: float(prop(high, "StunRemaining")) > 0, timeout=.5)
            ball.set_actor_tick_enabled(False)
            self.require(float(prop(high, "StunRemaining")) > 0, "Closest candidate was not physically stunned")
            self.seed_ball(5, (-1800, -1200, 1800))
            yield self.wait(.8)
            self.interact(True)
            yield self.wait_until(lambda: prop(ball, "Holder") == self.pawn, timeout=1)
            self.require(prop(ball, "Holder") == self.pawn, "Human could not reacquire after native impact recovery")
            self.interact(False)
            yield self.wait_until(lambda: not prop(self.pawn, "bInteractHeld"), timeout=1)
        expected = low if mode in ("tie", "stunned") else high
        untouched = high if expected == low else low
        untouched_position = high_pos if untouched == high else low_pos
        scores = self.scores()
        mark = (5730.24, 0, 3048)
        near_mark = lambda actor: sum((a - b) ** 2 for a, b in zip(xyz(actor.get_actor_location()), mark)) < 25
        yield self.wait_until(lambda: near_mark(low) or near_mark(high), timeout=3.4)
        # Native restart teleports the receiver to its prescribed mark. The CPU
        # can immediately collect/throw afterward, so Holder is not a stable
        # observation of which player received the restart.
        untouched_delta = sum((a - b) ** 2 for a, b in zip(xyz(untouched.get_actor_location()), untouched_position))
        self.record(name, near_mark(expected) and not near_mark(untouched)
                    and untouched_delta < 1 and self.scores() == scores,
                    expected_roster_slot=int(prop(expected, "RosterIndex")),
                    low_slot_position=xyz(low.get_actor_location()),
                    high_slot_position=xyz(high.get_actor_location()),
                    high_slot_stun=float(prop(high, "StunRemaining")),
                    low_initial_position=low_pos, high_initial_position=high_pos,
                    score_delta=self.score_delta(scores))

    def scenarios(self):
        self.require(int(prop(self.pawn, "TeamIndex")) == 0, "Fresh PIE human must start on Teal")
        self.require(callable(getattr(self.match, "development_get_bludger_control_seconds", None))
                     and callable(getattr(self.balls[5], "get_distance_since_release_cm", None)),
                     "Loaded DLL lacks the read-only Bludger diagnostics; rebuild and restart")
        self.original_dilation = unreal.GameplayStatics.get_global_time_dilation(self.world)
        unreal.GameplayStatics.set_global_time_dilation(self.world, .15)
        self.provenance["pie_time_dilation"] = .15
        self.provenance["fixture_policy"] = "Owned PIE transforms/tick isolation; ordinary inputs; actual native ball/rule ticks"
        yield from self.toss_case(CASES[0], (-1700, -1200, 1800), (0, 0, 0), False)
        yield from self.toss_case(CASES[1], (-1700, -1200, 1800), (5000, 0, 0), True)
        yield from self.toss_case(CASES[2], (-1700, -1200, 60), (0, 0, -300), True, contact=True)

        yield from self.prepare_held()
        enemy = self.rider(13)
        enemy.set_actor_location(vector((-1800, -1200, 1800)), False, True)
        yield from self.release_for_fixture((-2000, -1200, 1800), (1000, 0, 0))
        released_at = self.now()
        yield self.wait_until(lambda: float(prop(enemy, "StunRemaining")) > 0, timeout=.25)
        ball = self.balls[5]
        ball.set_actor_tick_enabled(False)
        hit_after = self.now() - released_at
        enemy_stun = float(prop(enemy, "StunRemaining"))
        human_stun = float(prop(self.pawn, "StunRemaining"))
        self.record(CASES[3], enemy_stun > 0 and hit_after < .3,
                    hit_after_seconds=hit_after, opponent_stun_seconds=enemy_stun,
                    accumulated_distance_cm=float(ball.get_distance_since_release_cm()))
        self.record(CASES[4], enemy_stun > 0 and human_stun == 0 and hit_after < .3,
                    human_stun_seconds=human_stun, opponent_stun_seconds=enemy_stun,
                    initial_ball_position="inside the releasing rider capsule")
        # Expire launch and impact recovery through real native flight steps,
        # then aim this same released ball back at its thrower. The fixture only
        # changes free-ball transform/velocity, preserving thrower identity.
        enemy.set_actor_location(vector((0, 18000, 1800)), False, True)
        self.seed_ball(5, (0, -2000, 1800), (0, 0, 0))
        yield self.wait(.8)
        self.seed_ball(5, (-2150, -1200, 1800), (1000, 0, 0))
        yield self.wait_until(lambda: float(prop(self.pawn, "StunRemaining")) > 0, timeout=.3)
        ball.set_actor_tick_enabled(False)
        self.record(CASES[5], float(prop(self.pawn, "StunRemaining")) > 0,
                    thrower_stun_seconds=float(prop(self.pawn, "StunRemaining")),
                    velocity=xyz(ball.get_flight_velocity()))
        # Let the impact recipient's native recovery finish before later cases.
        enemy.set_actor_tick_enabled(True)
        yield self.wait_until(lambda: float(prop(enemy, "StunRemaining")) <= 0
                             and float(prop(self.pawn, "StunRemaining")) <= 0, timeout=2)
        enemy.set_actor_tick_enabled(False)

        yield from self.restart_case(CASES[6], "nearest")
        yield from self.restart_case(CASES[7], "tie")
        yield from self.restart_case(CASES[8], "stunned")


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "planned_tests": list(CASES), "count": len(CASES)}
    test = NativeBludgerTests()
    try:
        started = test.begin()
    except Exception:
        test.finish("error", traceback.format_exc())
        started = False
    if unreal and started:
        unreal._basketbroom_native_test = test
        unreal._basketbroom_bludger_test = test
    return {"status": "started" if started else test.final_status,
            "report": str(REPORT), "planned_cases": len(CASES)}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

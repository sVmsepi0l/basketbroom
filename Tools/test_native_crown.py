"""RETIRED: superseded by the closed pyramid-net amendment on 2026/09/14.

Ordinary No Crown attribution, delayed enforcement and native restitution.

Owns/discards one PIE world. Inputs use the ordinary queued rider/RPC path;
free-ball transforms/velocities use the guarded physical fixture. There are no
score, penalty, clock, ownership or rule-state setters. CPU movement is isolated
to observe actual restart selection. Report: .local/native-crown-test-results.json.
"""

import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/native-crown-test-results.json"
CASES = (
    "unknown_exit_returns_without_penalty",
    "carried_exit_attributes_ordinary_foul_to_carrier",
    "other_ball_flight_and_live_clock_continue_during_crown_return",
    "penalty_flag_survives_neutral_reentry",
    "next_stoppage_awards_scoring_ball_to_eligible_opposing_chaser",
    "released_ball_keeps_responsibility_after_launch_clearance_expires",
    "incidental_net_bank_preserves_thrower_responsibility",
    "neutral_stoppage_removes_prior_release_responsibility",
    "carried_bludger_exit_attributes_hurleyback",
    "bludger_crown_restoration_uses_nearest_opposing_hurleyback",
)
spec = importlib.util.spec_from_file_location(
    "_basketbroom_crown_scaffold", ROOT / "Tools/test_native_playable.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.TEST_NAMES, base.REPORT = CASES, REPORT
base.ARGS = {"max_wall_seconds": 300, **globals().get("BRIDGE_ARGS", {})}
unreal, prop, xyz, vector = base.unreal, base.prop, base.xyz, base.vector


class NativeCrownTests(base.NativePlayableTests):
    def __init__(self):
        self.original_dilation = None
        super().__init__()

    def write_report(self, status, reason=None):
        tests = [{"name": name, **self.results.get(name, {"status": "not_run"})} for name in CASES]
        data = {"status": status, "phase": self.phase,
                "scope": "native single-world ordinary No Crown PIE integration",
                "elapsed_wall_seconds": round(time.monotonic() - self.started, 3),
                "passed": sum(t["status"] == "passed" for t in tests),
                "failed": sum(t["status"] == "failed" for t in tests),
                "not_run": sum(t["status"] == "not_run" for t in tests),
                "tests": tests, "events": self.events, "provenance": self.provenance,
                "not_covered": ["intent/repetition judgments for Dead-Roof Delay", "remote replication",
                                "false-start or penalty-shot systems", "autonomous CPU tactics"]}
        if reason:
            data["reason"] = reason
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")

    def finish(self, status, reason=None):
        if unreal and self.world and self.original_dilation is not None:
            try:
                unreal.GameplayStatics.set_global_time_dilation(self.world, self.original_dilation)
                self.provenance["pie_dilation_restored"] = self.original_dilation
            except Exception:
                status, reason = "error", (reason or "") + traceback.format_exc()
            self.original_dilation = None
        super().finish(status, reason)

    def crown_state(self, index):
        result = [int(v) for v in self.match.development_get_crown_penalty_state(index)]
        self.require(len(result) == 6, "Unexpected read-only Crown diagnostic schema")
        return result

    def rider(self, slot):
        return next(r for r in self.riders if int(prop(r, "RosterIndex")) == slot)

    def isolate_equipment(self):
        self.isolate()
        for index, ball in self.balls.items():
            if prop(ball, "bActive") and prop(ball, "Holder") is None:
                self.require(ball.development_set_flight_fixture(
                    vector((0, 22000 + index * 500, 1800)), vector((0, 0, 0))), "Could not isolate free ball")
        self.move_pawn((-2000, -1200, 1800))

    def prepare(self, role=3):
        self.interact(False)
        if prop(self.match, "bLive"):
            self.request(5)
            yield self.wait_until(lambda: not prop(self.match, "bLive"), timeout=2)
        self.require(not prop(self.match, "bLive"), "Official stoppage fixture failed")
        if int(prop(self.pawn, "Position")) != role:
            self.request(2, role)
            yield self.wait_until(lambda: int(prop(self.pawn, "Position")) == role, timeout=2)
        self.require(int(prop(self.pawn, "Position")) == role, "Required position change failed")
        self.isolate_equipment()
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")), timeout=2)
        self.require(prop(self.match, "bLive"), "Official resume failed")
        self.isolate_equipment()  # first kickoff restores legal starts

    def take(self, index, role=3):
        yield from self.prepare(role)
        ball = self.seed_ball(index, (-1800, -1200, 1800))
        yield self.wait(.8)  # native pickup recovery, no cooldown writes
        self.interact(True)
        yield self.wait_until(lambda: prop(ball, "Holder") == self.pawn, timeout=2)
        self.require(prop(ball, "Holder") == self.pawn, "Ordinary pickup did not complete")
        self.interact(False)
        yield self.wait_until(lambda: not prop(self.pawn, "bInteractHeld"), timeout=1)

    def release(self, index):
        ball = self.balls[index]
        ball.set_actor_tick_enabled(False)
        self.request(1)
        yield self.wait_until(lambda: prop(ball, "Holder") is None, timeout=1)
        self.require(prop(ball, "Holder") is None, "Ordinary release did not complete")

    def wait_dead(self, index):
        yield self.wait_until(lambda: str(prop(self.balls[index], "BallStatus")) == "crown", timeout=1)
        self.require(str(prop(self.balls[index], "BallStatus")) == "crown", "Actual roof crossing did not become dead")

    def wait_return(self, index):
        yield self.wait_until(lambda: bool(prop(self.balls[index], "bActive")), timeout=2)
        self.require(prop(self.balls[index], "bActive"), "Native neutral Crown return did not occur")
        self.balls[index].set_actor_tick_enabled(False)

    def restore(self, index, candidate_slot, farther_slot=None):
        ball = self.balls[index]
        mark = ball.get_actor_location()
        candidate = self.rider(candidate_slot)
        candidate.set_actor_location(vector((mark.x + 700, mark.y, 3806.24)), False, True)
        if farther_slot is not None:
            self.rider(farther_slot).set_actor_location(vector((mark.x + 1400, mark.y, 3806.24)), False, True)
        self.request(5)
        yield self.wait_until(lambda: not prop(self.match, "bLive") and self.crown_state(index)[1] == 0, timeout=2)
        self.require(not prop(self.match, "bLive"), "Could not administer Crown foul at stoppage")
        self.require(self.crown_state(index)[2] > 0 and str(prop(ball, "BallStatus")) == "crown_restart",
                     "Stoppage lost the unserved restorative restart")
        self.request(4)
        yield self.wait_until(lambda: self.crown_state(index)[2] == 0, timeout=2)
        self.require(prop(self.match, "bLive"), "Crown restart prevented ordinary live resume")
        return candidate

    def scenarios(self):
        self.require(callable(getattr(self.match, "development_get_crown_penalty_state", None)),
                     "Loaded native module lacks the read-only Crown diagnostic")
        self.original_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        unreal.GameplayStatics.set_global_time_dilation(self.world, .2)
        self.provenance["owned_world_dilation"] = .2
        scores = self.scores()

        yield from self.prepare()
        ball = self.seed_ball(0, (-2000, -1200, 4000), (0, 0, 900))
        yield from self.wait_dead(0)
        no_foul_at_exit = self.crown_state(0)[0] == 0
        yield from self.wait_return(0)
        self.record(CASES[0], no_foul_at_exit and self.crown_state(0)[0] == 0
                    and prop(ball, "Holder") is None and self.scores() == scores,
                    state=self.crown_state(0), location=xyz(ball.get_actor_location()), scores=self.scores())

        yield from self.take(1)
        offender = int(prop(self.pawn, "RosterIndex"))
        other = self.seed_ball(2, (1000, 1000, 1500), (300, 0, 0))
        other_start = other.get_actor_location().x
        live_before = float(prop(self.match, "LiveSeconds"))
        self.move_pawn((-2000, -1200, 4300))
        yield from self.wait_dead(1)
        state = self.crown_state(1)
        self.record(CASES[1], state[0:3] == [1, 1, 1] and state[3] == offender
                    and prop(self.balls[1], "Holder") is None and int(prop(self.match, "PendingPenaltyCount")) == 1,
                    state=state, expected_offender=offender, summary=str(prop(self.match, "PendingPenaltySummary")))
        yield self.wait(.25)
        self.record(CASES[2], bool(prop(self.match, "bLive")) and prop(other, "bActive")
                    and other.get_actor_location().x - other_start > 40
                    and float(prop(self.match, "LiveSeconds")) > live_before + .2,
                    other_ball_delta_x=other.get_actor_location().x - other_start,
                    live_clock_delta=float(prop(self.match, "LiveSeconds")) - live_before)
        other.set_actor_tick_enabled(False)
        yield from self.wait_return(1)
        self.record(CASES[3], self.crown_state(1)[1:3] == [1, 1]
                    and int(prop(self.match, "PendingPenaltyCount")) == 1
                    and bool(str(prop(self.match, "PendingPenaltySummary"))), state=self.crown_state(1))
        candidate = yield from self.restore(1, 9)
        self.record(CASES[4], self.crown_state(1)[4] == 9 and self.crown_state(1)[2] == 0
                    and int(prop(candidate, "Position")) == 1 and prop(self.balls[1], "Holder") == candidate
                    and self.scores() == scores, state=self.crown_state(1), receiver_position=int(prop(candidate, "Position")))

        yield from self.take(0)
        offender = int(prop(self.pawn, "RosterIndex"))
        yield from self.release(0)
        self.seed_ball(0, (-1700, -1200, 3800), (0, 0, 0))
        yield self.wait(.25)  # exceed .15s launch exemption using real steps
        self.seed_ball(0, (-1700, -1200, 4000), (0, 0, 900))
        yield from self.wait_dead(0)
        self.record(CASES[5], self.crown_state(0)[0:3] == [1, 1, 1]
                    and self.crown_state(0)[3] == offender, state=self.crown_state(0), expected_offender=offender)
        yield from self.wait_return(0)
        yield from self.restore(0, 9)

        yield from self.take(2)
        offender = int(prop(self.pawn, "RosterIndex"))
        yield from self.release(2)
        ball = self.seed_ball(2, (0, 3070, 4000), (0, 1500, 1400))
        yield self.wait_until(lambda: ball.get_flight_velocity().y < 0, timeout=.14)
        bank_velocity = xyz(ball.get_flight_velocity())
        yield from self.wait_dead(2)
        self.record(CASES[6], bank_velocity[1] < 0 and self.crown_state(2)[0:3] == [1, 1, 1]
                    and self.crown_state(2)[3] == offender,
                    observed_bank_velocity=bank_velocity, state=self.crown_state(2), expected_offender=offender)
        yield from self.wait_return(2)
        yield from self.restore(2, 9)

        yield from self.take(0)
        count_before = self.crown_state(0)[0]
        yield from self.release(0)
        self.request(5)
        yield self.wait_until(lambda: not prop(self.match, "bLive"), timeout=2)
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")), timeout=2)
        self.seed_ball(0, (-1700, -1200, 4000), (0, 0, 900))
        yield from self.wait_dead(0)
        yield from self.wait_return(0)
        self.record(CASES[7], self.crown_state(0)[0] == count_before
                    and self.crown_state(0)[1:3] == [0, 0], state=self.crown_state(0), earlier_total=count_before)

        yield from self.take(5, role=4)
        offender = int(prop(self.pawn, "RosterIndex"))
        self.move_pawn((-2000, -1200, 4300))
        yield from self.wait_dead(5)
        self.record(CASES[8], self.crown_state(5)[0:3] == [1, 1, 1]
                    and self.crown_state(5)[3] == offender, state=self.crown_state(5), expected_offender=offender)
        yield from self.wait_return(5)
        candidate = yield from self.restore(5, 14, farther_slot=13)
        self.record(CASES[9], self.crown_state(5)[4] == 14 and self.crown_state(5)[2] == 0
                    and int(prop(candidate, "Position")) == 4 and self.scores() == scores,
                    state=self.crown_state(5), receiver=xyz(candidate.get_actor_location()), scores=self.scores())


def main():
    # Keep historical cases/classes available for source inspection, but never
    # start PIE against a rule the user has removed. A separate receipt leaves
    # earlier real test evidence untouched.
    retired_report = ROOT / ".local/native-crown-retired-results.json"
    data = {"status": "not_run", "retired": True,
            "reason": "No Crown was retired by the closed pyramid-net amendment on 2026/09/14.",
            "replacement": "Tools/test_native_pyramid_net.py",
            "passed": 0, "failed": 0, "not_run": len(CASES),
            "planned_tests": [], "historical_tests": list(CASES),
            "count": 0, "historical_count": len(CASES),
            "tests": [{"name": name, "status": "not_run"} for name in CASES],
            "pie_started": False, "report": str(retired_report)}
    retired_report.parent.mkdir(parents=True, exist_ok=True)
    retired_report.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

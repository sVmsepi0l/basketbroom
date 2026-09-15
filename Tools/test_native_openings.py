"""Observe native kickoff/period layouts through real practice match clocks.

Owns a disposable PIE session, using the Snitch suite's proven practice URL and
settings cleanup. CPU movement and ball ticks are isolated, while MatchState
continues ticking. Four actual 180-second quarters and one 120-second overtime
run at 20x world dilation; no clock, phase, score, or availability is assigned.
The standalone host UI net mode must be configured as for test_native_snitch.py.
"""

import importlib.util as _arena_importlib
from pathlib import Path as _ArenaPath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)

import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/native-opening-test-results.json"
CASES = (
    "native_practice_configuration",
    "initial_kickoff_puts_whole_riders_behind_quarter_lines",
    "initial_kickoff_uses_neutral_ball_marks",
    "actual_quark_goals_create_nonzero_tie_for_period_transitions",
    "ordinary_official_stoppage_preserves_field_positions",
    "quarter_two_restores_legal_neutral_opening",
    "quarter_three_restores_legal_neutral_opening",
    "quarter_four_restores_legal_neutral_opening",
    "overtime_restores_neutral_layout_with_all_seven_balls",
    "donnybrook_starts_at_goal_lines_with_only_quarks_and_snipe",
    "play_settings_restored_and_pie_ended",
)

# Private instance: preserve the other suite's globals and report independently.
spec = importlib.util.spec_from_file_location(
    "_basketbroom_opening_scaffold", ROOT / "Tools/test_native_snitch.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.TESTS = CASES
base.REPORT = REPORT
base.ARGS = {"max_wall_seconds": 240, **globals().get("BRIDGE_ARGS", {})}
unreal, prop = base.unreal, base.prop


def coordinates(point):
    return [round(float(point.x), 3), round(float(point.y), 3), round(float(point.z), 3)]


class NativeOpeningTests(base.NativeSnitchTests):
    def write_report(self, status, reason=None):
        if reason:
            self.reason = reason
        tests = [{"name": name, **self.results.get(name, {"status": "not_run"})} for name in CASES]
        data = {
            "status": status, "phase": self.phase,
            "scope": "native practice PIE opening layouts across actual quarter/phase transitions",
            "elapsed_wall_seconds": round(time.monotonic() - self.started, 3),
            "passed": sum(t["status"] == "passed" for t in tests),
            "failed": sum(t["status"] == "failed" for t in tests),
            "not_run": sum(t["status"] == "not_run" for t in tests),
            "tests": tests, "events": self.events, "provenance": self.provenance,
            "reason": self.reason, "settings_restored": self.settings_restored,
            "dilation_restored": self.dilation_restored,
            "external_restore_required": base.net_mode_restore_actions(self.provenance),
            "not_covered": ["remote replication", "false-start adjudication", "CPU tactics",
                            "44-minute regulation clock duration", "FINAL rematch"],
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")

    def positions(self):
        return {
            "riders": {int(prop(r, "RosterIndex")): coordinates(r.get_actor_location()) for r in self.riders},
            "balls": {i: coordinates(b.get_actor_location()) for i, b in self.balls.items()},
        }

    def rider_layout(self, donnybrook=False):
        boundary = dimensions.GOAL_PLANE_X if donnybrook else dimensions.GOAL_PLANE_X / 2
        rows = []
        for rider in self.riders:
            pos = rider.get_actor_location()
            radius = self.component(rider, unreal.CapsuleComponent).get_scaled_capsule_radius()
            sign = -1 if int(prop(rider, "TeamIndex")) == 0 else 1
            legal = sign * float(pos.x) - radius >= boundary - .1
            rows.append({"slot": int(prop(rider, "RosterIndex")), "position": coordinates(pos),
                         "capsule_radius": radius, "behind_required_line": legal})
        return len(rows) == 16 and all(row["behind_required_line"] for row in rows), rows

    def ball_layout(self, active):
        marks = {0: (0, 0, None), 1: (0, -1066.8, None), 2: (0, 1066.8, None),
                 3: (0, 0, 670.56), 4: (0, 0, 3048),
                 5: (0, -2133.6, None), 6: (0, 2133.6, None)}
        rows = []
        for index, ball in self.balls.items():
            pos = coordinates(ball.get_actor_location())
            expected = marks[index]
            # The bible does not specify scoring/hazard launch altitude. Assert
            # only that it is above the floor and below the roof eaves.
            geometry = all(target is None or abs(value - target) < .1 for value, target in zip(pos, expected))
            geometry = geometry and 65 < pos[2] < dimensions.EAVE_HEIGHT
            velocity = coordinates(ball.get_flight_velocity())
            rows.append({"ball": index, "position": pos, "velocity": velocity,
                         "geometry_correct": geometry, "active": bool(prop(ball, "bActive")),
                         "held": prop(ball, "Holder") is not None})
        correct = (all(row["geometry_correct"] and not row["held"] and all(abs(v) < .01 for v in row["velocity"])
                       for row in rows)
                   and {row["ball"] for row in rows if row["active"]} == set(active))
        return correct, rows

    def disturb_positions(self):
        # Physical fixture only: provide a different arrangement for the next
        # opening to replace. All riders remain far from the isolated balls.
        for rider in self.riders:
            slot = int(prop(rider, "RosterIndex"))
            sign = -1 if slot < 8 else 1
            rider.set_actor_location(unreal.Vector(sign * 5000, (slot % 8 - 3.5) * 500, 2500), False, True)
        ball = self.balls[0]
        self.require(ball.development_set_flight_fixture(unreal.Vector(-1200, 900, 1900), unreal.Vector(0, 0, 0)),
                     "Could not arrange the free Quaffle for a later neutral reset")

    def resume(self):
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")), timeout=10)
        self.require(prop(self.match, "bLive"), "Host could not resume the observed period break")

    def scenarios(self):
        self.require(bool(prop(self.match, "bPractice")), "Practice URL must reach native GameMode")
        self.record(CASES[0], abs(float(prop(self.match, "SecondsLeft")) - 180) < .01,
                    practice=bool(prop(self.match, "bPractice")), quarter_seconds=float(prop(self.match, "SecondsLeft")))
        # Base isolation disables CPU movement and every ball's actor tick. The
        # human movement component is also disabled, retaining native input/RPC
        # Tick so the initial layout remains measurable after the horn.
        self.component(self.pawn, unreal.CharacterMovementComponent).set_component_tick_enabled(False)
        yield from self.resume()
        legal, riders = self.rider_layout()
        self.record(CASES[1], legal, riders=riders)
        neutral, balls = self.ball_layout({0, 1, 2, 3, 5, 6})
        self.record(CASES[2], neutral, balls=balls)

        # Establish a nonzero tie through real goal physics before testing score
        # carry. This catches an opening reset that accidentally zeroes scores.
        for index, sign, expected in ((1, 1, [37, 0]), (2, -1, [37, 37])):
            ball = self.seed_ball(index, (sign * (dimensions.GOAL_PLANE_X-200.8), 0, 3048), (sign * 2000, 0, 0))
            yield self.wait_until(lambda: self.scores() == expected, timeout=3)
            ball.set_actor_tick_enabled(False)
            self.require(self.scores() == expected, "Actual Quark fixture did not produce the required observed score")
        self.record(CASES[3], self.scores() == [37, 37], scores=self.scores(), method="Two native whole-ball goal sweeps")

        self.disturb_positions()
        before = self.positions()
        self.request(5)
        yield self.wait_until(lambda: not prop(self.match, "bLive"), timeout=3)
        self.require(str(prop(self.match, "Status")) == "STOPPAGE", "Expected ordinary official stoppage")
        paused = self.positions()
        yield from self.resume()
        after = self.positions()
        self.record(CASES[4], before == paused == after, before=before, paused=paused, after=after)
        self.dilation(20)
        self.provenance["natural_clock_path"] = "Four 180s practice quarters, 120s overtime, 20x owned-world dilation"

        for quarter in (2, 3, 4):
            yield self.wait_until(lambda: not prop(self.match, "bLive"), timeout=190)
            self.require(str(prop(self.match, "Status")) == "QUARTER BREAK", "Actual regulation quarter horn required")
            yield from self.resume()
            legal, riders = self.rider_layout()
            neutral, balls = self.ball_layout(range(7))
            self.record(CASES[quarter + 3], int(prop(self.match, "Quarter")) == quarter and legal and neutral
                        and self.scores() == [37, 37], quarter=int(prop(self.match, "Quarter")),
                        riders=riders, balls=balls, scores=self.scores())
            self.disturb_positions()

        yield self.wait_until(lambda: str(prop(self.match, "Phase")) == "OVERTIME"
                             and str(prop(self.match, "Status")) == "PHASE BREAK", timeout=195)
        self.require(str(prop(self.match, "Phase")) == "OVERTIME", "Tied fourth-quarter horn must reach overtime")
        yield from self.resume()
        legal, riders = self.rider_layout()
        neutral, balls = self.ball_layout(range(7))
        self.record(CASES[8], legal and neutral and self.scores() == [37, 37]
                    and 100 < float(prop(self.match, "SecondsLeft")) <= 120,
                    riders=riders, balls=balls, scores=self.scores(), overtime_seconds=float(prop(self.match, "SecondsLeft")))
        self.disturb_positions()
        yield self.wait_until(lambda: str(prop(self.match, "Phase")) == "DONNYBROOK"
                             and str(prop(self.match, "Status")) == "PHASE BREAK", timeout=135)
        self.require(str(prop(self.match, "Phase")) == "DONNYBROOK", "Tied overtime horn must reach Donnybrook")
        yield from self.resume()
        legal, riders = self.rider_layout(donnybrook=True)
        neutral, balls = self.ball_layout({1, 2, 3})
        self.record(CASES[9], legal and neutral and self.scores() == [37, 37]
                    and float(prop(self.match, "SecondsLeft")) == 0,
                    riders=riders, balls=balls, scores=self.scores(), seconds=float(prop(self.match, "SecondsLeft")))


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "planned_tests": list(CASES), "count": len(CASES)}
    runner = NativeOpeningTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and started:
        unreal._basketbroom_native_test = runner
        unreal._basketbroom_native_opening_test = runner
    return {"status": "started" if started else runner.final_status, "report": str(REPORT), "planned_cases": len(CASES)}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

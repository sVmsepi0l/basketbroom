"""Explicit native penalty-shot boundary and participant-lifecycle fixtures.

This is separate from ordinary-shot evidence. BRIDGE_ARGS edge may be before,
exact, after, admission, shooter_replacement, or keeper_replacement. Clock-edge
cases intentionally reposition an already released, unheld ball near the real
goal plane; they never change elapsed time, rule state, custody, scores or the
outcome. A measured final-frame hitch must straddle the remaining shot time.
Lifecycle cases use real CreatePlayer/RemovePlayer in the disposable PIE world.
"""

import importlib.util as _arena_importlib
from pathlib import Path as _ArenaPath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)
import importlib.util
import json
from pathlib import Path
import struct
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
ARGS = {"max_wall_seconds": 180, **globals().get("BRIDGE_ARGS", {})}
EDGE = str(ARGS.get("edge", "exact"))
VARIANT = str(ARGS.get("variant", "regulation"))
REPORT = ROOT / ".local" / ("native-penalty-shot-edge-%s-%s-results.json" % (VARIANT, EDGE))
_spec = importlib.util.spec_from_file_location("_bb_shot_edge_base", ROOT / "Tools/test_native_penalty_shots_playable.py")
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)
CASES = core.CASES[:7] + (
    "explicit_boundary_or_lifecycle_fixture_is_observed",
    "native_deadline_or_reserved_participant_contract_holds",
    "global_clocks_and_penalty_identity_survive_boundary_or_lifecycle_event",
)
core.ARGS, core.REPORT, core.VARIANT, core.OUTCOME = ARGS, REPORT, VARIANT, "make"
core.AFFECTED_BALL = 1 if EDGE == "keeper_replacement" else 0
core.CASES = CASES
base = core.base
base.TEST_NAMES, base.REPORT, base.ARGS = CASES, REPORT, ARGS
unreal, prop, xyz, vector = core.unreal, core.prop, core.xyz, core.vector


def f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


class PenaltyShotEdgeTests(core.NativePenaltyShotTests):
    def write_report(self, status, reason=None):
        data = core.receipts.single_world_payload(self, CASES, status, reason,
                                                   unreal.SystemLibrary.get_engine_version() if unreal else None)
        data.update(scope="explicit native deadline geometry / real participant lifecycle fixtures", edge=EDGE, variant=VARIANT,
                    fixture_policy="Clock-edge cases arrange free-ball position and velocity AFTER real shot release, then "
                                   "observe native collision and shot-clock resolution. Lifecycle cases use actual CreatePlayer/RemovePlayer. "
                                   "No rule clock, score, custody, penalty, effect or outcome is set.",
                    not_covered=["ordinary unmodified penalty shot trajectory (separate paired suite)",
                                 "network replication / separate-process disconnect", "physical controls and visual judgement"])
        core.receipts.write_json_atomic(REPORT, data)

    def timing(self):
        fn = getattr(self.match, "development_get_penalty_shot_timing", None)
        self.require(callable(fn), "Loaded DLL needs the read-only fractional shot timing diagnostic")
        values = [float(value) for value in fn()]
        self.require(len(values) == 3, "Timing diagnostic must be elapsed, duration, remaining")
        return dict(zip(("elapsed_ms", "duration_ms", "remaining_ms"), values))

    def remove_local(self, controller):
        self.controller_ticks = [(c, enabled) for c, enabled in self.controller_ticks if c != controller]
        if controller in self.extra_controllers:
            self.extra_controllers.remove(controller)
        unreal.GameplayStatics.remove_player(controller, True)

    def roster_refresh(self):
        self.riders = list(unreal.GameplayStatics.get_all_actors_of_class(self.world, self.classes["BBRiderCharacter"]))
        return len(self.riders) == 16 and self.roster_valid()

    def prepare_keeper_human(self):
        self.request(5)
        yield self.wait_until(lambda: not prop(self.match, "bLive"), timeout=1)
        self.keeper_controller = unreal.GameplayStatics.create_player(self.world, -1, True)
        self.require(self.keeper_controller is not None, "Third local keeper player must be created")
        self.extra_controllers.append(self.keeper_controller)
        yield self.wait_until(lambda: unreal.GameplayStatics.get_player_pawn(self.world, 2) is not None, timeout=1)
        self.keeper_human = unreal.GameplayStatics.get_player_pawn(self.world, 2)
        self.require(self.keeper_human is not None, "Third local keeper needs a pawn")
        self.require(self.keeper_human.development_request_action(3, 0), "Keeper team request queue failed")
        yield self.wait_until(lambda: int(prop(self.keeper_human, "TeamIndex")) == 0, timeout=1)
        self.require(self.keeper_human.development_request_action(2, 0), "Keeper role request queue failed")
        yield self.wait_until(lambda: int(prop(self.keeper_human, "Position")) == 0, timeout=1)
        self.require(int(prop(self.keeper_human, "TeamIndex")) == int(prop(self.keeper_human, "Position")) == 0,
                     "Actual human keeper selection must be accepted during stoppage")
        self.roster_refresh()
        self.request(4)
        yield self.wait_until(lambda: prop(self.match, "bLive"), timeout=1)
        self.isolate()
        yield from self.anchor_pair()

    def boundary(self):
        diagnostic = self.diagnostic()
        clock = self.clocks()
        # Release through native rider action first, then label all following
        # flight arrangement as boundary-test geometry in the receipt.
        self.guest_request(1)
        yield self.wait_until(lambda: self.diagnostic()["stage"] == 2, timeout=.5)
        self.require(self.diagnostic()["stage"] == 2 and prop(self.shot_ball, "Holder") is None,
                     "Boundary fixture needs a genuinely released penalty ball")
        radius = float(self.shot_ball.get_collision_radius())
        self.require(radius == 65, "Boundary goal geometry must agree with the actual scoring ball")
        fixtures = []

        def keep_safe():
            if self.diagnostic()["stage"] == 2:
                self.require(self.shot_ball.development_set_flight_fixture(vector((0, 0, 2800)), vector((0, 0, 0))),
                             "Holding boundary geometry requires an active, unheld authority ball")
                fixtures.append(self.timing())

        keep_safe()
        yield self.wait_until(lambda: self.timing()["remaining_ms"] <= 350, keep_safe, timeout=5)
        before = self.timing()
        self.require(self.diagnostic()["stage"] == 2 and 40 < before["remaining_ms"] <= 350,
                     "Observed native remaining shot time must bracket the boundary fixture")
        offset_ms = {"before": -20, "exact": 0, "after": 20}[EDGE]
        crossing_ms = before["remaining_ms"]+offset_ms
        speed = 4400.0
        plane = -f32(f32(dimensions.GOAL_PLANE_X)+radius)
        start = (plane + speed*crossing_ms/1000, 0, 2103.12)
        self.require(self.shot_ball.development_set_flight_fixture(vector(start), vector((-speed, 0, 0))),
                     "Final boundary flight fixture must be accepted without changing shot state")
        began = self.now()
        # This changes only time dilation on the owned disposable PIE world.
        # The receipt requires an observed frame crossing the remaining time.
        unreal.GameplayStatics.set_global_time_dilation(self.world, 32)
        after_frames = []

        def observe():
            after_frames.append({"world_seconds_since_fixture": self.now()-began, "timing": self.timing(),
                                 "diagnostic": self.diagnostic(), "point": xyz(self.shot_ball.get_actor_location())})

        yield self.wait_until(lambda: self.diagnostic()["outcome"] != 0, observe, timeout=20)
        observe()
        unreal.GameplayStatics.set_global_time_dilation(self.world, .5)
        self.record(CASES[7], bool(after_frames) and before["remaining_ms"] > 40,
                    explicit_post_release_fixture=True, safe_fixture_count=len(fixtures), before=before,
                    offset_ms=offset_ms, crossing_ms=crossing_ms, full_ball_plane_x=plane,
                    radius=radius, start=start, velocity=[-speed, 0, 0], frames=after_frames)
        expected_outcome = 1 if EDGE == "before" else 3
        expected_points = 13 if EDGE == "before" else 0
        result = self.diagnostic()
        self.record(CASES[8], result["outcome"] == expected_outcome and self.scores() == [0, expected_points],
                    result=result, expected_outcome=expected_outcome, scores=self.scores(), expected_points=expected_points)
        # A later frame can straddle the deadline even if the first frame
        # after arranging the ball was shorter than the original remainder.
        # Compare each actual frame with the remaining time observed before it.
        hitch_frames = []
        previous_world, previous_remaining = 0.0, before["remaining_ms"]
        previous_active = True
        for row in after_frames:
            frame_seconds = row["world_seconds_since_fixture"]-previous_world
            if previous_active and frame_seconds >= previous_remaining/1000 and previous_remaining > 0:
                hitch_frames.append({"frame_seconds": frame_seconds, "remaining_ms_before_frame": previous_remaining,
                                     "world_seconds_after_fixture": row["world_seconds_since_fixture"]})
            previous_world = row["world_seconds_since_fixture"]
            previous_remaining = row["timing"]["remaining_ms"]
            previous_active = row["diagnostic"]["stage"] in (1, 2)
        hitch = bool(hitch_frames)
        self.record(CASES[9], hitch and self.clocks() == clock and result["penalty_id"] == diagnostic["penalty_id"]
                    and abs(self.removal()-180) < .03, observed_frame_straddles_deadline=hitch, hitch_frames=hitch_frames,
                    clocks_before=clock, clocks_after=self.clocks(), removal=self.removal(), result=result)

    def lifecycle(self):
        # Observe replacement identity before a newly created CPU can reach its
        # normal 1.25-second automatic shot. The live rule clock is still frozen.
        unreal.GameplayStatics.set_global_time_dilation(self.world, .1)
        self.provenance["lifecycle_observation_dilation"] = .1
        original = self.diagnostic()
        timing = self.timing()
        clocks = self.clocks()
        old_shooter, old_keeper = self.shooter, self.keeper
        if EDGE == "admission":
            controller = unreal.GameplayStatics.create_player(self.world, -1, True)
            self.require(controller is not None, "A real joining local player must be created")
            self.extra_controllers.append(controller)
            yield self.wait_until(lambda: unreal.GameplayStatics.get_player_pawn(self.world, 2) is not None and self.roster_refresh(), timeout=1)
            joined = unreal.GameplayStatics.get_player_pawn(self.world, 2)
            self.require(joined is not None, "New local participant must receive a native pawn")
            event_ok = int(prop(joined, "RosterIndex")) not in (original["shooter"], original["keeper"])
            details = {"new_slot": int(prop(joined, "RosterIndex")), "reserved_slots": [original["shooter"], original["keeper"]]}
            contract = event_ok and prop(self.shot_ball, "Holder") == old_shooter and old_keeper in self.riders
        else:
            is_shooter = EDGE == "shooter_replacement"
            controller = self.guest_controller if is_shooter else self.keeper_controller
            old = old_shooter if is_shooter else old_keeper
            reserved_slot = original["shooter"] if is_shooter else original["keeper"]
            self.remove_local(controller)
            self.roster_refresh()
            for rider in self.riders:
                if int(prop(rider, "RosterIndex")) == reserved_slot and rider != old:
                    rider.set_actor_tick_enabled(False)
            if is_shooter:
                self.guest = self.guest_controller = None
            yield self.wait_until(lambda: self.roster_refresh() and any(int(prop(r, "RosterIndex")) == reserved_slot and r != old for r in self.riders), timeout=1)
            replacement = next((r for r in self.riders if int(prop(r, "RosterIndex")) == reserved_slot and r != old), None)
            self.require(replacement is not None, "Actual departed slot must receive a distinct native replacement")
            replacement.set_actor_tick_enabled(False)
            event_ok = not replacement.is_player_controlled() and int(prop(replacement, "RosterIndex")) == reserved_slot
            point = xyz(replacement.get_actor_location())
            if is_shooter:
                contract = prop(self.shot_ball, "Holder") == replacement and abs(point[0]+5059.68) < 1
            else:
                contract = abs(point[0]+6220.8) < 1 and abs(point[2]-3048) < 1 and int(prop(replacement, "Position")) == 0
            details = {"reserved_slot": reserved_slot, "replacement_point": point, "replacement_role": int(prop(replacement, "Position")),
                       "replacement_is_cpu": not replacement.is_player_controlled(), "held_by_replacement": prop(self.shot_ball, "Holder") == replacement}
        after = self.diagnostic()
        later = self.timing()
        self.record(CASES[7], event_ok and self.roster_refresh(), event=EDGE, **details)
        self.record(CASES[8], contract and after["stage"] == 1 and after["pending"] == 1
                    and after["shooter"] == original["shooter"] and after["keeper"] == original["keeper"],
                    before=original, after=after, **details)
        self.record(CASES[9], self.clocks() == clocks and after["penalty_id"] == original["penalty_id"]
                    and later["elapsed_ms"] > timing["elapsed_ms"] and later["remaining_ms"] < timing["remaining_ms"],
                    clocks_before=clocks, clocks_after=self.clocks(), timing_before=timing, timing_after=later)

    def scenarios(self):
        self.require(EDGE in ("before", "exact", "after", "admission", "shooter_replacement", "keeper_replacement"), "Unknown edge fixture")
        yield from self.prepare()
        if EDGE == "keeper_replacement":
            yield from self.prepare_keeper_human()
        yield from self.foul()
        yield from self.start_shot()
        if EDGE in ("before", "exact", "after"):
            yield from self.boundary()
        else:
            yield from self.lifecycle()


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "cases_per_run": len(CASES), "planned_cases": list(CASES),
                "edges": ["before", "exact", "after", "admission", "shooter_replacement", "keeper_replacement"]}
    test = PenaltyShotEdgeTests()
    try:
        started = test.begin()
    except Exception:
        test.finish("error", traceback.format_exc())
        started = False
    if unreal and started:
        unreal._basketbroom_native_test = test
    return {"status": "started" if started else test.final_status, "report": str(REPORT), "planned_cases": len(CASES), "edge": EDGE}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

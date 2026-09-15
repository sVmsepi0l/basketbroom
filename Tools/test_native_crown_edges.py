"""RETIRED: superseded by the closed pyramid-net amendment on 2026/09/14.

Physical Crown-restoration edges in an owned disposable PIE session.

Five real Bludger impacts temporarily make all eligible opposing receivers
unavailable. One then recovers naturally while the human holds another Quark
near the Crown mark, high above it and aiming down. This exercises actual late
restart spacing without assigning stun, custody, penalty or rules fields.
"""

import importlib.util
import json
from pathlib import Path
import sys
import traceback


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/native-crown-edge-test-results.json"
CASES = (
    "crown_restart_remains_dead_while_all_eligible_opponents_are_stunned",
    "awarded_recipient_carries_whole_scoring_ball_inside_near_end_net",
    "spacing_preserves_high_opponents_downward_aim_and_carried_ball_legality",
    "crown_spacing_chooses_inward_horizontal_position_inside_capsule_bounds",
)
spec = importlib.util.spec_from_file_location(
    "_basketbroom_crown_edge_scaffold", ROOT / "Tools/test_native_crown.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.CASES, base.REPORT = CASES, REPORT
base.base.TEST_NAMES, base.base.REPORT = CASES, REPORT
base.base.ARGS = {"max_wall_seconds": 240, **globals().get("BRIDGE_ARGS", {})}
unreal, prop, xyz, vector = base.unreal, base.prop, base.xyz, base.vector


class NativeCrownEdgeTests(base.NativeCrownTests):
    def scenarios(self):
        self.require(callable(getattr(self.match, "development_get_crown_penalty_state", None)),
                     "Loaded native module lacks Crown diagnostics")
        self.original_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        unreal.GameplayStatics.set_global_time_dilation(self.world, .2)
        self.provenance["owned_world_dilation"] = .2
        yield from self.take(1)
        # Own the view from the first roof-exit placement onward. Otherwise a
        # pending PlayerController rotation update can undo the outward yaw and
        # move the recorded mark hundreds of centimetres away from this edge.
        self.controller.set_actor_tick_enabled(False)
        self.controller.set_control_rotation(unreal.Rotator(pitch=0, yaw=180, roll=0))
        yield self.wait_until(lambda: self.pawn.get_aim_direction().x < -.99, timeout=.5)
        self.require(self.pawn.get_aim_direction().x < -.99, "Initial roof exit needs an outward aim")
        self.move_pawn((-6600, 0, 4300))
        yield from self.wait_dead(1)
        yield from self.wait_return(1)
        self.require(self.crown_state(1)[1:3] == [1, 1], "Fixture needs a real pending carried Crown foul")

        # These positions cannot possess Bludgers, so a free incoming impact
        # cannot be intercepted by CPU pickup before its physical collision.
        for ordinal, slot in enumerate((8, 10, 11, 12, 9)):
            opponent = self.rider(slot)
            point = (1000, (ordinal - 2) * 400, 1800)
            opponent.set_actor_location(vector(point), False, True)
            hazard = self.seed_ball(5, (point[0] - 150, point[1], point[2]), (1000, 0, 0))
            yield self.wait_until(lambda: float(prop(opponent, "StunRemaining")) > 0, timeout=.5)
            self.require(float(prop(opponent, "StunRemaining")) > 0, "Physical impact failed for receiver slot%d" % slot)
            self.seed_ball(5, (0, -2000, 1800), (0, 0, 0))
            yield self.wait(.8)  # actual native impact recovery between shots
            hazard.set_actor_tick_enabled(False)
        candidate = self.rider(9)
        # A default AI controller supplies a stable deliberate outward aim for
        # the recipient, independent of MatchState's CPU travel orientation.
        # Both SpawnDefaultController and GetController are public Pawn UFUNCTIONs.
        candidate.spawn_default_controller()
        candidate_control = candidate.get_controller()
        self.require(candidate_control is not None, "Recipient needs its native default controller")
        candidate_control.set_actor_tick_enabled(False)
        candidate_control.set_control_rotation(unreal.Rotator(pitch=0, yaw=180, roll=0))
        candidate.set_actor_location(vector((-5850.8, -35, 3806.24)), False, True)
        self.request(5)
        yield self.wait_until(lambda: not prop(self.match, "bLive") and self.crown_state(1)[1] == 0, timeout=2)
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")), timeout=2)
        yield self.wait(.2)
        state = self.crown_state(1)
        self.record(CASES[0], state[2] == 1 and str(prop(self.balls[1], "BallStatus")) == "crown_restart"
                    and not prop(self.balls[1], "bActive"), state=state,
                    opposing_stuns={slot: float(prop(self.rider(slot), "StunRemaining")) for slot in (8, 9, 10, 11, 12)})
        self.require(state[2] == 1, "The delayed restart must still be awaiting an eligible opponent")

        # Acquire another ball through live E input while the Crown reservation
        # waits. A global pause here would clear possession, so none is used.
        self.move_pawn((-6000, -35, 3600))
        carried = self.seed_ball(2, (-5800, -35, 3600))
        yield self.wait(.8)
        self.interact(True)
        yield self.wait_until(lambda: prop(carried, "Holder") == self.pawn, timeout=2)
        self.require(prop(carried, "Holder") == self.pawn, "Human needs a genuine carried Quark during spacing")
        self.interact(False)
        yield self.wait_until(lambda: not prop(self.pawn, "bInteractHeld"), timeout=1)
        # MatchState can still change ControlRotation directly despite the
        # suspended controller tick; that remains a failure below rather than
        # being overwritten by a per-frame fixture.
        self.controller.set_control_rotation(unreal.Rotator(pitch=-60, yaw=0, roll=0))
        yield self.wait_until(lambda: self.pawn.get_aim_direction().z < -.85, timeout=.5)
        self.require(self.pawn.get_aim_direction().z < -.85,
                     "Downward aim did not settle at safe height: " + str(xyz(self.pawn.get_aim_direction())))
        # The first horizontal push would point out of the near end net; the
        # server must choose the inward direction without raising the rider.
        self.move_pawn((-6600.8, -35, 4170))
        yield self.wait(.15)
        before_position = xyz(self.pawn.get_actor_location())
        before_aim = xyz(self.pawn.get_aim_direction())
        prior_crown_count = self.crown_state(2)[0]
        pending_mark = self.balls[1].get_actor_location()
        intended_restart = (pending_mark.x, pending_mark.y, 3806.24)
        trigger_distance = sum((a - b) ** 2 for a, b in zip(before_position, intended_restart)) ** .5
        self.event("high_carrier_fixture", position=before_position, aim=before_aim,
                   carried_ball=xyz(carried.get_actor_location()),
                   computed_carry=xyz(self.pawn.get_carry_location()),
                   held_by_human=prop(carried, "Holder") == self.pawn,
                   crown_state=self.crown_state(2), pending_ball=xyz(pending_mark),
                   expected_restart=intended_restart, spacing_trigger_distance_cm=trigger_distance)
        self.require(trigger_distance < 396.24,
                     "High carrier must be inside the real restart's 13ft protection radius")
        self.require(prop(carried, "Holder") == self.pawn and carried.get_actor_location().z + 65 < 4206.24,
                     "Downward-facing carried-ball fixture must start fully below the crown")
        self.balls[1].set_actor_tick_enabled(True)
        candidate.set_actor_tick_enabled(True)  # let this one native stun expire
        yield self.wait_until(lambda: self.crown_state(1)[2] == 0, timeout=3)
        yield self.wait(.15)
        restored = self.balls[1]
        center = xyz(restored.get_actor_location())
        outward_aim = xyz(candidate.get_aim_direction())
        self.record(CASES[1], self.crown_state(1)[4] == 9 and prop(restored, "Holder") == candidate
                    and outward_aim[0] < -.99 and center[0] - 65 >= -6850.8,
                    ball_center=center, radius_cm=65, end_net_x=-6850.8,
                    recipient_aim=outward_aim, recipient_position=xyz(candidate.get_actor_location()))
        after_position = xyz(self.pawn.get_actor_location())
        after_aim = xyz(self.pawn.get_aim_direction())
        aim_difference = sum((a - b) ** 2 for a, b in zip(before_aim, after_aim))
        self.record(CASES[2], abs(after_position[2] - before_position[2]) < .1 and aim_difference < .0001
                    and prop(carried, "Holder") == self.pawn and prop(carried, "bActive")
                    and carried.get_actor_location().z + 65 < 4206.24 and self.crown_state(2)[0] == prior_crown_count,
                    before_position=before_position, after_position=after_position,
                    before_aim=before_aim, after_aim=after_aim, carried_ball=xyz(carried.get_actor_location()),
                    crown_state=self.crown_state(2))
        radius = self.component(self.pawn, unreal.CapsuleComponent).get_scaled_capsule_radius()
        mark = candidate.get_actor_location()
        horizontal_distance = ((after_position[0] - mark.x) ** 2 + (after_position[1] - mark.y) ** 2) ** .5
        self.record(CASES[3], after_position[0] > before_position[0] + 300 and horizontal_distance >= 449
                    and abs(after_position[0]) + radius <= 6850.8 and abs(after_position[1]) + radius <= 3200.4,
                    after_position=after_position, capsule_radius=radius, horizontal_separation_cm=horizontal_distance)


def main():
    # Keep historical cases/classes available for source inspection, but never
    # start PIE against a rule the user has removed. A separate receipt leaves
    # earlier real test evidence untouched.
    retired_report = ROOT / ".local/native-crown-edge-retired-results.json"
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

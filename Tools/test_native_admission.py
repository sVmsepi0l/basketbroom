"""Native local-player departure/admission regression in disposable UE5.8 PIE.

Uses public CreatePlayer/RemovePlayer lifecycle APIs, ordinary rider inputs and
actual Crown/Bludger collisions. This is same-world local multiplayer coverage,
not an internet reconnect or account-identity test. No sanction fields are set.
"""
import importlib.util
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/native-admission-test-results.json"
CASES = (
    "clean_local_join_fills_balanced_team_position",
    "departed_penalized_human_is_replaced_by_one_cpu",
    "newcomer_avoids_departed_individual_penalty",
    "newcomer_can_change_role_while_departed_foul_remains_due",
    "departure_and_join_preserve_opponents_crown_reservation",
    "original_opponent_receives_crown_remedy_after_newcomer_joins",
    "all_remaining_cpu_slots_unavailable_admits_only_a_spectator",
)
spec = importlib.util.spec_from_file_location("_basketbroom_admission_scaffold", ROOT / "Tools/test_native_crown.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.CASES, base.REPORT = CASES, REPORT
base.base.TEST_NAMES, base.base.REPORT = CASES, REPORT
base.base.ARGS = {"max_wall_seconds": 240, **globals().get("BRIDGE_ARGS", {})}
unreal, prop, xyz, vector = base.unreal, base.prop, base.xyz, base.vector


class NativeAdmissionTests(base.NativeCrownTests):
    def __init__(self):
        self.extra_controllers = []
        self.match_tick_suspended = False
        super().__init__()

    def write_report(self, status, reason=None):
        super().write_report(status, reason)
        data = json.loads(REPORT.read_text(encoding="utf-8"))
        data["scope"] = "native same-world local-player admission and departure lifecycle"
        data["not_covered"] = ["internet/remote reconnection", "authenticated persistent participant identity",
                               "every-slot historical sanctions (separate portable policy suite)"]
        REPORT.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")

    def refresh_roster(self):
        self.riders = list(unreal.GameplayStatics.get_all_actors_of_class(self.world, self.classes["BBRiderCharacter"]))
        return self.riders

    def join_local(self):
        controller = unreal.GameplayStatics.create_player(self.world, -1, True)
        self.require(controller is not None, "Public CreatePlayer did not create a local participant")
        self.extra_controllers.append(controller)
        return controller

    def leave_local(self, controller):
        unreal.GameplayStatics.remove_player(controller, True)
        self.extra_controllers.remove(controller)

    def guest_input(self, rider, held):
        self.require(rider.development_set_interaction(bool(held)), "Guest interaction was not accepted")
        self.event("guest_interaction", held=bool(held), slot=int(prop(rider, "RosterIndex")))

    def finish(self, status, reason=None):
        if unreal and self.owns_play:
            try:
                if self.match_tick_suspended:
                    self.match.set_actor_tick_enabled(True)
                    self.match_tick_suspended = False
                    self.provenance["owned_match_tick_restored"] = True
                for controller in reversed(self.extra_controllers[:]):
                    self.leave_local(controller)
                self.provenance["extra_local_players_removed"] = True
            except Exception:
                status, reason = "error", (reason or "") + traceback.format_exc()
        super().finish(status, reason)

    def scenarios(self):
        self.original_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        unreal.GameplayStatics.set_global_time_dilation(self.world, .5)
        self.provenance["owned_world_dilation"] = .5
        yield from self.prepare(3)
        guest_control = self.join_local()
        yield self.wait_until(lambda: unreal.GameplayStatics.get_player_pawn(self.world, 1) is not None, timeout=2)
        guest = unreal.GameplayStatics.get_player_pawn(self.world, 1)
        self.require(guest is not None, "Clean local player needs a rider")
        guest_control.set_actor_tick_enabled(False)
        guest_control.set_control_rotation(unreal.Rotator(pitch=0, yaw=0, roll=0))
        self.component(guest, unreal.CharacterMovementComponent).set_component_tick_enabled(False)
        self.refresh_roster()
        self.record(CASES[0], len(self.riders) == 16 and self.roster_valid()
                    and int(prop(guest, "TeamIndex")) == 1 and int(prop(guest, "RosterIndex")) == 12,
                    roster=self.roster(), guest_slot=int(prop(guest, "RosterIndex")))
        self.require(int(prop(guest, "RosterIndex")) == 12, "Fixture expects the initially clean Copper Ranger")

        guest.set_actor_location(vector((-2000, -1200, 1800)), False, True)
        ball = self.seed_ball(1, (-1800, -1200, 1800))
        yield self.wait(.8)
        self.guest_input(guest, True)
        yield self.wait_until(lambda: prop(ball, "Holder") == guest, timeout=2)
        self.require(prop(ball, "Holder") == guest, "Guest must actually possess Quark before its roof exit")
        self.guest_input(guest, False)
        yield self.wait_until(lambda: not prop(guest, "bInteractHeld"), timeout=1)
        guest.set_actor_location(vector((-2200, -1200, 4300)), False, True)
        yield from self.wait_dead(1)
        yield from self.wait_return(1)
        pending = self.crown_state(1)
        self.require(pending[1:4] == [1, 1, 12], "Real carried exit must leave the guest's ordinary Crown foul due")
        self.leave_local(guest_control)
        yield self.wait_until(lambda: len(self.refresh_roster()) == 16 and self.roster_valid()
                             and sum(r.is_player_controlled() for r in self.riders) == 1, timeout=2)
        departed_slot = self.rider(12)
        self.record(CASES[1], len(self.riders) == 16 and self.roster_valid()
                    and not departed_slot.is_player_controlled() and self.crown_state(1) == pending,
                    roster=self.roster(), crown_state=self.crown_state(1))

        newcomer_control = self.join_local()
        yield self.wait_until(lambda: unreal.GameplayStatics.get_player_pawn(self.world, 1) is not None, timeout=2)
        newcomer = unreal.GameplayStatics.get_player_pawn(self.world, 1)
        self.require(newcomer is not None, "Clean alternative slot must admit a new rider")
        newcomer_control.set_actor_tick_enabled(False)
        self.component(newcomer, unreal.CharacterMovementComponent).set_component_tick_enabled(False)
        self.refresh_roster()
        new_slot = int(prop(newcomer, "RosterIndex"))
        self.record(CASES[2], 8 <= new_slot < 16 and new_slot != 12 and self.crown_state(1) == pending
                    and not self.rider(12).is_player_controlled() and self.roster_valid(),
                    newcomer_slot=new_slot, departed_slot=12, crown_state=self.crown_state(1))

        self.request(5)
        yield self.wait_until(lambda: not prop(self.match, "bLive") and self.crown_state(1)[1] == 0, timeout=2)
        self.require(not prop(self.match, "bLive"), "Host must reach a genuine official stoppage")
        self.require(newcomer.development_request_action(2, 2), "Newcomer role request must enter native input queue")
        yield self.wait_until(lambda: int(prop(newcomer, "Position")) == 2, timeout=2)
        state = self.crown_state(1)
        self.record(CASES[3], int(prop(newcomer, "Position")) == 2 and state[2] == 1 and state[3] == 12,
                    newcomer_role=int(prop(newcomer, "Position")), crown_state=state)
        self.record(CASES[4], state[0:4] == [1, 0, 1, 12] and not prop(ball, "bActive")
                    and str(prop(ball, "BallStatus")) == "crown_restart",
                    crown_state=state, status=str(prop(ball, "BallStatus")))

        # Re-isolate the refreshed roster after joins/role changes. The primary
        # human is the sole nearby eligible member of the owed opposing team.
        self.refresh_roster()
        self.isolate_equipment()
        mark = ball.get_actor_location()
        self.move_pawn((mark.x, mark.y, 3806.24))
        self.request(4)
        yield self.wait_until(lambda: self.crown_state(1)[2] == 0 and prop(ball, "Holder") == self.pawn, timeout=2)
        state = self.crown_state(1)
        self.record(CASES[5], state[0] == 1 and state[2] == 0 and state[3] == 12
                    and state[4] == int(prop(self.pawn, "RosterIndex")) and prop(ball, "Holder") == self.pawn,
                    crown_state=state, receiver_team=int(prop(self.pawn, "TeamIndex")))

        # Exercise the no-slot native path with physically stunned CPUs. Freeze
        # only Match's AI decisions to prevent Hurleybacks auto-catching the
        # incoming fixture before collision. Native ball collision and rider
        # stun still execute; already isolated CPU ticks preserve each stun.
        self.match.set_actor_tick_enabled(False)
        self.match_tick_suspended = True
        for rider in self.refresh_roster():
            if rider.is_player_controlled():
                continue
            slot = int(prop(rider, "RosterIndex"))
            rider.set_actor_location(vector((1000, 0, 1800)), False, True)
            hazard = self.seed_ball(5, (850, 0, 1800), (1000, 0, 0))
            yield self.wait_until(lambda: float(prop(rider, "StunRemaining")) > 0, timeout=.5)
            self.require(float(prop(rider, "StunRemaining")) > 0, "Physical stun did not reach CPU slot%d" % slot)
            rider.set_actor_location(vector((0, 14000 + slot * 300, 1800)), False, True)
            self.seed_ball(5, (0, -2000, 1800))
            yield self.wait(.8)
            hazard.set_actor_tick_enabled(False)
        before_spectator = self.crown_state(1)
        spectator = self.join_local()
        yield self.wait(.2)
        player_state = prop(spectator, "PlayerState")
        # GameplayStatics::GetPlayerPawn calls GetPawnOrSpectator in UE5.8;
        # a legitimate SpectatorPawn is expected and is not a roster rider.
        spectator_pawn = unreal.GameplayStatics.get_player_pawn(self.world, 2)
        no_rider = spectator_pawn is None or isinstance(spectator_pawn, unreal.SpectatorPawn)
        self.refresh_roster()
        self.record(CASES[6], player_state is not None and player_state.is_only_a_spectator()
                    and no_rider
                    and len(self.riders) == 16 and self.roster_valid()
                    and sum(r.is_player_controlled() for r in self.riders) == 2
                    and self.crown_state(1) == before_spectator,
                    only_spectator=bool(player_state and player_state.is_only_a_spectator()),
                    spectator_pawn_class=spectator_pawn.get_class().get_path_name() if spectator_pawn else None,
                    no_rider=no_rider, rider_count=len(self.riders), valid_roster=self.roster_valid(),
                    crown_unchanged=self.crown_state(1) == before_spectator,
                    human_riders=sum(r.is_player_controlled() for r in self.riders),
                    cpu_stuns={int(prop(r, "RosterIndex")): float(prop(r, "StunRemaining"))
                               for r in self.riders if not r.is_player_controlled()},
                    crown_state=self.crown_state(1))


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "planned_tests": list(CASES), "count": len(CASES)}
    runner = NativeAdmissionTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and started:
        unreal._basketbroom_native_test = runner
        unreal._basketbroom_native_admission_test = runner
    return {"status": "started" if started else runner.final_status, "report": str(REPORT), "planned_cases": len(CASES)}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

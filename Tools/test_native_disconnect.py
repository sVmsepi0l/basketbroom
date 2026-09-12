"""Actual local listen-server/client disconnect while holding equipment.

Requires Play As Listen Server selected in the UE5.8 Play UI and
BRIDGE_ARGS settings_already_configured=True when its net-mode enum is omitted.
Uses the existing network suite's supported startup/settings restoration.
The client executes Unreal's ordinary `disconnect` console command; server
custody and sanctions are observed through normal ticks, never assigned.
"""
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/native-disconnect-test-results.json"
CASES = (
    "client_role_swap_replicates_before_departure",
    "client_has_real_pending_crown_foul_and_holds_second_ball",
    "disconnect_retires_client_and_restores_sixteen_unique_slots",
    "departed_client_custody_is_free_without_cpu_inheritance",
    "historical_crown_foul_and_opponents_remedy_survive_disconnect",
    "remaining_human_can_acquire_departed_clients_ball_through_rules",
    "managed_play_settings_restored_and_pie_ended",
)
spec = importlib.util.spec_from_file_location("_basketbroom_disconnect_scaffold", ROOT / "Tools/test_native_network.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.TESTS, base.REPORT = CASES, REPORT
base.ARGS = {"max_wall_seconds": 180, **globals().get("BRIDGE_ARGS", {})}
unreal, prop, vec = base.unreal, base.prop, base.vec


class NativeDisconnectTests(base.NativeNetworkTests):
    def __init__(self):
        self.disconnect_requested = False
        super().__init__()

    def write(self, status):
        super().write(status)
        data = json.loads(REPORT.read_text(encoding="utf-8"))
        data["scope"] = "same-process local listen-server/client connection teardown"
        data["not_covered"] = ["remote-machine or internet reconnection", "authenticated persistent participant identity",
                               "abrupt transport timeout or packet loss", "Hogwarts Legacy multiplayer"]
        REPORT.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")

    def crown_state(self):
        return [int(v) for v in self.host["match"].development_get_crown_penalty_state(2)]

    def finish(self, status, reason=None):
        # The old client actor/world may have been destroyed by normal travel.
        # Do not send its input-cleanup request through a stale Python wrapper.
        if self.disconnect_requested:
            self.client = None
        super().finish(status, reason)

    def tick(self, delta):
        if not self.disconnect_requested or self.phase != "running_cases":
            return super().tick(delta)
        if self.done:
            return
        try:
            if time.monotonic() - self.started > float(base.ARGS["max_wall_seconds"]):
                raise TimeoutError("Disconnect integration exceeded its wall-time limit")
            self.require(self.level.is_in_play_in_editor() and self.host["world"] in self.worlds(),
                         "The listen-server PIE world ended during client disconnect")
            if self.waiting:
                wait = self.waiting
                if wait.get("fixture"):
                    wait["fixture"]()
                wait["samples"] += 1
                elapsed = self.now() - wait["start"]
                satisfied = wait["predicate"] is not None and elapsed >= .15 and wait["predicate"]()
                if wait["samples"] >= 3 and (satisfied or elapsed >= wait["seconds"]):
                    self.advance()
                elif time.monotonic() - wait["wall"] > 30:
                    raise TimeoutError("Listen-server time stalled after disconnect")
        except Exception:
            self.finish("error", traceback.format_exc())

    def scenarios(self):
        self.require(not self.live(self.host) and not self.live(self.client), "Fresh network lobby required")
        original_slot = int(prop(self.client["pawn"], "RosterIndex"))
        self.request(self.client, 2, 1)
        changed = lambda: int(prop(self.client["pawn"], "Position")) == 1 and int(prop(self.client_on_server(), "Position")) == 1
        yield self.wait(6, changed)
        self.require(changed(), "Client role request must reach the server")
        departed_slot = int(prop(self.client_on_server(), "RosterIndex"))
        self.record(CASES[0], original_slot != departed_slot and int(prop(self.client["pawn"], "RosterIndex")) == departed_slot,
                    initial_slot=original_slot, departed_slot=departed_slot)
        self.require(original_slot != departed_slot, "Regression needs a real slot swap after initial assignment")
        self.request(self.host, 4)
        yield self.wait(6, lambda: self.live(self.host) and self.live(self.client))
        self.require(self.live(self.host) and self.live(self.client), "Host kickoff must replicate")
        self.isolate_server()
        remote, client_pawn = self.client_on_server(), self.client["pawn"]
        # A stable center-field physical fixture keeps a voluntarily collecting
        # replacement CPU at its legal opening mark well away from the drop.
        for rider in (remote, client_pawn):
            movement = rider.get_component_by_class(unreal.CharacterMovementComponent)
            movement.stop_movement_immediately()
            rider.set_actor_location(vec(-2000,-1200,1800), False, True)
        yield self.wait(.5)

        async_ball, async_client_ball = self.host["balls"][2], self.client["balls"][2]
        position = remote.get_actor_location()
        self.require(async_ball.development_set_flight_fixture(position + vec(200,0,0), vec(0,0,0)), "Crown attribution fixture")
        async_ball.set_actor_tick_enabled(True)
        yield self.wait(.4)
        self.require(client_pawn.development_set_interaction(True), "Client first pickup input")
        owns_first = lambda: prop(async_ball,"Holder") == remote and prop(async_client_ball,"Holder") == client_pawn
        yield self.wait(6, owns_first)
        self.require(owns_first(), "Client must possess the first ball normally")
        client_pawn.development_set_interaction(False)
        yield self.wait(.4, lambda: not prop(remote,"bInteractHeld"))
        self.request(self.client, 1)
        yield self.wait(6, lambda: prop(async_ball,"Holder") is None and async_ball.get_flight_velocity().length() > 1000)
        self.require(prop(async_ball,"Holder") is None and async_ball.get_flight_velocity().length() > 1000,
                     "Actual client throw must establish release responsibility")
        self.require(async_ball.development_set_flight_fixture(vec(0,0,4180), vec(0,0,1400)), "Free released-ball roof fixture")
        yield self.wait(5, lambda: self.crown_state()[0] == 1)
        self.require(self.crown_state()[0] == 1, "Released ball must physically cross the Crown")
        yield self.wait(5, lambda: bool(prop(async_ball,"bActive")))
        self.require(prop(async_ball,"bActive"), "Neutral Crown return must finish before departure")
        async_ball.set_actor_tick_enabled(False)

        ball, client_ball = self.host["balls"][1], self.client["balls"][1]
        self.require(ball.development_set_flight_fixture(remote.get_actor_location() + vec(200,0,0), vec(0,0,0)), "Second pickup fixture")
        ball.set_actor_tick_enabled(True)
        yield self.wait(.4)
        self.require(client_pawn.development_set_interaction(True), "Client second pickup input")
        owns_second = lambda: prop(ball,"Holder") == remote and prop(client_ball,"Holder") == client_pawn
        yield self.wait(6, owns_second)
        self.require(owns_second(), "Client must really hold equipment before disconnect")
        client_pawn.development_set_interaction(False)
        yield self.wait(.4, lambda: not prop(remote,"bInteractHeld"))
        penalty_before = self.crown_state()
        scores_before = self.scores(self.host)
        self.record(CASES[1], owns_second() and penalty_before[0:4] == [1,1,1,departed_slot],
                    crown_state=penalty_before, holder_slot=int(prop(remote,"RosterIndex")))
        self.require(penalty_before[0:4] == [1,1,1,departed_slot], "Departed player must have a real pending restorative foul")
        self.events.append({"connection_action": "client disconnect console command", "server_time": self.now(),
                            "departed_slot": departed_slot})
        client_controller = unreal.GameplayStatics.get_player_controller(self.client["world"], 0)
        self.disconnect_requested = True
        unreal.SystemLibrary.execute_console_command(self.client["world"], "disconnect", client_controller)
        one_human = lambda: len(self.human_roster(self.host)) == 1
        yield self.wait(12, one_human)
        expected = [(slot, slot // 8, base.ROLES[slot % 8]) for slot in range(16)]
        self.record(CASES[2], one_human() and self.roster(self.host) == expected,
                    humans=self.human_roster(self.host), roster=self.roster(self.host))
        self.require(one_human(), "The real client connection did not leave the server")
        replacements = [r for r in self.actors(self.host["world"], "BBRiderCharacter") if int(prop(r,"RosterIndex")) == departed_slot]
        yield self.wait(.5)
        free = prop(ball,"Holder") is None
        self.record(CASES[3], free and prop(ball,"bActive") and len(replacements) == 1
                    and not replacements[0].is_player_controlled(),
                    free=free, active=bool(prop(ball,"bActive")), status=str(prop(ball,"BallStatus")),
                    replacement_count=len(replacements), ball_position=str(ball.get_actor_location()))
        self.record(CASES[4], self.crown_state() == penalty_before and self.scores(self.host) == scores_before
                    and self.live(self.host), crown_before=penalty_before, crown_after=self.crown_state(),
                    scores_before=scores_before, scores_after=self.scores(self.host))
        self.require(free, "A replacement CPU inherited the disconnected player's core custody")

        # A successful native pickup also proves rules custody was cleared,
        # rather than only hiding the destroyed actor in replicated Holder.
        self.host["pawn"].get_component_by_class(unreal.CharacterMovementComponent).stop_movement_immediately()
        self.host["pawn"].set_actor_location(ball.get_actor_location() + vec(-150,0,0), False, True)
        self.require(self.host["pawn"].development_set_interaction(True), "Remaining host pickup input")
        yield self.wait(6, lambda: prop(ball,"Holder") == self.host["pawn"])
        self.record(CASES[5], prop(ball,"Holder") == self.host["pawn"] and self.crown_state() == penalty_before,
                    host_has_ball=prop(ball,"Holder") == self.host["pawn"], crown_state=self.crown_state())
        self.host["pawn"].development_set_interaction(False)


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "planned_tests": list(CASES), "count": len(CASES)}
    runner = NativeDisconnectTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and (started or not runner.done):
        unreal._basketbroom_native_network_test = runner
        unreal._basketbroom_native_disconnect_test = runner
    return {"status": "started" if started else runner.final_status, "report": str(REPORT), "planned_cases": len(CASES)}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

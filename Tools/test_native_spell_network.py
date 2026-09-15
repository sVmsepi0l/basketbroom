"""bounded native spell/conduct replication checks in two local pie worlds.

run through editor_bridge.py with /Basketbroom/Maps/BB_Regulation open and pie
stopped. the existing network runner owns startup, deadlines and cleanup. its
settings_already_configured fallback and explicit settings_source provenance also apply here. the report is
.local/native-spell-network-test-results.json. this suite does not save assets.

positions and movement components are arranged in disposable pie worlds;
movement replication is outside this suite. all spell requests are queued on
the owning human and sent from normal native tick through ServerAction. never
write vitality, effects, ownership, conduct state, or fabricate hud receipts.
outside unreal, --list reports planned cases only.
"""

import importlib.util as _arena_importlib
from pathlib import path as _arenapath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)
import importlib.util
import json
import math
from pathlib import path
import sys
import time
import traceback

root = Path(__file__).resolve().parents[1]
report = root / ".local" / "native-spell-network-test-results.json"
args = dict(globals().get("BRIDGE_ARGS", {}))
ARGS.setdefault("max_wall_seconds", 240)
tests = (
    "client_cannot_toggle_bloodbroom",
    "client_basic_cast_damage_replicates",
    "client_protego_replicates_and_blocks_host_bolt",
    "client_stupefy_stun_replicates_and_recovers",
    "client_arresto_impediment_replicates_and_recovers",
    "host_headshot_applies_then_referee_pause_replicates",
    "client_cannot_adjudicate_pending_conduct",
    "host_possession_award_queues_then_actual_restart_replicates",
    "fallback_preserves_reserved_quaffle_and_its_scored_ball_restart",
    "managed_play_settings_restored_and_pie_ended",
)

# a private module instance prevents our report/case configuration from changing
# an independently imported copy of the general network test helper.
_spec = importlib.util.spec_from_file_location("_bb_spell_network_base", root / "tools" / "test_native_network.py")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
base.TESTS, base.REPORT, base.ARGS = tests, report, args
unreal, prop, vec = base.unreal, base.prop, base.vec


class SpellNetworkTests(base.NativeNetworkTests):
    def __init__(self):
        self.dilations = []
        self.dilations_restored = true
        super().__init__()

    def write(self, status):
        rows = [{"name": name, **self.results.get(name, {"status": "not_run"})} for name in tests]
        report = {
            "status": status, "phase": self.phase,
            "scope": "real spell rpc and property replication; two local pie worlds in one process",
            "elapsed_wall_seconds": round(time.monotonic() - self.started, 3),
            "passed": sum(row["status"] == "passed" for row in rows),
            "failed": sum(row["status"] == "failed" for row in rows),
            "not_run": sum(row["status"] == "not_run" for row in rows),
            "tests": rows, "provenance": self.provenance, "events": self.events,
            "settings_restored": self.settings_restored,
            "time_dilation_restored": self.dilations_restored, "reason": self.reason,
            "external_restore_required": base.net_mode_restore_actions(self.provenance),
            "not_covered": ["separate processes, remote machines or adverse network conditions",
                            "human keyboard or visual judgement", "movement replication",
                            "double-tap hud delivery/acknowledgement", "all catalog spells",
                            "automatic penalty severity selection or full regulation remedies",
                            "hogwarts legacy multiplayer"],
        }
        base.write_json_atomic(REPORT, report)

    def begin(self):
        if unreal:
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
            self.require(world is not none and world.get_path_name().split(".")[0]
                         == "/Basketbroom/Maps/BB_Regulation", "open the owned bb_regulation map first")
            self.provenance["editor_world"] = world.get_path_name()
        return super().begin()

    def record(self, name, passed, **detail):
        if name == TESTS[-1]:
            passed = passed and self.dilations_restored
            detail["time_dilation_restored"] = self.dilations_restored
        super().record(name, passed, **detail)

    def finish(self, status, reason=None):
        # both worlds are disposable, but explicitly restore time before asking
        # the inherited runner to end its session, including failure paths.
        try:
            for world, old in self.dilations:
                unreal.GameplayStatics.set_global_time_dilation(world, old)
            self.dilations_restored = all(abs(float(unreal.GameplayStatics.get_global_time_dilation(world)) - old) < .001
                                          for world, old in self.dilations)
            self.require(self.dilations_restored, "pie time dilation did not restore")
        except Exception:
            self.dilations_restored = false
            status, reason = "error", (reason or "") + "\nTime restoration: " + traceback.format_exc()
        super().finish(status, reason)

    def host_on_client(self):
        found = [r for r in self.client["riders"] if self.player_id(r) == self.player_id(self.host["pawn"])]
        self.require(len(found) == 1, "host has no unique client replica")
        return found[0]

    def target_pair(self, side):
        return ((self.host["pawn"], self.host_on_client()) if side is self.host
                else (self.client_on_server(), self.client["pawn"]))

    def values(self, side, field):
        return [float(prop(r, field)) for r in self.target_pair(side)]

    def ready(self, side):
        return all(float(prop(r, field)) <= .01 for r in self.target_pair(side)
                   for field in ("spellcooldownremaining", "stunremaining", "impedimentremaining", "disarmremaining"))

    def arrange(self):
        self.isolate_server()
        positions = {self.player_id(self.host["pawn"]): vec(-600, 0, 2100),
                     self.player_id(self.client["pawn"]): vec(600, 0, 2100)}
        # server and autonomous owner positions are explicitly arranged, not
        # offered as evidence for movement correction/replication. keep human
        # actor ticks active: they consume queued input and actual spell timers.
        for side in (self.host, self.client):
            for rider in side["riders"]:
                if not rider.is_player_controlled():
                    continue
                movement = rider.get_component_by_class(unreal.CharacterMovementComponent)
                self.require(movement is not none, "human movement component is missing")
                movement.stop_movement_immediately()
                movement.set_component_tick_enabled(False)
                rider.consume_movement_input_vector()
                rider.set_actor_location(positions[self.player_id(rider)], false, true)
            controller = unreal.GameplayStatics.get_player_controller(side["world"], 0)
            self.require(controller is not none, "local owning controller is missing")
            controller.set_actor_tick_enabled(False)
        self.provenance["position_fixture"] = "both pie views at +/-600 x, 0 y, 2100 z cm; human actor ticks retained"

    def aim(self, caster, victim, head=False):
        start = caster["pawn"].get_actor_location() + vec(0, 0, 72)
        target = victim["pawn"].get_actor_location() + vec(0, 0, 80 if head else 0)
        direction = target - start
        length = direction.length()
        self.require(100 < length < 2000, "spell fixture target is out of the intended range")
        pitch = math.degrees(math.atan2(direction.z, math.hypot(direction.x, direction.y)))
        yaw = math.degrees(math.atan2(direction.y, direction.x))
        controller = unreal.GameplayStatics.get_player_controller(caster["world"], 0)
        controller.set_control_rotation(unreal.Rotator(pitch=pitch, yaw=yaw, roll=0))
        # getbaseaimrotation reads the camera manager's cached POV. a queued
        # cast in this same callback can still use the previous frame's view.
        # the inherited wait requires >=3 native samples and >=.15 game seconds
        # before success. only then queue input; never force a camera update.
        def aim_dot():
            actual = caster["pawn"].get_aim_direction()
            return (actual.x * direction.x + actual.y * direction.y + actual.z * direction.z) / length

        yield self.wait(2, lambda: aim_dot() > .999)
        dot = aim_dot()
        self.require(dot > .999, "owning client's cached camera aim did not settle before input")
        actual = caster["pawn"].get_aim_direction()
        self.events.append({"fixture": "cached owner camera aim settled before cast submission",
                            "player_id": self.player_id(caster["pawn"]), "head_target": head,
                            "requested_unit": [direction.x / length, direction.y / length, direction.z / length],
                            "observed_unit": [actual.x, actual.y, actual.z], "dot": dot})

    def conduct(self, side):
        match = side["match"]
        return {name: prop(match, name) for name in
                ("bbloodbroom", "conductfoulcount", "lastconductcall", "bconductreviewpending",
                 "conductreviewstatus", "pendingpenaltycount", "blive", "status")}

    def capture(self, side, field, observed):
        values = self.values(side, field)
        if all(value > .05 for value in values):
            observed["active"] = values
        return values

    def scenarios(self):
        self.require(self.host["world"] != self.client["world"] and self.host["match"].has_authority()
                     and not self.client["match"].has_authority(), "distinct connected authority/client worlds required")
        self.require(not self.live(self.host) and not self.live(self.client), "fresh lobby required")
        self.require(not prop(self.host["match"], "bbloodbroom"), "this suite needs ordinary bb-0")
        # prove that this client's legitimate requests reach authority before
        # interpreting rejected privileged requests as successful enforcement.
        self.request(self.client, 3, 1)
        team_ok = lambda: int(prop(self.client["pawn"], "teamindex")) == int(prop(self.client_on_server(), "teamindex")) == 1
        yield self.wait(5, team_ok)
        self.require(team_ok(), "client team rpc did not reach authority")
        self.request(self.client, 2, 1)
        role_ok = lambda: int(prop(self.client["pawn"], "position")) == int(prop(self.client_on_server(), "position")) == 1
        yield self.wait(5, role_ok)
        self.require(role_ok(), "client must be an eligible chaser for the later possession award")
        self.request(self.client, 8)
        yield self.wait(.6)
        ordinary = not prop(self.host["match"], "bbloodbroom") and not prop(self.client["match"], "bbloodbroom")
        self.record(TESTS[0], ordinary and not self.live(self.host), server=self.conduct(self.host), client=self.conduct(self.client))
        self.require(ordinary, "remote client changed the lobby ruleset")

        self.isolate_server()
        self.request(self.host, 4)
        both_live = lambda: self.live(self.host) and self.live(self.client)
        yield self.wait(5, both_live)
        self.require(both_live(), "host start did not replicate")
        self.arrange()
        for side in (self.host, self.client):
            world = side["world"]
            self.dilations.append((world, float(unreal.GameplayStatics.get_global_time_dilation(world))))
        self.dilations_restored = false
        for world, _ in self.dilations:
            unreal.GameplayStatics.set_global_time_dilation(world, .25)
        self.provenance["disposable_pie_time_dilation"] = .25
        yield self.wait(.4)
        self.require(int(prop(self.host["pawn"], "teamindex")) == 0, "host must oppose the client")
        yield from self.aim(self.client, self.host)
        before = self.values(self.host, "vitality")
        self.request(self.client, 6, 0)
        damaged = lambda: all(value < old - 3 for value, old in zip(self.values(self.host, "vitality"), before))
        yield self.wait(2, damaged)
        after = self.values(self.host, "vitality")
        damage_ok = damaged() and abs(after[0] - after[1]) < 2 and both_live()
        self.record(TESTS[1], damage_ok, before=before, after=after, action=6, spell=0)
        self.require(damage_ok, "actual client basic cast did not damage and replicate")

        yield self.wait(4, lambda: self.ready(self.client))
        self.require(self.ready(self.client), "client spell cooldown did not recover")
        # let the earlier victim notice expire naturally so the block result
        # can be attributed to this cast, without clearing the feedback queue.
        feedback_empty = lambda: not str(prop(self.host["pawn"], "spellfeedback"))
        yield self.wait(3, feedback_empty)
        self.require(feedback_empty(), "prior host feedback did not drain before the block check")
        # settle the host's view before starting the one-second shield window.
        yield from self.aim(self.host, self.client)
        shield_observed = {}
        self.request(self.client, 6, 1)
        yield self.wait(2, lambda: "active" in shield_observed,
                        lambda: self.capture(self.client, "shieldremaining", shield_observed))
        self.require("active" in shield_observed and min(self.values(self.client, "shieldremaining")) > .15,
                     "replicated shield was not observed in time to test blocking")
        shield_vitality = self.values(self.client, "vitality")
        self.request(self.host, 6, 0)
        yield self.wait(.6, lambda: "block" in str(prop(self.host["pawn"], "SpellFeedback")).upper())
        # the owner's result proves a real cast reached the server blocking
        # branch; an unchanged target alone could instead be a miss.
        blocked_feedback = str(prop(self.host["pawn"], "spellfeedback"))
        blocked = "block" in blocked_feedback.upper() and self.values(self.client, "vitality") == shield_vitality
        self.record(TESTS[2], blocked, shield_active=shield_observed.get("active"), feedback=blocked_feedback,
                    vitality_before=shield_vitality, vitality_after=self.values(self.client, "vitality"))
        self.require(blocked, "protego did not block the actual host cast")

        yield self.wait(4, lambda: self.ready(self.client) and self.ready(self.host))
        self.require(self.ready(self.client) and self.ready(self.host), "spell cooldowns did not recover")
        yield from self.aim(self.client, self.host)
        stun_observed = {}
        self.request(self.client, 6, 2)
        yield self.wait(2, lambda: "active" in stun_observed,
                        lambda: self.capture(self.host, "stunremaining", stun_observed))
        yield self.wait(4, lambda: max(self.values(self.host, "stunremaining")) <= .01)
        stun_ok = "active" in stun_observed and max(self.values(self.host, "stunremaining")) <= .01 and both_live()
        self.record(TESTS[3], stun_ok, active=stun_observed.get("active"), recovered=self.values(self.host, "stunremaining"))
        self.require(stun_ok, "real stupefy stun or its recovery did not replicate")

        yield self.wait(4, lambda: self.ready(self.client))
        self.require(self.ready(self.client), "stupefy cooldown did not recover")
        yield from self.aim(self.client, self.host)
        slow_observed = {}
        self.request(self.client, 6, 10)
        yield self.wait(2, lambda: "active" in slow_observed,
                        lambda: self.capture(self.host, "impedimentremaining", slow_observed))
        yield self.wait(4, lambda: max(self.values(self.host, "impedimentremaining")) <= .01)
        slow_ok = "active" in slow_observed and max(self.values(self.host, "impedimentremaining")) <= .01 and both_live()
        self.record(TESTS[4], slow_ok, active=slow_observed.get("active"), recovered=self.values(self.host, "impedimentremaining"),
                    hud_acknowledgement="not simulated or asserted")
        self.require(slow_ok, "real arresto impediment or its recovery did not replicate")

        yield self.wait(4, lambda: self.ready(self.host) and self.ready(self.client))
        self.require(self.ready(self.host) and self.ready(self.client), "earlier effects must expire before the headshot")
        yield from self.aim(self.host, self.client, head=true)
        head_before = self.values(self.client, "vitality")
        fouls_before = int(prop(self.host["match"], "conductfoulcount"))
        scores_before = self.scores(self.host)
        self.require(fouls_before == 0, "earlier legal torso casts unexpectedly produced a foul")
        # two actual goals reserve the quaffle without a removed roof rule.
        # quark 2 first gives the defending keeper genuine scoring-ball custody.
        # the subsequent quaffle score must wait until that keeper releases it.
        quaffle, occupied = self.host["balls"][0], self.host["balls"][2]
        for ball in (quaffle, occupied):
            self.require(prop(ball, "holder") is none and prop(ball, "bactive"),
                         "fallback fixture needs two untouched active scoring balls")
        self.require(occupied.development_set_flight_fixture(vec((dimensions.GOAL_PLANE_X-200.8), 0, 3048), vec(2000, 0, 0)),
                     "physical quark goal fixture rejected")
        occupied.set_actor_tick_enabled(True)
        keeper_holds = lambda: prop(occupied, "holder") is not none
        yield self.wait(3, keeper_holds)
        self.require(keeper_holds(), "first native quark goal must reach a real keeper restart")
        keeper_slot = int(prop(prop(occupied, "holder"), "rosterindex"))
        self.require(self.scores(self.host) == [scores_before[0]+37, scores_before[1]],
                     "quark fixture must produce exactly one genuine 37-point goal")
        self.require(quaffle.development_set_flight_fixture(vec((dimensions.GOAL_PLANE_X-200.8), 0, 2103.12), vec(2000, 0, 0)),
                     "physical quaffle goal fixture rejected")
        quaffle.set_actor_tick_enabled(True)
        score_reserved = lambda: all(str(prop(side["balls"][0], "ballstatus")) == "score"
                                      and prop(side["balls"][0], "holder") is none
                                      for side in (self.host, self.client))
        yield self.wait(3, score_reserved)
        self.require(score_reserved(), "second native goal must retain its score restart while keeper is occupied")
        scores_before = [scores_before[0]+50, scores_before[1]]
        self.require(self.scores(self.host) == self.scores(self.client) == scores_before,
                     "both real goals and reserved quaffle state must replicate")
        score_fixture = {"server_status_at_cast_submission": str(prop(quaffle, "ballstatus")),
                         "keeper_holds_other_scoring_ball": keeper_holds(), "keeper_slot": keeper_slot,
                         "scores_from_actual_goals": scores_before,
                         "server_live_time": float(prop(self.host["match"], "liveseconds"))}
        self.request(self.host, 6, 0)
        review = lambda: all(prop(side["match"], "bconductreviewpending") and not self.live(side)
                             for side in (self.host, self.client))
        yield self.wait(4, review)
        self.require(score_reserved(), "headshot must preserve the genuine quaffle score reservation")
        head_after = self.values(self.client, "vitality")
        head_ok = review() and all(after <= before - 7.5 for before, after in zip(head_before, head_after))
        head_ok = head_ok and all(int(prop(side["match"], "conductfoulcount")) == fouls_before + 1
                                  and "headshot" in str(prop(side["match"], "lastconductcall"))
                                  and "playtest referee" in str(prop(side["match"], "conductreviewstatus"))
                                  for side in (self.host, self.client))
        self.record(TESTS[5], head_ok, before=head_before, after=head_after,
                    server=self.conduct(self.host), client=self.conduct(self.client), score_fixture=score_fixture)
        self.require(head_ok, "headshot effect and pending referee stoppage did not replicate")

        review_before = self.conduct(self.host)
        rejected = []
        for action in (9, 11):
            self.request(self.client, action)
            yield self.wait(.5)
            rejected.append(review() and self.conduct(self.host) == review_before
                            and self.conduct(self.client) == review_before)
        self.record(TESTS[6], all(rejected), actions=[9, 11], rejected=rejected,
                    server=self.conduct(self.host), client=self.conduct(self.client))
        self.require(all(rejected), "remote client adjudicated the pending conduct")

        self.request(self.host, 9)
        queued = lambda: all(not prop(side["match"], "bconductreviewpending") and not self.live(side)
                             and int(prop(side["match"], "pendingpenaltycount")) == 1
                             and "possession award queued" in str(prop(side["match"], "conductreviewstatus"))
                             and prop(side["balls"][1], "holder") is none
                             and str(prop(side["balls"][1], "ballstatus")) == "penalty"
                             for side in (self.host, self.client))
        yield self.wait(4, queued)
        queue_observed = queued()
        queue_state = self.conduct(self.host)
        yield self.wait(.5)
        queue_held = queued()
        score_preserved = score_reserved()
        self.require(queue_observed and queue_held and score_preserved,
                     "f7 must reserve available quark 1 and preserve the prior quaffle score reservation")
        self.request(self.host, 4)
        served = lambda: both_live() and all(int(prop(side["match"], "pendingpenaltycount")) == 0 for side in (self.host, self.client)) \
            and prop(self.host["balls"][1], "holder") == self.client_on_server() \
            and prop(self.client["balls"][1], "holder") == self.client["pawn"]
        yield self.wait(4, served)
        served_observed = served()
        yield self.wait(.6)
        award_ok = served_observed and served() and self.scores(self.host) == self.scores(self.client) == scores_before
        award_ok = award_ok and all(int(prop(side["match"], "conductfoulcount")) == fouls_before + 1 for side in (self.host, self.client))
        self.record(TESTS[7], award_ok, queued_observed=queue_observed, remained_pending=queue_held,
                    queued_state=queue_state, server=self.conduct(self.host), client=self.conduct(self.client),
                    server_holder_is_receiver=prop(self.host["balls"][1], "holder") == self.client_on_server(),
                    client_holder_is_receiver=prop(self.client["balls"][1], "holder") == self.client["pawn"],
                    award_ball=1, unavailable_first_choice=0,
                    scores_unchanged=self.scores(self.host) == scores_before)
        returned = lambda: all(prop(side["balls"][0], "bactive")
                               and str(prop(side["balls"][0], "ballstatus")) == ""
                               and prop(side["balls"][0], "holder") is not none
                               and int(prop(prop(side["balls"][0], "holder"), "rosterindex")) == keeper_slot
                               for side in (self.host, self.client))
        yield self.wait(3, returned)
        self.record(TESTS[8], score_preserved and returned() and served()
                    and self.scores(self.host) == self.scores(self.client) == scores_before,
                    physical_goals=score_fixture, reserved_through_f7=score_preserved,
                    scored_ball_keeper_restart_observed=returned(), opposing_quark_possession_retained=served())



def main():
    if unreal is none and "--list" in sys.argv:
        return {"status": "not_run", "scope": "two connected local pie worlds; actual queued spell requests",
                "planned_tests": list(tests), "count": len(tests)}
    runner = spellnetworktests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = false
    if unreal and (started or not runner.done):
        unreal._basketbroom_native_network_test = runner
    return {"status": "started" if started else runner.final_status,
            "report": str(report), "planned_cases": len(tests)}


if __name__ == "__main__":
    result = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

"""Bounded native spell/conduct replication checks in two local PIE worlds.

Run through editor_bridge.py with /Basketbroom/Maps/BB_Regulation open and PIE
stopped. The existing network runner owns startup, deadlines and cleanup. Its
settings_already_configured fallback and explicit settings_source provenance also apply here. The report is
.local/native-spell-network-test-results.json. This suite does not save assets.

Positions and movement components are arranged in disposable PIE worlds;
movement replication is outside this suite. All spell requests are queued on
the owning human and sent from normal native Tick through ServerAction. Never
write vitality, effects, ownership, conduct state, or fabricate HUD receipts.
Outside Unreal, --list reports planned cases only.
"""

import importlib.util as _arena_importlib
from pathlib import Path as _ArenaPath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local" / "native-spell-network-test-results.json"
ARGS = dict(globals().get("BRIDGE_ARGS", {}))
ARGS.setdefault("max_wall_seconds", 240)
TESTS = (
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

# A private module instance prevents our report/case configuration from changing
# an independently imported copy of the general network test helper.
_spec = importlib.util.spec_from_file_location("_bb_spell_network_base", ROOT / "Tools" / "test_native_network.py")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
base.TESTS, base.REPORT, base.ARGS = TESTS, REPORT, ARGS
unreal, prop, vec = base.unreal, base.prop, base.vec


class SpellNetworkTests(base.NativeNetworkTests):
    def __init__(self):
        self.dilations = []
        self.dilations_restored = True
        super().__init__()

    def write(self, status):
        rows = [{"name": name, **self.results.get(name, {"status": "not_run"})} for name in TESTS]
        report = {
            "status": status, "phase": self.phase,
            "scope": "real spell RPC and property replication; two local PIE worlds in one process",
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
                            "double-tap HUD delivery/acknowledgement", "all catalog spells",
                            "automatic penalty severity selection or full regulation remedies",
                            "Hogwarts Legacy multiplayer"],
        }
        base.write_json_atomic(REPORT, report)

    def begin(self):
        if unreal:
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
            self.require(world is not None and world.get_path_name().split(".")[0]
                         == "/Basketbroom/Maps/BB_Regulation", "Open the owned BB_Regulation map first")
            self.provenance["editor_world"] = world.get_path_name()
        return super().begin()

    def record(self, name, passed, **detail):
        if name == TESTS[-1]:
            passed = passed and self.dilations_restored
            detail["time_dilation_restored"] = self.dilations_restored
        super().record(name, passed, **detail)

    def finish(self, status, reason=None):
        # Both worlds are disposable, but explicitly restore time before asking
        # the inherited runner to end its session, including failure paths.
        try:
            for world, old in self.dilations:
                unreal.GameplayStatics.set_global_time_dilation(world, old)
            self.dilations_restored = all(abs(float(unreal.GameplayStatics.get_global_time_dilation(world)) - old) < .001
                                          for world, old in self.dilations)
            self.require(self.dilations_restored, "PIE time dilation did not restore")
        except Exception:
            self.dilations_restored = False
            status, reason = "error", (reason or "") + "\nTime restoration: " + traceback.format_exc()
        super().finish(status, reason)

    def host_on_client(self):
        found = [r for r in self.client["riders"] if self.player_id(r) == self.player_id(self.host["pawn"])]
        self.require(len(found) == 1, "Host has no unique client replica")
        return found[0]

    def target_pair(self, side):
        return ((self.host["pawn"], self.host_on_client()) if side is self.host
                else (self.client_on_server(), self.client["pawn"]))

    def values(self, side, field):
        return [float(prop(r, field)) for r in self.target_pair(side)]

    def ready(self, side):
        return all(float(prop(r, field)) <= .01 for r in self.target_pair(side)
                   for field in ("SpellCooldownRemaining", "StunRemaining", "ImpedimentRemaining", "DisarmRemaining"))

    def arrange(self):
        self.isolate_server()
        positions = {self.player_id(self.host["pawn"]): vec(-600, 0, 2100),
                     self.player_id(self.client["pawn"]): vec(600, 0, 2100)}
        # Server and autonomous owner positions are explicitly arranged, not
        # offered as evidence for movement correction/replication. Keep human
        # Actor ticks active: they consume queued input and actual spell timers.
        for side in (self.host, self.client):
            for rider in side["riders"]:
                if not rider.is_player_controlled():
                    continue
                movement = rider.get_component_by_class(unreal.CharacterMovementComponent)
                self.require(movement is not None, "Human movement component is missing")
                movement.stop_movement_immediately()
                movement.set_component_tick_enabled(False)
                rider.consume_movement_input_vector()
                rider.set_actor_location(positions[self.player_id(rider)], False, True)
            controller = unreal.GameplayStatics.get_player_controller(side["world"], 0)
            self.require(controller is not None, "Local owning controller is missing")
            controller.set_actor_tick_enabled(False)
        self.provenance["position_fixture"] = "both PIE views at +/-600 X, 0 Y, 2100 Z cm; human Actor ticks retained"

    def aim(self, caster, victim, head=False):
        start = caster["pawn"].get_actor_location() + vec(0, 0, 72)
        target = victim["pawn"].get_actor_location() + vec(0, 0, 80 if head else 0)
        direction = target - start
        length = direction.length()
        self.require(100 < length < 2000, "Spell fixture target is out of the intended range")
        pitch = math.degrees(math.atan2(direction.z, math.hypot(direction.x, direction.y)))
        yaw = math.degrees(math.atan2(direction.y, direction.x))
        controller = unreal.GameplayStatics.get_player_controller(caster["world"], 0)
        controller.set_control_rotation(unreal.Rotator(pitch=pitch, yaw=yaw, roll=0))
        # GetBaseAimRotation reads the camera manager's cached POV. A queued
        # cast in this same callback can still use the previous frame's view.
        # The inherited wait requires >=3 native samples and >=.15 game seconds
        # before success. Only then queue input; never force a camera update.
        def aim_dot():
            actual = caster["pawn"].get_aim_direction()
            return (actual.x * direction.x + actual.y * direction.y + actual.z * direction.z) / length

        yield self.wait(2, lambda: aim_dot() > .999)
        dot = aim_dot()
        self.require(dot > .999, "Owning client's cached camera aim did not settle before input")
        actual = caster["pawn"].get_aim_direction()
        self.events.append({"fixture": "cached owner camera aim settled before cast submission",
                            "player_id": self.player_id(caster["pawn"]), "head_target": head,
                            "requested_unit": [direction.x / length, direction.y / length, direction.z / length],
                            "observed_unit": [actual.x, actual.y, actual.z], "dot": dot})

    def conduct(self, side):
        match = side["match"]
        return {name: prop(match, name) for name in
                ("bBloodbroom", "ConductFoulCount", "LastConductCall", "bConductReviewPending",
                 "ConductReviewStatus", "PendingPenaltyCount", "bLive", "Status")}

    def capture(self, side, field, observed):
        values = self.values(side, field)
        if all(value > .05 for value in values):
            observed["active"] = values
        return values

    def scenarios(self):
        self.require(self.host["world"] != self.client["world"] and self.host["match"].has_authority()
                     and not self.client["match"].has_authority(), "Distinct connected authority/client worlds required")
        self.require(not self.live(self.host) and not self.live(self.client), "Fresh lobby required")
        self.require(not prop(self.host["match"], "bBloodbroom"), "This suite needs ordinary BB-0")
        # Prove that this client's legitimate requests reach authority before
        # interpreting rejected privileged requests as successful enforcement.
        self.request(self.client, 3, 1)
        team_ok = lambda: int(prop(self.client["pawn"], "TeamIndex")) == int(prop(self.client_on_server(), "TeamIndex")) == 1
        yield self.wait(5, team_ok)
        self.require(team_ok(), "Client team RPC did not reach authority")
        self.request(self.client, 2, 1)
        role_ok = lambda: int(prop(self.client["pawn"], "Position")) == int(prop(self.client_on_server(), "Position")) == 1
        yield self.wait(5, role_ok)
        self.require(role_ok(), "Client must be an eligible Chaser for the later possession award")
        self.request(self.client, 8)
        yield self.wait(.6)
        ordinary = not prop(self.host["match"], "bBloodbroom") and not prop(self.client["match"], "bBloodbroom")
        self.record(TESTS[0], ordinary and not self.live(self.host), server=self.conduct(self.host), client=self.conduct(self.client))
        self.require(ordinary, "Remote client changed the lobby ruleset")

        self.isolate_server()
        self.request(self.host, 4)
        both_live = lambda: self.live(self.host) and self.live(self.client)
        yield self.wait(5, both_live)
        self.require(both_live(), "Host start did not replicate")
        self.arrange()
        for side in (self.host, self.client):
            world = side["world"]
            self.dilations.append((world, float(unreal.GameplayStatics.get_global_time_dilation(world))))
        self.dilations_restored = False
        for world, _ in self.dilations:
            unreal.GameplayStatics.set_global_time_dilation(world, .25)
        self.provenance["disposable_pie_time_dilation"] = .25
        yield self.wait(.4)
        self.require(int(prop(self.host["pawn"], "TeamIndex")) == 0, "Host must oppose the client")
        yield from self.aim(self.client, self.host)
        before = self.values(self.host, "Vitality")
        self.request(self.client, 6, 0)
        damaged = lambda: all(value < old - 3 for value, old in zip(self.values(self.host, "Vitality"), before))
        yield self.wait(2, damaged)
        after = self.values(self.host, "Vitality")
        damage_ok = damaged() and abs(after[0] - after[1]) < 2 and both_live()
        self.record(TESTS[1], damage_ok, before=before, after=after, action=6, spell=0)
        self.require(damage_ok, "Actual client Basic Cast did not damage and replicate")

        yield self.wait(4, lambda: self.ready(self.client))
        self.require(self.ready(self.client), "Client spell cooldown did not recover")
        # Let the earlier victim notice expire naturally so the block result
        # can be attributed to this cast, without clearing the feedback queue.
        feedback_empty = lambda: not str(prop(self.host["pawn"], "SpellFeedback"))
        yield self.wait(3, feedback_empty)
        self.require(feedback_empty(), "Prior host feedback did not drain before the block check")
        # Settle the host's view before starting the one-second shield window.
        yield from self.aim(self.host, self.client)
        shield_observed = {}
        self.request(self.client, 6, 1)
        yield self.wait(2, lambda: "active" in shield_observed,
                        lambda: self.capture(self.client, "ShieldRemaining", shield_observed))
        self.require("active" in shield_observed and min(self.values(self.client, "ShieldRemaining")) > .15,
                     "Replicated shield was not observed in time to test blocking")
        shield_vitality = self.values(self.client, "Vitality")
        self.request(self.host, 6, 0)
        yield self.wait(.6, lambda: "BLOCK" in str(prop(self.host["pawn"], "SpellFeedback")).upper())
        # The owner's result proves a real cast reached the server blocking
        # branch; an unchanged target alone could instead be a miss.
        blocked_feedback = str(prop(self.host["pawn"], "SpellFeedback"))
        blocked = "BLOCK" in blocked_feedback.upper() and self.values(self.client, "Vitality") == shield_vitality
        self.record(TESTS[2], blocked, shield_active=shield_observed.get("active"), feedback=blocked_feedback,
                    vitality_before=shield_vitality, vitality_after=self.values(self.client, "Vitality"))
        self.require(blocked, "Protego did not block the actual host cast")

        yield self.wait(4, lambda: self.ready(self.client) and self.ready(self.host))
        self.require(self.ready(self.client) and self.ready(self.host), "Spell cooldowns did not recover")
        yield from self.aim(self.client, self.host)
        stun_observed = {}
        self.request(self.client, 6, 2)
        yield self.wait(2, lambda: "active" in stun_observed,
                        lambda: self.capture(self.host, "StunRemaining", stun_observed))
        yield self.wait(4, lambda: max(self.values(self.host, "StunRemaining")) <= .01)
        stun_ok = "active" in stun_observed and max(self.values(self.host, "StunRemaining")) <= .01 and both_live()
        self.record(TESTS[3], stun_ok, active=stun_observed.get("active"), recovered=self.values(self.host, "StunRemaining"))
        self.require(stun_ok, "Real Stupefy stun or its recovery did not replicate")

        yield self.wait(4, lambda: self.ready(self.client))
        self.require(self.ready(self.client), "Stupefy cooldown did not recover")
        yield from self.aim(self.client, self.host)
        slow_observed = {}
        self.request(self.client, 6, 10)
        yield self.wait(2, lambda: "active" in slow_observed,
                        lambda: self.capture(self.host, "ImpedimentRemaining", slow_observed))
        yield self.wait(4, lambda: max(self.values(self.host, "ImpedimentRemaining")) <= .01)
        slow_ok = "active" in slow_observed and max(self.values(self.host, "ImpedimentRemaining")) <= .01 and both_live()
        self.record(TESTS[4], slow_ok, active=slow_observed.get("active"), recovered=self.values(self.host, "ImpedimentRemaining"),
                    hud_acknowledgement="not simulated or asserted")
        self.require(slow_ok, "Real Arresto impediment or its recovery did not replicate")

        yield self.wait(4, lambda: self.ready(self.host) and self.ready(self.client))
        self.require(self.ready(self.host) and self.ready(self.client), "Earlier effects must expire before the headshot")
        yield from self.aim(self.host, self.client, head=True)
        head_before = self.values(self.client, "Vitality")
        fouls_before = int(prop(self.host["match"], "ConductFoulCount"))
        scores_before = self.scores(self.host)
        self.require(fouls_before == 0, "Earlier legal torso casts unexpectedly produced a foul")
        # Two actual goals reserve the Quaffle without a removed roof rule.
        # Quark 2 first gives the defending keeper genuine scoring-ball custody.
        # The subsequent Quaffle score must wait until that keeper releases it.
        quaffle, occupied = self.host["balls"][0], self.host["balls"][2]
        for ball in (quaffle, occupied):
            self.require(prop(ball, "Holder") is None and prop(ball, "bActive"),
                         "Fallback fixture needs two untouched active scoring balls")
        self.require(occupied.development_set_flight_fixture(vec((dimensions.GOAL_PLANE_X-200.8), 0, 3048), vec(2000, 0, 0)),
                     "Physical Quark goal fixture rejected")
        occupied.set_actor_tick_enabled(True)
        keeper_holds = lambda: prop(occupied, "Holder") is not None
        yield self.wait(3, keeper_holds)
        self.require(keeper_holds(), "First native Quark goal must reach a real keeper restart")
        keeper_slot = int(prop(prop(occupied, "Holder"), "RosterIndex"))
        self.require(self.scores(self.host) == [scores_before[0]+37, scores_before[1]],
                     "Quark fixture must produce exactly one genuine 37-point goal")
        self.require(quaffle.development_set_flight_fixture(vec((dimensions.GOAL_PLANE_X-200.8), 0, 2103.12), vec(2000, 0, 0)),
                     "Physical Quaffle goal fixture rejected")
        quaffle.set_actor_tick_enabled(True)
        score_reserved = lambda: all(str(prop(side["balls"][0], "BallStatus")) == "score"
                                      and prop(side["balls"][0], "Holder") is None
                                      for side in (self.host, self.client))
        yield self.wait(3, score_reserved)
        self.require(score_reserved(), "Second native goal must retain its score restart while keeper is occupied")
        scores_before = [scores_before[0]+50, scores_before[1]]
        self.require(self.scores(self.host) == self.scores(self.client) == scores_before,
                     "Both real goals and reserved Quaffle state must replicate")
        score_fixture = {"server_status_at_cast_submission": str(prop(quaffle, "BallStatus")),
                         "keeper_holds_other_scoring_ball": keeper_holds(), "keeper_slot": keeper_slot,
                         "scores_from_actual_goals": scores_before,
                         "server_live_time": float(prop(self.host["match"], "LiveSeconds"))}
        self.request(self.host, 6, 0)
        review = lambda: all(prop(side["match"], "bConductReviewPending") and not self.live(side)
                             for side in (self.host, self.client))
        yield self.wait(4, review)
        self.require(score_reserved(), "Headshot must preserve the genuine Quaffle score reservation")
        head_after = self.values(self.client, "Vitality")
        head_ok = review() and all(after <= before - 7.5 for before, after in zip(head_before, head_after))
        head_ok = head_ok and all(int(prop(side["match"], "ConductFoulCount")) == fouls_before + 1
                                  and "HEADSHOT" in str(prop(side["match"], "LastConductCall"))
                                  and "PLAYTEST REFEREE" in str(prop(side["match"], "ConductReviewStatus"))
                                  for side in (self.host, self.client))
        self.record(TESTS[5], head_ok, before=head_before, after=head_after,
                    server=self.conduct(self.host), client=self.conduct(self.client), score_fixture=score_fixture)
        self.require(head_ok, "Headshot effect and pending referee stoppage did not replicate")

        review_before = self.conduct(self.host)
        rejected = []
        for action in (9, 11):
            self.request(self.client, action)
            yield self.wait(.5)
            rejected.append(review() and self.conduct(self.host) == review_before
                            and self.conduct(self.client) == review_before)
        self.record(TESTS[6], all(rejected), actions=[9, 11], rejected=rejected,
                    server=self.conduct(self.host), client=self.conduct(self.client))
        self.require(all(rejected), "Remote client adjudicated the pending conduct")

        self.request(self.host, 9)
        queued = lambda: all(not prop(side["match"], "bConductReviewPending") and not self.live(side)
                             and int(prop(side["match"], "PendingPenaltyCount")) == 1
                             and "POSSESSION AWARD QUEUED" in str(prop(side["match"], "ConductReviewStatus"))
                             and prop(side["balls"][1], "Holder") is None
                             and str(prop(side["balls"][1], "BallStatus")) == "penalty"
                             for side in (self.host, self.client))
        yield self.wait(4, queued)
        queue_observed = queued()
        queue_state = self.conduct(self.host)
        yield self.wait(.5)
        queue_held = queued()
        score_preserved = score_reserved()
        self.require(queue_observed and queue_held and score_preserved,
                     "F7 must reserve available Quark 1 and preserve the prior Quaffle score reservation")
        self.request(self.host, 4)
        served = lambda: both_live() and all(int(prop(side["match"], "PendingPenaltyCount")) == 0 for side in (self.host, self.client)) \
            and prop(self.host["balls"][1], "Holder") == self.client_on_server() \
            and prop(self.client["balls"][1], "Holder") == self.client["pawn"]
        yield self.wait(4, served)
        served_observed = served()
        yield self.wait(.6)
        award_ok = served_observed and served() and self.scores(self.host) == self.scores(self.client) == scores_before
        award_ok = award_ok and all(int(prop(side["match"], "ConductFoulCount")) == fouls_before + 1 for side in (self.host, self.client))
        self.record(TESTS[7], award_ok, queued_observed=queue_observed, remained_pending=queue_held,
                    queued_state=queue_state, server=self.conduct(self.host), client=self.conduct(self.client),
                    server_holder_is_receiver=prop(self.host["balls"][1], "Holder") == self.client_on_server(),
                    client_holder_is_receiver=prop(self.client["balls"][1], "Holder") == self.client["pawn"],
                    award_ball=1, unavailable_first_choice=0,
                    scores_unchanged=self.scores(self.host) == scores_before)
        returned = lambda: all(prop(side["balls"][0], "bActive")
                               and str(prop(side["balls"][0], "BallStatus")) == ""
                               and prop(side["balls"][0], "Holder") is not None
                               and int(prop(prop(side["balls"][0], "Holder"), "RosterIndex")) == keeper_slot
                               for side in (self.host, self.client))
        yield self.wait(3, returned)
        self.record(TESTS[8], score_preserved and returned() and served()
                    and self.scores(self.host) == self.scores(self.client) == scores_before,
                    physical_goals=score_fixture, reserved_through_f7=score_preserved,
                    scored_ball_keeper_restart_observed=returned(), opposing_quark_possession_retained=served())



def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "scope": "two connected local PIE worlds; actual queued spell requests",
                "planned_tests": list(TESTS), "count": len(TESTS)}
    runner = SpellNetworkTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and (started or not runner.done):
        unreal._basketbroom_native_network_test = runner
    return {"status": "started" if started else runner.final_status,
            "report": str(REPORT), "planned_cases": len(TESTS)}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

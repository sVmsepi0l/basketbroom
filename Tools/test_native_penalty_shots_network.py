"""Paired native Serious/free-shot replication checks through owning inputs.

Run in separate fresh listen-server/client PIE worlds for each variant:
BRIDGE_ARGS={"variant":"regulation", "settings_already_configured":True}
BRIDGE_ARGS={"variant":"bloodbroom", "settings_already_configured":True}
Add "shot_kind":"free" to run the Moderate F6 path with no removal.
The existing network runner also accepts settings_source="editor_config" for
the standard PlayNetMode INI entry prepared with the editor closed. The report
records which external configuration route requires restoration afterward.
Both runs create an actual unlawful hit, then a host-selected Serious or free Quark
shot fired by the owning remote client. No protected gameplay property, score,
shot outcome, penalty or feedback receipt is injected. Actor/camera fixture
positions are arranged in disposable worlds, so movement replication is not
claimed. --list reports planned coverage without starting Unreal.
"""
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
ARGS = {"max_wall_seconds": 180, **globals().get("BRIDGE_ARGS", {})}
VARIANT = str(ARGS.get("variant", "regulation")).lower()
SHOT_KIND = str(ARGS.get("shot_kind", "serious")).lower()
FREE = SHOT_KIND == "free"
DISPOSITION = 12 if FREE else 10
REPORT = ROOT / ".local" / ("native-%s-shot-network-%s-results.json" % ("free" if FREE else "penalty", VARIANT))
TESTS = (
    "owning_client_role_and_affected_quark_pickup_reach_authority",
    "paired_variant_and_actual_illegal_hit_review_replicate",
    "remote_client_cannot_adjudicate_serious_shot",
    "host_serious_shot_ball_and_participants_replicate",
    "both_worlds_show_frozen_live_clock_during_shot_countdown",
    "client_wand_and_role_requests_cannot_bypass_shot_restrictions",
    "owning_client_shot_release_and_native_37_point_make_replicate",
    "actual_keeper_restart_and_single_served_penalty_replicate",
    "only_host_resumes_after_completed_shot",
    "managed_play_settings_restored_and_pie_ended",
)
if FREE:
    names = list(TESTS)
    names[2] = "remote_client_cannot_adjudicate_free_shot"
    names[3] = "host_free_shot_flag_ball_and_participants_replicate_without_removal"
    names[4] = "free_countdown_replicates_while_live_clocks_freeze_and_removal_stays_zero"
    names[7] = "free_keeper_restart_and_single_served_penalty_replicate_without_removal"
    names[8] = "only_host_resumes_free_shot_and_offender_remains_eligible"
    TESTS = tuple(names)
_spec = importlib.util.spec_from_file_location("_bb_penalty_network_fixture", ROOT / "Tools/test_native_spell_network.py")
spells = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spells)
base = spells.base
spells.TESTS, spells.REPORT, spells.ARGS = TESTS, REPORT, ARGS
base.TESTS, base.REPORT, base.ARGS = TESTS, REPORT, ARGS
unreal, prop, vec = base.unreal, base.prop, base.vec


def xyz(value):
    return [round(float(value.x), 3), round(float(value.y), 3), round(float(value.z), 3)]


class PenaltyShotNetworkTests(spells.SpellNetworkTests):
    def write(self, status):
        rows = [{"name": name, **self.results.get(name, {"status": "not_run"})} for name in TESTS]
        data = {
            "status": status, "phase": self.phase, "variant": VARIANT, "shot_kind": SHOT_KIND,
            "scope": "%s-shot RPC and state replication in distinct local PIE worlds" % SHOT_KIND,
            "elapsed_wall_seconds": round(time.monotonic()-self.started, 3),
            "passed": sum(row["status"] == "passed" for row in rows),
            "failed": sum(row["status"] == "failed" for row in rows),
            "not_run": sum(row["status"] == "not_run" for row in rows),
            "tests": rows, "provenance": self.provenance, "events": self.events,
            "settings_restored": self.settings_restored, "time_dilation_restored": self.dilations_restored,
            "reason": self.reason,
            "external_restore_required": base.net_mode_restore_actions(self.provenance),
            "not_covered": ["separate processes, remote machines, latency, loss and reconnect",
                            "physical controls and visual quality", "movement replication",
                            "automatic conduct severity, full regulation or Hogwarts Legacy multiplayer"],
        }
        base.write_json_atomic(REPORT, data)

    def shot(self, side):
        return {key: prop(side["match"], key) for key in
                ("bPenaltyShotActive", "bPenaltyShotReleased", "PenaltyShotSecondsLeft", "PenaltyShotBall",
                 "PenaltyShooterSlot", "PenaltyKeeperSlot", "PenaltyShotStatus", "PendingPenaltyCount", "bLive", "bFreeShot")}

    def diagnostic(self):
        values = [int(value) for value in self.host["match"].development_get_penalty_shot_state()]
        self.require(len(values) == 9, "Server shot diagnostic requires nine fields")
        return dict(zip(("penalty_id", "stage", "outcome", "ball", "shooter", "keeper",
                         "pending", "awarded_points", "offender"), values))

    def clocks(self):
        return [float(prop(side["match"], "LiveSeconds")) for side in (self.host, self.client)]

    def removal(self):
        method = getattr(self.host["match"], "development_get_removal_seconds", None)
        self.require(callable(method), "Server requires read-only removal diagnostic")
        return float(method(int(prop(self.host["pawn"], "RosterIndex"))))

    def free_state_correct(self):
        return all(bool(prop(side["match"], "bFreeShot")) == FREE for side in (self.host, self.client)) and (not FREE or self.removal() == 0)

    def paired_stop(self):
        return not self.live(self.host) and not self.live(self.client)

    def arrange_owner_at_native_shot(self):
        # CharacterMovement is disabled by the spell fixture. Mirror only the
        # server's genuine shot mark into its owning client to make camera aim
        # meaningful, explicitly excluding movement replication from evidence.
        native = self.client_on_server()
        point = native.get_actor_location()
        self.client["pawn"].set_actor_location(point, False, True)
        self.events.append({"fixture": "mirror native shooter mark to disabled-movement owner", "point": xyz(point)})
        keeper_slot = int(prop(self.host["match"], "PenaltyKeeperSlot"))
        keeper = next(r for r in self.host["riders"] if int(prop(r, "RosterIndex")) == keeper_slot)
        p = keeper.get_actor_location()
        keeper.set_actor_location(vec(p.x, 700, p.z), False, True)
        self.events.append({"fixture": "CPU keeper lateral defending position", "point": xyz(keeper.get_actor_location())})
        for ball in self.host["balls"].values():
            ball.set_actor_tick_enabled(True)

    def aim_quark(self):
        target = vec(-6400.8, 0, 3048)
        controller = unreal.GameplayStatics.get_player_controller(self.client["world"], 0)
        for unused in range(2):
            start = self.client["pawn"].get_carry_location()
            delta = target-start
            flight = math.hypot(delta.x, delta.y)/4400
            vertical = delta.z+.5*380*flight*flight
            pitch = math.degrees(math.atan2(vertical, math.hypot(delta.x, delta.y)))
            yaw = math.degrees(math.atan2(delta.y, delta.x))
            controller.set_control_rotation(unreal.Rotator(pitch=pitch, yaw=yaw, roll=0))
            desired = vec(math.cos(math.radians(pitch))*math.cos(math.radians(yaw)),
                          math.cos(math.radians(pitch))*math.sin(math.radians(yaw)), math.sin(math.radians(pitch)))
            aligned = lambda: sum(x*y for x, y in zip(xyz(self.client["pawn"].get_aim_direction()), xyz(desired))) > .999
            yield self.wait(.8, aligned)
            self.require(aligned(), "Actual client camera aim did not settle to the penalty shot")
        self.events.append({"action": "ordinary client shot aim", "carry": xyz(self.client["pawn"].get_carry_location()),
                            "aim": xyz(self.client["pawn"].get_aim_direction()), "target": xyz(target)})

    def scenarios(self):
        self.require(VARIANT in ("regulation", "bloodbroom"), "Unknown variant")
        self.require(SHOT_KIND in ("serious", "free"), "Unknown shot kind")
        self.require(self.host["world"] != self.client["world"] and self.host["match"].has_authority()
                     and not self.client["match"].has_authority(), "Distinct connected authority/client worlds required")
        self.shot(self.host)
        self.shot(self.client)
        self.require(self.paired_stop(), "Fresh lobby required")
        self.request(self.client, 3, 1)
        yield self.wait(5, lambda: int(prop(self.client["pawn"], "TeamIndex")) == int(prop(self.client_on_server(), "TeamIndex")) == 1)
        self.request(self.client, 2, 1)
        yield self.wait(5, lambda: int(prop(self.client["pawn"], "Position")) == int(prop(self.client_on_server(), "Position")) == 1)
        self.require(int(prop(self.client["pawn"], "Position")) == int(prop(self.client_on_server(), "Position")) == 1,
                     "Ordinary client role request must reach the server")
        desired = VARIANT == "bloodbroom"
        if bool(prop(self.host["match"], "bBloodbroom")) != desired:
            self.request(self.host, 8)
        selected = lambda: all(bool(prop(side["match"], "bBloodbroom")) == desired for side in (self.host, self.client))
        yield self.wait(3, selected)
        self.require(selected(), "Host-selected variant must replicate")
        self.request(self.host, 4)
        yield self.wait(5, lambda: self.live(self.host) and self.live(self.client))
        self.require(self.live(self.host) and self.live(self.client), "Host kickoff must reach both worlds")
        self.arrange()
        for side in (self.host, self.client):
            world = side["world"]
            self.dilations.append((world, float(unreal.GameplayStatics.get_global_time_dilation(world))))
            unreal.GameplayStatics.set_global_time_dilation(world, .25)
        self.dilations_restored = False
        self.provenance.update(disposable_pie_time_dilation=.25, input_path="owning rider FIFO -> ordinary ServerAction",
                               fixture_policy="Only disposable geometry and pre-pickup free flight; no gameplay state injected")
        ball, replica = self.host["balls"][1], self.client["balls"][1]
        remote = self.client_on_server()
        p = remote.get_actor_location()
        self.require(prop(ball, "Holder") is None and prop(ball, "bActive"), "Real pickup needs a free live Quark")
        self.require(ball.development_set_flight_fixture(p+vec(180, 0, 30), vec(0, 0, 0)), "Quark fixture rejected")
        ball.set_actor_tick_enabled(True)
        yield self.wait(.35)
        self.request(self.client, 0)
        owned = lambda: prop(ball, "Holder") == remote and prop(replica, "Holder") == self.client["pawn"]
        yield self.wait(3, owned)
        self.record(TESTS[0], owned(), server_holder=owned(), server_role=int(prop(remote, "Position")), client_role=int(prop(self.client["pawn"], "Position")))
        self.require(owned(), "Denied Quark must be held through a real client pickup")
        before = self.values(self.client, "Vitality")
        if desired:
            yield from self.aim(self.host, self.client)
            self.request(self.host, 6, 10)
            impeded = lambda: min(self.values(self.client, "ImpedimentRemaining")) > .1
            yield self.wait(2, impeded)
            self.require(impeded(), "Real Arresto must reach the remote rider")
            ready_notice = lambda: self.ready(self.host) and "target impeded" in str(prop(self.host["pawn"], "SpellFeedback"))
            yield self.wait(2, ready_notice)
            self.require(ready_notice() and min(self.values(self.client, "ImpedimentRemaining")) > .15,
                         "Bloodbroom double-tap needs actual live impediment and owner HUD delivery")
            self.request(self.host, 6, 2)
            flag = "DOUBLE-TAP"
        else:
            yield from self.aim(self.host, self.client, head=True)
            self.request(self.host, 6, 0)
            flag = "HEADSHOT"
        reviewed = lambda: all(prop(side["match"], "bConductReviewPending") and flag in str(prop(side["match"], "LastConductCall")) for side in (self.host, self.client))
        yield self.wait(3, reviewed)
        effect = min(self.values(self.client, "StunRemaining")) > 0 if desired else all(v < old-4 for v, old in zip(self.values(self.client, "Vitality"), before))
        self.record(TESTS[1], selected() and reviewed() and effect and self.paired_stop(),
                    server=self.conduct(self.host), client=self.conduct(self.client), applied_effect=effect)
        self.require(reviewed() and effect, "Actual applied illegal hit must precede host shot selection")
        before_call = self.conduct(self.host)
        self.request(self.client, DISPOSITION)
        yield self.wait(.4)
        rejected = self.conduct(self.host) == before_call and all(not prop(side["match"], "bPenaltyShotActive") for side in (self.host, self.client))
        self.record(TESTS[2], rejected, server=self.shot(self.host), client=self.shot(self.client))
        self.require(rejected, "Remote client must not adjudicate its own %s shot" % SHOT_KIND)
        self.request(self.host, DISPOSITION)
        staged = lambda: self.free_state_correct() and all(prop(side["match"], "bPenaltyShotActive") and int(prop(side["match"], "PenaltyShotBall")) == 1 for side in (self.host, self.client))
        yield self.wait(3, staged)
        same_participants = all(int(prop(self.host["match"], key)) == int(prop(self.client["match"], key)) for key in ("PenaltyShooterSlot", "PenaltyKeeperSlot"))
        self.record(TESTS[3], staged() and same_participants and owned(), server=self.shot(self.host), client=self.shot(self.client), offender_removal=self.removal())
        self.require(staged() and owned(), "Host-selected Quark shot and ownership must replicate")
        self.arrange_owner_at_native_shot()
        clocks = self.clocks()
        counters = [float(prop(side["match"], "PenaltyShotSecondsLeft")) for side in (self.host, self.client)]
        yield self.wait(.4)
        later = [float(prop(side["match"], "PenaltyShotSecondsLeft")) for side in (self.host, self.client)]
        self.record(TESTS[4], self.free_state_correct() and self.clocks() == clocks and self.paired_stop() and all(a < b-.15 for a, b in zip(later, counters)),
                    clocks_before=clocks, clocks_after=self.clocks(), countdown_before=counters, countdown_after=later, offender_removal=self.removal())
        role = int(prop(self.client["pawn"], "Position"))
        cooldowns = self.values(self.client, "SpellCooldownRemaining")
        self.request(self.client, 6, 0)
        yield self.wait(.2)
        self.request(self.client, 2, 5)
        yield self.wait(.2)
        self.record(TESTS[5], self.values(self.client, "SpellCooldownRemaining") == cooldowns
                    and int(prop(self.client["pawn"], "Position")) == int(prop(remote, "Position")) == role and owned() and self.paired_stop(),
                    server=self.shot(self.host), client=self.shot(self.client), cooldowns=self.values(self.client, "SpellCooldownRemaining"))
        yield from self.aim_quark()
        scores_before = self.scores(self.host)
        self.request(self.client, 1)
        released = lambda: prop(ball, "Holder") is None and prop(replica, "Holder") is None
        yield self.wait(.8, released)
        release_observed = released()
        self.request(self.client, 1)
        expected = [scores_before[0], scores_before[1]+37]
        scored = lambda: self.scores(self.host) == self.scores(self.client) == expected
        yield self.wait(4, scored)
        self.record(TESTS[6], release_observed and scored() and self.diagnostic()["outcome"] == 1,
                    release_observed=release_observed, scores_before=scores_before, expected=expected,
                    server_scores=self.scores(self.host), client_scores=self.scores(self.client), diagnostic=self.diagnostic())
        self.require(scored(), "Client-fired Quark must score through native server physics and replicate")
        keeper_slot = int(prop(self.host["match"], "PenaltyKeeperSlot"))
        def served():
            for side in (self.host, self.client):
                holder = prop(side["balls"][1], "Holder")
                if holder is None or int(prop(holder, "RosterIndex")) != keeper_slot or int(prop(side["match"], "PendingPenaltyCount")) != 0:
                    return False
            return self.diagnostic()["stage"] == 4 and self.paired_stop()
        yield self.wait(4, served)
        self.record(TESTS[7], served() and scored() and self.diagnostic()["pending"] == 0 and self.free_state_correct(),
                    server=self.shot(self.host), client=self.shot(self.client), diagnostic=self.diagnostic(), offender_removal=self.removal())
        self.require(served(), "Actual keeper restart must serve and replicate before global resume")
        self.request(self.client, 4)
        yield self.wait(.3)
        client_rejected = self.paired_stop()
        self.request(self.host, 4)
        live = lambda: self.live(self.host) and self.live(self.client)
        yield self.wait(3, live)
        self.record(TESTS[8], client_rejected and live() and self.scores(self.host) == self.scores(self.client) == expected
                    and (not FREE or self.removal() == 0),
                    remote_resume_rejected=client_rejected, server=self.snapshot(self.host), client=self.snapshot(self.client), offender_removal=self.removal())


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "planned_tests": list(TESTS), "count": len(TESTS), "variants": ["regulation", "bloodbroom"], "shot_kinds": ["serious", "free"]}
    runner = PenaltyShotNetworkTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and (started or not runner.done):
        unreal._basketbroom_native_network_test = runner
    return {"status": "started" if started else runner.final_status, "report": str(REPORT), "planned_cases": len(TESTS), "variant": VARIANT, "shot_kind": SHOT_KIND}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

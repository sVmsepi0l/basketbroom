"""Real native Serious-shot checks, one disposable PIE world per case.

Through editor_bridge.py, use BRIDGE_ARGS such as:
  {"variant": "regulation", "outcome": "make", "affected_ball": 0}
  {"variant": "bloodbroom", "outcome": "miss", "affected_ball": 1}
  {"variant": "bloodbroom", "outcome": "timeout", "affected_ball": 0}
Run both ball makes, a Quark miss and a Quaffle timeout in both variants. Each fresh run creates a real foul and
uses the ordinary host Serious action (10 / F8). No score, effect, possession,
penalty, shot result, timer or confirmation receipt is injected. A read-only
rule diagnostic establishes removal timing; camera/actor transforms arrange
only disposable test geometry. --list prints the plan without running Unreal.
"""
import importlib.util
import json
import math
from pathlib import Path
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
ARGS = {"max_wall_seconds": 180, **globals().get("BRIDGE_ARGS", {})}
VARIANT = str(ARGS.get("variant", "regulation")).lower()
OUTCOME = str(ARGS.get("outcome", "make")).lower()
AFFECTED_BALL = int(ARGS.get("affected_ball", 0))
REPORT = ROOT / ".local" / ("native-penalty-shot-%s-%s-ball%d-results.json" %
                            (VARIANT, OUTCOME, AFFECTED_BALL))
CASES = (
    "paired_variant_selected_and_locked_after_native_kickoff",
    "victim_takes_actual_scoring_ball_before_illegal_hit",
    "illegal_hit_applies_then_creates_real_conduct_review",
    "serious_disposition_without_review_cannot_create_shot",
    "host_serious_action_stages_correct_ball_shooter_and_keeper",
    "shot_countdown_advances_while_live_clocks_and_other_balls_freeze",
    "shot_blocks_wandwork_role_switch_and_global_resume",
    "shot_outcome_comes_from_one_release_or_actual_timeout",
    "shot_scores_ordinary_ball_value_exactly_once",
    "offender_removal_remains_frozen_during_shot_and_result",
    "defending_keeper_gets_actual_protected_restart",
    "offender_cannot_cast_or_escape_removal_by_role_switch",
    "ordinary_resume_advances_live_time_and_removal_together",
)

_spec = importlib.util.spec_from_file_location("_bb_penalty_spell_fixture", ROOT / "Tools/test_native_spells.py")
spells = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spells)
base = spells.base
base.TEST_NAMES, base.REPORT, base.ARGS = CASES, REPORT, ARGS
unreal, prop, xyz, vector = base.unreal, base.prop, base.xyz, base.vector
_receipt_spec = importlib.util.spec_from_file_location("_bb_penalty_receipts", ROOT / "Tools/native_test_receipts.py")
receipts = importlib.util.module_from_spec(_receipt_spec)
_receipt_spec.loader.exec_module(receipts)


def dist(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


class NativePenaltyShotTests(spells.NativeSpellTests):
    def write_report(self, status, reason=None):
        data = receipts.single_world_payload(self, CASES, status, reason,
                                              unreal.SystemLibrary.get_engine_version() if unreal else None)
        data["screenshots"] = [{**item, "file_written": Path(item["path"]).is_file(),
                                "bytes": Path(item["path"]).stat().st_size if Path(item["path"]).is_file() else 0}
                               for item in getattr(self, "screenshot_requests", [])]
        data.update(
            scope="native authority PIE Serious-shot flow with two real local humans",
            variant=VARIANT, outcome=OUTCOME, affected_ball=AFFECTED_BALL,
            fixture_policy="Only disposable actor/camera transforms, component ticks, local-player lifecycle, "
                           "free-ball trajectory before pickup, and ordinary queued input are arranged. "
                           "No shot flight/result, score, custody, penalty, effect, rule timer or HUD ACK is written.",
            not_covered=["network replication or remote ownership (separate two-world suite)",
                         "physical keyboard/controller bindings or visual quality",
                         "automatic BB-0 severity selection or Catastrophic adjudication",
                         "remote latency, loss, full-match balance or Hogwarts Legacy integration"],
        )
        receipts.write_json_atomic(REPORT, data)

    def capture_ui(self, label):
        if not ARGS.get("capture_screenshots", False):
            return
        if not hasattr(self, "screenshot_directory"):
            self.screenshot_directory = ROOT / ".local/penalty-shot-ui" / (
                "%s-%s-ball%d-%s" % (VARIANT, OUTCOME, AFFECTED_BALL, uuid.uuid4().hex[:12]))
            self.screenshot_directory.mkdir(parents=True, exist_ok=False)
            self.screenshot_requests = []
        output = self.screenshot_directory / (label + ".png")
        self.require(not output.exists(), "Optional screenshot destination must be fresh")
        # Verified in installed UE5.8 GameViewportClient.cpp:4284 and
        # UnrealClient.cpp:219: explicit path, actual viewport UI, no suffix.
        command = 'Shot showui filename="%s" -nosuffix' % output.as_posix()
        unreal.SystemLibrary.execute_console_command(self.world, command)
        self.screenshot_requests.append({"label": label, "path": str(output), "requested_world_seconds": self.now(),
                                         "shot_state_at_request": self.shot(), "command": command})
        self.event("real_viewport_screenshot_requested", label=label, path=str(output))

    def shot(self):
        return {name: prop(self.match, name) for name in
                ("bPenaltyShotActive", "bPenaltyShotReleased", "PenaltyShotSecondsLeft",
                 "PenaltyShotBall", "PenaltyShooterSlot", "PenaltyKeeperSlot", "PenaltyShotStatus")}

    def diagnostic(self):
        method = getattr(self.match, "development_get_penalty_shot_state", None)
        self.require(callable(method), "Loaded DLL lacks read-only shot diagnostic")
        values = [int(value) for value in method()]
        self.require(len(values) == 9, "Shot diagnostic must have nine documented fields")
        return dict(zip(("penalty_id", "stage", "outcome", "ball", "shooter", "keeper",
                         "pending", "awarded_points", "offender"), values))

    def clocks(self):
        return {key: float(prop(self.match, key)) for key in ("LiveSeconds", "SecondsLeft")}

    def removal(self):
        method = getattr(self.match, "development_get_removal_seconds", None)
        self.require(callable(method), "Loaded DLL lacks read-only DevelopmentGetRemovalSeconds")
        return float(method(int(prop(self.pawn, "RosterIndex"))))

    def equipment(self, excluded=None):
        return {str(index): {"xyz": xyz(ball.get_actor_location()), "active": bool(prop(ball, "bActive")),
                             "return_in": float(prop(ball, "ReturnIn")),
                             "holder": int(prop(prop(ball, "Holder"), "RosterIndex")) if prop(ball, "Holder") else -1}
                for index, ball in self.balls.items() if index != excluded}

    def prepare(self):
        self.require(VARIANT in ("regulation", "bloodbroom"), "Unknown variant")
        self.require(OUTCOME in ("make", "miss", "timeout"), "Unknown shot outcome")
        self.require(AFFECTED_BALL in (0, 1, 2), "Affected ball must be Quaffle or Quark")
        self.shot()  # Fail explicitly on a stale DLL before any fixture action.
        self.original_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        unreal.GameplayStatics.set_global_time_dilation(self.world, .5)
        self.provenance.update(owned_world_dilation=.5, input_path="guarded FIFO -> native Tick -> ordinary action",
                               editor_assets_saved=False, hit_confirmation="native HUD draw and later receipt only")
        self.guest_controller = unreal.GameplayStatics.create_player(self.world, -1, True)
        self.require(self.guest_controller is not None, "Public CreatePlayer failed")
        self.extra_controllers.append(self.guest_controller)
        yield self.wait_until(lambda: unreal.GameplayStatics.get_player_pawn(self.world, 1) is not None, timeout=2)
        self.guest = unreal.GameplayStatics.get_player_pawn(self.world, 1)
        self.require(self.guest and self.guest.get_class() == self.classes["BBRiderCharacter"], "Guest needs native rider")
        for controller in (self.controller, self.guest_controller):
            self.controller_ticks.append((controller, bool(controller.is_actor_tick_enabled())))
            controller.set_actor_tick_enabled(False)
        self.riders = list(unreal.GameplayStatics.get_all_actors_of_class(self.world, self.classes["BBRiderCharacter"]))
        self.require(self.roster_valid() and int(prop(self.pawn, "TeamIndex")) != int(prop(self.guest, "TeamIndex")),
                     "Two local humans must occupy opposite valid team slots")
        desired = VARIANT == "bloodbroom"
        if bool(prop(self.match, "bBloodbroom")) != desired:
            self.request(8)
            yield self.wait_until(lambda: bool(prop(self.match, "bBloodbroom")) == desired, timeout=1)
        self.require(bool(prop(self.match, "bBloodbroom")) == desired, "Host variant selection failed")
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")), timeout=2)
        self.require(prop(self.match, "bLive"), "Ordinary host kickoff failed")
        self.isolate()
        yield from self.anchor_pair()
        self.request(8)
        yield self.wait(.2)
        self.record(CASES[0], bool(prop(self.match, "bBloodbroom")) == desired and bool(prop(self.match, "bLive")),
                    variant=VARIANT, roster=self.roster(), world=self.world.get_path_name())
        self.require(self.scores() == [0, 0], "Controlled shot fixture must begin before a native CPU score")
        before = self.conduct()
        self.request(10)
        yield self.wait(.2)
        self.record(CASES[3], self.conduct() == before and not prop(self.match, "bPenaltyShotActive")
                    and prop(self.match, "bLive"), conduct=self.conduct(),
                    authority_scope="host input without a pending review; remote guard tested separately")

    def foul(self):
        # Guest ordinary pickup provides the denied-ball evidence before either
        # head damage or Stupefy can release its custody through native gameplay.
        target = (-400, 0, 1792 if VARIANT == "regulation" else 1872)
        yield from self.anchor_pair(target=target)
        ball = self.seed_ball(AFFECTED_BALL, (target[0]+200, target[1], target[2]+30))
        yield self.wait(.3)
        self.guest_request(0)
        yield self.wait_until(lambda: prop(ball, "Holder") == self.guest, timeout=1)
        held = prop(ball, "Holder") == self.guest
        self.record(CASES[1], held, ball=AFFECTED_BALL, holder=int(prop(self.guest, "RosterIndex")), scores=self.scores())
        self.require(held, "Victim must actually hold the affected scoring ball")
        before = self.conduct()
        health = float(prop(self.guest, "Vitality"))
        if VARIANT == "regulation":
            self.request(6, 0)
            yield self.wait_until(lambda: bool(prop(self.match, "bConductReviewPending")), timeout=.8)
            effect = float(prop(self.guest, "Vitality")) < health-4
            flags = 2
        else:
            yield from self.drain_feedback()
            self.request(6, 10)
            yield self.wait_until(lambda: float(prop(self.guest, "ImpedimentRemaining")) > 0, timeout=.8)
            self.require(float(prop(self.guest, "ImpedimentRemaining")) > 0 and self.conduct()[0] == before[0],
                         "Actual torso Arresto must apply without a Bloodbroom foul")
            yield self.wait_until(lambda: self.ready_to_cast() and "target impeded" in str(prop(self.pawn, "SpellFeedback")), timeout=2)
            self.require(self.ready_to_cast() and float(prop(self.guest, "ImpedimentRemaining")) > .15,
                         "Double-tap fixture needs a naturally active, owner-notified impediment")
            self.event("real_impediment_notice", notice=str(prop(self.pawn, "SpellFeedback")))
            self.request(6, 2)
            yield self.wait_until(lambda: bool(prop(self.match, "bConductReviewPending")), timeout=.8)
            effect = float(prop(self.guest, "StunRemaining")) > 0
            flags = 8
        state = self.conduct()
        passed = effect and state[0] == before[0]+1 and state[1] == 1 and state[3] == flags and not prop(self.match, "bLive")
        self.record(CASES[2], passed, before=before, after=state, effects=self.effects(self.guest),
                    mode=VARIANT, applied_before_adjudication=True)
        self.require(passed, "Only an observed illegal native hit can start this shot test")

    def start_shot(self):
        self.request(10)
        yield self.wait_until(lambda: bool(prop(self.match, "bPenaltyShotActive")), timeout=2)
        shot = self.shot()
        self.require(shot["bPenaltyShotActive"], "Host Serious action must enter a real shot")
        self.shot_ball = self.balls[int(shot["PenaltyShotBall"])]
        shooters = [r for r in self.riders if int(prop(r, "RosterIndex")) == int(shot["PenaltyShooterSlot"])]
        keepers = [r for r in self.riders if int(prop(r, "RosterIndex")) == int(shot["PenaltyKeeperSlot"])]
        self.require(len(shooters) == len(keepers) == 1, "Shot needs unique shooter and keeper")
        self.shooter, self.keeper = shooters[0], keepers[0]
        passed = (int(shot["PenaltyShotBall"]) == AFFECTED_BALL and self.shooter == self.guest
                  and int(prop(self.keeper, "Position")) == 0
                  and int(prop(self.keeper, "TeamIndex")) != int(prop(self.shooter, "TeamIndex"))
                  and prop(self.shot_ball, "Holder") == self.shooter and not prop(self.match, "bLive"))
        self.record(CASES[4], passed, shot=shot, shooter=xyz(self.shooter.get_actor_location()),
                    keeper=xyz(self.keeper.get_actor_location()), removal=self.removal())
        self.require(passed, "Native selection must use the harmed eligible human and the affected ball")
        diagnostic = self.diagnostic()
        self.require(diagnostic["penalty_id"] > 0 and diagnostic["pending"] == 1
                     and diagnostic["offender"] == int(prop(self.pawn, "RosterIndex")),
                     "Shot must retain an actual unresolved Serious penalty")
        if OUTCOME == "make":
            # Keeper remains a real defender; arrange a clear line for the make
            # fixture using only that disposable actor's legal lateral location.
            point = xyz(self.keeper.get_actor_location())
            self.keeper.set_actor_location(vector((point[0], 700, point[2])), False, True)
            self.event("keeper_clear_shooting_lane", location=xyz(self.keeper.get_actor_location()))
        # Turn the original equipment ticks back on: immobility must be caused
        # by shot rules, not the general fixture's disabled ticks.
        for ball in self.balls.values():
            ball.set_actor_tick_enabled(True)
        self.frozen_clocks, self.frozen_removal = self.clocks(), self.removal()
        before = self.equipment(AFFECTED_BALL)
        start = float(prop(self.match, "PenaltyShotSecondsLeft"))
        self.capture_ui("ready")
        yield self.wait(.4)
        after, end = self.equipment(AFFECTED_BALL), float(prop(self.match, "PenaltyShotSecondsLeft"))
        self.record(CASES[5], before == after and self.clocks() == self.frozen_clocks and end < start-.15,
                    before=before, after=after, clocks=self.clocks(), countdown=[start, end],
                    equipment_ticks_enabled=all(b.is_actor_tick_enabled() for b in self.balls.values()))
        role = int(prop(self.guest, "Position"))
        effects = self.effects(self.guest)
        self.guest_request(6, 0)
        yield self.wait(.12)
        self.guest_request(2, 5)
        yield self.wait(.12)
        self.request(4)
        yield self.wait(.12)
        self.record(CASES[6], self.effects(self.guest) == effects and int(prop(self.guest, "Position")) == role
                    and not prop(self.match, "bLive") and bool(prop(self.match, "bPenaltyShotActive"))
                    and not prop(self.match, "bPenaltyShotReleased"), effects=self.effects(self.guest), shot=self.shot())

    def aim_shot(self):
        # A real camera direction and ordinary release drive the native ball.
        # Corrections use observed carry origin; no in-flight fixture is used.
        sign = 1 if int(prop(self.guest, "TeamIndex")) == 0 else -1
        target = (sign*6400.8, 0 if OUTCOME == "make" else 2400,
                  2103.12 if AFFECTED_BALL == 0 else 3048.0)
        for unused in range(2):
            start = xyz(self.guest.get_carry_location())
            delta = [target[i]-start[i] for i in range(3)]
            flight = math.hypot(delta[0], delta[1])/4400
            delta[2] += .5*380*flight*flight
            pitch = math.degrees(math.atan2(delta[2], math.hypot(delta[0], delta[1])))
            yaw = math.degrees(math.atan2(delta[1], delta[0]))
            self.guest_controller.set_control_rotation(unreal.Rotator(pitch=pitch, yaw=yaw, roll=0))
            direction = [math.cos(math.radians(pitch))*math.cos(math.radians(yaw)),
                         math.cos(math.radians(pitch))*math.sin(math.radians(yaw)), math.sin(math.radians(pitch))]
            yield self.wait_until(lambda: sum(x*y for x, y in zip(xyz(self.guest.get_aim_direction()), direction)) > .999, timeout=.5)
        self.event("ordinary_shot_aim", start=xyz(self.guest.get_carry_location()), target=target,
                   native_aim=xyz(self.guest.get_aim_direction()), outcome=OUTCOME)

    def execute_shot(self):
        before_score = self.scores()
        points = 13 if AFFECTED_BALL == 0 else 37
        released, samples = False, []
        if OUTCOME != "timeout":
            yield from self.aim_shot()
            origin = xyz(self.guest.get_carry_location())
            self.guest_request(1)
            yield self.wait_until(lambda: prop(self.match, "bPenaltyShotReleased") or not prop(self.match, "bPenaltyShotActive"), timeout=.5)
            released = prop(self.shot_ball, "Holder") != self.guest
            self.event("first_release_observed", holder_lost=released, shot=self.shot(), ball=xyz(self.shot_ball.get_actor_location()))
            self.guest_request(1)  # Cannot restart/retake a shot already in flight.
        else:
            origin = xyz(self.shot_ball.get_actor_location())

        def observe():
            samples.append({"point": xyz(self.shot_ball.get_actor_location()), "shot": self.shot(),
                            "scores": self.scores(), "clocks": self.clocks(), "removal": self.removal()})

        yield self.wait_until(lambda: self.diagnostic()["outcome"] != 0, observe, timeout=7)
        observe()
        outcome_status = str(prop(self.match, "PenaltyShotStatus")).lower()
        travelled = max((dist(origin, row["point"]) for row in samples), default=0)
        result = self.diagnostic()
        expected_outcome = {"make": 1, "miss": 2, "timeout": 3}[OUTCOME]
        native_outcome = (result["outcome"] == expected_outcome and not prop(self.match, "bLive")
                          and ((OUTCOME == "timeout" and not released and "time" in outcome_status)
                               or (OUTCOME != "timeout" and released and travelled > 500)))
        self.record(CASES[7], native_outcome, requested_outcome=OUTCOME, status=outcome_status,
                    holder_lost=released, travel_cm=travelled, samples=samples,
                    release_requests=0 if OUTCOME == "timeout" else 2, diagnostic=result)
        self.require(native_outcome, "Shot must finish through native flight or its own attempt timeout")
        expected = [0, 0]
        if OUTCOME == "make":
            expected[int(prop(self.guest, "TeamIndex"))] = points
        delta = [a-b for a, b in zip(self.scores(), before_score)]
        score_after = self.scores()
        self.capture_ui("result")
        yield self.wait(.3)
        self.record(CASES[8], delta == expected and self.scores() == score_after, expected=expected,
                    before=before_score, after=self.scores(), actual_delta=delta)
        self.record(CASES[9], self.clocks() == self.frozen_clocks and abs(self.removal()-self.frozen_removal) < .03
                    and all(row["clocks"] == self.frozen_clocks and abs(row["removal"]-self.frozen_removal) < .03 for row in samples),
                    clocks=self.clocks(), removal_before=self.frozen_removal, removal_after=self.removal())
        yield self.wait_until(lambda: self.diagnostic()["stage"] == 4 and prop(self.shot_ball, "Holder") == self.keeper, timeout=3)
        self.record(CASES[10], not prop(self.match, "bLive") and prop(self.shot_ball, "Holder") == self.keeper
                    and int(prop(self.match, "PendingPenaltyCount")) == 0, shot=self.shot(),
                    holder=int(prop(self.keeper, "RosterIndex")) if prop(self.shot_ball, "Holder") == self.keeper else None,
                    pending=int(prop(self.match, "PendingPenaltyCount")), diagnostic=self.diagnostic())
        self.require(not prop(self.match, "bLive") and prop(self.shot_ball, "Holder") == self.keeper,
                     "Actual defending restart must be served before ordinary host resume")
        role = int(prop(self.pawn, "Position"))
        self.request(2, 5)  # Stopped play would otherwise allow role changes.
        yield self.wait(.12)
        role_locked_while_stopped = int(prop(self.pawn, "Position")) == role
        self.request(4)
        yield self.wait_until(lambda: prop(self.match, "bLive"), timeout=2)
        self.require(prop(self.match, "bLive"), "Host must resume ordinary play after actual shot resolution")
        self.isolate()
        yield self.wait_until(lambda: float(prop(self.pawn, "SpellCooldownRemaining")) <= 0, timeout=3)
        self.require(float(prop(self.pawn, "SpellCooldownRemaining")) <= 0, "Removed offender cooldown must expire naturally before cast rejection is tested")
        self.request(6, 0)
        yield self.wait(.12)
        self.record(CASES[11], self.removal() > 0 and role_locked_while_stopped and int(prop(self.pawn, "Position")) == role
                    and float(prop(self.pawn, "SpellCooldownRemaining")) == 0
                    and abs(self.pawn.get_actor_location().x) >= 7100, removal=self.removal(), role=int(prop(self.pawn, "Position")),
                    effects=self.effects(self.pawn), location=xyz(self.pawn.get_actor_location()))
        live, removal = float(prop(self.match, "LiveSeconds")), self.removal()
        yield self.wait(.5)
        live_delta = float(prop(self.match, "LiveSeconds"))-live
        removal_delta = removal-self.removal()
        self.record(CASES[12], live_delta > .2 and removal_delta > .2 and abs(live_delta-removal_delta) < .05,
                    live_delta=live_delta, removal_delta=removal_delta, removal_remaining=self.removal())

    def scenarios(self):
        yield from self.prepare()
        yield from self.foul()
        yield from self.start_shot()
        yield from self.execute_shot()


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "cases_per_run": len(CASES), "planned_cases": list(CASES),
                "required_matrix": [{"variant": v, "outcome": o, "affected_ball": b}
                                    for v in ("regulation", "bloodbroom")
                                    for o, b in (("make", 0), ("make", 1), ("miss", 1), ("timeout", 0))]}
    test = NativePenaltyShotTests()
    try:
        started = test.begin()
    except Exception:
        test.finish("error", traceback.format_exc())
        started = False
    if unreal and started:
        unreal._basketbroom_native_test = test
    return {"status": "started" if started else test.final_status, "report": str(REPORT), "planned_cases": len(CASES),
            "variant": VARIANT, "outcome": OUTCOME, "affected_ball": AFFECTED_BALL}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

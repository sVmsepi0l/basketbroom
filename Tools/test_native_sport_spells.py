"""Five sporting spell adapters through real native player input, in both modes.

Bridge arguments: {"variant":"regulation"} or {"variant":"bloodbroom"}.
No spell timer, hit receipt, possession, score, conduct or match clock is written.
Transforms/ordinary movement inputs/PIE time dilation arrange disposable fixtures.
--list only describes the plan. It does not execute or certify gameplay.
"""
import importlib.util
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
ARGS = {"max_wall_seconds": 420, **globals().get("BRIDGE_ARGS", {})}
VARIANT = str(ARGS.get("variant", "regulation")).lower()
CASES = (
    "native_opposing_players_and_variant",
    "disillusionment_is_hidden_only_from_opponent_view",
    "revelio_restores_in_range_visibility",
    "revelio_has_range_and_world_occlusion_limits",
    "targeted_cast_breaks_caster_concealment",
    "applied_hit_breaks_target_concealment",
    "petrificus_requires_concealment",
    "petrificus_requires_behind_approach",
    "petrificus_is_denied_when_target_revelio_detects_caster",
    "petrificus_binds_and_drops_real_possession",
    "protego_blocks_transformation",
    "transformation_drops_ball_and_displays_noncolliding_orb",
    "transformation_blocks_flight_wand_and_ball_interaction",
    "official_stoppage_freezes_new_status_timers",
    "transformation_expires_and_restores_flight",
    "imperio_keeps_controller_and_applies_mode_specific_conduct",
    "imperio_reverses_horizontal_movement_and_preserves_vertical",
    "imperio_recovers_without_ownership_change",
    "stoppage_rejects_new_spell_effects",
    "real_quarter_break_preserves_then_resumes_concealment",
    "contextual_actions_remain_unimplemented",
)
REPORT = ROOT / ".local" / ("native-sport-spells-" + VARIANT + "-results.json")

spec = importlib.util.spec_from_file_location("_bb_sport_spell_base", ROOT / "Tools/test_native_spells.py")
spells = importlib.util.module_from_spec(spec)
spells.BRIDGE_ARGS = ARGS
spec.loader.exec_module(spells)
base, unreal, prop, xyz, vector = spells.base, spells.unreal, spells.prop, spells.xyz, spells.vector
base.TEST_NAMES, base.REPORT, base.ARGS = CASES, REPORT, ARGS
receipts_spec = importlib.util.spec_from_file_location("_bb_sport_spell_receipts", ROOT / "Tools/native_test_receipts.py")
receipts = importlib.util.module_from_spec(receipts_spec)
receipts_spec.loader.exec_module(receipts)


class SportingSpellTests(spells.NativeSpellTests):
    def write_report(self, status, reason=None):
        data = receipts.single_world_payload(self, CASES, status, reason,
                    unreal.SystemLibrary.get_engine_version() if unreal else None)
        data.update(scope="native five-spell same-world player integration", variant=VARIANT,
            not_covered=["remote replication or internet multiplayer", "physical input devices",
                         "final art quality or frame rate", "remaining eight contextual adapters",
                         "genuine rematch reset (implemented but not exercised by this suite)"],
            fixture_policy="Disposable transforms, component ticks, native movement input, public local-player "
                           "lifecycle and world time dilation only. No spell status, receipt, possession, score, "
                           "conduct or match clock is injected.")
        receipts.write_json_atomic(REPORT, data)

    def record(self, name, passed, **detail):
        if name in (spells.REGULATION_CASES[0], spells.BLOODBROOM_CASES[0]):
            name = CASES[0]
        super().record(name, passed, **detail)
        self.require(passed, name)

    def effects(self, rider):
        return {name: round(float(prop(rider, name)), 4) for name in
            ("Vitality", "StunRemaining", "ImpedimentRemaining", "ShieldRemaining", "SpellCooldownRemaining",
             "DisarmRemaining", "RevealRemaining", "ConcealRemaining", "PetrificusRemaining",
             "TransformationRemaining", "ImperioRemaining")}

    def cooldowns(self):
        yield self.wait_until(lambda: self.ready_to_cast() and self.ready_to_cast(self.guest)
            and float(prop(self.pawn, "TransformationRemaining")) <= 0
            and float(prop(self.guest, "TransformationRemaining")) <= 0, timeout=8)
        self.require(self.ready_to_cast() and self.ready_to_cast(self.guest), "Both wands must recover")

    def concealed(self, rider, observer):
        return bool(rider.is_concealed_from(observer))

    def hide(self, guest=False):
        rider = self.guest if guest else self.pawn
        yield from self.cooldowns()
        (self.guest_request if guest else self.request)(6, 20)
        yield self.wait_until(lambda: float(prop(rider, "ConcealRemaining")) > 0, timeout=.5)
        self.require(float(prop(rider, "ConcealRemaining")) > 0, "Disillusionment must actually activate")

    def aim_guest(self, yaw):
        self.guest_controller.set_control_rotation(unreal.Rotator(pitch=0, yaw=yaw, roll=0))
        import math
        def aligned():
            aim = self.guest.get_aim_direction()
            return aim.x*math.cos(math.radians(yaw))+aim.y*math.sin(math.radians(yaw)) > .999
        yield self.wait_until(aligned, timeout=1)
        self.require(aligned(), "Guest native aim must settle")

    def movement_sample(self, direction=(0, 1, 0), seconds=.35):
        movement = self.component(self.guest, unreal.CharacterMovementComponent)
        movement.stop_movement_immediately()
        self.guest.consume_movement_input_vector()
        movement.set_component_tick_enabled(True)
        start = xyz(self.guest.get_actor_location())
        def feed():
            self.guest.add_movement_input(vector(direction), 1.0, True)
        feed()
        yield self.wait(seconds, feed)
        end = xyz(self.guest.get_actor_location())
        movement.stop_movement_immediately()
        movement.set_component_tick_enabled(False)
        self.guest.consume_movement_input_vector()
        return {"start": start, "end": end, "delta": [b-a for a,b in zip(start,end)]}

    def guest_ball(self):
        # The guest occupies an ordinary scoring-eligible role from its login.
        ball = self.balls[0]
        if prop(ball, "Holder") is not None:
            holder = prop(ball, "Holder")
            self.require(holder == self.guest, "Only the fixture guest may already hold this ball")
            return ball
        target = self.guest.get_actor_location()
        self.seed_ball(0, (target.x, target.y+160, target.z+30))
        yield self.wait(.3)  # Native fixture reset has a real pickup cooldown.
        self.guest_request(0)
        yield self.wait_until(lambda: prop(ball, "Holder") == self.guest, timeout=.6)
        self.require(prop(ball, "Holder") == self.guest, "Guest must gain real possession before forced drop")
        ball.set_actor_tick_enabled(False)
        return ball

    def resolve_review(self):
        self.request(9)
        yield self.wait_until(lambda: not prop(self.match, "bConductReviewPending"), timeout=1)
        self.require(not prop(self.match, "bConductReviewPending"), "Host must serve actual F7 disposition")
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")) and int(prop(self.match, "PendingPenaltyCount")) == 0,
                             timeout=4)
        self.require(prop(self.match, "bLive") and int(prop(self.match, "PendingPenaltyCount")) == 0,
                     "Real restart must finish before continuing")
        for ball in self.balls.values():
            holder = prop(ball, "Holder")
            if holder and holder != self.pawn and holder != self.guest:
                holder.set_actor_location(vector((2500, 2200, 1800)), False, True)

    def scenarios(self):
        yield from self.prepare()
        self.require(callable(getattr(self.pawn, "is_concealed_from", None)), "New sporting spell DLL is required")
        yield from self.hide(guest=True)
        yield self.wait(.15)
        self.record(CASES[1], self.concealed(self.guest,self.pawn)
            and not self.concealed(self.guest,self.guest)
            and self.guest.development_is_hidden_from(self.pawn)
            and not self.guest.development_is_hidden_from(self.guest), effects=self.effects(self.guest))
        self.request(6,3)
        yield self.wait_until(lambda: not self.concealed(self.guest,self.pawn), timeout=.5)
        yield self.wait(.15)
        self.record(CASES[2], float(prop(self.pawn,"RevealRemaining"))>0
            and not self.concealed(self.guest,self.pawn)
            and not self.guest.development_is_hidden_from(self.pawn), observer=self.effects(self.pawn))
        self.guest.set_actor_location(vector((1800,0,1872)),False,True)
        range_hidden = self.concealed(self.guest,self.pawn)
        self.pawn.set_actor_location(vector((-1200,2800,1800)),False,True)
        self.guest.set_actor_location(vector((-1200,3400,1872)),False,True)
        wall_hidden = self.concealed(self.guest,self.pawn)
        self.record(CASES[3], range_hidden and wall_hidden, outside_range_hidden=range_hidden, occluded_hidden=wall_hidden)
        yield from self.anchor_pair()
        # Expire both utility effects naturally before reversing caster/target roles.
        yield self.wait_until(lambda: float(prop(self.pawn,"RevealRemaining"))<=0
            and float(prop(self.guest,"ConcealRemaining"))<=0, timeout=7)
        yield from self.hide()
        yield from self.cooldowns()
        health=float(prop(self.guest,"Vitality"))
        self.request(6,0)
        yield self.wait_until(lambda: float(prop(self.guest,"Vitality"))<health-3,timeout=.5)
        self.record(CASES[4], float(prop(self.pawn,"ConcealRemaining"))==0
            and float(prop(self.guest,"Vitality"))<health-3, target=self.effects(self.guest))
        yield from self.hide(guest=True)
        yield from self.cooldowns()
        health=float(prop(self.guest,"Vitality"))
        self.request(6,0)
        yield self.wait_until(lambda: float(prop(self.guest,"ConcealRemaining"))==0,timeout=.5)
        self.record(CASES[5], float(prop(self.guest,"ConcealRemaining"))==0
            and float(prop(self.guest,"Vitality"))<health-3, target=self.effects(self.guest))

        yield from self.cooldowns()
        yield from self.anchor_pair(target=(-950,0,1872))
        yield from self.aim_guest(0)  # caster lies behind target's aim
        self.request(6,5)
        yield self.wait(.2)
        self.record(CASES[6], float(prop(self.guest,"PetrificusRemaining"))==0
            and float(prop(self.guest,"StunRemaining"))==0 and self.conduct()[0]==0,
            caster=self.effects(self.pawn), target=self.effects(self.guest))
        yield from self.hide()
        yield from self.cooldowns()
        yield from self.aim_guest(180)
        self.request(6,5)
        yield self.wait(.2)
        self.record(CASES[7], float(prop(self.guest,"PetrificusRemaining"))==0
            and float(prop(self.pawn,"ConcealRemaining"))==0, target=self.effects(self.guest))
        yield from self.hide()
        yield from self.cooldowns()
        yield from self.aim_guest(0)
        self.guest_request(6,3)
        yield self.wait_until(lambda: float(prop(self.guest,"RevealRemaining"))>0, timeout=.5)
        self.request(6,5)
        yield self.wait(.2)
        self.record(CASES[8], float(prop(self.guest,"PetrificusRemaining"))==0
            and float(prop(self.guest,"RevealRemaining"))>0, target=self.effects(self.guest))
        yield self.wait_until(lambda: float(prop(self.guest,"RevealRemaining"))<=0,timeout=7)
        ball=yield from self.guest_ball()
        yield from self.hide()
        yield from self.cooldowns()
        self.request(6,5)
        yield self.wait_until(lambda: float(prop(self.guest,"PetrificusRemaining"))>0, timeout=.5)
        self.record(CASES[9], float(prop(self.guest,"PetrificusRemaining"))>1
            and float(prop(self.guest,"StunRemaining"))>1 and prop(ball,"Holder") is None
            and self.conduct()[0]==0, target=self.effects(self.guest), ball_holder=str(prop(ball,"Holder")))

        yield from self.cooldowns()
        yield from self.anchor_pair()
        self.guest_request(7)
        yield self.wait_until(lambda: float(prop(self.guest,"ShieldRemaining"))>0,timeout=.5)
        self.request(6,13)
        yield self.wait(.2)
        self.record(CASES[10], float(prop(self.guest,"TransformationRemaining"))==0
            and float(prop(self.guest,"ShieldRemaining"))>0, target=self.effects(self.guest))
        yield from self.cooldowns()
        ball=yield from self.guest_ball()
        normal=yield from self.movement_sample()
        yield from self.anchor_pair()
        self.request(6,13)
        yield self.wait_until(lambda: float(prop(self.guest,"TransformationRemaining"))>0,timeout=.5)
        yield self.wait(.12)
        proxies=[p for p in self.guest.get_components_by_class(unreal.StaticMeshComponent)
                 if p.get_name()=="SportTransformationOrb"]
        self.record(CASES[11], float(prop(self.guest,"TransformationRemaining"))>1
            and prop(ball,"Holder") is None and len(proxies)==1 and proxies[0].is_visible()
            and not proxies[0].is_collision_enabled(), target=self.effects(self.guest), proxy=[p.get_name() for p in proxies])
        locked=yield from self.movement_sample()
        self.guest_request(6,3)
        self.guest.development_set_interaction(True)
        yield self.wait(.2)
        self.record(CASES[12], max(abs(d) for d in locked["delta"])<1
            and float(prop(self.guest,"RevealRemaining"))==0 and not prop(self.guest,"bInteractHeld")
            and prop(ball,"Holder") is None, normal=normal, transformed=locked, target=self.effects(self.guest))
        self.guest.development_set_interaction(False)
        self.request(5)
        yield self.wait_until(lambda: not prop(self.match,"bLive"),timeout=.5)
        before=self.effects(self.guest)
        yield self.wait(.5)
        self.record(CASES[13], before==self.effects(self.guest) and before["TransformationRemaining"]>0,
            before=before, after=self.effects(self.guest))
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match,"bLive")),timeout=.5)
        yield self.wait_until(lambda: float(prop(self.guest,"TransformationRemaining"))==0,timeout=4)
        recovered=yield from self.movement_sample()
        self.record(CASES[14], recovered["delta"][1]>20 and not proxies[0].is_visible(), recovered=recovered)

        yield from self.cooldowns()
        yield from self.anchor_pair()
        owner=self.guest.get_controller()
        slot=int(prop(self.guest,"RosterIndex"))
        self.guest_request(7)
        yield self.wait_until(lambda: float(prop(self.guest,"ShieldRemaining"))>0,timeout=.5)
        self.request(6,28)
        yield self.wait_until(lambda: float(prop(self.guest,"ImperioRemaining"))>0,timeout=.5)
        review=bool(prop(self.match,"bConductReviewPending"))
        self.record(CASES[15], self.guest.get_controller()==owner and int(prop(self.guest,"RosterIndex"))==slot
            and float(prop(self.guest,"ImperioRemaining"))>2
            and (not review if VARIANT=="bloodbroom" else review and self.conduct()[3]==1),
            target=self.effects(self.guest), conduct=self.conduct(), owner=owner.get_path_name())
        if review:
            before=self.effects(self.guest)
            yield self.wait(.3)
            self.require(before==self.effects(self.guest), "Applied Imperio must freeze during conduct review")
            yield from self.resolve_review()
        reverse=yield from self.movement_sample()
        vertical=yield from self.movement_sample((0,0,1))
        self.record(CASES[16], reverse["delta"][1]<-20 and vertical["delta"][2]>20
            and self.guest.get_controller()==owner, horizontal=reverse, vertical=vertical)
        yield self.wait_until(lambda: float(prop(self.guest,"ImperioRemaining"))==0,timeout=4)
        normal_again=yield from self.movement_sample()
        self.record(CASES[17], normal_again["delta"][1]>20 and self.guest.get_controller()==owner
            and int(prop(self.guest,"RosterIndex"))==slot, recovered=normal_again)

        yield from self.cooldowns()
        self.request(5)
        yield self.wait_until(lambda: not prop(self.match,"bLive"),timeout=.5)
        before=self.effects(self.pawn)
        self.request(6,3)
        yield self.wait(.2)
        self.record(CASES[18], before==self.effects(self.pawn), before=before, after=self.effects(self.pawn))
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match,"bLive")),timeout=.5)
        # Advance real native ticks to just before the period boundary, then
        # restore the slower fixture rate before casting an unexpired effect.
        unreal.GameplayStatics.set_global_time_dilation(self.world,20)
        while float(prop(self.match,"SecondsLeft"))>12:
            remaining=float(prop(self.match,"SecondsLeft"))
            yield self.wait_until(lambda: float(prop(self.match,"SecondsLeft"))<=12,
                                 timeout=min(90,remaining-12))
        unreal.GameplayStatics.set_global_time_dilation(self.world,.5)
        yield self.wait_until(lambda: float(prop(self.match,"SecondsLeft"))<=3,timeout=14)
        self.require(prop(self.match,"bLive") and float(prop(self.match,"SecondsLeft"))>0,
                     "Clock fixture must stop before the actual quarter boundary")
        self.request(6,20)
        yield self.wait_until(lambda: float(prop(self.pawn,"ConcealRemaining"))>0,timeout=.5)
        yield self.wait_until(lambda: str(prop(self.match,"Status"))=="QUARTER BREAK",timeout=4)
        before=float(prop(self.pawn,"ConcealRemaining"))
        quarter=int(prop(self.match,"Quarter"))
        self.require(before>0, "Concealment must still be unexpired at the real quarter break")
        yield self.wait(.4)
        frozen=float(prop(self.pawn,"ConcealRemaining"))
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match,"bLive")),timeout=1)
        yield self.wait(.15)
        resumed=float(prop(self.pawn,"ConcealRemaining"))
        self.record(CASES[19], bool(prop(self.match,"bLive")) and before>0 and frozen==before
            and 0<resumed<before,
            unexpired_at_break=before, frozen_at_break=frozen, resumed=resumed,
            quarter_at_break=quarter, after=self.effects(self.pawn))
        self.isolate()
        yield from self.anchor_pair()
        yield from self.drain_feedback()
        self.request(6,4)
        yield self.wait_until(lambda: bool(str(prop(self.pawn,"SpellFeedback"))),timeout=.5)
        self.record(CASES[20], float(prop(self.pawn,"SpellCooldownRemaining"))==0
            and "pending" in str(prop(self.pawn,"SpellFeedback")).lower(), feedback=str(prop(self.pawn,"SpellFeedback")))


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status":"not_run", "variant":VARIANT, "cases":list(CASES), "total_planned":len(CASES)}
    test=SportingSpellTests()
    try:
        started=test.begin()
    except Exception:
        test.finish("error",traceback.format_exc())
        started=False
    if unreal and started:
        unreal._basketbroom_native_test=test
    return {"status":"started" if started else test.final_status, "variant":VARIANT,
            "report":str(REPORT), "planned_cases":len(CASES)}


if __name__=="__main__":
    RESULT=main()
    if unreal is None:
        print(json.dumps(RESULT,indent=2))

"""five sporting spell adapters through real native player input, in both modes.

bridge arguments: {"variant":"regulation"} or {"variant":"bloodbroom"}.
no spell timer, hit receipt, possession, score, conduct or match clock is written.
Transforms/ordinary movement inputs/PIE time dilation arrange disposable fixtures.
--list only describes the plan. it does not execute or certify gameplay.
"""

import importlib.util as _arena_importlib
from pathlib import path as _arenapath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)
import importlib.util
import json
from pathlib import path
import sys
import traceback

root = Path(__file__).resolve().parents[1]
args = {"max_wall_seconds": 420, **globals().get("BRIDGE_ARGS", {})}
variant = str(ARGS.get("variant", "regulation")).lower()
cases = (
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
    "contextual_actions_require_owned_workshop_target",
)
report = root / ".local" / ("native-sport-spells-" + variant + "-results.json")

spec = importlib.util.spec_from_file_location("_bb_sport_spell_base", root / "Tools/test_native_spells.py")
spells = importlib.util.module_from_spec(spec)
spells.BRIDGE_ARGS = args
spec.loader.exec_module(spells)
base, unreal, prop, xyz, vector = spells.base, spells.unreal, spells.prop, spells.xyz, spells.vector
base.TEST_NAMES, base.REPORT, base.ARGS = cases, report, args
receipts_spec = importlib.util.spec_from_file_location("_bb_sport_spell_receipts", root / "Tools/native_test_receipts.py")
receipts = importlib.util.module_from_spec(receipts_spec)
receipts_spec.loader.exec_module(receipts)


class SportingSpellTests(spells.NativeSpellTests):
    def write_report(self, status, reason=None):
        data = receipts.single_world_payload(self, cases, status, reason,
                    unreal.SystemLibrary.get_engine_version() if unreal else none)
        data.update(scope="native five-spell same-world player integration", variant=variant,
            not_covered=["remote replication or internet multiplayer", "physical input devices",
                         "final art quality or frame rate", "separate eight contextual workshop/resource adapter suite",
                         "genuine rematch reset (implemented but not exercised by this suite)"],
            fixture_policy="disposable transforms, component ticks, native movement input, public local-player "
                           "lifecycle and world time dilation only. no spell status, receipt, possession, score, "
                           "conduct or match clock is injected.")
        receipts.write_json_atomic(REPORT, data)

    def record(self, name, passed, **detail):
        if name in (spells.REGULATION_CASES[0], spells.BLOODBROOM_CASES[0]):
            name = cases[0]
        super().record(name, passed, **detail)
        self.require(passed, name)

    def effects(self, rider):
        return {name: round(float(prop(rider, name)), 4) for name in
            ("vitality", "stunremaining", "impedimentremaining", "shieldremaining", "spellcooldownremaining",
             "disarmremaining", "revealremaining", "concealremaining", "petrificusremaining",
             "transformationremaining", "imperioremaining")}

    def cooldowns(self):
        yield self.wait_until(lambda: self.ready_to_cast() and self.ready_to_cast(self.guest)
            and float(prop(self.pawn, "transformationremaining")) <= 0
            and float(prop(self.guest, "transformationremaining")) <= 0, timeout=8)
        self.require(self.ready_to_cast() and self.ready_to_cast(self.guest), "both wands must recover")

    def concealed(self, rider, observer):
        return bool(rider.is_concealed_from(observer))

    def hide(self, guest=False):
        rider = self.guest if guest else self.pawn
        yield from self.cooldowns()
        (self.guest_request if guest else self.request)(6, 20)
        yield self.wait_until(lambda: float(prop(rider, "concealremaining")) > 0, timeout=.5)
        self.require(float(prop(rider, "concealremaining")) > 0, "disillusionment must actually activate")

    def aim_guest(self, yaw):
        self.guest_controller.set_control_rotation(unreal.Rotator(pitch=0, yaw=yaw, roll=0))
        import math
        def aligned():
            aim = self.guest.get_aim_direction()
            return aim.x*math.cos(math.radians(yaw))+aim.y*math.sin(math.radians(yaw)) > .999
        yield self.wait_until(aligned, timeout=1)
        self.require(aligned(), "guest native aim must settle")

    def movement_sample(self, direction=(0, 1, 0), seconds=.35):
        movement = self.component(self.guest, unreal.CharacterMovementComponent)
        movement.stop_movement_immediately()
        self.guest.consume_movement_input_vector()
        movement.set_component_tick_enabled(True)
        start = xyz(self.guest.get_actor_location())
        def feed():
            self.guest.add_movement_input(vector(direction), 1.0, true)
        feed()
        yield self.wait(seconds, feed)
        end = xyz(self.guest.get_actor_location())
        movement.stop_movement_immediately()
        movement.set_component_tick_enabled(False)
        self.guest.consume_movement_input_vector()
        return {"start": start, "end": end, "delta": [b-a for a,b in zip(start,end)]}

    def guest_ball(self):
        # the guest occupies an ordinary scoring-eligible role from its login.
        ball = self.balls[0]
        if prop(ball, "holder") is not None:
            holder = prop(ball, "holder")
            self.require(holder == self.guest, "only the fixture guest may already hold this ball")
            return ball
        target = self.guest.get_actor_location()
        self.seed_ball(0, (target.x, target.y+160, target.z+30))
        yield self.wait(.3)  # native fixture reset has a real pickup cooldown.
        self.guest_request(0)
        yield self.wait_until(lambda: prop(ball, "holder") == self.guest, timeout=.6)
        self.require(prop(ball, "holder") == self.guest, "guest must gain real possession before forced drop")
        ball.set_actor_tick_enabled(False)
        return ball

    def resolve_review(self):
        self.request(9)
        yield self.wait_until(lambda: not prop(self.match, "bconductreviewpending"), timeout=1)
        self.require(not prop(self.match, "bconductreviewpending"), "host must serve actual f7 disposition")
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "blive")) and int(prop(self.match, "pendingpenaltycount")) == 0,
                             timeout=4)
        self.require(prop(self.match, "blive") and int(prop(self.match, "pendingpenaltycount")) == 0,
                     "real restart must finish before continuing")
        for ball in self.balls.values():
            holder = prop(ball, "holder")
            if holder and holder != self.pawn and holder != self.guest:
                holder.set_actor_location(vector((2500, 2200, 1800)), false, true)

    def scenarios(self):
        yield from self.prepare()
        self.require(callable(getattr(self.pawn, "is_concealed_from", none)), "new sporting spell dll is required")
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
        self.pawn.set_actor_location(vector((-1200,dimensions.HALF_WIDTH-400.4,1800)),False,True)
        self.guest.set_actor_location(vector((-1200,dimensions.HALF_WIDTH+199.6,1872)),False,True)
        wall_hidden = self.concealed(self.guest,self.pawn)
        self.record(CASES[3], range_hidden and wall_hidden, outside_range_hidden=range_hidden, occluded_hidden=wall_hidden)
        yield from self.anchor_pair()
        # expire both utility effects naturally before reversing caster/target roles.
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
            and float(prop(self.guest,"StunRemaining"))>1 and prop(ball,"holder") is none
            and self.conduct()[0]==0, target=self.effects(self.guest), ball_holder=str(prop(ball,"holder")))

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
            and prop(ball,"holder") is none and len(proxies)==1 and proxies[0].is_visible()
            and not proxies[0].is_collision_enabled(), target=self.effects(self.guest), proxy=[p.get_name() for p in proxies])
        locked=yield from self.movement_sample()
        self.guest_request(6,3)
        self.guest.development_set_interaction(True)
        yield self.wait(.2)
        self.record(CASES[12], max(abs(d) for d in locked["delta"])<1
            and float(prop(self.guest,"RevealRemaining"))==0 and not prop(self.guest,"bInteractHeld")
            and prop(ball,"holder") is none, normal=normal, transformed=locked, target=self.effects(self.guest))
        self.guest.development_set_interaction(False)
        self.request(5)
        yield self.wait_until(lambda: not prop(self.match,"bLive"),timeout=.5)
        before=self.effects(self.guest)
        yield self.wait(.5)
        self.record(CASES[13], before==self.effects(self.guest) and before["transformationremaining"]>0,
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
            and (not review if variant=="bloodbroom" else review and self.conduct()[3]==1),
            target=self.effects(self.guest), conduct=self.conduct(), owner=owner.get_path_name())
        if review:
            before=self.effects(self.guest)
            yield self.wait(.3)
            self.require(before==self.effects(self.guest), "applied imperio must freeze during conduct review")
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
        # advance real native ticks to just before the period boundary, then
        # restore the slower fixture rate before casting an unexpired effect.
        unreal.GameplayStatics.set_global_time_dilation(self.world,20)
        while float(prop(self.match,"SecondsLeft"))>12:
            remaining=float(prop(self.match,"SecondsLeft"))
            yield self.wait_until(lambda: float(prop(self.match,"SecondsLeft"))<=12,
                                 timeout=min(90,remaining-12))
        unreal.GameplayStatics.set_global_time_dilation(self.world,.5)
        yield self.wait_until(lambda: float(prop(self.match,"SecondsLeft"))<=3,timeout=14)
        self.require(prop(self.match,"bLive") and float(prop(self.match,"SecondsLeft"))>0,
                     "clock fixture must stop before the actual quarter boundary")
        self.request(6,20)
        yield self.wait_until(lambda: float(prop(self.pawn,"ConcealRemaining"))>0,timeout=.5)
        yield self.wait_until(lambda: str(prop(self.match,"Status"))=="QUARTER break",timeout=4)
        before=float(prop(self.pawn,"ConcealRemaining"))
        quarter=int(prop(self.match,"Quarter"))
        self.require(before>0, "concealment must still be unexpired at the real quarter break")
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
            and "own" in str(prop(self.pawn,"SpellFeedback")).lower(), feedback=str(prop(self.pawn,"SpellFeedback")))


def main():
    if unreal is none and "--list" in sys.argv:
        return {"status":"not_run", "variant":VARIANT, "cases":list(CASES), "total_planned":len(CASES)}
    test=sportingspelltests()
    try:
        started=test.begin()
    except Exception:
        test.finish("error",traceback.format_exc())
        started=false
    if unreal and started:
        unreal._basketbroom_native_test=test
    return {"status":"started" if started else test.final_status, "variant":VARIANT,
            "report":str(REPORT), "planned_cases":len(CASES)}


if __name__=="__main__":
    result=main()
    if unreal is None:
        print(json.dumps(RESULT,indent=2))

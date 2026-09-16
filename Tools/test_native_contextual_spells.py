"""Eight original sporting spell adapters through real native player actions.

Run separately for regulation and bloodbroom via the editor bridge. Disposable
rider/ball transforms and component ticks arrange fixtures, never workshop,
meter, spell, conduct, score or rule state. Owns and ends its PIE session.
--list is a plan only, never gameplay proof.
"""
import importlib.util
import json
import math
from pathlib import Path
import sys
import traceback
ROOT=Path(__file__).resolve().parents[1]
ARGS={"max_wall_seconds":540,**globals().get("BRIDGE_ARGS",{})}
VARIANT=str(ARGS.get("variant","regulation")).lower()
CASES=(
    "two_actual_opposing_humans_in_selected_variant",
    "one_unique_owned_workshop_each_with_zero_charge",
    "locked_bay_rejects_conjuring_without_spending_cooldown",
    "alohomora_unlocks_owned_world_locker",
    "other_riders_workshop_cannot_be_unlocked_or_edited",
    "conjuring_creates_one_nonblocking_bounded_construct",
    "altering_changes_mesh_but_preserves_size_and_permissions",
    "wingardium_moves_in_live_time_and_freezes_at_stoppage",
    "actual_cast_damage_then_reparo_restores_construct_without_charge",
    "evanesco_removes_only_owned_construct",
    "contextual_spells_cannot_change_official_balls_or_create_arbitrary_objects",
    "miss_and_protego_block_do_not_earn_ancient_magic",
    "legal_applied_enemy_hits_earn_capped_ancient_magic",
    "ancient_magic_spends_meter_even_when_protego_blocks",
    "ancient_magic_pulse_applies_real_damage_without_refunding_itself",
    "throw_requires_intact_owned_object_and_valid_target_before_spending",
    "real_swept_throw_freezes_at_stoppage_then_applies_selected_torso_hit",
    "protego_blocks_real_construct_impact_after_charge_is_spent",
    "physical_throw_head_impact_applies_before_mode_specific_review",
    "departing_player_destroys_only_its_owned_workshop",
)
REPORT=ROOT/'.local'/('native-contextual-spells-'+VARIANT+'-results.json')
spec=importlib.util.spec_from_file_location('_bb_context_spells_base',ROOT/'Tools/test_native_spells.py')
spells=importlib.util.module_from_spec(spec);spells.BRIDGE_ARGS=ARGS;spec.loader.exec_module(spells)
base,unreal,prop,xyz,vector=spells.base,spells.unreal,spells.prop,spells.xyz,spells.vector
base.TEST_NAMES,base.REPORT,base.ARGS=CASES,REPORT,ARGS
rs=importlib.util.spec_from_file_location('_bb_context_receipts',ROOT/'Tools/native_test_receipts.py')
receipts=importlib.util.module_from_spec(rs);rs.loader.exec_module(receipts)


class ContextualSpellTests(spells.NativeSpellTests):
    def write_report(self,status,reason=None):
        data=receipts.single_world_payload(self,CASES,status,reason,unreal.SystemLibrary.get_engine_version() if unreal else None)
        data.update(scope='eight native sporting workshop/resource spell adapters',variant=VARIANT,
            not_covered=['internet/remote replication','physical input transports','rendered visual quality',
                         'Hogwarts Legacy spell or match integration','genuine rematch reset'],
            fixture_policy='Only ordinary queued player actions, disposable rider/ball transforms, component ticks, '
                           'public local-player lifecycle and world time dilation; no workshop, resource, spell, '
                           'conduct, score or clock state is injected.')
        receipts.write_json_atomic(REPORT,data)

    def record(self,name,passed,**detail):
        if name in (spells.REGULATION_CASES[0],spells.BLOODBROOM_CASES[0]):name=CASES[0]
        super().record(name,passed,**detail);self.require(passed,name)

    def state(self,obj=None):
        obj=obj or self.workshop
        return {name:prop(obj,name) for name in ('bUnlocked','bConjured','Integrity','Form','AncientMagicCharge','bInFlight')}|{
            'position':xyz(prop(obj,'ConstructPosition'))}

    def charge(self):return int(self.match.get_ancient_magic_charge(self.pawn))

    def cooldown(self):
        yield self.wait_until(lambda:self.ready_to_cast() and self.ready_to_cast(self.guest),timeout=10)
        self.require(self.ready_to_cast() and self.ready_to_cast(self.guest),'Wands must genuinely recover')

    def aim_object(self,obj=None,construct=False):
        obj=obj or self.workshop
        point=xyz(prop(obj,'ConstructPosition') if construct else obj.get_actor_location())
        yield from self.anchor_pair(caster=(point[0]-500,point[1],point[2]-72),target=(2000,0,2100))

    def cast_object(self,index,construct=False,predicate=None):
        yield from self.cooldown();yield from self.aim_object(construct=construct)
        self.request(6,index)
        yield self.wait_until(predicate or (lambda:float(prop(self.pawn,'SpellCooldownRemaining'))>0),timeout=1.5)

    def earn(self,wanted):
        rows=[]
        for _ in range(6):
            if self.charge()>=wanted:break
            yield from self.cooldown();yield from self.anchor_pair()
            yield self.wait_until(lambda:float(prop(self.guest,'Vitality'))>22,timeout=8)
            self.require(float(prop(self.guest,'Vitality'))>22,'Meter fixture needs a recovered target')
            before=self.charge();health=float(prop(self.guest,'Vitality'))
            self.request(6,0)
            yield self.wait_until(lambda:self.charge()>before,timeout=.8)
            rows.append({'before':before,'after':self.charge(),'health_before':health,'health_after':float(prop(self.guest,'Vitality'))})
            self.require(self.charge()==min(100,before+20) and float(prop(self.guest,'Vitality'))<health
                         and not prop(self.match,'bConductReviewPending'),'Resource must follow actual legal damaging enemy contact')
        self.require(self.charge()>=wanted,'Required resource must be genuinely earned')
        return rows

    def throw_pair(self,head=False):
        point=xyz(prop(self.workshop,'ConstructPosition'))
        # The source object and the crosshair ray both meet the selected torso.
        # For the deliberate head test aim 80cm above the victim capsule centre.
        yield from self.anchor_pair(caster=(point[0]-300,point[1],point[2]-72),
            target=(point[0]+1800,point[1],point[2]-(80 if head else 0)))

    def ensure_construct(self):
        if not prop(self.workshop,'bConjured'):
            yield from self.cast_object(23,predicate=lambda:bool(prop(self.workshop,'bConjured')))
        if float(prop(self.workshop,'Integrity'))<100:
            yield from self.cast_object(22,True,lambda:float(prop(self.workshop,'Integrity'))==100)
        self.require(prop(self.workshop,'bConjured') and float(prop(self.workshop,'Integrity'))==100,'Real conjuring/repair must create an intact object')

    def scenarios(self):
        yield from self.prepare()
        self.require(callable(getattr(self.match,'get_spell_workshop',None)),'New contextual spell DLL required')
        yield self.wait_until(lambda:self.match.get_spell_workshop(self.pawn) is not None
            and self.match.get_spell_workshop(self.guest) is not None,timeout=2)
        self.workshop=self.match.get_spell_workshop(self.pawn);self.other_workshop=self.match.get_spell_workshop(self.guest)
        self.workshop_class=unreal.load_class(None,'/Script/BasketbroomRuntime.BBSpellArenaObject')
        self.require(self.workshop_class and self.workshop and self.other_workshop,'Both admitted humans need genuine replicated workshops')
        self.record(CASES[1],self.workshop!=self.other_workshop
            and prop(self.workshop,'WorkshopOwner')==self.pawn and prop(self.other_workshop,'WorkshopOwner')==self.guest
            and self.charge()==0 and len(unreal.GameplayStatics.get_all_actors_of_class(self.world,self.workshop_class))==2,
            own=self.state(),other=self.state(self.other_workshop))
        yield from self.aim_object();before=self.state();self.request(6,23);yield self.wait(.2)
        self.record(CASES[2],self.state()==before and float(prop(self.pawn,'SpellCooldownRemaining'))==0,before=before,after=self.state())
        yield from self.cast_object(4,predicate=lambda:bool(prop(self.workshop,'bUnlocked')))
        self.record(CASES[3],prop(self.workshop,'bUnlocked') and not prop(self.workshop,'bConjured'),state=self.state())
        yield from self.cooldown();yield from self.aim_object(self.other_workshop)
        before=self.state(self.other_workshop);self.request(6,4);yield self.wait(.2)
        self.record(CASES[4],self.state(self.other_workshop)==before and float(prop(self.pawn,'SpellCooldownRemaining'))==0,
            before=before,after=self.state(self.other_workshop))
        yield from self.ensure_construct()
        part=prop(self.workshop,'Construct')
        response=str(part.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN))
        before=self.state();yield from self.cast_object(23,predicate=lambda:False)
        self.record(CASES[5],prop(self.workshop,'bConjured') and self.state()==before and 'IGNORE' in response.upper()
            and len(unreal.GameplayStatics.get_all_actors_of_class(self.world,self.workshop_class))==2,
            state=self.state(),pawn_collision=response,construct_scale=xyz(part.get_world_scale()))
        mesh=prop(part,'StaticMesh');scale=xyz(part.get_world_scale());position=xyz(prop(self.workshop,'ConstructPosition'))
        yield from self.cast_object(24,True,lambda:int(prop(self.workshop,'Form'))==1)
        self.record(CASES[6],prop(part,'StaticMesh')!=mesh and xyz(part.get_world_scale())==scale
            and xyz(prop(self.workshop,'ConstructPosition'))==position and 'IGNORE' in str(part.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN)).upper(),
            old_mesh=mesh.get_path_name(),new_mesh=prop(part,'StaticMesh').get_path_name(),scale=scale,state=self.state())
        yield from self.cast_object(21,True,lambda:xyz(prop(self.workshop,'ConstructPosition'))[2]>position[2]+5)
        moving=xyz(prop(self.workshop,'ConstructPosition'));self.request(5)
        yield self.wait_until(lambda:not prop(self.match,'bLive'),timeout=.5)
        frozen=self.state();yield self.wait(.3);self.request(6,25);yield self.wait(.2)
        still=self.state();self.request(4);yield self.wait_until(lambda:prop(self.match,'bLive'),timeout=.5)
        yield self.wait_until(lambda:xyz(prop(self.workshop,'ConstructPosition'))[2]>=position[2]+159.99,timeout=2)
        self.record(CASES[7],position[2]<moving[2]<position[2]+160 and frozen==still
            and abs(xyz(prop(self.workshop,'ConstructPosition'))[2]-position[2]-160)<.1,
            original=position,intermediate=moving,frozen=frozen,after=self.state())
        yield from self.cast_object(0,True,lambda:float(prop(self.workshop,'Integrity'))<100)
        damaged=self.state();yield from self.cast_object(22,True,lambda:float(prop(self.workshop,'Integrity'))==100)
        self.record(CASES[8],0<damaged['Integrity']<100 and float(prop(self.workshop,'Integrity'))==100 and self.charge()==0,
            damaged=damaged,repaired=self.state())
        yield from self.cast_object(25,True,lambda:not prop(self.workshop,'bConjured'))
        self.record(CASES[9],not prop(self.workshop,'bConjured') and prop(self.workshop,'bUnlocked')
            and not prop(self.other_workshop,'bUnlocked') and len(self.balls)==7,state=self.state())
        yield from self.cooldown();yield from self.anchor_pair(caster=(-1200,0,1800),target=(2000,2200,2000))
        ball=self.balls[0];ball.set_actor_location(vector((-400,0,1872)),False,True)
        identities=[b.get_path_name() for b in self.balls.values()];location=xyz(ball.get_actor_location());denied=[]
        for index in (4,21,22,23,24,25):
            self.request(6,index);yield self.wait(.15)
            denied.append({'spell':index,'cooldown':float(prop(self.pawn,'SpellCooldownRemaining')),'state':self.state()})
        self.record(CASES[10],all(row['cooldown']==0 and not row['state']['bConjured'] for row in denied)
            and xyz(ball.get_actor_location())==location and [b.get_path_name() for b in self.balls.values()]==identities,
            attempts=denied,official_ball_identity=identities,ball_location=location)
        ball.set_actor_location(vector((2000,2200,1700)),False,True)
        yield from self.anchor_pair(target=(-400,800,1872));self.request(6,0);yield self.wait(.2)
        missed=self.charge();yield from self.cooldown();yield from self.anchor_pair()
        self.guest_request(7);yield self.wait_until(lambda:float(prop(self.guest,'ShieldRemaining'))>0,timeout=.5)
        before=float(prop(self.guest,'Vitality'));self.request(6,0);yield self.wait(.2)
        self.record(CASES[11],missed==0 and self.charge()==0 and float(prop(self.guest,'Vitality'))>=before,
            miss_charge=missed,blocked_charge=self.charge(),health_before=before,health_after=float(prop(self.guest,'Vitality')))
        hits=yield from self.earn(100)
        yield from self.cooldown();yield from self.anchor_pair();self.request(6,0);yield self.wait(.2)
        self.record(CASES[12],self.charge()==100 and len(hits)==5,hits=hits,capped_charge=self.charge())
        yield from self.cooldown();yield from self.anchor_pair()
        self.guest_request(7);yield self.wait_until(lambda:float(prop(self.guest,'ShieldRemaining'))>0,timeout=.5)
        before=float(prop(self.guest,'Vitality'));self.request(6,29);yield self.wait_until(lambda:self.charge()==0,timeout=.5)
        self.record(CASES[13],self.charge()==0 and float(prop(self.guest,'Vitality'))>=before and not prop(self.match,'bConductReviewPending'),
            health_before=before,health_after=float(prop(self.guest,'Vitality')),charge=self.charge())
        yield from self.earn(100);yield from self.cooldown();yield from self.anchor_pair()
        yield self.wait_until(lambda:float(prop(self.guest,'Vitality'))>65,timeout=20)
        before=float(prop(self.guest,'Vitality'));self.request(6,29);yield self.wait_until(lambda:self.charge()==0,timeout=.5)
        self.record(CASES[14],self.charge()==0 and float(prop(self.guest,'Vitality'))<before-50 and not prop(self.match,'bConductReviewPending'),
            health_before=before,health_after=float(prop(self.guest,'Vitality')),charge=self.charge())
        yield from self.earn(40);yield from self.cooldown();before=self.charge();self.request(6,30);yield self.wait(.2)
        absent=self.charge()==before and not prop(self.workshop,'bConjured') and float(prop(self.pawn,'SpellCooldownRemaining'))==0
        yield from self.ensure_construct();yield from self.cooldown();yield from self.throw_pair()
        self.guest.set_actor_location(vector((2000,0,1900)),False,True)
        self.request(6,30);yield self.wait(.2)
        self.record(CASES[15],absent and self.charge()==before and not prop(self.workshop,'bInFlight'),
            charge_before=before,charge_after=self.charge(),state=self.state())
        yield from self.throw_pair()
        yield self.wait_until(lambda:float(prop(self.guest,'Vitality'))>45,timeout=12)
        self.require(float(prop(self.guest,'Vitality'))>45,'Physical impact measurement needs a recovered target, not knockout recovery')
        before=self.charge();health=float(prop(self.guest,'Vitality'));start=xyz(prop(self.workshop,'ConstructPosition'))
        self.request(6,30);yield self.wait_until(lambda:bool(prop(self.workshop,'bInFlight')),timeout=.5)
        self.require(prop(self.workshop,'bInFlight'),'A real throw must be in flight before stopping it')
        intermediate=xyz(prop(self.workshop,'ConstructPosition'));self.request(5)
        yield self.wait_until(lambda:not prop(self.match,'bLive'),timeout=.5)
        frozen=self.state();yield self.wait(.35);still=self.state();self.request(4)
        yield self.wait_until(lambda:prop(self.match,'bLive'),timeout=.5)
        yield self.wait_until(lambda:not prop(self.workshop,'bInFlight'),timeout=2)
        self.record(CASES[16],start!=intermediate and frozen==still and self.charge()==before-25
            and float(prop(self.workshop,'Integrity'))==0 and float(prop(self.guest,'Vitality'))<health-25
            and not prop(self.match,'bConductReviewPending'),start=start,intermediate=intermediate,frozen=frozen,
            health_before=health,health_after=float(prop(self.guest,'Vitality')),after=self.state())
        yield from self.earn(40);yield from self.ensure_construct();yield from self.cooldown();yield from self.throw_pair()
        before=self.charge();health=float(prop(self.guest,'Vitality'));self.guest_request(7)
        yield self.wait_until(lambda:float(prop(self.guest,'ShieldRemaining'))>.9,timeout=.5)
        self.require(float(prop(self.guest,'ShieldRemaining'))>0,'Actual Protego must be active')
        self.request(6,30);yield self.wait_until(lambda:bool(prop(self.workshop,'bInFlight')),timeout=.5)
        yield self.wait_until(lambda:not prop(self.workshop,'bInFlight'),timeout=2)
        self.record(CASES[17],self.charge()==before-25 and float(prop(self.workshop,'Integrity'))==0
            and float(prop(self.guest,'Vitality'))>=health and not prop(self.match,'bConductReviewPending'),
            health_before=health,health_after=float(prop(self.guest,'Vitality')),after=self.state())
        yield from self.earn(40);yield from self.ensure_construct();yield from self.cooldown();yield from self.throw_pair(head=True)
        yield self.wait_until(lambda:float(prop(self.guest,'Vitality'))>45,timeout=12)
        health=float(prop(self.guest,'Vitality'));prior=self.conduct();self.request(6,30)
        yield self.wait_until(lambda:bool(prop(self.workshop,'bInFlight')),timeout=.5)
        yield self.wait_until(lambda:not prop(self.workshop,'bInFlight'),timeout=2)
        after=self.conduct();blood=VARIANT=='bloodbroom'
        self.record(CASES[18],float(prop(self.guest,'Vitality'))<health-25 and (after==prior if blood else
            after[0]==prior[0]+1 and after[1]==1 and after[3]==2 and not prop(self.match,'bLive')),
            health_before=health,health_after=float(prop(self.guest,'Vitality')),conduct_before=prior,conduct_after=after,variant=VARIANT)
        # In regulation the hit intentionally leaves a pending conduct review.
        # Remove the guest only after resuming legitimately so the live lifecycle
        # tick can prove removal without manipulating the workshop directly.
        if not blood:
            self.request(9);yield self.wait_until(lambda:not prop(self.match,'bConductReviewPending'),timeout=1)
            self.request(4);yield self.wait_until(lambda:prop(self.match,'bLive'),timeout=4)
            self.require(prop(self.match,'bLive'),'Host disposition and real restart must resume play')
        guest=self.guest_controller
        guest.set_actor_tick_enabled(True)
        self.controller_ticks=[row for row in self.controller_ticks if row[0]!=guest]
        unreal.GameplayStatics.remove_player(guest,True);self.extra_controllers.remove(guest)
        yield self.wait_until(lambda:len(unreal.GameplayStatics.get_all_actors_of_class(self.world,self.workshop_class))==1,timeout=2)
        objects=list(unreal.GameplayStatics.get_all_actors_of_class(self.world,self.workshop_class))
        self.record(CASES[19],objects==[self.workshop] and self.match.get_spell_workshop(self.pawn)==self.workshop,
            remaining=[obj.get_path_name() for obj in objects])


def main():
    if unreal is None and '--list' in sys.argv:
        return {'status':'not_run','variant':VARIANT,'cases':list(CASES),'total_planned':len(CASES)}
    test=ContextualSpellTests()
    try:started=test.begin()
    except Exception:test.finish('error',traceback.format_exc());started=False
    if unreal and started:unreal._basketbroom_native_test=test
    return {'status':'started' if started else test.final_status,'report':str(REPORT),'planned_cases':len(CASES)}

if __name__=='__main__':
    RESULT=main()
    if unreal is None:print(json.dumps(RESULT,indent=2))

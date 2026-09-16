"""Sprint 3 spell replication through an owned client in two real PIE worlds.

Use editor_bridge.py with BB_Regulation open and PIE stopped. The network
runner's settings_already_configured/settings_source fallback is supported.
No effect, ownership, hit receipt, possession or conduct state is injected.
Transforms/component ticks arrange fixtures; movement evidence thereafter uses
only owning-client AddMovementInput and actual CharacterMovement saved moves.
"""
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'.local/native-sport-spell-network-results.json'
ARGS={"max_wall_seconds":300, **globals().get("BRIDGE_ARGS", {})}
TESTS=(
    "two_connected_worlds_and_real_client_roster_rpc",
    "client_disillusionment_replicates_and_hides_from_host_view",
    "host_revelio_replicates_and_reveals_concealed_client",
    "client_revelio_status_reaches_authority_and_owner",
    "transformation_replicates_real_drop_orb_and_action_lock",
    "transformed_client_movement_is_locked_on_authority_and_owner",
    "official_stoppage_freezes_replicated_new_status_timers",
    "transformation_recovery_restores_real_client_movement",
    "imperio_applies_before_review_without_transferring_client_ownership",
    "remote_client_cannot_serve_f6_free_shot_disposition",
    "imperio_reverses_client_horizontal_flight_preserves_vertical_and_recovers",
    "managed_play_settings_restored_and_pie_ended",
)
spec=importlib.util.spec_from_file_location('_bb_sport_spell_network_base', ROOT/'Tools/test_native_spell_network.py')
spells=importlib.util.module_from_spec(spec)
spells.BRIDGE_ARGS=ARGS
spec.loader.exec_module(spells)
base,unreal,prop,vec=spells.base,spells.unreal,spells.prop,spells.vec
base.TESTS,base.REPORT,base.ARGS=TESTS,REPORT,ARGS


def xyz(point):
    return [float(point.x),float(point.y),float(point.z)]


class SportSpellNetworkTests(spells.SpellNetworkTests):
    def write(self,status):
        rows=[{"name":name,**self.results.get(name,{"status":"not_run"})} for name in TESTS]
        base.write_json_atomic(REPORT,{
            "status":status,"phase":self.phase,"scope":"four sporting adapters (Disillusionment, Revelio, Transformation, Imperio): real ownership RPC and replication across two local PIE worlds",
            "elapsed_wall_seconds":round(time.monotonic()-self.started,3),
            "passed":sum(row['status']=='passed' for row in rows),"failed":sum(row['status']=='failed' for row in rows),
            "not_run":sum(row['status']=='not_run' for row in rows),"tests":rows,"provenance":self.provenance,
            "events":self.events,"reason":self.reason,"settings_restored":self.settings_restored,
            "time_dilation_restored":self.dilations_restored,
            "external_restore_required":base.net_mode_restore_actions(self.provenance),
            "not_covered":["separate processes/remote machines, latency, loss or reconnect","human physical controller input",
                "Petrificus Totalus network cast, status, ownership and double-tap behavior","final art or adverse-network movement reconciliation",
                "Hogwarts Legacy multiplayer"],
            "fixture_policy":"Disposable transforms, component ticks, public world time dilation and ordinary player inputs only. "
                "No gameplay status, custody, hit receipt, rule result or network ownership writes."})

    def record(self,name,passed,**detail):
        super().record(name,passed,**detail)
        self.require(passed,name)

    def ready(self,side):
        return super().ready(side) and max(self.values(side,'TransformationRemaining'))<=.01

    def cooldowns(self):
        yield self.wait(7,lambda:self.ready(self.host) and self.ready(self.client))
        self.require(self.ready(self.host) and self.ready(self.client),'Both wands/effects must recover')

    def both_live(self):
        return self.live(self.host) and self.live(self.client)

    def statuses(self):
        return {label:{field:[round(v,3) for v in self.values(side,field)] for field in
            ('ConcealRemaining','RevealRemaining','TransformationRemaining','ImperioRemaining','SpellCooldownRemaining')}
            for label,side in (('host',self.host),('client',self.client))}

    def controller(self,side):
        return unreal.GameplayStatics.get_player_controller(side['world'],0)

    def client_motion(self,direction=(0,1,0),seconds=.4):
        remote,owner=self.target_pair(self.client)
        movements=[r.get_component_by_class(unreal.CharacterMovementComponent) for r in (remote,owner)]
        self.controller(self.client).set_actor_tick_enabled(True)
        for rider,movement in zip((remote,owner),movements):
            movement.stop_movement_immediately()
            rider.consume_movement_input_vector()
            movement.set_component_tick_enabled(True)
        before=[xyz(r.get_actor_location()) for r in (remote,owner)]
        observed=[]
        def feed():
            owner.add_movement_input(vec(*direction),1.0,False)
            observed.append([xyz(r.get_actor_location()) for r in (remote,owner)])
        feed()
        yield self.wait(seconds,fixture=feed)
        # Give real saved moves and authority responses time to drain; no
        # transform or velocity fixture runs during this measurement window.
        yield self.wait(.2)
        after=[xyz(r.get_actor_location()) for r in (remote,owner)]
        result={"before":before,"after":after,"delta":[[b-a for a,b in zip(p,q)] for p,q in zip(before,after)],
                "disagreement_cm":(remote.get_actor_location()-owner.get_actor_location()).length(),
                "samples":len(observed),"input_direction":list(direction)}
        for rider,movement in zip((remote,owner),movements):
            movement.stop_movement_immediately()
            rider.consume_movement_input_vector()
            movement.set_component_tick_enabled(False)
        self.controller(self.client).set_actor_tick_enabled(False)
        return result

    def scenarios(self):
        self.require(self.host['world']!=self.client['world'] and self.host['match'].has_authority()
            and not self.client['match'].has_authority(),'Separate authority/client worlds are mandatory')
        self.require(not self.live(self.host) and not self.live(self.client),'Fresh lobby required')
        self.require(not prop(self.host['match'],'bBloodbroom'),'Run this suite in regulation for real curse review')
        self.request(self.client,3,1)
        yield self.wait(5,lambda:all(int(prop(r,'TeamIndex'))==1 for r in self.target_pair(self.client)))
        self.request(self.client,2,1)
        ready=lambda:all(int(prop(r,'Position'))==1 and int(prop(r,'TeamIndex'))==1 for r in self.target_pair(self.client))
        yield self.wait(5,ready)
        self.record(TESTS[0],ready() and int(prop(self.host['pawn'],'TeamIndex'))==0,
            worlds=self.provenance['worlds'],host_id=self.player_id(self.host['pawn']),client_id=self.player_id(self.client['pawn']))
        self.isolate_server()
        self.request(self.host,4)
        yield self.wait(5,self.both_live)
        self.require(self.both_live(),'Host kickoff must replicate')
        self.arrange()
        for side in (self.host,self.client):
            world=side['world']
            self.dilations.append((world,float(unreal.GameplayStatics.get_global_time_dilation(world))))
            unreal.GameplayStatics.set_global_time_dilation(world,.25)
        self.dilations_restored=False
        self.provenance['disposable_pie_time_dilation']=.25
        yield self.wait(.3)
        remote=self.client_on_server()
        self.request(self.client,6,20)
        hidden=lambda:min(self.values(self.client,'ConcealRemaining'))>0 and remote.is_concealed_from(self.host['pawn']) \
            and remote.development_is_hidden_from(self.host['pawn'])
        yield self.wait(2,hidden)
        self.record(TESTS[1],hidden() and not self.client['pawn'].is_concealed_from(self.client['pawn']),
            statuses=self.statuses(),host_hidden=remote.development_is_hidden_from(self.host['pawn']))
        self.request(self.host,6,3)
        revealed=lambda:min(self.values(self.host,'RevealRemaining'))>0 and not remote.is_concealed_from(self.host['pawn']) \
            and not remote.development_is_hidden_from(self.host['pawn'])
        yield self.wait(2,revealed)
        self.record(TESTS[2],revealed(),statuses=self.statuses())
        yield from self.cooldowns()
        self.request(self.client,6,3)
        client_reveal=lambda:min(self.values(self.client,'RevealRemaining'))>0
        yield self.wait(2,client_reveal)
        self.record(TESTS[3],client_reveal() and abs(self.values(self.client,'RevealRemaining')[0]-self.values(self.client,'RevealRemaining')[1])<.3,
            client_revelio=self.values(self.client,'RevealRemaining'))

        yield from self.cooldowns()
        yield from self.aim(self.host,self.client)
        quark,client_quark=self.host['balls'][1],self.client['balls'][1]
        self.require(prop(quark,'Holder') is None and prop(quark,'bActive'),'Real possession fixture needs a free active Quark')
        self.require(quark.development_set_flight_fixture(remote.get_actor_location()+vec(0,150,0),vec(0,0,0)),
            'Server physical ball fixture rejected')
        quark.set_actor_tick_enabled(True)
        yield self.wait(.4)
        self.require(self.client['pawn'].development_set_interaction(True),'Client pickup input submission rejected')
        held=lambda:prop(quark,'Holder')==remote and prop(client_quark,'Holder')==self.client['pawn']
        yield self.wait(3,held)
        self.require(held(),'Client must genuinely acquire replicated possession before transformation')
        self.client['pawn'].development_set_interaction(False)
        yield self.wait(.2)
        quark.set_actor_tick_enabled(False)
        self.request(self.host,6,13)
        transformed=lambda:min(self.values(self.client,'TransformationRemaining'))>.1 and prop(quark,'Holder') is None and prop(client_quark,'Holder') is None
        yield self.wait(2,transformed)
        self.require(transformed(),'Actual Transformation/drop must reach the owner and authority')
        proxies=[]
        for rider in self.target_pair(self.client):
            items=[p for p in rider.get_components_by_class(unreal.StaticMeshComponent) if p.get_name()=='SportTransformationOrb']
            self.require(len(items)==1,'Each replicated rider must have its original sporting orb')
            proxies.append(items[0])
        # Submit while LIVE, so rejection proves the transformed action lock
        # rather than the independent ordinary-stoppage gate.
        self.request(self.client,6,20)
        self.client['pawn'].development_set_interaction(True)
        yield self.wait(.3)
        live_actions_denied=self.both_live() and max(self.values(self.client,'ConcealRemaining'))<=.01 \
            and max(self.values(self.client,'SpellCooldownRemaining'))<=.01 \
            and not any(bool(prop(r,'bInteractHeld')) for r in self.target_pair(self.client))
        # Freeze while enough of the three-second effect remains for movement
        # assertions. The actual hit and action rejection happened before pause.
        self.request(self.host,5)
        stopped=lambda:not self.live(self.host) and not self.live(self.client)
        yield self.wait(2,stopped)
        self.require(stopped(),'Host official stoppage must reach both worlds')
        yield self.wait(.3)
        self.record(TESTS[4],transformed() and live_actions_denied
            and all(p.is_visible() and not p.is_collision_enabled() for p in proxies)
            and not any(bool(prop(r,'bInteractHeld')) for r in self.target_pair(self.client)),
            live_actions_denied=live_actions_denied,statuses=self.statuses(),
            actual_ball_drop=prop(quark,'Holder') is None and prop(client_quark,'Holder') is None)
        self.client['pawn'].development_set_interaction(False)
        locked=yield from self.client_motion()
        self.record(TESTS[5],all(max(abs(v) for v in delta)<3 for delta in locked['delta']),movement=locked,statuses=self.statuses())
        before=self.statuses()
        yield self.wait(.6)
        self.record(TESTS[6],stopped() and before==self.statuses() and min(self.values(self.client,'TransformationRemaining'))>0,
            before=before,after=self.statuses())
        self.request(self.host,4)
        yield self.wait(2,self.both_live)
        yield self.wait(5,lambda:max(self.values(self.client,'TransformationRemaining'))<=.01)
        normal=yield from self.client_motion()
        self.record(TESTS[7],max(self.values(self.client,'TransformationRemaining'))<=.01
            and all(not p.is_visible() for p in proxies) and all(d[1]>25 for d in normal['delta'])
            and normal['disagreement_cm']<150,movement=normal,statuses=self.statuses())

        yield from self.cooldowns()
        self.arrange()
        yield from self.aim(self.host,self.client)
        owner_controller=self.client['pawn'].get_controller()
        server_controller=remote.get_controller()
        identity=self.player_id(self.client['pawn'])
        slot=int(prop(self.client['pawn'],'RosterIndex'))
        self.request(self.host,6,28)
        review=lambda:all(prop(side['match'],'bConductReviewPending') and not self.live(side) for side in (self.host,self.client))
        applied=lambda:review() and min(self.values(self.client,'ImperioRemaining'))>0
        yield self.wait(3,applied)
        same_owner=lambda:self.client['pawn'].get_controller()==owner_controller and remote.get_controller()==server_controller \
            and self.player_id(self.client['pawn'])==identity and int(prop(self.client['pawn'],'RosterIndex'))==slot
        self.record(TESTS[8],applied() and same_owner() and all('UNFORGIVABLE' in str(prop(side['match'],'LastConductCall')) for side in (self.host,self.client)),
            statuses=self.statuses(),server=self.conduct(self.host),client=self.conduct(self.client),player_id=identity,slot=slot)
        before=[self.conduct(side) for side in (self.host,self.client)]
        self.request(self.client,12)
        yield self.wait(.6)
        unchanged=before==[self.conduct(side) for side in (self.host,self.client)]
        self.record(TESTS[9],review() and unchanged and not any(prop(side['match'],'bPenaltyShotActive') for side in (self.host,self.client)),
            action=12,unchanged=unchanged,server=self.conduct(self.host),client=self.conduct(self.client))
        self.request(self.host,9)
        queued=lambda:all(not prop(side['match'],'bConductReviewPending') and not self.live(side) for side in (self.host,self.client))
        yield self.wait(3,queued)
        self.require(queued(),'Host F7 must actually queue the allowed disposition')
        self.request(self.host,4)
        served=lambda:self.both_live() and all(int(prop(side['match'],'PendingPenaltyCount'))==0 for side in (self.host,self.client))
        yield self.wait(4,served)
        self.require(served(),'Host restart must genuinely serve the conduct penalty')
        reverse=yield from self.client_motion()
        vertical=yield from self.client_motion((0,0,1))
        yield self.wait(5,lambda:max(self.values(self.client,'ImperioRemaining'))<=.01)
        recovered=yield from self.client_motion()
        self.record(TESTS[10],all(d[1]<-25 for d in reverse['delta']) and all(d[2]>25 for d in vertical['delta'])
            and all(d[1]>25 for d in recovered['delta']) and same_owner()
            and all(m['disagreement_cm']<150 for m in (reverse,vertical,recovered)),
            reversed=reverse,vertical=vertical,recovered=recovered,statuses=self.statuses(),ownership_preserved=same_owner())


def main():
    if unreal is None and '--list' in sys.argv:
        return {"status":"not_run","planned_tests":list(TESTS),"count":len(TESTS)}
    runner=SportSpellNetworkTests()
    try:
        started=runner.begin()
    except Exception:
        runner.finish('error',traceback.format_exc())
        started=False
    if unreal and (started or not runner.done):
        unreal._basketbroom_native_network_test=runner
    return {"status":"started" if started else runner.final_status,"report":str(REPORT),"planned_cases":len(TESTS)}


if __name__=='__main__':
    RESULT=main()
    if unreal is None:
        print(json.dumps(RESULT,indent=2))

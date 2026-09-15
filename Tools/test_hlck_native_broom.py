"""Bounded real native-broom activation, mount and optional ascent observation.

Bridge args: {"execute": true, "drive_ascent": false, "stop_pie": false}.
Default is read-only preflight. Uses only signatures captured by the installed
Creator Kit API probe. Never teleports, sets mounted/flying flags, changes
inventory, unlocks input, alters speed/height rules, saves or travels.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import re
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
PROJECT=Path('C:/Program Files/HogwartsLegacyCreatorKit/PhoenixGame/Phoenix.uproject')
RECORD='/Game/Gameplay/ToolSet/Items/InventoryItems/Broom/DA_BroomHouseItem.DA_BroomHouseItem'
WORLD_RE=r'/Basketbroom/Maps/UEDPIE_\d+_Basketbroom_DungeonMap\.Basketbroom_DungeonMap'
KEY='_bb_native_broom_test_v1'
TIMEOUT=45.;CLEANUP_TIMEOUT=15.;ASCENT_SECONDS=1.25
REQUIRED={
 'ToolSetComponent':('get_tool_records','get_active_tool','is_tool_usage_allowed','activate_tool','clear_active_tool'),
 'BroomItemTool':('get_tool_record','get_our_tool_set_component','spawn_and_mount_broom','unequip_tool'),
 'FlyingBroom':('get_movement_component','add_movement_input','get_velocity','dismount_broom'),
 'FlyingBroomMovementComponent':('is_flying','is_move_input_ignored','get_last_input_vector','get_pending_input_vector','is_component_tick_enabled'),
}


def utc():return datetime.now(timezone.utc).isoformat()


def object_path(value):return value.get_path_name() if value else None


def xyz(value):return [float(value.x),float(value.y),float(value.z)]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence():
    inv_path=ROOT/'.local/hlck/native-broom-inventory.json';api_path=ROOT/'.local/hlck/gameplay-api.json'
    inv=json.loads(inv_path.read_text(encoding='utf-8-sig'));api=json.loads(api_path.read_text(encoding='utf-8-sig'))
    if inv.get('status')!='inspected' or inv.get('tools_activated') is not False:raise RuntimeError('Expected untouched observed inventory evidence')
    slots=[s for s in inv['toolsets'] if s['path'].endswith('.InventoryToolSetComponent')]
    if len(slots)!=1 or not any("'"+RECORD+"'" in r for r in slots[0]['records']):raise RuntimeError('Exact house broom was not witnessed in inventory')
    gaps=[cls+'.'+name for cls,names in REQUIRED.items() for name in names if name not in api.get('classes',{}).get(cls,{})]
    if 'get_is_on_a_mount_or_in_transition' not in api.get('pawn_api',{}):gaps.append('Biped_Player.get_is_on_a_mount_or_in_transition')
    if gaps:raise RuntimeError('Read-only API evidence gaps: '+', '.join(gaps))
    return {'inventory_report':str(inv_path),'inventory_sha256':digest(inv_path),'api_report':str(api_path),'api_sha256':digest(api_path),
            'record':RECORD,'api_gaps':[], 'movement_limit':'Only inherited normal AddMovementInput is exposed; actual vertical response is measured, never assumed.'}


class BroomTest:
    def __init__(self,u,execute=False,drive_ascent=False,stop_pie=False):
        self.u=u;self.execute=execute;self.drive=drive_ascent;self.stop=stop_pie
        self.world=self.player=self.controller=self.inventory=self.tool=self.broom=self.movement=None
        self.handle=None;self.done=False;self.phase='preflight';self.begin=time.monotonic();self.phase_at=self.begin
        self.first_world_time=None;self.last_sample=None;self.mount_since=None;self.mount_world_time=None
        self.ascent_started=None;self.ascent_baseline=None;self.max_ascent=0.;self.failure=None;self.cleanup_started=None
        self.initial_tools={};self.initial_brooms=set();self.sent_dismount=False;self.sent_spawn=False;self.activation_world_time=None
        self.attempt=ROOT/'.local/hlck/native-broom-tests'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8])
        self.attempt.mkdir(parents=True,exist_ok=False);self.report=self.attempt/'result.json'
        self.result={'status':'preflight','pid':os.getpid(),'started_utc':utc(),'execute':execute,'drive_ascent':drive_ascent,
            'stop_pie_requested':stop_pie,'play_started':False,'play_stopped':False,'assets_saved':False,'travel_invoked':False,
            'inventory_modified':False,'forced_flags':False,'teleport_invoked':False,'input_injected':False,'spawn_and_mount_calls':0,
            'activation_calls':0,'dismount_calls':0,'ascent_input_calls':0,'samples':[],'events':[],'checks':{},'scope':'Native broom mount and bounded movement response; no full match/arena flight certification.'}

    def save(self):
        self.result['phase']=self.phase;self.result['elapsed_wall_seconds']=time.monotonic()-self.begin
        temp=self.report.with_suffix('.next');temp.write_text(json.dumps(self.result,indent=2)+'\n',encoding='utf-8');temp.replace(self.report)

    def event(self,name,**data):self.result['events'].append(dict(name=name,utc=utc(),**data));self.save()

    def guard(self):
        u=self.u
        project=Path(u.Paths.convert_relative_path_to_full(u.Paths.get_project_file_path())).resolve()
        if project!=PROJECT.resolve() or not str(u.SystemLibrary.get_engine_version()).startswith('4.27.'):
            raise RuntimeError('Wrong native project/engine')
        if not u.GameModManagerSubsystem.has_active_editor_mod_bp() or str(u.GameModManagerSubsystem.get_active_mod_name_bp())!='Basketbroom':
            raise RuntimeError('Expected active Basketbroom native mod')
        worlds=list(u.EditorLevelLibrary.get_pie_worlds(True))
        if len(worlds)!=1 or not re.fullmatch(WORLD_RE,worlds[0].get_path_name()):raise RuntimeError('Expected one existing owned dungeon Play world')
        if self.world is not None and worlds[0]!=self.world:raise RuntimeError('The retained Play session changed')
        dirty=list(u.EditorLoadingAndSavingUtils.get_dirty_map_packages())+list(u.EditorLoadingAndSavingUtils.get_dirty_content_packages())
        if dirty:raise RuntimeError('Unsaved editor work exists; no test mutation permitted')
        return worlds[0]

    def start(self):
        existing=getattr(self.u,KEY,None)
        if existing:
            safe_stale=(getattr(existing,'done',False) and getattr(existing,'handle',None) is None)
            safe_preflight=(getattr(existing,'execute',None) is False and getattr(existing,'result',{}).get('activation_calls',0)==0)
            if safe_stale or safe_preflight:
                if getattr(existing,'handle',None) is not None:self.u.unregister_slate_post_tick_callback(existing.handle);existing.handle=None
                delattr(self.u,KEY)
            else:raise RuntimeError('A broom test is already observing: '+str(getattr(existing,'report','unknown'))+' phase='+str(getattr(existing,'phase','unknown')))
        self.result['evidence']=evidence();self.world=self.guard()
        self.player=self.u.GameplayStatics.get_player_pawn(self.world,0)
        self.controller=self.u.GameplayStatics.get_player_controller(self.world,0)
        if not self.player or not self.controller or self.controller.get_controlled_pawn()!=self.player:
            raise RuntimeError('Expected possessed native player')
        if self.player.get_class().get_path_name()!='/Game/Pawn/Player/BP_Biped_Player.BP_Biped_Player_C':raise RuntimeError('Wrong native player class')
        if self.player.get_is_on_a_mount_or_in_transition():raise RuntimeError('Initial player is already mounted or transitioning; preserving it')
        components=list(self.player.get_components_by_class(self.u.ToolSetComponent))
        inv=[c for c in components if c.get_name()=='InventoryToolSetComponent']
        if len(inv)!=1:raise RuntimeError('Expected one observed InventoryToolSetComponent')
        self.inventory=inv[0]
        for c in components:self.initial_tools[c.get_path_name()]=object_path(c.get_active_tool())
        if self.inventory.get_active_tool() is not None:raise RuntimeError('Initial inventory tool is active; preserving it without replacement')
        records=[r for r in self.inventory.get_tool_records() if r.get_path_name()==RECORD]
        if len(records)!=1:raise RuntimeError('Exact witnessed house broom record is absent/ambiguous')
        self.record=records[0]
        allowed=bool(self.inventory.is_tool_usage_allowed(self.record))
        self.result.update(world=self.world.get_path_name(),player=self.player.get_path_name(),controller=self.controller.get_path_name(),
            initial_tools=dict(self.initial_tools),tool_usage_allowed=allowed,initial_player_location=xyz(self.player.get_actor_location()))
        self.result['checks']['existing_exact_inventory_record']=True
        self.result['checks']['tool_usage_allowed']=allowed
        if not allowed:raise RuntimeError('Native tool rules disallow the broom here; no whitelist/blacklist bypass attempted')
        self.initial_brooms={a.get_path_name() for a in self.u.GameplayStatics.get_all_actors_of_class(self.world,self.u.FlyingBroom)}
        self.first_world_time=float(self.u.GameplayStatics.get_time_seconds(self.world))
        if not self.execute:
            self.result.update(status='ready',read_only=True,finished_utc=utc());self.save();return self.summary()
        self.phase='settle';self.phase_at=time.monotonic();self.result['status']='running';self.save()
        setattr(self.u,KEY,self);self.handle=self.u.register_slate_post_tick_callback(self.tick)
        return self.summary()

    def summary(self):return {'status':self.result['status'],'report':str(self.report),'execute':self.execute,'stop_pie_requested':self.stop}

    def sample(self,world_time):
        player_location=xyz(self.player.get_actor_location())
        s={'world_seconds':world_time,'mounted_or_transitioning':bool(self.player.get_is_on_a_mount_or_in_transition()),
           'player_location':player_location,'controlled_pawn':object_path(self.controller.get_controlled_pawn()),'active_inventory_tool':object_path(self.inventory.get_active_tool())}
        if self.broom and self.u.SystemLibrary.is_valid(self.broom):
            s.update(broom=self.broom.get_path_name(),broom_location=xyz(self.broom.get_actor_location()),broom_velocity=xyz(self.broom.get_velocity()))
            if self.movement:
                s.update(is_flying=bool(self.movement.is_flying()),movement_tick=bool(self.movement.is_component_tick_enabled()),
                  move_input_ignored=bool(self.movement.is_move_input_ignored()),last_input=xyz(self.movement.get_last_input_vector()),pending_input=xyz(self.movement.get_pending_input_vector()))
        if not all(math.isfinite(v) for v in player_location):raise RuntimeError('Non-finite native player position')
        self.result['samples'].append(s)
        if len(self.result['samples'])>600:self.result['samples']=self.result['samples'][-600:]
        return s

    def begin_cleanup(self,error=None):
        if self.phase in ('cleanup','ending'):return
        self.failure=error;self.result['observation_error']=error
        self.phase='cleanup';self.phase_at=time.monotonic();self.cleanup_started=self.phase_at
        self.event('observation_complete',error=error,actual_ascent_cm=self.max_ascent)
        if (self.broom and self.u.SystemLibrary.is_valid(self.broom) and self.player.get_is_on_a_mount_or_in_transition()
                and self.controller.get_controlled_pawn()==self.broom):
            self.broom.dismount_broom(self.player,False);self.sent_dismount=True;self.result['dismount_calls']+=1
            self.event('normal_dismount_requested')

    def finish(self,error=None):
        if self.done:return
        self.done=True
        if self.handle is not None:self.u.unregister_slate_post_tick_callback(self.handle);self.handle=None
        if getattr(self.u,KEY,None) is self:delattr(self.u,KEY)
        self.result['error']=error or self.failure
        self.result['status']='failed' if self.result['error'] else 'passed'
        self.result['finished_utc']=utc();self.save()

    def tick(self,delta):
        if self.done:return
        now=time.monotonic()
        try:
            if self.phase=='ending':
                worlds=list(self.u.EditorLevelLibrary.get_pie_worlds(True))
                if not worlds:
                    self.result['play_stopped']=True;self.result['checks']['owned_pie_stopped']=True;return self.finish()
                if now-self.phase_at>15:return self.finish('Owned Play did not stop within cleanup observation')
                if len(worlds)!=1 or worlds[0]!=self.world:return self.finish('Play identity changed during cleanup; no further action taken')
                return
            self.guard()
            world_time=float(self.u.GameplayStatics.get_time_seconds(self.world))
            if world_time<self.first_world_time:raise RuntimeError('Native world clock moved backwards')
            if self.last_sample is None or now-self.last_sample>=.1:
                self.last_sample=now;s=self.sample(world_time)
                if self.phase in ('observe','ascent','cleanup'):self.save()
            if self.phase not in ('cleanup','ending') and now-self.begin>TIMEOUT:
                self.result['api_evidence_gap']='If a broom exists without local controller possession, probe a read-only player-to-broom association API; no mount is inferred from the transition flag alone.'
                return self.begin_cleanup('Native mount/flight observation exceeded 45 seconds')
            if self.phase=='settle':
                if world_time-self.first_world_time<1.:return
                self.result['checks']['world_clock_advanced']=True
                self.tool=self.inventory.activate_tool(self.record);self.result['activation_calls']+=1
                self.activation_world_time=world_time
                if self.tool is None or not isinstance(self.tool,self.u.BroomItemTool):raise RuntimeError('activate_tool did not return a real native BroomItemTool')
                if self.tool.get_tool_record()!=self.record or self.tool.get_our_tool_set_component()!=self.inventory:raise RuntimeError('Activated tool does not belong to the witnessed record/inventory')
                self.result['returned_tool']=self.tool.get_path_name();self.result['returned_tool_class']=self.tool.get_class().get_path_name()
                self.result['checks']['real_broom_item_tool_returned']=True
                self.phase='mount';self.phase_at=now;self.event('native_inventory_tool_activated')
                return
            if self.phase=='mount':
                new=[a for a in self.u.GameplayStatics.get_all_actors_of_class(self.world,self.u.FlyingBroom) if a.get_path_name() not in self.initial_brooms]
                if len(new)>1:raise RuntimeError('Multiple new brooms appeared; no ambiguous ownership assumed')
                if new:
                    if self.broom is not None and new[0]!=self.broom:raise RuntimeError('New broom identity changed')
                    self.broom=new[0];movement=self.broom.get_movement_component()
                    if not isinstance(movement,self.u.FlyingBroomMovementComponent):raise RuntimeError('Native broom lacks expected FlyingBroomMovementComponent')
                    self.movement=movement
                mounted=bool(self.player.get_is_on_a_mount_or_in_transition())
                # Inventory activation can itself begin the mount. Wait through
                # its ordinary transition before considering the observed API.
                if not mounted and not new and not self.sent_spawn and world_time-self.activation_world_time>=1.:
                    if not self.u.SystemLibrary.is_valid(self.tool):raise RuntimeError('Activated tool expired before mount; refusing an invented fallback')
                    self.tool.spawn_and_mount_broom(True,True);self.sent_spawn=True;self.result['spawn_and_mount_calls']+=1
                    self.event('normal_spawn_and_mount_requested')
                    return
                flying=self.movement and self.movement.is_flying()
                if mounted and self.broom and flying and self.controller.get_controlled_pawn()==self.broom:
                    self.result['checks']['local_controller_possesses_native_broom']=True
                    if self.mount_since is None:self.mount_since=world_time
                    if world_time-self.mount_since>=1.:
                        self.result['checks']['native_mount_settled']=True;self.result['checks']['native_movement_is_flying']=True
                        self.result['broom_class']=self.broom.get_class().get_path_name();self.mount_world_time=world_time
                        self.phase='observe';self.phase_at=now;self.event('native_flying_mount_observed')
                else:self.mount_since=None
                return
            if self.phase=='observe':
                if not self.player.get_is_on_a_mount_or_in_transition() or not self.movement.is_flying():raise RuntimeError('Native mount ended before observation finished')
                if world_time-self.mount_world_time<2.:return
                if self.drive:
                    if self.movement.is_move_input_ignored():raise RuntimeError('Native input is ignored; no forced-input bypass attempted')
                    self.ascent_started=world_time;self.ascent_baseline=xyz(self.broom.get_actor_location())[2]
                    self.phase='ascent';self.phase_at=now;self.event('bounded_ordinary_ascent_started')
                else:
                    self.result['checks']['settled_flight_observed_for_two_seconds']=True
                    self.result['ascent_tested']=False;return self.begin_cleanup()
            if self.phase=='ascent':
                if (not self.player.get_is_on_a_mount_or_in_transition() or not self.movement.is_flying()
                        or self.controller.get_controlled_pawn()!=self.broom):raise RuntimeError('Native broom possession/mount ended during ordinary ascent')
                self.max_ascent=max(self.max_ascent,xyz(self.broom.get_actor_location())[2]-self.ascent_baseline)
                if world_time-self.ascent_started<ASCENT_SECONDS and self.max_ascent<250:
                    # Normal Pawn API; force=False respects the game's input gates.
                    self.broom.add_movement_input(self.u.Vector(0,0,1),.4,False)
                    self.result['input_injected']=True;self.result['ascent_input_calls']+=1
                    return
                self.result.update(ascent_tested=True,actual_ascent_cm=self.max_ascent)
                self.result['checks']['ordinary_input_caused_vertical_rise']=self.max_ascent>=20
                if self.max_ascent<20:
                    self.result['api_evidence_gap']='Inherited AddMovementInput produced no >=20 cm rise; probe actual broom vertical input bindings before claiming controllable flight.'
                    return self.begin_cleanup('Native mount succeeded, but ordinary ascent response was not demonstrated')
                return self.begin_cleanup()
            if self.phase=='cleanup':
                if now-self.cleanup_started>CLEANUP_TIMEOUT:
                    if self.stop:return self.end_owned_pie('Normal dismount/tool restoration not verified within 15 seconds')
                    return self.finish('Normal dismount/tool restoration not verified within 15 seconds; Play left open')
                if self.player.get_is_on_a_mount_or_in_transition():return
                active=self.inventory.get_active_tool()
                if active is not None:
                    if self.tool and active==self.tool:
                        self.inventory.clear_active_tool();self.event('owned_inventory_slot_cleared')
                        return
                    raise RuntimeError('Another active inventory tool appeared; preserving it without replacement')
                restored={c.get_path_name():object_path(c.get_active_tool()) for c in self.player.get_components_by_class(self.u.ToolSetComponent)}
                self.result['final_tools']=restored
                if restored!=self.initial_tools:raise RuntimeError('Initial tool state was not restored')
                if self.controller.get_controlled_pawn()!=self.player:raise RuntimeError('Initial native player possession was not restored')
                self.result['checks']['normal_dismount_complete']=True;self.result['checks']['initial_tools_preserved']=True
                if self.stop:return self.end_owned_pie()
                return self.finish()
        except Exception as exc:
            reason=type(exc).__name__+': '+str(exc)
            try:
                if self.phase=='cleanup':
                    if self.stop:return self.end_owned_pie(reason)
                    return self.finish(reason)
                self.guard();self.begin_cleanup(reason)
            except Exception as cleanup_exc:self.finish(reason+'; cleanup: '+str(cleanup_exc))

    def end_owned_pie(self,error=None):
        if error:self.failure='; '.join(e for e in (self.failure,error) if e)
        if not self.stop:raise RuntimeError('Explicit stop_pie argument required')
        self.guard();self.phase='ending';self.phase_at=time.monotonic();self.event('same_owned_pie_stop_requested')
        self.u.EditorLevelLibrary.editor_end_play()


def run(args=None):
    import unreal
    args=args or {}
    operation=args.pop('operation','run')
    if operation in ('inspect','cancel'):
        existing=getattr(unreal,KEY,None)
        if existing is None:return {'status':'idle','observer_active':False}
        if type(existing).__name__!='BroomTest' or (ROOT/'.local/hlck/native-broom-tests').resolve() not in Path(existing.report).resolve().parents:raise RuntimeError('Unknown observer object; no cleanup attempted')
        if operation=='cancel':
            if existing.result.get('activation_calls',0)==0:existing.finish('Cancelled before any tool activation')
            elif not existing.done:existing.begin_cleanup('Explicit cancellation; normal cleanup requested')
        return dict(existing.summary(),phase=existing.phase,done=existing.done,activation_calls=existing.result.get('activation_calls',0),observer_active=existing.handle is not None)
    if operation!='run':raise ValueError('Unknown operation')
    if set(args)-{'execute','drive_ascent','stop_pie'}:raise ValueError('Unexpected test argument')
    if any(type(v) is not bool for v in args.values()):raise ValueError('Test arguments must be JSON booleans')
    observer=BroomTest(unreal,execute=args.get('execute',False),drive_ascent=args.get('drive_ascent',False),stop_pie=args.get('stop_pie',False))
    try:return observer.start()
    except Exception as exc:
        observer.result.update(status='not_run',error=type(exc).__name__+': '+str(exc),finished_utc=utc());observer.save();return observer.summary()


if __name__=='__main__':RESULT=run(globals().get('BRIDGE_ARGS',{}))

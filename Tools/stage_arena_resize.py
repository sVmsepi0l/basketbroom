"""Bounded checkpoint-to-longer/wider amendment of four existing UE5 arenas.

Run through the owned UE5 editor bridge. Default dry_run=True; execute requires
both dry_run=False and execute=True. Exact legacy preservation, byte backup,
mesh-slot and real collision checks are reused without rebuilding any map.
"""
from pathlib import Path
import importlib.util
import json
from datetime import datetime,timezone
import uuid

ROOT=Path(__file__).resolve().parents[1]
def module(name,file):
    s=importlib.util.spec_from_file_location(name,ROOT/'Tools'/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

base=module('_bb_resize_ue5_preservation','stage_arena_expansion.py')
plan_module=module('_bb_resize_ue5_plan','arena_resize_plan.py')
env=module('_bb_resize_env_ownership','stage_arena_environments.py')
MAPS=base.MAPS+env.MAPS
original_match=base.match_plan

def match_plan(records,plan,phase='old'):
    environment=[r for r in records.values() if env.TAG in r['tags']]
    if environment:
        # Only the documented environment variants lack these nine backdrops.
        if not all(r['label'].startswith(('redrock /','redwoods /')) for r in environment):raise RuntimeError('Unexpected environment ownership')
        filtered=dict(plan,actors=[r for r in plan['actors'] if r['label'] not in env.BACKDROPS])
        env.backdrop_keys(records,False)  # Still rejects spoofed backdrop ownership.
        return original_match(records,filtered,phase)
    return original_match(records,plan,phase)

def match_training(records,map_path,phase='old'):
    if map_path!=MAPS[1]:return {}  # Current regulation/native anchors remain fixed.
    expected=base.training_layout(base.dimensions.LINEAR_SCALE)
    newer=json.loads(json.dumps(expected))
    delta=base.dimensions.GOAL_PLANE_X-base.dimensions.BASELINE_GOAL_PLANE_X*base.dimensions.LINEAR_SCALE
    for row in newer.values():
        if row['category']=='bot' and row['bot_identity'][2]==0:
            sign=-1 if row['bot_identity'][0]==0 else 1
            row['location'][0]+=sign*delta;row['home'][0]+=sign*delta
    selected={}
    for label,old in expected.items():
        found=[(p,r) for p,r in records.items() if r['label']==label]
        if len(found)!=1:raise RuntimeError('Expected unique existing training actor '+label)
        path,actual=found[0];new=newer[label];wanted=old if phase=='old' else new
        category=old['category']
        cls={'start':'/Script/Engine.PlayerStart','ball':'/Basketbroom/Blueprints/BP_BBBall.BP_BBBall_C','bot':'/Basketbroom/Blueprints/BP_BBBot.BP_BBBot_C'}[category]
        if actual['class']!=cls or 'BB.Gameplay' not in actual['tags']:raise RuntimeError('Training ownership differs '+label)
        if category=='ball' and actual.get('kind')!=old['kind']:raise RuntimeError('Training ball kind differs')
        if category=='bot' and actual.get('bot_identity')!=old['bot_identity']:raise RuntimeError('Training roster differs')
        keys=('location',) if category=='start' else ('location','home')
        if any(not base.near(actual[k],wanted[k]) for k in keys):raise RuntimeError('Training '+phase+' pose differs '+label)
        selected[path]={'old':{k:old[k] for k in keys},'new':{k:new[k] for k in keys}}
    return selected

def run(args=None):
    import unreal
    args=dict(globals().get('BRIDGE_ARGS',{}) if args is None else args)
    dry=args.get('dry_run',True)
    if type(dry) is not bool or (not dry and args.get('execute') is not True):raise ValueError('Execute needs dry_run=false, execute=true')
    if not unreal.SystemLibrary.get_engine_version().startswith('5.8.') or Path(unreal.Paths.project_dir()).resolve()!=(ROOT/'DevelopmentHarness').resolve():raise RuntimeError('Wrong engine/project')
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);worlds=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    def clean():
        if levels.is_in_play_in_editor() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():raise RuntimeError('Stop Play and preserve/save editor work first')
    clean();original=worlds.get_editor_world().get_path_name().split('.')[0]
    if original not in MAPS:raise RuntimeError('Open an owned arena')
    plan=plan_module.build_plan();states=[];before=base.content_hashes();checks=[]
    try:
        for map_path in MAPS:
            clean()
            if not levels.load_level(map_path):raise RuntimeError('Cannot load '+map_path)
            actual=list(actors.get_all_level_actors());records=base.snapshot(unreal,actual)
            failures={}
            for phase in ('old','new'):
                try:
                    match_plan(records,plan,phase);match_training(records,map_path,phase);break
                except RuntimeError as exc:failures[phase]=str(exc)
            else:raise RuntimeError('Neither owned baseline nor current resize pose: '+map_path+' '+str(failures))
            dims=plan['dimensions_before' if phase=='old' else 'dimensions_after']
            checks.append({'map':map_path,'phase':phase,'collision':base.collision_audit(unreal,worlds.get_editor_world(),actual,dims)})
            states.append(phase)
        if len(set(states))!=1:raise RuntimeError('Partially staged maps; inspect existing backups before proceeding')
    finally:
        clean()
        if not levels.load_level(original):raise RuntimeError('Could not restore original map')
        clean();base.check_file_scope(before,base.content_hashes(),[])
    if states[0]=='new':
        attempt=ROOT/'.local/arena-resize-stage'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8]);receipt=attempt/'result.json'
        report={'status':'already_staged','dry_run':dry,'plan':plan,'maps':checks,'preservation_verified':True,'changed_content':[],'original_map_restored':True,'runtime_validation_pending':True}
        base.write(receipt,report);return {'status':'already_staged','report':str(receipt),'maps_checked':len(MAPS),'assets_unchanged':True}
    # Reuse the known immutable-backup, exact-transform/material and collision
    # pipeline with explicit new plan/allowlist. Historical entrypoint unchanged.
    old_module=base.module
    base.module=lambda name,relative: plan_module if relative=='Tools/arena_expansion_plan.py' else old_module(name,relative)
    base.validate_plan=plan_module.validate_plan;base.MAPS=MAPS
    base.match_plan=match_plan;base.match_training=match_training
    base.SUCCESS=ROOT/'.local/arena-resize-success.json'
    result=base.build(args)
    if 'maps_checked' in result:result['maps_checked']=len(MAPS)
    if 'maps_updated' in result:result['maps_updated']=len(MAPS)
    return result

if __name__=='__main__':RESULT=run()

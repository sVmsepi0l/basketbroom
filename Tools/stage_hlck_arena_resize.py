"""Resize the two owned native Creator Kit arenas without rebuilding their maps.

The stage preserves the CURRENT saved actors/materials, including user edits.
Immutable backups and before/after native collision audits accompany every write.
No UE5 package copying, installed asset edits, travel or registration occurs.
"""
from pathlib import Path
from datetime import datetime,timezone
import importlib.util,json,shutil,traceback,uuid

ROOT=Path(__file__).resolve().parents[1]
def module(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=module('_bb_native_resize_preservation','Tools/stage_hlck_arena_expansion.py')
planner=module('_bb_native_resize_plan','Tools/arena_resize_plan.py')
CONTENT=base.CONTENT;MAPS=base.MAPS
SUCCESS=ROOT/'.local/hlck/arena-resize-success.json'

def validate_sources(plan):
 importer=module('_bb_resize_source_import','Mod/Tools/import_sources.py');manifest=importer.validate_sources()
 indexed={e['destination']:e for e in manifest['source_imports']}
 for entry in plan['changed_meshes']:
  row=indexed.get(entry['destination'],{})
  if row.get('source')!=entry['source'] or row.get('sha256')!=entry['sha256_after'] or row.get('asset_type')!='StaticMesh':raise RuntimeError('Prepared native source mismatch')
  if base.digest(ROOT/entry['source'])!=entry['sha256_after']:raise RuntimeError('Source changed during preflight')
 return manifest

def run(dry_run=True):
 stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8]
 directory=ROOT/'.local/hlck/arena-resize-stage'/stamp;receipt=directory/'result.json'
 report={'status':'preflight','dry_run':dry_run,'amendment_kind':'arena_length2_width4over3','maps':[],'gameplay_tested':False,'registration_invoked':False,'travel_invoked':False,'runtime_python':False,'installed_assets_modified':False}
 original=None;mutated=False
 def save():base.write(receipt,report)
 try:
  if type(dry_run) is not bool:raise ValueError('dry_run must be boolean')
  plan=planner.build_plan();manifest=validate_sources(plan);report.update(plan=plan,plan_sha256=base.plan_hash(plan))
  import unreal
  guard=module('_bb_resize_hlck_guard','Tools/load_hlck_dungeon.py');roof=module('_bb_resize_hlck_roof','Tools/stage_hlck_pyramid_net.py')
  registrar=module('_bb_resize_hlck_registration','Tools/register_hlck_dungeon.py');dungeon=module('_bb_resize_hlck_dungeon','Tools/stage_hlck_dungeon.py')
  port=module('_bb_resize_hlck_port','Mod/Tools/build_arena_port.py');importer=port.import_sources
  report['active_mod']=guard.require_editor(unreal);guard.require_clean(unreal)
  active=Path(unreal.Paths.convert_relative_path_to_full(str(unreal.GameModManagerSubsystem.get_active_mod_content_path_bp()))).resolve()
  if active!=CONTENT.resolve():raise RuntimeError('Active native mod is not this repository')
  levels=unreal.EditorLevelLibrary;original=roof.world_path(levels.get_editor_world())
  if original not in MAPS:raise RuntimeError('Open an owned native arena')
  report.update(original_world=original,engine=str(unreal.SystemLibrary.get_engine_version()),registration_before=registrar.verified_saved_registration(unreal,dungeon))
  before=registrar.hashes(CONTENT,base.digest)
  installed=registrar.metadata(registrar.KIT_CONTENT,'.umap');databases={str(p):base.digest(p) for p in (registrar.KIT_CONTENT/'SQLiteDB').glob('*.sqlite')}
  report.update(content_before=before,installed_map_metadata_before=installed,installed_database_hashes_before=databases)
  phases=[]
  prior=None
  if base.SUCCESS.is_file():
   pointer=json.loads(base.SUCCESS.read_text(encoding='utf-8'))
   if base.digest(Path(pointer['report']))!=pointer['sha256']:raise RuntimeError('Prior expansion receipt hash differs')
   prior=json.loads(Path(pointer['report']).read_text(encoding='utf-8'));report['prior_expansion_success']=pointer
  for path in MAPS:
   guard.require_clean(unreal)
   if not levels.load_level(path):raise RuntimeError('Cannot load '+path)
   world,actors=roof.validate_map_ownership(unreal,path);records=base.snapshot(unreal,actors);errors={}
   for phase in ('old','new'):
    try: selected=base.match_plan(records,plan,phase);break
    except RuntimeError as exc:errors[phase]=str(exc)
   else:raise RuntimeError('Neither baseline nor resized owned geometry: '+str(errors))
   phases.append(phase);sha=base.digest(base.map_file(path))
   oldrow=next((r for r in prior.get('maps',[]) if r['path']==path),{}) if prior else {}
   report['maps'].append({'path':path,'phase':phase,'sha256_before':sha,'actors_before':records,
      'preexisting_saved_changes_since_expansion':bool(oldrow and oldrow.get('sha256_after')!=sha),
      'prior_expansion_map_sha256':oldrow.get('sha256_after'),
      'game_mode_before':str(world.get_world_settings().get_editor_property('default_game_mode')),
      'geometry_before':base.geometry_audit(unreal,world,actors,plan['dimensions_before' if phase=='old' else 'dimensions_after'])})
   save()
  if len(set(phases))!=1:raise RuntimeError('Mixed native resize phases; inspect previous backups')
  current_phase=phases[0]
  baseline=json.loads(planner.BASELINE.read_text(encoding='utf-8'));changed={e['name']:e for e in plan['changed_meshes']}
  slots={};report['mesh_slots_before']={};report['source_metadata_before']=[]
  for row in manifest['source_imports']:
   if row['asset_type']!='StaticMesh':continue
   name=Path(row['source']).stem;mesh=unreal.EditorAssetLibrary.load_asset(row['destination'])
   if not isinstance(mesh,unreal.StaticMesh):raise RuntimeError('Expected existing original mesh')
   importer._owned(unreal,mesh)
   expected=(changed[name]['sha256_after'] if current_phase=='new' and name in changed else baseline['meshes'][name]['sha256'])
   actual=unreal.EditorAssetLibrary.get_metadata_tag(mesh,importer.META_HASH)
   if actual!=expected or unreal.EditorAssetLibrary.get_metadata_tag(mesh,importer.META_REVISION)!=importer.REVISION:raise RuntimeError('Native original-source metadata differs: '+name)
   report['source_metadata_before'].append({'asset':row['destination'],'source_sha256':actual})
   if name in changed:
    slots[row['destination']]=[s.copy() for s in mesh.get_editor_property('static_materials')]
    report['mesh_slots_before'][row['destination']]=base.mesh_slots(mesh)
  if not dry_run and current_phase=='old':
   report['package_backups']=[]
   for path in base.allowed_files(plan):
    target=directory/'backups'/path.relative_to(CONTENT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    if base.digest(target)!=base.digest(path):raise RuntimeError('Native byte backup did not verify')
    report['package_backups'].append({'path':str(path),'backup':str(target),'sha256':base.digest(target)})
   for row in report['maps']:row['backup']=str(directory/'backups'/base.map_file(row['path']).relative_to(CONTENT))
   report['status']='backed_up';save();guard.require_clean(unreal)
   mutated=True;unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
   imported=importer.build(create_materials=False,asset_names=[e['name'] for e in plan['changed_meshes']])
   if imported.get('status')!='complete':raise RuntimeError('Targeted original native mesh import failed')
   for entry in plan['changed_meshes']:
    mesh=unreal.EditorAssetLibrary.load_asset(entry['destination']);mesh.set_editor_property('static_materials',slots[entry['destination']])
    if base.mesh_slots(mesh)!=report['mesh_slots_before'][entry['destination']]:raise RuntimeError('Native mesh slots changed')
    if not unreal.EditorAssetLibrary.save_loaded_asset(mesh,only_if_is_dirty=False):raise RuntimeError('Native mesh save failed')
   collision=port.ArenaPortBuilder(manifest,report);collision.meshes={'SM_BB_PyramidCollision':unreal.EditorAssetLibrary.load_asset('/Basketbroom/Art/Meshes/SM_BB_PyramidCollision')};collision.configure_pyramid_collision()
   for row in report['maps']:
    guard.require_clean(unreal)
    if not levels.load_level(row['path']):raise RuntimeError('Cannot reopen native map')
    world,actors=roof.validate_map_ownership(unreal,row['path']);actual=base.snapshot(unreal,actors)
    if base.canonical_snapshot(actual)!=base.canonical_snapshot(row['actors_before']):raise RuntimeError('Native actor/component state changed before resize')
    selected=base.match_plan(actual,plan,'old')
    for actor in actors:
     entry=selected.get(actor.get_path_name())
     if not entry or entry['old']==entry['new']:continue
     target=entry['new']
     actor.set_actor_location(unreal.Vector(*target['location']),False,True)
     actor.set_actor_rotation(unreal.Rotator(pitch=target['rotation'][0],yaw=target['rotation'][1],roll=target['rotation'][2]),True)
     actor.set_actor_scale3d(unreal.Vector(*target['scale']))
    current=list(levels.get_all_level_actors());base.compare_preservation(actual,base.snapshot(unreal,current),selected)
    row['geometry_pre_save']=base.geometry_audit(unreal,world,current,plan['dimensions_after'])
    if str(world.get_world_settings().get_editor_property('default_game_mode'))!=row['game_mode_before']:raise RuntimeError('Native game mode changed')
    dirty=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if any(p!=row['path'] for p in dirty) or unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():raise RuntimeError('Unexpected dirty work; do not save it')
    if not levels.save_current_level() or not levels.load_level(row['path']):raise RuntimeError('Native map save/reload failed')
    world,actors=roof.validate_map_ownership(unreal,row['path']);saved=base.snapshot(unreal,actors)
    count=base.compare_preservation(actual,saved,selected);base.match_plan(saved,plan,'new')
    if str(world.get_world_settings().get_editor_property('default_game_mode'))!=row['game_mode_before']:raise RuntimeError('Game mode did not survive reload')
    row.update(sha256_after=base.digest(base.map_file(row['path'])),actors_after=saved,saved_reloaded=True,unrelated_actors_preserved=True,actor_identity_and_components_preserved=True,transformed_actor_count=count,geometry_after=base.geometry_audit(unreal,world,actors,plan['dimensions_after']))
    save()
  if not levels.load_level(original):raise RuntimeError('Cannot restore original native map')
  guard.require_clean(unreal);after=registrar.hashes(CONTENT,base.digest)
  changed_files=sorted(p for p in set(before)|set(after) if before.get(p)!=after.get(p));allowed={str(p.relative_to(CONTENT.resolve())) for p in base.allowed_files(plan)}
  if set(changed_files)-allowed or ((dry_run or current_phase=='new') and changed_files):raise RuntimeError('Unexpected saved asset mutation')
  if registrar.metadata(registrar.KIT_CONTENT,'.umap')!=installed or any(base.digest(Path(p))!=sha for p,sha in databases.items()):raise RuntimeError('Installed native content changed')
  report['registration_after']=registrar.verified_saved_registration(unreal,dungeon)
  if report['registration_before']!=report['registration_after']:raise RuntimeError('Native registration changed')
  for destination,expected in report['mesh_slots_before'].items():
   if base.mesh_slots(unreal.EditorAssetLibrary.load_asset(destination))!=expected:raise RuntimeError('Native mesh slots did not survive reload')
  report.update(status='already_staged' if current_phase=='new' else 'ready' if dry_run else 'staged',
    saved_package_hashes={str(p):base.digest(p) for p in base.allowed_files(plan)},changed_content_files=changed_files,
    preservation_verified=True,materials_preserved=True,original_world_restored=True,runtime_validation_pending=True,finished_utc=datetime.now(timezone.utc).isoformat())
  save()
  if not dry_run and current_phase=='old':base.write(SUCCESS,{'report':str(receipt),'sha256':base.digest(receipt)})
 except Exception:
  report.update(status='failed',error=traceback.format_exc(),mutation_started=mutated,recovery='Inspect retained byte backups; no automatic rollback or discard of editor work.')
  if original and not mutated:
   try:
    guard.require_clean(unreal);levels.load_level(original);guard.require_clean(unreal);report['original_world_restored']=True
   except Exception:report['restore_error']=traceback.format_exc()
  save()
 return {'status':report['status'],'report':str(receipt),'dry_run':dry_run,'runtime_tested':False}

if __name__=='__main__':
 if 'BRIDGE_ARGS' in globals():RESULT=run(BRIDGE_ARGS.get('dry_run',True))
 else:
  plan=planner.build_plan();validate_sources(plan);print(json.dumps({'status':'sources_valid','unreal_called':False,'changed_meshes':len(plan['changed_meshes'])}))

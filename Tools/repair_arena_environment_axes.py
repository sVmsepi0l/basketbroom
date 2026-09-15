"""Prove OBJ import handedness and compensate only owned venue mesh actors.

Default dry_run=True reads imported bounds/topology and reports evidence.
Execute false backs up and updates only BB_Redrock/BB_Redwoods actor scales.
No source mesh reimport, material rebuild, sporting changes, or camera workaround.
"""
from pathlib import Path
import importlib.util
import json
import hashlib
from datetime import datetime,timezone
import shutil
import uuid
import traceback

ROOT=Path(__file__).resolve().parents[1]

def module(name,file):
    s=importlib.util.spec_from_file_location(name,ROOT/'Tools'/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def bounds_errors(source,actual):
    reflected=[[source[0][0],-source[1][1],source[0][2]],[source[1][0],-source[0][1],source[1][2]]]
    error=lambda wanted:max(abs(actual[i][j]-wanted[i][j]) for i in range(2) for j in range(3))
    return error(source),error(reflected)

def run(dry_run=True):
    import unreal
    stage=module('_bb_env_axes_stage','stage_arena_environments.py');manifest,textures=stage.load_manifest()
    if not unreal.SystemLibrary.get_engine_version().startswith('5.8.') or Path(unreal.Paths.project_dir()).resolve()!=(ROOT/'DevelopmentHarness').resolve():raise RuntimeError('Wrong engine/project')
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);worlds=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    def clean():
        if levels.is_in_play_in_editor():raise RuntimeError('Stop PIE before reading/loading venue maps')
        if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():raise RuntimeError('Dirty editor work must stay untouched')
    clean();original=worlds.get_editor_world().get_path_name().split('.')[0]
    if original not in (stage.SOURCE,'/Basketbroom/Maps/BB_Arena')+stage.MAPS:raise RuntimeError('Load an owned map')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8]
    attempt=ROOT/'.local/environment-axis-audit'/stamp;attempt.mkdir(parents=True,exist_ok=False);receipt=attempt/'result.json'
    result={'status':'preflight','dry_run':dry_run,'meshes':[],'maps':[],'source_manifest_sha256':stage.digest(ROOT/'SourceArt/Environments/environments_manifest.json')}
    before=stage.content_hashes();allowed={'Maps/'+p.rsplit('/',1)[-1]+'.umap' for p in stage.MAPS}
    try:
        orientations=[]
        for venue in manifest['venues']:
            for row in venue['meshes']:
                mesh=unreal.EditorAssetLibrary.load_asset(stage.ART+'/Meshes/'+row['name'])
                if not isinstance(mesh,unreal.StaticMesh):raise RuntimeError('Missing environment mesh '+row['name'])
                box=mesh.get_bounding_box();actual=[[float(box.min.x),float(box.min.y),float(box.min.z)],[float(box.max.x),float(box.max.y),float(box.max.z)]]
                same,flip=bounds_errors(row['bounds'],actual)
                topology=int(mesh.get_num_triangles(0))
                if topology!=row['triangles']:raise RuntimeError('Imported topology differs: '+row['name'])
                if min(same,flip)>.1:raise RuntimeError('Imported bounds have an unexplained transform: '+row['name'])
                orientation='ambiguous_symmetric' if same<=.1 and flip<=.1 else 'identity' if same<=.1 else 'mirror_y'
                if orientation!='ambiguous_symmetric':orientations.append(orientation)
                result['meshes'].append({'name':row['name'],'source_sha256':row['sha256'],'source_bounds':row['bounds'],'imported_bounds':actual,
                  'identity_error_cm':same,'mirror_y_error_cm':flip,'orientation':orientation,'triangles':topology,'topology_preserved':True})
        if not orientations or len(set(orientations))!=1:raise RuntimeError('No single evidenced import handedness covers all asymmetric meshes')
        orientation=orientations[0];sign=-1 if orientation=='mirror_y' else 1
        result.update(import_handedness=orientation,asymmetric_evidence_meshes=len(orientations),required_actor_y_scale_multiplier=sign)
        if not levels.load_level(stage.SOURCE):raise RuntimeError('Cannot load source map')
        baseline=stage.protected(stage.portable_snapshot(unreal,list(actors.get_all_level_actors())))
        for venue in manifest['venues']:
            clean()
            if not levels.load_level(venue['map']):raise RuntimeError('Cannot load variant')
            current=list(actors.get_all_level_actors());records=stage.portable_snapshot(unreal,current);stage.assert_protected(baseline,stage.protected(records,False))
            selected=[]
            for placement in venue['instances']:
                matches=[a for a in current if a.get_actor_label()==placement['label'] and a.actor_has_tag(stage.TAG)]
                if len(matches)!=1:raise RuntimeError('Expected exact unique environment actor '+placement['label'])
                a=matches[0];c=a.get_component_by_class(unreal.StaticMeshComponent)
                if c is None or c.get_editor_property('static_mesh').get_path_name().split('.')[0]!=stage.ART+'/Meshes/'+placement['mesh']:raise RuntimeError('Actor source identity mismatch')
                expected=placement['scale'];wanted=[expected[0],expected[1]*sign,expected[2]];scale=[a.get_actor_scale3d().x,a.get_actor_scale3d().y,a.get_actor_scale3d().z]
                if any(abs(a-b)>.001 for a,b in zip(scale,expected)) and any(abs(a-b)>.001 for a,b in zip(scale,wanted)):raise RuntimeError('Unexpected prior environment scale')
                if c.get_collision_enabled()!=unreal.CollisionEnabled.NO_COLLISION:raise RuntimeError('Scenery has collision')
                selected.append((a,placement,wanted))
            mapfile=stage.CONTENT/'Maps'/(venue['map'].rsplit('/',1)[-1]+'.umap')
            item={'path':venue['map'],'sha256_before':stage.digest(mapfile),'expected_mesh_actor_count':len(selected)};result['maps'].append(item)
            if not dry_run:
                backup=attempt/(mapfile.name+'.before');shutil.copy2(mapfile,backup)
                if stage.digest(backup)!=item['sha256_before']:raise RuntimeError('Backup verification failed')
                for a,p,wanted in selected:a.set_actor_scale3d(unreal.Vector(*wanted))
                stage.assert_protected(baseline,stage.protected(stage.portable_snapshot(unreal,list(actors.get_all_level_actors())),False))
                if not levels.save_current_level() or not levels.load_level(venue['map']):raise RuntimeError('Cannot save/reload corrected map')
                fresh=list(actors.get_all_level_actors());stage.assert_protected(baseline,stage.protected(stage.portable_snapshot(unreal,fresh),False))
                for p in venue['instances']:
                    a=next(a for a in fresh if a.get_actor_label()==p['label'] and a.actor_has_tag(stage.TAG));actual=a.get_actor_scale3d();wanted=[p['scale'][0],p['scale'][1]*sign,p['scale'][2]]
                    if any(abs(x-y)>.001 for x,y in zip((actual.x,actual.y,actual.z),wanted)):raise RuntimeError('Compensated scale did not persist')
                helper=module('_bb_env_axes_collision','stage_arena_expansion.py')
                item.update(saved_reloaded=True,backup=str(backup),sha256_after=stage.digest(mapfile),geometry=helper.collision_audit(unreal,worlds.get_editor_world(),fresh,manifest['sporting_dimensions']),sporting_actors_preserved=True)
        if not levels.load_level(original):raise RuntimeError('Could not restore original map')
        clean();after=stage.content_hashes();changed=sorted(p for p in set(before)|set(after) if before.get(p)!=after.get(p))
        if set(changed)-allowed or (dry_run and changed):raise RuntimeError('Unexpected saved content mutation')
        result.update(status='ready' if dry_run else 'corrected',changed_files=changed,original_map_restored=True,content_scope_verified=True,
            visual_validation_pending=True,vertex_provenance_limit='Source hashes, exact imported triangle counts and all 30 signed bounds checked. Bounds prove global handedness on asymmetric meshes; this is not a vertex-by-vertex export comparison.')
        stage.write(receipt,result)
        if not dry_run:stage.write(ROOT/'.local/environment-axis-success.json',{'report':str(receipt),'sha256':stage.digest(receipt)})
    except Exception:result.update(status='failed',error=traceback.format_exc());stage.write(receipt,result)
    return {'status':result['status'],'report':str(receipt),'dry_run':dry_run}

if __name__=='__main__':RESULT=run(globals().get('BRIDGE_ARGS',{}).get('dry_run',True))

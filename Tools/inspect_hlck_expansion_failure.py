"""Read the current owned map after a failed expansion; make no editor changes."""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import uuid

ROOT=Path(__file__).resolve().parents[1]

def module(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def run(receipt):
    import unreal
    stage=module('_bb_expansion_failure_stage','Tools/stage_hlck_arena_expansion.py')
    guard=module('_bb_expansion_failure_guard','Tools/load_hlck_dungeon.py')
    guard.require_editor(unreal);guard.require_clean(unreal)
    path=Path(receipt).resolve();path.relative_to((ROOT/'.local/hlck/arena-expansion-stage').resolve())
    prior=json.loads(path.read_text(encoding='utf-8'))
    if prior.get('status')!='failed' or prior.get('dry_run') is not False or not prior.get('package_backups'):
        raise RuntimeError('Requires a backed-up failed real expansion attempt')
    world=unreal.EditorLevelLibrary.get_editor_world();world_path=world.get_path_name().split('.')[0]
    items=[item for item in prior['maps'] if item['path']==world_path]
    if len(items)!=1:raise RuntimeError('Current map is not owned by the exact failed attempt')
    if stage.digest(stage.map_file(world_path))!=items[0]['sha256_before']:
        raise RuntimeError('Current saved map no longer equals the failed attempt baseline')
    snapshot=stage.snapshot(unreal,list(unreal.EditorLevelLibrary.get_all_level_actors()))
    actual=json.loads(json.dumps(snapshot));before=items[0]['actors_before']
    differences=[]
    for actor_path in sorted(set(actual)|set(before)):
        old,new=before.get(actor_path),actual.get(actor_path)
        if old is None or new is None:
            differences.append({'actor':actor_path,'before':old,'after':new});continue
        for key in sorted(set(old)|set(new)):
            if old.get(key)!=new.get(key):differences.append({'actor':actor_path,'label':old['label'],'field':key,'before':old.get(key),'after':new.get(key)})
    report={'status':'inspected','read_only':True,'inspected_utc':datetime.now(timezone.utc).isoformat(),
        'attempt':str(path),'attempt_sha256':stage.digest(path),'world':world_path,'differences':differences,'actors_after_import':actual}
    target=path.parent/('diagnosis-'+uuid.uuid4().hex[:12]+'.json');stage.write(target,report)
    return {'status':'inspected','world':world_path,'difference_count':len(differences),'report':str(target)}

if __name__=='__main__':
    RESULT=run(BRIDGE_ARGS['receipt'])

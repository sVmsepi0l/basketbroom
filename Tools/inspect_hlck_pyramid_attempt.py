"""Inspect an interrupted owned roof attempt without saving or editing Unreal state."""
from pathlib import Path
import importlib.util,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
def run():
 import unreal
 project=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
 if project!=Path('C:/Program Files/HogwartsLegacyCreatorKit/PhoenixGame/Phoenix.uproject').resolve() or str(unreal.GameModManagerSubsystem.get_active_mod_name_bp())!='Basketbroom':
  raise RuntimeError('Expected installed Phoenix and active Basketbroom')
 if unreal.EditorLevelLibrary.get_pie_worlds(True): raise RuntimeError('Stop Play before inspecting authoring')
 path=Path(BRIDGE_ARGS['report']).resolve()
 path.relative_to((ROOT/'.local/hlck/pyramid-net-stage').resolve())
 receipt=json.loads(path.read_text(encoding='utf-8'))
 spec=importlib.util.spec_from_file_location('_bb_roof_attempt_probe',ROOT/'Tools/stage_hlck_pyramid_net.py')
 roof=importlib.util.module_from_spec(spec);spec.loader.exec_module(roof)
 world=roof.world_path(unreal.EditorLevelLibrary.get_editor_world())
 rows=[row for row in receipt['maps'] if row['path']==world]
 if len(rows)!=1: raise RuntimeError('Current map does not belong to this attempt')
 actors=list(unreal.EditorLevelLibrary.get_all_level_actors())
 before=rows[0]['preserved_before'];after=roof.snapshot(unreal,actors)
 changes={key:{'before':before[key],'after':after[key]} for key in before.keys() & after.keys() if before[key]!=after[key]}
 result={'read_only':True,'world':world,'added':{key:after[key] for key in after.keys()-before.keys()},'removed':{key:before[key] for key in before.keys()-after.keys()},'changed':changes,'dirty_maps':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],'dirty_content':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],'disk_map_unchanged':roof.digest(roof.asset_file(world,'.umap'))==rows[0]['sha256_before']}
 out=path.parent/'snapshot-diagnostic.json';out.write_text(json.dumps(result,indent=2)+'\n')
 return {'report':str(out),'added':len(result['added']),'removed':len(result['removed']),'changed':len(changes),'disk_map_unchanged':result['disk_map_unchanged']}
if __name__=='__main__': RESULT=run()

"""Load a clean owned UE5 venue and request its real editor-camera screenshot."""
from pathlib import Path
import json
from datetime import datetime, timezone
import unreal
ROOT=Path(__file__).resolve().parents[1]
ARGS=globals().get('BRIDGE_ARGS',{})
def run():
    venue=ARGS.get('arena','redrock')
    if venue not in ('redrock','redwoods'):raise ValueError('Unknown venue')
    if not unreal.SystemLibrary.get_engine_version().startswith('5.8.'):raise RuntimeError('UE5.8 only')
    project=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
    if project!=(ROOT/'DevelopmentHarness/BasketbroomDev.uproject').resolve():raise RuntimeError('Wrong project')
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if levels.is_in_play_in_editor():raise RuntimeError('Stop PIE first')
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():raise RuntimeError('Unsaved editor work')
    map_path='/Basketbroom/Maps/BB_'+('Redrock' if venue=='redrock' else 'Redwoods')
    if not levels.load_level(map_path):raise RuntimeError('Cannot load owned venue')
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    cameras=[a for a in actors if isinstance(a,unreal.CameraActor) and a.get_actor_label()==venue+' / environment hero']
    if len(cameras)!=1:raise RuntimeError('Expected exact authored hero camera')
    out=ROOT/'.local/environment-renders'/str(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+venue+'.png')
    out.parent.mkdir(parents=True,exist_ok=True)
    task=unreal.AutomationLibrary.take_high_res_screenshot(1600,900,str(out),camera=cameras[0],delay=3.0)
    unreal._bb_environment_capture_task=task
    report={'status':'requested','arena':venue,'map':map_path,'path':str(out),'started_utc':datetime.now(timezone.utc).isoformat(),'task':str(task),'gameplay_tested':False}
    (ROOT/'.local/environment-preview.json').write_text(json.dumps(report,indent=2))
    return report
if __name__=='__main__':RESULT=run()

"""Read native broom inventory from an owned user-started dungeon Play session."""
from pathlib import Path
from datetime import datetime,timezone
import json,time,os,re,unreal
ROOT=Path(__file__).resolve().parents[1];REPORT=ROOT/'.local/hlck/native-broom-inventory.json';KEY='_bb_native_broom_inventory'
def run():
    project=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
    if project!=Path('C:/Program Files/HogwartsLegacyCreatorKit/PhoenixGame/Phoenix.uproject').resolve():raise RuntimeError('Wrong native project')
    if str(unreal.GameModManagerSubsystem.get_active_mod_name_bp())!='Basketbroom':raise RuntimeError('Wrong active mod')
    if getattr(unreal,KEY,None):raise RuntimeError('Inventory observer already active')
    result={'status':'waiting_for_user_play','pid':os.getpid(),'started_utc':datetime.now(timezone.utc).isoformat(),'read_only':True,'inputs_injected':False,'tools_activated':False,'assets_saved':False}
    state={'handle':None,'started':time.monotonic(),'first_pie':None}
    def write():REPORT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    def finish(status,error=None):
        result['status']=status;result['error']=error;result['finished_utc']=datetime.now(timezone.utc).isoformat()
        if state['handle'] is not None:unreal.unregister_slate_post_tick_callback(state['handle']);state['handle']=None
        setattr(unreal,KEY,None);write()
    def tick(delta):
        try:
            if time.monotonic()-state['started']>600:return finish('not_run','No ready native Play within ten minutes')
            worlds=unreal.EditorLevelLibrary.get_pie_worlds(True)
            if not worlds:return
            if len(worlds)!=1 or not re.fullmatch(r'/Basketbroom/Maps/UEDPIE_\d+_Basketbroom_DungeonMap\.Basketbroom_DungeonMap',worlds[0].get_path_name()):return finish('failed','Unexpected PIE world')
            world=worlds[0];pawn=unreal.GameplayStatics.get_player_pawn(world,0);controller=unreal.GameplayStatics.get_player_controller(world,0)
            if not pawn or not controller or controller.get_controlled_pawn()!=pawn:return
            if state['first_pie'] is None:state['first_pie']=time.monotonic()
            if time.monotonic()-state['first_pie']<8:return
            components=list(pawn.get_components_by_class(unreal.ToolSetComponent))
            result.update(world=world.get_path_name(),pawn=pawn.get_path_name(),world_seconds=unreal.GameplayStatics.get_time_seconds(world),mounted=bool(pawn.get_is_on_a_mount_or_in_transition()),toolsets=[])
            for component in components:
                records=[]
                for record in component.get_tool_records():
                    records.append(record.export_text() if callable(getattr(record,'export_text',None)) else str(record))
                active=component.get_active_tool()
                result['toolsets'].append({'path':component.get_path_name(),'class':component.get_class().get_path_name(),'records':records,'active_tool':active.get_path_name() if active else None})
            return finish('inspected')
        except Exception as exc:finish('failed',type(exc).__name__+': '+str(exc))
    write();setattr(unreal,KEY,state);state['handle']=unreal.register_slate_post_tick_callback(tick)
    return {'status':result['status'],'report':str(REPORT),'read_only':True}
if __name__=='__main__':RESULT=run()
"""Read-only installed native Blueprint graph and broom authoring surface."""
from pathlib import Path
from datetime import datetime,timezone
import json,os,unreal
ROOT=Path(__file__).resolve().parents[1]
def run():
    project=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
    if project != Path('C:/Program Files/HogwartsLegacyCreatorKit/PhoenixGame/Phoenix.uproject').resolve(): raise RuntimeError('Wrong native project')
    if str(unreal.GameModManagerSubsystem.get_active_mod_name_bp()) != 'Basketbroom': raise RuntimeError('Wrong active mod')
    if unreal.EditorLevelLibrary.get_pie_worlds(True): raise RuntimeError('Stop Play before editor API inventory')
    classes={}
    names=[n for n in dir(unreal) if any(w in n.lower() for w in ('blueprinteditor','blueprintgraph','graphpin','k2node','blueprintfactory','blueprintlibrary','broomitem','toolsetcomponent'))]
    for name in names:
        cls=getattr(unreal,name)
        methods={key:str(getattr(getattr(cls,key,None),'__doc__',''))[:6000] for key in dir(cls) if not key.startswith('_') and any(w in key.lower() for w in ('graph','node','pin','event','function','blueprint','broom','tool','import','export','create','compile','spawn','mount')) and callable(getattr(cls,key,None))}
        classes[name]={'doc':str(getattr(cls,'__doc__',''))[:3000],'methods':methods}
    result={'status':'inspected','pid':os.getpid(),'time_utc':datetime.now(timezone.utc).isoformat(),'read_only':True,'assets_loaded':False,'classes':classes}
    path=ROOT/'.local/hlck/blueprint-authoring-api.json';path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return {'status':'inspected','report':str(path),'classes':list(classes)}
if __name__=='__main__':RESULT=run()
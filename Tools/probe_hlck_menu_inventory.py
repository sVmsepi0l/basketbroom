"""Read-only native player/menu/inventory reflection, from an existing owned PIE."""
from pathlib import Path
import json,os
from datetime import datetime,timezone
import unreal
ROOT=Path(__file__).resolve().parents[1]
def api(obj,words):
 return {n:str(getattr(obj,n).__doc__)[:2200] for n in dir(obj) if any(w in n.lower() for w in words) and callable(getattr(obj,n,None))}
def run():
 if not unreal.SystemLibrary.get_engine_version().startswith('4.27.'):raise RuntimeError('Native Kit only')
 if str(unreal.GameModManagerSubsystem.get_active_mod_name_bp())!='Basketbroom':raise RuntimeError('Wrong active mod')
 worlds=unreal.EditorLevelLibrary.get_pie_worlds(True)
 if len(worlds)!=1 or '/Basketbroom/Maps/UEDPIE_' not in worlds[0].get_path_name():raise RuntimeError('Expected owned PIE')
 w=worlds[0];p=unreal.GameplayStatics.get_player_pawn(w,0);pc=unreal.GameplayStatics.get_player_controller(w,0)
 data={'pid':os.getpid(),'utc':datetime.now(timezone.utc).isoformat(),'world':w.get_path_name(),'player':p.get_path_name() if p else None,'paused':unreal.GameplayStatics.is_game_paused(w),'controller_api':api(pc,('pause','menu','cheat','ui','inventory','spell','mount','broom')),'player_api':api(p,('inventory','tool','menu','pause','spell','broom','mount')),'classes':{}}
 for n in dir(unreal):
  if any(s in n.lower() for s in ('cheatmanager','inventorylibrary','inventoryfunction','pausemenu','uimanager','uiblueprint','menuhelper','menumanager','toolrecord','broomitem')):
   c=getattr(unreal,n);data['classes'][n]={'doc':str(c.__doc__)[:8000],'api':api(c,('broom','inventory','pause','menu','tool','spell','item','screen','unlock','count','quantity'))}
 out=ROOT/'.local/hlck/native-menu-inventory-surface.json';out.write_text(json.dumps(data,indent=2),encoding='utf-8')
 return {'status':'inspected','report':str(out),'class_names':list(data['classes'])}
if __name__=='__main__':RESULT=run()

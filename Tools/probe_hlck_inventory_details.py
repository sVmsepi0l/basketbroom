from pathlib import Path
import json,unreal
ROOT=Path(__file__).resolve().parents[1]
def api(obj,words):return {n:str(getattr(obj,n).__doc__)[:1500] for n in dir(obj) if any(w in n.lower() for w in words) and callable(getattr(obj,n,None))}
def run():
 w=unreal.EditorLevelLibrary.get_pie_worlds(True)[0]
 if '/Basketbroom/Maps/UEDPIE_' not in w.get_path_name():raise RuntimeError('Wrong PIE')
 p=unreal.GameplayStatics.get_player_pawn(w,0);gi=unreal.GameplayStatics.get_game_instance(w)
 d={'game_instance_class':gi.get_class().get_path_name(),'game_instance_api':api(gi,('ui','inventory','pause','broom','item','unlock')),'libraries':{},'records':[],'can_use_broom':unreal.UIBlueprintFunctionLibrary.can_use_broom(),'can_use_broom_without_avatar':unreal.UIBlueprintFunctionLibrary.can_use_broom(False)}
 for n in dir(unreal):
  c=getattr(unreal,n)
  if 'Inventory' in n or (('Library' in n or 'Blueprint' in n) and any(v in n for v in ('Phoenix','Game','UI'))):
   methods=api(c,('get_ui_manager','inventory','item_count','unlock','broom','quantity'))
   if methods:d['libraries'][n]=methods
 for comp in p.get_components_by_class(unreal.ToolSetComponent):
  for rec in comp.get_tool_records():
   if '/Broom/' in rec.get_path_name():
    row={'path':rec.get_path_name()}
    for key in ('lock_name','lookup_name','inventory_item_tool','contexts'):
     try:row[key]=str(rec.get_editor_property(key))
     except Exception as e:row[key]='unavailable '+str(e)
    d['records'].append(row)
 out=ROOT/'.local/hlck/native-inventory-details.json';out.write_text(json.dumps(d,indent=2),encoding='utf-8');return {'report':str(out),'class':d['game_instance_class'],'can_use_broom':d['can_use_broom'],'libraries':list(d['libraries'])}
if __name__=='__main__':RESULT=run()

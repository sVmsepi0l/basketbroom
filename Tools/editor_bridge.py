"""Singleton local editor bridge; development-only, never cooked into gameplay.

Runs only existing Python scripts below this repository's Tools directory.
Reconnect replaces the known callback and preserves the last request ID.
"""
import unreal
import pathlib
import json
import traceback
import runpy
import time
import os

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABEL = 'hlck' if unreal.SystemLibrary.get_engine_version().startswith('4.') else 'ue5'
BOX = ROOT / '.local' / LABEL
BOX.mkdir(parents=True, exist_ok=True)
KEY = '_basketbroom_editor_bridge_v2'
previous = getattr(unreal, KEY, None)
if previous is not None and previous.get('root') != str(ROOT):
    raise RuntimeError('A different Basketbroom workspace owns this bridge')
if previous is not None and previous.get('busy'):
    raise RuntimeError('Cannot reconnect while a bridge request is executing')
if previous is not None and previous.get('handle') is not None:
    unreal.unregister_slate_post_tick_callback(previous['handle'])
state = {'root':str(ROOT),'handle':None,'busy':False,'last_poll':0.,
         'last_id':previous.get('last_id') if previous else None,'executions':previous.get('executions',0) if previous else 0}
# A new connection never replays a stale mutation left in the mailbox.
if previous is None:
    try:state['last_id']=json.loads((BOX/'request.json').read_text(encoding='utf-8-sig'))['id']
    except (OSError,ValueError,KeyError):pass
setattr(unreal,KEY,state)

def poll(delta):
    if getattr(unreal,KEY,None) is not state or state['busy'] or time.monotonic()-state['last_poll']<.25:return
    state['last_poll']=time.monotonic()
    request=BOX/'request.json'
    if not request.exists():return
    try:
        data=json.loads(request.read_text(encoding='utf-8-sig'))
        request_id=data['id']
        if not isinstance(request_id,str) or not request_id or request_id==state['last_id']:return
    except (OSError,ValueError,KeyError):return
    state['last_id']=request_id
    state['busy']=True
    state['executions']+=1
    try:
        script=(ROOT/'Tools'/data['script']).resolve()
        if ROOT/'Tools' not in script.parents or script.suffix!='.py' or not script.is_file():
            raise ValueError('Only existing repository Tools Python scripts may run')
        result=runpy.run_path(str(script),init_globals={'BRIDGE_ARGS':data.get('args',{})},run_name='__main__')
        response={'id':request_id,'ok':True,'result':result.get('RESULT')}
    except Exception:
        response={'id':request_id,'ok':False,'error':traceback.format_exc()}
        unreal.log_error(response['error'])
    finally:state['busy']=False
    response['bridge']={'pid':os.getpid(),'execution':state['executions'],'version':2}
    temp=BOX/'response.tmp'
    temp.write_text(json.dumps(response,indent=2,default=str),encoding='utf-8')
    temp.replace(BOX/'response.json')

state['handle']=unreal.register_slate_post_tick_callback(poll)
(BOX/'ready.json').write_text(json.dumps({'engine':unreal.SystemLibrary.get_engine_version(),'project':unreal.Paths.project_dir(),'pid':os.getpid(),'version':2}),encoding='utf-8')
unreal.log('BASKETBROOM EDITOR BRIDGE READY: '+str(BOX))

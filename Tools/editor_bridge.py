"""Local, file-based editor development bridge. Never included in cooked gameplay.

Only executes scripts located inside this repository's Tools directory.
For UE5, launch with -ExecCmds="py <absolute path to this file>".
For Creator Kit, launch through signed-in Epic Games Launcher first, then run
py "C:/Git/basketbroom/Tools/editor_bridge.py" in its editor console. A direct
UE4Editor.exe relaunch omits the launcher authentication needed by ModAuth.
"""
import unreal
import pathlib
import json
import traceback
import runpy
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABEL = 'hlck' if unreal.SystemLibrary.get_engine_version().startswith('4.') else 'ue5'
BOX = ROOT / '.local' / LABEL
BOX.mkdir(parents=True, exist_ok=True)
_last_poll = 0
_last_id = None

def poll(delta):
    global _last_poll, _last_id
    if time.monotonic() - _last_poll < 0.25:
        return
    _last_poll = time.monotonic()
    request = BOX / 'request.json'
    if not request.exists():
        return
    try:
        data = json.loads(request.read_text(encoding='utf-8-sig'))
        if data['id'] == _last_id:
            return
        _last_id = data['id']
        script = (ROOT / 'Tools' / data['script']).resolve()
        if ROOT / 'Tools' not in script.parents:
            raise ValueError('Only repository Tools scripts may run')
        result = runpy.run_path(str(script), init_globals={'BRIDGE_ARGS': data.get('args', {})}, run_name='__main__')
        response = {'id': _last_id, 'ok': True, 'result': result.get('RESULT')}
    except Exception:
        response = {'id': _last_id, 'ok': False, 'error': traceback.format_exc()}
        unreal.log_error(response['error'])
    (BOX / 'response.json').write_text(json.dumps(response, indent=2, default=str), encoding='utf-8')

_bridge_handle = unreal.register_slate_post_tick_callback(poll)
(BOX / 'ready.json').write_text(json.dumps({'engine': unreal.SystemLibrary.get_engine_version(), 'project': unreal.Paths.project_dir()}), encoding='utf-8')
unreal.log('BASKETBROOM EDITOR BRIDGE READY: ' + str(BOX))

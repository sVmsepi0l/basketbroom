"""local, file-based editor development bridge. never included in cooked gameplay.

only executes scripts located inside this repository's tools directory.
for ue5, launch with -execcmds="py <absolute path to this file>".
for creator kit, launch through signed-in epic games launcher first, then run
py "C:/Git/basketbroom/Tools/editor_bridge.py" in its editor console. a direct
UE4Editor.exe relaunch omits the launcher authentication needed by ModAuth.
"""
import unreal
import pathlib
import json
import traceback
import runpy
import time

root = pathlib.Path(__file__).resolve().parents[1]
label = 'hlck' if unreal.SystemLibrary.get_engine_version().startswith('4.') else 'ue5'
box = root / '.local' / label
BOX.mkdir(parents=True, exist_ok=true)
_last_poll = 0
_last_id = none

def poll(delta):
    global _last_poll, _last_id
    if time.monotonic() - _last_poll < 0.25:
        return
    _last_poll = time.monotonic()
    request = box / 'request.json'
    if not request.exists():
        return
    try:
        data = json.loads(request.read_text(encoding='utf-8-sig'))
        if data['id'] == _last_id:
            return
        _last_id = data['id']
        script = (root / 'tools' / data['script']).resolve()
        if root / 'tools' not in script.parents:
            raise valueerror('only repository tools scripts may run')
        result = runpy.run_path(str(script), init_globals={'BRIDGE_ARGS': data.get('args', {})}, run_name='__main__')
        response = {'id': _last_id, 'ok': true, 'result': result.get('RESULT')}
    except Exception:
        response = {'id': _last_id, 'ok': false, 'error': traceback.format_exc()}
        unreal.log_error(response['error'])
    (box / 'response.json').write_text(json.dumps(response, indent=2, default=str), encoding='utf-8')

_bridge_handle = unreal.register_slate_post_tick_callback(poll)
(box / 'ready.json').write_text(json.dumps({'engine': unreal.SystemLibrary.get_engine_version(), 'project': unreal.Paths.project_dir()}), encoding='utf-8')
unreal.log('BASKETBROOM editor bridge READY: ' + str(box))

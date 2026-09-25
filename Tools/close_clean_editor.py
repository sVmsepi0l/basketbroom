"""Close a clean owned editor through its public API, without saving packages.

Bridge default is a read-only dry run. A queued close rechecks ownership and
cleanliness on a later Slate tick, then invokes only SystemLibrary.quit_editor.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import unreal

ROOT = Path(__file__).resolve().parents[1]
STATE = '_basketbroom_clean_editor_close'


def check():
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
    kit = Path(r'C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject').resolve()
    game = (ROOT / 'DevelopmentHarness/BasketbroomDev.uproject').resolve()
    lab = (ROOT / '.local/CharacterLab/BasketbroomCharacterLab.uproject').resolve()
    if project not in (kit, game, lab):
        raise RuntimeError('Refusing to close a different editor project')
    if unreal.EditorLevelLibrary.get_pie_worlds(True):
        raise RuntimeError('Stop the owned PIE session before closing its editor')
    saving = unreal.EditorLoadingAndSavingUtils
    dirty = [p.get_path_name() for p in list(saving.get_dirty_map_packages()) + list(saving.get_dirty_content_packages())]
    if dirty:
        raise RuntimeError('Preserving unsaved editor packages: ' + repr(dirty))
    world = unreal.EditorLevelLibrary.get_editor_world()
    path = world.get_path_name().split('.')[0] if world else None
    allowed = ('/Basketbroom/Maps/Basketbroom_DungeonMap', '/Basketbroom/Maps/BB_Arena_Port') if project == kit else ('/Basketbroom/Maps/BB_Regulation', '/Basketbroom/Maps/BB_Arena', '/Basketbroom/Maps/BB_Redrock', '/Basketbroom/Maps/BB_Redwoods')
    if project == lab:
        if not unreal.SystemLibrary.get_engine_version().startswith('5.8.'):
            raise RuntimeError('Expected the UE5.8 character lab')
        session = getattr(unreal, '_bb_human_cloud_build', None)
        if session is not None and not session.finished:
            raise RuntimeError('Preserving an active human character cloud session')
        if not path or not path.startswith(('/Temp/Untitled', '/Game/BasketbroomLab/Maps/Review_')):
            raise RuntimeError('Expected the clean transient character lab world')
    elif path not in allowed:
        raise RuntimeError('Expected an already-open owned arena map')
    if project == kit:
        manager = unreal.GameModManagerSubsystem
        if not manager.has_active_editor_mod_bp() or str(manager.get_active_mod_name_bp()) != 'Basketbroom':
            raise RuntimeError('Expected the active Basketbroom mod')
    method = getattr(unreal.SystemLibrary, 'quit_editor', None)
    if not callable(method):
        raise RuntimeError('The installed public quit_editor API is unavailable')
    return {'project': str(project), 'map': path, 'process_id': os.getpid(),
            'label': 'hlck' if project == kit else 'ue5', 'dirty_packages': dirty,
            'quit_api': str(method.__doc__)}


def run(dry_run=True):
    result = check()
    result.update(status='ready' if dry_run else 'queued', dry_run=dry_run,
                  sampled_utc=datetime.now(timezone.utc).isoformat(), packages_saved=False)
    report = ROOT / '.local' / result['label'] / 'clean-editor-close.json'
    report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    if dry_run:
        return result
    if getattr(unreal, STATE, None) is not None:
        raise RuntimeError('An editor close is already queued')
    state = {'ticks': 0, 'handle': None}
    def tick(delta):
        state['ticks'] += 1
        if state['ticks'] < 3:
            return
        unreal.unregister_slate_post_tick_callback(state['handle'])
        delattr(unreal, STATE)
        try:
            result.update(check())
            result['status'] = 'quit_requested'
            report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            unreal.SystemLibrary.quit_editor()
        except Exception as exc:
            result.update(status='failed', error=str(exc))
            report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    setattr(unreal, STATE, state)
    state['handle'] = unreal.register_slate_post_tick_callback(tick)
    return result


if __name__ == '__main__':
    RESULT = run(globals().get('BRIDGE_ARGS', {}).get('dry_run', True))

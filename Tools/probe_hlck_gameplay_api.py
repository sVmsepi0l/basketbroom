"""Read only the installed kit's gameplay-adapter APIs and current owned pawn.

No assets are loaded, graphs authored, inputs injected, or gameplay functions
invoked. Reflected function signatures identify candidates, not working adapters.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import unreal

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / '.local/hlck/gameplay-api.json'
PROJECT = Path(r'C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject')


def signatures(cls, words, limit=80):
    found = {}
    for name in dir(cls):
        if name.startswith('_') or not any(word in name.lower() for word in words):
            continue
        member = getattr(cls, name, None)
        if callable(member):
            found[name] = str(getattr(member, '__doc__', ''))[:5000]
        if len(found) >= limit:
            break
    return found


def run():
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
    if project != PROJECT.resolve():
        raise RuntimeError('Expected the installed Creator Kit project')
    manager = unreal.GameModManagerSubsystem
    if not manager.has_active_editor_mod_bp() or str(manager.get_active_mod_name_bp()) != 'Basketbroom':
        raise RuntimeError('Expected the active Basketbroom mod')
    worlds = unreal.EditorLevelLibrary.get_pie_worlds(True)
    if len(worlds) != 1 or re.fullmatch(
            r'/Basketbroom/Maps/UEDPIE_\d+_Basketbroom_DungeonMap\.Basketbroom_DungeonMap',
            worlds[0].get_path_name()) is None:
        raise RuntimeError('Expected exactly one already-running owned dungeon PIE')
    world = worlds[0]
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    if not pawn or not controller or controller.get_controlled_pawn() != pawn:
        raise RuntimeError('Expected a possessed native player')
    result = {
        'sampled_utc': datetime.now(timezone.utc).isoformat(),
        'process_id': os.getpid(), 'engine': unreal.SystemLibrary.get_engine_version(),
        'read_only': True, 'asset_loads_requested': False, 'input_injected': False,
        'scope': 'Installed reflected signatures and existing pawn components; no adapter implementation proof.',
        'world': world.get_path_name(), 'world_seconds': unreal.GameplayStatics.get_time_seconds(world),
        'pawn_class': pawn.get_class().get_path_name(),
        'controller_class': controller.get_class().get_path_name(),
        'pawn_api': signatures(type(pawn), ('broom', 'fly', 'flight', 'spell', 'ability', 'interact', 'mount', 'cast')),
        'controller_api': signatures(type(controller), ('broom', 'fly', 'flight', 'spell', 'ability', 'interact', 'mount', 'input')),
        'components': [], 'classes': {},
        'viewport_console_api': str(getattr(unreal.SystemLibrary.execute_console_command, '__doc__', '')),
        'screenshot_api': str(getattr(unreal.AutomationLibrary.take_high_res_screenshot, '__doc__', '')),
    }
    words = ('broom', 'fly', 'flight', 'spell', 'ability', 'interact', 'mount',
             'cast', 'mod', 'blueprint', 'graph', 'node', 'component', 'input',
             'velocity', 'speed', 'overlap', 'context', 'action', 'tool', 'target')
    for component in pawn.get_components_by_class(unreal.ActorComponent):
        item = {'name': component.get_name(), 'class': component.get_class().get_path_name()}
        if any(word in item['class'].lower() for word in ('ability', 'toolset', 'inputwatcher', 'gameplaymod')):
            item['api'] = signatures(type(component), words, limit=140)
        result['components'].append(item)
    for name in ('FlyingBroom', 'FlyingBroomMovementComponent', 'BroomItemTool',
                 'ModMutator', 'UGCBlueprintLibrary', 'PhxEditorBlueprintLibrary',
                 'AblAbilityComponent', 'RPGAbilityComponent', 'GameplayModComponent',
                 'ToolSetComponent', 'InputWatcherComponent'):
        cls = getattr(unreal, name, None)
        result['classes'][name] = signatures(cls, words, limit=140) if cls is not None else None
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix('.next')
    temporary.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    temporary.replace(REPORT)
    return {'status': 'inspected', 'process_id': result['process_id'], 'report': str(REPORT),
            'classes': list(result['classes']), 'pawn_components': len(result['components'])}


if __name__ == '__main__':
    RESULT = run()

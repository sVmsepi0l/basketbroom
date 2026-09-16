"""Preserve the sole owned map dirtied by the interrupted environment reimport.

Requires the explicit failed receipt and its immutable original-map backup.
Does not discard work, touch other packages, or mark staging successful.
"""
import importlib.util
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_bb_recover_env', ROOT/'Tools/stage_arena_environments.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
args = globals().get('BRIDGE_ARGS', {})
receipt = (ROOT/args['receipt']).resolve()
if ROOT/'.local/environment-stage' not in receipt.parents:
    raise RuntimeError('Expected an owned environment stage receipt')
report = json.loads(receipt.read_text())
if report['status'] != 'failed' or 'Unsaved editor work must remain untouched' not in report.get('error', ''):
    raise RuntimeError('Not the expected import checkpoint failure')
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
worlds = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if Path(unreal.Paths.project_dir()).resolve() != (ROOT/'DevelopmentHarness').resolve() or levels.is_in_play_in_editor():
    raise RuntimeError('Wrong project or active Play session')
current = worlds.get_editor_world().get_path_name().split('.')[0]
dirty = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if current not in stage.MAPS or dirty != [current] or unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
    raise RuntimeError('Unexpected unsaved package scope')
relative = 'Maps/'+current.rsplit('/',1)[-1]+'.umap'
backup = next(b for b in report['backups'] if b['file'] == relative)
if stage.digest(backup['backup']) != backup['sha256'] or stage.digest(stage.CONTENT/relative) != backup['sha256']:
    raise RuntimeError('Original map backup or on-disk map changed')
baseline = stage.protected(json.loads((receipt.parent/'source-actors.json').read_text()))
records = stage.portable_snapshot(unreal, list(actors.get_all_level_actors()))
stage.assert_protected(baseline, stage.protected(records, False))
stage.write(receipt.parent/'reimport-dirty-map-snapshot.json', records)
if not levels.save_current_level():
    raise RuntimeError('Could not preserve owned import checkpoint')
RESULT = {'status':'saved_import_checkpoint', 'map':current, 'backup':backup,
          'staging_complete':False, 'sporting_actors_preserved':True}
stage.write(receipt.parent/'recovery.json', RESULT)

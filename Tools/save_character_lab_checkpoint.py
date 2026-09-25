"""Preserve an unsaved lab review world before an editor restart."""
from datetime import datetime, timezone
from pathlib import Path
import unreal as ue

ROOT = Path(__file__).resolve().parents[1]


def run():
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.get_project_file_path())).resolve()
    if project != (ROOT/'.local/CharacterLab/BasketbroomCharacterLab.uproject').resolve():
        raise RuntimeError('Expected isolated character lab')
    if ue.get_editor_subsystem(ue.LevelEditorSubsystem).is_in_play_in_editor():
        raise RuntimeError('Stop Play before checkpointing')
    preview = getattr(ue, '_bb_human_render_preview', None)
    if preview and preview.data['status'] == 'running':
        raise RuntimeError('Wait for the human render to finish')
    saving = ue.EditorLoadingAndSavingUtils
    if saving.get_dirty_content_packages():
        raise RuntimeError('Preserve dirty character assets separately first')
    world = ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
    if not world or not world.get_path_name().startswith('/Temp/Untitled'):
        raise RuntimeError('Expected the transient lab review world')
    destination = '/Game/BasketbroomLab/Maps/Review_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    if not saving.save_map(world, destination):
        raise RuntimeError('Could not save the lab review world')
    return {'status':'saved', 'map':destination, 'playable_project_changed':False}


if __name__ == '__main__':
    RESULT = run()

"""Open one owned CharacterLab design for actual visual review, without saving."""
from pathlib import Path
import unreal


def run(name):
    root = Path(__file__).resolve().parents[1]
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
    if project != (root / '.local/CharacterLab/BasketbroomCharacterLab.uproject').resolve():
        raise RuntimeError('Only the isolated Basketbroom character workspace is supported')
    if name not in ('BB_AthleteA', 'BB_AthleteB'):
        raise ValueError('Unknown owned athlete design')
    asset = unreal.EditorAssetLibrary.load_asset('/Game/BasketbroomHumans/Design/' + name)
    if not isinstance(asset, unreal.MetaHumanCharacter) or unreal.EditorAssetLibrary.get_metadata_tag(asset, 'BB.Generator') != 'Basketbroom.HumanPlayerDesign.v1':
        raise RuntimeError('Expected an owned human design')
    subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
    opened = subsystem.open_editor_for_assets([asset])
    return {'opened': bool(opened), 'asset': asset.get_path_name(), 'assets_saved': False}


if __name__ == '__main__':
    RESULT = run(globals().get('BRIDGE_ARGS', {}).get('name', 'BB_AthleteA'))

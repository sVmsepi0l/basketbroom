"""Read-only diagnostics for the isolated human authoring workspace."""
from pathlib import Path


def run():
    import unreal as ue
    root = Path(__file__).resolve().parents[1]
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.get_project_file_path())).resolve()
    if project != (root / '.local/CharacterLab/BasketbroomCharacterLab.uproject').resolve():
        raise RuntimeError('Expected the isolated character lab')
    saving = ue.EditorLoadingAndSavingUtils
    dirty = [p.get_path_name() for p in list(saving.get_dirty_map_packages()) + list(saving.get_dirty_content_packages())]
    assets = ue.EditorAssetLibrary
    output = {'dirty_packages': dirty, 'characters': [], 'mutations': 0}
    for name in ('BB_AthleteA', 'BB_AthleteB'):
        path = '/Game/BasketbroomHumans/Assembled/' + name + '/BP_' + name
        blueprint = assets.load_asset(path) if assets.does_asset_exist(path) else None
        row = {'blueprint': path, 'exists': blueprint is not None}
        if blueprint:
            row.update(status=str(blueprint.get_editor_property('status')),
                       generated_class=blueprint.generated_class().get_path_name() if blueprint.generated_class() else None,
                       export_quality=assets.get_metadata_tag(blueprint, 'MHExportQuality'))
        output['characters'].append(row)
    return output


if __name__ == '__main__':
    RESULT = run()

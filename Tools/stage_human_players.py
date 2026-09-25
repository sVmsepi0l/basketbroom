"""Isolated MetaHuman character lab: inspect first, explicitly create designs.

Bridge arguments: {}, {"operation":"inspect"}, or {"operation":"create"}.
No cloud requests, rigging, downloads, assembly, game integration, or main
project writes occur. Creation duplicates two installed adult presets into
new owned lab design assets; existing designs are preserved, never replaced.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / '.local/CharacterLab'
PROJECT = LAB / 'BasketbroomCharacterLab.uproject'
OWNER = 'Basketbroom.HumanPlayerDesign.v1'
PRESETS = {
    'BB_AthleteA': '/MetaHumanCharacter/Optional/Presets/Ada',
    'BB_AthleteB': '/MetaHumanCharacter/Optional/Presets/Omari',
}
DESTINATION = '/Game/BasketbroomHumans/Design/'
PRESET_CONTENT = Path(r'C:\Program Files\Epic Games\UE_5.8\Engine\Plugins\MetaHuman\MetaHumanCharacter\Content')
ASSET_SUFFIXES = {'.uasset', '.umap', '.ubulk', '.uexp', '.uptnl'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def file_tree(base, suffixes=None):
    if not base.exists(): return {}
    return {str(p.relative_to(base)): digest(p) for p in base.rglob('*')
            if p.is_file() and (suffixes is None or p.suffix in suffixes)}


def playable_snapshot():
    result = {}
    for relative in ('DevelopmentHarness/Content', 'DevelopmentHarness/Plugins/Basketbroom/Content',
                     'DevelopmentHarness/Source', 'DevelopmentHarness/Config'):
        result[relative] = file_tree(ROOT/relative)
    for relative in ('DevelopmentHarness/BasketbroomDev.uproject', '.local/latest-package.json'):
        path = ROOT/relative
        result[relative] = digest(path) if path.exists() else None
    pointer = ROOT/'.local/latest-package.json'
    if pointer.is_file():
        manifest = json.loads(pointer.read_text(encoding='utf-8-sig'))
        executable = Path(manifest['Executable']).resolve()
        executable.relative_to((ROOT/'.local/Build').resolve())
        if executable.is_file(): result['accepted_game_executable'] = {'path':str(executable),'sha256':digest(executable)}
    return result


def api_inventory(ue):
    groups = {
        'MetaHumanCharacter': ('has_high_resolution_textures','has_face_dna_blendshapes','fixed_body_type',
                              'internal_collection','assembly_settings','skin_settings','head_model_settings'),
        'MetaHumanCharacterEditorSubsystem': ('try_add_object_to_edit','is_object_added_for_editing',
            'remove_object_to_edit','can_build_meta_human','request_auto_rigging','request_texture_sources',
            'build_meta_human','assemble_for_preview','initialize_from_preset','get_rigging_state'),
        'MetaHumanCharacterAutoRiggingRequestParams': (),
        'MetaHumanCharacterTextureRequestParams': (),
        'MetaHumanCharacterEditorBuildParameters': (),
    }
    result = {}
    for class_name, names in groups.items():
        cls = getattr(ue, class_name, None)
        if cls is None:
            result[class_name] = {'available':False}; continue
        result[class_name] = {'available':True, 'doc':str(cls.__doc__ or '')[:30000],
                             'public_names':[n for n in dir(cls) if not n.startswith('_')],
                             'selected':{n:{'available':hasattr(cls,n),'doc':str(getattr(cls,n).__doc__ or '')[:8000]
                                            if hasattr(cls,n) else None} for n in names}}
    return result


def read_property(obj, name):
    # Each name is an installed reflected UPROPERTY, also demonstrated by the
    # shipped MetaHuman Python examples. Unavailable fields are reported, not
    # invented or treated as a successful readiness check.
    try:
        value = obj.get_editor_property(name)
        if isinstance(value, (bool, int, float, str)): return {'available':True,'value':value}
        if hasattr(value, 'get_path_name'): return {'available':True,'path':value.get_path_name()}
        return {'available':True,'value':str(value)[:12000]}
    except Exception as exc:
        return {'available':False,'error':str(exc)}


def describe_character(ue, character):
    return {'path':character.get_path_name(), 'class':character.get_class().get_path_name(),
            'properties':{name:read_property(character,name) for name in (
                'has_high_resolution_textures','has_face_dna_blendshapes','fixed_body_type',
                'internal_collection','assembly_settings','skin_settings','head_model_settings',
                'synthesized_face_textures_info','high_res_body_textures_info')},
            'owner_tag':ue.EditorAssetLibrary.get_metadata_tag(character,'BB.Generator'),
            'source_preset_tag':ue.EditorAssetLibrary.get_metadata_tag(character,'BB.SourcePreset')}


def owns_collection(character):
    collection = character.get_editor_property('internal_collection')
    if collection is None: return False
    obj = collection
    for _ in range(16):
        if obj == character: return True
        obj = obj.get_outer()
        if obj is None: break
    return False


def readiness(ue, character, subsystem):
    if subsystem.is_object_added_for_editing(character):
        raise RuntimeError('Design already has an editor session; preserve it: '+character.get_path_name())
    if not subsystem.try_add_object_to_edit(character):
        raise RuntimeError('Could not open the new owned design for readiness inspection')
    try:
        return {'can_build_meta_human':bool(subsystem.can_build_meta_human(character)),
                'has_high_resolution_textures':bool(character.has_high_resolution_textures),
                'cloud_requests_made':False,
                'note':'A false build result means the design is not an assembled gameplay character.'}
    finally:
        if subsystem.is_object_added_for_editing(character): subsystem.remove_object_to_edit(character)


def run(operation='preflight'):
    import unreal as ue
    if operation not in ('preflight','inspect','create'): raise ValueError('Choose preflight, inspect, or create')
    current = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())).resolve()
    current_file = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.get_project_file_path())).resolve()
    if current != LAB.resolve() or current_file != PROJECT.resolve() or not ue.SystemLibrary.get_engine_version().startswith('5.8.'):
        raise RuntimeError('This tool is restricted to the isolated UE5.8 BasketbroomCharacterLab')
    if ue.get_editor_subsystem(ue.LevelEditorSubsystem).is_in_play_in_editor(): raise RuntimeError('Stop lab Play before character authoring')
    dirty = list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages()) + list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    if dirty: raise RuntimeError('Existing unsaved lab work must be preserved: '+str([p.get_path_name() for p in dirty]))
    if not hasattr(ue,'MetaHumanCharacter') or not hasattr(ue,'MetaHumanCharacterEditorSubsystem'):
        raise RuntimeError('MetaHuman Creator must be enabled in the isolated lab first')
    attempt = LAB/'receipts'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8])
    attempt.mkdir(parents=True, exist_ok=False)
    receipt = attempt/'result.json'
    before = playable_snapshot(); write(attempt/'playable-before.json',before)
    lab_before = file_tree(LAB/'Content', ASSET_SUFFIXES)
    source_files = {str(PRESET_CONTENT/(p.removeprefix('/MetaHumanCharacter/')+'.uasset')):None for p in PRESETS.values()}
    for filename in source_files:
        path = Path(filename)
        if not path.is_file(): raise RuntimeError('Installed preset file missing: '+filename)
        source_files[filename] = digest(path)
    report = {'status':'running','operation':operation,'engine':ue.SystemLibrary.get_engine_version(),
              'project':str(current_file),'presets':[],'designs':[],'cloud_requests_made':False,
              'game_integration_performed':False,'assets_created':[],'assets_saved':[],
              'api':api_inventory(ue),'installed_preset_hashes':source_files,
              'renderer':{name:ue.SystemLibrary.get_console_variable_int_value(name) for name in (
                  'r.SkinCache.Mode','r.SkinCache.CompileShaders','r.RayTracing','r.VirtualTextures')},
              'playable_snapshot':str(attempt/'playable-before.json')}
    write(receipt, report)
    try:
        assets = ue.EditorAssetLibrary
        loaded_presets = {}
        for name, path in PRESETS.items():
            preset = assets.load_asset(path)
            if not isinstance(preset,ue.MetaHumanCharacter): raise RuntimeError('Unexpected installed preset type: '+path)
            loaded_presets[name] = preset
            report['presets'].append(describe_character(ue,preset))
        # Preflight every existing destination before creating either design.
        existing = {}
        for name, source in PRESETS.items():
            path = DESTINATION+name
            character = assets.load_asset(path) if assets.does_asset_exist(path) else None
            if character is not None:
                if not isinstance(character,ue.MetaHumanCharacter) or assets.get_metadata_tag(character,'BB.Generator') != OWNER or assets.get_metadata_tag(character,'BB.SourcePreset') != source:
                    raise RuntimeError('Refusing an unrelated existing design: '+path)
                if not owns_collection(character): raise RuntimeError('Existing design does not own its collection: '+path)
            existing[name] = character
        subsystem = ue.get_editor_subsystem(ue.MetaHumanCharacterEditorSubsystem)
        for name, source in PRESETS.items():
            path = DESTINATION+name
            character = existing[name]
            was_existing = character is not None
            if operation == 'create' and character is None:
                character = assets.duplicate_asset(source,path)
                if not isinstance(character,ue.MetaHumanCharacter): raise RuntimeError('Could not duplicate installed preset to '+path)
                assets.set_metadata_tag(character,'BB.Generator',OWNER)
                assets.set_metadata_tag(character,'BB.SourcePreset',source)
                assets.set_metadata_tag(character,'BB.DesignIntent','Original adult Basketbroom athlete; prototype design, not finished character')
                if character == loaded_presets[name] or not owns_collection(character):
                    raise RuntimeError('Duplicated character lacks independently owned collection')
                report['assets_created'].append(path)
                if not assets.save_loaded_asset(character,only_if_is_dirty=False): raise RuntimeError('Could not save new design '+path)
                report['assets_saved'].append(path)
            row = {'destination':path,'exists':character is not None,'preserved_existing':was_existing}
            if character is not None:
                row['character'] = describe_character(ue,character)
                if operation == 'create' and not was_existing:
                    row['readiness'] = readiness(ue,character,subsystem)
                    # An edit-session initialization can update this new design;
                    # save only that exact design and no other dirty assets.
                    if not assets.save_loaded_asset(character,only_if_is_dirty=False): raise RuntimeError('Could not checkpoint new design')
            report['designs'].append(row)
            write(receipt, report)
        lab_after = file_tree(LAB/'Content',ASSET_SUFFIXES)
        allowed = {'BasketbroomHumans/Design/'+name+suffix for name in PRESETS for suffix in ASSET_SUFFIXES}
        changed = sorted(p for p in set(lab_before)|set(lab_after) if lab_before.get(p)!=lab_after.get(p))
        changed = [p.replace('\\','/') for p in changed]
        if (operation != 'create' and changed) or set(changed)-allowed:
            raise RuntimeError('Unexpected lab content changes: '+str(changed))
        if any(digest(Path(filename)) != sha for filename,sha in source_files.items()):
            raise RuntimeError('Installed preset bytes changed unexpectedly')
        after = playable_snapshot()
        if before != after:
            write(attempt/'playable-after.json',after)
            raise RuntimeError('The main playable project changed during the isolated operation')
        report.update(status='designs_created_pending_rig_and_textures' if report['assets_created'] else 'inspected',
                      changed_lab_packages=changed,main_playable_preserved=True,installed_presets_preserved=True,
                      asset_hashes={p:sha for p,sha in lab_after.items() if p.replace('\\','/') in allowed})
    except Exception:
        report.update(status='failed',error=traceback.format_exc())
        report['main_playable_preserved'] = before == playable_snapshot()
        write(receipt,report)
        raise
    write(receipt,report)
    write(LAB/'latest-character-stage.json',{'report':str(receipt),'status':report['status']})
    return {'status':report['status'],'report':str(receipt),'created':report['assets_created'],
            'main_playable_preserved':report['main_playable_preserved'],'cloud_requests_made':False}


if __name__ == '__main__':
    args = globals().get('BRIDGE_ARGS',{})
    RESULT = run(args.get('operation','preflight'))

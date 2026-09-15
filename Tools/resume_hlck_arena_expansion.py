"""Resume an exact backed-up failed native expansion after mesh-only import.

Default dry run. Requires both map bytes still at their original hashes and all
10 imported meshes at their new source hashes. Does not reimport, reset shaders,
replace materials, restore packages, delete actors or rewrite the failed receipt.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]

def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def validate_failed_attempt(stage, receipt, plan):
    path = Path(receipt).resolve()
    path.relative_to((ROOT / '.local/hlck/arena-expansion-stage').resolve())
    value = json.loads(path.read_text(encoding='utf-8'))
    if (path.name != 'result.json' or value.get('status') != 'failed' or value.get('dry_run') is not False
            or value.get('plan_sha256') != stage.plan_hash(plan) or value.get('plan') != plan
            or len(value.get('maps', [])) != 2 or any(item.get('sha256_after') for item in value['maps'])
            or value.get('pyramid_collision_build', {}).get('source_sha256') != next(entry['sha256_after'] for entry in plan['changed_meshes'] if entry['name'] == 'SM_BB_PyramidCollision')):
        raise RuntimeError('Only an exact failed mesh-import-only attempt may be resumed')
    expected = {str(file): file for file in stage.allowed_files(plan)}
    backups = value.get('package_backups', [])
    if len(backups) != len(expected) or {item['path'] for item in backups} != set(expected):
        raise RuntimeError('The failed attempt lacks every exact pre-expansion package backup')
    for item in backups:
        backup = Path(item['backup']).resolve()
        backup.relative_to(path.parent / 'backups')
        if stage.digest(backup) != item['sha256']:
            raise RuntimeError('A failed-attempt original package backup changed')
    if {item['path'] for item in value['maps']} != set(stage.MAPS):
        raise RuntimeError('The failed attempt references unexpected maps')
    for item in value['maps']:
        if stage.digest(stage.map_file(item['path'])) != item['sha256_before'] or not item.get('geometry_before', {}).get('passed'):
            raise RuntimeError('A saved map changed after the failed import; no resume is allowed')
    return path, value


def run(receipt, dry_run=True):
    stage = module('_bb_resume_expansion_stage', 'Tools/stage_hlck_arena_expansion.py')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '-' + uuid.uuid4().hex[:8]
    directory = ROOT / '.local/hlck/arena-expansion-stage' / stamp
    target = directory / 'result.json'
    report = {'status': 'not_run', 'started_utc': datetime.now(timezone.utc).isoformat(), 'dry_run': dry_run,
              'amendment_kind': 'arena_volume_45_percent', 'resumed_after_mesh_import': True, 'maps': [],
              'registration_invoked': False, 'travel_invoked': False, 'runtime_python': False,
              'gameplay_tested': False, 'materials_rebuilt': False, 'installed_assets_modified': False,
              'native_reload_adaptations': ['Scalar RGBA replaces temporary Color wrapper addresses',
                  'Aerial depth may reload at origin from its -800 cm editor position; no fog setter is called',
                  'Exact empty untagged SceneRigCameraManager_0 may be engine-created; never deleted'],
              'mesh_slot_history': 'Original import copied/restored full slot values, but did not record scalar slot names. Resume proves current slots stay unchanged; no retroactive scalar-before claim.'}
    try:
        if type(dry_run) is not bool:
            raise ValueError('dry_run must be a JSON boolean')
        plan = stage.build_plan()
        stage._validate_sources(plan)
        source, prior = validate_failed_attempt(stage, receipt, plan)
        if stage.SUCCESS.exists():
            raise RuntimeError('Expansion already has a successful result; never apply the scale twice')
        report.update(plan=plan, plan_sha256=stage.plan_hash(plan), resumed_from={'report': str(source), 'sha256': stage.digest(source)},
                      predecessor_roof_success=prior['predecessor_roof_success'], content_before=prior['content_before'],
                      material_hashes_before=prior['material_hashes_before'])
        import unreal
        guard = module('_bb_resume_expansion_guard', 'Tools/load_hlck_dungeon.py')
        dungeon = module('_bb_resume_expansion_dungeon', 'Tools/stage_hlck_dungeon.py')
        registrar = module('_bb_resume_expansion_registration', 'Tools/register_hlck_dungeon.py')
        importer = module('_bb_resume_expansion_importer', 'Mod/Tools/import_sources.py')
        roof = module('_bb_resume_expansion_roof', 'Tools/stage_hlck_pyramid_net.py')
        report['active_mod'] = guard.require_editor(unreal)
        guard.require_clean(unreal)
        levels = unreal.EditorLevelLibrary
        original = roof.world_path(levels.get_editor_world())
        if original not in stage.MAPS:
            raise RuntimeError('Open an exact owned arena map for resumed expansion')
        report['original_world'] = original
        report['engine'] = str(unreal.SystemLibrary.get_engine_version())
        allowed = {str(file.relative_to(stage.CONTENT.resolve())) for file in stage.allowed_files(plan)}
        current = registrar.hashes(stage.CONTENT, stage.digest)
        current_content_at_start = dict(current)
        if any(current.get(path) != prior['content_before'].get(path) for path in set(current) | set(prior['content_before']) if path not in allowed):
            raise RuntimeError('Content outside the failed attempt package allowlist changed')
        if (registrar.metadata(registrar.KIT_CONTENT, '.umap') != prior['installed_map_metadata_before']
                or any(stage.digest(Path(path)) != digest for path, digest in prior['installed_database_hashes_before'].items())):
            raise RuntimeError('Installed native maps/databases changed after the failed import')
        report['registration_before'] = registrar.verified_saved_registration(unreal, dungeon)
        if report['registration_before'] != prior['registration_before']:
            raise RuntimeError('Native registration differs from the failed attempt')
        report['mesh_slots_resume_before'] = {}
        for entry in plan['changed_meshes']:
            asset = unreal.EditorAssetLibrary.load_asset(entry['destination'])
            if not isinstance(asset, unreal.StaticMesh):
                raise RuntimeError('Expected the exact already-imported native mesh')
            importer._owned(unreal, asset)
            if (unreal.EditorAssetLibrary.get_metadata_tag(asset, importer.META_HASH) != entry['sha256_after']
                    or unreal.EditorAssetLibrary.get_metadata_tag(asset, importer.META_REVISION) != importer.REVISION):
                raise RuntimeError('Existing mesh is not at the exact failed-import target source: ' + entry['destination'])
            report['mesh_slots_resume_before'][entry['destination']] = stage.mesh_slots(asset)
        for previous in prior['maps']:
            guard.require_clean(unreal)
            if not levels.load_level(previous['path']):
                raise RuntimeError('Could not open exact saved baseline map')
            world, actors = roof.validate_map_ownership(unreal, previous['path'])
            before = stage.snapshot(unreal, actors)
            if stage.canonical_snapshot(before) != stage.canonical_snapshot(previous['actors_before']):
                raise RuntimeError('Current actor/components differ from the precisely qualified failed-import snapshot')
            selected = stage.match_plan(before, plan, 'old')
            if str(world.get_world_settings().get_editor_property('default_game_mode')) != previous['game_mode_before']:
                raise RuntimeError('Native game mode changed after failed import')
            item = {'path': previous['path'], 'sha256_before': previous['sha256_before'], 'actors_before': before,
                    'game_mode_before': previous['game_mode_before'], 'geometry_before': previous['geometry_before'],
                    'geometry_before_evidence': str(source), 'matching_current_actor_count': len(selected)}
            report['maps'].append(item)
        if not dry_run:
            report['package_backups'] = []
            for item in prior['package_backups']:
                destination = directory / 'backups' / Path(item['path']).relative_to(stage.CONTENT.resolve())
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item['backup'], str(destination))
                if stage.digest(destination) != item['sha256']:
                    raise RuntimeError('Copied original pre-expansion backup failed verification')
                report['package_backups'].append({'path': item['path'], 'backup': str(destination), 'sha256': item['sha256']})
            for item in report['maps']:
                item['backup'] = str(directory / 'backups' / stage.map_file(item['path']).relative_to(stage.CONTENT))
            report['status'] = 'backed_up'
            stage.write(target, report)
            for item in report['maps']:
                guard.require_clean(unreal)
                if not levels.load_level(item['path']):
                    raise RuntimeError('Could not reopen exact expansion destination')
                world, actors = roof.validate_map_ownership(unreal, item['path'])
                current = stage.snapshot(unreal, actors)
                if stage.canonical_snapshot(current) != stage.canonical_snapshot(item['actors_before']):
                    raise RuntimeError('A scene property changed before resumed transformation')
                selected = stage.match_plan(current, plan, 'old')
                indexed = {actor.get_path_name(): actor for actor in actors}
                for path, entry in selected.items():
                    actor, old, new = indexed[path], entry['old'], entry['new']
                    if new['location'] != old['location']:
                        actor.set_actor_location(unreal.Vector(*new['location']), False, True)
                    if new['rotation'] != old['rotation']:
                        actor.set_actor_rotation(unreal.Rotator(pitch=new['rotation'][0], yaw=new['rotation'][1], roll=new['rotation'][2]), True)
                    if new['scale'] != old['scale']:
                        actor.set_actor_scale3d(unreal.Vector(*new['scale']))
                actors = list(levels.get_all_level_actors())
                after = stage.snapshot(unreal, actors)
                changed = stage.compare_preservation(current, after, selected)
                stage.match_plan(after, plan, 'new')
                item['geometry_pre_save'] = stage.geometry_audit(unreal, world, actors, plan['dimensions_after'])
                if (str(world.get_world_settings().get_editor_property('default_game_mode')) != item['game_mode_before']
                        or any(package.get_path_name() != item['path'] for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
                        or unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()):
                    raise RuntimeError('Unexpected game mode or dirty packages before resumed save')
                if not levels.save_current_level() or not levels.load_level(item['path']):
                    raise RuntimeError('Could not save and reload the exact expanded map')
                world, actors = roof.validate_map_ownership(unreal, item['path'])
                saved = stage.snapshot(unreal, actors)
                stage.compare_preservation(current, saved, selected)
                stage.match_plan(saved, plan, 'new')
                if str(world.get_world_settings().get_editor_property('default_game_mode')) != item['game_mode_before']:
                    raise RuntimeError('Native game mode changed after saved reload')
                item.update(sha256_after=stage.digest(stage.map_file(item['path'])), saved_reloaded=True,
                    unrelated_actors_preserved=True, actor_identity_and_components_preserved=True,
                    game_mode_preserved=True, transformed_actor_count=changed, preserved_actor_count=len(stage.canonical_snapshot(current)),
                    geometry_after=stage.geometry_audit(unreal, world, actors, plan['dimensions_after']))
                stage.write(target, report)
        if not levels.load_level(original):
            raise RuntimeError('Could not restore the original clean owned map')
        report['dirty_after'] = guard.require_clean(unreal)
        after_content = registrar.hashes(stage.CONTENT, stage.digest)
        if any(after_content.get(path) != prior['content_before'].get(path) for path in set(after_content) | set(prior['content_before']) if path not in allowed):
            raise RuntimeError('Unrelated content/material bytes changed while resuming')
        if dry_run and after_content != current_content_at_start:
            raise RuntimeError('Native package bytes changed during resumed dry run')
        for entry in plan['changed_meshes']:
            if stage.mesh_slots(unreal.EditorAssetLibrary.load_asset(entry['destination'])) != report['mesh_slots_resume_before'][entry['destination']]:
                raise RuntimeError('Current native material slots changed while resuming')
        if (registrar.metadata(registrar.KIT_CONTENT, '.umap') != prior['installed_map_metadata_before']
                or any(stage.digest(Path(path)) != digest for path, digest in prior['installed_database_hashes_before'].items())):
            raise RuntimeError('Installed native maps/databases changed while resuming')
        report['registration_after'] = registrar.verified_saved_registration(unreal, dungeon)
        if report['registration_after'] != report['registration_before']:
            raise RuntimeError('Native registration changed while resuming')
        report.update(status='ready' if dry_run else 'staged', preservation_verified=True, materials_preserved=True,
            mesh_slots_preserved_during_resume=True, original_world_restored=True,
            finished_utc=datetime.now(timezone.utc).isoformat(),
            changed_content_files=sorted(path for path in set(after_content) | set(prior['content_before']) if after_content.get(path) != prior['content_before'].get(path)))
        if not dry_run:
            report['saved_package_hashes'] = {str(file): stage.digest(file) for file in stage.allowed_files(plan)}
        stage.write(target, report)
        if not dry_run:
            stage.write(stage.SUCCESS, {'report': str(target), 'sha256': stage.digest(target)})
    except Exception:
        report.update(status='failed', error=traceback.format_exc(), recovery='Preserve open editor and immutable attempts/backups; no automatic rollback or package discard occurred.')
        stage.write(target, report)
    return {'status': report['status'], 'report': str(target), 'dry_run': dry_run, 'runtime_tested': False}


if __name__ == '__main__':
    RESULT = run(BRIDGE_ARGS['receipt'], BRIDGE_ARGS.get('dry_run', True))

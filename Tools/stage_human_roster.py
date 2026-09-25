"""Stage owned human cosmetics without changing the active game configuration.

In CharacterLab, bridge operation=inventory traces ALL saved cosmetic, flight and
team-material roots together. Outside Unreal, --operation plan verifies that
inventory; --operation copy exclusively creates missing target files. In the
main editor, operation=stage creates a NEW BBHumanRiderRoster from copied assets
and explicit, rendered alignment values. No mode enables the roster or plugins.

Alignment JSON: {"BB_AthleteA": {"location": [0,0,0], "rotation": [0,0,0],
"scale": [1,1,1]}, "BB_AthleteB": {...}}. Rotation is pitch/yaw/roll in degrees,
relative to the rider's skeletal body component, not the world or capsule.
Use measured values; the example is a format, not a fitted transform.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import importlib.util
import json
import math
import os
import shutil
import subprocess
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / '.local/CharacterLab'
TARGET = ROOT / 'DevelopmentHarness/Content'
PROJECT = ROOT / 'DevelopmentHarness/BasketbroomDev.uproject'
NAMES = ('BB_AthleteA', 'BB_AthleteB')
OWNER = 'Basketbroom.HumanRoster.v1'
COSMETIC_OWNER = 'Basketbroom.HumanCosmetic.v1'
ASSET_SUFFIXES = ('.uasset', '.umap', '.uexp', '.ubulk', '.uptnl')
PREFIX = '/Game/BasketbroomHumans/'
ALLOWED_ROOTS = tuple(PREFIX + part + '/' for part in ('Assembled', 'Cosmetics', 'Flightwear', 'Flight'))
DEFAULT_ROSTER = PREFIX + 'Runtime/DA_BB_HumanRoster'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


planner = module('bb_roster_migration_planner', 'plan_human_migration.py')
digest, contained = planner.digest, planner.contained


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, data):
    path = contained(Path(path), LAB)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')
    os.replace(temporary, path)
    return str(path)


def receipt_path(kind):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '-' + uuid.uuid4().hex[:8]
    return LAB / 'roster-receipts' / (stamp + '-' + kind) / 'result.json'


def clean_editor(ue, expected, allowed_dirty=()):
    actual = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.get_project_file_path())).resolve()
    if actual != expected.resolve() or not ue.SystemLibrary.get_engine_version().startswith('5.8.'):
        raise RuntimeError('Expected this exact UE5.8 project: ' + str(expected))
    if ue.get_editor_subsystem(ue.LevelEditorSubsystem).is_in_play_in_editor():
        raise RuntimeError('Stop Play before staging human assets')
    dirty = list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages()) + list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    unrelated = [p.get_path_name() for p in dirty if p.get_path_name() not in allowed_dirty]
    if unrelated:
        raise RuntimeError('Save current work before staging: ' + str(unrelated))


def package_name(value):
    value = str(value).split('.')[0]
    if not value.startswith(ALLOWED_ROOTS) or any(p in ('.', '..', '') for p in value[1:].split('/')):
        raise ValueError('Package is outside owned runtime source roots: ' + value)
    return value


def cosmetic_inputs():
    result = {}
    for name in NAMES:
        path = LAB / ('cosmetic-' + name + '.json')
        data = read(path)
        if data.get('owner') != COSMETIC_OWNER or data.get('character') != name or not data.get('assets_saved') or not data.get('existing_asset_bytes_preserved'):
            raise ValueError('Expected a saved, preserved cosmetic receipt for ' + name)
        if data.get('revision') not in ('r2', 'r3'):
            raise ValueError('The rejected initial flightwear is not a runtime candidate')
        actor = data['actor_class']
        blueprint = package_name(data['blueprint'])
        if package_name(actor) != blueprint or not actor.endswith('_C'):
            raise ValueError('Cosmetic generated-class path differs from its Blueprint')
        animation = data.get('flight_animation', data.get('animation'))
        body = data.get('body_component_name', data.get('body_component'))
        if not animation or not body or not data.get('garments'):
            raise ValueError('Missing exact animation/body/garment contract for ' + name)
        roots = set(package_name(p) for p in data['dependency_roots'])
        roots.update((blueprint, package_name(animation)))
        garments = []
        for item in data['garments']:
            binding = {
                'component_name': item.get('component_name', item.get('component')),
                'material_slot_name': item.get('material_slot_name', item.get('material_slot')),
                'material_slot_index': item['material_slot_index'],
                'teal_material': item.get('teal_material', item.get('mint_material')),
                'copper_material': item['copper_material']}
            if not binding['component_name'] or not binding['material_slot_name'] or binding['material_slot_index'] < 0:
                raise ValueError('Missing exact garment component/slot/index')
            roots.update(package_name(binding[key]) for key in ('teal_material', 'copper_material'))
            garments.append(binding)
        result[name] = {'receipt': str(path), 'receipt_sha256': digest(path), 'revision': data['revision'],
                        'actor_class': actor, 'blueprint': blueprint, 'body_component_name': body,
                        'flight_animation': animation, 'garments': garments, 'dependency_roots': sorted(roots)}
    return result


def dependency_edges(registry, package, options):
    """None means no dependency node, not a verified empty dependency list.

    IAssetRegistry::K2_GetDependencies returns the underlying bool as an
    optional Python result. AssetRegistryState.cpp returns true for an existing
    node even when its selected edges are empty; a missing node returns false.
    """
    edges, unresolved = {}, []
    for kind, option in options.items():
        value = registry.get_dependencies(package, option)
        if value is None:
            unresolved.append(kind)
        edges[kind] = sorted(str(p) for p in (value or []))
    return edges, unresolved


def inventory():
    import unreal as ue
    clean_editor(ue, LAB / 'BasketbroomCharacterLab.uproject')
    characters = cosmetic_inputs()
    lib = ue.EditorAssetLibrary
    for item in characters.values():
        asset = lib.load_asset(item['blueprint'])
        if not isinstance(asset, ue.Blueprint) or lib.get_metadata_tag(asset, 'BB.Generator') != COSMETIC_OWNER:
            raise RuntimeError('Expected the saved owned cosmetic Blueprint')
        if asset.generated_class().get_path_name() != item['actor_class']:
            raise RuntimeError('Generated cosmetic class does not match its receipt')
    roots = sorted({p for item in characters.values() for p in item['dependency_roots']})
    registry = ue.AssetRegistryHelpers.get_asset_registry()
    # Just-saved packages can have an asset row before their on-disk dependency
    # node is refreshed. Refresh only our owned source roots, never saving or
    # changing their assets, before treating the registry as an inventory.
    scanned_roots = [p.rstrip('/') for p in ALLOWED_ROOTS]
    registry.scan_paths_synchronous(scanned_roots, force_rescan=True)
    options = {kind: ue.AssetRegistryDependencyOptions(include_soft_package_references=kind == 'soft',
               include_hard_package_references=kind == 'hard', include_searchable_names=False,
               include_soft_management_references=False, include_hard_management_references=False)
               for kind in ('hard', 'soft')}
    graph, rows, external, guidelines, unresolved = {}, [], {}, [], []
    pending = list(roots)
    while pending:
        package = pending.pop()
        if package in graph:
            continue
        package_name(package)
        edges, unavailable = dependency_edges(registry, package, options)
        if unavailable:
            unresolved.append({'package': package, 'query_kinds': unavailable})
        graph[package] = edges
        data = registry.get_assets_by_package_name(package) or []
        base = contained(LAB / 'Content' / package.removeprefix('/Game/'), LAB / 'Content')
        files = [base.with_suffix(suffix) for suffix in ASSET_SUFFIXES if base.with_suffix(suffix).is_file()]
        rows.append({'package': package, 'asset_classes': [str(a.asset_class_path) for a in data],
                     'registered_asset_exists': bool(data),
                     'saved_package_exists': any(p.suffix in ('.uasset', '.umap') for p in files),
                     'files': [{'path': str(p), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in files]})
        # Read the exact exported mesh guidelines, rather than inferring needed
        # rendering settings from the authoring project's entire configuration.
        for asset_data in data:
            if str(asset_data.asset_class_path).endswith('.SkeletalMesh'):
                mesh = asset_data.get_asset()
                for field in ('asset_user_data', 'asset_user_data_editor_only'):
                    for user_data in mesh.get_editor_property(field):
                        if user_data and user_data.get_class().get_name() == 'AssetGuideline':
                            guidelines.append({'mesh': mesh.get_path_name(),
                                'guideline': str(user_data.get_editor_property('guideline_name')),
                                'plugins': [str(p) for p in user_data.get_editor_property('plugins')],
                                'settings': [{key: str(setting.get_editor_property(key)) for key in ('section', 'key', 'value', 'filename')}
                                             for setting in user_data.get_editor_property('project_settings')]})
        for kind, refs in edges.items():
            for ref in refs:
                if ref.startswith('/Game/'):
                    pending.append(ref)
                else:
                    external.setdefault(ref, set()).add(kind)
        if len(graph) > 5000:
            raise RuntimeError('Unexpected dependency graph exceeding 5000 local packages')
    hard, pending = set(), list(roots)
    while pending:
        package = pending.pop()
        if package in hard:
            continue
        hard.add(package)
        pending.extend(p for p in graph[package]['hard'] if p.startswith('/Game/'))
    missing = [p['package'] for p in rows if not p['saved_package_exists']]
    unregistered = [p['package'] for p in rows if not p['registered_asset_exists']]
    result = {'owner': OWNER, 'operation': 'inventory',
              'status': 'incomplete_dependency_inventory' if unresolved or missing or unregistered else 'inventoried',
              'characters': characters,
              'roots': roots, 'packages': sorted(rows, key=lambda p: p['package']), 'dependency_graph': graph,
              'source_roots_rescanned': scanned_roots, 'unresolved_dependency_queries': unresolved,
              'missing_source_packages': missing, 'unregistered_source_packages': unregistered,
              'hard_closure': sorted(hard), 'soft_only_closure': sorted(set(graph) - hard),
              'external_packages': [{'package': p, 'reference_kinds': sorted(k)} for p, k in sorted(external.items())],
              'mesh_asset_guidelines': guidelines, 'assets_saved': False, 'files_copied': 0}
    clean_editor(ue, LAB / 'BasketbroomCharacterLab.uproject')
    output = receipt_path('inventory')
    write(output, result)
    write(LAB / 'roster-inventory.json', result)
    return {'status': result['status'], 'receipt': str(output), 'inventory': str(LAB / 'roster-inventory.json'),
            'packages': len(rows), 'roots': len(roots), 'guidelines': len(guidelines),
            'unresolved_dependency_queries': unresolved, 'missing_source_packages': missing,
            'unregistered_source_packages': unregistered}


def validate_alignment(path, names=NAMES):
    values = read(path)
    if set(values) != set(names):
        raise ValueError('Alignment must explicitly name each candidate exactly once')
    for name, transform in values.items():
        if set(transform) != {'location', 'rotation', 'scale'}:
            raise ValueError('Expected location, rotation and scale for ' + name)
        for key, vector in transform.items():
            if not isinstance(vector, list) or len(vector) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector):
                raise ValueError('Expected three finite numeric values for ' + name + '.' + key)
        if min(transform['scale']) <= 0:
            raise ValueError('Human alignment scale must be positive')
    return values


def file_records(data):
    records, destinations = [], set()
    for package in data['packages']:
        name = package_name(package['package'])
        base = contained(LAB / 'Content' / name.removeprefix('/Game/'), LAB / 'Content')
        headers = []
        if not package['files']:
            raise RuntimeError('Missing source package files: ' + name)
        for item in package['files']:
            source = contained(Path(item['path']), LAB / 'Content')
            if source.with_suffix('') != base or source.suffix not in ASSET_SUFFIXES:
                raise ValueError('Package/file path mismatch: ' + str(source))
            if not source.is_file() or digest(source) != item['sha256']:
                raise RuntimeError('Source changed or disappeared since inventory: ' + str(source))
            destination = contained(TARGET / source.relative_to(LAB / 'Content'), TARGET)
            if destination in destinations:
                raise ValueError('Duplicate target file in inventory')
            destinations.add(destination)
            if destination.exists() and (not destination.is_file() or digest(destination) != item['sha256']):
                raise RuntimeError('Refusing to overwrite a different target: ' + str(destination))
            records.append({'source': str(source), 'destination': str(destination), 'sha256': item['sha256'],
                            'bytes': source.stat().st_size, 'state': 'identical' if destination.exists() else 'absent'})
            if source.suffix in ('.uasset', '.umap'):
                headers.append(source)
        if len(headers) != 1 or planner.package_flags(headers[0], name)['editor_only']:
            raise ValueError('Expected one saved runtime package header: ' + name)
    return records


def checked_inventory(path):
    path = contained(Path(path), LAB)
    data = read(path)
    if data.get('owner') != OWNER or data.get('status') != 'inventoried' or set(data.get('characters', {})) != set(NAMES):
        raise ValueError('Expected the combined human roster inventory')
    if any(data.get(key) for key in ('unresolved_dependency_queries', 'missing_source_packages', 'unregistered_source_packages')):
        raise ValueError('The source dependency inventory still has unresolved or missing packages')
    packages = {p['package'] for p in data['packages']}
    if set(data['roots']) - packages:
        raise ValueError('Inventory is missing a requested root')
    for item in data['characters'].values():
        source = contained(Path(item['receipt']), LAB)
        if digest(source) != item['receipt_sha256']:
            raise RuntimeError('Cosmetic receipt changed; refresh inventory before copying')
    return path, data, file_records(data)


def proposal(data, roster):
    external = {entry['package']: set(entry['reference_kinds']) for entry in data['external_packages']}
    requirements = planner.dependency_requirements(external)
    runtime, editor = set(), set()
    for item in requirements:
        if not item.get('plugin'):
            continue
        if item.get('module_type') in ('Editor', 'UncookedOnly', 'Developer', 'DeveloperTool'):
            editor.add(item['plugin'])
        else:
            runtime.add(item['plugin'])
    settings = {}
    for guideline in data['mesh_asset_guidelines']:
        runtime.update(guideline['plugins'])
        for setting in guideline['settings']:
            key = (setting['filename'], setting['section'], setting['key'])
            if key in settings and settings[key]['value'] != setting['value']:
                raise ValueError('Conflicting exported mesh guidelines: ' + str(key))
            settings[key] = setting
    plugins = [{'Name': p, 'Enabled': True} for p in sorted(runtime)]
    plugins.extend({'Name': p, 'Enabled': True, 'TargetAllowList': ['Editor']} for p in sorted(editor - runtime))
    asset = roster + '.' + roster.rsplit('/', 1)[-1]
    return {'external_requirements': requirements, 'uproject_plugin_entries': plugins,
            'default_engine_settings_from_exported_assets': list(settings.values()),
            'default_game_ini': ['[/Script/BasketbroomRuntime.BBRiderCharacter]', 'HumanRoster=' + asset,
                                 '[/Script/UnrealEd.ProjectPackagingSettings]',
                                 '+DirectoriesToAlwaysCook=(Path="' + roster.rsplit('/', 1)[0] + '")'],
            'cook_reason': 'Cook the new roster directory; its hard variant references carry cosmetics, animations and both team materials.',
            'rhi_note': 'The lab renders on DX12/SM6. The exported asset guidelines above are authoritative settings; this tool does not infer an SM6 or ray-tracing requirement.',
            'activation_applied': False, 'target_editor_load_and_cook_validated': False}


def plan(inventory_path=None, roster=DEFAULT_ROSTER):
    if not roster.startswith(PREFIX + 'Runtime/') or '.' in roster or '..' in roster:
        raise ValueError('Roster must be a new package below the owned Runtime directory')
    path, data, records = checked_inventory(inventory_path or LAB / 'roster-inventory.json')
    result = {'owner': OWNER, 'operation': 'plan', 'status': 'source_verified',
              'inventory': str(path), 'inventory_sha256': digest(path), 'source_project': str(LAB / 'BasketbroomCharacterLab.uproject'),
              'target_project': str(PROJECT), 'roster_package': roster, 'characters': data['characters'],
              'files': records, 'configuration_proposal': proposal(data, roster),
              'assets_copied': 0, 'game_activated': False}
    output = receipt_path('plan')
    write(output, result)
    write(LAB / 'roster-migration-plan.json', result)
    return {'status': result['status'], 'receipt': str(output), 'plan': str(LAB / 'roster-migration-plan.json'),
            'files': len(records), 'bytes': sum(r['bytes'] for r in records),
            'missing_target_files': sum(r['state'] == 'absent' for r in records)}


def require_target_editor_closed():
    # Inspect only Unreal process command lines and emit a Boolean. Lab may stay
    # open; only the exact target project must be offline while packages arrive.
    command = "$ErrorActionPreference='Stop'; $bbTarget='" + str(PROJECT).replace("'", "''") + "'; "
    command += "$bbBusy=@(Get-CimInstance Win32_Process -Filter \"Name='UnrealEditor.exe' OR Name='UnrealEditor-Cmd.exe'\" | Where-Object { $_.CommandLine -and ($_.CommandLine.Replace('/','\\').IndexOf($bbTarget,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or $_.CommandLine -match '(?i)BasketbroomDev\\.uproject') }); if($bbBusy.Count){'busy'}else{'closed'}"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, text=True, check=True)
    if result.stdout.strip() != 'closed':
        raise RuntimeError('Close the BasketbroomDev editor/commandlet before copying its packages')


def copy_exclusive(record):
    source, destination = Path(record['source']), Path(record['destination'])
    if digest(source) != record['sha256']:
        raise RuntimeError('Source changed before exclusive copy: ' + str(source))
    if destination.exists():
        if destination.is_file() and digest(destination) == record['sha256']:
            return False
        raise RuntimeError('Target changed before copy: ' + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation is the final race-safe no-overwrite check. An interrupted
    # partial file is retained and named in the receipt, never silently replaced.
    with source.open('rb') as input_stream, destination.open('xb') as output_stream:
        shutil.copyfileobj(input_stream, output_stream, 4 * 1024 * 1024)
        output_stream.flush()
        os.fsync(output_stream.fileno())
    if digest(destination) != record['sha256']:
        raise RuntimeError('Target hash did not match after copy: ' + str(destination))
    return True


def copy(plan_path=None):
    plan_path = contained(Path(plan_path or LAB / 'roster-migration-plan.json'), LAB)
    data = read(plan_path)
    if data.get('owner') != OWNER or data.get('status') != 'source_verified' or Path(data['target_project']).resolve() != PROJECT.resolve():
        raise ValueError('Expected this project\'s verified roster plan')
    inventory_path = contained(Path(data['inventory']), LAB)
    if digest(inventory_path) != data['inventory_sha256']:
        raise RuntimeError('Inventory changed; produce a fresh migration plan')
    _, _, records = checked_inventory(inventory_path)
    expected = [{k: r[k] for k in ('source', 'destination', 'sha256', 'bytes')} for r in data['files']]
    actual = [{k: r[k] for k in ('source', 'destination', 'sha256', 'bytes')} for r in records]
    if actual != expected:
        raise RuntimeError('Plan does not match the verified source inventory')
    require_target_editor_closed()
    output = receipt_path('copy')
    result = {'owner': OWNER, 'operation': 'copy', 'status': 'copying', 'plan': str(plan_path),
              'plan_sha256': digest(plan_path), 'created_files': [], 'identical_files': [],
              'game_activated': False, 'configuration_modified': False, 'current_file': None}
    write(output, result)
    try:
        for record in records:
            result['current_file'] = record
            write(output, result)
            created = copy_exclusive(record)
            result['created_files' if created else 'identical_files'].append(record)
        result.update(status='copied_pending_target_load', current_file=None)
    except Exception:
        result.update(status='failed_partial_copy_preserved', error=traceback.format_exc())
        raise
    finally:
        write(output, result)
    return {'status': result['status'], 'receipt': str(output), 'created_files': len(result['created_files']),
            'identical_files': len(result['identical_files']), 'game_activated': False}


def variant_values(variant):
    """Serialize values; Python wrappers for reflected structs compare identity.

    StructBase.export_text is defined in installed PyWrapperStruct.cpp. Using
    it only for FTransform preserves the actual native translation/quaternion/
    scale representation, without relying on suppressed NativeBreakFunc APIs.
    """
    def object_path(value):
        return value.get_path_name() if value is not None else None
    garments = []
    for binding in variant.get_editor_property('garments'):
        garments.append({
            'component_name': str(binding.get_editor_property('component_name')),
            'material_slot_name': str(binding.get_editor_property('material_slot_name')),
            'material_slot_index': int(binding.get_editor_property('material_slot_index')),
            'teal_material': object_path(binding.get_editor_property('teal_material')),
            'copper_material': object_path(binding.get_editor_property('copper_material'))})
    return {'actor_class': object_path(variant.get_editor_property('actor_class')),
            'body_component_name': str(variant.get_editor_property('body_component_name')),
            'flight_animation': object_path(variant.get_editor_property('flight_animation')),
            'relative_transform': variant.get_editor_property('relative_transform').export_text(),
            'garments': garments}


def stage(alignment_path, plan_path=None, recover=False):
    import unreal as ue
    plan_path = contained(Path(plan_path or LAB / 'roster-migration-plan.json'), LAB)
    data = read(plan_path)
    if data.get('owner') != OWNER or data.get('status') != 'source_verified':
        raise ValueError('Expected a verified roster migration plan')
    inventory_path = contained(Path(data['inventory']), LAB)
    if digest(inventory_path) != data['inventory_sha256']:
        raise RuntimeError('Inventory changed after plan creation')
    _, source_inventory, files = checked_inventory(inventory_path)
    if data['characters'] != source_inventory['characters'] or Path(data['target_project']).resolve() != PROJECT.resolve():
        raise RuntimeError('Roster plan contracts differ from their verified source inventory')
    if any(r['state'] != 'identical' for r in files):
        raise RuntimeError('Every target package must match the verified source before roster staging')
    alignment = validate_alignment(alignment_path)
    destination = data['roster_package']
    if not destination.startswith(PREFIX + 'Runtime/') or '.' in destination or '..' in destination:
        raise ValueError('Refusing an unowned roster package')
    clean_editor(ue, PROJECT, (destination,) if recover else ())
    lib = ue.EditorAssetLibrary
    target_base = contained(TARGET / destination.removeprefix('/Game/'), TARGET)
    if any(target_base.with_suffix(suffix).exists() for suffix in ASSET_SUFFIXES):
        raise RuntimeError('Preserve existing roster; choose a new package name')
    if not recover and lib.does_asset_exist(destination):
        raise RuntimeError('Preserve existing in-memory roster; inspect or recover the exact pending asset')
    roster_class = ue.load_class(None, '/Script/BasketbroomRuntime.BBHumanRiderRoster')
    if roster_class is None:
        raise RuntimeError('Build the current native module before staging its roster')
    variants = []
    for name in NAMES:
        item = data['characters'][name]
        actor = ue.load_class(None, item['actor_class'])
        animation = lib.load_asset(item['flight_animation'])
        blueprint = lib.load_asset(item['blueprint'])
        if actor is None or not isinstance(animation, ue.AnimSequence) or not isinstance(blueprint, ue.Blueprint):
            raise RuntimeError('Target failed to load this exact cosmetic/animation: ' + name)
        if blueprint.generated_class() != actor or blueprint.get_editor_property('status') not in (ue.BlueprintStatus.BS_UP_TO_DATE, ue.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS):
            raise RuntimeError('Target cosmetic Blueprint requires compilation/repair: ' + name)
        variant = ue.BBHumanRiderVariant()
        variant.set_editor_property('actor_class', actor)
        variant.set_editor_property('body_component_name', item['body_component_name'])
        variant.set_editor_property('flight_animation', animation)
        fitted = alignment[name]
        transform = ue.Transform(location=ue.Vector(*fitted['location']), rotation=ue.Rotator(*fitted['rotation']), scale=ue.Vector(*fitted['scale']))
        variant.set_editor_property('relative_transform', transform)
        garments = []
        for row in item['garments']:
            binding = ue.BBHumanGarmentBinding()
            for key in ('component_name', 'material_slot_name', 'material_slot_index'):
                binding.set_editor_property(key, row[key])
            for key in ('teal_material', 'copper_material'):
                material = lib.load_asset(row[key])
                if not isinstance(material, ue.MaterialInterface):
                    raise RuntimeError('Target garment material failed to load: ' + row[key])
                binding.set_editor_property(key, material)
            garments.append(binding)
        variant.set_editor_property('garments', garments)
        variants.append(variant)
    # Loading may reveal dirty assets needing their own deliberate repair. Never
    # save those packages as a side effect of creating this one roster.
    clean_editor(ue, PROJECT, (destination,) if recover else ())
    directory, name = destination.rsplit('/', 1)
    if recover:
        asset = lib.load_asset(destination)
        if (asset is None or asset.get_class() != roster_class
                or asset.get_path_name() != destination + '.' + name
                or asset.get_outermost().get_path_name() != destination):
            raise RuntimeError('Recovery requires the exact unsaved native roster asset')
        if lib.get_metadata_tag(asset, 'BB.Generator') not in ('', OWNER):
            raise RuntimeError('Recovery refuses an asset owned by another generator')
        if lib.get_metadata_tag(asset, 'BB.InventorySHA256') not in ('', data['inventory_sha256']):
            raise RuntimeError('Recovery inventory differs from the asset provenance')
    else:
        factory = ue.DataAssetFactory()
        factory.set_editor_property('data_asset_class', roster_class)
        asset = ue.AssetToolsHelpers.get_asset_tools().create_asset(name, directory, roster_class, factory)
        if asset is None:
            raise RuntimeError('Could not create the new roster data asset')
        asset.set_editor_property('variants', variants)
    readback = list(asset.get_editor_property('variants'))
    actual_values = [variant_values(value) for value in readback]
    expected_values = [variant_values(value) for value in variants]
    if actual_values != expected_values:
        raise RuntimeError('Roster variant readback differs; asset remains unsaved for inspection')
    lib.set_metadata_tag(asset, 'BB.Generator', OWNER)
    lib.set_metadata_tag(asset, 'BB.InventorySHA256', data['inventory_sha256'])
    if not lib.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError('Could not save the exact new roster asset')
    clean_editor(ue, PROJECT)
    output = receipt_path('stage')
    result = {'owner': OWNER, 'operation': 'recover' if recover else 'stage', 'status': 'staged_pending_runtime_validation',
              'roster': asset.get_path_name(), 'characters': list(NAMES), 'alignment': alignment,
              'verified_variant_values': actual_values, 'unsaved_existing_asset_recovered': recover,
              'alignment_sha256': digest(Path(alignment_path)), 'alignment_status': 'explicit_candidate_pending_runtime_render',
              'plan_sha256': digest(plan_path),
              'configuration_proposal': data['configuration_proposal'], 'game_activated': False}
    write(output, result)
    return {'status': result['status'], 'receipt': str(output), 'roster': result['roster'], 'game_activated': False}


if __name__ == '__main__':
    if 'BRIDGE_ARGS' in globals():
        args = globals()['BRIDGE_ARGS']
        if args.get('operation') == 'inventory':
            RESULT = inventory()
        elif args.get('operation') in ('stage', 'recover'):
            RESULT = stage(args['alignment'], args.get('plan'), args.get('operation') == 'recover')
        else:
            raise ValueError('Bridge supports inventory, stage or recover; plan/copy run outside Unreal')
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--operation', choices=('plan', 'copy'), default='plan')
        parser.add_argument('--inventory', type=Path)
        parser.add_argument('--plan', type=Path)
        parser.add_argument('--roster', default=DEFAULT_ROSTER)
        args = parser.parse_args()
        result = plan(args.inventory, args.roster) if args.operation == 'plan' else copy(args.plan)
        print(json.dumps(result, indent=2))

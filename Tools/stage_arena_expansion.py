"""Targeted UE5.8 arena-volume amendment of existing saved maps and source meshes.

The default is read-only dry_run=True. Execute with {"dry_run": false,
"execute": true}. This never creates actors/maps, rebuilds materials, changes
native game modes, or imports Creator Kit packages. Original byte backups and
before/in-memory/saved collision receipts remain in an immutable attempt folder.
"""
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import traceback
import types
import uuid

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / 'DevelopmentHarness/Plugins/Basketbroom/Content'
MAPS = ('/Basketbroom/Maps/BB_Regulation', '/Basketbroom/Maps/BB_Arena')
SUCCESS = ROOT / '.local/arena-expansion-success.json'
# The earlier author named these same 18 unchanged actors Crown beacons.
# Only witnessed historic labels are aliases; class/tags/mesh/pose still match.
LABEL_ALIASES = {'Eave beacon %s %s' % (side, index): 'Crown beacon %s %s' % (side, index)
                 for side in (-1, 1) for index in range(9)}
LABEL_ALIASES['Continuous closed-arena rebound net'] = 'Continuous open-crown rebound net'


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


contract = module('_bb_standalone_expansion_contract', 'Tools/stage_hlck_arena_expansion.py')
dimensions = module('_bb_standalone_expansion_dimensions', 'Tools/arena_dimensions.py')
near, digest, write = contract.near, contract.digest, contract.write


def validate_plan(plan):
    contract.validate_plan(plan)
    if len(plan['changed_meshes']) != 10:
        raise ValueError('Standalone expansion requires the reviewed ten source meshes')
    return plan


def asset_file(package, plan):
    allowed = set(MAPS) | {item['destination'] for item in plan['changed_meshes']}
    if package not in allowed:
        raise ValueError('Package is outside the exact standalone expansion allowlist')
    path = (CONTENT / (package[len('/Basketbroom/'):] + ('.umap' if package in MAPS else '.uasset'))).resolve()
    path.relative_to(CONTENT.resolve())
    return path


def content_hashes():
    return {p.relative_to(CONTENT).as_posix(): digest(p) for p in CONTENT.rglob('*')
            if p.is_file() and p.suffix.lower() in ('.uasset', '.umap', '.uexp', '.ubulk')}


def check_file_scope(before, after, allowed):
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    unexpected = set(changed)-set(allowed)
    if unexpected:
        raise RuntimeError('Saved content changed outside the exact expansion allowlist: '+str(sorted(unexpected)))
    return changed


def object_path(value):
    return value.get_path_name() if value else None


def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def rotation(value):
    return [float(value.pitch), float(value.yaw), float(value.roll)]


def prop(actor, name):
    return actor.get_editor_property(name)


def color_channels(color):
    return [int(color.r), int(color.g), int(color.b), int(color.a)]


def snapshot(unreal, actors):
    result = {}
    for actor in actors:
        transform = actor.get_actor_transform()
        record = dict(label=actor.get_actor_label(), **{'class': actor.get_class().get_path_name()},
                      location=xyz(transform.translation), rotation=rotation(actor.get_actor_rotation()),
                      scale=xyz(transform.scale3d), tags=[str(t) for t in prop(actor, 'tags')],
                      folder=str(actor.get_folder_path()))
        root = prop(actor, 'root_component')
        components = {}
        for component in actor.get_components_by_class(unreal.ActorComponent):
            item = {'class': component.get_class().get_path_name()}
            if isinstance(component, unreal.SceneComponent):
                item.update(mobility=str(prop(component, 'mobility')), visible=bool(prop(component, 'visible')),
                            hidden_in_game=bool(prop(component, 'hidden_in_game')))
                if component != root:
                    item.update(relative_location=xyz(prop(component, 'relative_location')),
                                relative_rotation=rotation(prop(component, 'relative_rotation')),
                                relative_scale=xyz(prop(component, 'relative_scale3d')))
            if isinstance(component, unreal.PrimitiveComponent):
                item.update(profile=str(component.get_collision_profile_name()),
                            collision=str(component.get_collision_enabled()), cast_shadow=bool(prop(component, 'cast_shadow')),
                            physical_material=object_path(prop(prop(component, 'body_instance'), 'phys_material_override')))
            if isinstance(component, unreal.MeshComponent):
                item['materials'] = [object_path(component.get_material(i)) for i in range(component.get_num_materials())]
            if isinstance(component, unreal.StaticMeshComponent):
                item['mesh'] = object_path(prop(component, 'static_mesh'))
            if isinstance(component, unreal.TextRenderComponent):
                item['text'] = {key: str(prop(component, key)) for key in
                                ('text', 'world_size', 'horizontal_alignment', 'vertical_alignment')}
                item['text']['text_render_color'] = color_channels(prop(component, 'text_render_color'))
            components[component.get_name()] = item
        record['components'] = components
        mesh = actor.get_component_by_class(unreal.StaticMeshComponent)
        record['mesh'] = object_path(prop(mesh, 'static_mesh')) if mesh else None
        if actor.actor_has_tag('BB.Ball') or actor.actor_has_tag('BB.Bot'):
            record['home'] = xyz(prop(actor, 'Home'))
        if actor.actor_has_tag('BB.Ball'):
            record['kind'] = int(prop(actor, 'Kind'))
        if actor.actor_has_tag('BB.Bot'):
            record['bot_identity'] = [int(prop(actor, name)) for name in ('Team', 'Slot', 'PlayerRole')]
        if isinstance(actor, unreal.PlayerStart):
            record['player_start_tag'] = str(prop(actor, 'player_start_tag'))
        result[actor.get_path_name()] = record
    return result


def match_plan(records, plan, phase='old'):
    by_label = {}
    for path, record in records.items():
        if 'BB.Generated' in record['tags']:
            by_label.setdefault(record['label'], []).append((path, record))
    selected = {}
    for entry in plan['actors']:
        if entry['label'] == 'BB Player Start':
            # Training adopts this actor; regulation may retain the original
            # ground-level anchor. Preserve either saved native arrangement.
            continue
        labels = [entry['label']]
        if entry['label'] in LABEL_ALIASES:
            labels.append(LABEL_ALIASES[entry['label']])
        matches = [item for label in labels for item in by_label.get(label, [])]
        if len(matches) != 1:
            raise RuntimeError('Expected a unique original generated actor: '+entry['label'])
        path, record = matches[0]
        if record['class'] != entry['class'] or set(record['tags']) != {'BB.Generated'} | set(entry['tags']):
            raise RuntimeError('Generated actor class or ownership tags differ: '+entry['label'])
        # This exact native DirectionalLight's saved class default is 2.5 in
        # the observed UE5 regulation map. The offline recorder uses unit
        # defaults; preserve the verified light scale while moving its pose.
        if (entry['label'] == 'Twilight amber key' and entry['class'] == '/Script/Engine.DirectionalLight'
                and near(record['scale'], [2.5, 2.5, 2.5])):
            if entry['old']['scale'] != [1, 1, 1] or entry['new']['scale'] != [1, 1, 1]:
                raise RuntimeError('DirectionalLight source scale changed outside the observed default adaptation')
            entry = dict(entry)
            entry['old'], entry['new'] = dict(entry['old']), dict(entry['new'])
            entry['old']['scale'], entry['new']['scale'] = [2.5, 2.5, 2.5], [2.5, 2.5, 2.5]
        if record['folder'] != entry['folder']:
            raise RuntimeError('Generated actor folder differs: '+entry['label'])
        if entry['mesh']:
            expected = ('/Basketbroom/Art/Meshes/' if entry['mesh'].startswith('SM_BB_') else '/Engine/BasicShapes/')+entry['mesh']
            if (record['mesh'] or '').split('.')[0] != expected:
                raise RuntimeError('Generated actor mesh differs: '+entry['label'])
        for key in ('location', 'rotation', 'scale'):
            if not near(record[key], entry[phase][key], angular=key == 'rotation'):
                raise RuntimeError('Unexpected '+phase+' '+key+' on '+entry['label']+': '+str(record[key]))
        selected[path] = entry
    if len(selected) != len(plan['actors'])-1:
        raise RuntimeError('Every original venue actor except its adopted PlayerStart must match')
    return selected


def authored_values(relative, names, scale):
    tree = ast.parse((ROOT / relative).read_text(encoding='utf-8-sig'))
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id in names for target in node.targets)]
    values = {name: getattr(dimensions, name) for name in dir(dimensions) if name.isupper()}
    values.update(LINEAR_SCALE=scale, GOAL_PLANE_X=dimensions.BASELINE_GOAL_PLANE_X*scale)
    scope = {'dimensions': types.SimpleNamespace(**values)}
    exec(compile(ast.Module(body=assignments, type_ignores=[]), relative, 'exec'), scope)
    return scope


def training_layout(scale):
    game = authored_values('Tools/stage_game.py', {'PLAYER_START', 'BALLS'}, scale)
    roster = authored_values('Tools/stage_bots.py', {'ROSTER', 'ROLE_NAMES'}, scale)
    result = {'BB Training Player Start': dict(location=list(game['PLAYER_START']), home=None,
                                              category='start', kind=None, bot_identity=None)}
    for label, kind, point, size, material in game['BALLS']:
        result['BB '+label] = dict(location=list(point), home=list(point), category='ball', kind=kind, bot_identity=None)
    for slot, (team, role, home, target) in enumerate(roster['ROSTER'], 1):
        label = 'BB %s %02d %s' % ('Teal' if team == 0 else 'Copper', slot, roster['ROLE_NAMES'][role])
        result[label] = dict(location=list(home), home=list(home), category='bot', kind=None, bot_identity=[team, slot, role])
    return result


def match_training(records, map_path, phase='old'):
    old, new = training_layout(1.0), training_layout(dimensions.LINEAR_SCALE)
    selected = {}
    if map_path != MAPS[1]:
        # Only the explicitly authored regulation flight start moves. A native
        # BB Player Start remains a fully protected unrelated actor.
        rows = [(path, record) for path, record in records.items() if record['label'] == 'BB Regulation Player Start']
        if len(rows) > 1:
            raise RuntimeError('Ambiguous regulation PlayerStart')
        if rows:
            path, record = rows[0]
            expected = [-4400*(1.0 if phase == 'old' else dimensions.LINEAR_SCALE), 0, 1400]
            if record['class'] != '/Script/Engine.PlayerStart' or set(record['tags']) != {'BB.Regulation', 'BB.Spawn'} or not near(record['location'], expected):
                raise RuntimeError('Regulation start differs from its authoring contract; preserve it')
            selected[path] = dict(old=dict(location=[-4400, 0, 1400]), new=dict(location=[-4400*dimensions.LINEAR_SCALE, 0, 1400]))
        return selected
    for label, original in old.items():
        rows = [(path, record) for path, record in records.items() if record['label'] == label]
        if len(rows) != 1:
            raise RuntimeError('Training needs one existing authored actor: '+label)
        path, record = rows[0]
        expected = original if phase == 'old' else new[label]
        category = original['category']
        class_path = {'start': '/Script/Engine.PlayerStart', 'ball': '/Basketbroom/Blueprints/BP_BBBall.BP_BBBall_C',
                      'bot': '/Basketbroom/Blueprints/BP_BBBot.BP_BBBot_C'}[category]
        if record['class'] != class_path or 'BB.Gameplay' not in record['tags']:
            raise RuntimeError('Training identity differs: '+label)
        if category == 'ball' and ('BB.Ball' not in record['tags'] or record['kind'] != original['kind']):
            raise RuntimeError('Training ball identity differs: '+label)
        if category == 'bot' and ('BB.Bot' not in record['tags'] or record['bot_identity'] != original['bot_identity']):
            raise RuntimeError('Training roster identity differs: '+label)
        if not near(record['location'], expected['location']) or (expected['home'] is not None and not near(record['home'], expected['home'])):
            raise RuntimeError('Training actor is not at the expected '+phase+' home: '+label)
        fields = ('location', 'home') if category != 'start' else ('location',)
        selected[path] = {'old': {key: original[key] for key in fields}, 'new': {key: new[label][key] for key in fields}}
    return selected


def compare(before, after, geometry, training):
    if set(before) != set(after):
        raise RuntimeError('Actor identity changed; expansion cannot create, destroy or rename objects')
    changed = 0
    for path, original in before.items():
        expected = geometry.get(path) or training.get(path)
        allowed = set(expected['new']) if expected else set()
        current = after[path]
        for key in set(original) | set(current):
            if key not in allowed and original.get(key) != current.get(key):
                raise RuntimeError('Unrelated actor/component/material property changed: '+path+' / '+key)
        if expected:
            for key in allowed:
                if not near(current[key], expected['new'][key], angular=key == 'rotation'):
                    raise RuntimeError('Planned '+key+' did not persist: '+path)
            changed += expected['old'] != expected['new']
    return changed


def collision_audit(unreal, world, actors, d):
    def tagged(tag):
        values = [a for a in actors if a.actor_has_tag(tag)]
        if not values:
            raise RuntimeError('Missing collision group '+tag)
        return values
    rows = []
    def trace(label, start, end, expected=None, axis=None, coordinate=None):
        hit = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(*start), unreal.Vector(*end),
                    unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [], unreal.DrawDebugTrace.NONE, True)
        if expected is None:
            if hit is not None:
                raise RuntimeError('Expected an open collision bracket: '+label)
            rows.append(dict(name=label, clear=True, start=list(start), end=list(end)))
            return
        if hit is None:
            raise RuntimeError('Collision bracket escaped: '+label)
        value = hit.to_dict()
        if not value['blocking_hit'] or value['hit_actor'] not in expected:
            raise RuntimeError('Collision bracket hit the wrong actor: '+label)
        point = xyz(value['impact_point'])
        if coordinate is not None and abs(point[axis]-coordinate) > .8:
            raise RuntimeError('Collision surface has the wrong plane: '+label+' '+str(point))
        rows.append(dict(name=label, hit=object_path(value['hit_actor']), impact=point, start=list(start), end=list(end)))
    floor = tagged('BB.Floor')
    if len(floor) != 1:
        raise RuntimeError('Expected one trampoline collision floor')
    for x, y in ((0, 0), (d['half_x']*.94, d['half_y']*.91), (-d['half_x']*.94, -d['half_y']*.91)):
        trace('floor', (x, y, 80), (x, y, -80), floor, 2, 0)
    for axis, tag, extent in ((0, 'BB.Net.End', d['half_x']), (1, 'BB.Net.Side', d['half_y'])):
        walls = tagged(tag)
        if len(walls) != 2:
            raise RuntimeError('Expected two walls for '+tag)
        for sign in (-1, 1):
            expected = [a for a in walls if xyz(a.get_actor_location())[axis]*sign > 0]
            for reverse in (False, True):
                start, end = [0, 0, d['eave']*.47], [0, 0, d['eave']*.47]
                start[axis], end[axis] = sign*(extent-80), sign*(extent+80)
                if reverse: start, end = end, start
                trace(tag, start, end, expected, axis, sign*(extent+(30 if reverse else 0)))
    roof = module('_bb_standalone_expansion_roof_audit', 'Tools/stage_pyramid_net.py')
    roof.arena.HALF_WIDTH, roof.arena.BACKSTOP_X = d['half_y'], d['half_x']
    roof.arena.ROOFLINE, roof.arena.PYRAMID_APEX = d['eave'], d['apex']
    roof_result = roof.collision_audit(world, actors)
    goals = tagged('BB.Goal')
    if len(goals) != 8:
        raise RuntimeError('Expected six large and two small goals')
    goal_rows = []
    rims = tagged('BB.Goal.Rim')
    for goal in goals:
        large = goal.actor_has_tag('BB.Goal.Large')
        radius = dimensions.LARGE_HOOP_RADIUS if large else dimensions.SMALL_HOOP_RADIUS
        height = dimensions.LARGE_HOOP_HEIGHT if large else dimensions.SMALL_HOOP_HEIGHT
        x, y, z = xyz(goal.get_actor_location())
        if abs(abs(x)-d['goal_x']) > .02 or abs(z-height) > .02 or not near(xyz(goal.get_actor_scale3d()), [1, 1, 1]):
            raise RuntimeError('Hoop plane, fixed height or physical scale differs')
        expected_y = (-dimensions.HOOP_SPACING, 0, dimensions.HOOP_SPACING) if large else (0,)
        if min(abs(y-v) for v in expected_y) > .02:
            raise RuntimeError('Fixed hoop spacing changed')
        for offset, blocked in ((0, False), (radius-3, False), (radius+1, True)):
            trace(goal.get_actor_label(), (x-75, y+offset, z), (x+75, y+offset, z), rims if blocked else None)
        goal_rows.append(dict(actor=goal.get_path_name(), center=[x, y, z], radius_cm=radius, aperture_bracket_verified=True))
    return dict(passed=True, floor_wall_goal_queries=rows, roof=roof_result, goals=goal_rows)


def mesh_slots(mesh):
    return [dict(material=object_path(prop(slot, 'material_interface')), name=str(prop(slot, 'material_slot_name')),
                 imported_name=str(prop(slot, 'imported_material_slot_name'))) for slot in prop(mesh, 'static_materials')]


def capture_material_slots(mesh):
    # Struct.copy() is the public UE Python value-copy operation. Keep detached
    # full structs (including UV metadata) plus immutable scalar diagnostics.
    values = [slot.copy() for slot in prop(mesh, 'static_materials')]
    receipt = mesh_slots(mesh)
    copied = [dict(material=object_path(prop(slot, 'material_interface')), name=str(prop(slot, 'material_slot_name')),
                   imported_name=str(prop(slot, 'imported_material_slot_name'))) for slot in values]
    if copied != receipt:
        raise RuntimeError('Detached material-slot copies differ from the saved mesh')
    return dict(values=values, receipt=receipt)


def record_differences(before, after):
    differences = []
    for path in sorted(set(before) | set(after)):
        old, new = before.get(path, {}), after.get(path, {})
        changed = {key: dict(before=old.get(key), after=new.get(key))
                   for key in sorted(set(old) | set(new)) if old.get(key) != new.get(key)}
        if changed:
            differences.append(dict(actor=path, changes=changed))
    return differences


def build(args=None):
    import unreal
    args = dict(globals().get('BRIDGE_ARGS', {}) if args is None else args)
    dry_run = args.get('dry_run', True)
    if not isinstance(dry_run, bool) or not isinstance(args.get('execute', False), bool):
        raise ValueError('dry_run and execute must be booleans')
    if not dry_run and args.get('execute') is not True:
        raise ValueError('Explicit execute=true is required when dry_run=false')
    plan = validate_plan(module('_bb_standalone_expansion_plan', 'Tools/arena_expansion_plan.py').build_plan())
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    worlds = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    actor_system = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not unreal.SystemLibrary.get_engine_version().startswith('5.8.') or Path(unreal.Paths.project_dir()).resolve() != (ROOT/'DevelopmentHarness').resolve():
        raise RuntimeError('Standalone expansion requires this repository\'s native UE5.8 project')
    if levels.is_in_play_in_editor():
        raise RuntimeError('Stop PIE before the bounded expansion')
    def clean():
        saving = unreal.EditorLoadingAndSavingUtils
        dirty = [p.get_path_name() for p in list(saving.get_dirty_map_packages())+list(saving.get_dirty_content_packages())]
        if dirty: raise RuntimeError('Preserving unsaved editor work: '+str(dirty))
    def world_path():
        world = worlds.get_editor_world()
        return world.get_path_name().split('.')[0] if world else None
    clean()
    original = world_path()
    if original not in MAPS:
        raise RuntimeError('Open an existing BB_Arena or BB_Regulation map first')
    packages = list(MAPS)+[item['destination'] for item in plan['changed_meshes']]
    paths = [asset_file(package, plan) for package in packages]
    if any(not path.is_file() for path in paths):
        raise RuntimeError('Both existing maps and all ten existing meshes are required')
    for item in plan['changed_meshes']:
        if digest(ROOT/item['source']) != item['sha256_after']:
            raise RuntimeError('Original source changed after the expansion plan was read')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8]
    attempt = ROOT/'.local/arena-expansion-stage'/stamp
    attempt.mkdir(parents=True, exist_ok=False)
    report_path = attempt/'results.json'
    before_hashes = content_hashes()
    allowed = [path.relative_to(CONTENT).as_posix() for path in paths]
    report = dict(status='preflight', dry_run=dry_run, original_map=original, plan=plan,
                  plan_sha256=contract.plan_hash(plan), maps=[], engine=unreal.SystemLibrary.get_engine_version(),
                  allowed_saved_content=allowed, backup_manifest=[])
    def report_save(): write(report_path, report)
    report_save()
    captured = {}
    mutation_started = False
    try:
        for map_path in MAPS:
            clean()
            if not levels.load_level(map_path): raise RuntimeError('Could not load '+map_path)
            actors = list(actor_system.get_all_level_actors())
            if any(not actor.get_path_name().startswith(map_path+'.') for actor in actors):
                raise RuntimeError('Streaming actors outside the owned map are loaded')
            records = snapshot(unreal, actors)
            before_path = attempt/(map_path.rsplit('/', 1)[-1]+'-before.json')
            write(before_path, records)
            map_report = dict(path=map_path, actor_snapshot_before=str(before_path),
                              sha256_before=digest(asset_file(map_path, plan)))
            report['maps'].append(map_report)
            report_save()
            # Persist all observed actors before the first mismatch can reject
            # the map, so one read-only failure can diagnose every legacy delta.
            selected = match_plan(records, plan)
            training = match_training(records, map_path)
            mode = object_path(prop(worlds.get_editor_world().get_world_settings(), 'default_game_mode'))
            audit = collision_audit(unreal, worlds.get_editor_world(), actors, plan['dimensions_before'])
            captured[map_path] = dict(records=records, geometry=selected, training=training, mode=mode)
            map_report.update(geometry_before=audit, planned_geometry_actors=len(selected), planned_training_actors=len(training))
            report_save()
        if not levels.load_level(original): raise RuntimeError('Could not restore the original map after preflight')
        clean()
        check_file_scope(before_hashes, content_hashes(), [])
        if dry_run:
            report.update(status='dry_run_passed', original_map_restored=True, assets_unchanged=True)
            report_save()
            return dict(status=report['status'], report=str(report_path), maps_checked=2, execute_pending=True)
        backup_root = attempt/'backups'
        for path in paths:
            target = backup_root/path.relative_to(CONTENT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            if digest(target) != before_hashes[path.relative_to(CONTENT).as_posix()]:
                raise RuntimeError('Immutable original-byte backup failed validation')
            report['backup_manifest'].append(dict(source=str(path), backup=str(target), sha256=digest(target)))
        report.update(status='staging', mutation_started=True)
        report_save()
        mutation_started = True
        unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
        arena = module('_bb_standalone_expansion_builder', 'Tools/build_arena.py')
        builder = arena.ArenaBuilder()
        saved_slots = {}
        for item in plan['changed_meshes']:
            old_mesh = unreal.load_asset(item['destination'])
            if old_mesh is None: raise RuntimeError('Missing existing source mesh '+item['name'])
            saved_slots[item['name']] = capture_material_slots(old_mesh)
        report['mesh_material_slots_before'] = {name: row['receipt'] for name, row in saved_slots.items()}
        report_save()
        for item in plan['changed_meshes']:
            if digest(ROOT/item['source']) != item['sha256_after']:
                raise RuntimeError('Original OBJ changed before its targeted import')
            mesh = builder.import_mesh(item['name'])
            mesh.set_editor_property('static_materials', saved_slots[item['name']]['values'])
            if mesh_slots(mesh) != saved_slots[item['name']]['receipt']:
                raise RuntimeError('Static material slot references changed during reimport')
            if not builder.assets.save_loaded_asset(mesh, only_if_is_dirty=False): raise RuntimeError('Could not save reimported mesh')
        builder.configure_pyramid_collision()
        report['mesh_material_slots'] = {name: row['receipt'] for name, row in saved_slots.items()}
        for row in report['maps']:
            map_path = row['path']
            clean()
            if not levels.load_level(map_path): raise RuntimeError('Could not load '+map_path)
            actors = list(actor_system.get_all_level_actors())
            prior = captured[map_path]
            # Reimports may change bounds but must preserve saved actor state.
            imported_records = snapshot(unreal, actors)
            imported_path = attempt/(map_path.rsplit('/', 1)[-1]+'-after-mesh-reimport.json')
            write(imported_path, imported_records)
            row['actor_snapshot_after_reimport'] = str(imported_path)
            row['reimport_actor_differences'] = record_differences(prior['records'], imported_records)
            report_save()
            if row['reimport_actor_differences']:
                raise RuntimeError('Reimport unexpectedly changed actor/component/material setup; all differences are in the receipt')
            for actor in actors:
                path = actor.get_path_name()
                entry = prior['geometry'].get(path)
                if entry and entry['changed']:
                    value = entry['new']
                    actor.set_actor_location(unreal.Vector(*value['location']), False, False)
                    actor.set_actor_rotation(unreal.Rotator(pitch=value['rotation'][0], yaw=value['rotation'][1], roll=value['rotation'][2]), False)
                    actor.set_actor_scale3d(unreal.Vector(*value['scale']))
                home = prior['training'].get(path)
                if home:
                    actor.set_actor_location(unreal.Vector(*home['new']['location']), False, False)
                    if 'home' in home['new']: actor.set_editor_property('Home', unreal.Vector(*home['new']['home']))
            current = snapshot(unreal, list(actor_system.get_all_level_actors()))
            compare(prior['records'], current, prior['geometry'], prior['training'])
            if object_path(prop(worlds.get_editor_world().get_world_settings(), 'default_game_mode')) != prior['mode']:
                raise RuntimeError('Native game mode changed during expansion')
            row['geometry_before_save'] = collision_audit(unreal, worlds.get_editor_world(), list(actor_system.get_all_level_actors()), plan['dimensions_after'])
            report_save()
            if not levels.save_current_level() or not levels.load_level(map_path): raise RuntimeError('Could not save and reload '+map_path)
            actors = list(actor_system.get_all_level_actors())
            current = snapshot(unreal, actors)
            compare(prior['records'], current, prior['geometry'], prior['training'])
            match_plan(current, plan, 'new')
            match_training(current, map_path, 'new')
            if object_path(prop(worlds.get_editor_world().get_world_settings(), 'default_game_mode')) != prior['mode']:
                raise RuntimeError('Game mode did not survive save/reload')
            row.update(geometry_after=collision_audit(unreal, worlds.get_editor_world(), actors, plan['dimensions_after']),
                       sha256_after=digest(asset_file(map_path, plan)), saved_reloaded=True,
                       unrelated_actors_components_materials_preserved=True, native_game_mode_preserved=True)
            write(attempt/(map_path.rsplit('/', 1)[-1]+'-after.json'), current)
            report_save()
        if not levels.load_level(original): raise RuntimeError('Could not restore original map')
        clean()
        for item in plan['changed_meshes']:
            if mesh_slots(unreal.load_asset(item['destination'])) != saved_slots[item['name']]['receipt']:
                raise RuntimeError('Material slots did not survive save/reload')
        changed = check_file_scope(before_hashes, content_hashes(), allowed)
        if set(changed) != set(allowed): raise RuntimeError('Every planned map and mesh must have newly saved bytes')
        report.update(status='staged', original_map_restored=True, changed_content=changed,
                      preservation_verified=True, materials_preserved=True, runtime_validation_pending=True)
        report_save()
        write(SUCCESS, dict(report=str(report_path), sha256=digest(report_path), plan_sha256=report['plan_sha256']))
        return dict(status='staged', report=str(report_path), maps_updated=2, meshes_reimported=10, runtime_validation_pending=True)
    except Exception:
        report.update(status='failed', error=traceback.format_exc(), mutation_started=mutation_started,
                      recovery='Inspect immutable backups and current dirty packages; no automatic rollback was attempted.')
        if not mutation_started:
            try:
                clean()
                if not levels.load_level(original): raise RuntimeError('Original map reload failed')
                clean()
                report['original_map_restored'] = True
            except Exception:
                report['restore_error'] = traceback.format_exc()
        report_save()
        raise


if __name__ == '__main__':
    RESULT = build()

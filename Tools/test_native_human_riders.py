"""Human roster acceptance in a fresh, disposable UE5.8 native PIE world.

Bridge default operation=test starts and owns PIE, compares actual cosmetic
actors with the saved roster/cosmetic receipts, swaps teams using real gamepad
bindings, flies through PlayerInput, and confirms EndPlay. operation=inspect
only observes an already-running native PIE world and writes a separate probe.
Neither operation configures the roster, edits assets, resets animation, assigns
materials, or writes reflected gameplay state. --list works outside Unreal.

Optional BRIDGE_ARGS: inventory (combined roster inventory JSON), roster (asset
package), max_wall_seconds (default 240). The main project and one-player PIE
settings must already be selected. Captures and remote/package checks are separate.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'.local/native-human-riders-results.json'
INSPECTION = ROOT/'.local/native-human-riders-inspection.json'
ARGS = globals().get('BRIDGE_ARGS', {})
NAMES = ('BB_AthleteA', 'BB_AthleteB')
CASES = (
    'configured_roster_matches_both_saved_cosmetic_contracts',
    'sixteen_actual_human_children_cover_both_variants_and_teams',
    'body_uses_exact_flight_animation_and_matching_skeleton',
    'every_garment_uses_exact_named_slot_and_team_material',
    'quinn_fallback_is_hidden_without_hiding_the_human_child',
    'authored_body_face_hair_and_face_animation_pipeline_are_present',
    'all_cosmetic_actors_and_components_are_nonreplicated_and_nonphysical',
    'all_cosmetic_primitives_hide_from_owner_and_remain_visible_to_others',
    'team_change_preserves_human_identity_skin_face_and_hair',
    'team_change_updates_only_exact_garment_material_slots',
    'return_team_restores_garments_without_replacing_humans',
    'ordinary_input_starts_live_match_and_moves_human_rider',
    'neutral_input_stops_human_rider_without_losing_cosmetics',
)


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'Tools'/filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


ctrl = module('_bb_human_controller_base', 'test_native_controller.py')
receipts = module('_bb_human_receipts', 'native_test_receipts.py')
unreal, prop, xyz = ctrl.unreal, ctrl.prop, ctrl.xyz
ctrl.REPORT = ctrl.base.REPORT = REPORT
ctrl.base.TEST_NAMES = CASES
ctrl.base.ARGS = {'max_wall_seconds':240, **ARGS}


def path(value):
    return value.get_path_name() if value is not None else None


def sha(filename):
    return hashlib.sha256(Path(filename).read_bytes()).hexdigest()


def load_contracts():
    filename = Path(ARGS.get('inventory', ROOT/'.local/CharacterLab/roster-inventory.json')).resolve()
    data = json.loads(filename.read_text(encoding='utf-8-sig'))
    if (data.get('owner') != 'Basketbroom.HumanRoster.v1' or data.get('status') != 'inventoried'
            or set(data.get('characters', {})) != set(NAMES)):
        raise ValueError('Expected the complete, saved two-athlete roster inventory')
    contracts = []
    for name in NAMES:
        item = data['characters'][name]
        source = Path(item['receipt']).resolve()
        source.relative_to((ROOT/'.local/CharacterLab').resolve())
        if sha(source) != item['receipt_sha256']:
            raise ValueError('Cosmetic receipt changed after inventory: '+str(source))
        authored = json.loads(source.read_text(encoding='utf-8-sig'))
        if (authored.get('character') != name or not authored.get('assets_saved')
                or authored.get('actor_class') != item['actor_class']):
            raise ValueError('Cosmetic receipt is not the inventoried saved actor: '+name)
        components = authored['actor_contract']['components']
        if not all(key in components for key in ('Body', 'Face', 'Hair')):
            raise ValueError('Saved cosmetic receipt lacks Body, Face or Hair: '+name)
        contracts.append({**item, 'name':name, 'components':components})
    return contracts, {'inventory':str(filename), 'inventory_sha256':sha(filename),
                       'cosmetic_receipt_sha256':{row['name']:row['receipt_sha256'] for row in contracts}}


def dirty_packages():
    saving = unreal.EditorLoadingAndSavingUtils
    return sorted(path(package) for package in list(saving.get_dirty_map_packages())
                  + list(saving.get_dirty_content_packages()))


def component_map(actors):
    result = {}
    for actor in actors:
        for component in actor.get_components_by_class(unreal.MeshComponent):
            name = component.get_name()
            if name in result:
                raise ValueError('Ambiguous cosmetic component name: '+name)
            result[name] = component
    return result


def material_row(material):
    """Keep live identity and authored parent when a normal runtime MID exists."""
    live = path(material)
    seen = set()
    while isinstance(material, unreal.MaterialInstanceDynamic):
        if path(material) in seen:
            raise ValueError('Cyclic dynamic material parent')
        seen.add(path(material))
        material = prop(material, 'Parent')
    return {'live':live, 'asset':path(material)}


def visible_assets(component):
    row = {'class':path(component.get_class()),
           'visible':bool(component.is_visible()), 'hidden_in_game':bool(prop(component, 'bHiddenInGame')),
           'materials':[material_row(component.get_material(index)) for index in range(component.get_num_materials())]}
    if isinstance(component, unreal.SkeletalMeshComponent):
        mesh = component.get_skeletal_mesh_asset()
        row.update(mesh=path(mesh), skeleton=path(prop(mesh, 'Skeleton')) if mesh else None,
                   animation_class=path(prop(component, 'AnimClass')),
                   post_process_anim_blueprint=path(prop(mesh, 'PostProcessAnimBlueprint')) if mesh else None)
    if 'Groom' in component.get_class().get_name():
        row.update(groom_asset=path(prop(component, 'GroomAsset')), binding_asset=path(prop(component, 'BindingAsset')))
    return row


def binding_row(binding):
    return {'component_name':str(prop(binding, 'ComponentName')),
            'material_slot_name':str(prop(binding, 'MaterialSlotName')),
            'material_slot_index':int(prop(binding, 'MaterialSlotIndex')),
            'teal_material':path(prop(binding, 'TealMaterial')),
            'copper_material':path(prop(binding, 'CopperMaterial'))}


def variant_row(variant):
    return {'actor_class':path(prop(variant, 'ActorClass')),
            'body_component_name':str(prop(variant, 'BodyComponentName')),
            'flight_animation':path(prop(variant, 'FlightAnimation')),
            'garments':[binding_row(binding) for binding in prop(variant, 'Garments')]}


def inspect_rider(rider, contracts):
    row = {'rider':path(rider), 'team':int(prop(rider, 'TeamIndex')),
           'slot':int(prop(rider, 'RosterIndex')), 'appearance':int(prop(rider, 'AppearanceIdentity')),
           'enabled':bool(prop(rider, 'bHumanRiderEnabled'))}
    variants = list(prop(rider, 'HumanRiderVariants'))
    row['variants'] = [variant_row(variant) for variant in variants]
    # The private Transient strong reference is intentionally not exposed to
    # Python. Observe the public configured soft reference and separately prove
    # BeginPlay populated HumanRiderVariants and created the expected children.
    row['configured_roster'] = path(prop(rider, 'HumanRoster'))
    if row['appearance'] < 0 or len(variants) != len(contracts):
        raise ValueError('Rider has no admitted appearance or complete human variants: '+path(rider))
    variant_index = row['appearance'] % len(contracts)
    expected, variant = contracts[variant_index], variants[variant_index]
    child_components = [component for component in rider.get_components_by_class(unreal.ChildActorComponent)
                        if component.get_name() == 'HumanRiderCosmetic']
    if len(child_components) != 1:
        raise ValueError('Expected one native HumanCosmetic child component')
    child = prop(child_components[0], 'ChildActor')
    if child is None:
        raise ValueError('HumanCosmetic has no actual child actor')
    actors = [child, *child.get_all_child_actors(True)]
    components = component_map(actors)
    body = components[str(prop(variant, 'BodyComponentName'))]
    if not isinstance(body, unreal.SkeletalMeshComponent):
        raise ValueError('Verified Body is not a skeletal component')
    mesh = body.get_skeletal_mesh_asset()
    animation = prop(variant, 'FlightAnimation')
    instance = body.get_anim_instance()
    row.update(variant=variant_index, character=expected['name'], child=path(child),
               child_class=path(child.get_class()), child_hidden=bool(prop(child, 'bHidden')),
               body={'mesh':path(mesh), 'skeleton':path(prop(mesh, 'Skeleton')) if mesh else None,
                     'animation_skeleton':path(prop(animation, 'Skeleton')),
                     'animation':path(instance.get_animation_asset()) if isinstance(instance, unreal.AnimSingleNodeInstance) else None,
                     'single_node':isinstance(instance, unreal.AnimSingleNodeInstance),
                     'mode':str(body.get_animation_mode()), 'playing':bool(body.is_playing()),
                     'position':float(body.get_position()),
                     'tick_option':str(prop(body, 'VisibilityBasedAnimTickOption')),
                     'update_rate_optimization':bool(prop(body, 'bEnableUpdateRateOptimizations'))})
    fallback = [part for part in rider.get_components_by_class(unreal.SkeletalMeshComponent)
                if 'BB.SkeletalRider' in [str(tag) for tag in prop(part, 'ComponentTags')]]
    row['fallback'] = [{'name':part.get_name(), 'mesh':path(part.get_skeletal_mesh_asset()),
                        'visible':bool(part.is_visible())} for part in fallback]
    row['garments'] = []
    garment_names = {binding['component_name'] for binding in expected['garments']}
    for binding in expected['garments']:
        garment = components[binding['component_name']]
        index = binding['material_slot_index']
        slots = [str(name) for name in garment.get_material_slot_names()]
        material = garment.get_material(index) if 0 <= index < garment.get_num_materials() else None
        leader = prop(garment, 'LeaderPoseComponent') if isinstance(garment, unreal.SkeletalMeshComponent) else None
        expected_material = binding['teal_material' if row['team'] == 0 else 'copper_material']
        valid = (garment is not body and 0 <= index < len(slots) and slots[index] == binding['material_slot_name']
                 and path(material) == expected_material and leader == body
                 and path(garment.get_skeletal_mesh_asset()) == expected['components'][binding['component_name']]['mesh'])
        row['garments'].append({**binding, 'actual_material':path(material), 'actual_slot':slots[index] if 0 <= index < len(slots) else None,
                                'leader':path(leader), 'valid':valid,
                                'visible':bool(garment.is_visible()), 'hidden_in_game':bool(prop(garment, 'bHiddenInGame'))})
    row['protected'] = {name:visible_assets(component) for name, component in components.items()
                        if isinstance(component, unreal.MeshComponent) and name not in garment_names}
    row['cosmetic_actors'] = []
    row['cosmetic_primitives'] = []
    for actor in actors:
        all_components = actor.get_components_by_class(unreal.ActorComponent)
        row['cosmetic_actors'].append({'path':path(actor), 'owner':path(actor.get_owner()),
            'valid':actor.get_owner() == rider and not bool(prop(actor, 'bReplicates'))
                and not bool(prop(actor, 'bReplicateMovement')) and not actor.get_actor_enable_collision()
                and not isinstance(actor, (unreal.Pawn, unreal.Controller)),
            'component_count':len(all_components),
            'replicated_components':[part.get_name() for part in all_components if bool(prop(part, 'bReplicates'))]})
        for part in actor.get_components_by_class(unreal.PrimitiveComponent):
            row['cosmetic_primitives'].append({'path':path(part),
                'nonphysical':part.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
                    and str(part.get_collision_profile_name()) == 'NoCollision'
                    and not part.is_any_simulating_physics() and not bool(prop(part, 'bGenerateOverlapEvents'))
                    and not bool(prop(part, 'bCanEverAffectNavigation')),
                'owner_hidden':bool(prop(part, 'bOwnerNoSee')) and not bool(prop(part, 'bOnlyOwnerSee'))})
    return row


def inspect_world(world, contracts):
    rider_class = unreal.load_class(None, '/Script/BasketbroomRuntime.BBRiderCharacter')
    rows = []
    for rider in unreal.GameplayStatics.get_all_actors_of_class(world, rider_class):
        try:
            rows.append(inspect_rider(rider, contracts))
        except Exception:
            rows.append({'rider':path(rider), 'error':traceback.format_exc()})
    return sorted(rows, key=lambda row:row.get('slot', 999))


def protected_contract(row, contract):
    for name in ('Body', 'Face', 'Hair'):
        actual, expected = row['protected'][name], contract['components'][name]
        if (actual['class'] != expected['class'] or [material['asset'] for material in actual['materials']] != expected['materials']):
            return False
        if name in ('Body', 'Face'):
            if any(actual[key] != expected[key] for key in ('mesh', 'skeleton', 'post_process_anim_blueprint')):
                return False
        if name == 'Face' and (not actual['animation_class'] or actual['animation_class'] != expected['animation_class']):
            return False
        if name == 'Hair' and any(not actual[key] or actual[key] != expected['groom'][key].get('path')
                                  for key in ('groom_asset', 'binding_asset')):
            return False
    return True


def identity(row):
    return {key:row[key] for key in ('rider', 'appearance', 'variant', 'child', 'child_class', 'protected')}


class HumanRiderTests(ctrl.NativeControllerTests):
    def __init__(self):
        self.contracts = []
        self.observations = {}
        self.cleanup_pending = None
        self.editor_before = None
        super().__init__()

    def write_report(self, status, reason=None):
        data = receipts.single_world_payload(self, CASES, status, reason,
                    unreal.SystemLibrary.get_engine_version() if unreal else None)
        data.update(scope='actual human cosmetic roster in one disposable native PIE world',
            hardware_claim=False, rendered_pixels_claim=False, remote_replication_claim=False,
            observations=self.observations,
            fixture_policy='Read-only cosmetic observations; simulated mapped gamepad events enter ordinary PlayerInput. '
                'All 16 riders retain normal ticks. No cosmetic/state/config assignment, animation reset, asset save or CPU parking.',
            not_covered=['physical controller hardware', 'rendered appearance and first/third-person pixels',
                         'remote replication', 'dedicated servers', 'cooked packages', 'frame rate or memory performance'])
        receipts.write_json_atomic(REPORT, data)

    def begin(self):
        actual = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        self.require(actual == (ROOT/'DevelopmentHarness/BasketbroomDev.uproject').resolve(), 'Use the main native project')
        self.contracts, provenance = load_contracts()
        self.provenance.update(provenance)
        self.editor_before = {'world':path(self.editor.get_editor_world()), 'dirty_packages':dirty_packages()}
        self.require(self.editor_before['world'].split('.')[0] in
                     ('/Basketbroom/Maps/BB_Regulation', '/Basketbroom/Maps/BB_Redrock', '/Basketbroom/Maps/BB_Redwoods'),
                     'Select a supported native arena; this suite does not load maps')
        settings_class = unreal.load_class(None, '/Script/UnrealEd.LevelEditorPlaySettings')
        self.require(int(prop(unreal.get_default_object(settings_class), 'PlayNumberOfClients')) == 1,
                     'Select one-player PIE before running the disposable single-world suite')
        return super().begin()

    def isolate(self):
        # Base setup calls this before appearance identities settle. Keep every
        # rider/child/movement tick intact; lobby and short flight need no fixtures.
        pass

    def observe(self, stage):
        rows = inspect_world(self.world, self.contracts)
        self.observations[stage] = rows
        self.require(len(rows) == 16 and not any('error' in row for row in rows),
                     'Every runtime rider must be inspectable; see observations.'+stage)
        return rows

    def scenarios(self):
        self.require(callable(getattr(self.pawn, 'development_inject_gamepad_input', None)), 'Mapped input bridge required')
        self.require(self.controller.is_actor_tick_enabled(), 'Ordinary PlayerController input ticks required')
        self.require(not prop(self.match, 'bLive'), 'Start from the ordinary native lobby')
        yield self.wait_until(lambda: all(bool(prop(rider, 'bHumanRiderEnabled')) for rider in self.riders), timeout=15)
        yield self.wait(.3, minimum_frames=3)
        rows = self.observe('lobby')
        expected_variants = [{key:row[key] for key in ('actor_class', 'body_component_name', 'flight_animation', 'garments')}
                             for row in self.contracts]
        roster_package = ARGS.get('roster', '/Game/BasketbroomHumans/Runtime/DA_BB_HumanRoster')
        roster_path = roster_package if '.' in roster_package else roster_package+'.'+roster_package.rsplit('/', 1)[1]
        self.record(CASES[0], all(row['configured_roster'] == roster_path and row['variants'] == expected_variants for row in rows),
                    expected_roster=roster_path, expected_variants=expected_variants)
        coverage = {(team, variant):sum(row['team'] == team and row['variant'] == variant for row in rows)
                    for team in (0, 1) for variant in (0, 1)}
        self.record(CASES[1], self.roster_valid() and sorted(row['appearance'] for row in rows) == list(range(16))
                    and len({row['child'] for row in rows}) == 16 and all(count == 4 for count in coverage.values())
                    and all(row['enabled'] and row['child_class'] == self.contracts[row['variant']]['actor_class'] for row in rows),
                    coverage={str(key):count for key, count in coverage.items()})
        body_valid = lambda row: (row['body']['single_node'] and row['body']['playing']
            and row['body']['animation'] == self.contracts[row['variant']]['flight_animation']
            and row['body']['skeleton'] == row['body']['animation_skeleton']
            and 'alwaystickposeandrefreshbones' in row['body']['tick_option'].lower().replace('_', '')
            and not row['body']['update_rate_optimization'])
        self.record(CASES[2], all(body_valid(row) for row in rows), bodies=[row['body'] for row in rows])
        self.record(CASES[3], all(row['garments'] and all(item['valid'] for item in row['garments']) for row in rows))
        self.record(CASES[4], all(len(row['fallback']) == 1 and not row['fallback'][0]['visible']
                    and 'Quinn' in row['fallback'][0]['mesh'] and not row['child_hidden']
                    and all(row['protected'][name]['visible'] and not row['protected'][name]['hidden_in_game']
                            for name in ('Body', 'Face', 'Hair'))
                    and all(item['visible'] and not item['hidden_in_game'] for item in row['garments']) for row in rows))
        self.record(CASES[5], all(protected_contract(row, self.contracts[row['variant']]) for row in rows))
        self.record(CASES[6], all(row['cosmetic_actors'] and row['cosmetic_primitives']
                    and all(actor['valid'] and not actor['replicated_components'] for actor in row['cosmetic_actors'])
                    and all(part['nonphysical'] for part in row['cosmetic_primitives']) for row in rows))
        self.record(CASES[7], all(all(part['owner_hidden'] for part in row['cosmetic_primitives']) for row in rows))
        original = {row['rider']:row for row in rows}
        initial_team = int(prop(self.pawn, 'TeamIndex'))
        yield from self.tap('Gamepad_Special_Left', lambda: bool(prop(self.pawn, 'bShowRoster')))
        yield from self.tap('Gamepad_DPad_Left', lambda: int(prop(self.pawn, 'TeamIndex')) != initial_team)
        yield self.wait(.3, minimum_frames=2)
        changed = self.observe('changed_team')
        changed_team = int(prop(self.pawn, 'TeamIndex')) != initial_team
        retained = all(identity(row) == identity(original[row['rider']]) for row in changed)
        self.record(CASES[8], changed_team and retained and self.roster_valid(), changed_team=changed_team, identities_retained=retained)
        changed_riders = [row['rider'] for row in changed if row['team'] != original[row['rider']]['team']]
        self.record(CASES[9], changed_team and len(changed_riders) == 2
                    and all(all(item['valid'] for item in row['garments']) for row in changed), changed_riders=changed_riders)
        yield from self.tap('Gamepad_DPad_Left', lambda: int(prop(self.pawn, 'TeamIndex')) == initial_team)
        yield self.wait(.3, minimum_frames=2)
        returned = self.observe('returned_team')
        self.record(CASES[10], int(prop(self.pawn, 'TeamIndex')) == initial_team and self.roster_valid()
                    and all(identity(row) == identity(original[row['rider']])
                            and row['garments'] == original[row['rider']]['garments'] for row in returned))
        yield from self.tap('Gamepad_Special_Left', lambda: not prop(self.pawn, 'bShowRoster'))
        yield from self.tap('Gamepad_FaceButton_Bottom', lambda: bool(prop(self.match, 'bLive')))
        child_component = next(component for component in self.pawn.get_components_by_class(unreal.ChildActorComponent)
                               if component.get_name() == 'HumanRiderCosmetic')
        child = prop(child_component, 'ChildActor')
        before, child_before = xyz(self.pawn.get_actor_location()), xyz(child.get_actor_location())
        self.pad('Gamepad_LeftY', .65)
        yield self.wait_until(lambda: abs(self.state()[1]) > .1, timeout=2)
        yield self.wait(.35, minimum_frames=3)
        after, child_after = xyz(self.pawn.get_actor_location()), xyz(child.get_actor_location())
        distance = math.dist(before, after)
        follow_error = math.dist([b-a for a,b in zip(before, after)], [b-a for a,b in zip(child_before, child_after)])
        self.record(CASES[11], bool(prop(self.match, 'bLive')) and distance > 80 and follow_error < 3
                    and child == prop(child_component, 'ChildActor') and bool(prop(self.pawn, 'bHumanRiderEnabled')),
                    distance_cm=distance, child_follow_error_cm=follow_error, input_boundary='PlayerController::InputKey')
        yield from self.release_axis('Gamepad_LeftY', 1)
        yield self.wait(.5, minimum_frames=3)
        velocity = xyz(self.pawn.get_velocity())
        final = inspect_rider(self.pawn, self.contracts)
        self.record(CASES[12], math.sqrt(sum(value*value for value in velocity)) < 5
                    and identity(final) == identity(original[path(self.pawn)])
                    and all(item['valid'] for item in final['garments']), velocity_cm_s=velocity)

    def finish(self, status, reason=None):
        if self.cleanup_pending is not None:
            return
        if unreal and self.owns_play and self.level.is_in_play_in_editor():
            try:
                if self.pawn and callable(getattr(self.pawn, 'development_flush_controller_input', None)):
                    self.pawn.development_flush_controller_input()
            except Exception:
                status, reason = 'error', (reason or '')+'\nInput cleanup: '+traceback.format_exc()
            self.cleanup_pending = (status, reason, time.monotonic())
            self.phase = 'waiting_for_end_play'
            self.waiting = None
            self.level.editor_request_end_play()
            self.write_report('running', 'Owned PIE EndPlay requested; waiting for confirmation.')
            return
        ctrl.base.NativePlayableTests.finish(self, status, reason)

    def tick(self, delta):
        if self.cleanup_pending is None:
            return super().tick(delta)
        status, reason, started = self.cleanup_pending
        if self.level.is_in_play_in_editor():
            if time.monotonic()-started < 30:
                return
            status, reason = 'error', (reason or '')+'\nOwned PIE did not end within 30 seconds.'
        else:
            after = {'world':path(self.editor.get_editor_world()), 'dirty_packages':dirty_packages()}
            self.provenance['cleanup'] = {'pie_ended':True, 'editor_before':self.editor_before, 'editor_after':after,
                                          'editor_unchanged':after == self.editor_before}
            self.owns_play = False
            if after != self.editor_before:
                status, reason = 'error', (reason or '')+'\nEditor world or dirty packages changed during disposable PIE.'
        self.cleanup_pending = None
        ctrl.base.NativePlayableTests.finish(self, status, reason)


def main():
    if unreal is None:
        return {'status':'not_run', 'planned_tests':list(CASES), 'count':len(CASES),
                'instruction':'Run through editor_bridge.py in the main project after roster activation; operation=inspect is read-only.'}
    if ARGS.get('operation', 'test') == 'inspect':
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        if project != (ROOT/'DevelopmentHarness/BasketbroomDev.uproject').resolve() or not levels.is_in_play_in_editor():
            raise RuntimeError('Read-only inspection requires an already-running PIE world in the main project')
        contracts, provenance = load_contracts()
        world = editor.get_game_world()
        data = {'status':'observed', 'scope':'read-only human PIE component probe', 'world':path(world),
                'provenance':provenance, 'riders':inspect_world(world, contracts), 'mutations':0,
                'acceptance_claim':False, 'owns_pie':False}
        receipts.write_json_atomic(INSPECTION, data)
        return {'status':'observed', 'report':str(INSPECTION), 'riders':len(data['riders'])}
    if ARGS.get('operation', 'test') != 'test':
        raise ValueError('Use operation=test or operation=inspect')
    runner = HumanRiderTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish('error', traceback.format_exc())
        started = False
    if started:
        unreal._basketbroom_native_test = runner
    return {'status':'started' if started else runner.final_status, 'report':str(REPORT), 'planned_cases':len(CASES)}


if __name__ == '__main__':
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

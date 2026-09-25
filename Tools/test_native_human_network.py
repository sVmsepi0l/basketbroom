"""Human roster replication through three connected, disposable local PIE worlds.

Uses the proven listen-server/owner/observer startup and settings cleanup from
test_native_trail_network.py, and the actual component inspector accepted by
test_native_human_riders.py. The client team request enters the existing bounded
DevelopmentRequestAction queue; native Tick calls ordinary SubmitAction and its
ServerAction RPC outside Python's local-only script guard. No direct RPC calls,
replicated-field writes, cosmetic edits, animation resets or asset saves.

Bridge args match the trail network suite: settings_already_configured and
settings_source when the engine lacks its Python PlayNetMode enum. Optional
inventory, roster, max_wall_seconds. Default map is the existing BB_Regulation.
This certifies local PIE transport and component state, not physical input,
remote internet play, rendered pixels or packaged performance. --list is offline.
"""
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'.local/native-human-network-results.json'
ARGS = {'max_wall_seconds':240, **globals().get('BRIDGE_ARGS', {})}
TESTS = (
    'three_connected_worlds_have_distinct_authority_owner_and_observer',
    'each_world_has_sixteen_humans_without_duplicate_or_orphan_cosmetics',
    'appearance_identities_classes_and_authored_skin_assets_agree_across_worlds',
    'all_worlds_load_exact_roster_body_animation_face_and_hair_contracts',
    'initial_replicated_teams_select_exact_garment_materials_in_all_worlds',
    'all_local_cosmetics_are_nonreplicated_nonphysical_and_noncolliding',
    'each_world_has_one_local_owner_and_correct_cosmetic_owner_filters',
    'owned_client_native_tick_team_request_reaches_server_and_observer',
    'replicated_team_swap_updates_exact_garment_slots_on_every_copy',
    'team_swap_preserves_all_human_instances_identity_skin_face_and_hair',
    'queued_return_team_restores_all_rosters_and_garments_without_match_mutation',
    'managed_play_settings_restored_and_pie_ended',
)


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'Tools'/filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


trail = module('_bb_human_network_scaffold', 'test_native_trail_network.py')
human = module('_bb_human_network_inspector', 'test_native_human_riders.py')
base = trail.base
trail.TESTS = base.TESTS = TESTS
trail.REPORT = base.REPORT = REPORT
trail.ARGS = base.ARGS = human.ARGS = ARGS
unreal, prop = base.unreal, base.prop


def canonical(rows):
    """Cross-world comparison excludes world-local actor and MID object paths."""
    result = []
    for row in rows:
        protected = {}
        for name, part in row['protected'].items():
            protected[name] = {key:value for key, value in part.items() if key != 'materials'}
            protected[name]['materials'] = [material['asset'] for material in part['materials']]
        result.append({'appearance':row['appearance'], 'team':row['team'], 'slot':row['slot'],
            'variant':row['variant'], 'class':row['child_class'], 'protected':protected,
            'body_animation':row['body']['animation'], 'body_skeleton':row['body']['skeleton'],
            'garments':[{key:item[key] for key in ('component_name', 'material_slot_name', 'material_slot_index', 'actual_material')}
                        for item in row['garments']]})
    return sorted(result, key=lambda row:row['appearance'])


def identities(rows):
    return {row['appearance']:human.identity(row) for row in rows}


class HumanNetworkTests(trail.TrailNetworkTests):
    def __init__(self):
        self.contracts = []
        self.expected_variants = []
        self.observations = {}
        self.editor_before = None
        super().__init__()

    def write(self, status):
        rows = [{'name':name, **self.results.get(name, {'status':'not_run'})} for name in TESTS]
        base.write_json_atomic(REPORT, {
            'status':status, 'phase':self.phase, 'reason':self.reason,
            'scope':'human cosmetics in one listen-server and two connected client PIE worlds in one editor process',
            'elapsed_wall_seconds':round(time.monotonic()-self.started, 3),
            'passed':sum(row['status']=='passed' for row in rows),
            'failed':sum(row['status']=='failed' for row in rows),
            'not_run':sum(row['status']=='not_run' for row in rows),
            'tests':rows, 'events':self.events, 'provenance':self.provenance,
            'observations':self.observations, 'settings_restored':self.settings_restored,
            'external_restore_required':base.net_mode_restore_actions(self.provenance),
            'hardware_claim':False, 'rendered_pixels_claim':False, 'remote_internet_claim':False,
            'input_boundary':'existing PIE DevelopmentRequestAction -> normal native Tick -> SubmitAction -> owned ServerAction RPC',
            'not_covered':['physical keyboard/gamepad events', 'separate processes or remote machines',
                           'latency, packet loss, reconnect or late joining', 'rendered owner/remote pixels',
                           'cooked builds, frame rate and memory performance'],
            'fixture_policy':'Read-only cosmetic inspection plus two actual owned-client queued team actions in a fresh lobby. '
                'No direct RPC, reflected gameplay assignment, cosmetic setter, animation reset, material write, '
                'CPU isolation, asset save or persistent game configuration change. Managed play settings are restored.',
        })

    def begin(self):
        project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        self.require(project == (ROOT/'DevelopmentHarness/BasketbroomDev.uproject').resolve(), 'Main native project required')
        self.contracts, provenance = human.load_contracts()
        self.provenance.update(provenance)
        self.expected_variants = [{key:row[key] for key in ('actor_class', 'body_component_name', 'flight_animation', 'garments')}
                                  for row in self.contracts]
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.editor_before = {'world':human.path(editor.get_editor_world()), 'dirty_packages':human.dirty_packages()}
        return super().begin()

    def ready_humans(self):
        for _, side in self.sides():
            riders = self.actors(side['world'], 'BBRiderCharacter')
            if (len(riders) != 16 or not all(bool(prop(rider, 'bHumanRiderEnabled')) for rider in riders)
                    or sorted(int(prop(rider, 'AppearanceIdentity')) for rider in riders) != list(range(16))):
                return False
        return True

    def choose_editing_client(self):
        # The first admitted remote Ranger can face the host's occupied Ranger
        # slot. Select a real client whose opposite-team role is held by a CPU;
        # this respects normal ChangePosition eligibility without altering it.
        clients = (self.client, self.observer)
        eligible = []
        for side in clients:
            pawn = side['pawn']
            targets = [rider for rider in self.actors(self.host['world'], 'BBRiderCharacter')
                       if not rider.is_player_controlled() and int(prop(rider, 'TeamIndex')) != int(prop(pawn, 'TeamIndex'))
                       and int(prop(rider, 'Position')) == int(prop(pawn, 'Position'))]
            if targets:
                eligible.append(side)
        self.require(eligible, 'One actual client needs an eligible opposite-team CPU role for the ordinary team swap')
        self.client = eligible[0]
        self.observer = next(side for side in clients if side is not self.client)
        self.provenance['worlds'] = {label:side['world'].get_path_name() for label, side in self.sides()}
        self.provenance['editing_player_id'] = self.player_id(self.client['pawn'])

    def observe(self, stage):
        state = {}
        for label, side in self.sides():
            rows = human.inspect_world(side['world'], self.contracts)
            state[label] = {'riders':rows, 'roster':self.roster(side), 'match':self.snapshot(side)}
            if len(rows) != 16 or any('error' in row for row in rows):
                self.observations[stage] = state
                raise RuntimeError('Expected 16 inspectable human riders in '+label+'; see observations.'+stage)
            riders = {human.path(rider):rider for rider in self.actors(side['world'], 'BBRiderCharacter')}
            for row in rows:
                row['variants_match'] = row.pop('variants') == self.expected_variants
                row['locally_controlled'] = bool(riders[row['rider']].is_locally_controlled())
                row['player_id'] = self.player_id(riders[row['rider']])
            actual_children = []
            for contract in self.contracts:
                actor_class = unreal.load_class(None, contract['actor_class'])
                self.require(actor_class is not None, 'Expected native cosmetic class must load')
                actual_children.extend(human.path(actor) for actor in
                                       unreal.GameplayStatics.get_all_actors_of_class(side['world'], actor_class))
            expected_children = [row['child'] for row in rows]
            state[label].update(actual_cosmetics=sorted(actual_children),
                no_duplicates_or_orphans=len(set(actual_children)) == 16 and sorted(actual_children) == sorted(expected_children))
        self.observations[stage] = state
        return state

    @staticmethod
    def all_rows(state):
        return [row for side in state.values() for row in side['riders']]

    @staticmethod
    def all_garments(state):
        return all(row['garments'] and all(binding['valid'] for binding in row['garments'])
                   for row in HumanNetworkTests.all_rows(state))

    @staticmethod
    def agreement(state):
        values = [canonical(side['riders']) for side in state.values()]
        return len(values) == 3 and values[0] == values[1] == values[2]

    def all_owner_teams(self, team):
        return all(int(prop(rider, 'TeamIndex')) == team for _, rider in self.copies())

    def exact_assets(self, row):
        package = ARGS.get('roster', '/Game/BasketbroomHumans/Runtime/DA_BB_HumanRoster')
        roster = package if '.' in package else package+'.'+package.rsplit('/', 1)[1]
        expected = self.contracts[row['variant']]
        body = row['body']
        return (row['configured_roster'] == roster and row['variants_match'] and row['enabled']
            and row['child_class'] == expected['actor_class'] and not row['child_hidden']
            and body['single_node'] and body['playing'] and body['animation'] == expected['flight_animation']
            and body['skeleton'] == body['animation_skeleton']
            and human.protected_contract(row, expected)
            and len(row['fallback']) == 1 and not row['fallback'][0]['visible']
            and all(row['protected'][name]['visible'] and not row['protected'][name]['hidden_in_game']
                    for name in ('Body', 'Face', 'Hair'))
            and all(binding['visible'] and not binding['hidden_in_game'] for binding in row['garments']))

    def scenarios(self):
        self.choose_editing_client()
        yield self.wait(20, self.ready_humans)
        self.require(self.ready_humans(), 'All three actual worlds must finish human admission before observation')
        yield self.wait(.5)
        self.require(all(not self.live(side) for _, side in self.sides()), 'Fresh lobby required')
        owner = self.client['pawn']
        self.require(owner.is_locally_controlled() and not owner.has_authority(), 'Actual remote client ownership required')
        rosters = [self.human_roster(side) for _, side in self.sides()]
        self.record(TESTS[0], rosters[0] == rosters[1] == rosters[2]
                    and len(set(self.provenance['worlds'].values())) == 3
                    and unreal.GameplayStatics.get_game_mode(self.host['world']) is not None
                    and all(unreal.GameplayStatics.get_game_mode(side['world']) is None for side in (self.client, self.observer)),
                    worlds=self.provenance['worlds'], player_rosters=rosters)
        initial = self.observe('initial')
        rows = self.all_rows(initial)
        expected_roster = [(slot, slot//8, base.ROLES[slot%8]) for slot in range(16)]
        self.record(TESTS[1], all(side['no_duplicates_or_orphans'] and side['roster'] == expected_roster
                    and sorted(row['appearance'] for row in side['riders']) == list(range(16))
                    for side in initial.values()), counts={label:len(side['actual_cosmetics']) for label, side in initial.items()})
        self.record(TESTS[2], self.agreement(initial))
        self.record(TESTS[3], all(self.exact_assets(row) for row in rows))
        self.record(TESTS[4], self.all_garments(initial))
        self.record(TESTS[5], all(row['cosmetic_actors'] and row['cosmetic_primitives']
                    and all(actor['valid'] and not actor['replicated_components'] for actor in row['cosmetic_actors'])
                    and all(part['nonphysical'] for part in row['cosmetic_primitives']) for row in rows))
        owner_flags = all(sum(row['locally_controlled'] for row in side['riders']) == 1 for side in initial.values())
        owner_flags = owner_flags and all(all(part['owner_hidden'] for part in row['cosmetic_primitives']) for row in rows)
        self.record(TESTS[6], owner_flags,
                    local_owner_ids={label:[row['player_id'] for row in side['riders'] if row['locally_controlled']]
                                     for label, side in initial.items()}, rendered_visibility_claim=False)

        original_team = int(prop(owner, 'TeamIndex'))
        self.provenance['original_owner_team'] = original_team
        self.request(self.client, 3, 1-original_team)
        yield self.wait(10, lambda:self.all_owner_teams(1-original_team))
        yield self.wait(.5)
        changed = self.observe('changed_team')
        accepted = self.all_owner_teams(1-original_team)
        self.record(TESTS[7], accepted and self.agreement(changed),
                    teams={label:int(prop(rider, 'TeamIndex')) for label, rider in self.copies()},
                    dispatch='existing native-tick queue, ordinary owned ServerAction RPC')
        changed_appearances = {}
        for label, side in changed.items():
            before = {row['appearance']:row for row in initial[label]['riders']}
            changed_appearances[label] = sorted(row['appearance'] for row in side['riders']
                                                if row['team'] != before[row['appearance']]['team'])
        self.record(TESTS[8], accepted and self.all_garments(changed)
                    and all(len(values) == 2 for values in changed_appearances.values())
                    and len({tuple(values) for values in changed_appearances.values()}) == 1,
                    changed_appearances=changed_appearances)
        self.record(TESTS[9], accepted and all(identities(side['riders']) == identities(initial[label]['riders'])
                    and side['no_duplicates_or_orphans'] for label, side in changed.items()))

        self.request(self.client, 3, original_team)
        yield self.wait(10, lambda:self.all_owner_teams(original_team))
        yield self.wait(.5)
        returned = self.observe('returned_team')
        restored = self.all_owner_teams(original_team) and self.agreement(returned) and self.all_garments(returned)
        restored = restored and all(canonical(side['riders']) == canonical(initial[label]['riders'])
            and identities(side['riders']) == identities(initial[label]['riders'])
            and side['roster'] == initial[label]['roster'] and side['match'] == initial[label]['match']
            and side['no_duplicates_or_orphans'] for label, side in returned.items())
        self.record(TESTS[10], restored, lobby_preserved=all(not self.live(side) for _, side in self.sides()))

    def complete(self):
        if unreal and self.editor_before is not None:
            editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
            after = {'world':human.path(editor.get_editor_world()), 'dirty_packages':human.dirty_packages()}
            self.provenance['editor_state'] = {'before':self.editor_before, 'after':after, 'unchanged':after == self.editor_before}
            if after != self.editor_before:
                self.final_status = 'error'
                self.reason = (self.reason or '')+' Editor world or dirty assets changed during network PIE.'
        super().complete()


def main():
    if unreal is None:
        return {'status':'not_run', 'planned_tests':list(TESTS), 'count':len(TESTS),
                'scope':'three connected local PIE worlds; native-tick queued gameplay request'}
    runner = HumanNetworkTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish('error', traceback.format_exc())
        started = False
    if started or not runner.done:
        unreal._basketbroom_native_network_test = runner
    return {'status':'started' if started else runner.final_status, 'report':str(REPORT), 'planned_cases':len(TESTS)}


if __name__ == '__main__':
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

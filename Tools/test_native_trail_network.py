"""Owned trail-color RPC and replication across three local PIE worlds.

Reuse the established network startup/settings restoration fixture. The host,
editing client and observing client must be distinct real worlds and owners.
Only public cosmetic setters and the generated Server RPC are called; no menu,
preference-file, replicated-property or gameplay-result writes are performed.
PIE-only queues dispatch from native Tick outside Python's local-only RPC guard.
Raw RPC calls include a valid control before testing nonfinite rejection.
This does not certify remote machines, adverse networks, hardware or rendering.
"""
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'.local/native-trail-network-results.json'
ARGS = {'max_wall_seconds':180, **globals().get('BRIDGE_ARGS', {})}
TESTS = (
    'three_connected_worlds_with_distinct_player_owners',
    'owned_client_public_color_setter_replicates_to_authority_and_observer',
    'raw_owned_color_rpc_valid_control_replicates',
    'raw_owned_color_rpc_rejects_nan_and_positive_negative_infinity',
    'nonowner_public_color_setter_cannot_change_remote_rider',
    'owned_client_team_default_reset_replicates',
    'cosmetic_edits_preserve_team_role_identity_scores_and_flight_energy',
    'original_cosmetic_state_restored_across_all_three_worlds',
    'managed_play_settings_restored_and_pie_ended',
)
spec = importlib.util.spec_from_file_location('_bb_trail_network_base', ROOT/'Tools/test_native_network.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.TESTS, base.REPORT, base.ARGS = TESTS, REPORT, ARGS
unreal, prop = base.unreal, base.prop


def rgb(color):
    return [float(color.r), float(color.g), float(color.b)]


def close(left, right):
    return len(left) == len(right) and all(abs(a-b) < 2e-5 for a, b in zip(left, right))


class TrailNetworkTests(base.NativeNetworkTests):
    player_count = 3

    def __init__(self):
        self.observer = None
        super().__init__()

    def write(self, status):
        rows = [{'name':name, **self.results.get(name, {'status':'not_run'})} for name in TESTS]
        base.write_json_atomic(REPORT, {
            'status':status, 'phase':self.phase, 'reason':self.reason,
            'scope':'one-process listen server, owned editing client and separate observing client in local PIE',
            'elapsed_wall_seconds':round(time.monotonic()-self.started, 3),
            'passed':sum(row['status']=='passed' for row in rows),
            'failed':sum(row['status']=='failed' for row in rows),
            'not_run':sum(row['status']=='not_run' for row in rows),
            'tests':rows, 'events':self.events, 'provenance':self.provenance,
            'settings_restored':self.settings_restored,
            'external_restore_required':base.net_mode_restore_actions(self.provenance),
            'not_covered':['separate processes or remote machines', 'latency, loss, reconnect or late joining',
                           'physical controllers and picker UI', 'actual emitted trails, rendering and performance',
                           'process relaunch or file persistence'],
            'fixture_policy':'Only owned disposable PIE cosmetics through public setters and real reflected Server RPCs. '
                'No team, role, ownership, flight energy, match state, material or preference-file writes. '
                'The inherited fixture restores managed editor play settings and ends all owned worlds.',
        })

    def begin(self):
        if unreal:
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
            self.require(world is not None and world.get_path_name().split('.')[0] == '/Basketbroom/Maps/BB_Regulation',
                         'Open the owned BB_Regulation map first')
            self.provenance['editor_world'] = world.get_path_name()
        return super().begin()

    def setup(self):
        worlds = self.worlds()
        self.provenance['observed_worlds'] = [
            {'world':world.get_path_name(), 'native_riders':len(self.actors(world, 'BBRiderCharacter'))}
            for world in worlds]
        if len(worlds) != self.player_count:
            return False
        contexts = [self.context(world) for world in worlds]
        if any(side is None for side in contexts):
            return False
        servers = [side for side in contexts if side['match'].has_authority()]
        clients = [side for side in contexts if not side['match'].has_authority()]
        if len(servers) != 1 or len(clients) != 2:
            return False
        identities = [self.player_id(side['pawn']) for side in contexts]
        if None in identities or len(set(identities)) != self.player_count:
            return False
        clients.sort(key=lambda side:self.player_id(side['pawn']))
        self.host, self.client, self.observer = servers[0], clients[0], clients[1]
        self.provenance['worlds'] = {label:side['world'].get_path_name() for label, side in self.sides()}
        self.provenance['human_player_ids'] = identities
        self.phase = 'running_cases'
        self.sequence = self.scenarios()
        self.advance()
        return True

    def sides(self):
        return (('server', self.host), ('owner', self.client), ('observer', self.observer))

    def copies(self):
        identity = self.player_id(self.client['pawn'])
        result = []
        for label, side in self.sides():
            candidates = [rider for rider in self.actors(side['world'], 'BBRiderCharacter')
                          if self.player_id(rider) == identity]
            self.require(len(candidates) == 1, 'Editing client must have one replica in '+label)
            result.append((label, candidates[0]))
        return result

    def color_states(self):
        return {label:{'custom':bool(prop(rider, 'bUseCustomBroomTrailColor')),
                      'rgb':rgb(rider.get_broom_trail_color())} for label, rider in self.copies()}

    def all_colors(self, custom, expected):
        return all(value['custom'] == custom and close(value['rgb'], expected)
                   for value in self.color_states().values())

    def identity_snapshot(self):
        return {label:{
            'roster':sorted((int(prop(rider, 'RosterIndex')), int(prop(rider, 'TeamIndex')),
                            int(prop(rider, 'Position')), int(prop(rider, 'AppearanceIdentity')),
                            self.player_id(rider), bool(rider.is_player_controlled()),
                            float(prop(rider, 'FlightBoostCharge')), float(prop(rider, 'FlightSuperRemaining')),
                            float(prop(rider, 'FlightAccelerationScale')))
                           for rider in self.actors(side['world'], 'BBRiderCharacter')),
            'match':self.snapshot(side),
            'local_controller':side['pawn'].get_controller().get_path_name(),
        } for label, side in self.sides()}

    def raw_rpc(self, color):
        self.queue_color(True, color, True)

    def queue_color(self, custom, color, raw=False):
        # Python's FEditorScriptExecutionGuard forces Actor RPC callspace local.
        # Queue only the request; native Tick uses the actual network transport.
        self.require(self.client['pawn'].development_queue_broom_trail_color(custom,color,raw),
                     'Owned PIE native-tick color dispatch rejected')

    def scenarios(self):
        yield self.wait(1)
        self.require(all(not self.live(side) for _, side in self.sides()), 'Fresh lobby is required')
        self.require(all(callable(getattr(rider, 'get_broom_trail_color', None)) for _, rider in self.copies()),
                     'Rebuild and load the trail cosmetic APIs')
        owner = self.client['pawn']
        self.require(owner.is_locally_controlled() and not owner.has_authority(), 'Editing pawn must be the real client owner')
        human_rosters = [self.human_roster(side) for _, side in self.sides()]
        self.record(TESTS[0], human_rosters[0] == human_rosters[1] == human_rosters[2]
                    and len(set(self.provenance['worlds'].values())) == 3
                    and unreal.GameplayStatics.get_game_mode(self.host['world']) is not None
                    and all(unreal.GameplayStatics.get_game_mode(side['world']) is None for side in (self.client, self.observer)),
                    worlds=self.provenance['worlds'], human_rosters=human_rosters)
        original = self.color_states()['owner']
        self.require(self.all_colors(original['custom'], original['rgb']), 'Initial cosmetic state must settle across replicas')
        identity_before = self.identity_snapshot()
        self.provenance.update(original_color=original, raw_rpc_boundary='PIE-only bounded request queue -> native Tick -> owned Server RPC',
                               preference_files_written=False)

        chosen = [.19, .36, .91]
        self.queue_color(True, unreal.LinearColor(*chosen, 1))
        yield self.wait(5, lambda:self.all_colors(True, chosen))
        self.record(TESTS[1], self.all_colors(True, chosen), states=self.color_states())
        self.require(self.all_colors(True, chosen), 'Owned public setter must replicate before rejection checks')

        control = [.82, .13, .44]
        self.raw_rpc(unreal.LinearColor(*control, 1))
        yield self.wait(5, lambda:self.all_colors(True, control))
        self.record(TESTS[2], self.all_colors(True, control), states=self.color_states())
        self.require(self.all_colors(True, control), 'Valid raw RPC must work before testing malformed payloads')

        invalid_results = []
        for label, bad in (('nan', float('nan')), ('positive_infinity', float('inf')), ('negative_infinity', -float('inf'))):
            self.raw_rpc(unreal.LinearColor(bad, .25, .5, 1))
            yield self.wait(.8)
            invalid_results.append({'input':label, 'unchanged':self.all_colors(True, control), 'states':self.color_states()})
        self.record(TESTS[3], all(row['unchanged'] for row in invalid_results), attempts=invalid_results)

        observer_replica = next(rider for label, rider in self.copies() if label == 'observer')
        self.require(not observer_replica.is_locally_controlled(), 'Observer replica must not be an owned pawn')
        observer_replica.set_broom_trail_color(True, unreal.LinearColor(.95, .95, .1, 1))
        yield self.wait(.8)
        self.record(TESTS[4], self.all_colors(True, control), states=self.color_states())

        team = int(prop(owner, 'TeamIndex'))
        expected_team = [.075, 1, .61] if team == 0 else [1, .245, .045]
        self.queue_color(False, unreal.LinearColor(1, 1, 1, 1))
        yield self.wait(5, lambda:self.all_colors(False, expected_team))
        self.record(TESTS[5], self.all_colors(False, expected_team), team=team, states=self.color_states())
        identity_after = self.identity_snapshot()
        self.record(TESTS[6], identity_before == identity_after, before=identity_before, after=identity_after)

        self.queue_color(original['custom'], unreal.LinearColor(*original['rgb'], 1))
        yield self.wait(5, lambda:self.all_colors(original['custom'], original['rgb']))
        self.record(TESTS[7], self.all_colors(original['custom'], original['rgb']), states=self.color_states(),
                    persistent_preferences='untouched; setters modify disposable PIE cosmetics only')


def main():
    if unreal is None and '--list' in sys.argv:
        return {'status':'not_run', 'planned_tests':list(TESTS), 'count':len(TESTS),
                'scope':'three local PIE worlds in one editor process'}
    runner = TrailNetworkTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish('error', traceback.format_exc())
        started = False
    if unreal and (started or not runner.done):
        unreal._basketbroom_native_network_test = runner
    return {'status':'started' if started else runner.final_status, 'report':str(REPORT), 'planned_cases':len(TESTS)}


if __name__ == '__main__':
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

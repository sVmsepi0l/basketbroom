"""Observe native broom trails in an owned, disposable UE5.8 PIE world.

Movement and boost use simulated gamepad EKeys through ordinary PlayerInput.
Actual catches, throws and accepted goals earn every unit of boost charge.
Only disposable transforms/ticks and the public cosmetic setter are fixtures;
the suite never writes charge, scores, trail history, instances or materials.
Component/geometry observations are not rendered-pixel, physical-controller,
remote-replication or performance evidence. The color picker has its own suite.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'.local/native-broom-trails-results.json'
CASES = (
    'sixteen_riders_have_three_bounded_safe_tracer_components',
    'both_team_defaults_are_observed_without_changing_identity',
    'ordinary_input_movement_emits_bounded_world_space_geometry',
    'stationary_history_and_geometry_expire',
    'short_teleport_immediately_clears_existing_trail',
    'large_nonteleport_jump_resets_history_without_arena_spanning_segment',
    'actual_goal_earns_charge_before_partial_boost',
    'earned_partial_boost_increases_trail_lifetime_and_emission',
    'braking_stops_boost_and_lets_residual_trail_expire',
    'four_more_actual_goals_fill_capped_charge',
    'fresh_full_charge_trigger_extends_trail_further',
    'pause_freezes_existing_trail_geometry',
    'public_custom_color_clamps_finite_rgb_without_gameplay_mutation',
    'nonfinite_custom_rgb_is_rejected',
    'paused_color_change_updates_existing_dynamic_materials',
    'team_default_reset_restores_effective_color',
)
spec = importlib.util.spec_from_file_location('_bb_broom_flight_base', ROOT/'Tools/test_native_flight_controls.py')
flight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flight)
ctrl = flight.ctrl
unreal, prop, xyz, vector = flight.unreal, flight.prop, flight.xyz, flight.vector
receipt_spec = importlib.util.spec_from_file_location('_bb_broom_receipts', ROOT/'Tools/native_test_receipts.py')
receipts = importlib.util.module_from_spec(receipt_spec)
receipt_spec.loader.exec_module(receipts)
flight.REPORT = ctrl.REPORT = ctrl.base.REPORT = REPORT
ctrl.base.TEST_NAMES = CASES
ctrl.base.ARGS = {'max_wall_seconds':240, **globals().get('BRIDGE_ARGS', {})}


def close(left, right, tolerance=2e-5):
    return len(left) == len(right) and all(abs(a-b) <= tolerance for a, b in zip(left, right))


def rgba(color):
    return [float(color.r), float(color.g), float(color.b), float(color.a)]


class BroomTrailTests(flight.FlightTests):
    def __init__(self):
        self.original_color = None
        self.observed_limits = {'observations':0, 'max_samples':0, 'max_segments':0, 'invalid':[]}
        super().__init__()

    def write_report(self, status, reason=None):
        data = receipts.single_world_payload(self, CASES, status, reason,
                    unreal.SystemLibrary.get_engine_version() if unreal else None)
        data.update(
            scope='single-world PIE trail geometry and material state driven by local simulated gamepad gameplay',
            hardware_claim=False, rendered_pixels_claim=False, remote_replication_claim=False,
            observed_limits=self.observed_limits,
            not_covered=['physical controller, USB/Bluetooth transport or hardware disconnect',
                         'remote ownership, color RPC transport and replicated movement',
                         'rendered appearance, owner/remote pixels, frame time or packaged performance',
                         'full color-picker interaction or persistence; use test_native_trail_color.py',
                         'Transformation/concealment spell behavior; use test_native_sport_spells.py'],
            fixture_policy='Fresh owned PIE; CPU transforms/ticks and free-ball fixtures are isolated. '
                'Movement uses PlayerController::InputKey and normal PlayerInput. Actual thrown quaffle '
                'goals earn charge. Teleport fixtures change owned pawn transforms. Color validation '
                'uses the public local cosmetic setter, restores its original in-memory value and '
                'does not write preference files. No direct score, boost, history, instance or material writes.')
        receipts.write_json_atomic(REPORT, data)

    def trail(self, rider=None):
        values = [float(value) for value in (rider or self.pawn).development_get_broom_trail_state()]
        self.require(len(values) == 10 and all(math.isfinite(value) for value in values),
                     'Expected ten finite native trail diagnostic fields')
        return values

    def observe_limits(self):
        values = self.trail()
        limits = self.observed_limits
        limits['observations'] += 1
        limits['max_samples'] = max(limits['max_samples'], values[0])
        limits['max_segments'] = max(limits['max_segments'], values[1])
        valid = (0 <= values[0] <= 80 and 0 <= values[1] <= 240 and values[9] == 3
                 and 0 <= values[3] <= 1 and .2999 <= values[4] <= 1.1501)
        if not valid and len(limits['invalid']) < 8:
            limits['invalid'].append(values)
        return values

    def strands(self, rider=None):
        return sorted([part for part in (rider or self.pawn).get_components_by_class(unreal.InstancedStaticMeshComponent)
                       if 'BB.BroomTracer' in [str(tag) for tag in prop(part, 'ComponentTags')]],
                      key=lambda part: part.get_name())

    def geometry(self):
        """Read actual allocated instances, including their zero-scale unused slots."""
        rows, nonzero = [], []
        for part in self.strands():
            instances = []
            for index in range(part.get_instance_count()):
                transform = part.get_instance_transform(index, world_space=True)
                self.require(transform is not None, 'Allocated instance must have a transform')
                # Do not round the tapered radius to millimetres: valid thin
                # outer segments can have component scales smaller than .001.
                scale = [float(transform.scale3d.x), float(transform.scale3d.y), float(transform.scale3d.z)]
                if all(value > 0 for value in scale):
                    instances.append({'position':xyz(transform.translation), 'scale':scale})
            nonzero.extend(instances)
            rows.append({'name':part.get_name(), 'allocated':part.get_instance_count(),
                         'active':len(instances), 'visible_flag':bool(part.is_visible()),
                         'instances':instances})
        encoded = json.dumps(rows, sort_keys=True).encode('utf-8')
        return {'components':[dict(row, instances=None) for row in rows],
                'active':len(nonzero),
                'max_segment_length_cm':max([row['scale'][2]*100 for row in nonzero], default=0),
                'geometry_sha256':hashlib.sha256(encoded).hexdigest()}

    def materials(self):
        values = []
        for part in self.strands():
            material = part.get_material(0)
            self.require(isinstance(material, unreal.MaterialInstanceDynamic), 'Tracer must own a dynamic material')
            values.append({'name':part.get_name(), 'material':material.get_path_name(),
                           'tint':rgba(material.get_vector_parameter_value('Tint')),
                           'glow':float(material.get_scalar_parameter_value('Glow'))})
        return values

    def gameplay_snapshot(self):
        return {'team':int(prop(self.pawn, 'TeamIndex')), 'role':int(prop(self.pawn, 'Position')),
                'slot':int(prop(self.pawn, 'RosterIndex')), 'scores':self.scores(),
                'flight':self.flight(), 'roster':self.roster()}

    def component_checks(self):
        rows = []
        for rider in self.riders:
            parts = self.strands(rider)
            checks = []
            for part in parts:
                checks.append({'name':part.get_name(), 'allocated':part.get_instance_count(),
                    'no_collision':part.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
                        and str(part.get_collision_profile_name()) == 'NoCollision',
                    'no_overlap':not bool(prop(part, 'bGenerateOverlapEvents')),
                    'no_navigation':not bool(prop(part, 'bCanEverAffectNavigation')),
                    'no_shadow':not bool(prop(part, 'CastShadow')),
                    'no_indirect_light':not bool(prop(part, 'bAffectDynamicIndirectLighting')),
                    'no_distance_field_light':not bool(prop(part, 'bAffectDistanceFieldLighting')),
                    'owner_hidden':bool(prop(part, 'bOwnerNoSee')) and not bool(prop(part, 'bOnlyOwnerSee')),
                    'world_space':all(bool(prop(part, name)) for name in ('bAbsoluteLocation', 'bAbsoluteRotation', 'bAbsoluteScale')),
                    'cosmetic_unreplicated':not bool(prop(part, 'bReplicates')),
                    'mesh_and_material':prop(part, 'StaticMesh') is not None and part.get_material(0) is not None})
            valid = ([part.get_name() for part in parts] == ['BroomTracer0', 'BroomTracer1', 'BroomTracer2']
                     and all(row['allocated'] == 80 and all(value for key, value in row.items()
                         if key not in ('name', 'allocated')) for row in checks)
                     and self.trail(rider)[9] == 3)
            rows.append({'slot':int(prop(rider, 'RosterIndex')), 'valid':valid, 'components':checks})
        return rows

    def start_ordinary_trail(self):
        yield from self.anchor((-2800, -1000, 1800))
        start = xyz(self.pawn.get_actor_location())
        self.pad('Gamepad_LeftY', 1)
        yield self.wait_until(lambda: self.state()[1] > .9 and self.trail()[1] >= 6, timeout=3)
        yield self.wait(.4, self.observe_limits)
        self.require(self.trail()[1] >= 6, 'Ordinary live flight must produce geometry before reset fixture')
        end = xyz(self.pawn.get_actor_location())
        return {'start':start, 'end':end, 'forward_cm':end[0]-start[0]}

    def scenarios(self):
        yield self.wait(max(3, min(60, float(ctrl.base.ARGS.get('focus_grace_seconds', 10)))))
        for method in ('development_get_broom_trail_state', 'set_broom_trail_color', 'development_get_flight_state'):
            self.require(callable(getattr(self.pawn, method, None)), 'Current trail/flight API is required: '+method)
        self.require(self.controller.is_actor_tick_enabled(), 'PlayerController ticks must process native input')
        self.require(int(prop(self.pawn, 'TeamIndex')) == 0 and int(prop(self.pawn, 'Position')) == 3,
                     'Goal fixture requires fresh Teal host Ranger')
        self.original_color = (bool(prop(self.pawn, 'bUseCustomBroomTrailColor')), rgba(prop(self.pawn, 'CustomBroomTrailColor')))
        self.original_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        self.require(abs(self.original_dilation-1) < .001, 'Run cadence-sensitive trail checks at ordinary world time dilation')
        self.provenance.update(input_boundary='FInputKeyEventArgs::CreateSimulated -> PlayerController::InputKey -> PlayerInput/bindings',
                               original_cosmetic=self.original_color, controller_ticks='ordinary engine input processing retained',
                               editor_assets_saved=False, preference_files_written=False,
                               diagnostics=['samples','segments','resets','boost_blend','lifetime','red','green','blue','custom','components'])
        components = self.component_checks()
        self.record(CASES[0], len(components) == 16 and all(row['valid'] for row in components), riders=components)
        identity = self.gameplay_snapshot()
        self.pawn.set_broom_trail_color(False, unreal.LinearColor(1, 1, 1, 1))
        teal = self.trail()
        copper = self.trail(next(rider for rider in self.riders if int(prop(rider, 'TeamIndex')) == 1))
        self.record(CASES[1], close(teal[5:8], [.075, 1, .61]) and close(copper[5:8], [1, .245, .045])
                    and teal[8] == copper[8] == 0 and self.gameplay_snapshot() == identity, teal=teal, copper=copper)

        yield from self.tap('Gamepad_FaceButton_Bottom', lambda: bool(prop(self.match, 'bLive')))
        self.require(prop(self.match, 'bLive'), 'Cross must start a live match')
        self.isolate()
        motion = yield from self.start_ordinary_trail()
        normal, normal_geometry, normal_materials = self.observe_limits(), self.geometry(), self.materials()
        self.record(CASES[2], motion['forward_cm'] > 30 and self.flight()[0] == 0 and self.flight()[2] == 1 and normal[3] < .01
                    and 0 < normal[0] <= 80 and 0 < normal[1] <= 240 and normal_geometry['active'] == normal[1]
                    and all(row['visible_flag'] for row in normal_geometry['components'])
                    and not self.observed_limits['invalid'], movement=motion,
                    trail=normal, geometry=normal_geometry, materials=normal_materials)
        yield from self.release_axis('Gamepad_LeftY', 1)
        self.component(self.pawn, unreal.CharacterMovementComponent).stop_movement_immediately()
        yield self.wait(1.5, self.observe_limits)
        stopped = self.trail()
        self.record(CASES[3], stopped[0] == stopped[1] == 0 and not any(part.is_visible() for part in self.strands()), trail=stopped)

        yield from self.start_ordinary_trail()
        before = self.trail()
        point = xyz(self.pawn.get_actor_location())
        self.pawn.set_actor_location(vector((point[0], point[1]+100, point[2])), False, True)
        after = self.trail()
        self.record(CASES[4], before[1] > 0 and after[0] == after[1] == 0 and after[2] > before[2]
                    and not any(part.is_visible() for part in self.strands()), before=before, immediately_after=after,
                    teleport_distance_cm=100, teleport_physics=True)
        yield self.wait(.5, self.observe_limits)
        before = self.trail()
        self.require(before[1] > 0, 'Trail must rebuild before independent distance-jump fixture')
        point = xyz(self.pawn.get_actor_location())
        self.pawn.set_actor_location(vector((point[0], point[1]+2400, point[2])), False, False)
        yield self.wait_until(lambda: self.trail()[2] > before[2], timeout=2)
        after, geometry = self.trail(), self.geometry()
        self.record(CASES[5], after[2] > before[2] and geometry['max_segment_length_cm'] < 350
                    and not self.observed_limits['invalid'], before=before, after=after, geometry=geometry,
                    displacement_cm=2400, teleport_physics=False)
        yield from self.release_axis('Gamepad_LeftY', 1)
        self.component(self.pawn, unreal.CharacterMovementComponent).stop_movement_immediately()

        yield from self.score_goal()
        self.record(CASES[6], self.flight()[0] == 25, flight=self.flight(), scores=self.scores())
        yield from self.anchor((-2800, -1000, 1800))
        yield from self.trigger('Gamepad_RightTriggerAxis', 1, 3)
        yield self.wait(.55, self.observe_limits)
        partial, partial_geometry, partial_materials = self.trail(), self.geometry(), self.materials()
        self.record(CASES[7], 0 < self.flight()[0] < 25 and self.flight()[2] > 1 and .35 < partial[3] < .65
                    and partial[4] > normal[4]+.25 and partial[1] > 0 and partial_geometry['active'] == partial[1]
                    and all(current['glow'] > prior['glow']+3 for current, prior in zip(partial_materials, normal_materials))
                    and not self.observed_limits['invalid'], trail=partial, flight=self.flight(),
                    geometry=partial_geometry, materials=partial_materials)
        yield from self.trigger('Gamepad_LeftTriggerAxis', 1, 4)
        held_charge = self.flight()[0]
        yield self.wait(1.5, self.observe_limits)
        braked = self.trail()
        self.record(CASES[8], self.pawn.get_velocity().length() < 5 and self.flight()[2] == 1
                    and abs(self.flight()[0]-held_charge) < .01 and braked[0] == braked[1] == 0 and braked[3] < .01,
                    trail=braked, flight=self.flight(), charge_when_braked=held_charge)
        yield from self.trigger('Gamepad_RightTriggerAxis', 0, 3)
        yield from self.trigger('Gamepad_LeftTriggerAxis', 0, 4)
        for _ in range(4):
            yield from self.score_goal()
        self.record(CASES[9], self.flight()[0] == 100, flight=self.flight(), scores=self.scores())
        yield from self.anchor((-2800, -1000, 1800))
        yield from self.trigger('Gamepad_RightTriggerAxis', 1, 3)
        yield self.wait(.55, self.observe_limits)
        full, full_geometry, full_materials = self.trail(), self.geometry(), self.materials()
        self.record(CASES[10], self.flight()[0] == 0 and self.flight()[1] > 0 and self.flight()[2] == 2
                    and full[3] > .85 and full[4] > partial[4]+.25 and full[1] > 0
                    and full_geometry['active'] == full[1] and not self.observed_limits['invalid']
                    and all(current['glow'] > prior['glow']+3 for current, prior in zip(full_materials, partial_materials)),
                    trail=full, flight=self.flight(), geometry=full_geometry, materials=full_materials)

        yield from self.tap('Gamepad_Special_Right', lambda: bool(prop(self.pawn, 'bPauseMenuOpen')))
        self.require(unreal.GameplayStatics.is_game_paused(self.world), 'Options must pause the world')
        frozen, frozen_geometry = self.trail(), self.geometry()
        frozen_seconds = float(unreal.GameplayStatics.get_time_seconds(self.world))
        yield self.wait(.4)
        self.record(CASES[11], frozen[1] > 0 and self.trail() == frozen
                    and self.geometry() == frozen_geometry
                    and float(unreal.GameplayStatics.get_time_seconds(self.world)) == frozen_seconds,
                    trail=frozen, geometry=frozen_geometry)
        gameplay = self.gameplay_snapshot()
        self.pawn.set_broom_trail_color(True, unreal.LinearColor(-2, .4, 3, .2))
        custom = self.trail()
        self.record(CASES[12], custom[8] == 1 and close(custom[5:8], [0, .4, 1])
                    and close(rgba(prop(self.pawn, 'CustomBroomTrailColor')), [0, .4, 1, 1])
                    and self.gameplay_snapshot() == gameplay, submitted=[-2, .4, 3, .2], trail=custom)
        rejected = []
        for channel in range(3):
            for invalid, label in ((float('nan'), 'nan'), (float('inf'), 'positive_infinity'), (float('-inf'), 'negative_infinity')):
                values = [.2, .5, .8, 1]
                values[channel] = invalid
                self.pawn.set_broom_trail_color(True, unreal.LinearColor(*values))
                rejected.append({'channel':channel, 'invalid':label,
                                 'unchanged':self.trail() == custom and self.gameplay_snapshot() == gameplay})
        self.record(CASES[13], all(row['unchanged'] for row in rejected), submissions=rejected)
        yield self.wait(.25)
        materials = self.materials()
        expected = [[.28, .568, 1, 1], [0, .4, 1, 1], [0, .4, 1, 1]]
        self.record(CASES[14], all(close(row['tint'], color) for row, color in zip(materials, expected))
                    and len(materials) == 3 and self.geometry() == frozen_geometry
                    and unreal.GameplayStatics.is_game_paused(self.world), materials=materials, expected_tints=expected)
        self.pawn.set_broom_trail_color(False, unreal.LinearColor(1, 0, 0, 0))
        default = self.trail()
        self.record(CASES[15], default[8] == 0 and close(default[5:8], [.075, 1, .61])
                    and self.gameplay_snapshot() == gameplay, trail=default)
        yield from self.tap('Gamepad_Special_Right', lambda: not prop(self.pawn, 'bPauseMenuOpen'))

    def finish(self, status, reason=None):
        if unreal and self.owns_play and self.pawn and self.original_color is not None:
            try:
                enabled, color = self.original_color
                self.pawn.set_broom_trail_color(enabled, unreal.LinearColor(*color))
                self.provenance['original_in_memory_color_restored'] = (
                    bool(prop(self.pawn, 'bUseCustomBroomTrailColor')) == enabled
                    and (not enabled or close(rgba(prop(self.pawn, 'CustomBroomTrailColor')), color)))
                self.require(self.provenance['original_in_memory_color_restored'], 'Original cosmetic value must restore')
            except Exception:
                status, reason = 'error', (reason or '')+'\nTrail cleanup: '+traceback.format_exc()
        super().finish(status, reason)


def main():
    if unreal is None:
        return {'status':'not_run', 'planned_tests':list(CASES), 'count':len(CASES),
                'hardware_claim':False, 'rendered_pixels_claim':False, 'remote_replication_claim':False,
                'instruction':'Run through editor bridge with a fresh stopped UE5.8 native arena and focus its PIE viewport.'}
    runner = BroomTrailTests()
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

"""Capture real moving broom trails through the owned PIE game viewport.

Three frames each show ordinary, earned partial-charge and earned super flight.
An existing PIE hero-camera copy follows from behind/alongside the rider; native
PlayerController input ticks, control rotation and flight axes remain active.
During captures only, quarter-speed world time limits screenshot I/O hitches;
frames remain at least 200ms apart in gameplay time. Normal time is restored
before the next actual-goal fixture and during cleanup.
PNG integrity and request-time gameplay state are checked. Images still require
visual review; this is not hardware, remote replication or performance evidence.
"""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'.local/native-broom-trail-visual-results.json'
CASES = (
    'ordinary_motion_three_viewport_images_written',
    'earned_partial_boost_three_viewport_images_written',
    'earned_super_boost_three_viewport_images_written',
    'owned_pie_camera_hud_time_and_original_view_restored',
)
spec = importlib.util.spec_from_file_location('_bb_trail_visual_base', ROOT/'Tools/test_native_broom_trails.py')
trail = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trail)
unreal, prop, xyz, vector = trail.unreal, trail.prop, trail.xyz, trail.vector
trail.ctrl.base.TEST_NAMES, trail.ctrl.base.REPORT = CASES, REPORT
trail.ctrl.base.ARGS = {'max_wall_seconds':240, **globals().get('BRIDGE_ARGS', {})}


def png_dimensions(path):
    try:
        data = path.read_bytes()
        if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) < 32:
            return None
        dimensions, offset = struct.unpack('>II', data[16:24]), 8
        while offset+12 <= len(data):
            length = struct.unpack('>I', data[offset:offset+4])[0]
            if offset+length+12 > len(data):
                return None
            if data[offset+4:offset+8] == b'IEND':
                return dimensions if length == 0 else None
            offset += length+12
    except OSError:
        pass
    return None


class BroomTrailVisualTests(trail.BroomTrailTests):
    def __init__(self):
        self.camera = self.saved_camera = self.original_view = self.saved_hud = None
        self.captures = []
        self.directory = ROOT/'.local/native-broom-trail-visual'/str(time.time_ns())
        super().__init__()

    def write_report(self, status, reason=None):
        data = trail.receipts.single_world_payload(self, CASES, status, reason,
                    unreal.SystemLibrary.get_engine_version() if unreal else None)
        data.update(scope='real owned game-viewport images during local simulated-input flight with actual earned boost; capture-only world dilation 0.25',
                    captures=self.captures, hardware_claim=False, remote_replication_claim=False,
                    visual_review_status='rendered_pending_visual_review' if self.captures else 'not_rendered',
                    not_covered=['image appearance until separately reviewed', 'physical controller hardware',
                                 'remote replication and network ownership', 'performance and packaged runtime'],
                    fixture_policy='Disposable PIE CPU/free-ball fixtures and existing hero-camera copy only. '
                        'Real PlayerInput and flight remain enabled. Actual thrown quaffle goals earn charge. '
                        'Chase camera changes view target only; it does not set control rotation or flight input. '
                        'Captures use world time dilation 0.25 with 200ms gameplay-time spacing so PNG I/O '
                        'does not trigger the native long-frame trail/input safety resets. '
                        'The original camera, HUD visibility, view and local cosmetic setting are restored. '
                        'No direct boost, score, trail geometry or material writes.')
        trail.receipts.write_json_atomic(REPORT, data)

    def camera_snapshot(self):
        rotation = self.camera.get_actor_rotation()
        return {'location':xyz(self.camera.get_actor_location()),
                'rotation':[float(rotation.pitch), float(rotation.yaw), float(rotation.roll)],
                'scale':xyz(self.camera.get_actor_scale3d()),
                'fov':float(prop(self.component(self.camera, unreal.CameraComponent), 'FieldOfView'))}

    def select_camera(self):
        actors = unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.CameraActor)
        candidates = [actor for actor in actors if actor.get_actor_label() == 'BB Hero Camera'
                      and actor.get_path_name().startswith(self.world.get_path_name()+':')]
        self.require(len(candidates) == 1, 'Exactly one existing owned PIE hero-camera copy is required')
        self.camera = candidates[0]
        self.saved_camera = self.camera_snapshot()
        self.original_view = self.controller.get_view_target()
        hud = self.controller.get_hud()
        self.require(hud is not None, 'Owned viewport HUD is required')
        self.saved_hud = (hud, bool(prop(hud, 'bShowHUD')))
        hud.set_editor_property('bShowHUD', False)
        self.component(self.camera, unreal.CameraComponent).set_field_of_view(65)
        self.provenance['camera_fixture'] = {'actor':self.camera.get_path_name(), 'original_state':self.saved_camera,
            'position_offset_cm':[-1000, -1800, 500], 'look_at_offset_cm':[-450, 0, -40], 'fov':65,
            'ownership':'existing disposable PIE copy; no editor actor or asset changes'}

    def follow_camera(self):
        point = xyz(self.pawn.get_actor_location())
        position = vector((point[0]-1000, point[1]-1800, point[2]+500))
        target = vector((point[0]-450, point[1], point[2]-40))
        self.camera.set_actor_location(position, False, True)
        self.camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(position, target), True)

    def capture_motion(self, label, case):
        self.directory.mkdir(parents=True, exist_ok=True)
        prior_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        # A 2617x1563 Shot took ~0.41 seconds in the first captured receipt.
        # At normal world speed that legitimately clears trail history (>0.2s)
        # and can cancel the held boost (>0.35s). Change only simulation pacing
        # while reading pixels; do not weaken those native safety policies or
        # fabricate geometry/charge. Wait below still spaces frames by 0.2 game
        # seconds, so it captures distinct moving states at the same cm/game-s.
        unreal.GameplayStatics.set_global_time_dilation(self.world, .25)
        for ball in self.balls.values():
            # Keep isolated game balls out of the composed trail view. They are
            # disposable copies; the actual-goal helper resets its free ball.
            if prop(ball, 'Holder') is None:
                ball.set_actor_tick_enabled(False)
                ball.set_actor_location(vector((0, 22000+int(prop(ball, 'BallIndex'))*300, 1800)), False, True)
        self.follow_camera()
        control_before = self.controller.get_control_rotation()
        self.controller.set_view_target_with_blend(self.camera, 0.0)
        frames = []
        for index in range(3):
            # Observe rebuilt geometry after any preceding readback hitch. An
            # empty path is never accepted merely because a PNG was written.
            before_wait = self.trail()
            next_game_time = float(unreal.GameplayStatics.get_time_seconds(self.world))+.2
            ready = lambda: (float(unreal.GameplayStatics.get_time_seconds(self.world)) >= next_game_time
                             and self.trail()[1] >= 18)
            yield self.wait_until(ready, fixture=self.follow_camera, timeout=4)
            self.require(ready(), 'Moving trail must contain at least 18 real segments before capture')
            self.follow_camera()
            path = self.directory/('%s-%02d.png' % (label, index+1))
            self.require(not path.exists(), 'Capture filename must be unique')
            state, flight_state = self.trail(), self.flight()
            mode_valid = ((label == 'ordinary' and flight_state[0] == 0 and flight_state[2] == 1)
                          or (label == 'partial' and 0 < flight_state[0] < 25 and 1 < flight_state[2] < 2)
                          or (label == 'super' and flight_state[0] == 0 and flight_state[1] > 0 and flight_state[2] == 2))
            entry = {'label':label, 'frame':index+1, 'file':str(path),
                     'request_game_seconds':float(unreal.GameplayStatics.get_time_seconds(self.world)),
                     'request_world_time_dilation':float(unreal.GameplayStatics.get_global_time_dilation(self.world)),
                     'resets_while_waiting_for_capture':state[2]-before_wait[2],
                     'request_location':xyz(self.pawn.get_actor_location()),
                     'request_speed_cm_s':float(self.pawn.get_velocity().length()),
                     'request_trail_state':state, 'request_flight_state':flight_state,
                     'request_controller_input_state':self.state(),
                     'request_mode_valid':mode_valid, 'view_target':self.controller.get_view_target().get_path_name(),
                     'camera':self.camera_snapshot(), 'visual_review':'pending'}
            command = 'Shot filename='+path.as_posix()+' -nosuffix'
            entry['command'] = command
            unreal.SystemLibrary.execute_console_command(self.world, command, self.controller)
            frames.append(entry)
            self.captures.append(entry)
        yield self.wait_until(lambda: all(png_dimensions(Path(row['file'])) for row in frames),
                              fixture=self.follow_camera, timeout=15)
        for row in frames:
            path = Path(row['file'])
            dimensions = png_dimensions(path)
            row['dimensions'] = list(dimensions) if dimensions else None
            row['bytes'] = path.stat().st_size if path.exists() else None
        control_after = self.controller.get_control_rotation()
        unchanged = max(abs(float(getattr(control_after, name)-getattr(control_before, name)))
                        for name in ('pitch', 'yaw', 'roll')) < .01
        advancing = all(later['request_game_seconds']-earlier['request_game_seconds'] >= .19
                        and later['request_location'][0]-earlier['request_location'][0] > 10
                        for earlier, later in zip(frames, frames[1:]))
        passed = (all(row['dimensions'] and row['dimensions'][0] >= 640 and row['dimensions'][1] >= 360
                      and row['request_mode_valid'] and row['request_speed_cm_s'] > 80
                      and row['request_trail_state'][1] >= 6
                      and row['view_target'] == self.camera.get_path_name() for row in frames)
                  and advancing and unchanged and self.controller.is_actor_tick_enabled())
        self.record(case, passed, frames=frames, controller_rotation_unchanged=unchanged,
                    gameplay_time_and_position_advance=advancing,
                    pixels='written; appearance requires visual review')
        self.require(passed, 'All three '+label+' images need valid request-time movement and complete PNGs')
        self.controller.set_view_target_with_blend(self.original_view, 0.0)
        unreal.GameplayStatics.set_global_time_dilation(self.world, prior_dilation)

    def restore_view(self):
        if self.controller and self.original_view:
            self.controller.set_view_target_with_blend(self.original_view, 0.0)
        if self.saved_hud:
            hud, visible = self.saved_hud
            hud.set_editor_property('bShowHUD', visible)
        if self.camera and self.saved_camera:
            state = self.saved_camera
            self.camera.set_actor_location(vector(state['location']), False, True)
            self.camera.set_actor_rotation(unreal.Rotator(pitch=state['rotation'][0], yaw=state['rotation'][1], roll=state['rotation'][2]), True)
            self.camera.set_actor_scale3d(vector(state['scale']))
            self.component(self.camera, unreal.CameraComponent).set_field_of_view(state['fov'])

    def scenarios(self):
        yield self.wait(max(3, min(60, float(trail.ctrl.base.ARGS.get('focus_grace_seconds', 10)))))
        self.require(self.controller.is_actor_tick_enabled(), 'PlayerInput ticks must remain enabled')
        self.require(int(prop(self.pawn, 'TeamIndex')) == 0 and int(prop(self.pawn, 'Position')) == 3,
                     'Actual goal fixture requires fresh Teal host Ranger')
        self.original_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        self.require(abs(self.original_dilation-1) < .001, 'Goal fixtures start at ordinary world time dilation')
        self.original_color = (bool(prop(self.pawn, 'bUseCustomBroomTrailColor')), trail.rgba(prop(self.pawn, 'CustomBroomTrailColor')))
        self.pawn.set_broom_trail_color(False, unreal.LinearColor(1, 1, 1, 1))
        self.provenance.update(input_boundary='simulated EKeys -> native PlayerInput -> real flight bindings',
                               charge_fixture='accepted caught-and-thrown quaffle goals; never assigned',
                               capture_timing='three Shot requests per mode, separated by at least 200ms gameplay time at world dilation 0.25; request-time state recorded',
                               capture_hitch_mitigation='quarter-speed capture pacing plus observed geometry rebuild; native hitch resets unchanged',
                               controller_ticks='remain enabled', original_cosmetic=self.original_color)
        yield from self.tap('Gamepad_FaceButton_Bottom', lambda: bool(prop(self.match, 'bLive')))
        self.require(prop(self.match, 'bLive'), 'Cross must start the native match')
        self.isolate()
        self.select_camera()
        yield from self.start_ordinary_trail()
        yield from self.capture_motion('ordinary', CASES[0])
        yield from self.release_axis('Gamepad_LeftY', 1)
        self.component(self.pawn, unreal.CharacterMovementComponent).stop_movement_immediately()
        yield from self.score_goal()
        yield from self.anchor((-3500, -1000, 1800))
        yield from self.trigger('Gamepad_RightTriggerAxis', 1, 3)
        yield self.wait(.25)
        yield from self.capture_motion('partial', CASES[1])
        yield from self.trigger('Gamepad_RightTriggerAxis', 0, 3)
        self.component(self.pawn, unreal.CharacterMovementComponent).stop_movement_immediately()
        for _ in range(4):
            yield from self.score_goal()
        self.require(self.flight()[0] == 100, 'Four additional accepted goals must fill the capped meter')
        yield from self.anchor((-3500, -1000, 1800))
        yield from self.trigger('Gamepad_RightTriggerAxis', 1, 3)
        yield self.wait(.25)
        yield from self.capture_motion('super', CASES[2])
        yield from self.trigger('Gamepad_RightTriggerAxis', 0, 3)
        self.component(self.pawn, unreal.CharacterMovementComponent).stop_movement_immediately()
        before = self.saved_camera
        self.restore_view()
        after = self.camera_snapshot()
        restored = (all(trail.close(before[key], after[key], .01) for key in ('location', 'rotation', 'scale'))
                    and abs(before['fov']-after['fov']) < .01)
        self.record(CASES[3], restored and self.controller.get_view_target() == self.original_view
                    and bool(prop(self.saved_hud[0], 'bShowHUD')) == self.saved_hud[1]
                    and self.controller.is_actor_tick_enabled()
                    and abs(float(unreal.GameplayStatics.get_global_time_dilation(self.world))-self.original_dilation) < .001,
                    original=before, restored=after,
                    restored_world_time_dilation=float(unreal.GameplayStatics.get_global_time_dilation(self.world)),
                    view=self.controller.get_view_target().get_path_name())

    def finish(self, status, reason=None):
        if unreal and self.owns_play:
            try:
                self.restore_view()
                self.provenance['camera_cleanup'] = 'Original view, HUD and owned PIE camera transform/FOV restored'
            except Exception:
                status, reason = 'error', (reason or '')+'\nCamera cleanup: '+traceback.format_exc()
        super().finish(status, reason)


def main():
    if unreal is None:
        return {'status':'not_run', 'planned_tests':list(CASES), 'count':len(CASES), 'planned_images':9,
                'hardware_claim':False, 'remote_replication_claim':False, 'visual_review_status':'not_rendered'}
    runner = BroomTrailVisualTests()
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

"""Capture configured human riders and their actual brooms in fresh native PIE.

Bridge operation=start owns a new, ordinary non-live session through
native_play_session.py. It waits for sixteen runtime cosmetics, captures both
athletes in both team colors from two angles, then captures the real owner's
first-person view. operation=inspect reads progress; operation=stop cancels only
this tool's session. It never joins an existing PIE session or edits assets,
saved maps, configuration, poses, wardrobe, teams, scores, or player transforms.

Only the existing PIE hero-camera copy, local HUD visibility, and view target
are temporarily changed. Native Body/Face/garment animation is observed intact.
The camera/HUD/view are restored and owned PIE shutdown is observed. PNGs and
bone/grip diagnostics are evidence for review, not automatic visual acceptance.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import importlib.util
import json
import struct
import time
import traceback

import unreal

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'DevelopmentHarness/BasketbroomDev.uproject'
REPORT = ROOT / '.local/native-human-rider-preview.json'
KEY = '_basketbroom_native_human_rider_preview'
ARGS = globals().get('BRIDGE_ARGS', {})
spec = importlib.util.spec_from_file_location('_bb_human_preview_session', ROOT / 'Tools/native_play_session.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
prop, xyz, rotation = base.prop, base.xyz, base.rotation


def path(obj):
    return obj.get_path_name() if obj is not None else None


def png_dimensions(filename):
    try:
        data = filename.read_bytes()
    except OSError:
        return None
    if len(data) < 40 or not data.startswith(b'\x89PNG\r\n\x1a\n'):
        return None
    offset = 8
    while offset + 12 <= len(data):
        size = struct.unpack('>I', data[offset:offset + 4])[0]
        if offset + size + 12 > len(data):
            return None
        if data[offset + 4:offset + 8] == b'IEND':
            return list(struct.unpack('>II', data[16:24])) if size == 0 else None
        offset += size + 12
    return None


def named_component(actor, cls, name):
    matches = [c for c in actor.get_components_by_class(cls) if c.get_name() == name]
    if len(matches) != 1:
        raise RuntimeError('Expected one ' + name + ' component on ' + actor.get_path_name())
    return matches[0]


def frame(component):
    return {'location': xyz(component.get_world_location()), 'rotation': rotation(component.get_world_rotation()),
            'scale': xyz(component.get_world_scale()), 'forward': xyz(component.get_forward_vector()),
            'right': xyz(component.get_right_vector()), 'up': xyz(component.get_up_vector())}


def frame_point(component, local):
    origin = component.get_world_location()
    axes = (component.get_forward_vector(), component.get_right_vector(), component.get_up_vector())
    scale = component.get_world_scale()
    values = [float(origin.x), float(origin.y), float(origin.z)]
    for amount, axis, factor in zip(local, axes, (scale.x, scale.y, scale.z)):
        for i, name in enumerate(('x', 'y', 'z')):
            values[i] += float(amount) * float(getattr(axis, name)) * float(factor)
    return unreal.Vector(*values)


def in_frame(component, point):
    origin = component.get_world_location()
    delta = [float(getattr(point, a) - getattr(origin, a)) for a in ('x', 'y', 'z')]
    scale = component.get_world_scale()
    result = []
    for axis, factor in zip((component.get_forward_vector(), component.get_right_vector(), component.get_up_vector()),
                            (scale.x, scale.y, scale.z)):
        if abs(float(factor)) < 1e-8:
            raise RuntimeError('Cannot measure a zero-scale component')
        result.append(round(sum(delta[i] * float(getattr(axis, a)) for i, a in enumerate(('x', 'y', 'z'))) / float(factor), 4))
    return result


def distance(left, right):
    return round(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right)) ** .5, 4)


class Preview:
    def __init__(self, args):
        self.args = dict(args)
        self.done = self.owns_play = False
        self.started = time.monotonic()
        self.handle = self.launch = self.world = self.camera = self.controller = None
        self.original_view = self.saved_hud = self.saved_camera = None
        self.previous_test = None
        self.launch_requested = self.cleanup_pending_start = False
        self.directory = ROOT / '.local/native-human-rider-preview' / str(time.time_ns())
        self.directory.mkdir(parents=True, exist_ok=False)
        self.width, self.height = int(args.get('width', 1600)), int(args.get('height', 1000))
        self.timeout = float(args.get('timeout_seconds', 180))
        if not (640 <= self.width <= 3840 and 480 <= self.height <= 2160 and 30 <= self.timeout <= 600):
            raise ValueError('Use 640..3840 by 480..2160, with a 30..600 second timeout')
        self.data = {'status': 'running', 'phase': 'preflight', 'requested_utc': datetime.now(timezone.utc).isoformat(),
                     'engine': unreal.SystemLibrary.get_engine_version(), 'views': [], 'roster': [],
                     'maps_saved': 0, 'assets_modified': 0, 'configuration_modified': False,
                     'scope': 'Actual native human cosmetics in a fresh owned authority PIE lobby',
                     'visual_review_status': 'not_rendered', 'first_person_claim': 'pending real owner-view pixels',
                     'not_covered': ['packaged rendering', 'remote-client replication', 'frame-time benchmark',
                                     'facial expressions beyond the existing runtime animation'],
                     'fixture_policy': 'Existing PIE camera/HUD/view only. No human pose, face graph, garment, team or rider-transform edits.'}

    def save(self):
        self.data['elapsed_seconds'] = round(time.monotonic() - self.started, 3)
        text = json.dumps(self.data, indent=2, allow_nan=False) + '\n'
        for output in (REPORT, self.directory / 'result.json'):
            temporary = output.with_suffix('.tmp')
            temporary.write_text(text, encoding='utf-8')
            temporary.replace(output)

    def begin(self):
        current = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        if current != PROJECT.resolve() or not unreal.SystemLibrary.get_engine_version().startswith('5.8.'):
            raise RuntimeError('Expected the exact BasketbroomDev UE5.8 editor')
        self.levels, self.editor = base.subsystems()
        if self.levels.is_in_play_in_editor():
            raise RuntimeError('An existing PIE session is active; this preview refuses to join or stop it')
        if self.editor.get_editor_world().get_path_name().split('.', 1)[0] not in base.MAPS:
            raise RuntimeError('Select an owned native regulation map first')
        dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()) + list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
        if dirty:
            raise RuntimeError('Save pending work before disposable PIE review: ' + str([path(p) for p in dirty]))
        for key in (*base.TEST_RUNNERS, base.RUNNER_NAME):
            previous = getattr(unreal, key, None)
            if previous is not None and not previous.done:
                raise RuntimeError('Another native session/test is still active: ' + key)
        manifest_path = ROOT / 'SourceArt/Equipment/broom_equipment_manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        self.equipment_fit = manifest['pose_fit_cm']
        self.data['broom_reference'] = {'manifest': str(manifest_path),
            'sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'reference_points_local_cm': self.equipment_fit,
            'note': 'Authored equipment fit targets transformed through the ACTUAL runtime BroomWood component; no fake bones or sockets.'}
        self.previous_test = getattr(unreal, '_basketbroom_native_test', None)
        setattr(unreal, '_basketbroom_native_test', self)
        self.launch = base.SessionOperation('start', {'start_live': False, 'practice': False, 'timeout_seconds': min(self.timeout, 120)})
        setattr(unreal, base.RUNNER_NAME, self.launch)
        self.owns_play = True
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.launch.begin()
        self.launch_requested = True
        self.data['phase'] = 'waiting_for_native_session'
        self.save()

    def cosmetics(self, rider):
        component = named_component(rider, unreal.ChildActorComponent, 'HumanRiderCosmetic')
        # GetChildActor is a native-only inline getter in this engine build;
        # ChildActor itself is reflected and readable through the component.
        return component, prop(component, 'ChildActor')

    def ready(self):
        rider_class = unreal.load_class(None, '/Script/BasketbroomRuntime.BBRiderCharacter')
        self.riders = list(unreal.GameplayStatics.get_all_actors_of_class(self.world, rider_class))
        rows, candidates = [], {}
        for rider in sorted(self.riders, key=lambda r: int(prop(r, 'RosterIndex'))):
            component, child = self.cosmetics(rider)
            enabled = bool(prop(rider, 'bHumanRiderEnabled'))
            actor_class = child.get_class().get_path_name() if child else None
            row = {'rider': path(rider), 'slot': int(prop(rider, 'RosterIndex')),
                   'appearance_identity': int(prop(rider, 'AppearanceIdentity')), 'team': int(prop(rider, 'TeamIndex')),
                   'human_enabled': enabled, 'cosmetic_actor': path(child), 'class': actor_class}
            rows.append(row)
            if enabled and child:
                character = next((n for n in ('BB_AthleteA', 'BB_AthleteB') if '/' + n + '/' in actor_class), None)
                if character is not None:
                    candidates.setdefault((character, row['team']), rider)
        self.data['roster'] = rows
        if len(rows) != 16 or not all(row['human_enabled'] for row in rows):
            return False
        required = [(name, team) for name in ('BB_AthleteA', 'BB_AthleteB') for team in (0, 1)]
        if any(key not in candidates for key in required):
            return False
        self.selected = [(name, team, candidates[(name, team)]) for name, team in required]
        return True

    def pose(self, rider):
        mount, child = self.cosmetics(rider)
        if not child or not bool(prop(rider, 'bHumanRiderEnabled')):
            raise RuntimeError('Runtime human disappeared during capture')
        body = named_component(child, unreal.SkeletalMeshComponent, 'Body')
        face = named_component(child, unreal.SkeletalMeshComponent, 'Face')
        garment = named_component(child, unreal.SkeletalMeshComponent, 'SkeletalMesh')
        wood = named_component(rider, unreal.StaticMeshComponent, 'BroomWood')
        fallback = rider.get_component_by_class(unreal.SkeletalMeshComponent)
        bones = ('pelvis', 'head', 'hand_l', 'hand_r', 'foot_l', 'foot_r')
        bone_values = {name: {'world_cm': xyz(body.get_socket_location(name)),
                             'broom_local_cm': in_frame(wood, body.get_socket_location(name))} for name in bones}
        face_head = xyz(face.get_socket_location('head'))
        grip = frame_point(wood, self.equipment_fit['grip_center'])
        targets = [xyz(frame_point(wood, value)) for value in self.equipment_fit['hand_targets']]
        def component_state(component):
            mesh = component.get_skeletal_mesh_asset()
            leader = prop(component, 'leader_pose_component')
            return {'component': path(component), 'mesh': path(mesh), 'frame': frame(component),
                    'animation_mode': str(component.get_animation_mode()), 'animation_instance': path(component.get_anim_instance()),
                    'animation_class': path(prop(component, 'anim_class')), 'leader': path(leader),
                    'visible': bool(component.is_visible()), 'owner_no_see': bool(prop(component, 'owner_no_see')),
                    'only_owner_see': bool(prop(component, 'only_owner_see')),
                    'materials': [path(component.get_material(i)) for i in range(component.get_num_materials())]}
        return {'rider': path(rider), 'team': int(prop(rider, 'TeamIndex')),
                'appearance_identity': int(prop(rider, 'AppearanceIdentity')), 'cosmetic_class': child.get_class().get_path_name(),
                'cosmetic_owner': path(child.get_owner()), 'cosmetic_hidden': bool(prop(child, 'bHidden')),
                'mount_frame': frame(mount), 'mount_relative_transform': mount.get_relative_transform().export_text(),
                'body': component_state(body), 'face': component_state(face), 'garment': component_state(garment),
                'bones': bone_values, 'face_head_world_cm': face_head,
                'face_body_head_distance_cm': distance(face_head, bone_values['head']['world_cm']),
                'fallback_body_visible': bool(fallback.is_visible()),
                'fallback_pelvis_world_cm': xyz(fallback.get_socket_location('pelvis')),
                'human_fallback_pelvis_distance_cm': distance(xyz(fallback.get_socket_location('pelvis')), bone_values['pelvis']['world_cm']),
                'broom': {'component': path(wood), 'mesh': path(prop(wood, 'static_mesh')), 'frame': frame(wood),
                    'visible': bool(wood.is_visible()), 'owner_no_see': bool(prop(wood, 'owner_no_see')),
                    'grip_world_cm': xyz(grip), 'hand_target_world_cm': targets,
                    'hand_to_grip_center_cm': {name: distance(bone_values[name]['world_cm'], xyz(grip)) for name in ('hand_l', 'hand_r')},
                    'hand_to_nearest_authored_target_cm': {name: min(distance(bone_values[name]['world_cm'], target) for target in targets) for name in ('hand_l', 'hand_r')}}}

    def select_camera(self):
        cameras = [actor for actor in unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.CameraActor)
                   if actor.get_actor_label() == 'BB Hero Camera' and actor.get_path_name().startswith(self.world.get_path_name() + ':')]
        if len(cameras) != 1:
            raise RuntimeError('Expected the existing owned PIE BB Hero Camera')
        self.camera = cameras[0]
        self.camera_component = self.camera.get_component_by_class(unreal.CameraComponent)
        self.saved_camera = {'location': xyz(self.camera.get_actor_location()), 'rotation': rotation(self.camera.get_actor_rotation()),
                             'fov': float(prop(self.camera_component, 'FieldOfView'))}
        self.original_view = self.controller.get_view_target()
        hud = self.controller.get_hud()
        if hud is None:
            raise RuntimeError('The local native viewport HUD is missing')
        self.saved_hud = (hud, bool(prop(hud, 'bShowHUD')))
        self.saved_control = rotation(self.controller.get_control_rotation())
        self.camera_component.set_field_of_view(55)
        self.views = []
        for name, team, rider in self.selected:
            for angle, offset in (('side', (0, -520, 70)), ('three-quarter', (360, -390, 105))):
                self.views.append({'name': name + '-' + ('mint' if team == 0 else 'copper') + '-' + angle,
                                   'rider': rider, 'offset': offset, 'owner_view': False})
        self.views.append({'name': 'owner-first-person', 'rider': self.pawn, 'owner_view': True})
        self.view_index = 0
        self.configure_view()

    def configure_view(self):
        entry = self.views[self.view_index]
        if entry['owner_view']:
            self.controller.set_view_target_with_blend(self.pawn, 0)
            self.saved_hud[0].set_editor_property('bShowHUD', self.saved_hud[1])
        else:
            self.saved_hud[0].set_editor_property('bShowHUD', False)
            self.position_camera(entry)
            self.controller.set_view_target_with_blend(self.camera, 0)
        self.view_started = time.monotonic()
        self.last_game_time = float(unreal.GameplayStatics.get_time_seconds(self.world))
        self.settled_frames = 0
        self.pose_before = self.pose(entry['rider'])
        self.data.update(phase='settling_view', current_view=entry['name'])
        self.save()

    def position_camera(self, entry):
        wood = named_component(entry['rider'], unreal.StaticMeshComponent, 'BroomWood')
        location = frame_point(wood, entry['offset'])
        target = frame_point(wood, (0, 0, 35))
        self.camera.set_actor_location(location, False, True)
        self.camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(location, target), True)

    def request_capture(self):
        entry = self.views[self.view_index]
        filename = self.directory / (entry['name'] + '.png')
        if filename.exists():
            raise RuntimeError('Capture paths must be new')
        state = self.pose(entry['rider'])
        row = {'view': entry['name'], 'path': str(filename), 'owner_view': entry['owner_view'],
               'request_game_seconds': float(unreal.GameplayStatics.get_time_seconds(self.world)),
               'view_target': path(self.controller.get_view_target()), 'before_pose': self.pose_before, 'request_pose': state,
               'head_animation_change_cm': distance(self.pose_before['bones']['head']['world_cm'], state['bones']['head']['world_cm']),
               'visual_review': 'pending', 'settled_game_frames': self.settled_frames}
        if entry['owner_view']:
            manager = unreal.GameplayStatics.get_player_camera_manager(self.world, 0)
            row['camera'] = {'location': xyz(manager.get_camera_location()), 'rotation': rotation(manager.get_camera_rotation())}
        else:
            row['camera'] = frame(self.camera_component)
        command = 'HighResShot %dx%d filename="%s"' % (self.width, self.height, filename.as_posix())
        row['command'] = command
        self.data['views'].append(row)
        unreal.SystemLibrary.execute_console_command(self.world, command, self.controller)
        self.capture_started = time.monotonic()
        self.data['phase'] = 'waiting_for_png'
        self.save()

    def tick(self, delta):
        if self.done:
            return
        try:
            if self.data['phase'] == 'stopping_owned_pie':
                if self.cleanup_pending_start:
                    if self.levels.is_in_play_in_editor():
                        self.cleanup_pending_start = False
                        self.levels.editor_request_end_play()
                        self.cleanup_started = time.monotonic()
                    elif time.monotonic() - self.cleanup_started > 15:
                        self.terminal_status = 'error'
                        self.data['cleanup']['error'] = 'PIE launch was still unobserved after stop; shutdown cannot be certified'
                        self.complete()
                    return
                if not self.levels.is_in_play_in_editor():
                    self.data['cleanup']['pie_shutdown_observed'] = True
                    self.complete()
                elif time.monotonic() - self.cleanup_started > 15:
                    self.terminal_status = 'error'
                    self.data['cleanup']['error'] = 'Owned PIE end request did not complete within fifteen seconds'
                    self.complete()
                return
            if time.monotonic() - self.started > self.timeout:
                raise TimeoutError('Native human preview exceeded its bounded timeout')
            if self.launch is None or not self.launch.done:
                return
            if self.launch.data['status'] != 'ready':
                raise RuntimeError('Native session did not become ready: ' + json.dumps(self.launch.data))
            if self.world is None:
                self.world, self.match, self.pawn, self.controller, balls = base.context()
                self.data['world'] = self.world.get_path_name()
                self.data['launch'] = self.launch.data
                self.readiness_started = time.monotonic()
                self.readiness_saved = self.readiness_started
                self.data['phase'] = 'waiting_for_runtime_humans'
            if not self.levels.is_in_play_in_editor() or self.editor.get_game_world() != self.world:
                raise RuntimeError('Owned PIE ended or was replaced during preview')
            if bool(prop(self.match, 'bLive')):
                raise RuntimeError('Preview expected a quiet native lobby; live play was started externally')
            if self.data['phase'] == 'waiting_for_runtime_humans':
                if self.ready():
                    self.select_camera()
                elif time.monotonic() - self.readiness_started > 30:
                    raise RuntimeError('All sixteen configured humans and both identities/team colors did not become ready')
                elif time.monotonic() - self.readiness_saved >= 2:
                    self.save()
                    self.readiness_saved = time.monotonic()
                return
            entry = self.views[self.view_index]
            if not entry['owner_view']:
                self.position_camera(entry)
            if self.data['phase'] == 'settling_view':
                current_game_time = float(unreal.GameplayStatics.get_time_seconds(self.world))
                if current_game_time > self.last_game_time:
                    self.settled_frames += 1
                    self.last_game_time = current_game_time
                if self.settled_frames >= 8 and time.monotonic() - self.view_started >= 1.5:
                    self.request_capture()
            elif self.data['phase'] == 'waiting_for_png':
                row = self.data['views'][-1]
                dimensions = png_dimensions(Path(row['path']))
                if dimensions is not None:
                    if dimensions != [self.width, self.height]:
                        raise RuntimeError('Native viewport PNG dimensions differ from the request')
                    row.update(dimensions=dimensions, bytes=Path(row['path']).stat().st_size, png_complete=True)
                    self.view_index += 1
                    if self.view_index == len(self.views):
                        self.data['visual_review_status'] = 'captured_pending_visual_review'
                        self.data['first_person_claim'] = 'Actual possessed owner viewport captured; inspect pixels for visibility'
                        self.finish('captured_pending_visual_review')
                    else:
                        self.configure_view()
                elif time.monotonic() - self.capture_started > 20:
                    raise RuntimeError('The requested native viewport PNG was not completed')
        except Exception:
            self.finish('error', traceback.format_exc())

    def finish(self, status, reason=None):
        if self.done or self.data['phase'] == 'stopping_owned_pie':
            return
        self.terminal_status = status
        if reason:
            self.data['error'] = reason
        cleanup = self.data['cleanup'] = {'camera_hud_view_restored': False, 'pie_shutdown_observed': False}
        if self.launch is not None:
            try:
                if not self.launch.done:
                    self.launch.finish('cancelled', 'Owned preview ended')
                else:
                    self.launch.restore_practice_url()
            except Exception:
                self.terminal_status = 'error'
                cleanup['launch_restore_error'] = traceback.format_exc()
        if self.owns_play and self.levels.is_in_play_in_editor():
            if self.world is not None and self.editor.get_game_world() != self.world:
                self.terminal_status = 'error'
                cleanup['error'] = 'Refused to stop a different replacement PIE world'
                self.complete()
                return
            try:
                if self.original_view is not None:
                    self.controller.set_view_target_with_blend(self.original_view, 0)
                if self.saved_hud is not None:
                    self.saved_hud[0].set_editor_property('bShowHUD', self.saved_hud[1])
                if self.camera is not None and self.saved_camera is not None:
                    saved = self.saved_camera
                    self.camera.set_actor_location(unreal.Vector(*saved['location']), False, True)
                    self.camera.set_actor_rotation(unreal.Rotator(*saved['rotation']), True)
                    self.camera_component.set_field_of_view(saved['fov'])
                cleanup['camera_hud_view_restored'] = True
            except Exception:
                self.terminal_status = 'error'
                cleanup['restore_error'] = traceback.format_exc()
            self.levels.editor_request_end_play()
            self.data['phase'] = 'stopping_owned_pie'
            self.cleanup_started = time.monotonic()
            self.save()
            return
        if self.owns_play and self.launch_requested and self.world is None:
            # RequestEndPlayMap only affects an already-created PlayWorld in
            # installed PlayLevel.cpp. Keep observing our pending launch before
            # declaring it stopped, so an early cancellation cannot orphan PIE.
            self.cleanup_pending_start = True
            self.data['phase'] = 'stopping_owned_pie'
            self.cleanup_started = time.monotonic()
            self.save()
            return
        cleanup['pie_shutdown_observed'] = not self.owns_play or not self.levels.is_in_play_in_editor()
        self.complete()

    def complete(self):
        self.done = True
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        if getattr(unreal, '_basketbroom_native_test', None) is self:
            setattr(unreal, '_basketbroom_native_test', self.previous_test)
        self.data.update(status=self.terminal_status, phase='finished')
        self.save()


def main():
    previous = getattr(unreal, KEY, None)
    operation = ARGS.get('operation', 'inspect')
    if operation == 'inspect':
        return previous.data if previous else {'status': 'not_started'}
    if operation == 'stop':
        if previous and not previous.done:
            previous.finish('stopped', 'Explicit preview stop requested')
        return previous.data if previous else {'status': 'not_started'}
    if operation != 'start':
        raise ValueError('Choose start, inspect or stop')
    if previous and not previous.done:
        raise RuntimeError('A native human preview already owns a session')
    preview = Preview(ARGS)
    setattr(unreal, KEY, preview)
    try:
        preview.begin()
    except Exception:
        preview.finish('error', traceback.format_exc())
    return {'status': preview.data['status'], 'report': str(REPORT), 'run_report': str(preview.directory / 'result.json'), 'planned_views': 9}


if __name__ == '__main__':
    RESULT = main()

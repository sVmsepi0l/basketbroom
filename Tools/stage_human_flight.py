"""Fit the authored Basketbroom flight loop to an actual assembled human body."""
from pathlib import Path
import importlib.util
import json
import math

ROOT = Path(__file__).resolve().parents[1]
OWNER = 'Basketbroom.HumanFlight.v1'
spec = importlib.util.spec_from_file_location('bb_flight_math', ROOT/'Tools/stage_skeletal_rider.py')
flight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flight)


def run(name='BB_AthleteA', build=False):
    import unreal as ue
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.get_project_file_path())).resolve()
    if project != (ROOT/'.local/CharacterLab/BasketbroomCharacterLab.uproject').resolve():
        raise RuntimeError('Author human flight only in the isolated lab')
    if name not in ('BB_AthleteA', 'BB_AthleteB'):
        raise ValueError('Unknown owned athlete')
    if ue.get_editor_subsystem(ue.LevelEditorSubsystem).is_in_play_in_editor():
        raise RuntimeError('Stop lab Play before authoring')
    lib = ue.EditorAssetLibrary
    base = '/Game/BasketbroomHumans/Assembled/'+name
    blueprint = lib.load_asset(base+'/BP_'+name)
    if blueprint is None or lib.get_metadata_tag(blueprint, 'BB.Generator') != 'Basketbroom.HumanPlayerAssembly.v1':
        raise RuntimeError('Expected the owned assembled actor')
    mesh = lib.load_asset(base+'/Body/SKM_'+name+'_BodyMesh')
    if not isinstance(mesh, ue.SkeletalMesh):
        raise RuntimeError('Expected the actual assembled body mesh')
    skeleton = mesh.get_editor_property('skeleton')
    tracks, checks, max_error = {}, {}, 0.0
    for frame in range(flight.FRAMES+1) if build else (0, 15, 30, 60):
        pose, bones, errors = flight._seated_pose(ue, skeleton, frame)
        max_error = max(max_error, *errors.values())
        sample = flight._check_pose(ue, pose)
        if frame in (0, 15, 30, 60): checks[str(frame)] = sample
        if build:
            for bone in bones:
                transform = flight._transform(ue, pose, bone, local=True)
                key = (flight._v(transform.translation), flight._q(transform.rotation), flight._v(transform.scale3d))
                if not all(math.isfinite(v) for group in key for v in group):
                    raise RuntimeError('Invalid transform: '+bone)
                tracks.setdefault(bone, []).append(key)
    report = {'character': name, 'body_mesh': mesh.get_path_name(), 'skeleton': skeleton.get_path_name(),
              'pose_samples': checks, 'max_reach_error_cm': max_error,
              'status': 'pose_geometry_verified_pending_render', 'game_integrated': False}
    if not build: return report
    dirty = list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    if dirty: raise RuntimeError('Preserve unsaved lab work before authoring: '+str([p.get_path_name() for p in dirty]))
    path = '/Game/BasketbroomHumans/Flight/A_BB_SeatedFlight_'+name
    if lib.does_asset_exist(path): raise RuntimeError('Preserve the existing authored loop')
    for bone, keys in tracks.items():
        if max(abs(a-b) for left,right in zip(keys[0],keys[-1]) for a,b in zip(left,right)) > 1e-4:
            raise RuntimeError('Discontinuous loop: '+bone)
    if any(keys != tracks['root'][0] for keys in tracks['root']):
        raise RuntimeError('Unexpected root motion')
    factory = ue.AnimSequenceFactory()
    factory.set_editor_property('target_skeleton', skeleton)
    factory.set_editor_property('preview_skeletal_mesh', mesh)
    directory, asset_name = path.rsplit('/',1)
    animation = ue.AssetToolsHelpers.get_asset_tools().create_asset(asset_name,directory,ue.AnimSequence,factory)
    if not isinstance(animation,ue.AnimSequence): raise RuntimeError('Could not create fitted animation')
    lib.set_metadata_tag(animation,'BB.Generator',OWNER)
    lib.set_metadata_tag(animation,'BB.SourceMesh',mesh.get_path_name())
    controller = animation.get_editor_property('controller')
    controller.open_bracket('Fit human seated flight',False)
    try:
        controller.set_frame_rate(ue.FrameRate(flight.FPS,1),False)
        controller.set_number_of_frames(ue.FrameNumber(flight.FRAMES),False)
        for bone,keys in tracks.items():
            if not controller.add_bone_curve(bone,False): raise RuntimeError('Missing track '+bone)
            if not controller.set_bone_track_keys(bone,[ue.Vector(*k[0]) for k in keys],
                    [ue.Quat(*k[1]) for k in keys],[ue.Vector(*k[2]) for k in keys],False):
                raise RuntimeError('Could not set track '+bone)
    finally: controller.close_bracket(False)
    animation.set_editor_property('enable_root_motion',False)
    options = ue.AnimPoseEvaluationOptions()
    options.set_editor_property('should_retarget',False)
    options.set_editor_property('optional_skeletal_mesh',mesh)
    evaluated = flight._Pose(ue.AnimPoseExtensions.get_anim_pose_at_time(animation,.5,options))
    report['evaluated_pose'] = flight._check_pose(ue,evaluated)
    if not lib.save_loaded_asset(animation,only_if_is_dirty=False): raise RuntimeError('Could not save fitted loop')
    report.update(animation=animation.get_path_name(),bone_tracks=len(tracks),frames=flight.FRAMES,
                  fps=flight.FPS,status='authored_pending_render')
    output = ROOT/'.local/CharacterLab'/('flight-'+name+'.json')
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__ == '__main__':
    args = globals().get('BRIDGE_ARGS',{})
    RESULT = run(args.get('character','BB_AthleteA'),args.get('operation','inspect') == 'build')

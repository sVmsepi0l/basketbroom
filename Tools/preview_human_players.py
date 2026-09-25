"""Render an assembled human and fitted flight loop using transient lab actors."""
from pathlib import Path
import importlib.util
import json
import time
import traceback
import unreal as ue

ROOT = Path(__file__).resolve().parents[1]
KEY = '_bb_human_render_preview'
spec = importlib.util.spec_from_file_location('bb_pose_preview',ROOT/'Tools/preview_skeletal_rider.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.REPORT = ROOT/'.local/CharacterLab/preview.json'


class Preview(base.Preview):
    def begin(self,name,team):
        project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.get_project_file_path())).resolve()
        if project != (ROOT/'.local/CharacterLab/BasketbroomCharacterLab.uproject').resolve():
            raise RuntimeError('Render only in the isolated character lab')
        if name not in ('BB_AthleteA','BB_AthleteB') or team not in ('Teal','Copper'):
            raise ValueError('Unknown character or team')
        if ue.get_editor_subsystem(ue.LevelEditorSubsystem).is_in_play_in_editor():
            raise RuntimeError('Stop lab Play first')
        self.editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
        self.actor_system = ue.get_editor_subsystem(ue.EditorActorSubsystem)
        self.world = self.editor.get_editor_world()
        self.camera = self.editor.get_level_viewport_camera_info()
        self.selection = list(self.actor_system.get_selected_level_actors())
        self.directory = ROOT/'.local/CharacterLab/renders'/str(time.time_ns())
        self.directory.mkdir(parents=True)
        self.data.update(character=name,team=team,report=str(base.REPORT),fixture='Assembled human with fitted flight loop; transient CharacterLab render')
        library = ue.EditorAssetLibrary
        blueprint = library.load_asset('/Game/BasketbroomHumans/Assembled/'+name+'/BP_'+name)
        if library.get_metadata_tag(blueprint,'BB.Generator') != 'Basketbroom.HumanPlayerAssembly.v1':
            raise RuntimeError('Expected owned assembled character')
        actor = self.spawn(blueprint.generated_class(),(0,0,1400))
        components = actor.get_components_by_class(ue.SkeletalMeshComponent)
        body = next(c for c in components if c.get_name() == 'Body')
        animation = library.load_asset('/Game/BasketbroomHumans/Flight/A_BB_SeatedFlight_'+name)
        if animation.get_editor_property('skeleton') != body.get_skeletal_mesh_asset().get_editor_property('skeleton'):
            raise RuntimeError('Flight skeleton mismatch')
        for component in components:
            component.set_collision_enabled(ue.CollisionEnabled.NO_COLLISION)
            component.set_update_animation_in_editor(True)
        body.override_animation_data(animation,True,False,.5,0)
        # Reinitialize the transient face after the body has evaluated: editor
        # worlds do not necessarily update its Copy Pose node between captures.
        face = next(c for c in components if c.get_name() == 'Face')
        face_class = face.get_editor_property('anim_class')
        face.set_anim_instance_class(None)
        face.set_anim_instance_class(face_class)
        uniform = json.loads((ROOT/'.local/CharacterLab'/('uniform-'+name+'.json')).read_text(encoding='utf-8'))
        garment = next(c for c in components if c.get_name() == uniform['garments'][0]['component'])
        for row in uniform['garments']:
            index = row['material_slot_index']
            if str(garment.get_material_slot_names()[index]) != row['material_slot']:
                raise RuntimeError('Garment contract changed')
            garment.set_material(index,library.load_asset(row['mint_material' if team == 'Teal' else 'copper_material']))
        self.data['pelvis_world_z'] = body.get_socket_location('pelvis').z
        self.data['foot_world_z'] = body.get_socket_location('foot_l').z
        self.data['hand_world_z'] = body.get_socket_location('hand_l').z
        # The assembled MetaHuman post-process adjusts proportions. Check that
        # the seated pose evaluated, then inspect its actual corrected shape.
        if not 1395 < self.data['pelvis_world_z'] < 1440 or self.data['foot_world_z'] > self.data['pelvis_world_z']-25:
            raise RuntimeError('Flight pose did not evaluate')
        self.human_components = components
        for location,strength in (((100,-180,1550),4),((-80,160,1500),2)):
            light = self.spawn(ue.PointLight,location)
            component = light.get_component_by_class(ue.PointLightComponent)
            component.set_intensity(strength)
            component.set_attenuation_radius(700)
            component.set_cast_shadows(False)
        self.capture_actor = self.spawn(ue.SceneCapture2D,(200,-200,1450))
        self.capture = self.capture_actor.get_component_by_class(ue.SceneCaptureComponent2D)
        self.target = ue.RenderingLibrary.create_render_target2d(self.world,1280,960,ue.TextureRenderTargetFormat.RTF_RGBA8)
        self.capture.set_editor_property('texture_target',self.target)
        self.capture.set_editor_property('capture_source',ue.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        self.capture.set_editor_property('capture_every_frame',False)
        self.capture.set_editor_property('capture_on_movement',False)
        self.capture.set_editor_property('always_persist_rendering_state',True)
        self.capture.set_editor_property('fov_angle',90)
        self.actor_system.clear_actor_selection_set()
        self.views = [('side',(0,-210,1430)),('front',(210,0,1430)),('three-quarter',(170,-160,1490))]
        self.set_view()
        self.handle = ue.register_slate_post_tick_callback(self.tick)
        self.save()

    def tick(self,delta):
        try:
            if hasattr(self,'human_components'):
                self.data['component_pose'] = {c.get_name(): {
                    'head':str(c.get_socket_location('head')),
                    'pelvis':str(c.get_socket_location('pelvis')),
                    'visible':c.is_visible(), 'active':c.is_active(),
                    'animation_mode':str(c.get_animation_mode()),
                    'animation_instance':str(c.get_anim_instance())} for c in self.human_components}
            super().tick(delta)
        except Exception: self.finish('error',traceback.format_exc())


def run(args):
    prior = getattr(ue,KEY,None)
    if args.get('operation') == 'stop':
        if prior and prior.data['status']=='running': prior.finish('stopped')
        return prior.data if prior else {'status':'not_started'}
    if args.get('operation','inspect') == 'inspect':
        return prior.data if prior else {'status':'not_started'}
    if prior and prior.data['status']=='running': raise RuntimeError('A human render is already running')
    preview = Preview()
    setattr(ue,KEY,preview)
    try: preview.begin(args.get('character','BB_AthleteA'),args.get('team','Teal'))
    except Exception: preview.finish('error',traceback.format_exc())
    return preview.data


if __name__ == '__main__':
    RESULT = run(globals().get('BRIDGE_ARGS',{}))

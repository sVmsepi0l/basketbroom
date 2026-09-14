"""Owned native PIE equipment configuration checks and real viewport captures.

No editor actor, map, asset or input setting is changed. The existing hero
camera copy in the disposable PIE world is restored after its temporary use.
Generated images are render evidence pending human/agent visual review; native
assertions passing does not certify their aesthetic quality or final art.
"""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'.local/native-equipment-visual-results.json'
ARGS={"max_wall_seconds":180,**globals().get('BRIDGE_ARGS',{})}
CASES=(
    'sixteen_native_skeletal_riders_pass_existing_art_probe',
    'all_eight_authored_meshes_have_two_correct_noncolliding_view_layers',
    'both_team_accent_materials_match_native_team_identity',
    'actual_expelliarmus_hides_all_six_wand_layers',
    'live_recovery_restores_all_six_wand_layers',
    'owner_first_person_1600x900_image_written',
    'owner_hud_image_written_at_actual_viewport_size',
    'teal_third_person_1600x900_image_written',
    'copper_third_person_1600x900_image_written',
    'owned_pie_camera_transform_fov_and_original_view_restored',
)
spec=importlib.util.spec_from_file_location('_bb_equipment_native_base',ROOT/'Tools/test_native_playable.py')
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.TEST_NAMES,base.REPORT,base.ARGS=CASES,REPORT,ARGS
unreal,prop,xyz,vector=base.unreal,base.prop,base.xyz,base.vector
spec=importlib.util.spec_from_file_location('_bb_equipment_receipts',ROOT/'Tools/native_test_receipts.py')
receipts=importlib.util.module_from_spec(spec)
spec.loader.exec_module(receipts)
MOUNT='/Basketbroom/Art/Equipment/'


def asset_path(obj):
    return obj.get_path_name() if obj else None


def png_dimensions(path):
    try:
        data=path.read_bytes()
        if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data)<32:
            return None
        dims=struct.unpack('>II',data[16:24])
        offset=8
        while offset+12<=len(data):
            length=struct.unpack('>I',data[offset:offset+4])[0]
            if offset+length+12>len(data):
                return None
            if data[offset+4:offset+8]==b'IEND':
                return dims if length==0 else None
            offset+=length+12
    except OSError:
        pass
    return None


class EquipmentVisualTests(base.NativePlayableTests):
    def __init__(self):
        self.camera=None
        self.saved_camera_state=None
        self.original_view=None
        self.original_controller_tick=None
        self.captures=[]
        self.directory=ROOT/'.local/native-equipment-visual'/str(time.time_ns())
        self.probe_report=None
        super().__init__()

    def write_report(self,status,reason=None):
        data=receipts.single_world_payload(self,CASES,status,reason,
            unreal.SystemLibrary.get_engine_version() if unreal else None)
        data.update(scope='native equipment configuration, real spell visibility and owned game-viewport render integrity',
            captures=self.captures,probe_report=self.probe_report,
            visual_review_pending=bool(self.captures),
            visual_review_status='rendered_pending_visual_review' if self.captures else 'not_rendered',
            not_covered=['image aesthetics until separately reviewed','physical controller hardware','network transport',
                         'final character art or precise finger contact','frame rate/performance or packaged runtime'],
            fixture_policy='Only disposable PIE transforms/component ticks and the existing PIE hero CameraActor copy. '
                'Disarm uses ordinary native input. No gameplay status, effect, custody or score is written. '
                'Screenshots route through the owning PlayerController/game viewport; no editor preferences changed.')
        receipts.write_json_atomic(REPORT,data)

    def record(self,name,passed,**detail):
        super().record(name,passed,**detail)
        self.require(passed,name)

    def equipment_rows(self):
        rows=[]
        for rider in self.riders:
            team=int(prop(rider,'TeamIndex'))
            skeletal=self.component(rider,unreal.SkeletalMeshComponent)
            camera=self.component(rider,unreal.CameraComponent)
            components={p.get_name():p for p in rider.get_components_by_class(unreal.StaticMeshComponent)}
            layers=[]
            for cockpit in (False,True):
                for part,material in (('Wood','Wood'),('Leather','Leather'),('Bristles','Bristles'),('Copper','Copper'),('Accent','Team')):
                    layers.append((('CockpitBroom' if cockpit else 'Broom')+part,'SM_BB_Broom'+part,material,cockpit,
                                   (55,30,-48) if cockpit else (0,0,0)))
                for part,mesh,material in (('Wood','Wood','Wood'),('Grip','Leather','Leather'),('Collar','Copper','Copper')):
                    layers.append((('CockpitWand' if cockpit else 'RiderWand')+part,'SM_BB_Wand'+mesh,material,cockpit,
                                   (45,38,-29) if cockpit else (43,10,14)))
            evidence=[]
            for name,mesh,material,cockpit,mount in layers:
                component=components.get(name)
                if component is None:
                    evidence.append({'component':name,'valid':False,'reason':'missing native component'})
                    continue
                expected_mesh=MOUNT+mesh+'.'+mesh
                expected_material=('/Basketbroom/Art/Materials/M_BB_Rider'+('Teal' if team==0 else 'Copper')
                    +'.M_BB_Rider'+('Teal' if team==0 else 'Copper')) if material=='Team' else MOUNT+'M_BB_Equip'+material+'.M_BB_Equip'+material
                checks={
                    'mesh':asset_path(prop(component,'StaticMesh'))==expected_mesh,
                    'material':asset_path(component.get_material(0))==expected_material,
                    'no_collision':str(component.get_collision_profile_name())=='NoCollision' and not component.is_collision_enabled(),
                    'owner_filter':bool(prop(component,'bOnlyOwnerSee'))==cockpit and bool(prop(component,'bOwnerNoSee'))!=cockpit,
                    'parent':component.get_attach_parent()==(camera if cockpit else skeletal),
                    'authored_scale':max(abs(v-1) for v in xyz(prop(component, "RelativeScale3D")))<.01,
                    'mount':max(abs(a-b) for a,b in zip(xyz(prop(component, "RelativeLocation")),mount))<.01,
                    'visible':component.is_visible(),
                }
                evidence.append({'component':name,'mesh':asset_path(prop(component,'StaticMesh')),
                    'material':asset_path(component.get_material(0)),'checks':checks,'valid':all(checks.values())})
            rows.append({'rider':rider.get_path_name(),'team':team,'slot':int(prop(rider,'RosterIndex')),
                         'layers':evidence,'valid':len(evidence)==16 and all(item['valid'] for item in evidence)})
        return rows

    def wand_parts(self,rider):
        return [p for p in rider.get_components_by_class(unreal.StaticMeshComponent)
            if p.get_name() in ('RiderWandWood','RiderWandGrip','RiderWandCollar',
                                'CockpitWandWood','CockpitWandGrip','CockpitWandCollar')]

    def capture(self,label,case,high_resolution=True):
        self.directory.mkdir(parents=True,exist_ok=True)
        path=self.directory/(label+'.png')
        self.require(not path.exists(),'Each image must be a new capture, not stale evidence')
        command=('HighResShot 1600x900 filename='+path.as_posix()) if high_resolution else (
                 'Shot showui filename='+path.as_posix()+' -nosuffix')
        view=self.controller.get_view_target()
        self.require(view is not None and view.get_path_name().startswith(self.world.get_path_name()+':'),'Capture view must belong to the owned PIE world')
        hud=self.controller.get_hud()
        self.require(hud is not None, 'Owned player HUD is required for explicit capture visibility')
        self.saved_hud_visibility=(hud,bool(prop(hud,'bShowHUD')))
        hud.set_editor_property('bShowHUD',not high_resolution)
        yield self.wait(.12)
        unreal.SystemLibrary.execute_console_command(self.world,command,self.controller)
        yield self.wait_until(lambda:png_dimensions(path) is not None,timeout=15)
        dims=png_dimensions(path)
        passed=dims==(1600,900) if high_resolution else dims is not None and dims[0]>=640 and dims[1]>=360
        entry={'label':label,'file':str(path),'dimensions':list(dims) if dims else None,
               'view_target':view.get_path_name(),'world':self.world.get_path_name(),'command':command,
               'bytes':path.stat().st_size if path.exists() else None,'visual_review':'pending','hud_visible':bool(prop(hud,'bShowHUD'))}
        self.captures.append(entry)
        self.record(case,passed,**entry)
        hud.set_editor_property('bShowHUD',self.saved_hud_visibility[1])
        self.saved_hud_visibility=None
        yield self.wait(.3)

    def camera_snapshot(self,actor):
        rotation=actor.get_actor_rotation()
        return {'location':xyz(actor.get_actor_location()),
                'rotation':[float(rotation.pitch),float(rotation.yaw),float(rotation.roll)],
                'scale':xyz(actor.get_actor_scale3d()),
                'fov':float(prop(self.component(actor,unreal.CameraComponent),'FieldOfView'))}

    def select_camera(self):
        actors=list(unreal.GameplayStatics.get_all_actors_of_class(self.world,unreal.CameraActor))
        matches=[actor for actor in actors if actor.get_actor_label()=='BB Hero Camera'
                 and actor.get_path_name().startswith(self.world.get_path_name()+':')]
        self.require(len(matches)==1,'Exactly one existing BB Hero Camera copy must belong to the owned PIE world')
        actor=matches[0]
        state=self.camera_snapshot(actor)
        self.camera=actor
        self.saved_camera_state=state
        self.provenance['reused_pie_camera']={'actor':actor.get_path_name(),'original_state':state,
            'scope':'PIE copy only; editor map actor is neither accessed nor saved'}
        self.component(actor,unreal.CameraComponent).set_field_of_view(55)
        return actor

    def restore_view(self):
        if getattr(self,'saved_hud_visibility',None):
            hud,visible=self.saved_hud_visibility
            hud.set_editor_property('bShowHUD',visible)
            self.saved_hud_visibility=None
        if self.controller and self.original_view:
            self.controller.set_view_target_with_blend(self.original_view,0.0)
            if self.original_controller_tick is not None:
                self.controller.set_actor_tick_enabled(self.original_controller_tick)
        if self.camera and self.saved_camera_state:
            state=self.saved_camera_state
            self.camera.set_actor_location(vector(state['location']),False,True)
            self.camera.set_actor_rotation(unreal.Rotator(pitch=state['rotation'][0],yaw=state['rotation'][1],roll=state['rotation'][2]),True)
            self.camera.set_actor_scale3d(vector(state['scale']))
            self.component(self.camera,unreal.CameraComponent).set_field_of_view(state['fov'])
            self.camera=None
            self.saved_camera_state=None

    def scenarios(self):
        self.original_view=self.controller.get_view_target()
        self.original_controller_tick=bool(self.controller.is_actor_tick_enabled())
        self.controller.set_actor_tick_enabled(False)
        spec=importlib.util.spec_from_file_location('_bb_equipment_rider_probe',ROOT/'Tools/probe_native_rider_art.py')
        probe=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        self.probe_report=probe.inspect()
        self.record(CASES[0],self.probe_report['status']=='passed' and self.probe_report['rider_count']==16,
            rider_count=self.probe_report.get('rider_count'),riders_passed=self.probe_report.get('riders_passed'))
        rows=self.equipment_rows()
        self.record(CASES[1],len(rows)==16 and all(row['valid'] for row in rows),riders=rows)
        teams={str(team):sum(row['team']==team for row in rows) for team in (0,1)}
        self.record(CASES[2],teams=={'0':8,'1':8} and all(item['checks']['material'] for row in rows
            for item in row['layers'] if 'Accent' in item['component']),team_counts=teams)
        self.request(4)
        yield self.wait_until(lambda:bool(prop(self.match,'bLive')),timeout=2)
        self.require(prop(self.match,'bLive'),'Host kickoff must allow real Expelliarmus testing')
        self.isolate()
        movement=self.component(self.pawn,unreal.CharacterMovementComponent)
        movement.stop_movement_immediately()
        movement.set_component_tick_enabled(False)
        self.pawn.set_actor_location(vector((-1200,0,1800)),False,True)
        candidates=[r for r in self.riders if int(prop(r,'TeamIndex'))!=int(prop(self.pawn,'TeamIndex'))
                    and int(prop(r,'Position'))==3]
        self.require(len(candidates)==1,'Exactly one opposing Ranger is required')
        target=candidates[0]
        target.set_actor_tick_enabled(True)
        target.set_actor_location(vector((-400,0,1872)),False,True)
        self.controller.set_control_rotation(unreal.Rotator(pitch=0,yaw=0,roll=0))
        yield self.wait_until(lambda:self.pawn.get_aim_direction().x>.999,timeout=1)
        self.require(self.pawn.get_aim_direction().x>.999,'Native wand aim must settle before real cast')
        self.request(6,17)
        parts=self.wand_parts(target)
        yield self.wait_until(lambda:float(prop(target,'DisarmRemaining'))>0 and all(not p.is_visible() for p in parts),timeout=1)
        self.record(CASES[3],len(parts)==6 and float(prop(target,'DisarmRemaining'))>0 and all(not p.is_visible() for p in parts),
            target=target.get_path_name(),disarm_remaining=float(prop(target,'DisarmRemaining')),
            visibility={p.get_name():p.is_visible() for p in parts})
        yield self.wait_until(lambda:float(prop(target,'DisarmRemaining'))==0 and all(p.is_visible() for p in parts),timeout=4)
        self.record(CASES[4],len(parts)==6 and float(prop(target,'DisarmRemaining'))==0 and all(p.is_visible() for p in parts),
            visibility={p.get_name():p.is_visible() for p in parts})
        self.request(5)
        yield self.wait_until(lambda:not prop(self.match,'bLive'),timeout=1)
        self.require(not prop(self.match,'bLive'),'Stop owned gameplay before composed equipment views')
        self.isolate()
        for index,ball in self.balls.items():
            ball.set_actor_location(vector((0,20000+index*300,1800)),False,True)
        self.provenance['art_composition']='Stopped owned PIE; HUD hidden only for art frames; balls parked outside camera view.'
        self.pawn.set_actor_location(vector((-1800,-1200,1650)),False,True)
        self.controller.set_control_rotation(unreal.Rotator(pitch=-8,yaw=22,roll=0))
        self.controller.set_view_target_with_blend(self.pawn,0.0)
        yield self.wait(.8)
        yield from self.capture('owner-first-person',CASES[5])
        yield from self.capture('owner-first-person-hud',CASES[6],False)
        self.select_camera()
        self.controller.set_view_target_with_blend(self.camera,0.0)
        for team,label,case in ((0,'teal-third-person',CASES[7]),(1,'copper-third-person',CASES[8])):
            subject=next(r for r in self.riders if r!=self.pawn and int(prop(r,'TeamIndex'))==team and int(prop(r,'Position'))==1)
            location=vector((0,0,1650))
            subject.set_actor_location(location,False,True)
            subject.set_actor_rotation(unreal.Rotator(pitch=0,yaw=0,roll=0),True)
            self.camera.set_actor_location(vector((250,-400,1810)),False,True)
            self.camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(
                vector((250,-400,1810)),vector((-45,0,1665))),True)
            self.provenance[label]={'subject':subject.get_path_name(),'team':team,'camera':self.camera.get_path_name()}
            yield self.wait(.8)
            yield from self.capture(label,case)
            subject.set_actor_location(vector((0,14000+int(prop(subject,'RosterIndex'))*300,1800)),False,True)
        camera=self.camera
        camera_path=camera.get_path_name()
        before=self.saved_camera_state
        self.restore_view()
        yield self.wait(.2)
        after=self.camera_snapshot(camera)
        restored=(max(abs(a-b) for field in ('location','rotation','scale') for a,b in zip(before[field],after[field]))<.01
                  and abs(before['fov']-after['fov'])<.01)
        self.record(CASES[9],self.controller.get_view_target()==self.original_view and restored
            and camera_path in [a.get_path_name() for a in unreal.GameplayStatics.get_all_actors_of_class(self.world,unreal.CameraActor)],
            restored_view=self.controller.get_view_target().get_path_name(),restored_camera=camera_path,
            original_state=before,restored_state=after)

    def finish(self,status,reason=None):
        if unreal and self.owns_play:
            try:
                self.restore_view()
                self.provenance['cleanup']='Original view, controller tick, and PIE camera transform/FOV restored; PIE EndPlay requested'
            except Exception:
                status,reason='error',(reason or '')+'\nView cleanup: '+traceback.format_exc()
        super().finish(status,reason)


def main():
    if unreal is None and '--list' in sys.argv:
        return {'status':'not_run','planned_cases':list(CASES),'count':len(CASES),'visual_review':'not_run'}
    runner=EquipmentVisualTests()
    try:
        started=runner.begin()
    except Exception:
        runner.finish('error',traceback.format_exc())
        started=False
    if unreal and started:
        unreal._basketbroom_native_test=runner
    return {'status':'started' if started else runner.final_status,'report':str(REPORT),'planned_cases':len(CASES)}


if __name__=='__main__':
    RESULT=main()
    if unreal is None:
        print(json.dumps(RESULT,indent=2))

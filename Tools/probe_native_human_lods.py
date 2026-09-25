"""Observe existing main-project PIE human LODs/bone poses without changing them.

Run after the camera and ordinary Shot have settled. Does not start/stop PIE,
change cameras/LODs/poses/materials, spawn actors, or save assets. RequiredBones
is not a reflected UE5.8 property, so the report explicitly leaves it unknown;
bone positions and source reduction settings provide independent evidence.
"""
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import json
import math

ROOT=Path(__file__).resolve().parents[1]


def path(value):
    return value.get_path_name() if value is not None else None


def local_position(component,world):
    origin=component.get_world_location()
    delta=[float(getattr(world,a)-getattr(origin,a)) for a in ('x','y','z')]
    scale=component.get_world_scale()
    result=[]
    for direction,factor in zip((component.get_forward_vector(),component.get_right_vector(),component.get_up_vector()),
                                (scale.x,scale.y,scale.z)):
        if abs(float(factor))<1e-8: raise RuntimeError('Cannot inspect zero-scale component')
        result.append(round(sum(delta[i]*float(getattr(direction,a)) for i,a in enumerate(('x','y','z')))/float(factor),5))
    return result


def lod_settings(mesh,prop):
    result={'mesh':path(mesh)}
    try:
        settings=prop(mesh,'LODSettings')
        result['settings']=path(settings)
        if settings is None: return result
        result['groups']=[{'index':i,'filter_action':int(group.bone_filter_action_option.value),
            'bone_list':[{'name':str(item.bone_name),'exclude_self':bool(item.exclude_self)} for item in group.bone_list],
            'prioritized_bones':[str(name) for name in group.bones_to_prioritize]}
            for i,group in enumerate(prop(settings,'LODGroups'))]
    except Exception as exc:
        result['unavailable']=str(exc)
    return result


def run():
    import unreal as ue
    if Path(ue.Paths.convert_relative_path_to_full(ue.Paths.get_project_file_path())).resolve()!=ROOT/'DevelopmentHarness/BasketbroomDev.uproject':
        raise RuntimeError('Use only the main Basketbroom project')
    spec=importlib.util.spec_from_file_location('_bb_lod_probe_context',ROOT/'Tools/native_play_session.py')
    base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    prop=base.prop
    world,_,_,_,_=base.context()
    saving=ue.EditorLoadingAndSavingUtils
    dirty=lambda:sorted(path(p) for p in list(saving.get_dirty_map_packages())+list(saving.get_dirty_content_packages()))
    before=dirty()
    camera=ue.GameplayStatics.get_player_camera_manager(world,0)
    camera_location=camera.get_camera_location()
    rider_class=ue.load_class(None,'/Script/BasketbroomRuntime.BBRiderCharacter')
    riders=ue.GameplayStatics.get_all_actors_of_class(world,rider_class)
    if len(riders)!=16: raise RuntimeError('Expected the sixteen-rider native fixture')
    bone_names={};settings={};rows=[]
    for rider in riders:
        children=[c for c in rider.get_components_by_class(ue.ChildActorComponent) if c.get_name()=='HumanRiderCosmetic']
        if len(children)!=1 or children[0].get_child_actor() is None: raise RuntimeError('Missing human cosmetic child')
        child=children[0].get_child_actor()
        meshes={c.get_name():c for c in child.get_components_by_class(ue.SkeletalMeshComponent)}
        if any(name not in meshes for name in ('Body','Face','SkeletalMesh')): raise RuntimeError('Incomplete human components')
        syncs=[c for c in child.get_components_by_class(ue.LODSyncComponent)]
        row={'rider':path(rider),'child':path(child),'appearance':int(prop(rider,'AppearanceIdentity')),
            'distance_cm':math.sqrt(sum((getattr(rider.get_actor_location(),a)-getattr(camera_location,a))**2 for a in ('x','y','z'))),
            'components':{},'lod_sync_debug':[c.get_lod_sync_debug_text() for c in syncs]}
        for name,component in meshes.items():
            mesh=component.get_skeletal_mesh_asset();mesh_path=path(mesh)
            if mesh_path not in settings: settings[mesh_path]=lod_settings(mesh,prop)
            if mesh_path not in bone_names:
                bone_names[mesh_path]=[str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
            row['components'][name]={'mesh':mesh_path,'predicted_lod':int(component.get_predicted_lod_level()),
                'forced_lod_one_based':int(component.get_forced_lod()),'lod_count':int(component.get_num_lods()),
                'leader':path(prop(component,'LeaderPoseComponent')),
                'ignore_leader_lod':bool(prop(component,'bIgnoreLeaderPoseComponentLOD')),
                'sync_attach_parent_lod':bool(prop(component,'bSyncAttachParentLOD'))}
        body,garment=meshes['Body'],meshes['SkeletalMesh']
        body_names=bone_names[path(body.get_skeletal_mesh_asset())]
        garment_names={name.casefold():name for name in bone_names[path(garment.get_skeletal_mesh_asset())]}
        positions={};errors={}
        for name in body_names:
            body_world=body.get_socket_location(name)
            positions[name]=local_position(body,body_world)
            if name.casefold() in garment_names:
                garment_world=garment.get_socket_location(garment_names[name.casefold()])
                errors[name]=round(math.sqrt(sum((getattr(body_world,a)-getattr(garment_world,a))**2 for a in ('x','y','z'))),5)
        row['body_bone_component_translation_cm']=positions
        row['zero_translation_bone_candidates']=[name for name,p in positions.items() if name.casefold()!='root' and sum(v*v for v in p)<.0001]
        row['garment_body_pose_error_cm']={'max':max(errors.values(),default=None),
            'over_1mm':{name:value for name,value in errors.items() if value>.1},'common_bones':len(errors)}
        row['face_body_head_error_cm']=math.sqrt(sum((getattr(meshes['Face'].get_socket_location('head'),a)-
            getattr(body.get_socket_location('head'),a))**2 for a in ('x','y','z')))
        rows.append(row)
    after=dirty()
    report={'status':'observed','world':path(world),'game_seconds':float(ue.GameplayStatics.get_time_seconds(world)),
        'console':{name:ue.SystemLibrary.get_console_variable_int_value(name) for name in
            ('r.ForceLOD','r.SkeletalMeshForceLOD','r.SkeletalMeshLODBias','a.UseSafeMeshPoseIndices')},
        'riders':sorted(rows,key=lambda r:r['distance_cm']),'mesh_lod_settings':settings,
        'required_bones':{'available':False,'reason':'USkeletalMeshComponent::RequiredBones and valid pose bitsets are not Python-reflected; socket positions do not prove a GPU vertex skinning result.'},
        'dirty_before':before,'dirty_after':after,'assets_saved':False,'world_modified':False}
    if before!=after: raise RuntimeError('Read-only LOD probe changed dirty package state')
    directory=ROOT/'.local/native-human-lods';directory.mkdir(parents=True,exist_ok=True)
    output=directory/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.json')
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return {'status':'observed','report':str(output),'riders':len(rows),
        'lod_pairs':sorted({(r['components']['Body']['predicted_lod'],r['components']['SkeletalMesh']['predicted_lod']) for r in rows}),
        'zero_bone_candidates_by_lod':{str(lod):sorted({len(r['zero_translation_bone_candidates']) for r in rows if r['components']['Body']['predicted_lod']==lod})
                                       for lod in {r['components']['Body']['predicted_lod'] for r in rows}}}


if __name__=='__main__':
    RESULT=run()

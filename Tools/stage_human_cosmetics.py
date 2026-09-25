"""Create a NEW owned human cosmetic Blueprint with staged flightwear.

CharacterLab only. inspect validates inputs/templates; build duplicates the
assembly, changes the duplicate's clothing template, compiles and validates one
transient instance before saving. inventory only reads an existing owned output.
No original Blueprint, body, face, hair, skeleton, or main-game asset is edited.
"""
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import json
import traceback
import uuid

_spec=importlib.util.spec_from_file_location('bb_human_inventory',Path(__file__).with_name('probe_human_players.py'))
inventory=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(inventory)
builder,design=inventory.builder,inventory.design
OWNER='Basketbroom.HumanCosmetic.v1'
FLIGHTWEAR_OWNER='Basketbroom.HumanFlightwear.v1'
DESTINATION='/Game/BasketbroomHumans/Cosmetics'


def template_components(ue, blueprint):
    subsystem=ue.get_engine_subsystem(ue.SubobjectDataSubsystem)
    library=ue.SubobjectDataBlueprintFunctionLibrary
    result={}
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(blueprint):
        data=library.get_data(handle)
        obj=library.get_object_for_blueprint(data,blueprint)
        if not isinstance(obj,ue.ActorComponent): continue
        name=str(library.get_variable_name(data))
        if name in result: raise RuntimeError('Ambiguous template component '+name)
        result[name]=obj
    if any(name not in result for name in ('Body','Face','SkeletalMesh','LODSync')):
        raise RuntimeError('Expected assembled Body, Face, clothing and LODSync templates')
    return result


def actor_contract(ue, blueprint, animation=None):
    actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
    actor=None
    try:
        actor=actors.spawn_actor_from_class(blueprint.generated_class(),ue.Vector(0,0,1400),ue.Rotator(),transient=True)
        if actor is None: raise RuntimeError('Could not spawn cosmetic validation actor')
        if actor.get_editor_property('replicates'): raise RuntimeError('Cosmetic actor must not replicate')
        components={}
        for component in actor.get_components_by_class(ue.ActorComponent):
            if component.get_name() in components: raise RuntimeError('Ambiguous live component name')
            components[component.get_name()]=component
        body,face,garment=(components[name] for name in ('Body','Face','SkeletalMesh'))
        if animation is not None:
            if animation.get_editor_property('skeleton')!=body.get_skeletal_mesh_asset().get_editor_property('skeleton'):
                raise RuntimeError('Fitted flight animation has a different body skeleton')
            for component in (body,face,garment): component.set_update_animation_in_editor(True)
            body.override_animation_data(animation,True,False,.5,0)
            face_class=face.get_editor_property('anim_class')
            face.set_anim_instance_class(None); face.set_anim_instance_class(face_class)
        rows={}
        for name,component in components.items():
            row={'class':component.get_class().get_path_name()}
            if isinstance(component,ue.SceneComponent):
                parent=component.get_attach_parent()
                row.update(parent=parent.get_name() if parent else None,
                    transform={p:str(component.get_editor_property(p)) for p in ('relative_location','relative_rotation','relative_scale3d')})
            if isinstance(component,ue.MeshComponent):
                row.update(material_slots=[str(n) for n in component.get_material_slot_names()],
                           materials=[inventory.path(component.get_material(i)) for i in range(component.get_num_materials())])
            if isinstance(component,ue.SkeletalMeshComponent):
                mesh=component.get_skeletal_mesh_asset()
                leader=component.get_editor_property('leader_pose_component')
                row.update(mesh=inventory.path(mesh),skeleton=inventory.path(mesh.get_editor_property('skeleton')) if mesh else None,
                    animation_class=inventory.path(component.get_editor_property('anim_class')),
                    post_process_anim_blueprint=inventory.path(mesh.get_editor_property('post_process_anim_blueprint')) if mesh else None,
                    leader=leader.get_name() if leader else None,lods=component.get_num_lods(),
                    bones=[str(component.get_bone_name(i)) for i in range(component.get_num_bones())])
            if 'Groom' in component.get_class().get_name():
                row['groom']={p:inventory.prop(component,p) for p in ('groom_asset','binding_asset','forced_lod','use_cards')}
            if name=='LODSync':
                row['lod_sync']={p:str(component.get_editor_property(p)) for p in
                    ('num_lods','forced_lod','min_lod','components_to_sync','custom_lod_mapping')}
            rows[name]=row
        if rows['SkeletalMesh']['leader']!='Body': raise RuntimeError('Clothing construction did not establish the Body leader')
        body_bones=set(rows['Body']['bones'])
        missing=sorted(set(rows['SkeletalMesh']['bones'])-body_bones)
        if missing: raise RuntimeError('Clothing contains bones absent from Body: '+str(missing))
        # Names, rather than Skeleton object identity, bind a leader/follower.
        # The new outfit intentionally owns a separate Skeleton asset.
        pose_errors={}
        if animation is not None:
            for bone in ('pelvis','thigh_l','calf_l','foot_l','hand_l','hand_r'):
                left,right=body.get_socket_location(bone),garment.get_socket_location(bone)
                error=sum((getattr(left,axis)-getattr(right,axis))**2 for axis in ('x','y','z'))**.5
                pose_errors[bone]=error
                if error>.1: raise RuntimeError('Clothing leader pose mismatch at '+bone+': '+str(error))
        return {'components':rows,'clothing_bones_all_present_in_body':True,'leader_pose_errors_cm':pose_errors}
    finally:
        if actor is not None and not actors.destroy_actor(actor): raise RuntimeError('Could not destroy transient cosmetic validation actor')


def run(operation='inspect', name='BB_AthleteA', revision='r2'):
    import unreal as ue
    if operation not in ('inspect','build','inventory'): raise ValueError('Choose inspect, build, or inventory')
    if revision!='r2': raise ValueError('Only the corrected r2 outfit may be staged; preserve rejected r1')
    character,_=builder.validate(ue,name)
    builder.require_clean(ue)
    lib=ue.EditorAssetLibrary
    source_path=builder.ASSEMBLED+'/'+name+'/BP_'+name
    destination=DESTINATION+'/'+name+'/'+revision+'/BP_'+name+'_Flightwear'
    source=lib.load_asset(source_path)
    if not isinstance(source,ue.Blueprint) or lib.get_metadata_tag(source,'BB.Generator')!=builder.ASSEMBLY_OWNER:
        raise RuntimeError('Expected the owned assembly Blueprint')
    if operation=='inventory':
        existing=lib.load_asset(destination)
        if not isinstance(existing,ue.Blueprint) or lib.get_metadata_tag(existing,'BB.Generator')!=OWNER:
            raise RuntimeError('Expected a saved owned cosmetic output')
        output=design.LAB/('cosmetic-inventory-'+name+'.json')
        report={'owner':OWNER,'character':name,'blueprint':destination,'assets_saved':False,
                'dependencies':inventory.dependencies(ue,destination),'actor':actor_contract(ue,existing)}
        design.write(output,report)
        return {'status':'cosmetic_inventoried','report':str(output),'local_packages':len(report['dependencies']['local_packages'])}
    if lib.does_asset_exist(destination): raise RuntimeError('Preserve existing cosmetic output: '+destination)
    outfit_file=design.LAB/('flightwear-'+name+'.json')
    outfit=json.loads(outfit_file.read_text(encoding='utf-8'))
    if outfit.get('owner')!=FLIGHTWEAR_OWNER or outfit.get('character')!=name or outfit.get('revision')!=revision or not outfit.get('assets_saved') or not outfit.get('existing_asset_bytes_preserved'):
        raise RuntimeError('Expected this athlete\'s preserved flightwear staging receipt')
    outfit_mesh=lib.load_asset(outfit['mesh'])
    if not isinstance(outfit_mesh,ue.SkeletalMesh) or lib.get_metadata_tag(outfit_mesh,'BB.Generator')!=FLIGHTWEAR_OWNER:
        raise RuntimeError('Expected owned flightwear mesh')
    expected_root='/Game/BasketbroomHumans/Flightwear/'+name+'/'
    if not outfit_mesh.get_path_name().startswith(expected_root): raise RuntimeError('Flightwear output path mismatch')
    slots=[str(row.material_slot_name) for row in outfit_mesh.get_editor_property('materials')]
    if slots!=outfit['material_slots']: raise RuntimeError('Flightwear material slots differ from receipt')
    team_materials={team:[lib.load_asset(path) for path in outfit['team_materials'][team]] for team in ('Teal','Copper')}
    for materials in team_materials.values():
        if len(materials)!=len(slots) or any(m is None or not m.get_path_name().startswith(expected_root) or
            lib.get_metadata_tag(m,'BB.Generator')!=FLIGHTWEAR_OWNER for m in materials):
            raise RuntimeError('Expected exact owned flightwear team materials')
    flight=json.loads((design.LAB/('flight-'+name+'.json')).read_text(encoding='utf-8'))
    animation=lib.load_asset(flight['animation'])
    if not isinstance(animation,ue.AnimSequence) or lib.get_metadata_tag(animation,'BB.Generator')!='Basketbroom.HumanFlight.v1':
        raise RuntimeError('Expected owned fitted animation')
    templates=template_components(ue,source)
    template_summary={key:{'class':obj.get_class().get_path_name(),'path':obj.get_path_name()} for key,obj in templates.items()}
    report={'owner':OWNER,'revision':revision,'operation':operation,'character':name,'source_blueprint':source_path,'blueprint':destination,
            'outfit_receipt':str(outfit_file),'outfit_receipt_sha256':design.digest(outfit_file),
            'mesh':outfit['mesh'],'animation':flight['animation'],'templates':template_summary,
            'assets_saved':False,'game_integrated':False,'status':'inputs_verified'}
    if operation=='inspect': return report
    attempt=design.LAB/'cosmetic-receipts'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8])
    attempt.mkdir(parents=True,exist_ok=False)
    report['report']=str(attempt/'result.json')
    before=design.file_tree(design.LAB/'Content',design.ASSET_SUFFIXES)
    actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
    selected=list(actors.get_selected_level_actors())
    try:
        baseline=actor_contract(ue,source,animation)
        duplicate=lib.duplicate_asset(source_path,destination)
        if not isinstance(duplicate,ue.Blueprint): raise RuntimeError('Cosmetic Blueprint duplication failed')
        duplicate_templates=template_components(ue,duplicate)
        garment=duplicate_templates['SkeletalMesh']
        if garment.get_outermost().get_path_name()!=destination:
            raise RuntimeError('Refusing to edit a clothing template outside the new Blueprint package')
        if not isinstance(garment,ue.SkeletalMeshComponent): raise RuntimeError('Expected a skeletal clothing template')
        garment.set_skeletal_mesh_asset(outfit_mesh)
        # This is an unregistered Blueprint template. ActorComponent.cpp's
        # PreEditChange adds a reconstruction context only for registered
        # components; never use this property setter on a live preview actor.
        garment.set_editor_property('override_materials',team_materials['Teal'])
        garment=template_components(ue,duplicate)['SkeletalMesh']
        if garment.get_outermost().get_path_name()!=destination or garment.get_skeletal_mesh_asset()!=outfit_mesh:
            raise RuntimeError('Clothing template changed during property notification')
        if list(garment.get_editor_property('override_materials'))!=team_materials['Teal']:
            raise RuntimeError('Clothing template override materials failed readback')
        ue.BlueprintEditorLibrary.compile_blueprint(duplicate)
        if duplicate.generated_class() is None or duplicate.get_editor_property('status') not in (
                ue.BlueprintStatus.BS_UP_TO_DATE,ue.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS):
            raise RuntimeError('New cosmetic Blueprint did not compile')
        actual=actor_contract(ue,duplicate,animation)
        if set(actual['components'])!=set(baseline['components']): raise RuntimeError('Component topology changed')
        for component,contract in baseline['components'].items():
            if component!='SkeletalMesh' and actual['components'][component]!=contract:
                raise RuntimeError('Original human component contract changed: '+component)
        clothing=actual['components']['SkeletalMesh']
        if clothing['mesh']!=outfit_mesh.get_path_name() or clothing['material_slots']!=slots:
            raise RuntimeError('Construction replaced the staged clothing mesh or slots')
        if clothing['materials']!=[m.get_path_name() for m in team_materials['Teal']]:
            raise RuntimeError('Construction changed the staged clothing materials')
        if clothing['lods']!=1: raise RuntimeError('Expected the staged one-LOD clothing mesh')
        for field in ('parent','transform','leader'):
            if clothing[field]!=baseline['components']['SkeletalMesh'][field]:
                raise RuntimeError('Clothing relationship changed: '+field)
        lib.set_metadata_tag(duplicate,'BB.Generator',OWNER)
        lib.set_metadata_tag(duplicate,'BB.Revision',revision)
        lib.set_metadata_tag(duplicate,'BB.SourceAssembly',source.get_path_name())
        lib.set_metadata_tag(duplicate,'BB.FlightwearMesh',outfit_mesh.get_path_name())
        dirty=[p.get_path_name() for p in list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages())+
               list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())]
        if any(p!=destination for p in dirty): raise RuntimeError('Unexpected dirty packages: '+str(dirty))
        if not lib.save_loaded_asset(duplicate,only_if_is_dirty=False): raise RuntimeError('Could not save exact cosmetic Blueprint')
        bindings=[{'component':'SkeletalMesh','material_slot':slot,'material_slot_index':i,
                   'mint_material':outfit['team_materials']['Teal'][i],'copper_material':outfit['team_materials']['Copper'][i]}
                  for i,slot in enumerate(slots)]
        report.update(status='authored_pending_visual_review',assets_saved=True,actor_class=duplicate.generated_class().get_path_name(),
            body_component='Body',garments=bindings,actor_contract=actual,
            dependency_roots=[destination,flight['animation'].split('.')[0]]+
                             [p.split('.')[0] for p in outfit['team_materials']['Copper']],
            dependencies=inventory.dependencies(ue,destination),
            relative_transform='Pending rendered saddle/hand/foot alignment; not guessed by this tool.',
            lod_note='Original LODSync preserved; the one-LOD clothing follower clamps requested mesh LOD to its available LOD.')
    except Exception:
        report.update(status='failed',error=traceback.format_exc()); raise
    finally:
        actors.set_selected_level_actors(selected)
        after=design.file_tree(design.LAB/'Content',design.ASSET_SUFFIXES)
        report['existing_asset_bytes_preserved']=all(after.get(path)==digest for path,digest in before.items())
        report['dirty_after']=[p.get_path_name() for p in list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages())+
                               list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())]
        design.write(attempt/'result.json',report)
        if report.get('assets_saved'): design.write(design.LAB/('cosmetic-'+name+'.json'),report)
    return {'status':report['status'],'report':report['report'],'blueprint':destination,
            'existing_asset_bytes_preserved':report['existing_asset_bytes_preserved']}


if __name__=='__main__':
    args=globals().get('BRIDGE_ARGS',{})
    RESULT=run(args.get('operation','inspect'),args.get('character','BB_AthleteA'),args.get('revision','r2'))

"""CharacterLab-only assembled human inventory; never saves/copies assets.

operation=inventory traces hard/soft package dependencies and source files.
operation=components also spawns one transient actor, inspects actual component
contracts/materials, then destroys only that actor and restores selection.
"""
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import json
import traceback
import uuid

_spec=importlib.util.spec_from_file_location('bb_human_builder',Path(__file__).with_name('build_human_players.py'))
builder=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(builder)
design=builder.design


def path(obj):
    return obj.get_path_name() if obj is not None else None


def prop(obj,name):
    return design.read_property(obj,name)


def texture_info(ue,texture):
    row={'path':path(texture),'class':texture.get_class().get_path_name()}
    if isinstance(texture,ue.Texture2D):
        row['width']=texture.blueprint_get_size_x(); row['height']=texture.blueprint_get_size_y()
    return row


def material_info(ue,material):
    if material is None: return None
    library=ue.MaterialEditingLibrary
    row={'path':path(material),'class':material.get_class().get_path_name(),
         'parent':prop(material,'parent'),
         'vector_parameters':[str(n) for n in library.get_vector_parameter_names(material)],
         'scalar_parameters':[str(n) for n in library.get_scalar_parameter_names(material)],
         'texture_parameters':[str(n) for n in library.get_texture_parameter_names(material)]}
    if isinstance(material,ue.MaterialInstanceConstant):
        row['vectors']={}
        for name in row['vector_parameters']:
            value=library.get_material_instance_vector_parameter_value(material,name)
            row['vectors'][name]=[value.r,value.g,value.b,value.a]
        row['textures']={}
        for name in row['texture_parameters']:
            texture=library.get_material_instance_texture_parameter_value(material,name)
            row['textures'][name]=texture_info(ue,texture) if texture else None
    return row


def dependencies(ue,blueprint_path):
    registry=ue.AssetRegistryHelpers.get_asset_registry()
    options={kind:ue.AssetRegistryDependencyOptions(
        include_soft_package_references=kind=='soft',include_hard_package_references=kind=='hard',
        include_searchable_names=False,include_soft_management_references=False,
        include_hard_management_references=False) for kind in ('hard','soft')}
    graph={}; pending=[blueprint_path]; external={}; rows=[]
    while pending:
        package=pending.pop()
        if package in graph: continue
        edges={kind:sorted(str(n) for n in registry.get_dependencies(package,option)) for kind,option in options.items()}
        graph[package]=edges
        asset_data=registry.get_assets_by_package_name(package)
        flags=[int(a.package_flags) for a in asset_data if hasattr(a,'package_flags')]
        # PKG_EditorOnly is 0x40 in installed ObjectMacros.h. Missing reflection
        # stays unknown; it is never silently treated as runtime-compatible.
        classes=[str(a.asset_class_path) for a in asset_data]
        base=design.LAB/'Content'/package.removeprefix('/Game/')
        files=[base.with_suffix(suffix) for suffix in design.ASSET_SUFFIXES if base.with_suffix(suffix).is_file()]
        rows.append({'package':package,'asset_classes':classes,'package_flags':flags,
                     'editor_only':any(f & 0x40 for f in flags) if flags else None,
                     'files':[{'path':str(p),'sha256':design.digest(p),'bytes':p.stat().st_size} for p in files],
                     'saved_package_exists':base.with_suffix('.uasset').is_file() or base.with_suffix('.umap').is_file()})
        for kind,refs in edges.items():
            for ref in refs:
                if ref.startswith('/Game/'): pending.append(ref)
                else: external.setdefault(ref,set()).add(kind)
        if len(graph)>5000: raise RuntimeError('Unexpected dependency closure larger than 5000 local packages')
    hard=set(); pending=[blueprint_path]
    while pending:
        package=pending.pop()
        if package in hard: continue
        hard.add(package)
        pending.extend(n for n in graph.get(package,{}).get('hard',[]) if n.startswith('/Game/'))
    return {'root':blueprint_path,'local_packages':sorted(rows,key=lambda r:r['package']),
            'local_hard_closure':sorted(hard),'local_including_soft_closure':sorted(graph),
            'local_soft_only_closure':sorted(set(graph)-hard),'dependency_graph':graph,
            'external_packages':[{'package':p,'reference_kinds':sorted(k)} for p,k in sorted(external.items())],
            'external_roots':sorted({p.split('/')[1] for p in external if p.startswith('/')}),
            'missing_local_packages':[r['package'] for r in rows if not r['saved_package_exists']],
            'editor_only_local_packages':[r['package'] for r in rows if r['editor_only'] is True],
            'unknown_editor_only_flags':[r['package'] for r in rows if r['editor_only'] is None],
            'files_copied':0,'note':'Registry graph includes editor soft references; it is an inventory, not an automatic migration allowlist.'}


def component_inventory(ue,blueprint):
    actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
    selected=list(actors.get_selected_level_actors())
    dirty_before=[p.get_path_name() for p in ue.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    content_before=[p.get_path_name() for p in ue.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    if dirty_before: raise RuntimeError('Use a clean lab map for transient component inspection')
    actor=None; report={'components':[],'spawned_transient':False,'destroyed':False,'map_saved':False}
    try:
        actor=actors.spawn_actor_from_class(blueprint.generated_class(),ue.Vector(0,0,300),ue.Rotator(),transient=True)
        if actor is None: raise RuntimeError('Could not spawn the assembled human actor')
        report.update(actor=path(actor),spawned_transient=True)
        for component in actor.get_components_by_class(ue.ActorComponent):
            row={'name':component.get_name(),'class':component.get_class().get_path_name()}
            if isinstance(component,ue.SceneComponent):
                row.update(parent=path(component.get_attach_parent()),
                           relative_location=prop(component,'relative_location'),
                           relative_rotation=prop(component,'relative_rotation'),
                           relative_scale=prop(component,'relative_scale3d'),visible=bool(component.is_visible()))
            if isinstance(component,ue.PrimitiveComponent):
                row['owner_visibility']={n:prop(component,n) for n in ('owner_no_see','only_owner_see')}
                row['material_slots']=[str(n) for n in component.get_material_slot_names()]
                row['materials']=[material_info(ue,component.get_material(i)) for i in range(component.get_num_materials())]
            if isinstance(component,ue.SkeletalMeshComponent):
                mesh=component.get_skeletal_mesh_asset()
                row.update(mesh=path(mesh),animation_mode=str(component.get_animation_mode()),
                           lod_count=component.get_num_lods(),bone_count=component.get_num_bones(),
                           bone_names=[str(component.get_bone_name(i)) for i in range(component.get_num_bones())],
                           skeleton=prop(mesh,'skeleton') if mesh else None,
                           post_process_anim_blueprint=prop(mesh,'post_process_anim_blueprint') if mesh else None,
                           animation_class=prop(component,'anim_class'),
                           animation_data=prop(component,'animation_data'),
                           leader_pose_component=prop(component,'leader_pose_component'))
            if 'Groom' in component.get_class().get_name():
                row['groom']={n:prop(component,n) for n in ('groom_asset','binding_asset','forced_lod','use_cards')}
            if 'LODSync' in component.get_class().get_name():
                row['lod_sync']={n:prop(component,n) for n in ('num_lods','forced_lod','min_lod','components_to_sync','custom_lod_mapping')}
            report['components'].append(row)
    finally:
        if actor is not None:
            report['destroyed']=bool(actors.destroy_actor(actor))
            if not report['destroyed']: raise RuntimeError('Transient probe actor cleanup failed')
        actors.set_selected_level_actors(selected)
        report['dirty_maps_before']=dirty_before
        report['dirty_maps_after']=[p.get_path_name() for p in ue.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
        report['dirty_content_before']=content_before
        report['dirty_content_after']=[p.get_path_name() for p in ue.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    return report


def run(operation='inventory',name='BB_AthleteA'):
    import unreal as ue
    character,_=builder.validate(ue,name)
    if operation not in ('inventory','components'): raise ValueError('Choose inventory or components')
    blueprint_path=builder.ASSEMBLED+'/'+name+'/BP_'+name
    blueprint=ue.EditorAssetLibrary.load_asset(blueprint_path)
    if not isinstance(blueprint,ue.Blueprint) or ue.EditorAssetLibrary.get_metadata_tag(blueprint,'BB.Generator') != builder.ASSEMBLY_OWNER:
        raise RuntimeError('Expected a completed owned actor assembly')
    attempt=design.LAB/'inspection-receipts'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8])
    attempt.mkdir(parents=True,exist_ok=False)
    output=attempt/'result.json'
    report={'operation':operation,'status':'inspecting','blueprint':blueprint_path,
            'character':design.describe_character(ue,character),'assets_saved':False,'files_copied':0,'report':str(output)}
    try:
        report['dependencies']=dependencies(ue,blueprint_path)
        body=character.get_editor_property('body_textures')
        report['design_body_textures']={str(key):texture_info(ue,texture) for key,texture in body.items() if texture}
        if operation=='components': report['transient_actor']=component_inventory(ue,blueprint)
        report['status']='inspected_pending_render_and_runtime_validation'
    except Exception:
        report.update(status='failed',error=traceback.format_exc())
        raise
    finally:
        design.write(output,report)
        design.write(design.LAB/'latest-human-inspection.json',{'report':str(output),'status':report['status']})
    return {'status':report['status'],'report':str(output),'local_package_count':len(report['dependencies']['local_packages']),
            'external_roots':report['dependencies']['external_roots']}


if __name__=='__main__':
    args=globals().get('BRIDGE_ARGS',{})
    RESULT=run(args.get('operation','inventory'),args.get('character','BB_AthleteA'))

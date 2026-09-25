"""Read-only fitted-flightwear feasibility probe in the isolated CharacterLab.

Copies owned preview/assembled mesh geometry into transient DynamicMeshes;
records positions, topology and skinning API contracts. No saved asset edits,
cloud calls, geometry authoring, or main project changes occur.
"""
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import traceback
import uuid

_spec=importlib.util.spec_from_file_location('bb_human_builder',Path(__file__).with_name('build_human_players.py'))
builder=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(builder)
design=builder.design


def docs(ue):
    contracts={
        'GeometryScript_AssetUtils':['copy_mesh_from_skeletal_mesh'],
        'GeometryScript_NewAssetUtils':['create_new_skeletal_mesh_asset_from_mesh'],
        'GeometryScript_MeshQueries':['get_all_vertex_positions','get_all_triangle_indices','get_vertex_count','get_num_uv_sets'],
        'GeometryScript_List':['convert_vector_list_to_array','convert_triangle_list_to_array','convert_array_to_vector_list','convert_array_to_index_list'],
        'GeometryScript_BoneWeights':['get_vertex_bone_weights','get_all_bones_info','transfer_bone_weights_from_mesh'],
        'GeometryScript_Normals':['get_mesh_per_vertex_normals','recompute_normals'],
        'GeometryScript_MeshEdits':['set_all_mesh_vertex_positions','delete_triangles_from_mesh'],
        'GeometryScript_SelectionQueries':['convert_index_array_to_mesh_selection'],
        'GeometryScriptCreateNewSkeletalMeshAssetOptions':[],
        'GeometryScriptMeshReadLOD':[],
    }
    output={}
    for name,methods in contracts.items():
        cls=getattr(ue,name,None)
        output[name]={'available':cls is not None,'doc':str(getattr(cls,'__doc__',''))[:16000],
                      'public_names':[n for n in dir(cls) if not n.startswith('_')] if cls else [],
                      'methods':{method:str(getattr(getattr(cls,method,None),'__doc__',''))[:10000] for method in methods}}
    return output


def copy_geometry(ue,mesh):
    lod=ue.GeometryScriptMeshReadLOD()
    lod.lod_index=0
    dynamic=ue.DynamicMesh()
    result=ue.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(mesh,dynamic,ue.GeometryScriptCopyMeshFromAssetOptions(),lod)
    if not isinstance(result,tuple) or result[-1]!=ue.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError('Skeletal mesh copy did not report success: '+str(result))
    query=ue.GeometryScript_MeshQueries
    positions_result=query.get_all_vertex_positions(dynamic,False)
    triangles_result=query.get_all_triangle_indices(dynamic,False)
    vectors=next(value for value in positions_result if isinstance(value,ue.GeometryScriptVectorList))
    triangles=next(value for value in triangles_result if isinstance(value,ue.GeometryScriptTriangleList))
    positions=ue.GeometryScript_List.convert_vector_list_to_array(vectors)
    indices=ue.GeometryScript_List.convert_triangle_list_to_array(triangles)
    return dynamic,{'mesh':mesh.get_path_name(),'skeleton':design.read_property(mesh,'skeleton'),
        'vertex_count':query.get_vertex_count(dynamic),'uv_sets':query.get_num_uv_sets(dynamic),
        'position_result':str(positions_result),'triangles_result':str(triangles_result),
        'positions':[[v.x,v.y,v.z] for v in positions],'triangles':[[v.x,v.y,v.z] for v in indices]}


def run(name='BB_AthleteA',geometry=True):
    import unreal as ue
    character,subsystem=builder.validate(ue,name)
    builder.require_clean(ue)
    active=getattr(ue,builder.KEY,None)
    if active and not active.finished: raise RuntimeError('Wait for cloud work before geometry inspection')
    if subsystem.is_object_added_for_editing(character): raise RuntimeError('Close the character asset editor first')
    attempt=design.LAB/'flightwear-probes'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8])
    attempt.mkdir(parents=True,exist_ok=False)
    report={'status':'inspecting','character':character.get_path_name(),'api':docs(ue),
            'assets_saved':False,'cloud_requests_made':False,'report':str(attempt/'result.json')}
    design.write(attempt/'result.json',report)
    if not geometry:
        report['status']='api_inspected_no_flightwear_created'
        design.write(attempt/'result.json',report)
        return report
    registered=False; preview=None
    actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
    selected=list(actors.get_selected_level_actors())
    before=design.file_tree(design.LAB/'Content',design.ASSET_SUFFIXES)
    try:
        if not subsystem.try_add_object_to_edit(character): raise RuntimeError('Could not open owned design for transient geometry inspection')
        registered=True
        preview=subsystem.spawn_meta_human_actor(character=character,keep_transient=True)
        if preview is None: raise RuntimeError('Could not spawn the owned transient preview')
        components=preview.get_components_by_class(ue.SkeletalMeshComponent)
        report['preview_components']=[{'name':c.get_name(),'mesh':c.get_skeletal_mesh_asset().get_path_name() if c.get_skeletal_mesh_asset() else None} for c in components]
        bodies=[c for c in components if c.get_name()=='Body']
        if len(bodies)!=1 or bodies[0].get_skeletal_mesh_asset() is None: raise RuntimeError('Preview must have exactly one Body mesh')
        preview_dynamic,preview_info=copy_geometry(ue,bodies[0].get_skeletal_mesh_asset())
        assembled=ue.EditorAssetLibrary.load_asset(builder.ASSEMBLED+'/'+name+'/Body/SKM_'+name+'_BodyMesh')
        assembled_dynamic,assembled_info=copy_geometry(ue,assembled)
        design.write(attempt/'preview-body-geometry.json',preview_info)
        design.write(attempt/'assembled-body-geometry.json',assembled_info)
        report['preview_geometry']={k:v for k,v in preview_info.items() if k not in ('positions','triangles')}
        report['assembled_geometry']={k:v for k,v in assembled_info.items() if k not in ('positions','triangles')}
        report['preview_triangle_count']=len(preview_info['triangles'])
        report['assembled_triangle_count']=len(assembled_info['triangles'])
        weights=getattr(ue,'GeometryScript_BoneWeights',None)
        if weights:
            report['sample_skin_weights']={str(i):str(weights.get_vertex_bone_weights(preview_dynamic,i)) for i in (0,len(preview_info['positions'])//2,len(preview_info['positions'])-1)}
            report['bone_info']=str(weights.get_all_bones_info(preview_dynamic))
        report['status']='geometry_inspected_no_flightwear_created'
    except Exception:
        report.update(status='failed',error=traceback.format_exc()); raise
    finally:
        if registered and subsystem.is_object_added_for_editing(character): subsystem.remove_object_to_edit(character)
        actors.set_selected_level_actors(selected)
        report['asset_bytes_preserved']=before==design.file_tree(design.LAB/'Content',design.ASSET_SUFFIXES)
        report['dirty_after']=[p.get_path_name() for p in list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages())+list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())]
        design.write(attempt/'result.json',report)
    return {'status':report['status'],'report':report['report'],'preview_triangles':report.get('preview_triangle_count'),
            'assembled_triangles':report.get('assembled_triangle_count'),'asset_bytes_preserved':report['asset_bytes_preserved']}


if __name__=='__main__':
    args=globals().get('BRIDGE_ARGS',{})
    RESULT=run(args.get('character','BB_AthleteA'),args.get('geometry',True))

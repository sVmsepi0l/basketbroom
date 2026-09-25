"""Stage two original environment variants of the existing UE5 regulation map.

Bridge: stage_arena_environments.py {"dry_run": false}
Dry run is default. Only two new map paths and /Basketbroom/Environments assets
are writable. Existing regulation/training maps and all sporting assets remain
byte-identical. Native kit imports require a separate authenticated native stage.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import shutil
import traceback
import uuid

ROOT=Path(__file__).resolve().parents[1]
CONTENT=ROOT/'DevelopmentHarness/Plugins/Basketbroom/Content'
SOURCE='/Basketbroom/Maps/BB_Regulation'
ART='/Basketbroom/Environments'
TAG='BB.Environment.v1'
MAPS=('/Basketbroom/Maps/BB_Redrock','/Basketbroom/Maps/BB_Redwoods')
TEXTURES=('T_BB_RedSandstone_Albedo','T_BB_Adobe_Albedo','T_BB_RedwoodBark_Albedo')
BACKDROPS={
 'Distant continuous ridgeline':('/Script/Engine.StaticMeshActor','/Basketbroom/Art/Meshes/SM_BB_Terrain'),
 'Distant layered conifer forest':('/Script/Engine.StaticMeshActor','/Basketbroom/Art/Meshes/SM_BB_Treeline'),
 'Twilight dome':('/Script/Engine.StaticMeshActor','/Engine/BasicShapes/Sphere'),
 'Distant stars':('/Script/Engine.StaticMeshActor','/Basketbroom/Art/Meshes/SM_BB_Stars'),
 'Ground horizon':('/Script/Engine.StaticMeshActor','/Engine/BasicShapes/Cube'),
 'Twilight amber key':('/Script/Engine.DirectionalLight',None),
 'Blue twilight ambience':('/Script/Engine.SkyLight',None),
 'Aerial depth':('/Script/Engine.ExponentialHeightFog',None),
 'Arena presentation':('/Script/Engine.PostProcessVolume',None),
}


def module(name, filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/'Tools'/filename)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')


def content_hashes():
    return {p.relative_to(CONTENT).as_posix():digest(p) for p in CONTENT.rglob('*') if p.is_file() and p.suffix in ('.uasset','.umap','.uexp','.ubulk')}


def load_manifest():
    path=ROOT/'SourceArt/Environments/environments_manifest.json'
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    dimensions=module('_bb_env_dims','arena_dimensions.py')
    if value.get('schema')!=1 or value.get('ownership_tag')!=TAG or value.get('source_map')!=SOURCE:
        raise ValueError('Unexpected environment source ownership/schema')
    if value['sporting_dimensions'] != dimensions.dimensions():raise ValueError('Environment source used stale sporting dimensions')
    if set(v['map'] for v in value['venues'])!=set(MAPS) or len(value['venues'])!=2:raise ValueError('Expected exactly two owned venues')
    names=set()
    for venue in value['venues']:
        if venue['clearance_audit']['decorative_intrusions']!=0:raise ValueError('Source decoration enters playing volume')
        for mesh in venue['meshes']:
            source=(ROOT/'SourceArt/Environments'/mesh['file']).resolve()
            source.relative_to((ROOT/'SourceArt/Environments/Meshes').resolve())
            if source.suffix!='.obj' or not mesh['name'].startswith('SM_BB_ENV_') or mesh['name'] in names:raise ValueError('Unowned/duplicate source mesh')
            if digest(source)!=mesh['sha256']:raise ValueError('Source mesh hash differs: '+mesh['name'])
            names.add(mesh['name'])
        local={m['name'] for m in venue['meshes']}
        if any(i['mesh'] not in local or i['material'] not in value['materials'] or i['collision']!='NoCollision' for i in venue['instances']):
            raise ValueError('Invalid environment instance')
    textures={}
    for name in TEXTURES:
        source=ROOT/'SourceArt/Environments/Textures'/(name+'.png')
        if not source.is_file():raise ValueError('Required original albedo not ready: '+str(source))
        textures[name]={'source':str(source),'sha256':digest(source)}
    return value,textures


def allowed_content(manifest):
    result={'Maps/'+p.rsplit('/',1)[-1]+'.umap' for p in MAPS}
    result |= {'Environments/Meshes/'+m['name']+'.uasset' for v in manifest['venues'] for m in v['meshes']}
    result |= {'Environments/Materials/M_BB_ENV_'+name+'.uasset' for name in manifest['materials']}
    result |= {'Environments/Materials/M_BB_ENV_Sky_'+name+'.uasset' for name in ('redrock','redwoods')}
    result |= {'Environments/Textures/'+name+'.uasset' for name in TEXTURES}
    return result


def portable_snapshot(unreal, actors):
    helper=module('_bb_env_snapshot','stage_arena_expansion.py')
    result={}
    for path,record in helper.snapshot(unreal,actors).items():
        # Actor names are stable across NewLevelFromTemplate. Package prefixes
        # necessarily differ, but each sporting component/material stays exact.
        result[path.rsplit(':PersistentLevel.',1)[-1]]=record
    return result


def backdrop_keys(records, require_all=True):
    result=set()
    for key,r in records.items():
        if r['label'] not in BACKDROPS:continue
        cls,mesh=BACKDROPS[r['label']]
        if r['class']!=cls or 'BB.Generated' not in r['tags'] or (r.get('mesh') or '').split('.')[0]!=(mesh or ''):
            raise RuntimeError('Backdrop label is not sufficient ownership: '+r['label'])
        result.add(key)
    if require_all and len(result)!=len(BACKDROPS):raise RuntimeError('Expected exactly nine existing owned backdrop actors')
    return result


def protected(records, require_backdrops=True):
    removed=backdrop_keys(records,require_backdrops)
    return {key:r for key,r in records.items() if key not in removed and TAG not in r['tags']}


def assert_protected(expected, current):
    if set(expected)!=set(current):raise RuntimeError('Sporting/unrelated actor identities differ in variant map')
    for key in expected:
        if expected[key]!=current[key]:raise RuntimeError('Sporting/unrelated actor state differs: '+key)


def run(dry_run=True):
    import unreal
    manifest,textures=load_manifest()
    if not unreal.SystemLibrary.get_engine_version().startswith('5.8.'):
        raise RuntimeError('This saved-map stage targets the UE5.8 harness only; no UE5 packages enter HLCK')
    project=Path(unreal.Paths.project_dir()).resolve()
    if project!=(ROOT/'DevelopmentHarness').resolve():raise RuntimeError('Wrong editor project')
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    worlds=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assets=unreal.EditorAssetLibrary;asset_tools=unreal.AssetToolsHelpers.get_asset_tools()
    def clean():
        if levels.is_in_play_in_editor():raise RuntimeError('Stop Play before environment staging')
        dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
        if dirty:raise RuntimeError('Unsaved editor work must remain untouched: '+str([p.get_path_name() for p in dirty]))
    clean()
    original=worlds.get_editor_world().get_path_name().split('.')[0]
    if original not in (SOURCE,'/Basketbroom/Maps/BB_Arena')+MAPS:raise RuntimeError('Load an owned Basketbroom map first')
    attempt=ROOT/'.local/environment-stage'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8])
    attempt.mkdir(parents=True,exist_ok=False);receipt=attempt/'result.json'
    before=content_hashes();allowed=allowed_content(manifest)
    report={'status':'preflight','dry_run':dry_run,'original_map':original,'engine':unreal.SystemLibrary.get_engine_version(),
       'manifest_sha256':digest(ROOT/'SourceArt/Environments/environments_manifest.json'),'textures':textures,'allowed_content':sorted(allowed),'maps':[],'backups':[]}
    def save():write(receipt,report)
    save()
    def actor(cls,label,location=(0,0,0),rotation=(0,0,0)):
        a=actors.spawn_actor_from_class(cls,unreal.Vector(*location),unreal.Rotator(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]))
        if a is None:raise RuntimeError('Failed to create '+label)
        a.set_actor_label(label);a.set_editor_property('tags',[unreal.Name(TAG)])
        a.set_folder_path('Basketbroom/Environment');return a
    def load_material(name):return assets.load_asset(ART+'/Materials/M_BB_ENV_'+name)
    def static_mesh(label,mesh,mat,location=(0,0,0),scale=(1,1,1),yaw=0,shadow=True):
        a=actor(unreal.StaticMeshActor,label,location,(0,yaw,0));a.set_actor_scale3d(unreal.Vector(*scale))
        c=a.get_component_by_class(unreal.StaticMeshComponent);c.set_static_mesh(mesh);c.set_material(0,mat)
        c.set_collision_profile_name('NoCollision');c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        c.set_editor_property('cast_shadow',shadow);c.set_editor_property('generate_overlap_events',False)
        return a
    def material(name, data, sky=False):
        path=ART+'/Materials/M_BB_ENV_'+name
        mat=assets.load_asset(path) or asset_tools.create_asset(path.rsplit('/',1)[-1],ART+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
        if mat is None:raise RuntimeError('Cannot create environment material '+name)
        lib=unreal.MaterialEditingLibrary;lib.delete_all_material_expressions(mat)
        mat.set_editor_property('two_sided',True)
        mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT if sky else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
        def node(cls,**props):
            n=lib.create_material_expression(mat,cls,-700,0)
            for key,value in props.items():n.set_editor_property(key,value)
            return n
        def wire(a,b,pin='',output=''):
            if not lib.connect_material_expressions(a,output,b,pin):raise RuntimeError('Material connection failed '+name+' '+pin)
        def mul(a,value):
            b=node(unreal.MaterialExpressionMultiply,const_b=value);wire(a,b,'A');return b
        def add(a,b=None,value=0):
            n=node(unreal.MaterialExpressionAdd,const_b=value);wire(a,n,'A')
            if b is not None:wire(b,n,'B')
            return n
        color=node(unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(*data['color'],1))
        world=node(unreal.MaterialExpressionWorldPosition)
        if sky:
            z=node(unreal.MaterialExpressionComponentMask,r=False,g=False,b=True,a=False);wire(world,z)
            clamp=node(unreal.MaterialExpressionClamp);wire(mul(z,1/43000),clamp)
            horizon=node(unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(*data['horizon'],1))
            mix=node(unreal.MaterialExpressionLinearInterpolate);wire(horizon,mix,'A');wire(color,mix,'B');wire(clamp,mix,'Alpha')
            lib.connect_material_property(mix,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        else:
            texname=data.get('texture')
            if texname:
                texture=assets.load_asset(ART+'/Textures/'+texname)
                pos=mul(world,1/data['texture_cm']);normal=node(unreal.MaterialExpressionVertexNormalWS)
                absolute=node(unreal.MaterialExpressionAbs);wire(normal,absolute)
                samples=[];weights=[]
                for axes,axis in (((True,True,False),2),((True,False,True),1),((False,True,True),0)):
                    uv=node(unreal.MaterialExpressionComponentMask,r=axes[0],g=axes[1],b=axes[2],a=False);wire(pos,uv)
                    sample=node(unreal.MaterialExpressionTextureSample,texture=texture);wire(uv,sample)
                    weight=node(unreal.MaterialExpressionComponentMask,r=axis==0,g=axis==1,b=axis==2,a=False);wire(absolute,weight)
                    weighted=node(unreal.MaterialExpressionMultiply);wire(sample,weighted,'A',output='RGB');wire(weight,weighted,'B')
                    samples.append(weighted);weights.append(weight)
                blend=node(unreal.MaterialExpressionDivide);wire(add(add(samples[0],samples[1]),samples[2]),blend,'A');wire(add(add(weights[0],weights[1]),weights[2]),blend,'B')
                # Generated basecolor is an art source, not a calibrated scan.
                # A moderate tint preserves mineral/bark detail and readable albedo.
                tint=node(unreal.MaterialExpressionMultiply);wire(color,tint,'A');wire(add(mul(blend,1.6),value=.35),tint,'B');color=tint
            else:
                noise=node(unreal.MaterialExpressionNoise,scale=.004,quality=1,levels=1,output_min=0.,output_max=1.)
                wire(world,noise,str(lib.get_material_expression_input_names(noise)[0]))
                varied=node(unreal.MaterialExpressionMultiply);wire(color,varied,'A');wire(add(mul(noise,.30),value=.8),varied,'B');color=varied
            lib.connect_material_property(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
            for value,prop in ((data.get('roughness',.95),unreal.MaterialProperty.MP_ROUGHNESS),(data.get('metallic',0.),unreal.MaterialProperty.MP_METALLIC)):
                n=node(unreal.MaterialExpressionConstant,r=value);lib.connect_material_property(n,'',prop)
            if data.get('water'):
                # Low-amplitude actual vertex waves on the gridded sea surface.
                mask=node(unreal.MaterialExpressionComponentMask,r=True,g=False,b=False,a=False);wire(world,mask)
                timer=node(unreal.MaterialExpressionTime)
                phase=add(mul(mask,.00025),mul(timer,.055));sine=node(unreal.MaterialExpressionSine);wire(phase,sine)
                direction=node(unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(0,0,22,1))
                offset=node(unreal.MaterialExpressionMultiply);wire(sine,offset,'A');wire(direction,offset,'B')
                lib.connect_material_property(offset,'',unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
        lib.recompile_material(mat)
        if not assets.save_loaded_asset(mat):raise RuntimeError('Cannot save '+path)
        return mat
    try:
        if not levels.load_level(SOURCE):raise RuntimeError('Cannot load existing regulation source')
        source_actors=list(actors.get_all_level_actors());source_records=portable_snapshot(unreal,source_actors)
        baseline=protected(source_records);write(attempt/'source-actors.json',source_records)
        mode=worlds.get_editor_world().get_world_settings().get_editor_property('default_game_mode')
        if mode is None or mode.get_path_name()!='/Script/BasketbroomRuntime.BBGameMode':raise RuntimeError('Expected native regulation game mode')
        report['source_map_sha256']=digest(CONTENT/'Maps/BB_Regulation.umap');report['preserved_actor_count']=len(baseline)
        for venue in manifest['venues']:
            exists=assets.does_asset_exist(venue['map'])
            if exists:
                clean()
                if not levels.load_level(venue['map']):raise RuntimeError('Cannot load existing variant')
                current=portable_snapshot(unreal,list(actors.get_all_level_actors()))
                assert_protected(baseline,protected(current,False))
            report['maps'].append({'path':venue['map'],'exists_before':exists,'source_clearance':venue['clearance_audit']})
        if not dry_run:
            for relative in sorted(allowed):
                path=CONTENT/relative
                if path.exists():
                    target=attempt/'backups'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
                    if digest(target)!=before[relative]:raise RuntimeError('Environment backup hash mismatch')
                    report['backups'].append({'file':relative,'backup':str(target),'sha256':before[relative]})
            save()
            # Reimporting referenced meshes dirties the open venue package even
            # before actor edits. Keep the scenery-free source open for imports.
            clean()
            if not levels.load_level(SOURCE):raise RuntimeError('Cannot isolate environment imports from venue maps')
            for name,item in textures.items():
                task=unreal.AssetImportTask()
                for key,value in {'filename':item['source'],'destination_path':ART+'/Textures','destination_name':name,'automated':True,'replace_existing':True,'save':True}.items():task.set_editor_property(key,value)
                asset_tools.import_asset_tasks([task]);tex=assets.load_asset(ART+'/Textures/'+name)
                if tex is None:raise RuntimeError('Texture import failed '+name)
                tex.set_editor_property('srgb',True);tex.set_editor_property('max_texture_size',2048)
                tex.set_editor_property('power_of_two_mode',unreal.TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO)
                assets.save_loaded_asset(tex)
            for name,data in manifest['materials'].items():material(name,data)
            material('Sky_redrock',{'color':[.13,.30,.48],'horizon':[.54,.42,.30]},True)
            material('Sky_redwoods',{'color':[.095,.22,.31],'horizon':[.40,.51,.52]},True)
            for venue in manifest['venues']:
                for item in venue['meshes']:
                    task=unreal.AssetImportTask()
                    for key,value in {'filename':str(ROOT/'SourceArt/Environments'/item['file']),'destination_path':ART+'/Meshes','destination_name':item['name'],'automated':True,'replace_existing':True,'save':True,'factory':unreal.FbxFactory()}.items():task.set_editor_property(key,value)
                    options=unreal.FbxImportUI()
                    for key,value in {'import_mesh':True,'import_materials':False,'import_textures':False,'import_as_skeletal':False,'mesh_type_to_import':unreal.FBXImportType.FBXIT_STATIC_MESH}.items():options.set_editor_property(key,value)
                    data=options.get_editor_property('static_mesh_import_data')
                    for key,value in {'combine_meshes':True,'auto_generate_collision':False,'convert_scene':False,'convert_scene_unit':False,'normal_import_method':unreal.FBXNormalImportMethod.FBXNIM_COMPUTE_NORMALS}.items():data.set_editor_property(key,value)
                    task.set_editor_property('options',options);asset_tools.import_asset_tasks([task])
                    mesh=assets.load_asset(ART+'/Meshes/'+item['name'])
                    if mesh is None:raise RuntimeError('Mesh import failed '+item['name'])
                    mesh.set_material(0,load_material(item['material']));assets.save_loaded_asset(mesh)
            # OBJ import can reflect Y even with convert_scene disabled. Prove
            # that from all signed bounds/topology before compensating actors.
            axes=module('_bb_env_import_axes','arena_environment_axes.py')
            report['import_axes']=axes.audit(unreal,manifest,ART)
            y_compensation=report['import_axes']['actor_y_compensation']
            save()
            for venue,item in zip(manifest['venues'],report['maps']):
                clean()
                if item['exists_before']:
                    if not levels.load_level(venue['map']):raise RuntimeError('Cannot load owned variant')
                elif not levels.new_level_from_template(venue['map'],SOURCE):raise RuntimeError('Cannot duplicate regulation map')
                world=worlds.get_editor_world()
                if world.get_path_name().split('.')[0]!=venue['map']:raise RuntimeError('Wrong variant world')
                existing=list(actors.get_all_level_actors());records=portable_snapshot(unreal,existing)
                assert_protected(baseline,protected(records,not item['exists_before']))
                removable=backdrop_keys(records,not item['exists_before'])
                for a in existing:
                    key=a.get_path_name().rsplit(':PersistentLevel.',1)[-1]
                    if a.actor_has_tag(TAG):
                        if not a.get_actor_label().startswith(('redrock /','redwoods /')):raise RuntimeError('Environment ownership tag on unexpected label')
                        if a.get_class().get_path_name() not in ('/Script/Engine.StaticMeshActor','/Script/Engine.DirectionalLight','/Script/Engine.SkyLight','/Script/Engine.ExponentialHeightFog','/Script/Engine.PostProcessVolume','/Script/Engine.CameraActor'):
                            raise RuntimeError('Environment ownership tag on unexpected class')
                        removable.add(key)
                    if key in removable and not actors.destroy_actor(a):raise RuntimeError('Cannot replace exact owned backdrop actor')
                for placement in venue['instances']:
                    static_mesh(placement['label'],assets.load_asset(ART+'/Meshes/'+placement['mesh']),load_material(placement['material']),
                       placement['location'],[placement['scale'][0],placement['scale'][1]*y_compensation,placement['scale'][2]],placement['yaw'],placement['cast_shadow'])
                vid=venue['id'];warm=vid=='redrock'
                static_mesh(vid+' / daylight sky',assets.load_asset('/Engine/BasicShapes/Sphere'),load_material('Sky_'+vid),scale=(6000,6000,6000),shadow=False)
                sun=actor(unreal.DirectionalLight,vid+' / sun',(0,0,15000),(-31,-76 if warm else -122,0))
                light=sun.get_component_by_class(unreal.DirectionalLightComponent);light.set_mobility(unreal.ComponentMobility.MOVABLE)
                light.set_intensity(3.2 if warm else 2.7);light.set_light_color(unreal.LinearColor(*( (1.,.80,.57,1.) if warm else (.76,.88,1.,1.))))
                light.set_editor_property('light_source_angle',1.3);light.set_editor_property('dynamic_shadow_distance_movable_light',65000.)
                sky=actor(unreal.SkyLight,vid+' / sky fill',(0,0,9000));c=sky.get_component_by_class(unreal.SkyLightComponent)
                c.set_mobility(unreal.ComponentMobility.MOVABLE);c.set_intensity(1.4 if warm else 1.1);c.set_editor_property('lower_hemisphere_is_black',False);c.recapture_sky()
                fog=actor(unreal.ExponentialHeightFog,vid+' / atmosphere',(0,0,-850));c=fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
                c.set_fog_density(.00085 if warm else .0016);c.set_fog_height_falloff(.16);c.set_start_distance(8000 if warm else 5500)
                c.set_fog_inscattering_color(unreal.LinearColor(*( (.26,.16,.08,1.) if warm else (.14,.24,.27,1.))))
                c.set_volumetric_fog(False)
                pp=actor(unreal.PostProcessVolume,vid+' / presentation');pp.set_editor_property('unbound',True)
                settings=pp.get_editor_property('settings')
                for key,value in {'override_auto_exposure_min_brightness':True,'override_auto_exposure_max_brightness':True,'auto_exposure_min_brightness':.6,'auto_exposure_max_brightness':.6,'override_bloom_intensity':True,'bloom_intensity':.14,'override_motion_blur_amount':True,'motion_blur_amount':0.,'override_vignette_intensity':True,'vignette_intensity':.10}.items():settings.set_editor_property(key,value)
                pp.set_editor_property('settings',settings)
                # Preserve the overview framing as the arena footprint grows.
                framing=module('_bb_env_camera_dimensions','arena_dimensions.py').FOOTPRINT_LINEAR_MULTIPLIER
                actor(unreal.CameraActor,vid+' / environment hero',(-30000*framing,-32000*framing,9400*framing),(-12,47,0))
                current=list(actors.get_all_level_actors());assert_protected(baseline,protected(portable_snapshot(unreal,current),False))
                if world.get_world_settings().get_editor_property('default_game_mode')!=mode:raise RuntimeError('Variant game mode changed')
                for a in current:
                    if a.actor_has_tag(TAG):
                        for c in a.get_components_by_class(unreal.PrimitiveComponent):
                            if c.get_collision_enabled()!=unreal.CollisionEnabled.NO_COLLISION:raise RuntimeError('Scenery unexpectedly collides')
                audit=module('_bb_env_geometry','stage_arena_expansion.py')
                item['geometry_before_save']=audit.collision_audit(unreal,world,current,manifest['sporting_dimensions'])
                if not levels.save_current_level() or not levels.load_level(venue['map']):raise RuntimeError('Cannot save/reload variant')
                current=list(actors.get_all_level_actors());assert_protected(baseline,protected(portable_snapshot(unreal,current),False))
                item['geometry_after_reload']=audit.collision_audit(unreal,worlds.get_editor_world(),current,manifest['sporting_dimensions'])
                item.update(saved_reloaded=True,sporting_actors_preserved=True,game_mode_preserved=True,environment_actor_count=sum(a.actor_has_tag(TAG) for a in current),sha256=digest(CONTENT/'Maps'/(venue['map'].rsplit('/',1)[-1]+'.umap')))
                save()
        if not levels.load_level(original):raise RuntimeError('Cannot restore original clean map')
        clean();after=content_hashes();changed=sorted(p for p in set(before)|set(after) if before.get(p)!=after.get(p))
        if set(changed)-allowed:raise RuntimeError('Content changed outside the exact environment allowlist: '+str(sorted(set(changed)-allowed)))
        if dry_run and changed:raise RuntimeError('Dry run changed content')
        if digest(CONTENT/'Maps/BB_Regulation.umap')!=report['source_map_sha256']:raise RuntimeError('Source regulation map bytes changed')
        report.update(status='ready' if dry_run else 'staged',changed_files=changed,original_world_restored=True,source_map_preserved=True,
                      content_scope_verified=True,gameplay_tested=False,finished_utc=datetime.now(timezone.utc).isoformat())
        save()
        if not dry_run:write(ROOT/'.local/environment-stage-success.json',{'report':str(receipt),'sha256':digest(receipt)})
    except Exception:
        report.update(status='failed',error=traceback.format_exc(),recovery='Inspect receipt and editor. Existing-file backups retained; unsaved work is not discarded automatically.')
        save()
    return {'status':report['status'],'report':str(receipt),'dry_run':dry_run,'gameplay_tested':False}


if __name__=='__main__':
    RESULT=run(dry_run=globals().get('BRIDGE_ARGS',{}).get('dry_run',True))

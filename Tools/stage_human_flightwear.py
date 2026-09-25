"""Stage owned fitted flightwear in CharacterLab, without editing an assembly.

Bridge: {"operation":"inspect"|"build", "character":"BB_AthleteA"}.
Inspect performs the complete transient fit and reports it; build additionally
creates a NEW mesh, dedicated skeleton and materials. Existing output is refused.
The exported outfit replaces the assembly's clothing component for review and
continues to follow Body. Genuine Body, Face, AnimBPs and skin are untouched.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import json
import math
import traceback
import uuid

_spec = importlib.util.spec_from_file_location('bb_flightwear_probe', Path(__file__).with_name('probe_human_flightwear.py'))
probe = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(probe)
builder, design = probe.builder, probe.design
OWNER = 'Basketbroom.HumanFlightwear.v1'
DESTINATION = '/Game/BasketbroomHumans/Flightwear'
SLOTS = ('TeamCloth', 'DarkCloth', 'Leather', 'Trim', 'Sole')


def xyz(v):
    return [float(v.x), float(v.y), float(v.z)]


def unit(v):
    length = math.sqrt(sum(x*x for x in v))
    if length < 1e-7: raise RuntimeError('Degenerate fitting direction')
    return [x/length for x in v]


def subtract(a, b):
    return [x-y for x,y in zip(a,b)]


def dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def srgb(value):
    values = [int(value[i:i+2],16)/255 for i in (0,2,4)]
    return [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values]


def fit_cloth(positions, triangles, normals, bones, neck_band=False):
    """Keep torso/limbs, open wrists and collar, and overlap boot tops.

    All existing UVs and skin weights remain attached to their original vertex
    IDs. Only transient positions and triangle membership are changed.
    """
    required = ('pelvis','neck_01','hand_l','hand_r','lowerarm_l','lowerarm_r','calf_l','calf_r','foot_l','foot_r')
    if any(key not in bones for key in required): raise RuntimeError('Missing reference fitting bones')
    top = max(p[2] for p in positions)
    if not 125 < top < 205 or min(p[2] for p in positions) < -3:
        raise RuntimeError('Unexpected intact body coordinate frame')
    scale = top/144.0
    boot_top = top*.263
    waist = bones['pelvis'][2]+8.0*scale
    collar = min(top-.4*scale, bones['neck_01'][2]+1.8*scale)
    if neck_band:
        # Body ends at a broad chest opening, not at the neck. R3 covers the
        # remaining chest with a separately fitted low band from owned Face.
        collar = max(top+2*scale,min(top+5*scale,bones['neck_01'][2]+3*scale))
    wrists = [(bones['hand_'+side], unit(subtract(bones['hand_'+side],bones['lowerarm_'+side]))) for side in ('l','r')]
    arm_start = min(abs(center[0]) for center,_ in wrists)*.62

    def cuff_distance(p):
        # The nearest wrist avoids letting the opposite arm's half-space cut
        # the torso. Hand geometry projects beyond this cuff plane.
        center,direction = min(wrists,key=lambda row:dot(subtract(p,row[0]),subtract(p,row[0])))
        return dot(subtract(p,center),direction)

    def is_arm(p):
        return abs(p[0])>arm_start

    def keep(p):
        # Wrist planes slope downward in the source rest pose. Applying them
        # globally also amputates the knees: constrain EVERY cuff operation to
        # the arm region, including geometry, allowance and shader masks.
        return p[2] >= boot_top-1.8*scale and (neck_band or p[2] <= collar) and (not is_arm(p) or cuff_distance(p) <= -1.2*scale)

    # Use triangle centroids at the garment openings so the copied surface
    # has a continuous boundary; there is no random decimation or remeshing.
    centroids = [[sum(positions[v][axis] for v in tri)/3 for axis in range(3)] for tri in triangles]
    remove = [i for i,p in enumerate(centroids) if not keep(p)]
    remove_set = set(remove)
    retained = [i for i in range(len(triangles)) if i not in remove_set]
    vertices = sorted({v for i in retained for v in triangles[i]})
    if not 14000 < len(retained) < len(triangles)-1000:
        raise RuntimeError('Unexpected fitted cloth coverage: '+str(len(retained)))
    trouser_band=[i for i,p in enumerate(centroids) if boot_top+3*scale<p[2]<waist-4*scale and not is_arm(p)]
    if len(trouser_band)<500 or any(i in remove_set for i in trouser_band):
        raise RuntimeError('Long-trouser coverage was cut by an unrelated fitting plane')

    adjacent = [set() for _ in positions]
    for i in retained:
        a,b,c = triangles[i]
        adjacent[a].update((b,c)); adjacent[b].update((a,c)); adjacent[c].update((a,b))
    fitted = [list(p) for p in positions]
    # A small constrained smoothing removes skin details from the copied cloth.
    # Projection onto the original normal clamps it outside the actual body.
    for _ in range(8):
        previous = fitted
        fitted = [list(p) for p in previous]
        for i in vertices:
            neighbors = adjacent[i]
            if not neighbors: continue
            smooth = [sum(previous[j][axis] for j in neighbors)/len(neighbors) for axis in range(3)]
            delta = subtract(smooth,positions[i])
            inward = min(0.0,dot(delta,normals[i]))
            fitted[i] = [positions[i][axis]+delta[axis]*.55-normals[i][axis]*inward for axis in range(3)]
    for i in vertices:
        p = positions[i]
        torso = p[2] > waist and abs(p[0]) < 22*scale
        allowance = (1.65 if torso else 1.05)*scale
        # Keep the wrist opening closer to the skin; a wide leather cuff is
        # separately distinguished by material, with no skin tint overrides.
        if is_arm(p) and cuff_distance(p) > -5*scale: allowance = .8*scale
        fitted[i] = [fitted[i][axis]+normals[i][axis]*allowance for axis in range(3)]
    # Project opening rims onto their cut plane to avoid a stair-step cut that
    # follows the source body's irregular triangle rows.
    edges=Counter(tuple(sorted((a,b))) for i in retained for a,b in zip(triangles[i],triangles[i][1:]+triangles[i][:1]))
    boundary={v for edge,count in edges.items() if count==1 for v in edge}
    for i in boundary:
        p=positions[i]
        if p[2]<boot_top+scale: fitted[i][2]=boot_top-1.8*scale
        elif not neck_band and p[2]>collar-2*scale: fitted[i][2]=collar
        elif is_arm(p):
            center,direction=min(wrists,key=lambda row:dot(subtract(p,row[0]),subtract(p,row[0])))
            distance=dot(subtract(fitted[i],center),direction)+1.2*scale
            fitted[i]=[fitted[i][a]-distance*direction[a] for a in range(3)]
    # Continuous pre-skinned shader masks define panel/piping borders. Assigning
    # triangle IDs by centroid made visible jagged patches at arbitrary edges.
    material_ids = [0]*len(triangles)
    return fitted, remove, material_ids, vertices, {
        'reference_height_cm':top,'scale':scale,'boot_top_cm':boot_top,'waist_cm':waist,'collar_cm':collar,
        'separate_neck_band':neck_band,
        'arm_start_cm':arm_start,'wrists':[{'center':center,'direction':direction} for center,direction in wrists],
        'trouser_band_triangles_preserved':len(trouser_band),'opening_boundary_vertices':len(boundary),
        'cloth_triangles':len(retained),'cloth_vertices':len(vertices),
        'cloth_material_triangles':{SLOTS[k]:v for k,v in Counter(material_ids[i] for i in retained).items()}}


def fit_neck_band(positions, triangles, normals, body_positions, body_triangles, fitted_body, fit):
    """Cover the body's open chest rim using only the owned Face's low neck.

    The exported Face and skin are untouched. This copy becomes opaque cloth,
    receives Body weights, and overlaps the garment rim. Abort if the two owned
    fitting sources do not actually share the expected chest boundary.
    """
    scale,top=fit['scale'],fit['collar_cm']
    body_edges=Counter(tuple(sorted((a,b))) for tri in body_triangles for a,b in zip(tri,tri[1:]+tri[:1]))
    rim=sorted({v for edge,count in body_edges.items() if count==1 for v in edge})
    if not 40<=len(rim)<=250: raise RuntimeError('Unexpected source Body chest rim')
    bottom=min(body_positions[v][2] for v in rim)
    if any(body_positions[v][2]<fit['reference_height_cm']-15*scale for v in rim):
        raise RuntimeError('Source Body has unexpected non-chest openings')
    centroids=[[sum(positions[v][a] for v in tri)/3 for a in range(3)] for tri in triangles]
    retained=[i for i,p in enumerate(centroids) if bottom-.5*scale<=p[2]<=top and abs(p[0])<23*scale]
    if not 100<len(retained)<12000 or len(retained)>len(triangles)*.4:
        raise RuntimeError('Unexpected owned Face chest/neck coverage: '+str(len(retained)))
    kept=set(retained); removed=[i for i in range(len(triangles)) if i not in kept]
    vertices=sorted({v for i in retained for v in triangles[i]})
    edges=Counter(tuple(sorted((a,b))) for i in retained for a,b in zip(triangles[i],triangles[i][1:]+triangles[i][:1]))
    boundary={v for edge,count in edges.items() if count==1 for v in edge}
    fitted=[list(p) for p in positions]
    seam={}
    for v in vertices:
        p=positions[v]
        fitted[v]=[p[a]+normals[v][a]*1.65*scale for a in range(3)]
        if v not in boundary: continue
        nearest=min(rim,key=lambda b:dot(subtract(p,body_positions[b]),subtract(p,body_positions[b])))
        distance=math.sqrt(dot(subtract(p,body_positions[nearest]),subtract(p,body_positions[nearest])))
        if distance<.25*scale:
            seam[v]=nearest
            # Overlap by 8 mm into the existing jacket so independently
            # skinned seam vertices cannot expose a fine chest crack.
            fitted[v]=list(fitted_body[nearest]); fitted[v][2]-=.8*scale
        elif p[2]>top-2*scale:
            fitted[v][2]=top
        else:
            raise RuntimeError('Neck band has an unmatched low boundary at '+str(p))
    matched={v for v in seam.values()}
    if len(matched)<len(rim)*.9:
        raise RuntimeError('Owned Face/Body chest rims do not match: '+str((len(matched),len(rim))))
    return fitted,removed,vertices,{'source_chest_rim_vertices':len(rim),'matched_chest_rim_vertices':len(matched),
        'triangles':len(retained),'vertices':len(vertices),'collar_top_cm':top,'lower_overlap_cm':.8*scale,
        'body_weight_transfer':'closest_source_body_surface','original_face_modified':False}


def boot_buffers(positions, fit):
    """Original closed boot shells fitted around each source foot and lower leg.

    Rings have a continuous toe box, a flat sole and a tall shaft; unlike the
    body surface they never contain individual toe shapes. The original body
    is only a fitting/weight-transfer source and is not exported as a boot.
    """
    scale, top = fit['scale'], fit['boot_top_cm']
    vertices, triangles, uvs, material_ids = [], [], [], []
    count = 32
    for side in (-1,1):
        foot = [p for p in positions if p[0]*side > 0 and p[2] < 9*scale]
        if not foot: raise RuntimeError('Could not find both reference feet')
        mean=[sum(p[a] for p in foot)/len(foot) for a in range(2)]
        xx=sum((p[0]-mean[0])**2 for p in foot); yy=sum((p[1]-mean[1])**2 for p in foot)
        xy=sum((p[0]-mean[0])*(p[1]-mean[1]) for p in foot)
        angle=.5*math.atan2(2*xy,xx-yy)
        forward=[math.cos(angle),math.sin(angle)]
        if forward[1]<0: forward=[-v for v in forward]
        lateral=[forward[1],-forward[0]]
        def local(p): return (dot(subtract(p[:2],mean),lateral),dot(subtract(p[:2],mean),forward))
        def world(u,v): return [mean[a]+u*lateral[a]+v*forward[a] for a in range(2)]
        foot_center=mean
        floor = min(p[2] for p in foot)-.45*scale
        heights = [floor, floor+.85*scale, 2.6*scale, 4.2*scale, 6.6*scale, 9*scale,
                   12*scale, 17*scale, 23*scale,29*scale,top-1.2*scale,top-.55*scale,top]
        offset = len(vertices)
        for ring,z in enumerate(heights):
            # Follow the measured foot orientation and each actual height
            # section. R1 extruded the whole footprint to 6 cm, inflating toes.
            section=foot if ring<=1 else [p for p in positions if p[0]*side>0 and abs(p[2]-z)<1.25*scale]
            if not section: raise RuntimeError('Missing source lower-leg cross section')
            points=[local(p) for p in section]
            low=[min(p[a] for p in points) for a in range(2)]
            high=[max(p[a] for p in points) for a in range(2)]
            cx,cy=[(a+b)*.5 for a,b in zip(low,high)]
            margin=(.55 if z<12*scale else .8)*scale
            if ring>=len(heights)-2: margin+=.2*scale
            rx,ry=[(b-a)*.5+margin for a,b in zip(low,high)]
            exponent=.68 if z<7*scale else .90
            power=2/exponent
            enclosure=max(((abs((u-cx)/rx)**power+abs((v-cy)/ry)**power)**(1/power) for u,v in points),default=1.)
            rx*=max(1.,enclosure)*1.015; ry*=max(1.,enclosure)*1.015
            for j in range(count):
                angle=2*math.pi*j/count
                a,b=math.cos(angle),math.sin(angle)
                px,py=world(cx+rx*math.copysign(abs(a)**exponent,a),cy+ry*math.copysign(abs(b)**exponent,b))
                vertices.append([px,py,z])
                uvs.append([j/count,ring/(len(heights)-1)])
        for ring in range(len(heights)-1):
            material=4 if ring==0 else (3 if ring==len(heights)-2 else 2)
            for j in range(count):
                a=offset+ring*count+j; b=offset+ring*count+(j+1)%count
                c=b+count; d=a+count
                triangles.extend(([a,b,c],[a,c,d])); material_ids.extend((material,material))
        # Closed bottom, open top fits around the trousers. UVs/normals are
        # authored for new vertices; source cloth attributes remain unchanged.
        center=len(vertices); vertices.append([foot_center[0],foot_center[1],floor]); uvs.append([.5,0])
        for j in range(count):
            triangles.append([center,offset+(j+1)%count,offset+j]); material_ids.append(4)
    return vertices,triangles,uvs,material_ids


def weight_sample(ue, mesh, vertex):
    _,weights,valid = ue.GeometryScript_BoneWeights.get_vertex_bone_weights(mesh,vertex)
    if not valid or not weights: raise RuntimeError('Missing source skin weights at '+str(vertex))
    return [(int(w.bone_index),round(float(w.weight),7)) for w in weights]


def make_material(ue, directory, name, color, roughness, metallic=0., fit=None, palette=None):
    lib=ue.MaterialEditingLibrary
    mat=ue.AssetToolsHelpers.get_asset_tools().create_asset(name,directory,ue.Material,ue.MaterialFactoryNew())
    if mat is None: raise RuntimeError('Could not create '+name)
    ue.EditorAssetLibrary.set_metadata_tag(mat,'BB.Generator',OWNER)
    mat.set_editor_property('used_with_skeletal_mesh',True)
    mat.set_editor_property('two_sided',True)
    def node(cls, **props):
        obj=lib.create_material_expression(mat,cls,-500,0)
        for key,value in props.items(): obj.set_editor_property(key,value)
        return obj
    def wire(a,b,pin=''):
        if not lib.connect_material_expressions(a,'',b,pin): raise RuntimeError('Material connection failed')
    def mul(a,b=None,value=1.):
        out=node(ue.MaterialExpressionMultiply,const_b=value); wire(a,out,'A')
        if b is not None: wire(b,out,'B')
        return out
    def add(a,b=None,value=0.):
        out=node(ue.MaterialExpressionAdd,const_b=value); wire(a,out,'A')
        if b is not None: wire(b,out,'B')
        return out
    def mask(a,axis):
        out=node(ue.MaterialExpressionComponentMask,r=axis==0,g=axis==1,b=axis==2,a=False); wire(a,out); return out
    def invert(a):
        out=node(ue.MaterialExpressionOneMinus); wire(a,out); return out
    def ramp(a,start,end):
        out=node(ue.MaterialExpressionClamp,min_default=0.,max_default=1.)
        wire(mul(add(a,value=-start),value=1/(end-start)),out); return out
    def band(a,low,high,feather):
        return mul(ramp(a,low-feather,low),invert(ramp(a,high,high+feather)))
    def lerp(a,b,alpha):
        out=node(ue.MaterialExpressionLinearInterpolate); wire(a,out,'A'); wire(b,out,'B'); wire(alpha,out,'Alpha'); return out
    def constant(value): return node(ue.MaterialExpressionConstant,r=value)
    def color_parameter(parameter,value):
        return node(ue.MaterialExpressionVectorParameter,parameter_name=parameter,default_value=ue.LinearColor(*srgb(value),1))
    base=node(ue.MaterialExpressionVectorParameter,parameter_name='Color',default_value=ue.LinearColor(*srgb(color),1))
    roughness_node=constant(roughness)
    if fit is not None:
        scale,waist,collar=fit['scale'],fit['waist_cm'],fit['collar_cm']
        position=node(ue.MaterialExpressionLocalPosition,local_origin=ue.LocalPositionOrigin.INSTANCE_PRE_SKINNING,
                      included_offsets=ue.PositionIncludedOffsets.EXCLUDE_OFFSETS)
        interpolated=node(ue.MaterialExpressionVertexInterpolator); wire(position,interpolated)
        x=node(ue.MaterialExpressionAbs); wire(mask(interpolated,0),x)
        y,z=mask(interpolated,1),mask(interpolated,2)
        dark=color_parameter('Contrast Color',palette['contrast_srgb'])
        trim=color_parameter('Trim Color',palette['trim_srgb'])
        leather=color_parameter('Leather Color','29251F')
        base=lerp(dark,base,ramp(z,waist,waist+.45*scale))
        torso=band(z,waist+3*scale,collar-3*scale,.4*scale)
        side=mul(torso,band(x,14*scale,21*scale,.7*scale))
        base=lerp(base,dark,side)
        # Smooth, reference-space bands follow bending cloth. The material is
        # wholly confined to the garment, never applied to natural skin.
        belt=band(z,waist-1.2*scale,waist+1.2*scale,.15*scale)
        collar_mask=ramp(z,collar-2.0*scale,collar-1.8*scale)
        cuff_masks=[]; cuff_trim=[]
        arms=ramp(x,fit['arm_start_cm'],fit['arm_start_cm']+.5*scale)
        for wrist in fit['wrists']:
            center=node(ue.MaterialExpressionConstant3Vector,constant=ue.LinearColor(*[-p for p in wrist['center']],1))
            direction=node(ue.MaterialExpressionConstant3Vector,constant=ue.LinearColor(*wrist['direction'],1))
            distance=node(ue.MaterialExpressionDotProduct); wire(add(interpolated,center),distance,'A'); wire(direction,distance,'B')
            # Select only the matching side and arm. Opposite wrist planes
            # must not create stripes on the torso or trousers.
            signed_x=mul(mask(interpolated,0),value=1. if wrist['center'][0]>0 else -1.)
            side_arm=mul(arms,ramp(signed_x,fit['arm_start_cm'],fit['arm_start_cm']+.5*scale))
            cuff_masks.append(mul(side_arm,ramp(distance,-6.8*scale,-6.5*scale)))
            cuff_trim.append(mul(side_arm,band(distance,-2.3*scale,-1.95*scale,.1*scale)))
        contact=node(ue.MaterialExpressionClamp,min_default=0.,max_default=1.)
        wire(add(add(belt,collar_mask),add(cuff_masks[0],cuff_masks[1])),contact)
        base=lerp(base,leather,contact)
        front=ramp(y,0.,.8*scale)
        placket=mul(mul(band(x,0.,.25*scale,.1*scale),torso),front)
        chest=mul(band(z,waist+24*scale,waist+24.38*scale,.12*scale),invert(ramp(x,23*scale,25*scale)))
        piping=node(ue.MaterialExpressionClamp,min_default=0.,max_default=1.)
        wire(add(add(placket,chest),add(cuff_trim[0],cuff_trim[1])),piping)
        base=lerp(base,trim,piping)
        roughness_node=lerp(constant(.84),constant(.68),contact)
    # Body UVs are retained, and the cloth micro-weave follows those UVs while
    # animated. It never projects world-space patterns onto skin or garments.
    if roughness>.7:
        uv=node(ue.MaterialExpressionTextureCoordinate,u_tiling=160.,v_tiling=160.)
        channels=[]
        for axis in range(2):
            mask=node(ue.MaterialExpressionComponentMask,r=axis==0,g=axis==1,b=False,a=False); wire(uv,mask)
            wave=node(ue.MaterialExpressionSine,period=1.); wire(mask,wave); channels.append(wave)
        weave=node(ue.MaterialExpressionMultiply); wire(channels[0],weave,'A'); wire(channels[1],weave,'B')
        amount=node(ue.MaterialExpressionMultiply,const_b=.025); wire(weave,amount,'A')
        brightness=node(ue.MaterialExpressionAdd,const_b=.975); wire(amount,brightness,'A')
        shaded=node(ue.MaterialExpressionMultiply); wire(base,shaded,'A'); wire(brightness,shaded,'B'); base=shaded
    for expr,prop in ((base,ue.MaterialProperty.MP_BASE_COLOR),
            (roughness_node,ue.MaterialProperty.MP_ROUGHNESS),
            (node(ue.MaterialExpressionConstant,r=metallic),ue.MaterialProperty.MP_METALLIC)):
        if not lib.connect_material_property(expr,'',prop): raise RuntimeError('Material output connection failed')
    errors=list(lib.recompile_material(mat))
    if errors: raise RuntimeError('Flightwear shader compile errors: '+str(errors))
    return mat


def run(operation='inspect', name='BB_AthleteA', revision='r3'):
    import unreal as ue
    if operation not in ('inspect','build','api'): raise ValueError('Choose inspect, build, or api')
    character,subsystem=builder.validate(ue,name)
    builder.require_clean(ue)
    if operation=='api': return probe.docs(ue)
    active=getattr(ue,builder.KEY,None)
    if active and not active.finished: raise RuntimeError('Wait for retained cloud work')
    if subsystem.is_object_added_for_editing(character): raise RuntimeError('Close the owned design window first')
    lib=ue.EditorAssetLibrary
    if revision not in ('r2','r3'): raise ValueError('Choose revision r2 or r3; existing outputs remain preserved')
    directory=DESTINATION+'/'+name+'/'+revision
    if lib.list_assets(directory,recursive=True,include_folder=False):
        raise RuntimeError('Preserve existing flightwear; staging only creates a new owned output')
    blueprint=lib.load_asset(builder.ASSEMBLED+'/'+name+'/BP_'+name)
    if blueprint is None or lib.get_metadata_tag(blueprint,'BB.Generator') != builder.ASSEMBLY_OWNER:
        raise RuntimeError('Expected the owned saved assembly')
    assembled=lib.load_asset(builder.ASSEMBLED+'/'+name+'/Body/SKM_'+name+'_BodyMesh')
    source_skeleton=assembled.get_editor_property('skeleton')
    if not source_skeleton.get_path_name().startswith(builder.ASSEMBLED+'/Common/'):
        raise RuntimeError('Expected owned assembled skeleton')
    attempt=design.LAB/'flightwear-receipts'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8])
    attempt.mkdir(parents=True,exist_ok=False)
    report={'owner':OWNER,'character':name,'revision':revision,'operation':operation,'status':'fitting','report':str(attempt/'result.json'),
            'destination':directory,'original_skin_modified':False,'original_assemblies_modified':False,
            'game_integrated':False,'cloud_requests_made':False,'assets_saved':False}
    design.write(attempt/'result.json',report)
    before=design.file_tree(design.LAB/'Content',design.ASSET_SUFFIXES)
    actor_system=ue.get_editor_subsystem(ue.EditorActorSubsystem)
    selected=list(actor_system.get_selected_level_actors())
    registered=False
    try:
        if not subsystem.try_add_object_to_edit(character): raise RuntimeError('Cannot open owned preview edit session')
        registered=True
        preview=subsystem.spawn_meta_human_actor(character=character,keep_transient=True)
        if preview is None: raise RuntimeError('Cannot spawn owned transient preview')
        body=next(c for c in preview.get_components_by_class(ue.SkeletalMeshComponent) if c.get_name()=='Body')
        source,info=probe.copy_geometry(ue,body.get_skeletal_mesh_asset())
        cloth,_=probe.copy_geometry(ue,body.get_skeletal_mesh_asset())
        positions,triangles=info['positions'],info['triangles']
        if info['uv_sets']<1 or len(triangles)<40000: raise RuntimeError('An intact, UV-mapped source body is required')
        if any(min(t)<0 for t in triangles): raise RuntimeError('Source triangle IDs must be dense')
        _,normal_list,valid,gaps=ue.GeometryScript_Normals.get_mesh_per_vertex_normals(source,True)
        if not valid or gaps: raise RuntimeError('Source normals must be valid and dense')
        normals=[xyz(v) for v in ue.GeometryScript_List.convert_vector_list_to_array(normal_list)]
        _,bone_info=ue.GeometryScript_BoneWeights.get_all_bones_info(source)
        bones={str(b.name):xyz(b.world_transform.translation) for b in bone_info}
        fitted,remove,material_ids,retained,fit=fit_cloth(positions,triangles,normals,bones,neck_band=revision=='r3')
        report.update(source_mesh=info['mesh'],source_triangles=len(triangles),source_uv_sets=info['uv_sets'],fit=fit,
                      source_skeleton=source_skeleton.get_path_name())
        samples=retained[::max(1,len(retained)//64)]
        weights_before={i:weight_sample(ue,cloth,i) for i in samples}
        edits=ue.GeometryScript_MeshEdits; lists=ue.GeometryScript_List
        edits.set_all_mesh_vertex_positions(cloth,lists.convert_array_to_vector_list([ue.Vector(*p) for p in fitted]))
        # Installed PythonizeName/CamelCaseBreakIterator splits IDs as I|Ds.
        ue.GeometryScript_Materials.set_all_triangle_material_i_ds(cloth,lists.convert_array_to_index_list(material_ids))
        _,deleted=edits.delete_triangles_from_mesh(cloth,lists.convert_array_to_index_list(remove))
        if deleted!=len(remove): raise RuntimeError('Cloth triangle crop was incomplete')
        if any(weight_sample(ue,cloth,i)!=weights_before[i] for i in samples): raise RuntimeError('Copied cloth weights changed')
        neck_triangles=0
        if revision=='r3':
            face=next(c for c in preview.get_components_by_class(ue.SkeletalMeshComponent) if c.get_name()=='Face')
            neck,neck_info=probe.copy_geometry(ue,face.get_skeletal_mesh_asset())
            _,neck_normal_list,valid,gaps=ue.GeometryScript_Normals.get_mesh_per_vertex_normals(neck,True)
            if not valid or gaps or neck_info['uv_sets']!=info['uv_sets']:
                raise RuntimeError('Owned Face fitting copy needs valid dense normals and matching UV channels')
            neck_normals=[xyz(v) for v in lists.convert_vector_list_to_array(neck_normal_list)]
            neck_fitted,neck_remove,neck_vertices,neck_fit=fit_neck_band(neck_info['positions'],neck_info['triangles'],
                neck_normals,positions,triangles,fitted,fit)
            edits.set_all_mesh_vertex_positions(neck,lists.convert_array_to_vector_list([ue.Vector(*p) for p in neck_fitted]))
            ue.GeometryScript_Materials.set_all_triangle_material_i_ds(neck,lists.convert_array_to_index_list([0]*len(neck_info['triangles'])))
            _,deleted=edits.delete_triangles_from_mesh(neck,lists.convert_array_to_index_list(neck_remove))
            if deleted!=len(neck_remove): raise RuntimeError('Neck band crop was incomplete')
            ue.GeometryScript_BoneWeights.transfer_bone_weights_from_mesh(source,neck)
            for i in neck_vertices: weight_sample(ue,neck,i)
            _,neck_bones=ue.GeometryScript_BoneWeights.get_all_bones_info(neck)
            if [str(b.name) for b in neck_bones]!=[str(b.name) for b in bone_info]:
                raise RuntimeError('Neck band retained facial skeleton bones after Body weight transfer')
            edits.append_mesh(cloth,neck,ue.Transform())
            neck_triangles=neck_fit['triangles']
            report['neck_band']=dict(neck_fit,source_mesh=neck_info['mesh'])
        verts,tris,uvs,mids=boot_buffers(positions,fit)
        boots=ue.DynamicMesh(); buffers=ue.GeometryScriptSimpleMeshBuffers()
        buffers.vertices=[ue.Vector(*p) for p in verts]
        buffers.triangles=[ue.IntVector(*p) for p in tris]
        buffers.uv0=[ue.Vector2D(*p) for p in uvs]
        buffers.normals=[ue.Vector(0,0,1) for _ in verts]
        _,added=edits.append_buffers_to_mesh(boots,buffers)
        actual=list(lists.convert_index_list_to_array(added))
        if len(actual)!=len(tris) or any(i<0 for i in actual): raise RuntimeError('Boot mesh authoring failed')
        ue.GeometryScript_Materials.set_all_triangle_material_i_ds(boots,lists.convert_array_to_index_list(mids))
        ue.GeometryScript_BoneWeights.transfer_bone_weights_from_mesh(source,boots)
        for i in range(len(verts)): weight_sample(ue,boots,i)
        edits.append_mesh(cloth,boots,ue.Transform())
        ue.GeometryScript_Normals.recompute_normals(cloth,ue.GeometryScriptCalculateNormalsOptions())
        if ue.GeometryScript_MeshQueries.get_num_uv_sets(cloth)!=info['uv_sets']:
            raise RuntimeError('UV channel count changed while combining fitted outfit')
        if any(weight_sample(ue,cloth,i)!=weights_before[i] for i in samples): raise RuntimeError('Cloth skin weights changed during append')
        report.update(boot_vertices=len(verts),boot_triangles=len(tris),source_weight_samples_preserved=len(samples),
                      fitted_vertices=ue.GeometryScript_MeshQueries.get_vertex_count(cloth),
                      fitted_triangles=fit['cloth_triangles']+neck_triangles+len(tris),status='fitted_transient_pending_render')
        # Close the exact edit registration before asset creation. Removing the
        # subsystem's preview does not touch the separately copied DynamicMeshes.
        subsystem.remove_object_to_edit(character); registered=False
        builder.require_clean(ue)
        if operation=='inspect': return report
        skeleton_path=directory+'/SKEL_'+name+'_Flightwear'
        skeleton=lib.duplicate_asset(source_skeleton.get_path_name(),skeleton_path)
        if skeleton is None or skeleton==source_skeleton: raise RuntimeError('Dedicated skeleton duplication failed')
        lib.set_metadata_tag(skeleton,'BB.Generator',OWNER)
        lib.set_metadata_tag(skeleton,'BB.SourceSkeleton',source_skeleton.get_path_name())
        recipe=json.loads((design.ROOT/'SourceArt/Characters/player_uniforms.json').read_text(encoding='utf-8'))
        materials={}; authored=[skeleton]
        for team in ('Teal','Copper'):
            colors=recipe['teams'][team]
            specs=[(colors['color_srgb'],.84,0.),(colors['contrast_srgb'],.86,0.),('29251F',.68,0.),
                   (colors['trim_srgb'],.60,.10),('151513',.9,0.)]
            materials[team]=[]
            for slot,(color,rough,metal) in zip(SLOTS,specs):
                material=make_material(ue,directory,'M_'+name+'_'+team+'_'+slot,color,rough,metal,
                                       fit=fit if slot=='TeamCloth' else None,palette=colors)
                materials[team].append(material); authored.append(material)
        options=ue.GeometryScriptCreateNewSkeletalMeshAssetOptions()
        options.use_mesh_bone_proportions=True
        options.enable_recompute_normals=True; options.enable_recompute_tangents=True
        options.materials={slot:material for slot,material in zip(SLOTS,materials['Teal'])}
        mesh_path=directory+'/SKM_'+name+'_Flightwear'
        mesh,outcome=ue.GeometryScript_NewAssetUtils.create_new_skeletal_mesh_asset_from_mesh(cloth,skeleton,mesh_path,options)
        if outcome!=ue.GeometryScriptOutcomePins.SUCCESS or not isinstance(mesh,ue.SkeletalMesh):
            raise RuntimeError('Outfit export failed')
        if mesh.get_editor_property('skeleton')!=skeleton: raise RuntimeError('Export ignored dedicated skeleton')
        slots=[str(m.material_slot_name) for m in mesh.get_editor_property('materials')]
        if slots!=list(SLOTS): raise RuntimeError('Export material order changed: '+str(slots))
        lib.set_metadata_tag(mesh,'BB.Generator',OWNER)
        lib.set_metadata_tag(mesh,'BB.Revision',revision)
        lib.set_metadata_tag(mesh,'BB.SourceDesign',character.get_path_name())
        authored.append(mesh)
        dirty=[p.get_path_name() for p in list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages())+
               list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())]
        if any(not p.startswith(directory+'/') for p in dirty):
            raise RuntimeError('Unexpected dirty packages; preserved for inspection: '+str(dirty))
        if not lib.save_loaded_assets(authored,only_if_is_dirty=True): raise RuntimeError('Could not save exact flightwear output')
        report.update(status='authored_pending_visual_review',assets_saved=True,mesh=mesh.get_path_name(),skeleton=skeleton.get_path_name(),
                      material_slots=list(SLOTS),team_materials={team:[m.get_path_name() for m in mats] for team,mats in materials.items()},
                      saved_assets=[a.get_path_name() for a in authored],
                      preview_binding={'component':'SkeletalMesh','leader':'Body','replace_mesh':mesh.get_path_name()},
                      scope=revision.upper()+' full-length flightwear with original boot shells'+(' and a fitted standing collar.' if revision=='r3' else '.')+' One LOD; visual and deformation review required.')
        design.write(design.LAB/('flightwear-'+name+'-'+revision+'.json'),report)
        design.write(design.LAB/('flightwear-'+name+'.json'),report)
    except Exception:
        report.update(status='failed',error=traceback.format_exc()); raise
    finally:
        if registered and subsystem.is_object_added_for_editing(character): subsystem.remove_object_to_edit(character)
        actor_system.set_selected_level_actors(selected)
        after=design.file_tree(design.LAB/'Content',design.ASSET_SUFFIXES)
        report['existing_asset_bytes_preserved']=all(after.get(p)==digest for p,digest in before.items())
        report['dirty_after']=[p.get_path_name() for p in list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages())+
                               list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())]
        design.write(attempt/'result.json',report)
        if report.get('assets_saved'):
            design.write(design.LAB/('flightwear-'+name+'-'+revision+'.json'),report)
            design.write(design.LAB/('flightwear-'+name+'.json'),report)
    return report


if __name__=='__main__':
    args=globals().get('BRIDGE_ARGS',{})
    RESULT=run(args.get('operation','inspect'),args.get('character','BB_AthleteA'),args.get('revision','r3'))

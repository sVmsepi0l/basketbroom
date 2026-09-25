"""Author original woven uniform shaders on existing UE5 rider material paths.

Default is read-only preflight. Explicit {"dry_run": false} saves one owned
material, four existing owned instances, and two existing team accent tints.
No maps, skeletons, meshes, animations, native HL assets, or gameplay are edited.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / 'DevelopmentHarness/Plugins/Basketbroom/Content'
DIRECTORY = '/Basketbroom/Art/Characters'
PARENT = DIRECTORY + '/M_BB_WovenFlightUniform'
GENERATOR = 'Basketbroom.PlayerUniform.v1'
PREVIOUS = 'Basketbroom.SeatedFlight.v1'
RECIPE = ROOT / 'SourceArt/Characters/player_uniforms.json'


def srgb(hex_color):
    values = [int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def outputs():
    return [PARENT] + [DIRECTORY + '/MI_BB_Quinn_' + team + '_0' + str(index)
        for team in ('Teal', 'Copper') for index in (1, 2)] + [
        '/Basketbroom/Art/Materials/M_BB_Rider' + team for team in ('Teal', 'Copper')]


def package_file(path):
    return CONTENT / (path.removeprefix('/Basketbroom/') + '.uasset')


def build_graph(ue, mat, recipe, source):
    lib = ue.MaterialEditingLibrary
    lib.delete_all_material_expressions(mat)
    mat.set_editor_property('used_with_skeletal_mesh', True)
    mat.set_editor_property('shading_model', ue.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property('two_sided', False)
    count = 0

    def node(cls, **properties):
        nonlocal count
        count += 1
        value = lib.create_material_expression(mat, cls, -2400 + (count % 12)*180, (count//12)*170)
        for key, item in properties.items():
            value.set_editor_property(key, item)
        return value

    def wire(a, b, pin='', output=''):
        if not lib.connect_material_expressions(a, output, b, pin):
            raise RuntimeError('Uniform shader connection failed: ' + pin + ' into ' + b.get_class().get_name())

    def constant(value):
        return node(ue.MaterialExpressionConstant, r=value)

    def vector(name, color):
        return node(ue.MaterialExpressionVectorParameter, parameter_name=name,
                    default_value=ue.LinearColor(*srgb(color), 1))

    def mul(a, b=None, value=1):
        result = node(ue.MaterialExpressionMultiply, const_b=value)
        wire(a, result, 'A')
        if b is not None: wire(b, result, 'B')
        return result

    def add(a, b=None, value=0):
        result = node(ue.MaterialExpressionAdd, const_b=value)
        wire(a, result, 'A')
        if b is not None: wire(b, result, 'B')
        return result

    def clamp(a):
        result = node(ue.MaterialExpressionClamp, min_default=0., max_default=1.)
        wire(a, result)
        return result

    def invert(a):
        result = node(ue.MaterialExpressionOneMinus)
        wire(a, result)
        return result

    def mask(a, axis):
        result = node(ue.MaterialExpressionComponentMask, r=axis==0, g=axis==1, b=axis==2, a=False)
        wire(a, result)
        return result

    def lerp(a, b, alpha):
        result = node(ue.MaterialExpressionLinearInterpolate)
        wire(a, result, 'A'); wire(b, result, 'B'); wire(alpha, result, 'Alpha')
        return result

    def ramp(a, start, end):
        return clamp(mul(add(a, value=-start), value=1/(end-start)))

    def band(a, low, high, feather=.8):
        return mul(ramp(a, low-feather, low), invert(ramp(a, high, high+feather)))

    def sample(name, texture, sampler):
        return node(ue.MaterialExpressionTextureSampleParameter2D, parameter_name=name,
                    texture=texture, sampler_type=sampler)

    # Pre-skinned coordinates follow the garment during the flight animation.
    # World-space projections would slide when the riders move or bend.
    position = node(ue.MaterialExpressionLocalPosition,
                    local_origin=ue.LocalPositionOrigin.INSTANCE_PRE_SKINNING,
                    included_offsets=ue.PositionIncludedOffsets.EXCLUDE_OFFSETS)
    interpolated = node(ue.MaterialExpressionVertexInterpolator)
    wire(position, interpolated)
    z = mask(interpolated, 2)
    x = node(ue.MaterialExpressionAbs); wire(mask(interpolated, 0), x)
    team = vector('Team Color', recipe['teams']['Teal']['color_srgb'])
    dark = vector('Contrast Color', recipe['teams']['Teal']['contrast_srgb'])
    trim = vector('Trim Color', recipe['teams']['Teal']['trim_srgb'])
    leather = vector('Leather Color', '292923')

    # Tailoring on the installed 180 cm mesh: dark trousers, colored jersey,
    # contrast side panels, two clear chest bands and a small collar piping.
    jersey = ramp(z, 93, 97)
    color = lerp(mul(dark, value=1.35), team, jersey)
    side = mul(band(x, 15, 21), band(z, 101, 137))
    color = lerp(color, dark, side)
    chest = band(z, 125.2, 129.8, .35)
    piping = clamp(add(band(z, 123.2, 123.8, .2), band(z, 146.0, 147.0, .25)))
    color = lerp(color, dark, chest)
    color = lerp(color, trim, piping)
    # A cloth cap remains a mannequin cap; this pass makes no human face claim.
    cap = ramp(z, 155, 157)
    color = lerp(color, mul(dark, value=1.8), cap)
    cap_piping = band(z, 157.3, 158.0, .2)
    color = lerp(color, trim, cap_piping)
    # Leather boots, gloves and waistband, bounded in the reference body.
    contact = clamp(add(add(invert(ramp(z, 29, 33)), ramp(x, 43, 46)), band(z, 91, 95, .4)))
    color = lerp(color, leather, contact)

    uv = node(ue.MaterialExpressionTextureCoordinate)
    u = mul(mask(uv, 0), value=recipe['weave_cycles_per_uv'])
    v = mul(mask(uv, 1), value=recipe['weave_cycles_per_uv'])
    warp = node(ue.MaterialExpressionSine); wire(u, warp)
    weft = node(ue.MaterialExpressionSine); wire(v, weft)
    weave = mul(warp, weft)
    depth = node(ue.MaterialExpressionPixelDepth)
    fade = invert(ramp(depth, recipe['detail_fade_start_cm'], recipe['detail_fade_end_cm']))
    fabric = mul(invert(contact), invert(cap))
    detail = mul(fade, fabric)
    color = mul(color, add(mul(mul(weave, detail), value=.045), value=.9775))
    normal = sample('BNormal', source['BNormal'], ue.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    normal_flat = node(ue.MaterialExpressionConstant3Vector, constant=ue.LinearColor(0, 0, 1, 1))
    stock_normal = lerp(normal_flat, normal, constant(.68))
    xy = node(ue.MaterialExpressionAppendVector)
    wire(mul(mul(warp, detail), value=.035), xy, 'A')
    wire(mul(mul(weft, detail), value=.035), xy, 'B')
    micro = node(ue.MaterialExpressionAppendVector); wire(xy, micro, 'A'); wire(constant(0), micro, 'B')
    combined = node(ue.MaterialExpressionNormalize); wire(add(stock_normal, micro), combined)
    roughness = lerp(constant(recipe['fabric_roughness']), constant(recipe['leather_roughness']), contact)
    roughness = clamp(add(roughness, mul(mul(weave, detail), value=.025)))
    # The installed Quinn MRA textures use default compression with sRGB off,
    # so UE requires Linear Color rather than the Masks compression sampler.
    mra = sample('MRA', source['MRA'], ue.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    for expression, prop in (
        (color, ue.MaterialProperty.MP_BASE_COLOR), (combined, ue.MaterialProperty.MP_NORMAL),
        (roughness, ue.MaterialProperty.MP_ROUGHNESS), (constant(0), ue.MaterialProperty.MP_METALLIC),
        (mask(mra, 2), ue.MaterialProperty.MP_AMBIENT_OCCLUSION)):
        if not lib.connect_material_property(expression, '', prop):
            raise RuntimeError('Uniform material output connection failed: ' + str(prop))
    errors = list(lib.recompile_material(mat))
    if errors: raise RuntimeError('Uniform shader did not compile: ' + '; '.join(str(e) for e in errors))
    return count


def run(dry_run=True):
    import unreal as ue
    if type(dry_run) is not bool: raise ValueError('dry_run must be boolean')
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())).resolve()
    if project != (ROOT/'DevelopmentHarness').resolve() or not ue.SystemLibrary.get_engine_version().startswith('5.8.'):
        raise RuntimeError('Player uniform stage requires the UE5.8 Basketbroom harness')
    levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
    if levels.is_in_play_in_editor(): raise RuntimeError('Stop PIE before player uniform authoring')
    dirty = list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages()) + list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    if dirty: raise RuntimeError('Preserve existing unsaved work: ' + str([p.get_path_name() for p in dirty]))
    recipe = json.loads(RECIPE.read_text(encoding='utf-8'))
    if recipe.get('schema_version') != 1 or recipe.get('generator') != GENERATOR or set(recipe['teams']) != {'Teal', 'Copper'}:
        raise RuntimeError('Unexpected player uniform source recipe')
    assets, lib = ue.EditorAssetLibrary, ue.MaterialEditingLibrary
    if not hasattr(ue.LocalPositionOrigin, 'INSTANCE_PRE_SKINNING') or not hasattr(ue.PositionIncludedOffsets, 'EXCLUDE_OFFSETS'):
        raise RuntimeError('Required UE5.8 local-position authoring enum unavailable')
    loaded = {}
    for path in outputs():
        item = assets.load_asset(path) if assets.does_asset_exist(path) else None
        if path == PARENT:
            if item and (not isinstance(item, ue.Material) or assets.get_metadata_tag(item, 'BB.Generator') != GENERATOR):
                raise RuntimeError('Refusing an unrelated material at ' + path)
        elif '/MI_' in path:
            if not isinstance(item, ue.MaterialInstanceConstant) or assets.get_metadata_tag(item, 'BB.Generator') != PREVIOUS:
                raise RuntimeError('Expected existing owned team instance: ' + path)
        else:
            if not isinstance(item, ue.Material): raise RuntimeError('Missing original team accent material: ' + path)
            tint = [n for n in lib.get_material_expressions(item) if isinstance(n, ue.MaterialExpressionVectorParameter)
                    and str(n.get_editor_property('parameter_name')) == 'Tint']
            # The existing graph contains three same-name Tint nodes from its
            # older authoring passes, with the third connected to Base Color.
            # Preserve the graph and update their shared identity consistently.
            connected = lib.get_material_property_input_node(item, ue.MaterialProperty.MP_BASE_COLOR)
            if len(tint) != 3 or connected not in tint:
                raise RuntimeError('Unexpected original team tint graph: ' + path)
            values = [n.get_editor_property('default_value') for n in tint]
            if any(max(abs(a-b) for a,b in zip((v.r,v.g,v.b,v.a),(values[0].r,values[0].g,values[0].b,values[0].a))) > 1e-5 for v in values):
                raise RuntimeError('Existing shared Tint nodes disagree: ' + path)
        loaded[path] = item
    sources = {}
    for index in (1, 2):
        material = assets.load_asset('/Game/Characters/Mannequins/Materials/Quinn/MI_Quinn_0'+str(index))
        sources[index] = {name: lib.get_material_instance_texture_parameter_value(material, name) for name in ('BNormal', 'MRA')}
        if any(not isinstance(tex, ue.Texture2D) for tex in sources[index].values()):
            raise RuntimeError('Installed Quinn normal/AO textures unavailable')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '-' + uuid.uuid4().hex[:8]
    attempt = ROOT/'.local/player-uniform-stage'/stamp
    attempt.mkdir(parents=True, exist_ok=False)
    receipt = attempt/'result.json'
    before = {str(p.relative_to(CONTENT)): digest(p) for p in CONTENT.rglob('*') if p.is_file() and p.suffix in ('.uasset', '.umap')}
    report = {'status': 'preflight_passed', 'dry_run': dry_run, 'recipe_sha256': digest(RECIPE),
              'outputs': outputs(), 'backups': [], 'maps_saved': 0, 'mesh_animation_edits': 0,
              'palette_linear': {team: {key: list(srgb(value)) for key, value in data.items() if key.endswith('_srgb')}
                                 for team, data in recipe['teams'].items()},
              'render_review': 'not_run', 'runtime_review': 'not_run'}
    write(receipt, report)
    if dry_run: return {'status': report['status'], 'report': str(receipt)}
    try:
        for path in outputs():
            source = package_file(path)
            if source.is_file():
                backup = attempt/'backups'/source.relative_to(CONTENT)
                backup.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, backup)
                if digest(backup) != digest(source): raise RuntimeError('Uniform backup mismatch')
                report['backups'].append({'path': path, 'backup': str(backup), 'sha256': digest(backup)})
        write(receipt, report)
        parent = loaded[PARENT] or ue.AssetToolsHelpers.get_asset_tools().create_asset(
            PARENT.rsplit('/', 1)[1], DIRECTORY, ue.Material, ue.MaterialFactoryNew())
        assets.set_metadata_tag(parent, 'BB.Generator', GENERATOR)
        assets.set_metadata_tag(parent, 'BB.RecipeSHA256', digest(RECIPE))
        report['expression_count'] = build_graph(ue, parent, recipe, sources[1])
        if not assets.save_loaded_asset(parent, only_if_is_dirty=False): raise RuntimeError('Could not save uniform parent')
        for team, data in recipe['teams'].items():
            for index in (1, 2):
                path = DIRECTORY+'/MI_BB_Quinn_'+team+'_0'+str(index)
                instance = loaded[path]
                lib.set_material_instance_parent(instance, parent)
                for param, key in (('Team Color', 'color_srgb'), ('Contrast Color', 'contrast_srgb'), ('Trim Color', 'trim_srgb')):
                    expected = srgb(data[key])
                    lib.set_material_instance_vector_parameter_value(instance, param, ue.LinearColor(*expected, 1))
                    actual = lib.get_material_instance_vector_parameter_value(instance, param)
                    if max(abs(a-b) for a,b in zip((actual.r,actual.g,actual.b),expected)) > 1e-5:
                        raise RuntimeError('Uniform color did not persist: '+path+' '+param)
                for name, texture in sources[index].items():
                    lib.set_material_instance_texture_parameter_value(instance, name, texture)
                    if lib.get_material_instance_texture_parameter_value(instance, name) != texture:
                        raise RuntimeError('Uniform texture binding did not persist')
                assets.set_metadata_tag(instance, 'BB.UniformGenerator', GENERATOR)
                assets.set_metadata_tag(instance, 'BB.RecipeSHA256', digest(RECIPE))
                lib.update_material_instance(instance)
                if not assets.save_loaded_asset(instance, only_if_is_dirty=False): raise RuntimeError('Could not save '+path)
            accent = loaded['/Basketbroom/Art/Materials/M_BB_Rider'+team]
            tints = [n for n in lib.get_material_expressions(accent) if isinstance(n, ue.MaterialExpressionVectorParameter)
                     and str(n.get_editor_property('parameter_name')) == 'Tint']
            for tint in tints:
                tint.set_editor_property('default_value', ue.LinearColor(*srgb(data['color_srgb']), 1))
            assets.set_metadata_tag(accent, 'BB.UniformGenerator', GENERATOR)
            errors = list(lib.recompile_material(accent))
            if errors: raise RuntimeError('Team accent shader did not compile: ' + '; '.join(str(e) for e in errors))
            if not assets.save_loaded_asset(accent, only_if_is_dirty=False): raise RuntimeError('Could not save team accent')
        after = {str(p.relative_to(CONTENT)): digest(p) for p in CONTENT.rglob('*') if p.is_file() and p.suffix in ('.uasset', '.umap')}
        allowed = {str(package_file(path).relative_to(CONTENT)) for path in outputs()}
        changed = sorted(p for p in set(before)|set(after) if before.get(p) != after.get(p))
        if set(changed)-allowed: raise RuntimeError('Unexpected package changes: '+str(set(changed)-allowed))
        dirty = list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages()) + list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())
        if dirty: raise RuntimeError('Unexpected dirty package after isolated uniform stage: '+str([p.get_path_name() for p in dirty]))
        report.update(status='saved_pending_visual_review', changed_packages=changed,
                      package_sha256={p: after[p] for p in sorted(allowed)}, unrelated_packages_preserved=True)
        write(receipt, report)
        write(ROOT/'.local/player-uniform-success.json', {'report': str(receipt), 'recipe_sha256': digest(RECIPE)})
    except Exception:
        report.update(status='failed', error=traceback.format_exc())
        write(receipt, report)
        raise
    return {'status': report['status'], 'report': str(receipt), 'packages': len(report['changed_packages'])}


if __name__ == '__main__':
    args = globals().get('BRIDGE_ARGS', {})
    RESULT = run(args.get('dry_run', True))

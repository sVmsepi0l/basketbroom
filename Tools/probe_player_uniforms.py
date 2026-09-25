"""Read-only checks of saved uniform identity and per-slot texture bindings."""
from pathlib import Path
import importlib.util
import json


def run():
    import unreal as ue
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('_bb_uniform_author', root/'Tools/stage_player_uniforms.py')
    author = importlib.util.module_from_spec(spec); spec.loader.exec_module(author)
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())).resolve()
    if project != (root/'DevelopmentHarness').resolve() or not ue.SystemLibrary.get_engine_version().startswith('5.8.'):
        raise RuntimeError('Only UE5 Basketbroom uniform assets may be inspected')
    recipe = json.loads(author.RECIPE.read_text(encoding='utf-8'))
    lib, assets = ue.MaterialEditingLibrary, ue.EditorAssetLibrary
    parent = assets.load_asset(author.PARENT)
    parent_checks = {
        'owned_parent': bool(parent and assets.get_metadata_tag(parent, 'BB.Generator') == author.GENERATOR),
        'recipe_matches': bool(parent and assets.get_metadata_tag(parent, 'BB.RecipeSHA256') == author.digest(author.RECIPE)),
        'skeletal_shader_usage': bool(parent and parent.get_editor_property('used_with_skeletal_mesh')),
        'lit_material': bool(parent and parent.get_editor_property('shading_model') == ue.MaterialShadingModel.MSM_DEFAULT_LIT),
        'required_outputs_connected': bool(parent and all(lib.get_material_property_input_node(parent, prop) is not None for prop in (
            ue.MaterialProperty.MP_BASE_COLOR, ue.MaterialProperty.MP_NORMAL, ue.MaterialProperty.MP_ROUGHNESS,
            ue.MaterialProperty.MP_METALLIC, ue.MaterialProperty.MP_AMBIENT_OCCLUSION))),
    }
    rows = []
    for team, data in recipe['teams'].items():
        for index in (1, 2):
            path = author.DIRECTORY+'/MI_BB_Quinn_'+team+'_0'+str(index)
            material = assets.load_asset(path)
            checks = {'uniform_parent': material.get_editor_property('parent') == parent,
                      'owned_uniform': assets.get_metadata_tag(material, 'BB.UniformGenerator') == author.GENERATOR,
                      'recipe_matches': assets.get_metadata_tag(material, 'BB.RecipeSHA256') == author.digest(author.RECIPE)}
            for param, key in (('Team Color','color_srgb'),('Contrast Color','contrast_srgb'),('Trim Color','trim_srgb')):
                color = lib.get_material_instance_vector_parameter_value(material, param)
                checks[param] = max(abs(a-b) for a,b in zip((color.r,color.g,color.b), author.srgb(data[key]))) < 1e-5
            for param, suffix in (('BNormal','N'),('MRA','MRA')):
                texture = lib.get_material_instance_texture_parameter_value(material, param)
                expected = '/Game/Characters/Mannequins/Textures/Quinn/T_Quinn_0'+str(index)+'_'+suffix
                checks[param] = bool(texture and texture.get_path_name().split('.')[0] == expected)
            rows.append({'path':path,'checks':checks,'passed':all(checks.values())})
        path = '/Basketbroom/Art/Materials/M_BB_Rider'+team
        material = assets.load_asset(path)
        tints = [n for n in lib.get_material_expressions(material) if isinstance(n,ue.MaterialExpressionVectorParameter)
                 and str(n.get_editor_property('parameter_name')) == 'Tint']
        values = [n.get_editor_property('default_value') for n in tints]
        matches = len(values)==3 and all(max(abs(a-b) for a,b in zip((value.r,value.g,value.b),author.srgb(data['color_srgb']))) < 1e-5 for value in values)
        connected = lib.get_material_property_input_node(material, ue.MaterialProperty.MP_BASE_COLOR) in tints
        rows.append({'path':path,'checks':{'three_preserved_tint_nodes':len(tints)==3,'base_color_uses_tint':connected,
                                          'palette_matches':matches},'passed':matches and connected})
    report = {'status':'passed' if all(parent_checks.values()) and all(r['passed'] for r in rows) else 'failed',
              'parent_checks':parent_checks,'assets':rows,'asset_count':len(rows)+1,'mutations':0,
              'scope':'Material configuration and bindings only; actual rendered appearance is reviewed separately.'}
    output = root/'.local/player-uniform-inspection.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return {'status':report['status'],'report':str(output),'assets':report['asset_count']}


if __name__ == '__main__':
    RESULT = run()

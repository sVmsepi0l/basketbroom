"""Read-only UE5 stock rider material inventory for owned uniform authoring."""
from pathlib import Path
import json


def run():
    import unreal as ue
    root = Path(__file__).resolve().parents[1]
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())).resolve()
    if project != (root / 'DevelopmentHarness').resolve() or not ue.SystemLibrary.get_engine_version().startswith('5.8.'):
        raise RuntimeError('Only the UE5 Basketbroom harness may be inspected')
    lib = ue.MaterialEditingLibrary
    result = {'status': 'inspected', 'materials': [], 'mutations': 0}
    for index in (1, 2):
        path = '/Game/Characters/Mannequins/Materials/Quinn/MI_Quinn_0' + str(index)
        material = ue.EditorAssetLibrary.load_asset(path)
        row = {'path': path, 'parent': material.get_editor_property('parent').get_path_name()}
        row['textures'] = {str(name): str(lib.get_material_instance_texture_parameter_value(material, name).get_path_name())
                           for name in lib.get_texture_parameter_names(material)
                           if lib.get_material_instance_texture_parameter_value(material, name)}
        row['scalars'] = {str(name): lib.get_material_instance_scalar_parameter_value(material, name)
                          for name in lib.get_scalar_parameter_names(material)}
        row['vectors'] = {str(name): str(lib.get_material_instance_vector_parameter_value(material, name))
                          for name in lib.get_vector_parameter_names(material)}
        row['switches'] = {str(name): lib.get_material_instance_static_switch_parameter_value(material, name)
                           for name in lib.get_static_switch_parameter_names(material)}
        result['materials'].append(row)
    mesh = ue.EditorAssetLibrary.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple')
    result['mesh_bounds'] = str(mesh.get_bounds())
    result['preskinned_node'] = hasattr(ue, 'MaterialExpressionPreSkinnedPosition')
    result['preskinned_normal_node'] = hasattr(ue, 'MaterialExpressionPreSkinnedNormal')
    result['transform_position_node'] = hasattr(ue, 'MaterialExpressionTransformPosition')
    result['skin_cache_mode'] = ue.SystemLibrary.get_console_variable_int_value('r.SkinCache.Mode')
    result['skin_cache_compile_shaders'] = ue.SystemLibrary.get_console_variable_int_value('r.SkinCache.CompileShaders')
    result['raytracing'] = ue.SystemLibrary.get_console_variable_int_value('r.RayTracing')
    result['modern_position_enums'] = {'origin':[v for v in dir(ue.LocalPositionOrigin) if v.isupper()],
                                       'offsets':[v for v in dir(ue.PositionIncludedOffsets) if v.isupper()]}
    result['accent_graphs'] = []
    for team in ('Teal', 'Copper'):
        material = ue.EditorAssetLibrary.load_asset('/Basketbroom/Art/Materials/M_BB_Rider'+team)
        row = {'path':material.get_path_name(),'expressions':[], 'base_color_input':None}
        connected = lib.get_material_property_input_node(material, ue.MaterialProperty.MP_BASE_COLOR)
        row['base_color_input'] = connected.get_path_name() if connected else None
        for expression in lib.get_material_expressions(material):
            entry = {'path':expression.get_path_name(),'class':expression.get_class().get_name()}
            for key in ('parameter_name','default_value','constant','r','const_a','const_b'):
                try: entry[key] = str(expression.get_editor_property(key))
                except Exception: pass
            row['expressions'].append(entry)
        result['accent_graphs'].append(row)
    output = root / '.local/player-skin-source-probe.json'
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    ue.log('BASKETBROOM PLAYER SKIN SOURCE PROBE: ' + str(output))
    return result


if __name__ == '__main__':
    RESULT = run()

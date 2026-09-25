"""Create garment-only team materials using inspected assembled clothing slots."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OWNER = 'Basketbroom.HumanUniform.v1'


def linear(hex_value):
    values = [int(hex_value[i:i+2],16)/255 for i in (0,2,4)]
    return [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values]


def run(name, receipt):
    import unreal as ue
    lab = ROOT/'.local/CharacterLab'
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.get_project_file_path())).resolve()
    if project != (lab/'BasketbroomCharacterLab.uproject').resolve() or name not in ('BB_AthleteA','BB_AthleteB'):
        raise RuntimeError('Expected an owned character in the isolated lab')
    source = Path(receipt).resolve()
    source.relative_to((lab/'inspection-receipts').resolve())
    inspection = json.loads(source.read_text(encoding='utf-8'))
    if inspection['character']['path'] != '/Game/BasketbroomHumans/Design/'+name+'.'+name:
        raise RuntimeError('Inspection belongs to another character')
    components = inspection['transient_actor']['components']
    clothing = next(c for c in components if c['name'] == 'SkeletalMesh')
    body = next(c for c in components if c['name'] == 'Body')
    if clothing['skeleton'] != body['skeleton'] or not clothing['leader_pose_component'].get('path','').endswith('.Body'):
        raise RuntimeError('Unexpected garment pose relationship')
    lib, mats = ue.EditorAssetLibrary, ue.MaterialEditingLibrary
    mesh = lib.load_asset('/Game/BasketbroomHumans/Assembled/'+name+'/Clothing/'+name+'_Outfits')
    live_materials = mesh.get_editor_property('materials')
    expected_slots = clothing['material_slots']
    if [str(m.material_slot_name) for m in live_materials] != expected_slots:
        raise RuntimeError('Garment slots changed since inspection')
    dirty = list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    if dirty: raise RuntimeError('Save existing lab work before authoring uniforms')
    recipe = json.loads((ROOT/'SourceArt/Characters/player_uniforms.json').read_text(encoding='utf-8'))
    parents = {}
    for category in ('Shirt','Short'):
        candidates = sorted(set(m['path'] for m in clothing['materials'] if
            m['class'] == '/Script/Engine.MaterialInstanceConstant' and m['path'].split('.')[0].endswith('_'+category)))
        if len(candidates) != 1: raise RuntimeError('Expected exactly one inspected '+category+' source material')
        parents[category] = lib.load_asset(candidates[0])
    directory = '/Game/BasketbroomHumans/Uniforms/'+name
    authored, paths = [], {}
    for team, colors in recipe['teams'].items():
        for category, parent in parents.items():
            asset_name = 'MI_'+name+'_'+team+'_'+category
            asset_path = directory+'/'+asset_name
            if lib.does_asset_exist(asset_path): raise RuntimeError('Preserve existing uniform '+asset_path)
            material = ue.AssetToolsHelpers.get_asset_tools().create_asset(asset_name,directory,
                ue.MaterialInstanceConstant,ue.MaterialInstanceConstantFactoryNew())
            lib.set_metadata_tag(material,'BB.Generator',OWNER)
            mats.set_material_instance_parent(material,parent)
            primary = colors['color_srgb'] if category == 'Shirt' else colors['contrast_srgb']
            parameters = {'diffuse_color_1':primary,'diffuse_color_2':colors['trim_srgb'],
                          'B_diffuse_color_1':colors['contrast_srgb']}
            available = {str(n) for n in mats.get_vector_parameter_names(material)}
            for parameter, value in parameters.items():
                if parameter not in available: raise RuntimeError('Missing cloth parameter '+parameter)
                rgb = linear(value)
                mats.set_material_instance_vector_parameter_value(material,parameter,ue.LinearColor(*rgb,1))
                actual = mats.get_material_instance_vector_parameter_value(material,parameter)
                if max(abs(a-b) for a,b in zip((actual.r,actual.g,actual.b),rgb)) > 1e-5:
                    raise RuntimeError('Uniform color failed readback')
            mats.update_material_instance(material)
            paths[team,category] = asset_path
            authored.append(material)
    if not lib.save_loaded_assets(authored,only_if_is_dirty=True): raise RuntimeError('Could not save team garments')
    bindings = []
    for index,slot in enumerate(expected_slots):
        if 'shirt' in slot.lower(): category = 'Shirt'
        elif 'short' in slot.lower(): category = 'Short'
        else: raise RuntimeError('Unrecognized garment slot '+slot)
        bindings.append({'component':'SkeletalMesh','material_slot':slot,'material_slot_index':index,
                         'mint_material':paths['Teal',category],'copper_material':paths['Copper',category]})
    report = {'status':'authored_pending_render','character':name,'inspection':str(source),
              'garments':bindings,'materials':[m.get_path_name() for m in authored],
              'body_component':'Body','skin_modified':False,'geometry_modified':False,
              'clothing_scope':'Existing fitted shirt and shorts; custom long flightwear remains pending.'}
    (lab/('uniform-'+name+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__ == '__main__':
    args = globals().get('BRIDGE_ARGS',{})
    RESULT = run(args.get('character','BB_AthleteA'),args['inspection_receipt'])

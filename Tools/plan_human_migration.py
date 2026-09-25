"""Offline, read-only asset migration planning from saved CharacterLab receipts.

Does not import Unreal, copy assets, enable plugins, alter the game, or activate
appearance. Writes a local JSON plan, retaining unresolved dependencies as such.
Package names are preserved: /Game/... goes to DevelopmentHarness/Content/....
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct

ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'.local/CharacterLab'
TARGET=ROOT/'DevelopmentHarness/Content'
ASSEMBLED='/Game/BasketbroomHumans/Assembled/'
NAMES=('BB_AthleteA','BB_AthleteB')


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''): value.update(chunk)
    return value.hexdigest()


def contained(path, parent):
    resolved=path.resolve()
    resolved.relative_to(parent.resolve())
    return resolved


def package_flags(path, expected_package):
    """Read only the verified UE5.8 binary summary format; reject other versions.

    Installed PackageFileSummary.cpp writes the six prefix fields, 20-byte
    FIoHash, TotalHeaderSize, optimized custom versions (GUID + int32), FString
    PackageName, then PackageFlags. ObjectVersion.h: UE5 1018 includes SavedHash.
    ObjectMacros.h: PKG_EditorOnly = 0x40. This is not a cook compatibility test.
    """
    with path.open('rb') as stream: data=stream.read(65536)
    if len(data)<64: raise ValueError('Truncated package summary')
    prefix=struct.unpack_from('<Iiiiii',data)
    if prefix!=(0x9e2a83c1,-9,864,522,1018,0):
        raise ValueError('Unreviewed package summary version: '+str(prefix))
    header_size,count=struct.unpack_from('<ii',data,44)
    if not 0<=count<=2048 or not 64<header_size<=path.stat().st_size:
        raise ValueError('Invalid package summary bounds')
    offset=52+count*20
    length=struct.unpack_from('<i',data,offset)[0]; offset+=4
    if not 1<=abs(length)<=2048: raise ValueError('Invalid package-name length')
    size=abs(length)*(2 if length<0 else 1)
    raw=data[offset:offset+size]; offset+=size
    if len(raw)!=size or not raw.endswith(b'\x00'): raise ValueError('Invalid package-name terminator')
    name=raw.decode('utf-16le' if length<0 else 'utf-8').rstrip('\x00')
    if name!=expected_package: raise ValueError('Package-name mismatch: '+name)
    flags,name_count,name_offset=struct.unpack_from('<Iii',data,offset)
    if not 0<=name_count<=1000000 or not offset+12<=name_offset<=header_size:
        raise ValueError('Invalid name-map bounds after package flags')
    return {'flags':flags,'editor_only':bool(flags&0x40),'source':'verified UE5.8 on-disk FPackageFileSummary',
            'serialized_package_name':name,'header_size':header_size}


def choose_receipts():
    result={}
    for path in sorted((LAB/'inspection-receipts').glob('*/result.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('status')!='inspected_pending_render_and_runtime_validation': continue
        for name in NAMES:
            if data.get('blueprint')==ASSEMBLED+name+'/BP_'+name:
                result[name]=(path,data)
    return result


def dependency_requirements(external):
    # The precise /Script identities come from AssetRegistry, not guessed
    # plugin names. Resolve plugin ownership using installed descriptors.
    engine=Path(r'C:\Program Files\Epic Games\UE_5.8\Engine')
    modules={}; mounts={}
    for path in (engine/'Plugins').rglob('*.uplugin'):
        try: data=json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError,ValueError): continue
        descriptor={'plugin':path.stem,'descriptor':str(path),'enabled_by_default':data.get('EnabledByDefault')}
        if data.get('CanContainContent'): mounts[path.stem]=descriptor
        for module in data.get('Modules',[]):
            modules[module['Name']]={**descriptor,'module_type':module.get('Type')}
    requirements=[]
    for path,kinds in sorted(external.items()):
        root=path.split('/')[1]
        item={'package':path,'reference_kinds':sorted(kinds),'copy':False}
        if root=='Script':
            module=path.split('/')[2]
            item.update(modules.get(module,{}))
            item['resolution']='installed_plugin_module' if module in modules else 'engine_module_needs_cook_validation'
            if item.get('module_type') not in (None,'Runtime','RuntimeNoCommandlet','RuntimeAndProgram'):
                item['resolution']='editor_or_developer_module_reference_needs_cook_stripping_validation'
        elif root=='Engine':
            item['resolution']='engine_content_needs_cook_validation'
        elif root in mounts:
            item.update(mounts[root]); item['resolution']='installed_plugin_content_needs_target_enablement_and_cook_validation'
        else: item['resolution']='unresolved_external_mount'
        requirements.append(item)
    return requirements


def run(output=None):
    receipts=choose_receipts()
    plan={'schema_version':1,'status':'planning_only','assets_copied':0,'game_modified':False,
          'package_mapping':'Preserve /Game/ package names in DevelopmentHarness/Content; no binary string rewriting.',
          'source_project':str(LAB/'BasketbroomCharacterLab.uproject'),
          'target_project':str(ROOT/'DevelopmentHarness/BasketbroomDev.uproject'),
          'characters':{},'packages':[],'blockers':[],'next_inventory_roots':[]}
    all_rows={}; external={}
    for name in NAMES:
        if name not in receipts:
            plan['blockers'].append('Missing saved assembly dependency inventory for '+name)
            plan['next_inventory_roots'].append(ASSEMBLED+name+'/BP_'+name)
            continue
        source,data=receipts[name]; deps=data['dependencies']
        row={'receipt':str(source),'receipt_sha256':digest(source),'blueprint':deps['root'],
             'hard_packages':len(deps['local_hard_closure']),'soft_only_packages':len(deps['local_soft_only_closure']),
             'variant_input':{'actor_class':deps['root']+'.BP_'+name+'_C','body_component_name':'Body',
                              'flight_animation':None,'garments':[],
                              'relative_transform':'Must be derived from rendered saddle/hand/foot alignment; not assumed.'}}
        for entry in deps['local_packages']:
            package=entry['package']
            # Shared skeleton/face preview references can legitimately reach
            # the other owned assembly; both designs are in the requested set.
            allowed=package.startswith(tuple(ASSEMBLED+n+'/' for n in NAMES)+(ASSEMBLED+'Common/',))
            if not allowed: plan['blockers'].append('Dependency outside owned assembly roots: '+package)
            if package in all_rows:
                prior=all_rows[package]
                if prior['files']!=entry['files']: plan['blockers'].append('Conflicting shared dependency receipts: '+package)
                prior['required_by'].append(name)
                prior['reachability_by_character'][name]='hard' if package in deps['local_hard_closure'] else 'soft_only'
                if package in deps['local_hard_closure']: prior['reachability']='hard'
                continue
            all_rows[package]={**entry,'allowed_source_root':allowed,'required_by':[name],
                               'reachability_by_character':{name:'hard' if package in deps['local_hard_closure'] else 'soft_only'},
                               'reachability':'hard' if package in deps['local_hard_closure'] else 'soft_only'}
        for entry in deps['external_packages']:
            external.setdefault(entry['package'],set()).update(entry['reference_kinds'])
        flight_path=LAB/('flight-'+name+'.json')
        if flight_path.exists():
            flight=json.loads(flight_path.read_text(encoding='utf-8'))
            row['variant_input']['flight_animation']=flight.get('animation')
            if flight.get('animation'): plan['next_inventory_roots'].append(flight['animation'].split('.')[0])
        else: plan['blockers'].append('Missing saved fitted animation receipt for '+name)
        outfit_path=LAB/('flightwear-'+name+'.json')
        if outfit_path.exists():
            outfit=json.loads(outfit_path.read_text(encoding='utf-8'))
            if outfit.get('status')=='authored_pending_visual_review' and outfit.get('existing_asset_bytes_preserved'):
                row['flightwear_receipt']=str(outfit_path)
                row['flightwear_mesh']=outfit['mesh']
                plan['next_inventory_roots'].append(outfit['mesh'].split('.')[0])
                for index,slot in enumerate(outfit['material_slots']):
                    row['variant_input']['garments'].append({'component_name':'SkeletalMesh','material_slot_name':slot,
                        'material_slot_index':index,'teal_material':outfit['team_materials']['Teal'][index],
                        'copper_material':outfit['team_materials']['Copper'][index]})
                    for team in ('Teal','Copper'):
                        plan['next_inventory_roots'].append(outfit['team_materials'][team][index].split('.')[0])
            else: plan['blockers'].append('Flightwear receipt is not a completed preserved staging output for '+name)
        else: plan['blockers'].append('Flightwear has not been staged for '+name)
        plan['characters'][name]=row
    unknown=[]; stale=[]; missing=[]; collisions=[]
    for package,row in sorted(all_rows.items()):
        records=[]
        expected_base=contained(LAB/'Content'/package.removeprefix('/Game/'),LAB/'Content')
        for file in row['files']:
            source=contained(Path(file['path']),LAB/'Content')
            if source.with_suffix('')!=expected_base or source.suffix not in ('.uasset','.uexp','.ubulk','.uptnl','.umap'):
                raise RuntimeError('Receipt package/file mismatch: '+str(source))
            destination=contained(TARGET/source.relative_to(LAB/'Content'),TARGET)
            exists=source.is_file()
            current=digest(source) if exists else None
            if not exists: missing.append(str(source))
            elif current!=file['sha256']: stale.append(str(source))
            target_hash=digest(destination) if destination.is_file() else None
            if target_hash and target_hash!=current: collisions.append(str(destination))
            records.append({'source':str(source),'destination':str(destination),'recorded_sha256':file['sha256'],
                            'current_sha256':current,'source_matches_receipt':current==file['sha256'],
                            'target_state':'identical' if target_hash and target_hash==current else 'collision' if target_hash else 'absent',
                            'bytes':source.stat().st_size if exists else None})
        if not records: missing.append(package)
        headers=[Path(f['source']) for f in records if Path(f['source']).suffix in ('.uasset','.umap')]
        try:
            if len(headers)!=1: raise ValueError('Expected exactly one saved package header')
            row['on_disk_package_flags']=package_flags(headers[0],package)
            if row.get('editor_only') is not None and row['editor_only']!=row['on_disk_package_flags']['editor_only']:
                plan['blockers'].append('Receipt and on-disk package flags disagree: '+package)
            row['editor_only']=row['on_disk_package_flags']['editor_only']
        except (OSError,ValueError,struct.error) as exc:
            row['package_flags_error']=str(exc)
        if row.get('editor_only') is None: unknown.append(package)
        elif row['editor_only']: plan['blockers'].append('Editor-only local dependency: '+package)
        row['files']=records
        plan['packages'].append(row)
    plan['verification']={'unknown_editor_only_flags':unknown,'stale_source_files':stale,
                          'missing_source_files':missing,'target_collisions':collisions}
    for label,items in (('unknown package flags',unknown),('stale source files',stale),('missing source files',missing),('target collisions',collisions)):
        if items: plan['blockers'].append(str(len(items))+' '+label+' require resolution before an allowlist can be accepted')
    plan['external_requirements']=dependency_requirements(external)
    plan['next_inventory_roots']=sorted(set(plan['next_inventory_roots']))
    plan['blockers'].extend([
        'Create a NEW cosmetic actor variant with the accepted flightwear replacing the original clothing; preserve assembly outputs.',
        'Inventory the new cosmetic actor, fitted animations, and both team materials together; assembly receipts alone do not cover those assets.',
        'Resolve target plugin/module requirements and perform a target-editor load/compile followed by cook validation.',
        'Review fitted outfit, first-person hiding, remote animation, and full-roster performance before activating the optional variants.'
    ])
    plan['runtime_activation']={
        'existing_entry_point':'ABBRiderCharacter::ConfigureHumanCosmetics(const TArray<FBBHumanRiderVariant>&)',
        'existing_fallback':'An empty array, invalid contract or unavailable actor preserves the existing mannequin.',
        'proposed_configuration':'A UDataAsset containing variants, optionally loaded from an exact configured soft-object path. Include that asset in the cook with an explicit primary-asset label or packaging directory.',
        'appearance_identity':'Replicated AppearanceIdentity chooses the variant independently of TeamIndex; team changes update garment materials only.',
        'no_runtime_changes_made':True}
    plan['summary']={'characters_inventoried':len(plan['characters']),'candidate_packages':len(plan['packages']),
                     'candidate_bytes':sum(f['bytes'] or 0 for p in plan['packages'] for f in p['files']),
                     'external_requirements':len(plan['external_requirements']),'blockers':len(plan['blockers'])}
    destination=contained(Path(output) if output else LAB/'migration-plan.json',LAB)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    return {'plan':str(destination),**plan['summary'],'assets_copied':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    print(json.dumps(run(parser.parse_args().output),indent=2))

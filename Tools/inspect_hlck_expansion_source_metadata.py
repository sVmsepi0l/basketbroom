"""Read only native mesh metadata; no imports, saves, transforms or registration."""
import hashlib
import importlib.util
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

def module(name, relative):
    spec=importlib.util.spec_from_file_location(name, ROOT/relative)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value

def run():
    import unreal
    stage=module('_bb_expansion_metadata_stage','Tools/stage_hlck_arena_expansion.py')
    guard=module('_bb_expansion_metadata_guard','Tools/load_hlck_dungeon.py')
    importer=module('_bb_expansion_metadata_import','Mod/Tools/import_sources.py')
    guard.require_editor(unreal);guard.require_clean(unreal)
    plan=stage.build_plan()
    manifest=importer.validate_sources()
    changed={entry['destination']:entry for entry in plan['changed_meshes']}
    records=[]
    for entry in manifest['source_imports']:
        if entry['asset_type']!='StaticMesh':continue
        asset=unreal.EditorAssetLibrary.load_asset(entry['destination'])
        if not isinstance(asset,unreal.StaticMesh):raise RuntimeError('Expected native StaticMesh')
        importer._owned(unreal,asset)
        raw=(ROOT/entry['source']).read_bytes()
        lf=raw.replace(b'\r\n',b'\n')
        records.append({'destination':entry['destination'],'changed':entry['destination'] in changed,
            'native_source_sha256':unreal.EditorAssetLibrary.get_metadata_tag(asset,importer.META_HASH),
            'native_revision':unreal.EditorAssetLibrary.get_metadata_tag(asset,importer.META_REVISION),
            'planned_before_sha256':changed.get(entry['destination'],{}).get('sha256_before',entry['sha256']),
            'current_source_sha256':hashlib.sha256(raw).hexdigest(),
            'current_lf_sha256':hashlib.sha256(lf).hexdigest(),
            'current_crlf_sha256':hashlib.sha256(lf.replace(b'\n',b'\r\n')).hexdigest()})
    report={'status':'inspected','read_only':True,'inspected_utc':datetime.now(timezone.utc).isoformat(),'meshes':records}
    path=ROOT/'.local/hlck/arena-expansion-source-metadata.json';stage.write(path,report)
    return {'status':'inspected','mesh_count':len(records),'report':str(path)}

if __name__=='__main__':
    RESULT=run()

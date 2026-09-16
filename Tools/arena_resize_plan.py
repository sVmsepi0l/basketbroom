"""Immutable checkpoint-to-current anisotropic arena amendment plan.

This is separate from the historical +45% amendment. Source identities are
preserved, goal sets translate as units, and heights/sporting sizes stay fixed.
"""
from pathlib import Path
import importlib.util
import json
import math

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'SourceArt/Arena/arena_resize_baseline.json'

def module(name, relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

legacy=module('_bb_resize_recorder','Tools/arena_expansion_plan.py')
dim=module('_bb_resize_dimensions','Tools/arena_dimensions.py')
digest=legacy.digest

def build_plan():
    baseline=json.loads(BASELINE.read_text(encoding='utf-8'))
    if baseline['source_commit']!='0375ec5' or baseline['dimensions']!=dim.dimensions(dim.LINEAR_SCALE):
        raise ValueError('Resize baseline is not the immutable +45% checkpoint')
    old={r['label']:r for r in baseline['actors']};new={r['label']:r for r in legacy.source_actors()}
    if set(old)!=set(new) or len(old)!=905:raise ValueError('Resize must preserve all 905 authoring identities')
    actors=[]
    for label,a in old.items():
        b=new[label]
        if any(a[k]!=b[k] for k in ('class','tags','mesh','folder')):raise ValueError('Non-transform source change: '+label)
        entry={k:a[k] for k in ('label','class','tags','mesh','folder')}
        entry.update(old={k:a[k] for k in ('location','rotation','scale')},new={k:b[k] for k in ('location','rotation','scale')})
        entry['changed']=entry['old']!=entry['new'];actors.append(entry)
    meshes=[]
    for name,row in baseline['meshes'].items():
        now=digest(ROOT/row['source'])
        if now!=row['sha256']:
            meshes.append(dict(name=name,source=row['source'],destination='/Basketbroom/Art/Meshes/'+name,sha256_before=row['sha256'],sha256_after=now))
    plan=dict(schema_version=2,geometry_version=dim.GEOMETRY_VERSION,baseline_sha256=digest(BASELINE),
      source_commit=baseline['source_commit'],source_builder_sha256=digest(ROOT/'Tools/build_arena.py'),
      axis_multipliers=[2.,4./3.,1.],volume_ratio=8./3.,dimensions_before=baseline['dimensions'],dimensions_after=dim.dimensions(),
      actors=actors,actor_count=len(actors),changed_actor_count=sum(r['changed'] for r in actors),changed_meshes=meshes)
    return validate_plan(plan)

def validate_plan(plan):
    if plan.get('schema_version')!=2 or plan.get('geometry_version')!=dim.GEOMETRY_VERSION:raise ValueError('Wrong resize revision')
    before,after=plan['dimensions_before'],plan['dimensions_after']
    if before!=dim.dimensions(dim.LINEAR_SCALE) or after!=dim.dimensions():raise ValueError('Unexpected resize dimensions')
    if not math.isclose(after['half_x']/before['half_x'],2.) or not math.isclose(after['half_y']/before['half_y'],4./3.):raise ValueError('Wrong footprint ratio')
    if any(after[k]!=before[k] for k in ('eave','apex')):raise ValueError('Height must not change')
    if not math.isclose(after['half_x']-after['goal_x'],before['half_x']-before['goal_x'],abs_tol=1e-8):raise ValueError('Goal setback must not grow')
    allowed={'SM_BB_ReboundNet','SM_BB_PyramidNet','SM_BB_PyramidRibs','SM_BB_PyramidCopper','SM_BB_PyramidCollision',
             'SM_BB_StoneDetail','SM_BB_CopperDetail','SM_BB_IronDetail','SM_BB_TealSeats','SM_BB_CopperSeats'}
    if {r['name'] for r in plan['changed_meshes']}!=allowed:raise ValueError('Resize must change exactly the reviewed ten sources')
    for entry in plan['actors']:
        for phase in ('old','new'):
            for key in ('location','rotation','scale'):
                if len(entry[phase][key])!=3 or any(not math.isfinite(v) for v in entry[phase][key]):raise ValueError('Invalid transform')
        if 'BB.Goal' in entry['tags']:
            if entry['new']['location'][1:]!=entry['old']['location'][1:] or entry['new']['scale']!=entry['old']['scale']:raise ValueError('Sporting hoop geometry changed')
        if entry['class'].endswith('PlayerStart') and entry['old']!=entry['new']:raise ValueError('Native PlayerStart moved')
    return plan

if __name__=='__main__':
    p=build_plan();print(json.dumps({k:v for k,v in p.items() if k not in ('actors','changed_meshes')},indent=2))

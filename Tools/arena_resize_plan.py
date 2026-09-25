"""Immutable checkpoint-to-current arena amendment plans for both engines.

UE5 starts at the verified September 16 shape; the native Kit still starts at
the historical +45% checkpoint. Neither baseline may be silently recaptured.
Source identities, heights and sporting sizes are preserved.
"""
from pathlib import Path
import importlib.util
import json
import math

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'SourceArt/Arena/arena_resize_baseline_20260916.json'
LEGACY_BASELINE = ROOT / 'SourceArt/Arena/arena_resize_baseline.json'
BASELINES = {
    'standalone': (BASELINE, '409d22e', '7b8a5fdf314faddf04d2c7a42a1dc916383850cb32b742ae27a8e75eb1b04296'),
    'hlck': (LEGACY_BASELINE, '0375ec5', '849c2dcaed1e0c8f93f83fcd4922155a2ae1a477dd2d6a33b50281ba71d3e22a'),
}

def module(name, relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

legacy=module('_bb_resize_recorder','Tools/arena_expansion_plan.py')
dim=module('_bb_resize_dimensions','Tools/arena_dimensions.py')
digest=legacy.digest

def baseline_dimensions(engine='standalone'):
    if engine not in BASELINES:raise ValueError('Unknown arena resize engine')
    return dim.previous_dimensions() if engine=='standalone' else dim.dimensions(dim.LINEAR_SCALE)

def load_baseline(engine='standalone'):
    if engine not in BASELINES:raise ValueError('Unknown arena resize engine')
    path,commit,sha=BASELINES[engine]
    if digest(path)!=sha:raise ValueError('Immutable resize baseline hash differs: '+engine)
    baseline=json.loads(path.read_text(encoding='utf-8'))
    if baseline['source_commit']!=commit or baseline['dimensions']!=baseline_dimensions(engine):
        raise ValueError('Resize baseline is not the reviewed '+engine+' checkpoint')
    return baseline

def build_plan(engine='standalone'):
    baseline=load_baseline(engine)
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
    before,after=baseline['dimensions'],dim.dimensions()
    plan=dict(schema_version=2,geometry_version=dim.GEOMETRY_VERSION,engine=engine,
      baseline_source=BASELINES[engine][0].relative_to(ROOT).as_posix(),baseline_sha256=BASELINES[engine][2],
      source_commit=baseline['source_commit'],source_builder_sha256=digest(ROOT/'Tools/build_arena.py'),
      axis_multipliers=[after['half_x']/before['half_x'],after['half_y']/before['half_y'],1.],
      volume_ratio=dim.enclosed_volume_cm3(after)/dim.enclosed_volume_cm3(before),dimensions_before=before,dimensions_after=after,
      actors=actors,actor_count=len(actors),changed_actor_count=sum(r['changed'] for r in actors),changed_meshes=meshes)
    return validate_plan(plan)

def validate_plan(plan):
    if plan.get('schema_version')!=2 or plan.get('geometry_version')!=dim.GEOMETRY_VERSION:raise ValueError('Wrong resize revision')
    engine=plan.get('engine')
    baseline=load_baseline(engine)
    if (plan.get('baseline_source')!=BASELINES[engine][0].relative_to(ROOT).as_posix() or
        plan.get('baseline_sha256')!=BASELINES[engine][2] or plan.get('source_commit')!=baseline['source_commit']):
        raise ValueError('Unexpected resize baseline provenance')
    before,after=plan['dimensions_before'],plan['dimensions_after']
    if before!=baseline['dimensions'] or after!=dim.dimensions():raise ValueError('Unexpected resize dimensions')
    ratios=[after['half_x']/before['half_x'],after['half_y']/before['half_y'],1.]
    if plan.get('axis_multipliers')!=ratios:raise ValueError('Wrong footprint ratios')
    if not math.isclose(plan.get('volume_ratio',0),dim.enclosed_volume_cm3(after)/dim.enclosed_volume_cm3(before)):raise ValueError('Wrong volume ratio')
    if engine=='standalone' and (not math.isclose(ratios[0],math.sqrt(2)) or not math.isclose(ratios[1],math.sqrt(2))):raise ValueError('Floor area must double without changing its aspect ratio')
    if any(after[k]!=before[k] for k in ('eave','apex')):raise ValueError('Height must not change')
    if not math.isclose(after['half_x']-after['goal_x'],before['half_x']-before['goal_x'],abs_tol=1e-8):raise ValueError('Goal setback must not grow')
    allowed={'SM_BB_ReboundNet','SM_BB_PyramidNet','SM_BB_PyramidRibs','SM_BB_PyramidCopper','SM_BB_PyramidCollision',
             'SM_BB_StoneDetail','SM_BB_CopperDetail','SM_BB_IronDetail','SM_BB_TealSeats','SM_BB_CopperSeats'}
    if {r['name'] for r in plan['changed_meshes']}!=allowed:raise ValueError('Resize must change exactly the reviewed ten sources')
    originals={row['label']:row for row in baseline['actors']}
    if len(plan['actors'])!=905 or {row['label'] for row in plan['actors']}!=set(originals):raise ValueError('Resize actor identities differ')
    for entry in plan['actors']:
        original=originals[entry['label']]
        if any(entry[k]!=original[k] for k in ('class','tags','mesh','folder')) or entry['old']!={k:original[k] for k in ('location','rotation','scale')}:
            raise ValueError('Resize actor differs from immutable baseline')
        for phase in ('old','new'):
            for key in ('location','rotation','scale'):
                if len(entry[phase][key])!=3 or any(not math.isfinite(v) for v in entry[phase][key]):raise ValueError('Invalid transform')
        if 'BB.Goal' in entry['tags']:
            if entry['new']['location'][1:]!=entry['old']['location'][1:] or entry['new']['scale']!=entry['old']['scale']:raise ValueError('Sporting hoop geometry changed')
        if entry['class'].endswith('PlayerStart') and entry['old']!=entry['new']:raise ValueError('Native PlayerStart moved')
    return plan

if __name__=='__main__':
    p=build_plan();print(json.dumps({k:v for k,v in p.items() if k not in ('actors','changed_meshes')},indent=2))

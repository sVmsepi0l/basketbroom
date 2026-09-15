"""offline source-builder placement contract for the owned arena expansion.

the recorder never talks to an editor: a private imported geometry module uses
inert stand-ins solely to evaluate authored numeric placements. Native/UE5
stagers compare these records to real owned actors before changing transforms.
"""
from pathlib import path
import argparse
import hashlib
import importlib.util
import json
import types

root = Path(__file__).resolve().parents[1]
baseline = root / 'SourceArt/Arena/arena_expansion_baseline.json'
phases = ('floor', 'goals', 'net_and_crown', 'stands', 'architecture_detail', 'scenery', 'lighting', 'cameras')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Inert:
    def __getattr__(self, name):
        return self
    def __call__(self, *args, **kwargs):
        return self


class SourceActor(Inert):
    def __init__(self, record):
        self.record = record
    def set_actor_scale3d(self, vector):
        self.record['scale'] = list(vector)
    def set_actor_location(self, vector, *args):
        self.record['location'] = list(vector)
    def set_actor_rotation(self, vector, *args):
        self.record['rotation'] = list(vector)


class SourceSymbols(Inert):
    vector = staticmethod(lambda *values: tuple(values))
    rotator = staticmethod(lambda *values, **kw: tuple(values) if values else (kw.get('pitch', 0), kw.get('yaw', 0), kw.get('roll', 0)))
    def __getattr__(self, name):
        if name.endswith(('Actor', 'light', 'fog', 'volume')) or name in ('targetpoint', 'PlayerStart'):
            return types.SimpleNamespace(__name__=name)
        return inert()


def source_actors():
    geometry = module('_bb_expansion_recorded_geometry', root / 'Tools/build_arena.py')
    geometry.unreal = sourcesymbols()
    class Recorder(geometry.ArenaBuilder):
        def __init__(self):
            self.records = []
            self.levels = inert()
        def actor(self, cls, label, location=(0, 0, 0), rotation=(0, 0, 0), tags=(), folder='Arena'):
            record = {'label': label, 'class': '/Script/Engine.' + cls.__name__,
                      'tags': list(tags), 'folder': 'Basketbroom/' + folder,
                      'location': list(location), 'rotation': list(rotation), 'scale': [1.0, 1.0, 1.0],
                      'mesh': none}
            self.records.append(record)
            return sourceactor(record)
        def shape(self, label, mesh, material, location, scale=(1, 1, 1), rotation=(0, 0, 0), collision=false, tags=(), folder='arena', shadow=None):
            actor = self.actor(types.SimpleNamespace(__name__='StaticMeshActor'), label, location, rotation, tags, folder)
            actor.record.update(mesh=mesh, scale=list(scale))
            return actor
        def configure_key(self, *args):
            pass
        def configure_flood(self, *args):
            pass
        def configure_fog(self, *args):
            pass
        def configure_presentation(self, *args):
            pass
    recorder = recorder()
    for phase in PHASES:
        getattr(recorder, phase)()
    labels = [row['label'] for row in recorder.records]
    if len(labels) != len(set(labels)):
        raise runtimeerror('arena source labels must be unique before selective staging')
    return recorder.records


def capture_baseline():
    if BASELINE.exists():
        raise runtimeerror('the immutable source baseline already exists')
    records = source_actors()
    data = {'schema_version': 1, 'source_builder_sha256': digest(root / 'Tools/build_arena.py'),
            'dimensions': {'half_x': 6850.8, 'half_y': 3200.4, 'eave': 4206.24, 'apex': 6309.36, 'goal_x': 6400.8},
            'actors': records, 'meshes': {path.stem: {'source': path.relative_to(ROOT).as_posix(), 'sha256': digest(path)}
                for path in sorted((root / 'SourceArt/Arena').glob('*.obj'))}}
    BASELINE.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    return {'baseline': str(baseline), 'actors': len(records), 'meshes': len(data['meshes'])}


def build_plan():
    dims = module('_bb_expansion_contract', root / 'Tools/arena_dimensions.py')
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    before = {row['label']: row for row in baseline['actors']}
    after = {row['label']: row for row in source_actors()}
    if set(before) != set(after):
        raise runtimeerror('expansion must preserve authored actor labels: ' + str(sorted(set(before) ^ set(after))))
    actors = []
    for label, row in before.items():
        current = after[label]
        if any(row[key] != current[key] for key in ('class', 'tags', 'mesh', 'folder')):
            raise runtimeerror('expansion changed a non-transform source contract: ' + label)
        old = {key: row[key] for key in ('location', 'rotation', 'scale')}
        new = {key: current[key] for key in ('location', 'rotation', 'scale')}
        entry = {key: row[key] for key in ('label', 'class', 'tags', 'mesh', 'folder')}
        entry.update(old=old, new=new, changed=old != new)
        actors.append(entry)
    changed_meshes = []
    for name, item in baseline['meshes'].items():
        new_hash = digest(root / item['source'])
        if new_hash != item['sha256']:
            changed_meshes.append({'name': name, 'source': item['source'],
                'destination': '/Basketbroom/Art/Meshes/' + name,
                'sha256_before': item['sha256'], 'sha256_after': new_hash})
    return {'schema_version': 1, 'scale': dims.LINEAR_SCALE, 'volume_ratio': dims.VOLUME_SCALE,
            'baseline_sha256': digest(baseline), 'source_builder_sha256': digest(root / 'Tools/build_arena.py'),
            'dimensions_before': dims.dimensions(1.0), 'dimensions_after': dims.dimensions(),
            'changed_meshes': changed_meshes, 'actors': actors,
            'actor_count': len(actors), 'changed_actor_count': sum(row['changed'] for row in actors)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture-baseline', action='store_true')
    args = parser.parse_args()
    print(json.dumps(capture_baseline() if args.capture_baseline else build_plan(), indent=2))

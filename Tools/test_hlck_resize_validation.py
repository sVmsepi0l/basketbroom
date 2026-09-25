"""Portable guards for linking a preserved native editor resave to its receipt."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


validator = module('_bb_resize_validation', 'Tools/stage_hlck_arena_expansion.py')
planner = module('_bb_resize_validation_plan', 'Tools/arena_resize_plan.py')


class ResizeReceiptTests(unittest.TestCase):
    def setUp(self):
        self.plan = planner.build_plan('hlck')
        records = {}
        for index, entry in enumerate(self.plan['actors']):
            record = {key: copy.deepcopy(entry[key]) for key in ('label', 'class', 'tags', 'folder')}
            record.update(copy.deepcopy(entry['old']))
            record['tags'].append(validator.GENERATED_TAG)
            record['components_identity'] = []
            if entry['mesh']:
                prefix = '/Basketbroom/Art/Meshes/' if entry['mesh'].startswith('SM_BB_') else '/Engine/BasicShapes/'
                record['mesh'] = prefix + entry['mesh'] + '.' + entry['mesh']
            if entry['label'] == 'Twilight amber key':
                record['scale'] = [2.5, 2.5, 2.5]
            records[validator.MAPS[0] + '.PersistentLevel.actor_' + str(index)] = record
        selected = validator.match_plan(records, self.plan, 'old')
        current = copy.deepcopy(records)
        for path, entry in selected.items():
            current[path].update(copy.deepcopy(entry['new']))
        self.predecessor = {'sha256_after': 'a' * 64, 'actors_before': records, 'game_mode_before': 'None'}
        self.item = {'prior_expansion_map_sha256': 'a' * 64, 'sha256_before': 'b' * 64,
                     'preexisting_saved_changes_since_expansion': True, 'game_mode_before': 'None',
                     'actors_before': current}

    def verify(self):
        return validator.verified_resize_predecessor(self.item, self.predecessor, self.plan)

    def test_identical_snapshot_after_planned_moves_accepts_resave(self):
        self.assertTrue(self.verify())

    def test_exact_predecessor_bytes_need_no_resave_exception(self):
        self.item['sha256_before'] = self.predecessor['sha256_after']
        self.assertFalse(self.verify())

    def test_wrong_predecessor_hash_rejected(self):
        self.item['prior_expansion_map_sha256'] = 'c' * 64
        with self.assertRaises(RuntimeError):
            self.verify()

    def test_unrecorded_resave_rejected(self):
        self.item['preexisting_saved_changes_since_expansion'] = False
        with self.assertRaises(RuntimeError):
            self.verify()

    def test_changed_game_mode_rejected(self):
        self.item['game_mode_before'] = 'OtherMode'
        with self.assertRaises(RuntimeError):
            self.verify()

    def test_changed_component_or_material_rejected(self):
        record = next(iter(self.item['actors_before'].values()))
        record['physical_material'] = '/Other/Material'
        with self.assertRaises(RuntimeError):
            self.verify()

    def test_relocated_spawn_rejected(self):
        record = next(row for row in self.item['actors_before'].values() if row['class'].endswith('PlayerStart'))
        record['location'][0] += 100
        with self.assertRaises(RuntimeError):
            self.verify()

    def test_missing_actor_rejected(self):
        self.item['actors_before'].pop(next(iter(self.item['actors_before'])))
        with self.assertRaises(RuntimeError):
            self.verify()


if __name__ == '__main__':
    unittest.main()

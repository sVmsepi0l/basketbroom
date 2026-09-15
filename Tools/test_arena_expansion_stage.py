"""Portable rejection/preservation tests for the selective UE5 arena stager.

These cover its data contracts only; no Unreal assets or collision are loaded.
"""
import copy
import importlib.util
from pathlib import Path
import unittest

TOOLS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('_bb_standalone_stage_test', TOOLS/'stage_arena_expansion.py')
stage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stage)


class StandaloneExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = stage.validate_plan(stage.module('_bb_stage_test_source_plan', 'Tools/arena_expansion_plan.py').build_plan())

    def records(self):
        records = {}
        for index, entry in enumerate(self.plan['actors']):
            mesh = entry['mesh']
            path = (('/Basketbroom/Art/Meshes/' if mesh.startswith('SM_BB_') else '/Engine/BasicShapes/')+mesh+'.'+mesh) if mesh else None
            records[stage.MAPS[0]+'.PersistentLevel.Actor_'+str(index)] = dict(
                label=entry['label'], **{'class': entry['class']}, tags=['BB.Generated']+entry['tags'],
                folder=entry['folder'], mesh=path, components={'Component': {'materials': ['/Basketbroom/Material.Original']}},
                **copy.deepcopy(entry['old']))
        return records

    def training_records(self, map_path=stage.MAPS[1]):
        result = {}
        for index, (label, row) in enumerate(stage.training_layout(1.0).items()):
            category = row['category']
            classes = {'start': '/Script/Engine.PlayerStart', 'ball': '/Basketbroom/Blueprints/BP_BBBall.BP_BBBall_C',
                       'bot': '/Basketbroom/Blueprints/BP_BBBot.BP_BBBot_C'}
            tags = {'start': ['BB.Gameplay', 'BB.Spawn'], 'ball': ['BB.Gameplay', 'BB.Ball'], 'bot': ['BB.Gameplay', 'BB.Bot']}
            record = dict(label=label, **{'class': classes[category]}, tags=tags[category], location=row['location'],
                          home=row['home'], kind=row['kind'], bot_identity=row['bot_identity'], components={})
            result[map_path+'.PersistentLevel.Training_'+str(index)] = record
        return result

    def test_material_slot_backups_are_detached_before_source_array_changes(self):
        class Material:
            def get_path_name(self): return '/Basketbroom/Art/Materials/Original.Original'
        class Slot:
            def __init__(self):
                self.values = dict(material_interface=Material(), material_slot_name='authored', imported_material_slot_name='source')
            def get_editor_property(self, key): return self.values[key]
            def copy(self):
                result = Slot()
                result.values = copy.copy(self.values)
                return result
        original = Slot()
        class Mesh:
            def get_editor_property(self, key): return [original]
        captured = stage.capture_material_slots(Mesh())
        original.values['material_slot_name'] = 'reimport replacement'
        original.values['material_interface'] = None
        self.assertEqual(captured['values'][0].values['material_slot_name'], 'authored')
        self.assertIsNotNone(captured['values'][0].values['material_interface'])
        self.assertEqual(captured['receipt'][0]['name'], 'authored')
        self.assertEqual(captured['receipt'][0]['imported_name'], 'source')

    def test_text_color_snapshot_compares_rgba_without_wrapper_addresses(self):
        class Color:
            r, g, b, a = 231, 191, 121, 255
        before, after = Color(), Color()
        self.assertNotEqual(str(before), str(after))
        self.assertEqual(stage.color_channels(before), stage.color_channels(after))
        after.r = 100
        self.assertNotEqual(stage.color_channels(before), stage.color_channels(after))

    def test_reimport_diagnostics_include_all_changed_actors_and_fields(self):
        before = {'a': {'location': [0, 0, 0], 'material': 'original'}, 'b': {'scale': [1, 1, 1]}}
        after = {'a': {'location': [1, 0, 0], 'material': 'wrong'}, 'b': {'scale': [2, 2, 2]}}
        differences = stage.record_differences(before, after)
        self.assertEqual(len(differences), 2)
        self.assertEqual(set(differences[0]['changes']), {'location', 'material'})
        self.assertEqual(differences[1]['changes']['scale']['before'], [1, 1, 1])

    def test_ten_meshes_and_two_maps_are_the_only_allowed_files(self):
        destinations = list(stage.MAPS)+[item['destination'] for item in self.plan['changed_meshes']]
        self.assertEqual(len(destinations), 12)
        for path in destinations:
            self.assertTrue(stage.asset_file(path, self.plan).is_relative_to(stage.CONTENT))
        with self.assertRaises(ValueError):
            stage.asset_file('/Basketbroom/Art/Materials/M_BB_Iron', self.plan)
        with self.assertRaises(ValueError):
            stage.asset_file('/Basketbroom/Maps/Basketbroom_DungeonMap', self.plan)

    def test_every_source_actor_except_adopted_start_is_required(self):
        records = self.records()
        selected = stage.match_plan(records, self.plan)
        self.assertEqual(len(selected), 904)
        del records[next(iter(selected))]
        with self.assertRaises(RuntimeError): stage.match_plan(records, self.plan)

    def test_legacy_lower_net_label_is_accepted_without_renaming(self):
        records = self.records()
        target = next(row for row in records.values() if row['label'] == 'Continuous closed-arena rebound net')
        target['label'] = 'Continuous open-crown rebound net'
        selected = stage.match_plan(records, self.plan)
        updated = copy.deepcopy(records)
        for path, entry in selected.items(): updated[path].update(entry['new'])
        stage.compare(records, updated, selected, {})
        self.assertIn('Continuous open-crown rebound net', [row['label'] for row in updated.values()])

    def test_observed_native_light_default_scale_stays_two_point_five(self):
        records = self.records()
        path = next(path for path, row in records.items() if row['label'] == 'Twilight amber key')
        records[path]['scale'] = [2.5, 2.5, 2.5]
        selected = stage.match_plan(records, self.plan)
        self.assertEqual(selected[path]['new']['scale'], [2.5, 2.5, 2.5])
        self.assertEqual(next(row for row in self.plan['actors'] if row['label'] == 'Twilight amber key')['new']['scale'], [1, 1, 1])
        after = copy.deepcopy(records)
        for key, entry in selected.items(): after[key].update(entry['new'])
        stage.compare(records, after, selected, {})
        self.assertEqual(after[path]['scale'], [2.5, 2.5, 2.5])

    def test_unobserved_light_scale_is_not_accepted_as_a_class_default(self):
        records = self.records()
        light = next(row for row in records.values() if row['label'] == 'Twilight amber key')
        light['scale'] = [3, 3, 3]
        with self.assertRaises(RuntimeError): stage.match_plan(records, self.plan)

    def test_all_eighteen_historical_crown_beacons_match_without_renames(self):
        records = self.records()
        changed = 0
        for record in records.values():
            if record['label'].startswith('Eave beacon '):
                record['label'] = stage.LABEL_ALIASES[record['label']]
                changed += 1
        self.assertEqual(changed, 18)
        selected = stage.match_plan(records, self.plan)
        after = copy.deepcopy(records)
        for path, entry in selected.items(): after[path].update(entry['new'])
        stage.compare(records, after, selected, {})
        self.assertEqual(sum(row['label'].startswith('Crown beacon ') for row in after.values()), 18)

    def test_duplicate_crown_and_eave_beacons_are_ambiguous(self):
        records = self.records()
        duplicate = next(copy.deepcopy(row) for row in records.values() if row['label'] == 'Eave beacon -1 0')
        duplicate['label'] = 'Crown beacon -1 0'
        records['duplicate'] = duplicate
        with self.assertRaises(RuntimeError): stage.match_plan(records, self.plan)

    def test_unwitnessed_float_label_spelling_is_not_an_alias(self):
        records = self.records()
        row = next(row for row in records.values() if row['label'] == 'Eave beacon -1 0')
        row['label'] = 'Eave beacon -1 0.0'
        with self.assertRaises(RuntimeError): stage.match_plan(records, self.plan)

    def test_ambiguous_alias_does_not_claim_either_actor(self):
        records = self.records()
        target = next(copy.deepcopy(row) for row in records.values() if row['label'] == 'Continuous closed-arena rebound net')
        target['label'] = 'Continuous open-crown rebound net'
        records['extra'] = target
        with self.assertRaises(RuntimeError): stage.match_plan(records, self.plan)

    def test_label_alone_cannot_authorize_a_different_mesh_or_owner(self):
        for field, value in (('tags', ['Unrelated']), ('mesh', '/Game/AnotherMesh.AnotherMesh')):
            records = self.records()
            next(iter(records.values()))[field] = value
            with self.assertRaises(RuntimeError): stage.match_plan(records, self.plan)

    def test_user_modified_old_pose_is_preserved_by_rejection(self):
        records = self.records()
        next(iter(records.values()))['location'][0] += 1
        with self.assertRaises(RuntimeError): stage.match_plan(records, self.plan)

    def test_component_material_changes_cannot_hide_behind_expected_transform(self):
        before = self.records()
        selected = stage.match_plan(before, self.plan)
        after = copy.deepcopy(before)
        for path, entry in selected.items(): after[path].update(entry['new'])
        self.assertGreater(stage.compare(before, after, selected, {}), 0)
        after[next(iter(selected))]['components']['Component']['materials'] = ['/Game/Unwanted.Material']
        with self.assertRaises(RuntimeError): stage.compare(before, after, selected, {})

    def test_unrelated_native_start_pose_stays_protected(self):
        before = self.records()
        path = next(path for path, record in before.items() if record['label'] == 'BB Player Start')
        before[path]['location'] = [-3000, 0, 300]
        selected = stage.match_plan(before, self.plan)
        after = copy.deepcopy(before)
        for key, entry in selected.items(): after[key].update(entry['new'])
        stage.compare(before, after, selected, {})
        after[path]['location'] = [-4400, 0, 1400]
        with self.assertRaises(RuntimeError): stage.compare(before, after, selected, {})

    def test_training_homes_move_without_changing_class_role_or_components(self):
        before = self.training_records()
        selected = stage.match_training(before, stage.MAPS[1])
        self.assertEqual(len(selected), 21)
        after = copy.deepcopy(before)
        for path, entry in selected.items(): after[path].update(entry['new'])
        stage.compare(before, after, {}, selected)
        stage.match_training(after, stage.MAPS[1], 'new')
        bot = next(row for row in after.values() if row['bot_identity'])
        bot['bot_identity'] = [9, 9, 9]
        with self.assertRaises(RuntimeError): stage.compare(before, after, {}, selected)

    def test_training_home_disagreement_rejects_before_staging(self):
        records = self.training_records()
        ball = next(row for row in records.values() if row['kind'] == 0)
        ball['home'] = [0, 0, 0]
        with self.assertRaises(RuntimeError): stage.match_training(records, stage.MAPS[1])

    def test_moved_regulation_native_ground_start_is_not_replaced(self):
        records = {'native': dict(label='BB Player Start', **{'class': '/Script/Engine.PlayerStart'},
                                 tags=['BB.Generated', 'BB.Spawn'], location=[-3000, 0, 300])}
        self.assertEqual(stage.match_training(records, stage.MAPS[0]), {})

    def test_saved_material_or_unlisted_asset_bytes_are_rejected(self):
        before = {'Maps/BB_Arena.umap': 'old', 'Art/Materials/Original.uasset': 'preserved'}
        after = dict(before, **{'Maps/BB_Arena.umap': 'new'})
        self.assertEqual(stage.check_file_scope(before, after, ['Maps/BB_Arena.umap']), ['Maps/BB_Arena.umap'])
        after['Art/Materials/Original.uasset'] = 'changed'
        with self.assertRaises(RuntimeError): stage.check_file_scope(before, after, ['Maps/BB_Arena.umap'])


if __name__ == '__main__':
    unittest.main()

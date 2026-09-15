"""Portable guard tests; no editor, asset or registration is changed."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bb_native_expansion', ROOT / 'Tools/stage_hlck_arena_expansion.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.content = self.root / 'Mod/Basketbroom/Content'
        self.patches = [patch.object(stage, 'ROOT', self.root), patch.object(stage, 'CONTENT', self.content),
                        patch.object(stage, 'SUCCESS', self.root / '.local/hlck/arena-expansion-success.json')]
        for item in self.patches:
            item.start()
        self.map = stage.map_file(stage.MAPS[1])
        self.map.parent.mkdir(parents=True)
        self.map.write_bytes(b'original native dungeon and anchors')
        self.original = stage.digest(self.map)
        stage.map_file(stage.MAPS[0]).write_bytes(b'original source arena')

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def amendment(self, kind='expansion', previous=None):
        directory = self.root / ('.local/hlck/arena-expansion-stage/one' if kind == 'expansion' else '.local/hlck/pyramid-net-stage/roof')
        backup = directory / 'backups/Maps/Basketbroom_DungeonMap.umap'
        backup.parent.mkdir(parents=True)
        backup.write_bytes(self.map.read_bytes())
        before = stage.digest(self.map)
        self.map.write_bytes(self.map.read_bytes() + kind.encode())
        receipt = directory / 'result.json'
        plan = {'dimensions_after': {'half_x': 7754.086}, 'volume_ratio': 1.45, 'changed_meshes': []}
        result = {'status': 'staged', 'preservation_verified': True, 'materials_preserved': True,
                  'amendment_kind': 'arena_volume_45_percent', 'plan': plan, 'plan_sha256': stage.plan_hash(plan),
                  'predecessor_roof_success': previous,
                  'saved_package_hashes': {str(path): stage.digest(path) for path in stage.allowed_files(plan)},
                  'maps': [{'path': stage.MAPS[1], 'sha256_before': before, 'sha256_after': stage.digest(self.map),
                            'backup': str(backup), 'unrelated_actors_preserved': True,
                            'actor_identity_and_components_preserved': True, 'saved_reloaded': True,
                            'geometry_after': {'passed': True}}]}
        stage.write(receipt, result)
        pointer = {'report': str(receipt), 'sha256': stage.digest(receipt)}
        if kind == 'expansion':
            stage.write(stage.SUCCESS, pointer)
        return receipt, backup, pointer

    def revise(self, receipt, edit):
        value = json.loads(receipt.read_text())
        edit(value)
        stage.write(receipt, value)
        stage.write(stage.SUCCESS, {'report': str(receipt), 'sha256': stage.digest(receipt)})

    def test_no_receipt_is_not_a_pass(self):
        self.assertIsNone(stage.verified_amendment(stage.MAPS[1], self.original))

    def test_exact_expansion_validates(self):
        self.amendment()
        self.assertEqual(stage.verified_amendment(stage.MAPS[1], self.original)['verified_expansions'], 1)

    def test_expansion_reaches_original_through_immutable_roof(self):
        roof_receipt, unused, pointer = self.amendment('roof')
        roof_hash = stage.digest(roof_receipt)
        self.amendment(previous=pointer)
        result = stage.verified_amendment(stage.MAPS[1], self.original)
        self.assertEqual(result['verified_roof_amendments'], 1)
        self.assertEqual(stage.digest(roof_receipt), roof_hash)

    def test_edited_map_rejected(self):
        self.amendment()
        self.map.write_bytes(b'unrelated edit')
        with self.assertRaises(RuntimeError):
            stage.verified_amendment(stage.MAPS[1], self.original)

    def test_edited_backup_rejected(self):
        unused, backup, pointer = self.amendment()
        backup.write_bytes(b'unrelated bytes')
        with self.assertRaises(RuntimeError):
            stage.verified_amendment(stage.MAPS[1], self.original)

    def test_edited_receipt_rejected(self):
        receipt, unused, pointer = self.amendment()
        receipt.write_text(receipt.read_text() + ' ')
        with self.assertRaises(RuntimeError):
            stage.verified_amendment(stage.MAPS[1], self.original)

    def test_failed_dryrun_or_missing_preservation_rejected(self):
        receipt, unused, pointer = self.amendment()
        valid = json.loads(receipt.read_text())
        for edit in (lambda value: value.update(status='ready'), lambda value: value.update(status='failed'),
                     lambda value: value.update(preservation_verified=False), lambda value: value.update(materials_preserved=False),
                     lambda value: value.update(saved_package_hashes={}),
                     lambda value: value['maps'][0].update(actor_identity_and_components_preserved=False),
                     lambda value: value['maps'][0].update(saved_reloaded=False),
                     lambda value: value['maps'][0].update(geometry_after={'passed': False})):
            stage.write(receipt, valid)
            self.revise(receipt, edit)
            with self.assertRaises(RuntimeError):
                stage.verified_amendment(stage.MAPS[1], self.original)

    def test_altered_plan_hash_rejected(self):
        receipt, unused, pointer = self.amendment()
        self.revise(receipt, lambda value: value['plan'].update(volume_ratio=2))
        with self.assertRaises(RuntimeError):
            stage.verified_amendment(stage.MAPS[1], self.original)

    def test_wrong_map_or_unrelated_origin_not_authorized(self):
        self.amendment()
        self.assertIsNone(stage.verified_amendment('/Game/Levels/Overland', self.original))
        self.assertIsNone(stage.verified_amendment(stage.MAPS[1], '0' * 64))

    def test_paths_outside_package_allowlist_rejected(self):
        plan = {'changed_meshes': [{'destination': '/Basketbroom/Art/Meshes/SM_BB_PyramidCollision'}]}
        self.assertEqual(len(stage.allowed_files(plan)), 3)
        for destination in ('/Game/Levels/Overland', '/Basketbroom/Art/Materials/M_BBPort_RoofNet', '/Basketbroom/ModEdits'):
            with self.assertRaises(ValueError):
                stage.asset_file(destination, plan)


    def test_malicious_plan_cannot_authorize_material_or_installed_package(self):
        for destination in ('/Game/Levels/Overland', '/Basketbroom/Art/Materials/M_BBPort_RoofNet', '/Basketbroom/Art/Meshes/../Secrets'):
            plan = {'changed_meshes': [{'destination': destination}]}
            with self.assertRaises(ValueError):
                stage.asset_file(destination, plan)


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.path = stage.MAPS[0] + '.World:PersistentLevel.StaticMeshActor_1'
        self.pose = {'location': [1, 2, 3], 'rotation': [0, 0, 0], 'scale': [1, 1, 1]}
        self.entry = {'label': 'Owned arena actor', 'class': '/Script/Engine.StaticMeshActor',
                      'tags': ['BB.Net.Side'], 'mesh': 'Cube', 'old': copy.deepcopy(self.pose), 'new': copy.deepcopy(self.pose)}
        self.entry['new']['location'][0] = 100
        self.plan = {'actors': [self.entry]}
        self.record = {'label': self.entry['label'], 'class': self.entry['class'], 'tags': [stage.GENERATED_TAG, 'BB.Net.Side'],
                       'mesh': '/Engine/BasicShapes/Cube.Cube', 'materials': ['preserved'], **copy.deepcopy(self.pose)}

    def test_owned_exact_pose_matches(self):
        self.assertEqual(list(stage.match_plan({self.path: self.record}, self.plan)), [self.path])

    def test_label_without_ownership_does_not_authorize(self):
        self.record['tags'].remove(stage.GENERATED_TAG)
        with self.assertRaises(RuntimeError):
            stage.match_plan({self.path: self.record}, self.plan)

    def test_duplicate_label_refused(self):
        with self.assertRaises(RuntimeError):
            stage.match_plan({self.path: self.record, self.path + '_2': self.record}, self.plan)

    def test_class_mesh_tag_and_old_pose_changes_refused(self):
        for field, value in (('class', '/Script/Engine.CameraActor'), ('mesh', '/Game/Unrelated.Mesh'),
                             ('tags', [stage.GENERATED_TAG, 'Wrong']), ('location', [1, 2, 40])):
            record = copy.deepcopy(self.record)
            record[field] = value
            with self.assertRaises(RuntimeError):
                stage.match_plan({self.path: record}, self.plan)

    def test_known_legacy_net_label_preserved(self):
        self.entry['label'] = 'Continuous closed-arena rebound net'
        self.record['label'] = 'Continuous open-crown rebound net'
        selected = stage.match_plan({self.path: self.record}, self.plan)
        self.assertIn(self.path, selected)
        self.assertEqual(self.record['label'], 'Continuous open-crown rebound net')

    def test_known_legacy_beacon_alias_is_bounded(self):
        self.entry['label'] = 'Eave beacon -1 0'
        self.record['label'] = 'Crown beacon -1 0'
        self.assertIn(self.path, stage.match_plan({self.path: self.record}, self.plan))
        self.entry['label'] = 'Eave beacon -1 99'
        self.record['label'] = 'Crown beacon -1 99'
        with self.assertRaises(RuntimeError):
            stage.match_plan({self.path: self.record}, self.plan)

    def test_native_directional_light_default_is_preserved(self):
        self.entry.update(label='Twilight amber key', **{'class': '/Script/Engine.DirectionalLight', 'mesh': None})
        self.record.update(label='Twilight amber key', **{'class': '/Script/Engine.DirectionalLight', 'scale': [2.5, 2.5, 2.5]})
        selected = stage.match_plan({self.path: self.record}, self.plan)
        self.assertEqual(selected[self.path]['new']['scale'], [2.5, 2.5, 2.5])
        self.assertEqual(self.entry['new']['scale'], [1, 1, 1])
        self.record['scale'] = [3, 3, 3]
        with self.assertRaises(RuntimeError):
            stage.match_plan({self.path: self.record}, self.plan)

    def test_dungeon_fog_adaptation_is_preserved_only_in_dungeon(self):
        self.path = stage.MAPS[1] + '.World:PersistentLevel.Fog'
        self.entry.update(label='Aerial depth', **{'class': '/Script/Engine.ExponentialHeightFog', 'mesh': None})
        self.entry['old']['location'] = [0, 0, -800]
        self.entry['new']['location'] = [0, 0, -800]
        self.record.update(label='Aerial depth', **{'class': '/Script/Engine.ExponentialHeightFog', 'location': [0, 0, 0]})
        selected = stage.match_plan({self.path: self.record}, self.plan)
        self.assertEqual(selected[self.path]['new']['location'], [0, 0, 0])
        self.assertIn(self.path.replace(stage.MAPS[1], stage.MAPS[0]),
                      stage.match_plan({self.path.replace(stage.MAPS[1], stage.MAPS[0]): self.record}, self.plan))
        self.record['location'] = [0, 0, 100]
        with self.assertRaises(RuntimeError):
            stage.match_plan({self.path: self.record}, self.plan)

    def test_exact_new_transform_preserves_components(self):
        selected = stage.match_plan({self.path: self.record}, self.plan)
        after = copy.deepcopy(self.record)
        after['location'][0] = 100
        self.assertEqual(stage.compare_preservation({self.path: self.record}, {self.path: after}, selected), 1)
        after['materials'] = ['replaced']
        with self.assertRaises(RuntimeError):
            stage.compare_preservation({self.path: self.record}, {self.path: after}, selected)

    def test_unrelated_actor_transform_and_identity_preserved(self):
        after = copy.deepcopy(self.record)
        after['location'][0] += 10
        with self.assertRaises(RuntimeError):
            stage.compare_preservation({self.path: self.record}, {self.path: after}, {})
        with self.assertRaises(RuntimeError):
            stage.compare_preservation({self.path: self.record}, {}, {})

    def test_equivalent_rotator_wrap_and_small_float_roundoff(self):
        self.assertTrue(stage.near([180, 360, -180], [-180, 0, 180], angular=True))
        self.assertTrue(stage.near([7141.2568], [7141.25666]))
        self.assertFalse(stage.near([7142.2568], [7141.25666]))


class StableSnapshotTests(unittest.TestCase):
    def actor(self, label='Actor', klass='/Script/Engine.StaticMeshActor'):
        return {'label': label, 'class': klass, 'location': [0, 0, 0], 'rotation': [0, 0, 0],
                'scale': [1, 1, 1], 'tags': [], 'folder': 'None', 'components_identity': []}

    def test_color_wrapper_address_is_not_a_scene_change(self):
        record = self.actor()
        record['text_settings'] = {'text_render_color': "<Struct 'Color' (0x123ABC) {b: 232, g: 191, r: 122, a: 255}>"}
        result = stage.canonical_snapshot({'actor': record})
        self.assertEqual(result['actor']['text_settings']['text_render_color'], {'r': 122, 'g': 191, 'b': 232, 'a': 255})
        record['text_settings']['text_render_color'] = 'unrecognized bytes'
        with self.assertRaises(RuntimeError):
            stage.canonical_snapshot({'actor': record})

    def test_only_exact_empty_engine_camera_is_qualified(self):
        record = self.actor('SceneRigCameraManager', '/Script/SceneRig.SceneRigCameraManager')
        path = stage.MAPS[0] + '.BB_Arena_Port:PersistentLevel.SceneRigCameraManager_0'
        self.assertEqual(stage.canonical_snapshot({path: record}), {})
        record['tags'] = ['UserOwned']
        self.assertIn(path, stage.canonical_snapshot({path: record}))
        record['tags'] = []
        record['components_identity'] = [('UserComponent', '/Script/Engine.SceneComponent')]
        self.assertIn(path, stage.canonical_snapshot({path: record}))

    def test_only_observed_fog_reload_positions_are_equivalent(self):
        record = self.actor('Aerial depth', '/Script/Engine.ExponentialHeightFog')
        record['tags'] = [stage.GENERATED_TAG]
        record['location'] = [0, 0, -800]
        self.assertEqual(stage.canonical_snapshot({'fog': record})['fog']['location'], [0, 0, 0])
        record['location'] = [0, 0, 100]
        self.assertEqual(stage.canonical_snapshot({'fog': record})['fog']['location'], [0, 0, 100])


class SourceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch = patch.object(stage, 'ROOT', self.root)
        self.patch.start()
        self.base = self.root / 'SourceArt/Arena/arena_expansion_baseline.json'
        self.base.parent.mkdir(parents=True)
        baseline = {'meshes': {'SM_BB_Test': {'source': 'SourceArt/Arena/SM_BB_Test.obj', 'sha256': 'a' * 64}}}
        stage.write(self.base, baseline)
        self.path = self.base.with_name('arena_expansion_source_hashes.json')
        self.provenance = {'schema_version': 1, 'baseline_file_sha256': stage.digest(self.base),
            'meshes': {'SM_BB_Test': {'source': 'SourceArt/Arena/SM_BB_Test.obj', 'baseline_sha256': 'a' * 64,
                                    'text_variants': {'lf': 'a' * 64, 'crlf': 'b' * 64}, 'git_source_sha256': 'a' * 64}}}
        stage.write(self.path, self.provenance)
        self.plan = {'baseline_sha256': stage.digest(self.base), 'changed_meshes': []}
        self.manifest = {'source_imports': [{'asset_type': 'StaticMesh', 'source': 'SourceArt/Arena/SM_BB_Test.obj', 'sha256': 'a' * 64}]}

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_captured_baseline_allows_only_its_two_text_variants(self):
        result = stage.source_provenance(self.plan, self.manifest)
        self.assertEqual(set(result['meshes']['SM_BB_Test']['text_variants'].values()), {'a' * 64, 'b' * 64})

    def test_changed_baseline_bytes_rejected(self):
        self.base.write_text(self.base.read_text() + ' ')
        with self.assertRaises(RuntimeError):
            stage.source_provenance(self.plan, self.manifest)

    def test_unrelated_source_or_digest_rejected(self):
        for key, value in (('source', 'SourceArt/Arena/Other.obj'), ('baseline_sha256', 'c' * 64), ('git_source_sha256', 'c' * 64)):
            modified = copy.deepcopy(self.provenance)
            modified['meshes']['SM_BB_Test'][key] = value
            stage.write(self.path, modified)
            with self.assertRaises(RuntimeError):
                stage.source_provenance(self.plan, self.manifest)

    def test_missing_mesh_provenance_rejected(self):
        self.provenance['meshes'] = {}
        stage.write(self.path, self.provenance)
        with self.assertRaises(RuntimeError):
            stage.source_provenance(self.plan, self.manifest)


if __name__ == '__main__':
    unittest.main()

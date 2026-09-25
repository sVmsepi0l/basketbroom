"""Offline guards for original venue geometry and bounded map authoring."""
import copy
import importlib.util
import json
import itertools
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'Tools'/file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

builder=load('_bb_env_builder_test','build_arena_environments.py')
stage=load('_bb_env_stage_test','stage_arena_environments.py')

class EnvironmentTests(unittest.TestCase):
    def test_triangle_crossing_without_interior_vertices_is_rejected(self):
        self.assertTrue(builder.triangle_intersects_box([(-4,-4,0),(4,-4,0),(0,4,0)],(0,0,0),(1,1,1)))

    def test_overhang_above_protected_box_is_clear(self):
        self.assertFalse(builder.triangle_intersects_box([(-20000,-20000,10000),(20000,-20000,10000),(0,20000,10000)],(0,0,3700),(7905,3773,3700)))

    def test_slanted_triangle_separates_from_box(self):
        self.assertFalse(builder.triangle_intersects_box([(3,0,0),(0,3,0),(3,3,2)],(0,0,0),(.5,.5,.5)))

    def test_instance_rotation_and_scale_transform_real_geometry(self):
        result=builder.transformed((2,1,3),{'location':[100,200,300],'scale':[2,3,4],'yaw':90})
        for a,b in zip(result,(97,204,312)):self.assertAlmostEqual(a,b)

    def test_intruding_instance_rejected(self):
        venue=builder.Venue('redrock');mesh=venue.mesh('Test','Adobe');mesh.box((0,0,500),(100,100,100));venue.place('Test','bad')
        with self.assertRaisesRegex(ValueError,'protected arena'):builder.validate_venue(venue)

    def test_ellipsoid_triangles_face_outward(self):
        mesh=builder.Mesh();mesh.ellipsoid((0,0,0),(5,5,5),roughness=0)
        for face in mesh.faces:
            a,b,c=[mesh.vertices[i-1] for i in face]
            normal=builder.cross(tuple(b[k]-a[k] for k in range(3)),tuple(c[k]-a[k] for k in range(3)))
            center=tuple((a[k]+b[k]+c[k])/3 for k in range(3))
            self.assertGreater(sum(normal[k]*center[k] for k in range(3)),0)

    def test_source_manifest_has_exact_current_enclosure(self):
        manifest=json.loads((ROOT/'SourceArt/Environments/environments_manifest.json').read_text())
        self.assertEqual(manifest['sporting_dimensions'],builder.dim.dimensions())
        self.assertEqual({v['map'] for v in manifest['venues']},set(stage.MAPS))
        for venue in manifest['venues']:
            self.assertEqual(venue['clearance_audit']['decorative_intrusions'],0)
            self.assertGreater(venue['clearance_audit']['triangles_checked'],50000)
            self.assertTrue(all(i['collision']=='NoCollision' for i in venue['instances']))

    def redwood_manifest(self):
        manifest=json.loads((ROOT/'SourceArt/Environments/environments_manifest.json').read_text())
        return next(venue for venue in manifest['venues'] if venue['id']=='redwoods')

    def test_redwood_trunks_and_crowns_stay_paired(self):
        trees={}
        for item in self.redwood_manifest()['instances']:
            if 'tree' in item:trees.setdefault(item['tree']['id'],[]).append(item)
        self.assertEqual(set(trees),set(range(49)))
        for pair in trees.values():
            self.assertEqual(len(pair),2)
            self.assertEqual({item['label'].rsplit(' ',1)[-1] for item in pair},{'trunk','crown'})
            for key in ('tree','location','scale','yaw'):
                self.assertEqual(pair[0][key],pair[1][key])

    def test_selected_redwoods_are_triple_the_actual_previous_size(self):
        # Captured September 25 pre-giant instance scales, before generation.
        previous={3:.8958462320321466,8:1.1996948291419465,14:.8836743258438154,
                  21:1.0468040317924385,26:.9582037839542685,31:1.1645726407348995,
                  38:.9194666613064418,44:1.043001942008899}
        trunks=[item for item in self.redwood_manifest()['instances'] if item['label'].endswith(' trunk')]
        giants=[item for item in trunks if item['tree']['size_class']=='giant']
        self.assertEqual({item['tree']['id'] for item in giants},set(previous))
        for item in giants:
            self.assertEqual(item['tree']['previous_scale'],previous[item['tree']['id']])
            for scale in item['scale']:self.assertAlmostEqual(scale,3*previous[item['tree']['id']])

    def test_redwood_grove_keeps_size_and_depth_variation(self):
        venue=self.redwood_manifest()
        self.assertEqual(venue['forest_scale']['size_counts'],{'original':21,'medium':20,'giant':8})
        trunks=[item for item in venue['instances'] if item['label'].endswith(' trunk')]
        self.assertEqual(len(trunks),49)
        self.assertGreater(len({round(item['scale'][0],2) for item in trunks}),30)
        giants=[item for item in trunks if item['tree']['size_class']=='giant']
        self.assertEqual({item['tree']['depth_band'] for item in giants},{'near','middle','deep','side'})
        for item in trunks:
            tree=item['tree'];multiplier=tree['scale_multiplier']
            if tree['size_class']=='medium':self.assertTrue(1.45<=multiplier<=1.8)
            if tree['size_class']=='original':self.assertEqual(multiplier,1)
            self.assertAlmostEqual(item['scale'][0],tree['previous_scale']*multiplier)

    def test_whole_redwood_bounds_stay_outside_enlarged_arena(self):
        venue=self.redwood_manifest();meshes={mesh['name']:mesh for mesh in venue['meshes']}
        arena=venue['clearance_audit'];minimum=arena['protected_box_min'];maximum=arena['protected_box_max']
        for item in venue['instances']:
            if 'tree' not in item:continue
            bounds=meshes[item['mesh']]['bounds']
            corners=[builder.transformed(point,item) for point in itertools.product(*zip(*bounds))]
            self.assertTrue(any(max(point[axis] for point in corners)<minimum[axis]
                                or min(point[axis] for point in corners)>maximum[axis]
                                for axis in range(3)),item['label'])

    def test_all_source_meshes_match_hashes(self):
        manifest=json.loads((ROOT/'SourceArt/Environments/environments_manifest.json').read_text())
        for venue in manifest['venues']:
            for mesh in venue['meshes']:
                path=ROOT/'SourceArt/Environments'/mesh['file']
                self.assertEqual(stage.digest(path),mesh['sha256'])
                self.assertLess(path.stat().st_size,25_000_000)

    def test_no_sporting_assets_in_write_allowlist(self):
        manifest=json.loads((ROOT/'SourceArt/Environments/environments_manifest.json').read_text())
        allowed=stage.allowed_content(manifest)
        self.assertNotIn('Maps/BB_Regulation.umap',allowed)
        self.assertNotIn('Maps/BB_Arena.umap',allowed)
        self.assertTrue(all(p.startswith('Environments/') or p in ('Maps/BB_Redrock.umap','Maps/BB_Redwoods.umap') for p in allowed))

    def test_backdrop_label_cannot_claim_unrelated_actor(self):
        data={'a':{'label':'Twilight dome','class':'/Script/Engine.StaticMeshActor','tags':[],'mesh':'/Engine/BasicShapes/Sphere.Sphere'}}
        with self.assertRaisesRegex(RuntimeError,'ownership'):stage.backdrop_keys(data,False)

    def test_sporting_transform_change_rejected(self):
        original={'Goal':{'location':[7244.753,0,2103.12],'mesh':'rim','material':'gold'}}
        changed=copy.deepcopy(original);changed['Goal']['location'][0]+=1
        with self.assertRaisesRegex(RuntimeError,'state differs'):stage.assert_protected(original,changed)

    def test_sporting_material_change_rejected(self):
        original={'Goal':{'location':[7244.753,0,2103.12],'mesh':'rim','material':'gold'}}
        changed=copy.deepcopy(original);changed['Goal']['material']='adobe'
        with self.assertRaisesRegex(RuntimeError,'state differs'):stage.assert_protected(original,changed)

    def test_missing_actor_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'identities'):stage.assert_protected({'Goal':{}},{})

if __name__=='__main__':unittest.main()

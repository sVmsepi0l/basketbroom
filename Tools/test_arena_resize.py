"""Focused source and ownership contracts for the anisotropic arena resize."""
import copy,importlib.util,json,math,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/'Tools'/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
planmod=module('_resize_test_plan','arena_resize_plan.py');d=planmod.dim
axes=module('_resize_test_axes','arena_environment_axes.py');stage=module('_resize_test_stage','stage_arena_resize.py')
native_stage=module('_resize_test_native_stage','stage_hlck_arena_resize.py')
class ResizeTests(unittest.TestCase):
 def test_current_relative_ratios_and_height(self):
  old=d.previous_dimensions();new=d.dimensions()
  self.assertAlmostEqual(new['half_x']/old['half_x'],math.sqrt(2))
  self.assertAlmostEqual(new['half_y']/old['half_y'],math.sqrt(2))
  self.assertAlmostEqual(new['half_x']/new['half_y'],old['half_x']/old['half_y'])
  for key in ('eave','apex'):self.assertEqual(old[key],new[key])
  self.assertAlmostEqual(d.enclosed_volume_cm3(new)/d.enclosed_volume_cm3(old),2)
 def test_fixed_goal_setback(self):
  old=d.dimensions(d.LINEAR_SCALE);new=d.dimensions()
  self.assertAlmostEqual(new['half_x']-new['goal_x'],old['half_x']-old['goal_x'])
 def test_generated_header_exact(self):self.assertEqual(d.HEADER.read_text(),d.header_text())
 def test_exact_plan_mesh_scope(self):
  for engine in ('standalone','hlck'):
   p=planmod.build_plan(engine);self.assertEqual(len(p['actors']),905);self.assertEqual(len(p['changed_meshes']),10)
   self.assertTrue(all('Hoop' not in r['name'] for r in p['changed_meshes']))
 def test_engine_specific_immutable_baselines(self):
  standalone=planmod.load_baseline('standalone');native=planmod.load_baseline('hlck')
  self.assertEqual(standalone['dimensions'],d.previous_dimensions())
  self.assertEqual(native['dimensions'],d.dimensions(d.LINEAR_SCALE))
  self.assertEqual(len(standalone['actors']),905);self.assertEqual(len(standalone['meshes']),18)
  self.assertEqual(standalone['verified_predecessor']['baseline_sha256'],planmod.BASELINES['hlck'][2])
  self.assertNotEqual(standalone['dimensions'],native['dimensions'])
  with self.assertRaises(ValueError):planmod.load_baseline('unknown')
 def test_native_and_standalone_reach_identical_geometry(self):
  one=planmod.build_plan('standalone');two=planmod.build_plan('hlck')
  self.assertEqual(one['dimensions_after'],two['dimensions_after'])
  self.assertEqual([a['new'] for a in one['actors']],[a['new'] for a in two['actors']])
  self.assertAlmostEqual(one['volume_ratio'],2);self.assertAlmostEqual(two['volume_ratio'],16/3)
 def test_wrong_baseline_provenance_rejected(self):
  p=planmod.build_plan();p['engine']='hlck'
  with self.assertRaises(ValueError):planmod.validate_plan(p)
 def test_wrong_baseline_actor_pose_rejected(self):
  p=planmod.build_plan();p['actors'][0]['old']['location'][0]+=1
  with self.assertRaises(ValueError):planmod.validate_plan(p)
 def test_declared_ratio_tampering_rejected(self):
  p=planmod.build_plan();p['axis_multipliers'][0]=2
  with self.assertRaises(ValueError):planmod.validate_plan(p)
 def test_native_unchanged_meshes_accept_only_proved_newline_variants(self):
  plan=planmod.build_plan('hlck');baseline=planmod.load_baseline('hlck')
  changed={r['name'] for r in plan['changed_meshes']};unchanged=set(baseline['meshes'])-changed
  self.assertEqual(len(unchanged),8)
  for name in unchanged:
   values=native_stage.source_hashes_for_phase(plan,baseline,name,'old')
   self.assertIn(baseline['meshes'][name]['sha256'],values);self.assertEqual(len(values),2)
   self.assertNotIn('0'*64,values)
   self.assertEqual(values,native_stage.source_hashes_for_phase(plan,baseline,name,'new'))
 def test_native_changed_meshes_require_exact_revision_hash(self):
  plan=planmod.build_plan('hlck');baseline=planmod.load_baseline('hlck')
  for row in plan['changed_meshes']:
   self.assertEqual(native_stage.source_hashes_for_phase(plan,baseline,row['name'],'old'),{row['sha256_before']})
   self.assertEqual(native_stage.source_hashes_for_phase(plan,baseline,row['name'],'new'),{row['sha256_after']})
 def test_native_unchanged_source_with_different_content_rejected(self):
  plan=planmod.build_plan('hlck');baseline=planmod.load_baseline('hlck')
  baseline['meshes']['SM_BB_LargeHoop']['sha256']='0'*64
  with self.assertRaises(RuntimeError):native_stage.source_hashes_for_phase(plan,baseline,'SM_BB_LargeHoop','old')
 def test_sporting_goals_move_without_shape_or_height_change(self):
  p=planmod.build_plan();goals=[a for a in p['actors'] if 'BB.Goal' in a['tags']];self.assertEqual(len(goals),8)
  for a in goals:
   self.assertEqual(a['old']['location'][1:],a['new']['location'][1:]);self.assertEqual(a['old']['scale'],a['new']['scale'])
 def test_user_changed_height_rejected(self):
  p=planmod.build_plan();p['dimensions_after']['apex']+=1
  with self.assertRaises(ValueError):planmod.validate_plan(p)
 def test_scope_four_owned_standalone_maps(self):
  self.assertEqual(set(stage.MAPS),{'/Basketbroom/Maps/BB_Regulation','/Basketbroom/Maps/BB_Arena','/Basketbroom/Maps/BB_Redrock','/Basketbroom/Maps/BB_Redwoods'})
 def training_records(self,layout):
  classes={'start':'/Script/Engine.PlayerStart','ball':'/Basketbroom/Blueprints/BP_BBBall.BP_BBBall_C','bot':'/Basketbroom/Blueprints/BP_BBBot.BP_BBBot_C'}
  return {label:dict(row,label=label,tags=['BB.Gameplay'],**{'class':classes[row['category']]}) for label,row in layout.items()}
 def test_training_keepers_accept_both_exact_phases(self):
  old=stage.training_layout_at(d.previous_dimensions()['goal_x']);new=stage.training_layout_at(d.GOAL_PLANE_X)
  for phase,layout in (('old',old),('new',new)):
   selected=stage.match_training(self.training_records(layout),stage.MAPS[1],phase)
   self.assertEqual(len(selected),len(layout))
  changed=[label for label in old if old[label]!=new[label]]
  self.assertEqual(len(changed),2)
  for label in changed:
   self.assertEqual(old[label]['bot_identity'][2],0)
   self.assertAlmostEqual(abs(new[label]['home'][0]-old[label]['home'][0]),d.GOAL_PLANE_X-d.previous_dimensions()['goal_x'])
 def test_training_rejects_historical_or_mixed_poses(self):
  historical=stage.base.training_layout(d.LINEAR_SCALE)
  with self.assertRaises(RuntimeError):stage.match_training(self.training_records(historical),stage.MAPS[1],'old')
  old=stage.training_layout_at(d.previous_dimensions()['goal_x']);new=stage.training_layout_at(d.GOAL_PLANE_X)
  label=next(label for label in old if old[label]!=new[label]);old[label]=new[label]
  with self.assertRaises(RuntimeError):stage.match_training(self.training_records(old),stage.MAPS[1],'old')
  with self.assertRaises(RuntimeError):stage.match_training(self.training_records(old),stage.MAPS[1],'new')
 def test_axis_identity(self):
  b=[[-10,-30,-2],[20,5,7]];self.assertEqual(axes.classify(b,b,20,20)['orientation'],'identity')
 def test_axis_reflection_and_compensation(self):
  b=[[-10,-30,-2],[20,5,7]];actual=[[-10,-5,-2],[20,30,7]];row=axes.classify(b,actual,20,20)
  self.assertEqual(axes.combined_sign([row]),-1)
  # A known asymmetric source point returns to the exact authored world point
  # after import Y reflection and actor Y compensation, even at nonzero yaw.
  p=(3,7,11);yaw=.7;scale=(1.2,1.2,1.2);position=(100,200,300)
  def transform(q,s):return (q[0]*s[0]*math.cos(yaw)-q[1]*s[1]*math.sin(yaw)+position[0],q[0]*s[0]*math.sin(yaw)+q[1]*s[1]*math.cos(yaw)+position[1],q[2]*s[2]+position[2])
  self.assertEqual(transform(p,scale),transform((3,-7,11),(1.2,-1.2,1.2)))
 def test_axis_rejects_unknown_transform(self):
  with self.assertRaises(ValueError):axes.classify([[-10,-30,-2],[20,5,7]],[[-10,-30,-2],[20,6,7]],20,20)
 def test_axis_rejects_wrong_topology_and_mixed_sign(self):
  with self.assertRaises(ValueError):axes.classify([[0,0,0],[1,1,1]],[[0,0,0],[1,1,1]],20,19)
  with self.assertRaises(ValueError):axes.combined_sign([{'orientation':'identity'},{'orientation':'mirror_y'}])
 def test_axis_symmetric_is_not_evidence(self):
  b=[[-10,-30,-2],[20,30,7]];row=axes.classify(b,b,20,20)
  with self.assertRaises(ValueError):axes.combined_sign([row])
 def test_new_rule_geometry_matches(self):
  r=json.loads((ROOT/'Rules/alpha_rules.json').read_text())['geometry_ft']
  self.assertAlmostEqual(r['length']*30.48,d.GOAL_PLANE_X*2);self.assertAlmostEqual(r['enclosure_length']*30.48,d.HALF_LENGTH*2);self.assertAlmostEqual(r['width']*30.48,d.HALF_WIDTH*2)
if __name__=='__main__':unittest.main()

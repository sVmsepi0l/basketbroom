"""Focused source and ownership contracts for the anisotropic arena resize."""
import copy,importlib.util,json,math,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/'Tools'/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
planmod=module('_resize_test_plan','arena_resize_plan.py');d=planmod.dim
axes=module('_resize_test_axes','arena_environment_axes.py');stage=module('_resize_test_stage','stage_arena_resize.py')
class ResizeTests(unittest.TestCase):
 def test_current_relative_ratios_and_height(self):
  old=d.dimensions(d.LINEAR_SCALE);new=d.dimensions()
  self.assertAlmostEqual(new['half_x']/old['half_x'],2)
  self.assertAlmostEqual(new['half_y']/old['half_y'],4/3)
  for key in ('eave','apex'):self.assertEqual(old[key],new[key])
  self.assertAlmostEqual(d.enclosed_volume_cm3(new)/d.enclosed_volume_cm3(old),8/3)
 def test_fixed_goal_setback(self):
  old=d.dimensions(d.LINEAR_SCALE);new=d.dimensions()
  self.assertAlmostEqual(new['half_x']-new['goal_x'],old['half_x']-old['goal_x'])
 def test_generated_header_exact(self):self.assertEqual(d.HEADER.read_text(),d.header_text())
 def test_exact_plan_mesh_scope(self):
  p=planmod.build_plan();self.assertEqual(len(p['actors']),905);self.assertEqual(len(p['changed_meshes']),10)
  self.assertTrue(all('Hoop' not in r['name'] for r in p['changed_meshes']))
 def test_sporting_goals_move_without_shape_or_height_change(self):
  p=planmod.build_plan();goals=[a for a in p['actors'] if 'BB.Goal' in a['tags']];self.assertEqual(len(goals),8)
  for a in goals:
   self.assertEqual(a['old']['location'][1:],a['new']['location'][1:]);self.assertEqual(a['old']['scale'],a['new']['scale'])
 def test_user_changed_height_rejected(self):
  p=planmod.build_plan();p['dimensions_after']['apex']+=1
  with self.assertRaises(ValueError):planmod.validate_plan(p)
 def test_scope_four_owned_standalone_maps(self):
  self.assertEqual(set(stage.MAPS),{'/Basketbroom/Maps/BB_Regulation','/Basketbroom/Maps/BB_Arena','/Basketbroom/Maps/BB_Redrock','/Basketbroom/Maps/BB_Redwoods'})
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

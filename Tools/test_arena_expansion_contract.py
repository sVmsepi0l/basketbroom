"""Offline arena expansion contract: authored geometry, sporting sizes, and scope.

Run after regenerating SourceArt/Arena. These tests evaluate numeric source
placements without an editor; they do not claim imported collision or gameplay
has passed. The immutable baseline preserves the pre-expansion venue contract.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


dimensions = load_module("bb_expansion_dimensions_test", "Tools/arena_dimensions.py")
planner = load_module("bb_expansion_plan_test", "Tools/arena_expansion_plan.py")


def read_obj(name):
    vertices, faces = [], []
    for line in (ROOT / "SourceArt/Arena" / (name + ".obj")).read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields and fields[0] == "v":
            vertices.append(tuple(float(value) for value in fields[1:4]))
        elif fields and fields[0] == "f":
            faces.append(tuple(int(value.split("/")[0]) - 1 for value in fields[1:]))
    return vertices, faces


def cube_bounds(transform):
    # Unreal's basic Cube is 100cm on every axis. Collision boxes are unrotated.
    center, scale = transform["location"], transform["scale"]
    return tuple((center[i] - 50 * scale[i], center[i] + 50 * scale[i]) for i in range(3))


class DimensionContractTests(unittest.TestCase):
    def test_pre_expansion_baseline_cannot_silently_move(self):
        baseline = json.loads(planner.BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(baseline["dimensions"], {
            "half_x": 6850.8, "half_y": 3200.4, "eave": 4206.24,
            "apex": 6309.36, "goal_x": 6400.8,
        })
        self.assertEqual(dimensions.dimensions(1.0), baseline["dimensions"])
        self.assertEqual(len(baseline["actors"]), 905)
        self.assertEqual(len({row["label"] for row in baseline["actors"]}), 905)
        # Canonical JSON permits Git's line-ending conversion, but no silent
        # rebaselining of actor placements, source provenance, or mesh hashes.
        canonical = json.dumps(baseline, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(),
                         "61119060e25f4d94b9900e7faf39b2f2a335f8ab59bd0bd23630f7bfc10b897e")

    def test_true_enclosure_volume_grows_45_percent(self):
        old = dimensions.dimensions(1.0)
        new = dimensions.dimensions()
        def volume(values):
            prism = 4 * values["half_x"] * values["half_y"] * values["eave"]
            pyramid = 4 * values["half_x"] * values["half_y"] * (values["apex"] - values["eave"]) / 3
            return prism + pyramid
        ratio = volume(new) / volume(old)
        self.assertAlmostEqual(ratio, 1.45, places=12)
        self.assertGreaterEqual(ratio, 1.40)
        self.assertLessEqual(ratio, 1.50)
        self.assertAlmostEqual(dimensions.enclosed_volume_cm3(), volume(new), delta=.001)
        self.assertAlmostEqual(volume(old) / 1e6, 430374.351, places=3)
        self.assertGreater(old["half_x"], old["goal_x"])
        self.assertGreater(volume(new), volume(dict(new, half_x=new["goal_x"])))

    def test_each_axis_and_the_behind_goal_bay_scale_together(self):
        old, new = dimensions.dimensions(1.0), dimensions.dimensions()
        for key in old:
            with self.subTest(dimension=key):
                self.assertAlmostEqual(new[key] / old[key], dimensions.LINEAR_SCALE, places=13)
        self.assertAlmostEqual(new["half_x"] - new["goal_x"], 450 * dimensions.LINEAR_SCALE, places=9)
        self.assertAlmostEqual(dimensions.LINEAR_SCALE ** 3, 1.45, places=13)

    def test_generated_cpp_header_has_exact_python_values(self):
        text = dimensions.HEADER.read_text(encoding="utf-8")
        self.assertEqual(text, dimensions.header_text())
        parsed = dict((name, float(value)) for name, value in
                      re.findall(r"inline constexpr double (\w+) = ([^;]+);", text))
        names = {
            "VolumeScale": "VOLUME_SCALE", "LinearScale": "LINEAR_SCALE",
            "GoalPlaneX": "GOAL_PLANE_X", "HalfLength": "HALF_LENGTH",
            "HalfWidth": "HALF_WIDTH", "EaveHeight": "EAVE_HEIGHT", "ApexHeight": "APEX_HEIGHT",
            "LargeHoopHeight": "LARGE_HOOP_HEIGHT", "SmallHoopHeight": "SMALL_HOOP_HEIGHT",
            "HoopSpacing": "HOOP_SPACING", "LargeHoopRadius": "LARGE_HOOP_RADIUS",
            "SmallHoopRadius": "SMALL_HOOP_RADIUS", "FreeShotDistance": "FREE_SHOT_DISTANCE",
            "RestartDistance": "RESTART_DISTANCE",
        }
        self.assertEqual(set(parsed), set(names))
        for cpp_name, python_name in names.items():
            with self.subTest(constant=cpp_name):
                self.assertEqual(parsed[cpp_name], getattr(dimensions, python_name))

    def test_sporting_measurements_remain_unscaled(self):
        for name, feet in (("LARGE_HOOP_HEIGHT", 69), ("SMALL_HOOP_HEIGHT", 100),
                           ("HOOP_SPACING", 35), ("LARGE_HOOP_RADIUS", 11),
                           ("SMALL_HOOP_RADIUS", 6.5), ("FREE_SHOT_DISTANCE", 44),
                           ("RESTART_DISTANCE", 22)):
            with self.subTest(measurement=name):
                self.assertAlmostEqual(getattr(dimensions, name), feet * 30.48, places=10)


class AuthoredExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = planner.build_plan()
        cls.rows = {row["label"]: row for row in cls.plan["actors"]}
        cls.baseline = json.loads(planner.BASELINE.read_text(encoding="utf-8"))
        cls.manifest = json.loads((ROOT / "SourceArt/Arena/arena_manifest.json").read_text(encoding="utf-8"))

    def assert_vector_close(self, actual, expected, tolerance=.00001):
        self.assertEqual(len(actual), len(expected))
        for axis, (observed, target) in enumerate(zip(actual, expected)):
            self.assertAlmostEqual(observed, target, delta=tolerance, msg="axis %d" % axis)

    def test_plan_preserves_905_actor_identities_and_every_old_transform(self):
        self.assertEqual(self.plan["actor_count"], 905)
        self.assertEqual(len(self.rows), 905)
        self.assertEqual(self.plan["dimensions_before"], dimensions.dimensions(1.0))
        self.assertEqual(self.plan["dimensions_after"], dimensions.dimensions())
        for source in self.baseline["actors"]:
            row = self.rows[source["label"]]
            with self.subTest(actor=source["label"]):
                self.assertEqual(row["old"], {key: source[key] for key in ("location", "rotation", "scale")})
                self.assertEqual(row["changed"], row["old"] != row["new"])
                for key in ("class", "tags", "mesh", "folder"):
                    self.assertEqual(row[key], source[key])
        self.assertEqual(self.plan["changed_actor_count"], sum(row["changed"] for row in self.rows.values()))
        self.assertGreater(self.plan["changed_actor_count"], 0)

    def test_trampoline_covers_full_net_footprint_at_zero_altitude(self):
        floor = self.rows["Trampoline - continuous rebound surface"]
        self.assertEqual(floor["mesh"], "Cube")
        self.assertIn("BB.Rebound", floor["tags"])
        self.assert_vector_close(floor["new"]["rotation"], (0, 0, 0))
        bounds = cube_bounds(floor["new"])
        self.assert_vector_close(bounds[0], (-dimensions.HALF_LENGTH - 50, dimensions.HALF_LENGTH + 50))
        self.assert_vector_close(bounds[1], (-dimensions.HALF_WIDTH - 50, dimensions.HALF_WIDTH + 50))
        self.assert_vector_close(bounds[2], (-70, 0))

    def test_wall_inner_faces_match_roof_eaves_and_shared_playable_bounds(self):
        walls = [row for row in self.rows.values() if "BB.Net.End" in row["tags"] or "BB.Net.Side" in row["tags"]]
        self.assertEqual(len(walls), 4)
        for row in walls:
            with self.subTest(wall=row["label"]):
                transform = row["new"]
                self.assertEqual(row["mesh"], "Cube")
                self.assert_vector_close(transform["rotation"], (0, 0, 0))
                bounds = cube_bounds(transform)
                self.assert_vector_close(bounds[2], (0, dimensions.EAVE_HEIGHT))
                axis = 0 if "BB.Net.End" in row["tags"] else 1
                half_extent = dimensions.HALF_LENGTH if axis == 0 else dimensions.HALF_WIDTH
                inner = bounds[axis][0] if transform["location"][axis] > 0 else -bounds[axis][1]
                self.assertAlmostEqual(inner, half_extent, delta=.00001)
                self.assertAlmostEqual(bounds[axis][1] - bounds[axis][0], 30, places=9)
                other_half_extent = dimensions.HALF_WIDTH if axis == 0 else dimensions.HALF_LENGTH
                self.assert_vector_close(bounds[1 - axis], (-other_half_extent, other_half_extent))

    def test_eight_goals_move_without_scaling_apertures_or_hoop_heights(self):
        goals = [row for row in self.rows.values() if "BB.Goal" in row["tags"]]
        self.assertEqual(len(goals), 8)
        for team, side in (("Teal", -1), ("Copper", 1)):
            owned = [row for row in goals if "BB.Team." + team in row["tags"]]
            self.assertEqual(len(owned), 4)
            large = [row for row in owned if "BB.Goal.Large" in row["tags"]]
            small = [row for row in owned if "BB.Goal.Small" in row["tags"]]
            self.assertEqual(len(large), 3)
            self.assertEqual(len(small), 1)
            self.assert_vector_close(sorted(row["new"]["location"][1] for row in large),
                                     (-dimensions.HOOP_SPACING, 0, dimensions.HOOP_SPACING))
            for row in owned:
                with self.subTest(goal=row["label"]):
                    large_goal = "BB.Goal.Large" in row["tags"]
                    self.assertAlmostEqual(row["new"]["location"][0], side * dimensions.GOAL_PLANE_X, places=8)
                    self.assertAlmostEqual(row["new"]["location"][2],
                                           dimensions.LARGE_HOOP_HEIGHT if large_goal else dimensions.SMALL_HOOP_HEIGHT, places=8)
                    self.assertEqual(row["new"]["scale"], [1, 1, 1])
                    self.assertEqual(row["new"]["rotation"], row["old"]["rotation"])
            self.assertAlmostEqual(small[0]["new"]["location"][1], 0, places=8)

    def test_goal_rim_collision_and_supports_follow_goal_without_body_rescale(self):
        selected = [row for row in self.rows.values() if "BB.Goal.Rim" in row["tags"]
                    or "BB.Support" in row["tags"] or row["label"].endswith(" elevated mast")]
        self.assertEqual(sum("BB.Goal.Rim" in row["tags"] for row in selected), 480)
        self.assertEqual(sum("BB.Support" in row["tags"] for row in selected), 6)
        self.assertEqual(sum(row["label"].endswith(" elevated mast") for row in selected), 2)
        for row in selected:
            with self.subTest(actor=row["label"]):
                old, new = row["old"], row["new"]
                side = -1 if old["location"][0] < 0 else 1
                delta = side * (dimensions.GOAL_PLANE_X - dimensions.BASELINE_GOAL_PLANE_X)
                self.assert_vector_close(new["location"], (old["location"][0] + delta,
                                                            old["location"][1], old["location"][2]))
                self.assertEqual(new["rotation"], old["rotation"])
                self.assertEqual(new["scale"], old["scale"])

    def test_authored_torus_apertures_keep_their_real_mesh_radii(self):
        for name, expected in (("SM_BB_LargeHoop", dimensions.LARGE_HOOP_RADIUS),
                               ("SM_BB_SmallHoop", dimensions.SMALL_HOOP_RADIUS)):
            with self.subTest(mesh=name):
                vertices, faces = read_obj(name)
                self.assertGreater(len(faces), 0)
                radius = min(math.hypot(point[1], point[2]) for point in vertices)
                self.assertAlmostEqual(radius, expected, delta=.00002)
                source = ROOT / self.baseline["meshes"][name]["source"]
                self.assertEqual(planner.digest(source), self.baseline["meshes"][name]["sha256"])
                self.assertNotIn(name, {row["name"] for row in self.plan["changed_meshes"]})

    def test_collision_source_is_exactly_four_sloped_triangles_with_open_base(self):
        vertices, faces = read_obj("SM_BB_PyramidCollision")
        self.assertEqual(len(vertices), 5)
        self.assertEqual(len(faces), 4)
        expected = ((-dimensions.HALF_LENGTH, -dimensions.HALF_WIDTH, dimensions.EAVE_HEIGHT),
                    (dimensions.HALF_LENGTH, -dimensions.HALF_WIDTH, dimensions.EAVE_HEIGHT),
                    (dimensions.HALF_LENGTH, dimensions.HALF_WIDTH, dimensions.EAVE_HEIGHT),
                    (-dimensions.HALF_LENGTH, dimensions.HALF_WIDTH, dimensions.EAVE_HEIGHT),
                    (0, 0, dimensions.APEX_HEIGHT))
        for actual, target in zip(vertices, expected):
            self.assert_vector_close(actual, target)
        self.assertEqual(set(faces), {(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)})
        edges = {}
        for face in faces:
            self.assertEqual(len(face), 3)
            self.assertIn(4, face)
            self.assertGreater(max(vertices[i][2] for i in face), min(vertices[i][2] for i in face))
            for first, second in zip(face, face[1:] + face[:1]):
                edge = tuple(sorted((first, second)))
                edges[edge] = edges.get(edge, 0) + 1
        self.assertEqual(sum(count == 1 for count in edges.values()), 4)
        self.assertTrue(all(count == 2 for edge, count in edges.items() if 4 in edge))

    def test_roof_mesh_actors_do_not_double_apply_source_scale(self):
        roof = [row for row in self.rows.values() if row["mesh"] in
                ("SM_BB_PyramidNet", "SM_BB_PyramidRibs", "SM_BB_PyramidCopper", "SM_BB_PyramidCollision")]
        self.assertEqual(len(roof), 4)
        for row in roof:
            with self.subTest(actor=row["label"]):
                self.assert_vector_close(row["new"]["location"], (0, 0, 0))
                self.assert_vector_close(row["new"]["rotation"], (0, 0, 0))
                self.assert_vector_close(row["new"]["scale"], (1, 1, 1))
        self.assert_vector_close(self.rows["Pyramidion apex"]["new"]["location"], (0, 0, dimensions.APEX_HEIGHT))
        self.assert_vector_close(self.rows["Pyramidion eave reference"]["new"]["location"], (0, 0, dimensions.EAVE_HEIGHT))

    def test_manifest_agrees_with_actual_authored_enclosure_and_goals(self):
        manifest = self.manifest
        self.assert_vector_close(manifest["goal_planes_x_cm"], (-dimensions.GOAL_PLANE_X, dimensions.GOAL_PLANE_X))
        self.assert_vector_close(manifest["end_net_x_cm"], (-dimensions.HALF_LENGTH, dimensions.HALF_LENGTH))
        self.assert_vector_close(manifest["side_net_y_cm"], (-dimensions.HALF_WIDTH, dimensions.HALF_WIDTH))
        self.assertAlmostEqual(manifest["pitch_goal_to_goal_cm"], 2 * dimensions.GOAL_PLANE_X, places=8)
        self.assertAlmostEqual(manifest["roof"]["eave_z_cm"], dimensions.EAVE_HEIGHT, places=8)
        self.assert_vector_close(manifest["roof"]["apex_cm"], (0, 0, dimensions.APEX_HEIGHT))
        self.assertEqual(manifest["roof"]["faces"], 4)
        self.assertIs(manifest["roof"]["horizontal_base"], False)

    def test_plan_rejects_missing_actor_or_changed_mesh_identity(self):
        records = planner.source_actors()
        with patch.object(planner, "source_actors", return_value=records[:-1]):
            with self.assertRaisesRegex(RuntimeError, "preserve authored actor labels"):
                planner.build_plan()
        changed = [dict(row) for row in records]
        changed[0]["mesh"] = "UnrelatedMesh"
        with patch.object(planner, "source_actors", return_value=changed):
            with self.assertRaisesRegex(RuntimeError, "non-transform source contract"):
                planner.build_plan()


if __name__ == "__main__":
    unittest.main(verbosity=2)

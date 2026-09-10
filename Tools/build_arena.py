"""Build Basketbroom's original arena in Unreal Engine 5.8.

Editor console (Python mode)::

    exec(open(r'C:/Git/basketbroom/Tools/build_arena.py').read())

The Basketbroom content plugin must already be enabled. This creates or updates
only /Basketbroom/Maps/BB_Arena and generated assets under /Basketbroom/Art.
Existing untagged actors survive rebuilds. Call build() after importing as a module.

Outside Unreal, ``python Tools/build_arena.py --generate-source`` creates the
original, deterministic OBJ meshes and their dimension manifest using stdlib.
UE5 editor subsystems are preferred; legacy APIs remain a Creator Kit fallback.
It authors a venue; game rules and match execution belong to the runtime module.
"""

import argparse
import json
import math
import os
from pathlib import Path

try:
    import unreal
except ImportError:
    unreal = None


REPO_ROOT = Path(os.environ.get("BASKETBROOM_REPO", r"C:\Git\basketbroom"))
SOURCE_ROOT = REPO_ROOT / "SourceArt" / "Arena"
MOUNT = "/Basketbroom"
LEVEL_PATH = MOUNT + "/Maps/BB_Arena"
ART_PATH = MOUNT + "/Art"
GENERATED_TAG = "BB.Generated"
FT = 30.48
HALF_LENGTH = 210.0 * FT
HALF_WIDTH = 105.0 * FT
ROOFLINE = 138.0 * FT
LARGE_CENTER = 69.0 * FT
SMALL_CENTER = 100.0 * FT
LARGE_RADIUS = 11.0 * FT
SMALL_RADIUS = 6.5 * FT
GOAL_SPACING = 35.0 * FT
BACKSTOP_X = HALF_LENGTH + 450.0
CAMERA_LOCATION = (-12400.0, -11400.0, 9400.0)
CAMERA_ROTATION = (-25.0, 42.0, 0.0)
SCENERY_TAG = "BB.Scenery"
COURT_FLOOD_INTENSITY = 1000.0
EXPOSURE_BRIGHTNESS = 0.6
BLOOM_INTENSITY = 0.16

# Keep these shared with polish_scene.py so an in-place refresh and a new build
# render identically. Low net specularity is essential for readable goal rims.
ARENA_PALETTE = (
    ("M_BB_Trampoline", (0.018, 0.036, 0.045), 0.98, 0.0, 0.0, False),
    ("M_BB_FloorAlternate", (0.023, 0.045, 0.052), 0.98, 0.0, 0.0, False),
    ("M_BB_Basalt", (0.038, 0.046, 0.060), 0.90, 0.04, 0.0, False),
    ("M_BB_Iron", (0.025, 0.042, 0.049), 0.65, 0.42, 0.0, False),
    ("M_BB_Copper", (0.47, 0.19, 0.061), 0.46, 0.60, 0.025, False),
    ("M_BB_Teal", (0.023, 0.29, 0.27), 0.50, 0.30, 0.035, False),
    ("M_BB_Cream", (0.40, 0.47, 0.40), 0.88, 0.0, 0.025, False),
    ("M_BB_TealLight", (0.035, 0.70, 0.49), 0.65, 0.0, 2.1, False),
    ("M_BB_CopperLight", (1.0, 0.30, 0.045), 0.65, 0.0, 2.1, False),
    ("M_BB_IvoryLight", (0.83, 0.57, 0.22), 0.65, 0.0, 1.45, False),
    ("M_BB_Net", (0.027, 0.051, 0.061), 1.0, 0.0, 0.0, False),
    ("M_BB_Sky", (0.010, 0.020, 0.046), 1.0, 0.0, 1.0, True),
    ("M_BB_Stars", (0.37, 0.51, 0.66), 1.0, 0.0, 1.6, True),
    ("M_BB_Ground", (0.010, 0.020, 0.024), 1.0, 0.0, 1.0, True),
    ("M_BB_Ridge", (0.014, 0.026, 0.040), 1.0, 0.0, 1.0, True),
    ("M_BB_Pine", (0.009, 0.019, 0.024), 1.0, 0.0, 1.0, True),
)


class ObjMesh:
    """Small mesh writer; vertices are Unreal centimeters, Z up."""

    def __init__(self):
        self.vertices = []
        self.faces = []

    def vertex(self, point):
        self.vertices.append(point)
        return len(self.vertices)

    def face(self, *indices):
        self.faces.append(indices)

    def torus(self, inner_radius, tube_radius, segments=128, tube_segments=12):
        # Torus normal along X: goals face along the longitudinal pitch axis.
        base = len(self.vertices) + 1
        major = inner_radius + tube_radius
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            for j in range(tube_segments):
                b = 2.0 * math.pi * j / tube_segments
                radius = major + tube_radius * math.cos(b)
                self.vertex((tube_radius * math.sin(b), radius * math.cos(a), radius * math.sin(a)))
        for i in range(segments):
            for j in range(tube_segments):
                a = base + i * tube_segments + j
                b = base + ((i + 1) % segments) * tube_segments + j
                c = base + ((i + 1) % segments) * tube_segments + ((j + 1) % tube_segments)
                d = base + i * tube_segments + ((j + 1) % tube_segments)
                self.face(a, b, c, d)

    def rod(self, start, end, radius=2.3, sides=6):
        direction = tuple(end[i] - start[i] for i in range(3))
        length = math.sqrt(sum(v * v for v in direction))
        axis = tuple(v / length for v in direction)
        seed = (0.0, 0.0, 1.0) if abs(axis[2]) < 0.9 else (0.0, 1.0, 0.0)
        u = (axis[1] * seed[2] - axis[2] * seed[1],
             axis[2] * seed[0] - axis[0] * seed[2],
             axis[0] * seed[1] - axis[1] * seed[0])
        unit = math.sqrt(sum(v * v for v in u))
        u = tuple(v / unit for v in u)
        v = (axis[1] * u[2] - axis[2] * u[1],
             axis[2] * u[0] - axis[0] * u[2],
             axis[0] * u[1] - axis[1] * u[0])
        base = len(self.vertices) + 1
        for center in (start, end):
            for i in range(sides):
                a = i * math.pi * 2 / sides
                self.vertex(tuple(center[j] + radius * (math.cos(a) * u[j] + math.sin(a) * v[j]) for j in range(3)))
        for i in range(sides):
            j = (i + 1) % sides
            self.face(base + i, base + j, base + sides + j, base + sides + i)
        self.face(*[base + i for i in reversed(range(sides))])
        self.face(*[base + sides + i for i in range(sides)])

    def octahedron(self, center, radius):
        base = len(self.vertices) + 1
        for offset in ((radius, 0, 0), (-radius, 0, 0), (0, radius, 0), (0, -radius, 0), (0, 0, radius), (0, 0, -radius)):
            self.vertex(tuple(center[j] + offset[j] for j in range(3)))
        for a, b in ((0, 2), (2, 1), (1, 3), (3, 0)):
            self.face(base + a, base + b, base + 4)
            self.face(base + b, base + a, base + 5)

    def save(self, filename):
        path = SOURCE_ROOT / filename
        with path.open("w", encoding="ascii", newline="\n") as handle:
            handle.write("# Original Basketbroom procedural mesh; units cm, Z up\n")
            handle.write("o " + path.stem + "\ns 1\n")
            for point in self.vertices:
                handle.write("v %.5f %.5f %.5f\n" % point)
            for face in self.faces:
                handle.write("f " + " ".join(str(v) for v in face) + "\n")
        return {"file": filename, "vertices": len(self.vertices), "polygons": len(self.faces)}


def generate_source_meshes():
    """Return source manifest; safe to run without Unreal installed."""
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    meshes = []
    for filename, inner, tube in (("SM_BB_LargeHoop.obj", LARGE_RADIUS, 20.0),
                                  ("SM_BB_SmallHoop.obj", SMALL_RADIUS, 16.0),
                                  ("SM_BB_CenterCircle.obj", 880.0, 5.0)):
        mesh = ObjMesh()
        mesh.torus(inner, tube)
        meshes.append(mesh.save(filename))

    # A single visual mesh avoids hundreds of independently tickable net actors.
    # Dedicated hidden blocking bodies provide simple stable planar collision.
    mesh = ObjMesh()
    spacing = 250.0
    for side in (-1.0, 1.0):
        y = side * HALF_WIDTH
        count = int(2 * BACKSTOP_X / spacing)
        for i in range(count + 1):
            x = -BACKSTOP_X + 2 * BACKSTOP_X * i / count
            mesh.rod((x, y, 70.0), (x, y, ROOFLINE), 2.0)
        count = int(ROOFLINE / spacing)
        for i in range(count + 1):
            z = 70.0 + (ROOFLINE - 70.0) * i / count
            mesh.rod((-BACKSTOP_X, y, z), (BACKSTOP_X, y, z), 2.0)
        x = side * BACKSTOP_X
        count = int(2 * HALF_WIDTH / spacing)
        for i in range(count + 1):
            y = -HALF_WIDTH + 2 * HALF_WIDTH * i / count
            mesh.rod((x, y, 70.0), (x, y, ROOFLINE), 2.0)
        count = int(ROOFLINE / spacing)
        for i in range(count + 1):
            z = 70.0 + (ROOFLINE - 70.0) * i / count
            mesh.rod((x, -HALF_WIDTH, z), (x, HALF_WIDTH, z), 2.0)
    meshes.append(mesh.save("SM_BB_ReboundNet.obj"))

    # Deterministic sparse pinpricks, well outside the aerial chase envelope.
    mesh = ObjMesh()
    for i in range(96):
        azimuth = i * 2.399963229728653
        height = 0.15 + 0.8 * ((i * 37) % 97) / 97.0
        horizontal = math.sqrt(1 - height * height)
        mesh.octahedron((32000.0 * horizontal * math.cos(azimuth),
                         32000.0 * horizontal * math.sin(azimuth),
                         32000.0 * height), 8.0 + (i % 4) * 4.0)
    meshes.append(mesh.save("SM_BB_Stars.obj"))

    manifest = {
        "units": "centimeters", "origin": "midfield, trampoline top",
        "pitch_goal_to_goal_cm": 2 * HALF_LENGTH, "pitch_width_cm": 2 * HALF_WIDTH,
        "goal_planes_x_cm": [-HALF_LENGTH, HALF_LENGTH],
        "large_goal_centers_y_cm": [-GOAL_SPACING, 0, GOAL_SPACING],
        "large_goal_z_cm": LARGE_CENTER, "large_goal_inner_radius_cm": LARGE_RADIUS,
        "small_goal_z_cm": SMALL_CENTER, "small_goal_inner_radius_cm": SMALL_RADIUS,
        "roofline_z_cm": ROOFLINE, "chase_ceiling_z_cm": 207 * FT,
        "end_net_x_cm": [-BACKSTOP_X, BACKSTOP_X], "side_net_y_cm": [-HALF_WIDTH, HALF_WIDTH],
        "backstop_note": "450cm catch bay behind each goal plane; 420ft remains goal-to-goal.",
        "restitution": 0.75, "level": LEVEL_PATH,
        "screenshot_camera": {"location": CAMERA_LOCATION, "rotation_pitch_yaw_roll": CAMERA_ROTATION},
        "meshes": meshes,
    }
    (SOURCE_ROOT / "arena_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _optional(obj, property_name, value):
    """Only cosmetic/version-dependent settings may use this helper."""
    try:
        obj.set_editor_property(property_name, value)
        return True
    except Exception as error:
        unreal.log_warning("Basketbroom optional setting %s: %s" % (property_name, error))
        return False


class EditorWorldAccess:
    """UE5 subsystem access with the older Creator Kit API as a fallback."""

    def __init__(self):
        self.modern = hasattr(unreal, "LevelEditorSubsystem") and hasattr(unreal, "EditorActorSubsystem")
        if self.modern:
            self.level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
            self.actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        else:
            self.level = unreal.EditorLevelLibrary
            self.actors = unreal.EditorLevelLibrary

    def spawn_actor_from_class(self, cls, location, rotation):
        return self.actors.spawn_actor_from_class(cls, location, rotation)

    def get_all_level_actors(self):
        return self.actors.get_all_level_actors()

    def destroy_actor(self, actor):
        return self.actors.destroy_actor(actor)

    def new_level(self, path):
        return self.level.new_level(path)

    def load_level(self, path):
        return self.level.load_level(path)

    def save_current_level(self):
        return self.level.save_current_level()

    def set_level_viewport_camera_info(self, location, rotation):
        if self.modern:
            key = self.level.get_active_viewport_config_key()
            self.level.set_level_viewport_camera_info(location, rotation, key)
        else:
            self.level.set_level_viewport_camera_info(location, rotation)


class ArenaBuilder:
    def __init__(self):
        self.assets = (unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
                       if hasattr(unreal, "EditorAssetSubsystem") else unreal.EditorAssetLibrary)
        self.levels = EditorWorldAccess()
        self.asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        self.materials = {}
        self.meshes = {}
        self.actors = []
        self.physics = None

    def load_mesh(self, path):
        mesh = self.assets.load_asset(path)
        if mesh is None:
            raise RuntimeError("Required arena mesh is unavailable: " + path)
        return mesh

    def import_mesh(self, name):
        path = ART_PATH + "/Meshes/" + name
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(SOURCE_ROOT / (name + ".obj")))
        task.set_editor_property("destination_path", ART_PATH + "/Meshes")
        task.set_editor_property("destination_name", name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", True)
        # Explicit legacy FBX/OBJ factory keeps our authored Z-up coordinates and
        # avoids the UE5 Interchange importer ignoring FbxImportUI settings.
        task.set_editor_property("factory", unreal.FbxFactory())
        options = unreal.FbxImportUI()
        options.set_editor_property("import_mesh", True)
        options.set_editor_property("import_materials", False)
        options.set_editor_property("import_textures", False)
        options.set_editor_property("import_as_skeletal", False)
        options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
        data = options.get_editor_property("static_mesh_import_data")
        data.set_editor_property("combine_meshes", True)
        data.set_editor_property("auto_generate_collision", False)
        # OBJ coordinates already use centimeters and Unreal's Z-up basis.
        data.set_editor_property("convert_scene", False)
        data.set_editor_property("convert_scene_unit", False)
        _optional(data, "normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_COMPUTE_NORMALS)
        task.set_editor_property("options", options)
        self.asset_tools.import_asset_tasks([task])
        mesh = self.assets.load_asset(path)
        if mesh is None:
            imported = task.get_editor_property("imported_object_paths")
            if imported:
                mesh = self.assets.load_asset(imported[0])
        if mesh is None:
            raise RuntimeError("OBJ import failed for " + name)
        self.meshes[name] = mesh
        return mesh

    def material(self, name, color, roughness=0.55, metallic=0.0, glow=0.0, unlit=False):
        path = ART_PATH + "/Materials/" + name
        mat = self.assets.load_asset(path)
        if mat is None:
            mat = self.asset_tools.create_asset(name, ART_PATH + "/Materials", unreal.Material, unreal.MaterialFactoryNew())
        library = unreal.MaterialEditingLibrary
        library.delete_all_material_expressions(mat)
        mat.set_editor_property("two_sided", True)
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT if unlit else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
        base = library.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -650, -150)
        base.set_editor_property("parameter_name", "Tint")
        base.set_editor_property("default_value", unreal.LinearColor(*color, 1.0))
        if not unlit:
            library.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
            for pname, value, prop, pos in (("Roughness", roughness, unreal.MaterialProperty.MP_ROUGHNESS, 50),
                                            ("Metallic", metallic, unreal.MaterialProperty.MP_METALLIC, 170)):
                node = library.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -350, pos)
                node.set_editor_property("parameter_name", pname)
                node.set_editor_property("default_value", value)
                library.connect_material_property(node, "", prop)
        strength = library.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -650, -320)
        strength.set_editor_property("parameter_name", "Glow")
        strength.set_editor_property("default_value", glow)
        multiply = library.create_material_expression(mat, unreal.MaterialExpressionMultiply, -250, -150)
        library.connect_material_expressions(base, "", multiply, "A")
        library.connect_material_expressions(strength, "", multiply, "B")
        library.connect_material_property(multiply, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        library.recompile_material(mat)
        self.assets.save_loaded_asset(mat)
        self.materials[name] = mat
        return mat

    def actor(self, cls, label, location=(0, 0, 0), rotation=(0, 0, 0), tags=(), folder="Arena"):
        actor = self.levels.spawn_actor_from_class(cls, unreal.Vector(*location),
                                                 unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        if actor is None:
            raise RuntimeError("Could not spawn " + label)
        actor.set_actor_label(label)
        actor.set_editor_property("tags", [unreal.Name(tag) for tag in (GENERATED_TAG,) + tuple(tags)])
        actor.set_folder_path("Basketbroom/" + folder)
        self.actors.append(actor)
        return actor

    def shape(self, label, mesh, material, location, scale=(1, 1, 1), rotation=(0, 0, 0), collision=False, tags=(), folder="Arena"):
        actor = self.actor(unreal.StaticMeshActor, label, location, rotation, tags, folder)
        component = actor.static_mesh_component
        component.set_static_mesh(self.meshes[mesh])
        component.set_material(0, self.materials[material])
        component.set_mobility(unreal.ComponentMobility.STATIC)
        # A saved BlockAll profile restores blocking on map reload even when
        # collision was disabled transiently. Persist the intended profile first.
        component.set_collision_profile_name("BlockAll" if collision else "NoCollision")
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS if collision else unreal.CollisionEnabled.NO_COLLISION)
        if collision:
            if self.physics is not None:
                component.set_phys_material_override(self.physics)
        component.set_editor_property("cast_shadow", collision)
        actor.set_actor_scale3d(unreal.Vector(*scale))
        return actor

    def box(self, label, material, location, size, **kwargs):
        return self.shape(label, "Cube", material, location, tuple(v / 100.0 for v in size), **kwargs)

    def cylinder(self, label, material, location, radius, height, **kwargs):
        return self.shape(label, "Cylinder", material, location, (radius / 50.0, radius / 50.0, height / 100.0), **kwargs)

    def text(self, label, text, location, rotation=(0, 0, 0), size=120.0, color=(208, 235, 239)):
        actor = self.actor(unreal.TextRenderActor, label, location, rotation, folder="Signage")
        component = actor.get_component_by_class(unreal.TextRenderComponent)
        component.set_text(text)
        component.set_world_size(size)
        component.set_text_render_color(unreal.Color(*color, 255))
        component.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
        component.set_vertical_alignment(unreal.VerticalTextAligment.EVRTA_TEXT_CENTER)
        return actor

    def setup_assets(self):
        for primitive in ("Cube", "Cylinder", "Sphere", "Cone"):
            self.meshes[primitive] = self.load_mesh("/Engine/BasicShapes/" + primitive)
        for name in ("SM_BB_LargeHoop", "SM_BB_SmallHoop", "SM_BB_CenterCircle", "SM_BB_ReboundNet", "SM_BB_Stars"):
            self.import_mesh(name)
        for spec in ARENA_PALETTE:
            self.material(*spec)
        path = ART_PATH + "/Materials/PM_BB_Rebound"
        self.physics = self.assets.load_asset(path)
        if self.physics is None:
            factory = unreal.PhysicalMaterialFactoryNew()
            factory.set_editor_property("physical_material_class", unreal.PhysicalMaterial)
            self.physics = self.asset_tools.create_asset("PM_BB_Rebound", ART_PATH + "/Materials", unreal.PhysicalMaterial, factory)
        if self.physics is None:
            raise RuntimeError("Could not create Basketbroom's rebound physical material")
        self.physics.set_editor_property("friction", 0.12)
        self.physics.set_editor_property("restitution", 0.75)
        self.physics.set_editor_property("override_restitution_combine_mode", True)
        self.physics.set_editor_property("restitution_combine_mode", unreal.FrictionCombineMode.MAX)
        self.assets.save_loaded_asset(self.physics)

    def floor(self):
        self.box("Trampoline - continuous rebound surface", "M_BB_Trampoline", (0, 0, -35),
                 (2 * BACKSTOP_X + 100, 2 * HALF_WIDTH + 100, 70), collision=True, tags=("BB.Floor", "BB.Rebound"), folder="Collision")
        self.box("Basalt foundation", "M_BB_Basalt", (0, 0, -220), (2 * BACKSTOP_X + 480, 2 * HALF_WIDTH + 520, 370))
        # Alternating broad strips retain the visual unity of one trampoline.
        for i in range(-6, 7):
            if i % 2 == 0:
                self.box("Court weave %02d" % i, "M_BB_FloorAlternate", (i * 975, 0, 0.6), (970, 2 * HALF_WIDTH - 160, 0.8))
        self.box("Midfield stripe", "M_BB_Cream", (0, 0, 2), (9, 2 * HALF_WIDTH - 100, 2))
        self.shape("Center court ring", "SM_BB_CenterCircle", "M_BB_Cream", (0, 0, 7), rotation=(90, 0, 0))
        self.cylinder("Center medallion", "M_BB_Copper", (0, 0, 2), 180, 3)
        for side in (-1, 1):
            mat = "M_BB_TealLight" if side < 0 else "M_BB_CopperLight"
            self.box("Sideline ribbon %s" % side, "M_BB_TealLight", (0, side * (HALF_WIDTH - 40), 4), (2 * BACKSTOP_X, 7, 5))
            self.box("Goal line %s" % side, mat, (side * HALF_LENGTH, 0, 4), (10, 2 * HALF_WIDTH - 80, 5))
            self.box("Attacking third %s" % side, "M_BB_Cream", (side * 3600, 0, 2), (6, 2 * HALF_WIDTH - 100, 2))
            self.box("Goal bay accent %s" % side, mat, (side * (HALF_LENGTH - 900), 0, 4), (10, 3600, 4))
            for y in (-1800, 1800):
                self.box("Goal bay edge %s %s" % (side, y), mat, (side * (HALF_LENGTH - 450), y, 4), (900, 7, 4))
            for index in range(9):
                x = (index - 4) * 1350
                self.box("Boundary marker %s %s" % (side, index), "M_BB_Cream", (x, side * (HALF_WIDTH - 110), 4), (10, 130, 4))
                self.box("Deck inset %s %s" % (side, index), "M_BB_IvoryLight", (x, side * (HALF_WIDTH + 145), -18), (360, 12, 15))

    def goals(self):
        for side, team in ((-1, "Teal"), (1, "Copper")):
            x = side * HALF_LENGTH
            mat = "M_BB_" + team
            glow = mat + "Light"
            for i, y in enumerate((-GOAL_SPACING, 0, GOAL_SPACING)):
                label = "%s large hoop %s" % (team, i)
                self.shape(label, "SM_BB_LargeHoop", glow, (x, y, LARGE_CENTER), tags=("BB.Goal", "BB.Goal.Large", "BB.Team." + team), folder="Goals")
                # Component collision uses external segmented padding, never a
                # convex hull that would invisibly cap the scoring aperture.
                for segment in range(64):
                    angle = segment * 2 * math.pi / 64
                    radius = LARGE_RADIUS + 21
                    py = y + radius * math.cos(angle)
                    pz = LARGE_CENTER + radius * math.sin(angle)
                    self.shape(label + " rim padding %02d" % segment, "Sphere", mat, (x, py, pz),
                               (0.43, 0.43, 0.43), collision=True, tags=("BB.Goal.Rim", "BB.Rebound"), folder="Goals/Rim collision")
                support_x = x + side * 120
                self.cylinder(label + " tower", "M_BB_Iron", (support_x, y, LARGE_CENTER / 2 - 90), 24, LARGE_CENTER - 180,
                              collision=True, tags=("BB.Support", "BB.Rebound"), folder="Goals")
                self.cylinder(label + " impact sleeve", mat, (support_x, y, 300), 54, 600, collision=True, folder="Goals")
                self.cylinder(label + " foundation", "M_BB_Basalt", (support_x, y, 50), 160, 100, collision=True, folder="Goals")
                self.box(label + " vertical light", glow, (support_x - side * 28, y, 670), (7, 15, 730), folder="Goals")
            self.shape(team + " elevated quark hoop", "SM_BB_SmallHoop", "M_BB_IvoryLight", (x, 0, SMALL_CENTER),
                       tags=("BB.Goal", "BB.Goal.Small", "BB.Team." + team), folder="Goals")
            for segment in range(48):
                a = segment * 2 * math.pi / 48
                radius = SMALL_RADIUS + 16
                self.shape(team + " quark rim padding %02d" % segment, "Sphere", mat,
                           (x, radius * math.cos(a), SMALL_CENTER + radius * math.sin(a)), (0.33, 0.33, 0.33),
                           collision=True, tags=("BB.Goal.Rim", "BB.Rebound"), folder="Goals/Rim collision")
            self.cylinder(team + " elevated mast", "M_BB_Iron", (x + side * 175, 0, SMALL_CENTER / 2), 19, SMALL_CENTER, collision=True, folder="Goals")
            self.box(team + " goals nameplate", "M_BB_Iron", (x + side * 220, 0, 3680), (70, 2500, 430), folder="Signage")
            self.text(team + " end identity", "B A S K E T B R O O M", (x + side * 174, 0, 3730),
                      rotation=(0, 180 if side > 0 else 0, 0), size=155, color=(232, 191, 122))
            self.text(team + " hoop values", "LARGE 13   |   HIGH 37", (x - side * 50, 0, 1260),
                      rotation=(0, 180 if side > 0 else 0, 0), size=94, color=(225, 182, 112))

    def net_and_crown(self):
        self.actor(unreal.TargetPoint, "No Crown reference plane", (0, 0, ROOFLINE),
                   tags=("BB.Roofline", "BB.NoCrown.Plane"), folder="Gameplay anchors")
        self.shape("Continuous open-crown rebound net", "SM_BB_ReboundNet", "M_BB_Net", (0, 0, 0), folder="Nets")
        for side in (-1, 1):
            net = self.box("End net collision %s" % side, "M_BB_Iron", (side * (BACKSTOP_X + 15), 0, ROOFLINE / 2),
                           (30, 2 * HALF_WIDTH, ROOFLINE), collision=True,
                           tags=("BB.Net", "BB.Net.End", "BB.Rebound"), folder="Collision")
            net.set_actor_hidden_in_game(True)
            net.static_mesh_component.set_visibility(False)
            net = self.box("Side net collision %s" % side, "M_BB_Iron", (0, side * (HALF_WIDTH + 15), ROOFLINE / 2),
                           (2 * BACKSTOP_X, 30, ROOFLINE), collision=True,
                           tags=("BB.Net", "BB.Net.Side", "BB.Rebound"), folder="Collision")
            net.set_actor_hidden_in_game(True)
            net.static_mesh_component.set_visibility(False)
            for z, thickness, material in ((75, 35, "M_BB_Iron"), (ROOFLINE, 12, "M_BB_IvoryLight")):
                self.box("Side tension rail %s %s" % (side, z), material, (0, side * HALF_WIDTH, z), (2 * BACKSTOP_X, thickness, thickness), folder="Nets")
                self.box("End tension rail %s %s" % (side, z), material, (side * BACKSTOP_X, 0, z), (thickness, 2 * HALF_WIDTH, thickness), folder="Nets")
            for index in range(9):
                x = -BACKSTOP_X + index * BACKSTOP_X / 4
                y = side * (HALF_WIDTH + 35)
                self.cylinder("Net mast %s %s" % (side, index), "M_BB_Iron", (x, y, ROOFLINE / 2), 20, ROOFLINE, folder="Nets")
                self.cylinder("Mast copper base %s %s" % (side, index), "M_BB_Copper", (x, y, 210), 38, 420, folder="Nets")
                self.shape("Crown beacon %s %s" % (side, index), "Sphere", "M_BB_IvoryLight", (x, y, ROOFLINE + 40), (0.42, 0.42, 0.42), folder="Nets")

    def stands(self):
        for side in (-1, 1):
            for tier in range(5):
                y = side * (HALF_WIDTH + 350 + tier * 280)
                z = -30 + tier * 150
                self.box("Gallery tier %s %s" % (side, tier), "M_BB_Basalt", (0, y, z), (12200, 275, 160))
                self.box("Gallery copper lip %s %s" % (side, tier), "M_BB_Copper", (0, y - side * 115, z + 80), (12200, 18, 12))
                for section in range(-5, 6):
                    # Empty bleachers, with clear geometric sections and aisles.
                    self.box("Gallery bench %s %s %s" % (side, tier, section), "M_BB_Teal" if section < 0 else "M_BB_Copper",
                             (section * 1060, y, z + 105), (880, 86, 42))
            for index in range(-4, 5):
                x = index * 1450
                y = side * (HALF_WIDTH + 1960)
                self.box("Gallery buttress %s %s" % (side, index), "M_BB_Iron", (x, y, 840), (130, 170, 2100))
                self.box("Gallery pennant %s %s" % (side, index), "M_BB_Teal" if x < 0 else "M_BB_Copper", (x, y - side * 110, 1680), (340, 18, 620))
                self.shape("Gallery finial %s %s" % (side, index), "Cone", "M_BB_Copper", (x, y, 2080), (1.5, 1.5, 3.7))
                self.shape("Gallery lantern %s %s" % (side, index), "Sphere", "M_BB_IvoryLight", (x, y, 2240), (0.60, 0.60, 0.60))
        # The approach gives the venue a front door and an intentional silhouette.
        for side in (-1, 1):
            x = side * (BACKSTOP_X + 620)
            for y in (-2300, 2300):
                self.box("Gate pier %s %s" % (side, y), "M_BB_Basalt", (x, y, 540), (480, 480, 1350))
                self.box("Gate inset %s %s" % (side, y), "M_BB_Copper", (x - side * 248, y, 620), (14, 280, 1050))
                self.shape("Gate flame %s %s" % (side, y), "Sphere", "M_BB_IvoryLight", (x, y, 1250), (1.4, 1.4, 1.4))
        self.box("South grandstand identity slab", "M_BB_Iron", (0, -HALF_WIDTH - 2020, 1500), (3800, 100, 620), folder="Signage")
        self.text("Venue title", "B A S K E T B R O O M", (0, -HALF_WIDTH - 1958, 1600), (0, 90, 0), 198, (232, 191, 122))
        self.text("Venue subtitle", "T H E   R E B O U N D   G R O U N D S", (0, -HALF_WIDTH - 1958, 1340), (0, 90, 0), 83, (201, 169, 108))

    def scenery(self):
        """Original geometric scenery, kept outside the flying pitch envelope."""
        # Broad, overlapping shapes read as distant ridgelines in silhouette.
        # Dark unlit materials keep the surroundings below the court's contrast.
        for index in range(18):
            angle = index * math.tau / 18.0
            radius = 26700.0 + 1600.0 * math.sin(index * 2.3)
            height = 6300.0 + 2000.0 * math.sin(index * 1.7)
            self.shape("Distant ridge %02d" % index, "Cone", "M_BB_Ridge",
                       (radius * math.cos(angle), radius * math.sin(angle), height / 2.0 - 1600.0),
                       (130.0 + 25.0 * math.cos(index), 105.0, height / 100.0),
                       rotation=(0, index * 29.0, 0), tags=(SCENERY_TAG,), folder="Atmosphere/Scenery")
        for index in range(44):
            angle = index * math.tau / 44.0
            radius = 17200.0 + 1300.0 * math.sin(index * 2.7)
            x, y = radius * math.cos(angle), radius * math.sin(angle)
            height = 1550.0 + 500.0 * math.sin(index * 1.3)
            self.shape("Distant pine %02d" % index, "Cone", "M_BB_Pine",
                       (x, y, height / 2.0 - 570.0),
                       (height / 165.0, height / 165.0, height / 100.0),
                       tags=(SCENERY_TAG,), folder="Atmosphere/Scenery")

    def lighting(self):
        self.shape("Twilight dome", "Sphere", "M_BB_Sky", (0, 0, 0), (850, 850, 850), folder="Atmosphere")
        self.shape("Distant stars", "SM_BB_Stars", "M_BB_Stars", (0, 0, 0), folder="Atmosphere")
        self.box("Ground horizon", "M_BB_Ground", (0, 0, -670), (160000, 160000, 200), folder="Atmosphere")
        key = self.actor(unreal.DirectionalLight, "Twilight amber key", (0, 0, 10000), (-28, -38, 0), folder="Lighting")
        light = key.get_component_by_class(unreal.DirectionalLightComponent)
        light.set_mobility(unreal.ComponentMobility.MOVABLE)
        light.set_intensity(3.0)
        light.set_light_color(unreal.LinearColor(1.0, 0.78, 0.55, 1.0))
        _optional(light, "dynamic_shadow_distance_movable_light", 22000.0)
        sky = self.actor(unreal.SkyLight, "Blue twilight ambience", (0, 0, 9000), folder="Lighting")
        sky_component = sky.get_component_by_class(unreal.SkyLightComponent)
        sky_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        sky_component.set_intensity(2.2)
        _optional(sky_component, "lower_hemisphere_is_black", False)
        sky_component.recapture_sky()
        fog = self.actor(unreal.ExponentialHeightFog, "Aerial depth", (0, 0, -800), folder="Atmosphere")
        fog_component = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
        fog_component.set_fog_density(0.0035)
        fog_component.set_fog_height_falloff(0.17)
        fog_component.set_fog_inscattering_color(unreal.LinearColor(0.032, 0.066, 0.105, 1.0))
        for index, x in enumerate((-4400, 0, 4400)):
            for side in (-1, 1):
                lamp = self.actor(unreal.PointLight, "Court flood %s %s" % (side, index), (x, side * 2500, 3500), folder="Lighting")
                component = lamp.get_component_by_class(unreal.PointLightComponent)
                component.set_mobility(unreal.ComponentMobility.MOVABLE)
                component.set_intensity(COURT_FLOOD_INTENSITY)
                component.set_attenuation_radius(6000.0)
                component.set_light_color(unreal.LinearColor(0.52, 0.73, 1.0, 1.0))
                component.set_cast_shadows(False)
        # Keep presentation exposure stable across the dark dome and bright rims.
        pp = self.actor(unreal.PostProcessVolume, "Arena presentation", folder="Lighting")
        pp.set_editor_property("unbound", True)
        settings = pp.get_editor_property("settings")
        for name, value in (("override_auto_exposure_min_brightness", True),
                            ("override_auto_exposure_max_brightness", True),
                            ("auto_exposure_min_brightness", EXPOSURE_BRIGHTNESS),
                            ("auto_exposure_max_brightness", EXPOSURE_BRIGHTNESS),
                            ("override_bloom_intensity", True), ("bloom_intensity", BLOOM_INTENSITY),
                            ("override_vignette_intensity", True), ("vignette_intensity", 0.22)):
            _optional(settings, name, value)
        pp.set_editor_property("settings", settings)

    def cameras(self):
        camera = self.actor(unreal.CameraActor, "BB Hero Camera", CAMERA_LOCATION, CAMERA_ROTATION,
                            tags=("BB.Camera.Hero",), folder="Cameras")
        camera.get_component_by_class(unreal.CameraComponent).set_field_of_view(58.0)
        self.actor(unreal.CameraActor, "BB Flight Camera", (-4400, -1300, 1500), (5, 14, 0), folder="Cameras")
        self.actor(unreal.PlayerStart, "BB Player Start", (-3000, 0, 300), (0, 0, 0), tags=("BB.Spawn",), folder="Gameplay anchors")
        self.levels.set_level_viewport_camera_info(
            unreal.Vector(*CAMERA_LOCATION),
            unreal.Rotator(pitch=CAMERA_ROTATION[0], yaw=CAMERA_ROTATION[1], roll=CAMERA_ROTATION[2]))

    def build(self):
        manifest = generate_source_meshes()
        if not self.assets.does_directory_exist(MOUNT) and not self.assets.make_directory(MOUNT):
            raise RuntimeError("Enable the Basketbroom content plugin before building the arena.")
        for path in (MOUNT + "/Maps", ART_PATH + "/Meshes", ART_PATH + "/Materials"):
            self.assets.make_directory(path)
        if self.assets.does_asset_exist(LEVEL_PATH):
            if not self.levels.load_level(LEVEL_PATH):
                raise RuntimeError("Could not load " + LEVEL_PATH)
        elif not self.levels.new_level(LEVEL_PATH):
            raise RuntimeError("Could not create " + LEVEL_PATH)
        # Preserve authored gameplay actors on subsequent visual rebuilds.
        for actor in self.levels.get_all_level_actors():
            if actor.actor_has_tag(GENERATED_TAG):
                self.levels.destroy_actor(actor)
        self.setup_assets()
        self.floor()
        self.goals()
        self.net_and_crown()
        self.stands()
        self.scenery()
        self.lighting()
        self.cameras()
        if not self.levels.save_current_level():
            raise RuntimeError("Arena map failed to save")
        self.assets.save_directory(ART_PATH, only_if_is_dirty=True, recursive=True)
        manifest["generated_actor_count"] = len(self.actors)
        unreal.log("BASKETBROOM_ARENA_BUILD_COMPLETE " + json.dumps(manifest, sort_keys=True))
        return manifest


def build():
    if unreal is None:
        raise RuntimeError("build() must run in the Unreal/Creator Kit editor Python environment")
    return ArenaBuilder().build()


if __name__ == "__main__":
    if unreal is not None:
        build()
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--generate-source", action="store_true", help="Generate original OBJ sources without launching Unreal")
        args = parser.parse_args()
        if args.generate_source:
            print(json.dumps(generate_source_meshes(), indent=2))
        else:
            parser.error("Use --generate-source outside the Unreal editor")

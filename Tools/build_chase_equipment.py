"""Author original decorative chase-ball wings; no physics or rule changes.

Outside Unreal, --generate-source writes four deterministic centimeter OBJ files.
The editor bridge may explicitly request operation=build with PIE stopped.
Only these owned meshes are imported/saved; no map or other asset is saved.
"""
from pathlib import Path
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "SourceArt/Equipment"
MOUNT = "/Basketbroom/Art/Equipment"
GENERATOR = "Basketbroom.ChaseWings.v1"


def wing(span, chord, side):
    vertices, faces = [], []

    def blade(start, end, width):
        # Closed, shallow lenticular foil with a tapered, rounded silhouette.
        axis = [end[i] - start[i] for i in range(3)]
        length = math.sqrt(sum(v*v for v in axis))
        lateral = (-axis[1]/length, axis[0]/length, 0)
        rings = []
        for t, size in ((0, .28), (.15, .85), (.5, 1), (.84, .65), (1, .025)):
            ring = []
            for k in range(8):
                angle = math.tau*k/8
                point = [start[i] + axis[i]*t + lateral[i]*math.cos(angle)*width*size for i in range(3)]
                point[2] += math.sin(angle)*1.15*size
                vertices.append((point[0], point[1]*side, point[2]))
                ring.append(len(vertices))
            rings.append(ring)
        for a, b in zip(rings, rings[1:]):
            for k in range(8):
                faces.append((a[k], a[(k+1)%8], b[(k+1)%8], b[k]))
        faces.extend((tuple(reversed(rings[0])), tuple(rings[-1])))

    # Swept leading spar with individually separated trailing vanes.
    blade((0, 0, 0), (12, span, 3), 3.4)
    for index in range(8):
        t = .13 + index*.107
        y = span*t
        reach = chord*(1-.48*t)
        blade((12*t-1.5, y, 1.5*t), (-reach, min(span+7, y+span*.21), -1.0+3*t), 3.8)
    if side < 0:
        faces = [tuple(reversed(face)) for face in faces]
    return vertices, faces


def generate_source():
    SOURCE.mkdir(parents=True, exist_ok=True)
    assets = []
    for kind, span, chord in (("Snipe", 76, 34), ("Snitch", 98, 23)):
        for label, side in (("Left", -1), ("Right", 1)):
            name = "SM_BB_" + kind + "Wing" + label
            # UE's legacy OBJ importer always reflects source Y when moving
            # from right-handed OBJ coordinates to Unreal's coordinate system,
            # even with convert_scene disabled. Author the inverse here so each
            # named wing extends outward from its native +/-Y hinge.
            vertices, faces = wing(span, chord, -side)
            path = SOURCE / (name + ".obj")
            lines = ["# Original Basketbroom wing; centimeters, Z up; Unreal Y = -OBJ Y", "o " + name, "s 1"]
            lines.extend("v %.6f %.6f %.6f" % point for point in vertices)
            lines.extend("f " + " ".join(str(i) for i in face) for face in faces)
            path.write_text("\n".join(lines) + "\n", encoding="ascii")
            assets.append({"name": name, "file": str(path), "vertices": len(vertices),
                           "polygons": len(faces), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "bounds_cm": [[min(p[i] for p in vertices) for i in range(3)],
                                         [max(p[i] for p in vertices) for i in range(3)]]})
    manifest = {"generator": GENERATOR, "original_geometry": True, "decorative_only": True,
                "physics_radius_unchanged": True, "assets": assets}
    (SOURCE / "chase_equipment_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest


def build():
    import unreal as ue
    if not ue.SystemLibrary.get_engine_version().startswith("5.8."):
        raise RuntimeError("Chase wing authoring requires UE5.8")
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())).resolve()
    if project != (ROOT / "DevelopmentHarness").resolve():
        raise RuntimeError("Open the exact BasketbroomDev project")
    if ue.get_editor_subsystem(ue.LevelEditorSubsystem).is_in_play_in_editor():
        raise RuntimeError("Stop PIE before importing chase equipment")
    manifest = generate_source()
    for row in manifest["assets"]:
        package = MOUNT + "/" + row["name"]
        if ue.EditorAssetLibrary.does_asset_exist(package):
            existing = ue.EditorAssetLibrary.load_asset(package)
            if ue.EditorAssetLibrary.get_metadata_tag(existing, "BB.Generator") != GENERATOR:
                raise RuntimeError("Refusing to replace an unowned mesh: " + package)
    saved = []
    for row in manifest["assets"]:
        task = ue.AssetImportTask()
        for key, value in {"filename": row["file"], "destination_path": MOUNT,
                           "destination_name": row["name"], "automated": True,
                           "replace_existing": True, "save": False}.items():
            task.set_editor_property(key, value)
        task.set_editor_property("factory", ue.FbxFactory())
        options = ue.FbxImportUI()
        for key, value in {"import_mesh": True, "import_materials": False, "import_textures": False,
                           "import_as_skeletal": False, "mesh_type_to_import": ue.FBXImportType.FBXIT_STATIC_MESH}.items():
            options.set_editor_property(key, value)
        data = options.get_editor_property("static_mesh_import_data")
        for key, value in {"combine_meshes": True, "auto_generate_collision": False,
                           "convert_scene": False, "convert_scene_unit": False,
                           "normal_import_method": ue.FBXNormalImportMethod.FBXNIM_COMPUTE_NORMALS}.items():
            data.set_editor_property(key, value)
        task.set_editor_property("options", options)
        ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        package = MOUNT + "/" + row["name"]
        mesh = ue.EditorAssetLibrary.load_asset(package)
        if not isinstance(mesh, ue.StaticMesh):
            raise RuntimeError("Original chase wing import failed: " + package)
        ue.EditorAssetLibrary.set_metadata_tag(mesh, "BB.Generator", GENERATOR)
        ue.EditorAssetLibrary.set_metadata_tag(mesh, "BB.SourceSHA256", row["sha256"])
        if not ue.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False):
            raise RuntimeError("Could not save chase wing: " + package)
        saved.append(package)
    result = {"status": "imported_pending_render", "meshes": saved, "maps_saved": 0,
              "collision_generated": False, "runtime_visual_validation": "not_run"}
    (ROOT / ".local/chase-equipment-staging.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    args = globals().get("BRIDGE_ARGS", {})
    if args.get("operation") == "build":
        RESULT = build()
    elif "--generate-source" in sys.argv:
        RESULT = generate_source()
        print(json.dumps({"status": "source_generated", "assets": len(RESULT["assets"])}))
    else:
        RESULT = {"status": "not_run", "required_operation": "build"}

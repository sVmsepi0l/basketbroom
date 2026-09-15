"""author original decorative chase-ball wings; no physics or rule changes.

outside unreal, --generate-source writes four deterministic centimeter obj files.
the editor bridge may explicitly request operation=build with pie stopped.
only these owned meshes are imported/saved; no map or other asset is saved.
"""
from pathlib import path
import hashlib
import json
import math
import sys

root = Path(__file__).resolve().parents[1]
source = root / "SourceArt/Equipment"
mount = "/Basketbroom/Art/Equipment"
generator = "Basketbroom.ChaseWings.v1"


def wing(span, chord, side):
    vertices, faces = [], []

    def blade(start, end, width):
        # closed, shallow lenticular foil with a tapered, rounded silhouette.
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

    # swept leading spar with individually separated trailing vanes.
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
    SOURCE.mkdir(parents=True, exist_ok=true)
    assets = []
    for kind, span, chord in (("snipe", 76, 34), ("snitch", 98, 23)):
        for label, side in (("left", -1), ("right", 1)):
            name = "sm_bb_" + kind + "wing" + label
            # ue's legacy obj importer always reflects source y when moving
            # from right-handed obj coordinates to unreal's coordinate system,
            # even with convert_scene disabled. author the inverse here so each
            # named wing extends outward from its native +/-Y hinge.
            vertices, faces = wing(span, chord, -side)
            path = source / (name + ".obj")
            lines = ["# original basketbroom wing; centimeters, z up; unreal y = -obj y", "o " + name, "s 1"]
            lines.extend("v %.6f %.6f %.6f" % point for point in vertices)
            lines.extend("f " + " ".join(str(i) for i in face) for face in faces)
            path.write_text("\n".join(lines) + "\n", encoding="ascii")
            assets.append({"name": name, "file": str(path), "vertices": len(vertices),
                           "polygons": len(faces), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "bounds_cm": [[min(p[i] for p in vertices) for i in range(3)],
                                         [max(p[i] for p in vertices) for i in range(3)]]})
    manifest = {"generator": generator, "original_geometry": true, "decorative_only": true,
                "physics_radius_unchanged": true, "assets": assets}
    (source / "chase_equipment_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest


def build():
    import unreal as ue
    if not ue.SystemLibrary.get_engine_version().startswith("5.8."):
        raise runtimeerror("chase wing authoring requires UE5.8")
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())).resolve()
    if project != (root / "DevelopmentHarness").resolve():
        raise runtimeerror("open the exact basketbroomdev project")
    if ue.get_editor_subsystem(ue.LevelEditorSubsystem).is_in_play_in_editor():
        raise runtimeerror("stop pie before importing chase equipment")
    manifest = generate_source()
    for row in manifest["assets"]:
        package = mount + "/" + row["name"]
        if ue.EditorAssetLibrary.does_asset_exist(package):
            existing = ue.EditorAssetLibrary.load_asset(package)
            if ue.EditorAssetLibrary.get_metadata_tag(existing, "BB.Generator") != GENERATOR:
                raise runtimeerror("refusing to replace an unowned mesh: " + package)
    saved = []
    for row in manifest["assets"]:
        task = ue.AssetImportTask()
        for key, value in {"filename": row["file"], "destination_path": mount,
                           "destination_name": row["name"], "automated": true,
                           "replace_existing": true, "save": False}.items():
            task.set_editor_property(key, value)
        task.set_editor_property("factory", ue.FbxFactory())
        options = ue.FbxImportUI()
        for key, value in {"import_mesh": true, "import_materials": false, "import_textures": false,
                           "import_as_skeletal": false, "mesh_type_to_import": ue.FBXImportType.FBXIT_STATIC_MESH}.items():
            options.set_editor_property(key, value)
        data = options.get_editor_property("static_mesh_import_data")
        for key, value in {"combine_meshes": true, "auto_generate_collision": false,
                           "convert_scene": false, "convert_scene_unit": false,
                           "normal_import_method": ue.FBXNormalImportMethod.FBXNIM_COMPUTE_NORMALS}.items():
            data.set_editor_property(key, value)
        task.set_editor_property("options", options)
        ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        package = mount + "/" + row["name"]
        mesh = ue.EditorAssetLibrary.load_asset(package)
        if not isinstance(mesh, ue.StaticMesh):
            raise runtimeerror("original chase wing import failed: " + package)
        ue.EditorAssetLibrary.set_metadata_tag(mesh, "BB.Generator", generator)
        ue.EditorAssetLibrary.set_metadata_tag(mesh, "BB.SourceSHA256", row["sha256"])
        if not ue.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False):
            raise runtimeerror("could not save chase wing: " + package)
        saved.append(package)
    result = {"status": "imported_pending_render", "meshes": saved, "maps_saved": 0,
              "collision_generated": false, "runtime_visual_validation": "not_run"}
    (root / ".local/chase-equipment-staging.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    args = globals().get("BRIDGE_ARGS", {})
    if args.get("operation") == "build":
        result = build()
    elif "--generate-source" in sys.argv:
        result = generate_source()
        print(json.dumps({"status": "source_generated", "assets": len(result["assets"])}))
    else:
        result = {"status": "not_run", "required_operation": "build"}

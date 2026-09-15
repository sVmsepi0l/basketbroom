"""Stage only the eight original cosmetic equipment meshes and four materials.

Editor bridge: stage_broom_equipment.py {"operation": "build"}
Requires this repository's UE5.8 DevelopmentHarness and stopped, clean editor.
No actor edits, map saves, external assets, physics changes or Creator Kit writes.
Owned assets are backed up locally before reimport. This reports asset checks;
actual owner/remote rendered validation is a separate, required runtime check.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import traceback

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "DevelopmentHarness/Plugins/Basketbroom/Content"
_spec = importlib.util.spec_from_file_location("basketbroom_flight_equipment", ROOT / "Tools/build_broom_equipment.py")
source = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(source)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def require_clean(ue):
    saving = ue.EditorLoadingAndSavingUtils
    dirty = [p.get_path_name() for p in list(saving.get_dirty_map_packages()) + list(saving.get_dirty_content_packages())]
    if dirty:
        raise RuntimeError("Preserving unsaved work; staging requires clean packages: " + ", ".join(dirty))


def map_hashes():
    return {p.relative_to(CONTENT).as_posix(): sha(p) for p in sorted((CONTENT / "Maps").rglob("*.umap"))}


def create_material(ue, specification):
    name = specification["name"]
    path = source.MOUNT + "/" + name
    assets = ue.EditorAssetLibrary
    material = assets.load_asset(path) if assets.does_asset_exist(path) else None
    if material is None:
        material = ue.AssetToolsHelpers.get_asset_tools().create_asset(name, source.MOUNT, ue.Material, ue.MaterialFactoryNew())
    if not isinstance(material, ue.Material): raise RuntimeError("Could not create owned material " + path)
    # Tag newly created in-memory assets immediately so a failed shader edit
    # remains attributable to this authoring tool without claiming a saved pass.
    assets.set_metadata_tag(material, "BB.Generator", source.GENERATOR)
    lib = ue.MaterialEditingLibrary
    lib.delete_all_material_expressions(material)
    material.set_editor_property("two_sided", False)
    material.set_editor_property("shading_model", ue.MaterialShadingModel.MSM_DEFAULT_LIT)
    # All surface detail is mesh-local UV math, so wood grain cannot swim while
    # the broom flies. No texture streaming or world-position noise is required.
    def node(cls, x=-500, y=0, **props):
        expression = lib.create_material_expression(material, cls, x, y)
        if expression is None: raise RuntimeError("Cannot create equipment material node")
        for key, value in props.items(): expression.set_editor_property(key, value)
        return expression
    def wire(a, b, pin=""):
        if not lib.connect_material_expressions(a, "", b, pin):
            raise RuntimeError("Equipment material connection failed: " + str(lib.get_material_expression_input_names(b)))
    def output(expression, prop):
        if not lib.connect_material_property(expression, "", prop):
            raise RuntimeError("Equipment material output connection failed")
    tint = node(ue.MaterialExpressionVectorParameter, x=-650, y=-160, parameter_name="Tint",
                default_value=ue.LinearColor(*specification["color"], 1.))
    uv = node(ue.MaterialExpressionTextureCoordinate, x=-1500, y=160)
    across = node(ue.MaterialExpressionComponentMask, x=-1300, y=120, r=True, g=False, b=False, a=False)
    along = node(ue.MaterialExpressionComponentMask, x=-1300, y=300, r=False, g=True, b=False, a=False)
    wire(uv, across); wire(uv, along)
    long_scale = node(ue.MaterialExpressionMultiply, x=-1150, y=300, const_b=.22)
    wire(along, long_scale, "A")
    long_wave = node(ue.MaterialExpressionSine, x=-1000, y=300, period=1.)
    wire(long_scale, long_wave)
    wobble = node(ue.MaterialExpressionMultiply, x=-850, y=300, const_b=.012)
    wire(long_wave, wobble, "A")
    phase = node(ue.MaterialExpressionAdd, x=-1100, y=100)
    wire(across, phase, "A"); wire(wobble, phase, "B")
    frequency = node(ue.MaterialExpressionMultiply, x=-900, y=100, const_b=19.)
    wire(phase, frequency, "A")
    grain = node(ue.MaterialExpressionSine, x=-720, y=100, period=1.)
    wire(frequency, grain)
    amplitude = node(ue.MaterialExpressionMultiply, x=-550, y=100, const_b=specification["grain"])
    wire(grain, amplitude, "A")
    value = node(ue.MaterialExpressionAdd, x=-390, y=100, const_b=1.-specification["grain"]*.3)
    wire(amplitude, value, "A")
    base = node(ue.MaterialExpressionMultiply, x=-190, y=-50)
    wire(tint, base, "A"); wire(value, base, "B")
    output(base, ue.MaterialProperty.MP_BASE_COLOR)
    for index, (label, scalar, prop) in enumerate((
            ("Roughness", specification["roughness"], ue.MaterialProperty.MP_ROUGHNESS),
            ("Metallic", specification["metallic"], ue.MaterialProperty.MP_METALLIC),
            ("Specular", .30, ue.MaterialProperty.MP_SPECULAR))):
        expression = node(ue.MaterialExpressionScalarParameter, x=-190, y=250+index*120,
                          parameter_name=label, default_value=scalar)
        output(expression, prop)
    lib.recompile_material(material)
    assets.set_metadata_tag(material, "BB.Generator", source.GENERATOR)
    assets.set_metadata_tag(material, "BB.SourceSHA256", hashlib.sha256(
        json.dumps(specification, sort_keys=True).encode()).hexdigest())
    if not assets.save_loaded_asset(material, only_if_is_dirty=False): raise RuntimeError("Could not save " + path)
    return material


def build():
    import unreal as ue
    if not ue.SystemLibrary.get_engine_version().startswith("5.8."):
        raise RuntimeError("Flight equipment staging requires Unreal 5.8")
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())).resolve()
    if project != (ROOT / "DevelopmentHarness").resolve():
        raise RuntimeError("Refusing to stage outside this repository's DevelopmentHarness")
    if ue.get_editor_subsystem(ue.LevelEditorSubsystem).is_in_play_in_editor():
        raise RuntimeError("Stop PIE before importing equipment")
    require_clean(ue)
    api = ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem)
    for method in ("get_simple_collision_count", "remove_collisions"):
        if not callable(getattr(api, method, None)):
            raise RuntimeError("Required public StaticMeshEditorSubsystem API unavailable: " + method)
    for method in ("get_bounding_box", "get_num_triangles", "get_num_sections"):
        if not callable(getattr(ue.StaticMesh, method, None)):
            raise RuntimeError("Required public StaticMesh audit API unavailable: " + method)
    manifest = source.generate_source()
    assets = ue.EditorAssetLibrary
    planned = [(source.MOUNT+"/"+row["name"], ue.StaticMesh) for row in manifest["assets"]]
    planned += [(source.MOUNT+"/"+row["name"], ue.Material) for row in manifest["materials"].values()]
    # Preflight every destination before mutating even the first package.
    for path, expected_class in planned:
        if assets.does_asset_exist(path):
            existing = assets.load_asset(path)
            if not isinstance(existing, expected_class) or assets.get_metadata_tag(existing, "BB.Generator") != source.GENERATOR:
                raise RuntimeError("Refusing to overwrite an unowned equipment asset: " + path)
    teal = assets.load_asset("/Basketbroom/Art/Materials/M_BB_RiderTeal")
    if not isinstance(teal, ue.MaterialInterface): raise RuntimeError("Existing team material is missing")
    before_maps = map_hashes()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    directory = ROOT / ".local/broom-equipment-stage" / stamp
    backups = directory / "backups"
    backups.mkdir(parents=True)
    for path, _ in planned:
        disk = CONTENT / (path.removeprefix("/Basketbroom/")+".uasset")
        if disk.exists():
            backup = backups / disk.relative_to(CONTENT)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(disk, backup)
    report = {"status": "staging", "utc": datetime.now(timezone.utc).isoformat(),
              "engine": ue.SystemLibrary.get_engine_version(), "project": str(project),
              "generator": source.GENERATOR, "generator_sha256": sha(ROOT / "Tools/build_broom_equipment.py"),
              "source_manifest_sha256": sha(source.SOURCE / "broom_equipment_manifest.json"),
              "source_checks": manifest["checks"], "maps_before": before_maps, "maps_saved": 0,
              "backup_directory": str(backups), "materials": [], "meshes": [],
              "rendered_validation": "not_run", "runtime_owner_collision_validation": "not_run"}
    def publish(): (directory / "result.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    publish()
    try:
        materials = {key: create_material(ue, spec) for key, spec in manifest["materials"].items()}
        materials["Team"] = teal
        for key, material in materials.items():
            if key == "Team": continue
            disk = CONTENT / "Art/Equipment" / (material.get_name()+".uasset")
            report["materials"].append({"path": material.get_path_name(), "sha256": sha(disk), "saved": True})
        for row in manifest["assets"]:
            task = ue.AssetImportTask()
            for key, value in {"filename": str(ROOT / row["file"]), "destination_path": source.MOUNT,
                               "destination_name": row["name"], "automated": True,
                               "replace_existing": True, "save": False}.items(): task.set_editor_property(key, value)
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
            path = source.MOUNT+"/"+row["name"]
            imported = [str(p).split(".")[0] for p in task.get_editor_property("imported_object_paths")]
            if imported != [path]: raise RuntimeError("Importer did not return exactly the owned target: " + str(imported))
            mesh = assets.load_asset(path)
            if not isinstance(mesh, ue.StaticMesh): raise RuntimeError("Equipment import failed: " + path)
            if api.get_simple_collision_count(mesh): api.remove_collisions(mesh)
            if api.get_simple_collision_count(mesh) != 0: raise RuntimeError("Cosmetic mesh contains simple collision")
            mesh.set_material(0, materials[row["material"]])
            sections = int(mesh.get_num_sections(0))
            triangles = int(mesh.get_num_triangles(0))
            if sections != 1 or triangles != row["triangles"]:
                raise RuntimeError("Imported topology differs from source: " + json.dumps({
                    "name": row["name"], "sections": sections, "triangles": triangles, "expected": row["triangles"]}))
            box = mesh.get_bounding_box()
            imported_bounds = [[box.min.x, box.min.y, box.min.z], [box.max.x, box.max.y, box.max.z]]
            bounds_error = max(abs(imported_bounds[i][j]-row["ue_bounds_cm"][i][j]) for i in range(2) for j in range(3))
            if bounds_error > .05: raise RuntimeError("Equipment importer altered axis, scale or bounds: " + row["name"])
            assets.set_metadata_tag(mesh, "BB.Generator", source.GENERATOR)
            assets.set_metadata_tag(mesh, "BB.SourceSHA256", row["sha256"])
            assets.set_metadata_tag(mesh, "BB.DecorativeOnly", "true")
            if not assets.save_loaded_asset(mesh, only_if_is_dirty=False): raise RuntimeError("Could not save " + path)
            disk = CONTENT / "Art/Equipment" / (row["name"]+".uasset")
            report["meshes"].append({"path": path, "source_sha256": row["sha256"], "asset_sha256": sha(disk),
                "triangles": triangles, "sections": sections, "simple_collision_shapes": 0,
                "bounds_cm": imported_bounds, "bounds_max_error_cm": bounds_error})
            publish()
        report["maps_after"] = map_hashes()
        if report["maps_after"] != before_maps: raise RuntimeError("An existing map file changed during equipment import")
        require_clean(ue)
        report["status"] = "staged_pending_runtime_review"
        report["map_files_unchanged"] = True
        publish()
    except Exception:
        report["status"] = "error"
        report["error"] = traceback.format_exc()
        report["maps_after"] = map_hashes()
        publish()
        raise
    return {"status": report["status"], "report": str(directory / "result.json"),
            "meshes": len(report["meshes"]), "materials": len(report["materials"]), "maps_saved": 0}


if __name__ == "__main__":
    args = globals().get("BRIDGE_ARGS", {})
    RESULT = build() if args.get("operation") == "build" else {"status": "not_run", "required_operation": "build"}

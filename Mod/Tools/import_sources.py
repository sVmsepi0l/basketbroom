"""Import original Basketbroom sources into the mounted UE4.27 Creator Kit mod.

Ordinary Python: python Mod/Tools/import_sources.py --validate-sources
Creator Kit Python: import import_sources; import_sources.build()

This authors content only. It neither launches an editor nor mounts a plugin,
creates gameplay Blueprints, runs Python at game time, or imports UE5 packages.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sources import digest, validate_source

MANIFEST = ROOT / "Mod" / "SourceData" / "port-manifest.json"
CONTENT = ROOT / "Mod" / "Basketbroom" / "Content"
REPORT = ROOT / ".local" / "hlck" / "import-result.json"
OWNER = "Basketbroom.HLCK.SourceImporter"
REVISION = "1"
META_OWNER = "BasketbroomImporter"
META_HASH = "BasketbroomSourceSHA256"
META_REVISION = "BasketbroomImporterRevision"
PREFIXES = {"StaticMesh": (".obj", "SourceArt/Arena/", "/Basketbroom/Art/Meshes/"),
            "SoundWave": (".wav", "SourceArt/Audio/", "/Basketbroom/Audio/"),
            "Texture2D": (".png", "SourceArt/Textures/", "/Basketbroom/Art/Textures/")}

# Portable defaults for the imported geometry, not a port of UE5 materials.
MATERIALS = {
    "M_BB_Basalt": ((0.15, 0.18, 0.20), 0.86, 0.0, 0.0),
    "M_BB_Ground": ((0.12, 0.16, 0.15), 0.93, 0.0, 0.0),
    "M_BB_Foliage": ((0.035, 0.09, 0.065), 0.9, 0.0, 0.0),
    "M_BB_Copper": ((0.62, 0.26, 0.085), 0.35, 0.8, 0.0),
    "M_BB_Iron": ((0.055, 0.07, 0.09), 0.42, 0.75, 0.0),
    "M_BB_Teal": ((0.025, 0.30, 0.27), 0.55, 0.2, 0.0),
    "M_BB_TealLight": ((0.10, 0.70, 0.60), 0.4, 0.1, 2.0),
    "M_BB_GoldLight": ((1.0, 0.55, 0.12), 0.4, 0.1, 2.0),
    "M_BB_White": ((0.76, 0.80, 0.73), 0.55, 0.0, 0.0),
}
MESH_MATERIALS = {
    "SM_BB_LargeHoop": "M_BB_Copper", "SM_BB_SmallHoop": "M_BB_Copper",
    "SM_BB_CenterCircle": "M_BB_White", "SM_BB_ReboundNet": "M_BB_Iron",
    "SM_BB_Stars": "M_BB_GoldLight", "SM_BB_Terrain": "M_BB_Ground",
    "SM_BB_Treeline": "M_BB_Foliage", "SM_BB_StoneDetail": "M_BB_Basalt",
    "SM_BB_CopperDetail": "M_BB_Copper", "SM_BB_IronDetail": "M_BB_Iron",
    "SM_BB_TealSeats": "M_BB_Teal", "SM_BB_CopperSeats": "M_BB_Copper",
    "SM_BB_LargeHoopLight": "M_BB_TealLight", "SM_BB_SmallHoopLight": "M_BB_GoldLight",
}


def checked_destination(path):
    if not re.fullmatch(r"/Basketbroom/(?:Art/(?:Meshes|Textures|Materials)|Audio)/[A-Za-z0-9_]+", path):
        raise ValueError("Refusing asset destination outside Basketbroom import folders: " + str(path))
    return path


def validate_sources():
    """Read-only preflight; usable without Unreal or an installed Creator Kit."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported source manifest schema")
    for key in ("rules", "arena"):
        source = (ROOT / manifest[key + "_source"]).resolve()
        source.relative_to(ROOT.resolve())
        if digest(source) != manifest[key + "_sha256"]:
            raise ValueError("Stale " + key + " manifest; run Mod/Tools/prepare_sources.py")
    arena = json.loads((ROOT / manifest["arena_source"]).read_text(encoding="utf-8"))
    expected_meshes = {entry["file"]: entry for entry in arena["meshes"]}
    found_meshes, destinations = set(), set()
    entries = manifest.get("source_imports", [])
    if not entries:
        raise ValueError("Source manifest has no imports")
    for entry in entries:
        asset_type = entry["asset_type"]
        if asset_type not in PREFIXES:
            raise ValueError("Unsupported import type: " + str(asset_type))
        extension, source_prefix, destination_prefix = PREFIXES[asset_type]
        source = (ROOT / entry["source"]).resolve()
        source.relative_to((ROOT / source_prefix).resolve())
        if source.suffix.lower() != extension or source.parent != (ROOT / source_prefix).resolve():
            raise ValueError("Unexpected source location: " + str(source))
        destination = checked_destination(entry["destination"])
        if destination != destination_prefix + source.stem or destination in destinations:
            raise ValueError("Duplicate or mismatched source destination: " + destination)
        destinations.add(destination)
        if digest(source) != entry["sha256"]:
            raise ValueError("Source changed; regenerate manifest before import: " + str(source))
        expected = expected_meshes.get(source.name) if asset_type == "StaticMesh" else None
        result = validate_source(source, asset_type, expected)
        if result != entry.get("validated"):
            raise ValueError("Source validation differs; regenerate manifest: " + str(source))
        if asset_type == "StaticMesh":
            found_meshes.add(source.name)
    if found_meshes != set(expected_meshes):
        raise ValueError("Import manifest must include every mesh in the current arena manifest")
    return manifest


def _editor():
    import unreal
    version = str(unreal.SystemLibrary.get_engine_version())
    if not re.match(r"^4\.27\.", version):
        raise RuntimeError("This importer requires Creator Kit UE4.27, got " + version)
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path()))
    if project.stem.lower() != "phoenix":
        raise RuntimeError("Run this helper in the Creator Kit Phoenix project")
    # A root-owned junction is accepted; resolving it must reach the separate
    # repo mod. Merely seeing an unrelated /Basketbroom mount is insufficient.
    mounted = project.parent / "Mods" / "Basketbroom"
    descriptor = mounted / "Basketbroom.uplugin"
    expected = ROOT / "Mod" / "Basketbroom" / "Basketbroom.uplugin"
    if not descriptor.is_file() or descriptor.resolve() != expected.resolve():
        raise RuntimeError("Mount repo Mod/Basketbroom at PhoenixGame/Mods/Basketbroom before importing")
    if (mounted / "Content").resolve() != CONTENT.resolve() or not CONTENT.is_dir():
        raise RuntimeError("Basketbroom Content does not resolve to the separate UE4 mod directory")
    if not unreal.EditorAssetLibrary.does_directory_exist("/Basketbroom"):
        raise RuntimeError("Basketbroom plugin is not mounted in this editor; restart after mounting it")
    for name in ("AssetImportTask", "AssetToolsHelpers", "FbxFactory", "FbxImportUI", "TextureFactory", "SoundFactory"):
        if not hasattr(unreal, name):
            raise RuntimeError("Required UE4.27 editor API unavailable: " + name)
    return unreal, version


def _journal(report):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REPORT)


def _owned(unreal, asset):
    if unreal.EditorAssetLibrary.get_metadata_tag(asset, META_OWNER) != OWNER:
        raise RuntimeError("Existing asset was not made by this importer; preserving it: " + asset.get_path_name())


def _save(unreal, asset, fingerprint):
    checked_destination(asset.get_path_name().split(".")[0])
    assets = unreal.EditorAssetLibrary
    assets.set_metadata_tag(asset, META_OWNER, OWNER)
    assets.set_metadata_tag(asset, META_HASH, fingerprint)
    assets.set_metadata_tag(asset, META_REVISION, REVISION)
    if not assets.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError("Failed to save " + asset.get_path_name())


def _import(unreal, entry, force=False):
    assets = unreal.EditorAssetLibrary
    destination = checked_destination(entry["destination"])
    asset_type = getattr(unreal, entry["asset_type"])
    existing = assets.load_asset(destination) if assets.does_asset_exist(destination) else None
    if existing is not None:
        if not isinstance(existing, asset_type):
            raise RuntimeError("Existing asset type mismatch: " + destination)
        _owned(unreal, existing)
        if not force and assets.get_metadata_tag(existing, META_HASH) == entry["sha256"] and assets.get_metadata_tag(existing, META_REVISION) == REVISION:
            return existing, "unchanged"
    folder, _, name = destination.rpartition("/")
    task = unreal.AssetImportTask()
    for key, value in (("filename", str(ROOT / entry["source"])), ("destination_path", folder),
                       ("destination_name", name), ("automated", True), ("replace_existing", True),
                       ("replace_existing_settings", True), ("save", False)):
        task.set_editor_property(key, value)
    if entry["asset_type"] == "StaticMesh":
        task.set_editor_property("factory", unreal.FbxFactory())
        options = unreal.FbxImportUI()
        for key, value in (("import_mesh", True), ("import_as_skeletal", False), ("import_materials", False),
                           ("import_textures", False), ("import_animations", False),
                           ("automated_import_should_detect_type", False),
                           ("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)):
            options.set_editor_property(key, value)
        data = options.get_editor_property("static_mesh_import_data")
        for key, value in (("combine_meshes", True), ("auto_generate_collision", False),
                           ("convert_scene", False), ("convert_scene_unit", False),
                           ("import_uniform_scale", 1.0), ("generate_lightmap_u_vs", False),
                           ("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_COMPUTE_NORMALS)):
            data.set_editor_property(key, value)
        task.set_editor_property("options", options)
    else:
        factory = unreal.TextureFactory() if entry["asset_type"] == "Texture2D" else unreal.SoundFactory()
        task.set_editor_property("factory", factory)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = [str(path) for path in task.get_editor_property("imported_object_paths")]
    if not paths or any(path.split(".")[0] != destination for path in paths):
        raise RuntimeError("Importer did not return the exact requested package: " + repr(paths))
    asset = assets.load_asset(destination)
    if asset is None or not isinstance(asset, asset_type) or asset.get_path_name().split(".")[0] != destination:
        raise RuntimeError("Import failed or returned wrong asset class: " + destination)
    # Mark before optional property setup, so retrying an interrupted import can
    # recognize its own in-memory asset. Only _save writes the package to disk.
    assets.set_metadata_tag(asset, META_OWNER, OWNER)
    if entry["asset_type"] == "Texture2D":
        asset.set_editor_property("srgb", True)
        asset.set_editor_property("max_texture_size", 2048)
    _save(unreal, asset, entry["sha256"])
    return asset, "imported"


def _material(unreal, name, values, texture, force=False):
    import hashlib
    path = checked_destination("/Basketbroom/Art/Materials/" + name)
    fingerprint = hashlib.sha256(json.dumps([REVISION, name, values], sort_keys=True).encode("utf-8")).hexdigest()
    assets, lib = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    material = assets.load_asset(path) if assets.does_asset_exist(path) else None
    if material is not None:
        if not isinstance(material, unreal.Material):
            raise RuntimeError("Existing material type mismatch: " + path)
        _owned(unreal, material)
        if not force and assets.get_metadata_tag(material, META_HASH) == fingerprint:
            return material, "unchanged"
    else:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, "/Basketbroom/Art/Materials", unreal.Material, unreal.MaterialFactoryNew())
        if material is None:
            raise RuntimeError("Material creation failed: " + path)
        assets.set_metadata_tag(material, META_OWNER, OWNER)
    lib.delete_all_material_expressions(material)
    material.set_editor_property("two_sided", True)

    def node(cls, **properties):
        result = lib.create_material_expression(material, cls, -600, 0)
        if result is None:
            raise RuntimeError("Material expression creation failed")
        for key, value in properties.items():
            result.set_editor_property(key, value)
        return result

    def wire(source, target, pin, output=""):
        if not lib.connect_material_expressions(source, output, target, pin):
            raise RuntimeError("Cannot connect material node: " + name + " / " + pin)

    def connect(source, property_name):
        if not lib.connect_material_property(source, "", getattr(unreal.MaterialProperty, property_name)):
            raise RuntimeError("Cannot connect material property: " + property_name)

    color, roughness, metallic, glow = values
    tint = node(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(*color, 1.0))
    base = tint
    if name == "M_BB_Basalt":
        # Original OBJ meshes have no artist UVs. Project along all three world
        # axes using vertex-normal weights; all nodes are stock UE4.27 classes.
        position = node(unreal.MaterialExpressionWorldPosition)
        uv_scale = node(unreal.MaterialExpressionMultiply, const_b=1.0 / 220.0)
        wire(position, uv_scale, "A")
        normal = node(unreal.MaterialExpressionVertexNormalWS)
        absolute = node(unreal.MaterialExpressionAbs)
        wire(normal, absolute, "")
        samples, weights = [], []
        for axes, axis in (((True, True, False), 2), ((True, False, True), 1), ((False, True, True), 0)):
            uv = node(unreal.MaterialExpressionComponentMask, r=axes[0], g=axes[1], b=axes[2], a=False)
            wire(uv_scale, uv, "")
            sample = node(unreal.MaterialExpressionTextureSample, texture=texture)
            wire(uv, sample, "")
            weight = node(unreal.MaterialExpressionComponentMask, r=axis == 0, g=axis == 1, b=axis == 2, a=False)
            wire(absolute, weight, "")
            weighted = node(unreal.MaterialExpressionMultiply)
            wire(sample, weighted, "A", "RGB"); wire(weight, weighted, "B")
            samples.append(weighted); weights.append(weight)

        def sum_three(items):
            first = node(unreal.MaterialExpressionAdd)
            wire(items[0], first, "A"); wire(items[1], first, "B")
            result = node(unreal.MaterialExpressionAdd)
            wire(first, result, "A"); wire(items[2], result, "B")
            return result

        blend = node(unreal.MaterialExpressionDivide)
        wire(sum_three(samples), blend, "A"); wire(sum_three(weights), blend, "B")
        base = node(unreal.MaterialExpressionMultiply)
        wire(blend, base, "A"); wire(tint, base, "B")
    connect(base, "MP_BASE_COLOR")
    connect(node(unreal.MaterialExpressionConstant, r=roughness), "MP_ROUGHNESS")
    connect(node(unreal.MaterialExpressionConstant, r=metallic), "MP_METALLIC")
    if glow:
        emissive = node(unreal.MaterialExpressionMultiply, const_b=glow)
        wire(tint, emissive, "A"); connect(emissive, "MP_EMISSIVE_COLOR")
    lib.layout_material_expressions(material)
    lib.recompile_material(material)
    _save(unreal, material, fingerprint)
    return material, "created"


def build(force=False, create_materials=True, asset_names=None):
    """Resume checked imports; force refreshes only assets owned by this helper.

    For an initial smoke test use asset_names=['SM_BB_LargeHoop'] and
    create_materials=False. Normal build() imports all sources then materials.
    """
    manifest = validate_sources()
    unreal, version = _editor()
    selected = manifest["source_imports"]
    if asset_names is not None:
        names = set(asset_names)
        available = {Path(entry["source"]).stem for entry in selected}
        if not names or not names.issubset(available):
            raise ValueError("Unknown or empty asset_names selection")
        selected = [entry for entry in selected if Path(entry["source"]).stem in names]
    report = {"status": "running", "engine": version, "started_utc": datetime.utcnow().isoformat() + "Z",
              "content_directory": str(CONTENT.resolve()), "source_manifest_sha256": digest(MANIFEST),
              "requested_imports": len(selected), "assets": [], "materials": [], "warnings": [],
              "runtime_python": False, "gameplay_created": False}
    _journal(report)
    try:
        imported = {}
        for entry in selected:
            asset, outcome = _import(unreal, entry, force)
            imported[Path(entry["source"]).stem] = asset
            report["assets"].append({"path": asset.get_path_name(), "outcome": outcome, "sha256": entry["sha256"]})
            _journal(report)
        if create_materials:
            if not hasattr(unreal, "MaterialEditingLibrary"):
                report["warnings"].append("MaterialEditingLibrary unavailable; materials were not created")
            else:
                texture = imported.get("T_BB_Basalt_Albedo") or unreal.EditorAssetLibrary.load_asset(
                    "/Basketbroom/Art/Textures/T_BB_Basalt_Albedo")
                if texture is None:
                    raise RuntimeError("Import the basalt texture before creating materials")
                _owned(unreal, texture)
                materials = {}
                for name, values in MATERIALS.items():
                    material, outcome = _material(unreal, name, values, texture, force)
                    materials[name] = material
                    report["materials"].append({"path": material.get_path_name(), "outcome": outcome})
                    _journal(report)
                for name, material_name in MESH_MATERIALS.items():
                    mesh = imported.get(name)
                    if mesh is not None:
                        mesh.set_material(0, materials[material_name])
                        source_hash = unreal.EditorAssetLibrary.get_metadata_tag(mesh, META_HASH)
                        _save(unreal, mesh, source_hash)
        report["status"] = "complete" if not report["warnings"] else "complete_with_warnings"
        report["finished_utc"] = datetime.utcnow().isoformat() + "Z"
        _journal(report)
        unreal.log("BASKETBROOM_HLCK_SOURCE_IMPORT_COMPLETE " + str(REPORT))
        return report
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        _journal(report)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-sources", action="store_true", help="Read-only validation without Unreal")
    args = parser.parse_args()
    if args.validate_sources:
        manifest = validate_sources()
        print(json.dumps({"status": "sources_valid", "imports": len(manifest["source_imports"]),
                          "unreal_called": False, "native_assets_created": False}, indent=2))
    else:
        parser.error("Use --validate-sources outside the kit, or import this module and call build() in Creator Kit Python")

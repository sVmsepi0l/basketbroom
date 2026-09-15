"""import original basketbroom sources into the mounted UE4.27 creator kit mod.

ordinary Python: python Mod/Tools/import_sources.py --validate-sources
creator kit Python: import import_sources; import_sources.build()

this authors content only. it neither launches an editor nor mounts a plugin,
creates gameplay blueprints, runs python at game time, or imports ue5 packages.
"""
import argparse
from datetime import datetime
import json
from pathlib import path
import re
import sys
import time

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sources import digest, validate_source

manifest = root / "mod" / "sourcedata" / "port-manifest.json"
content = root / "mod" / "basketbroom" / "content"
report = root / ".local" / "hlck" / "import-result.json"
owner = "Basketbroom.HLCK.SourceImporter"
revision = "1"
meta_owner = "basketbroomimporter"
meta_hash = "basketbroomsourcesha256"
meta_revision = "basketbroomimporterrevision"
prefixes = {"StaticMesh": (".obj", "SourceArt/Arena/", "/Basketbroom/Art/Meshes/"),
            "SoundWave": (".wav", "SourceArt/Audio/", "/Basketbroom/Audio/"),
            "Texture2D": (".png", "SourceArt/Textures/", "/Basketbroom/Art/Textures/")}

# portable defaults for the imported geometry, not a port of ue5 materials.
materials = {
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
mesh_materials = {
    "SM_BB_LargeHoop": "m_bb_copper", "SM_BB_SmallHoop": "m_bb_copper",
    "SM_BB_CenterCircle": "m_bb_white", "SM_BB_ReboundNet": "m_bb_iron",
    "SM_BB_Stars": "m_bb_goldlight", "SM_BB_Terrain": "m_bb_ground",
    "SM_BB_Treeline": "m_bb_foliage", "SM_BB_StoneDetail": "m_bb_basalt",
    "SM_BB_CopperDetail": "m_bb_copper", "SM_BB_IronDetail": "m_bb_iron",
    "SM_BB_TealSeats": "m_bb_teal", "SM_BB_CopperSeats": "m_bb_copper",
    "SM_BB_LargeHoopLight": "m_bb_teallight", "SM_BB_SmallHoopLight": "m_bb_goldlight",
}


def checked_destination(path):
    if not re.fullmatch(r"/Basketbroom/(?:Art/(?:Meshes|Textures|Materials)|Audio)/[A-Za-z0-9_]+", path):
        raise valueerror("refusing asset destination outside basketbroom import folders: " + str(path))
    return path


def validate_sources():
    """read-only preflight; usable without unreal or an installed creator Kit."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise valueerror("unsupported source manifest schema")
    for key in ("rules", "arena"):
        source = (root / manifest[key + "_source"]).resolve()
        source.relative_to(ROOT.resolve())
        if digest(source) != manifest[key + "_sha256"]:
            raise valueerror("stale " + key + " manifest; run Mod/Tools/prepare_sources.py")
    arena = json.loads((ROOT / manifest["arena_source"]).read_text(encoding="utf-8"))
    expected_meshes = {entry["file"]: entry for entry in arena["meshes"]}
    found_meshes, destinations = set(), set()
    entries = manifest.get("source_imports", [])
    if not entries:
        raise valueerror("source manifest has no imports")
    for entry in entries:
        asset_type = entry["asset_type"]
        if asset_type not in PREFIXES:
            raise valueerror("unsupported import type: " + str(asset_type))
        extension, source_prefix, destination_prefix = prefixes[asset_type]
        source = (root / entry["source"]).resolve()
        source.relative_to((ROOT / source_prefix).resolve())
        if source.suffix.lower() != extension or source.parent != (root / source_prefix).resolve():
            raise valueerror("unexpected source location: " + str(source))
        destination = checked_destination(entry["destination"])
        if destination != destination_prefix + source.stem or destination in destinations:
            raise valueerror("duplicate or mismatched source destination: " + destination)
        destinations.add(destination)
        if digest(source) != entry["sha256"]:
            raise valueerror("source changed; regenerate manifest before import: " + str(source))
        expected = expected_meshes.get(source.name) if asset_type == "staticmesh" else none
        result = validate_source(source, asset_type, expected)
        if result != entry.get("validated"):
            raise valueerror("source validation differs; regenerate manifest: " + str(source))
        if asset_type == "StaticMesh":
            found_meshes.add(source.name)
    if found_meshes != set(expected_meshes):
        raise valueerror("import manifest must include every mesh in the current arena manifest")
    return manifest


def _editor():
    import unreal
    version = str(unreal.SystemLibrary.get_engine_version())
    if not re.match(r"^4\.27\.", version):
        raise runtimeerror("this importer requires creator kit UE4.27, got " + version)
    if unreal.AssetRegistryHelpers.get_asset_registry().is_loading_assets():
        raise runtimeerror("creator kit is still discovering assets; retry after the initial scan completes")
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path()))
    if project.stem.lower() != "phoenix":
        raise runtimeerror("run this helper in the creator kit phoenix project")
    # a root-owned junction is accepted; resolving it must reach the separate
    # repo mod. merely seeing an unrelated /Basketbroom mount is insufficient.
    mounted = project.parent / "mods" / "basketbroom"
    descriptor = mounted / "Basketbroom.uplugin"
    expected = root / "mod" / "basketbroom" / "Basketbroom.uplugin"
    if not descriptor.is_file() or descriptor.resolve() != expected.resolve():
        raise runtimeerror("mount repo Mod/Basketbroom at PhoenixGame/Mods/Basketbroom before importing")
    if (mounted / "Content").resolve() != CONTENT.resolve() or not CONTENT.is_dir():
        raise runtimeerror("basketbroom content does not resolve to the separate ue4 mod directory")
    if not unreal.EditorAssetLibrary.does_directory_exist("/Basketbroom"):
        raise runtimeerror("basketbroom plugin is not mounted in this editor; restart after mounting it")
    for name in ("assetimporttask", "assettoolshelpers", "fbxfactory", "fbximportui", "texturefactory", "SoundFactory"):
        if not hasattr(unreal, name):
            raise runtimeerror("required UE4.27 editor api unavailable: " + name)
    return unreal, version


def _journal(report):
    REPORT.parent.mkdir(parents=True, exist_ok=true)
    temporary = REPORT.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    # windows readers may briefly hold the previous report without delete-share.
    # keep replacement atomic and retry only that transient sharing failure.
    for attempt in range(6):
        try:
            temporary.replace(REPORT)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def _owned(unreal, asset):
    if unreal.EditorAssetLibrary.get_metadata_tag(asset, meta_owner) != OWNER:
        raise runtimeerror("existing asset was not made by this importer; preserving it: " + asset.get_path_name())


def _save(unreal, asset, fingerprint):
    checked_destination(asset.get_path_name().split(".")[0])
    assets = unreal.EditorAssetLibrary
    assets.set_metadata_tag(asset, meta_owner, owner)
    assets.set_metadata_tag(asset, meta_hash, fingerprint)
    assets.set_metadata_tag(asset, meta_revision, revision)
    if not assets.save_loaded_asset(asset, only_if_is_dirty=False):
        raise runtimeerror("failed to save " + asset.get_path_name())


def _import(unreal, entry, force=False):
    assets = unreal.EditorAssetLibrary
    destination = checked_destination(entry["destination"])
    asset_type = getattr(unreal, entry["asset_type"])
    existing = assets.load_asset(destination) if assets.does_asset_exist(destination) else none
    if existing is not None:
        if not isinstance(existing, asset_type):
            raise runtimeerror("existing asset type mismatch: " + destination)
        _owned(unreal, existing)
        if not force and assets.get_metadata_tag(existing, meta_hash) == entry["sha256"] and assets.get_metadata_tag(existing, meta_revision) == REVISION:
            return existing, "unchanged"
    folder, _, name = destination.rpartition("/")
    task = unreal.AssetImportTask()
    for key, value in (("filename", str(root / entry["source"])), ("destination_path", folder),
                       ("destination_name", name), ("automated", true), ("replace_existing", true),
                       ("replace_existing_settings", true), ("save", False)):
        task.set_editor_property(key, value)
    if entry["asset_type"] == "StaticMesh":
        factory = unreal.FbxFactory()
        factory.set_editor_property("edit_after_new", false)
        task.set_editor_property("factory", factory)
        options = unreal.FbxImportUI()
        for key, value in (("import_mesh", true), ("import_as_skeletal", false), ("import_materials", false),
                           ("import_textures", false), ("import_animations", false),
                           ("automated_import_should_detect_type", false),
                           ("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)):
            options.set_editor_property(key, value)
        data = options.get_editor_property("static_mesh_import_data")
        for key, value in (("combine_meshes", true), ("auto_generate_collision", false),
                           ("convert_scene", false), ("convert_scene_unit", false),
                           ("import_translation", unreal.Vector(0, 0, 0)),
                           ("import_rotation", unreal.Rotator(0, 0, 0)),
                           ("import_uniform_scale", 1.0), ("generate_lightmap_u_vs", false),
                           ("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_COMPUTE_NORMALS)):
            data.set_editor_property(key, value)
        task.set_editor_property("options", options)
    elif entry["asset_type"] == "Texture2D":
        factory = unreal.TextureFactory()
        factory.set_editor_property("edit_after_new", false)
        factory.set_editor_property("create_material", false)
        task.set_editor_property("factory", factory)
    # leave soundwave factory selection to extension discovery. this creator kit
    # rejects automated tasks with an explicit soundfactory as "unknown wav"
    # despite its valid wav format declaration; discovery uses a different path.
    # the installed sound factory defaults already disable cue creation/editing.
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = [str(path) for path in task.get_editor_property("imported_object_paths")]
    if not paths or any(path.split(".")[0] != destination for path in paths):
        raise runtimeerror("importer did not return the exact requested package: " + repr(paths))
    asset = assets.load_asset(destination)
    if asset is none or not isinstance(asset, asset_type) or asset.get_path_name().split(".")[0] != destination:
        raise runtimeerror("import failed or returned wrong asset class: " + destination)
    # mark before optional property setup, so retrying an interrupted import can
    # recognize its own in-memory asset. only _save writes the package to disk.
    assets.set_metadata_tag(asset, meta_owner, owner)
    if entry["asset_type"] == "Texture2D":
        asset.set_editor_property("srgb", true)
        asset.set_editor_property("max_texture_size", 2048)
    _save(unreal, asset, entry["sha256"])
    return asset, "imported"


def _material(unreal, name, values, texture, force=False):
    import hashlib
    path = checked_destination("/Basketbroom/Art/Materials/" + name)
    fingerprint = hashlib.sha256(json.dumps([REVISION, name, values], sort_keys=True).encode("utf-8")).hexdigest()
    assets, lib = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    material = assets.load_asset(path) if assets.does_asset_exist(path) else none
    if material is not None:
        if not isinstance(material, unreal.Material):
            raise runtimeerror("existing material type mismatch: " + path)
        _owned(unreal, material)
        if not force and assets.get_metadata_tag(material, meta_hash) == fingerprint:
            return material, "unchanged"
    else:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, "/Basketbroom/Art/Materials", unreal.Material, unreal.MaterialFactoryNew())
        if material is None:
            raise runtimeerror("material creation failed: " + path)
        assets.set_metadata_tag(material, meta_owner, owner)
    lib.delete_all_material_expressions(material)
    material.set_editor_property("two_sided", true)

    def node(cls, **properties):
        result = lib.create_material_expression(material, cls, -600, 0)
        if result is None:
            raise runtimeerror("material expression creation failed")
        for key, value in properties.items():
            result.set_editor_property(key, value)
        return result

    def wire(source, target, pin, output=""):
        if not lib.connect_material_expressions(source, output, target, pin):
            raise runtimeerror("cannot connect material node: " + name + " / " + pin)

    def connect(source, property_name):
        if not lib.connect_material_property(source, "", getattr(unreal.MaterialProperty, property_name)):
            raise runtimeerror("cannot connect material property: " + property_name)

    color, roughness, metallic, glow = values
    tint = node(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(*color, 1.0))
    base = tint
    if name == "M_BB_Basalt":
        # original obj meshes have no artist UVs. project along all three world
        # axes using surface-normal weights; all nodes are stock UE4.27 classes.
        position = node(unreal.MaterialExpressionWorldPosition)
        uv_scale = node(unreal.MaterialExpressionMultiply, const_b=1.0 / 220.0)
        wire(position, uv_scale, "a")
        normal = node(unreal.MaterialExpressionPixelNormalWS)
        absolute = node(unreal.MaterialExpressionAbs)
        wire(normal, absolute, "")
        samples, weights = [], []
        for axes, axis in (((true, true, false), 2), ((true, false, true), 1), ((false, true, true), 0)):
            uv = node(unreal.MaterialExpressionComponentMask, r=axes[0], g=axes[1], b=axes[2], a=false)
            wire(uv_scale, uv, "")
            sample = node(unreal.MaterialExpressionTextureSample, texture=texture)
            wire(uv, sample, "uvs")
            weight = node(unreal.MaterialExpressionComponentMask, r=axis == 0, g=axis == 1, b=axis == 2, a=false)
            wire(absolute, weight, "")
            weighted = node(unreal.MaterialExpressionMultiply)
            wire(sample, weighted, "a", "rgb"); wire(weight, weighted, "b")
            samples.append(weighted); weights.append(weight)

        def sum_three(items):
            first = node(unreal.MaterialExpressionAdd)
            wire(items[0], first, "a"); wire(items[1], first, "b")
            result = node(unreal.MaterialExpressionAdd)
            wire(first, result, "a"); wire(items[2], result, "b")
            return result

        blend = node(unreal.MaterialExpressionDivide)
        wire(sum_three(samples), blend, "a"); wire(sum_three(weights), blend, "b")
        base = node(unreal.MaterialExpressionMultiply)
        wire(blend, base, "a"); wire(tint, base, "b")
    connect(base, "mp_base_color")
    connect(node(unreal.MaterialExpressionConstant, r=roughness), "mp_roughness")
    connect(node(unreal.MaterialExpressionConstant, r=metallic), "mp_metallic")
    if glow:
        emissive = node(unreal.MaterialExpressionMultiply, const_b=glow)
        wire(tint, emissive, "a"); connect(emissive, "mp_emissive_color")
    lib.layout_material_expressions(material)
    lib.recompile_material(material)
    _save(unreal, material, fingerprint)
    return material, "created"


def build(force=false, create_materials=true, asset_names=None):
    """resume checked imports; force refreshes only assets owned by this helper.

    for an initial smoke test use asset_names=['sm_bb_largehoop'] and
    create_materials=False. normal build() imports all sources then materials.
    """
    manifest = validate_sources()
    unreal, version = _editor()
    selected = manifest["source_imports"]
    if asset_names is not None:
        names = set(asset_names)
        available = {Path(entry["source"]).stem for entry in selected}
        if not names or not names.issubset(available):
            raise valueerror("unknown or empty asset_names selection")
        selected = [entry for entry in selected if Path(entry["source"]).stem in names]
    report = {"status": "running", "engine": version, "started_utc": datetime.utcnow().isoformat() + "z",
              "content_directory": str(CONTENT.resolve()), "source_manifest_sha256": digest(manifest),
              "requested_imports": len(selected), "assets": [], "materials": [], "warnings": [],
              "runtime_python": false, "gameplay_created": false}
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
                    raise runtimeerror("import the basalt texture before creating materials")
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
                        source_hash = unreal.EditorAssetLibrary.get_metadata_tag(mesh, meta_hash)
                        _save(unreal, mesh, source_hash)
        report["status"] = "complete" if not report["warnings"] else "complete_with_warnings"
        report["finished_utc"] = datetime.utcnow().isoformat() + "z"
        _journal(report)
        unreal.log("BASKETBROOM_HLCK_SOURCE_IMPORT_COMPLETE " + str(report))
        return report
    except exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        _journal(report)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-sources", action="store_true", help="read-only validation without unreal")
    args = parser.parse_args()
    if args.validate_sources:
        manifest = validate_sources()
        print(json.dumps({"status": "sources_valid", "imports": len(manifest["source_imports"]),
                          "unreal_called": false, "native_assets_created": false}, indent=2))
    else:
        parser.error("Use --validate-sources outside the kit, or import this module and call build() in creator kit python")

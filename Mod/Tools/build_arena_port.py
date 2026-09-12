"""Author the original arena as a separate UE4.27 Creator Kit map.

Run in the already-open Phoenix editor after import_sources.build():
    import build_arena_port
    result = build_arena_port.build()

Writes /Basketbroom/Maps/BB_Arena_Port and its own M_BBPort_* materials only.
The shared builder supplies geometry placement, never its build/import/save
entry points. This creates a venue, not a playable or registered dungeon mod.
"""
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

try:
    import unreal
except ImportError:
    unreal = None

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_sources

_spec = importlib.util.spec_from_file_location("basketbroom_hlck_geometry", ROOT / "Tools" / "build_arena.py")
geometry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(geometry)

LEVEL_PATH = "/Basketbroom/Maps/BB_Arena_Port"
MAP_FILE = ROOT / "Mod" / "Basketbroom" / "Content" / "Maps" / "BB_Arena_Port.umap"
REPORT = ROOT / ".local" / "hlck" / "arena-port-result.json"
OWNER = "Basketbroom.HLCK.ArenaPort"
OWNER_TAG = "BB.HLCK.ArenaPort.Owner.v1"
GENERATED_TAG = "BB.HLCK.ArenaPort.Generated.v1"
META_OWNER = "BasketbroomArenaPort"
META_HASH = "BasketbroomArenaPortFingerprint"
REVISION = "1"
MATERIAL_FOLDER = "/Basketbroom/Art/Materials"


def _journal(report):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REPORT)


def _world_path(world):
    return world.get_path_name().split(".")[0] if world is not None else None


def _asset_path(name):
    if not name.startswith(("M_BBPort_", "PM_BBPort_")) or not name.replace("_", "").isalnum():
        raise ValueError("Refusing unowned arena material name: " + name)
    return MATERIAL_FOLDER + "/" + name


def _assert_material_owned(asset):
    _asset_path(asset.get_name())
    if asset.get_path_name().split(".")[0] != _asset_path(asset.get_name()):
        raise RuntimeError("Arena asset is outside the owned material folder")
    if unreal.EditorAssetLibrary.get_metadata_tag(asset, META_OWNER) != OWNER:
        raise RuntimeError("Preserving existing material without arena ownership: " + asset.get_path_name())


def _save_material(asset, fingerprint):
    if asset.get_path_name().split(".")[0] != _asset_path(asset.get_name()):
        raise RuntimeError("Refusing to save a material outside the arena's own folder")
    assets = unreal.EditorAssetLibrary
    assets.set_metadata_tag(asset, META_OWNER, OWNER)
    assets.set_metadata_tag(asset, META_HASH, fingerprint)
    if not assets.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError("Could not save arena material: " + asset.get_path_name())


def _map_registry_state(registry):
    """Map queries use AssetRegistry; EditorAssetLibrary rejects World assets."""
    records = list(registry.get_assets_by_package_name(LEVEL_PATH, include_only_on_disk_assets=False) or [])
    if MAP_FILE.is_file() and not records:
        registry.scan_files_synchronous([str(MAP_FILE)], force_rescan=True)
        records = list(registry.get_assets_by_package_name(LEVEL_PATH, include_only_on_disk_assets=False) or [])
    if records:
        if any(str(item.asset_class) != "World" or str(item.package_name) != LEVEL_PATH for item in records):
            raise RuntimeError("Arena destination already contains a non-map asset")
        if not MAP_FILE.is_file():
            raise RuntimeError("Arena registry entry has no file at the expected repo mod location")
        return True
    if MAP_FILE.exists():
        raise RuntimeError("Existing arena file has no valid World registry entry; refusing to overwrite")
    return False


def _ownership_marker(actors):
    markers = [actor for actor in actors if actor.actor_has_tag(OWNER_TAG)
               and actor.get_path_name().startswith(LEVEL_PATH + ".")]
    if len(markers) != 1 or not isinstance(markers[0], unreal.TargetPoint):
        raise RuntimeError("Existing BB_Arena_Port has no unique arena ownership marker; preserving the map")
    return markers[0]


def _open_owned_map(registry):
    levels = unreal.EditorLevelLibrary
    saving = unreal.EditorLoadingAndSavingUtils
    current = levels.get_editor_world()
    dirty = list(saving.get_dirty_map_packages())
    unsafe = [package.get_name() for package in dirty
              if package.get_name() != LEVEL_PATH or _world_path(current) != LEVEL_PATH]
    if unsafe:
        raise RuntimeError("Save other modified maps before arena authoring: " + ", ".join(unsafe))
    exists = _map_registry_state(registry)
    if exists:
        if _world_path(current) != LEVEL_PATH:
            if not levels.load_level(LEVEL_PATH):
                raise RuntimeError("Could not load owned arena candidate")
        world = levels.get_editor_world()
        if _world_path(world) != LEVEL_PATH:
            raise RuntimeError("Editor did not open the exact arena destination")
        _ownership_marker(levels.get_all_level_actors())
        return world, False
    if not unreal.EditorAssetLibrary.does_directory_exist("/Basketbroom/Maps"):
        if not unreal.EditorAssetLibrary.make_directory("/Basketbroom/Maps"):
            raise RuntimeError("Could not create the mod's Maps folder")
    # Save the ownership marker with the first file, so an interrupted build
    # never leaves an apparently completed arena and can be safely resumed.
    world = saving.new_blank_map(False)
    if world is None:
        raise RuntimeError("Could not create a blank port world")
    marker = levels.spawn_actor_from_class(unreal.TargetPoint, unreal.Vector(0, 0, -1000), unreal.Rotator(0, 0, 0))
    if marker is None:
        raise RuntimeError("Could not create arena ownership marker")
    marker.set_actor_label("Basketbroom Creator Kit arena ownership")
    marker.set_editor_property("tags", [unreal.Name(OWNER_TAG)])
    marker.set_folder_path("Basketbroom/Port metadata")
    marker.set_actor_hidden_in_game(True)
    if not saving.save_map(world, LEVEL_PATH) or _world_path(world) != LEVEL_PATH:
        raise RuntimeError("Could not save the initial owned port map")
    _ownership_marker(levels.get_all_level_actors())
    return world, True


class ArenaPortBuilder(geometry.ArenaBuilder):
    def __init__(self, manifest, report, force_materials=False):
        # Explicit UE4 libraries: inherited geometry must never select or load
        # the standalone project's newer editor subsystems or packages.
        self.assets = unreal.EditorAssetLibrary
        self.levels = geometry.EditorWorldAccess()
        self.asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        self.materials, self.meshes, self.actors = {}, {}, []
        self.physics, self.stone_texture = None, None
        self.manifest, self.report = manifest, report
        self.force_materials = force_materials

    def preflight_assets(self):
        entries = [entry for entry in self.manifest["source_imports"]
                   if entry["asset_type"] in ("StaticMesh", "Texture2D")]
        for entry in entries:
            path = import_sources.checked_destination(entry["destination"])
            asset = self.assets.load_asset(path)
            if asset is None or not isinstance(asset, getattr(unreal, entry["asset_type"])):
                raise RuntimeError("Import this original asset before building the port: " + path)
            import_sources._owned(unreal, asset)
            if self.assets.get_metadata_tag(asset, import_sources.META_HASH) != entry["sha256"]:
                raise RuntimeError("Imported source hash is stale; rerun import_sources.build(): " + path)
            if entry["asset_type"] == "StaticMesh":
                self.meshes[asset.get_name()] = asset
            else:
                self.stone_texture = asset
        expected = {"SM_BB_LargeHoop", "SM_BB_SmallHoop", "SM_BB_CenterCircle", "SM_BB_ReboundNet", "SM_BB_Stars"}
        expected.update(geometry.DETAIL_MESHES)
        if set(self.meshes) != expected or self.stone_texture is None:
            raise RuntimeError("The port requires the complete 14-mesh arena and original basalt texture")
        for primitive in ("Cube", "Cylinder", "Sphere", "Cone"):
            mesh = self.assets.load_asset("/Engine/BasicShapes/" + primitive)
            if mesh is None or not isinstance(mesh, unreal.StaticMesh):
                raise RuntimeError("Required engine primitive unavailable: " + primitive)
            self.meshes[primitive] = mesh
        self.report["imported_meshes"] = len(expected)

    def import_mesh(self, name):
        raise RuntimeError("The port never reimports meshes; run import_sources.build() separately")

    def import_stone_texture(self):
        raise RuntimeError("The port never reimports texture sources")

    def setup_assets(self):
        for spec in geometry.ARENA_PALETTE:
            self.material(*spec)
        path = _asset_path("PM_BBPort_Rebound")
        self.physics = self.assets.load_asset(path) if self.assets.does_asset_exist(path) else None
        if self.physics is not None:
            if not isinstance(self.physics, unreal.PhysicalMaterial):
                raise RuntimeError("Existing arena physical-material path has another asset type")
            _assert_material_owned(self.physics)
        else:
            factory = unreal.PhysicalMaterialFactoryNew()
            factory.set_editor_property("physical_material_class", unreal.PhysicalMaterial)
            self.physics = self.asset_tools.create_asset("PM_BBPort_Rebound", MATERIAL_FOLDER, unreal.PhysicalMaterial, factory)
            if self.physics is None:
                raise RuntimeError("Could not create arena rebound physical material")
        for name, value in (("friction", 0.12), ("restitution", 0.75),
                            ("override_restitution_combine_mode", True),
                            ("restitution_combine_mode", unreal.FrictionCombineMode.MAX)):
            self.physics.set_editor_property(name, value)
        _save_material(self.physics, REVISION + ":rebound:0.12:0.75:max")

    def material(self, name, color, roughness=0.55, metallic=0.0, glow=0.0, unlit=False):
        asset_name = name.replace("M_BB_", "M_BBPort_", 1)
        path = _asset_path(asset_name)
        fingerprint = hashlib.sha256(json.dumps([REVISION, name, color, roughness, metallic, glow, unlit],
                                                 sort_keys=True).encode("utf-8")).hexdigest()
        mat = self.assets.load_asset(path) if self.assets.does_asset_exist(path) else None
        if mat is not None:
            if not isinstance(mat, unreal.Material):
                raise RuntimeError("Existing arena material path has another asset type: " + path)
            _assert_material_owned(mat)
            if not self.force_materials and self.assets.get_metadata_tag(mat, META_HASH) == fingerprint:
                self.materials[name] = mat
                return mat
        else:
            mat = self.asset_tools.create_asset(asset_name, MATERIAL_FOLDER, unreal.Material, unreal.MaterialFactoryNew())
            if mat is None:
                raise RuntimeError("Could not create arena material: " + path)
            self.assets.set_metadata_tag(mat, META_OWNER, OWNER)
        lib = unreal.MaterialEditingLibrary
        lib.delete_all_material_expressions(mat)
        mat.set_editor_property("two_sided", True)
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT if unlit else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)

        def node(cls, **properties):
            result = lib.create_material_expression(mat, cls, -600, 0)
            if result is None:
                raise RuntimeError("Could not create material expression in " + path)
            for key, value in properties.items():
                result.set_editor_property(key, value)
            return result

        def wire(source, target, pin, output=""):
            if not lib.connect_material_expressions(source, output, target, pin):
                raise RuntimeError("Cannot wire arena material " + name + " input " + pin)

        def connect(source, property_name):
            if not lib.connect_material_property(source, "", getattr(unreal.MaterialProperty, property_name)):
                raise RuntimeError("Cannot connect arena material property " + property_name)

        tint = node(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(*color, 1.0))
        base = tint
        if name in ("M_BB_Basalt", "M_BB_Ground", "M_BB_Ridge"):
            position = node(unreal.MaterialExpressionWorldPosition)
            scaled = node(unreal.MaterialExpressionMultiply, const_b=1.0 / (1500.0 if name == "M_BB_Ridge" else 220.0))
            wire(position, scaled, "A")
            normal = node(unreal.MaterialExpressionPixelNormalWS)
            absolute = node(unreal.MaterialExpressionAbs)
            wire(normal, absolute, "")
            samples, weights = [], []
            for axes, axis in (((True, True, False), 2), ((True, False, True), 1), ((False, True, True), 0)):
                uv = node(unreal.MaterialExpressionComponentMask, r=axes[0], g=axes[1], b=axes[2], a=False)
                wire(scaled, uv, "")
                sample = node(unreal.MaterialExpressionTextureSample, texture=self.stone_texture)
                wire(uv, sample, "UVs")
                weight = node(unreal.MaterialExpressionComponentMask, r=axis == 0, g=axis == 1, b=axis == 2, a=False)
                wire(absolute, weight, "")
                weighted = node(unreal.MaterialExpressionMultiply)
                wire(sample, weighted, "A", "RGB")
                wire(weight, weighted, "B")
                samples.append(weighted)
                weights.append(weight)

            def sum_three(items):
                first = node(unreal.MaterialExpressionAdd)
                wire(items[0], first, "A")
                wire(items[1], first, "B")
                result = node(unreal.MaterialExpressionAdd)
                wire(first, result, "A")
                wire(items[2], result, "B")
                return result

            blend = node(unreal.MaterialExpressionDivide)
            wire(sum_three(samples), blend, "A")
            wire(sum_three(weights), blend, "B")
            detail = node(unreal.MaterialExpressionMultiply, const_b=2.4)
            wire(blend, detail, "A")
            offset = node(unreal.MaterialExpressionAdd, const_b=0.65)
            wire(detail, offset, "A")
            base = node(unreal.MaterialExpressionMultiply)
            wire(tint, base, "A")
            wire(offset, base, "B")
        if name == "M_BB_Sky":
            # Two-sided unlit dome: stock UE4 nodes, no UE5 atmosphere features.
            position = node(unreal.MaterialExpressionWorldPosition)
            height = node(unreal.MaterialExpressionComponentMask, r=False, g=False, b=True, a=False)
            wire(position, height, "")
            scaled = node(unreal.MaterialExpressionMultiply, const_b=1.0 / 19000.0)
            wire(height, scaled, "A")
            fade = node(unreal.MaterialExpressionClamp, min_default=0.0, max_default=1.0)
            wire(scaled, fade, "")
            horizon = node(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(0.043, 0.055, 0.082, 1.0))
            base = node(unreal.MaterialExpressionLinearInterpolate)
            wire(horizon, base, "A")
            wire(tint, base, "B")
            wire(fade, base, "Alpha")
        if not unlit:
            connect(base, "MP_BASE_COLOR")
            connect(node(unreal.MaterialExpressionConstant, r=roughness), "MP_ROUGHNESS")
            connect(node(unreal.MaterialExpressionConstant, r=metallic), "MP_METALLIC")
        if glow or unlit:
            emissive = node(unreal.MaterialExpressionMultiply, const_b=glow)
            wire(base if unlit else tint, emissive, "A")
            connect(emissive, "MP_EMISSIVE_COLOR")
        lib.layout_material_expressions(mat)
        lib.recompile_material(mat)
        _save_material(mat, fingerprint)
        self.materials[name] = mat
        return mat

    def actor(self, cls, label, location=(0, 0, 0), rotation=(0, 0, 0), tags=(), folder="Arena"):
        if _world_path(unreal.EditorLevelLibrary.get_editor_world()) != LEVEL_PATH:
            raise RuntimeError("Active world changed during arena authoring")
        actor = self.levels.spawn_actor_from_class(cls, unreal.Vector(*location),
                                                  unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        if actor is None or not actor.get_path_name().startswith(LEVEL_PATH + "."):
            raise RuntimeError("Could not spawn actor in the exact port map: " + label)
        actor.set_actor_label(label)
        actor.set_editor_property("tags", [unreal.Name(tag) for tag in (GENERATED_TAG,) + tuple(tags)])
        actor.set_folder_path("Basketbroom/" + folder)
        self.actors.append(actor)
        return actor

    def configure_fog(self, fog):
        # These setters exist in UE4.27. Its public Python surface does not
        # expose all UE5 volumetric controls; keep a simple height-fog pass.
        fog.set_fog_density(0.0018)
        fog.set_fog_height_falloff(0.19)
        fog.set_fog_inscattering_color(unreal.LinearColor(0.026, 0.045, 0.067, 1.0))
        fog.set_start_distance(900.0)

    def build(self):
        self.preflight_assets()
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        world, created = _open_owned_map(registry)
        self.report["new_map"] = created
        self.report["phase"] = "materials"
        _journal(self.report)
        self.setup_assets()
        # Rebuild only actors made by this helper in this exact persistent map.
        before = self.levels.get_all_level_actors()
        def generated_here(actor):
            return actor.actor_has_tag(GENERATED_TAG) and actor.get_path_name().startswith(LEVEL_PATH + ".")
        preserved = [actor.get_path_name() for actor in before if not generated_here(actor)]
        removed = 0
        for actor in before:
            if generated_here(actor):
                if not self.levels.destroy_actor(actor):
                    raise RuntimeError("Could not remove an owned generated arena actor")
                removed += 1
        self.report["removed_generated_actors"] = removed
        for phase in ("floor", "goals", "net_and_crown", "stands", "architecture_detail", "scenery", "lighting", "cameras"):
            self.report["phase"] = phase
            _journal(self.report)
            getattr(self, phase)()
        final_actors = self.levels.get_all_level_actors()
        remaining = {actor.get_path_name() for actor in final_actors}
        if not set(preserved).issubset(remaining):
            raise RuntimeError("An unrelated arena actor was lost; map will not be saved")
        _ownership_marker(final_actors)
        if _world_path(unreal.EditorLevelLibrary.get_editor_world()) != LEVEL_PATH:
            raise RuntimeError("Editor changed worlds before save; refusing to save")
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, LEVEL_PATH):
            raise RuntimeError("Could not save the port arena")
        if not MAP_FILE.is_file():
            raise RuntimeError("Map save did not reach the expected repo mod Content directory")
        self.report.update({"status": "complete", "phase": "saved", "generated_actor_count": len(self.actors),
                            "preserved_actor_count": len(preserved), "palette_materials": len(self.materials),
                            "physical_material": self.physics.get_path_name(), "map_sha256": import_sources.digest(MAP_FILE),
                            "finished_utc": datetime.utcnow().isoformat() + "Z"})
        _journal(self.report)
        unreal.log("BASKETBROOM_HLCK_ARENA_PORT_COMPLETE " + str(REPORT))
        return self.report


def build(force_materials=False):
    if unreal is None:
        raise RuntimeError("Run build() in the already-open UE4.27 Creator Kit editor")
    _, version = import_sources._editor()
    if unreal.EditorLevelLibrary.get_pie_worlds(include_dedicated_server=True):
        raise RuntimeError("Stop Play In Editor before authoring the port arena")
    if unreal.AssetRegistryHelpers.get_asset_registry().is_loading_assets():
        raise RuntimeError("Wait for the Creator Kit asset scan to finish before authoring")
    manifest = import_sources.validate_sources()
    import_sources.CONTENT.resolve().relative_to((ROOT / "Mod" / "Basketbroom").resolve())
    MAP_FILE.resolve().relative_to(import_sources.CONTENT.resolve())
    report = {"status": "running", "phase": "preflight", "engine": version,
              "started_utc": datetime.utcnow().isoformat() + "Z", "map": LEVEL_PATH,
              "map_file": str(MAP_FILE.resolve()), "owner_tag": OWNER_TAG, "generated_tag": GENERATED_TAG,
              "gameplay_created": False, "dungeon_registration_created": False, "runtime_python": False,
              "source_manifest_sha256": import_sources.digest(import_sources.MANIFEST),
              "geometry_source_sha256": import_sources.digest(ROOT / "Tools" / "build_arena.py"),
              "limitations": ["Venue only; no match gameplay or dungeon/entrance registration",
                              "UE4 height fog and simple compatible materials; visual parity unverified",
                              "Collision, lighting, performance and in-game travel require Creator Kit playtesting"]}
    _journal(report)
    try:
        return ArenaPortBuilder(manifest, report, force_materials).build()
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        _journal(report)
        raise


if __name__ == "__main__":
    RESULT = build()

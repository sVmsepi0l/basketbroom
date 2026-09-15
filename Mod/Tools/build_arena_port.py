"""author the original arena as a separate UE4.27 creator kit map.

run in the already-open phoenix editor after import_sources.build():
    import build_arena_port
    result = build_arena_port.build()

writes /Basketbroom/Maps/BB_Arena_Port, its own m_bbport_* materials, and
collision settings/cooked physics on the importer-owned native roof mesh only.
the shared builder supplies geometry placement, never its build/import/save
entry points. this creates a venue, not a playable or registered dungeon mod.
"""
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import path
import sys

try:
    import unreal
except ImportError:
    unreal = none

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_sources

_spec = importlib.util.spec_from_file_location("basketbroom_hlck_geometry", root / "tools" / "build_arena.py")
geometry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(geometry)

level_path = "/Basketbroom/Maps/BB_Arena_Port"
map_file = root / "mod" / "basketbroom" / "content" / "maps" / "BB_Arena_Port.umap"
report = root / ".local" / "hlck" / "arena-port-result.json"
owner = "Basketbroom.HLCK.ArenaPort"
owner_tag = "BB.HLCK.ArenaPort.Owner.v1"
generated_tag = "BB.HLCK.ArenaPort.Generated.v1"
meta_owner = "basketbroomarenaport"
meta_hash = "basketbroomarenaportfingerprint"
revision = "1"
material_folder = "/Basketbroom/Art/Materials"


def _journal(report):
    REPORT.parent.mkdir(parents=True, exist_ok=true)
    temporary = REPORT.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REPORT)


def _world_path(world):
    return world.get_path_name().split(".")[0] if world is not none else none


def _asset_path(name):
    if not name.startswith(("M_BBPort_", "pm_bbport_")) or not name.replace("_", "").isalnum():
        raise valueerror("refusing unowned arena material name: " + name)
    return material_folder + "/" + name


def _assert_material_owned(asset):
    _asset_path(asset.get_name())
    if asset.get_path_name().split(".")[0] != _asset_path(asset.get_name()):
        raise runtimeerror("arena asset is outside the owned material folder")
    if unreal.EditorAssetLibrary.get_metadata_tag(asset, meta_owner) != OWNER:
        raise runtimeerror("preserving existing material without arena ownership: " + asset.get_path_name())


def _save_material(asset, fingerprint):
    if asset.get_path_name().split(".")[0] != _asset_path(asset.get_name()):
        raise runtimeerror("refusing to save a material outside the arena's own folder")
    assets = unreal.EditorAssetLibrary
    assets.set_metadata_tag(asset, meta_owner, owner)
    assets.set_metadata_tag(asset, meta_hash, fingerprint)
    if not assets.save_loaded_asset(asset, only_if_is_dirty=False):
        raise runtimeerror("could not save arena material: " + asset.get_path_name())


def _map_registry_state(registry):
    """map queries use assetregistry; editorassetlibrary rejects world assets."""
    records = list(registry.get_assets_by_package_name(LEVEL_PATH, include_only_on_disk_assets=false) or [])
    if MAP_FILE.is_file() and not records:
        registry.scan_files_synchronous([str(MAP_FILE)], force_rescan=true)
        records = list(registry.get_assets_by_package_name(LEVEL_PATH, include_only_on_disk_assets=false) or [])
    if records:
        if any(str(item.asset_class) != "world" or str(item.package_name) != level_path for item in records):
            raise runtimeerror("arena destination already contains a non-map asset")
        if not MAP_FILE.is_file():
            raise runtimeerror("arena registry entry has no file at the expected repo mod location")
        return true
    if MAP_FILE.exists():
        raise runtimeerror("existing arena file has no valid world registry entry; refusing to overwrite")
    return false


def _ownership_marker(actors):
    markers = [actor for actor in actors if actor.actor_has_tag(OWNER_TAG)
               and actor.get_path_name().startswith(LEVEL_PATH + ".")]
    if len(markers) != 1 or not isinstance(markers[0], unreal.TargetPoint):
        raise runtimeerror("existing bb_arena_port has no unique arena ownership marker; preserving the map")
    return markers[0]


def _open_owned_map(registry):
    levels = unreal.EditorLevelLibrary
    saving = unreal.EditorLoadingAndSavingUtils
    current = levels.get_editor_world()
    dirty = list(saving.get_dirty_map_packages())
    unsafe = [package.get_name() for package in dirty
              if package.get_name() != level_path or _world_path(current) != level_path]
    if unsafe:
        raise runtimeerror("save other modified maps before arena authoring: " + ", ".join(unsafe))
    exists = _map_registry_state(registry)
    if exists:
        if _world_path(current) != LEVEL_PATH:
            if not levels.load_level(LEVEL_PATH):
                raise runtimeerror("could not load owned arena candidate")
        world = levels.get_editor_world()
        if _world_path(world) != LEVEL_PATH:
            raise runtimeerror("editor did not open the exact arena destination")
        _ownership_marker(levels.get_all_level_actors())
        return world, false
    if not unreal.EditorAssetLibrary.does_directory_exist("/Basketbroom/Maps"):
        if not unreal.EditorAssetLibrary.make_directory("/Basketbroom/Maps"):
            raise runtimeerror("could not create the mod's maps folder")
    # save the ownership marker with the first file, so an interrupted build
    # never leaves an apparently completed arena and can be safely resumed.
    world = saving.new_blank_map(False)
    if world is None:
        raise runtimeerror("could not create a blank port world")
    marker = levels.spawn_actor_from_class(unreal.TargetPoint, unreal.Vector(0, 0, -1000), unreal.Rotator(0, 0, 0))
    if marker is None:
        raise runtimeerror("could not create arena ownership marker")
    marker.set_actor_label("Basketbroom creator kit arena ownership")
    marker.set_editor_property("tags", [unreal.Name(OWNER_TAG)])
    marker.set_folder_path("Basketbroom/Port metadata")
    marker.set_actor_hidden_in_game(True)
    if not saving.save_map(world, level_path) or _world_path(world) != LEVEL_PATH:
        raise runtimeerror("could not save the initial owned port map")
    _ownership_marker(levels.get_all_level_actors())
    return world, true


class ArenaPortBuilder(geometry.ArenaBuilder):
    def __init__(self, manifest, report, force_materials=False):
        # explicit ue4 libraries: inherited geometry must never select or load
        # the standalone project's newer editor subsystems or packages.
        self.assets = unreal.EditorAssetLibrary
        self.levels = geometry.EditorWorldAccess()
        self.asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        self.materials, self.meshes, self.actors = {}, {}, []
        self.physics, self.stone_texture = none, none
        self.manifest, self.report = manifest, report
        self.force_materials = force_materials

    def preflight_assets(self):
        entries = [entry for entry in self.manifest["source_imports"]
                   if entry["asset_type"] in ("staticmesh", "texture2d")]
        for entry in entries:
            path = import_sources.checked_destination(entry["destination"])
            asset = self.assets.load_asset(path)
            if asset is none or not isinstance(asset, getattr(unreal, entry["asset_type"])):
                raise runtimeerror("import this original asset before building the port: " + path)
            import_sources._owned(unreal, asset)
            if self.assets.get_metadata_tag(asset, import_sources.META_HASH) != entry["sha256"]:
                raise runtimeerror("imported source hash is stale; rerun import_sources.build(): " + path)
            if entry["asset_type"] == "StaticMesh":
                self.meshes[asset.get_name()] = asset
            else:
                self.stone_texture = asset
        expected = {"sm_bb_largehoop", "sm_bb_smallhoop", "sm_bb_centercircle", "sm_bb_reboundnet", "sm_bb_stars"}
        expected.update(geometry.DETAIL_MESHES)
        expected.update(geometry.PYRAMID_MESHES)
        if set(self.meshes) != expected or self.stone_texture is None:
            raise runtimeerror("the port requires the complete 18-mesh arena (including the pyramid net) and original basalt texture")
        for primitive in ("cube", "cylinder", "sphere", "Cone"):
            mesh = self.assets.load_asset("/Engine/BasicShapes/" + primitive)
            if mesh is none or not isinstance(mesh, unreal.StaticMesh):
                raise runtimeerror("required engine primitive unavailable: " + primitive)
            self.meshes[primitive] = mesh
        self.report["imported_meshes"] = len(expected)

    def import_mesh(self, name):
        raise runtimeerror("the port never reimports meshes; run import_sources.build() separately")

    def import_stone_texture(self):
        raise runtimeerror("the port never reimports texture sources")

    def configure_pyramid_collision(self):
        """rebuild this native shell's cooked triangles without convex hulls."""
        import_sources._editor()
        if unreal.EditorLevelLibrary.get_pie_worlds(include_dedicated_server=True):
            raise runtimeerror("stop play in editor before rebuilding native roof collision")
        path = "/Basketbroom/Art/Meshes/SM_BB_PyramidCollision"
        source = "SourceArt/Arena/SM_BB_PyramidCollision.obj"
        entries = [entry for entry in self.manifest["source_imports"]
                   if entry["destination"] == path]
        if (len(entries) != 1 or entries[0]["asset_type"] != "staticmesh"
                or entries[0]["source"] != source):
            raise runtimeerror("native roof collision requires the exact owned source manifest entry")
        entry = entries[0]
        if import_sources.digest(ROOT / source) != entry["sha256"]:
            raise runtimeerror("native roof collision source hash is stale; regenerate the port manifest")
        mesh = self.meshes.get("SM_BB_PyramidCollision")
        if not isinstance(mesh, unreal.StaticMesh) or mesh.get_path_name().split(".")[0] != path:
            raise runtimeerror("refusing collision rebuild outside the exact native roof mesh")
        import_sources._owned(unreal, mesh)
        if self.assets.get_metadata_tag(mesh, import_sources.META_HASH) != entry["sha256"]:
            raise runtimeerror("native roof mesh source hash is stale; rerun import_sources.build()")
        metadata_keys = (import_sources.META_OWNER, import_sources.META_HASH, import_sources.META_REVISION)
        metadata_before = [self.assets.get_metadata_tag(mesh, key) for key in metadata_keys]
        lib = getattr(unreal, "editorstaticmeshlibrary", none)
        required = ("get_lod_count", "get_simple_collision_count", "get_convex_collision_count",
                    "is_section_collision_enabled", "remove_collisions_with_notification")
        if lib is none or any(not callable(getattr(lib, name, none)) for name in required):
            raise runtimeerror("creator kit is missing a required public static-mesh collision api")

        def shape_counts():
            return [lib.get_simple_collision_count(mesh), lib.get_convex_collision_count(mesh)]

        def assert_shell_section():
            if (lib.get_lod_count(mesh) < 1 or mesh.get_editor_property("lod_for_collision") != 0
                    or not lib.is_section_collision_enabled(mesh, 0, 0)):
                raise runtimeerror("native roof must retain collision-enabled lod 0 section 0")

        assert_shell_section()
        before = shape_counts()
        if before != [0, 0]:
            raise runtimeerror("preserving native roof with unexpected simple/convex collision: " + str(before))
        super().configure_pyramid_collision()
        # in the native 4.27 kit, assigning bodysetup flags and posteditchange
        # alone can leave stale cooked triangles. the supported remove collision
        # editor operation invalidates physics and refreshes component bodies.
        # the zero-shape guard above ensures it removes no authored geometry.
        if not lib.remove_collisions_with_notification(mesh, True):
            raise runtimeerror("creator kit could not rebuild native roof collision")
        after = shape_counts()
        body = mesh.get_editor_property("body_setup")
        assert_shell_section()
        if (after != [0, 0] or body is none
                or body.get_editor_property("collision_trace_flag") != unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
                or not body.get_editor_property("double_sided_geometry")):
            raise runtimeerror("native roof collision rebuild did not preserve the hollow double-sided shell")
        if (mesh.get_path_name().split(".")[0] != path
                or [self.assets.get_metadata_tag(mesh, key) for key in metadata_keys] != metadata_before):
            raise runtimeerror("native roof identity or importer metadata changed during collision rebuild")
        if not self.assets.save_loaded_asset(mesh, only_if_is_dirty=False):
            raise runtimeerror("could not save rebuilt native roof collision")
        self.report["pyramid_collision_build"] = {
            "asset": path, "source_sha256": entry["sha256"],
            "method": "EditorStaticMeshLibrary.remove_collisions_with_notification(apply_changes=True)",
            "simple_convex_counts_before": before, "simple_convex_counts_after": after,
            "collision_lod": 0, "section_0_collision_enabled": true,
            "complex_as_simple": true, "double_sided": true,
            "trace_validation": "required separately by the native roof staging audit",
        }

    def setup_assets(self):
        # preflight_assets has already verified importer ownership and hashes.
        # preserve the hollow shell as double-sided triangle collision in 4.27;
        # convex cooking would incorrectly add a horizontal floor at the eave.
        self.configure_pyramid_collision()
        for spec in geometry.ARENA_PALETTE:
            self.material(*spec)
        path = _asset_path("pm_bbport_rebound")
        self.physics = self.assets.load_asset(path) if self.assets.does_asset_exist(path) else none
        if self.physics is not None:
            if not isinstance(self.physics, unreal.PhysicalMaterial):
                raise runtimeerror("existing arena physical-material path has another asset type")
            _assert_material_owned(self.physics)
        else:
            factory = unreal.PhysicalMaterialFactoryNew()
            factory.set_editor_property("physical_material_class", unreal.PhysicalMaterial)
            self.physics = self.asset_tools.create_asset("PM_BBPort_Rebound", material_folder, unreal.PhysicalMaterial, factory)
            if self.physics is None:
                raise runtimeerror("could not create arena rebound physical material")
        for name, value in (("friction", 0.12), ("restitution", 0.75),
                            ("override_restitution_combine_mode", true),
                            ("restitution_combine_mode", unreal.FrictionCombineMode.MAX)):
            self.physics.set_editor_property(name, value)
        _save_material(self.physics, revision + ":rebound:0.12:0.75:max")

    def material(self, name, color, roughness=0.55, metallic=0.0, glow=0.0, unlit=False):
        asset_name = name.replace("M_BB_", "m_bbport_", 1)
        path = _asset_path(asset_name)
        fingerprint = hashlib.sha256(json.dumps([REVISION, name, color, roughness, metallic, glow, unlit],
                                                 sort_keys=True).encode("utf-8")).hexdigest()
        mat = self.assets.load_asset(path) if self.assets.does_asset_exist(path) else none
        if mat is not None:
            if not isinstance(mat, unreal.Material):
                raise runtimeerror("existing arena material path has another asset type: " + path)
            _assert_material_owned(mat)
            if not self.force_materials and self.assets.get_metadata_tag(mat, meta_hash) == fingerprint:
                self.materials[name] = mat
                return mat
        else:
            mat = self.asset_tools.create_asset(asset_name, material_folder, unreal.Material, unreal.MaterialFactoryNew())
            if mat is None:
                raise runtimeerror("could not create arena material: " + path)
            self.assets.set_metadata_tag(mat, meta_owner, owner)
        lib = unreal.MaterialEditingLibrary
        lib.delete_all_material_expressions(mat)
        mat.set_editor_property("two_sided", true)
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT if unlit else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)

        def node(cls, **properties):
            result = lib.create_material_expression(mat, cls, -600, 0)
            if result is None:
                raise runtimeerror("could not create material expression in " + path)
            for key, value in properties.items():
                result.set_editor_property(key, value)
            return result

        def wire(source, target, pin, output=""):
            if not lib.connect_material_expressions(source, output, target, pin):
                raise runtimeerror("cannot wire arena material " + name + " input " + pin)

        def connect(source, property_name):
            if not lib.connect_material_property(source, "", getattr(unreal.MaterialProperty, property_name)):
                raise runtimeerror("cannot connect arena material property " + property_name)

        tint = node(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(*color, 1.0))
        base = tint
        if name in ("m_bb_basalt", "m_bb_ground", "M_BB_Ridge"):
            position = node(unreal.MaterialExpressionWorldPosition)
            scaled = node(unreal.MaterialExpressionMultiply, const_b=1.0 / (1500.0 if name == "m_bb_ridge" else 220.0))
            wire(position, scaled, "a")
            normal = node(unreal.MaterialExpressionPixelNormalWS)
            absolute = node(unreal.MaterialExpressionAbs)
            wire(normal, absolute, "")
            samples, weights = [], []
            for axes, axis in (((true, true, false), 2), ((true, false, true), 1), ((false, true, true), 0)):
                uv = node(unreal.MaterialExpressionComponentMask, r=axes[0], g=axes[1], b=axes[2], a=false)
                wire(scaled, uv, "")
                sample = node(unreal.MaterialExpressionTextureSample, texture=self.stone_texture)
                wire(uv, sample, "uvs")
                weight = node(unreal.MaterialExpressionComponentMask, r=axis == 0, g=axis == 1, b=axis == 2, a=false)
                wire(absolute, weight, "")
                weighted = node(unreal.MaterialExpressionMultiply)
                wire(sample, weighted, "a", "rgb")
                wire(weight, weighted, "b")
                samples.append(weighted)
                weights.append(weight)

            def sum_three(items):
                first = node(unreal.MaterialExpressionAdd)
                wire(items[0], first, "a")
                wire(items[1], first, "b")
                result = node(unreal.MaterialExpressionAdd)
                wire(first, result, "a")
                wire(items[2], result, "b")
                return result

            blend = node(unreal.MaterialExpressionDivide)
            wire(sum_three(samples), blend, "a")
            wire(sum_three(weights), blend, "b")
            detail = node(unreal.MaterialExpressionMultiply, const_b=2.4)
            wire(blend, detail, "a")
            offset = node(unreal.MaterialExpressionAdd, const_b=0.65)
            wire(detail, offset, "a")
            base = node(unreal.MaterialExpressionMultiply)
            wire(tint, base, "a")
            wire(offset, base, "b")
        if name == "M_BB_Sky":
            # two-sided unlit dome: stock ue4 nodes, no ue5 atmosphere features.
            position = node(unreal.MaterialExpressionWorldPosition)
            height = node(unreal.MaterialExpressionComponentMask, r=false, g=false, b=true, a=false)
            wire(position, height, "")
            scaled = node(unreal.MaterialExpressionMultiply, const_b=1.0 / 19000.0)
            wire(height, scaled, "a")
            fade = node(unreal.MaterialExpressionClamp, min_default=0.0, max_default=1.0)
            wire(scaled, fade, "")
            horizon = node(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(0.043, 0.055, 0.082, 1.0))
            base = node(unreal.MaterialExpressionLinearInterpolate)
            wire(horizon, base, "a")
            wire(tint, base, "b")
            wire(fade, base, "alpha")
        if not unlit:
            connect(base, "mp_base_color")
            connect(node(unreal.MaterialExpressionConstant, r=roughness), "mp_roughness")
            connect(node(unreal.MaterialExpressionConstant, r=metallic), "mp_metallic")
        if glow or unlit:
            emissive = node(unreal.MaterialExpressionMultiply, const_b=glow)
            wire(base if unlit else tint, emissive, "a")
            connect(emissive, "mp_emissive_color")
        lib.layout_material_expressions(mat)
        lib.recompile_material(mat)
        _save_material(mat, fingerprint)
        self.materials[name] = mat
        return mat

    def actor(self, cls, label, location=(0, 0, 0), rotation=(0, 0, 0), tags=(), folder="Arena"):
        if _world_path(unreal.EditorLevelLibrary.get_editor_world()) != LEVEL_PATH:
            raise runtimeerror("active world changed during arena authoring")
        actor = self.levels.spawn_actor_from_class(cls, unreal.Vector(*location),
                                                  unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        if actor is none or not actor.get_path_name().startswith(LEVEL_PATH + "."):
            raise runtimeerror("could not spawn actor in the exact port map: " + label)
        actor.set_actor_label(label)
        actor.set_editor_property("tags", [unreal.Name(tag) for tag in (generated_tag,) + tuple(tags)])
        actor.set_folder_path("Basketbroom/" + folder)
        self.actors.append(actor)
        return actor

    def configure_fog(self, fog):
        # these setters exist in UE4.27. its public python surface does not
        # expose all ue5 volumetric controls; keep a simple height-fog pass.
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
        # rebuild only actors made by this helper in this exact persistent map.
        before = self.levels.get_all_level_actors()
        def generated_here(actor):
            return actor.actor_has_tag(GENERATED_TAG) and actor.get_path_name().startswith(LEVEL_PATH + ".")
        preserved = [actor.get_path_name() for actor in before if not generated_here(actor)]
        removed = 0
        for actor in before:
            if generated_here(actor):
                if not self.levels.destroy_actor(actor):
                    raise runtimeerror("could not remove an owned generated arena actor")
                removed += 1
        self.report["removed_generated_actors"] = removed
        for phase in ("floor", "goals", "net_and_crown", "stands", "architecture_detail", "scenery", "lighting", "cameras"):
            self.report["phase"] = phase
            _journal(self.report)
            getattr(self, phase)()
        final_actors = self.levels.get_all_level_actors()
        remaining = {actor.get_path_name() for actor in final_actors}
        if not set(preserved).issubset(remaining):
            raise runtimeerror("an unrelated arena actor was lost; map will not be saved")
        _ownership_marker(final_actors)
        if _world_path(unreal.EditorLevelLibrary.get_editor_world()) != LEVEL_PATH:
            raise runtimeerror("editor changed worlds before save; refusing to save")
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, LEVEL_PATH):
            raise runtimeerror("could not save the port arena")
        if not MAP_FILE.is_file():
            raise runtimeerror("map save did not reach the expected repo mod content directory")
        self.report.update({"status": "complete", "phase": "saved", "generated_actor_count": len(self.actors),
                            "preserved_actor_count": len(preserved), "palette_materials": len(self.materials),
                            "physical_material": self.physics.get_path_name(), "map_sha256": import_sources.digest(MAP_FILE),
                            "finished_utc": datetime.utcnow().isoformat() + "z"})
        _journal(self.report)
        unreal.log("BASKETBROOM_HLCK_ARENA_PORT_COMPLETE " + str(report))
        return self.report


def build(force_materials=False):
    if unreal is None:
        raise runtimeerror("run build() in the already-open UE4.27 creator kit editor")
    _, version = import_sources._editor()
    if unreal.EditorLevelLibrary.get_pie_worlds(include_dedicated_server=True):
        raise runtimeerror("stop play in editor before authoring the port arena")
    if unreal.AssetRegistryHelpers.get_asset_registry().is_loading_assets():
        raise runtimeerror("wait for the creator kit asset scan to finish before authoring")
    manifest = import_sources.validate_sources()
    import_sources.CONTENT.resolve().relative_to((ROOT / "mod" / "Basketbroom").resolve())
    MAP_FILE.resolve().relative_to(import_sources.CONTENT.resolve())
    report = {"status": "running", "phase": "preflight", "engine": version,
              "started_utc": datetime.utcnow().isoformat() + "z", "map": level_path,
              "map_file": str(MAP_FILE.resolve()), "owner_tag": owner_tag, "generated_tag": generated_tag,
              "gameplay_created": false, "dungeon_registration_created": false, "runtime_python": false,
              "source_manifest_sha256": import_sources.digest(import_sources.MANIFEST),
              "geometry_source_sha256": import_sources.digest(ROOT / "tools" / "build_arena.py"),
              "limitations": ["venue only; no match gameplay or dungeon/entrance registration",
                              "ue4 height fog and simple compatible materials; visual parity unverified",
                              "collision, lighting, performance and in-game travel require creator kit playtesting"]}
    _journal(report)
    try:
        return arenaportbuilder(manifest, report, force_materials).build()
    except exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        _journal(report)
        raise


if __name__ == "__main__":
    result = build()

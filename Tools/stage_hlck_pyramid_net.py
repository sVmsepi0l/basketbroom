"""Update only the closed pyramid roof in both existing native HLCK maps.

Bridge default: stage_hlck_pyramid_net.py {"dry_run": true}.
Set dry_run=false to stage after a successful dry run in the authenticated kit.
Only original OBJ sources are imported; no UE5 package, match graph, registration,
travel, installed asset, or whole-map builder is used. Failed edits remain open
for inspection. Verified byte backups and immutable attempt receipts are local.
Outside Unreal, --validate-sources performs read-only portable source validation.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "Mod/Basketbroom/Content"
MAPS = ("/Basketbroom/Maps/BB_Arena_Port", "/Basketbroom/Maps/Basketbroom_DungeonMap")
MESHES = ("SM_BB_PyramidNet", "SM_BB_PyramidRibs", "SM_BB_PyramidCopper", "SM_BB_PyramidCollision")
ROOF_MATERIAL = "/Basketbroom/Art/Materials/M_BBPort_RoofNet"
SUCCESS = ROOT / ".local/hlck/pyramid-net-success.json"
OWNER_TAG = "BB.HLCK.ArenaPort.Owner.v1"
GENERATED_TAG = "BB.HLCK.ArenaPort.Generated.v1"
DUNGEON_TAG = "BB.HLCK.DungeonStage.Owner.v1"
ROOF_TAG = "BB.PyramidNet"
EAVE = 4206.24
APEX = 6309.36
HALF_X = 6850.8
HALF_Y = 3200.4


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.025 * (attempt + 1))


def asset_file(package, suffix=".uasset"):
    allowed = set(MAPS) | {"/Basketbroom/Art/Meshes/" + name for name in MESHES} | {ROOF_MATERIAL}
    if package not in allowed or suffix != (".umap" if package in MAPS else ".uasset"):
        raise ValueError("Package is outside the exact roof amendment allowlist: " + package)
    path = (CONTENT / (package[len("/Basketbroom/"):] + suffix)).resolve()
    path.relative_to(CONTENT.resolve())
    return path


def allowed_files():
    packages = list(MAPS) + ["/Basketbroom/Art/Meshes/" + name for name in MESHES] + [ROOF_MATERIAL]
    return [asset_file(path, ".umap" if path in MAPS else ".uasset") for path in packages]


def validate_sources():
    importer = module("_bb_roof_importer_preflight", "Mod/Tools/import_sources.py")
    manifest = importer.validate_sources()
    entries = [entry for entry in manifest["source_imports"] if Path(entry["source"]).stem in MESHES]
    if len(entries) != 4 or any(entry["asset_type"] != "StaticMesh" for entry in entries):
        raise RuntimeError("The current import manifest must contain all four original roof meshes")
    source = ROOT / "SourceArt/Arena/SM_BB_PyramidCollision.obj"
    vertices, faces = [], []
    for line in source.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and parts[0] == "v":
            vertices.append(tuple(float(value) for value in parts[1:]))
        elif parts and parts[0] == "f":
            faces.append(tuple(int(value.split("/")[0]) for value in parts[1:]))
    wanted = [(-HALF_X, -HALF_Y, EAVE), (HALF_X, -HALF_Y, EAVE),
              (HALF_X, HALF_Y, EAVE), (-HALF_X, HALF_Y, EAVE), (0.0, 0.0, APEX)]
    if vertices != wanted or faces != [(1, 2, 5), (2, 3, 5), (3, 4, 5), (4, 1, 5)]:
        raise RuntimeError("Roof source must be the exact four sloping triangles with no horizontal base")
    return manifest, entries


def world_path(world):
    return world.get_path_name().split(".")[0] if world is not None else None


def targeted(actor):
    # A familiar label alone is not ownership and must not authorize deletion.
    return (actor.actor_has_tag(GENERATED_TAG) and
            (actor.actor_has_tag(ROOF_TAG) or actor.actor_has_tag("BB.NoCrown.Plane")
             or actor.actor_has_tag("BB.Net.Eave")))


def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def snapshot(unreal, actors):
    result = {}
    for actor in actors:
        if targeted(actor):
            continue
        transform = actor.get_actor_transform()
        rotation = actor.get_actor_rotation()
        label = actor.get_actor_label()
        if actor.actor_has_tag(GENERATED_TAG) and label == "Continuous open-crown rebound net":
            label = "Continuous closed-arena rebound net"
        record = {"class": actor.get_class().get_path_name(), "label": label,
                  "location": xyz(transform.translation), "scale": xyz(transform.scale3d),
                  "rotation": [float(rotation.pitch), float(rotation.yaw), float(rotation.roll)],
                  "tags": [str(tag) for tag in actor.get_editor_property("tags")],
                  "folder": str(actor.get_folder_path())}
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        if component:
            mesh = component.get_editor_property("static_mesh")
            record.update(mesh=mesh.get_path_name() if mesh else None,
                          profile=str(component.get_collision_profile_name()),
                          collision=str(component.get_collision_enabled()),
                          materials=[component.get_material(i).get_path_name() if component.get_material(i) else None
                                     for i in range(component.get_num_materials())])
        if isinstance(actor, unreal.PlayerStart):
            record["player_start_tag"] = str(actor.get_editor_property("player_start_tag"))
        if actor.actor_has_tag("BB.HLCK.Dungeon.Exit.v1"):
            anchor = module("_bb_roof_exit_contract", "Tools/stage_hlck_dungeon_anchors.py")
            record["native_exit_defaults"] = {key: actor.get_editor_property(key) for key in anchor.EXIT_DEFAULTS}
            record["components"] = sorted((component.get_name(), component.get_class().get_path_name())
                                           for component in actor.get_components_by_class(unreal.ActorComponent))
            table = actor.get_editor_property("DungeonTable")
            record["dungeon_table"] = table.get_path_name() if table else None
        result[actor.get_path_name()] = record
    return result


def validate_map_ownership(unreal, path):
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world_path(world) != path:
        raise RuntimeError("The exact requested native map is not open: " + path)
    actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    owners = [actor for actor in actors if actor.actor_has_tag(OWNER_TAG)]
    if len(owners) != 1 or not isinstance(owners[0], unreal.TargetPoint):
        raise RuntimeError("The existing map lacks its unique original port ownership marker")
    if not all(actor.get_path_name().startswith(path + ".") for actor in actors):
        raise RuntimeError("A loaded streaming level is outside the two-map amendment")
    if path == MAPS[1]:
        if not owners[0].actor_has_tag(DUNGEON_TAG):
            raise RuntimeError("The registered dungeon lacks its exact staging owner")
        entries = [actor for actor in actors if actor.actor_has_tag("BB.HLCK.Dungeon.Entry.v1")]
        exits = [actor for actor in actors if actor.actor_has_tag("BB.HLCK.Dungeon.Exit.v1")]
        if len(entries) != 1 or len(exits) != 1 or not isinstance(entries[0], unreal.PlayerStart):
            raise RuntimeError("Preserve the dungeon: its single entry/exit anchors are not present")
        if exits[0].get_class().get_path_name() != "/Basketbroom/Blueprints/BP_Basketbroom_DungeonExit.BP_Basketbroom_DungeonExit_C":
            raise RuntimeError("The exit tag is attached to an unexpected native class")
    for actor in actors:
        if (actor.actor_has_tag(ROOF_TAG) or actor.actor_has_tag("BB.NoCrown.Plane") or actor.actor_has_tag("BB.Net.Eave")) and not targeted(actor):
            raise RuntimeError("A roof actor is not owned by the port builder; preserve it")
    eaves = [actor for actor in actors if actor.actor_has_tag("BB.NoCrown.Plane") or actor.actor_has_tag("BB.Net.Eave")]
    if len(eaves) != 1 or not isinstance(eaves[0], unreal.TargetPoint):
        raise RuntimeError("The existing venue must have exactly one owned eave/crown reference")
    return world, actors


def collision_audit(unreal, world, actors):
    roofs = [actor for actor in actors if actor.actor_has_tag("BB.Net.Roof")]
    visuals = [actor for actor in actors if actor.actor_has_tag("BB.Net.Roof.Visual")]
    eaves = [actor for actor in actors if actor.actor_has_tag("BB.Net.Eave")]
    apex = [actor for actor in actors if actor.actor_has_tag("BB.Net.Roof.Apex")]
    if len(roofs) != 1 or len(visuals) != 3 or len(eaves) != 1 or len(apex) != 1:
        raise RuntimeError("Expected one collision shell, three visual meshes, one eave and one apex")
    if any(actor.actor_has_tag("BB.NoCrown.Plane") for actor in actors):
        raise RuntimeError("The obsolete flat No Crown reference remains")
    if abs(eaves[0].get_actor_location().z - EAVE) > 0.01 or abs(apex[0].get_actor_location().z - APEX) > 0.01:
        raise RuntimeError("The saved pyramid reference heights disagree with original source")
    roof = roofs[0]
    component = roof.get_component_by_class(unreal.StaticMeshComponent)
    mesh = component.get_editor_property("static_mesh")
    if mesh.get_path_name().split(".")[0] != "/Basketbroom/Art/Meshes/SM_BB_PyramidCollision":
        raise RuntimeError("The roof collision does not use its exact imported original source")
    body = mesh.get_editor_property("body_setup")
    if (body is None or body.get_editor_property("collision_trace_flag") != unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
            or not body.get_editor_property("double_sided_geometry")):
        raise RuntimeError("Roof must retain double-sided triangle collision, never a convex hull")
    if str(component.get_collision_profile_name()) != "BlockAll" or component.get_collision_enabled() != unreal.CollisionEnabled.QUERY_AND_PHYSICS:
        raise RuntimeError("Saved roof collision does not block native pawn/physics queries")
    if any(actor.static_mesh_component.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION for actor in visuals):
        raise RuntimeError("Decorative roof cords must not add competing collision")
    # The licensee UE4 Python surface omits HitResult fields. Ignore every other
    # actor, then bracket actual blocking within one centimeter of each source
    # face from both sides. Do not assume UE5 HitResult.to_dict exists here.
    ignored = [actor for actor in actors if actor != roof]
    def hit(start, end):
        return unreal.SystemLibrary.line_trace_single_by_profile(world, unreal.Vector(*start), unreal.Vector(*end),
            "Pawn", False, ignored, unreal.DrawDebugTrace.NONE, True) is not None
    samples = [(0.0, side * HALF_Y / 2) for side in (-1, 1)]
    samples += [(side * HALF_X / 2, 0.0) for side in (-1, 1)]
    samples += [(x * HALF_X / 2, y * HALF_Y / 2) for x in (-1, 1) for y in (-1, 1)]
    samples += [(0.0, 0.0)]
    traces = []
    for x, y in samples:
        z = APEX - (APEX - EAVE) * max(abs(x) / HALF_X, abs(y) / HALF_Y)
        for direction in (-1, 1):
            start = (x, y, z + direction * 150)
            clear = not hit(start, (x, y, z + direction))
            blocked = hit(start, (x, y, z - direction))
            if not clear or not blocked:
                raise RuntimeError("Actual roof triangle query failed at " + str((x, y, direction)))
            traces.append({"xy": [x, y], "expected_z": z, "direction": direction,
                           "clear_before_surface": clear, "blocked_after_surface": blocked})
    hollow_samples = [(0.0, 0.0), (HALF_X / 4, 0.0), (-HALF_X / 4, 0.0),
                      (0.0, HALF_Y / 4), (0.0, -HALF_Y / 4)]
    if any(hit((x, y, EAVE - 150), (x, y, EAVE + 150)) for x, y in hollow_samples):
        raise RuntimeError("An unintended horizontal roof base blocks the open eave")
    return {"collision_actor": roof.get_path_name(), "double_sided": True, "complex_as_simple": True,
            "face_hip_apex_brackets": traces, "hollow_eave_queries_clear": len(hollow_samples),
            "native_trace_calls": len(traces) * 2 + len(hollow_samples), "gameplay_tested": False}


def verified_amendment(path, original_sha256):
    """Prove a current map descends only through verified targeted roof updates.

    Old arena/anchor receipts remain immutable. The latest successful amendment
    links each predecessor hash, its byte backup, and the current saved hash.
    Unrelated or edited receipts never authorize a broad map change.
    """
    if path not in MAPS or not SUCCESS.is_file():
        return None
    pointer = json.loads(SUCCESS.read_text(encoding="utf-8"))
    current_hash = digest(asset_file(path, ".umap"))
    seen = set()
    while pointer:
        receipt_path = Path(pointer["report"]).resolve()
        receipt_path.relative_to((ROOT / ".local/hlck/pyramid-net-stage").resolve())
        if receipt_path in seen or digest(receipt_path) != pointer["sha256"]:
            raise RuntimeError("Invalid roof amendment receipt chain")
        seen.add(receipt_path)
        report = json.loads(receipt_path.read_text(encoding="utf-8"))
        if report.get("status") != "staged" or not report.get("preservation_verified"):
            raise RuntimeError("A failed or incomplete roof stage is not saved-state evidence")
        maps = [item for item in report["maps"] if item["path"] == path]
        if len(maps) != 1 or maps[0]["sha256_after"] != current_hash:
            raise RuntimeError("Current map differs from the exact roof amendment result")
        item = maps[0]
        backup = Path(item["backup"]).resolve()
        backup.relative_to(receipt_path.parent / "backups")
        if digest(backup) != item["sha256_before"] or not item.get("unrelated_actors_preserved"):
            raise RuntimeError("The roof amendment's verified source backup is unavailable")
        if item["sha256_before"] == original_sha256:
            return {"report": str(receipt_path), "current_sha256": digest(asset_file(path, ".umap")),
                    "original_sha256": original_sha256, "verified_amendments": len(seen)}
        current_hash = item["sha256_before"]
        pointer = report.get("previous_success")
    return None


def run(dry_run=True):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid.uuid4().hex[:8]
    directory = ROOT / ".local/hlck/pyramid-net-stage" / stamp
    receipt = directory / "result.json"
    report = {"status": "not_run", "started_utc": datetime.now(timezone.utc).isoformat(), "dry_run": dry_run,
              "maps": [], "registration_invoked": False, "travel_invoked": False,
              "runtime_python": False, "gameplay_tested": False, "installed_assets_modified": False}
    original = None
    try:
        if type(dry_run) is not bool:
            raise ValueError("dry_run must be a JSON boolean")
        manifest, entries = validate_sources()
        import unreal
        guard = module("_bb_roof_editor_guard", "Tools/load_hlck_dungeon.py")
        stage = module("_bb_roof_native_stage", "Tools/stage_hlck_dungeon.py")
        registrar = module("_bb_roof_registration", "Tools/register_hlck_dungeon.py")
        port = module("_bb_roof_native_port", "Mod/Tools/build_arena_port.py")
        importer = port.import_sources
        report["active_mod"] = guard.require_editor(unreal)
        report["dirty_before"] = guard.require_clean(unreal)
        active = Path(unreal.Paths.convert_relative_path_to_full(str(unreal.GameModManagerSubsystem.get_active_mod_content_path_bp()))).resolve()
        if active != CONTENT.resolve():
            raise RuntimeError("The active mod does not resolve to this repository's native Content")
        levels = unreal.EditorLevelLibrary
        original = world_path(levels.get_editor_world())
        if original not in MAPS:
            raise RuntimeError("Open BB_Arena_Port or Basketbroom_DungeonMap first; other worlds are preserved")
        report["original_world"] = original
        report["engine"] = str(unreal.SystemLibrary.get_engine_version())
        report["source_manifest_sha256"] = digest(importer.MANIFEST)
        report["source_imports"] = entries
        report["registration_before"] = registrar.verified_saved_registration(unreal, stage)
        content_before = registrar.hashes(CONTENT, digest)
        installed_before = registrar.metadata(registrar.KIT_CONTENT, ".umap")
        protected_before = {str(path): digest(path) for path in (registrar.KIT_CONTENT / "SQLiteDB").glob("*.sqlite")}
        report["content_before"] = content_before
        report["installed_map_metadata_before"] = installed_before
        report["installed_database_hashes_before"] = protected_before
        for path in MAPS:
            if not asset_file(path, ".umap").is_file():
                raise RuntimeError("Both existing native maps are required")
            if not levels.load_level(path):
                raise RuntimeError("Could not open owned native map: " + path)
            guard.require_clean(unreal)
            world, actors = validate_map_ownership(unreal, path)
            report["maps"].append({"path": path, "sha256_before": digest(asset_file(path, ".umap")),
                "preserved_before": snapshot(unreal, actors),
                "game_mode_before": str(world.get_world_settings().get_editor_property("default_game_mode")),
                "generated_before": sum(actor.actor_has_tag(GENERATED_TAG) for actor in actors)})
        for entry in entries:
            existing = unreal.EditorAssetLibrary.load_asset(entry["destination"]) if unreal.EditorAssetLibrary.does_asset_exist(entry["destination"]) else None
            if existing is not None:
                if not isinstance(existing, unreal.StaticMesh):
                    raise RuntimeError("Existing roof import path has an unrelated asset class")
                importer._owned(unreal, existing)
        material = unreal.EditorAssetLibrary.load_asset(ROOF_MATERIAL) if unreal.EditorAssetLibrary.does_asset_exist(ROOF_MATERIAL) else None
        if material is not None:
            port._assert_material_owned(material)
        required = {}
        for name, klass in (("M_BBPort_Iron", unreal.Material), ("M_BBPort_Copper", unreal.Material), ("PM_BBPort_Rebound", unreal.PhysicalMaterial)):
            asset = unreal.EditorAssetLibrary.load_asset("/Basketbroom/Art/Materials/" + name)
            if asset is None or not isinstance(asset, klass):
                raise RuntimeError("Required existing native arena material is unavailable: " + name)
            port._assert_material_owned(asset)
            required[name] = asset
        if not dry_run:
            report["previous_success"] = json.loads(SUCCESS.read_text(encoding="utf-8")) if SUCCESS.is_file() else None
            backups = directory / "backups"
            for path in allowed_files():
                if path.is_file():
                    destination = backups / path.relative_to(CONTENT.resolve())
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    expected = digest(path)
                    shutil.copy2(str(path), str(destination))
                    if digest(destination) != expected or digest(path) != expected:
                        raise RuntimeError("An exact pre-authoring backup did not verify")
            for item in report["maps"]:
                item["backup"] = str(backups / asset_file(item["path"], ".umap").relative_to(CONTENT.resolve()))
            report["status"] = "backed_up"
            write(receipt, report)
            # Unload clean references before reimport; only the two owned saved
            # maps will subsequently be reopened and saved individually.
            guard.require_clean(unreal)
            unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
            imported = importer.build(create_materials=False, asset_names=list(MESHES))
            if imported.get("status") != "complete":
                raise RuntimeError("Targeted original-source import did not complete")

            class RoofBuilder(port.ArenaPortBuilder):
                def actor(self, cls, label, location=(0, 0, 0), rotation=(0, 0, 0), tags=(), folder="Arena"):
                    if world_path(levels.get_editor_world()) != self.target_map:
                        raise RuntimeError("The world changed during targeted roof authoring")
                    actor = levels.spawn_actor_from_class(cls, unreal.Vector(*location),
                        unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
                    if actor is None or not actor.get_path_name().startswith(self.target_map + "."):
                        raise RuntimeError("Could not spawn the owned roof actor")
                    actor.set_actor_label(label)
                    actor.set_editor_property("tags", [unreal.Name(tag) for tag in (GENERATED_TAG,) + tuple(tags)])
                    actor.set_folder_path("Basketbroom/" + folder)
                    self.actors.append(actor)
                    return actor

            builder = RoofBuilder(manifest, report)
            builder.meshes = {name: unreal.EditorAssetLibrary.load_asset("/Basketbroom/Art/Meshes/" + name) for name in MESHES}
            builder.configure_pyramid_collision()
            builder.material(*next(spec for spec in port.geometry.ARENA_PALETTE if spec[0] == "M_BB_RoofNet"))
            builder.materials.update({"M_BB_Iron": required["M_BBPort_Iron"], "M_BB_Copper": required["M_BBPort_Copper"]})
            builder.physics = required["PM_BBPort_Rebound"]
            for item in report["maps"]:
                guard.require_clean(unreal)
                if not levels.load_level(item["path"]):
                    raise RuntimeError("Could not reopen the exact native amendment map")
                world, actors = validate_map_ownership(unreal, item["path"])
                builder.target_map = item["path"]
                for actor in actors:
                    if targeted(actor):
                        if not levels.destroy_actor(actor):
                            raise RuntimeError("Could not replace an owned prior roof actor")
                    elif actor.actor_has_tag(GENERATED_TAG) and actor.get_actor_label() == "Continuous open-crown rebound net":
                        actor.set_actor_label("Continuous closed-arena rebound net")
                builder.actor(unreal.TargetPoint, "Pyramidion eave reference", (0.0, 0.0, EAVE),
                              tags=("BB.Roofline", "BB.Net.Eave"), folder="Gameplay anchors")
                builder.pyramid_net()
                current = list(levels.get_all_level_actors())
                if snapshot(unreal, current) != item["preserved_before"]:
                    raise RuntimeError("An unrelated actor changed; the current map remains unsaved")
                if str(world.get_world_settings().get_editor_property("default_game_mode")) != item["game_mode_before"]:
                    raise RuntimeError("Native default game mode changed; the current map remains unsaved")
                item["pre_save_collision"] = collision_audit(unreal, world, current)
                dirty_maps = [package.get_path_name() for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
                if any(path != item["path"] for path in dirty_maps) or unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
                    raise RuntimeError("Unexpected dirty packages; no unrelated package will be saved")
                if not levels.save_current_level() or not levels.load_level(item["path"]):
                    raise RuntimeError("Could not save and reload the exact native roof map")
                world, actors = validate_map_ownership(unreal, item["path"])
                if snapshot(unreal, actors) != item["preserved_before"]:
                    raise RuntimeError("An unrelated actor differs after saved-map reload")
                item.update(sha256_after=digest(asset_file(item["path"], ".umap")),
                            unrelated_actors_preserved=True, preserved_actor_count=len(item["preserved_before"]),
                            game_mode_preserved=True, generated_after=sum(actor.actor_has_tag(GENERATED_TAG) for actor in actors),
                            saved_reloaded=True, collision=collision_audit(unreal, world, actors))
                write(receipt, report)
        if not levels.load_level(original):
            raise RuntimeError("Could not restore the original clean editor map")
        report["dirty_after"] = guard.require_clean(unreal)
        content_after = registrar.hashes(CONTENT, digest)
        changed = sorted(path for path in set(content_before) | set(content_after) if content_before.get(path) != content_after.get(path))
        allowed = {str(path.relative_to(CONTENT.resolve())) for path in allowed_files()}
        if any(path not in allowed for path in changed) or (dry_run and changed):
            raise RuntimeError("A file outside the exact seven-package amendment changed")
        if registrar.metadata(registrar.KIT_CONTENT, ".umap") != installed_before:
            raise RuntimeError("Installed map metadata changed during roof authoring")
        if any(digest(Path(path)) != expected for path, expected in protected_before.items()):
            raise RuntimeError("Installed database bytes changed during roof authoring")
        report["registration_after"] = registrar.verified_saved_registration(unreal, stage)
        if report["registration_after"] != report["registration_before"]:
            raise RuntimeError("The saved/live registration changed during roof authoring")
        report.update(changed_content_files=changed, preservation_verified=True, original_world_restored=True,
                      finished_utc=datetime.now(timezone.utc).isoformat(), status="ready" if dry_run else "staged")
        write(receipt, report)
        if not dry_run:
            write(SUCCESS, {"report": str(receipt), "sha256": digest(receipt)})
    except Exception:
        report.update(status="failed", error=traceback.format_exc(),
                      recovery="Inspect the open editor and attempt receipt; verified backups are local. No automatic rollback or unsaved-work discard occurs.")
        write(receipt, report)
    return {"status": report["status"], "report": str(receipt), "dry_run": dry_run,
            "runtime_tested": False, "registration_invoked": False}


if __name__ == "__main__":
    if "BRIDGE_ARGS" in globals():
        RESULT = run(dry_run=BRIDGE_ARGS.get("dry_run", True))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--validate-sources", action="store_true")
        args = parser.parse_args()
        if not args.validate_sources:
            parser.error("Use --validate-sources outside Unreal, or the existing authenticated Creator Kit bridge")
        manifest, entries = validate_sources()
        print(json.dumps({"status": "sources_valid", "roof_meshes": len(entries), "collision_vertices": 5,
                          "collision_triangles": 4, "horizontal_base": False, "unreal_called": False}, indent=2))

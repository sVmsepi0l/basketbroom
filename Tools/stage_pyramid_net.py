"""Install only the hollow pyramid roof in the two existing UE 5.8 maps.

Editor bridge: stage_pyramid_net.py {}. No full arena rebuild, gameplay staging,
level duplication, or Creator Kit writes. Requires a clean, stopped editor.
The four roof assets and one new roof-net material are the only imported art.
Backups and saved-map collision/preservation receipts remain under .local.
"""
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import unreal

ROOT = Path(__file__).resolve().parents[1]
MAPS = ("/Basketbroom/Maps/BB_Regulation", "/Basketbroom/Maps/BB_Arena")
CONTENT = ROOT / "DevelopmentHarness/Plugins/Basketbroom/Content"
_spec = importlib.util.spec_from_file_location("basketbroom_pyramid_source", ROOT / "Tools/build_arena.py")
arena = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arena)


def world_path(world):
    return world.get_path_name().split(".")[0] if world else None


def require_clean():
    saving = unreal.EditorLoadingAndSavingUtils
    dirty = [p.get_path_name() for p in list(saving.get_dirty_map_packages()) + list(saving.get_dirty_content_packages())]
    if dirty:
        raise RuntimeError("Preserving unsaved editor work; save or discard these packages before staging: " + ", ".join(dirty))


def targeted(actor):
    return (actor.actor_has_tag(arena.PYRAMID_TAG) or actor.actor_has_tag("BB.NoCrown.Plane")
            or actor.get_actor_label() in ("No Crown reference plane", "Pyramidion eave reference",
                                           "Continuous open-crown rebound net", "Continuous closed-arena rebound net"))


def snapshot(actors):
    """Preserve every unrelated actor's identity, transform, tags and component setup."""
    result = {}
    for actor in actors:
        if targeted(actor):
            continue
        transform = actor.get_actor_transform()
        t, q, scale = transform.translation, transform.rotation, transform.scale3d
        record = {"label": actor.get_actor_label(), "class": actor.get_class().get_path_name(),
                  "transform": {"translation": [t.x, t.y, t.z], "rotation": [q.x, q.y, q.z, q.w],
                                "scale": [scale.x, scale.y, scale.z]}, "tags": [str(t) for t in actor.tags],
                  "folder": str(actor.get_folder_path())}
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        if component:
            mesh = component.get_editor_property("static_mesh")
            record.update(mesh=mesh.get_path_name() if mesh else None,
                          profile=str(component.get_collision_profile_name()),
                          collision=str(component.get_collision_enabled()),
                          materials=[component.get_material(i).get_path_name() if component.get_material(i) else None
                                     for i in range(component.get_num_materials())])
        result[actor.get_path_name()] = record
    return result


def collision_audit(world, actors):
    roofs = [a for a in actors if a.actor_has_tag("BB.Net.Roof")]
    if len(roofs) != 1:
        raise RuntimeError("Expected exactly one four-face roof collision actor")
    roof = roofs[0]
    component = roof.get_component_by_class(unreal.StaticMeshComponent)
    mesh = component.get_editor_property("static_mesh")
    body = mesh.get_editor_property("body_setup")
    if body.get_editor_property("collision_trace_flag") != unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE:
        raise RuntimeError("Roof must use triangle collision; a convex hull would close the eave")
    if not body.get_editor_property("double_sided_geometry"):
        raise RuntimeError("Roof collision must work from inside and outside")
    if str(component.get_collision_profile_name()) != "BlockAll":
        raise RuntimeError("Saved roof does not block spell/projectile and pawn queries")
    for actor in actors:
        if actor.actor_has_tag("BB.Net.Roof.Visual"):
            if actor.static_mesh_component.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION:
                raise RuntimeError("Decorative roof strands must not produce separate collision")
    samples = [(0, side * arena.HALF_WIDTH / 2) for side in (-1, 1)]
    samples += [(side * arena.BACKSTOP_X / 2, 0) for side in (-1, 1)]
    samples += [(x * arena.BACKSTOP_X / 2, y * arena.HALF_WIDTH / 2) for x in (-1, 1) for y in (-1, 1)]
    samples += [(0, 0)]
    traces = []
    for x, y in samples:
        z = arena.PYRAMID_APEX - (arena.PYRAMID_APEX - arena.ROOFLINE) * max(abs(x) / arena.BACKSTOP_X, abs(y) / arena.HALF_WIDTH)
        for direction in (-1, 1):
            hit = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(x, y, z - direction * 150),
                unreal.Vector(x, y, z + direction * 150), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                False, [], unreal.DrawDebugTrace.NONE, True)
            if hit is None:
                raise RuntimeError("Roof query escaped through face, hip, or apex: " + str((x, y, direction)))
            # Python folds NativeBreakFunc into HitResult conversions. Keys
            # come from GameplayStatics.BreakHitResult's named output params.
            details = hit.to_dict()
            if not details["blocking_hit"]:
                raise RuntimeError("Roof query returned a nonblocking hit")
            if details["hit_actor"] != roof or abs(details["impact_point"].z - z) > 0.5:
                raise RuntimeError("Roof query returned wrong actor or surface height")
            traces.append({"xy": [x, y], "expected_z": z,
                           "impact_z": details["impact_point"].z, "direction": direction})
    clear = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(0, 0, arena.ROOFLINE - 200),
        unreal.Vector(0, 0, arena.ROOFLINE + 200), unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
        False, [], unreal.DrawDebugTrace.NONE, True)
    if clear is not None:
        raise RuntimeError("Unexpected horizontal floor/cap blocks the hollow eave opening")
    return {"roof_actor": roof.get_path_name(), "collision": str(body.get_editor_property("collision_trace_flag")),
            "double_sided": True, "face_hip_apex_queries": traces, "hollow_eave_query_clear": True}


def build():
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    worlds = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8."):
        raise RuntimeError("This targeted stage is for the standalone UE 5.8 project only")
    project = Path(unreal.Paths.project_dir()).resolve()
    if project != (ROOT / "DevelopmentHarness").resolve():
        raise RuntimeError("Refusing to stage roof outside this repository's DevelopmentHarness")
    if levels.is_in_play_in_editor():
        raise RuntimeError("Stop PIE before staging the roof")
    require_clean()
    original = world_path(worlds.get_editor_world())
    if original not in MAPS:
        raise RuntimeError("Open BB_Regulation or BB_Arena first; this stage preserves other editor maps")
    for path in MAPS:
        if not (CONTENT / (path.removeprefix("/Basketbroom/") + ".umap")).is_file():
            raise RuntimeError("Both existing arena maps are required: " + path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    receipt_dir = ROOT / ".local/pyramid-net-stage" / stamp
    receipt_dir.mkdir(parents=True)
    backups = receipt_dir / "backups"
    backups.mkdir()
    backup_paths = [CONTENT / (path.removeprefix("/Basketbroom/") + ".umap") for path in MAPS]
    backup_paths += [CONTENT / "Art/Meshes" / (name + ".uasset") for name in arena.PYRAMID_MESHES]
    backup_paths += [CONTENT / "Art/Materials/M_BB_RoofNet.uasset"]
    for path in backup_paths:
        if path.exists():
            shutil.copy2(path, backups / path.name)
    report = {"status": "staging", "engine": unreal.SystemLibrary.get_engine_version(),
              "original_map": original, "maps": [], "backup_dir": str(backups),
              "mesh_sources": arena.generate_pyramid_meshes()}
    def save_report():
        (receipt_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    save_report()
    # Reimporting an asset referenced by the current map can mark that map dirty
    # even if its actors are untouched. Unload the already-clean arena first;
    # the disposable blank map is never saved. This also makes reruns safe.
    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    builder = arena.ArenaBuilder()
    for name in arena.PYRAMID_MESHES:
        builder.import_mesh(name)
    builder.configure_pyramid_collision()
    spec = next(s for s in arena.ARENA_PALETTE if s[0] == "M_BB_RoofNet")
    builder.material(*spec)
    for name in ("M_BB_Iron", "M_BB_Copper"):
        material = builder.assets.load_asset(arena.ART_PATH + "/Materials/" + name)
        if material is None:
            raise RuntimeError("Expected existing arena material: " + name)
        builder.materials[name] = material
    builder.physics = builder.assets.load_asset(arena.ART_PATH + "/Materials/PM_BB_Rebound")
    if builder.physics is None:
        raise RuntimeError("Expected existing rebound physical material")
    for path in MAPS:
        require_clean()
        if not levels.load_level(path):
            raise RuntimeError("Could not load " + path)
        actors = list(builder.levels.get_all_level_actors())
        before = snapshot(actors)
        mode = str(worlds.get_editor_world().get_world_settings().get_editor_property("default_game_mode"))
        for actor in actors:
            if not targeted(actor):
                continue
            if actor.get_actor_label() in ("Continuous open-crown rebound net", "Continuous closed-arena rebound net"):
                actor.set_actor_label("Continuous closed-arena rebound net")
            else:
                if not builder.levels.destroy_actor(actor):
                    raise RuntimeError("Could not replace owned prior roof actor")
        builder.actor(unreal.TargetPoint, "Pyramidion eave reference", (0, 0, arena.ROOFLINE),
                      tags=("BB.Roofline", "BB.Net.Eave"), folder="Gameplay anchors")
        builder.pyramid_net()
        after = snapshot(list(builder.levels.get_all_level_actors()))
        if before != after:
            differences = []
            for key in sorted(set(before) | set(after)):
                if before.get(key) != after.get(key):
                    old, new = before.get(key, {}), after.get(key, {})
                    differences.append({"actor": key, "changes": {
                        field: {"before": old.get(field), "after": new.get(field)}
                        for field in sorted(set(old) | set(new)) if old.get(field) != new.get(field)}})
            report["preservation_failure"] = {"map": path, "differences": differences}
            save_report()
            raise RuntimeError("An unrelated arena actor changed; current map left unsaved. "
                               + str(len(differences)) + " differences: " + json.dumps(differences[:5]))
        if mode != str(worlds.get_editor_world().get_world_settings().get_editor_property("default_game_mode")):
            raise RuntimeError("Unexpected game mode change; current map left unsaved")
        if not levels.save_current_level() or not levels.load_level(path):
            raise RuntimeError("Could not save and reload roof update for " + path)
        audit = collision_audit(worlds.get_editor_world(), list(builder.levels.get_all_level_actors()))
        file = CONTENT / (path.removeprefix("/Basketbroom/") + ".umap")
        report["maps"].append({"path": path, "unrelated_actors_preserved": len(before),
                               "game_mode_preserved": True, "saved_reloaded": True,
                               "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "audit": audit})
        save_report()
    if not levels.load_level(original):
        raise RuntimeError("Could not restore original editor map")
    require_clean()
    report["status"] = "passed"
    report["original_map_restored"] = True
    save_report()
    result = {"status": report["status"], "report": str(receipt_dir / "results.json"),
              "maps_updated": len(report["maps"]), "saved_collision_queries": 38}
    unreal.log("BASKETBROOM_PYRAMID_NET_STAGE " + json.dumps(result))
    return result


if __name__ == "__main__":
    RESULT = build()

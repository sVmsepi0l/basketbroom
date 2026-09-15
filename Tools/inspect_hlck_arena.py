"""Read-only inspection of the loaded Creator Kit Basketbroom arena.

Run through the Creator Kit Python bridge after build_arena_port.build().
The map must already be /Basketbroom/Maps/BB_Arena_Port. This script does not
reload, save, move actors, change collision, or take a screenshot. Its JSON
report includes the installed high-resolution screenshot API documentation.
"""
from collections import Counter
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import re
import time

import unreal

ROOT = Path(__file__).resolve().parents[1]
LEVEL_PATH = "/Basketbroom/Maps/BB_Arena_Port"
GENERATED_TAG = "BB.HLCK.ArenaPort.Generated.v1"
OWNER_TAG = "BB.HLCK.ArenaPort.Owner.v1"
REPORT = ROOT / ".local" / "hlck" / "arena-port-inspection.json"


def xyz(value):
    return [round(float(value.x), 3), round(float(value.y), 3), round(float(value.z), 3)]


def _write(report):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for attempt in range(6):
        try:
            temporary.replace(REPORT)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05)


def inspect():
    version = str(unreal.SystemLibrary.get_engine_version())
    if not re.match(r"^4\.27\.", version):
        raise RuntimeError("Arena inspection requires Creator Kit UE4.27: " + version)
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path()))
    if project.stem.lower() != "phoenix":
        raise RuntimeError("Run this inspection in the Phoenix Creator Kit project")
    descriptor = project.parent / "Mods" / "Basketbroom" / "Basketbroom.uplugin"
    expected = ROOT / "Mod" / "Basketbroom" / "Basketbroom.uplugin"
    if not descriptor.is_file() or descriptor.resolve() != expected.resolve():
        raise RuntimeError("The mounted mod does not resolve to this repository's UE4 mod")
    levels = unreal.EditorLevelLibrary
    world = levels.get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != LEVEL_PATH:
        raise RuntimeError("Open the exact BB_Arena_Port map before inspecting; no map will be loaded here")
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    if registry.is_loading_assets():
        raise RuntimeError("Wait for Creator Kit asset discovery to finish before inspection")
    actors = [actor for actor in levels.get_all_level_actors()
              if actor.get_path_name().startswith(LEVEL_PATH + ".")]
    generated = [actor for actor in actors if actor.actor_has_tag(GENERATED_TAG)]
    owners = [actor for actor in actors if actor.actor_has_tag(OWNER_TAG)]
    checks = []
    roof_amendment = None
    expansion_amendment = None
    geometry_dimensions = {"goal_x": 6400.8, "eave": 4206.24}
    roof_audit = None
    expected_generated, expected_meshes, expected_materials = 900, 14, 18
    if any(actor.actor_has_tag("BB.Net.Roof") for actor in actors):
        spec = importlib.util.spec_from_file_location("_bb_inspect_native_roof", ROOT / "Tools/stage_hlck_pyramid_net.py")
        roof = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(roof)
        if LEVEL_PATH == roof.MAPS[0]:
            baseline = json.loads((ROOT / ".local/hlck/arena-port-result.json").read_text(encoding="utf-8-sig"))["map_sha256"]
        elif LEVEL_PATH == roof.MAPS[1]:
            baseline = json.loads((ROOT / ".local/hlck/dungeon-anchor-result.json").read_text(encoding="utf-8-sig"))["map_sha256_after"]
        else:
            raise RuntimeError("No exact roof amendment contract exists for this map")
        expansion_spec = importlib.util.spec_from_file_location("_bb_inspect_native_expansion", ROOT / "Tools/stage_hlck_arena_expansion.py")
        expansion = importlib.util.module_from_spec(expansion_spec)
        expansion_spec.loader.exec_module(expansion)
        expansion_amendment = expansion.verified_amendment(LEVEL_PATH, baseline)
        if expansion_amendment is not None:
            geometry_dimensions = expansion_amendment["dimensions"]
            roof_audit = expansion.geometry_audit(unreal, world, actors, geometry_dimensions)
        else:
            roof_amendment = roof.verified_amendment(LEVEL_PATH, baseline)
            if roof_amendment is None:
                raise RuntimeError("The saved roof map lacks its verified original-map amendment chain")
            roof_audit = roof.collision_audit(unreal, world, actors)
        expected_generated, expected_meshes, expected_materials = 905, 18, 19

    def check(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("single_port_ownership_marker", len(owners) == 1 and isinstance(owners[0], unreal.TargetPoint) if owners else False,
          [actor.get_actor_label() for actor in owners])
    check("generated_geometry_actor_count", len(generated) == expected_generated, {"observed": len(generated), "expected": expected_generated})
    class_counts = Counter(actor.get_class().get_name() for actor in generated)
    mesh_paths, material_paths = set(), set()
    mesh_actor_count = 0
    collision_samples = []
    for actor in generated:
        # CameraActors contain an editor-only MatineeCam visualization mesh.
        # Only StaticMeshActors are authored arena geometry; editor icons must
        # not enter the mesh/material whitelist or decorative collision audit.
        if not isinstance(actor, unreal.StaticMeshActor):
            continue
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        if component is None:
            continue
        mesh_actor_count += 1
        mesh = component.get_editor_property("static_mesh")
        if mesh is not None:
            mesh_paths.add(mesh.get_path_name())
        material = component.get_material(0)
        if material is not None:
            material_paths.add(material.get_path_name())
        if actor.actor_has_tag("BB.ArtDetail") or actor.actor_has_tag("BB.Scenery"):
            profile = str(component.get_collision_profile_name())
            enabled = component.get_collision_enabled()
            collision_samples.append({"actor": actor.get_actor_label(), "profile": profile,
                                      "enabled": str(enabled), "no_collision": profile == "NoCollision" and enabled == unreal.CollisionEnabled.NO_COLLISION})
    check("detail_and_scenery_remain_nonblocking", len(collision_samples) == 15 and all(item["no_collision"] for item in collision_samples),
          collision_samples)
    imported_mesh_paths = sorted(path for path in mesh_paths if path.startswith("/Basketbroom/Art/Meshes/"))
    check("all_original_meshes_used", len(imported_mesh_paths) == expected_meshes, imported_mesh_paths)
    check("geometry_uses_port_palette", bool(material_paths) and all(path.startswith("/Basketbroom/Art/Materials/M_BBPort_") for path in material_paths),
          sorted(material_paths))
    records = registry.get_assets_by_path("/Basketbroom/Art/Materials", recursive=False, include_only_on_disk_assets=False) or []
    palette = sorted(str(record.object_path) for record in records
                     if str(record.asset_name).startswith("M_BBPort_") and str(record.asset_class) == "Material")
    physical = sorted(str(record.object_path) for record in records
                      if str(record.asset_name) == "PM_BBPort_Rebound" and str(record.asset_class) == "PhysicalMaterial")
    check("port_materials_and_rebound_material", len(palette) == expected_materials and len(physical) == 1,
          {"materials": palette, "physical_materials": physical})
    goal_positions = {}
    for tag, expected_count, height in (("BB.Goal.Large", 6, 2103.12), ("BB.Goal.Small", 2, 3048.0)):
        positions = [xyz(actor.get_actor_location()) for actor in generated if actor.actor_has_tag(tag)]
        goal_positions[tag] = positions
        expected_positions = [(side * geometry_dimensions["goal_x"], y, height) for side in (-1, 1)
                              for y in ((-1066.8, 0.0, 1066.8) if tag.endswith("Large") else (0.0,))]
        matches = len(positions) == expected_count and all(
            any(all(abs(actual[axis] - wanted[axis]) < 1.0 for axis in range(3)) for actual in positions)
            for wanted in expected_positions)
        check(tag + "_centers_cm", matches, positions)
    reference_tag = "BB.Net.Eave" if roof_amendment or expansion_amendment else "BB.NoCrown.Plane"
    eaves = [xyz(actor.get_actor_location()) for actor in generated if actor.actor_has_tag(reference_tag)]
    check("roofline_reference_and_current_collision", len(eaves) == 1 and abs(eaves[0][2] - geometry_dimensions["eave"]) < 1.0 if eaves else False,
          {"reference": eaves, "roof_amendment": roof_amendment, "expansion_amendment": expansion_amendment, "collision": roof_audit,
           "legacy_open_roof": roof_amendment is None and expansion_amendment is None})
    screenshot_api = getattr(getattr(unreal, "AutomationLibrary", None), "take_high_res_screenshot", None)
    screenshot_doc = str(screenshot_api.__doc__) if screenshot_api is not None else None
    report = {"status": "passed" if all(item["passed"] for item in checks) else "failed",
              "engine": version, "inspected_utc": datetime.utcnow().isoformat() + "Z", "map": world.get_path_name(),
              "scope": "Loaded editor-world geometry inspection; no reload, save, gameplay or screenshot performed",
              "map_dirty": any(package.get_name() == LEVEL_PATH for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
              "total_map_actors": len(actors), "generated_actors": len(generated),
              "generated_actor_classes": dict(sorted(class_counts.items())), "static_mesh_actors": mesh_actor_count,
              "unique_static_meshes": sorted(mesh_paths), "unique_assigned_materials": sorted(material_paths),
              "passed": sum(item["passed"] for item in checks), "failed": sum(not item["passed"] for item in checks),
              "checks": checks, "screenshot_api": "unreal.AutomationLibrary.take_high_res_screenshot",
              "screenshot_api_doc": screenshot_doc,
              "screenshot_note": "Use the installed signature below in a separate action; this inspection does not capture or synthesize an image."}
    _write(report)
    unreal.log("BASKETBROOM_HLCK_ARENA_INSPECTION " + report["status"] + " " + str(REPORT))
    unreal.log("BASKETBROOM_HLCK_SCREENSHOT_API\n" + (screenshot_doc or "Unavailable in this editor"))
    return report


if __name__ == "__main__":
    RESULT = inspect()

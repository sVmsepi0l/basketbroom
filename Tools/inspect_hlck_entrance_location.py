"""Inspect a fixed installed Overland area without actor edits or map saves.

open_area=True is an explicit editor-navigation option, guarded by empty dirty
map/content lists. It only loads one allowlisted existing map. No new streaming
level is added and no visibility, actor, package, database or registration API is
written. Read-only map hashes bracket loading and inspection.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
KIT_CONTENT = Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Content")
AREAS = {
    "quidditch": "/Game/Levels/Overland/SubLevels/CO_AG_Feature_Quidditch_01",
    "pitch": "/Game/Levels/Overland/SubLevels/HN_AZ_QuidditchPitchArea_Render",
    "stadium": "/Game/Levels/Overland/SubLevels/HN_AZ_Quidditch",
    "grounds": "/Game/Levels/Overland/HOG/HN_AZ",
    "overland": "/Game/Levels/Overland/Overland",
}


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def run(area="quidditch", open_area=False):
    report_path = ROOT / ".local/hlck" / ("entrance-location-" + (area if area in AREAS else "invalid") + ".json")
    result = {"status": "not_run", "read_only": True, "registration_invoked": False,
              "started_utc": datetime.now(timezone.utc).isoformat(), "area": area}
    try:
        if area not in AREAS or not isinstance(open_area, bool):
            raise RuntimeError("Choose a fixed known area and a boolean open_area")
        import unreal
        guard = module("_bb_location_guard", "Tools/load_hlck_dungeon.py")
        stage = module("_bb_location_stage", "Tools/stage_hlck_dungeon.py")
        anchors = module("_bb_location_records", "Tools/stage_hlck_dungeon_anchors.py")
        result["active_mod"] = guard.require_editor(unreal)
        result["dirty_before"] = guard.require_clean(unreal)
        path = AREAS[area]
        physical = KIT_CONTENT / (path[len("/Game/"):] + ".umap")
        physical.resolve().relative_to(KIT_CONTENT.resolve())
        if not physical.is_file() or not stage.records(unreal, path):
            raise RuntimeError("The allowlisted installed map is not available")
        hashes = {str(physical): stage.digest(physical)}
        for own_map in (stage.SOURCE_MAP, stage.TARGET_MAP):
            own_file = stage.checked_file(own_map, ".umap")
            hashes[str(own_file)] = stage.digest(own_file)
        result["previous_world"] = stage.world_path(unreal.EditorLevelLibrary.get_editor_world())
        if result["previous_world"] != path:
            if not open_area:
                raise RuntimeError("The selected area is not open; open_area is false")
            result["status"] = "loading"
            report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            if not unreal.EditorLevelLibrary.load_level(path):
                raise RuntimeError("The installed area could not be opened")
        world = unreal.EditorLevelLibrary.get_editor_world()
        if stage.world_path(world) != path:
            raise RuntimeError("The expected area is not open")
        result["world"] = path
        result["actors"] = []
        for actor in unreal.EditorLevelLibrary.get_all_level_actors():
            record = anchors.actor_record(actor)
            origin, extent = actor.get_actor_bounds(False)
            record["bounds"] = {"origin": anchors.xyz(origin), "extent": anchors.xyz(extent)}
            if isinstance(actor, unreal.StaticMeshActor):
                component = actor.get_component_by_class(unreal.StaticMeshComponent)
                mesh = component.get_editor_property("static_mesh")
                record["mesh"] = mesh.get_path_name() if mesh else None
                record["collision_profile"] = str(component.get_collision_profile_name())
            result["actors"].append(record)
        result["actor_count"] = len(result["actors"])
        result["read_only_api_docs"] = {}
        for cls, name in ((unreal.EditorLevelUtils, "get_levels"),
                          (unreal.GameplayStatics, "get_streaming_level"),
                          (unreal.SystemLibrary, "line_trace_single")):
            method = getattr(cls, name, None)
            result["read_only_api_docs"][name] = str(getattr(method, "__doc__", "") or "")
        result["native_sql_getter_available"] = callable(getattr(getattr(unreal, "DbGateway", None), "get_sql_edits_filename", None))
        active_content = unreal.GameModManagerSubsystem.get_active_mod_content_path_bp()
        active_path = Path(unreal.Paths.convert_relative_path_to_full(str(active_content))).resolve()
        if active_path != (ROOT / "Mod/Basketbroom/Content").resolve():
            raise RuntimeError("The active mod content path does not resolve to this repository")
        result["mod_sql_output"] = str(active_path / "ModEdits.sql")
        result["mod_sql_exists"] = (active_path / "ModEdits.sql").is_file()
        result["file_hashes_unchanged"] = all(stage.digest(Path(name)) == digest for name, digest in hashes.items())
        result["hashes"] = hashes
        if not result["file_hashes_unchanged"]:
            raise RuntimeError("A map's disk hash changed during read-only inspection")
        result["dirty_after"] = guard.require_clean(unreal)
        result["status"] = "inspected"
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "actors": result.get("actor_count"), "report": str(report_path)}


if __name__ == "__main__":
    args = globals().get("BRIDGE_ARGS", {})
    RESULT = run(area=args.get("area", "quidditch"), open_area=args.get("open_area", False))

"""Read-only map-save and subdivision diagnostics for the installed HLCK.

No map loads, asset edits/saves, registration, travel, or active-mod changes.
The parent task runs this through the existing editor bridge when convenient.
"""

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import traceback
import time

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/dungeon-stage-state.json"


def probe(inspect_recovery_contents=False):
    result = {"status": "not_run", "read_only": True,
              "started_utc": datetime.now(timezone.utc).isoformat()}
    try:
        import unreal
        spec = importlib.util.spec_from_file_location("_bb_hlck_stage_state", ROOT / "Tools/stage_hlck_dungeon.py")
        stage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stage)
        spec = importlib.util.spec_from_file_location("_bb_hlck_stage_state_guard", ROOT / "Mod/Tools/import_sources.py")
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        guard._editor()
        project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        if project != Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject").resolve():
            raise RuntimeError("Expected the exact installed Phoenix project")
        if unreal.EditorLevelLibrary.get_pie_worlds(True):
            raise RuntimeError("Stop PIE before the read-only stage probe")
        world = unreal.EditorLevelLibrary.get_editor_world()
        if stage.world_path(world) not in (stage.SOURCE_MAP, stage.TARGET_MAP):
            raise RuntimeError("Expected the source or staged dungeon arena")
        result["world"] = {"path": world.get_path_name(), "name": world.get_name(),
                           "outer": world.get_outer().get_path_name(),
                           "outermost": world.get_outermost().get_path_name()}
        result["dirty_maps"] = [item.get_path_name() for item in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
        result["map_api"] = {name: str(getattr(getattr(unreal.EditorLoadingAndSavingUtils, name, None), "__doc__", ""))
                             for name in ("save_map", "load_map", "get_dirty_map_packages")}
        result["map_files"] = {path: {"sha256": stage.digest(stage.checked_file(path, ".umap")),
                                          "registry": [{"package": str(entry.package_name),
                                                        "object": str(entry.object_path),
                                                        "class": str(entry.asset_class)}
                                                       for entry in stage.records(unreal, path)]}
                               for path in (stage.SOURCE_MAP, stage.TARGET_MAP)
                               if stage.checked_file(path, ".umap").is_file()}
        result["owners"] = [{"path": actor.get_path_name(), "tags": [str(tag) for tag in actor.get_editor_property("tags")]}
                            for actor in unreal.EditorLevelLibrary.get_all_level_actors()
                            if actor.actor_has_tag(stage.BASE_MARKER) or actor.actor_has_tag(stage.STAGE_MARKER)]
        result["active_mod"] = str(unreal.GameModManagerSubsystem.get_active_mod_name_bp())
        fields = ("DungeonName", "OwnerName", "MissionLock", "MissionStepLock", "OpenAfterMission", "PerceptionRadius", "ZoomFactor")
        struct = unreal.MapDungeonSubdivisionTable()
        result["subdivision_defaults"] = {field: str(struct.get_editor_property(field)) for field in
                                          ("dungeon_name", "owner_name", "mission_lock", "mission_step_lock", "open_after_mission", "perception_radius", "zoom_factor")}
        mission = struct.get_editor_property("mission_lock").get_editor_property("mission_name")
        result["mission_name_default"] = {"type": type(mission).__name__, "repr": repr(mission),
                                           "text": str(mission), "equals_empty_name": mission == unreal.Name("")}
        result["recovery_loaded_objects"] = {}
        result["find_object_api"] = str(getattr(unreal.find_object, "__doc__", ""))
        result["collect_garbage_api"] = str(getattr(getattr(unreal, "collect_garbage", None), "__doc__", ""))
        result["recovery_api"] = {name: {"available": hasattr(unreal, name), "doc": str(getattr(getattr(unreal, name, None), "__doc__", ""))}
                                  for name in ("get_objects_with_outer", "ObjectIterator")}
        result["system_gc_api"] = str(getattr(getattr(unreal.SystemLibrary, "collect_garbage", None), "__doc__", ""))
        for path in sorted((ROOT / "Mod/Basketbroom/Content/Recovery").glob("*.umap")):
            package = "/Basketbroom/Recovery/" + path.stem
            found = unreal.find_object(None, package + "." + path.stem)
            found_package = unreal.find_object(None, package)
            result["recovery_loaded_objects"][package] = {"world": found.get_path_name() if found else None,
                                                           "package": found_package.get_path_name() if found_package else None,
                                                           "sha256": stage.digest(path)}
            if found_package:
                result["recovery_loaded_objects"][package]["package_api"] = {name: str(getattr(getattr(found_package, name), "__doc__", ""))
                    for name in dir(found_package) if any(key in name for key in ("fully", "dirty", "load", "objects"))}
        if inspect_recovery_contents:
            packages = result["recovery_loaded_objects"]
            contents = {name: [] for name in packages}
            started = time.monotonic()
            scanned = 0
            complete = True
            for obj in unreal.ObjectIterator():
                scanned += 1
                outer = obj.get_outermost().get_path_name()
                if outer in contents and obj.get_path_name() != outer:
                    contents[outer].append({"path": obj.get_path_name(), "class": obj.get_class().get_path_name()})
                if scanned % 2048 == 0 and time.monotonic() - started > 20:
                    complete = False
                    break
            result["recovery_contents"] = {"complete": complete, "scanned_objects": scanned,
                                            "elapsed_seconds": time.monotonic() - started, "packages": contents}
        result["subdivision_tables"] = {}
        for path in (stage.SOURCE_SUBDIVISIONS, stage.BASE_SUBDIVISIONS, "/Game/UI/Map/UI_DT_MapDungeonSubdivisionTable"):
            table = unreal.load_asset(path)
            if table is None:
                result["subdivision_tables"][path] = {"error": "unavailable"}
                continue
            names = [str(name) for name in unreal.DataTableFunctionLibrary.get_data_table_row_names(table)]
            columns = {field: [str(value) for value in unreal.DataTableFunctionLibrary.get_data_table_column_as_string(table, field)]
                       for field in fields}
            result["subdivision_tables"][path] = {"names": names, "columns": columns}
        result["status"] = "complete"
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = probe(inspect_recovery_contents=globals().get("BRIDGE_ARGS", {}).get("inspect_recovery_contents", False))

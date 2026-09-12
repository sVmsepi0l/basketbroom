"""Read-only public reflection for the native entrance/SQL registration route."""
from datetime import datetime, timezone
import importlib.util
import json
import re
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/registration-api.json"


def run():
    result = {"status": "not_run", "read_only": True,
              "started_utc": datetime.now(timezone.utc).isoformat()}
    try:
        import unreal
        spec = importlib.util.spec_from_file_location("_bb_reg_api_guard", ROOT / "Tools/load_hlck_dungeon.py")
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        result["active_mod"] = guard.require_editor(unreal)
        result["dirty_before"] = guard.require_clean(unreal)
        result["classes"] = {}
        for name in ("BeaconManager", "DbGateway", "DungeonEntrancePlacement"):
            cls = getattr(unreal, name, None)
            item = {"available": cls is not None}
            if cls:
                item["doc"] = str(cls.__doc__)
                item["methods"] = {method: str(getattr(getattr(cls, method), "__doc__", ""))
                    for method in dir(cls) if any(token in method.lower() for token in
                        ("dungeon", "beacon", "query", "sql", "database", "editor"))}
                cdo = unreal.get_default_object(cls)
                if cdo:
                    filename = ROOT / ".local/hlck" / ("registration-api-" + name + ".t3d")
                    task = unreal.AssetExportTask()
                    task.object = cdo
                    task.filename = str(filename)
                    task.automated = True
                    task.prompt = False
                    task.replace_identical = True
                    task.exporter = unreal.ObjectExporterT3D()
                    item["exported"] = bool(unreal.Exporter.run_asset_export_task(task))
                    item["export"] = str(filename)
                    if not item["exported"] or not filename.is_file():
                        raise RuntimeError("Fresh native CDO export failed for " + name)
                elif name == "BeaconManager":
                    raise RuntimeError("The native manager has no default object to inspect")
            elif name == "BeaconManager":
                raise RuntimeError("The native manager class is unavailable")
            result["classes"][name] = item
        result["spawn_doc"] = str(unreal.EditorLevelLibrary.spawn_actor_from_class.__doc__)
        result["call_method_doc"] = str(unreal.Object.call_method.__doc__)
        exported = (ROOT / ".local/hlck/registration-api-BeaconManager.t3d").read_text(encoding="utf-8-sig")
        configured = re.search(r'DungeonEntranceClass=BlueprintGeneratedClass\x27"([^"]+)"', exported)
        if not configured:
            raise RuntimeError("The native manager export does not identify its entrance class")
        result["configured_entrance_class"] = configured.group(1)
        result["query_result_doc"] = str(unreal.SQLiteQueryResult.__doc__)
        result["query_row_doc"] = str(unreal.SQLiteQueryResultRow.__doc__)
        result["query_pair_doc"] = str(unreal.SQLiteKeyValuePair.__doc__)
        query = "SELECT DungeonName, EntranceIndex, XPos, YPos, ZPos, ZRot, Transient FROM DungeonEntrances WHERE DungeonName='Basketbroom_DungeonMap'"
        rows = unreal.DbGateway.db_editor_query(query)
        result["owned_rows"] = {"query": query, "returned": rows is not None}
        if rows is not None:
            result["owned_rows"]["members"] = [name for name in dir(rows) if not name.startswith("_")]
            result["owned_rows"]["tuple"] = str(rows.to_tuple())
            result["owned_rows"]["count"] = len(rows.result_rows)
        schedules = unreal.DbGateway.db_editor_query("SELECT LevelName,WorldKeys FROM SchedulesForLevels WHERE LevelName='Overland'")
        result["schedules"] = [{"fields": [str(pair.to_tuple()) for pair in row.fields]}
                               for row in schedules.result_rows]
        result["dirty_after"] = guard.require_clean(unreal)
        result["status"] = "inspected"
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = run()

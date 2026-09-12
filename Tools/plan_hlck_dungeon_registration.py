"""Read-only registration prerequisites; no entrance placement or native calls.

The exit and spawn must already pass inspection. Public reflection documents the
native endpoint used by the supplied entrance graph without invoking it. Separate
collision and native database probes document the selected location and SQL route.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/dungeon-registration-plan.json"


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def plan():
    result = {"status": "not_run", "read_only": True,
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "registration_invoked": False, "travel_invoked": False,
              "overland_loaded": False, "outside_entrance_placed": False}
    try:
        import unreal
        guard = module("_bb_registration_guard", "Tools/load_hlck_dungeon.py")
        stage = module("_bb_registration_stage", "Tools/stage_hlck_dungeon.py")
        result["active_mod"] = guard.require_editor(unreal)
        result["dirty_before"] = guard.require_clean(unreal)
        inspection = module("_bb_registration_inspection", "Tools/inspect_hlck_dungeon_anchors.py").inspect()
        if inspection.get("status") != "passed" or inspection.get("passed") != 27:
            raise RuntimeError("All 27 saved dungeon/anchor checks must pass first")
        result["checks_passed"] = 27
        result["prerequisites_proved"] = {
            "project": "Phoenix UE4.27.2", "mounted_mod": str(ROOT / "Mod/Basketbroom"),
            "map_and_row_name": stage.ROW_NAME, "required_map_suffix": "_DungeonMap",
            "dungeon_map": stage.TARGET_MAP,
            "dungeon_table": stage.DESTINATIONS[stage.SOURCE_DUNGEONS],
            "subdivision_table": stage.DESTINATIONS[stage.SOURCE_SUBDIVISIONS],
            "compiled_mutator": stage.DESTINATIONS[stage.SOURCE_MUTATOR],
            "compiled_entrance_with_row_handle": stage.DESTINATIONS[stage.SOURCE_ENTRANCE],
            "first_entry_spawn": "One ordinary PlayerStart; no _EXIT tag",
            "return_actor": stage.DESTINATIONS[stage.SOURCE_EXIT]}
        result["native_api_documents"] = {}
        for class_name, method_name in (
                ("BeaconManager", "register_transient_dungeon_entrance"),
                ("ModGameSupport", "get_composite_data_table_from_base")):
            cls = getattr(unreal, class_name, None)
            method = getattr(cls, method_name, None) if cls else None
            result["native_api_documents"][class_name + "." + method_name] = {
                "available": callable(method), "doc": str(getattr(method, "__doc__", "") or "")}
        result["inspected_template_event"] = {
            "event": "RegisterDungeon", "metadata": "CallInEditor=true",
            "flow": ["Read the selected DungeonName/DataTable row", "Validate the entrance data/marker",
                     "BeaconManager.RegisterTransientDungeonEntrance", "Print the result"],
            "native_inputs": ["DungeonName", "Position", "ZRot", "BeaconPosition", "EntranceIndex"],
            "source_export": str(ROOT / ".local/hlck/dungeon-probe/entrance_blueprint.t3d")}
        result["minimal_next_change"] = [
            "Load the clean Overland master and run register_hlck_dungeon.py with dry_run=True.",
            "Register through the public native BeaconManager endpoint using the verified return location and a co-located map beacon.",
            "Verify one live Transient=1 row, only owned ModEdits.sql changed, and installed database/map hashes unchanged.",
            "Test first entry and return, then navigation/minimap and match gameplay separately."]
        result["entrance_plan"] = {"position_cm": [329400.0, -466800.0, -85380.65625], "yaw_degrees": 180.0,
            "beacon": "co-located with return spawn", "entrance_index": 0,
            "sql_destination": str(ROOT / "Mod/Basketbroom/Content/ModEdits.sql"),
            "runtime_class": "/ModSupport/Blueprints/BP_DungeonEntrance.BP_DungeonEntrance_C",
            "map_actor_persistence_required": False}
        result["not_proved"] = ["Successful native registration readback", "Entry/return travel", "Navigation/minimap",
                                "Match gameplay in Phoenix", "Cloud-cooked game operation"]
        registrar = module("_bb_registration_saved_verifier", "Tools/register_hlck_dungeon.py")
        receipt_file = ROOT / ".local/hlck/dungeon-registration-result.json"
        if receipt_file.is_file():
            receipt = json.loads(receipt_file.read_text(encoding="utf-8-sig"))
            if receipt.get("status") == "registered":
                saved = registrar.verified_saved_registration(unreal, stage)
                result["saved_registration_verified"] = True
                result["registered_row"] = saved["row"]
                result["sql_sha256"] = saved["sql_sha256"]
                result["minimal_next_change"] = ["Validate actual first entry and return using the native game player.",
                    "Generate/validate navigation and minimap, then implement the separate match adapter."]
                result["not_proved"].remove("Successful native registration readback")
        result["official_guide"] = "https://support.curseforge.com/support/solutions/articles/9000259716-hogwarts-legacy-creators-level-design-environment"
        result["dirty_after"] = guard.require_clean(unreal)
        result["status"] = "prepared"
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = plan()

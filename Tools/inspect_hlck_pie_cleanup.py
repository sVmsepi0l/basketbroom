"""Record the owned editor's post-PIE state without saves or database queries."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/dungeon-pie-cleanup.json"
PROJECT = Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject")
WORLD = "/Basketbroom/Maps/Basketbroom_DungeonMap.Basketbroom_DungeonMap"


def write_report(report, result):
    """Publish complete JSON, retrying brief Windows reader locks only."""
    report.parent.mkdir(parents=True, exist_ok=True)
    temporary = report.with_name(report.name + "." + uuid.uuid4().hex + ".next")
    try:
        temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        for attempt in range(8):
            try:
                temporary.replace(report)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.025)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def run(unreal_module=None, report_path=None):
    report = Path(report_path) if report_path is not None else REPORT
    result = {
        "attempt_id": uuid.uuid4().hex,
        "process_id": os.getpid(),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "observed_utc": None,
        "completed_utc": None,
        "status": "inspecting",
        "error": None,
        "read_only": True, "database_queried": False, "assets_saved": False,
        "project": None, "active_mod": None, "editor_world": None,
        "pie_worlds": None, "dirty_maps": None, "dirty_content": None,
        "observer_still_registered": None,
        "clean_owned_editor": False,
    }
    # Invalidate a previous success before imports or queries can fail or stall.
    # A report I/O failure propagates: no inspection is reported as successful.
    write_report(report, result)
    try:
        if unreal_module is None:
            import unreal as unreal_module
        u = unreal_module
        project = Path(u.Paths.convert_relative_path_to_full(
            u.Paths.get_project_file_path())).resolve()
        result["project"] = str(project)
        if project != PROJECT.resolve():
            raise RuntimeError("Expected the exact installed Phoenix project")
        result["active_mod"] = str(u.GameModManagerSubsystem.get_active_mod_name_bp())
        if result["active_mod"] != "Basketbroom":
            raise RuntimeError("Expected the active Basketbroom mod")
        world = u.EditorLevelLibrary.get_editor_world()
        result["editor_world"] = world.get_path_name() if world else None
        result["pie_worlds"] = [item.get_path_name() for item in
                                u.EditorLevelLibrary.get_pie_worlds(True)]
        result["dirty_maps"] = [item.get_path_name() for item in
                                u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
        result["dirty_content"] = [item.get_path_name() for item in
                                   u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        result["observer_still_registered"] = getattr(
            u, "_basketbroom_hlck_dungeon_pie_smoke", None) is not None
        result["observed_utc"] = datetime.now(timezone.utc).isoformat()
        failures = []
        if result["editor_world"] != WORLD:
            failures.append("Expected the exact owned dungeon editor world")
        if result["pie_worlds"]:
            failures.append("PIE worlds remain")
        if result["dirty_maps"] or result["dirty_content"]:
            failures.append("Dirty packages remain")
        if result["observer_still_registered"]:
            failures.append("PIE observer remains registered")
        if failures:
            raise RuntimeError("; ".join(failures))
        result["clean_owned_editor"] = True
        result["status"] = "passed"
    except Exception as exc:
        result["status"] = "failed"
        result["clean_owned_editor"] = False
        result["error"] = type(exc).__name__ + ": " + str(exc)
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    write_report(report, result)
    return {"status": result["status"], "clean_owned_editor": result["clean_owned_editor"],
            "attempt_id": result["attempt_id"], "process_id": result["process_id"],
            "error": result["error"], "report": str(report)}


if __name__ == "__main__":
    RESULT = run()

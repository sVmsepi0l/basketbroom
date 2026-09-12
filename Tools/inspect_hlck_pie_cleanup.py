"""Record the owned editor's post-PIE state without saves or database queries."""
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/dungeon-pie-cleanup.json"


def run():
    import unreal
    project = Path(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.get_project_file_path())).resolve()
    if project != Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject").resolve():
        raise RuntimeError("Expected the exact installed Phoenix project")
    active = str(unreal.GameModManagerSubsystem.get_active_mod_name_bp())
    if active != "Basketbroom":
        raise RuntimeError("Expected the active Basketbroom mod")
    world = unreal.EditorLevelLibrary.get_editor_world()
    worlds = unreal.EditorLevelLibrary.get_pie_worlds(True)
    result = {
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True, "database_queried": False, "assets_saved": False,
        "active_mod": active,
        "editor_world": world.get_path_name() if world else None,
        "pie_worlds": [item.get_path_name() for item in worlds],
        "dirty_maps": [item.get_path_name() for item in
                       unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
        "dirty_content": [item.get_path_name() for item in
                          unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
        "observer_still_registered": getattr(
            unreal, "_basketbroom_hlck_dungeon_pie_smoke", None) is not None,
    }
    result["clean_owned_editor"] = (not worlds and not result["dirty_maps"]
        and not result["dirty_content"] and not result["observer_still_registered"]
        and result["editor_world"] ==
        "/Basketbroom/Maps/Basketbroom_DungeonMap.Basketbroom_DungeonMap")
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"clean_owned_editor": result["clean_owned_editor"], "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = run()

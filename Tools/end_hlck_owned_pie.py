"""End only the exact Basketbroom dungeon PIE after an observer startup failure."""
from pathlib import Path
import json
import re
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/dungeon-pie-recovery.json"
WORLD_NAME = "Basketbroom_DungeonMap"


def run():
    import unreal
    result = {"status": "not_run", "travel_invoked": False, "termination_requested": False}
    try:
        project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        if project != Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject").resolve():
            raise RuntimeError("Wrong project for owned PIE cleanup")
        if str(unreal.GameModManagerSubsystem.get_active_mod_name_bp()) != "Basketbroom":
            raise RuntimeError("Wrong active mod for owned PIE cleanup")
        worlds = unreal.EditorLevelLibrary.get_pie_worlds(True)
        paths = [world.get_path_name() for world in worlds]
        result["worlds_before"] = paths
        if len(paths) != 1 or re.fullmatch(
                r"/Basketbroom/Maps/UEDPIE_\d+_Basketbroom_DungeonMap\.Basketbroom_DungeonMap",
                paths[0]) is None:
            raise RuntimeError("Expected exactly the owned dungeon PIE; refusing other sessions")
        result["status"] = "ending_exact_owned_pie"
        REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        unreal.EditorLevelLibrary.editor_end_play()
        result["end_play_requested"] = True
        started = time.monotonic()
        state = {"handle": None}
        def tick(unused_delta):
            complete = False
            try:
                remaining = unreal.EditorLevelLibrary.get_pie_worlds(True)
                if remaining and time.monotonic() - started < 60:
                    return
                complete = True
                result["worlds_after"] = [world.get_path_name() for world in remaining]
                editor = unreal.EditorLevelLibrary.get_editor_world()
                result["editor_world"] = editor.get_path_name() if editor else None
                result["status"] = "ended" if not remaining else "cleanup_timeout"
                REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            except Exception:
                complete = True
                result["status"] = "failed"
                result["error"] = traceback.format_exc()
                REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            finally:
                if complete and state["handle"] is not None:
                    unreal.unregister_slate_post_tick_callback(state["handle"])
                    state["handle"] = None
        state["handle"] = unreal.register_slate_post_tick_callback(tick)
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
        REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = run()

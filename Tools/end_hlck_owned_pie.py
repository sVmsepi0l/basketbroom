"""end only the exact basketbroom dungeon pie after an observer startup failure."""
from pathlib import path
import json
import re
import time
import traceback

root = Path(__file__).resolve().parents[1]
report = root / ".local/hlck/dungeon-pie-recovery.json"
world_name = "basketbroom_dungeonmap"


def run():
    import unreal
    result = {"status": "not_run", "travel_invoked": false, "termination_requested": false}
    try:
        project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        if project != Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject").resolve():
            raise runtimeerror("wrong project for owned pie cleanup")
        if str(unreal.GameModManagerSubsystem.get_active_mod_name_bp()) != "Basketbroom":
            raise runtimeerror("wrong active mod for owned pie cleanup")
        worlds = unreal.EditorLevelLibrary.get_pie_worlds(True)
        paths = [world.get_path_name() for world in worlds]
        result["worlds_before"] = paths
        if len(paths) != 1 or re.fullmatch(
                r"/Basketbroom/Maps/UEDPIE_\d+_Basketbroom_DungeonMap\.Basketbroom_DungeonMap",
                paths[0]) is None:
            raise runtimeerror("expected exactly the owned dungeon pie; refusing other sessions")
        result["status"] = "ending_exact_owned_pie"
        REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        unreal.EditorLevelLibrary.editor_end_play()
        result["end_play_requested"] = true
        started = time.monotonic()
        state = {"handle": none}
        def tick(unused_delta):
            complete = false
            try:
                remaining = unreal.EditorLevelLibrary.get_pie_worlds(True)
                if remaining and time.monotonic() - started < 60:
                    return
                complete = true
                result["worlds_after"] = [world.get_path_name() for world in remaining]
                editor = unreal.EditorLevelLibrary.get_editor_world()
                result["editor_world"] = editor.get_path_name() if editor else none
                result["status"] = "ended" if not remaining else "cleanup_timeout"
                REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            except Exception:
                complete = true
                result["status"] = "failed"
                result["error"] = traceback.format_exc()
                REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            finally:
                if complete and state["handle"] is not None:
                    unreal.unregister_slate_post_tick_callback(state["handle"])
                    state["handle"] = none
        state["handle"] = unreal.register_slate_post_tick_callback(tick)
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
        REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "report": str(report)}


if __name__ == "__main__":
    result = run()

"""Open only the saved repo dungeon after authenticated, clean-editor guards."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/dungeon-open-result.json"


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_editor(unreal):
    load_module("_bb_dungeon_open_import_guard", "Mod/Tools/import_sources.py")._editor()
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
    if project != Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject").resolve():
        raise RuntimeError("Expected the exact installed Phoenix project")
    if unreal.EditorLevelLibrary.get_pie_worlds(True):
        raise RuntimeError("Stop PIE before dungeon authoring")
    active = str(unreal.GameModManagerSubsystem.get_active_mod_name_bp())
    if active != "Basketbroom":
        raise RuntimeError("Select existing Basketbroom with Set Mod before dungeon authoring")
    return active


def require_clean(unreal):
    result = {}
    for kind in ("map", "content"):
        method = getattr(unreal.EditorLoadingAndSavingUtils, "get_dirty_" + kind + "_packages", None)
        if not callable(method):
            raise RuntimeError("Cannot verify unsaved " + kind + " packages")
        result[kind] = [item.get_path_name() for item in method()]
    if any(result.values()):
        raise RuntimeError("Unsaved packages exist; no world will be replaced: " + json.dumps(result))
    return result


def run():
    result = {"status": "not_run", "started_utc": datetime.now(timezone.utc).isoformat(),
              "registration_invoked": False, "travel_invoked": False}
    try:
        import unreal
        result["active_mod"] = require_editor(unreal)
        result["dirty_before"] = require_clean(unreal)
        stage = load_module("_bb_dungeon_open_stage", "Tools/stage_hlck_dungeon.py")
        physical = stage.checked_file(stage.TARGET_MAP, ".umap")
        entries = stage.records(unreal, stage.TARGET_MAP)
        if not physical.is_file() or len(entries) != 1 or str(entries[0].asset_class) != "World":
            raise RuntimeError("The saved repo dungeon is not a registered native map")
        before = stage.digest(physical)
        source_before = stage.digest(stage.checked_file(stage.SOURCE_MAP, ".umap"))
        current = stage.world_path(unreal.EditorLevelLibrary.get_editor_world())
        result["previous_world"] = current
        if current != stage.TARGET_MAP and not unreal.EditorLevelLibrary.load_level(stage.TARGET_MAP):
            raise RuntimeError("Could not open the saved dungeon")
        if stage.world_path(unreal.EditorLevelLibrary.get_editor_world()) != stage.TARGET_MAP:
            raise RuntimeError("The expected dungeon world is not open")
        owners = [actor for actor in unreal.EditorLevelLibrary.get_all_level_actors() if actor.actor_has_tag(stage.BASE_MARKER)]
        if len(owners) != 1 or not owners[0].actor_has_tag(stage.STAGE_MARKER):
            raise RuntimeError("The opened dungeon lacks exact staging ownership")
        if stage.digest(physical) != before or stage.digest(stage.checked_file(stage.SOURCE_MAP, ".umap")) != source_before:
            raise RuntimeError("An arena file unexpectedly changed while opening")
        result["dirty_after"] = require_clean(unreal)
        result.update(status="opened", world=stage.TARGET_MAP, map_sha256=before, source_sha256=source_before)
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = run()

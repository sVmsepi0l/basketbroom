"""Release only verified inactive recovery packages before an external move.

No file moves, map loads/saves, registration, or gameplay actions occur here.
The caller must check the resulting hashes/unloaded status before moving files.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/recovery-release.json"


def run():
    result = {"status": "not_run", "released_utc": datetime.now(timezone.utc).isoformat(), "packages": []}
    try:
        import unreal
        spec = importlib.util.spec_from_file_location("_bb_hlck_release_stage", ROOT / "Tools/stage_hlck_dungeon.py")
        stage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stage)
        spec = importlib.util.spec_from_file_location("_bb_hlck_release_guard", ROOT / "Mod/Tools/import_sources.py")
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        guard._editor()
        project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        if project != Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject").resolve():
            raise RuntimeError("Expected the exact installed Phoenix project")
        if unreal.EditorLevelLibrary.get_pie_worlds(True):
            raise RuntimeError("Stop PIE before releasing inactive recovery packages")
        world = unreal.EditorLevelLibrary.get_editor_world()
        if stage.world_path(world) != stage.TARGET_MAP:
            raise RuntimeError("The staged dungeon target must remain the current world")
        stage.require_clean_maps(unreal)
        probe = json.loads((ROOT / ".local/hlck/dungeon-stage-state.json").read_text(encoding="utf-8"))
        if probe.get("status") != "complete" or probe.get("world", {}).get("outermost") != stage.TARGET_MAP:
            raise RuntimeError("A completed target-world recovery probe is required")
        assets = probe.get("recovery_loaded_objects", {})
        if not assets:
            raise RuntimeError("The read-only probe did not identify a recovery package")
        source_before = stage.digest(stage.checked_file(stage.SOURCE_MAP, ".umap"))
        target_before = stage.digest(stage.checked_file(stage.TARGET_MAP, ".umap"))
        dirty_content = {item.get_path_name() for item in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
        for package, evidence in assets.items():
            if not re.fullmatch(r"/Basketbroom/Recovery/BB_SourceRecovery_\d{8}_\d{6}_\d{6}_[0-9a-f]{8}", package):
                raise RuntimeError("Refusing a package outside exact generated recovery naming")
            physical = stage.checked_file(package, ".umap")
            if not physical.is_file() or stage.digest(physical) != evidence["sha256"] or package in dirty_content:
                raise RuntimeError("Recovery package differs from the read-only proof or has unsaved content")
            loaded = unreal.find_object(None, package)
            unload_result = unreal.EditorLoadingAndSavingUtils.unload_packages([loaded]) if loaded is not None else None
            found_world = unreal.find_object(None, package + "." + physical.stem)
            found_package = unreal.find_object(None, package)
            entry = {"package": package, "file": str(physical), "sha256": evidence["sha256"],
                     "unload_result": str(unload_result), "unloaded": found_world is None and found_package is None}
            result["packages"].append(entry)
            if stage.digest(physical) != evidence["sha256"]:
                raise RuntimeError("Recovery changed; do not move its file")
            if not entry["unloaded"]:
                # The Python wrapper can keep an otherwise unloaded Package
                # alive during this call. The public collection API runs at
                # frame end; a later read-only probe must confirm its absence.
                loaded = found_world = found_package = None
                unreal.SystemLibrary.collect_garbage()
        if stage.world_path(unreal.EditorLevelLibrary.get_editor_world()) != stage.TARGET_MAP:
            raise RuntimeError("Current world unexpectedly changed while releasing recovery")
        stage.require_clean_maps(unreal)
        if stage.digest(stage.checked_file(stage.SOURCE_MAP, ".umap")) != source_before or stage.digest(stage.checked_file(stage.TARGET_MAP, ".umap")) != target_before:
            raise RuntimeError("An arena file unexpectedly changed while releasing recovery")
        result.update(status="released" if all(item["unloaded"] for item in result["packages"]) else "release_requested_verify_next_frame", current_world=stage.TARGET_MAP,
                      source_sha256=source_before, target_sha256=target_before)
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = run()

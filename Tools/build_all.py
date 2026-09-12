r"""Rebuild and save the complete standalone UE5.8 Basketbroom training game.

Run in the active project's editor Python console after saving your work:
    import runpy; runpy.run_path(r'C:\Git\basketbroom\Tools\build_all.py', run_name='__main__')

Imports explicitly call build(): individual modules need not have a __main__
entry point. Gameplay runs in the resulting Blueprints, not this authoring code.
"""

import importlib
import json
import os
from pathlib import Path
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
STAGES = (
    "build_audio", "build_gameplay", "build_arena", "build_hud",
    "stage_game", "build_bots", "stage_bots",
)


def build():
    try:
        import unreal
    except ImportError as error:
        raise RuntimeError("Run build_all.py inside the Basketbroom Unreal Engine 5.8 editor.") from error

    engine_version = unreal.SystemLibrary.get_engine_version()
    if not engine_version.startswith("5.8."):
        raise RuntimeError("Basketbroom requires Unreal Engine 5.8; current engine: " + engine_version)
    expected_project = (ROOT / "DevelopmentHarness").resolve()
    actual_project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    if actual_project != expected_project:
        raise RuntimeError("Open %s before rebuilding; current project is %s" % (expected_project, actual_project))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("Stop Play In Editor before rebuilding Basketbroom.")

    os.environ["BASKETBROOM_REPO"] = str(ROOT)
    tools_path = str(ROOT / "Tools")
    if tools_path not in sys.path:
        sys.path.insert(0, tools_path)
    report_path = ROOT / ".local" / "build-all-results.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    report = {"status": "running", "engine": engine_version, "project": str(actual_project), "stages": []}

    def save_report():
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        report_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    save_report()
    try:
        importlib.reload(importlib.import_module("bp_graph"))
        for name in STAGES:
            entry = {"name": name, "status": "running"}
            report["stages"].append(entry)
            save_report()
            unreal.log("BASKETBROOM BUILD: " + name)
            module = importlib.reload(importlib.import_module(name))
            if name == "build_gameplay":
                # Existing assets must also receive the current source graphs.
                module.BRIDGE_ARGS = {"rebuild": ["manager", "ball", "broom"]}
            result = module.build()
            entry.update(status="complete", result=result.get_path_name() if hasattr(result, "get_path_name") else result)
            save_report()
        report["status"] = "complete"
        save_report()
        unreal.log("BASKETBROOM_BUILD_ALL_COMPLETE " + str(report_path))
        return report
    except Exception:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
        if report["stages"] and report["stages"][-1]["status"] == "running":
            report["stages"][-1]["status"] = "failed"
        save_report()
        unreal.log_error(report["error"])
        raise


if __name__ == "__main__":
    RESULT = build()

"""Request a genuine UE4.27 viewport image from the loaded port's hero camera.

Run in Creator Kit Python after inspect_hlck_arena.py. This uses the signature
observed in the installed engine, requests a 1-second delay, and returns while
AutomationEditorTask finishes. The helper does not reload or save the world.
"""
from datetime import datetime
import json
from pathlib import Path
import re

import unreal

ROOT = Path(__file__).resolve().parents[1]
LEVEL_PATH = "/Basketbroom/Maps/BB_Arena_Port"
OUTPUT = ROOT / "Docs" / "Screenshots" / "hlck-arena.png"
CAPTURE_NAME = "Basketbroom_HLCK_Arena.png"
REPORT = ROOT / ".local" / "hlck" / "arena-capture-request.json"
CAPTURE_TASK = None


def capture():
    global CAPTURE_TASK
    version = str(unreal.SystemLibrary.get_engine_version())
    if not re.match(r"^4\.27\.", version):
        raise RuntimeError("Capture requires the UE4.27 Creator Kit")
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path()))
    if project.stem.lower() != "phoenix":
        raise RuntimeError("Capture requires the Phoenix project")
    descriptor = project.parent / "Mods" / "Basketbroom" / "Basketbroom.uplugin"
    if not descriptor.is_file() or descriptor.resolve() != (ROOT / "Mod" / "Basketbroom" / "Basketbroom.uplugin").resolve():
        raise RuntimeError("The mounted Basketbroom mod is not this repository's UE4 port")
    levels = unreal.EditorLevelLibrary
    world = levels.get_editor_world()
    if world is None or world.get_path_name().split(".")[0] != LEVEL_PATH:
        raise RuntimeError("The exact BB_Arena_Port world must already be open")
    if levels.get_pie_worlds(include_dedicated_server=True):
        raise RuntimeError("End Creator Kit Play In Editor before capturing the arena viewport")
    cameras = [actor for actor in levels.get_all_level_actors()
               if isinstance(actor, unreal.CameraActor)
               and actor.get_path_name().startswith(LEVEL_PATH + ".")
               and actor.actor_has_tag("BB.Camera.Hero")
               and actor.get_actor_label() == "BB Hero Camera"]
    if len(cameras) != 1:
        raise RuntimeError("Expected exactly one actual BB Hero Camera in the port arena")
    camera = cameras[0]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    generated = project.parent / "Saved" / "Screenshots" / "Windows" / CAPTURE_NAME
    # Installed signature: (res_x, res_y, filename, camera=None,
    # mask_enabled=False, capture_hdr=False, comparison_tolerance=LOW,
    # comparison_notes='', delay=0.0) -> AutomationEditorTask.
    CAPTURE_TASK = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=1600, res_y=900, filename=CAPTURE_NAME, camera=camera,
        mask_enabled=False, capture_hdr=False, comparison_notes="Basketbroom UE4.27 original arena port",
        delay=1.0)
    if CAPTURE_TASK is None:
        raise RuntimeError("Creator Kit did not return a screenshot task")
    report = {"status": "requested", "requested_utc": datetime.utcnow().isoformat() + "Z",
              "engine": version, "map": world.get_path_name(), "camera": camera.get_path_name(),
              "width": 1600, "height": 900, "delay_seconds": 1.0,
              "capture_filename": CAPTURE_NAME, "generated_output": str(generated.resolve()),
              "intended_repo_output": str(OUTPUT.resolve()),
              "task": str(CAPTURE_TASK), "note": "Check the generated PNG after the editor task finishes, then copy it unchanged to intended_repo_output. This request is not a capture-success claim."}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    unreal.log("BASKETBROOM_HLCK_ARENA_CAPTURE_REQUESTED " + str(generated))
    return report


if __name__ == "__main__":
    RESULT = capture()

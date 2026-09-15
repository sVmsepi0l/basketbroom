"""Rebuild training match, balls, bots and HUD for the expanded closed arena.

Run through the editor bridge with {} after the native roof map stage. Requires
PIE stopped and clean saved work. Maps, pawn and game mode stay intact. Bot graph goals move with the arena. Use {"hud_only": true} for a label-only refresh.
"""
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import unreal

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "DevelopmentHarness/Plugins/Basketbroom/Content"
OWNED = ("BP_BBMatch", "BP_BBBall", "BP_BBHUD", "BP_BBBot")
MAPS = ("BB_Arena", "BB_Regulation")


def clean():
    saving = unreal.EditorLoadingAndSavingUtils
    dirty = [p.get_path_name() for p in list(saving.get_dirty_map_packages()) + list(saving.get_dirty_content_packages())]
    if dirty:
        raise RuntimeError("Preserving unsaved packages before training graph rebuild: " + ", ".join(dirty))


def hashes():
    return {p.relative_to(CONTENT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in CONTENT.rglob("*") if p.is_file() and p.suffix in (".umap", ".uasset")}


def build():
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    worlds = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if levels.is_in_play_in_editor():
        raise RuntimeError("Stop PIE before rebuilding training roof graphs")
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8."):
        raise RuntimeError("Training graph stage requires the standalone UE 5.8 editor")
    if Path(unreal.Paths.project_dir()).resolve() != (ROOT / "DevelopmentHarness").resolve():
        raise RuntimeError("Refusing to rebuild graphs outside this repository's DevelopmentHarness")
    clean()
    world = worlds.get_editor_world()
    original = world.get_path_name().split(".")[0] if world else None
    if original not in tuple("/Basketbroom/Maps/" + n for n in MAPS):
        raise RuntimeError("Open saved BB_Regulation or BB_Arena first")
    owned = ("BP_BBHUD",) if globals().get("BRIDGE_ARGS", {}).get("hud_only", False) else OWNED
    paths = [CONTENT / "Blueprints" / (name + ".uasset") for name in owned]
    if not all(p.is_file() for p in paths):
        raise RuntimeError("This is a targeted rebuild; the selected existing Blueprints are required")
    receipt = ROOT / ".local/training-pyramid-stage" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    receipt.mkdir(parents=True)
    before = hashes()
    for p in paths:
        shutil.copy2(p, receipt / p.name)
    spec = importlib.util.spec_from_file_location("basketbroom_training_pyramid_source", ROOT / "Tools/build_gameplay.py")
    gameplay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gameplay)
    # The generated actors must be unloaded while their variable tables change.
    # The disposable blank map is never saved, and no existing map is modified.
    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    rebuilt = [] if owned == ("BP_BBHUD",) else [gameplay.make_manager(), gameplay.make_ball()]
    hud_spec = importlib.util.spec_from_file_location("basketbroom_training_pyramid_hud", ROOT / "Tools/build_hud.py")
    hud = importlib.util.module_from_spec(hud_spec)
    hud_spec.loader.exec_module(hud)
    rebuilt.append(hud.build())
    if owned != ("BP_BBHUD",):
        bot_spec = importlib.util.spec_from_file_location("basketbroom_training_bots", ROOT / "Tools/build_bots.py")
        bots = importlib.util.module_from_spec(bot_spec)
        bot_spec.loader.exec_module(bots)
        rebuilt.append(bots.build())
    for bp in rebuilt:
        if bp.get_editor_property("status") == unreal.BlueprintStatus.BS_ERROR:
            raise RuntimeError("Training Blueprint compile failed: " + bp.get_path_name())
    after = hashes()
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    allowed = {"Blueprints/" + name + ".uasset" for name in owned}
    if set(changed) - allowed:
        raise RuntimeError("Unexpected saved content changed: " + str(changed))
    if not levels.load_level(original):
        raise RuntimeError("Could not restore original saved map after training graph rebuild")
    clean()
    result = {"status": "passed", "blueprints": [b.get_path_name() for b in rebuilt],
              "changed_content": changed, "maps_unchanged": True, "other_assets_unchanged": True,
              "editor_map_restored": original, "saved_content_sha256": {p: after[p] for p in changed},
              "runtime_validation_pending": True}
    path = receipt / "results.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    unreal.log("BASKETBROOM_TRAINING_PYRAMID_STAGE " + json.dumps(result))
    return {"status": "passed", "report": str(path), "blueprints_rebuilt": len(rebuilt),
            "runtime_validation_pending": True}


if __name__ == "__main__":
    RESULT = build()

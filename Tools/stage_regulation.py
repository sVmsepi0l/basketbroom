"""Derive a native UE5.8 regulation map while preserving the training map."""

import importlib.util as _arena_importlib
from pathlib import Path as _ArenaPath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)
from pathlib import Path
import sys
import unreal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "Tools"))
from stage_game import set_ini_values
SOURCE = "/Basketbroom/Maps/BB_Arena"
DESTINATION = "/Basketbroom/Maps/BB_Regulation"

def build():
    game_mode = unreal.load_class(None, "/Script/BasketbroomRuntime.BBGameMode")
    if game_mode is None:
        raise RuntimeError("Compile BasketbroomDevEditor with native module and reopen the editor first")
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    worlds = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if levels.is_in_play_in_editor():
        raise RuntimeError("Stop PIE before staging the regulation map")
    if not unreal.EditorAssetLibrary.does_asset_exist(SOURCE):
        raise RuntimeError("Build the training arena before staging regulation")
    current = worlds.get_editor_world()
    if current and current.get_path_name().split(".", 1)[0] in (SOURCE, DESTINATION):
        if not levels.save_current_level():
            raise RuntimeError("Could not save the current Basketbroom map")
    created = not unreal.EditorAssetLibrary.does_asset_exist(DESTINATION)
    # NewLevelFromTemplate loads into a separate package and cannot overwrite
    # the source. SaveCurrentLevelAs is not a UE5.8 LevelEditorSubsystem API.
    if created:
        if not levels.new_level_from_template(DESTINATION, SOURCE):
            raise RuntimeError("Could not create regulation map from the arena")
    elif not levels.load_level(DESTINATION):
        raise RuntimeError("Could not load the existing regulation map")
    world = worlds.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != DESTINATION:
        raise RuntimeError("Editor did not select the expected regulation map")
    for actor in actors.get_all_level_actors():
        if any(actor.actor_has_tag(tag) for tag in ("BB.Gameplay", "BB.Bot", "BB.Regulation")):
            if not actors.destroy_actor(actor):
                raise RuntimeError("Could not remove a prior generated gameplay actor")
    start = actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(-4400*dimensions.LINEAR_SCALE,0,1400),unreal.Rotator(pitch=0,yaw=0,roll=0))
    if start is None:
        raise RuntimeError("Could not create the regulation PlayerStart")
    start.set_actor_label("BB Regulation Player Start")
    start.set_editor_property("tags", [unreal.Name("BB.Regulation"), unreal.Name("BB.Spawn")])
    start.set_folder_path("Basketbroom/Regulation")
    world.get_world_settings().set_editor_property("default_game_mode",game_mode)
    if not levels.save_current_level():
        raise RuntimeError("Could not save the native regulation map")
    set_ini_values(ROOT / "DevelopmentHarness" / "Config" / "DefaultEngine.ini",
        "/Script/EngineSettings.GameMapsSettings", {
            "EditorStartupMap":DESTINATION, "GameDefaultMap":DESTINATION,
            "GlobalDefaultGameMode":"/Script/BasketbroomRuntime.BBGameMode"})
    unreal.log("Basketbroom native regulation map staged: " + DESTINATION)
    return {"map":DESTINATION,"game_mode":str(game_mode),"created":created}

if __name__ == "__main__":
    build()

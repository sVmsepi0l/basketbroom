"""Read-only PIE native match progress for long-running validation."""
import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
cls = unreal.load_class(None, "/Script/BasketbroomRuntime.BBMatchState")
actors = unreal.GameplayStatics.get_all_actors_of_class(world, cls) if world and cls else []
RESULT = {"read_only": True, "world": world.get_path_name() if world else None}
if len(actors) == 1:
    match = actors[0]
    RESULT.update({name: match.get_editor_property(name) for name in
        ("seconds_left", "live_seconds", "quarter", "phase", "status", "live", "bloodbroom")})
    RESULT["time_dilation"] = unreal.GameplayStatics.get_global_time_dilation(world)

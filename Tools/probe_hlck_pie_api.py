"""Read-only discovery of public Creator Kit PIE controls and runtime query APIs."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/pie-api.json"


def run():
    result = {"status": "not_run", "read_only": True, "started_utc": datetime.now(timezone.utc).isoformat()}
    try:
        import unreal
        spec = importlib.util.spec_from_file_location("_bb_pie_api_guard", ROOT / "Tools/load_hlck_dungeon.py")
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        result["active_mod"] = guard.require_editor(unreal)
        result["dirty_before"] = guard.require_clean(unreal)
        world = unreal.EditorLevelLibrary.get_editor_world()
        if world.get_path_name().split(".", 1)[0] != "/Basketbroom/Maps/Basketbroom_DungeonMap":
            raise RuntimeError("Open only the saved owned dungeon before the PIE probe")
        result["world"] = world.get_path_name()
        result["controls"] = {}
        for name in dir(unreal):
            if not any(word in name for word in ("Editor", "Automation", "Automated", "PIE")):
                continue
            cls = getattr(unreal, name)
            methods = {}
            for method in dir(cls):
                if any(word in method.lower() for word in ("play_session", "begin_play", "end_play", "pie_", "editor_play", "simulate")):
                    member = getattr(cls, method, None)
                    if callable(member):
                        methods[method] = str(getattr(member, "__doc__", ""))
            if methods:
                result["controls"][name] = methods
        result["query_docs"] = {}
        for class_name, names in {
                "EditorLevelLibrary": ["get_pie_worlds", "editor_request_end_play"],
                "GameplayStatics": ["get_game_mode", "get_game_instance", "get_player_controller", "get_player_pawn", "get_all_actors_of_class"],
                "BeaconManager": ["register_dungeon_exit", "get_dungeon_exit"],
                "CharacterMovementComponent": ["is_falling", "is_moving_on_ground"],
                "ModGameSupport": ["get_composite_data_table_from_base"],
                "UGCBlueprintLibrary": ["get_ugc_registry", "get_ugc_data_table"],
                "UGCRegistry": ["get_mod_table_for_base_table"],
                "Controller": ["get_pawn", "get_controlled_pawn", "is_local_controller"],
                "PrimitiveComponent": ["get_generate_overlap_events", "get_collision_enabled"],
                "SphereComponent": ["get_scaled_sphere_radius"]}.items():
            cls = getattr(unreal, class_name, None)
            result["query_docs"][class_name] = {name: str(getattr(getattr(cls, name, None), "__doc__", "")) for name in names}
        mode_class = unreal.EditorAssetLibrary.load_blueprint_class("/Game/Data/GameMode/Phoenix_Game_Mode")
        mode = unreal.get_default_object(mode_class)
        result["native_game_defaults"] = {"mode": mode_class.get_path_name()}
        for name in ("default_pawn_class", "player_controller_class", "hud_class"):
            value = mode.get_editor_property(name)
            result["native_game_defaults"][name] = value.get_path_name() if value else None
        result["dirty_after"] = guard.require_clean(unreal)
        result["status"] = "inspected"
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = run()

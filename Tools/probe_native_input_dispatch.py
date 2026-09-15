"""Read-only native PIE input-dispatch snapshot. Never queues input or changes PIE."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/ue5/native-input-dispatch.json"


def optional_call(obj, name, *args):
    method = getattr(obj, name, None) if obj is not None else None
    if not callable(method):
        return {"available": False, "reason": "not reflected"}
    try:
        value = method(*args)
        return value.get_path_name() if hasattr(value, "get_path_name") else value
    except Exception as error:
        return {"available": False, "reason": str(error)[:180]}


def prop(obj, name):
    if obj is None:
        return None
    aliases = [name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()]
    if name.startswith("b") and len(name) > 1 and name[1].isupper():
        aliases.append(re.sub(r"(?<!^)(?=[A-Z])", "_", name[1:]).lower())
    for key in aliases:
        try:
            value = obj.get_editor_property(key)
            return value.get_path_name() if hasattr(value, "get_path_name") else value
        except Exception:
            pass
    return {"available": False, "reason": "not reflected"}


def path(obj):
    return obj.get_path_name() if obj else None


def actor(obj):
    if obj is None:
        return None
    return dict(path=path(obj), actor_class=path(obj.get_class()),
                tick_enabled=optional_call(obj, "is_actor_tick_enabled"),
                tick_interval_seconds=optional_call(obj, "get_actor_tick_interval"),
                authority=optional_call(obj, "has_authority"),
                local_role=optional_call(obj, "get_local_role"),
                actor_custom_dilation=prop(obj, "CustomTimeDilation"))


def main():
    import unreal
    data = dict(sampled_utc=datetime.now(timezone.utc).isoformat(), process_id=os.getpid(),
                engine=unreal.SystemLibrary.get_engine_version(), project=unreal.Paths.project_dir(),
                read_only=True, status="not_run", report=str(REPORT))
    try:
        level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        data["pie_active"] = level.is_in_play_in_editor()
        world = editor.get_game_world() if data["pie_active"] else None
        data["editor_world"] = path(editor.get_editor_world())
        if world is None:
            data["reason"] = "No active PIE game world; no input or editor action performed"
        else:
            data["world"] = dict(path=path(world), world_type=prop(world, "WorldType"),
                                 net_mode=optional_call(world, "get_net_mode"),
                                 standalone=unreal.SystemLibrary.is_standalone(world),
                                 server=unreal.SystemLibrary.is_server(world),
                                 dedicated_server=unreal.SystemLibrary.is_dedicated_server(world),
                                 paused=unreal.GameplayStatics.is_game_paused(world),
                                 game_seconds=unreal.GameplayStatics.get_time_seconds(world),
                                 time_dilation=unreal.GameplayStatics.get_global_time_dilation(world))
            data["unattended"] = optional_call(unreal.SystemLibrary, "is_unattended")
            pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
            controller = unreal.GameplayStatics.get_player_controller(world, 0)
            game_mode = unreal.GameplayStatics.get_game_mode(world)
            match = unreal.GameplayStatics.get_game_state(world)
            data["pawn"] = actor(pawn)
            if pawn:
                data["pawn"].update(locally_controlled=optional_call(pawn, "is_locally_controlled"),
                                    player_controlled=optional_call(pawn, "is_player_controlled"),
                                    controller=optional_call(pawn, "get_controller"),
                                    roster_slot=prop(pawn, "RosterIndex"), team=prop(pawn, "TeamIndex"),
                                    position=prop(pawn, "Position"), interaction=prop(pawn, "bInteractHeld"),
                                    movement_locked=optional_call(pawn, "has_spell_movement_lock"),
                                    spell_feedback=prop(pawn, "SpellFeedback"),
                                    input_state=optional_call(pawn, "development_get_controller_input_state"),
                                    input_component=prop(pawn, "InputComponent"))
                movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
                data["pawn"]["movement"] = dict(path=path(movement),
                    tick_enabled=optional_call(movement, "is_component_tick_enabled"),
                    active=optional_call(movement, "is_active")) if movement else None
            data["controller"] = actor(controller)
            if controller:
                data["controller"].update(local_controller=optional_call(controller, "is_local_controller"),
                    local_player_controller=optional_call(controller, "is_local_player_controller"),
                    pawn=optional_call(controller, "get_pawn"), player_input=prop(controller, "PlayerInput"),
                    player=prop(controller, "Player"), state_name=optional_call(controller, "get_state_name"))
            data["game_mode"] = actor(game_mode)
            data["match"] = actor(match)
            if match:
                data["match"]["state"] = {name: prop(match, name) for name in
                    ("Status", "Announcement", "bLive", "bPractice", "bBloodbroom", "SecondsLeft", "LiveSeconds",
                     "bPenaltyShotActive", "bConductReviewPending", "PendingPenaltyCount")}
                try:
                    data["match"]["contains_local_pawn"] = pawn in match.get_editor_property("riders")
                except Exception:
                    data["match"]["contains_local_pawn"] = {"available": False, "reason": "not reflected"}
            data["queue_observability"] = "PendingDevelopmentInputs is private non-UPROPERTY C++; no queue reads or mutations attempted"
            data["status"] = "sampled"
    except Exception:
        data.update(status="error", reason=traceback.format_exc())
    spec = importlib.util.spec_from_file_location("_bb_input_probe_receipts", ROOT / "Tools/native_test_receipts.py")
    receipts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(receipts)
    receipts.write_json_atomic(REPORT, data)
    return data


if __name__ == "__main__":
    RESULT = main()

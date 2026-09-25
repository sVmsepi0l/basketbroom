"""Read-only native broom/inventory/menu gates in an existing Basketbroom PIE.

No inventory grants, unlocks, tool activation, input, graph edits or saves.
The installed Phoenix DLL exports GetUIManagerPure and GetCharacterID; capture
their reflected signatures before invoking those exact read-only getters.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import unreal

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path("C:/Program Files/HogwartsLegacyCreatorKit/PhoenixGame/Phoenix.uproject")
WORLD_RE = r"/Basketbroom/Maps/UEDPIE_\d+_Basketbroom_DungeonMap\.Basketbroom_DungeonMap"


def value(item):
    if item is None or isinstance(item, (str, int, float, bool)):
        return item
    if callable(getattr(item, "get_path_name", None)):
        return item.get_path_name()
    if callable(getattr(item, "export_text", None)):
        return item.export_text()
    if isinstance(item, (list, tuple)) or type(item).__name__ in ("Array", "Set"):
        return [value(part) for part in item]
    return str(item)


def signatures(obj, words=None):
    found = {}
    for name in dir(obj):
        if name.startswith("_") or (words and not any(word in name.lower() for word in words)):
            continue
        member = getattr(obj, name, None)
        if callable(member):
            found[name] = str(member.__doc__ or "")
    return found


def read_call(obj, name, *args):
    member = getattr(obj, name, None)
    if not callable(member):
        return {"available": False}
    result = {"signature": str(member.__doc__ or ""), "args": [value(arg) for arg in args]}
    try:
        result["value"] = value(member(*args))
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
    return result


def properties(obj, words):
    """Only read explicitly documented reflected properties, never guessed fields."""
    doc = str(type(obj).__doc__ or "")
    names = re.findall(r"- ``([a-z_0-9]+)``", doc)
    result = {}
    for name in names:
        if any(word in name.lower() for word in words):
            try:
                result[name] = value(obj.get_editor_property(name))
            except Exception as exc:
                result[name] = {"error": type(exc).__name__ + ": " + str(exc)}
    return result


def run():
    project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
    if project != PROJECT.resolve() or not unreal.SystemLibrary.get_engine_version().startswith("4.27."):
        raise RuntimeError("Expected native Creator Kit project")
    if str(unreal.GameModManagerSubsystem.get_active_mod_name_bp()) != "Basketbroom":
        raise RuntimeError("Expected active Basketbroom mod")
    worlds = list(unreal.EditorLevelLibrary.get_pie_worlds(True))
    if len(worlds) != 1 or not re.fullmatch(WORLD_RE, worlds[0].get_path_name()):
        raise RuntimeError("Expected one existing owned dungeon Play world")
    world = worlds[0]
    player = unreal.GameplayStatics.get_player_pawn(world, 0)
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    if not player or not controller or controller.get_controlled_pawn() != player:
        raise RuntimeError("Expected possessed native player")
    if player.get_class().get_path_name() != "/Game/Pawn/Player/BP_Biped_Player.BP_Biped_Player_C":
        raise RuntimeError("Expected native player class")
    words = ("inventory", "character_id", "broom", "mount", "fly", "flight", "lock", "ui_manager")
    data = {
        "status": "inspected", "utc": datetime.now(timezone.utc).isoformat(), "pid": os.getpid(),
        "read_only": True, "assets_saved": False, "inventory_modified": False,
        "inputs_injected": False, "tools_activated": False, "world": value(world),
        "player": value(player), "controller": value(controller),
        "can_use_broom": read_call(unreal.UIBlueprintFunctionLibrary, "can_use_broom", True),
        "can_use_broom_without_avatar_state": read_call(unreal.UIBlueprintFunctionLibrary, "can_use_broom", False),
        "player_character_id": read_call(player, "get_character_id"),
        "player_selected_inventory_result": read_call(player, "get_inventory_result"),
        "controller_last_valid_mount_location": read_call(controller, "get_last_valid_mount_location"),
        "player_api": signatures(player, words), "controller_api": signatures(controller, words),
        "player_properties": properties(player, words),
        "world_settings_properties": properties(world.get_world_settings(), words),
        "classes": {}, "toolsets": [],
    }
    for name in ("InventoryManagerInterface", "InventoryObjectManagerBPInterface", "InventoryResult",
                 "InventoryFilter", "UIManager", "UIBlueprintFunctionLibrary", "GameLogicVarBool",
                 "GameLogicVarManager", "LockManager", "LockManagerInterface", "LockManagerLock",
                 "ToolRecord", "InventoryItemToolRecord", "BroomItemTool"):
        cls = getattr(unreal, name, None)
        if cls is None:
            data["classes"][name] = {"available": False}
            continue
        data["classes"][name] = {"doc": str(cls.__doc__ or ""), "api": signatures(cls)}
        if name == "InventoryFilter":
            data["classes"][name]["enum_members"] = {
                key: str(getattr(cls, key)) for key in dir(cls)
                if key.isupper() and not key.startswith("_")
            }
    data["inventory_types"] = read_call(unreal.InventoryManagerInterface, "get_inventory_types_bp")
    if "value" in data["player_character_id"]:
        character_id = player.get_character_id()
        if str(character_id) not in ("", "None"):
            data["has_backpack_inventory"] = read_call(unreal.InventoryManagerInterface, "has_any_inventory", character_id)
            # BroomStorage is the shipped ItemDefinition.StorageLocation for BroomHouse.
            data["has_broom_storage_inventory"] = read_call(
                unreal.InventoryManagerInterface, "has_any_inventory", character_id, "BroomStorage")
    data["shipped_broom_definition"] = {
        "source": "PhoenixGame/Content/SQLiteDB/PhoenixGameData.sqlite (read-only inspection)",
        "inventory_item_id": "BroomHouse", "tool_record_lookup_name": "item_BroomHouse",
        "storage_location": "BroomStorage", "item_lock": "Vendor_Broom_Acquired",
        "availability_lock": "BroomAvailable", "availability_lock_default_type": "Simple_Locked",
        "note": "Definitions identify the next queries; they do not establish current runtime ownership or lock state.",
    }

    manager_getter = getattr(unreal.UIManager, "get_ui_manager_pure", None)
    data["ui_manager_getter"] = {"available": callable(manager_getter)}
    if callable(manager_getter):
        data["ui_manager_getter"]["signature"] = str(manager_getter.__doc__ or "")
        try:
            manager = manager_getter()
            data["ui_manager_getter"]["instance"] = value(manager)
            if manager is not None:
                data["ui_manager_properties"] = properties(manager, ("game_player_controller", "hidden_menu", "promo", "pause"))
                actual_controller = manager.get_editor_property("game_player_controller")
                data["ui_manager_matches_pie_controller"] = actual_controller == controller
                if actual_controller == controller:
                    data["ui_manager_state"] = {
                        name: read_call(manager, name) for name in (
                            "get_hidden_menu_tabs", "get_temp_pause_lock", "in_pause_mode",
                            "get_in_menu_transition", "get_in_game_menu_widget")
                    }
        except Exception as exc:
            data["ui_manager_getter"]["error"] = type(exc).__name__ + ": " + str(exc)

    for component in player.get_components_by_class(unreal.ToolSetComponent):
        entry = {"path": value(component), "active_tool": value(component.get_active_tool()), "brooms": []}
        for record in component.get_tool_records():
            if "/Broom/" not in record.get_path_name():
                continue
            lookup = record.get_editor_property("lookup_name")
            entry["brooms"].append({
                "path": value(record), "lookup_name": str(lookup),
                "lock_name": value(record.get_editor_property("lock_name")),
                "tool_usage_allowed": bool(component.is_tool_usage_allowed(record)),
                # LookupName is NOT the identifier accepted by this UI helper:
                # the September 25 probe triggered an Ensure at native line 1508.
                "ui_blacklisted": {"not_queried": "UI helper rejects ToolRecord lookup names; use the exact record allowance above."},
            })
        data["toolsets"].append(entry)
    report = ROOT / ".local/hlck/native-broom-gates.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    temporary = report.with_suffix(".next")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(report)
    return {"status": data["status"], "report": str(report), "read_only": True,
            "can_use_broom": data["can_use_broom"], "ui_manager_getter": data["ui_manager_getter"]}


if __name__ == "__main__":
    RESULT = run()

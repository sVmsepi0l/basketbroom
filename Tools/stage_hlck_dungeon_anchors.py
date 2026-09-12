"""Stage the first-entry PlayerStart and native exit in the owned dungeon only.

Bridge args default to dry_run=True. This never places an Overland entrance,
registers a dungeon, calls a travel event, or runs PIE. The ordinary entrance
template opens the first entrance without a PlayerStartTag URL option; its
second-entrance branch alone appends the map name plus _EXIT. Keep one ordinary
PlayerStart, and keep the native exit's first-exit defaults and graph intact.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import shutil
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/dungeon-anchor-result.json"
PLAN_REPORT = ROOT / ".local/hlck/dungeon-anchor-plan.json"
ENTRY_TAG = "BB.HLCK.Dungeon.Entry.v1"
EXIT_TAG = "BB.HLCK.Dungeon.Exit.v1"
EXIT_LABEL = "BB Dungeon Return to Overland"
EXIT_LOCATION = (-3600.0, 0.0, 100.0)
EXIT_ROTATION = (0.0, 0.0, 0.0)
EXIT_DEFAULTS = {
    "This is a second _EXIT": False,
    "ExitPrompt": True,
    "OneWay": False,
    "RequireSwitch": False,
    "PlayerStartTag": "?PlayerStartTag=",
}


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def actor_record(actor):
    rotation = actor.get_actor_rotation()
    return {"path": actor.get_path_name(), "class": actor.get_class().get_path_name(),
            "label": actor.get_actor_label(), "location": xyz(actor.get_actor_location()),
            "rotation": [float(rotation.pitch), float(rotation.yaw), float(rotation.roll)],
            "scale": xyz(actor.get_actor_scale3d()),
            "tags": [str(tag) for tag in actor.get_editor_property("tags")]}


def construction_contract(unreal, blueprint):
    """Read the actual owned graph before allowing its constructor to execute."""
    export = ROOT / ".local/hlck/dungeon-anchors/exit_blueprint.t3d"
    export.parent.mkdir(parents=True, exist_ok=True)
    task = unreal.AssetExportTask()
    task.set_editor_property("object", blueprint)
    task.set_editor_property("filename", str(export))
    task.set_editor_property("automated", True)
    task.set_editor_property("prompt", False)
    task.set_editor_property("replace_identical", True)
    task.set_editor_property("exporter", unreal.ObjectExporterT3D())
    if not unreal.Exporter.run_asset_export_task(task) or not export.is_file():
        raise RuntimeError("Could not inspect the owned exit construction graph")
    stack, calls, writes, macros = [], set(), set(), set()
    for line in export.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith("Begin Object"):
            name = re.search(r'Name="([^"]+)"', line)
            stack.append(name.group(1) if name else "?")
        if len(stack) >= 3 and stack[1] in ("UserConstructionScript", "EdGraph_0"):
            member = re.search(r'MemberName="([^"]+)"', line)
            if "FunctionReference=" in line and member:
                calls.add(member.group(1))
            if "VariableReference=" in line and "VariableSet" in stack[-1] and member:
                writes.add(member.group(1))
            if "MacroGraphReference=" in line:
                macros.add(line)
        if line == "End Object":
            stack.pop()
    wanted = {"UserConstructionScript", "Conv_StringToName", "GetCompositeDataTableFromBase",
              "Concat_StrStr", "GetCurrentLevelName", "Conv_StringToText", "K2_SetText",
              "GetDataTableRowFromName"}
    if calls != wanted or writes != {"LoadingToLevel", "LevelName"} or macros:
        raise RuntimeError("The exit construction graph differs from the inspected read-only contract: "
                           + json.dumps({"calls": sorted(calls), "writes": sorted(writes), "macros": sorted(macros)}))
    return {"calls": sorted(calls), "actor_field_writes": sorted(writes), "export": str(export)}


def run(dry_run=True):
    destination_report = PLAN_REPORT if dry_run is True else REPORT
    report = {"status": "not_run", "started_utc": datetime.now(timezone.utc).isoformat(),
              "dry_run": dry_run, "registration_invoked": False, "travel_invoked": False,
              "overland_modified": False}
    try:
        if not isinstance(dry_run, bool):
            raise RuntimeError("dry_run must be a JSON boolean")
        import unreal
        guard = module("_bb_anchor_guard", "Tools/load_hlck_dungeon.py")
        stage = module("_bb_anchor_stage", "Tools/stage_hlck_dungeon.py")
        report["active_mod"] = guard.require_editor(unreal)
        report["dirty_before"] = guard.require_clean(unreal)
        world = unreal.EditorLevelLibrary.get_editor_world()
        if stage.world_path(world) != stage.TARGET_MAP:
            raise RuntimeError("Open the saved owned dungeon before staging anchors")
        actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
        owners = [actor for actor in actors if actor.actor_has_tag(stage.BASE_MARKER)]
        if len(owners) != 1 or not owners[0].actor_has_tag(stage.STAGE_MARKER):
            raise RuntimeError("The current dungeon lacks exact staging ownership")
        inspection = module("_bb_anchor_preinspection", "Tools/inspect_hlck_dungeon.py").inspect()
        if inspection.get("status") != "passed" or inspection.get("passed") != 20:
            raise RuntimeError("All 20 dungeon prerequisites must pass before anchor authoring")
        report["dungeon_checks_passed"] = 20
        map_file = stage.checked_file(stage.TARGET_MAP, ".umap")
        source_file = stage.checked_file(stage.SOURCE_MAP, ".umap")
        source_before, target_before = stage.digest(source_file), stage.digest(map_file)
        report["source_sha256"] = source_before
        report["map_sha256_before"] = target_before
        starts = [actor for actor in actors if isinstance(actor, unreal.PlayerStart)]
        if len(starts) != 1 or not starts[0].actor_has_tag("BB.Spawn"):
            raise RuntimeError("Expected the arena's single owned PlayerStart; no ambiguous spawn will be added")
        start = starts[0]
        if str(start.get_editor_property("player_start_tag")) not in ("", "None"):
            raise RuntimeError("The first-entry PlayerStart has a custom tag; preserve it for review")
        if any(abs(a - b) > 0.01 for a, b in zip(xyz(start.get_actor_location()), (-3000, 0, 300))):
            raise RuntimeError("The existing entry spawn was moved; preserve it for review")
        report["entry_before"] = actor_record(start)
        exit_path = stage.DESTINATIONS[stage.SOURCE_EXIT]
        exit_blueprint = unreal.load_asset(exit_path)
        if exit_blueprint is None:
            raise RuntimeError("The owned exit Blueprint is unavailable")
        report["construction_contract"] = construction_contract(unreal, exit_blueprint)
        exit_class = unreal.EditorAssetLibrary.load_blueprint_class(exit_path)
        default = unreal.get_default_object(exit_class)
        for key, value in EXIT_DEFAULTS.items():
            if default.get_editor_property(key) != value:
                raise RuntimeError("The owned exit no longer retains native default: " + key)
        report["native_exit_defaults"] = dict(EXIT_DEFAULTS)
        report["native_exit_dungeon_table"] = default.get_editor_property("DungeonTable").get_path_name()
        # Do not replace DungeonTable with the mod table: the fallback table uses
        # STR_DungeonListData, while our extension uses STR_TransientDungeonListData.
        exits = [actor for actor in actors if actor.get_class() == exit_class]
        if len(exits) > 1 or (exits and not exits[0].actor_has_tag(EXIT_TAG)):
            raise RuntimeError("An unowned or duplicate exit already exists; preserve it for review")
        if any(actor.actor_has_tag(EXIT_TAG) and actor not in exits for actor in actors):
            raise RuntimeError("The exit ownership tag is attached to an unexpected class")
        if exits and (xyz(exits[0].get_actor_location()) != list(EXIT_LOCATION)
                      or any(exits[0].get_editor_property(key) != value for key, value in EXIT_DEFAULTS.items())):
            raise RuntimeError("The staged exit was changed; preserve it for review")
        report["entry_plan"] = "Reuse the single ordinary PlayerStart; add ownership tag only"
        report["exit_plan"] = {"class": exit_path, "location": list(EXIT_LOCATION), "first_exit": True}
        report["registration_prerequisites"] = {
            "active_mod": "Basketbroom", "dungeon_map": stage.TARGET_MAP, "row_name": stage.ROW_NAME,
            "entrance_blueprint": stage.DESTINATIONS[stage.SOURCE_ENTRANCE],
            "dungeon_table": stage.DESTINATIONS[stage.SOURCE_DUNGEONS],
            "outside_entrance_placement": "NOT_DONE: a chosen loaded Overland sublevel and return transform are required",
            "register_dungeon": "NOT_RUN: separate CallInEditor action on the outside entrance",
            "entry_return_test": "NOT_RUN", "navigation_minimap": "NOT_BUILT"}
        if dry_run:
            report["dirty_after"] = guard.require_clean(unreal)
            report["status"] = "ready"
        else:
            before = {actor.get_path_name(): actor_record(actor) for actor in actors if actor != start}
            backup = ROOT / ".local/hlck/dungeon-anchors/backups" / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + ".umap")
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(map_file), str(backup))
            if stage.digest(backup) != target_before:
                raise RuntimeError("The exact pre-authoring map backup did not verify")
            report["backup"] = {"path": str(backup), "sha256": target_before, "original": str(map_file)}
            report["status"] = "backed_up"
            destination_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            tags = list(start.get_editor_property("tags"))
            if not start.actor_has_tag(ENTRY_TAG):
                start.set_editor_property("tags", tags + [unreal.Name(ENTRY_TAG)])
            if exits:
                exit_actor = exits[0]
            else:
                exit_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                    exit_class, unreal.Vector(*EXIT_LOCATION), unreal.Rotator(*EXIT_ROTATION))
                if exit_actor is None:
                    raise RuntimeError("The native exit actor could not be spawned")
                exit_actor.set_actor_label(EXIT_LABEL)
                exit_actor.set_folder_path("Basketbroom/Dungeon anchors")
                exit_actor.set_editor_property("tags", list(exit_actor.get_editor_property("tags")) + [unreal.Name(EXIT_TAG)])
            after = {actor.get_path_name(): actor_record(actor) for actor in unreal.EditorLevelLibrary.get_all_level_actors()
                     if actor != start and actor != exit_actor}
            expected = {key: value for key, value in before.items() if key != exit_actor.get_path_name()}
            if after != expected:
                raise RuntimeError("An unrelated actor changed; leave the map unsaved for review")
            for key, value in EXIT_DEFAULTS.items():
                if exit_actor.get_editor_property(key) != value:
                    raise RuntimeError("The exit actor did not retain native default: " + key)
            dirty_maps = [item.get_path_name() for item in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
            dirty_content = [item.get_path_name() for item in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
            if any(path != stage.TARGET_MAP for path in dirty_maps) or dirty_content:
                raise RuntimeError("Unexpected dirty packages; only the owned dungeon may be saved")
            if stage.world_path(unreal.EditorLevelLibrary.get_editor_world()) != stage.TARGET_MAP:
                raise RuntimeError("The world changed during authoring")
            if not unreal.EditorLevelLibrary.save_current_level():
                raise RuntimeError("Could not save the owned dungeon")
            if stage.digest(source_file) != source_before:
                raise RuntimeError("The original arena disk hash changed unexpectedly")
            report["entry"] = actor_record(start)
            report["exit"] = actor_record(exit_actor)
            report["exit_loading_text"] = str(exit_actor.get_editor_property("LoadingToLevel"))
            report["map_sha256_after"] = stage.digest(map_file)
            report["dirty_after"] = guard.require_clean(unreal)
            report["status"] = "staged"
    except Exception:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
    destination_report.parent.mkdir(parents=True, exist_ok=True)
    destination_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {"status": report["status"], "report": str(destination_report)}


if __name__ == "__main__":
    RESULT = run(dry_run=globals().get("BRIDGE_ARGS", {}).get("dry_run", True))

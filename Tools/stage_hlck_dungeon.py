"""Stage native Creator Kit dungeon assets without registration or travel.

Open the unchanged /Basketbroom/Maps/BB_Arena_Port in Phoenix UE4.27 first.
Alternatively pass open_source_map=True through the editor bridge; the helper
then opens only that exact map after refusing every unsaved dirty map.
preserve_dirty_source=True separately preserves a dirty source-world snapshot
to a unique /Basketbroom/Recovery package before resuming an existing copy.
The helper saves a separately named Basketbroom_DungeonMap copy, duplicates
the supported tables/mutator/entrance/exit Blueprints, and configures only
owned defaults. No Overland actor is placed, no database SQL is authored,
and RegisterDungeon is never invoked. Existing unrelated assets are refused.

The subdivision row follows the inspected native wizard: map-name key and
DungeonName, with every other native field left at its constructor default.
A completed staging report does NOT certify working travel.
Run --plan outside Unreal to inspect destinations without writing anything.
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "Mod/Basketbroom/Content"
REPORT = ROOT / ".local/hlck/dungeon-stage-result.json"
PROBE = ROOT / ".local/hlck/dungeon-probe.json"
MAP_RECEIPT = ROOT / ".local/hlck/dungeon-map-stage.json"
WIZARD_DLL = Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Plugins\PhoenixUGC\Binaries\Win64\UE4Editor-PhoenixUGCEditor.dll")
WIZARD_SHA256 = "ccb2eb0cd3825c3abbad0debf057b077475bf01cea02adb6c85a78ce98835ea1"
SOURCE_MAP = "/Basketbroom/Maps/BB_Arena_Port"
TARGET_MAP = "/Basketbroom/Maps/Basketbroom_DungeonMap"
ROW_NAME = "Basketbroom_DungeonMap"
BASE_MARKER = "BB.HLCK.ArenaPort.Owner.v1"
STAGE_MARKER = "BB.HLCK.DungeonStage.Owner.v1"
OWNER = "Basketbroom.HLCK.DungeonStage.v1"
META_OWNER = "BB.DungeonStage.Owner"
META_SOURCE = "BB.DungeonStage.Source"
SOURCE_DUNGEONS = "/PhoenixUGC/DungeonMod/Data/DT_PLUGIN_NAME_DungeonsTable"
SOURCE_SUBDIVISIONS = "/PhoenixUGC/DungeonMod/Data/UI_DT_PLUGIN_NAME_MapSubdivisionTable"
SOURCE_MUTATOR = "/PhoenixUGC/DungeonMod/Blueprints/BP_PLUGIN_NAME_DataMutator"
SOURCE_ENTRANCE = "/ModSupport/Blueprints/BP_DungeonEntrance"
SOURCE_EXIT = "/Game/Gameplay/Blueprints/Triggers/BP_WorldTeleport"
BASE_DUNGEONS = "/Game/Data/Dungeons/DT_TransientDungeonsTable"
BASE_SUBDIVISIONS = "/Game/UI/Map/UI_DT_MapDungeonSubdivisionTable_Comp"
DESTINATIONS = {
    SOURCE_DUNGEONS: "/Basketbroom/Data/DT_Basketbroom_DungeonsTable",
    SOURCE_SUBDIVISIONS: "/Basketbroom/Data/UI_DT_Basketbroom_MapSubdivisionTable",
    SOURCE_MUTATOR: "/Basketbroom/Blueprints/BP_Basketbroom_DataMutator",
    SOURCE_ENTRANCE: "/Basketbroom/Blueprints/BP_Basketbroom_DungeonEntrance",
    SOURCE_EXIT: "/Basketbroom/Blueprints/BP_Basketbroom_DungeonExit",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_file(asset_path, extension=".uasset"):
    if not asset_path.startswith("/Basketbroom/"):
        raise RuntimeError("Refusing a destination outside the repository mod: " + asset_path)
    path = (CONTENT / (asset_path[len("/Basketbroom/"):] + extension)).resolve()
    if CONTENT.resolve() not in path.parents:
        raise RuntimeError("Destination escapes mod Content")
    return path


def write_report(report):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(REPORT)


def world_path(world):
    return world.get_path_name().split(".")[0] if world else ""


def records(unreal, path):
    return [entry for entry in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(
        path.rpartition("/")[0], recursive=False) if str(entry.package_name) == path]


def schema_fields(probe):
    evidence = probe["assets"]["dungeon_template_table"]["row_struct_export"]
    source = ROOT / ".local/hlck/dungeon-probe/dungeon_template_table_row_struct.t3d"
    if not evidence.get("succeeded") or digest(source) != evidence["sha256"]:
        raise RuntimeError("The live-probed dungeon schema export is missing or changed; rerun the read-only probe")
    result = []
    for line in source.read_text(encoding="utf-8-sig").splitlines():
        match = re.search(r'VariablesDescriptions\(\d+\)=\(VarName="([A-Za-z0-9_]+)".*?FriendlyName="([A-Za-z0-9_]+)"', line)
        if match:
            result.append(match.groups())
    if len(result) != 24 or sum(friendly == "DungeonLevel" for raw, friendly in result) != 1:
        raise RuntimeError("Dungeon row schema differs from the 24-field live proof; review before staging")
    return result


def source_row(unreal, source, fields):
    library = unreal.DataTableFunctionLibrary
    if [str(name) for name in library.get_data_table_row_names(source)] != ["NewRow"]:
        raise RuntimeError("Dungeon template no longer has exactly its original NewRow")
    values = []
    for raw, friendly in fields:
        column = list(library.get_data_table_column_as_string(source, raw))
        if len(column) != 1:
            raise RuntimeError("Cannot read original template column: " + raw)
        values.append(str(column[0]))
    return values


def save_asset(unreal, asset, source):
    path = asset.get_path_name().split(".")[0]
    checked_file(path)
    if path != DESTINATIONS[source]:
        raise RuntimeError("Unexpected owned asset path: " + path)
    library = unreal.EditorAssetLibrary
    library.set_metadata_tag(asset, META_OWNER, OWNER)
    library.set_metadata_tag(asset, META_SOURCE, source)
    if not library.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError("Failed to save owned asset: " + path)


def duplicate(unreal, source):
    destination = DESTINATIONS[source]
    physical = checked_file(destination)
    library = unreal.EditorAssetLibrary
    existing = records(unreal, destination)
    if existing or physical.exists():
        asset = unreal.load_asset(destination)
        if asset is None or library.get_metadata_tag(asset, META_OWNER) != OWNER \
                or library.get_metadata_tag(asset, META_SOURCE) != source:
            raise RuntimeError("Preserving existing asset without exact staging ownership: " + destination)
        return asset
    asset = library.duplicate_asset(source, destination)
    if asset is None:
        raise RuntimeError("Native template duplication failed: " + source)
    save_asset(unreal, asset, source)
    return asset


def extension_pairs(mutator):
    pairs = set()
    entries = list(mutator.get_editor_property("data_table_extensions"))
    for entry in entries:
        additional = entry.get_editor_property("additional_data")
        base = entry.get_editor_property("table_to_add_to")
        if additional is None or base is None:
            raise RuntimeError("Owned mutator has an incomplete table extension")
        pairs.add((additional.get_path_name().split(".")[0], base.get_path_name().split(".")[0]))
    if len(pairs) != len(entries):
        raise RuntimeError("Owned mutator contains duplicate table extensions")
    return pairs


def subdivision_values(unreal):
    # Read-only inspection of this exact installed DLL's PluginAssetFixer.cpp
    # implementation (RVA 0x10ef0) showed InitializeStruct, assignment of only
    # DungeonName (string at RVA 0x2ce28), then AddRow using the world FName
    # (0x114c3..0x11552). OwnerName is not assigned. Guard that evidence when
    # deriving the same native defaults through supported reflected APIs.
    if not WIZARD_DLL.is_file() or digest(WIZARD_DLL) != WIZARD_SHA256:
        raise RuntimeError("The inspected dungeon wizard implementation changed; reprobe before adding subdivision data")
    row = unreal.MapDungeonSubdivisionTable()
    mission = row.get_editor_property("mission_lock").get_editor_property("mission_name")
    # The live kit returns an empty FName whose text is "None", not an empty
    # Python string. Compare the native sentinel rather than its display text.
    if mission != unreal.Name(""):
        raise RuntimeError("Native subdivision mission default changed; do not invent a mission reference")
    return {"DungeonName": ROW_NAME,
            "OwnerName": str(row.get_editor_property("owner_name")),
            "MissionLock": '(MissionName="")',
            "MissionStepLock": str(row.get_editor_property("mission_step_lock")),
            "OpenAfterMission": "True" if row.get_editor_property("open_after_mission") else "False",
            "PerceptionRadius": "{:.6f}".format(float(row.get_editor_property("perception_radius"))),
            "ZoomFactor": "{:.6f}".format(float(row.get_editor_property("zoom_factor")))}


def stage_subdivision(unreal, table, report):
    values = subdivision_values(unreal)
    library = unreal.DataTableFunctionLibrary
    names = [str(name) for name in library.get_data_table_row_names(table)]
    if names not in ([], [ROW_NAME]):
        raise RuntimeError("Preserving owned subdivision table with unrelated authored rows")
    if not names:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["Name"] + list(values))
        writer.writerow([ROW_NAME] + list(values.values()))
        if not library.fill_data_table_from_csv_string(table, stream.getvalue()):
            raise RuntimeError("Native subdivision import failed")
    if [str(name) for name in library.get_data_table_row_names(table)] != [ROW_NAME]:
        raise RuntimeError("Subdivision key does not match the exact dungeon map name")
    observed = {name: [str(value) for value in library.get_data_table_column_as_string(table, name)] for name in values}
    if any(observed[name] != [value] for name, value in values.items()):
        raise RuntimeError("Subdivision readback differs from native wizard defaults; preserving authored data for review")
    if not names:
        save_asset(unreal, table, SOURCE_SUBDIVISIONS)
    report["subdivision"] = {"row": ROW_NAME, "values": values,
                             "action": "created" if not names else "reused_verified",
                             "evidence": "Native PluginAssetFixer.cpp initializes defaults and assigns only DungeonName and row key from the world name",
                             "wizard_sha256": WIZARD_SHA256, "travel_verified": False}


def require_clean_maps(unreal):
    method = getattr(unreal.EditorLoadingAndSavingUtils, "get_dirty_map_packages", None)
    if not callable(method):
        raise RuntimeError("Cannot verify dirty maps in this editor; no map will be loaded or staged")
    dirty = list(method())
    if dirty:
        raise RuntimeError("Unsaved map changes exist; save/review them before staging: "
                           + ", ".join(package.get_name() for package in dirty))


def preserve_source_if_requested(unreal, report, requested):
    if not requested:
        return
    method = getattr(unreal.EditorLoadingAndSavingUtils, "get_dirty_map_packages", None)
    if not callable(method):
        raise RuntimeError("Cannot inspect dirty maps before recovery")
    dirty = [item.get_path_name() for item in method()]
    if not dirty:
        report["source_recovery"] = {"requested": True, "action": "already_clean"}
        return
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world_path(world) != SOURCE_MAP or dirty != [SOURCE_MAP]:
        raise RuntimeError("Recovery only preserves the exact source arena; other dirty maps require review")
    target_file = checked_file(TARGET_MAP, ".umap")
    target_entries = records(unreal, TARGET_MAP)
    if not target_file.is_file() or len(target_entries) != 1 or str(target_entries[0].asset_class) != "World":
        raise RuntimeError("Recovery requires the already-saved dungeon target")
    owners = [actor for actor in unreal.EditorLevelLibrary.get_all_level_actors() if actor.actor_has_tag(BASE_MARKER)]
    if len(owners) != 1 or not owners[0].actor_has_tag(STAGE_MARKER):
        raise RuntimeError("Recovery requires the failed staging attempt's exact source ownership marker")
    before = digest(checked_file(SOURCE_MAP, ".umap"))
    target_before = digest(target_file)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:8]
    backup = "/Basketbroom/Recovery/BB_SourceRecovery_" + suffix
    physical = checked_file(backup, ".umap")
    if physical.exists() or records(unreal, backup):
        raise RuntimeError("Unique recovery destination unexpectedly exists")
    report["source_recovery"] = {"requested": True, "action": "saving_copy", "path": backup,
                                 "file": str(physical), "local_backup_only": True,
                                 "source_sha256_before": before, "target_sha256_before": target_before}
    write_report(report)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, backup) or not physical.is_file():
        raise RuntimeError("Source recovery copy was not saved; preserving the current editor world")
    if digest(checked_file(SOURCE_MAP, ".umap")) != before or digest(target_file) != target_before:
        raise RuntimeError("Unexpected source or dungeon file change during recovery copy")
    report["source_recovery"].update(action="copy_verified", sha256=digest(physical))
    write_report(report)
    # Explicit opt-in: every dirty source-world change now exists in a separate
    # recovery package. No dirty flags are cleared and no source save occurs.
    if not unreal.EditorLevelLibrary.load_level(TARGET_MAP) or world_path(unreal.EditorLevelLibrary.get_editor_world()) != TARGET_MAP:
        raise RuntimeError("Recovery was preserved but the dungeon target could not be opened")
    report["source_recovery"]["action"] = "copy_verified_target_opened"


def open_source_if_requested(unreal, report, requested):
    if not requested:
        return
    require_clean_maps(unreal)
    current = world_path(unreal.EditorLevelLibrary.get_editor_world())
    # An already opened owned destination is handled by the ordinary ownership
    # checks; an opt-in source load must not replace it during a resume.
    if current in (SOURCE_MAP, TARGET_MAP):
        report["source_map_open"] = {"requested": True, "action": "already_in_staging_map", "path": current}
        return
    entries = records(unreal, SOURCE_MAP)
    if len(entries) != 1 or str(entries[0].asset_class) != "World" or not checked_file(SOURCE_MAP, ".umap").is_file():
        raise RuntimeError("The exact source arena is not a registered native map in repository Mod Content")
    if not unreal.EditorLevelLibrary.load_level(SOURCE_MAP):
        raise RuntimeError("Could not open the exact clean source arena")
    if world_path(unreal.EditorLevelLibrary.get_editor_world()) != SOURCE_MAP:
        raise RuntimeError("The editor did not open the requested source arena")
    report["source_map_open"] = {"requested": True, "action": "loaded_source", "path": SOURCE_MAP}


def stage_map(unreal, report):
    world = unreal.EditorLevelLibrary.get_editor_world()
    current = world_path(world)
    source_file = checked_file(SOURCE_MAP, ".umap")
    destination_file = checked_file(TARGET_MAP, ".umap")
    if current not in (SOURCE_MAP, TARGET_MAP):
        raise RuntimeError("Open BB_Arena_Port or the already-owned Basketbroom_DungeonMap before staging; this helper will not load maps")
    require_clean_maps(unreal)
    actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    owners = [actor for actor in actors if actor.actor_has_tag(BASE_MARKER)]
    if len(owners) != 1:
        raise RuntimeError("Arena ownership marker is missing or ambiguous")
    if current == TARGET_MAP:
        if not destination_file.is_file() or not owners[0].actor_has_tag(STAGE_MARKER):
            raise RuntimeError("Existing dungeon map does not have staging ownership")
        report["map"] = {"path": TARGET_MAP, "action": "reused", "file": str(destination_file)}
        return
    before = digest(source_file)
    if records(unreal, TARGET_MAP) or destination_file.exists():
        receipt = json.loads(MAP_RECEIPT.read_text(encoding="utf-8")) if MAP_RECEIPT.is_file() else {}
        if receipt.get("owner") != OWNER or receipt.get("path") != TARGET_MAP \
                or receipt.get("source_sha256") != before or not destination_file.is_file() \
                or receipt.get("sha256") != digest(destination_file):
            raise RuntimeError("Dungeon destination already exists without an exact copy receipt; open its owned map or use explicit source recovery")
        action = "resumed_verified_copy"
    else:
        # UE4.27 saves a separate package and restores the original world. Do
        # not add the staging tag to the source before this copy operation.
        report["map"] = {"path": TARGET_MAP, "action": "saving_separate_copy", "source_sha256_before": before}
        write_report(report)
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, TARGET_MAP) or not destination_file.is_file():
            raise RuntimeError("Saving the separate dungeon copy failed; no source map save will be attempted")
        receipt = {"owner": OWNER, "path": TARGET_MAP, "source_sha256": before,
                   "sha256": digest(destination_file)}
        MAP_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        MAP_RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        action = "saved_separate_copy"
    if digest(source_file) != before:
        raise RuntimeError("Unexpected source map file change during save-as")
    require_clean_maps(unreal)
    if not unreal.EditorLevelLibrary.load_level(TARGET_MAP):
        raise RuntimeError("Saved copy exists but could not be opened; its exact receipt permits a safe retry")
    world = unreal.EditorLevelLibrary.get_editor_world()
    if world_path(world) != TARGET_MAP:
        raise RuntimeError("The saved dungeon copy is not the current world")
    owners = [actor for actor in unreal.EditorLevelLibrary.get_all_level_actors() if actor.actor_has_tag(BASE_MARKER)]
    if len(owners) != 1:
        raise RuntimeError("Saved arena copy does not retain its unique original ownership marker")
    tags = list(owners[0].get_editor_property("tags"))
    if not owners[0].actor_has_tag(STAGE_MARKER):
        tags.append(unreal.Name(STAGE_MARKER))
        owners[0].set_editor_property("tags", tags)
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, TARGET_MAP):
            raise RuntimeError("Failed to save ownership on the separate dungeon copy")
    if digest(source_file) != before:
        raise RuntimeError("Source changed while saving the separate dungeon marker")
    receipt["sha256"] = digest(destination_file)
    MAP_RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    report["map"] = {"path": TARGET_MAP, "action": action, "file": str(destination_file),
                     "source_sha256_unchanged": before, "actor_count": len(actors), "sha256": receipt["sha256"]}


def stage(open_source_map=False, preserve_dirty_source=False):
    report = {"status": "not_run", "started_utc": datetime.now(timezone.utc).isoformat(),
              "registration_invoked": False, "travel_invoked": False, "overland_modified": False,
              "active_mod_changed": False, "assets": {}, "registration_ready": False}
    try:
        import unreal
        # Reuse the tested exact-engine/mounted-repository guard, not its build.
        spec = importlib.util.spec_from_file_location("_bb_hlck_stage_import_guard", ROOT / "Mod/Tools/import_sources.py")
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        guard._editor()
        project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        if project != Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject").resolve():
            raise RuntimeError("Expected the exact installed Phoenix project")
        if unreal.EditorLevelLibrary.get_pie_worlds(True):
            raise RuntimeError("Stop PIE before staging native dungeon assets")
        active = str(unreal.GameModManagerSubsystem.get_active_mod_name_bp())
        if active not in ("", "Basketbroom"):
            raise RuntimeError("Another mod is active; preserving its authoring context: " + active)
        report["active_mod"] = active
        if not isinstance(open_source_map, bool) or not isinstance(preserve_dirty_source, bool):
            raise RuntimeError("open_source_map and preserve_dirty_source must be JSON booleans")
        preserve_source_if_requested(unreal, report, preserve_dirty_source)
        open_source_if_requested(unreal, report, open_source_map)
        subdivision_type = getattr(unreal, "MapDungeonSubdivisionTable", None)
        report["subdivision_schema_api"] = {"available": subdivision_type is not None,
                                             "doc": str(getattr(subdivision_type, "__doc__", "") or "")}
        probe = json.loads(PROBE.read_text(encoding="utf-8-sig"))
        if probe.get("status") != "complete" or not str(probe.get("engine", "")).startswith("4.27."):
            raise RuntimeError("A completed live Creator Kit dungeon probe is required")
        fields = schema_fields(probe)
        originals = {path: unreal.load_asset(path) for path in list(DESTINATIONS) + [BASE_DUNGEONS, BASE_SUBDIVISIONS]}
        if any(asset is None for asset in originals.values()):
            raise RuntimeError("A required native template or base-table reference is unavailable")
        for source, base_path in ((SOURCE_DUNGEONS, BASE_DUNGEONS), (SOURCE_SUBDIVISIONS, BASE_SUBDIVISIONS)):
            if originals[source].get_editor_property("row_struct") != originals[base_path].get_editor_property("row_struct"):
                raise RuntimeError("Template and target table row structures differ")
        defaults = source_row(unreal, originals[SOURCE_DUNGEONS], fields)
        report["original_template_values"] = dict(zip((raw for raw, friendly in fields), defaults))
        report["status"] = "running"
        write_report(report)
        stage_map(unreal, report)
        owned = {source: duplicate(unreal, source) for source in DESTINATIONS}
        for source, asset in owned.items():
            if asset.get_class() != originals[source].get_class():
                raise RuntimeError("Duplicated asset class differs: " + source)
        table = owned[SOURCE_DUNGEONS]
        values = list(defaults)
        index = next(i for i, pair in enumerate(fields) if pair[1] == "DungeonLevel")
        values[index] = TARGET_MAP + "." + ROW_NAME
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["Name"] + [raw for raw, friendly in fields])
        writer.writerow([ROW_NAME] + values)
        if not unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(table, stream.getvalue()):
            raise RuntimeError("Owned dungeon table import failed; no fabricated row will be accepted")
        if [str(name) for name in unreal.DataTableFunctionLibrary.get_data_table_row_names(table)] != [ROW_NAME]:
            raise RuntimeError("Dungeon table row name does not match the destination map")
        observed = [list(unreal.DataTableFunctionLibrary.get_data_table_column_as_string(table, raw)) for raw, friendly in fields]
        if any(len(column) != 1 for column in observed) or TARGET_MAP not in str(observed[index][0]):
            raise RuntimeError("Dungeon level readback does not reference the new native map")
        for i, column in enumerate(observed):
            if i != index and str(column[0]) != defaults[i]:
                raise RuntimeError("Template default changed during CSV round-trip: " + fields[i][0])
        save_asset(unreal, table, SOURCE_DUNGEONS)
        stage_subdivision(unreal, owned[SOURCE_SUBDIVISIONS], report)
        mutator_class = unreal.EditorAssetLibrary.load_blueprint_class(DESTINATIONS[SOURCE_MUTATOR])
        mutator = unreal.get_default_object(mutator_class)
        mutator.modify(True)
        for additional, base_path in ((owned[SOURCE_DUNGEONS], BASE_DUNGEONS), (owned[SOURCE_SUBDIVISIONS], BASE_SUBDIVISIONS)):
            mutator.add_data_table_extension(additional, originals[base_path])
        expected_pairs = {(DESTINATIONS[SOURCE_DUNGEONS], BASE_DUNGEONS), (DESTINATIONS[SOURCE_SUBDIVISIONS], BASE_SUBDIVISIONS)}
        pairs = extension_pairs(mutator)
        if pairs != expected_pairs:
            raise RuntimeError("Owned mutator extensions differ from the two supported target tables")
        unreal.PhxEditorBlueprintLibrary.compile_blueprint(owned[SOURCE_MUTATOR])
        mutator = unreal.get_default_object(unreal.EditorAssetLibrary.load_blueprint_class(DESTINATIONS[SOURCE_MUTATOR]))
        if extension_pairs(mutator) != expected_pairs:
            raise RuntimeError("Compiled mutator defaults did not retain both native table extensions")
        save_asset(unreal, owned[SOURCE_MUTATOR], SOURCE_MUTATOR)
        entrance_class = unreal.EditorAssetLibrary.load_blueprint_class(DESTINATIONS[SOURCE_ENTRANCE])
        entrance = unreal.get_default_object(entrance_class)
        handle = unreal.DungeonName()
        handle.set_editor_property("data_table", table)
        handle.set_editor_property("dungeon_name", unreal.Name(ROW_NAME))
        entrance.modify(True)
        entrance.set_editor_property("dungeon_name", handle)
        unreal.PhxEditorBlueprintLibrary.compile_blueprint(owned[SOURCE_ENTRANCE])
        entrance = unreal.get_default_object(unreal.EditorAssetLibrary.load_blueprint_class(DESTINATIONS[SOURCE_ENTRANCE]))
        handle = entrance.get_editor_property("dungeon_name")
        if handle.get_editor_property("data_table") != table or str(handle.get_editor_property("dungeon_name")) != ROW_NAME:
            raise RuntimeError("Compiled entrance defaults did not retain the owned dungeon row handle")
        save_asset(unreal, owned[SOURCE_ENTRANCE], SOURCE_ENTRANCE)
        report["assets"] = {source: {"path": destination, "sha256": digest(checked_file(destination))}
                            for source, destination in DESTINATIONS.items()}
        report["row"] = ROW_NAME
        report["mutator_extensions"] = sorted(pairs)
        report["status"] = "staged"
        report["remaining"] = ["Select existing Basketbroom using Creator Kit Set Active Mod before registration",
                               "Generate and verify Creator Kit navigation/minimap data for the new arena",
                               "Choose and verify an Overland entrance location and mod-owned registration output",
                               "Place entrance/exit actors, invoke registration, then validate entry/return in PIE",
                               "Run validation and cloud-cooked in-game travel checks; match gameplay remains separate"]
    except Exception:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_report(report)
    return {"status": report["status"], "report": str(REPORT), "registration_ready": False}


if __name__ == "__main__":
    try:
        import unreal
    except ImportError:
        unreal = None
    if unreal is None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--plan", action="store_true")
        args = parser.parse_args()
        if not args.plan:
            parser.error("Use --plan outside the Creator Kit; staging requires its native editor APIs")
        RESULT = {"status": "not_run", "source_map": SOURCE_MAP, "destination_map": TARGET_MAP,
                  "destinations": DESTINATIONS, "registration_ready": False}
        print(json.dumps(RESULT, indent=2))
    else:
        RESULT = stage(open_source_map=globals().get("BRIDGE_ARGS", {}).get("open_source_map", False),
                       preserve_dirty_source=globals().get("BRIDGE_ARGS", {}).get("preserve_dirty_source", False))

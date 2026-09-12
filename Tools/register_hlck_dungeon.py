"""Register one guarded native entrance; persist only the active mod SQL delta.

The public BeaconManager endpoint used by the stock RegisterDungeon event writes
the native editor database and ModEdits.sql. The native Overland loader recreates
placement actors from Transient=1 rows. No editor actor is created or map saved.
Default dry_run=True verifies all prerequisites without calling registration.
The map beacon is deliberately co-located with the return spawn. No travel/cook.
The successful result receipt is retained separately from later attempt reports.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import traceback

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "Mod/Basketbroom/Content"
KIT_CONTENT = Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Content")
OVERLAND = "/Game/Levels/Overland/Overland"
POSITION = (329400.0, -466800.0, -85380.65625)
YAW = 180.0
STOCK_CLASS = "/ModSupport/Blueprints/BP_DungeonEntrance.BP_DungeonEntrance_C"
REPORT = ROOT / ".local/hlck/dungeon-registration-result.json"
LAST_RUN = ROOT / ".local/hlck/dungeon-registration-last-run.json"
PLAN = ROOT / ".local/hlck/dungeon-registration-dry-run.json"


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def query(unreal, sql):
    if not sql.startswith("SELECT ") or ";" in sql:
        raise RuntimeError("The registration verifier only permits fixed SELECT queries")
    result = unreal.DbGateway.db_editor_query(sql)
    if result is None or not result.success:
        raise RuntimeError("Native editor query failed: " + str(result.error_message if result else "no result"))
    return [{str(pair.key): str(pair.value) for pair in row.fields} for row in result.result_rows]


def rows(unreal):
    return query(unreal, "SELECT * FROM DungeonEntrances WHERE DungeonName='Basketbroom_DungeonMap'")


def metadata(root, suffix):
    return {str(path.relative_to(root)): [path.stat().st_size, path.stat().st_mtime_ns]
            for path in root.rglob("*" + suffix) if path.is_file()}


def hashes(root, digest):
    return {str(path.relative_to(root)): digest(path) for path in root.rglob("*") if path.is_file()}


def write(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def verify_row(row, beacon=None):
    if row.get("DungeonName") != "Basketbroom_DungeonMap" or row.get("EntranceIndex") != "0" or row.get("Transient") != "1":
        raise RuntimeError("The native database row has the wrong identity/type")
    for name, expected in zip(("XPos", "YPos", "ZPos", "ZRot"), POSITION + (YAW,)):
        if abs(float(row[name]) - expected) > 0.1:
            raise RuntimeError("The native database transform differs at " + name)
    if beacon:
        for name, expected in zip(("BeaconXPos", "BeaconYPos", "BeaconZPos"), beacon):
            if abs(float(row[name]) - expected) > 0.1:
                raise RuntimeError("The native beacon readback differs at " + name)


def verified_saved_registration(unreal, stage, live_rows=None):
    """Check durable authoring proof without replacing it with a run status."""
    if not REPORT.is_file():
        raise RuntimeError("The existing entrance has no successful registration receipt")
    receipt = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    sql_file = CONTENT / "ModEdits.sql"
    if receipt.get("status") != "registered" or not sql_file.is_file() \
            or stage.digest(sql_file) != receipt.get("sql_sha256"):
        raise RuntimeError("The saved registration receipt and SQL file differ")
    observed = rows(unreal) if live_rows is None else live_rows
    if len(observed) != 1:
        raise RuntimeError("The saved registration requires exactly one matching live row")
    verify_row(observed[0], POSITION)
    return {"row": observed[0], "sql_sha256": receipt["sql_sha256"]}


def run(dry_run=True):
    report = {"status": "not_run", "dry_run": dry_run,
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "registration_invoked": False, "travel_invoked": False, "map_saved": False}
    # Failed preflights and idempotent reruns are observations, not replacements
    # for the successful native-write receipt used by later saved-state checks.
    output = PLAN if dry_run else LAST_RUN
    before_actors = None
    try:
        if not isinstance(dry_run, bool):
            raise RuntimeError("dry_run must be a boolean")
        import unreal
        guard = module("_bb_register_guard", "Tools/load_hlck_dungeon.py")
        stage = module("_bb_register_stage", "Tools/stage_hlck_dungeon.py")
        anchors = module("_bb_register_actors", "Tools/stage_hlck_dungeon_anchors.py")
        report["active_mod"] = guard.require_editor(unreal)
        report["dirty_before"] = guard.require_clean(unreal)
        active = Path(unreal.Paths.convert_relative_path_to_full(str(
            unreal.GameModManagerSubsystem.get_active_mod_content_path_bp()))).resolve()
        if active != CONTENT.resolve():
            raise RuntimeError("The active mod's SQL destination is not this repository")
        if stage.world_path(unreal.EditorLevelLibrary.get_editor_world()) != OVERLAND:
            raise RuntimeError("Open the clean Overland master before native registration")
        schedules = query(unreal, "SELECT LevelName,WorldKeys FROM SchedulesForLevels WHERE LevelName='Overland'")
        if len(schedules) != 1 or "Overland" not in schedules[0]["WorldKeys"].replace(" ", "").split(","):
            raise RuntimeError("The current world lacks the native Overland schedule key")
        report["schedules"] = schedules
        inspection = json.loads((ROOT / ".local/hlck/dungeon-anchor-inspection.json").read_text(encoding="utf-8-sig"))
        if inspection.get("status") != "passed" or inspection.get("passed") != 27:
            raise RuntimeError("The saved dungeon must have all 27 anchor checks passed")
        receipt = json.loads((ROOT / ".local/hlck/dungeon-anchor-result.json").read_text(encoding="utf-8-sig"))
        current_target = stage.digest(stage.checked_file(stage.TARGET_MAP, ".umap"))
        if current_target != receipt.get("map_sha256_after"):
            raise RuntimeError("The dungeon map changed after the successful anchor stage")
        collision = json.loads((ROOT / ".local/hlck/entrance-collision.json").read_text(encoding="utf-8-sig"))
        point = [sample for sample in collision.get("samples", []) if sample.get("xy") == list(POSITION[:2])]
        if collision.get("status") != "inspected" or len(point) != 1 or not point[0].get("usable") or point[0]["spawn_center"] != list(POSITION):
            raise RuntimeError("The exact selected location lacks successful collision evidence")
        report["collision"] = point[0]
        api = module("_bb_register_api", "Tools/probe_hlck_registration_api.py").run()
        if api["status"] != "inspected":
            raise RuntimeError("Native registration reflection/readback preflight failed")
        api_report = json.loads(Path(api["report"]).read_text(encoding="utf-8-sig"))
        if api_report.get("configured_entrance_class") != STOCK_CLASS:
            raise RuntimeError("The native loader's configured entrance class changed")
        report["configured_runtime_class"] = STOCK_CLASS
        table = unreal.EditorAssetLibrary.load_asset(stage.DESTINATIONS[stage.SOURCE_DUNGEONS])
        for destination in stage.DESTINATIONS.values():
            asset = unreal.EditorAssetLibrary.load_asset(destination)
            if asset is None or str(unreal.EditorAssetLibrary.get_metadata_tag(asset, stage.META_OWNER)) != stage.OWNER:
                raise RuntimeError("Missing exact ownership for " + destination)
        klass = unreal.EditorAssetLibrary.load_blueprint_class(stage.DESTINATIONS[stage.SOURCE_ENTRANCE])
        if klass is None:
            raise RuntimeError("Owned entrance Blueprint class is unavailable")
        entrance = unreal.get_default_object(klass)
        handle = entrance.get_editor_property("dungeon_name")
        if handle.get_editor_property("data_table") != table or str(handle.get_editor_property("dungeon_name")) != stage.ROW_NAME:
            raise RuntimeError("The compiled entrance does not point to the owned row")
        report["owned_row_handle"] = {"table": table.get_path_name(), "row": stage.ROW_NAME}
        report["beacon_position"] = list(POSITION)
        report["beacon_policy"] = "Map beacon intentionally co-located with the verified return spawn"
        fields = stage.schema_fields(json.loads(stage.PROBE.read_text(encoding="utf-8-sig")))
        defaults = stage.source_row(unreal, unreal.load_asset(stage.SOURCE_DUNGEONS), fields)
        tables = unreal.DataTableFunctionLibrary
        if [str(name) for name in tables.get_data_table_row_names(table)] != [stage.ROW_NAME]:
            raise RuntimeError("The owned table does not contain exactly the intended dungeon row")
        report["row_fields"] = {}
        for index, (raw, friendly) in enumerate(fields):
            values = [str(value) for value in tables.get_data_table_column_as_string(table, raw)]
            if len(values) != 1 or (stage.TARGET_MAP not in values[0] if friendly == "DungeonLevel" else values != [defaults[index]]):
                raise RuntimeError("The native dungeon row contract changed at " + friendly)
            report["row_fields"][friendly] = values[0]
        report["rows_before"] = rows(unreal)
        if report["rows_before"]:
            saved = verified_saved_registration(unreal, stage, report["rows_before"])
            report["sql_sha256"] = saved["sql_sha256"]
            report["saved_registration_receipt"] = str(REPORT)
            report["dirty_after"] = guard.require_clean(unreal)
            report["status"] = "already_registered"
            return {"status": report["status"], "report": str(output), "receipt": str(REPORT)}
        content_before = hashes(CONTENT, stage.digest)
        installed_before = metadata(KIT_CONTENT, ".umap")
        protected = list((KIT_CONTENT / "SQLiteDB").glob("*.sqlite"))
        protected += [KIT_CONTENT / (name[len("/Game/"):] + ".umap") for name in (
            OVERLAND, "/Game/Levels/Overland/HOG/HN_AZ", "/Game/Levels/Overland/SubLevels/HN_AZ_Quidditch")]
        protected_before = {str(path): stage.digest(path) for path in protected}
        report["protected_hashes_before"] = protected_before
        report["installed_map_count"] = len(installed_before)
        report["content_hashes_before"] = content_before
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        backup = ROOT / ".local/hlck/registration-backups" / stamp
        backup.mkdir(parents=True, exist_ok=False)
        sql_file = CONTENT / "ModEdits.sql"
        if sql_file.exists():
            shutil.copy2(str(sql_file), str(backup / "ModEdits.sql"))
        write(backup / "manifest.json", {"sql_existed": sql_file.exists(), "content_hashes": content_before,
              "installed_maps": installed_before, "protected_hashes": protected_before})
        report["backup"] = str(backup)
        before_actors = {a.get_path_name(): anchors.actor_record(a) for a in unreal.EditorLevelLibrary.get_all_level_actors()}
        report["status"] = "preflight_passed"
        write(output, report)
        if not dry_run:
            report["status"] = "calling_native_RegisterTransientDungeonEntrance"
            report["registration_attempted"] = True
            write(output, report)
            unreal.BeaconManager.register_transient_dungeon_entrance(
                stage.ROW_NAME, unreal.Vector(*POSITION), YAW, unreal.Vector(*POSITION), 0)
            report["registration_invoked"] = True
        report["rows_after"] = rows(unreal)
        if dry_run:
            if report["rows_after"]:
                raise RuntimeError("A dry run unexpectedly changed the database")
        else:
            if len(report["rows_after"]) != 1 or not sql_file.is_file():
                raise RuntimeError("RegisterDungeon did not create one row and the owned SQL delta")
            verify_row(report["rows_after"][0], POSITION)
        report["status"] = "dry_run_passed" if dry_run else "registered"
    except Exception:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
    finally:
        try:
            if before_actors is not None:
                after = {a.get_path_name(): anchors.actor_record(a) for a in unreal.EditorLevelLibrary.get_all_level_actors()}
                if after != before_actors:
                    raise RuntimeError("The original Overland actor set/transform changed; no map was saved")
                report["original_actors_unchanged"] = True
                report["dirty_after"] = guard.require_clean(unreal)
                protected_after = {name: stage.digest(Path(name)) for name in protected_before}
                report["protected_hashes_after"] = protected_after
                report["installed_maps_unchanged"] = metadata(KIT_CONTENT, ".umap") == installed_before
                if protected_after != protected_before or not report["installed_maps_unchanged"]:
                    raise RuntimeError("An installed database/map changed unexpectedly")
                content_after = hashes(CONTENT, stage.digest)
                changes = sorted(name for name in set(content_before) | set(content_after)
                                 if content_before.get(name) != content_after.get(name))
                report["content_files_changed"] = changes
                expected = ["ModEdits.sql"] if report.get("registration_attempted") else []
                if changes != expected:
                    raise RuntimeError("Unexpected owned content changes: " + json.dumps(changes))
                if not dry_run and (CONTENT / "ModEdits.sql").is_file():
                    report["sql_sha256"] = stage.digest(CONTENT / "ModEdits.sql")
        except Exception:
            report["status"] = "failed"
            report["cleanup_error"] = traceback.format_exc()
        if not dry_run and report["status"] == "registered":
            write(REPORT, report)
        write(output, report)
    return {"status": report["status"], "report": str(output), "receipt": str(REPORT)}


if __name__ == "__main__":
    RESULT = run(dry_run=globals().get("BRIDGE_ARGS", {}).get("dry_run", True))

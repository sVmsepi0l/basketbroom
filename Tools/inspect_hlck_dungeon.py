"""Read-only inspection of the already-open native dungeon staging assets."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/dungeon-inspection.json"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def inspect():
    result = {"status": "not_run", "read_only": True, "checks": [],
              "inspected_utc": datetime.now(timezone.utc).isoformat(),
              "travel_verified": False, "registration_invoked": False}
    try:
        import unreal
        stage = module("_bb_dungeon_inspect_stage", "Tools/stage_hlck_dungeon.py")
        module("_bb_dungeon_inspect_guard", "Mod/Tools/import_sources.py")._editor()
        project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        if project != Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject").resolve():
            raise RuntimeError("Expected the exact installed Phoenix project")
        if unreal.EditorLevelLibrary.get_pie_worlds(True):
            raise RuntimeError("Stop PIE before read-only dungeon inspection")
        world = unreal.EditorLevelLibrary.get_editor_world()
        if stage.world_path(world) != stage.TARGET_MAP:
            raise RuntimeError("Open the staged dungeon map first; this inspection loads no maps")
        stage.require_clean_maps(unreal)

        def check(name, passed, detail):
            result["checks"].append({"name": name, "passed": bool(passed), "detail": detail})

        result["world"] = world.get_path_name()
        result["active_mod"] = str(unreal.GameModManagerSubsystem.get_active_mod_name_bp())
        arena = module("_bb_dungeon_geometry_inspect", "Tools/inspect_hlck_arena.py")
        arena.LEVEL_PATH = stage.TARGET_MAP
        arena.REPORT = ROOT / ".local/hlck/dungeon-geometry-inspection.json"
        geometry = arena.inspect()
        result["checks"].extend(geometry["checks"])
        owners = [actor for actor in unreal.EditorLevelLibrary.get_all_level_actors() if actor.actor_has_tag(stage.BASE_MARKER)]
        check("dungeon_staging_ownership", len(owners) == 1 and owners[0].actor_has_tag(stage.STAGE_MARKER), [actor.get_path_name() for actor in owners])
        original = json.loads((ROOT / ".local/hlck/arena-port-result.json").read_text(encoding="utf-8-sig"))["map_sha256"]
        check("source_arena_unchanged", stage.digest(stage.checked_file(stage.SOURCE_MAP, ".umap")) == original, original)
        library = unreal.EditorAssetLibrary
        owned = {}
        for source, destination in stage.DESTINATIONS.items():
            asset = unreal.load_asset(destination)
            valid = asset is not None and stage.checked_file(destination).is_file()
            if valid:
                valid = library.get_metadata_tag(asset, stage.META_OWNER) == stage.OWNER and library.get_metadata_tag(asset, stage.META_SOURCE) == source
            check("owned_asset:" + destination.rsplit("/", 1)[-1], valid, destination)
            if asset is None:
                raise RuntimeError("Staged asset unavailable: " + destination)
            owned[source] = asset
        tables = unreal.DataTableFunctionLibrary
        table = owned[stage.SOURCE_DUNGEONS]
        fields = stage.schema_fields(json.loads(stage.PROBE.read_text(encoding="utf-8-sig")))
        defaults = stage.source_row(unreal, unreal.load_asset(stage.SOURCE_DUNGEONS), fields)
        names = [str(name) for name in tables.get_data_table_row_names(table)]
        values = {raw: [str(value) for value in tables.get_data_table_column_as_string(table, raw)] for raw, friendly in fields}
        correct = names == [stage.ROW_NAME]
        for i, (raw, friendly) in enumerate(fields):
            correct = correct and (len(values[raw]) == 1 and stage.TARGET_MAP in values[raw][0] if friendly == "DungeonLevel" else values[raw] == [defaults[i]])
        check("dungeon_row_and_all_template_defaults", correct, {"rows": names, "values": values})
        subdivision = owned[stage.SOURCE_SUBDIVISIONS]
        expected = stage.subdivision_values(unreal)
        actual = {key: [str(value) for value in tables.get_data_table_column_as_string(subdivision, key)] for key in expected}
        check("subdivision_matches_native_wizard", [str(name) for name in tables.get_data_table_row_names(subdivision)] == [stage.ROW_NAME] and actual == {key: [value] for key, value in expected.items()}, actual)
        mutator = unreal.get_default_object(library.load_blueprint_class(stage.DESTINATIONS[stage.SOURCE_MUTATOR]))
        pairs = stage.extension_pairs(mutator)
        wanted = {(stage.DESTINATIONS[stage.SOURCE_DUNGEONS], stage.BASE_DUNGEONS), (stage.DESTINATIONS[stage.SOURCE_SUBDIVISIONS], stage.BASE_SUBDIVISIONS)}
        check("both_native_table_extensions", pairs == wanted, sorted(pairs))
        entrance = unreal.get_default_object(library.load_blueprint_class(stage.DESTINATIONS[stage.SOURCE_ENTRANCE]))
        handle = entrance.get_editor_property("dungeon_name")
        check("entrance_default_uses_owned_dungeon_row", handle.get_editor_property("data_table") == table and str(handle.get_editor_property("dungeon_name")) == stage.ROW_NAME, str(handle))
        result["status"] = "passed" if all(item["passed"] for item in result["checks"]) else "failed"
        result["passed"] = sum(item["passed"] for item in result["checks"])
        result["failed"] = len(result["checks"]) - result["passed"]
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "passed": result.get("passed"), "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = inspect()

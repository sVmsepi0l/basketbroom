"""Read-only Creator Kit dungeon/template reflection and export probe.

Run through Tools/editor_bridge.py in the installed Phoenix UE4.27 editor,
after Asset Registry discovery finishes and with PIE stopped. The probe loads
template/data/Blueprint assets but never loads a map, spawns an actor, compiles
a Blueprint, modifies an asset/default, selects an active mod, or registers a
dungeon. Transient export-task configuration is the only UObject write.

Reports and text exports go only to .local/hlck/dungeon-probe*. Existing map
and asset files are never saved. Missing reflection/export APIs are recorded
as unavailable, rather than guessed. Outside Unreal, --plan lists the scope.
The bridge may pass wait_for_registry=True (max_wall_seconds defaults to 600)
to queue inspection on a Slate callback. The default remains an immediate run.
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import time
import traceback

try:
    import unreal
except ImportError:
    unreal = None

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject")
REPORT = ROOT / ".local/hlck/dungeon-probe.json"
EXPORTS = ROOT / ".local/hlck/dungeon-probe"
ASSETS = (
    ("dungeon_template_table", "/PhoenixUGC/DungeonMod/Data/DT_PLUGIN_NAME_DungeonsTable", "table"),
    ("subdivision_template_table", "/PhoenixUGC/DungeonMod/Data/UI_DT_PLUGIN_NAME_MapSubdivisionTable", "table"),
    ("template_mutator", "/PhoenixUGC/DungeonMod/Blueprints/BP_PLUGIN_NAME_DataMutator", "blueprint"),
    ("entrance", "/ModSupport/Blueprints/BP_DungeonEntrance", "blueprint"),
    ("exit", "/Game/Gameplay/Blueprints/Triggers/BP_WorldTeleport", "blueprint"),
    ("base_dungeons", "/Game/Data/Dungeons/DT_TransientDungeonsTable", "base_table"),
    ("base_subdivisions", "/Game/UI/Map/UI_DT_MapDungeonSubdivisionTable_Comp", "base_table"),
    ("template_map", "/PhoenixUGC/DungeonMod/Maps/PLUGIN_NAME_DungeonMap", "map_metadata_only"),
    ("arena_map", "/Basketbroom/Maps/BB_Arena_Port", "map_metadata_only"),
)
API_CLASSES = (
    "DungeonEntrancePlacement", "DungeonName", "ModMutator", "DataTableExtension",
    "GameModManagerSubsystem", "ModSupportBPFunctionLibrary", "PhoenixBPLibrary",
    "UGCRegistry", "FixupDungeonData", "DataTableFunctionLibrary", "DataTable",
    "PhxEditorBlueprintLibrary", "PeevesBlueprintHelpers", "Object",
)
KEYWORDS = ("dungeon", "table", "mutator", "active_mod", "register", "fixup", "call_method")
GETTERS = tuple(name + suffix for name in
                ("get_active_mod_name", "get_active_mod_path", "get_active_mod_content_path",
                 "get_active_mod_package_path_root", "get_active_mod_label_for_ui")
                for suffix in ("_bp", ""))


def stamp():
    return datetime.now(timezone.utc).isoformat()


def attempt(function):
    try:
        return {"available": True, "value": value(function())}
    except Exception as error:
        return {"available": False, "error": str(error), "error_type": type(error).__name__}


def value(item, depth=0):
    if item is None or isinstance(item, (bool, int, float, str)):
        return item
    if depth > 3:
        return str(item)[:3000]
    if isinstance(item, dict):
        return {str(key): value(val, depth + 1) for key, val in item.items()}
    if isinstance(item, (list, tuple)) or type(item).__name__ in ("Array", "Set"):
        return [value(val, depth + 1) for val in item]
    if callable(getattr(item, "get_path_name", None)):
        return {"object_path": item.get_path_name(), "class": item.get_class().get_path_name()}
    if callable(getattr(item, "get_editor_property", None)):
        doc = str(getattr(type(item), "__doc__", "") or "")
        names = set(re.findall(r"(?:^|\n)\s*-?\s*[`*]*([a-z_][a-z0-9_]*)[`*]*\s*\([^\n]*\):\s*\[", doc))
        if type(item).__name__ == "DungeonName":
            names.update(("dungeon_name", "data_table"))
        fields = {}
        for name in sorted(names):
            try:
                fields[name] = value(item.get_editor_property(name), depth + 1)
            except Exception as error:
                fields[name] = {"error": str(error)}
        if fields:
            return {"struct_type": type(item).__name__, "fields": fields, "text": str(item)[:12000]}
    return str(item)[:12000]


def properties(obj, extra=()):
    doc = str(getattr(type(obj), "__doc__", "") or "")
    # Native docs list editor fields; Blueprint-only fields may instead appear
    # in the exported CDO/Blueprint. All requested spelling variants are logged.
    names = set(re.findall(r"(?:^|\n)\s*-?\s*[`*]*([a-z_][a-z0-9_]*)[`*]*\s*\([^\n]*\):\s*\[", doc))
    names.update(extra)
    return {name: attempt(lambda name=name: obj.get_editor_property(name)) for name in sorted(names)}


def describe(obj):
    members = {}
    for name in dir(obj):
        if name.startswith("_") or not any(key in name.lower() for key in KEYWORDS):
            continue
        try:
            member = getattr(obj, name)
            members[name] = {"callable": callable(member), "doc": str(getattr(member, "__doc__", "") or "")[:5000]}
        except Exception as error:
            members[name] = {"error": str(error)}
    return {"doc": str(getattr(obj, "__doc__", "") or "")[:30000], "members": members}


def export_object(obj, stem, extension, exporter_name=None):
    path = EXPORTS / (stem + "." + extension)
    result = {"path": str(path), "format": extension, "exporter_requested": exporter_name or "automatic"}
    try:
        exporter = getattr(unreal, exporter_name, None) if exporter_name else None
        if exporter_name and exporter is None:
            raise RuntimeError("Exporter unavailable: " + exporter_name)
        task = unreal.AssetExportTask()
        task.set_editor_property("object", obj)
        task.set_editor_property("filename", str(path))
        task.set_editor_property("automated", True)
        task.set_editor_property("prompt", False)
        task.set_editor_property("replace_identical", True)
        if exporter:
            task.set_editor_property("exporter", exporter())
        result["succeeded"] = bool(unreal.Exporter.run_asset_export_task(task))
        result["errors"] = [str(error) for error in task.get_editor_property("errors")]
        if result["succeeded"] and path.is_file():
            content = path.read_bytes()
            result.update(bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
            # This is the exact native export, not a fabricated row schema.
            text = content.decode("utf-8-sig", errors="replace")
            if extension == "csv":
                rows = list(csv.reader(io.StringIO(text)))
                result["columns"] = rows[0] if rows else []
                result["rows"] = rows[1:]
            elif extension == "json":
                try:
                    result["data"] = json.loads(text)
                except ValueError as error:
                    result["parse_error"] = str(error)
            elif extension == "t3d":
                lines = text.splitlines()
                pattern = r"RegisterDungeon|RegisterTransientDungeon|RegisterDungeonExit|CallInEditor|FunctionFlags|DungeonName|DataTableExtensions|RowStruct|DungeonMap|DungeonLevel"
                selected = set()
                for index, line in enumerate(lines):
                    if re.search(pattern, line):
                        selected.update(range(max(0, index - 2), min(len(lines), index + 3)))
                result["relevant_lines"] = [{"line": index + 1, "text": lines[index][:1500]}
                                            for index in sorted(selected)[:500]]
                result["relevant_lines_truncated"] = len(selected) > 500
    except Exception as error:
        result.update(succeeded=False, error=str(error), error_type=type(error).__name__)
    return result


def registry_record(registry, path):
    folder, _, name = path.rpartition("/")
    matches = [entry for entry in registry.get_assets_by_path(folder, recursive=False)
               if str(entry.package_name) == path]
    return [{key: value(getattr(entry, key)) for key in
             ("object_path", "package_name", "package_path", "asset_name", "asset_class")}
            for entry in matches]


def function_metadata(cls, name, stem):
    result = {"name": name, "invoked": False}
    try:
        function = unreal.find_object(cls, name)
        if function is None:
            result.update(found=False, note="No loaded reflected function found under this class; inspect Blueprint export.")
            return result
        result.update(found=True, object=value(function))
        result["properties"] = properties(function, ("function_flags", "FunctionFlags", "num_parms", "parms_size"))
        result["metadata"] = {key: attempt(lambda key=key: unreal.EditorAssetLibrary.get_metadata_tag(function, key))
                              for key in ("CallInEditor", "DisplayName", "Category", "ToolTip", "BlueprintCallable")}
        result["export"] = export_object(function, stem + "_" + name, "t3d", "ObjectExporterT3D")
    except Exception as error:
        result.update(found=False, error=str(error))
    return result


def inspect_asset(registry, key, path, kind):
    result = {"requested_path": path, "kind": kind, "registry": registry_record(registry, path)}
    if kind == "map_metadata_only":
        result["loaded"] = False
        result["note"] = "World presence is checked only through Asset Registry; no map is loaded."
        return result
    asset = unreal.load_asset(path)
    if asset is None:
        result.update(loaded=False, error="Asset could not be loaded after registry discovery completed.")
        return result
    result.update(loaded=True, object=value(asset))
    if kind in ("table", "base_table"):
        result["properties"] = properties(asset, ("row_struct", "RowStruct", "import_key_field"))
        names = unreal.DataTableFunctionLibrary.get_data_table_row_names(asset)
        result["row_count"] = len(names)
        result["row_names"] = [str(name) for name in names[:256]]
        result["row_names_truncated"] = len(names) > 256
        try:
            row_struct = asset.get_editor_property("row_struct")
            result["row_struct"] = value(row_struct)
            if row_struct:
                result["row_struct_api"] = describe(row_struct)
                result["row_struct_properties"] = properties(row_struct, ("editor_data", "guid", "status"))
                result["row_struct_export"] = export_object(row_struct, key + "_row_struct", "t3d", "ObjectExporterT3D")
        except Exception as error:
            result["row_struct_error"] = str(error)
        if kind == "table":
            result["exports"] = [export_object(asset, key, extension) for extension in ("csv", "json")]
    elif kind == "blueprint":
        result["blueprint_properties"] = properties(asset, ("parent_class", "generated_class", "blueprint_type", "status",
                                                             "new_variables", "function_graphs", "ubergraph_pages"))
        result["exports"] = [export_object(asset, key + "_blueprint", "t3d", "ObjectExporterT3D")]
        cls = unreal.EditorAssetLibrary.load_blueprint_class(path)
        result["generated_class"] = value(cls)
        if cls:
            cdo = unreal.get_default_object(cls)
            result["class_api"] = describe(cls)
            result["default_object"] = value(cdo)
            result["defaults"] = properties(cdo, ("dungeon_name", "DungeonName", "data_table_extensions", "DataTableExtensions",
                                                  "dungeon_table", "DungeonTable", "this_is_a_second__exit", "IsExit"))
            result["exports"].append(export_object(cdo, key + "_defaults", "t3d", "ObjectExporterT3D"))
            result["functions"] = [function_metadata(cls, name, key) for name in
                                   (("RegisterDungeon", "GetDungeonDatatableHandle") if key == "entrance"
                                    else ("RegisterDungeonExit",) if key == "exit" else ())]
    return result


def write_report(report):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    for attempt_index in range(6):
        try:
            temporary.replace(REPORT)
            return
        except PermissionError:
            if attempt_index == 5:
                raise
            # Retry replacement only; never block the editor on a sleep.


def probe():
    report = {"status": "not_run", "started_utc": stamp(), "assets": {}, "apis": {},
              "scope": "Read-only loaded-asset reflection and native text exports",
              "registration_invoked": False, "active_mod_changed": False, "asset_or_map_saved": False}
    try:
        if unreal is None:
            raise RuntimeError("Run this probe inside the installed Creator Kit; no engine API is available here.")
        version = str(unreal.SystemLibrary.get_engine_version())
        report["engine"] = version
        if not version.startswith("4.27."):
            raise RuntimeError("Expected Creator Kit UE4.27, got " + version)
        project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        report["project"] = str(project)
        if project != PROJECT.resolve():
            raise RuntimeError("Expected the exact installed Phoenix Creator Kit project.")
        if unreal.EditorLevelLibrary.get_pie_worlds(True):
            raise RuntimeError("Stop PIE before this read-only editor inspection.")
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        if registry.is_loading_assets():
            raise RuntimeError("Asset Registry discovery is still running; retry after it completes.")
        descriptor = project.parent / "Mods/Basketbroom/Basketbroom.uplugin"
        expected = ROOT / "Mod/Basketbroom/Basketbroom.uplugin"
        report["repo_mod_mount"] = {"descriptor": str(descriptor), "expected": str(expected),
                                    "matches": descriptor.is_file() and descriptor.resolve() == expected.resolve()}
        if not report["repo_mod_mount"]["matches"]:
            raise RuntimeError("The Basketbroom mount does not resolve to this repository's separate UE4 mod.")
        report["editor_world_before"] = value(unreal.EditorLevelLibrary.get_editor_world())
        EXPORTS.mkdir(parents=True, exist_ok=True)
        report["status"] = "running"
        for name in API_CLASSES:
            cls = getattr(unreal, name, None)
            report["apis"][name] = describe(cls) if cls is not None else {"available": False}
            if cls is not None and name in ("DungeonEntrancePlacement", "ModMutator"):
                try:
                    cdo = unreal.get_default_object(cls)
                    report["apis"][name]["default_object"] = value(cdo)
                    report["apis"][name]["defaults"] = properties(cdo, ("dungeon_name", "data_table_extensions"))
                    report["apis"][name]["default_export"] = export_object(cdo, name + "_native_defaults", "t3d", "ObjectExporterT3D")
                except Exception as error:
                    report["apis"][name]["default_error"] = str(error)
        report["exporter_apis"] = {name: describe(getattr(unreal, name)) for name in dir(unreal)
                                   if "Exporter" in name and any(term in name.lower() for term in ("table", "object", "json", "csv"))}
        report["active_mod_getters"] = {}
        manager = getattr(unreal, "GameModManagerSubsystem", None)
        for name in GETTERS:
            method = getattr(manager, name, None) if manager else None
            report["active_mod_getters"][name] = attempt(method) if callable(method) else {"available": False}
        for key, path, kind in ASSETS:
            try:
                report["assets"][key] = inspect_asset(registry, key, path, kind)
            except Exception:
                report["assets"][key] = {"requested_path": path, "error": traceback.format_exc()}
        report["editor_world_after"] = value(unreal.EditorLevelLibrary.get_editor_world())
        report["same_editor_world"] = report["editor_world_before"] == report["editor_world_after"]
        report["status"] = "complete" if report["same_editor_world"] else "error"
        report["interpretation"] = "Complete means inspection finished, not that registration or travel is valid; inspect per-item availability/errors."
    except Exception:
        report["error"] = traceback.format_exc()
        if report["status"] == "running":
            report["status"] = "error"
    report["finished_utc"] = stamp()
    write_report(report)
    if unreal:
        unreal.log("BASKETBROOM_HLCK_DUNGEON_PROBE %s: %s" % (report["status"], REPORT))
    return {"status": report["status"], "report": str(REPORT), "exports": str(EXPORTS), "registration_invoked": False}


class RegistryWait:
    """One owned Slate callback; no editor tick loop or blocking registry wait."""

    def __init__(self, max_wall_seconds):
        self.started = time.monotonic()
        self.requested_utc = stamp()
        self.max_wall_seconds = float(max_wall_seconds)
        if not 1 <= self.max_wall_seconds <= 600:
            raise ValueError("max_wall_seconds must be between 1 and 600")
        self.handle = None
        self.done = False
        self.last_check = -1.0
        self.last_report = -1.0
        self.result = None

    def publish(self, status, phase, reason=None):
        report = {"status": status, "phase": phase, "requested_utc": self.requested_utc,
                  "wait_for_registry": True, "max_wall_seconds": self.max_wall_seconds,
                  "elapsed_wall_seconds": round(time.monotonic() - self.started, 3),
                  "registration_invoked": False, "active_mod_changed": False, "asset_or_map_saved": False}
        if reason:
            report["reason"] = reason
        if self.done:
            report["finished_utc"] = stamp()
        write_report(report)
        self.last_report = time.monotonic()

    def unregister(self):
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None

    def start(self):
        self.publish("requested", "waiting_for_registry")
        # Reject another engine/project immediately, before waiting on its
        # registry. probe() will repeat all guards just before asset reads.
        version = str(unreal.SystemLibrary.get_engine_version())
        project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
        if not version.startswith("4.27.") or project != PROJECT.resolve():
            self.done = True
            self.publish("not_run", "preflight", "Expected the exact installed Phoenix UE4.27 Creator Kit project.")
            return {"status": "not_run", "report": str(REPORT)}
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        return {"status": "requested", "wait_for_registry": True, "max_wall_seconds": self.max_wall_seconds,
                "report": str(REPORT), "registration_invoked": False}

    def tick(self, delta_seconds):
        if self.done:
            return
        now = time.monotonic()
        if now - self.last_check < 1.0:
            return
        self.last_check = now
        try:
            if now - self.started >= self.max_wall_seconds:
                self.done = True
                self.unregister()
                self.publish("not_run", "registry_timeout", "Asset Registry did not become ready before the wall-time limit.")
                return
            if unreal.EditorLevelLibrary.get_pie_worlds(True):
                self.done = True
                self.unregister()
                self.publish("not_run", "preflight", "PIE became active while waiting; no dungeon inspection was run.")
                return
            if unreal.AssetRegistryHelpers.get_asset_registry().is_loading_assets():
                if now - self.last_report >= 5.0 or self.last_report < 0:
                    self.publish("running", "waiting_for_registry")
                return
            self.publish("running", "inspecting")
            # Detach before doing any exports: re-entrancy cannot run the probe
            # twice, and a failing probe cannot leave a live polling callback.
            self.unregister()
            self.done = True
            self.result = probe()
        except Exception:
            self.done = True
            self.unregister()
            self.publish("error", "registry_wait", traceback.format_exc())


def run(wait_for_registry=False, max_wall_seconds=600):
    if not wait_for_registry or unreal is None:
        return probe()
    previous = getattr(unreal, "_basketbroom_hlck_dungeon_probe", None)
    if previous is not None and not previous.done:
        return {"status": "already_requested", "report": str(REPORT), "registration_invoked": False}
    runner = RegistryWait(max_wall_seconds)
    unreal._basketbroom_hlck_dungeon_probe = runner
    try:
        return runner.start()
    except Exception:
        runner.done = True
        runner.unregister()
        runner.publish("error", "preflight", traceback.format_exc())
        return {"status": "error", "report": str(REPORT), "registration_invoked": False}


if __name__ == "__main__":
    if unreal is None:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--plan", action="store_true", help="Print planned inspection without loading Unreal or writing a report")
        args = parser.parse_args()
        if args.plan:
            RESULT = {"status": "not_run", "assets": ASSETS, "api_classes": API_CLASSES, "report": str(REPORT)}
        else:
            RESULT = probe()
        print(json.dumps(RESULT, indent=2))
    else:
        bridge_args = globals().get("BRIDGE_ARGS", {})
        RESULT = run(wait_for_registry=bridge_args.get("wait_for_registry", False),
                     max_wall_seconds=bridge_args.get("max_wall_seconds", 600))

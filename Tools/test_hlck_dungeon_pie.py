"""Observe one real owned-dungeon PIE session, then end it without travelling.

Call arm() through the editor bridge, then use the normal editor Play button.
The kit exposes Simulate but no reflected true-Play starter, so this helper never
substitutes simulation. It observes the native controller/character, grounded
spawn, runtime database, UGC tables and exit components. No input, possession,
teleport, generic OpenLevel, registration, asset save or account operation occurs.
"""
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
WORLD = "/Basketbroom/Maps/Basketbroom_DungeonMap"
REPORT = ROOT / ".local/hlck/dungeon-pie-smoke.json"
STATE_NAME = "_basketbroom_hlck_dungeon_pie_smoke"
DYNAMIC_DATABASE = Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Content\SQLiteDB\PhoenixDynData.sqlite")


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def canonical(world):
    if world is None:
        return None
    path = world.get_path_name().split(".", 1)[0]
    return re.sub(r"/UEDPIE_\d+_", "/", path)


def is_owned_pie(world):
    return world is not None and re.fullmatch(
        r"/Basketbroom/Maps/UEDPIE_\d+_Basketbroom_DungeonMap\.Basketbroom_DungeonMap",
        world.get_path_name()) is not None


def object_class(obj):
    return obj.get_class().get_path_name() if obj else None


def backup_databases(backup, protected_before, digest):
    """Preserve actual pre-Play bytes, refusing a changing source snapshot."""
    copies = {}
    destination = backup / "installed-databases"
    destination.mkdir(parents=True, exist_ok=False)
    for name, expected in protected_before.items():
        source = Path(name)
        if source.suffix.lower() != ".sqlite":
            continue
        target = destination / source.name
        if target.exists():
            raise RuntimeError("Duplicate protected database basename")
        shutil.copy2(str(source), str(target))
        if digest(target) != expected or digest(source) != expected:
            raise RuntimeError("Protected database changed during pre-Play backup: " + source.name)
        copies[name] = {"copy": str(target), "sha256": expected}
    return copies


class Smoke:
    def __init__(self, unreal):
        self.u = unreal
        self.guard = module("_bb_pie_guard", "Tools/load_hlck_dungeon.py")
        self.stage = module("_bb_pie_stage", "Tools/stage_hlck_dungeon.py")
        self.registrar = module("_bb_pie_registration", "Tools/register_hlck_dungeon.py")
        self.anchors = module("_bb_pie_anchors", "Tools/stage_hlck_dungeon_anchors.py")
        self.started = time.monotonic()
        self.first_pie = None
        self.stop_time = None
        self.last_poll = 0.0
        self.stable_since = None
        self.native_ready_since = None
        self.owns_session = False
        self.handle = None
        self.result = {"status": "preflight", "started_utc": datetime.now(timezone.utc).isoformat(),
                       "runtime_checks": "NOT_RUN",
                       "travel_invoked": False, "input_injected": False, "map_saved": False,
                       "play_start": "Normal editor Play requested from root UI", "checks": {}}

    def write(self):
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        temporary = REPORT.with_name(REPORT.name + ".next")
        temporary.write_text(json.dumps(self.result, indent=2) + "\n", encoding="utf-8")
        for attempt in range(8):
            try:
                temporary.replace(REPORT)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.025)

    def preflight(self):
        u = self.u
        self.result["active_mod"] = self.guard.require_editor(u)
        self.result["dirty_before"] = self.guard.require_clean(u)
        if canonical(u.EditorLevelLibrary.get_editor_world()) != WORLD:
            raise RuntimeError("Only the already-open owned dungeon may start this smoke test")
        if not callable(getattr(u.EditorLevelLibrary, "editor_end_play", None)):
            raise RuntimeError("The supported PIE cleanup API is unavailable")
        if not callable(getattr(getattr(u, "UGCBlueprintLibrary", None), "get_ugc_registry", None)):
            raise RuntimeError("The public runtime UGC registry query is unavailable")
        inspection = module("_bb_pie_saved_preflight", "Tools/plan_hlck_dungeon_registration.py").plan()
        if inspection.get("status") != "prepared":
            raise RuntimeError("Saved dungeon and registration validation failed")
        saved = json.loads((ROOT / ".local/hlck/dungeon-registration-plan.json").read_text(encoding="utf-8-sig"))
        if saved.get("checks_passed") != 27 or not saved.get("saved_registration_verified"):
            raise RuntimeError("All 27 saved checks and registered SQL must pass before PIE")
        content = self.registrar.CONTENT
        kit = self.registrar.KIT_CONTENT
        self.content_before = self.registrar.hashes(content, self.stage.digest)
        self.installed_before = self.registrar.metadata(kit, ".umap")
        self.protected_before = {str(path): self.stage.digest(path) for path in (kit / "SQLiteDB").glob("*.sqlite")}
        for path in (kit / "Levels/Overland/Overland.umap", kit / "Levels/Overland/HOG/HN_AZ.umap"):
            self.protected_before[str(path)] = self.stage.digest(path)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        backup = ROOT / ".local/hlck/pie-smoke-backups" / stamp
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(str(self.stage.checked_file(WORLD, ".umap")), str(backup / "Basketbroom_DungeonMap.umap"))
        shutil.copy2(str(content / "ModEdits.sql"), str(backup / "ModEdits.sql"))
        protected_copies = backup_databases(backup, self.protected_before, self.stage.digest)
        self.registrar.write(backup / "manifest.json", {"content_hashes": self.content_before,
            "installed_map_metadata": self.installed_before, "protected_hashes": self.protected_before,
            "protected_database_copies": protected_copies})
        self.result["backup"] = str(backup)
        self.result["protected_hashes_before"] = self.protected_before
        self.result["status"] = "awaiting_actual_play"
        self.write()

    def snapshot(self, world):
        u = self.u
        self.result["runtime_checks"] = "OBSERVED"
        checks = {"owned_pie_world": canonical(world) == WORLD}
        snap = {"world": world.get_path_name()}
        mode = u.GameplayStatics.get_game_mode(world)
        instance = u.GameplayStatics.get_game_instance(world)
        controller = u.GameplayStatics.get_player_controller(world, 0)
        pawn = u.GameplayStatics.get_player_pawn(world, 0)
        snap.update(game_mode=object_class(mode), game_instance=object_class(instance),
                    controller=object_class(controller), pawn=object_class(pawn))
        checks["native_game_mode"] = snap["game_mode"] == "/Game/Data/GameMode/Phoenix_Game_Mode.Phoenix_Game_Mode_C"
        checks["native_game_instance"] = snap["game_instance"] == "/Game/Data/GameInstance/BP_PhoenixGameInstance.BP_PhoenixGameInstance_C"
        checks["native_character"] = pawn is not None and isinstance(pawn, u.Character)
        checks["native_player_blueprint"] = snap["pawn"] == "/Game/Pawn/Player/BP_Biped_Player.BP_Biped_Player_C"
        checks["native_controller_blueprint"] = snap["controller"] == "/Game/Pawn/Player/BP_Phoenix_Player_Controller.BP_Phoenix_Player_Controller_C"
        checks["possessed_local_player"] = controller is not None and pawn is not None and controller.get_controlled_pawn() == pawn and controller.is_local_controller()
        checks["grounded_start"] = False
        native_ready = all(checks[name] for name in ("native_game_mode", "native_game_instance", "native_character", "possessed_local_player"))
        if not native_ready:
            self.native_ready_since = None
            self.result.update(checks=checks, snapshot=snap,
                               passed=sum(bool(value) for value in checks.values()), total=len(checks))
            return False
        if self.native_ready_since is None:
            self.native_ready_since = time.monotonic()
        if pawn:
            position = self.anchors.xyz(pawn.get_actor_location())
            snap["pawn_position"] = position
            snap["distance_from_start_xy_cm"] = math.hypot(position[0] + 3000.0, position[1])
            movement = pawn.get_component_by_class(u.CharacterMovementComponent)
            snap["movement_class"] = object_class(movement)
            if movement:
                snap["falling"] = bool(movement.is_falling())
                snap["on_ground"] = bool(movement.is_moving_on_ground())
                checks["grounded_start"] = (snap["on_ground"] and not snap["falling"]
                    and snap["distance_from_start_xy_cm"] < 400 and abs(position[2] - 300) < 600)
        checks["runtime_services_settled"] = time.monotonic() - self.native_ready_since >= 2 and time.monotonic() - self.first_pie >= 5
        if not checks["runtime_services_settled"]:
            self.result.update(checks=checks, snapshot=snap,
                               passed=sum(bool(value) for value in checks.values()), total=len(checks))
            return False
        query = u.DbGateway.db_query("SELECT * FROM DungeonEntrances WHERE DungeonName='Basketbroom_DungeonMap'")
        runtime_rows = [{str(pair.key): str(pair.value) for pair in row.fields}
                        for row in query.result_rows] if query is not None and query.success else []
        snap["runtime_entrance_rows"] = runtime_rows
        checks["runtime_registered_row"] = False
        if len(runtime_rows) == 1:
            try:
                self.registrar.verify_row(runtime_rows[0], self.registrar.POSITION)
                checks["runtime_registered_row"] = True
            except (RuntimeError, KeyError, ValueError):
                pass
        registry = u.UGCBlueprintLibrary.get_ugc_registry(world)
        snap["ugc_registry"] = object_class(registry)
        checks["runtime_ugc_registry"] = registry is not None
        snap["composite_tables"] = {}
        for label, base_path in (("dungeon", self.stage.BASE_DUNGEONS), ("subdivision", self.stage.BASE_SUBDIVISIONS)):
            item = {"base": base_path, "has_owned_row": False}
            base = u.load_asset(base_path)
            table = registry.get_mod_table_for_base_table(base) if registry and base else None
            item["resolved"] = table.get_path_name() if table else None
            if table:
                names = [str(name) for name in u.DataTableFunctionLibrary.get_data_table_row_names(table)]
                item["has_owned_row"] = self.stage.ROW_NAME in names
                item["row_count"] = len(names)
            checks["runtime_" + label + "_extension"] = item["has_owned_row"]
            snap["composite_tables"][label] = item
        actors = u.GameplayStatics.get_all_actors_of_class(world, u.Actor)
        exits = [actor for actor in actors if actor.actor_has_tag(self.anchors.EXIT_TAG)]
        checks["native_owned_exit"] = len(exits) == 1 and object_class(exits[0]) == "/Basketbroom/Blueprints/BP_Basketbroom_DungeonExit.BP_Basketbroom_DungeonExit_C"
        checks["exit_interaction_components"] = False
        checks["exit_first_return_defaults"] = False
        if len(exits) == 1:
            exit_actor = exits[0]
            snap["exit"] = self.anchors.actor_record(exit_actor)
            values = {name: exit_actor.get_editor_property(name) for name in self.anchors.EXIT_DEFAULTS}
            snap["exit"]["defaults"] = values
            checks["exit_first_return_defaults"] = values == self.anchors.EXIT_DEFAULTS
            components = exit_actor.get_components_by_class(u.ActorComponent)
            sphere_records = []
            for component in components:
                if isinstance(component, u.SphereComponent):
                    sphere_records.append({"name": component.get_name(), "radius": float(component.get_scaled_sphere_radius()),
                        "collision": str(component.get_collision_enabled()), "overlap_events": bool(component.get_editor_property("generate_overlap_events"))})
            snap["exit"]["spheres"] = sphere_records
            cognition = [object_class(component) for component in components if "CognitionStimuliSource" in object_class(component)]
            snap["exit"]["cognition_components"] = cognition
            checks["exit_interaction_components"] = len(sphere_records) == 2 and len(cognition) == 1 and any(
                sphere["radius"] > 0 and sphere["overlap_events"] and "NO_COLLISION" not in sphere["collision"] for sphere in sphere_records)
            snap["exit"]["loading_to_level"] = str(exit_actor.get_editor_property("LoadingToLevel"))
        self.result["checks"] = checks
        self.result["snapshot"] = snap
        self.result["passed"] = sum(bool(value) for value in checks.values())
        self.result["total"] = len(checks)
        return all(checks.values())

    def stop(self, failure=None):
        if failure:
            self.result["failure"] = failure
        self.result["status"] = "ending_owned_pie"
        if self.stop_time is None:
            self.stop_time = time.monotonic()
        try:
            self.write()
        finally:
            worlds = self.u.EditorLevelLibrary.get_pie_worlds(True)
            if (self.owns_session and len(worlds) == 1 and is_owned_pie(worlds[0])
                    and not self.result.get("end_play_requested")):
                self.result["end_play_requested"] = True
                self.u.EditorLevelLibrary.editor_end_play()

    def finish(self):
        try:
            if self.u.EditorLevelLibrary.get_pie_worlds(True):
                raise RuntimeError("PIE cleanup did not finish; session is still present")
            if canonical(self.u.EditorLevelLibrary.get_editor_world()) != WORLD:
                raise RuntimeError("Editor did not return to the exact owned dungeon")
            self.result["dirty_after"] = self.guard.require_clean(self.u)
            content_after = self.registrar.hashes(self.registrar.CONTENT, self.stage.digest)
            self.result["content_unchanged"] = content_after == self.content_before
            protected_after = {}
            immutable_names = []
            for name in self.protected_before:
                if Path(name).resolve() == DYNAMIC_DATABASE.resolve():
                    # Phoenix InitializeManager refreshes this native runtime
                    # cache. A hash delta is evidence, not a gameplay failure.
                    try:
                        after = self.stage.digest(Path(name))
                        protected_after[name] = after
                        self.result["dynamic_database"] = {
                            "status": "hash_observed", "path": name,
                            "before_sha256": self.protected_before[name], "after_sha256": after,
                            "changed": after != self.protected_before[name],
                            "logical_delta_verified": False}
                    except OSError:
                        protected_after[name] = None
                        self.result["dynamic_database"] = {
                            "status": "postclose_inspection_required", "path": name,
                            "before_sha256": self.protected_before[name],
                            "changed": None, "logical_delta_verified": False}
                else:
                    immutable_names.append(name)
                    protected_after[name] = self.stage.digest(Path(name))
            self.result["protected_hashes_after"] = protected_after
            self.result["immutable_protected_files"] = immutable_names
            self.result["protected_files_unchanged"] = all(
                protected_after[name] == self.protected_before[name] for name in immutable_names)
            self.result["installed_maps_unchanged"] = self.registrar.metadata(self.registrar.KIT_CONTENT, ".umap") == self.installed_before
            if not all(self.result[name] for name in ("content_unchanged", "protected_files_unchanged", "installed_maps_unchanged")):
                raise RuntimeError("A protected file changed during PIE")
            self.result["status"] = "failed" if self.result.get("failure") else "passed"
        except Exception:
            self.result["status"] = "failed"
            self.result["cleanup_error"] = traceback.format_exc()
        self.result["finished_utc"] = datetime.now(timezone.utc).isoformat()
        try:
            self.write()
        finally:
            try:
                if self.handle is not None:
                    self.u.unregister_slate_post_tick_callback(self.handle)
                    self.handle = None
            finally:
                if getattr(self.u, STATE_NAME, None) is self:
                    delattr(self.u, STATE_NAME)

    def tick(self, unused_delta):
        now = time.monotonic()
        if now - self.last_poll < 0.5:
            return
        self.last_poll = now
        try:
            worlds = self.u.EditorLevelLibrary.get_pie_worlds(True)
            if self.stop_time is not None:
                if not worlds or now - self.stop_time > 30:
                    self.finish()
                return
            if self.first_pie is None:
                # UE4.27 can return no editor world during real Play. Claim the
                # exact observed PIE world before asking for the editor world,
                # so any subsequent fixture error still cleans up our session.
                if worlds:
                    if len(worlds) != 1 or not is_owned_pie(worlds[0]):
                        self.result["failure_stage"] = "startup_world_guard"
                        self.stop("An unexpected Play world appeared; this observer does not own it")
                        return
                    self.owns_session = True
                    self.first_pie = now
                    self.result["status"] = "observing_native_runtime"
                    self.result["pie_started_utc"] = datetime.now(timezone.utc).isoformat()
                    self.write()
                else:
                    editor_world = self.u.EditorLevelLibrary.get_editor_world()
                    if editor_world is not None and canonical(editor_world) != WORLD:
                        self.result["failure_stage"] = "startup_world_guard"
                        self.stop("The editor world changed before our PIE session started")
                    elif now - self.started > 600:
                        self.result["failure_stage"] = "startup_timeout"
                        self.stop("Startup timeout: no owned Play world became observable within ten minutes")
                return
            if len(worlds) != 1 or not is_owned_pie(worlds[0]):
                self.stop("PIE ended or changed to an unexpected world; no travel was requested")
                return
            ready = self.snapshot(worlds[0])
            self.write()
            if ready and now - self.first_pie >= 5:
                if self.stable_since is None:
                    self.stable_since = now
                elif now - self.stable_since >= 2:
                    self.stop()
            else:
                self.stable_since = None
            if now - self.first_pie > 180:
                self.stop("Native runtime readiness did not pass within three minutes")
        except Exception:
            self.result["failure_stage"] = "observer_fixture"
            self.stop(traceback.format_exc())


def arm(replace_waiting=False):
    import unreal
    existing = getattr(unreal, STATE_NAME, None)
    if existing is not None:
        if (replace_waiting is not True or existing.result.get("status") != "awaiting_actual_play"
                or unreal.EditorLevelLibrary.get_pie_worlds(True)
                or canonical(unreal.EditorLevelLibrary.get_editor_world()) != WORLD):
            raise RuntimeError("A dungeon PIE observer is already active")
        unreal.unregister_slate_post_tick_callback(existing.handle)
        existing.handle = None
        delattr(unreal, STATE_NAME)
    smoke = Smoke(unreal)
    try:
        smoke.preflight()
        setattr(unreal, STATE_NAME, smoke)
        smoke.handle = unreal.register_slate_post_tick_callback(smoke.tick)
        return {"status": "awaiting_actual_play", "report": str(REPORT), "world": WORLD}
    except Exception:
        smoke.result["status"] = "failed"
        smoke.result["error"] = traceback.format_exc()
        try:
            smoke.write()
        finally:
            if smoke.handle is not None:
                unreal.unregister_slate_post_tick_callback(smoke.handle)
            if getattr(unreal, STATE_NAME, None) is smoke:
                delattr(unreal, STATE_NAME)
        return {"status": "failed", "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = arm(replace_waiting=globals().get("BRIDGE_ARGS", {}).get("replace_waiting", False))

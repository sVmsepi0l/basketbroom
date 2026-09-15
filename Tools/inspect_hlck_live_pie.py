"""Observe an already-running owned native dungeon without changing its session.

Bridge: inspect_hlck_live_pie.py {}. This records current runtime readiness only,
not startup time, pre-Play preservation, successful travel, or a full match.
The existing native snapshot is reused; its lifecycle methods are never called.
No input, travel, save, registration, start or end-Play operation is performed.
Sixteen native checks plus a separate advancing-world-clock check are recorded.
The Slate callback stops observing after a bounded 30 seconds; a blocked engine
thread can delay callback execution beyond that wall-clock deadline.
"""
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/dungeon-live-pie-observation.json"
PROJECT = Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject")
STATE_NAME = "_basketbroom_hlck_live_pie_observer"
SMOKE_STATE_NAME = "_basketbroom_hlck_dungeon_pie_smoke"
MAX_SECONDS = 30.0
CHECK_NAMES = (
    "owned_pie_world", "native_game_mode", "native_game_instance",
    "native_character", "native_player_blueprint", "native_controller_blueprint",
    "possessed_local_player", "grounded_start", "runtime_services_settled",
    "runtime_registered_row", "runtime_ugc_registry", "runtime_dungeon_extension",
    "runtime_subdivision_extension", "native_owned_exit",
    "exit_interaction_components", "exit_first_return_defaults",
)


def utc():
    return datetime.now(timezone.utc).isoformat()


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def write_report(report, result):
    """Atomic complete JSON with bounded retries for brief Windows reader locks."""
    report.parent.mkdir(parents=True, exist_ok=True)
    temporary = report.with_name(report.name + "." + uuid.uuid4().hex + ".next")
    try:
        temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        for attempt in range(8):
            try:
                temporary.replace(report)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.025)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def snapshot_reader(unreal):
    """Create only the state consumed by Smoke.snapshot, without its lifecycle."""
    source = module("_bb_live_pie_snapshot", "Tools/test_hlck_dungeon_pie.py")
    reader = source.Smoke.__new__(source.Smoke)
    reader.u = unreal
    reader.stage = module("_bb_live_pie_stage_constants", "Tools/stage_hlck_dungeon.py")
    reader.registrar = module("_bb_live_pie_registration_check", "Tools/register_hlck_dungeon.py")
    reader.anchors = module("_bb_live_pie_anchor_readers", "Tools/stage_hlck_dungeon_anchors.py")
    reader.first_pie = None
    reader.native_ready_since = None
    reader.result = {"checks": {}}
    return source, reader


class Observation:
    def __init__(self, report):
        self.report = report
        self.u = self.source = self.reader = self.world = None
        self.handle = None
        self.done = False
        self.started = self.stable_since = self.first_world_time = None
        self.last_poll = None
        self.result = {
            "attempt_id": uuid.uuid4().hex, "process_id": os.getpid(),
            "started_utc": utc(), "first_observed_utc": None,
            "last_observed_utc": None, "completed_utc": None,
            "status": "pending", "error": None, "read_only": True,
            "scope": "already running session observation; no pre-Play preservation/startup proof",
            "pre_play_preservation_verified": False, "startup_verified": False,
            "session_start_time_known": False,
            "play_started": False, "play_stopped": False, "input_injected": False,
            "travel_invoked": False, "assets_saved": False, "registration_invoked": False,
            "runtime_database_query_scope": "read-only SELECT by existing native snapshot",
            "observation_timeout_seconds": MAX_SECONDS,
            "callback_registered": False, "project": None, "engine": None,
            "active_mod": None, "has_active_editor_mod": None, "pie_worlds": None,
            "dirty_maps": None, "dirty_content": None,
            "runtime_checks": "NOT_RUN", "checks": {name: None for name in CHECK_NAMES + ("world_time_advanced",)},
            "passed": 0, "total": len(CHECK_NAMES) + 1, "observed_check_count": 0,
            "native_runtime_passed": 0, "native_runtime_total": len(CHECK_NAMES),
            "callback_count": 0, "world_time_samples": [], "world_elapsed_seconds": 0.0,
            "elapsed_observation_seconds": 0.0, "all_checks_stable_seconds": 0.0,
            "native_services_observed_seconds": 0.0,
            "runtime_ready": False,
        }

    def guard(self):
        u = self.u
        project = Path(u.Paths.convert_relative_path_to_full(u.Paths.get_project_file_path())).resolve()
        self.result["project"] = str(project)
        if project != PROJECT.resolve():
            raise RuntimeError("Expected the exact installed Phoenix project")
        self.result["engine"] = str(u.SystemLibrary.get_engine_version())
        if not self.result["engine"].startswith("4.27."):
            raise RuntimeError("Expected the native Creator Kit UE4.27 engine")
        self.result["has_active_editor_mod"] = bool(u.GameModManagerSubsystem.has_active_editor_mod_bp())
        if not self.result["has_active_editor_mod"]:
            raise RuntimeError("Expected an active editor mod, not only a selected dungeon map")
        self.result["active_mod"] = str(u.GameModManagerSubsystem.get_active_mod_name_bp())
        if self.result["active_mod"] != "Basketbroom":
            raise RuntimeError("Expected the active Basketbroom mod")
        if getattr(u, SMOKE_STATE_NAME, None) is not None:
            raise RuntimeError("An existing dungeon smoke observer is active")
        existing = getattr(u, STATE_NAME, None)
        if existing is not None and existing is not self:
            raise RuntimeError("An existing live PIE observation is active")
        worlds = list(u.EditorLevelLibrary.get_pie_worlds(True))
        self.result["pie_worlds"] = [world.get_path_name() for world in worlds]
        if len(worlds) != 1 or not self.source.is_owned_pie(worlds[0]):
            raise RuntimeError("Expected exactly one already-running owned dungeon PIE world")
        if self.world is not None and worlds[0] != self.world:
            raise RuntimeError("The observed PIE session changed")
        self.result["dirty_maps"] = [p.get_path_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
        self.result["dirty_content"] = [p.get_path_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        if self.result["dirty_maps"] or self.result["dirty_content"]:
            raise RuntimeError("Dirty packages exist; observation requires clean saved work")
        return worlds[0]

    def sample_world_time(self, world):
        getter = getattr(self.u.GameplayStatics, "get_time_seconds", None)
        if not callable(getter):
            raise RuntimeError("Public world clock query is unavailable; responsiveness is unverified")
        seconds = float(getter(world))
        if not math.isfinite(seconds):
            raise RuntimeError("World clock query returned a non-finite time")
        if self.first_world_time is None:
            self.first_world_time = seconds
        elapsed = seconds - self.first_world_time
        if elapsed < -0.001:
            raise RuntimeError("World clock moved backwards; the observed session may have changed")
        self.result["world_elapsed_seconds"] = max(0.0, elapsed)
        self.result["world_time_samples"].append({"observed_utc": utc(),
            "world_time_seconds": seconds,
            "observation_elapsed_seconds": max(0.0, time.monotonic() - self.started)})
        return elapsed >= 1.0

    def complete(self, error=None):
        if self.done:
            return
        self.done = True
        cleanup_error = None
        try:
            if self.handle is not None:
                self.u.unregister_slate_post_tick_callback(self.handle)
                self.handle = None
                self.result["callback_registered"] = False
        except Exception as exc:
            cleanup_error = "Could not unregister observation callback: " + str(exc)
        finally:
            # Retain our state on unregister failure so a second observer cannot
            # be armed while the existing callback remains registered.
            if self.u is not None and self.handle is None and getattr(self.u, STATE_NAME, None) is self:
                delattr(self.u, STATE_NAME)
        self.result["error"] = "; ".join(str(item) for item in (error, cleanup_error) if item) or None
        self.result["runtime_ready"] = self.result["error"] is None
        self.result["status"] = "passed" if self.result["runtime_ready"] else "failed"
        self.result["completed_utc"] = utc()
        write_report(self.report, self.result)

    def tick(self, unused_delta):
        if self.done:
            return
        self.result["callback_count"] += 1
        now = time.monotonic()
        if self.last_poll is not None and now - self.last_poll < 0.5:
            return
        self.last_poll = now
        try:
            self.result["elapsed_observation_seconds"] = max(0.0, now - self.started)
            if now - self.started >= MAX_SECONDS:
                failed = [name for name, value in self.result["checks"].items() if value is not True]
                reason = "Current native runtime did not pass within 30 seconds of observation; unresolved: " + ", ".join(failed)
                if self.result["world_elapsed_seconds"] < 1.0:
                    reason += "; world clock did not advance by 1 second (paused or stalled session)"
                raise RuntimeError(reason)
            world = self.guard()
            # This is the sole method called on the original smoke class.
            ready = self.source.Smoke.snapshot(self.reader, world)
            observed = self.reader.result.get("checks", {})
            if set(observed) - set(CHECK_NAMES):
                raise RuntimeError("The reused native snapshot check contract changed")
            checks = {name: observed.get(name) for name in CHECK_NAMES}
            native_passed = sum(value is True for value in checks.values())
            checks["world_time_advanced"] = self.sample_world_time(world)
            now = time.monotonic()
            self.result["elapsed_observation_seconds"] = max(0.0, now - self.started)
            if now - self.started >= MAX_SECONDS:
                raise RuntimeError("Native snapshot exceeded the 30-second observation deadline")
            self.result.update(checks=checks, snapshot=self.reader.result.get("snapshot"),
                runtime_checks=self.reader.result.get("runtime_checks", "NOT_RUN"),
                passed=sum(value is True for value in checks.values()), native_runtime_passed=native_passed,
                observed_check_count=sum(value is not None for value in checks.values()),
                last_observed_utc=utc())
            services_since = self.reader.native_ready_since
            self.result["native_services_observed_seconds"] = max(0.0, now - services_since) if services_since is not None else 0.0
            ready = (ready and all(value is True for value in checks.values())
                     and now - self.started >= 5.0
                     and self.result["native_services_observed_seconds"] >= 2.0)
            self.stable_since = (now if self.stable_since is None else self.stable_since) if ready else None
            stable = now - self.stable_since if self.stable_since is not None else 0.0
            self.result["all_checks_stable_seconds"] = stable
            passed = ready and stable >= 2.0
            if not passed:
                write_report(self.report, self.result)
        except Exception as exc:
            self.complete(type(exc).__name__ + ": " + str(exc))
            return
        if passed:
            self.complete()


def run(unreal_module=None, report_path=None):
    report = Path(report_path) if report_path is not None else REPORT
    protected = ROOT / ".local/hlck"
    resolved = report.resolve()
    if (resolved == (protected / "dungeon-pie-smoke.json").resolve()
            or (protected / "pie-success").resolve() in resolved.parents
            or resolved == (protected / "native-play-success.json").resolve()):
        raise ValueError("Refusing to overwrite historical native Play evidence")
    observer = Observation(report)
    # Publish a fresh non-success before imports, engine getters, or callbacks.
    # If publication itself fails, no engine operation takes place.
    write_report(report, observer.result)
    try:
        if unreal_module is None:
            import unreal as unreal_module
        observer.u = unreal_module
        observer.source, observer.reader = snapshot_reader(unreal_module)
        observer.world = observer.guard()
        observer.started = time.monotonic()
        # The underlying snapshot's first_pie is our first real observation,
        # never a guessed or backdated native Play start time.
        observer.reader.first_pie = observer.started
        observer.result.update(status="observing", first_observed_utc=utc())
        observer.sample_world_time(observer.world)
        setattr(unreal_module, STATE_NAME, observer)
        observer.handle = unreal_module.register_slate_post_tick_callback(observer.tick)
        if observer.handle is None:
            raise RuntimeError("Slate callback registration returned no handle")
        observer.result["callback_registered"] = True
        write_report(report, observer.result)
    except Exception as exc:
        observer.complete(type(exc).__name__ + ": " + str(exc))
    return {"status": observer.result["status"], "attempt_id": observer.result["attempt_id"],
            "process_id": observer.result["process_id"], "report": str(report),
            "error": observer.result["error"], "scope": observer.result["scope"]}


if __name__ == "__main__":
    RESULT = run()

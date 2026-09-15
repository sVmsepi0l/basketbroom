"""Observe one clean native map reload immediately and after ordinary ticks.

Bridge args: {"map": "/Basketbroom/Maps/BB_Arena_Port"} (default shown).
Only an existing owned arena/dungeon can be loaded. No actor/property edits,
imports, saves, registration, database queries or PIE are performed. The selected
map stays open for inspection. Snapshots cover nonroof actors without a class
whitelist; changes are evidence, not permission to ignore preservation failures.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
STATE_NAME = "_basketbroom_hlck_map_reload_observer"
MAPS = ("/Basketbroom/Maps/BB_Arena_Port", "/Basketbroom/Maps/Basketbroom_DungeonMap")
THRESHOLDS = (0.5, 2.0, 5.0)


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def actor_delta(before, after):
    return {"added": {key: after[key] for key in sorted(set(after) - set(before))},
            "removed": {key: before[key] for key in sorted(set(before) - set(after))},
            "changed": {key: {"before": before[key], "after": after[key]}
                        for key in sorted(set(before) & set(after)) if before[key] != after[key]}}


class Observation:
    def __init__(self, unreal, map_path):
        if map_path not in MAPS:
            raise ValueError("Only an existing native Basketbroom arena/dungeon map may be observed")
        self.u, self.map = unreal, map_path
        self.roof = module("_bb_reload_roof_definitions", "Tools/stage_hlck_pyramid_net.py")
        self.guard = module("_bb_reload_guard", "Tools/load_hlck_dungeon.py")
        self.registrar = module("_bb_reload_files", "Tools/register_hlck_dungeon.py")
        self.handle, self.started, self.baseline = None, None, None
        self.pending = list(THRESHOLDS)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid.uuid4().hex[:8]
        self.output = ROOT / ".local/hlck/map-reload-observation" / stamp / "result.json"
        self.result = {"status": "preflight", "read_only": True, "started_utc": datetime.now(timezone.utc).isoformat(),
                       "map": map_path, "map_loaded": False, "map_saved": False, "actors_edited": False,
                       "registration_invoked": False, "database_queried": False, "pie_started": False,
                       "requested_after_reload_seconds": list(THRESHOLDS), "snapshots": []}

    def write(self):
        self.roof.write(self.output, self.result)

    def capture(self, phase, satisfied=()):
        u = self.u
        if u.EditorLevelLibrary.get_pie_worlds(True):
            raise RuntimeError("PIE appeared; stop read-only observation without ending it")
        world, actors = self.roof.validate_map_ownership(u, self.map)
        current = json.loads(json.dumps(self.roof.snapshot(u, actors)))
        dirty = {"map": [p.get_path_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
                 "content": [p.get_path_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}
        if dirty["content"] or any(path != self.map for path in dirty["map"]):
            raise RuntimeError("Unrelated unsaved work appeared; preserve it and stop observation")
        elapsed = time.monotonic() - self.started
        entry = {"phase": phase, "observed_utc": datetime.now(timezone.utc).isoformat(),
                 "elapsed_after_reload_seconds": elapsed, "satisfied_thresholds": list(satisfied),
                 "world": world.get_path_name(), "all_actor_count": len(actors), "nonroof_actor_count": len(current),
                 "dirty_packages": dirty, "actors": current,
                 "map_sha256": self.roof.digest(self.roof.asset_file(self.map, ".umap"))}
        if entry["map_sha256"] != self.result["map_hashes_before"][self.map]:
            raise RuntimeError("The saved map changed during read-only observation")
        if self.baseline is None:
            self.baseline = current
        entry["changes_from_immediate"] = actor_delta(self.baseline, current)
        self.result["snapshots"].append(entry)
        self.write()

    def prepare(self):
        u = self.u
        self.result["active_mod"] = self.guard.require_editor(u)
        self.result["dirty_before"] = self.guard.require_clean(u)
        current = self.roof.world_path(u.EditorLevelLibrary.get_editor_world())
        if current not in MAPS:
            raise RuntimeError("Open a clean owned Basketbroom map before the no-edit reload probe")
        active = Path(u.Paths.convert_relative_path_to_full(str(
            u.GameModManagerSubsystem.get_active_mod_content_path_bp()))).resolve()
        if active != self.roof.CONTENT.resolve():
            raise RuntimeError("The active mod content is not the exact repository")
        self.result["original_map"] = current
        self.content_before = self.registrar.hashes(self.roof.CONTENT, self.roof.digest)
        self.result["map_hashes_before"] = {path: self.roof.digest(self.roof.asset_file(path, ".umap")) for path in MAPS}
        self.result["content_hashes_before"] = self.content_before
        # This is a normal load of a clean saved map. No world/property changes
        # are made after load: native engine initialization is the subject.
        if not u.EditorLevelLibrary.load_level(self.map):
            raise RuntimeError("Could not reload the exact saved owned map")
        self.result["map_loaded"] = True
        self.started = time.monotonic()
        self.result["status"] = "observing"
        self.capture("immediate_after_load")

    def detach(self):
        try:
            if self.handle is not None:
                self.u.unregister_slate_post_tick_callback(self.handle)
                self.handle = None
        finally:
            if getattr(self.u, STATE_NAME, None) is self:
                delattr(self.u, STATE_NAME)

    def finish(self, failure=None):
        try:
            if failure:
                self.result["failure"] = failure
            hashes = {path: self.roof.digest(self.roof.asset_file(path, ".umap")) for path in MAPS}
            self.result["map_hashes_after"] = hashes
            self.result["saved_maps_unchanged"] = hashes == self.result["map_hashes_before"]
            self.result["content_unchanged"] = self.registrar.hashes(self.roof.CONTENT, self.roof.digest) == self.content_before
            if not self.result["saved_maps_unchanged"] or not self.result["content_unchanged"]:
                self.result["failure"] = "A saved mod package changed during observation"
            self.result["status"] = "failed" if self.result.get("failure") else "observed"
        except Exception:
            self.result.update(status="failed", cleanup_error=traceback.format_exc())
        self.result["finished_utc"] = datetime.now(timezone.utc).isoformat()
        try:
            self.write()
        finally:
            self.detach()

    def tick(self, unused_delta):
        try:
            elapsed = time.monotonic() - self.started
            if elapsed > 30:
                self.finish("The editor did not deliver the requested observations within 30 seconds")
                return
            due = [threshold for threshold in self.pending if elapsed >= threshold]
            if due:
                # If a native stall crosses several thresholds, retain one honest
                # timestamped observation instead of inventing intermediate data.
                self.capture("deferred_editor_tick", due)
                self.pending = [threshold for threshold in self.pending if threshold not in due]
            if not self.pending:
                self.finish()
        except Exception:
            self.finish(traceback.format_exc())


def arm(map_path=MAPS[0]):
    import unreal
    if getattr(unreal, STATE_NAME, None) is not None:
        raise RuntimeError("An owned map reload observation is already active")
    observation = Observation(unreal, map_path)
    try:
        observation.prepare()
        setattr(unreal, STATE_NAME, observation)
        observation.handle = unreal.register_slate_post_tick_callback(observation.tick)
    except Exception:
        observation.result.update(status="failed", error=traceback.format_exc())
        try:
            observation.write()
        finally:
            observation.detach()
    return {"status": observation.result["status"], "report": str(observation.output), "map": map_path}


if __name__ == "__main__":
    if "BRIDGE_ARGS" not in globals():
        raise SystemExit("Run only through the existing authenticated Creator Kit bridge")
    RESULT = arm(map_path=BRIDGE_ARGS.get("map", MAPS[0]))

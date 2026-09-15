"""Discard only a diagnosed, unsaved first-map native roof attempt.

Bridge arguments: {"report": "C:/Git/basketbroom/.local/hlck/pyramid-net-stage/<attempt>/result.json"}.
Requires an immutable failed attempt plus its read-only snapshot-diagnostic.json.
No map/package save, import, registration, database write or PIE operation occurs.
The root operator must retain all diagnostics before invoking this helper.
"""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "Mod/Basketbroom/Content"
MAPS = ("/Basketbroom/Maps/BB_Arena_Port", "/Basketbroom/Maps/Basketbroom_DungeonMap")


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def same_json(value):
    # Unreal snapshot component tuples become lists in the retained JSON.
    return json.loads(json.dumps(value))


def expected_snapshot(attempt, diagnostic):
    """Reconstruct the exact diagnosed nonroof state; never whitelist actors."""
    if attempt.get("status") != "failed" or attempt.get("dry_run") is not False:
        raise RuntimeError("Recovery requires a failed authoring attempt, not a dry run or success")
    if attempt.get("original_world") != MAPS[1]:
        raise RuntimeError("Recovery must return to the recorded original dungeon")
    maps = attempt.get("maps", [])
    if [item.get("path") for item in maps] != list(MAPS):
        raise RuntimeError("The failed attempt must identify both exact native maps in stage order")
    for item in maps:
        if ("sha256_after" in item or item.get("saved_reloaded")
                or item.get("unrelated_actors_preserved")):
            raise RuntimeError("A map may already have been saved; unsaved-only recovery is forbidden")
        if not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256_before", "")):
            raise RuntimeError("The attempt lacks an exact pre-edit map hash")
    if (diagnostic.get("read_only") is not True or diagnostic.get("world") != MAPS[0]
            or diagnostic.get("disk_map_unchanged") is not True
            or diagnostic.get("dirty_maps") != [MAPS[0]] or diagnostic.get("dirty_content") != []):
        raise RuntimeError("The retained diagnostic does not identify this sole unsaved first-map attempt")
    expected = same_json(maps[0]["preserved_before"])
    delta_names = ("added", "removed", "changed")
    deltas = {name: diagnostic.get(name) for name in delta_names}
    if any(not isinstance(value, dict) for value in deltas.values()):
        raise RuntimeError("The retained diagnostic must include all three exact actor deltas")
    seen = set()
    for name in delta_names:
        keys = set(deltas[name])
        if seen.intersection(keys):
            raise RuntimeError("The retained actor deltas overlap")
        seen.update(keys)
        if any(not path.startswith(MAPS[0] + ".") for path in keys):
            raise RuntimeError("A retained actor delta is outside the exact first map")
    for path, before in deltas["removed"].items():
        if path not in expected or expected[path] != before:
            raise RuntimeError("Removed actor evidence differs from the failed attempt snapshot")
        del expected[path]
    for path, change in deltas["changed"].items():
        if (not isinstance(change, dict) or set(change) != {"before", "after"}
                or path not in expected or expected[path] != change["before"]):
            raise RuntimeError("Changed actor evidence differs from the failed attempt snapshot")
        expected[path] = change["after"]
    for path, after in deltas["added"].items():
        if path in expected:
            raise RuntimeError("Added actor evidence would replace an existing snapshot")
        expected[path] = after
    return expected


def evidence(report_path, roof):
    if not isinstance(report_path, str) or not report_path:
        raise ValueError("Pass the exact failed attempt result.json path as the report argument")
    path = Path(report_path).resolve()
    base = (ROOT / ".local/hlck/pyramid-net-stage").resolve()
    relative = path.relative_to(base)
    if len(relative.parts) != 2 or relative.name != "result.json":
        raise RuntimeError("Only an immediate native roof attempt result.json is accepted")
    diagnostic_path = path.parent / "snapshot-diagnostic.json"
    attempt = json.loads(path.read_text(encoding="utf-8-sig"))
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8-sig"))
    expected = expected_snapshot(attempt, diagnostic)
    checks = []
    for item in attempt["maps"]:
        physical = roof.asset_file(item["path"], ".umap")
        expected_backup = (path.parent / "backups" / physical.relative_to(CONTENT.resolve())).resolve()
        backup = Path(item["backup"]).resolve()
        if backup != expected_backup:
            raise RuntimeError("A map backup is outside this attempt's exact mirrored backup path")
        if roof.digest(physical) != item["sha256_before"] or roof.digest(backup) != item["sha256_before"]:
            raise RuntimeError("A saved map or verified backup changed; do not discard the open map")
        checks.append({"map": item["path"], "sha256": item["sha256_before"], "backup": str(backup)})
    return {"path": path, "attempt": attempt, "diagnostic_path": diagnostic_path,
            "expected": expected, "map_checks": checks,
            "attempt_sha256": roof.digest(path), "diagnostic_sha256": roof.digest(diagnostic_path)}


def dirty_state(unreal):
    saving = unreal.EditorLoadingAndSavingUtils
    return {"map": [package.get_path_name() for package in saving.get_dirty_map_packages()],
            "content": [package.get_path_name() for package in saving.get_dirty_content_packages()]}


def run(report=None):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid.uuid4().hex[:8]
    output = ROOT / ".local/hlck/pyramid-net-recovery" / stamp / "result.json"
    result = {"status": "not_run", "started_utc": datetime.now(timezone.utc).isoformat(),
              "source_report": report, "discard_requested": False, "map_saved": False,
              "imports_preserved": False, "registration_invoked": False, "travel_invoked": False,
              "database_write_invoked": False}
    roof = module("_bb_roof_recovery_definitions", "Tools/stage_hlck_pyramid_net.py")
    try:
        import unreal
        guard = module("_bb_roof_recovery_guard", "Tools/load_hlck_dungeon.py")
        registrar = module("_bb_roof_recovery_files", "Tools/register_hlck_dungeon.py")
        result["active_mod"] = guard.require_editor(unreal)
        active = Path(unreal.Paths.convert_relative_path_to_full(str(
            unreal.GameModManagerSubsystem.get_active_mod_content_path_bp()))).resolve()
        if active != CONTENT.resolve():
            raise RuntimeError("Active mod Content differs from the exact repository content")
        proof = evidence(report, roof)
        levels = unreal.EditorLevelLibrary
        if roof.world_path(levels.get_editor_world()) != MAPS[0]:
            raise RuntimeError("Only the diagnosed unsaved first arena map may be discarded")
        state = dirty_state(unreal)
        if state != {"map": [MAPS[0]], "content": []}:
            raise RuntimeError("Expected only the diagnosed arena to be dirty; preserve other work")
        world, actors = roof.validate_map_ownership(unreal, MAPS[0])
        observed = same_json(roof.snapshot(unreal, actors))
        if observed != proof["expected"]:
            differences = sorted(path for path in set(observed) | set(proof["expected"])
                                 if observed.get(path) != proof["expected"].get(path))
            result["unexpected_actor_paths"] = differences
            raise RuntimeError("Nonroof actors drifted after the retained diagnostic; do not discard")
        content_before = registrar.hashes(CONTENT, roof.digest)
        installed_before = registrar.metadata(registrar.KIT_CONTENT, ".umap")
        database_before = {str(path): roof.digest(path) for path in (registrar.KIT_CONTENT / "SQLiteDB").glob("*.sqlite")}
        result.update(source_report=str(proof["path"]), source_report_sha256=proof["attempt_sha256"],
                      diagnostic=str(proof["diagnostic_path"]), diagnostic_sha256=proof["diagnostic_sha256"],
                      verified_maps=proof["map_checks"], dirty_before=state,
                      diagnosed_nonroof_actor_count=len(observed), content_hashes_before=content_before,
                      installed_map_metadata_before=installed_before, database_hashes_before=database_before)
        # Recheck exact files, evidence and current world after all slow hash reads.
        fresh = evidence(report, roof)
        if (fresh["attempt_sha256"] != proof["attempt_sha256"]
                or fresh["diagnostic_sha256"] != proof["diagnostic_sha256"]
                or roof.world_path(levels.get_editor_world()) != MAPS[0]
                or levels.get_pie_worlds(True) or dirty_state(unreal) != state
                or same_json(roof.snapshot(unreal, list(levels.get_all_level_actors()))) != proof["expected"]):
            raise RuntimeError("Recovery evidence or editor state changed before discard")
        result.update(status="discarding_diagnosed_unsaved_roof", discard_requested=True)
        roof.write(output, result)
        blank = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
        if blank is None:
            raise RuntimeError("The supported discard-to-blank operation did not return a world")
        if not levels.load_level(MAPS[1]) or roof.world_path(levels.get_editor_world()) != MAPS[1]:
            raise RuntimeError("Could not reopen the exact original dungeon after discard")
        guard.require_editor(unreal)
        result["dirty_after"] = guard.require_clean(unreal)
        roof.validate_map_ownership(unreal, MAPS[1])
        # The discarded attempt and its diagnostic remain immutable.
        fresh = evidence(report, roof)
        if (fresh["attempt_sha256"] != proof["attempt_sha256"]
                or fresh["diagnostic_sha256"] != proof["diagnostic_sha256"]):
            raise RuntimeError("The original failed-attempt evidence changed")
        result["content_unchanged"] = registrar.hashes(CONTENT, roof.digest) == content_before
        result["installed_maps_unchanged"] = registrar.metadata(registrar.KIT_CONTENT, ".umap") == installed_before
        database_after = {str(path): roof.digest(path) for path in (registrar.KIT_CONTENT / "SQLiteDB").glob("*.sqlite")}
        result["database_hashes_after"] = database_after
        result["databases_unchanged"] = database_after == database_before
        if not all(result[name] for name in ("content_unchanged", "installed_maps_unchanged", "databases_unchanged")):
            raise RuntimeError("A protected file changed during unsaved-only recovery")
        result.update(status="recovered", imports_preserved=True, original_world_restored=MAPS[1])
    except Exception:
        result.update(status="failed", error=traceback.format_exc(),
                      recovery="Inspect current editor state and this recovery report; no automatic further discard or rollback occurs.")
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    roof.write(output, result)
    return {"status": result["status"], "report": str(output), "discard_requested": result["discard_requested"]}


if __name__ == "__main__":
    if "BRIDGE_ARGS" not in globals():
        raise SystemExit("Run only through the existing authenticated Creator Kit bridge with the exact report argument")
    RESULT = run(report=BRIDGE_ARGS.get("report"))

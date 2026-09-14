"""Read-only checks of the already-open dungeon's staged entry and exit."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/dungeon-anchor-inspection.json"


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def inspect():
    result = {"status": "not_run", "read_only": True, "checks": [],
              "inspected_utc": datetime.now(timezone.utc).isoformat(),
              "registration_invoked": False, "travel_verified": False}
    try:
        import unreal
        guard = module("_bb_anchor_inspect_guard", "Tools/load_hlck_dungeon.py")
        stage = module("_bb_anchor_inspect_stage", "Tools/stage_hlck_dungeon.py")
        anchors = module("_bb_anchor_inspect_definitions", "Tools/stage_hlck_dungeon_anchors.py")
        result["active_mod"] = guard.require_editor(unreal)
        result["dirty_before"] = guard.require_clean(unreal)
        world = unreal.EditorLevelLibrary.get_editor_world()
        if stage.world_path(world) != stage.TARGET_MAP:
            raise RuntimeError("Open the staged dungeon first; this inspection changes no world")
        previous = module("_bb_anchor_inspect_prerequisites", "Tools/inspect_hlck_dungeon.py").inspect()
        if previous.get("status") != "passed":
            raise RuntimeError("The existing dungeon checks failed")
        result["checks"].extend(json.loads((ROOT / ".local/hlck/dungeon-inspection.json").read_text(encoding="utf-8"))["checks"])

        def check(name, passed, detail):
            result["checks"].append({"name": name, "passed": bool(passed), "detail": detail})

        actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
        starts = [actor for actor in actors if isinstance(actor, unreal.PlayerStart)]
        entry_tags = [actor for actor in actors if actor.actor_has_tag(anchors.ENTRY_TAG)]
        check("one_owned_first_entry_spawn", len(starts) == 1 and starts == entry_tags
              and starts[0].actor_has_tag("BB.Spawn"), [anchors.actor_record(actor) for actor in starts])
        check("first_entry_retains_ordinary_spawn", len(starts) == 1
              and str(starts[0].get_editor_property("player_start_tag")) in ("", "None")
              and anchors.xyz(starts[0].get_actor_location()) == [-3000.0, 0.0, 300.0],
              "No second-entrance _EXIT tag; ordinary first-entry travel options are empty")
        exit_path = stage.DESTINATIONS[stage.SOURCE_EXIT]
        exit_class = unreal.EditorAssetLibrary.load_blueprint_class(exit_path)
        exits = [actor for actor in actors if actor.get_class() == exit_class]
        exit_tags = [actor for actor in actors if actor.actor_has_tag(anchors.EXIT_TAG)]
        check("one_owned_native_exit", len(exits) == 1 and exits == exit_tags,
              [anchors.actor_record(actor) for actor in exits])
        if len(exits) != 1:
            raise RuntimeError("Cannot inspect native exit fields without exactly one owned exit")
        exit_actor = exits[0]
        values = {key: exit_actor.get_editor_property(key) for key in anchors.EXIT_DEFAULTS}
        check("native_first_exit_defaults", values == anchors.EXIT_DEFAULTS
              and anchors.xyz(exit_actor.get_actor_location()) == list(anchors.EXIT_LOCATION), values)
        components = list(exit_actor.get_components_by_class(unreal.ActorComponent))
        classes = [component.get_class().get_path_name() for component in components]
        check("native_exit_interaction_components", sum(isinstance(component, unreal.SphereComponent) for component in components) >= 2
              and any("CognitionStimuliSource" in path for path in classes)
              and not exit_actor.get_editor_property("is_editor_only_actor"), classes)
        check("no_outside_entrance_misplaced_in_dungeon",
              not any(isinstance(actor, unreal.DungeonEntrancePlacement) for actor in actors),
              "The external entrance belongs in a selected Overland sublevel, not inside the dungeon")
        report = json.loads((ROOT / ".local/hlck/dungeon-anchor-result.json").read_text(encoding="utf-8"))
        current_hash = stage.digest(stage.checked_file(stage.TARGET_MAP, ".umap"))
        amendment = None
        if report.get("status") == "staged" and report.get("map_sha256_after") != current_hash:
            amendment = module("_bb_anchor_roof_amendment", "Tools/stage_hlck_pyramid_net.py").verified_amendment(
                stage.TARGET_MAP, report["map_sha256_after"])
        check("saved_dungeon_matches_anchor_receipt_or_verified_roof_amendment", report.get("status") == "staged"
              and (report.get("map_sha256_after") == current_hash or amendment is not None),
              {"current_sha256": current_hash, "roof_amendment": amendment})
        result["dirty_after"] = guard.require_clean(unreal)
        result["world"] = stage.TARGET_MAP
        result["passed"] = sum(item["passed"] for item in result["checks"])
        result["failed"] = len(result["checks"]) - result["passed"]
        result["status"] = "passed" if not result["failed"] else "failed"
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "passed": result.get("passed"), "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = inspect()

"""Read-only collision checks near the inspected Hogwarts Quidditch east gate."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/hlck/entrance-collision.json"


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def surface_height(unreal, world, x, y):
    """Bracket the first Pawn collision using the public trace hit/None contract.

    This kit deliberately does not expose HitResult's point/normal fields.
    Twenty-four bisections give <0.001 cm brackets. World-coordinate float32
    rounding at this location is about 0.008 cm, which dominates precision.
    """
    def hit_to(z):
        return unreal.SystemLibrary.line_trace_single_by_profile(
            world, unreal.Vector(x, y, -83500), unreal.Vector(x, y, z),
            "Pawn", True, [], unreal.DrawDebugTrace.NONE, True) is not None
    low, high = -90000.0, -83500.0
    if not hit_to(low) or hit_to(high - 0.01):
        return None
    for unused in range(24):
        middle = (low + high) / 2.0
        if hit_to(middle):
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def run():
    result = {"status": "not_run", "read_only": True, "registration_invoked": False,
              "started_utc": datetime.now(timezone.utc).isoformat(), "samples": []}
    try:
        import unreal
        guard = module("_bb_collision_guard", "Tools/load_hlck_dungeon.py")
        stage = module("_bb_collision_stage", "Tools/stage_hlck_dungeon.py")
        guard.require_editor(unreal)
        result["dirty_before"] = guard.require_clean(unreal)
        world = unreal.EditorLevelLibrary.get_editor_world()
        expected = "/Game/Levels/Overland/HOG/HN_AZ"
        if stage.world_path(world) != expected:
            raise RuntimeError("Open the inspected HN_AZ grounds first; this probe loads no maps")
        result["world"] = expected
        result["measurement"] = "24-step vertical collision bisection; neighbouring samples estimate local slope"
        result["bisection_interval_cm"] = 6500.0 / (2 ** 24)
        result["world_coordinate_rounding_cm"] = 0.008
        result["collision_profile"] = "Pawn"
        for x in (328900.0, 329400.0, 329900.0):
            for y in (-467300.0, -466800.0, -466300.0):
                item = {"xy": [x, y]}
                z = surface_height(unreal, world, x, y)
                item["hit"] = z is not None
                if z is not None:
                    item["surface_point"] = [x, y, z]
                    adjacent = [surface_height(unreal, world, x + dx, y + dy)
                                for dx, dy in ((60, 0), (-60, 0), (0, 60), (0, -60))]
                    item["adjacent_heights"] = adjacent
                    item["flat_within_20cm"] = all(value is not None and abs(value-z) < 20 for value in adjacent)
                    center = unreal.Vector(x, y, z + 135)
                    blocked = unreal.SystemLibrary.capsule_trace_single_by_profile(world, center,
                        unreal.Vector(center.x, center.y, center.z + 1), 60.0, 110.0,
                        "Pawn", False, [], unreal.DrawDebugTrace.NONE, True)
                    item["pawn_capsule_clear"] = blocked is None
                    item["spawn_center"] = [center.x, center.y, center.z]
                    item["usable"] = item["flat_within_20cm"] and item["pawn_capsule_clear"]
                result["samples"].append(item)
        result["dirty_after"] = guard.require_clean(unreal)
        result["status"] = "inspected"
    except Exception:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = run()

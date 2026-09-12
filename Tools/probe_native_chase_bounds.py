"""Read-only chase-wing import/attachment diagnostic in native BB_Regulation PIE.

Bridge invocation needs no arguments. Reports source OBJ and imported signed
bounds plus live component transforms; never changes an actor, asset, or setting.
GetBoundingBox, GetLocalBounds, GetWorldTransform/Scale/Rotation and
SystemLibrary.GetComponentBounds are reflected in the installed UE5.8 headers.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import traceback
import unreal

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/native-chase-bounds.json"
MOUNT = "/Basketbroom/Art/Equipment/"


def prop(obj, name):
    names = [name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()]
    if name.startswith("b") and len(name) > 1 and name[1].isupper():
        names.append(re.sub(r"(?<!^)(?=[A-Z])", "_", name[1:]).lower())
    for alias in names:
        try:
            return obj.get_editor_property(alias)
        except Exception:
            pass
    raise RuntimeError("Missing reflected diagnostic property: " + name)


def xyz(value):
    return [round(float(value.x), 6), round(float(value.y), 6), round(float(value.z), 6)]


def rot(value):
    return [round(float(value.pitch), 6), round(float(value.yaw), 6), round(float(value.roll), 6)]


def bounds(low, high):
    return {"min": low, "max": high, "size": [round(high[i] - low[i], 6) for i in range(3)]}


def asset_row(name):
    points = [list(map(float, line.split()[1:4]))
              for line in (ROOT / "SourceArt/Equipment" / (name + ".obj")).read_text().splitlines()
              if line.startswith("v ")]
    source = bounds([min(p[i] for p in points) for i in range(3)],
                    [max(p[i] for p in points) for i in range(3)])
    mesh = unreal.load_asset(MOUNT + name)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("Missing imported mesh: " + name)
    box = mesh.get_bounding_box()
    imported = bounds(xyz(prop(box, "Min")), xyz(prop(box, "Max")))
    same_error = max(abs(source[key][i] - imported[key][i]) for key in ("min", "max") for i in range(3))
    reflected = {"min": [source["min"][0], -source["max"][1], source["min"][2]],
                 "max": [source["max"][0], -source["min"][1], source["max"][2]]}
    y_flip_error = max(abs(reflected[key][i] - imported[key][i]) for key in ("min", "max") for i in range(3))
    return {"mesh": mesh.get_path_name(), "source_obj_cm": source, "imported_asset_cm": imported,
            "unchanged_bounds_max_error_cm": same_error, "y_reflected_bounds_max_error_cm": y_flip_error,
            "interpretation": "unchanged signed bounds" if same_error < .01 else
                              "Y reflected during import" if y_flip_error < .01 else "other import transform; inspect bounds"}


def component_row(component):
    mesh = prop(component, "StaticMesh")
    low, high = component.get_local_bounds()
    origin, extent, radius = unreal.SystemLibrary.get_component_bounds(component)
    parent = component.get_attach_parent()
    return {"component": component.get_name(), "mesh": mesh.get_path_name() if mesh else None,
            "parent": parent.get_name() if parent else None,
            "relative_location_cm": xyz(prop(component, "RelativeLocation")),
            "relative_rotation_pitch_yaw_roll": rot(prop(component, "RelativeRotation")),
            "relative_scale": xyz(prop(component, "RelativeScale3D")),
            "absolute_scale": bool(prop(component, "bAbsoluteScale")),
            "world_location_cm": xyz(component.get_world_location()),
            "world_rotation_pitch_yaw_roll": rot(component.get_world_rotation()),
            "world_scale": xyz(component.get_world_scale()),
            "local_bounds_cm": bounds(xyz(low), xyz(high)),
            "world_bounds": {"origin_cm": xyz(origin), "extent_cm": xyz(extent), "sphere_radius_cm": radius},
            "collision_profile": str(component.get_collision_profile_name()),
            "collision_enabled": str(component.get_collision_enabled()), "visible": bool(component.is_visible())}


def inspect():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if (not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
            or world is None or not re.fullmatch(r"/Basketbroom/Maps/UEDPIE_\d+_BB_Regulation\.BB_Regulation", world.get_path_name())):
        raise RuntimeError("Start native BB_Regulation PIE before this read-only probe")
    assets = [asset_row("SM_BB_" + kind + "Wing" + side)
              for kind in ("Snipe", "Snitch") for side in ("Left", "Right")]
    ball_class = unreal.load_class(None, "/Script/BasketbroomRuntime.BBBall")
    if ball_class is None:
        raise RuntimeError("Native BBBall class is unavailable")
    balls = []
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, ball_class):
        index = int(prop(actor, "BallIndex"))
        if index not in (3, 4):
            continue
        parts = [part for part in actor.get_components_by_class(unreal.StaticMeshComponent)
                 if part.get_name() in ("BallMesh", "LeftWing", "RightWing")]
        balls.append({"actor": actor.get_path_name(), "index": index, "active": bool(prop(actor, "bActive")),
                      "components": [component_row(part) for part in parts]})
    return {"status": "inspected", "utc": datetime.now(timezone.utc).isoformat(), "world": world.get_path_name(),
            "assets": assets, "balls": sorted(balls, key=lambda row: row["index"]),
            "scope": "single-frame read-only import and attachment diagnostics; no pixel-size or flight-quality certification"}


def main():
    try:
        report = inspect()
    except Exception:
        report = {"status": "error", "error": traceback.format_exc()}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"status": report["status"], "report": str(REPORT),
            "import_findings": [row["interpretation"] for row in report.get("assets", [])]}


if __name__ == "__main__":
    RESULT = main()

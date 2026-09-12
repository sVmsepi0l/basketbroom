"""Read-only native PIE equipment inspection; no input or camera mutation.

After compiling/reopening the native editor, start fresh BB_Regulation PIE.
At lobby/stoppage use normal input: key 5 selects Hurleyback, key 6 Scout.
Wait two game frames after each selection, then run this probe with a distinct
BRIDGE_ARGS.label. It appends observations to .local/native-hurley-inspection.json.
Owner filters are inspected here; they still require actual image review:
capture the Hurleyback owner's view with native_play_session.py, then the Scout
view, and an existing spectator camera looking at a remote Hurleyback. The
owner should see the camera-attached prop; other views should see the rider's
prop only. Capture after two actual game frames, as the session helper does.

Donnybrook hiding is only covered when that phase is actually observed. This
probe never writes a phase, role, score, input, transform, visibility, or asset.
It does not validate striking, pocket flex/release, physical ball fit, or art.
"""

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re

import unreal

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/native-hurley-inspection.json"
ARGS = globals().get("BRIDGE_ARGS", {})


def prop(obj, name):
    aliases = [name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()]
    if name.startswith("b") and len(name) > 1 and name[1].isupper():
        aliases.append(re.sub(r"(?<!^)(?=[A-Z])", "_", name[1:]).lower())
    for alias in aliases:
        try:
            return obj.get_editor_property(alias)
        except Exception:
            pass
    raise RuntimeError("Required reflected property unavailable: " + name)


def inspect():
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if not level.is_in_play_in_editor() or world is None or not re.fullmatch(
            r"/Basketbroom/Maps/UEDPIE_\d+_BB_Regulation\.BB_Regulation", world.get_path_name()):
        raise RuntimeError("A native BB_Regulation PIE session is required; this probe does not start one")
    match_cls = unreal.load_class(None, "/Script/BasketbroomRuntime.BBMatchState")
    rider_cls = unreal.load_class(None, "/Script/BasketbroomRuntime.BBRiderCharacter")
    states = unreal.GameplayStatics.get_all_actors_of_class(world, match_cls)
    if len(states) != 1:
        raise RuntimeError("Expected exactly one native match")
    phase = str(prop(states[0], "Phase"))
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    camera = unreal.GameplayStatics.get_player_camera_manager(world, 0)
    camera_position = camera.get_camera_location()
    camera_rotation = camera.get_camera_rotation()
    pitch, yaw = math.radians(camera_rotation.pitch), math.radians(camera_rotation.yaw)
    forward = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
    right = (-math.sin(yaw), math.cos(yaw), 0)
    up = (-math.sin(pitch) * math.cos(yaw), -math.sin(pitch) * math.sin(yaw), math.cos(pitch))
    rows = []
    for rider in unreal.GameplayStatics.get_all_actors_of_class(world, rider_cls):
        role = int(prop(rider, "Position"))
        expected = role == 4 and phase != "DONNYBROOK"
        parts = []
        for component in rider.get_components_by_class(unreal.InstancedStaticMeshComponent):
            tags = [str(tag) for tag in prop(component, "ComponentTags")]
            if "BB.Hurley" not in tags:
                continue
            owner_view = "BB.Hurley.Owner" in tags
            parent = component.get_attach_parent()
            visible = bool(component.is_visible())
            only_owner = bool(prop(component, "bOnlyOwnerSee"))
            owner_hidden = bool(prop(component, "bOwnerNoSee"))
            profile = str(component.get_collision_profile_name())
            collision = component.get_collision_enabled()
            parts.append({
                "name": component.get_name(), "owner_view": owner_view,
                "parent": parent.get_name() if parent else None,
                "visible_flag": visible, "only_owner_see": only_owner, "owner_no_see": owner_hidden,
                "instances": component.get_instance_count(), "collision_profile": profile,
                "collision": str(collision),
                "valid": (visible == expected and only_owner == owner_view and owner_hidden != owner_view
                          and profile == "NoCollision" and collision == unreal.CollisionEnabled.NO_COLLISION
                          and component.get_instance_count() > 0
                          and parent == (rider.get_editor_property("Camera") if owner_view
                                         else rider.get_component_by_class(unreal.SkeletalMeshComponent))),
            })
        decision = bool(prop(rider, "bHurleyVisible"))
        location = rider.get_actor_location()
        delta = (location.x - camera_position.x, location.y - camera_position.y, location.z - camera_position.z)
        camera_space = [sum(a * b for a, b in zip(delta, axis)) for axis in (forward, right, up)]
        body = [{"name": part.get_name(), "owner_no_see": bool(prop(part, "bOwnerNoSee")),
                 "only_owner_see": bool(prop(part, "bOnlyOwnerSee")), "visible_flag": bool(part.is_visible())}
                for part in rider.get_components_by_class(unreal.StaticMeshComponent)
                if "BB.RiderVisual" in [str(tag) for tag in prop(part, "ComponentTags")]]
        rows.append({
            "actor": rider.get_path_name(), "local_pawn": rider == pawn,
            "location_cm": [location.x, location.y, location.z],
            "camera_forward_right_up_cm": [round(value, 3) for value in camera_space],
            "camera_distance_cm": round(math.sqrt(sum(value * value for value in delta)), 3),
            "body_owner_filters": body,
            "slot": int(prop(rider, "RosterIndex")), "team": int(prop(rider, "TeamIndex")), "role": role,
            "expected_visible": expected, "native_visible_decision": decision,
            "parts": parts,
            "valid": decision == expected and len(parts) == 8
                     and sum(part["owner_view"] for part in parts) == 4 and all(part["valid"] for part in parts),
        })
    return {
        "utc": datetime.now(timezone.utc).isoformat(), "label": str(ARGS.get("label", "inspection")),
        "world": world.get_path_name(), "game_seconds": unreal.GameplayStatics.get_time_seconds(world),
        "camera_location_cm": [camera_position.x, camera_position.y, camera_position.z],
        "phase": phase, "riders": rows,
        "status": "passed" if len(rows) == 16 and all(row["valid"] for row in rows) else "failed",
    }


def main():
    history = []
    if REPORT.is_file():
        history = json.loads(REPORT.read_text(encoding="utf-8")).get("observations", [])
    observation = inspect()
    history.append(observation)
    valid = [entry for entry in history if entry.get("status") == "passed"]
    coverage = {
        "local_hurleyback_observed": any(row["local_pawn"] and row["role"] == 4 and row["expected_visible"]
                                         for entry in valid for row in entry["riders"]),
        "local_other_role_observed": any(row["local_pawn"] and row["role"] != 4 and not row["expected_visible"]
                                        for entry in valid for row in entry["riders"]),
        "donnybrook_observed": any(entry["phase"] == "DONNYBROOK" for entry in valid),
    }
    report = {
        "status": observation["status"], "scope": "read-only native equipment visibility/configuration snapshot",
        "coverage": coverage, "observations": history,
        "not_covered": ["actual owner/remote rendered images", "striking mechanics", "physical ball/pocket fit",
                        "pocket flex and release test", "final art quality", "network visibility under latency"],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {"status": observation["status"], "coverage": coverage, "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = main()

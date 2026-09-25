"""Read-only native PIE skeletal rider configuration probe.

Run after the new native DLL is loaded and BB_Regulation PIE has its 16 riders.
No input, state/transform mutation, asset save, or forced animation evaluation.
Owner filters are configuration evidence; they do not replace rendered QA.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import traceback
import unreal

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/native-rider-art-inspection.json"
ARGS = globals().get("BRIDGE_ARGS", {})
MESH = "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"
ANIMATION = "/Basketbroom/Art/Characters/A_BB_SeatedFlight_Quinn.A_BB_SeatedFlight_Quinn"
LEGACY = {"Tunic", "Head", "Helmet", "ChestMark"} | {
    side + part for side in ("Left", "Right") for part in ("Arm", "Glove", "BentLeg", "Boot")}


def prop(obj, name):
    aliases = [name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()]
    if name.startswith("b") and len(name) > 1 and name[1].isupper():
        aliases.append(re.sub(r"(?<!^)(?=[A-Z])", "_", name[1:]).lower())
    for alias in aliases:
        try:
            return obj.get_editor_property(alias)
        except Exception:
            pass
    raise RuntimeError("Required reflected art property unavailable: " + name)


def path(obj):
    return obj.get_path_name() if obj else None


def inspect():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not level.is_in_play_in_editor() or world is None or not re.fullmatch(
            r"/Basketbroom/Maps/UEDPIE_\d+_(BB_Regulation|BB_Redrock|BB_Redwoods)\.\1", world.get_path_name()):
        raise RuntimeError("Start an owned native regulation arena PIE before this read-only probe")
    rider_class = unreal.load_class(None, "/Script/BasketbroomRuntime.BBRiderCharacter")
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, rider_class)
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    rows = []
    for rider in actors:
        team = int(prop(rider, "TeamIndex"))
        enabled = bool(prop(rider, "bSkeletalRiderEnabled"))
        mesh = rider.get_component_by_class(unreal.SkeletalMeshComponent)
        if mesh is None:
            rows.append({"actor": path(rider), "team": team, "checks": {"skeletal_mesh_component": False}, "valid": False})
            continue
        animation_data = prop(mesh, "AnimationData")
        animation = prop(animation_data, "AnimToPlay")
        team_name = "Teal" if team == 0 else "Copper"
        expected_materials = ["/Basketbroom/Art/Characters/MI_BB_Quinn_" + team_name + "_0" + str(index)
                              + ".MI_BB_Quinn_" + team_name + "_0" + str(index) for index in (1, 2)]
        materials = [path(mesh.get_material(index)) for index in (0, 1)]
        static_parts = rider.get_components_by_class(unreal.StaticMeshComponent)
        legacy = [part.get_name() for part in static_parts if part.get_name() in LEGACY]
        supports = [part for part in static_parts if part.get_name() in ("BroomWood", "BroomLeather")]
        support_valid = len(supports) == 2 and all(
            str(part.get_collision_profile_name()) == "NoCollision"
            and part.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
            and bool(prop(part, "bOwnerNoSee")) and not bool(prop(part, "bOnlyOwnerSee"))
            and path(part.get_editor_property("static_mesh")) == "/Basketbroom/Art/Equipment/SM_BB_" + part.get_name() + ".SM_BB_" + part.get_name()
            and abs(prop(part, "RelativeLocation").x) < .01 and abs(prop(part, "RelativeLocation").y) < .01 and abs(prop(part, "RelativeLocation").z) < .01
            and abs(prop(part, "RelativeScale3D").x-1) < .01 and abs(prop(part, "RelativeScale3D").y-1) < .01 and abs(prop(part, "RelativeScale3D").z-1) < .01
            and part.get_attach_parent() == mesh for part in supports)
        checks = {
            "skeletal_body_enabled": enabled,
            "expected_mesh": path(mesh.get_skeletal_mesh_asset()) == MESH,
            "expected_animation": path(animation) == ANIMATION,
            "single_node_mode": mesh.get_animation_mode() == unreal.AnimationMode.ANIMATION_SINGLE_NODE,
            "looping_playback_configured": bool(prop(animation_data, "bSavedLooping"))
                and bool(prop(animation_data, "bSavedPlaying")) and abs(float(prop(animation_data, "SavedPlayRate"))-1.0) < 1e-5,
            "root_motion_disabled": animation is not None and not bool(prop(animation, "bEnableRootMotion")),
            "no_collision": str(mesh.get_collision_profile_name()) == "NoCollision"
                and mesh.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION,
            "owner_filtered": bool(prop(mesh, "bOwnerNoSee")) and not bool(prop(mesh, "bOnlyOwnerSee")),
            "component_visible": bool(mesh.is_visible()),
            "correct_team_materials": team in (0, 1) and materials == expected_materials,
            "legacy_body_removed": enabled and not legacy,
            "raised_grip_supported": support_valid,
        }
        rows.append({"actor": path(rider), "team": team, "slot": int(prop(rider, "RosterIndex")),
            "role": int(prop(rider, "Position")), "local_pawn": rider == pawn,
            "mesh": path(mesh.get_skeletal_mesh_asset()), "animation": path(animation),
            "animation_position_seconds": mesh.get_position(), "materials": materials,
            "legacy_body_components": legacy, "grip_components": [part.get_name() for part in supports],
            "checks": checks, "valid": all(checks.values())})
    team_counts = {str(team): sum(row["team"] == team for row in rows) for team in (0, 1)}
    roster_valid = len(rows) == 16 and team_counts == {"0": 8, "1": 8}
    return {"status": "passed" if roster_valid and all(row["valid"] for row in rows) else "failed",
            "label": str(ARGS.get("label", "inspection")), "utc": datetime.now(timezone.utc).isoformat(),
            "world": path(world), "rider_count": len(rows), "team_counts": team_counts,
            "riders_passed": sum(row["valid"] for row in rows), "riders": rows,
            "scope": "read-only configuration in one native PIE world",
            "not_covered": ["actual owner/remote pixels", "animation advancing over time", "network transport",
                            "finger contact", "frame time", "packaged runtime", "all viewpoints/LODs"]}


def main():
    try:
        report = inspect()
    except Exception:
        report = {"status": "error", "error": traceback.format_exc(), "checks_not_run": True}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"status": report["status"], "rider_count": report.get("rider_count"),
            "riders_passed": report.get("riders_passed"), "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = main()

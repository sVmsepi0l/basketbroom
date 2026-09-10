"""Stage fifteen original mounted riders in the UE5 Basketbroom arena.

Run after build_bots.py and stage_game.py. The player occupies Teal's Ranger
position. Persistent Blueprint components provide the rider/broom visuals;
Blueprint gameplay supplies flight and decisions without Python at runtime.
Only BB.Bot actors are replaced by this script.
"""

import json
import os
from pathlib import Path
import sys

import unreal

ROOT = Path(os.environ.get("BASKETBROOM_REPO", r"C:\Git\basketbroom"))
sys.path.insert(0, str(ROOT / "Tools"))
from build_arena import ArenaBuilder, EditorWorldAccess, LEVEL_PATH, ART_PATH
from stage_game import load_required_asset, compiled_class

BOT_PATH = "/Basketbroom/Blueprints/BP_BBBot"
ROLE_NAMES = {0: "Netminder", 1: "Chaser", 2: "Trapper", 3: "Ranger", 4: "Hurleyback", 5: "Scout"}
# Team, role, home, carried-ball label. Slot is assigned once by row index + 1.
# Patrol-only roles still have valid Target references for a uniform contract.
ROSTER = (
    (0, 0, (-5740, 0, 2060), "BB Quaffle"),
    (0, 1, (-3500, -1100, 1800), "BB Quaffle"),
    (0, 1, (-3000, 900, 2100), "BB Quark A"),
    (0, 2, (-2200, -1800, 1800), "BB Quark B"),
    (0, 4, (-1700, 1600, 2500), "BB Quark A"),
    (0, 4, (-4600, 2100, 1450), "BB Quark B"),
    (0, 5, (-800, -600, 3400), "BB Quaffle"),
    (1, 0, (5740, 0, 2060), "BB Quaffle"),
    (1, 1, (3300, -1000, 1850), "BB Quaffle"),
    (1, 1, (2600, 1150, 2350), "BB Quark A"),
    (1, 2, (4700, -1800, 1850), "BB Quark B"),
    (1, 3, (1800, -600, 2750), "BB Quark B"),
    (1, 4, (1700, 1900, 2250), "BB Quark A"),
    (1, 4, (4000, 2100, 1450), "BB Quark B"),
    (1, 5, (900, 500, 3550), "BB Quaffle"),
)


def rider_materials(builder):
    for name, color, roughness, metallic, glow in (
        ("M_BB_RiderTeal", (0.035, 0.60, 0.50), 0.66, 0.03, 0.16),
        ("M_BB_RiderCopper", (0.93, 0.29, 0.065), 0.64, 0.03, 0.16),
        ("M_BB_RiderFace", (0.64, 0.45, 0.27), 0.88, 0.0, 0.04),
        ("M_BB_RiderPants", (0.028, 0.044, 0.061), 0.85, 0.0, 0.02),
        ("M_BB_RiderLeather", (0.07, 0.047, 0.027), 0.71, 0.0, 0.0),
        ("M_BB_RiderWood", (0.25, 0.115, 0.042), 0.56, 0.03, 0.01),
        ("M_BB_RiderBristles", (0.21, 0.14, 0.073), 0.95, 0.0, 0.0),
        ("M_BB_RiderIvory", (0.90, 0.82, 0.61), 0.56, 0.09, 0.12),
    ):
        builder.material(name, color, roughness, metallic, glow)
    return builder.materials


def make_rider_components(blueprint, materials):
    """Original rounded silhouette, seated facing +X on a long wooden broom."""
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    handles = subsystem.k2_gather_subobject_data_for_blueprint(blueprint)
    if not handles:
        raise RuntimeError("Cannot inspect BP_BBBot component hierarchy")
    root_handle = handles[0]
    existing = {}
    for handle in handles:
        data = library.get_data(handle)
        existing[str(library.get_variable_name(data))] = handle
        if library.is_root_component(data):
            root_handle = handle
    meshes = {name: load_required_asset("/Engine/BasicShapes/" + name)
              for name in ("Sphere", "Cylinder", "Cone")}
    # Name, mesh, material, position, scale, pitch/yaw/roll. Uniform tags allow
    # copper instances to override the template's teal tunic and helmet.
    pieces = [
        ("Tunic", "Sphere", "M_BB_RiderTeal", (8, 0, 33), (0.42, 0.46, 0.69), (-12, 0, 0)),
        ("Head", "Sphere", "M_BB_RiderFace", (23, 0, 81), (0.27, 0.25, 0.31), (0, 0, 0)),
        ("Helmet", "Sphere", "M_BB_RiderTeal", (21, 0, 92), (0.30, 0.28, 0.19), (0, 0, 0)),
        ("ChestMark", "Sphere", "M_BB_RiderIvory", (30, 0, 40), (0.027, 0.17, 0.24), (-12, 0, 0)),
        ("BroomShaft", "Cylinder", "M_BB_RiderWood", (25, 0, -8), (0.07, 0.07, 2.70), (90, 0, 0)),
        ("BroomBristles", "Cone", "M_BB_RiderBristles", (-148, 0, -8), (0.39, 0.39, 1.03), (-90, 0, 0)),
        ("BroomBinding", "Cylinder", "M_BB_RiderIvory", (-95, 0, -8), (0.115, 0.115, 0.13), (90, 0, 0)),
        ("BroomNose", "Sphere", "M_BB_RiderWood", (160, 0, -8), (0.13, 0.079, 0.079), (0, 0, 0)),
    ]
    for side, word in ((-1, "Left"), (1, "Right")):
        pieces.extend([
            (word + "Arm", "Sphere", "M_BB_RiderTeal", (32, side * 24, 32), (0.66, 0.15, 0.17), (-40, 0, 0)),
            (word + "Glove", "Sphere", "M_BB_RiderLeather", (56, side * 21, 11), (0.17, 0.14, 0.15), (0, 0, 0)),
            (word + "BentLeg", "Sphere", "M_BB_RiderPants", (8, side * 19, -18), (0.50, 0.18, 0.24), (-30, 0, 0)),
            (word + "Boot", "Sphere", "M_BB_RiderLeather", (29, side * 20, -49), (0.25, 0.20, 0.48), (-10, 0, 0)),
        ])
    for suffix, primitive, material, position, scale, rotation in pieces:
        name = "BB_Rider" + suffix
        handle = existing.get(name)
        if handle is None:
            params = unreal.AddNewSubobjectParams()
            params.set_editor_property("parent_handle", root_handle)
            params.set_editor_property("new_class", unreal.StaticMeshComponent)
            params.set_editor_property("blueprint_context", blueprint)
            handle, reason = subsystem.add_new_subobject(params)
            if not library.is_handle_valid(handle):
                raise RuntimeError("Cannot create %s: %s" % (name, reason))
            if not subsystem.rename_subobject(handle, name):
                raise RuntimeError("Cannot name rider component " + name)
        component = library.get_object_for_blueprint(library.get_data(handle), blueprint)
        if component is None:
            raise RuntimeError("Missing rider component template " + name)
        component.set_static_mesh(meshes[primitive])
        component.set_material(0, materials[material])
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.set_collision_profile_name("NoCollision")
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        component.set_editor_property("relative_location", unreal.Vector(*position))
        component.set_editor_property("relative_scale3d", unreal.Vector(*scale))
        component.set_editor_property("relative_rotation", unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        component.set_editor_property("cast_shadow", True)
        tags = ["BB.RiderVisual"]
        if material == "M_BB_RiderTeal":
            tags.append("BB.Uniform")
        component.set_editor_property("component_tags", [unreal.Name(tag) for tag in tags])
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    cdo = unreal.get_default_object(compiled_class(blueprint))
    if isinstance(cdo, unreal.StaticMeshActor):
        # The native component remains the movable root, while the component
        # hierarchy above provides the full rider silhouette.
        root = cdo.static_mesh_component
        root.set_static_mesh(None)
        root.set_mobility(unreal.ComponentMobility.MOVABLE)
        root.set_collision_profile_name("NoCollision")
        root.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    unreal.EditorAssetLibrary.save_loaded_asset(blueprint)
    return len(pieces)


def stage():
    blueprint = load_required_asset(BOT_PATH)
    compiled_class(blueprint)
    levels = EditorWorldAccess()
    if not levels.load_level(LEVEL_PATH):
        raise RuntimeError("Cannot load Basketbroom arena; run stage_game.py first")
    actors = levels.get_all_level_actors()
    managers = [actor for actor in actors if actor.actor_has_tag("BB.Match")]
    if len(managers) != 1:
        raise RuntimeError("Expected one staged match controller, found %d" % len(managers))
    scoring_balls = {}
    for actor in actors:
        if actor.actor_has_tag("BB.Ball") and actor.get_editor_property("Kind") in (0, 1):
            scoring_balls[actor.get_actor_label()] = actor
    required = {row[3] for row in ROSTER}
    missing = sorted(required.difference(scoring_balls))
    if missing:
        raise RuntimeError("Stage the carried balls before riders: " + ", ".join(missing))
    expected_kinds = {"BB Quaffle": 0, "BB Quark A": 1, "BB Quark B": 1}
    for name, kind in expected_kinds.items():
        if scoring_balls[name].get_editor_property("Kind") != kind:
            raise RuntimeError("Staged ball label/type mismatch: " + name)
    builder = ArenaBuilder()
    materials = rider_materials(builder)
    component_count = make_rider_components(blueprint, materials)
    bot_class = compiled_class(blueprint)
    for actor in levels.get_all_level_actors():
        if actor.actor_has_tag("BB.Bot"):
            levels.destroy_actor(actor)
    manifest = []
    for slot, (team, role, home, target_name) in enumerate(ROSTER, start=1):
        team_name = "Teal" if team == 0 else "Copper"
        actor = levels.spawn_actor_from_class(bot_class, unreal.Vector(*home),
                                             unreal.Rotator(pitch=0, yaw=0 if team == 0 else 180, roll=0))
        if actor is None:
            raise RuntimeError("Cannot create rider slot %d" % slot)
        label = "BB %s %02d %s" % (team_name, slot, ROLE_NAMES[role])
        actor.set_actor_label(label)
        actor.set_folder_path("Basketbroom/Teams/" + team_name)
        actor.set_editor_property("tags", [unreal.Name(tag) for tag in (
            "BB.Gameplay", "BB.Bot", "BB.Rider", "BB.Team." + team_name,
            "BB.Role.%d" % role, "BB.Slot.%d" % slot)])
        for name, value in (("Team", team), ("Slot", slot), ("PlayerRole", role),
                            ("Home", unreal.Vector(*home)), ("Target", scoring_balls[target_name])):
            actor.set_editor_property(name, value)
        root = actor.get_component_by_class(unreal.StaticMeshComponent)
        if isinstance(actor, unreal.StaticMeshActor):
            root = actor.static_mesh_component
        root.set_mobility(unreal.ComponentMobility.MOVABLE)
        root.set_collision_profile_name("NoCollision")
        root.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        uniform = materials["M_BB_Rider" + team_name]
        for component in actor.get_components_by_class(unreal.StaticMeshComponent):
            if component.component_has_tag("BB.Uniform"):
                component.set_material(0, uniform)
        manifest.append({"slot": slot, "team": team, "role": role, "role_name": ROLE_NAMES[role],
                         "home": home, "target": target_name, "label": label})
    if not levels.save_current_level():
        raise RuntimeError("Mounted riders staged, but arena save failed")
    result = {"level": LEVEL_PATH, "bots": len(manifest), "teal_bots": 7, "copper_bots": 8,
              "player_team": 0, "player_role": 3, "total_riders": 16,
              "mesh_components_per_rider": component_count, "roster": manifest}
    output = ROOT / ".local" / "staged-bots.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    unreal.log("BASKETBROOM_BOTS_STAGED " + json.dumps(result, sort_keys=True))
    return result


def build():
    return stage()


if __name__ == "__main__":
    RESULT = stage()

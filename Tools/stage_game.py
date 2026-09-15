"""Stage the UE5.8 Basketbroom training game after arena and gameplay authoring.

In the editor Python console:
    exec(open(r'C:/Git/basketbroom/Tools/stage_game.py').read())

Requires BP_BBMatch, BP_BBBall, BP_BBBroom and BP_BBHUD. Adds persistent native
Blueprint instances, a game mode, five balls and a first-person broom cockpit.
No Python is required while playing. Restaging replaces only BB.Gameplay actors.
"""

import importlib.util as _arena_importlib
from pathlib import Path as _ArenaPath
_arena_spec = _arena_importlib.spec_from_file_location("_bb_active_dimensions", _ArenaPath(__file__).resolve().parent / "arena_dimensions.py")
dimensions = _arena_importlib.module_from_spec(_arena_spec)
_arena_spec.loader.exec_module(dimensions)

import json
import os
from pathlib import Path
import sys

import unreal

ROOT = Path(os.environ.get("BASKETBROOM_REPO", r"C:\Git\basketbroom"))
sys.path.insert(0, str(ROOT / "Tools"))
from build_arena import ArenaBuilder, EditorWorldAccess, LEVEL_PATH, ART_PATH

BASE = "/Basketbroom/Blueprints/"
GAMEPLAY_TAG = "BB.Gameplay"
GAME_MODE_PATH = BASE + "BP_BBGameMode"
PLAYER_START = (-4400.0 * dimensions.LINEAR_SCALE, 0.0, 1400.0)
BALLS = (
    ("Quaffle", 0, (-4050.0, 0.0, 1350.0), 0.65, "M_BB_BallQuaffle"),
    ("Quark A", 1, (-2750.0, -800.0, 1550.0), 0.48, "M_BB_BallQuark"),
    ("Quark B", 1, (-2300.0, 850.0, 1900.0), 0.48, "M_BB_BallQuark"),
    ("Snipe", 2, (-500.0, -1400.0, 2200.0), 0.30, "M_BB_BallSnipe"),
    ("Snitch", 3, (2000.0, 1200.0, 2800.0), 0.24, "M_BB_BallSnitch"),
)
# Move the opening layout across the expanded pitch while retaining its
# playable altitudes and equipment sizes.
BALLS = tuple((name, kind, (point[0]*dimensions.LINEAR_SCALE, point[1]*dimensions.LINEAR_SCALE, point[2]), size, material)
              for name, kind, point, size, material in BALLS)


def load_required_asset(path):
    asset = unreal.load_asset(path)
    if asset is None:
        raise RuntimeError("Required gameplay asset missing: " + path + ". Build the gameplay and HUD first.")
    return asset


def compiled_class(blueprint):
    result = blueprint.generated_class()
    if result is None:
        raise RuntimeError("Blueprint has no generated class: " + blueprint.get_path_name())
    return result


def set_ini_values(path, section, values):
    """Change only our keys, preserving unrelated project settings and ordering."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    header = "[" + section + "]"
    start = next((i for i, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([header] + [key + "=" + value for key, value in values.items()])
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
        seen = set()
        replacement = []
        for line in lines[start + 1:end]:
            key = line.partition("=")[0].strip()
            if key in values:
                if key not in seen:
                    replacement.append(key + "=" + values[key])
                    seen.add(key)
            else:
                replacement.append(line)
        replacement.extend(key + "=" + value for key, value in values.items() if key not in seen)
        lines[start + 1:end] = replacement
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def configure_project_maps():
    config = ROOT / "DevelopmentHarness" / "Config" / "DefaultEngine.ini"
    set_ini_values(config, "/Script/EngineSettings.GameMapsSettings", {
        "EditorStartupMap": LEVEL_PATH,
        "GameDefaultMap": LEVEL_PATH,
        "GlobalDefaultGameMode": GAME_MODE_PATH + ".BP_BBGameMode_C",
    })
    return str(config)


def setup_materials(builder):
    for name, color, roughness, metallic, glow in (
            ("M_BB_BallQuaffle", (0.95, 0.105, 0.045), 0.38, 0.18, 0.6),
            ("M_BB_BallQuark", (0.42, 0.055, 0.95), 0.24, 0.3, 1.3),
            ("M_BB_BallSnipe", (0.80, 0.28, 0.095), 0.28, 0.6, 1.8),
            ("M_BB_BallSnitch", (1.0, 0.60, 0.065), 0.2, 0.8, 1.7),
            ("M_BB_BroomWood", (0.13, 0.055, 0.022), 0.50, 0.06, 0.0),
            ("M_BB_BroomLeather", (0.031, 0.054, 0.052), 0.76, 0.03, 0.0)):
        builder.material(name, color, roughness, metallic, glow)
    for name in ("M_BB_Copper", "M_BB_TealLight", "M_BB_Iron"):
        builder.materials[name] = load_required_asset(ART_PATH + "/Materials/" + name)


def add_broom_cockpit(blueprint, materials):
    """Persist camera and original primitive broom as Blueprint components.

    Uses UE5.8's reflected SubobjectDataSubsystem API, so it survives cooking and
    travel. Existing named BB_ components are updated without duplication.
    """
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    handles = subsystem.k2_gather_subobject_data_for_blueprint(blueprint)
    if not handles:
        raise RuntimeError("Cannot inspect the broom Blueprint component hierarchy")
    root_handle = handles[0]
    existing = {}
    for handle in handles:
        data = library.get_data(handle)
        name = str(library.get_variable_name(data))
        existing[name] = handle
        if library.is_root_component(data):
            root_handle = handle

    def component(name, cls, parent):
        handle = existing.get(name)
        if handle is None:
            params = unreal.AddNewSubobjectParams()
            params.set_editor_property("parent_handle", parent)
            params.set_editor_property("new_class", cls)
            params.set_editor_property("blueprint_context", blueprint)
            handle, reason = subsystem.add_new_subobject(params)
            if not library.is_handle_valid(handle):
                raise RuntimeError("Cannot add broom component %s: %s" % (name, reason))
            if not subsystem.rename_subobject(handle, name):
                raise RuntimeError("Cannot name broom component " + name)
            existing[name] = handle
        data = library.get_data(handle)
        obj = library.get_object_for_blueprint(data, blueprint)
        if obj is None:
            raise RuntimeError("Cannot retrieve broom component template " + name)
        return handle, obj

    camera_handle, camera = component("BB_FlightCamera", unreal.CameraComponent, root_handle)
    camera.set_editor_property("relative_location", unreal.Vector(0, 0, 0))
    camera.set_editor_property("use_pawn_control_rotation", True)
    camera.set_editor_property("field_of_view", 92.0)
    camera.set_editor_property("auto_activate", True)
    meshes = {name: load_required_asset("/Engine/BasicShapes/" + name) for name in ("Cylinder", "Sphere", "Cube", "Cone")}

    # Camera local forward is +X. The broom occupies the lower right of the view
    # and leaves the central reticle and carried-ball sight line unobstructed.
    parts = [
        ("Shaft", "Cylinder", "M_BB_BroomWood", (108, 30, -56), (0.082, 0.082, 2.25), (90, 0, 0)),
        ("Nose", "Sphere", "M_BB_BroomWood", (220, 30, -54), (0.15, 0.105, 0.105), (0, 0, 0)),
        ("Grip", "Cylinder", "M_BB_BroomLeather", (65, 30, -56), (0.105, 0.105, 0.42), (90, 0, 0)),
        ("ForwardCollar", "Cylinder", "M_BB_Copper", (152, 30, -56), (0.124, 0.124, 0.065), (90, 0, 0)),
        ("GripCollar", "Cylinder", "M_BB_Copper", (90, 30, -56), (0.116, 0.116, 0.05), (90, 0, 0)),
        ("CharmMount", "Cube", "M_BB_Iron", (145, 30, -48), (0.17, 0.14, 0.08), (0, 0, 0)),
        ("FlightCharm", "Sphere", "M_BB_TealLight", (145, 30, -42), (0.12, 0.11, 0.065), (0, 0, 0)),
        ("RearBristle", "Cone", "M_BB_BroomWood", (-55, 30, -56), (0.4, 0.4, 0.75), (-90, 0, 0)),
    ]
    for i in range(6):
        parts.append(("GripWrap%02d" % i, "Cylinder", "M_BB_Copper", (47 + i * 6.5, 30, -56),
                      (0.111, 0.111, 0.012), (90, 0, 0)))
    for suffix, mesh_name, material, location, scale, rotation in parts:
        handle, mesh = component("BB_Broom" + suffix, unreal.StaticMeshComponent, camera_handle)
        mesh.set_static_mesh(meshes[mesh_name])
        mesh.set_material(0, materials[material])
        mesh.set_mobility(unreal.ComponentMobility.MOVABLE)
        mesh.set_collision_profile_name("NoCollision")
        mesh.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        mesh.set_editor_property("relative_location", unreal.Vector(*location))
        mesh.set_editor_property("relative_scale3d", unreal.Vector(*scale))
        mesh.set_editor_property("relative_rotation", unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        mesh.set_editor_property("cast_shadow", False)
        mesh.set_editor_property("only_owner_see", True)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    cdo = unreal.get_default_object(compiled_class(blueprint))
    inherited_mesh = cdo.get_editor_property("mesh_component")
    if inherited_mesh is not None:
        inherited_mesh.set_visibility(False)
        inherited_mesh.set_collision_profile_name("NoCollision")
        inherited_mesh.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    cdo.set_editor_property("find_camera_component_when_view_target", True)
    unreal.EditorAssetLibrary.save_loaded_asset(blueprint)
    return len(parts)


def setup_game_mode(pawn, hud):
    blueprint = unreal.load_asset(GAME_MODE_PATH)
    if blueprint is None:
        factory = unreal.BlueprintFactory()
        factory.set_editor_property("parent_class", unreal.GameModeBase)
        blueprint = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "BP_BBGameMode", BASE.rstrip("/"), unreal.Blueprint, factory)
    if blueprint is None:
        raise RuntimeError("Could not create Basketbroom's game mode")
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    cdo = unreal.get_default_object(compiled_class(blueprint))
    cdo.set_editor_property("default_pawn_class", compiled_class(pawn))
    cdo.set_editor_property("hud_class", compiled_class(hud))
    cdo.set_editor_property("start_players_as_spectators", False)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    unreal.EditorAssetLibrary.save_loaded_asset(blueprint, False)
    return blueprint


def build():
    # Verify every dependency before touching the existing staged actors.
    blueprints = {name: load_required_asset(BASE + name) for name in (
        "BP_BBMatch", "BP_BBBall", "BP_BBBroom", "BP_BBHUD")}
    for blueprint in blueprints.values():
        compiled_class(blueprint)
    load_required_asset(LEVEL_PATH)
    builder = ArenaBuilder()
    setup_materials(builder)
    cockpit_parts = add_broom_cockpit(blueprints["BP_BBBroom"], builder.materials)
    mode = setup_game_mode(blueprints["BP_BBBroom"], blueprints["BP_BBHUD"])
    levels = EditorWorldAccess()
    if not levels.load_level(LEVEL_PATH):
        raise RuntimeError("Could not open the Basketbroom arena")
    for actor in levels.get_all_level_actors():
        if actor.actor_has_tag(GAMEPLAY_TAG):
            levels.destroy_actor(actor)
    spawned = []

    def spawn(cls, label, location, tags=()):
        actor = levels.spawn_actor_from_class(cls, unreal.Vector(*location), unreal.Rotator(pitch=0, yaw=0, roll=0))
        if actor is None:
            raise RuntimeError("Could not stage " + label)
        actor.set_actor_label(label)
        actor.set_folder_path("Basketbroom/Gameplay")
        actor.set_editor_property("tags", [unreal.Name(tag) for tag in (GAMEPLAY_TAG,) + tuple(tags)])
        spawned.append(actor)
        return actor

    manager = spawn(compiled_class(blueprints["BP_BBMatch"]), "BB Match Controller", (0, 0, -300), ("BB.Match",))
    sphere = load_required_asset("/Engine/BasicShapes/Sphere")
    for label, kind, home, scale, material in BALLS:
        ball = spawn(compiled_class(blueprints["BP_BBBall"]), "BB " + label, home,
                     ("BB.Ball", "BB.Ball.Kind.%d" % kind))
        ball.set_editor_property("Kind", kind)
        ball.set_editor_property("Home", unreal.Vector(*home))
        mesh = ball.get_component_by_class(unreal.StaticMeshComponent)
        if mesh is None:
            raise RuntimeError("BB ball must inherit StaticMeshActor: " + label)
        mesh.set_mobility(unreal.ComponentMobility.MOVABLE)
        mesh.set_static_mesh(sphere)
        mesh.set_material(0, builder.materials[material])
        mesh.set_simulate_physics(False)
        mesh.set_collision_profile_name("NoCollision")
        mesh.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        mesh.set_editor_property("cast_shadow", True)
        ball.set_actor_scale3d(unreal.Vector(scale, scale, scale))

    # Adopt the venue's start anchor so the game mode never chooses a second
    # random spawn. Restaging only replaces this now-owned gameplay actor.
    starts = [actor for actor in levels.get_all_level_actors()
              if isinstance(actor, unreal.PlayerStart) and actor.actor_has_tag("BB.Spawn")]
    if starts:
        start = starts[0]
        start.set_actor_location(unreal.Vector(*PLAYER_START), False, False)
        start.set_actor_rotation(unreal.Rotator(pitch=0, yaw=0, roll=0), False)
        start.set_actor_label("BB Training Player Start")
        start.set_folder_path("Basketbroom/Gameplay")
        start.set_editor_property("tags", [unreal.Name(GAMEPLAY_TAG), unreal.Name("BB.Spawn")])
        spawned.append(start)
    else:
        start = spawn(unreal.PlayerStart, "BB Training Player Start", PLAYER_START, ("BB.Spawn",))
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property("default_game_mode", compiled_class(mode))
    if not levels.save_current_level():
        raise RuntimeError("Could not save the staged Basketbroom arena")
    unreal.EditorAssetLibrary.save_directory(BASE.rstrip("/"), only_if_is_dirty=True, recursive=True)
    config = configure_project_maps()
    result = {
        "level": LEVEL_PATH, "game_mode": GAME_MODE_PATH,
        "match_actor": manager.get_path_name(), "ball_count": len(BALLS),
        "quaffle": 1, "quarks": 2, "snipe": 1, "snitch": 1, "hazards": 0,
        "spawned_actor_count": len(spawned), "player_start": PLAYER_START,
        "first_person_broom_components": cockpit_parts, "config": config,
    }
    output = ROOT / ".local" / "staged-game.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    unreal.log("BASKETBROOM_GAME_STAGED " + json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    RESULT = build()

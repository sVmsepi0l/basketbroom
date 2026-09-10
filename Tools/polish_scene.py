"""Refresh BB_Arena presentation in place; keep all gameplay actors intact.

Run build() in the Unreal Editor Python environment. The map must be loaded and
PIE stopped. Shared palette and lighting settings live in build_arena.py.
"""

import importlib.util
import json
from pathlib import Path

import unreal


def build():
    source = Path(__file__).with_name("build_arena.py")
    spec = importlib.util.spec_from_file_location("basketbroom_arena_polish_source", source)
    arena = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(arena)
    builder = arena.ArenaBuilder()
    actors = list(builder.levels.get_all_level_actors())
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not world or world.get_path_name().split(".")[0] != arena.LEVEL_PATH:
        raise RuntimeError("Load " + arena.LEVEL_PATH + " before polishing the arena")

    counts = {"materials": 0, "floodlights": 0, "presentation_volumes": 0,
              "ground_surfaces": 0, "signs": 0, "old_scenery_removed": 0,
              "scenery_created": 0, "visual_collision_profiles": 0,
              "old_details_removed": 0, "detail_actors_created": 0, "metal_goal_rims": 0,
              "hidden_collision_rims": 0, "textures": 0, "detail_meshes": 0}
    builder.import_stone_texture()
    counts["textures"] = 1
    arena.generate_detail_meshes()
    for name in arena.DETAIL_MESHES:
        builder.import_mesh(name)
        counts["detail_meshes"] += 1
    for material in arena.ARENA_PALETTE:
        builder.material(*material)
        counts["materials"] += 1

    for actor in actors:
        if not actor.actor_has_tag(arena.GENERATED_TAG):
            continue
        label = actor.get_actor_label()
        if actor.actor_has_tag(arena.DETAIL_TAG):
            builder.levels.destroy_actor(actor)
            counts["old_details_removed"] += 1
            continue
        if actor.actor_has_tag(arena.SCENERY_TAG):
            builder.levels.destroy_actor(actor)
            counts["old_scenery_removed"] += 1
            continue
        if label in ("Continuous open-crown rebound net", "Twilight dome",
                     "Distant stars", "Ground horizon"):
            # Repair previously saved visual meshes as well as the scenery
            # recreated below. Physical net walls are separate hidden actors.
            component = actor.get_component_by_class(unreal.StaticMeshComponent)
            if component:
                component.set_collision_profile_name("NoCollision")
                component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                counts["visual_collision_profiles"] += 1
        if label.startswith("Court flood "):
            component = actor.get_component_by_class(unreal.PointLightComponent)
            if component:
                builder.configure_flood(component)
                counts["floodlights"] += 1
        elif label == "Twilight amber key":
            builder.configure_key(actor.get_component_by_class(unreal.DirectionalLightComponent))
        elif label == "Aerial depth":
            builder.configure_fog(actor.get_component_by_class(unreal.ExponentialHeightFogComponent))
        elif actor.actor_has_tag("BB.Goal.Rim"):
            actor.set_actor_hidden_in_game(True)
            actor.static_mesh_component.set_visibility(False)
            counts["hidden_collision_rims"] += 1
        elif actor.actor_has_tag("BB.Goal"):
            material = ("M_BB_Copper" if actor.actor_has_tag("BB.Goal.Small") else
                        "M_BB_Teal" if actor.actor_has_tag("BB.Team.Teal") else "M_BB_Copper")
            actor.static_mesh_component.set_material(0, builder.materials[material])
            counts["metal_goal_rims"] += 1
        elif label == "Ground horizon":
            actor.static_mesh_component.set_material(0, builder.materials["M_BB_Ground"])
            counts["ground_surfaces"] += 1
        elif label == "Arena presentation":
            builder.configure_presentation(actor)
            counts["presentation_volumes"] += 1
        elif label in ("Venue title", "Teal end identity", "Copper end identity"):
            component = actor.get_component_by_class(unreal.TextRenderComponent)
            if component:
                component.set_text_render_color(unreal.Color(232, 191, 122, 255))
                counts["signs"] += 1

    for primitive in ("Cube", "Cylinder", "Sphere", "Cone"):
        builder.meshes[primitive] = builder.load_mesh("/Engine/BasicShapes/" + primitive)
    builder.scenery()
    counts["scenery_created"] = len(builder.actors)
    builder.architecture_detail()
    builder.lantern_lighting()
    counts["detail_actors_created"] = len(builder.actors) - counts["scenery_created"]
    # Palette updates change the captured environment; capture after alterations.
    for actor in builder.levels.get_all_level_actors():
        if actor.actor_has_tag(arena.GENERATED_TAG) and actor.get_actor_label() == "Blue twilight ambience":
            sky = actor.get_component_by_class(unreal.SkyLightComponent)
            sky.set_intensity(1.75)
            sky.recapture_sky()
    if not builder.levels.save_current_level():
        raise RuntimeError("Polished arena could not be saved")
    builder.assets.save_directory(arena.ART_PATH, only_if_is_dirty=True, recursive=True)
    unreal.log("BASKETBROOM_SCENE_POLISH_COMPLETE " + json.dumps(counts, sort_keys=True))
    return counts


def capture():
    """Capture the real editor scene from an authored camera for art review."""
    args = globals().get("BRIDGE_ARGS", {})
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    label = args.get("camera", "BB Hero Camera")
    camera = next((actor for actor in actors if actor.get_actor_label() == label), None)
    if camera is None:
        raise RuntimeError("Missing review camera " + label)
    destination = Path(__file__).resolve().parents[1] / ".local" / "art-review"
    destination.mkdir(parents=True, exist_ok=True)
    filename = destination / ("flight.png" if label == "BB Flight Camera" else "hero.png")
    task = unreal.AutomationLibrary.take_high_res_screenshot(1600, 900, str(filename), camera=camera)
    if task is None:
        raise RuntimeError("Editor screenshot could not be scheduled")
    return {"camera": label, "screenshot": str(filename), "scheduled": True}


def audit_saved_scene():
    """Reload the saved map and verify decorative collision remains disabled."""
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not level.load_level("/Basketbroom/Maps/BB_Arena"):
        raise RuntimeError("Cannot reload the saved arena for art validation")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    checked = []
    for actor in actors:
        label = actor.get_actor_label()
        decorative = actor.actor_has_tag("BB.Scenery") or actor.actor_has_tag("BB.ArtDetail") or label in (
            "Continuous open-crown rebound net", "Twilight dome", "Distant stars", "Ground horizon")
        component = actor.get_component_by_class(unreal.StaticMeshComponent) if decorative else None
        if component is not None:
            if str(component.get_collision_profile_name()) != "NoCollision" or component.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION:
                raise RuntimeError("Decorative mesh blocks after saved-map reload: " + label)
            checked.append(label)
    return {"saved_map_reloaded": True, "nonblocking_visual_meshes": len(checked), "labels": checked}


if __name__ == "__main__":
    operation = globals().get("BRIDGE_ARGS", {}).get("operation")
    RESULT = capture() if operation == "capture" else audit_saved_scene() if operation == "audit" else build()

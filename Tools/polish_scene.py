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
              "scenery_created": 0, "visual_collision_profiles": 0}
    for material in arena.ARENA_PALETTE:
        builder.material(*material)
        counts["materials"] += 1

    for actor in actors:
        if not actor.actor_has_tag(arena.GENERATED_TAG):
            continue
        label = actor.get_actor_label()
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
                component.set_intensity(arena.COURT_FLOOD_INTENSITY)
                component.set_cast_shadows(False)
                counts["floodlights"] += 1
        elif label == "Ground horizon":
            actor.static_mesh_component.set_material(0, builder.materials["M_BB_Ground"])
            counts["ground_surfaces"] += 1
        elif label == "Arena presentation":
            settings = actor.get_editor_property("settings")
            for name, value in (("override_auto_exposure_min_brightness", True),
                                ("override_auto_exposure_max_brightness", True),
                                ("auto_exposure_min_brightness", arena.EXPOSURE_BRIGHTNESS),
                                ("auto_exposure_max_brightness", arena.EXPOSURE_BRIGHTNESS),
                                ("override_bloom_intensity", True),
                                ("bloom_intensity", arena.BLOOM_INTENSITY)):
                settings.set_editor_property(name, value)
            actor.set_editor_property("settings", settings)
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
    # Palette updates change the captured environment; capture after alterations.
    for actor in builder.levels.get_all_level_actors():
        if actor.actor_has_tag(arena.GENERATED_TAG) and actor.get_actor_label() == "Blue twilight ambience":
            actor.get_component_by_class(unreal.SkyLightComponent).recapture_sky()
    if not builder.levels.save_current_level():
        raise RuntimeError("Polished arena could not be saved")
    builder.assets.save_directory(arena.ART_PATH, only_if_is_dirty=True, recursive=True)
    unreal.log("BASKETBROOM_SCENE_POLISH_COMPLETE " + json.dumps(counts, sort_keys=True))
    return counts


if __name__ == "__main__":
    build()

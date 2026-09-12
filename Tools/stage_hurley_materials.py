"""Enable instanced-mesh shaders on exactly the three shared Hurley materials.

Run with PIE stopped. This changes/saves only the named material packages;
it does not rebuild graphs, stage actors, save maps, or save other dirty assets.
ArenaBuilder.material also preserves these flags on later authoring rebuilds.
"""

import json
import unreal

MATERIALS = ("M_BB_BroomWood", "M_BB_BroomLeather", "M_BB_RiderIvory")


def build():
    if unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():
        raise RuntimeError("Stop PIE before updating the three Hurley material packages")
    rows = []
    for name in MATERIALS:
        path = "/Basketbroom/Art/Materials/" + name
        material = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(material, unreal.Material):
            raise RuntimeError("Expected original Material: " + path)
        before = bool(material.get_editor_property("used_with_instanced_static_meshes"))
        material.set_editor_property("used_with_instanced_static_meshes", True)
        unreal.MaterialEditingLibrary.recompile_material(material)
        if not material.get_editor_property("used_with_instanced_static_meshes"):
            raise RuntimeError("Instanced-mesh usage did not persist in memory: " + path)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False):
            raise RuntimeError("Could not save the named material: " + path)
        rows.append({"path": path, "previous_instanced_usage": before, "instanced_usage": True, "saved": True})
    result = {"status": "saved", "materials": rows, "material_count": len(rows),
              "maps_saved": 0, "shader_and_render_validation_pending": True}
    unreal.log("BASKETBROOM HURLEY MATERIAL USAGE " + json.dumps(result))
    return result


if __name__ == "__main__":
    RESULT = build()

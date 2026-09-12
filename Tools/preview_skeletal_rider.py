"""Transient UE5 editor pose review; never saves a map or changes live riders."""
from pathlib import Path
import importlib.util
import json
import math
import struct
import time
import traceback
import unreal

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/skeletal-rider-preview.json"
KEY = "_basketbroom_skeletal_preview"
ARGS = globals().get("BRIDGE_ARGS", {})


def png_dimensions(data):
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 24:
        return None
    dimensions = struct.unpack(">II", data[16:24])
    offset = 8
    while offset+12 <= len(data):
        length = struct.unpack(">I", data[offset:offset+4])[0]
        if offset+length+12 > len(data):
            return None
        if data[offset+4:offset+8] == b"IEND":
            # Render-target PNG export may retain zero-padded allocation bytes.
            return dimensions if length == 0 else None
        offset += length+12
    return None


class Preview:
    def __init__(self):
        self.actors = []
        self.handle = None
        self.camera = None
        self.selection = []
        self.index = 0
        self.pending = None
        self.capture_task = None
        self.frames = 0
        self.started = time.monotonic()
        self.changed = self.started
        self.directory = ROOT / ".local/art-review/skeletal-rider" / str(time.time_ns())
        self.directory.mkdir(parents=True, exist_ok=True)
        self.data = {"status": "running", "views": [], "maps_saved": 0,
                     "fixture": "transient stock-mesh pose and existing broom geometry in editor", "report": str(REPORT)}

    def save(self):
        REPORT.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def spawn(self, cls, location, rotation=None):
        actor = self.actor_system.spawn_actor_from_class(cls, unreal.Vector(*location),
            rotation or unreal.Rotator(), transient=True)
        if actor is None:
            raise RuntimeError("Could not create transient preview actor")
        actor.set_editor_property("tags", list(actor.get_editor_property("tags")) + ["BB.SkeletalPreview"])
        self.actors.append(actor)
        return actor

    def begin(self):
        spec = importlib.util.spec_from_file_location("bb_skeletal_author", ROOT / "Tools/stage_skeletal_rider.py")
        author = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(author)
        author._editor()
        self.editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self.actor_system = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        self.world = self.editor.get_editor_world()
        self.camera = self.editor.get_level_viewport_camera_info()
        self.selection = list(self.actor_system.get_selected_level_actors())
        mesh = unreal.EditorAssetLibrary.load_asset(author.MESH_PACKAGE)
        animation = unreal.EditorAssetLibrary.load_asset(author.ANIMATION_PACKAGE)
        if not isinstance(animation, unreal.AnimSequence):
            raise RuntimeError("Build and save the seated animation before preview")
        self.base = (0, 0, 1400)
        actor = self.spawn(unreal.SkeletalMeshActor, self.base)
        actor.set_actor_label("BB transient seated rider review")
        component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
        component.set_skeletal_mesh_asset(mesh)
        team = ARGS.get("team", "Teal")
        if team not in ("Teal", "Copper"):
            raise ValueError("team must be Teal or Copper")
        self.data["team"] = team
        for index in (0, 1):
            path = "/Basketbroom/Art/Characters/MI_BB_Quinn_" + team + "_0" + str(index+1)
            material = unreal.EditorAssetLibrary.load_asset(path)
            if material is not None:
                component.set_material(index, material)
        component.set_collision_profile_name("NoCollision")
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        # This public method also ticks animation and refreshes bone transforms;
        # PlayAnimation/SetPosition alone can leave an idle editor in reference pose.
        component.override_animation_data(animation, True, False, .5, 0)
        component.set_update_animation_in_editor(True)
        self.data["pelvis_world_z"] = component.get_socket_location("pelvis").z
        self.data["foot_world_z"] = component.get_socket_location("foot_l").z
        if abs(self.data["pelvis_world_z"]-1408) > 1 or self.data["foot_world_z"] > 1375:
            raise RuntimeError("The preview component did not evaluate the seated animation")
        for shape, position, scale, pitch, roll, material in (
            ("Cylinder", (25, 0, 1392), (.07, .07, 2.70), 90, 0, "M_BB_BroomWood"),
            ("Cone", (-148, 0, 1392), (.39, .39, 1.03), -90, 0, "M_BB_RiderBristles"),
            ("Cylinder", (-95, 0, 1392), (.115, .115, .13), 90, 0, "M_BB_RiderIvory"),
            ("Cylinder", (43, 0, 1399.5), (.045, .045, .155), 0, 0, "M_BB_BroomWood"),
            ("Cylinder", (43, 0, 1407), (.065, .065, .34), 0, 90, "M_BB_BroomLeather"),
        ):
            broom = self.spawn(unreal.StaticMeshActor, position, unreal.Rotator(pitch=pitch, yaw=0, roll=roll))
            part = broom.get_component_by_class(unreal.StaticMeshComponent)
            part.set_static_mesh(unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/" + shape))
            part.set_material(0, unreal.EditorAssetLibrary.load_asset("/Basketbroom/Art/Materials/" + material))
            part.set_collision_profile_name("NoCollision")
            part.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            broom.set_actor_scale3d(unreal.Vector(*scale))
            broom.set_actor_rotation(unreal.Rotator(pitch=pitch, yaw=0, roll=roll), False)
        for location, strength in (((100, -180, 1550), 4), ((-80, 160, 1500), 2)):
            light = self.spawn(unreal.PointLight, location)
            point = light.get_component_by_class(unreal.PointLightComponent)
            point.set_intensity(strength)
            point.set_attenuation_radius(700)
            point.set_cast_shadows(False)
        self.capture_actor = self.spawn(unreal.SceneCapture2D, self.base)
        self.capture = self.capture_actor.get_component_by_class(unreal.SceneCaptureComponent2D)
        self.target = unreal.RenderingLibrary.create_render_target2d(
            self.world, 1280, 960, unreal.TextureRenderTargetFormat.RTF_RGBA8)
        self.capture.set_editor_property("texture_target", self.target)
        self.capture.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        self.capture.set_editor_property("capture_every_frame", False)
        self.capture.set_editor_property("capture_on_movement", False)
        self.capture.set_editor_property("always_persist_rendering_state", True)
        self.capture.set_editor_property("fov_angle", 90)
        self.data["capture_backend"] = "transient SceneCapture2D, immediate RGBA8 render-target export"
        self.actor_system.clear_actor_selection_set()
        self.views = [("side", (0, -230, 1430)), ("front", (230, 0, 1430)),
                      ("three-quarter", (175, -170, 1480))]
        self.set_view()
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.save()

    def set_view(self):
        name, location = self.views[self.index]
        rotation = unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*location), unreal.Vector(0, 0, 1425))
        self.capture_actor.set_actor_location(unreal.Vector(*location), False, True)
        self.capture_actor.set_actor_rotation(rotation, False)
        self.frames = 0
        self.changed = time.monotonic()
        self.pending = None

    def tick(self, delta):
        try:
            if time.monotonic()-self.started > 120:
                raise RuntimeError("Timed out capturing seated rider review")
            if self.pending is not None:
                if self.pending.is_file():
                    data = self.pending.read_bytes()
                    dimensions = png_dimensions(data)
                    if dimensions is not None:
                        if dimensions != (1280, 960):
                            raise RuntimeError("Unexpected capture dimensions: " + str(dimensions))
                        self.data["views"].append({"view": self.views[self.index][0], "path": str(self.pending), "dimensions": dimensions})
                        self.index += 1
                        if self.index == len(self.views):
                            self.finish("captured_pending_visual_review")
                        else:
                            self.set_view()
                            self.save()
                return
            self.frames += 1
            self.capture.capture_scene()
            if self.frames >= 8 and time.monotonic()-self.changed >= 2:
                self.pending = self.directory / (self.views[self.index][0]+".png")
                unreal.RenderingLibrary.export_render_target(self.world, self.target,
                    str(self.directory), self.pending.name)
        except Exception:
            self.finish("error", traceback.format_exc())

    def finish(self, status, error=None):
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        cleanup_failures = []
        for actor in reversed(self.actors):
            name = actor.get_path_name()
            if not self.actor_system.destroy_actor(actor):
                cleanup_failures.append(name)
        self.actors = []
        if hasattr(self, "target") and self.target is not None:
            unreal.RenderingLibrary.release_render_target2d(self.target)
            self.target = None
        if self.camera:
            values = list(self.camera)
            if len(values) == 3 and isinstance(values[0], bool):
                values = values[1:] if values[0] else []
            if len(values) == 2:
                self.editor.set_level_viewport_camera_info(values[0], values[1])
        if hasattr(self, "actor_system"):
            self.actor_system.set_selected_level_actors(self.selection)
        self.data.update(status="cleanup_failed" if cleanup_failures else status,
                         transient_actors_removed=not cleanup_failures,
                         cleanup_failures=cleanup_failures, elapsed_seconds=time.monotonic()-self.started)
        if error:
            self.data["error"] = error
        self.save()


def main():
    operation = ARGS.get("operation", "inspect")
    prior = getattr(unreal, KEY, None)
    if operation == "inspect":
        return prior.data if prior else {"status": "not_started"}
    if operation == "stop":
        if prior and prior.data["status"] == "running":
            prior.finish("stopped")
        return prior.data if prior else {"status": "not_started"}
    if operation != "start":
        raise ValueError("Choose inspect, start, or stop")
    if prior and prior.data["status"] == "running":
        raise RuntimeError("A seated rider preview is already running")
    preview = Preview()
    setattr(unreal, KEY, preview)
    try:
        preview.begin()
    except Exception:
        preview.finish("error", traceback.format_exc())
    return preview.data


if __name__ == "__main__":
    RESULT = main()

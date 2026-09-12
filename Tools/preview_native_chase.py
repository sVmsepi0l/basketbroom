"""Capture an existing active chase ball in native PIE without altering gameplay.

With PIE stopped, operation=prepare stages one unsaved editor camera for PIE
duplication. Start a native session, then request operation=start, ball_index=3
(Snipe) or 4 (Snitch). Optional pause_on_release waits up to 90 seconds for an
active ball and requests an ordinary host stoppage for review. The session stays
at that stoppage afterward. A disposable SceneCapture follows the existing ball;
no gameplay properties, transforms, animation clocks, or maps are assigned.
"""
from pathlib import Path
import importlib.util
import json
import time
import traceback
import unreal

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/native-chase-preview.json"
KEY = "_basketbroom_native_chase_preview"
ARGS = globals().get("BRIDGE_ARGS", {})
CAMERA_TAG = "BB.Development.ChaseCapture"
spec = importlib.util.spec_from_file_location("_bb_chase_context", ROOT / "Tools/native_play_session.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class Preview:
    def __init__(self):
        self.started = time.monotonic()
        self.handle = self.capture_actor = self.target = None
        self.index = self.frames = 0
        self.flap = []
        self.directory = ROOT / ".local/art-review/chase" / str(time.time_ns())
        self.directory.mkdir(parents=True)
        self.data = {"status": "running", "views": [], "maps_saved": 0,
                     "gameplay_written": False, "fixture": "SceneCapture of existing native PIE ball"}

    def save(self):
        REPORT.write_text(json.dumps(self.data, indent=2, default=str)+"\n", encoding="utf-8")

    def begin(self):
        self.world, self.match, self.pawn, controller, balls = base.context()
        index = ARGS.get("ball_index", 3)
        if type(index) is not int or index not in (3, 4):
            raise ValueError("Choose native Snipe=3 or Snitch=4")
        self.ball = next(ball for ball in balls if base.prop(ball, "BallIndex") == index)
        self.pause_on_release = ARGS.get("pause_on_release", False)
        if type(self.pause_on_release) is not bool:
            raise ValueError("pause_on_release must be a boolean")
        self.pause_requested = False
        self.data.update(ball_index=index, actor=self.ball.get_path_name(),
                         phase="waiting_for_active_ball", pause_on_release=self.pause_on_release)
        if not self.pause_on_release:
            if not base.prop(self.ball, "bActive"):
                raise RuntimeError("The requested chase ball must already be active")
            self.configure_capture()
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.save()

    def configure_capture(self):
        self.mesh = base.prop(self.ball, "Mesh")
        self.left, self.right = [base.prop(self.ball, name) for name in ("LeftWing", "RightWing")]
        parts = []
        for component in (self.left, self.right):
            mesh = component.get_editor_property("static_mesh")
            if not mesh or not component.is_visible() or component.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION:
                raise RuntimeError("Native wing is missing, hidden, or collidable")
            parts.append({"component": component.get_name(), "mesh": mesh.get_path_name(),
                          "collision": str(component.get_collision_enabled()),
                          "material": component.get_material(0).get_path_name(),
                          "world_scale": str(component.get_world_scale())})
        self.data.update(wings=parts, capture_match_status=str(base.prop(self.match, "Status")))
        cameras = [actor for actor in unreal.GameplayStatics.get_all_actors_of_class(self.world, unreal.SceneCapture2D)
                   if actor.actor_has_tag(CAMERA_TAG)]
        if len(cameras) != 1:
            raise RuntimeError("Stop PIE and request operation=prepare to stage the transient capture camera")
        actor = cameras[0]
        self.capture_actor = actor
        self.capture = actor.get_component_by_class(unreal.SceneCaptureComponent2D)
        self.target = unreal.RenderingLibrary.create_render_target2d(
            self.world, 1280, 960, unreal.TextureRenderTargetFormat.RTF_RGBA8)
        for name, value in {"texture_target": self.target,
                            "capture_source": unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR,
                            "capture_every_frame": False, "capture_on_movement": False,
                            "always_persist_rendering_state": True, "fov_angle": 60.0}.items():
            self.capture.set_editor_property(name, value)
        self.views = [("three-quarter", (240, -280, 190)), ("front", (330, 0, 70))]
        self.changed = time.monotonic()
        self.data["phase"] = "capturing"

    def tick(self, delta):
        try:
            if time.monotonic()-self.started > (90 if self.pause_on_release else 35):
                raise RuntimeError("Native chase capture timed out")
            if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():
                raise RuntimeError("PIE ended during native chase capture")
            if self.capture_actor is None:
                if not base.prop(self.ball, "bActive"):
                    if str(base.prop(self.match, "Status")) == "FINAL":
                        raise RuntimeError("Match ended before review; start a fresh native session")
                    return
                if self.pause_on_release and base.prop(self.match, "bLive"):
                    if not self.pause_requested:
                        if not self.pawn.development_request_action(5, 0):
                            raise RuntimeError("Could not queue the ordinary host stoppage")
                        self.pause_requested = True
                        self.data["host_stoppage"] = "queued through ordinary native input"
                        self.save()
                    return
                self.configure_capture()
                self.save()
            if not base.prop(self.ball, "bActive"):
                raise RuntimeError("Chase ball became inactive during capture")
            position = self.mesh.get_world_location()
            name, offset = self.views[self.index]
            location = position + self.mesh.get_forward_vector()*offset[0] + self.mesh.get_right_vector()*offset[1] + unreal.Vector(0, 0, offset[2])
            self.capture_actor.set_actor_location(location, False, True)
            self.capture_actor.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(location, position), False)
            self.flap.append(float(self.left.get_editor_property("relative_rotation").roll))
            self.capture.capture_scene()
            self.frames += 1
            if self.frames < 8 or time.monotonic()-self.changed < 2:
                return
            path = self.directory / (name+".png")
            unreal.RenderingLibrary.export_render_target(self.world, self.target, str(self.directory), path.name)
            if not path.is_file() or not path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("SceneCapture did not export a PNG")
            self.data["views"].append({"view": name, "path": str(path), "dimensions": [1280, 960]})
            self.index += 1
            self.frames = 0
            self.changed = time.monotonic()
            if self.index == len(self.views):
                self.data["observed_left_flap_range_degrees"] = [min(self.flap), max(self.flap)]
                if max(self.flap)-min(self.flap) < 5:
                    raise RuntimeError("The actual native flap did not visibly advance")
                self.finish("captured_pending_visual_review")
            else:
                self.save()
        except Exception:
            self.finish("error", traceback.format_exc())

    def finish(self, status, error=None):
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        if self.capture_actor is not None:
            self.capture.set_editor_property("texture_target", None)
            self.capture_actor = None
        if self.target is not None:
            unreal.RenderingLibrary.release_render_target2d(self.target)
            self.target = None
        self.data.update(status=status, elapsed_seconds=round(time.monotonic()-self.started, 3),
                         capture_target_released=True, camera_lifetime="owned transient PIE copy; removed when PIE ends")
        if error:
            self.data["error"] = error
        self.save()


def main():
    prior = getattr(unreal, KEY, None)
    operation = ARGS.get("operation", "inspect")
    if operation in ("prepare", "cleanup"):
        if unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():
            raise RuntimeError("Stop PIE before preparing/removing the editor camera")
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if world.get_path_name().split(".", 1)[0] != "/Basketbroom/Maps/BB_Regulation":
            raise RuntimeError("Select the owned BB_Regulation map")
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        actors = [actor for actor in subsystem.get_all_level_actors() if actor.actor_has_tag(CAMERA_TAG)]
        if operation == "cleanup":
            for actor in actors:
                subsystem.destroy_actor(actor)
            return {"status": "cleaned", "cameras_removed": len(actors), "maps_saved": 0}
        if actors:
            raise RuntimeError("An owned capture camera is already staged")
        # RF_Transient actors are excluded from PIE duplication in this build.
        # Keep this explicitly owned fixture unsaved, then cleanup before cook.
        actor = subsystem.spawn_actor_from_class(unreal.SceneCapture2D, unreal.Vector(0, 0, 1500), transient=False)
        actor.set_editor_property("tags", [CAMERA_TAG])
        actor.set_actor_label("BB transient native chase review")
        component = actor.get_component_by_class(unreal.SceneCaptureComponent2D)
        component.set_editor_property("capture_every_frame", False)
        component.set_editor_property("capture_on_movement", False)
        return {"status": "prepared", "actor": actor.get_path_name(), "unsaved_editor_fixture": True, "maps_saved": 0}
    if operation == "inspect":
        return prior.data if prior else {"status": "not_started"}
    if operation == "stop":
        if prior and prior.data["status"] == "running":
            prior.finish("stopped")
        return prior.data if prior else {"status": "not_started"}
    if operation != "start":
        raise ValueError("Choose inspect, start, or stop")
    if prior and prior.data["status"] == "running":
        raise RuntimeError("A native chase preview is already active")
    preview = Preview()
    setattr(unreal, KEY, preview)
    try:
        preview.begin()
    except Exception:
        preview.finish("error", traceback.format_exc())
    return {"status": preview.data["status"], "report": str(REPORT)}


if __name__ == "__main__":
    RESULT = main()

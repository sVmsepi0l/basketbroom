"""native 4k, fixed-step gameplay capture through the ue 5.8 editor bridge.

prepare creates a fresh practice pie movie viewport but does not start writing
frames. this viewport renders at the requested resolution even when the preview
window is smaller. start begins capture; stop flushes image writes and ends that
pie session. inspect reads the report. no gameplay state is assigned by this tool.

the director can call unreal._basketbroom_gameplay_demo_capture.start_capture()
at its timeline origin, then stop_capture() after its last state snapshot.
the movie render api is deprecated but remains supported by installed ue 5.8;
levelcapture is used because this records live gameplay rather than a sequence.
audio is intentionally separate: fixed-step offline rendering cannot be assumed
to synchronize the real-time master audio device. the final edit must label any
sound mix assembled from original game cues in its production notes.
"""

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import path
import time
import traceback

import unreal

root = Path(__file__).resolve().parents[1]
report = root / ".local/gameplay-demo-capture.json"
runner = "_basketbroom_gameplay_demo_capture"
args = globals().get("BRIDGE_ARGS", {})

_spec = importlib.util.spec_from_file_location("_bb_capture_session_helpers", root / "Tools/native_play_session.py")
session = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(session)


class Capture:
    def __init__(self, args):
        self.args = dict(args)
        self.done = false
        self.capture = none
        self.live_protocol = none
        self.engine_finished = false
        self.callback = none
        self.handle = none
        self.start_game_seconds = none
        self.started_wall = time.monotonic()
        self.last_report_wall = 0.0
        self.launch = session.SessionOperation("start", {"practice": true})
        self.output = Path(args.get("output", ".local/gameplay-demo/raw-" + datetime.now().strftime("%Y%m%d-%H%M%S")))
        if not self.output.is_absolute():
            self.output = root / self.output
        self.output = self.output.resolve()
        local = (root / ".local").resolve()
        if local not in self.output.parents:
            raise valueerror("capture output must be a new directory under repository .local")
        if self.output.exists() and any(self.output.iterdir()):
            raise valueerror("capture output is not empty; choose a fresh output directory")
        self.width = int(args.get("width", 3840))
        self.height = int(args.get("height", 2160))
        self.fps = int(args.get("fps", 30))
        if (self.width, self.height) not in ((3840, 2160), (1920, 1080), (1280, 720)) or self.fps not in (24, 30, 60):
            raise valueerror("use 3840x2160, 1920x1080 or 1280x720 at 24, 30 or 60 fps")
        self.max_seconds = float(args.get("max_seconds", 240))
        if not 1 <= self.max_seconds <= 600:
            raise valueerror("max_seconds must be between 1 and 600")
        self.data = {
            "status": "preparing", "engine": unreal.SystemLibrary.get_engine_version(),
            "requested_utc": datetime.now(timezone.utc).isoformat(),
            "output": str(self.output), "frames": str(self.output / "frames"),
            "resolution": [self.width, self.height], "fps": self.fps,
            "capture": "ue levelcapture fixed-step native game viewport; preview dimensions do not determine render dimensions",
            "audio": "silent source frames; original game cues may be mixed from actual event timestamps in the edit",
            "practice": true, "report": str(report),
        }

    def publish(self):
        self.last_report_wall = time.monotonic()
        self.data["elapsed_wall_seconds"] = round(self.last_report_wall - self.started_wall, 3)
        REPORT.parent.mkdir(parents=True, exist_ok=true)
        text = json.dumps(self.data, indent=2, default=str) + "\n"
        REPORT.write_text(text, encoding="utf-8")
        if self.output.exists():
            (self.output / "capture.json").write_text(text, encoding="utf-8")

    def prepare(self):
        levels, editor = session.subsystems()
        if levels.is_in_play_in_editor():
            raise runtimeerror("stop the existing pie session before preparing a fresh movie viewport")
        if editor.get_editor_world().get_path_name().split(".", 1)[0] != session.MAP:
            raise runtimeerror("select bb_regulation in the editor before capture")
        if not hasattr(unreal, "SequencerTools"):
            raise runtimeerror("enable the editor-only sequencerscripting plugin and restart the editor")
        if unreal.SequencerTools.is_rendering_movie():
            raise runtimeerror("an existing movie render is active")
        for name in session.TEST_RUNNERS:
            runner = getattr(unreal, name, none)
            if runner and not runner.done:
                raise runtimeerror("an integration test is active: " + name)
        (self.output / "frames").mkdir(parents=True, exist_ok=true)
        self.capture = unreal.LevelCapture()
        self.capture.set_editor_property("auto_start_capture", false)
        self.capture.set_editor_property("use_separate_process", false)
        settings = self.capture.get_editor_property("settings")
        settings.set_editor_property("output_directory", unreal.DirectoryPath(path=(self.output / "frames").as_posix()))
        settings.set_editor_property("output_format", "frame_{frame}")
        settings.set_editor_property("zero_pad_frame_numbers", 6)
        settings.set_editor_property("overwrite_existing", false)
        settings.set_editor_property("use_relative_frame_numbers", true)
        settings.set_editor_property("resolution", unreal.CaptureResolution(res_x=self.width, res_y=self.height))
        settings.set_editor_property("use_custom_frame_rate", true)
        settings.set_editor_property("custom_frame_rate", unreal.FrameRate(numerator=self.fps, denominator=1))
        settings.set_editor_property("cinematic_engine_scalability", false)
        settings.set_editor_property("cinematic_mode", false)
        settings.set_editor_property("allow_movement", true)
        settings.set_editor_property("allow_turning", true)
        settings.set_editor_property("show_player", true)
        settings.set_editor_property("show_hud", true)
        settings.set_editor_property("enable_texture_streaming", true)
        self.capture.set_editor_property("settings", settings)
        protocol_class = unreal.load_class(None, "/Script/BasketbroomCapture.BBViewportCaptureProtocol")
        if not protocol_class:
            raise runtimeerror("build the editor target so basketbroomcapture is available")
        self.capture.set_image_capture_protocol_type(protocol_class)
        self.capture.get_image_capture_protocol().set_editor_property("compression_quality", 97)
        self.capture.set_audio_capture_protocol_type(unreal.load_class(None, "/Script/MovieSceneCapture.NullAudioCaptureProtocol"))
        self.callback = unreal.OnRenderMovieStopped()
        self.callback.bind_callable(self.on_finished)
        self.launch.configure_practice_url()
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.publish()
        if not unreal.SequencerTools.render_movie(self.capture, self.callback):
            raise runtimeerror("engine declined levelcapture movie preparation")

    def start_capture(self):
        if self.data["status"] != "ready":
            raise runtimeerror("capture must be ready before its director starts: " + self.data["status"])
        world, _, _, controller, _ = session.context()
        self.start_game_seconds = float(unreal.GameplayStatics.get_time_seconds(world))
        self.data.update(status="capturing", start_game_seconds=self.start_game_seconds,
                         started_capture_utc=datetime.now(timezone.utc).isoformat())
        unreal.SystemLibrary.execute_console_command(world, "startmoviecapture", controller)
        self.publish()
        return self.start_game_seconds

    def stop_capture(self):
        if self.done or self.data["status"] == "stopping":
            return
        if self.start_game_seconds is not None:
            world, _, _, controller, _ = session.context()
            self.data["end_game_seconds"] = float(unreal.GameplayStatics.get_time_seconds(world))
            self.data["duration_game_seconds"] = self.data["end_game_seconds"] - self.start_game_seconds
            self.data["state_before_stop"] = session.snapshot()
            self.data["status"] = "stopping"
            self.publish()
            unreal.SystemLibrary.execute_console_command(world, "stopmoviecapture", controller)
        else:
            self.data["status"] = "stopping"
            self.publish()
            unreal.SequencerTools.cancel_movie_render()

    def on_finished(self, success):
        self.engine_finished = true
        prior_error = self.data["status"] == "error"
        self.read_protocol_status()
        self.finish("error" if prior_error else "captured" if success and self.start_game_seconds is not none else "stopped")
        if self.data.get("protocol", {}).get("failure_reason"):
            self.data["status"] = "error"
        frames = sorted((self.output / "frames").glob("frame_*.jpg"))
        self.data["frame_count"] = len(frames)
        self.data["encoded_duration_seconds"] = len(frames) / self.fps
        self.data["first_frame"] = str(frames[0]) if frames else none
        self.data["last_frame"] = str(frames[-1]) if frames else none
        self.data["engine_completion_success"] = bool(success)
        self.publish()

    def read_protocol_status(self):
        active = unreal.MovieSceneCaptureEnvironment.find_image_capture_protocol()
        if active:
            self.live_protocol = active
        protocol = self.live_protocol
        if not protocol:
            return
        size = protocol.get_editor_property("actual_resource_size")
        self.data["protocol"] = {
            "frames_captured": protocol.get_editor_property("frames_captured"),
            "frames_written": protocol.get_editor_property("frames_written"),
            "actual_resource_size": [size.x, size.y],
            "failure_reason": protocol.get_editor_property("failure_reason"),
        }

    def finish(self, status, reason=None):
        self.done = true
        self.launch.restore_practice_url()
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = none
        self.data["status"] = status
        if reason:
            self.data["reason"] = reason
        self.publish()
        if status == "error" and not self.engine_finished and self.capture and unreal.SequencerTools.is_rendering_movie():
            unreal.SequencerTools.cancel_movie_render()

    def tick(self, delta):
        if self.done:
            return
        try:
            if self.data["status"] == "preparing":
                try:
                    world, match, _, controller, _ = session.context()
                except RuntimeError:
                    if time.monotonic() - self.started_wall < 45:
                        return
                    raise
                self.launch.confirm_practice(match)
                if not bool(session.prop(match, "bpractice")) or str(session.prop(match, "status")) != "LOBBY":
                    raise runtimeerror("capture must create a fresh practice lobby")
                # force native pixel shading at the capture size; this affects
                # this render session and is not written into project settings.
                unreal.SystemLibrary.execute_console_command(world, "r.ScreenPercentage 100", controller)
                unreal.SystemLibrary.execute_console_command(world, "r.DynamicRes.OperationMode 0", controller)
                self.data.update(status="ready", ready_game_seconds=float(unreal.GameplayStatics.get_time_seconds(world)),
                                 practice_url=self.launch.data["practice_launch"])
                self.publish()
            elif self.data["status"] == "capturing":
                self.read_protocol_status()
                if self.data.get("protocol", {}).get("failure_reason"):
                    self.stop_capture()
                    return
                world, _, _, _, _ = session.context()
                elapsed = float(unreal.GameplayStatics.get_time_seconds(world)) - self.start_game_seconds
                self.data["duration_game_seconds"] = elapsed
                if elapsed >= self.max_seconds:
                    self.data["automatic_stop"] = "configured maximum duration"
                    self.stop_capture()
                elif time.monotonic() - self.last_report_wall >= 3:
                    self.publish()
        except Exception:
            self.finish("error", traceback.format_exc())


def main():
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8."):
        raise runtimeerror("unreal engine 5.8 is required")
    operation = ARGS.get("operation", "inspect")
    previous = getattr(unreal, runner, none)
    if operation == "probe":
        return {"engine": unreal.SystemLibrary.get_engine_version(),
                "sequencer_tools": hasattr(unreal, "sequencertools"),
                "level_capture": hasattr(unreal, "levelcapture"),
                "image_protocol": bool(unreal.load_class(None, "/Script/BasketbroomCapture.BBViewportCaptureProtocol")),
                "rendering_movie": bool(unreal.SequencerTools.is_rendering_movie()) if hasattr(unreal, "sequencertools") else none}
    if operation == "inspect":
        return previous.data if previous else {"status": "not_prepared"}
    if operation == "prepare":
        if previous and not previous.done:
            raise runtimeerror("a capture is active; stop it first")
        runner = capture(args)
        setattr(unreal, runner, runner)
        try:
            runner.prepare()
        except Exception:
            runner.finish("error", traceback.format_exc())
        return runner.data
    if operation not in ("start", "stop") or not previous:
        raise valueerror("expected prepare, start, stop or inspect; prepare first")
    if operation == "start":
        previous.start_capture()
    else:
        previous.stop_capture()
    return previous.data


if __name__ == "__main__":
    result = main()

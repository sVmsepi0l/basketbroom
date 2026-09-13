"""Native 4K, fixed-step gameplay capture through the UE 5.8 editor bridge.

prepare creates a fresh Practice PIE movie viewport but does not start writing
frames. This viewport renders at the requested resolution even when the preview
window is smaller. start begins capture; stop flushes image writes and ends that
PIE session. inspect reads the report. No gameplay state is assigned by this tool.

The director can call unreal._basketbroom_gameplay_demo_capture.start_capture()
at its timeline origin, then stop_capture() after its last state snapshot.
The movie render API is deprecated but remains supported by installed UE 5.8;
LevelCapture is used because this records live gameplay rather than a sequence.
Audio is intentionally separate: fixed-step offline rendering cannot be assumed
to synchronize the real-time master audio device. The final edit must label any
sound mix assembled from original game cues in its production notes.
"""

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time
import traceback

import unreal

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/gameplay-demo-capture.json"
RUNNER = "_basketbroom_gameplay_demo_capture"
ARGS = globals().get("BRIDGE_ARGS", {})

_spec = importlib.util.spec_from_file_location("_bb_capture_session_helpers", ROOT / "Tools/native_play_session.py")
session = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(session)


class Capture:
    def __init__(self, args):
        self.args = dict(args)
        self.done = False
        self.capture = None
        self.live_protocol = None
        self.engine_finished = False
        self.callback = None
        self.handle = None
        self.start_game_seconds = None
        self.started_wall = time.monotonic()
        self.last_report_wall = 0.0
        self.launch = session.SessionOperation("start", {"practice": True})
        self.output = Path(args.get("output", ".local/gameplay-demo/raw-" + datetime.now().strftime("%Y%m%d-%H%M%S")))
        if not self.output.is_absolute():
            self.output = ROOT / self.output
        self.output = self.output.resolve()
        local = (ROOT / ".local").resolve()
        if local not in self.output.parents:
            raise ValueError("Capture output must be a new directory under repository .local")
        if self.output.exists() and any(self.output.iterdir()):
            raise ValueError("Capture output is not empty; choose a fresh output directory")
        self.width = int(args.get("width", 3840))
        self.height = int(args.get("height", 2160))
        self.fps = int(args.get("fps", 30))
        if (self.width, self.height) not in ((3840, 2160), (1920, 1080), (1280, 720)) or self.fps not in (24, 30, 60):
            raise ValueError("Use 3840x2160, 1920x1080 or 1280x720 at 24, 30 or 60 fps")
        self.max_seconds = float(args.get("max_seconds", 240))
        if not 1 <= self.max_seconds <= 600:
            raise ValueError("max_seconds must be between 1 and 600")
        self.data = {
            "status": "preparing", "engine": unreal.SystemLibrary.get_engine_version(),
            "requested_utc": datetime.now(timezone.utc).isoformat(),
            "output": str(self.output), "frames": str(self.output / "frames"),
            "resolution": [self.width, self.height], "fps": self.fps,
            "capture": "UE LevelCapture fixed-step native game viewport; preview dimensions do not determine render dimensions",
            "audio": "silent source frames; original game cues may be mixed from actual event timestamps in the edit",
            "practice": True, "report": str(REPORT),
        }

    def publish(self):
        self.last_report_wall = time.monotonic()
        self.data["elapsed_wall_seconds"] = round(self.last_report_wall - self.started_wall, 3)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.data, indent=2, default=str) + "\n"
        REPORT.write_text(text, encoding="utf-8")
        if self.output.exists():
            (self.output / "capture.json").write_text(text, encoding="utf-8")

    def prepare(self):
        levels, editor = session.subsystems()
        if levels.is_in_play_in_editor():
            raise RuntimeError("Stop the existing PIE session before preparing a fresh movie viewport")
        if editor.get_editor_world().get_path_name().split(".", 1)[0] != session.MAP:
            raise RuntimeError("Select BB_Regulation in the editor before capture")
        if not hasattr(unreal, "SequencerTools"):
            raise RuntimeError("Enable the Editor-only SequencerScripting plugin and restart the editor")
        if unreal.SequencerTools.is_rendering_movie():
            raise RuntimeError("An existing movie render is active")
        for name in session.TEST_RUNNERS:
            runner = getattr(unreal, name, None)
            if runner and not runner.done:
                raise RuntimeError("An integration test is active: " + name)
        (self.output / "frames").mkdir(parents=True, exist_ok=True)
        self.capture = unreal.LevelCapture()
        self.capture.set_editor_property("auto_start_capture", False)
        self.capture.set_editor_property("use_separate_process", False)
        settings = self.capture.get_editor_property("settings")
        settings.set_editor_property("output_directory", unreal.DirectoryPath(path=(self.output / "frames").as_posix()))
        settings.set_editor_property("output_format", "frame_{frame}")
        settings.set_editor_property("zero_pad_frame_numbers", 6)
        settings.set_editor_property("overwrite_existing", False)
        settings.set_editor_property("use_relative_frame_numbers", True)
        settings.set_editor_property("resolution", unreal.CaptureResolution(res_x=self.width, res_y=self.height))
        settings.set_editor_property("use_custom_frame_rate", True)
        settings.set_editor_property("custom_frame_rate", unreal.FrameRate(numerator=self.fps, denominator=1))
        settings.set_editor_property("cinematic_engine_scalability", False)
        settings.set_editor_property("cinematic_mode", False)
        settings.set_editor_property("allow_movement", True)
        settings.set_editor_property("allow_turning", True)
        settings.set_editor_property("show_player", True)
        settings.set_editor_property("show_hud", True)
        settings.set_editor_property("enable_texture_streaming", True)
        self.capture.set_editor_property("settings", settings)
        protocol_class = unreal.load_class(None, "/Script/BasketbroomCapture.BBViewportCaptureProtocol")
        if not protocol_class:
            raise RuntimeError("Build the Editor target so BasketbroomCapture is available")
        self.capture.set_image_capture_protocol_type(protocol_class)
        self.capture.get_image_capture_protocol().set_editor_property("compression_quality", 97)
        self.capture.set_audio_capture_protocol_type(unreal.load_class(None, "/Script/MovieSceneCapture.NullAudioCaptureProtocol"))
        self.callback = unreal.OnRenderMovieStopped()
        self.callback.bind_callable(self.on_finished)
        self.launch.configure_practice_url()
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.publish()
        if not unreal.SequencerTools.render_movie(self.capture, self.callback):
            raise RuntimeError("Engine declined LevelCapture movie preparation")

    def start_capture(self):
        if self.data["status"] != "ready":
            raise RuntimeError("Capture must be ready before its director starts: " + self.data["status"])
        world, _, _, controller, _ = session.context()
        self.start_game_seconds = float(unreal.GameplayStatics.get_time_seconds(world))
        self.data.update(status="capturing", start_game_seconds=self.start_game_seconds,
                         started_capture_utc=datetime.now(timezone.utc).isoformat())
        unreal.SystemLibrary.execute_console_command(world, "StartMovieCapture", controller)
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
            unreal.SystemLibrary.execute_console_command(world, "StopMovieCapture", controller)
        else:
            self.data["status"] = "stopping"
            self.publish()
            unreal.SequencerTools.cancel_movie_render()

    def on_finished(self, success):
        self.engine_finished = True
        prior_error = self.data["status"] == "error"
        self.read_protocol_status()
        self.finish("error" if prior_error else "captured" if success and self.start_game_seconds is not None else "stopped")
        if self.data.get("protocol", {}).get("failure_reason"):
            self.data["status"] = "error"
        frames = sorted((self.output / "frames").glob("frame_*.jpg"))
        self.data["frame_count"] = len(frames)
        self.data["encoded_duration_seconds"] = len(frames) / self.fps
        self.data["first_frame"] = str(frames[0]) if frames else None
        self.data["last_frame"] = str(frames[-1]) if frames else None
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
        self.done = True
        self.launch.restore_practice_url()
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
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
                if not bool(session.prop(match, "bPractice")) or str(session.prop(match, "Status")) != "LOBBY":
                    raise RuntimeError("Capture must create a fresh Practice lobby")
                # Force native pixel shading at the capture size; this affects
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
        raise RuntimeError("Unreal Engine 5.8 is required")
    operation = ARGS.get("operation", "inspect")
    previous = getattr(unreal, RUNNER, None)
    if operation == "probe":
        return {"engine": unreal.SystemLibrary.get_engine_version(),
                "sequencer_tools": hasattr(unreal, "SequencerTools"),
                "level_capture": hasattr(unreal, "LevelCapture"),
                "image_protocol": bool(unreal.load_class(None, "/Script/BasketbroomCapture.BBViewportCaptureProtocol")),
                "rendering_movie": bool(unreal.SequencerTools.is_rendering_movie()) if hasattr(unreal, "SequencerTools") else None}
    if operation == "inspect":
        return previous.data if previous else {"status": "not_prepared"}
    if operation == "prepare":
        if previous and not previous.done:
            raise RuntimeError("A capture is active; stop it first")
        runner = Capture(ARGS)
        setattr(unreal, RUNNER, runner)
        try:
            runner.prepare()
        except Exception:
            runner.finish("error", traceback.format_exc())
        return runner.data
    if operation not in ("start", "stop") or not previous:
        raise ValueError("Expected prepare, start, stop or inspect; prepare first")
    if operation == "start":
        previous.start_capture()
    else:
        previous.stop_capture()
    return previous.data


if __name__ == "__main__":
    RESULT = main()

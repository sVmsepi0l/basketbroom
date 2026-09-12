"""Start/stop/inspect/capture the native regulation PIE session.

Editor bridge examples (all mutations are confined to PIE copies):
  {"operation": "start", "start_live": true}
  {"operation": "start", "position": 4, "start_live": false}
  {"operation": "inspect"}
  {"operation": "capture", "filename": "Docs/Screenshots/native-flight.png",
   "presentation": {"location": [-4300, -1500, 1800], "rotation": [0, 12, 0]}}
  {"operation": "capture", "position": 5, "filename": "Docs/Screenshots/native-scout.png"}
  {"operation": "stop"}

Optional presentation.camera_actor_label selects an existing PIE CameraActor;
otherwise the location/rotation fixture moves the native rider's point of view.
Capture waits two actual game-time frames after preparation/live-start, requests
HighResShot, and verifies a fresh complete PNG. A written file still needs visual
review. Optional position (0..5) selects a lobby/stoppage role through ordinary
queued native input and waits for actual acceptance before starting/capturing.
The helper never assigns scores, clocks, ball states, role fields, or rules.
It does not load/save editor maps: BB_Regulation must already be selected.
"""

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import struct
import time
import traceback

import unreal

ROOT = Path(__file__).resolve().parents[1]
MAP = "/Basketbroom/Maps/BB_Regulation"
REPORT = ROOT / ".local/native-play-session.json"
ARGS = globals().get("BRIDGE_ARGS", {})
RUNNER_NAME = "_basketbroom_native_play_session"
TEST_RUNNERS = ("_basketbroom_native_test", "_basketbroom_native_network_test", "_basketbroom_native_snitch_test",
                "_basketbroom_native_opening_test", "_basketbroom_bludger_test", "_basketbroom_native_audio_test",
                "_basketbroom_playable_test", "_basketbroom_bot_test")


def prop(obj, name):
    aliases = [name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()]
    if name.startswith("b") and len(name) > 1 and name[1].isupper():
        aliases.append(re.sub(r"(?<!^)(?=[A-Z])", "_", name[1:]).lower())
    for alias in aliases:
        try:
            return obj.get_editor_property(alias)
        except Exception:
            pass
    raise RuntimeError("Missing native read-only property: " + name)


def xyz(point):
    return [round(float(point.x), 3), round(float(point.y), 3), round(float(point.z), 3)]


def rotation(rot):
    return [round(float(rot.pitch), 3), round(float(rot.yaw), 3), round(float(rot.roll), 3)]


def triple(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(label + " must contain three finite numbers")
    result = [float(item) for item in value]
    if not all(math.isfinite(item) for item in result):
        raise ValueError(label + " must contain three finite numbers")
    return result


def write_report(data):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def subsystems():
    return (unreal.get_editor_subsystem(unreal.LevelEditorSubsystem),
            unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem))


def context():
    """An explicit PIE + exact map + native class guard for every mutation."""
    levels, editor = subsystems()
    if not levels.is_in_play_in_editor():
        raise RuntimeError("A native Play In Editor session is required")
    world = editor.get_game_world()
    if world is None or not re.fullmatch(r"/Basketbroom/Maps/UEDPIE_\d+_BB_Regulation\.BB_Regulation", world.get_path_name()):
        raise RuntimeError("Only a PIE copy of BB_Regulation is supported")
    game_mode = unreal.GameplayStatics.get_game_mode(world)
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    if (not game_mode or game_mode.get_class().get_path_name() != "/Script/BasketbroomRuntime.BBGameMode"
            or not pawn or pawn.get_class().get_path_name() != "/Script/BasketbroomRuntime.BBRiderCharacter"
            or not controller):
        raise RuntimeError("The native authority GameMode and local rider are not ready")
    match_class = unreal.load_class(None, "/Script/BasketbroomRuntime.BBMatchState")
    ball_class = unreal.load_class(None, "/Script/BasketbroomRuntime.BBBall")
    states = unreal.GameplayStatics.get_all_actors_of_class(world, match_class)
    if len(states) != 1:
        raise RuntimeError("Expected exactly one native match state")
    balls = list(unreal.GameplayStatics.get_all_actors_of_class(world, ball_class))
    if len(balls) != 7:
        raise RuntimeError("Expected all seven native balls")
    return world, states[0], pawn, controller, balls


def snapshot():
    world, match, pawn, controller, balls = context()
    camera = unreal.GameplayStatics.get_player_camera_manager(world, 0)
    hud = controller.get_hud()
    return {
        "world": world.get_path_name(),
        "game_seconds": round(float(unreal.GameplayStatics.get_time_seconds(world)), 3),
        "pawn": pawn.get_class().get_path_name(),
        "hud": hud.get_class().get_path_name() if hud else None,
        "rider": {"position_cm": xyz(pawn.get_actor_location()),
                  "velocity_cm_s": xyz(pawn.get_velocity()),
                  "control_rotation_pitch_yaw_roll": rotation(controller.get_control_rotation()),
                  "team": int(prop(pawn, "TeamIndex")), "role": int(prop(pawn, "Position")),
                  "slot": int(prop(pawn, "RosterIndex"))},
        "camera": {"location_cm": xyz(camera.get_camera_location()),
                   "rotation_pitch_yaw_roll": rotation(camera.get_camera_rotation())} if camera else None,
        "match": {name: prop(match, name) for name in
                  ("TealScore", "CopperScore", "Quarter", "SecondsLeft", "Phase", "Status",
                   "bPractice", "bLive", "Winner", "Announcement")},
        "balls": [{"index": int(prop(ball, "BallIndex")), "position_cm": xyz(ball.get_actor_location()),
                   "active": bool(prop(ball, "bActive")), "status": str(prop(ball, "BallStatus")),
                   "holder": prop(ball, "Holder").get_path_name() if prop(ball, "Holder") else None,
                   "capture_progress": float(prop(ball, "CaptureProgress")),
                   "return_seconds": float(prop(ball, "ReturnIn"))}
                  for ball in sorted(balls, key=lambda value: int(prop(value, "BallIndex")))],
    }


class SessionOperation:
    def __init__(self, operation, args):
        self.operation, self.args = operation, dict(args)
        self.started = time.monotonic()
        self.done = False
        self.handle = None
        self.phase = "waiting_for_world"
        self.prepared = False
        self.live_requested = False
        self.position = self.args.get("position")
        self.position_confirmed = self.position is None
        self.position_request_time = None
        self.position_observed_time = None
        self.role_settle_start = None
        self.live_request_time = None
        self.last_game_time = None
        self.game_frames = 0
        self.capture_baseline = None
        self.output = None
        self.data = {"status": "requested", "operation": operation,
                     "engine": unreal.SystemLibrary.get_engine_version(),
                     "requested_utc": datetime.now(timezone.utc).isoformat(),
                     "scope": "native authority PIE session; optional ordinary role/start input and presentation",
                     "report": str(REPORT), "presentation_fixture": None}

    def begin(self):
        if self.position is not None and (type(self.position) is not int or not 0 <= self.position <= 5):
            raise ValueError("position must be an integer from 0 through 5")
        levels, editor = subsystems()
        if not levels.is_in_play_in_editor():
            if self.operation != "start":
                raise RuntimeError("Start native PIE before capture")
            selected = editor.get_editor_world()
            if selected is None or selected.get_path_name().split(".", 1)[0] != MAP:
                raise RuntimeError("Select BB_Regulation before starting; the helper does not load maps")
            if unreal.load_class(None, "/Script/BasketbroomRuntime.BBGameMode") is None:
                raise RuntimeError("The compiled native module must be loaded")
            levels.editor_request_begin_play()
        else:
            context()
        if self.operation == "capture":
            self.output = Path(self.args.get("filename", "Docs/Screenshots/native-flight.png"))
            if not self.output.is_absolute():
                self.output = ROOT / self.output
            self.output = self.output.resolve()
            if ROOT not in self.output.parents or self.output.suffix.lower() != ".png":
                raise ValueError("Capture filename must be a PNG inside this repository")
            if any(character in str(self.output) for character in ('"', '\n', '\r')):
                raise ValueError("Capture filename contains console-command delimiters")
            self.output.parent.mkdir(parents=True, exist_ok=True)
            self.capture_baseline = self.output.stat().st_mtime_ns if self.output.exists() else None
            self.width, self.height = int(self.args.get("width", 1600)), int(self.args.get("height", 900))
            if not (640 <= self.width <= 3840 and 480 <= self.height <= 2160):
                raise ValueError("Capture resolution must be within 640x480 and 3840x2160")
            self.data.update(output=str(self.output), width=self.width, height=self.height,
                             visual_review_required=True)
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.publish()

    def publish(self):
        self.data.update(phase=self.phase, elapsed_wall_seconds=round(time.monotonic() - self.started, 3))
        write_report(self.data)

    def finish(self, status, reason=None):
        self.done = True
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        self.data["status"] = status
        if reason:
            self.data["reason"] = reason
        self.publish()

    def prepare(self, world, pawn, controller):
        fixture = self.args.get("presentation")
        if fixture is None:
            return
        if not isinstance(fixture, dict):
            raise ValueError("presentation must be an object")
        before = snapshot()
        actor = pawn
        label = fixture.get("camera_actor_label")
        if label:
            cameras = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CameraActor)
            matches = [camera for camera in cameras if camera.get_actor_label() == label]
            if len(matches) != 1:
                raise RuntimeError("Expected one PIE CameraActor with the requested label")
            actor = matches[0]
        if "location" in fixture:
            position = triple(fixture["location"], "presentation.location")
            if actor == pawn:
                pawn.get_component_by_class(unreal.CharacterMovementComponent).stop_movement_immediately()
            actor.set_actor_location(unreal.Vector(*position), False, True)
        if "rotation" in fixture:
            pitch, yaw, roll = triple(fixture["rotation"], "presentation.rotation")
            view = unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll)
            if actor == pawn:
                controller.set_control_rotation(view)
            else:
                actor.set_actor_rotation(view, True)
        if actor != pawn:
            controller.set_view_target_with_blend(actor, 0.0)
        self.data["presentation_fixture"] = {"actor": actor.get_path_name(), "requested": fixture,
                                              "before_rider": before["rider"], "before_camera": before["camera"],
                                              "note": "PIE transform/view fixture; no score, clock, ball or rule state changed"}

    def select_position(self, match, pawn, game_time):
        if self.position_confirmed:
            # A confirmed queued role request has just used the shared native
            # action throttle. Give it 0.1 game seconds before queuing ready.
            return self.position_observed_time is None or game_time - self.position_observed_time >= .1
        actual = int(prop(pawn, "Position"))
        if actual == self.position:
            self.position_confirmed = True
            self.position_observed_time = game_time
            self.data["position_selection"] = {
                **self.data.get("position_selection", {}), "requested": self.position, "observed": actual,
                "status": "confirmed", "confirmed_game_seconds": game_time,
                "request_queued": self.position_request_time is not None,
            }
            self.phase = "waiting_after_position"
            self.publish()
            return False
        status = str(prop(match, "Status"))
        if prop(match, "bLive") or status not in ("LOBBY", "STOPPAGE"):
            raise RuntimeError("Position selection requires the lobby or an ordinary stoppage; observed " + status)
        if self.position_request_time is None:
            if self.role_settle_start is None:
                self.role_settle_start = game_time
                self.phase = "waiting_to_request_position"
                self.data["position_selection"] = {"requested": self.position, "before": actual,
                                                   "status": "waiting for input spacing"}
                self.publish()
                return False
            if game_time - self.role_settle_start < .1:
                return False
            if not pawn.development_request_action(2, self.position):
                raise RuntimeError("Native position request was not queued")
            self.position_request_time = game_time
            self.phase = "waiting_for_position"
            self.data["position_selection"].update(status="queued through native ordinary input bridge",
                                                    queued_game_seconds=game_time)
            self.publish()
            return False
        if game_time - self.position_request_time > 5:
            raise RuntimeError("Native position selection was not accepted within five game seconds; observed role "
                               + str(actual) + ", announcement: " + str(prop(match, "Announcement")))
        return False

    def tick(self, delta):
        if self.done:
            return
        try:
            if time.monotonic() - self.started > float(self.args.get("timeout_seconds", 60)):
                raise TimeoutError("Native session operation timed out")
            try:
                world, match, pawn, controller, _ = context()
            except RuntimeError:
                if self.phase == "waiting_for_world" and time.monotonic() - self.started < 20:
                    return
                raise
            game_time = float(unreal.GameplayStatics.get_time_seconds(world))
            if not self.select_position(match, pawn, game_time):
                return
            if not self.prepared:
                if self.args.get("start_live", self.operation == "start") and not prop(match, "bLive"):
                    if self.live_requested:
                        if game_time - self.live_request_time > 5:
                            raise RuntimeError("Native host start request was not accepted within five game seconds")
                        return
                    if not pawn.development_request_action(4, 0):
                        raise RuntimeError("Native host start request was not queued")
                    self.live_requested = True
                    self.live_request_time = game_time
                    self.data["host_start"] = "queued through native ordinary input bridge"
                    self.phase = "waiting_for_live"
                    self.publish()
                    return
                # Kickoff changes native opening positions. Apply the camera
                # fixture after live-start acceptance so it is not overwritten.
                self.prepare(world, pawn, controller)
                self.prepared = True
                self.phase = "waiting_for_camera_frames"
                self.last_game_time = game_time
                self.game_frames = 0
                self.publish()
                return
            if self.phase == "waiting_for_camera_frames":
                game_time = float(unreal.GameplayStatics.get_time_seconds(world))
                if game_time > self.last_game_time:
                    self.last_game_time = game_time
                    self.game_frames += 1
                if self.game_frames < 2:
                    return
                self.data["settled_game_frames"] = self.game_frames
                self.data["state"] = snapshot()
                if self.operation == "start":
                    self.finish("ready")
                    return
                command = 'HighResShot %dx%d filename="%s"' % (self.width, self.height, self.output.as_posix())
                self.data["capture_command"] = command
                unreal.SystemLibrary.execute_console_command(world, command, controller)
                self.phase = "waiting_for_png"
                self.publish()
                return
            if self.phase == "waiting_for_png" and self.output.exists():
                stat = self.output.stat()
                if stat.st_mtime_ns == self.capture_baseline or stat.st_size < 40:
                    return
                payload = self.output.read_bytes()
                if not (payload.startswith(b"\x89PNG\r\n\x1a\n")
                        and payload.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82")):
                    return
                dimensions = list(struct.unpack(">II", payload[16:24]))
                if dimensions != [self.width, self.height]:
                    raise RuntimeError("Capture has unexpected PNG dimensions: " + str(dimensions))
                self.data.update(png_bytes=len(payload), png_dimensions=dimensions,
                                 note="Actual engine PNG written. Inspect it before claiming HUD/render quality.")
                self.finish("captured")
        except Exception:
            self.finish("error", traceback.format_exc())


def main():
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8."):
        raise RuntimeError("This helper requires Unreal Engine 5.8")
    operation = ARGS.get("operation", "inspect")
    if operation not in ("start", "stop", "inspect", "capture"):
        raise ValueError("Expected operation start, stop, inspect, or capture")
    if "position" in ARGS and operation not in ("start", "capture"):
        raise ValueError("position is supported only for start or capture")
    if operation != "inspect":
        for name in TEST_RUNNERS:
            runner = getattr(unreal, name, None)
            if runner and not runner.done:
                raise RuntimeError("Wait for the active integration test before changing PIE: " + name)
    previous = getattr(unreal, RUNNER_NAME, None)
    if previous and not previous.done and operation != "stop":
        raise RuntimeError("A native session operation is still running; read its report first")
    if operation == "stop":
        if previous and not previous.done:
            previous.finish("cancelled", "Explicit stop requested")
        levels, _ = subsystems()
        data = {"operation": operation, "status": "already_stopped"}
        if levels.is_in_play_in_editor():
            data["state_before_stop"] = snapshot()
            levels.editor_request_end_play()
            data["status"] = "stop_requested"
        write_report(data)
        return data
    if operation == "inspect":
        data = {"operation": operation, "status": "inspected", "state": snapshot()}
        write_report(data)
        return data
    runner = SessionOperation(operation, ARGS)
    setattr(unreal, RUNNER_NAME, runner)
    try:
        runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
    return runner.data


if __name__ == "__main__":
    RESULT = main()

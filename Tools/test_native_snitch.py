"""Native Snitch release/catch/result/rematch checks in disposable practice PIE.

Run in the staged BB_Regulation UE5.8 editor with PIE stopped. If this engine
omits the PlayNetMode Python enum, configure Play As Listen Server through the
UI or normal editor config while the editor is closed. Pass
settings_already_configured=True and settings_source="editor_ui" (default) or
"editor_config", matching the actual route as with test_native_network.py. The suite
sets the live EditorEngine's editable InEditorGameURLOptions to include
'?Practice=1' and one in-process player, then restores all settings it changed.
AdditionalServerGameOptions only reaches new-process launches in UE5.8.
The suite verifies the resulting bPractice flag before exercising the Snitch.

Only the owned PIE world's time dilation changes: 8x to approach the release,
1x across 60 live seconds, 0.1x during capture sampling, 1x for certification.
No score, clock, rules, ball activation, capture progress, or ownership is set.
The hold fixture follows the actual Snitch; physical piloting is not validated.
Outside Unreal, --list reports the plan as NOT_RUN.
"""

import json
from pathlib import Path
import re
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "Tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "Tools"))
from test_native_playable import NativePlayableTests, prop, unreal
from test_native_network import net_mode_restore_actions

REPORT = ROOT / ".local/native-snitch-test-results.json"
ARGS = globals().get("BRIDGE_ARGS", {})
TESTS = (
    "native_practice_configuration", "sixteen_riders_seven_balls",
    "snitch_initially_scheduled", "host_selects_scout", "practice_live_clock_starts",
    "snitch_absent_before_sixty_live_seconds", "snitch_releases_at_sixty_live_seconds",
    "release_does_not_award_points", "snitch_partial_hold_progress",
    "snitch_release_resets_hold", "snitch_continuous_catch_awards_150",
    "snitch_catch_enters_review", "review_certifies_correct_winner",
    "host_enter_starts_practice_rematch", "rematch_resets_scores_and_clocks",
    "rematch_preserves_actor_roster_identities", "rematch_clears_held_and_stun_state",
    "rematch_reschedules_snitch",
    "play_settings_restored_and_pie_ended",
)


def external_net_mode_provenance(source="editor_ui"):
    """Record the declared external route; this does not read an absent enum."""
    source = str(source)
    if source not in ("editor_ui", "editor_config"):
        raise ValueError("Unknown preconfigured Play Net Mode source")
    result = {"net_mode_configuration_source": source,
              "net_mode_configured_in_editor": source == "editor_ui"}
    if source == "editor_config":
        result["net_mode_config_entry"] = {
            "file": "EditorPerProjectUserSettings.ini", "section": "/Script/UnrealEd.LevelEditorPlaySettings",
            "key": "PlayNetMode", "declared_value": "PIE_ListenServer",
            "verification": "Subsequent native world authority and owning-client checks; no absent enum readback is claimed",
        }
    return result


def setting_slot(obj, name):
    aliases = [name, re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()]
    if name.startswith("b") and len(name) > 1 and name[1].isupper():
        aliases.append(re.sub(r"(?<!^)(?=[A-Z])", "_", name[1:]).lower())
    for alias in aliases:
        try:
            return alias, obj.get_editor_property(alias)
        except Exception:
            pass
    raise RuntimeError("Required editable PIE setting is not exposed: " + name)


class NativeSnitchTests(NativePlayableTests):
    def __init__(self):
        self.settings = None
        self.saved_settings = {}
        self.settings_restored = False
        self.editor_engine = None
        self.editor_url_key = None
        self.original_editor_url = None
        self.editor_url_restored = False
        self.original_dilation = None
        self.dilation_restored = False
        self.reason = None
        self.capture_sampling = False
        self.capture_last_time = None
        self.capture_max_step = 0.0
        self.release_samples = []
        self.first_release = None
        self.last_inactive = None
        self.early_release = False
        self.boundary_max_step = 0.0
        super().__init__()

    def write_report(self, status, reason=None):
        if reason:
            self.reason = reason
        rows = [{"name": name, **self.results.get(name, {"status": "not_run"})} for name in TESTS]
        data = {
            "status": status, "phase": self.phase,
            "scope": "single-authority practice PIE Snitch integration with recorded time dilation",
            "engine": unreal.SystemLibrary.get_engine_version() if unreal else None,
            "elapsed_wall_seconds": round(time.monotonic() - self.started, 3),
            "passed": sum(row["status"] == "passed" for row in rows),
            "failed": sum(row["status"] == "failed" for row in rows),
            "not_run": sum(row["status"] == "not_run" for row in rows),
            "tests": rows, "provenance": self.provenance, "events": self.events,
            "release_boundary_samples": self.release_samples,
            "capture_max_game_step_seconds": round(self.capture_max_step, 4),
            "settings_restored": self.settings_restored, "dilation_restored": self.dilation_restored,
            "editor_url_restored": self.editor_url_restored,
            "reason": self.reason,
            "external_restore_required": net_mode_restore_actions(self.provenance),
            "not_covered": ["physical piloting or keyboard timing", "normal-speed catch difficulty",
                            "22-minute regulation release", "overtime 300-point catch",
                            "network transport or remote ownership", "full-roster autonomous match quality"],
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")

    def record(self, name, passed, **detail):
        self.require(name in TESTS and name not in self.results, "Unknown/repeated Snitch check: " + name)
        self.results[name] = {"status": "passed" if passed else "failed", "detail": detail}
        unreal.log("BASKETBROOM SNITCH TEST %s: %s" % (self.results[name]["status"].upper(), name))
        self.write_report("running")

    def begin(self):
        self.reason = None
        if unreal is None:
            self.finish("not_run", "Run in the compiled UE5.8 editor. No Snitch test was executed.")
            return False
        if self.level.is_in_play_in_editor():
            self.finish("not_run", "The Snitch suite must own a fresh PIE session.")
            return False
        for name in ("_basketbroom_native_test", "_basketbroom_native_network_test",
                     "_basketbroom_native_snitch_test", "_basketbroom_native_play_session"):
            runner = getattr(unreal, name, None)
            if runner and not runner.done:
                self.finish("not_run", "Another native test/session operation is active.")
                return False
        selected = self.editor.get_editor_world()
        if selected is None or selected.get_path_name().split(".", 1)[0] != "/Basketbroom/Maps/BB_Regulation":
            self.finish("not_run", "Select the staged BB_Regulation map first.")
            return False
        cls = unreal.load_class(None, "/Script/UnrealEd.LevelEditorPlaySettings")
        self.require(cls is not None, "LevelEditorPlaySettings is not reflected")
        self.settings = unreal.get_default_object(cls)
        wanted = {"RunUnderOneProcess": True, "PlayNumberOfClients": 1,
                  "bLaunchSeparateServer": False}
        net_mode = getattr(getattr(unreal, "PlayNetMode", None), "PIE_LISTEN_SERVER", None)
        if net_mode is not None:
            wanted["PlayNetMode"] = net_mode
        elif ARGS.get("settings_already_configured", False):
            self.provenance.update(external_net_mode_provenance(ARGS.get("settings_source", "editor_ui")))
        else:
            self.finish("not_run", "PlayNetMode Python enum is unavailable. Configure Play As Listen Server through the "
                        "editor UI or normal config while the editor is closed, record its prior value, and run with "
                        "settings_already_configured=True and settings_source='editor_ui' or 'editor_config'.")
            return False
        resolved = {}
        for name, value in wanted.items():
            key, old = setting_slot(self.settings, name)
            self.saved_settings[key] = old
            resolved[key] = value
        # GameInstance.cpp calls the live EditorEngine's BuildPlayWorldURL for
        # in-process PIE; PlayLevel.cpp appends this public EditAnywhere string.
        # A settings CDO or AdditionalServerGameOptions does not feed that path.
        engine_class = unreal.load_class(None, "/Script/UnrealEd.EditorEngine")
        self.require(engine_class is not None, "EditorEngine is not reflected")
        engines = [obj for obj in unreal.ObjectIterator(engine_class)
                   if obj.get_path_name().startswith("/Engine/Transient.")
                   and not obj.get_name().startswith("Default__")]
        self.require(len(engines) == 1, "Expected one live EditorEngine, found " + str(len(engines)))
        self.editor_engine = engines[0]
        self.editor_url_key, self.original_editor_url = setting_slot(self.editor_engine, "InEditorGameURLOptions")
        requested_url = str(self.original_editor_url) + "?Practice=1"
        self.provenance.update(editor_engine=self.editor_engine.get_path_name(),
                               original_editor_game_url_options=self.original_editor_url,
                               requested_editor_game_url_options=requested_url)
        self.provenance.update(original_play_settings=dict(self.saved_settings), requested_play_settings=resolved)
        for key, value in resolved.items():
            self.settings.set_editor_property(key, value)
            self.require(self.settings.get_editor_property(key) == value, "PIE setting did not change: " + key)
        self.editor_engine.set_editor_property(self.editor_url_key, requested_url)
        self.require(self.editor_engine.get_editor_property(self.editor_url_key) == requested_url,
                     "Editable PIE game URL did not change")
        return super().begin()

    def setup_world(self):
        world = self.editor.get_game_world()
        if world is not None and self.original_dilation is None:
            self.original_dilation = float(unreal.GameplayStatics.get_global_time_dilation(world))
            self.provenance["original_world_time_dilation"] = self.original_dilation
        return super().setup_world()

    def dilation(self, value):
        unreal.GameplayStatics.set_global_time_dilation(self.world, value)
        actual = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        self.require(abs(actual - value) < 0.001, "World dilation request was clamped/rejected")
        self.event("owned_pie_world_time_dilation", requested=value, observed=actual)

    def sample_release(self):
        seconds = float(prop(self.match, "LiveSeconds"))
        if self.release_samples and abs(seconds - self.release_samples[-1]["live_seconds"]) < 0.0001:
            return
        active = bool(prop(self.balls[4], "bActive"))
        if self.release_samples and self.release_samples[-1]["live_seconds"] >= 55:
            self.boundary_max_step = max(self.boundary_max_step, seconds - self.release_samples[-1]["live_seconds"])
        sample = {"live_seconds": round(seconds, 4), "active": active,
                  "status": str(prop(self.balls[4], "BallStatus"))}
        self.release_samples.append(sample)
        if active and seconds < 60:
            self.early_release = True
        if active and self.first_release is None:
            self.first_release = sample
        if not active:
            self.last_inactive = sample

    def follow_snitch(self):
        point = self.balls[4].get_actor_location()
        self.move_pawn((point.x, point.y, point.z))

    def actor_roster_identity(self):
        riders = unreal.GameplayStatics.get_all_actors_of_class(self.world, self.classes["BBRiderCharacter"])
        balls = unreal.GameplayStatics.get_all_actors_of_class(self.world, self.classes["BBBall"])
        states = unreal.GameplayStatics.get_all_actors_of_class(self.world, self.classes["BBMatchState"])
        pawn = unreal.GameplayStatics.get_player_pawn(self.world, 0)
        controller = unreal.GameplayStatics.get_player_controller(self.world, 0)
        mode = unreal.GameplayStatics.get_game_mode(self.world)
        return {
            "world": self.world.get_path_name(), "game_mode": mode.get_path_name() if mode else None,
            "match_states": sorted(state.get_path_name() for state in states),
            "pawn": pawn.get_path_name() if pawn else None,
            "controller": controller.get_path_name() if controller else None,
            "riders": sorted((rider.get_path_name(), int(prop(rider, "RosterIndex")),
                              int(prop(rider, "TeamIndex")), int(prop(rider, "Position"))) for rider in riders),
            "balls": sorted((ball.get_path_name(), int(prop(ball, "BallIndex"))) for ball in balls),
        }

    def isolate_after_live(self):
        # First kickoff/rematch repositions the roster. Reapply only the
        # disposable CPU/ball fixture after observing that native transition.
        if prop(self.match, "bLive"):
            self.isolate()

    def scenarios(self):
        practice = bool(prop(self.match, "bPractice"))
        self.record(TESTS[0], practice and abs(float(prop(self.match, "SecondsLeft")) - 180) < 0.01,
                    practice=practice, quarter_seconds=float(prop(self.match, "SecondsLeft")))
        self.require(practice, "The InEditorGameURLOptions practice URL did not reach the native world")
        self.record(TESTS[1], len(self.riders) == 16 and self.roster_valid() and sorted(self.balls) == list(range(7)))
        snitch = self.balls[4]
        self.record(TESTS[2], not prop(snitch, "bActive") and str(prop(snitch, "BallStatus")) == "scheduled_release"
                    and 59.9 <= float(prop(snitch, "ReturnIn")) <= 60.1,
                    active=bool(prop(snitch, "bActive")), return_seconds=float(prop(snitch, "ReturnIn")))
        self.request(2, 5)
        yield self.wait_until(lambda: int(prop(self.pawn, "Position")) == 5)
        self.record(TESTS[3], int(prop(self.pawn, "Position")) == 5 and self.roster_valid())
        original_identity = self.actor_roster_identity()
        self.isolate()
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")) and float(prop(self.match, "LiveSeconds")) > 0,
                             self.isolate_after_live)
        self.record(TESTS[4], bool(prop(self.match, "bLive")) and float(prop(self.match, "LiveSeconds")) > 0)
        self.require(prop(self.match, "bLive"), "Native host could not start practice")
        self.isolate()
        yield self.wait(0.12)
        before = self.scores()
        self.dilation(8.0)
        self.sample_release()
        yield self.wait_until(lambda: float(prop(self.match, "LiveSeconds")) >= 55,
                             self.sample_release, timeout=70)
        self.dilation(1.0)
        yield self.wait_until(lambda: float(prop(self.match, "LiveSeconds")) >= 58,
                             self.sample_release, timeout=10)
        live = float(prop(self.match, "LiveSeconds"))
        self.record(TESTS[5], 58 <= live < 60 and not prop(snitch, "bActive") and not self.early_release,
                    live_seconds=live, active=bool(prop(snitch, "bActive")))
        yield self.wait_until(lambda: bool(prop(snitch, "bActive")), self.sample_release, timeout=6)
        self.sample_release()
        boundary = (self.first_release is not None and self.last_inactive is not None
                    and not self.early_release and self.last_inactive["live_seconds"] < 60
                    and 60 <= self.first_release["live_seconds"] <= 60 + self.boundary_max_step + 0.02)
        self.record(TESTS[6], boundary, last_inactive=self.last_inactive, first_active=self.first_release,
                    max_boundary_step_seconds=self.boundary_max_step, expected_live_seconds=60)
        self.record(TESTS[7], self.scores() == before, scores_before=before, scores_after=self.scores())
        self.require(prop(snitch, "bActive"), "Actual timed Snitch release is required before capture")
        self.dilation(0.1)
        self.capture_sampling = True
        self.capture_last_time = self.now()
        snitch.set_actor_tick_enabled(True)
        self.follow_snitch()
        self.interact(True)
        yield self.wait_until(lambda: float(prop(snitch, "CaptureProgress")) >= 0.1,
                             self.follow_snitch, timeout=3)
        progress = float(prop(snitch, "CaptureProgress"))
        self.record(TESTS[8], 0.1 <= progress < 0.9 and prop(snitch, "CapturingRider") == self.pawn
                    and self.scores() == before, progress=progress, scores=self.scores())
        self.interact(False)
        yield self.wait_until(lambda: not prop(self.pawn, "bInteractHeld")
                             and float(prop(snitch, "CaptureProgress")) == 0, self.follow_snitch, timeout=3)
        self.record(TESTS[9], float(prop(snitch, "CaptureProgress")) == 0
                    and prop(snitch, "CapturingRider") is None and self.scores() == before)
        self.interact(True)
        yield self.wait_until(lambda: self.scores() != before, self.follow_snitch, timeout=4)
        team = int(prop(self.pawn, "TeamIndex"))
        expected = [0, 0]
        expected[team] = 150
        self.record(TESTS[10], self.score_delta(before) == expected,
                    score_delta=self.score_delta(before), expected=expected)
        self.record(TESTS[11], not prop(self.match, "bLive")
                    and str(prop(self.match, "Status")) == "CERTIFYING RESULT" and int(prop(self.match, "Winner")) == -1,
                    status=str(prop(self.match, "Status")), winner=int(prop(self.match, "Winner")))
        self.interact(False)
        self.capture_sampling = False
        self.dilation(1.0)
        review_started = self.now()
        yield self.wait_until(lambda: int(prop(self.match, "Winner")) >= 0, timeout=6)
        self.record(TESTS[12], int(prop(self.match, "Winner")) == team and str(prop(self.match, "Status")) == "FINAL"
                    and not prop(self.match, "bLive") and self.score_delta(before) == expected,
                    winner=int(prop(self.match, "Winner")), catching_team=team,
                    observed_review_wait_game_seconds=self.now() - review_started, scores=self.scores())

        self.require(str(prop(self.match, "Status")) == "FINAL", "Rematch must follow an actual certified result")
        # Ordinary held input makes the reset check non-vacuous. No state field
        # is written; the host's normal Enter action must clear this hold.
        self.interact(True)
        yield self.wait_until(lambda: bool(prop(self.pawn, "bInteractHeld")))
        self.require(prop(self.pawn, "bInteractHeld"), "Rematch held-input fixture was not applied")
        final_live_seconds = float(prop(self.match, "LiveSeconds"))
        final_scores = self.scores()
        self.event("certified_final_before_rematch", scores=final_scores,
                   live_seconds=final_live_seconds, host_interact_held=True)
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive"))
                             and str(prop(self.match, "Status")) == "LIVE", self.isolate_after_live)
        self.isolate()
        yield self.wait(0.12)
        self.record(TESTS[13], bool(prop(self.match, "bPractice")) and bool(prop(self.match, "bLive"))
                    and int(prop(self.match, "Quarter")) == 1 and int(prop(self.match, "Winner")) == -1
                    and str(prop(self.match, "Phase")) == "REGULATION" and str(prop(self.match, "Status")) == "LIVE",
                    practice=bool(prop(self.match, "bPractice")), live=bool(prop(self.match, "bLive")),
                    quarter=int(prop(self.match, "Quarter")), winner=int(prop(self.match, "Winner")),
                    phase=str(prop(self.match, "Phase")), status=str(prop(self.match, "Status")))
        live = float(prop(self.match, "LiveSeconds"))
        seconds_left = float(prop(self.match, "SecondsLeft"))
        self.record(TESTS[14], self.scores() == [0, 0] and 0 < live < 5 and live < final_live_seconds
                    and abs(seconds_left + live - 180) < 0.02,
                    final_scores=final_scores, rematch_scores=self.scores(), previous_live_seconds=final_live_seconds,
                    live_seconds=live, seconds_left=seconds_left, expected_quarter_seconds=180)
        rematch_identity = self.actor_roster_identity()
        self.record(TESTS[15], rematch_identity == original_identity and self.roster_valid()
                    and len(rematch_identity["riders"]) == 16 and len(rematch_identity["balls"]) == 7,
                    before=original_identity, after=rematch_identity)
        flags = [{"actor": rider.get_path_name(), "held": bool(prop(rider, "bInteractHeld")),
                  "stun_seconds": float(prop(rider, "StunRemaining"))} for rider in self.riders]
        equipment = [{"ball": index, "holder": prop(ball, "Holder") is not None,
                      "capture_owner": prop(ball, "CapturingRider") is not None,
                      "capture_progress": float(prop(ball, "CaptureProgress"))} for index, ball in sorted(self.balls.items())]
        self.record(TESTS[16], all(not row["held"] and row["stun_seconds"] == 0 for row in flags)
                    and all(not row["holder"] and not row["capture_owner"] and row["capture_progress"] == 0
                            for row in equipment),
                    host_held_before_rematch=True, riders=flags, balls=equipment)
        return_in = float(prop(snitch, "ReturnIn"))
        self.record(TESTS[17], not prop(snitch, "bActive")
                    and str(prop(snitch, "BallStatus")) == "scheduled_release"
                    and abs(return_in + live - 60) < 0.02 and bool(prop(self.balls[3], "bActive")),
                    active=bool(prop(snitch, "bActive")), status=str(prop(snitch, "BallStatus")),
                    return_seconds=return_in, live_seconds=live, snipe_active=bool(prop(self.balls[3], "bActive")))
        self.interact(False)

    def advance(self):
        try:
            self.waiting = next(self.sequence)
            self.waiting.update(last_game_seconds=self.now(), game_frames=0,
                                until=self.now() + self.waiting["seconds"], wall_started=time.monotonic())
        except StopIteration:
            passed = len(self.results) == len(TESTS) - 1 and all(row["status"] == "passed" for row in self.results.values())
            self.finish("passed" if passed else "failed")

    def tick(self, delta):
        if self.done:
            return
        try:
            if self.phase == "ending_pie":
                if not self.level.is_in_play_in_editor():
                    self.complete()
                elif time.monotonic() - self.cleanup_started > 20:
                    self.final_status = "error"
                    self.reason = (self.reason or "") + " PIE did not end within 20 seconds."
                    self.complete()
                return
            elapsed = time.monotonic() - self.started
            if elapsed > float(ARGS.get("max_wall_seconds", 240)):
                raise TimeoutError("Native Snitch integration exceeded its wall-time limit")
            if self.phase == "waiting_for_native_world":
                if not self.setup_world() and elapsed > 30:
                    self.finish("not_run", "No complete native world appeared. Stage BB_Regulation, rebuild, and restart the editor.")
                return
            if not self.level.is_in_play_in_editor():
                raise RuntimeError("PIE ended before native Snitch checks completed")
            now = self.now()
            if self.capture_sampling:
                step = now - self.capture_last_time
                self.capture_last_time = now
                self.capture_max_step = max(self.capture_max_step, step)
                if step > 0.2:
                    self.finish("not_run", "Capture sampling excluded: a PIE game-time step exceeded 0.2 seconds "
                                "despite 0.1 world dilation, so following cannot reliably stay within 380cm. "
                                "Earlier release observations remain recorded; catch/result checks are incomplete.")
                    return
            if self.waiting:
                if self.waiting["fixture"]:
                    self.waiting["fixture"]()
                if now > self.waiting["last_game_seconds"]:
                    self.waiting["game_frames"] += 1
                    self.waiting["last_game_seconds"] = now
                    # A four-game-second deadline takes forty wall seconds at
                    # 0.1x. Only a lack of game-time progress counts as a stall.
                    self.waiting["wall_started"] = time.monotonic()
                predicate = self.waiting["predicate"]
                started = self.waiting["until"] - self.waiting["seconds"]
                ready = (bool(predicate()) and now - started >= self.waiting.get("minimum_seconds", 0)) if predicate else False
                expired = now >= self.waiting["until"]
                if self.waiting["game_frames"] >= self.waiting["minimum_frames"] and (ready or expired):
                    if predicate and expired and not ready:
                        self.event("observation_timeout", limit_seconds=self.waiting["seconds"])
                    self.advance()
                elif time.monotonic() - self.waiting["wall_started"] > 30:
                    raise TimeoutError("PIE world time stopped advancing for 30 wall seconds")
        except Exception:
            self.finish("error", traceback.format_exc())

    def finish(self, status, reason=None):
        self.final_status, self.reason = status, reason
        self.capture_sampling = False
        errors = []
        try:
            if unreal and self.world and self.original_dilation is not None:
                unreal.GameplayStatics.set_global_time_dilation(self.world, self.original_dilation)
                self.dilation_restored = abs(float(unreal.GameplayStatics.get_global_time_dilation(self.world))
                                            - self.original_dilation) < 0.001
        except Exception:
            errors.append("World dilation: " + traceback.format_exc())
        try:
            if self.pawn:
                self.pawn.development_set_interaction(False)
        except Exception:
            errors.append("Interaction: " + traceback.format_exc())
        if self.editor_engine and self.editor_url_key is not None:
            try:
                self.editor_engine.set_editor_property(self.editor_url_key, self.original_editor_url)
                self.editor_url_restored = self.editor_engine.get_editor_property(self.editor_url_key) == self.original_editor_url
            except Exception:
                errors.append("Editor game URL: " + traceback.format_exc())
        if self.settings:
            for key, value in self.saved_settings.items():
                try:
                    self.settings.set_editor_property(key, value)
                except Exception:
                    errors.append("Setting " + key + ": " + traceback.format_exc())
            try:
                self.settings_restored = (all(self.settings.get_editor_property(key) == value
                                              for key, value in self.saved_settings.items())
                                          and (self.editor_url_key is None or self.editor_url_restored))
            except Exception:
                errors.append("Settings readback: " + traceback.format_exc())
        if errors:
            self.final_status = "error"
            self.reason = (self.reason or "") + "\nCleanup: " + "\n".join(errors)
        if self.owns_play:
            self.phase = "ending_pie"
            self.cleanup_started = time.monotonic()
            self.level.editor_request_end_play()
            self.write_report("running")
        else:
            self.complete()

    def complete(self):
        if self.owns_play:
            ended = not self.level.is_in_play_in_editor()
            self.record(TESTS[-1], ended and self.settings_restored and self.dilation_restored,
                        no_pie_session=ended, settings_restored=self.settings_restored,
                        dilation_restored=self.dilation_restored, editor_url_restored=self.editor_url_restored)
            if not (ended and self.settings_restored and self.dilation_restored):
                self.final_status = "error"
        self.done = True
        if unreal and self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        self.phase = "complete"
        self.write_report(self.final_status)


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "planned_tests": list(TESTS), "count": len(TESTS),
                "conditions": "practice PIE; 8x approach, 1x release, 0.1x capture, 1x review"}
    runner = NativeSnitchTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and (started or not runner.done):
        unreal._basketbroom_native_snitch_test = runner
    return {"status": "started" if started else runner.final_status,
            "report": str(REPORT), "planned_cases": len(TESTS)}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

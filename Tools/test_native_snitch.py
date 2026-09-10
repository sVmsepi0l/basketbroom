"""Focused native Snitch release/catch/result checks in disposable practice PIE.

Run in the staged BB_Regulation UE5.8 editor with PIE stopped. If this engine
omits the PlayNetMode Python enum, select Play As Listen Server in the UI and
pass settings_already_configured=True, as with test_native_network.py. The suite
sets AdditionalServerGameOptions='?Practice=1' and one in-process player, then
restores all settings it changed. It verifies the resulting bPractice flag.

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

REPORT = ROOT / ".local/native-snitch-test-results.json"
ARGS = globals().get("BRIDGE_ARGS", {})
TESTS = (
    "native_practice_configuration", "sixteen_riders_seven_balls",
    "snitch_initially_scheduled", "host_selects_scout", "practice_live_clock_starts",
    "snitch_absent_before_sixty_live_seconds", "snitch_releases_at_sixty_live_seconds",
    "release_does_not_award_points", "snitch_partial_hold_progress",
    "snitch_release_resets_hold", "snitch_continuous_catch_awards_150",
    "snitch_catch_enters_review", "review_certifies_correct_winner",
    "play_settings_restored_and_pie_ended",
)


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
            "reason": self.reason,
            "external_restore_required": ["Restore the previous editor UI Play Net Mode"]
                if self.provenance.get("net_mode_configured_in_editor") else [],
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
                  "bLaunchSeparateServer": False, "AdditionalServerGameOptions": "?Practice=1"}
        net_mode = getattr(getattr(unreal, "PlayNetMode", None), "PIE_LISTEN_SERVER", None)
        if net_mode is not None:
            wanted["PlayNetMode"] = net_mode
        elif ARGS.get("settings_already_configured", False):
            self.provenance["net_mode_configured_in_editor"] = True
        else:
            self.finish("not_run", "PlayNetMode Python enum is unavailable. Select Play As Listen Server in the "
                        "editor UI, record its prior value, and run with settings_already_configured=True.")
            return False
        resolved = {}
        for name, value in wanted.items():
            key, old = setting_slot(self.settings, name)
            self.saved_settings[key] = old
            resolved[key] = value
        self.provenance.update(original_play_settings=dict(self.saved_settings), requested_play_settings=resolved)
        for key, value in resolved.items():
            self.settings.set_editor_property(key, value)
            self.require(self.settings.get_editor_property(key) == value, "PIE setting did not change: " + key)
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

    def scenarios(self):
        practice = bool(prop(self.match, "bPractice"))
        self.record(TESTS[0], practice and abs(float(prop(self.match, "SecondsLeft")) - 180) < 0.01,
                    practice=practice, quarter_seconds=float(prop(self.match, "SecondsLeft")))
        self.require(practice, "The AdditionalServerGameOptions practice URL did not reach the native world")
        self.record(TESTS[1], len(self.riders) == 16 and self.roster_valid() and sorted(self.balls) == list(range(7)))
        snitch = self.balls[4]
        self.record(TESTS[2], not prop(snitch, "bActive") and str(prop(snitch, "BallStatus")) == "scheduled_release"
                    and 59.9 <= float(prop(snitch, "ReturnIn")) <= 60.1,
                    active=bool(prop(snitch, "bActive")), return_seconds=float(prop(snitch, "ReturnIn")))
        self.request(2, 5)
        yield self.wait_until(lambda: int(prop(self.pawn, "Position")) == 5)
        self.record(TESTS[3], int(prop(self.pawn, "Position")) == 5 and self.roster_valid())
        self.isolate()
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")) and float(prop(self.match, "LiveSeconds")) > 0)
        self.record(TESTS[4], bool(prop(self.match, "bLive")) and float(prop(self.match, "LiveSeconds")) > 0)
        self.require(prop(self.match, "bLive"), "Native host could not start practice")
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
        if self.phase == "ending_pie":
            if not self.level.is_in_play_in_editor():
                self.complete()
            elif time.monotonic() - self.cleanup_started > 20:
                self.final_status = "error"
                self.reason = (self.reason or "") + " PIE did not end within 20 seconds."
                self.complete()
            return
        if self.capture_sampling:
            step = self.now() - self.capture_last_time
            self.capture_last_time = self.now()
            self.capture_max_step = max(self.capture_max_step, step)
            if step > 0.2:
                self.finish("not_run", "Capture sampling excluded: a PIE game-time step exceeded 0.2 seconds "
                            "despite 0.1 world dilation, so following cannot reliably stay within 380cm. "
                            "Earlier release observations remain recorded; catch/result checks are incomplete.")
                return
        super().tick(delta)

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
        if self.settings:
            for key, value in self.saved_settings.items():
                try:
                    self.settings.set_editor_property(key, value)
                except Exception:
                    errors.append("Setting " + key + ": " + traceback.format_exc())
            try:
                self.settings_restored = all(self.settings.get_editor_property(key) == value
                                             for key, value in self.saved_settings.items())
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
                        dilation_restored=self.dilation_restored)
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

"""Focused native PIE audio checks; never invokes the 35-case gameplay suite.

Run through editor_bridge.py after rebuilding the module and loading the native
arena, with PIE stopped and editor audio enabled. Real queued player actions
and the guarded physical ball fixture produce the transitions. This proves
SoundWave bindings and creation of audio components, not human audibility or
mix quality. The runner owns/ends its PIE world and never saves editor assets.
Outside Unreal, --list only reports the plan.
"""

import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local" / "native-audio-test-results.json"
TESTS = (
    "original_soundwave_assets_load",
    "local_hud_silent_baseline",
    "real_pickup_starts_one_audio_component",
    "held_ball_does_not_repeat_audio",
    "real_throw_starts_one_audio_component",
    "free_ball_does_not_repeat_audio",
    "whole_ball_goal_starts_one_score_chime",
    "unchanged_score_does_not_repeat_audio",
    "real_snipe_catch_starts_sparkle_and_score_chime",
    "snipe_timeout_does_not_repeat_audio",
    "completed_cues_release_audio_components",
)

# A private import reuses only the lifecycle, queued input, waits, and physical
# fixtures. Its test names/report are isolated from the ordinary gameplay runner.
spec = importlib.util.spec_from_file_location("_basketbroom_audio_test_base", ROOT / "Tools/test_native_playable.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.TEST_NAMES = TESTS
base.REPORT = REPORT
base.ARGS = {"max_wall_seconds": 120, **globals().get("BRIDGE_ARGS", {})}
unreal = base.unreal
prop = base.prop


class NativeAudioTests(base.NativePlayableTests):
    def write_report(self, status, reason=None):
        rows = [{"name": name, **self.results.get(name, {"status": "not_run"})} for name in TESTS]
        report = {
            "status": status, "phase": self.phase,
            "scope": "Local native PIE SoundWave bindings, observed game transitions, and audio component creation",
            "engine": unreal.SystemLibrary.get_engine_version() if unreal else None,
            "elapsed_wall_seconds": round(time.monotonic() - self.started, 3),
            "passed": sum(row["status"] == "passed" for row in rows),
            "failed": sum(row["status"] == "failed" for row in rows),
            "not_run": sum(row["status"] == "not_run" for row in rows),
            "tests": rows, "events": self.events, "provenance": self.provenance,
            "not_covered": ["Human audibility and subjective mix quality", "Audio device output capture",
                            "Packaged audio cooking", "Remote client timing and packet loss", "Bounce sounds"],
        }
        if reason:
            report["reason"] = reason
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    def begin(self):
        if unreal:
            for name in ("_basketbroom_native_audio_test", "_basketbroom_native_network_test"):
                runner = getattr(unreal, name, None)
                if runner and not runner.done:
                    self.finish("not_run", "Another native PIE runner is active: " + name)
                    return False
            hud_class = unreal.load_class(None, base.MODULE + "BBHUD")
            audio_class = unreal.load_class(None, base.MODULE + "BBAudioFeedback")
            if hud_class is None or audio_class is None or not callable(
                    getattr(unreal.get_default_object(hud_class), "get_audio_feedback", None)):
                self.finish("not_run", "The native HUD/audio helper is not compiled and loaded. Rebuild/restart before testing.")
                return False
        return super().begin()

    def feedback(self):
        hud = self.controller.get_hud() if self.controller else None
        return hud.get_audio_feedback() if hud else None

    def counts(self):
        audio = self.feedback()
        self.require(audio is not None, "Native HUD has not created its audio feedback helper")
        return {name: int(prop(audio, name)) for name in
                ("PickupEvents", "ThrowEvents", "ChaseCatchEvents", "ScoreEvents", "SoundsStarted")}

    def scenarios(self):
        loaded = {}
        for name in ("S_BB_Throw", "S_BB_Catch", "S_BB_Score"):
            asset = unreal.load_asset("/Basketbroom/Audio/" + name)
            loaded[name] = asset.get_class().get_name() if asset else None
        self.record("original_soundwave_assets_load", all(value == "SoundWave" for value in loaded.values()), assets=loaded)
        self.require(all(value == "SoundWave" for value in loaded.values()), "Original sound assets are not loaded")
        yield self.wait_until(lambda: self.feedback() is not None and bool(prop(self.feedback(), "bHasBaseline")))
        baseline = self.counts()
        self.record("local_hud_silent_baseline", bool(prop(self.feedback(), "bAssetsReady"))
                    and bool(prop(self.feedback(), "bHasBaseline")) and all(value == 0 for value in baseline.values()),
                    baseline=baseline, helper=self.feedback().get_class().get_path_name())
        self.require(bool(prop(self.feedback(), "bHasBaseline")), "HUD DrawHUD hook did not establish a baseline")

        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, "bLive")))
        self.require(bool(prop(self.match, "bLive")), "Host failed to start live play")
        self.close_ball(2)
        yield self.wait(0.35)
        before = self.counts()
        self.interact(True)
        yield self.wait_until(lambda: prop(self.balls[2], "Holder") == self.pawn
                             and self.counts()["PickupEvents"] > before["PickupEvents"])
        picked = self.counts()
        self.record("real_pickup_starts_one_audio_component", prop(self.balls[2], "Holder") == self.pawn
                    and picked["PickupEvents"] == before["PickupEvents"] + 1
                    and picked["SoundsStarted"] == before["SoundsStarted"] + 1,
                    before=before, after=picked)
        self.require(prop(self.balls[2], "Holder") == self.pawn, "Throw check requires an actual pickup")
        self.interact(False)
        yield self.wait(0.6, minimum_frames=3)
        self.record("held_ball_does_not_repeat_audio", self.counts() == picked, before=picked, after=self.counts())

        before = self.counts()
        self.request(1)
        yield self.wait_until(lambda: prop(self.balls[2], "Holder") is None
                             and self.counts()["ThrowEvents"] > before["ThrowEvents"])
        thrown = self.counts()
        self.record("real_throw_starts_one_audio_component", prop(self.balls[2], "Holder") is None
                    and thrown["ThrowEvents"] == before["ThrowEvents"] + 1
                    and thrown["SoundsStarted"] == before["SoundsStarted"] + 1,
                    before=before, after=thrown, velocity=base.xyz(self.balls[2].get_flight_velocity()))
        self.balls[2].set_actor_tick_enabled(False)
        yield self.wait(0.6, minimum_frames=3)
        self.record("free_ball_does_not_repeat_audio", self.counts() == thrown, before=thrown, after=self.counts())

        self.isolate()
        before = self.counts()
        scores = self.scores()
        self.seed_ball(0, (6200, 0, 2103.12), (2000, 0, 0))
        yield self.wait_until(lambda: self.scores() != scores and self.counts()["ScoreEvents"] > before["ScoreEvents"])
        scored = self.counts()
        self.record("whole_ball_goal_starts_one_score_chime", self.score_delta(scores) == [13, 0]
                    and scored["ScoreEvents"] == before["ScoreEvents"] + 1
                    and scored["SoundsStarted"] == before["SoundsStarted"] + 1,
                    before=before, after=scored, score_delta=self.score_delta(scores))
        self.balls[0].set_actor_tick_enabled(False)
        yield self.wait(0.75, minimum_frames=3)
        self.record("unchanged_score_does_not_repeat_audio", self.counts() == scored, before=scored, after=self.counts())

        self.isolate()
        before = self.counts()
        scores = self.scores()
        self.balls[3].set_actor_tick_enabled(True)
        self.follow_snipe()
        self.interact(True)
        yield self.wait_until(lambda: not prop(self.balls[3], "bActive")
                             and self.counts()["ChaseCatchEvents"] > before["ChaseCatchEvents"]
                             and self.counts()["ScoreEvents"] > before["ScoreEvents"], self.follow_snipe)
        caught = self.counts()
        expected = [0, 0]
        expected[int(prop(self.pawn, "TeamIndex"))] = 69
        self.record("real_snipe_catch_starts_sparkle_and_score_chime", self.score_delta(scores) == expected
                    and str(prop(self.balls[3], "BallStatus")) == "timeout"
                    and caught["ChaseCatchEvents"] == before["ChaseCatchEvents"] + 1
                    and caught["ScoreEvents"] == before["ScoreEvents"] + 1
                    and caught["SoundsStarted"] == before["SoundsStarted"] + 2,
                    before=before, after=caught, score_delta=self.score_delta(scores))
        self.interact(False)
        yield self.wait(0.9, minimum_frames=3)
        self.record("snipe_timeout_does_not_repeat_audio", self.counts() == caught, before=caught, after=self.counts())
        active = int(self.feedback().get_active_sound_count())
        self.record("completed_cues_release_audio_components", active == 0, active_components=active)


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "planned_tests": list(TESTS), "count": len(TESTS)}
    runner = NativeAudioTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and started:
        unreal._basketbroom_native_audio_test = runner
        # Existing suites already check this shared native-runner guard.
        unreal._basketbroom_native_test = runner
    return {"status": "started" if started else runner.final_status,
            "report": str(REPORT), "planned_cases": len(TESTS)}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

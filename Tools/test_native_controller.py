"""Gamepad input-boundary integration in a disposable UE5.8 PIE world.

Only the guarded native bridge injects mapped EKeys through Unreal's supported
FInputKeyEventArgs::CreateSimulated -> PlayerController::InputKey path. Native
PlayerInput evaluates real bindings/AxisConfig before ordinary gameplay RPCs.
This does NOT certify a physical controller, USB, Bluetooth, OS pairing, actual
disconnect events or rumble. Run with normal PlayerController ticks enabled.
The shared focus/disconnect FlushPressedKeys boundary is exercised explicitly.
--list prints the plan without running Unreal or claiming hardware evidence.
"""
import importlib.util
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / ".local/native-controller-test-results.json"
CASES = (
    "input_boundary_rejects_unmapped_nonfinite_and_out_of_range_values",
    "view_and_roster_dpad_context_change_team_and_lobby_variant",
    "dpad_cycles_roles_at_stoppage",
    "menu_starts_native_match",
    "left_stick_deadzone_prevents_drift",
    "left_stick_partial_deflection_produces_slower_flight",
    "left_stick_strafe_and_face_buttons_control_vertical_flight",
    "right_stick_turn_rate_tracks_game_time_and_pitch_looks_up",
    "dpad_cycles_spells_and_top_face_toggles_spellbook",
    "right_shoulder_casts_actual_selected_spell",
    "left_shoulder_raises_actual_protego",
    "left_face_catches_ball_and_releases_held_interaction",
    "right_trigger_releases_actual_carried_ball",
    "menu_pauses_freezes_clock_and_resumes",
    "conduct_review_requires_explicit_choice_and_separate_confirmation",
    "menu_confirms_selected_possession_award_then_resumes_real_restart",
    "engine_input_flush_clears_axes_catch_and_ghost_flight",
    "serious_dpad_choice_selects_without_adjudication_or_spell_change",
    "free_shot_dpad_choice_selects_without_adjudication_or_spell_change",
)
spec = importlib.util.spec_from_file_location("_bb_controller_scaffold", ROOT / "Tools/test_native_playable.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.TEST_NAMES, base.REPORT = CASES, REPORT
base.ARGS = {"max_wall_seconds": 240, **globals().get("BRIDGE_ARGS", {})}
unreal, prop, xyz, vector = base.unreal, base.prop, base.xyz, base.vector


class NativeControllerTests(base.NativePlayableTests):
    def __init__(self):
        self.original_dilation = None
        super().__init__()

    def write_report(self, status, reason=None):
        super().write_report(status, reason)
        data = json.loads(REPORT.read_text(encoding="utf-8"))
        data.update(scope="simulated gamepad events through real native PlayerInput and gameplay bindings",
                    not_covered=["physical controller hardware, USB or Bluetooth transport",
                                 "Windows pairing, actual device-disconnection notifications or rumble",
                                 "remote gamepad ownership/replication",
                                 "physical focus changes and hardware-specific glyphs"],
                    fixture_policy="Only owned PIE transforms/component ticks and world time dilation are arranged. "
                                   "Inputs enter PlayerController::InputKey; no direct action, effect, custody or penalty writes.")
        REPORT.write_text(json.dumps(data, indent=2, default=str)+"\n", encoding="utf-8")

    def pad(self, key, value):
        self.require(self.pawn.development_inject_gamepad_input(key, float(value)), "Mapped gamepad input was not queued: "+key)
        self.event("player_input_event", key=key, value=float(value))

    def state(self):
        state = [float(v) for v in self.pawn.development_get_controller_input_state()]
        self.require(len(state) == 9, "Loaded DLL lacks the nine-field controller input diagnostic")
        return state

    def release_axis(self, key, index):
        # PlayerInput adds analog samples received before one evaluation. A
        # final nonzero feed plus zero in the same callback would add to the
        # previous value, then persist indefinitely without another sample.
        # Supply one transition, let native input evaluate it, and prove neutral.
        self.pad(key, 0)
        yield self.wait_until(lambda: abs(self.state()[index]) < .001, timeout=1)
        state = self.state()
        self.event("axis_release_observed", key=key, input_state=state)
        self.require(abs(state[index]) < .001, "Native axis did not become neutral after release: "+key)

    def tap(self, key, predicate=None, timeout=2):
        self.pad(key, 1)
        yield self.wait_until(predicate, timeout=timeout) if predicate else self.wait(.12)
        self.pad(key, 0)
        yield self.wait(.12)

    def anchor(self, point=(-2000, -1000, 1800)):
        movement = self.component(self.pawn, unreal.CharacterMovementComponent)
        movement.stop_movement_immediately()
        movement.set_component_tick_enabled(True)
        self.pawn.consume_movement_input_vector()
        self.pawn.set_actor_location(vector(point), False, True)
        self.controller.set_control_rotation(unreal.Rotator(pitch=0, yaw=0, roll=0))
        yield self.wait_until(lambda: self.pawn.get_aim_direction().x > .999, timeout=1)
        self.require(self.pawn.get_aim_direction().x > .999, "Camera cache must settle before an input measurement")

    def axis_motion(self, key, value, index, axis, seconds=.35):
        yield from self.anchor()
        # A gamepad axis is retained by PlayerInput between samples. Repeating
        # samples from Slate can combine two of them in one native input frame.
        self.pad(key, value)
        yield self.wait_until(lambda: abs(self.state()[index]) > .05, timeout=1)
        self.require(abs(self.state()[index]) > .05, "Positive axis control did not reach native PlayerInput")
        movement = self.component(self.pawn, unreal.CharacterMovementComponent)
        movement.stop_movement_immediately()
        start, began = xyz(self.pawn.get_actor_location()), self.now()
        yield self.wait(seconds)
        end, elapsed = xyz(self.pawn.get_actor_location()), self.now()-began
        processed = self.state()[index]
        yield from self.release_axis(key, index)
        movement.stop_movement_immediately()
        return {"start": start, "end": end, "delta": end[axis]-start[axis], "seconds": elapsed,
                "mean_speed": (end[axis]-start[axis])/max(elapsed, .001), "processed_axis": processed}

    def button_motion(self, key, sign):
        yield from self.anchor()
        self.pad(key, 1)
        yield self.wait_until(lambda: self.state()[5 if sign > 0 else 6] == 1, timeout=1)
        start = xyz(self.pawn.get_actor_location())
        yield self.wait(.3)
        end = xyz(self.pawn.get_actor_location())
        self.pad(key, 0)
        yield self.wait_until(lambda: self.state()[5 if sign > 0 else 6] == 0, timeout=1)
        self.component(self.pawn, unreal.CharacterMovementComponent).stop_movement_immediately()
        return {"start": start, "end": end, "signed_vertical_delta": (end[2]-start[2])*sign}

    def turn(self, dilation, key="Gamepad_RightX", index=2):
        unreal.GameplayStatics.set_global_time_dilation(self.world, dilation)
        yield from self.anchor()
        self.pad(key, .7)
        yield self.wait_until(lambda: self.state()[index] > .05, timeout=1)
        self.require(self.state()[index] > .05, "Right-stick input did not reach the real binding")
        start = self.controller.get_control_rotation()
        began = self.now()
        yield self.wait(.35)
        end, elapsed = self.controller.get_control_rotation(), self.now()-began
        delta = (float(end.yaw-start.yaw) if index == 2 else float(end.pitch-start.pitch))
        delta = (delta+180) % 360-180
        yield from self.release_axis(key, index)
        return {"dilation": dilation, "delta_degrees": delta, "seconds": elapsed, "rate": delta/max(elapsed, .001)}

    def aim_at_target(self, head=False):
        yield from self.anchor((-1200, 0, 1800))
        candidates = [r for r in self.riders if r != self.pawn
                      and int(prop(r, "TeamIndex")) != int(prop(self.pawn, "TeamIndex"))
                      and int(prop(r, "Position")) == 3]
        self.require(len(candidates) == 1, "Fixture requires the opposing CPU Ranger")
        target = candidates[0]
        target.set_actor_location(vector((-400, 0, 1792 if head else 1872)), False, True)
        return target

    def conduct(self):
        state = [int(v) for v in self.match.development_get_conduct_state()]
        self.require(len(state) == 6, "Native conduct diagnostic is missing")
        return state

    def scenarios(self):
        for method in ("development_inject_gamepad_input", "development_flush_controller_input", "development_get_controller_input_state"):
            self.require(callable(getattr(self.pawn, method, None)), "Rebuild/load controller DLL before this suite: "+method)
        self.original_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        self.provenance.update(input_boundary="FInputKeyEventArgs::CreateSimulated -> PlayerController::InputKey -> PlayerInput/bindings",
                               hardware_connected="not asserted", controller_ticks="ordinary engine input processing retained",
                               editor_assets_saved=False)
        self.require(self.controller.is_actor_tick_enabled(), "PlayerController Tick must process real input bindings")
        rejected = [not self.pawn.development_inject_gamepad_input(key, value) for key, value in
                    (("MouseX", 1), ("Gamepad_LeftY", 2), ("Gamepad_RightX", float("nan")),
                     ("Gamepad_FaceButton_Left", .5), ("UnmappedControllerKey", 1))]
        self.record(CASES[0], all(rejected), rejected=rejected)
        yield from self.tap("Gamepad_Special_Left", lambda: bool(prop(self.pawn, "bShowRoster")))
        self.require(prop(self.pawn, "bShowRoster"), "View must open the real roster panel")
        initial_variant, initial_team = bool(prop(self.match, "bBloodbroom")), int(prop(self.pawn, "TeamIndex"))
        yield from self.tap("Gamepad_DPad_Right", lambda: bool(prop(self.match, "bBloodbroom")) != initial_variant)
        variant_changed = bool(prop(self.match, "bBloodbroom")) != initial_variant
        yield from self.tap("Gamepad_DPad_Right", lambda: bool(prop(self.match, "bBloodbroom")) == initial_variant)
        yield from self.tap("Gamepad_DPad_Left", lambda: int(prop(self.pawn, "TeamIndex")) != initial_team)
        self.record(CASES[1], variant_changed and bool(prop(self.match, "bBloodbroom")) == initial_variant
                    and int(prop(self.pawn, "TeamIndex")) != initial_team and self.roster_valid()
                    and bool(prop(self.pawn, "bUsingGamepad")), team=int(prop(self.pawn, "TeamIndex")),
                    variant_changed=variant_changed, using_gamepad=bool(prop(self.pawn, "bUsingGamepad")))
        self.require(not prop(self.match, "bBloodbroom"), "Conduct checks require Regulation rules")
        role = int(prop(self.pawn, "Position"))
        yield from self.tap("Gamepad_DPad_Up", lambda: int(prop(self.pawn, "Position")) == (role+1) % 6)
        cycled = int(prop(self.pawn, "Position")) == (role+1) % 6
        yield from self.tap("Gamepad_DPad_Down", lambda: int(prop(self.pawn, "Position")) == role)
        self.record(CASES[2], cycled and int(prop(self.pawn, "Position")) == role and self.roster_valid(), role=role, cycled=cycled)
        self.require(role == 3, "The standard host Ranger is needed for the real ball pickup fixture")
        yield from self.tap("Gamepad_Special_Left", lambda: not prop(self.pawn, "bShowRoster"))
        yield from self.tap("Gamepad_Special_Right", lambda: bool(prop(self.match, "bLive")))
        self.record(CASES[3], bool(prop(self.match, "bLive")), status=str(prop(self.match, "Status")))
        self.require(prop(self.match, "bLive"), "Menu kickoff must enter live match")
        self.isolate()

        yield from self.anchor()
        start = xyz(self.pawn.get_actor_location())
        self.pad("Gamepad_LeftY", .1)
        yield self.wait(.4)
        end, deadzone_state = xyz(self.pawn.get_actor_location()), self.state()
        yield from self.release_axis("Gamepad_LeftY", 1)
        self.record(CASES[4], sum(abs(a-b) for a, b in zip(start, end)) < 3 and abs(deadzone_state[1]) < .001,
                    before=start, after=end, processed_input=deadzone_state, injected_raw_axis=.1)
        partial = yield from self.axis_motion("Gamepad_LeftY", .5, 1, 0)
        full = yield from self.axis_motion("Gamepad_LeftY", 1, 1, 0)
        self.record(CASES[5], full["delta"] > 30 and partial["delta"] > 5
                    and 0 < partial["mean_speed"] < full["mean_speed"]*.8
                    and 0 < partial["processed_axis"] < full["processed_axis"], partial=partial, full=full)
        strafe = yield from self.axis_motion("Gamepad_LeftX", 1, 0, 1)
        up = yield from self.button_motion("Gamepad_FaceButton_Bottom", 1)
        down = yield from self.button_motion("Gamepad_FaceButton_Right", -1)
        self.record(CASES[6], strafe["delta"] > 30 and up["signed_vertical_delta"] > 30
                    and down["signed_vertical_delta"] > 30, strafe=strafe, rise=up, descend=down)
        slower = yield from self.turn(.5)
        normal = yield from self.turn(1)
        pitch = yield from self.turn(1, "Gamepad_RightY", 3)
        self.record(CASES[7], slower["rate"] > 20 and normal["rate"] > 20
                    and .75 < slower["rate"]/normal["rate"] < 1.25 and pitch["delta_degrees"] > 5,
                    slower_step=slower, normal_step=normal, look_up=pitch)
        unreal.GameplayStatics.set_global_time_dilation(self.world, self.original_dilation)

        original_spell = int(prop(self.pawn, "SelectedSpell"))
        yield from self.tap("Gamepad_DPad_Right", lambda: int(prop(self.pawn, "SelectedSpell")) != original_spell)
        changed = int(prop(self.pawn, "SelectedSpell")) != original_spell
        yield from self.tap("Gamepad_DPad_Left", lambda: int(prop(self.pawn, "SelectedSpell")) == original_spell)
        yield from self.tap("Gamepad_FaceButton_Top", lambda: bool(prop(self.pawn, "bShowSpellbook")))
        book_open = bool(prop(self.pawn, "bShowSpellbook")) and not prop(self.pawn, "bShowRoster")
        yield from self.tap("Gamepad_FaceButton_Top", lambda: not prop(self.pawn, "bShowSpellbook"))
        self.record(CASES[8], changed and book_open and not prop(self.pawn, "bShowSpellbook")
                    and int(prop(self.pawn, "SelectedSpell")) == original_spell,
                    spell=int(prop(self.pawn, "SelectedSpell")), book_open=book_open)
        self.require(original_spell == 0, "Fresh selected spell must be Basic Cast")
        target = yield from self.aim_at_target()
        health = float(prop(target, "Vitality"))
        yield from self.tap("Gamepad_RightShoulder", lambda: float(prop(target, "Vitality")) < health-3)
        self.record(CASES[9], float(prop(target, "Vitality")) < health-3 and self.conduct()[0] == 0,
                    health_before=health, health_after=float(prop(target, "Vitality")), conduct=self.conduct())
        yield self.wait_until(lambda: float(prop(self.pawn, "SpellCooldownRemaining")) <= 0, timeout=1)
        yield from self.tap("Gamepad_LeftShoulder", lambda: float(prop(self.pawn, "ShieldRemaining")) > 0)
        self.record(CASES[10], float(prop(self.pawn, "ShieldRemaining")) > 0,
                    shield=float(prop(self.pawn, "ShieldRemaining")))

        yield from self.anchor((-2000, -1200, 1800))
        ball = self.seed_ball(0, (-1800, -1200, 1800))
        yield self.wait(.4)
        self.pad("Gamepad_FaceButton_Left", 1)
        yield self.wait_until(lambda: prop(ball, "Holder") == self.pawn and prop(self.pawn, "bInteractHeld"), timeout=2)
        held = prop(ball, "Holder") == self.pawn and bool(prop(self.pawn, "bInteractHeld"))
        self.pad("Gamepad_FaceButton_Left", 0)
        yield self.wait_until(lambda: not prop(self.pawn, "bInteractHeld"), timeout=1)
        self.record(CASES[11], held and prop(ball, "Holder") == self.pawn and not prop(self.pawn, "bInteractHeld"),
                    actual_pickup=held, input_state=self.state())
        self.require(prop(ball, "Holder") == self.pawn, "Trigger fixture requires actual native custody")
        yield from self.tap("Gamepad_RightTrigger", lambda: prop(ball, "Holder") is None)
        velocity = xyz(ball.get_flight_velocity())
        self.record(CASES[12], prop(ball, "Holder") is None and sum(v*v for v in velocity) > 10000,
                    holder=prop(ball, "Holder"), flight_velocity=velocity)
        yield from self.tap("Gamepad_Special_Right", lambda: not prop(self.match, "bLive"))
        frozen = float(prop(self.match, "LiveSeconds"))
        yield self.wait(.3)
        clock_frozen = not prop(self.match, "bLive") and float(prop(self.match, "LiveSeconds")) == frozen
        yield from self.tap("Gamepad_Special_Right", lambda: bool(prop(self.match, "bLive")))
        self.record(CASES[13], clock_frozen and prop(self.match, "bLive"), clock_frozen=clock_frozen)

        yield self.wait_until(lambda: float(prop(self.pawn, "SpellCooldownRemaining")) == 0, timeout=3)
        target = yield from self.aim_at_target(head=True)
        yield from self.tap("Gamepad_RightShoulder", lambda: bool(prop(self.match, "bConductReviewPending")))
        self.require(prop(self.match, "bConductReviewPending") and self.conduct()[3] == 2,
                     "Actual gamepad headshot must create referee review")
        pending = self.conduct()
        neutral_choice = int(prop(self.pawn, "GamepadRefereeChoice")) == 0
        yield from self.tap("Gamepad_Special_Right")
        menu_did_nothing = self.conduct() == pending and not prop(self.match, "bLive")
        yield from self.tap("Gamepad_DPad_Down", lambda: int(prop(self.pawn, "GamepadRefereeChoice")) == 2)
        severe_selection_only = self.conduct() == pending and int(prop(self.match, "PendingPenaltyCount")) == 0
        spell_before_serious_choice = int(prop(self.pawn, "SelectedSpell"))
        score_before_serious_choice = self.scores()
        yield from self.tap("Gamepad_DPad_Left", lambda: int(prop(self.pawn, "GamepadRefereeChoice")) == 4)
        free_selection_only = (int(prop(self.pawn, "GamepadRefereeChoice")) == 4
                               and self.conduct() == pending and int(prop(self.match, "PendingPenaltyCount")) == 0
                               and not prop(self.match, "bPenaltyShotActive") and not prop(self.match, "bLive")
                               and self.scores() == score_before_serious_choice
                               and int(prop(self.pawn, "SelectedSpell")) == spell_before_serious_choice)
        self.record(CASES[18], free_selection_only,
                    choice=int(prop(self.pawn, "GamepadRefereeChoice")), conduct=self.conduct(),
                    shot_active=bool(prop(self.match, "bPenaltyShotActive")),
                    scores_before=score_before_serious_choice, scores_after=self.scores(),
                    spell_before=spell_before_serious_choice, spell_after=int(prop(self.pawn, "SelectedSpell")),
                    input_path="D-pad Left via native PlayerInput; no confirmation sent")
        yield from self.tap("Gamepad_DPad_Right", lambda: int(prop(self.pawn, "GamepadRefereeChoice")) == 3)
        serious_selection_only = (int(prop(self.pawn, "GamepadRefereeChoice")) == 3
                                  and self.conduct() == pending and int(prop(self.match, "PendingPenaltyCount")) == 0
                                  and not prop(self.match, "bPenaltyShotActive") and not prop(self.match, "bLive")
                                  and self.scores() == score_before_serious_choice
                                  and int(prop(self.pawn, "SelectedSpell")) == spell_before_serious_choice)
        self.record(CASES[17], serious_selection_only,
                    choice=int(prop(self.pawn, "GamepadRefereeChoice")), conduct=self.conduct(),
                    shot_active=bool(prop(self.match, "bPenaltyShotActive")),
                    scores_before=score_before_serious_choice, scores_after=self.scores(),
                    spell_before=spell_before_serious_choice, spell_after=int(prop(self.pawn, "SelectedSpell")),
                    input_path="D-pad Right via native PlayerInput; no confirmation sent")
        yield from self.tap("Gamepad_DPad_Up", lambda: int(prop(self.pawn, "GamepadRefereeChoice")) == 1)
        self.record(CASES[14], neutral_choice and menu_did_nothing and severe_selection_only
                    and self.conduct() == pending and int(prop(self.pawn, "GamepadRefereeChoice")) == 1,
                    neutral_choice=neutral_choice, menu_without_selection_rejected=menu_did_nothing,
                    ejection_selection_has_no_gameplay_effect=severe_selection_only, conduct=self.conduct())
        yield from self.tap("Gamepad_Special_Right", lambda: not prop(self.match, "bConductReviewPending"))
        queued = self.conduct()
        self.require(queued[5] in (0, 1, 2), "Confirmed Menu must queue a real scoring-ball possession award")
        award = self.balls[queued[5]]
        queued_while_paused = not prop(self.match, "bLive") and prop(award, "Holder") is None
        choice_cleared = int(prop(self.pawn, "GamepadRefereeChoice")) == 0
        yield from self.tap("Gamepad_Special_Right", lambda: prop(self.match, "bLive")
                            and prop(award, "Holder") is not None)
        receiver = prop(award, "Holder")
        self.record(CASES[15], queued_while_paused and choice_cleared and receiver is not None
                    and int(prop(receiver, "TeamIndex")) != int(prop(self.pawn, "TeamIndex"))
                    and int(prop(self.match, "PendingPenaltyCount")) == 0 and self.conduct()[5] == -1,
                    queued=queued, after=self.conduct(), choice_cleared=choice_cleared,
                    receiver_slot=int(prop(receiver, "RosterIndex")) if receiver else None)

        yield from self.anchor((-2200, -1800, 1800))
        self.pad("Gamepad_FaceButton_Left", 1)
        self.pad("Gamepad_LeftY", 1)
        yield self.wait_until(lambda: self.state()[1] > .5 and prop(self.pawn, "bInteractHeld"), timeout=1)
        self.require(self.state()[1] > .5 and prop(self.pawn, "bInteractHeld"), "Flush fixture requires actual held axis and catch")
        flush_before = self.state()[8]
        self.require(self.pawn.development_flush_controller_input(), "Native input flush was not queued")
        yield self.wait_until(lambda: self.state()[8] > flush_before and not prop(self.pawn, "bInteractHeld")
                             and max(abs(v) for v in self.state()[:8]) < .001, timeout=1)
        after_flush = self.state()
        start = xyz(self.pawn.get_actor_location())
        yield self.wait(.4)
        end = xyz(self.pawn.get_actor_location())
        self.record(CASES[16], after_flush[8] > flush_before and max(abs(v) for v in self.state()[:8]) < .001
                    and not prop(self.pawn, "bInteractHeld") and sum(abs(a-b) for a, b in zip(start, end)) < 3,
                    flush_count_before=flush_before, after_flush=after_flush, current=self.state(), start=start, end=end,
                    hardware_disconnect="not simulated; shared engine flush boundary exercised")

    def finish(self, status, reason=None):
        if unreal and self.owns_play:
            try:
                if self.pawn and callable(getattr(self.pawn, "development_flush_controller_input", None)):
                    self.pawn.development_flush_controller_input()
                if self.world and self.original_dilation is not None:
                    unreal.GameplayStatics.set_global_time_dilation(self.world, self.original_dilation)
                    self.provenance["world_dilation_restored"] = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
                self.provenance["cleanup"] = "Owned PIE EndPlay requested; its PlayerInput and temporary actors are destroyed"
            except Exception:
                status, reason = "error", (reason or "")+"\nController cleanup: "+traceback.format_exc()
        super().finish(status, reason)


def main():
    if unreal is None and "--list" in sys.argv:
        return {"status": "not_run", "planned_tests": list(CASES), "count": len(CASES), "hardware_claim": False}
    runner = NativeControllerTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish("error", traceback.format_exc())
        started = False
    if unreal and started:
        unreal._basketbroom_native_test = runner
    return {"status": "started" if started else runner.final_status, "report": str(REPORT), "planned_cases": len(CASES)}


if __name__ == "__main__":
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

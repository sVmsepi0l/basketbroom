"""PIE acceptance for real trigger input, earned charge and pause settings.

Fixtures move disposable actors/balls, never write scores, charge or penalties.
Actual catches, throws, goals and input bindings produce gameplay outcomes.
No physical USB/Bluetooth claim. Ends its own PIE session and restores settings.
"""
import importlib.util
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_bb_flight_controller_base', ROOT/'Tools/test_native_controller.py')
ctrl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctrl)
unreal, prop, xyz, vector = ctrl.unreal, ctrl.prop, ctrl.xyz, ctrl.vector
REPORT = ROOT/'.local/native-flight-controls-results.json'
CASES = (
    'r2_accelerates_at_zero_charge',
    'l2_brakes_with_r2_held',
    'pause_settings_change_altitude_inversion',
    'inversion_reverses_real_right_stick_altitude',
    'actual_thrown_quaffle_goal_earns_charge',
    'partial_charge_boost_drains_only_while_used',
    'four_more_actual_goals_fill_but_do_not_exceed_meter',
    'fresh_r2_at_full_starts_super_boost',
    'l2_cancels_super_without_refunding_charge',
    'pause_resume_clears_held_trigger_and_preserves_match',
    'actual_enemy_bludger_hit_earns_charge_once',
)
ctrl.REPORT = ctrl.base.REPORT = REPORT
ctrl.base.TEST_NAMES = CASES
ctrl.base.ARGS = {'max_wall_seconds':240, **globals().get('BRIDGE_ARGS', {})}


class FlightTests(ctrl.NativeControllerTests):
    def flight(self):
        values = list(self.pawn.development_get_flight_state())
        self.require(len(values) == 8, 'Expected current flight diagnostics')
        return values

    def trigger(self, key, value, index):
        self.pad(key, value)
        yield self.wait_until(lambda: abs(self.flight()[index]-value) < .025, timeout=2)
        self.require(abs(self.flight()[index]-value) < .025, 'Trigger binding did not settle: '+key)

    def score_goal(self):
        # A referee stoppage/resume releases the prior goal restart normally.
        if prop(self.match, 'bLive'):
            self.request(5)
            yield self.wait_until(lambda: not prop(self.match, 'bLive'))
        self.request(4)
        yield self.wait_until(lambda: bool(prop(self.match, 'bLive')))
        self.isolate()
        ball = self.balls[0]
        self.require(prop(ball, 'Holder') is None, 'Goal fixture needs a free quaffle after restart')
        goal = ctrl.base.dimensions.GOAL_PLANE_X
        yield from self.anchor((goal-1000, 1066.8, 2031.12))
        self.seed_ball(0, (goal-800, 1066.8, 2031.12))
        yield self.wait(.35)
        self.pad('Gamepad_FaceButton_Left', 1)
        yield self.wait_until(lambda: prop(ball, 'Holder') == self.pawn, timeout=2)
        self.require(prop(ball, 'Holder') == self.pawn, 'Square must catch actual quaffle')
        self.pad('Gamepad_FaceButton_Left', 0)
        yield self.wait(.15)
        before, charge = self.scores(), self.flight()[0]
        yield from self.tap('Gamepad_FaceButton_Bottom', lambda: prop(ball, 'Holder') is None)
        yield self.wait_until(lambda: self.scores() != before, timeout=3)
        delta = self.score_delta(before)
        self.require(delta == [13, 0], 'Actual thrown quaffle must cross the scoring hoop: '+str(delta))
        self.require(abs(self.flight()[0]-min(100, charge+25)) < .01, 'Accepted goal must award exactly capped 25 charge')
        self.event('actual_goal_reward', score_delta=delta, charge_before=charge, charge_after=self.flight()[0])

    def scenarios(self):
        # Give the operator time to focus the fresh embedded Play viewport.
        # The normal focus/neutral safety latch must remain active in this test.
        yield self.wait(max(10, min(60, float(ctrl.base.ARGS.get('focus_grace_seconds', 10)))))
        self.original_inversion = (bool(prop(self.pawn, 'bInvertControllerAltitude')), bool(prop(self.pawn, 'bInvertControllerAimY')))
        self.pawn.set_controller_inversion(False, False)
        self.original_dilation = float(unreal.GameplayStatics.get_global_time_dilation(self.world))
        self.require(int(prop(self.pawn, 'TeamIndex')) == 0, 'Expected fresh Teal host')
        yield from self.tap('Gamepad_FaceButton_Bottom', lambda: bool(prop(self.match, 'bLive')))
        self.isolate()
        yield from self.anchor()
        start = xyz(self.pawn.get_actor_location())
        yield from self.trigger('Gamepad_RightTriggerAxis', 1, 3)
        yield self.wait(.4)
        forward = xyz(self.pawn.get_actor_location())[0]-start[0]
        self.record(CASES[0], forward > 30 and self.flight()[0] == 0 and self.flight()[2] == 1, distance=forward, flight=self.flight())
        yield from self.trigger('Gamepad_LeftTriggerAxis', 1, 4)
        yield self.wait(.4)
        speed = self.pawn.get_velocity().length()
        self.record(CASES[1], speed < 5 and self.flight()[3] > .9, stopped_speed=speed, flight=self.flight())
        yield from self.trigger('Gamepad_RightTriggerAxis', 0, 3)
        yield from self.trigger('Gamepad_LeftTriggerAxis', 0, 4)

        yield from self.tap('Gamepad_Special_Right', lambda: bool(prop(self.pawn, 'bPauseMenuOpen')))
        yield from self.tap('Gamepad_DPad_Down')
        yield from self.tap('Gamepad_FaceButton_Bottom', lambda: int(prop(self.pawn, 'PauseMenuPage')) == 1)
        yield from self.tap('Gamepad_FaceButton_Bottom', lambda: bool(prop(self.pawn, 'bInvertControllerAltitude')))
        self.record(CASES[2], prop(self.pawn, 'bInvertControllerAltitude') and unreal.GameplayStatics.is_game_paused(self.world), flight=self.flight())
        yield from self.tap('Gamepad_Special_Right', lambda: not prop(self.pawn, 'bPauseMenuOpen'))
        yield self.wait(.25)
        inverted = yield from self.axis_motion('Gamepad_RightY', 1, 3, 2)
        self.record(CASES[3], inverted['delta'] < -30, movement=inverted)
        self.pawn.set_controller_inversion(False, False)

        yield from self.score_goal()
        self.record(CASES[4], self.flight()[0] == 25, flight=self.flight(), scores=self.scores())
        yield from self.anchor()
        yield from self.trigger('Gamepad_RightTriggerAxis', 1, 3)
        boosted = self.flight()[2]
        yield self.wait(.4)
        yield from self.trigger('Gamepad_RightTriggerAxis', 0, 3)
        charge = self.flight()[0]
        yield self.wait(.4)
        self.record(CASES[5], boosted > 1 and 0 < charge < 25 and abs(self.flight()[0]-charge) < .01,
                    boosted_scale=boosted, charge_after_use=charge, idle_charge=self.flight()[0])
        for _ in range(4):
            yield from self.score_goal()
        self.record(CASES[6], self.flight()[0] == 100, flight=self.flight(), scores=self.scores())
        yield from self.anchor()
        yield from self.trigger('Gamepad_RightTriggerAxis', 1, 3)
        self.record(CASES[7], self.flight()[0] == 0 and self.flight()[1] > 0 and self.flight()[2] == 2, flight=self.flight())
        yield from self.trigger('Gamepad_LeftTriggerAxis', 1, 4)
        self.record(CASES[8], self.flight()[0] == 0 and self.flight()[1] == 0 and self.flight()[2] == 1, flight=self.flight())
        yield from self.trigger('Gamepad_LeftTriggerAxis', 0, 4)
        yield from self.tap('Gamepad_Special_Right', lambda: bool(prop(self.pawn, 'bPauseMenuOpen')))
        frozen = float(prop(self.match, 'LiveSeconds'))
        yield self.wait(.3)
        paused = unreal.GameplayStatics.is_game_paused(self.world) and float(prop(self.match, 'LiveSeconds')) == frozen
        yield from self.tap('Gamepad_Special_Right', lambda: not prop(self.pawn, 'bPauseMenuOpen'))
        yield self.wait(.3)
        self.record(CASES[9], paused and prop(self.match, 'bLive') and self.flight()[3] == 0
                    and float(prop(self.match, 'LiveSeconds')) > frozen, flight=self.flight())
        yield from self.switch_role(4)
        yield from self.anchor((-2000, -1200, 1800))
        target = next(r for r in self.riders if int(prop(r, 'TeamIndex')) == 1 and int(prop(r, 'Position')) == 3)
        target.set_actor_location(vector((-500, -1200, 1872)), False, True)
        ball = self.seed_ball(5, (-1800, -1200, 1800))
        yield self.wait(.35)
        self.pad('Gamepad_FaceButton_Left', 1)
        yield self.wait_until(lambda: prop(ball, 'Holder') == self.pawn)
        self.require(prop(ball, 'Holder') == self.pawn, 'Hurleyback must actually catch the bludger')
        self.pad('Gamepad_FaceButton_Left', 0)
        yield self.wait(.15)
        charge = self.flight()[0]
        yield from self.tap('Gamepad_FaceButton_Bottom', lambda: prop(ball, 'Holder') is None)
        yield self.wait_until(lambda: self.flight()[0] > charge, timeout=3)
        yield self.wait(.5)
        self.record(CASES[10], abs(self.flight()[0]-charge-15) < .01, charge_before=charge,
                    charge_after=self.flight()[0], target_slot=int(prop(target, 'RosterIndex')))


def main():
    if unreal is None and '--list' in sys.argv:
        return {'status':'not_run', 'planned_tests':CASES, 'hardware_claim':False}
    runner = FlightTests()
    try:
        started = runner.begin()
    except Exception:
        runner.finish('error', traceback.format_exc())
        started = False
    if unreal and started:
        unreal._basketbroom_native_test = runner
    return {'status':'started' if started else runner.final_status, 'report':str(REPORT), 'planned_cases':len(CASES)}


if __name__ == '__main__':
    RESULT = main()
    if unreal is None:
        print(json.dumps(RESULT, indent=2))

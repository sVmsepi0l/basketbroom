"""Portable fixture checks; these do not claim actual HUD rendering or RPC delivery."""
import importlib.util
from pathlib import Path
import unittest

_spec = importlib.util.spec_from_file_location(
    '_bb_display_fixture', Path(__file__).resolve().parent / 'test_native_spells.py')
spells = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spells)


class ReadOnlyRider:
    def __init__(self, **values):
        self.values = values

    def get_editor_property(self, name):
        return self.values[name]


class Fixture(spells.NativeSpellTests):
    def __init__(self):
        self.pawn = ReadOnlyRider(
            SpellFeedback='Arresto Momentum HIT - target impeded. No follow-up stun.',
            SpellFeedbackRemaining=2.25, SpellCooldownRemaining=0., StunRemaining=0.)
        self.guest = ReadOnlyRider(ImpedimentRemaining=2.)
        self.events = []

    def wait_until(self, predicate, timeout):
        return {'predicate': predicate, 'timeout': timeout}

    def event(self, kind, **detail):
        self.events.append({'kind': kind, **detail})

    def require(self, condition, message):
        if not condition:
            raise RuntimeError(message)


class DisplayedImpedimentFixtureContract(unittest.TestCase):
    def begin_gate(self):
        fixture = Fixture()
        sequence = fixture.wait_for_displayed_impediment()
        wait = next(sequence)
        return fixture, sequence, wait['predicate']

    def test_queued_message_without_draw_cannot_unlock_followup(self):
        fixture, sequence, ready = self.begin_gate()
        self.assertFalse(ready())
        with self.assertRaisesRegex(RuntimeError, 'queued text alone is insufficient'):
            next(sequence)  # Simulate the wait expiring with no renderer draw.
        self.assertFalse(fixture.events[-1]['displayed_countdown_observed'])
        self.assertEqual(fixture.events[-1]['feedback_seconds_remaining'], 2.25)

    def test_brief_display_waits_for_native_confirmation_interval(self):
        fixture, sequence, ready = self.begin_gate()
        fixture.pawn.values['SpellFeedbackRemaining'] = 2.10
        self.assertFalse(ready())
        fixture.pawn.values['SpellFeedbackRemaining'] = 1.90
        self.assertTrue(ready())
        with self.assertRaises(StopIteration) as returned:
            next(sequence)
        self.assertEqual(returned.exception.value['feedback_seconds_remaining'], 1.90)
        self.assertTrue(fixture.events[-1]['displayed_countdown_observed'])

    def test_followup_still_requires_cooldown_and_stun_recovery(self):
        fixture, sequence, ready = self.begin_gate()
        fixture.pawn.values['SpellFeedbackRemaining'] = 1.2
        for key in ('SpellCooldownRemaining', 'StunRemaining'):
            fixture.pawn.values[key] = .01
            self.assertFalse(ready(), key)
            fixture.pawn.values[key] = 0.
        self.assertTrue(ready())
        sequence.close()

    def test_expired_notice_and_impediment_do_not_count_as_display_proof(self):
        fixture, sequence, ready = self.begin_gate()
        for timer in (0., -.1):
            fixture.pawn.values['SpellFeedbackRemaining'] = timer
            self.assertFalse(ready())
        fixture.pawn.values['SpellFeedbackRemaining'] = 1.2
        for timer in (0., .15):
            fixture.guest.values['ImpedimentRemaining'] = timer
            self.assertFalse(ready())
        fixture.guest.values['ImpedimentRemaining'] = 2.
        fixture.pawn.values['SpellFeedback'] = 'Basic Cast HIT'
        self.assertFalse(ready())
        sequence.close()

    def test_success_observes_state_without_writing_receipt_or_effect(self):
        fixture, sequence, ready = self.begin_gate()
        fixture.pawn.values['SpellFeedbackRemaining'] = 1.2
        before = (fixture.pawn.values.copy(), fixture.guest.values.copy())
        self.assertTrue(ready())
        with self.assertRaises(StopIteration):
            next(sequence)
        self.assertEqual((fixture.pawn.values, fixture.guest.values), before)
        # ReadOnlyRider has no action, setter, HUD or acknowledgment methods;
        # the actual gate can complete solely through public observations.
        self.assertEqual(len(fixture.events), 1)


if __name__ == '__main__':
    unittest.main()

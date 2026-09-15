"""Run from repository root: python -m unittest discover -s Rules -v"""
from copy import deepcopy
import json
import unittest

from basketbroom import Match, RulesError, default_roster, load_config


def goal(ball="quaffle", team="A", hoop=None, **evidence):
    return dict(kind="goal", ball=ball, attacking_team=team,
                hoop=hoop or ("large" if ball == "quaffle" else "small"),
                entire_ball=True, forward=True, teleported=False) | evidence


def catch(ball="snipe", player="A_scout_1", **evidence):
    return dict(kind="catch", ball=ball, player=player, secure_ms=1000,
                by_hand=True, mounted=True, inside_envelope=True) | evidence


def short_match():
    config = load_config()
    config["timing"].update(quarter_ms=10000, overtime_ms=5000, snitch_release_ms=5000)
    return Match(config=config)


def to_final_horn(match):
    for _ in range(4):
        match.advance(match.config["timing"]["quarter_ms"])
        if match.status == "quarter_break":
            match.resume()


def overtime(scores=None):
    match = short_match()
    if scores:
        match.scores = scores.copy()  # Controlled scenario fixture, never a game API.
    to_final_horn(match)
    match.certify()
    match.resume()
    return match


def donnybrook():
    match = overtime()
    match.advance(5000)
    match.certify()
    match.resume()
    return match


class ScoringTests(unittest.TestCase):
    def test_canonical_configuration(self):
        config = load_config()
        self.assertEqual(config["score"], dict(quaffle=13, quark=37, snipe=69,
                                             snitch_regulation=150, snitch_overtime=300))
        self.assertEqual(config["timing"]["quarter_ms"] * 4, 176 * 60 * 1000)
        geometry = config["geometry_ft"]
        scale = 1.45 ** (1.0 / 3.0)
        self.assertAlmostEqual(geometry["length"], 420 * scale)
        self.assertAlmostEqual(geometry["width"], 210 * scale)
        self.assertAlmostEqual(geometry["roof"], 138 * scale)
        self.assertAlmostEqual(geometry["net_apex"], 207 * scale)
        self.assertAlmostEqual(geometry["enclosure_length"], (420 + 900 / 30.48) * scale)
        self.assertEqual(geometry["large_hoop_diameter"], 22)
        self.assertEqual(geometry["small_hoop_diameter"], 13)
        self.assertEqual(geometry["restart_goal_offset"], 22)
        self.assertAlmostEqual(config["arena_volume"]["volume_m3"] /
                               config["arena_volume"]["baseline_volume_m3"], 1.45)

    def test_seven_balls_open_with_delayed_snitch(self):
        match = Match()
        self.assertEqual(len(match.balls), 7)
        self.assertEqual(sum(b["play_state"] == "live" for b in match.balls.values()), 6)
        match.advance(1320000)
        self.assertEqual(match.balls["snitch"]["play_state"], "live")

    def test_three_scoring_balls_resolve_independently(self):
        match = Match()
        match.process_batch(10, [goal(), goal("quark_1"), goal("quark_2", "B")])
        self.assertEqual(match.scores, {"A": 50, "B": 37})
        self.assertEqual(match.balls["snipe"]["play_state"], "live")
        self.assertEqual(match.status, "live")
        self.assertEqual(match.balls["quaffle"]["restart_team"], "B")

    def test_wrong_hoop_reverse_incomplete_teleported_never_score(self):
        for event in [goal(hoop="small"), goal("quark_1", hoop="large"),
                      goal(forward=False), goal(entire_ball=False), goal(teleported=True)]:
            with self.subTest(event=event):
                match = Match()
                match.process_batch(0, [event])
                self.assertEqual(match.scores, {"A": 0, "B": 0})
                self.assertEqual(match.balls[event["ball"]]["play_state"], "live")

    def test_own_goal_credits_attacking_team(self):
        match = Match()
        match.possess("B_chaser_1", "quaffle")
        match.release("B_chaser_1", "quaffle")
        match.process_batch(1, [goal(team="A")])
        self.assertEqual(match.scores["A"], 13)

    def test_invalid_batch_rolls_back_time_points_and_log(self):
        match = Match()
        before = deepcopy(match.__dict__)
        with self.assertRaises(RulesError):
            match.process_batch(10, [goal(), catch(player="A_chaser_1")])
        self.assertEqual(match.__dict__, before)

    def test_duplicate_ball_event_rejected(self):
        match = Match()
        with self.assertRaises(RulesError):
            match.process_batch(0, [goal(), goal(team="B")])
        self.assertEqual(match.scores["A"], 0)

    def test_scoring_restart_requires_defending_netminder(self):
        match = Match()
        match.process_batch(0, [goal()])
        with self.assertRaises(RulesError):
            match.restart("quaffle", "B_chaser_1")
        match.restart("quaffle", "B_netminder_1")
        self.assertEqual(match.balls["quaffle"]["controller"], "B_netminder_1")
        self.assertEqual(match.balls["quaffle"]["protection_until"], 3000)
        match.release("B_netminder_1", "quaffle")
        self.assertIsNone(match.balls["quaffle"]["protection_until"])

    def test_netminder_cannot_hold_multiple_restart_balls(self):
        match = Match()
        match.process_batch(0, [goal(), goal("quark_1")])
        match.restart("quaffle", "B_netminder_1")
        before = match.snapshot()
        with self.assertRaises(RulesError):
            match.restart("quark_1", "B_netminder_1")
        self.assertEqual(match.snapshot(), before)


class EligibilityTests(unittest.TestCase):
    def test_required_roster_distribution(self):
        roster = default_roster()
        roster[0]["role"] = "chaser"
        with self.assertRaises(RulesError):
            Match(roster)

    def test_unauthorized_carriers(self):
        for player in ("A_scout_1", "A_hurleyback_1"):
            with self.subTest(player=player), self.assertRaises(RulesError):
                Match().possess(player, "quaffle")

    def test_trapper_shooting_and_single_ball(self):
        match = Match()
        match.possess("A_trapper_1", "quaffle")
        with self.assertRaises(RulesError):
            match.possess("A_trapper_1", "quark_1")
        match.release("A_trapper_1", "quaffle")
        match.process_batch(0, [goal()])
        self.assertEqual(match.scores["A"], 13)

    def test_ranger_must_release_before_capture(self):
        match = Match()
        match.possess("A_ranger_1", "quark_1")
        with self.assertRaises(RulesError):
            match.process_batch(0, [catch(player="A_ranger_1")])
        match.release("A_ranger_1", "quark_1")
        match.process_batch(0, [catch(player="A_ranger_1")])
        self.assertEqual(match.scores["A"], 69)

    def test_capture_requires_every_evidence_field(self):
        for evidence in (dict(secure_ms=999), dict(by_hand=False), dict(mounted=False),
                         dict(inside_envelope=False)):
            with self.subTest(evidence=evidence), self.assertRaises(RulesError):
                Match().process_batch(0, [catch(**evidence)])

    def test_chase_balls_are_not_carried(self):
        with self.assertRaises(RulesError):
            Match().possess("A_scout_1", "snipe")

    def test_removed_player_cannot_play(self):
        match = Match()
        penalty = match.record_penalty("A_scout_1", "interference", "serious")
        match.resolve_penalty(penalty, disposition="penalty shot missed; removal applied")
        match.resume()
        with self.assertRaises(RulesError):
            match.process_batch(0, [catch()])
        match.advance(180000)
        match.process_batch(180000, [catch()])
        self.assertEqual(match.scores["A"], 69)


class ChaseClockTests(unittest.TestCase):
    def test_snipe_three_live_minutes_with_ten_second_warning(self):
        match = Match()
        match.process_batch(1000, [catch()])
        match.advance(170000)
        self.assertEqual(match.balls["snipe"]["dead_reason"], "timeout")
        self.assertEqual(match.log[-1]["kind"], "snipe_warning")
        match.advance(9999)
        self.assertEqual(match.balls["snipe"]["play_state"], "dead")
        match.advance(1)
        self.assertEqual(match.balls["snipe"]["play_state"], "live")

    def test_global_pause_freezes_snipe_and_removal_clock(self):
        match = Match()
        match.process_batch(0, [catch()])
        penalty = match.record_penalty("B_scout_1", "interference", "serious")
        match.resolve_penalty(penalty, disposition="shot missed")
        before = match.snapshot()
        self.assertEqual(match.advance(1000000), 0)
        self.assertEqual(match.snapshot(), before)

    def test_timeout_carries_quarter_break(self):
        match = Match()
        match.process_batch(2600000, [catch()])
        match.advance(40000)
        self.assertEqual(match.status, "quarter_break")
        self.assertEqual(match.advance(1000000), 0)
        match.resume()
        match.advance(139999)
        self.assertEqual(match.balls["snipe"]["play_state"], "dead")
        match.advance(1)
        self.assertEqual(match.balls["snipe"]["play_state"], "live")

    def test_overtime_clears_snipe_timeout(self):
        match = short_match()
        for _ in range(3):
            match.advance(10000)
            match.resume()
        match.process_batch(39000, [catch()])
        match.advance(1000)
        match.certify()
        match.resume()
        self.assertEqual(match.phase, "overtime")
        self.assertTrue(all(b["play_state"] == "live" for b in match.balls.values()))


class EndingTests(unittest.TestCase):
    def test_regulation_margin_boundaries(self):
        for margin, expected in ((0, "overtime"), (149, "overtime"), (150, "regulation"), (151, "regulation")):
            with self.subTest(margin=margin):
                match = short_match()
                match.scores["A"] = margin
                to_final_horn(match)
                self.assertEqual(match.status, "review")
                match.certify()
                self.assertEqual(match.phase, expected)
                self.assertEqual(match.winner, "A" if margin >= 150 else None)

    def test_snitch_catcher_can_lose_and_still_be_reckoner(self):
        match = short_match()
        match.scores["B"] = 151
        match.process_batch(5001, [catch("snitch")])
        self.assertIsNone(match.winner)
        match.certify()
        self.assertEqual(match.winner, "B")
        self.assertEqual(match.reckoner, "A_scout_1")

    def test_snitch_exact_tie_goes_to_catcher(self):
        match = short_match()
        match.scores["B"] = 150
        match.process_batch(5001, [catch("snitch")])
        self.assertEqual(match.certify(), "A")
        self.assertEqual(match.scores, {"A": 150, "B": 150})

    def test_ranger_catch_does_not_award_reckoner(self):
        match = short_match()
        match.process_batch(5001, [catch("snitch", "A_ranger_1")])
        match.certify()
        self.assertIsNone(match.reckoner)

    def test_simultaneous_points_count_before_snitch_ending(self):
        match = short_match()
        match.scores["B"] = 140
        match.process_batch(5001, [catch("snitch"), goal(team="B")])
        self.assertEqual(match.scores, {"A": 150, "B": 153})
        self.assertEqual(match.certify(), "B")

    def test_exact_horn_goal_does_not_count_and_batch_is_atomic(self):
        match = short_match()
        with self.assertRaises(RulesError):
            match.process_batch(10000, [goal()])
        self.assertEqual(match.now_ms, 0)
        match.process_batch(9999, [goal()])
        match.advance(1)
        self.assertEqual(match.status, "quarter_break")
        self.assertEqual(match.scores["A"], 13)

    def test_overtime_catch_worth_300(self):
        match = overtime()
        match.process_batch(match.now_ms, [catch("snitch")])
        self.assertEqual(match.scores["A"], 300)
        self.assertEqual(match.certify(), "A")

    def test_overtime_simultaneous_net_threshold(self):
        match = overtime({"A": 149, "B": 0})
        match.process_batch(match.now_ms, [goal(team="A"), goal("quark_1", "B")])
        self.assertEqual(match.margin, 125)
        self.assertEqual(match.status, "live")
        match.process_batch(match.now_ms + 1, [goal("quark_2", "A")])
        self.assertEqual(match.status, "review")
        self.assertEqual(match.certify(), "A")

    def test_overtime_horn_any_nonzero_lead_wins(self):
        match = overtime({"A": 1, "B": 0})
        match.advance(5000)
        self.assertEqual(match.certify(), "A")

    def test_penalty_blocks_certification_and_can_change_winner(self):
        match = short_match()
        match.scores["B"] = 140
        penalty = match.record_penalty("A_chaser_1", "denied goal", "moderate", "quark_1")
        match.process_batch(5001, [catch("snitch")])
        with self.assertRaises(RulesError):
            match.certify()
        match.resolve_penalty(penalty, disposition="B made Quark free shot")
        match.certify([dict(team="B", delta=37, reason="free shot", committed_ms=0)])
        self.assertEqual(match.winner, "B")

    def test_adjusted_overtime_threshold_resumes(self):
        match = overtime({"A": 149, "B": 0})
        match.process_batch(match.now_ms + 100, [goal()])
        timestamp = match.now_ms
        match.certify([dict(team="B", delta=37, reason="pre-termination penalty shot", committed_ms=timestamp)])
        self.assertEqual(match.status, "live")
        self.assertEqual(match.now_ms, timestamp)
        self.assertEqual(match.margin, 125)
        self.assertEqual(match.balls["snitch"]["play_state"], "live")

    def test_overturned_snitch_restores_phase_and_neutral_ball(self):
        match = short_match()
        match.process_batch(5001, [catch("snitch"), goal("quark_1", "B")])
        match.overturn_snitch("replay establishes a bobble")
        match.resume()
        self.assertEqual(match.scores, {"A": 0, "B": 37})
        self.assertEqual(match.now_ms, 5001)
        self.assertEqual(match.balls["snitch"]["play_state"], "live")


class DonnybrookTests(unittest.TestCase):
    def test_three_balls_positions_suspended(self):
        match = donnybrook()
        active = [key for key, ball in match.balls.items() if ball["phase_status"] == "active"]
        self.assertEqual(active, ["quark_1", "quark_2", "snipe"])
        match.possess("A_hurleyback_1", "quark_1")
        match.release("A_hurleyback_1", "quark_1")
        match.process_batch(match.now_ms, [catch(player="A_netminder_1")])
        self.assertEqual(match.certify(), "A")
        self.assertEqual(match.scores["A"], 69)

    def test_opposing_simultaneous_wins_void_and_reset(self):
        match = donnybrook()
        match.process_batch(match.now_ms, [catch(), goal("quark_1", "B")])
        self.assertEqual(match.status, "live")
        self.assertEqual(match.scores, {"A": 0, "B": 0})
        self.assertTrue(all(match.balls[key]["play_state"] == "live" for key in ("snipe", "quark_1", "quark_2")))
        match.process_batch(match.now_ms + 1, [goal("quark_2", "B")])
        self.assertEqual(match.certify(), "B")

    def test_carried_quark_prevents_donnybrook_snipe_capture(self):
        match = donnybrook()
        match.possess("A_scout_1", "quark_1")
        with self.assertRaises(RulesError):
            match.process_batch(match.now_ms, [catch()])

    def test_unexpired_removal_converts_to_donnybrook_exclusion(self):
        match = overtime()
        penalty = match.record_penalty("A_scout_1", "interference", "serious")
        match.resolve_penalty(penalty, disposition="penalty shot missed")
        match.resume()
        match.advance(5000)
        match.certify()
        match.resume()
        match.advance(1000000)
        self.assertFalse(match.eligible("A_scout_1", "snipe"))
        self.assertEqual(match.status, "live")


class ClosedRoofTests(unittest.TestCase):
    def test_default_crown_exit_is_atomic_rejection(self):
        match = Match()
        self.assertFalse(match.config["enable_legacy_crown_exit"])
        for ball in match.balls:
            before = deepcopy(match.__dict__)
            with self.assertRaisesRegex(RulesError, "closed pyramid net"):
                match.crown_exit(ball, [0, 0, 207])
            self.assertEqual(match.__dict__, before)
        match.possess("A_chaser_1", "quaffle")
        before = deepcopy(match.__dict__)
        with self.assertRaises(RulesError):
            match.crown_exit("quaffle", [0, 0, 138], "A_chaser_1", deliberate_delay=True)
        self.assertEqual(match.__dict__, before)


class LegacyCrownTests(unittest.TestCase):
    """Historical open-roof fixtures; not current regulation behavior."""
    def legacy_match(self):
        config = load_config()
        config["enable_legacy_crown_exit"] = True
        return Match(config=config)

    def test_crown_only_kills_one_ball_and_flag_survives_return(self):
        match = self.legacy_match()
        match.crown_exit("quaffle", [0, 0, 138], "A_chaser_1")
        self.assertEqual(match.balls["quaffle"]["play_state"], "dead")
        self.assertEqual(match.balls["quark_1"]["play_state"], "live")
        match.advance(2000)
        match.crown_return("quaffle")
        match.advance(1000)
        self.assertEqual(match.status, "live")
        self.assertEqual(match.penalties[0]["status"], "pending")
        match.pause()
        with self.assertRaises(RulesError):
            match.resume()
        match.resolve_penalty(1, disposition="captain declined restoration after advantage")
        match.resume()

    def test_missed_reentry_target_triggers_safety_stoppage(self):
        match = self.legacy_match()
        match.crown_exit("quark_1", [1, 2, 138])
        consumed = match.advance(10000)
        self.assertEqual(consumed, 3000)
        self.assertEqual(match.status, "paused")
        self.assertEqual(match.balls["quark_1"]["crown_mark"], [1, 2, 138])
        match.resume()
        self.assertEqual(match.balls["quark_1"]["play_state"], "live")

    def test_dead_roof_delay_is_moderate(self):
        match = self.legacy_match()
        match.crown_exit("bludger_1", [0, 0, 138], "A_hurleyback_1", deliberate_delay=True)
        self.assertEqual(match.penalties[0]["severity"], "moderate")

    def test_simultaneous_crown_returns_stop_once_and_preserve_timeout(self):
        match = self.legacy_match()
        match.process_batch(0, [catch()])
        match.advance(177000)
        match.crown_exit("quaffle", [0, 0, 138])
        match.crown_exit("quark_1", [1, 0, 138])
        match.advance(3000)
        self.assertEqual(match.status, "paused")
        self.assertTrue(all(b["play_state"] == "dead" for b in match.balls.values()))
        self.assertEqual(sum(e["kind"] == "stoppage" for e in match.log), 1)
        match.resume()
        self.assertEqual(match.balls["snipe"]["play_state"], "live")

    def test_winged_envelope_recall_has_no_crown_penalty(self):
        match = self.legacy_match()
        with self.assertRaises(RulesError):
            match.crown_exit("snipe", [0, 0, 138])
        match.recall_chase("snipe")
        self.assertEqual(match.penalties, [])
        self.assertEqual(match.balls["snipe"]["play_state"], "live")


class HurleyTests(unittest.TestCase):
    def hold(self, match, player="A_hurleyback_1", ball="bludger_1"):
        match.possess(player, ball, inspected_hurley=True)

    def test_individual_warning_and_exact_three_second_foul(self):
        match = Match()
        self.hold(match)
        match.advance(2000)
        self.assertTrue(match.hurleys["bludger_1"]["warned"])
        match.advance(1000)
        self.assertEqual(match.penalties[0]["reason"], "Illegal Prolonged Bludger Control")
        self.assertEqual(match.balls["bludger_1"]["restart_team"], "B")
        self.assertEqual(match.balls["bludger_2"]["play_state"], "live")

    def test_hurley_required_and_one_bludger_limit(self):
        match = Match()
        with self.assertRaises(RulesError):
            match.possess("A_hurleyback_1", "bludger_1")
        self.hold(match)
        with self.assertRaises(RulesError):
            self.hold(match, ball="bludger_2")

    def test_short_self_toss_keeps_individual_clock(self):
        match = Match()
        self.hold(match)
        match.advance(2500)
        match.release("A_hurleyback_1", "bludger_1")
        match.advance(200)
        self.hold(match)
        match.advance(300)
        self.assertEqual(match.penalties[0]["reason"], "Illegal Prolonged Bludger Control")

    def test_private_self_bank_does_not_reset(self):
        match = Match()
        self.hold(match)
        match.advance(2500)
        match.release("A_hurleyback_1", "bludger_1")
        match.flight_evidence("bludger_1", contact="net", contestable=False)
        self.hold(match)
        match.advance(500)
        self.assertTrue(match.penalties)

    def test_ten_foot_self_toss_resets_individual(self):
        match = Match()
        self.hold(match)
        match.advance(2500)
        match.release("A_hurleyback_1", "bludger_1")
        match.flight_evidence("bludger_1", distance_ft=10)
        self.hold(match)
        match.advance(1000)
        self.assertEqual(match.penalties, [])

    def test_team_relay_accumulates_six_seconds(self):
        match = Match()
        self.hold(match)
        match.advance(2500)
        match.release("A_hurleyback_1", "bludger_1")
        self.hold(match, "A_hurleyback_2")
        match.advance(2500)
        match.release("A_hurleyback_2", "bludger_1")
        self.hold(match)
        match.advance(1000)
        self.assertEqual(match.penalties[0]["reason"], "Team Relay Hoarding")

    def test_one_second_contestable_flight_resets_team(self):
        match = Match()
        self.hold(match)
        match.advance(2500)
        match.release("A_hurleyback_1", "bludger_1", contestable=True)
        match.advance(999)
        self.assertEqual(match.hurleys["bludger_1"]["team_ms"], 2500)
        match.advance(1)
        self.assertEqual(match.hurleys["bludger_1"]["team_ms"], 0)
        self.hold(match)
        match.advance(2500)
        self.assertEqual(match.penalties, [])

    def test_opponent_challenge_resets_team_not_individual(self):
        match = Match()
        self.hold(match)
        match.advance(2500)
        match.opponent_challenge("bludger_1", "B_hurleyback_1")
        self.assertEqual(match.hurleys["bludger_1"]["team_ms"], 0)
        match.advance(500)
        self.assertEqual(match.penalties[0]["reason"], "Illegal Prolonged Bludger Control")

    def test_team_clock_after_challenge_survives_teammate_handoff(self):
        match = Match()
        self.hold(match)
        match.advance(1000)
        match.opponent_challenge("bludger_1", "B_hurleyback_1")
        match.advance(1000)
        match.release("A_hurleyback_1", "bludger_1")
        self.hold(match, "A_hurleyback_2")
        self.assertEqual(match.hurleys["bludger_1"]["team_ms"], 1000)


class DeterminismTests(unittest.TestCase):
    def test_chunked_clock_matches_single_step(self):
        single, chunked = Match(), Match()
        for match in (single, chunked):
            match.process_batch(0, [catch()])
            match.possess("A_hurleyback_1", "bludger_1", inspected_hurley=True)
        single.advance(180000)
        for _ in range(1800):
            chunked.advance(100)
        self.assertEqual(single.snapshot(), chunked.snapshot())
        self.assertEqual(single.log, chunked.log)

    def test_repeated_command_stream_replays_identically(self):
        def run():
            match = Match()
            match.process_batch(1, [goal(), goal("quark_1", "B"), catch()])
            match.restart("quaffle", "B_netminder_1")
            match.advance(180000)
            match.process_batch(180001, [catch(player="B_scout_1")])
            return json.dumps(dict(state=match.snapshot(), events=match.log), sort_keys=True)
        self.assertEqual(run(), run())

    def test_public_snapshot_does_not_alias_live_state(self):
        match = Match()
        snapshot = match.snapshot()
        snapshot["scores"]["A"] = 500
        self.assertEqual(match.scores["A"], 0)

    def test_time_is_integer_and_monotonic(self):
        match = Match()
        for value in (1.1, -1, True):
            with self.subTest(value=value), self.assertRaises(RulesError):
                match.advance(value)
        match.advance(2)
        with self.assertRaises(RulesError):
            match.process_batch(1, [goal()])


if __name__ == "__main__":
    unittest.main()

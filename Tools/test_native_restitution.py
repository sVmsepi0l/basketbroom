"""Portable post-termination restitution checks for both match variants.

The shared regulation engine owns these rules in Basketbroom and Bloodbroom.
This runner supplies explicit official rulings and physical goal evidence; it
makes no claim about rendered gameplay, native contacts or remote networking.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bb_restitution_shots", ROOT / "Tools/test_native_penalty_shots.py")
SHOTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHOTS)
RUNNER = SHOTS.RUNNER
RUNNER.OUTPUT = ROOT / ".local/native-restitution"
RUNNER.PREAMBLE += r'''
Match snitch_review(std::int64_t opponent_score=0, bool in_overtime=false) {
 auto m=in_overtime?overtime():short_match(); m.scores[1]=opponent_score;
 bool ok=m.process_batch(in_overtime?m.now_ms+100:5001,{caught(4)}); assert(ok);return m;
}
bool terminal_shot(Match& m, int ball, int offender, int shooter, int keeper, bool free_shot,
                   PenaltyShotOutcome outcome=PenaltyShotOutcome::Goal) {
 const auto ending=m.ending; const auto period=m.period_elapsed_ms; const auto at=m.now_ms;
 const int id=m.record_penalty(offender,"reported pre-termination conduct",
     free_shot?Severity::Moderate:Severity::Serious,ball,at-1);
 CHECK(id>0&&m.start_penalty_shot(id,ball,shooter,keeper,free_shot));
 CHECK(m.penalty_shot.post_termination&&m.status==Status::Review&&m.winner==-1);
 CHECK(m.advance(100000)==0&&m.now_ms==at&&m.period_elapsed_ms==period);
 CHECK(!m.certify()&&!m.resume());
 CHECK(m.release_penalty_shot(shooter)&&m.advance_penalty_shot(500)==500);
 CHECK(m.complete_penalty_shot(outcome,goal(ball,m.players[shooter].team)));
 CHECK(m.penalties[id-1].pending&&!m.certify());
 CHECK(m.restart_penalty_shot(keeper)&&!m.penalties[id-1].pending);
 CHECK(m.status==Status::Review&&m.now_ms==at&&m.period_elapsed_ms==period);
 CHECK(m.ending.active==ending.active&&m.ending.reason==ending.reason&&m.ending.at_ms==ending.at_ms
     &&m.ending.catching_team==ending.catching_team&&m.ending.catcher==ending.catcher
     &&m.ending.winning_team==ending.winning_team&&m.ending.catch_points==ending.catch_points);
 CHECK(count_log(m,"post_termination_shot_started")==count_log(m,"post_termination_shot_served"));
 return true;
}
'''
RUNNER.CASES = [
("snitch_restitution_can_reverse_winner_without_erasing_capture", r'''for(bool free_shot:{false,true}){auto m=snitch_review(140);CHECK(terminal_shot(m,1,1,9,0,free_shot));CHECK(score_is(m,150,177)&&m.certify()&&m.winner==1&&m.reckoner==7&&m.status==Status::Complete);}'''),
("exact_tie_still_goes_to_original_catching_team", r'''auto m=snitch_review(113);CHECK(terminal_shot(m,2,1,9,0,true));CHECK(score_is(m,150,150)&&m.certify()&&m.winner==0&&m.reckoner==7);'''),
("overtime_snitch_stays_terminal_below_margin_after_shot", r'''auto m=snitch_review(290,true);CHECK(terminal_shot(m,0,1,9,0,false));CHECK(score_is(m,300,303)&&m.certify()&&m.winner==1&&m.status==Status::Complete);'''),
("ranger_remains_ineligible_for_reckoner_after_restitution", r'''auto m=short_match();CHECK(m.process_batch(5001,{caught(4,4)}));CHECK(terminal_shot(m,0,1,9,0,true)&&m.certify()&&m.winner==0&&m.reckoner==-1);'''),
("regulation_horn_retest_can_send_apparent_winner_to_overtime", r'''auto m=short_match();m.scores[0]=150;final_horn(m);CHECK(terminal_shot(m,1,1,9,0,true));CHECK(m.certify()&&m.phase==Phase::Overtime&&m.status==Status::PhaseBreak&&m.winner==-1&&score_is(m,150,37));'''),
("regulation_horn_retest_can_award_threshold_victory", r'''auto m=short_match();m.scores[0]=149;final_horn(m);CHECK(terminal_shot(m,0,9,1,8,false));CHECK(m.certify()&&m.winner==0&&score_is(m,162,0));'''),
("regulation_horn_miss_preserves_threshold_victory", r'''auto m=short_match();m.scores[0]=150;final_horn(m);CHECK(terminal_shot(m,0,1,9,0,true,PenaltyShotOutcome::Miss));CHECK(m.certify()&&m.winner==0&&score_is(m,150,0));'''),
("overtime_margin_restitution_resumes_original_live_timestamp", r'''auto m=overtime(149);CHECK(m.process_batch(m.now_ms+100,{goal(0)}));auto at=m.now_ms;auto period=m.period_elapsed_ms;CHECK(terminal_shot(m,1,1,9,0,false));CHECK(m.certify()&&m.status==Status::Live&&!m.ending.active&&m.winner==-1&&m.margin()==125&&m.now_ms==at&&m.period_elapsed_ms==period&&m.balls[1].controller==0&&m.balls[1].protection_until==at+3000&&m.balls[4].live);CHECK(m.players[1].removed_until==at+180000&&m.advance(1)==1&&m.players[1].removed_until==at+180000);'''),
("overtime_margin_retest_keeps_a_remaining_150_point_lead", r'''auto m=overtime(149);CHECK(m.process_batch(m.now_ms+100,{goal(0),goal(1)}));CHECK(m.margin()==199);CHECK(terminal_shot(m,2,1,9,0,true));CHECK(m.margin()==162&&m.certify()&&m.winner==0);'''),
("overtime_restorative_goal_does_not_replace_margin_ending", r'''auto m=overtime(149);CHECK(m.process_batch(m.now_ms+100,{goal(0)}));auto ended=count_log(m,"provisional_end");CHECK(terminal_shot(m,1,9,1,8,false));CHECK(count_log(m,"provisional_end")==ended&&m.ending.reason=="overtime_margin"&&m.certify()&&m.winner==0);'''),
("overtime_horn_restitution_can_flip_the_winner", r'''auto m=overtime(1);m.advance(5000);CHECK(terminal_shot(m,0,1,9,0,true));CHECK(m.certify()&&m.winner==1&&score_is(m,1,13));'''),
("overtime_horn_restitution_tie_enters_donnybrook", r'''auto m=overtime(13);m.advance(5000);CHECK(terminal_shot(m,0,1,9,0,false));CHECK(m.certify()&&m.status==Status::PhaseBreak&&m.phase==Phase::Donnybrook&&m.winner==-1&&m.players[1].donnybrook_excluded);'''),
("timeout_serves_remedy_without_consuming_live_time", r'''auto m=snitch_review();auto at=m.now_ms;CHECK(m.record_penalty(1,"late reported foul",Severity::Serious,0,at-1)==1&&m.start_penalty_shot(1,0,9,0));CHECK(m.advance_penalty_shot(1000000)==5000&&m.penalty_shot.outcome==PenaltyShotOutcome::Timeout&&m.now_ms==at&&m.penalties[0].pending&&!m.certify());CHECK(m.restart_penalty_shot(0)&&m.certify()&&m.winner==0&&m.players[1].removed_until==at+180000);'''),
("mixed_sequential_remedies_keep_same_ending_and_distinct_removals", r'''auto m=snitch_review(100);CHECK(m.record_penalty(1,"Moderate",Severity::Moderate,0,5000)==1&&m.record_penalty(2,"Serious",Severity::Serious,0,5000)==2);CHECK(m.start_penalty_shot(1,0,9,0,true)&&m.release_penalty_shot(9)&&m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(0,1))&&m.restart_penalty_shot(0));CHECK(!m.certify()&&m.start_penalty_shot(2,0,10,0)&&m.release_penalty_shot(10)&&m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(0,1))&&m.restart_penalty_shot(0));CHECK(m.ending.reason=="snitch"&&m.ending.at_ms==5001&&m.players[1].removed_until==-1&&m.players[2].removed_until==185001&&score_is(m,150,126)&&m.certify());CHECK(count_log(m,"post_termination_shot_started")==2&&count_log(m,"post_termination_shot_served")==2);'''),
("other_pretermination_penalties_still_block_certification", r'''auto m=snitch_review();CHECK(m.record_penalty(2,"Severe",Severity::Severe,2,5000)==1);CHECK(terminal_shot(m,0,1,9,0,true)&&!m.certify()&&m.resolve_penalty(1,"ejection served")&&m.certify()&&m.players[2].ejected);'''),
("late_reported_foul_at_exact_ending_timestamp_is_eligible", r'''auto m=snitch_review();CHECK(m.record_penalty(1,"same timestamp",Severity::Moderate,0,m.ending.at_ms)==1&&m.start_penalty_shot(1,0,9,0,true));'''),
("post_ending_or_negative_conduct_timestamp_rejects_atomically", r'''for(auto offset:{1,-5002}){auto m=snitch_review();CHECK(m.record_penalty(1,"reported foul",Severity::Moderate,0,5000)==1);m.penalties[0].committed_ms=m.ending.at_ms+offset;auto before=fingerprint(m);CHECK(!m.start_penalty_shot(1,0,9,0,true)&&fingerprint(m)==before&&m.penalties[0].pending);}'''),
("uncertain_terminal_reason_or_mismatched_phase_stays_pending", r'''for(int v=0;v<6;++v){auto m=snitch_review();CHECK(m.record_penalty(1,"reported foul",Severity::Moderate,0,5000)==1);if(v==0)m.ending.reason="unknown";if(v==1)m.ending.reason="overtime_margin";if(v==2)m.ending.active=false;if(v==3)++m.ending.at_ms;if(v==4)m.status=Status::Paused;if(v==5)m.phase=Phase::Donnybrook;auto before=fingerprint(m);CHECK(!m.start_penalty_shot(1,0,9,0,true)&&fingerprint(m)==before);}'''),
("certified_match_cannot_reopen_for_another_shot", r'''auto m=snitch_review();CHECK(m.certify()&&m.record_penalty(1,"late report after certification",Severity::Moderate,0,5000)==1);auto before=fingerprint(m);CHECK(!m.start_penalty_shot(1,0,9,0,true)&&fingerprint(m)==before);'''),
("donnybrook_terminal_conflict_requires_official_adjudication", r'''auto m=donnybrook();CHECK(m.process_batch(m.now_ms+1,{caught(3)}));CHECK(m.record_penalty(1,"pre-termination denial",Severity::Serious,1,m.now_ms-1)==1);auto before=fingerprint(m);CHECK(!m.start_penalty_shot(1,1,9,0)&&fingerprint(m)==before&&!m.certify()&&m.penalties[0].pending&&m.winner==-1);'''),
("every_reserved_stage_blocks_overturn_and_manual_adjudication", r'''for(int stage=0;stage<3;++stage){auto m=snitch_review();CHECK(m.record_penalty(1,"denial",Severity::Moderate,0,5000)==1&&m.start_penalty_shot(1,0,9,0,true));if(stage>=1)CHECK(m.release_penalty_shot(9));if(stage==2)CHECK(m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(0,1)));auto before=fingerprint(m);CHECK(!m.overturn_snitch("replay bobble")&&fingerprint(m)==before);CHECK(!m.resolve_penalty(1,"skip attempt")&&fingerprint(m)==before);CHECK(!m.certify({{1,13,"fabricated score",5000}})&&fingerprint(m)==before);CHECK(!m.resume()&&fingerprint(m)==before);}'''),
("overturned_catch_after_served_shot_preserves_restitution_points", r'''auto m=snitch_review(10);auto at=m.now_ms;CHECK(terminal_shot(m,0,1,9,0,true));CHECK(m.overturn_snitch("replay shows bobble")&&m.status==Status::Paused&&score_is(m,0,23)&&m.now_ms==at&&m.resume()&&m.balls[4].live);'''),
("original_simultaneous_goal_remedy_is_not_overwritten", r'''auto m=short_match();CHECK(m.process_batch(5001,{caught(4),goal(0,1)}));CHECK(m.record_penalty(1,"denied Quaffle",Severity::Moderate,0,5000)==1);auto before=fingerprint(m);CHECK(!m.start_penalty_shot(1,0,9,0,true)&&fingerprint(m)==before&&m.balls[0].dead_reason=="score"&&score_is(m,150,13));'''),
("unreserved_second_quark_serves_matching_restoration", r'''auto m=short_match();CHECK(m.process_batch(5001,{caught(4),goal(1,1)}));CHECK(m.record_penalty(1,"denied Quark",Severity::Moderate,1,5000)==1&&m.start_penalty_shot(1,2,9,0,true));CHECK(m.balls[1].dead_reason=="score"&&m.balls[1].restart_team==0&&m.scores[1]==37);'''),
("unavailable_defending_keeper_keeps_remedy_pending", r'''auto m=snitch_review();CHECK(m.record_penalty(1,"denial",Severity::Serious,0,5000)==1);m.players[0].ejected=true;auto before=fingerprint(m);CHECK(!m.start_penalty_shot(1,0,9,0)&&fingerprint(m)==before&&!m.certify());'''),
("tampered_terminal_context_cannot_advance_release_or_restart", r'''for(int stage=0;stage<3;++stage)for(int v=0;v<4;++v){auto m=snitch_review();CHECK(m.record_penalty(1,"denial",Severity::Moderate,0,5000)==1&&m.start_penalty_shot(1,0,9,0,true));if(stage>=1)CHECK(m.release_penalty_shot(9));if(stage==2)CHECK(m.complete_penalty_shot(PenaltyShotOutcome::Miss));if(v==0)m.penalty_shot.post_termination=false;if(v==1)m.status=Status::Paused;if(v==2)++m.now_ms;if(v==3)m.penalties[0].committed_ms=m.ending.at_ms+1;auto before=fingerprint(m);CHECK(m.advance_penalty_shot(1)==-1&&fingerprint(m)==before);CHECK(!m.release_penalty_shot(9)&&fingerprint(m)==before);CHECK(!m.restart_penalty_shot(0)&&fingerprint(m)==before);}'''),
("moderate_terminal_shot_keeps_all_existing_removal_clocks", r'''auto m=snitch_review();m.players[2].removed_until=m.now_ms+7000;auto until=m.players[2].removed_until;CHECK(terminal_shot(m,0,1,9,0,true));CHECK(m.players[1].removed_until==-1&&m.players[2].removed_until==until&&count_log(m,"temporary_removal")==0);'''),
("terminal_shot_audit_names_original_event_and_timestamp", r'''auto m=snitch_review();CHECK(terminal_shot(m,0,1,9,0,false));int found=0;for(const auto& e:m.log)if(e.kind=="post_termination_shot_started"||e.kind=="post_termination_shot_served"){CHECK(e.penalty_id==1&&e.at_ms==5001&&e.value==5001&&e.reason=="snitch"&&e.ball==0);++found;}CHECK(found==2&&count_log(m,"provisional_end")==1);'''),
]


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        code = RUNNER.main()
    path = RUNNER.OUTPUT / "results.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report.pop("reference_scenarios", None)
    report["scope"] = "Portable post-termination restitution shared by Basketbroom and Bloodbroom; no rendered/native contact/network claim"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())

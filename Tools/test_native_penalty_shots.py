"""Compile focused portable Serious penalty-shot scenarios without Unreal.

Reuses the established compiler runner; --compiler, --vcvars and --emit-only
have the same behavior as test_native_rules.py. Physical marks/flight and
wand/input restrictions belong to the host integration, not this rules test.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("_bb_shot_compiler", ROOT / "Tools/test_native_rules.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
RUNNER.OUTPUT = ROOT / ".local/native-penalty-shots"
# Extend the existing state fingerprint so failed calls must preserve the new
# reservation and every attempt field as well as the original ledger/log/state.
RUNNER.PREAMBLE = RUNNER.PREAMBLE.replace(
    "<<p.crown_restoration_receiver;", "<<p.crown_restoration_receiver<<','<<p.penalty_shot_reserved;")
RUNNER.PREAMBLE = RUNNER.PREAMBLE.replace(" return s.str();", r'''
 const auto& shot=m.penalty_shot;
 s<<int(shot.stage)<<','<<int(shot.outcome)<<','<<shot.penalty_id<<','<<shot.ball<<','<<shot.shooter<<','<<shot.netminder<<','<<shot.attacking_team<<','<<shot.elapsed_ms<<','<<shot.released_ms<<','<<shot.awarded_points<<','<<shot.free_shot<<','<<shot.post_termination<<';';
 return s.str();''')
assert "<<p.penalty_shot_reserved" in RUNNER.PREAMBLE and "<<shot.awarded_points" in RUNNER.PREAMBLE
RUNNER.PREAMBLE += r'''
Match serious(int ball=-1) {
 Match m; bool ok=m.record_penalty(1,"Serious BB0 conduct",Severity::Serious,ball)==1;
 assert(ok); return m;
}
Match ready(int ball=0) {
 auto m=serious(ball); bool ok=m.start_penalty_shot(1,ball,9,0); assert(ok); return m;
}
Match released(int ball=0) {
 auto m=ready(ball); bool ok=m.release_penalty_shot(9); assert(ok); return m;
}
Match missed(int ball=0) {
 auto m=released(ball); bool ok=m.complete_penalty_shot(PenaltyShotOutcome::Miss); assert(ok); return m;
}
'''
RUNNER.CASES = [
("canonical_attempt_clock_and_invalid_config", r'''Match m; CHECK(m.config.penalty_shot_ms==5000); for(Millis ms:{0,-1}){Config c; c.penalty_shot_ms=ms; Match invalid(c); CHECK(!invalid.is_valid());}'''),
("requires_pending_serious_at_stoppage", r'''for(auto severity:{Severity::Minor,Severity::Moderate,Severity::Severe,Severity::Catastrophic}){Match m; CHECK(m.record_penalty(1,"conduct",severity)==1); if(m.status==Status::Live)CHECK(m.pause()); auto before=fingerprint(m); CHECK(!m.start_penalty_shot(1,0,9,0)&&fingerprint(m)==before);} auto m=serious(); CHECK(m.resolve_penalty(1,"external adjudication")); auto before=fingerprint(m); CHECK(!m.start_penalty_shot(1,0,9,0)&&fingerprint(m)==before);'''),
("invalid_identifiers_are_atomic", r'''for(auto args:std::vector<std::array<int,4>>{{0,0,9,0},{2,0,9,0},{1,-1,9,0},{1,7,9,0},{1,0,-1,0},{1,0,16,0},{1,0,9,-1},{1,0,9,16},{1,0,1,0},{1,0,9,8},{1,0,9,2},{1,0,13,0},{1,0,15,0}}){auto m=serious(); auto before=fingerprint(m); CHECK(!m.start_penalty_shot(args[0],args[1],args[2],args[3])&&fingerprint(m)==before);}'''),
("ball_type_matches_denied_chance_or_default", r'''for(int denied:{-1,3,4,5,6}){auto m=serious(denied); auto before=fingerprint(m); CHECK(!m.start_penalty_shot(1,1,9,0)&&fingerprint(m)==before); CHECK(m.start_penalty_shot(1,0,9,0));} for(int denied:{1,2}){auto m=serious(denied); auto before=fingerprint(m); CHECK(!m.start_penalty_shot(1,0,9,0)&&fingerprint(m)==before); CHECK(m.start_penalty_shot(1,3-denied,9,0));}'''),
("removed_ejected_or_absent_participants_reject", r'''for(int variant=0;variant<6;++variant){auto m=serious(); if(variant==0)m.players[9].ejected=true; if(variant==1)m.players[9].removed_until=100; if(variant==2)m.players[9].donnybrook_excluded=true; if(variant==3)m.players[0].ejected=true; if(variant==4)m.players[0].removed_until=100; if(variant==5)m.players[0].role=Role::Chaser; auto before=fingerprint(m); CHECK(!m.start_penalty_shot(1,0,9,0)&&fingerprint(m)==before);} Match m; CHECK(m.record_penalty(0,"keeper offense",Severity::Serious)==1); auto before=fingerprint(m); CHECK(!m.start_penalty_shot(1,0,9,0)&&fingerprint(m)==before);'''),
("every_existing_dead_ball_remedy_is_preserved", r'''for(const char* reason:{"score","crown","crown_restart","timeout","penalty","removed","scheduled_release","hurley_foul"}){auto m=serious(); m.balls[0].dead_reason=reason; auto before=fingerprint(m); CHECK(!m.start_penalty_shot(1,0,9,0)&&fingerprint(m)==before);}'''),
("outstanding_crown_restoration_owns_ball", r'''Match m(legacy_crown_config()); CHECK(m.crown_exit(0,{1,2,138},2)&&m.crown_return(0)); CHECK(m.record_penalty(1,"conduct",Severity::Serious)==2); auto before=fingerprint(m); CHECK(!m.start_penalty_shot(2,0,9,0)&&fingerprint(m)==before); CHECK(m.prepare_crown_restart(1)); before=fingerprint(m); CHECK(!m.start_penalty_shot(2,0,9,0)&&fingerprint(m)==before);'''),
("conduct_award_reservation_is_preserved", r'''Match m; CHECK(m.record_penalty(2,"moderate",Severity::Moderate)==1&&m.pause()&&m.queue_conduct_possession_award(1,0,1)); CHECK(m.record_penalty(1,"Serious",Severity::Serious)==2); auto before=fingerprint(m); CHECK(!m.start_penalty_shot(2,0,9,0)&&fingerprint(m)==before);'''),
("ready_reserves_only_shooter_and_applies_removal", r'''auto m=ready(); CHECK(m.status==Status::Paused&&m.now_ms==0&&m.period_elapsed_ms==0); CHECK(m.penalty_shot.stage==PenaltyShotStage::Ready&&m.penalty_shot.penalty_id==1&&m.penalty_shot.shooter==9&&m.penalty_shot.netminder==0); CHECK(m.penalties[0].pending&&m.penalties[0].penalty_shot_reserved&&m.players[1].removed_until==180000&&!m.eligible(1,0)); for(int i=0;i<7;++i) CHECK(!m.balls[i].live&&m.balls[i].controller==(i==0?9:-1)); CHECK(m.balls[0].dead_reason=="penalty_shot"&&m.balls[0].restart_team==0&&count_log(m,"penalty_shot_started")==1);'''),
("one_active_shot_cannot_be_replaced_or_duplicated", r'''auto m=ready(); CHECK(m.record_penalty(2,"another Serious",Severity::Serious,1)==2); auto before=fingerprint(m); CHECK(!m.start_penalty_shot(1,0,9,0)&&fingerprint(m)==before); CHECK(!m.start_penalty_shot(2,1,10,0)&&fingerprint(m)==before);'''),
("generic_paths_cannot_bypass_reserved_shot", r'''for(auto m:{ready(),released(),missed()}){auto before=fingerprint(m); CHECK(!m.resolve_penalty(1,"pretend served")&&fingerprint(m)==before); CHECK(!m.resume()&&fingerprint(m)==before); CHECK(!m.certify()&&fingerprint(m)==before); CHECK(!m.possess(9,0)&&fingerprint(m)==before); CHECK(!m.release(9,0)&&fingerprint(m)==before); CHECK(!m.restart(0,0)&&fingerprint(m)==before); CHECK(!m.process_batch(m.now_ms,{goal(0,1)})&&fingerprint(m)==before); CHECK(!m.crown_exit(0,{0,0,138})&&fingerprint(m)==before); CHECK(!m.possess(13,5,true)&&fingerprint(m)==before);}'''),
("shot_clock_never_consumes_live_or_removal_time", r'''auto m=ready(); auto before=fingerprint(m); CHECK(m.advance(1000000)==0&&fingerprint(m)==before); CHECK(m.advance_penalty_shot(4000)==4000&&m.penalty_shot.elapsed_ms==4000&&m.now_ms==0&&m.period_elapsed_ms==0&&m.players[1].removed_until==180000);'''),
("only_designated_shooter_gets_one_release", r'''auto m=ready(); for(int player:{-1,0,1,10,16}){auto before=fingerprint(m); CHECK(!m.release_penalty_shot(player)&&fingerprint(m)==before);} CHECK(m.advance_penalty_shot(2000)==2000&&m.release_penalty_shot(9)); CHECK(m.penalty_shot.stage==PenaltyShotStage::InFlight&&m.penalty_shot.released_ms==2000&&m.balls[0].controller==-1&&!m.balls[0].live); auto before=fingerprint(m); CHECK(!m.release_penalty_shot(9)&&fingerprint(m)==before);'''),
("goal_and_miss_require_release_timeout_requires_deadline", r'''auto m=ready(); auto before=fingerprint(m); CHECK(!m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(0,1))&&fingerprint(m)==before); CHECK(!m.complete_penalty_shot(PenaltyShotOutcome::Miss)&&fingerprint(m)==before); CHECK(!m.complete_penalty_shot(PenaltyShotOutcome::Timeout)&&fingerprint(m)==before); CHECK(!m.complete_penalty_shot(PenaltyShotOutcome::None)&&fingerprint(m)==before);'''),
("five_second_deadline_times_out_held_or_flying_ball", r'''for(bool release:{false,true}){auto m=ready(); if(release)CHECK(m.release_penalty_shot(9)); CHECK(m.advance_penalty_shot(4999)==4999&&m.penalty_shot.outcome==PenaltyShotOutcome::None); CHECK(m.advance_penalty_shot(1000000)==1&&m.penalty_shot.elapsed_ms==5000&&m.penalty_shot.outcome==PenaltyShotOutcome::Timeout&&m.penalty_shot.stage==PenaltyShotStage::AwaitingRestart); CHECK(m.now_ms==0&&m.scores[1]==0&&m.penalties[0].pending&&m.balls[0].controller==-1); auto before=fingerprint(m); CHECK(!m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(0,1))&&fingerprint(m)==before); CHECK(m.advance_penalty_shot(1)==-1&&fingerprint(m)==before); CHECK(m.restart_penalty_shot(0)&&m.resume());}'''),
("invalid_attempt_clock_is_atomic", r'''auto m=ready(); auto before=fingerprint(m); CHECK(m.advance_penalty_shot(-1)==-1&&fingerprint(m)==before); CHECK(m.advance_penalty_shot(0)==0&&fingerprint(m)==before); CHECK(m.advance_penalty_shot(std::numeric_limits<Millis>::max())==5000&&m.penalty_shot.outcome==PenaltyShotOutcome::Timeout);'''),
("every_goal_evidence_field_is_checked_atomically", r'''for(int variant=0;variant<9;++variant){auto m=released(); auto e=goal(0,1); if(variant==0)e.kind=EventKind::Catch; if(variant==1)e.ball=1; if(variant==2)e.attacking_team=0; if(variant==3)e.player=10; if(variant==4)e.hoop=Hoop::Small; if(variant==5)e.entire_ball=false; if(variant==6)e.forward=false; if(variant==7)e.teleported=true; if(variant==8)e.ball=-1; auto before=fingerprint(m); CHECK(!m.complete_penalty_shot(PenaltyShotOutcome::Goal,e)&&fingerprint(m)==before);}'''),
("quaffle_and_both_quarks_score_ordinary_values", r'''for(int ball:{0,1,2}){auto m=released(ball); auto e=goal(ball,1); e.player=9; CHECK(m.advance_penalty_shot(1234)==1234&&m.complete_penalty_shot(PenaltyShotOutcome::Goal,e)); CHECK(m.scores[1]==(ball==0?13:37)&&m.penalty_shot.awarded_points==m.scores[1]&&m.last_awards.size()==1&&m.last_awards[0].player==9); CHECK(m.penalties[0].pending&&m.penalties[0].penalty_shot_reserved&&m.balls[ball].dead_reason=="penalty_shot_restart"&&m.now_ms==0&&m.status==Status::Paused); CHECK(count_log(m,"points")==1&&count_log(m,"penalty_resolved")==0);}'''),
("miss_scores_nothing_and_stays_pending", r'''auto m=missed(); CHECK(m.scores[1]==0&&m.last_awards.empty()&&m.penalty_shot.outcome==PenaltyShotOutcome::Miss&&m.penalties[0].pending); CHECK(count_log(m,"points")==0&&count_log(m,"penalty_shot_completed")==1);'''),
("completion_is_exactly_once", r'''for(auto outcome:{PenaltyShotOutcome::Goal,PenaltyShotOutcome::Miss}){auto m=released(); CHECK(m.complete_penalty_shot(outcome,goal(0,1))); auto before=fingerprint(m); CHECK(!m.complete_penalty_shot(outcome,goal(0,1))&&fingerprint(m)==before); CHECK(!m.release_penalty_shot(9)&&fingerprint(m)==before);}'''),
("score_overflow_does_not_consume_attempt", r'''auto m=released(); m.scores[1]=std::numeric_limits<std::int64_t>::max()-1; auto before=fingerprint(m); CHECK(!m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(0,1))&&fingerprint(m)==before&&m.penalty_shot.stage==PenaltyShotStage::InFlight);'''),
("only_defending_netminder_can_restart_after_completion", r'''auto m=ready(); auto before=fingerprint(m); CHECK(!m.restart_penalty_shot(0)&&fingerprint(m)==before); m=missed(); for(int p:{-1,1,8,9,16}){before=fingerprint(m); CHECK(!m.restart_penalty_shot(p)&&fingerprint(m)==before);} CHECK(m.restart_penalty_shot(0)); CHECK(m.penalty_shot.stage==PenaltyShotStage::Complete&&!m.penalties[0].pending&&!m.penalties[0].penalty_shot_reserved&&m.balls[0].live&&m.balls[0].controller==0&&m.balls[0].dead_reason.empty()&&m.balls[0].protection_until==3000); for(int b=1;b<7;++b)CHECK(!m.balls[b].live); CHECK(count_log(m,"penalty_resolved")==1&&count_log(m,"penalty_shot_restart")==1&&count_log(m,"protected_restart")==1); before=fingerprint(m); CHECK(!m.restart_penalty_shot(0)&&fingerprint(m)==before); CHECK(m.resume()&&m.balls[0].controller==0&&m.balls[0].protection_until==3000&&m.balls[1].live);'''),
("restart_requires_available_keeper_and_free_hands", r'''for(int variant=0;variant<3;++variant){auto m=missed(); if(variant==0)m.players[0].ejected=true; if(variant==1)m.players[0].removed_until=10; if(variant==2)m.balls[1].controller=0; auto before=fingerprint(m); CHECK(!m.restart_penalty_shot(0)&&fingerprint(m)==before&&m.penalties[0].pending);}'''),
("restart_overflow_is_atomic", r'''auto m=missed(); m.now_ms=std::numeric_limits<Millis>::max()-1; m.players[1].removed_until=std::numeric_limits<Millis>::max(); auto before=fingerprint(m); CHECK(!m.restart_penalty_shot(0)&&fingerprint(m)==before);'''),
("removal_is_three_live_minutes_with_pause_freeze", r'''auto m=missed(); CHECK(m.restart_penalty_shot(0)&&m.resume()); CHECK(m.advance(179999)==179999&&!m.eligible(1,0)); CHECK(m.pause()); auto before=fingerprint(m); CHECK(m.advance(1000000)==0&&fingerprint(m)==before); CHECK(m.resume()&&m.advance(1)==1&&m.eligible(1,0));'''),
("removal_does_not_shorten_existing_removal", r'''auto m=serious(); m.players[1].removed_until=200000; CHECK(m.start_penalty_shot(1,0,9,0)&&m.players[1].removed_until==200000);'''),
("quarter_break_is_preserved_until_shot_restart_and_resume", r'''auto m=short_match(); CHECK(m.advance(10000)==10000&&m.status==Status::QuarterBreak); CHECK(m.record_penalty(1,"late reported Serious",Severity::Serious)==1&&m.start_penalty_shot(1,0,9,0)); CHECK(m.advance_penalty_shot(5000)==5000&&m.restart_penalty_shot(0)); CHECK(m.status==Status::QuarterBreak&&m.quarter==1&&m.resume()&&m.quarter==2&&m.balls[0].controller==0);'''),
("preexisting_snitch_review_serves_a_real_shot_before_certification", r'''auto m=short_match(); CHECK(m.process_batch(5001,{caught(4)})); CHECK(m.record_penalty(1,"reported pre-end Serious",Severity::Serious,-1,5000)==1); CHECK(m.start_penalty_shot(1,0,9,0)&&m.penalty_shot.post_termination); auto before=fingerprint(m); CHECK(!m.certify()&&fingerprint(m)==before&&m.winner==-1&&m.penalties[0].pending); CHECK(m.advance_penalty_shot(5000)==5000&&m.restart_penalty_shot(0)); CHECK(m.status==Status::Review&&m.ending.reason=="snitch"&&m.ending.at_ms==5001&&m.certify()&&m.winner==0);'''),
("overtime_goal_ends_only_after_defending_restart", r'''auto m=overtime(0,149); CHECK(m.record_penalty(1,"Serious",Severity::Serious)==1&&m.start_penalty_shot(1,0,9,0)&&m.release_penalty_shot(9)); CHECK(m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(0,1))); CHECK(m.scores[1]==162&&m.status==Status::Paused&&m.penalties[0].pending&&m.winner==-1); auto before=fingerprint(m); CHECK(!m.certify()&&fingerprint(m)==before); CHECK(m.restart_penalty_shot(0)&&m.status==Status::Review&&m.ending.reason=="overtime_margin"&&!m.penalties[0].pending); CHECK(m.certify()&&m.winner==1&&m.status==Status::Complete);'''),
("overtime_miss_does_not_end_or_advance_live_time", r'''auto m=overtime(0,149); auto at=m.now_ms; CHECK(m.record_penalty(1,"Serious",Severity::Serious)==1&&m.start_penalty_shot(1,0,9,0)&&m.release_penalty_shot(9)&&m.complete_penalty_shot(PenaltyShotOutcome::Miss)&&m.restart_penalty_shot(0)); CHECK(m.status==Status::Paused&&!m.ending.active&&m.now_ms==at&&m.resume());'''),
("donnybrook_quark_shot_scores_and_excludes_offender", r'''auto m=donnybrook(); auto at=m.now_ms; CHECK(m.record_penalty(1,"Serious",Severity::Serious)==1); auto before=fingerprint(m); CHECK(!m.start_penalty_shot(1,0,13,0)&&fingerprint(m)==before); CHECK(m.start_penalty_shot(1,1,13,0)&&m.players[1].donnybrook_excluded&&m.players[1].removed_until==-1); CHECK(m.release_penalty_shot(13)&&m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(1,1))); CHECK(m.scores[1]==37&&m.now_ms==at&&m.penalties[0].pending&&m.status==Status::Paused); CHECK(m.restart_penalty_shot(0)&&m.status==Status::Review&&m.ending.reason=="donnybrook"&&m.certify()&&m.winner==1);'''),
("donnybrook_miss_restarts_quark_without_ending", r'''auto m=donnybrook(); CHECK(m.record_penalty(1,"Serious",Severity::Serious,2)==1&&m.start_penalty_shot(1,2,15,0)); CHECK(m.advance_penalty_shot(5000)==5000&&m.restart_penalty_shot(0)&&m.resume()); CHECK(m.status==Status::Live&&!m.ending.active&&m.balls[2].controller==0&&!m.eligible(1,2));'''),
("other_crown_and_conduct_remedies_survive_shot", r'''Match m(legacy_crown_config()); CHECK(m.crown_exit(2,{1,2,138},2)&&m.crown_return(2)); CHECK(m.record_penalty(3,"Moderate",Severity::Moderate,1)==2&&m.record_penalty(1,"Serious",Severity::Serious,0)==3); CHECK(m.prepare_crown_restart(1)&&m.queue_conduct_possession_award(2,1,1)&&m.start_penalty_shot(3,0,9,0)); CHECK(m.advance_penalty_shot(5000)==5000&&m.restart_penalty_shot(0)&&m.resume()); CHECK(m.restart(1,9)&&m.restart(2,10)&&!m.penalties[1].pending&&!m.penalties[0].crown_restoration_pending&&m.balls[0].controller==0);'''),
("sequential_serious_shots_serve_independently", r'''auto m=serious(); CHECK(m.record_penalty(2,"other Serious",Severity::Serious)==2&&m.start_penalty_shot(1,0,9,0)); CHECK(m.advance_penalty_shot(5000)==5000&&m.restart_penalty_shot(0)); auto before=fingerprint(m); CHECK(!m.resume()&&fingerprint(m)==before); CHECK(m.start_penalty_shot(2,0,10,0)&&m.advance_penalty_shot(5000)==5000&&m.restart_penalty_shot(0)&&m.resume()); CHECK(!m.penalties[0].pending&&!m.penalties[1].pending&&m.players[1].removed_until==180000&&m.players[2].removed_until==180000);'''),
("invalid_reserved_state_cannot_release_or_complete", r'''for(int variant=0;variant<9;++variant){auto m=ready(); if(variant==0)m.penalties[0].pending=false; if(variant==1)m.penalties[0].penalty_shot_reserved=false; if(variant==2)m.penalty_shot.netminder=2; if(variant==3)m.balls[0].live=true; if(variant==4)m.balls[0].controller=10; if(variant==5)m.balls[0].restart_team=1; if(variant==6)m.penalty_shot.elapsed_ms=-1; if(variant==7)m.penalty_shot.stage=static_cast<PenaltyShotStage>(99); if(variant==8)m.balls[0].conduct_restart_penalty=1; auto before=fingerprint(m); CHECK(!m.release_penalty_shot(9)&&fingerprint(m)==before); CHECK(!m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(0,1))&&fingerprint(m)==before);}'''),
]


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        code = RUNNER.main()
    path = RUNNER.OUTPUT / "results.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report.pop("reference_scenarios", None)
    report["scope"] = "Portable Serious penalty-shot state machine; no physical native-gameplay claim"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())

"""Compile focused portable conduct-award scenarios; never launch Unreal.

Uses the existing native rules compiler runner. All failure checks compare full
public state (including the new reservation ID) and audit events, excluding only
last_error. --compiler/--vcvars/--emit-only behave like test_native_rules.py.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("_bb_conduct_compiler", ROOT / "Tools/test_native_rules.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
RUNNER.OUTPUT = ROOT / ".local/native-conduct-awards"
RUNNER.PREAMBLE = RUNNER.PREAMBLE.replace(
    "<<b.crown_restart_penalty;", "<<b.crown_restart_penalty<<','<<b.conduct_restart_penalty;")
assert "<<b.conduct_restart_penalty" in RUNNER.PREAMBLE
RUNNER.PREAMBLE += r'''
Match conduct(int ball=0) {
 Match m; int id=m.record_penalty(1,"BB0 conduct",Severity::Moderate,ball);
 bool ok=id==1&&m.pause("playtest referee"); assert(ok); return m;
}
'''
RUNNER.CASES = [
("queue_requires_stoppage", r'''Match m; CHECK(m.record_penalty(1,"conduct",Severity::Moderate)==1); auto before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(1,0,1)); CHECK(fingerprint(m)==before);'''),
("invalid_ids_ball_team_are_atomic", r'''for(auto args:std::vector<std::array<int,3>>{{0,0,1},{-1,0,1},{2,0,1},{1,-1,1},{1,3,1},{1,4,1},{1,7,1},{1,0,-1},{1,0,2},{1,0,0}}){auto m=conduct(); auto before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(args[0],args[1],args[2])); CHECK(fingerprint(m)==before);}'''),
("only_pending_moderate_is_accepted", r'''for(auto severity:{Severity::Minor,Severity::Serious,Severity::Severe,Severity::Catastrophic}){Match m; CHECK(m.record_penalty(1,"conduct",severity)==1); if(m.status==Status::Live)CHECK(m.pause()); auto before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(1,0,1)); CHECK(fingerprint(m)==before);} auto m=conduct(); CHECK(m.resolve_penalty(1,"prior explicit disposition")); auto before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(1,0,1)&&fingerprint(m)==before);'''),
("inactive_or_non_scoring_ball_is_rejected", r'''for(int variant=0;variant<3;++variant){auto m=conduct(); if(variant==0)m.balls[0].phase_active=false; if(variant==1)m.balls[0].type=BallType::Bludger; if(variant==2)m.balls[0].live=true; auto before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(1,0,1)&&fingerprint(m)==before);}'''),
("other_dead_ball_remedies_are_not_overwritten", r'''for(const char* reason:{"score","crown","crown_restart","scheduled_release","timeout","hurley_foul","penalty","removed"}){auto m=conduct(); m.balls[0].dead_reason=reason; auto before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(1,0,1)&&fingerprint(m)==before);}'''),
("outstanding_neutral_return_crown_claim_has_priority", r'''Match m; CHECK(m.crown_exit(0,{2,3,138},1)&&m.crown_return(0)); CHECK(m.record_penalty(2,"conduct",Severity::Moderate,0)==2&&m.pause()); auto before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(2,0,1)&&fingerprint(m)==before); CHECK(m.prepare_crown_restart(1)); before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(2,0,1)&&fingerprint(m)==before);'''),
("queue_retains_pending_identity_and_actual_award_ball", r'''auto m=conduct(2); m.balls[0].controller=0; CHECK(m.queue_conduct_possession_award(1,0,1)); CHECK(m.penalties[0].id==1&&m.penalties[0].player==1&&m.penalties[0].ball==2&&m.penalties[0].reason=="BB0 conduct"&&m.penalties[0].severity==Severity::Moderate&&m.penalties[0].pending); CHECK(!m.balls[0].live&&m.balls[0].dead_reason=="penalty"&&m.balls[0].controller==-1&&m.balls[0].restart_team==1&&m.balls[0].conduct_restart_penalty==1); CHECK(count_log(m,"conduct_possession_award_queued")==1&&count_log(m,"penalty_resolved")==0);'''),
("one_penalty_cannot_reserve_two_balls_or_queue_twice", r'''auto m=conduct(); CHECK(m.queue_conduct_possession_award(1,0,1)); auto before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(1,0,1)&&fingerprint(m)==before); CHECK(!m.queue_conduct_possession_award(1,1,1)&&fingerprint(m)==before);'''),
("one_ball_cannot_serve_two_queued_penalties", r'''auto m=conduct(); CHECK(m.record_penalty(2,"another conduct",Severity::Moderate)==2&&m.queue_conduct_possession_award(1,0,1)); auto before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(2,0,1)&&fingerprint(m)==before);'''),
("generic_resolver_cannot_complete_queued_award", r'''auto m=conduct(); CHECK(m.queue_conduct_possession_award(1,0,1)); auto before=fingerprint(m); CHECK(!m.resolve_penalty(1,"fake completed restart")&&fingerprint(m)==before&&m.penalties[0].pending);'''),
("resume_allows_valid_queue_but_releases_other_stoppage_balls", r'''auto m=conduct(); CHECK(m.queue_conduct_possession_award(1,0,1)&&m.resume()); CHECK(m.status==Status::Live&&!m.balls[0].live&&m.penalties[0].pending&&m.balls[1].live&&m.balls[2].live&&m.balls[4].dead_reason=="scheduled_release");'''),
("unrelated_pending_penalty_still_blocks_resume_atomically", r'''auto m=conduct(); CHECK(m.queue_conduct_possession_award(1,0,1)&&m.record_penalty(2,"unadministered",Severity::Minor)==2); auto before=fingerprint(m); CHECK(!m.resume()&&fingerprint(m)==before);'''),
("invalid_or_orphaned_reservations_cannot_resume", r'''for(int variant=0;variant<9;++variant){auto m=conduct(); CHECK(m.queue_conduct_possession_award(1,0,1)); if(variant==0)m.balls[0].restart_team=0; if(variant==1)m.balls[0].live=true; if(variant==2)m.balls[0].dead_reason="stoppage"; if(variant==3)m.penalties[0].disposition="not queued"; if(variant==4)m.penalties[0].pending=false; if(variant==5)m.balls[0].conduct_restart_penalty=9; if(variant==6)m.balls[1].conduct_restart_penalty=1; if(variant==7)m.balls[0].controller=9; if(variant==8)m.balls[0].crown_restart_penalty=2; auto before=fingerprint(m); CHECK(!m.resume()&&fingerprint(m)==before);}'''),
("wrong_team_and_restricted_receivers_leave_remedy_pending", r'''auto m=conduct(); CHECK(m.queue_conduct_possession_award(1,0,1)&&m.resume()); for(int receiver:{-1,16,1,13,15}){auto before=fingerprint(m); CHECK(!m.restart(0,receiver)&&fingerprint(m)==before&&m.penalties[0].pending);} m.players[9].ejected=true; auto before=fingerprint(m); CHECK(!m.restart(0,9)&&fingerprint(m)==before);'''),
("temporarily_removed_receiver_must_recover_before_service", r'''auto m=conduct(); CHECK(m.queue_conduct_possession_award(1,0,1)&&m.resume()); m.players[9].removed_until=100; auto before=fingerprint(m); CHECK(!m.restart(0,9)&&fingerprint(m)==before); CHECK(m.advance(100)==100&&m.restart(0,9)&&!m.penalties[0].pending);'''),
("receiver_must_release_other_carried_ball_first", r'''auto m=conduct(); CHECK(m.queue_conduct_possession_award(1,0,1)&&m.resume()&&m.possess(9,1)); auto before=fingerprint(m); CHECK(!m.restart(0,9)&&fingerprint(m)==before&&m.penalties[0].pending); CHECK(m.release(9,1)&&m.restart(0,9));'''),
("actual_restart_consumes_once_and_grants_protection", r'''auto m=conduct(); CHECK(m.queue_conduct_possession_award(1,0,1)); auto before=fingerprint(m); CHECK(!m.restart(0,9)&&fingerprint(m)==before); CHECK(m.resume()&&m.restart(0,9)); CHECK(m.balls[0].controller==9&&m.balls[0].live&&m.balls[0].conduct_restart_penalty==-1&&m.balls[0].protection_until==m.now_ms+m.config.restart_protection_ms); CHECK(!m.penalties[0].pending&&m.penalties[0].disposition=="conduct possession award served by protected restart"); CHECK(count_log(m,"conduct_possession_award_served")==1&&count_log(m,"penalty_resolved")==1&&count_log(m,"protected_restart")==1); before=fingerprint(m); CHECK(!m.restart(0,9)&&fingerprint(m)==before); CHECK(m.release(9,0)&&m.balls[0].protection_until==-1&&m.pause()); before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(1,0,1)&&fingerprint(m)==before);'''),
("distinct_awards_are_consumed_independently", r'''auto m=conduct(); CHECK(m.record_penalty(9,"opposing conduct",Severity::Moderate,1)==2); CHECK(m.queue_conduct_possession_award(1,0,1)&&m.queue_conduct_possession_award(2,1,0)&&m.resume()); CHECK(m.restart(0,9)&&!m.penalties[0].pending&&m.penalties[1].pending); CHECK(m.restart(1,1)&&!m.penalties[1].pending&&count_log(m,"conduct_possession_award_served")==2);'''),
("pending_award_blocks_terminal_certification", r'''auto m=short_match(); CHECK(m.record_penalty(1,"conduct",Severity::Moderate)==1&&m.process_batch(5001,{caught(4)})); CHECK(m.status==Status::Review&&m.queue_conduct_possession_award(1,0,1)); auto before=fingerprint(m); CHECK(!m.certify()&&fingerprint(m)==before); CHECK(!m.resume()&&fingerprint(m)==before); CHECK(!m.restart(0,9)&&fingerprint(m)==before&&m.winner==-1&&m.penalties[0].pending);'''),
("quarter_break_can_resume_with_valid_award", r'''auto m=short_match(); CHECK(m.record_penalty(1,"conduct",Severity::Moderate)==1&&m.advance(10000)==10000&&m.status==Status::QuarterBreak); CHECK(m.queue_conduct_possession_award(1,0,1)&&m.resume()&&m.quarter==2&&m.restart(0,9));'''),
("donnybrook_rejects_quaffle_and_respects_suspended_roles", r'''auto m=donnybrook(); CHECK(m.record_penalty(1,"conduct",Severity::Moderate)==1&&m.pause()); auto before=fingerprint(m); CHECK(!m.queue_conduct_possession_award(1,0,1)&&fingerprint(m)==before); CHECK(m.queue_conduct_possession_award(1,1,1)&&m.resume()&&m.restart(1,13));'''),
("restart_clock_overflow_is_atomic", r'''auto m=conduct(); CHECK(m.queue_conduct_possession_award(1,0,1)&&m.resume()); m.now_ms=std::numeric_limits<Millis>::max(); auto before=fingerprint(m); CHECK(!m.restart(0,9)&&fingerprint(m)==before&&m.penalties[0].pending);'''),
("existing_score_restart_and_crown_remedies_still_work", r'''Match m; CHECK(m.process_batch(0,{goal()})); CHECK(m.crown_exit(2,{2,3,138},2)&&m.crown_return(2)); CHECK(m.record_penalty(1,"conduct",Severity::Moderate,1)==2&&m.pause()); CHECK(m.prepare_crown_restart(1)&&m.queue_conduct_possession_award(2,1,1)&&m.resume()); auto before=fingerprint(m); CHECK(!m.restart(0,9)&&fingerprint(m)==before); CHECK(m.restart(0,8)&&m.restart(1,9)&&m.restart(2,10)); CHECK(!m.penalties[1].pending&&!m.penalties[0].crown_restoration_pending&&m.penalties[0].crown_restoration_receiver==10);'''),
("existing_hurley_foul_still_restarts_to_hurleyback", r'''Match m; CHECK(m.possess(5,5,true)); CHECK(m.advance(3000)==3000&&m.balls[5].dead_reason=="hurley_foul"); CHECK(m.restart(5,13)&&m.balls[5].live&&m.balls[5].controller==-1);'''),
]


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        code = RUNNER.main()
    path = RUNNER.OUTPUT / "results.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report.pop("reference_scenarios", None)
    report["scope"] = "Portable conduct possession awards; no native-editor or physical-gameplay claim"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())

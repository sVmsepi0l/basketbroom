"""Portable Moderate free-shot authorization, scoring and no-removal regression checks."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bb_shot_tests", ROOT / "Tools/test_native_penalty_shots.py")
shots = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shots)
runner = shots.RUNNER
runner.OUTPUT = ROOT / ".local/native-free-shots"
runner.PREAMBLE += r'''
Match free_ready(int ball=0,int offender=1,int keeper=0) {
 Match m; bool ok=m.pause() && m.record_penalty(offender,"Moderate",Severity::Moderate,ball)==1 && m.start_penalty_shot(1,ball,9,keeper,true); assert(ok);return m;
}
'''
runner.CASES = [
("moderate_free_shot_has_no_removal_or_duplicate_package", r'''auto m=free_ready(); CHECK(m.penalty_shot.free_shot&&m.players[1].removed_until==-1&&!m.players[1].donnybrook_excluded&&count_log(m,"temporary_removal")==0); auto before=fingerprint(m); CHECK(!m.resolve_penalty(1,"duplicate",true)&&fingerprint(m)==before); CHECK(!m.queue_conduct_possession_award(1,1,1)&&fingerprint(m)==before);'''),
("queued_possession_cannot_become_a_second_free_shot_package", r'''Match m;CHECK(m.pause()&&m.record_penalty(1,"denied Quark",Severity::Moderate,1)==1&&m.queue_conduct_possession_award(1,0,1));auto before=fingerprint(m);CHECK(!m.start_penalty_shot(1,1,9,0,true)&&fingerprint(m)==before);CHECK(m.balls[0].conduct_restart_penalty==1&&m.penalties[0].pending&&!m.penalties[0].penalty_shot_reserved);'''),
("conflicting_same_penalty_reservation_cannot_advance_or_release", r'''auto m=free_ready(1);m.balls[0].conduct_restart_penalty=1;auto before=fingerprint(m);CHECK(m.advance_penalty_shot(1)==-1&&fingerprint(m)==before);CHECK(!m.release_penalty_shot(9)&&fingerprint(m)==before);'''),
("wrong_tiers_reject_atomically", r'''for(auto severity:{Severity::Minor,Severity::Serious,Severity::Severe,Severity::Catastrophic}) {Match m; CHECK(m.pause()&&m.record_penalty(1,"conduct",severity)==1);auto before=fingerprint(m);CHECK(!m.start_penalty_shot(1,0,9,0,true)&&fingerprint(m)==before);}'''),
("free_shot_requires_stoppage", r'''Match m;CHECK(m.record_penalty(1,"conduct",Severity::Moderate)==1);auto before=fingerprint(m);CHECK(!m.start_penalty_shot(1,0,9,0,true)&&fingerprint(m)==before);'''),
("offending_keeper_can_defend_moderate_shot", r'''auto m=free_ready(0,0,0);CHECK(m.eligible(0,0)&&m.advance_penalty_shot(5000)==5000&&m.restart_penalty_shot(0)&&m.resume()&&m.players[0].removed_until==-1);'''),
("ordinary_ball_points_exactly_once_and_restart_required", r'''for(int b:{0,1,2}){auto m=free_ready(b);CHECK(m.release_penalty_shot(9)&&m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(b,1)));CHECK(m.scores[1]==(b==0?13:37)&&m.penalties[0].pending);auto before=fingerprint(m);CHECK(!m.resume()&&fingerprint(m)==before);CHECK(!m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(b,1))&&fingerprint(m)==before);CHECK(m.restart_penalty_shot(0)&&m.resume()&&!m.penalties[0].pending&&m.eligible(1,b));}'''),
("attempt_clock_freezes_live_time_and_existing_removal", r'''auto m=free_ready();m.players[2].removed_until=70000;CHECK(m.advance_penalty_shot(4000)==4000&&m.now_ms==0&&m.players[2].removed_until==70000&&m.players[1].removed_until==-1);CHECK(m.advance_penalty_shot(5000)==1000&&m.penalty_shot.outcome==PenaltyShotOutcome::Timeout&&m.scores[1]==0);'''),
("wrong_shooter_repeat_release_and_wrong_keeper_reject", r'''auto m=free_ready();auto before=fingerprint(m);CHECK(!m.release_penalty_shot(10)&&fingerprint(m)==before);CHECK(m.release_penalty_shot(9));before=fingerprint(m);CHECK(!m.release_penalty_shot(9)&&fingerprint(m)==before);CHECK(m.complete_penalty_shot(PenaltyShotOutcome::Miss));before=fingerprint(m);CHECK(!m.restart_penalty_shot(2)&&fingerprint(m)==before);'''),
("mixed_sequential_moderate_and_serious_remain_distinct", r'''auto m=free_ready();CHECK(m.record_penalty(2,"Serious",Severity::Serious)==2&&m.advance_penalty_shot(5000)==5000&&m.restart_penalty_shot(0));CHECK(m.start_penalty_shot(2,0,10,0)&&!m.penalty_shot.free_shot&&m.players[1].removed_until==-1&&m.players[2].removed_until==180000);CHECK(m.advance_penalty_shot(5000)==5000&&m.restart_penalty_shot(0)&&m.resume());'''),
("donnybrook_any_eligible_designated_defender_free_goal_wins", r'''auto m=donnybrook();CHECK(m.pause()&&m.record_penalty(1,"Moderate",Severity::Moderate,1)==1&&m.start_penalty_shot(1,1,15,7,true));CHECK(m.release_penalty_shot(15)&&m.complete_penalty_shot(PenaltyShotOutcome::Goal,goal(1,1))&&m.restart_penalty_shot(7));CHECK(m.status==Status::Review&&!m.players[1].donnybrook_excluded&&m.certify()&&m.winner==1);'''),
("corrupt_severity_or_kind_cannot_advance", r'''for(int v=0;v<2;++v){auto m=free_ready();if(v==0)m.penalty_shot.free_shot=false;else m.penalties[0].severity=Severity::Minor;auto before=fingerprint(m);CHECK(m.advance_penalty_shot(1)==-1&&fingerprint(m)==before);}'''),
]
def main():
    with contextlib.redirect_stdout(io.StringIO()):
        code = runner.main()
    path = runner.OUTPUT / "results.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report.pop("reference_scenarios", None)
    report["scope"] = "Portable Moderate free-shot state machine; no actor placement, rendering or network claim"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())

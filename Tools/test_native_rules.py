"""Compile and exercise the portable regulation engine without Unreal Engine.

Uses MSVC, clang++, or g++. Windows: --vcvars path/to/vcvars64.bat configures
an installed compiler in this child process only. --emit-only writes the test
driver when a compiler is not available; it does not report tests as passed.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "DevelopmentHarness" / "Source" / "BasketbroomRuntime"
OUTPUT = ROOT / ".local" / "native-rules"

PREAMBLE = r'''
#include "BBRuleEngine.h"
#include <algorithm>
#include <cassert>
#include <iostream>
#include <limits>
#include <sstream>
using namespace BB;
#define CHECK(...) do { if (!(__VA_ARGS__)) { std::cerr << "line " << __LINE__ << ": " << #__VA_ARGS__ << "\n"; return false; } } while(false)
PointEvent goal(int ball=0,int team=0,Hoop hoop=Hoop::None) {
 PointEvent e; e.ball=ball; e.attacking_team=team; e.hoop=hoop==Hoop::None?(ball==0?Hoop::Large:Hoop::Small):hoop;
 e.entire_ball=e.forward=true; return e;
}
PointEvent caught(int ball=3,int player=7) {
 PointEvent e; e.kind=EventKind::Catch; e.ball=ball; e.player=player; e.secure_ms=1000;
 e.by_hand=e.mounted=e.inside_envelope=true; return e;
}
Match short_match() { Config c; c.quarter_ms=10000; c.overtime_ms=5000; c.snitch_release_ms=5000; return Match(c); }
void final_horn(Match& m) { for(int i=0;i<4;++i) { m.advance(m.config.quarter_ms); if(m.status==Status::QuarterBreak) { bool ok=m.resume(); assert(ok); } } }
Match overtime(std::int64_t a=0,std::int64_t b=0) { auto m=short_match(); m.scores={a,b}; final_horn(m); bool ok=m.certify()&&m.resume(); assert(ok); return m; }
Match donnybrook() { auto m=overtime(); m.advance(5000); bool ok=m.certify()&&m.resume(); assert(ok); return m; }
bool score_is(const Match& m,std::int64_t a,std::int64_t b) { return m.scores[0]==a&&m.scores[1]==b; }
std::size_t count_log(const Match& m,const std::string& kind) { return static_cast<std::size_t>(std::count_if(m.log.begin(),m.log.end(),[&](const LogEvent& e){return e.kind==kind;})); }
// Full public gameplay state and event payloads; last_error is diagnostic only.
std::string fingerprint(const Match& m) {
 std::ostringstream s; s.precision(17);
 s<<int(m.phase)<<','<<int(m.status)<<','<<m.quarter<<','<<m.now_ms<<','<<m.period_elapsed_ms<<','<<m.scores[0]<<','<<m.scores[1]<<','<<m.winner<<','<<m.reckoner<<';';
 const auto& e=m.ending; s<<e.active<<','<<e.reason<<','<<e.at_ms<<','<<e.catching_team<<','<<e.catcher<<','<<e.winning_team<<','<<e.catch_points<<';';
 for(const auto& p:m.players) s<<p.team<<','<<int(p.role)<<','<<p.removed_until<<','<<p.ejected<<','<<p.donnybrook_excluded<<';';
 for(const auto& b:m.balls) { s<<int(b.type)<<','<<b.phase_active<<','<<b.live<<','<<b.controller<<','<<b.dead_reason<<','<<b.timeout_until<<','<<b.crown_deadline<<','<<b.protection_until<<','<<b.restart_team<<','<<b.crown_restart_penalty; for(auto v:b.crown_mark)s<<','<<v; s<<';'; }
 for(const auto& h:m.hurleys) s<<h.last_player<<','<<h.team<<','<<h.individual_started<<','<<h.team_ms<<','<<h.flight_started<<','<<h.contestable<<','<<h.individual_reset<<','<<h.warned<<';';
 for(const auto& p:m.penalties) { s<<p.id<<','<<p.player<<','<<p.ball<<','<<p.reason<<','<<p.disposition<<','<<int(p.severity)<<','<<p.committed_ms<<','<<p.pending<<','<<p.crown_restoration_pending<<','<<p.crown_restoration_receiver; for(auto v:p.crown_mark)s<<','<<v; s<<';'; }
 for(const auto& l:m.log) s<<l.sequence<<','<<l.at_ms<<','<<l.kind<<','<<l.reason<<','<<l.player<<','<<l.ball<<','<<l.team<<','<<l.penalty_id<<','<<l.value<<';';
 for(const auto& a:m.last_awards) s<<a.team<<','<<a.points<<','<<a.ball<<','<<a.player<<';';
 return s.str();
}
'''

# One native scenario for each of the 54 reference tests, plus hardening cases.
CASES = [
("canonical_configuration", r'''Match m; CHECK(m.config.quaffle_points==13&&m.config.quark_points==37&&m.config.snipe_points==69); CHECK(m.config.snitch_regulation_points==150&&m.config.snitch_overtime_points==300); CHECK(m.config.quarter_ms*4==176*60*1000);'''),
("seven_balls_open_with_delayed_snitch", r'''Match m; CHECK(std::count_if(m.balls.begin(),m.balls.end(),[](const Ball& b){return b.live;})==6); CHECK(m.advance(1320000)==1320000); CHECK(m.balls[4].live);'''),
("three_scoring_balls_resolve_independently", r'''Match m; CHECK(m.process_batch(10,{goal(),goal(1),goal(2,1)})); CHECK(score_is(m,50,37)&&m.balls[3].live&&m.status==Status::Live&&m.balls[0].restart_team==1);'''),
("wrong_hoop_reverse_incomplete_teleported_never_score", r'''std::vector<PointEvent> events{goal(0,0,Hoop::Small),goal(1,0,Hoop::Large),goal(),goal(),goal()}; events[2].forward=false; events[3].entire_ball=false; events[4].teleported=true; for(auto e:events){Match m; CHECK(m.process_batch(0,{e})); CHECK(score_is(m,0,0)&&m.balls[e.ball].live);}'''),
("own_goal_credits_attacking_team", r'''Match m; CHECK(m.possess(9,0)&&m.release(9,0)&&m.process_batch(1,{goal()})); CHECK(m.scores[0]==13);'''),
("invalid_batch_rolls_back_time_points_and_log", r'''Match m; auto before=fingerprint(m); CHECK(!m.process_batch(10,{goal(),caught(3,1)})); CHECK(fingerprint(m)==before);'''),
("duplicate_ball_event_rejected", r'''Match m; auto before=fingerprint(m); CHECK(!m.process_batch(0,{goal(),goal(0,1)})); CHECK(fingerprint(m)==before);'''),
("scoring_restart_requires_defending_netminder", r'''Match m; CHECK(m.process_batch(0,{goal()})); CHECK(!m.restart(0,9)); CHECK(m.restart(0,8)); CHECK(m.balls[0].controller==8&&m.balls[0].protection_until==3000); CHECK(m.release(8,0)&&m.balls[0].protection_until==-1);'''),
("netminder_cannot_hold_multiple_restart_balls", r'''Match m; CHECK(m.process_batch(0,{goal(),goal(1)})&&m.restart(0,8)); auto before=fingerprint(m); CHECK(!m.restart(1,8)); CHECK(fingerprint(m)==before);'''),
("required_roster_distribution", r'''Match m; auto roster=Match::default_roster(); roster[0].role=Role::Chaser; CHECK(!m.configure_roster(roster)); CHECK(m.players[0].role==Role::Netminder);'''),
("unauthorized_carriers", r'''for(int player:{7,5}){Match m; CHECK(!m.possess(player,0));}'''),
("trapper_shooting_and_single_ball", r'''Match m; CHECK(m.possess(3,0)); CHECK(!m.possess(3,1)); CHECK(m.release(3,0)&&m.process_batch(0,{goal()})); CHECK(m.scores[0]==13);'''),
("ranger_must_release_before_capture", r'''Match m; CHECK(m.possess(4,1)); CHECK(!m.process_batch(0,{caught(3,4)})); CHECK(m.release(4,1)&&m.process_batch(0,{caught(3,4)})); CHECK(m.scores[0]==69);'''),
("capture_requires_every_evidence_field", r'''for(int i=0;i<4;++i){Match m; auto e=caught(); if(i==0)e.secure_ms=999; if(i==1)e.by_hand=false; if(i==2)e.mounted=false; if(i==3)e.inside_envelope=false; CHECK(!m.process_batch(0,{e}));}'''),
("chase_balls_are_not_carried", r'''Match m; CHECK(!m.possess(7,3));'''),
("removed_player_cannot_play", r'''Match m; int p=m.record_penalty(7,"interference",Severity::Serious); CHECK(p>0&&m.resolve_penalty(p,"shot missed")&&m.resume()); CHECK(!m.process_batch(0,{caught()})); CHECK(m.advance(180000)==180000&&m.process_batch(180000,{caught()})); CHECK(m.scores[0]==69);'''),
("snipe_three_live_minutes_with_ten_second_warning", r'''Match m; CHECK(m.process_batch(1000,{caught()})); m.advance(170000); CHECK(m.balls[3].dead_reason=="timeout"&&m.log.back().kind=="snipe_warning"); m.advance(9999); CHECK(!m.balls[3].live); m.advance(1); CHECK(m.balls[3].live);'''),
("global_pause_freezes_snipe_and_removal_clock", r'''Match m; CHECK(m.process_batch(0,{caught()})); int p=m.record_penalty(15,"interference",Severity::Serious); CHECK(m.resolve_penalty(p,"shot missed")); auto before=fingerprint(m); CHECK(m.advance(1000000)==0&&fingerprint(m)==before);'''),
("timeout_carries_quarter_break", r'''Match m; CHECK(m.process_batch(2600000,{caught()})); m.advance(40000); CHECK(m.status==Status::QuarterBreak&&m.advance(1000000)==0&&m.resume()); m.advance(139999); CHECK(!m.balls[3].live); m.advance(1); CHECK(m.balls[3].live);'''),
("overtime_clears_snipe_timeout", r'''auto m=short_match(); for(int i=0;i<3;++i){m.advance(10000); CHECK(m.resume());} CHECK(m.process_batch(39000,{caught()})); m.advance(1000); CHECK(m.certify()&&m.resume()); CHECK(m.phase==Phase::Overtime); for(auto b:m.balls)CHECK(b.live);'''),
("regulation_margin_boundaries", r'''for(int margin:{0,149,150,151}){auto m=short_match(); m.scores[0]=margin; final_horn(m); CHECK(m.status==Status::Review&&m.certify()); CHECK(m.phase==(margin<150?Phase::Overtime:Phase::Regulation)); CHECK(m.winner==(margin<150?-1:0));}'''),
("snitch_catcher_can_lose_and_still_be_reckoner", r'''auto m=short_match(); m.scores[1]=151; CHECK(m.process_batch(5001,{caught(4)})); CHECK(m.winner==-1&&m.certify()); CHECK(m.winner==1&&m.reckoner==7);'''),
("snitch_exact_tie_goes_to_catcher", r'''auto m=short_match(); m.scores[1]=150; CHECK(m.process_batch(5001,{caught(4)})&&m.certify()); CHECK(m.winner==0&&score_is(m,150,150));'''),
("ranger_catch_does_not_award_reckoner", r'''auto m=short_match(); CHECK(m.process_batch(5001,{caught(4,4)})&&m.certify()); CHECK(m.reckoner==-1);'''),
("simultaneous_points_count_before_snitch_ending", r'''auto m=short_match(); m.scores[1]=140; CHECK(m.process_batch(5001,{caught(4),goal(0,1)})); CHECK(score_is(m,150,153)&&m.certify()&&m.winner==1);'''),
("exact_horn_goal_does_not_count_and_batch_is_atomic", r'''auto m=short_match(); auto before=fingerprint(m); CHECK(!m.process_batch(10000,{goal()})); CHECK(fingerprint(m)==before); CHECK(m.process_batch(9999,{goal()})); m.advance(1); CHECK(m.status==Status::QuarterBreak&&m.scores[0]==13);'''),
("overtime_catch_worth_300", r'''auto m=overtime(); CHECK(m.process_batch(m.now_ms,{caught(4)})); CHECK(m.scores[0]==300&&m.certify()&&m.winner==0);'''),
("overtime_simultaneous_net_threshold", r'''auto m=overtime(149); CHECK(m.process_batch(m.now_ms,{goal(),goal(1,1)})); CHECK(m.margin()==125&&m.status==Status::Live); CHECK(m.process_batch(m.now_ms+1,{goal(2)})); CHECK(m.status==Status::Review&&m.certify()&&m.winner==0);'''),
("overtime_horn_any_nonzero_lead_wins", r'''auto m=overtime(1); m.advance(5000); CHECK(m.certify()&&m.winner==0);'''),
("penalty_blocks_certification_and_can_change_winner", r'''auto m=short_match(); m.scores[1]=140; int p=m.record_penalty(1,"denied goal",Severity::Moderate,1); CHECK(m.process_batch(5001,{caught(4)})); CHECK(!m.certify()&&m.resolve_penalty(p,"B made Quark free shot")); CHECK(m.certify({{1,37,"free shot",0}})&&m.winner==1);'''),
("adjusted_overtime_threshold_resumes", r'''auto m=overtime(149); CHECK(m.process_batch(m.now_ms+100,{goal()})); auto at=m.now_ms; CHECK(m.certify({{1,37,"pre-termination penalty shot",at}})); CHECK(m.status==Status::Live&&m.now_ms==at&&m.margin()==125&&m.balls[4].live);'''),
("overturned_snitch_restores_phase_and_neutral_ball", r'''auto m=short_match(); CHECK(m.process_batch(5001,{caught(4),goal(1,1)})&&m.overturn_snitch("replay establishes bobble")&&m.resume()); CHECK(score_is(m,0,37)&&m.now_ms==5001&&m.balls[4].live);'''),
("three_balls_positions_suspended", r'''auto m=donnybrook(); for(int i=0;i<7;++i)CHECK(m.balls[i].phase_active==(i==1||i==2||i==3)); CHECK(m.possess(5,1)&&m.release(5,1)&&m.process_batch(m.now_ms,{caught(3,0)})); CHECK(m.certify()&&m.winner==0&&m.scores[0]==69);'''),
("opposing_simultaneous_wins_void_and_reset", r'''auto m=donnybrook(); CHECK(m.process_batch(m.now_ms,{caught(),goal(1,1)})); CHECK(m.status==Status::Live&&score_is(m,0,0)); for(int i:{1,2,3})CHECK(m.balls[i].live); CHECK(m.process_batch(m.now_ms+1,{goal(2,1)})&&m.certify()&&m.winner==1);'''),
("carried_quark_prevents_donnybrook_snipe_capture", r'''auto m=donnybrook(); CHECK(m.possess(7,1)); CHECK(!m.process_batch(m.now_ms,{caught()}));'''),
("unexpired_removal_converts_to_donnybrook_exclusion", r'''auto m=overtime(); int p=m.record_penalty(7,"interference",Severity::Serious); CHECK(m.resolve_penalty(p,"shot missed")&&m.resume()); m.advance(5000); CHECK(m.certify()&&m.resume()); m.advance(1000000); CHECK(!m.eligible(7,3)&&m.status==Status::Live);'''),
("crown_only_kills_one_ball_and_flag_survives_return", r'''Match m; CHECK(m.crown_exit(0,{0,0,138},1)); CHECK(!m.balls[0].live&&m.balls[1].live); m.advance(2000); CHECK(m.crown_return(0)); m.advance(1000); CHECK(m.status==Status::Live&&m.penalties[0].pending); CHECK(m.pause()&&!m.resume()); CHECK(m.resolve_penalty(1,"captain declined restoration after advantage")&&m.resume());'''),
("missed_reentry_target_triggers_safety_stoppage", r'''Match m; CHECK(m.crown_exit(1,{1,2,138})); CHECK(m.advance(10000)==3000&&m.status==Status::Paused); CHECK(m.balls[1].crown_mark[0]==1&&m.balls[1].crown_mark[1]==2&&m.balls[1].crown_mark[2]==138); CHECK(m.resume()&&m.balls[1].live);'''),
("dead_roof_delay_is_moderate", r'''Match m; CHECK(m.crown_exit(5,{0,0,138},5,true)); CHECK(m.penalties[0].severity==Severity::Moderate);'''),
("ordinary_crown_restart_requires_stoppage_and_allows_opposing_chaser", r'''Match m; CHECK(m.crown_exit(0,{2,3,138},1)); CHECK(m.penalties[0].crown_restoration_pending&&!m.prepare_crown_restart(1)); CHECK(m.crown_return(0)&&m.penalties[0].pending&&m.balls[1].live); CHECK(m.pause()&&m.prepare_crown_restart(1)); CHECK(!m.penalties[0].pending&&m.penalties[0].crown_restoration_pending&&m.balls[0].crown_restart_penalty==1); CHECK(!m.restart(0,9)&&m.resume()); CHECK(!m.restart(0,1)&&!m.restart(0,13)&&m.restart(0,9)); CHECK(m.balls[0].controller==9&&m.balls[0].protection_until==3000&&!m.penalties[0].crown_restoration_pending&&m.penalties[0].crown_restoration_receiver==9&&score_is(m,0,0));'''),
("unknown_crown_return_never_creates_restoration", r'''Match m; CHECK(m.crown_exit(1,{4,5,138})&&m.crown_return(1)); CHECK(m.penalties.empty()&&m.pause()&&!m.prepare_crown_restart(1)&&m.resume()&&m.balls[1].live);'''),
("crown_hazard_restoration_is_free_flight_to_hurleyback", r'''Match m; CHECK(m.crown_exit(5,{4,5,138},5)&&m.crown_return(5)&&m.pause()&&m.prepare_crown_restart(1)&&m.resume()); CHECK(!m.restart(5,9)&&m.restart(5,14)); CHECK(m.balls[5].live&&m.balls[5].controller==-1&&!m.penalties[0].crown_restoration_pending&&m.penalties[0].crown_restoration_receiver==14);'''),
("crown_restart_waits_while_all_opponents_unavailable", r'''Config c; c.removal_ms=1000; Match m(c); CHECK(m.crown_exit(0,{0,0,138},1)&&m.crown_return(0)&&m.pause()); for(int p:{8,9,10,11,12}) {int id=m.record_penalty(p,"unsafe contact",Severity::Serious); CHECK(id>0&&m.resolve_penalty(id,"removal"));} CHECK(m.prepare_crown_restart(1)&&m.resume()); for(int p:{8,9,10,11,12}) CHECK(!m.restart(0,p)); CHECK(!m.balls[0].live&&m.penalties[0].crown_restoration_pending); m.advance(1000); CHECK(m.restart(0,9)&&m.balls[0].controller==9);'''),
("crown_reservation_survives_quarter_resume", r'''auto m=short_match(); CHECK(m.crown_exit(1,{2,3,138},1)&&m.crown_return(1)); m.advance(10000); CHECK(m.status==Status::QuarterBreak&&m.prepare_crown_restart(1)&&m.resume()&&m.quarter==2); CHECK(m.balls[1].dead_reason=="crown_restart"&&m.balls[1].crown_mark[0]==2&&m.restart(1,9));'''),
("crown_reservation_survives_overtime_transition", r'''auto m=short_match(); for(int i=0;i<3;++i){m.advance(10000); CHECK(m.resume());} CHECK(m.crown_exit(0,{2,3,138},1)&&m.crown_return(0)); m.advance(10000); CHECK(m.status==Status::Review&&m.prepare_crown_restart(1)&&m.certify()&&m.phase==Phase::Overtime&&m.resume()); CHECK(m.balls[0].dead_reason=="crown_restart"&&m.restart(0,9)&&m.balls[0].controller==9);'''),
("same_ball_crown_restorations_remain_ordered_across_stoppages", r'''Match m; CHECK(m.crown_exit(0,{1,0,138},1)&&m.crown_return(0)&&m.crown_exit(0,{2,0,138},9)&&m.crown_return(0)&&m.pause()); CHECK(m.prepare_crown_restart(2)&&m.balls[0].crown_restart_penalty==-1&&m.prepare_crown_restart(1)&&m.resume()&&m.restart(0,9)); CHECK(!m.penalties[0].crown_restoration_pending&&m.penalties[1].crown_restoration_pending); CHECK(m.pause()&&m.prepare_crown_restart(2)&&m.resume()&&m.restart(0,1)); CHECK(!m.penalties[1].crown_restoration_pending&&m.balls[0].crown_mark[0]==2&&count_log(m,"crown_restoration_served")==2);'''),
("certified_match_expires_ordinary_restoration_without_erasing_ejection", r'''auto m=short_match(); int severe=m.record_penalty(8,"dangerous contact",Severity::Severe); CHECK(m.resolve_penalty(severe,"ejection")&&m.resume()); CHECK(m.crown_exit(0,{0,0,138},1)&&m.crown_return(0)&&m.process_batch(5001,{caught(4)})); CHECK(m.prepare_crown_restart(2)&&m.certify()&&m.status==Status::Complete); CHECK(!m.penalties[1].crown_restoration_pending&&m.players[8].ejected&&m.penalties[0].severity==Severity::Severe&&count_log(m,"crown_restoration_expired")==1);'''),
("simultaneous_crown_returns_stop_once_and_preserve_timeout", r'''Match m; CHECK(m.process_batch(0,{caught()})); m.advance(177000); CHECK(m.crown_exit(0,{0,0,138})&&m.crown_exit(1,{1,0,138})); m.advance(3000); CHECK(m.status==Status::Paused); for(auto b:m.balls)CHECK(!b.live); CHECK(count_log(m,"stoppage")==1&&m.resume()&&m.balls[3].live);'''),
("winged_envelope_recall_has_no_crown_penalty", r'''Match m; CHECK(!m.crown_exit(3,{0,0,138})); CHECK(m.recall_chase(3)&&m.penalties.empty()&&m.balls[3].live);'''),
("individual_warning_and_exact_three_second_foul", r'''Match m; CHECK(m.possess(5,5,true)); m.advance(2000); CHECK(m.hurleys[0].warned); m.advance(1000); CHECK(m.penalties[0].reason=="Illegal Prolonged Bludger Control"&&m.balls[5].restart_team==1&&m.balls[6].live);'''),
("hurley_required_and_one_bludger_limit", r'''Match m; CHECK(!m.possess(5,5)); CHECK(m.possess(5,5,true)); CHECK(!m.possess(5,6,true));'''),
("short_self_toss_keeps_individual_clock", r'''Match m; CHECK(m.possess(5,5,true)); m.advance(2500); CHECK(m.release(5,5)); m.advance(200); CHECK(m.possess(5,5,true)); m.advance(300); CHECK(m.penalties[0].reason=="Illegal Prolonged Bludger Control");'''),
("private_self_bank_does_not_reset", r'''Match m; CHECK(m.possess(5,5,true)); m.advance(2500); CHECK(m.release(5,5)&&m.flight_evidence(5,0,Contact::Net,false)&&m.possess(5,5,true)); m.advance(500); CHECK(!m.penalties.empty());'''),
("ten_foot_self_toss_resets_individual", r'''Match m; CHECK(m.possess(5,5,true)); m.advance(2500); CHECK(m.release(5,5)&&m.flight_evidence(5,10)&&m.possess(5,5,true)); m.advance(1000); CHECK(m.penalties.empty());'''),
("team_relay_accumulates_six_seconds", r'''Match m; CHECK(m.possess(5,5,true)); m.advance(2500); CHECK(m.release(5,5)&&m.possess(6,5,true)); m.advance(2500); CHECK(m.release(6,5)&&m.possess(5,5,true)); m.advance(1000); CHECK(m.penalties[0].reason=="Team Relay Hoarding");'''),
("one_second_contestable_flight_resets_team", r'''Match m; CHECK(m.possess(5,5,true)); m.advance(2500); CHECK(m.release(5,5,true)); m.advance(999); CHECK(m.hurleys[0].team_ms==2500); m.advance(1); CHECK(m.hurleys[0].team_ms==0&&m.possess(5,5,true)); m.advance(2500); CHECK(m.penalties.empty());'''),
("opponent_challenge_resets_team_not_individual", r'''Match m; CHECK(m.possess(5,5,true)); m.advance(2500); CHECK(m.opponent_challenge(5,13)); CHECK(m.hurleys[0].team_ms==0); m.advance(500); CHECK(m.penalties[0].reason=="Illegal Prolonged Bludger Control");'''),
("team_clock_after_challenge_survives_teammate_handoff", r'''Match m; CHECK(m.possess(5,5,true)); m.advance(1000); CHECK(m.opponent_challenge(5,13)); m.advance(1000); CHECK(m.release(5,5)&&m.possess(6,5,true)); CHECK(m.hurleys[0].team_ms==1000);'''),
("chunked_clock_matches_single_step", r'''Match a,b; CHECK(a.process_batch(0,{caught()})&&b.process_batch(0,{caught()})); CHECK(a.possess(5,5,true)&&b.possess(5,5,true)); a.advance(180000); for(int i=0;i<1800;++i)b.advance(100); CHECK(fingerprint(a)==fingerprint(b));'''),
("repeated_command_stream_replays_identically", r'''auto run=[](){Match m; bool ok=m.process_batch(1,{goal(),goal(1,1),caught()})&&m.restart(0,8); assert(ok); m.advance(180000); ok=m.process_batch(180001,{caught(3,15)}); assert(ok); return fingerprint(m);}; CHECK(run()==run());'''),
("public_snapshot_does_not_alias_live_state", r'''Match m; Match snapshot=m; snapshot.scores[0]=500; snapshot.balls[0].dead_reason="modified copy"; CHECK(m.scores[0]==0&&m.balls[0].dead_reason.empty());'''),
("time_is_integer_and_monotonic", r'''Match m; CHECK(m.advance(-1)==-1); CHECK(m.advance(2)==2); CHECK(!m.process_batch(1,{goal()})); CHECK(m.now_ms==2);'''),
("zero_index_controller_is_a_real_player", r'''Match m; auto roster=Match::default_roster(); std::swap(roster[0].role,roster[5].role); CHECK(m.configure_roster(roster)&&m.possess(0,5,true)); m.advance(3000); CHECK(m.penalties.size()==1&&m.penalties[0].player==0);'''),
("double_chase_capture_rejected_atomically", r'''auto m=short_match(); auto before=fingerprint(m); CHECK(!m.process_batch(5001,{caught(3),caught(4)})); CHECK(fingerprint(m)==before);'''),
("adjustments_validate_atomically", r'''auto m=short_match(); CHECK(m.process_batch(5001,{caught(4)})); auto before=fingerprint(m); CHECK(!m.certify({{0,-151,"invalid negative score",0}})); CHECK(fingerprint(m)==before); CHECK(!m.certify({{0,1,"future",5002}})); CHECK(fingerprint(m)==before);'''),
("severe_ejection_and_catastrophic_external_adjudication", r'''Match m; int p=m.record_penalty(5,"dangerous",Severity::Severe); CHECK(!m.resolve_penalty(p,"declined",false)); CHECK(m.resolve_penalty(p,"ejected")&&m.players[5].ejected&&m.resume()); CHECK(!m.possess(5,5,true)); p=m.record_penalty(7,"forfeit",Severity::Catastrophic); CHECK(!m.resolve_penalty(p,"cannot auto-resolve")&&m.penalties.back().pending);'''),
("invalid_indices_and_nonfinite_evidence", r'''Match m; CHECK(!m.possess(-1,0)&&!m.possess(16,0)&&!m.release(-1,0)&&!m.eligible(0,7)); CHECK(!m.crown_exit(0,{0,std::numeric_limits<double>::infinity(),138})); CHECK(!m.flight_evidence(5,std::numeric_limits<double>::quiet_NaN())); CHECK(!m.process_batch(0,{goal(7)}));'''),
("score_and_time_overflow_rejected", r'''Match m; m.scores[0]=std::numeric_limits<std::int64_t>::max()-1; auto before=fingerprint(m); CHECK(!m.process_batch(0,{goal()})); CHECK(fingerprint(m)==before); m.now_ms=std::numeric_limits<Millis>::max(); CHECK(m.advance(1)==-1);'''),
]


def driver_source():
    functions = []
    calls = []
    for index, (name, body) in enumerate(CASES):
        functions.append("bool case_%d(){\n%s\nreturn true;\n}\n" % (index, body))
        calls.append('if(case_%d()){std::cout<<"PASS\\t%s\\n";}else{++failed;std::cout<<"FAIL\\t%s\\n";}' % (index, name, name))
    return PREAMBLE + "\n".join(functions) + "\nint main(){int failed=0;\n" + "\n".join(calls) + "\nreturn failed?1:0;}\n"


def compiler_environment(vcvars):
    env = os.environ.copy()
    if vcvars:
        if os.name != "nt" or not Path(vcvars).is_file():
            raise ValueError("--vcvars must point to an installed Windows vcvars64.bat")
        # Only the selected compiler's environment is imported into this child.
        command = 'call "%s" >nul && set' % str(Path(vcvars).resolve())
        # cmd.exe does not understand the backslash-escaped quotes produced by
        # subprocess's list-to-command-line conversion. Preserve its /s /c
        # outer quotes so installed compiler paths with spaces remain intact.
        result = subprocess.run('cmd.exe /d /s /c "' + command + '"',
                                capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator and key:
                env[key] = value
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler")
    parser.add_argument("--vcvars")
    parser.add_argument("--emit-only", action="store_true")
    options = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    driver = OUTPUT / "native_rules_tests.cpp"
    driver.write_text(driver_source(), encoding="utf-8")
    report = {"status": "not_run", "scenarios": len(CASES), "reference_scenarios": 54,
              "driver": str(driver)}
    report_path = OUTPUT / "results.json"
    if options.emit_only:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    env = compiler_environment(options.vcvars)
    search_path = env.get("PATH", env.get("Path", ""))
    # Windows environment dictionaries can contain both Path and PATH after vcvars.
    if options.vcvars:
        for key, value in env.items():
            if key.lower() == "path":
                search_path = value
    compiler = options.compiler or next((shutil.which(name, path=search_path)
                                         for name in ("cl.exe", "clang++", "g++")
                                         if shutil.which(name, path=search_path)), None)
    if compiler is None:
        report["reason"] = "No C++ compiler available; pass --vcvars or --compiler."
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 2
    # Bundled MinGW compilers also keep their runtime DLLs alongside g++.exe.
    compiler_bin = str(Path(compiler).resolve().parent)
    for key in list(env):
        if key.lower() == "path":
            del env[key]
    env["PATH"] = compiler_bin + os.pathsep + search_path
    executable = OUTPUT / ("native_rules_tests.exe" if os.name == "nt" else "native_rules_tests")
    if Path(compiler).name.lower() in ("cl", "cl.exe"):
        command = [compiler, "/nologo", "/std:c++17", "/EHsc", "/W4", "/WX", "/O2",
                   "/I" + str(SOURCE), str(driver), str(SOURCE / "BBRuleEngine.cpp"),
                   "/Fe:" + str(executable)]
    else:
        command = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fno-exceptions", "-O2",
                   "-I", str(SOURCE), str(driver), str(SOURCE / "BBRuleEngine.cpp"), "-o", str(executable)]
    compiled = subprocess.run(command, cwd=OUTPUT, env=env, capture_output=True, text=True)
    (OUTPUT / "compile.log").write_text(compiled.stdout + compiled.stderr, encoding="utf-8")
    report["compiler"] = compiler
    if compiled.returncode:
        report.update(status="compile_failed", output=compiled.stdout + compiled.stderr)
    else:
        run = subprocess.run([str(executable)], cwd=OUTPUT, env=env, capture_output=True, text=True)
        (OUTPUT / "test.log").write_text(run.stdout + run.stderr, encoding="utf-8")
        passed = [line[5:] for line in run.stdout.splitlines() if line.startswith("PASS\t")]
        failed = [line[5:] for line in run.stdout.splitlines() if line.startswith("FAIL\t")]
        report.update(status="passed" if run.returncode == 0 and len(passed) == len(CASES) else "failed",
                      passed=len(passed), failed=failed, errors=run.stderr, exit_code=run.returncode)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())

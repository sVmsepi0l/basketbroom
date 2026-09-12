"""Compile BB-0 conduct policy tests without Unreal; no editor or game launched.

Supports --vcvars/--compiler and --emit-only like test_native_rules.py.
The driver uses only public server-side events; no private state injection.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "DevelopmentHarness/Source/BasketbroomRuntime"
OUTPUT = ROOT / ".local/native-combat-rules"
PREAMBLE = r'''
#include "BBCombatRules.h"
#include <iostream>
#include <limits>
#include <sstream>
using namespace BB;
#define CHECK(...) do { if (!(__VA_ARGS__)) { std::cerr << "line " << __LINE__ << ": " << #__VA_ARGS__ << "\n"; return false; } } while(false)
AttackSpec stun(){AttackSpec s; s.stun=true; return s;}
AttackSpec impediment(){AttackSpec s; s.impediment=true; return s;}
bool candidate(const CombatDecision& d,ConductViolation v){return (d.attempt_violations&static_cast<std::uint32_t>(v))!=0;}
std::uint64_t success(CombatPolicy& p,int a=0,int t=8,std::int64_t duration=-1){
 auto cast=p.begin_attack(a,t,impediment()); if(!cast.accepted)return 0;
 if(!p.resolve_hit(cast.attack_id,HitOutcome::Impeded,false,duration).accepted)return 0;
 if(!p.confirm_impediment(cast.attack_id,a).accepted)return 0; return cast.attack_id;
}
'''

CASES = [
    ("regulation_applies_unforgivable_headshot_then_reports_once", r'''
CombatPolicy p; AttackSpec s=stun(); s.unforgivable=s.aimed_at_head=true;
auto cast=p.begin_attack(0,8,s); CHECK(cast.accepted&&cast.attack_id&&!cast.legal()&&!cast.requires_adjudication());
CHECK(candidate(cast,ConductViolation::Unforgivable)&&candidate(cast,ConductViolation::Headshot));
auto hit=p.resolve_hit(cast.attack_id,HitOutcome::Contact,true);
CHECK(hit.accepted&&!hit.legal()&&hit.has(ConductViolation::Unforgivable)&&hit.has(ConductViolation::Headshot));
auto duplicate=p.resolve_hit(cast.attack_id,HitOutcome::Contact,true);
CHECK(!duplicate.accepted&&duplicate.denial==CombatDenial::AlreadyResolved&&!duplicate.requires_adjudication());
'''),
    ("bloodbroom_exempts_only_unforgivable_and_headshot", r'''
CombatPolicy p(CombatConfig{},CombatVariant::Bloodbroom); auto s=stun(); s.unforgivable=s.aimed_at_head=s.impediment=true;
auto cast=p.begin_attack(0,8,s); CHECK(cast.accepted&&cast.legal());
auto hit=p.resolve_hit(cast.attack_id,HitOutcome::Impeded,true); CHECK(hit.accepted&&hit.legal());
CHECK(p.confirm_impediment(cast.attack_id,0).accepted);
auto second=p.begin_attack(0,8,s); CHECK(second.accepted&&candidate(second,ConductViolation::DoubleTap));
auto repeat=p.resolve_hit(second.attack_id,HitOutcome::Impeded,true);
CHECK(repeat.accepted&&repeat.violations==static_cast<std::uint32_t>(ConductViolation::DoubleTap));
'''),
    ("physical_holding_is_contact_foul_in_both_variants", r'''
for(auto variant:{CombatVariant::Regulation,CombatVariant::Bloodbroom}) {
 CombatPolicy p(CombatConfig{},variant); AttackSpec s; s.physical_hold=true;
 auto cast=p.begin_attack(0,8,s); CHECK(cast.accepted&&candidate(cast,ConductViolation::PhysicalHolding));
 CHECK(!cast.requires_adjudication()); auto hit=p.resolve_hit(cast.attack_id,HitOutcome::Contact);
 CHECK(hit.accepted&&hit.has(ConductViolation::PhysicalHolding));
}
'''),
    ("missed_or_blocked_illegal_attempts_do_not_create_hit_penalties", r'''
for(auto outcome:{HitOutcome::Miss,HitOutcome::Blocked}) {
 CombatPolicy p; CHECK(success(p)); auto s=stun(); s.unforgivable=s.aimed_at_head=s.physical_hold=true;
 auto cast=p.begin_attack(0,8,s); CHECK(cast.accepted&&!cast.legal());
 auto hit=p.resolve_hit(cast.attack_id,outcome,true); CHECK(hit.accepted&&hit.legal()&&!hit.requires_adjudication());
 CHECK(!p.confirm_impediment(cast.attack_id,0).accepted);
}
'''),
    ("headshot_requires_actual_head_impact", r'''
CombatPolicy p; AttackSpec s; s.aimed_at_head=true; auto cast=p.begin_attack(0,8,s);
CHECK(candidate(cast,ConductViolation::Headshot)); CHECK(p.resolve_hit(cast.attack_id,HitOutcome::Contact,false).legal());
s.aimed_at_head=false; cast=p.begin_attack(0,8,s); auto hit=p.resolve_hit(cast.attack_id,HitOutcome::Contact,true);
CHECK(hit.accepted&&hit.has(ConductViolation::Headshot));
'''),
    ("three_distinct_attackers_then_fourth_hit_reports_mob", r'''
CombatPolicy p; for(int a=0;a<3;++a) {auto c=p.begin_attack(a,8,AttackSpec{}); CHECK(c.legal()); CHECK(p.resolve_hit(c.attack_id,HitOutcome::Contact).legal());}
auto fourth=p.begin_attack(3,8,AttackSpec{}); CHECK(fourth.accepted&&candidate(fourth,ConductViolation::Mobbing));
CHECK(p.active_attackers(0,8)==4&&!fourth.requires_adjudication());
auto hit=p.resolve_hit(fourth.attack_id,HitOutcome::Contact); CHECK(hit.accepted&&hit.has(ConductViolation::Mobbing));
'''),
    ("duplicate_attacker_is_one_mob_participant", r'''
CombatPolicy p; for(int i=0;i<20;++i) {auto c=p.begin_attack(0,8,AttackSpec{}); CHECK(c.legal()); CHECK(p.resolve_hit(c.attack_id,HitOutcome::Contact).legal());}
CHECK(p.active_attackers(0,8)==1); CHECK(p.begin_attack(1,8,AttackSpec{}).legal()); CHECK(p.begin_attack(2,8,AttackSpec{}).legal());
CHECK(p.begin_attack(0,8,AttackSpec{}).legal()&&p.active_attackers(0,8)==3);
'''),
    ("mob_teams_and_targets_are_independent", r'''
CombatPolicy p; for(int a:{0,1,2,8,9,10}) CHECK(p.begin_attack(a,15,AttackSpec{}).legal());
CHECK(p.active_attackers(0,15)==3&&p.active_attackers(1,15)==3);
CHECK(p.begin_attack(3,14,AttackSpec{}).legal());
CHECK(candidate(p.begin_attack(3,15,AttackSpec{}),ConductViolation::Mobbing));
CHECK(candidate(p.begin_attack(11,15,AttackSpec{}),ConductViolation::Mobbing));
'''),
    ("bloodbroom_retains_mob_rule", r'''
CombatPolicy p(CombatConfig{},CombatVariant::Bloodbroom); for(int a=0;a<3;++a) CHECK(p.begin_attack(a,8,AttackSpec{}).accepted);
auto cast=p.begin_attack(3,8,AttackSpec{}); auto hit=p.resolve_hit(cast.attack_id,HitOutcome::Contact,true);
CHECK(hit.accepted&&hit.violations==static_cast<std::uint32_t>(ConductViolation::Mobbing));
'''),
    ("blocked_fourth_attacker_does_not_receive_hit_adjudication", r'''
CombatPolicy p; for(int a=0;a<3;++a) CHECK(p.begin_attack(a,8,AttackSpec{}).accepted);
auto cast=p.begin_attack(3,8,AttackSpec{}); CHECK(candidate(cast,ConductViolation::Mobbing));
CHECK(p.resolve_hit(cast.attack_id,HitOutcome::Blocked).legal());
'''),
    ("invalid_attackers_do_not_occupy_mob_slots", r'''
CombatPolicy p; CHECK(!p.begin_attack(-1,8,AttackSpec{}).accepted&&!p.begin_attack(16,8,AttackSpec{}).accepted);
CHECK(!p.begin_attack(0,-1,AttackSpec{}).accepted&&!p.begin_attack(0,16,AttackSpec{}).accepted);
CHECK(!p.begin_attack(0,0,AttackSpec{}).accepted); CHECK(p.set_actor(0,0,false));
CHECK(!p.begin_attack(0,8,AttackSpec{}).accepted); CHECK(p.active_attackers(0,8)==0);
'''),
    ("protego_and_utility_do_not_count_as_attacks", r'''
CombatPolicy p; AttackSpec shield; shield.offensive=false;
for(int a=0;a<8;++a) {auto cast=p.begin_attack(a,8,shield); CHECK(cast.accepted&&cast.attack_id==0&&cast.legal());}
CHECK(p.begin_attack(0,0,shield).accepted&&p.active_attackers(0,8)==0);
CHECK(!p.resolve_hit(0,HitOutcome::Contact).accepted);
'''),
    ("cannot_hide_offensive_traits_in_nonoffensive_spec", r'''
CombatPolicy p; for(int i=0;i<5;++i) {AttackSpec s; s.offensive=false;
 if(i==0)s.stun=true; if(i==1)s.impediment=true; if(i==2)s.unforgivable=true; if(i==3)s.physical_hold=true; if(i==4)s.aimed_at_head=true;
 CHECK(!p.begin_attack(0,8,s).accepted);}
CHECK(p.active_attackers(0,8)==0);
'''),
    ("stun_and_impediment_are_distinct_traits", r'''
CombatPolicy p; auto first=p.begin_attack(0,8,stun()); CHECK(first.accepted&&first.legal());
CHECK(p.resolve_hit(first.attack_id,HitOutcome::Contact).legal());
CHECK(p.confirm_impediment(first.attack_id,0).denial==CombatDenial::NoSuccessfulImpediment);
auto second=p.begin_attack(0,8,stun()); CHECK(second.accepted&&second.legal());
CHECK(p.resolve_hit(second.attack_id,HitOutcome::Contact).legal());
'''),
    ("successful_impediment_needs_caster_confirmation", r'''
CombatPolicy p; auto first=p.begin_attack(0,8,impediment()); CHECK(p.resolve_hit(first.attack_id,HitOutcome::Impeded).accepted);
CHECK(p.begin_attack(0,8,stun()).legal()); CHECK(p.confirm_impediment(first.attack_id,0).accepted);
auto cast=p.begin_attack(0,8,stun()); CHECK(cast.accepted&&candidate(cast,ConductViolation::DoubleTap));
auto hit=p.resolve_hit(cast.attack_id,HitOutcome::Contact); CHECK(hit.accepted&&hit.has(ConductViolation::DoubleTap));
'''),
    ("cast_before_first_hit_is_not_retroactively_double_tap", r'''
CombatPolicy p; auto first=p.begin_attack(0,8,impediment()); auto in_flight=p.begin_attack(0,8,stun());
CHECK(p.resolve_hit(first.attack_id,HitOutcome::Impeded).accepted&&p.confirm_impediment(first.attack_id,0).accepted);
CHECK(p.resolve_hit(in_flight.attack_id,HitOutcome::Contact).legal());
CHECK(candidate(p.begin_attack(0,8,stun()),ConductViolation::DoubleTap));
'''),
    ("cast_after_hit_but_before_notice_is_not_retroactively_double_tap", r'''
CombatPolicy p; auto first=p.begin_attack(0,8,impediment()); CHECK(p.resolve_hit(first.attack_id,HitOutcome::Impeded).accepted);
auto in_flight=p.begin_attack(0,8,stun()); CHECK(p.confirm_impediment(first.attack_id,0).accepted);
CHECK(p.resolve_hit(in_flight.attack_id,HitOutcome::Contact).legal());
'''),
    ("miss_block_and_nonimpeding_contact_create_no_protection", r'''
for(auto outcome:{HitOutcome::Miss,HitOutcome::Blocked,HitOutcome::Contact}) {
 CombatPolicy p; auto cast=p.begin_attack(0,8,impediment()); CHECK(p.resolve_hit(cast.attack_id,outcome).accepted);
 CHECK(p.confirm_impediment(cast.attack_id,0).denial==CombatDenial::NoSuccessfulImpediment);
 CHECK(p.begin_attack(0,8,stun()).legal());
}
'''),
    ("confirmation_requires_existing_success_id_and_its_caster", r'''
CombatPolicy p; CHECK(!p.confirm_impediment(999,0).accepted); auto cast=p.begin_attack(0,8,impediment());
CHECK(!p.confirm_impediment(cast.attack_id,0).accepted); CHECK(p.resolve_hit(cast.attack_id,HitOutcome::Impeded).accepted);
CHECK(p.confirm_impediment(cast.attack_id,1).denial==CombatDenial::WrongNotifier);
CHECK(p.begin_attack(0,8,stun()).legal()); CHECK(p.confirm_impediment(cast.attack_id,0).accepted);
CHECK(p.confirm_impediment(cast.attack_id,0).denial==CombatDenial::AlreadyConfirmed);
'''),
    ("confirmation_scope_is_caster_and_victim_and_stun_only", r'''
CombatPolicy p; CHECK(success(p)); CHECK(p.begin_attack(0,9,stun()).legal());
CHECK(p.begin_attack(1,8,stun()).legal()); CHECK(p.begin_attack(0,8,impediment()).legal());
CHECK(candidate(p.begin_attack(0,8,stun()),ConductViolation::DoubleTap));
'''),
    ("mob_window_expires_at_exact_live_boundary", r'''
CombatPolicy p; for(int a=0;a<3;++a) CHECK(p.begin_attack(a,8,AttackSpec{}).accepted);
CHECK(p.advance(1999)&&p.active_attackers(0,8)==3); CHECK(p.advance(1)&&p.active_attackers(0,8)==0);
CHECK(p.begin_attack(3,8,AttackSpec{}).legal());
'''),
    ("duplicate_attack_refreshes_only_its_own_window", r'''
CombatPolicy p; CHECK(p.begin_attack(0,8,AttackSpec{}).accepted&&p.begin_attack(1,8,AttackSpec{}).accepted);
CHECK(p.advance(1500)&&p.begin_attack(0,8,AttackSpec{}).accepted&&p.advance(500));
CHECK(p.active_attackers(0,8)==1); CHECK(p.advance(1500)&&p.active_attackers(0,8)==0);
'''),
    ("impediment_expires_from_hit_not_confirmation", r'''
CombatPolicy p; auto cast=p.begin_attack(0,8,impediment()); CHECK(p.resolve_hit(cast.attack_id,HitOutcome::Impeded).accepted);
CHECK(p.advance(2900)&&p.confirm_impediment(cast.attack_id,0).accepted);
CHECK(candidate(p.begin_attack(0,8,stun()),ConductViolation::DoubleTap)); CHECK(p.advance(100));
CHECK(p.begin_attack(0,8,stun()).legal());
'''),
    ("late_notice_cannot_revive_recovered_impediment", r'''
CombatPolicy p; auto cast=p.begin_attack(0,8,impediment()); CHECK(p.resolve_hit(cast.attack_id,HitOutcome::Impeded,false,200).accepted);
CHECK(p.advance(200)&&p.confirm_impediment(cast.attack_id,0).denial==CombatDenial::ImpedimentExpired);
CHECK(p.begin_attack(0,8,stun()).legal());
'''),
    ("native_recovery_ends_protection_before_maximum", r'''
CombatPolicy p; auto id=success(p); CHECK(id&&p.advance(100)&&p.end_impediment(id));
CHECK(!p.end_impediment(id)&&p.begin_attack(0,8,stun()).legal());
CHECK(success(p)); p.recover_target(8); CHECK(p.begin_attack(0,8,stun()).legal());
'''),
    ("ending_one_impediment_does_not_clear_another", r'''
CombatPolicy p; auto first=success(p); auto second=success(p); CHECK(first&&second&&p.end_impediment(first));
CHECK(candidate(p.begin_attack(0,8,stun()),ConductViolation::DoubleTap)); CHECK(p.end_impediment(second));
CHECK(p.begin_attack(0,8,stun()).legal());
'''),
    ("stoppage_freezes_windows_and_rejects_new_attack_or_hit", r'''
CombatPolicy p; CHECK(success(p)); auto pending=p.begin_attack(1,8,AttackSpec{});
CHECK(p.advance(1000000,false)&&p.now_ms()==0&&!p.is_live());
CHECK(p.begin_attack(0,8,stun()).denial==CombatDenial::NotLive);
CHECK(p.resolve_hit(pending.attack_id,HitOutcome::Contact).denial==CombatDenial::NotLive);
p.set_live(true); CHECK(candidate(p.begin_attack(0,8,stun()),ConductViolation::DoubleTap));
CHECK(p.resolve_hit(pending.attack_id,HitOutcome::Contact).accepted);
'''),
    ("feedback_delivery_during_pause_preserves_live_timing", r'''
CombatPolicy p; auto cast=p.begin_attack(0,8,impediment()); CHECK(p.resolve_hit(cast.attack_id,HitOutcome::Impeded).accepted);
p.set_live(false); CHECK(p.confirm_impediment(cast.attack_id,0).accepted&&p.advance(999999,false));
p.set_live(true); CHECK(candidate(p.begin_attack(0,8,stun()),ConductViolation::DoubleTap));
'''),
    ("phase_reset_clears_windows_and_rejects_old_ids", r'''
CombatPolicy p; auto old=success(p); CHECK(old&&p.advance(100)); p.reset_phase();
CHECK(p.now_ms()==100&&p.active_attackers(0,8)==0&&p.begin_attack(0,8,stun()).legal());
CHECK(!p.confirm_impediment(old,0).accepted&&!p.resolve_hit(old,HitOutcome::Impeded).accepted);
CHECK(p.begin_attack(1,8,AttackSpec{}).attack_id>old);
'''),
    ("rematch_changes_variant_without_reusing_ids", r'''
CombatPolicy p; auto old=success(p); CHECK(old&&p.advance(100)&&p.reset_match(CombatVariant::Bloodbroom));
CHECK(p.now_ms()==0&&p.variant()==CombatVariant::Bloodbroom&&p.active_attackers(0,8)==0);
auto s=stun(); s.unforgivable=true; auto cast=p.begin_attack(0,8,s); CHECK(cast.legal()&&cast.attack_id>old);
CHECK(!p.confirm_impediment(old,0).accepted);
'''),
    ("reused_combatant_slot_does_not_inherit_confirmation_or_pending_ids", r'''
CombatPolicy p; auto old=success(p); CHECK(old&&p.set_actor(0,0,true,true));
CHECK(p.begin_attack(0,8,stun()).legal()&&!p.confirm_impediment(old,0).accepted);
auto victim_old=success(p); CHECK(victim_old&&p.set_actor(8,1,true,true));
CHECK(p.begin_attack(0,8,stun()).legal()&&!p.confirm_impediment(victim_old,0).accepted);
'''),
    ("eligibility_refresh_does_not_erase_existing_confirmation", r'''
CombatPolicy p; CHECK(success(p)&&p.set_actor(0,0,false)); CHECK(!p.begin_attack(0,8,stun()).accepted);
CHECK(p.set_actor(0,0,true)); CHECK(candidate(p.begin_attack(0,8,stun()),ConductViolation::DoubleTap));
'''),
    ("invalid_and_unproven_hit_evidence_never_consumes_pending_id", r'''
CombatPolicy p; auto cast=p.begin_attack(0,8,impediment()); CHECK(!p.resolve_hit(999,HitOutcome::Impeded).accepted);
CHECK(!p.resolve_hit(cast.attack_id,static_cast<HitOutcome>(99)).accepted);
CHECK(!p.resolve_hit(cast.attack_id,HitOutcome::Impeded,false,0).accepted);
CHECK(!p.resolve_hit(cast.attack_id,HitOutcome::Impeded,false,3001).accepted);
CHECK(p.resolve_hit(cast.attack_id,HitOutcome::Impeded,false,500).accepted);
auto plain=p.begin_attack(0,9,AttackSpec{}); CHECK(!p.resolve_hit(plain.attack_id,HitOutcome::Impeded).accepted);
CHECK(p.resolve_hit(plain.attack_id,HitOutcome::Contact).accepted);
'''),
    ("unresolved_attack_has_configurable_live_expiry", r'''
CombatConfig c; c.pending_attack_ms=100; CombatPolicy p(c); auto cast=p.begin_attack(0,8,stun());
CHECK(p.advance(100)&&!p.resolve_hit(cast.attack_id,HitOutcome::Impeded).accepted);
CHECK(p.begin_attack(0,8,stun()).legal());
'''),
    ("provisional_windows_are_configurable", r'''
CombatConfig c; c.mob_window_ms=50; c.max_impediment_ms=75; CombatPolicy p(c);
CHECK(success(p)); CHECK(p.advance(50)&&p.active_attackers(0,8)==0);
CHECK(candidate(p.begin_attack(0,8,stun()),ConductViolation::DoubleTap)); CHECK(p.advance(25));
CHECK(p.begin_attack(0,8,stun()).legal());
'''),
    ("invalid_config_roster_team_and_variant_are_rejected", r'''
for(int field=0;field<3;++field) {CombatConfig c; if(field==0)c.mob_window_ms=0; if(field==1)c.max_impediment_ms=-1; if(field==2)c.pending_attack_ms=0;
 CombatPolicy invalid(c); CHECK(!invalid.is_valid()&&!invalid.begin_attack(0,8,stun()).accepted);}
CombatPolicy p; auto roster=CombatPolicy::default_roster(); roster[0].team=2; CHECK(!p.configure_roster(roster));
CHECK(!p.set_actor(16,0,true)&&!p.set_actor(0,2,true)&&!p.set_actor(0,-1,true));
CHECK(!p.reset_match(static_cast<CombatVariant>(99))&&p.variant()==CombatVariant::Regulation);
CHECK(p.set_actor(0,-1,false)&&!p.begin_attack(0,8,stun()).accepted);
'''),
    ("clock_invalid_input_and_overflow_are_atomic", r'''
CombatPolicy p; p.set_live(false); CHECK(!p.advance(-1,true)&&p.now_ms()==0&&!p.is_live());
CHECK(p.advance(std::numeric_limits<std::int64_t>::max(),true));
CHECK(p.advance(1,false)); CHECK(p.now_ms()==std::numeric_limits<std::int64_t>::max()&&!p.is_live());
CHECK(!p.advance(1,true)&&!p.is_live()); p.set_live(true);
CHECK(p.begin_attack(0,8,stun()).denial==CombatDenial::InvalidTime&&p.active_attackers(0,8)==0);
'''),
    ("same_event_stream_replays_identically", r'''
auto run=[](){CombatPolicy p; std::ostringstream out; auto a=p.begin_attack(0,8,impediment());
 out<<a.accepted<<a.attack_id<<a.attempt_violations; auto h=p.resolve_hit(a.attack_id,HitOutcome::Impeded);
 out<<h.accepted<<h.violations<<p.confirm_impediment(a.attack_id,0).accepted; auto b=p.begin_attack(0,8,stun());
 out<<b.attack_id<<b.attempt_violations<<p.resolve_hit(b.attack_id,HitOutcome::Contact).violations;
 p.advance(3000); out<<p.now_ms()<<p.begin_attack(0,8,stun()).legal(); return out.str();}; CHECK(run()==run());
'''),
]


def driver_source():
    functions, calls = [], []
    for index, (name, body) in enumerate(CASES):
        functions.append("bool case_%d(){\n%s\nreturn true;\n}" % (index, body))
        calls.append('if(case_%d()){std::cout<<"PASS\\t%s\\n";}else{++failed;std::cout<<"FAIL\\t%s\\n";}' % (index, name, name))
    return PREAMBLE + "\n".join(functions) + "\nint main(){int failed=0;\n" + "\n".join(calls) + "\nreturn failed?1:0;}\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler")
    parser.add_argument("--vcvars")
    parser.add_argument("--emit-only", action="store_true")
    options = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    driver = OUTPUT / "combat_rules_tests.cpp"
    driver.write_text(driver_source(), encoding="utf-8")
    report = {"status": "not_run", "scenarios": len(CASES), "driver": str(driver),
              "scope": "Portable BB-0 server conduct policy, not engine/network validation"}
    report_path = OUTPUT / "results.json"
    if options.emit_only:
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    spec = importlib.util.spec_from_file_location("_bb_combat_compiler", Path(__file__).with_name("test_native_rules.py"))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    env = helper.compiler_environment(options.vcvars)
    search_path = next((value for key, value in reversed(list(env.items())) if key.lower() == "path"), "")
    compiler = options.compiler or next((shutil.which(name, path=search_path) for name in ("cl.exe", "clang++", "g++")
                                         if shutil.which(name, path=search_path)), None)
    if compiler is None:
        report["reason"] = "No compiler available; pass --vcvars or --compiler."
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2
    for key in list(env):
        if key.lower() == "path":
            del env[key]
    env["PATH"] = str(Path(compiler).resolve().parent) + os.pathsep + search_path
    executable = OUTPUT / ("combat_rules_tests.exe" if os.name == "nt" else "combat_rules_tests")
    if Path(compiler).name.lower() in ("cl", "cl.exe"):
        command = [compiler, "/nologo", "/std:c++17", "/EHs-c-", "/D_HAS_EXCEPTIONS=0", "/W4", "/WX", "/O2",
                   "/I" + str(SOURCE), str(driver), str(SOURCE / "BBCombatRules.cpp"), "/Fe:" + str(executable)]
    else:
        command = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fno-exceptions", "-O2", "-I", str(SOURCE),
                   str(driver), str(SOURCE / "BBCombatRules.cpp"), "-o", str(executable)]
    built = subprocess.run(command, cwd=OUTPUT, env=env, capture_output=True, text=True)
    (OUTPUT / "compile.log").write_text(built.stdout + built.stderr, encoding="utf-8")
    report["compiler"] = compiler
    if built.returncode:
        report.update(status="compile_failed", output=built.stdout + built.stderr)
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

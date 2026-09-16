"""Portable tests for server-owned earned broom energy; no Unreal/hardware claim."""
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bb_flight_runner', ROOT/'Tools/test_native_rules.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
r.OUTPUT = ROOT/'.local/native-flight-policy'
r.PREAMBLE = r'''
#include "BBFlightPolicy.h"
#include <iostream>
#include <limits>
#include <cmath>
#define CHECK(...) do { if(!(__VA_ARGS__)) { std::cerr << "line " << __LINE__ << ": " << #__VA_ARGS__ << "\n"; return false; } } while(false)
using BBFlight::Energy;
Energy full(){Energy s;for(unsigned i=1;i<=4;++i)s.award(0,i,25.f);return s;}
bool near(float a,float b){return std::abs(a-b)<.001f;}
'''
r.CASES = [
('empty_meter_retains_normal_acceleration',r'Energy s;s.input(1,0,true);s.advance(1,true);CHECK(s.charge==0&&s.scale(true)==1);'),
('score_and_bludger_rewards_are_bounded_and_independent',r'Energy s;CHECK(s.award(0,1,25)&&s.award(1,1,15)&&s.charge==40);'),
('duplicate_and_old_events_cannot_farm_energy',r'Energy s;CHECK(s.award(0,4,25));CHECK(!s.award(0,4,25)&&!s.award(0,3,25)&&s.charge==25);'),
('invalid_rewards_reject_without_consuming_event_ids',r'Energy s;for(float v:{-1.f,0.f,26.f,std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()})CHECK(!s.award(0,1,v));CHECK(!s.award(2,1,1)&&!s.award(0,0,1)&&!s.award(1,1,16));CHECK(s.award(0,1,25));'),
('charge_saturates_at_100',r'auto s=full();CHECK(s.award(0,5,25)&&s.charge==100);'),
('partial_meter_provides_regular_boost_and_drain',r'Energy s;s.award(0,1,25);s.input(1,0,true);CHECK(near(s.scale(true),1.35f));s.advance(1,true);CHECK(s.charge==13&&s.super_remaining==0);'),
('partial_trigger_scales_boost_and_consumption',r'Energy s;s.award(0,1,25);s.input(.5f,0,true);CHECK(near(s.scale(true),1.175f));s.advance(1,true);CHECK(s.charge==19);'),
('zero_charge_never_goes_negative',r'Energy s;s.award(1,1,15);s.input(1,0,true);s.advance(500,true);CHECK(s.charge==0&&s.scale(true)==1);'),
('full_fresh_press_spends_100_for_superboost',r'auto s=full();s.input(1,0,true);CHECK(s.charge==0&&s.super_remaining==2&&s.scale(true)==2);'),
('super_expires_without_creating_new_energy',r'auto s=full();s.input(1,0,true);s.advance(1,true);CHECK(s.super_remaining==1);s.advance(1,true);CHECK(s.super_remaining==0&&s.charge==0&&s.scale(true)==1);'),
('held_trigger_filling_to_full_never_auto_bursts',r'Energy s;s.input(1,0,true);for(unsigned i=1;i<=4;++i)s.award(0,i,25);s.input(1,0,true);s.advance(.5f,true);CHECK(s.charge==100&&s.super_remaining==0&&s.scale(true)==1);s.input(0,0,true);s.input(1,0,true);CHECK(s.charge==0&&s.super_remaining==2);'),
('brake_has_priority_without_consuming_charge',r'auto s=full();s.input(1,.5f,true);s.advance(1,true);CHECK(s.charge==100&&s.super_remaining==0&&s.scale(true)==1);'),
('release_brake_while_throttle_held_does_not_create_fresh_press',r'auto s=full();s.input(1,1,true);s.input(1,0,true);CHECK(s.charge==100&&s.super_remaining==0);'),
('brake_cancels_super_without_refund',r'auto s=full();s.input(1,0,true);s.input(1,1,true);CHECK(s.charge==0&&s.super_remaining==0&&s.scale(true)==1);'),
('release_cancels_super_without_refund',r'auto s=full();s.input(1,0,true);s.input(0,0,true);CHECK(s.charge==0&&s.super_remaining==0);'),
('stoppage_spelllock_penalty_never_spend_or_boost',r'auto s=full();s.input(1,0,false);s.advance(10,false);CHECK(s.charge==100&&s.super_remaining==0&&s.scale(false)==1);s.input(1,0,true);CHECK(s.charge==100&&s.super_remaining==0);'),
('stoppage_cancels_active_super_without_refund',r'auto s=full();s.input(1,0,true);s.advance(.5f,false);CHECK(s.charge==0&&s.super_remaining==0);'),
('focus_or_disconnect_cancel_preserves_charge_and_ledger',r'Energy s;s.award(0,1,25);s.input(1,0,true);s.cancel();CHECK(s.charge==25&&s.throttle==0&&!s.held&&!s.award(0,1,25));'),
('nan_trigger_and_brake_are_safe',r'auto s=full();s.input(std::numeric_limits<float>::quiet_NaN(),0,true);CHECK(s.scale(true)==1&&s.charge==100);s.input(1,std::numeric_limits<float>::quiet_NaN(),true);CHECK(s.brake==1&&s.charge==100);'),
('invalid_delta_time_never_changes_energy',r'Energy s;s.award(0,1,25);s.input(1,0,true);for(float dt:{-1.f,0.f,std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()})s.advance(dt,true);CHECK(s.charge==25);'),
('time_partition_preserves_regular_drain',r'Energy a,b;a.award(0,1,25);b.award(0,1,25);a.input(.6f,0,true);b.input(.6f,0,true);a.advance(1,true);for(int i=0;i<100;++i)b.advance(.01f,true);CHECK(near(a.charge,b.charge));'),
('genuine_match_reset_alone_clears_energy_and_ledger',r'auto s=full();s=Energy{};CHECK(s.charge==0&&s.award(0,1,25));'),
]
if __name__=='__main__':
    with contextlib.redirect_stdout(io.StringIO()):
        code = r.main()
    path = r.OUTPUT/'results.json'
    report = json.loads(path.read_text())
    report.pop('reference_scenarios', None)
    report['scope'] = 'Portable server-owned flight energy policy; no Unreal or hardware proof'
    path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    sys.exit(code)

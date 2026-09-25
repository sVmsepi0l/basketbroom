"""Compile/test the actual bounded native trail sampler; no rendered VFX claim.

--list is read-only discovery. Full execution uses the established portable C++
test runner and writes evidence beneath .local/native-broom-trail-policy.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bb_trail_runner', ROOT/'Tools/test_native_rules.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
r.OUTPUT = ROOT/'.local/native-broom-trail-policy'
r.PREAMBLE = r'''
#include "BBBroomTrailPolicy.h"
#include <iostream>
#include <limits>
#define CHECK(...) do { if(!(__VA_ARGS__)) { std::cerr << "line " << __LINE__ << ": " << #__VA_ARGS__ << "\n"; return false; } } while(false)
using namespace BBBroomTrail;
Sample frame(double time, double speed=2100.) { Sample s; s.time=time; s.position={time*speed,0,0}; return s; }
History run(int fps,double seconds=3.) { History h; for(int i=0;i<=int(seconds*fps);++i)h.advance(frame(double(i)/fps),true,2100.);return h; }
bool near(double a,double b){return std::abs(a-b)<1e-6;}
'''
r.CASES = [
('fixed_timeline_matches_30_60_120_and_144_fps', r'''
auto a=run(30); for(int fps:{60,120,144}) { auto b=run(fps);CHECK(a.size()==b.size());
for(std::size_t i=0;i<a.size();++i){CHECK(near(a.at(i).time,b.at(i).time));CHECK(near(a.at(i).position[0],b.at(i).position[0]));}}'''),
('history_storage_and_age_are_bounded_over_long_flight', r'''
History h;for(int i=0;i<100000;++i){double t=i/60.;h.advance(frame(t),true,2100.);CHECK(h.size()<=Capacity);
CHECK(h.size()>0&&t-h.at(0).time<=MaxLifetime+SamplePeriod);}'''),
('teleport_starts_new_strand_instead_of_cross_arena_beam', r'''
auto h=run(60);auto s=frame(3.+SamplePeriod);s.position[1]=10000.;CHECK(h.advance(s,true,2100.));
CHECK(h.size()==1&&near(h.at(0).position[1],10000.));'''),
('hitch_discards_stale_interpolated_path', r'''
auto h=run(60);CHECK(h.advance(frame(4.),true,2100.));CHECK(h.size()==1&&near(h.at(0).time,4.));'''),
('clock_rewind_starts_fresh_history', r'''
auto h=run(60);CHECK(h.advance(frame(1.),true,2100.));CHECK(h.size()==1&&near(h.at(0).time,1.));'''),
('paused_clock_does_not_duplicate_samples', r'''
auto h=run(60);auto count=h.size();for(int i=0;i<100;++i)CHECK(!h.advance(frame(3.),true,2100.));CHECK(h.size()==count);'''),
('stopped_emitter_ages_out_without_new_points', r'''
auto h=run(60);for(int i=1;i<=120;++i){auto s=frame(3.);s.time=3.+i/60.;h.advance(s,false,0.);}CHECK(h.size()==0);'''),
('disabled_initial_emitter_cannot_create_stationary_tracer', r'''
History h;for(int i=0;i<120;++i)h.advance(frame(i/60.,0),false,0.);CHECK(h.size()==0);'''),
('full_speed_continuous_super_flight_is_not_a_teleport', r'''
History h;for(int i=0;i<300;++i)CHECK(!h.advance(frame(i/30.,4200.),true,4200.));CHECK(h.size()>60);'''),
('nonfinite_transform_clears_history_safely', r'''
auto h=run(60);auto s=frame(3.+SamplePeriod);s.right[1]=std::numeric_limits<double>::quiet_NaN();
CHECK(h.advance(s,true,2100.)&&h.size()==0);'''),
('invalid_speed_clears_history_without_emission', r'''
auto h=run(60);CHECK(h.advance(frame(3.+SamplePeriod),true,std::numeric_limits<double>::infinity()));CHECK(h.size()==0);'''),
('explicit_respawn_clear_cannot_reconnect_old_history', r'''
auto h=run(60);h.clear();CHECK(h.size()==0);auto s=frame(3.);s.position[2]=20000.;CHECK(!h.advance(s,true,2100.));CHECK(h.size()==1);'''),
('earned_boost_extends_lifetime_with_hard_maximum', r'''
CHECK(lifetime(0)<lifetime(.55)&&lifetime(.55)<lifetime(1));CHECK(lifetime(1)<=MaxLifetime);
CHECK(near(lifetime(-4),lifetime(0))&&near(lifetime(50),lifetime(1)));'''),
('tail_taper_is_monotonic_and_expires_exactly', r'''
double before=1;for(int i=0;i<=100;++i){double value=taper(i/100.,1.);CHECK(value>=0&&value<=before);before=value;}
CHECK(taper(1.,1.)==0&&taper(2.,1.)==0&&taper(-1.,1.)==0&&taper(0,0)==0);'''),
('custom_color_clamps_rgb_without_changing_valid_hues', r'''
std::array<float,3> c{-2.f,.4f,6.f};CHECK(normalize_color(c));CHECK(c[0]==0&&c[1]==.4f&&c[2]==1);
std::array<float,3> d{.15f,.7f,.3f};auto old=d;CHECK(normalize_color(d)&&d==old);'''),
('nonfinite_custom_colors_are_rejected_atomically', r'''
for(float invalid:{std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()})
{std::array<float,3> c{-3.f,invalid,5.f};CHECK(!normalize_color(c));CHECK(c[0]==-3.f&&c[2]==5.f);}'''),
]

if __name__ == '__main__':
    if '--list' in sys.argv:
        print(json.dumps({'status':'not_run','cases':[name for name,_ in r.CASES],
                          'total_planned':len(r.CASES)},indent=2))
        raise SystemExit(0)
    with contextlib.redirect_stdout(io.StringIO()):
        code = r.main()
    path = r.OUTPUT/'results.json'
    report = json.loads(path.read_text())
    report.pop('reference_scenarios',None)
    report['scope'] = 'Portable native trail sampling, bounds and color validation; no Unreal rendering or network proof'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    raise SystemExit(code)

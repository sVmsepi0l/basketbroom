"""Compile the exact native admission policy against real portable rule transitions.

No Unreal editor is launched. Reuses the existing compiler/report harness in a
private module; its original 68-scenario suite and report remain untouched.
"""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_basketbroom_admission_compiler", ROOT / "Tools/test_native_rules.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.OUTPUT = ROOT / ".local/native-admission-rules"
base.PREAMBLE += '\n#include "BBAdmission.h"\n'
base.CASES = [
    ("newcomer_avoids_departed_players_pending_crown_without_erasing_it", r'''
        Match m(legacy_crown_config()); std::array<bool,16> occupied{};
        CHECK(m.possess(4,1)&&m.crown_exit(1,{0,0,138},4)&&m.crown_return(1));
        const auto before=fingerprint(m); const int slot=SelectAdmissionSlot(m,occupied,0);
        CHECK(slot>=0&&slot<8&&slot!=4&&m.eligible(slot,1));
        CHECK(fingerprint(m)==before&&m.penalties[0].pending&&m.penalties[0].crown_restoration_pending);
    '''),
    ("reserved_team_remedy_survives_newcomer_selection_and_serves_opponent", r'''
        Match m(legacy_crown_config()); std::array<bool,16> occupied{};
        CHECK(m.crown_exit(1,{0,0,138},4)&&m.pause()&&m.prepare_crown_restart(1));
        const auto before=fingerprint(m); const int slot=SelectAdmissionSlot(m,occupied,0);
        CHECK(slot>=0&&slot!=4&&fingerprint(m)==before);
        CHECK(!m.penalties[0].pending&&m.penalties[0].crown_restoration_pending);
        CHECK(m.balls[1].crown_restart_penalty==1&&m.balls[1].restart_team==1);
        CHECK(m.resume()&&m.restart(1,9));
        CHECK(!m.penalties[0].crown_restoration_pending&&m.penalties[0].player==4);
        CHECK(m.penalties[0].crown_restoration_receiver==9);
    '''),
    ("all_pending_slots_require_spectating_and_keep_every_historical_foul", r'''
        Match m; std::array<bool,16> occupied{};
        for(int slot=0;slot<16;++slot) CHECK(m.record_penalty(slot,"ordinary foul",Severity::Minor)>0);
        const auto before=fingerprint(m);
        CHECK(SelectAdmissionSlot(m,occupied,0)==-1&&SelectAdmissionSlot(m,occupied,1)==-1);
        CHECK(fingerprint(m)==before&&m.penalties.size()==16);
    '''),
    ("occupied_clean_slots_do_not_make_a_restricted_slot_safe", r'''
        Match m(legacy_crown_config()); std::array<bool,16> occupied; occupied.fill(true); occupied[4]=false;
        CHECK(m.crown_exit(1,{0,0,138},4)); const auto before=fingerprint(m);
        CHECK(SelectAdmissionSlot(m,occupied,0)==-1&&fingerprint(m)==before);
    '''),
    ("all_physical_slots_unavailable_requires_spectating", r'''
        Match m; std::array<bool,16> occupied; occupied.fill(true);
        CHECK(SelectAdmissionSlot(m,occupied,0)==-1);
        occupied[12]=false; CHECK(SelectAdmissionSlot(m,occupied,0)==12);
    '''),
    ("temporary_removal_must_expire_before_slot_is_available", r'''
        Match m; std::array<bool,16> occupied; occupied.fill(true); occupied[4]=false;
        const int p=m.record_penalty(4,"serious foul",Severity::Serious);
        CHECK(p>0&&m.resolve_penalty(p,"serve removal"));
        const auto before=fingerprint(m);
        CHECK(SelectAdmissionSlot(m,occupied,0)==-1&&fingerprint(m)==before);
        CHECK(m.resume()&&m.advance(m.config.removal_ms)==m.config.removal_ms);
        CHECK(SelectAdmissionSlot(m,occupied,0)==4&&m.penalties.size()==1);
    '''),
    ("resolved_ejection_does_not_transfer_to_a_newcomer", r'''
        Match m; std::array<bool,16> occupied; occupied.fill(true); occupied[4]=false;
        const int p=m.record_penalty(4,"severe foul",Severity::Severe);
        CHECK(p>0&&m.resolve_penalty(p,"ejected")); const auto before=fingerprint(m);
        CHECK(!m.penalties[0].pending&&m.players[4].ejected);
        CHECK(SelectAdmissionSlot(m,occupied,0)==-1&&fingerprint(m)==before);
    '''),
    ("donnybrook_exclusion_does_not_transfer_to_a_newcomer", r'''
        auto m=donnybrook(); std::array<bool,16> occupied; occupied.fill(true); occupied[4]=false;
        const int p=m.record_penalty(4,"serious foul",Severity::Serious);
        CHECK(p>0&&m.resolve_penalty(p,"excluded for Donnybrook")); const auto before=fingerprint(m);
        CHECK(m.players[4].donnybrook_excluded&&m.players[4].removed_until<0);
        CHECK(SelectAdmissionSlot(m,occupied,0)==-1&&fingerprint(m)==before);
    '''),
    ("served_ordinary_crown_remedy_reopens_slot_without_erasing_history", r'''
        Match m(legacy_crown_config()); std::array<bool,16> occupied; occupied.fill(true); occupied[4]=false;
        CHECK(m.crown_exit(1,{0,0,138},4)&&m.pause()&&m.prepare_crown_restart(1));
        CHECK(SelectAdmissionSlot(m,occupied,0)==-1);
        CHECK(m.resume()&&m.restart(1,9)); const auto before=fingerprint(m);
        CHECK(SelectAdmissionSlot(m,occupied,0)==4&&fingerprint(m)==before);
        CHECK(m.penalties[0].player==4&&m.penalties[0].crown_restoration_receiver==9);
    '''),
    ("clean_preferred_team_is_used_before_overflow_to_other_team", r'''
        Match m; std::array<bool,16> occupied{};
        for(int slot=0;slot<8;++slot) occupied[slot]=true;
        CHECK(SelectAdmissionSlot(m,occupied,0)>=8);
        occupied[3]=false; CHECK(SelectAdmissionSlot(m,occupied,0)==3);
        CHECK(SelectAdmissionSlot(m,occupied,1)>=8);
    '''),
]


def main():
    if "--list" in sys.argv:
        print(json.dumps({"status": "not_run", "planned_tests": [name for name, _ in base.CASES]}, indent=2))
        return 0
    result = base.main()
    path = base.OUTPUT / "results.json"
    if path.is_file():
        report = json.loads(path.read_text(encoding="utf-8"))
        report.pop("reference_scenarios", None)
        report["scope"] = "Native shared admission policy against real portable rule transitions"
        report["not_covered"] = ["Unreal player-controller lifecycle", "remote identity or reconnect authentication"]
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    sys.exit(main())

#pragma once
// Portable, host-authoritative regulation rules. No Unreal or exceptions.
#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace BB {
using Millis = std::int64_t;
enum class Role : int { Netminder, Chaser, Trapper, Ranger, Hurleyback, Scout };
enum class BallType : int { Quaffle, Quark, Snipe, Snitch, Bludger };
enum class Phase : int { Regulation, Overtime, Donnybrook };
enum class Status : int { Live, Paused, QuarterBreak, PhaseBreak, Review, Complete };
enum class Severity : int { Minor, Moderate, Serious, Severe, Catastrophic };
enum class Contact : int { None, Player, Hurley, Net, Floor, Goal };
enum class EventKind : int { Goal, Catch };
enum class Hoop : int { None, Large, Small };

struct Config {
    std::int64_t quaffle_points = 13, quark_points = 37, snipe_points = 69;
    std::int64_t snitch_regulation_points = 150, snitch_overtime_points = 300;
    int quarters = 4;
    Millis quarter_ms = 2640000, overtime_ms = 1320000, snitch_release_ms = 1320000;
    Millis snipe_timeout_ms = 180000, snipe_warning_ms = 10000, catch_control_ms = 1000;
    Millis hurley_warning_ms = 2000, hurley_individual_ms = 3000, hurley_team_ms = 6000;
    Millis contestable_reset_ms = 1000, crown_return_ms = 3000, removal_ms = 180000;
    Millis restart_protection_ms = 3000;
    std::int64_t regulation_margin = 150, overtime_margin = 150;
    double self_toss_reset_distance_ft = 10.0;
};
struct Player {
    int team = 0;
    Role role = Role::Netminder;
    Millis removed_until = -1;
    bool ejected = false, donnybrook_excluded = false;
};
struct Ball {
    BallType type = BallType::Quaffle;
    bool phase_active = true, live = true;
    int controller = -1;
    std::string dead_reason;
    Millis timeout_until = -1, crown_deadline = -1, protection_until = -1;
    int restart_team = -1;
    std::array<double, 3> crown_mark{{0, 0, 0}};
};
struct Hurley {
    int last_player = -1, team = -1;
    Millis individual_started = -1, team_ms = 0, flight_started = -1;
    bool contestable = false, individual_reset = false, warned = false;
};
struct PointEvent {
    EventKind kind = EventKind::Goal;
    int ball = -1, attacking_team = -1, player = -1;
    Hoop hoop = Hoop::None;
    // Evidence defaults deny a score. Only the authority may certify it.
    bool entire_ball = false, forward = false, teleported = false;
    Millis secure_ms = 0;
    bool by_hand = false, mounted = false, inside_envelope = false;
};
struct Award { int team = -1; std::int64_t points = 0; int ball = -1, player = -1; };
struct Penalty {
    int id = 0, player = -1, ball = -1;
    std::string reason, disposition;
    Severity severity = Severity::Minor;
    Millis committed_ms = 0;
    bool pending = true;
};
struct Adjustment {
    int team = -1;
    std::int64_t delta = 0;
    std::string reason;
    Millis committed_ms = 0;
};
struct Ending {
    bool active = false;
    std::string reason;
    Millis at_ms = 0;
    int catching_team = -1, catcher = -1, winning_team = -1;
    std::int64_t catch_points = 0;
};
struct LogEvent {
    std::uint64_t sequence = 0;
    Millis at_ms = 0;
    std::string kind, reason;
    int player = -1, ball = -1, team = -1, penalty_id = -1;
    std::int64_t value = 0;
};

class Match {
public:
    // Players: A 0..7, B 8..15. Within each team: N,C,C,T,R,H,H,S.
    // Balls: 0 Quaffle, 1/2 Quarks, 3 Snipe, 4 Snitch, 5/6 Bludgers.
    explicit Match(const Config& rules = Config{});
    static std::array<Player, 16> default_roster();
    bool configure_roster(const std::array<Player, 16>& roster);
    bool eligible(int player, int ball) const;
    bool possess(int player, int ball, bool inspected_hurley = false);
    bool release(int player, int ball, bool contestable = false);
    bool flight_evidence(int ball, double distance_ft = 0, Contact contact = Contact::None,
                         bool contestable = false);
    bool opponent_challenge(int ball, int player);
    // Atomic including advance, state, awards and audit log; last_error reports rejection.
    bool process_batch(Millis at_ms, const std::vector<PointEvent>& events);
    // Returns consumed live milliseconds; -1 on invalid input. Pauses consume zero.
    Millis advance(Millis delta_ms);
    bool pause(const std::string& reason = "official");
    bool resume();
    bool restart(int ball, int player);
    bool crown_exit(int ball, const std::array<double, 3>& mark, int responsible_player = -1,
                    bool deliberate_delay = false);
    bool crown_return(int ball);
    bool recall_chase(int ball);
    // Returns positive penalty id, or -1 on rejection. -1 committed_ms means now.
    int record_penalty(int player, const std::string& reason, Severity severity,
                       int ball = -1, Millis committed_ms = -1);
    bool resolve_penalty(int id, const std::string& disposition, bool apply_removal = true);
    bool certify(const std::vector<Adjustment>& adjustments = {});
    bool overturn_snitch(const std::string& reason);
    std::int64_t margin() const;
    int leader() const; // -1 when tied
    bool is_valid() const { return valid_; }

    Config config;
    std::array<Player, 16> players;
    std::array<Ball, 7> balls;
    std::array<Hurley, 2> hurleys;
    std::array<std::int64_t, 2> scores{{0, 0}};
    Phase phase = Phase::Regulation;
    Status status = Status::Live;
    int quarter = 1, winner = -1, reckoner = -1;
    Millis now_ms = 0, period_elapsed_ms = 0;
    Ending ending;
    std::vector<Penalty> penalties;
    std::vector<LogEvent> log;
    std::vector<Award> last_awards;
    std::string last_error;

private:
    bool valid_ = true;
    bool reject(const std::string& reason);
    bool available(int player) const;
    bool live_ball(int ball);
    bool carries_scoring_ball(int player) const;
    bool process_batch_impl(Millis at_ms, const std::vector<PointEvent>& events);
    void emit(const std::string& kind, int player = -1, int ball = -1, int team = -1,
              std::int64_t value = 0, const std::string& reason = "", int penalty_id = -1);
    void dead(int ball, const std::string& reason);
    void release_ball(int ball);
    void check_hurleys();
    void hurley_violation(int ball, const std::string& reason);
    void secure_balls();
    void end(const std::string& reason, int catching_team = -1, int catcher = -1,
             std::int64_t catch_points = 0, int winning_team = -1);
    void enter_phase(Phase next);
    void finish(int winning_team);
};
} // namespace BB

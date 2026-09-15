#pragma once
// portable, host-authoritative regulation rules. no unreal or exceptions.
#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace bb {
using millis = std::int64_t;
enum class role : int { netminder, chaser, trapper, ranger, hurleyback, scout };
enum class balltype : int { quaffle, quark, snipe, snitch, bludger };
enum class phase : int { regulation, overtime, donnybrook };
enum class status : int { live, paused, quarterbreak, phasebreak, review, complete };
enum class severity : int { minor, moderate, serious, severe, catastrophic };
enum class contact : int { none, player, hurley, net, floor, goal };
enum class eventkind : int { goal, catch };
enum class hoop : int { none, large, small };
enum class penaltyshotstage : int { none, ready, inflight, awaitingrestart, complete };
enum class penaltyshotoutcome : int { none, goal, miss, timeout };

struct config {
    std::int64_t quaffle_points = 13, quark_points = 37, snipe_points = 69;
    std::int64_t snitch_regulation_points = 150, snitch_overtime_points = 300;
    int quarters = 4;
    millis quarter_ms = 2640000, overtime_ms = 1320000, snitch_release_ms = 1320000;
    millis snipe_timeout_ms = 180000, snipe_warning_ms = 10000, catch_control_ms = 1000;
    millis hurley_warning_ms = 2000, hurley_individual_ms = 3000, hurley_team_ms = 6000;
    millis contestable_reset_ms = 1000, crown_return_ms = 3000, removal_ms = 180000;
    millis restart_protection_ms = 3000, penalty_shot_ms = 5000;
    std::int64_t regulation_margin = 150, overtime_margin = 150;
    double self_toss_reset_distance_ft = 10.0;
    // historical replay/test compatibility only. current venues have a closed top net.
    bool enable_legacy_crown_exit = false;
};
struct player {
    int team = 0;
    role role = Role::Netminder;
    millis removed_until = -1;
    bool ejected = false, donnybrook_excluded = false;
};
struct ball {
    balltype type = BallType::Quaffle;
    bool phase_active = true, live = true;
    int controller = -1;
    std::string dead_reason;
    millis timeout_until = -1, crown_deadline = -1, protection_until = -1;
    int restart_team = -1;
    int crown_restart_penalty = -1;
    int conduct_restart_penalty = -1;
    std::array<double, 3> crown_mark{{0, 0, 0}};
};
struct hurley {
    int last_player = -1, team = -1;
    millis individual_started = -1, team_ms = 0, flight_started = -1;
    bool contestable = false, individual_reset = false, warned = false;
};
struct pointevent {
    eventkind kind = EventKind::Goal;
    int ball = -1, attacking_team = -1, player = -1;
    hoop hoop = Hoop::None;
    // evidence defaults deny a score. only the authority may certify it.
    bool entire_ball = false, forward = false, teleported = false;
    millis secure_ms = 0;
    bool by_hand = false, mounted = false, inside_envelope = false;
};
struct award { int team = -1; std::int64_t points = 0; int ball = -1, player = -1; };
struct penaltyshot {
    bool free_shot = false; // Moderate: restorative shot, no temporary removal.
    bool post_termination = false; // keep the provisional ending until certification.
    penaltyshotstage stage = PenaltyShotStage::None;
    penaltyshotoutcome outcome = PenaltyShotOutcome::None;
    int penalty_id = -1, ball = -1, shooter = -1, netminder = -1, attacking_team = -1;
    millis elapsed_ms = 0, released_ms = -1;
    std::int64_t awarded_points = 0;
};
struct penalty {
    int id = 0, player = -1, ball = -1;
    std::string reason, disposition;
    severity severity = Severity::Minor;
    millis committed_ms = 0;
    bool pending = true;
    bool crown_restoration_pending = false;
    bool penalty_shot_reserved = false;
    int crown_restoration_receiver = -1;
    std::array<double, 3> crown_mark{{0, 0, 0}};
};
struct adjustment {
    int team = -1;
    std::int64_t delta = 0;
    std::string reason;
    millis committed_ms = 0;
};
struct ending {
    bool active = false;
    std::string reason;
    millis at_ms = 0;
    int catching_team = -1, catcher = -1, winning_team = -1;
    std::int64_t catch_points = 0;
};
struct logevent {
    std::uint64_t sequence = 0;
    millis at_ms = 0;
    std::string kind, reason;
    int player = -1, ball = -1, team = -1, penalty_id = -1;
    std::int64_t value = 0;
};

class match {
public:
    // Players: a 0..7, b 8..15. within each team: N,C,C,T,R,H,H,S.
    // Balls: 0 quaffle, 1/2 quarks, 3 snipe, 4 snitch, 5/6 Bludgers.
    explicit match(const config& rules = config{});
    static std::array<Player, 16> default_roster();
    bool configure_roster(const std::array<Player, 16>& roster);
    bool eligible(int player, int ball) const;
    bool possess(int player, int ball, bool inspected_hurley = false);
    bool release(int player, int ball, bool contestable = false);
    bool flight_evidence(int ball, double distance_ft = 0, contact contact = Contact::None,
                         bool contestable = false);
    bool opponent_challenge(int ball, int player);
    // atomic including advance, state, awards and audit log; last_error reports rejection.
    bool process_batch(millis at_ms, const std::vector<PointEvent>& events);
    // returns consumed live milliseconds; -1 on invalid input. pauses consume zero.
    millis advance(millis delta_ms);
    bool pause(const std::string& reason = "official");
    bool resume();
    bool restart(int ball, int player);
    bool crown_exit(int ball, const std::array<double, 3>& mark, int responsible_player = -1,
                    bool deliberate_delay = false);
    bool crown_return(int ball);
    // records ordinary no crown administration at a stoppage. the ball stays
    // dead for an eligible opposing restart after resume; later same-ball
    // remedies remain queued for the following stoppage.
    bool prepare_crown_restart(int penalty_id);
    // queue a moderate scoring-ball possession remedy at a stoppage. the
    // penalty remains pending until an eligible opponent takes restart().
    bool queue_conduct_possession_award(int penalty_id, int ball, int team);
    // serious shot administration uses a separate stopped-time attempt clock.
    // native callers supply physical goal/save/miss evidence; these methods
    // never infer points from a disposition string. five seconds includes flight.
    // pre-termination remedies can run during Snitch/horn/OT-margin review;
    // the original ending and live timestamp stay frozen until certification.
    // donnybrook terminal conflicts or an unavailable defending netminder
    // need external adjudication and are rejected without changing state.
    bool start_penalty_shot(int penalty_id, int ball, int shooter, int netminder, bool free_shot = false);
    bool release_penalty_shot(int shooter);
    millis advance_penalty_shot(millis delta_ms);
    bool complete_penalty_shot(penaltyshotoutcome outcome, const pointevent& goal = pointevent{});
    // actual protected defending custody resolves the pending penalty. a made
    // Donnybrook/OT-ending shot enters review only after this restart. existing
    // terminal review keeps its original ending for the later certify() retest.
    bool restart_penalty_shot(int netminder);
    bool penalty_shot_active() const;
    bool recall_chase(int ball);
    // returns positive penalty id, or -1 on rejection. -1 committed_ms means now.
    int record_penalty(int player, const std::string& reason, severity severity,
                       int ball = -1, millis committed_ms = -1);
    // compatibility for explicit external official adjudication of unreserved
    // penalties. native serious play must reserve and serve the shot lifecycle;
    // a reserved shot cannot be cleared by a disposition string.
    bool resolve_penalty(int id, const std::string& disposition, bool apply_removal = true);
    bool certify(const std::vector<Adjustment>& adjustments = {});
    bool overturn_snitch(const std::string& reason);
    std::int64_t margin() const;
    int leader() const; // -1 when tied
    bool is_valid() const { return valid_; }

    config config;
    std::array<Player, 16> players;
    std::array<Ball, 7> balls;
    std::array<Hurley, 2> hurleys;
    std::array<std::int64_t, 2> scores{{0, 0}};
    phase phase = Phase::Regulation;
    status status = Status::Live;
    int quarter = 1, winner = -1, reckoner = -1;
    millis now_ms = 0, period_elapsed_ms = 0;
    ending ending;
    penaltyshot penalty_shot;
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
    bool valid_shot_stoppage() const;
    bool valid_penalty_shot() const;
    bool valid_conduct_award(const penalty& penalty, int* award_ball = nullptr) const;
    bool process_batch_impl(millis at_ms, const std::vector<PointEvent>& events);
    void emit(const std::string& kind, int player = -1, int ball = -1, int team = -1,
              std::int64_t value = 0, const std::string& reason = "", int penalty_id = -1);
    void dead(int ball, const std::string& reason);
    void release_ball(int ball);
    void check_hurleys();
    void hurley_violation(int ball, const std::string& reason);
    void secure_balls();
    void end(const std::string& reason, int catching_team = -1, int catcher = -1,
             std::int64_t catch_points = 0, int winning_team = -1);
    void enter_phase(phase next);
    void finish(int winning_team);
};
} // namespace bb

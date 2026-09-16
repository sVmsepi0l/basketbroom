#include "BBRuleEngine.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <utility>

namespace BB {
namespace {
bool player_index(int value) { return value >= 0 && value < 16; }
bool ball_index(int value) { return value >= 0 && value < 7; }
bool team_index(int value) { return value == 0 || value == 1; }
bool scoring(BallType type) { return type == BallType::Quaffle || type == BallType::Quark; }
bool chase(BallType type) { return type == BallType::Snipe || type == BallType::Snitch; }
bool sum_valid(std::int64_t a, std::int64_t b) {
    return (b >= 0 && a <= std::numeric_limits<std::int64_t>::max() - b) ||
           (b < 0 && a >= std::numeric_limits<std::int64_t>::min() - b);
}
}

std::array<Player, 16> Match::default_roster() {
    std::array<Player, 16> result{};
    const Role roles[] = {Role::Netminder, Role::Chaser, Role::Chaser, Role::Trapper,
                          Role::Ranger, Role::Hurleyback, Role::Hurleyback, Role::Scout};
    for (int i = 0; i < 16; ++i) { result[i].team = i / 8; result[i].role = roles[i % 8]; }
    return result;
}

Match::Match(const Config& rules) : config(rules), players(default_roster()) {
    const BallType types[] = {BallType::Quaffle, BallType::Quark, BallType::Quark,
                             BallType::Snipe, BallType::Snitch, BallType::Bludger, BallType::Bludger};
    for (int i = 0; i < 7; ++i) balls[i].type = types[i];
    const Millis positive[] = {config.quarter_ms, config.overtime_ms, config.snitch_release_ms,
        config.snipe_timeout_ms, config.catch_control_ms, config.hurley_warning_ms,
        config.hurley_individual_ms, config.hurley_team_ms, config.contestable_reset_ms,
        config.crown_return_ms, config.removal_ms, config.restart_protection_ms, config.penalty_shot_ms};
    for (Millis v : positive) if (v <= 0) valid_ = false;
    const std::int64_t nonnegative[] = {config.quaffle_points, config.quark_points,
        config.snipe_points, config.snitch_regulation_points, config.snitch_overtime_points,
        config.regulation_margin, config.overtime_margin, config.snipe_warning_ms};
    for (auto v : nonnegative) if (v < 0) valid_ = false;
    if (config.quarters <= 0 || config.snipe_warning_ms > config.snipe_timeout_ms ||
        config.hurley_warning_ms >= config.hurley_individual_ms ||
        !std::isfinite(config.self_toss_reset_distance_ft) || config.self_toss_reset_distance_ft < 0)
        valid_ = false;
    dead(4, "scheduled_release");
    emit("opening_horn", -1, -1, -1, 1);
    if (!valid_) { status = Status::Paused; last_error = "invalid rules configuration"; }
}

bool Match::reject(const std::string& reason) { last_error = reason; return false; }
void Match::emit(const std::string& kind, int player, int ball, int team,
                 std::int64_t value, const std::string& reason, int penalty_id) {
    log.push_back({static_cast<std::uint64_t>(log.size() + 1), now_ms, kind, reason,
                   player, ball, team, penalty_id, value});
}
bool Match::configure_roster(const std::array<Player, 16>& roster) {
    if (!valid_ || now_ms != 0 || status != Status::Live || !penalties.empty() ||
        scores[0] != 0 || scores[1] != 0 || log.size() != 1)
        return reject("roster can only be configured before play");
    std::array<std::array<int, 6>, 2> counts{};
    for (const auto& p : roster) {
        int role = static_cast<int>(p.role);
        if (!team_index(p.team) || role < 0 || role >= 6) return reject("unknown team or position");
        ++counts[p.team][role];
    }
    const std::array<int, 6> required{{1, 2, 1, 1, 2, 1}};
    if (counts[0] != required || counts[1] != required)
        return reject("each team must field the configured eight positions");
    players = roster;
    for (auto& p : players) { p.removed_until = -1; p.ejected = p.donnybrook_excluded = false; }
    last_error.clear(); return true;
}
bool Match::available(int player) const {
    return player_index(player) && !players[player].ejected &&
           !players[player].donnybrook_excluded && players[player].removed_until < 0;
}
bool Match::live_ball(int ball) {
    if (!valid_) return reject("invalid rules configuration");
    if (!ball_index(ball)) return reject("unknown ball");
    if (penalty_shot_active()) return reject("ordinary ball play is suspended during a penalty shot");
    if (status != Status::Live || !balls[ball].phase_active || !balls[ball].live)
        return reject("ball is not live");
    return true;
}
bool Match::carries_scoring_ball(int player) const {
    for (const auto& b : balls) if (scoring(b.type) && b.controller == player) return true;
    return false;
}
bool Match::eligible(int player, int ball) const {
    if (!valid_ || !available(player) || !ball_index(ball) || !balls[ball].phase_active) return false;
    const auto type = balls[ball].type;
    const auto role = players[player].role;
    if (phase == Phase::Donnybrook) return type == BallType::Quark || type == BallType::Snipe;
    if (scoring(type)) return role == Role::Netminder || role == Role::Chaser ||
                              role == Role::Trapper || role == Role::Ranger;
    if (chase(type)) return role == Role::Ranger || role == Role::Scout;
    return role == Role::Hurleyback;
}
void Match::dead(int ball, const std::string& reason) {
    auto& b = balls[ball]; b.live = false; b.controller = -1;
    b.dead_reason = reason; b.protection_until = -1;
}
void Match::release_ball(int ball) {
    auto& b = balls[ball]; b.live = true; b.controller = -1; b.dead_reason.clear();
    b.timeout_until = b.crown_deadline = b.protection_until = -1;
}
bool Match::possess(int player, int ball, bool inspected_hurley) {
    if (!live_ball(ball)) return false;
    if (!available(player)) return reject("player is unavailable");
    if (!eligible(player, ball)) return reject("Unauthorized Ball Play");
    auto& b = balls[ball]; const auto& p = players[player];
    if (b.controller >= 0) return reject("release or verified turnover required before possession");
    if (scoring(b.type)) {
        if (carries_scoring_ball(player)) return reject("Multi-Ball Hoarding");
        if (b.protection_until >= 0 && now_ms < b.protection_until && p.team != b.restart_team)
            return reject("protected restart");
    } else if (b.type == BallType::Bludger) {
        if (!inspected_hurley) return reject("Bludgers require inspected Hurleys");
        if (!sum_valid(now_ms, config.hurley_individual_ms) || !sum_valid(now_ms, config.hurley_team_ms))
            return reject("clock overflow");
        for (const auto& other : balls)
            if (other.type == BallType::Bludger && other.controller == player)
                return reject("one Bludger per Hurleyback");
        auto& h = hurleys[ball - 5];
        if (h.team != p.team) { h.team = p.team; h.team_ms = 0; }
        if (h.last_player != player || h.individual_reset || h.individual_started < 0) {
            h.individual_started = now_ms; h.warned = false;
        }
        h.last_player = player; h.flight_started = -1; h.contestable = h.individual_reset = false;
    } else return reject("chase balls resolve through capture events");
    b.controller = player; emit("possession", player, ball); check_hurleys();
    last_error.clear(); return true;
}
bool Match::release(int player, int ball, bool contestable) {
    if (!live_ball(ball)) return false;
    auto& b = balls[ball];
    if (!player_index(player) || b.controller != player) return reject("player does not control this ball");
    if (b.type == BallType::Bludger && contestable && !sum_valid(now_ms, config.contestable_reset_ms))
        return reject("clock overflow");
    b.controller = -1; b.protection_until = -1;
    if (b.type == BallType::Bludger) {
        auto& h = hurleys[ball - 5]; h.flight_started = now_ms; h.contestable = contestable;
    }
    emit("release", player, ball, -1, contestable ? 1 : 0); last_error.clear(); return true;
}
bool Match::flight_evidence(int ball, double distance_ft, Contact contact, bool contestable) {
    if (!live_ball(ball)) return false;
    auto& b = balls[ball];
    if (b.type != BallType::Bludger || b.controller >= 0)
        return reject("flight evidence requires a free Bludger");
    if (!std::isfinite(distance_ft) || distance_ft < 0 || static_cast<int>(contact) < 0 ||
        static_cast<int>(contact) > static_cast<int>(Contact::Goal)) return reject("invalid flight evidence");
    auto& h = hurleys[ball - 5];
    if (contestable && !h.contestable && !sum_valid(now_ms, config.contestable_reset_ms))
        return reject("clock overflow");
    if (contestable && !h.contestable) { h.contestable = true; h.flight_started = now_ms; }
    h.individual_reset = h.individual_reset || distance_ft >= config.self_toss_reset_distance_ft ||
        contact == Contact::Player || contact == Contact::Hurley ||
        (contestable && (contact == Contact::Net || contact == Contact::Floor || contact == Contact::Goal));
    emit("flight_evidence", -1, ball); last_error.clear(); return true;
}
bool Match::opponent_challenge(int ball, int player) {
    if (!live_ball(ball)) return false;
    if (!available(player)) return reject("player is unavailable");
    if (balls[ball].type != BallType::Bludger || players[player].role != Role::Hurleyback)
        return reject("challenge requires a Hurleyback and Bludger");
    auto& h = hurleys[ball - 5];
    if (h.team == players[player].team) return reject("teammate challenge does not reset team control");
    h.team_ms = 0; emit("opponent_challenge", player, ball); last_error.clear(); return true;
}
void Match::hurley_violation(int ball, const std::string& reason) {
    const int player = balls[ball].controller;
    record_penalty(player, reason, Severity::Minor, ball);
    balls[ball].restart_team = 1 - players[player].team;
    dead(ball, "hurley_foul"); hurleys[ball - 5] = Hurley{};
}
void Match::check_hurleys() {
    for (int i = 0; i < 2; ++i) {
        auto& h = hurleys[i]; const int ball = i + 5;
        if (balls[ball].controller < 0) continue;
        Millis individual = now_ms - h.individual_started;
        if (individual >= config.hurley_individual_ms)
            hurley_violation(ball, "Illegal Prolonged Bludger Control");
        else if (h.team_ms >= config.hurley_team_ms) hurley_violation(ball, "Team Relay Hoarding");
        else if (individual >= config.hurley_warning_ms && !h.warned) {
            h.warned = true; emit("hurley_warning", balls[ball].controller, ball);
        }
    }
}
std::int64_t Match::margin() const { return scores[0] > scores[1] ? scores[0] - scores[1] : scores[1] - scores[0]; }
int Match::leader() const { return scores[0] == scores[1] ? -1 : (scores[0] > scores[1] ? 0 : 1); }

bool Match::process_batch(Millis at_ms, const std::vector<PointEvent>& events) {
    Match backup = *this;
    if (process_batch_impl(at_ms, events)) { last_error.clear(); return true; }
    const auto error = last_error; *this = std::move(backup); last_error = error; return false;
}
bool Match::process_batch_impl(Millis at_ms, const std::vector<PointEvent>& events) {
    if (penalty_shot_active()) return reject("penalty-shot evidence requires the reserved shot API");
    if (at_ms < 0 || at_ms < now_ms) return reject("events may not run backwards");
    if (advance(at_ms - now_ms) < 0) return false;
    if (status != Status::Live || now_ms != at_ms) return reject("event completed after a stoppage or horn");
    std::array<bool, 7> seen{};
    std::vector<Award> awards;
    int snitch_team = -1, snitch_player = -1; std::int64_t snitch_points = 0;
    for (const auto& e : events) {
        if (!ball_index(e.ball)) return reject("unknown ball");
        if (seen[e.ball]) return reject("one ball cannot complete two point events at one timestamp");
        seen[e.ball] = true;
        if (!live_ball(e.ball)) return false;
        const auto type = balls[e.ball].type;
        if (e.kind == EventKind::Goal) {
            if (!team_index(e.attacking_team)) return reject("unknown team");
            const Hoop expected = type == BallType::Quaffle ? Hoop::Large :
                                  (type == BallType::Quark ? Hoop::Small : Hoop::None);
            if (expected == Hoop::None || e.hoop != expected || !e.entire_ball || !e.forward || e.teleported) {
                emit("no_goal", -1, e.ball); continue;
            }
            awards.push_back({e.attacking_team, type == BallType::Quaffle ? config.quaffle_points : config.quark_points, e.ball, -1});
        } else if (e.kind == EventKind::Catch) {
            if (!available(e.player)) return reject("player is unavailable");
            if (!chase(type) || !eligible(e.player, e.ball)) return reject("ineligible chase catch");
            if (e.secure_ms < 0 || carries_scoring_ball(e.player) || e.secure_ms < config.catch_control_ms)
                return reject("capture requires one second and no carried scoring ball");
            if (!e.by_hand || !e.mounted || !e.inside_envelope) return reject("capture evidence failed");
            for (const auto& award : awards) if (award.player == e.player)
                return reject("one player cannot complete both chase catches simultaneously");
            auto points = type == BallType::Snipe ? config.snipe_points :
                (phase == Phase::Regulation ? config.snitch_regulation_points : config.snitch_overtime_points);
            awards.push_back({players[e.player].team, points, e.ball, e.player});
            if (type == BallType::Snitch) { snitch_team = players[e.player].team; snitch_player = e.player; snitch_points = points; }
        } else return reject("unknown point event");
    }
    last_awards.clear();
    if (phase == Phase::Donnybrook && !awards.empty()) {
        bool both_teams = false;
        for (const auto& a : awards) both_teams |= a.team != awards[0].team;
        if (both_teams) {
            for (int ball : {1, 2, 3}) release_ball(ball);
            emit("donnybrook_simultaneous_void"); return true;
        }
    }
    for (const auto& a : awards) {
        if (!sum_valid(scores[a.team], a.points)) return reject("score overflow");
        if (a.ball == 3 && !sum_valid(now_ms, config.snipe_timeout_ms)) return reject("clock overflow");
        scores[a.team] += a.points; emit("points", a.player, a.ball, a.team, a.points);
        dead(a.ball, a.ball == 3 ? "timeout" : "score");
        if (a.ball == 3) balls[a.ball].timeout_until = now_ms + config.snipe_timeout_ms;
        else if (scoring(balls[a.ball].type)) balls[a.ball].restart_team = 1 - a.team;
    }
    last_awards = awards;
    if (snitch_team >= 0) end("snitch", snitch_team, snitch_player, snitch_points);
    else if (phase == Phase::Donnybrook && !awards.empty()) end("donnybrook", -1, -1, 0, awards[0].team);
    else if (phase == Phase::Overtime && !awards.empty() && margin() >= config.overtime_margin)
        end("overtime_margin");
    return true;
}
void Match::secure_balls() {
    for (int i = 0; i < 7; ++i) if (balls[i].live) dead(i, "stoppage");
    hurleys = {};
}
void Match::end(const std::string& reason, int catching_team, int catcher,
                std::int64_t catch_points, int winning_team) {
    ending = {true, reason, now_ms, catching_team, catcher, winning_team, catch_points};
    status = Status::Review; secure_balls(); emit("provisional_end", catcher, -1, catching_team, catch_points, reason);
}
Millis Match::advance(Millis delta_ms) {
    if (!valid_) { reject("invalid rules configuration"); return -1; }
    if (delta_ms < 0 || !sum_valid(now_ms, delta_ms)) { reject("invalid live-time increment"); return -1; }
    if (penalty_shot_active()) {
        if (!valid_penalty_shot()) { reject("invalid reserved penalty shot"); return -1; }
        last_error.clear(); return 0;
    }
    const Millis start = now_ms, target = now_ms + delta_ms;
    while (status == Status::Live && now_ms < target) {
        Millis next = target;
        auto deadline = [&](Millis when) { if (when > now_ms && when < next) next = when; };
        auto after = [&](Millis duration) {
            if (duration > 0 && sum_valid(now_ms, duration)) deadline(now_ms + duration);
        };
        const Millis duration = phase == Phase::Regulation ? config.quarter_ms : config.overtime_ms;
        if (phase != Phase::Donnybrook) after(duration - period_elapsed_ms);
        if (phase == Phase::Regulation && balls[4].dead_reason == "scheduled_release") deadline(config.snitch_release_ms);
        for (const auto& b : balls) {
            deadline(b.timeout_until); deadline(b.crown_deadline);
            if (b.timeout_until >= 0) deadline(b.timeout_until - config.snipe_warning_ms);
        }
        for (const auto& p : players) deadline(p.removed_until);
        for (int i = 0; i < 2; ++i) {
            const auto& h = hurleys[i];
            if (balls[i + 5].controller >= 0) {
                deadline(h.individual_started + config.hurley_individual_ms);
                if (!h.warned) deadline(h.individual_started + config.hurley_warning_ms);
                after(config.hurley_team_ms - h.team_ms);
            } else if (h.contestable && h.flight_started >= 0)
                deadline(h.flight_started + config.contestable_reset_ms);
        }
        const Millis step = next - now_ms;
        for (int i = 0; i < 2; ++i) if (balls[i + 5].controller >= 0) hurleys[i].team_ms += step;
        now_ms = next; period_elapsed_ms += step;
        bool crown_returns = false;
        for (int i = 0; i < 7; ++i) {
            auto& b = balls[i];
            if (b.timeout_until >= 0) {
                if (now_ms >= b.timeout_until) { release_ball(i); emit("snipe_release", -1, i); }
                else if (now_ms == b.timeout_until - config.snipe_warning_ms)
                    emit("snipe_warning", -1, i, -1, config.snipe_warning_ms);
            }
            if (b.crown_deadline >= 0 && now_ms >= b.crown_deadline) {
                release_ball(i); crown_returns = true; emit("crown_safety_return", -1, i);
            }
        }
        if (crown_returns) pause("crown_safety");
        for (int i = 0; i < 16; ++i) {
            if (players[i].removed_until >= 0 && now_ms >= players[i].removed_until) {
                players[i].removed_until = -1; emit("removal_expired", i);
            }
        }
        for (int i = 0; i < 2; ++i) {
            auto& h = hurleys[i];
            if (h.contestable && h.flight_started >= 0 && now_ms - h.flight_started >= config.contestable_reset_ms) {
                h.team = -1; h.team_ms = 0; h.flight_started = -1; h.contestable = false; h.individual_reset = true;
                emit("hurley_flight_reset", -1, i + 5);
            }
        }
        check_hurleys();
        if (phase == Phase::Regulation && balls[4].dead_reason == "scheduled_release" && now_ms >= config.snitch_release_ms) {
            release_ball(4); emit("snitch_release");
        }
        if (phase != Phase::Donnybrook && period_elapsed_ms >= duration) {
            if (phase == Phase::Regulation && quarter < config.quarters) {
                status = Status::QuarterBreak; emit("quarter_horn", -1, -1, -1, quarter); secure_balls();
            } else end(phase == Phase::Regulation ? "regulation_horn" : "overtime_horn");
        }
    }
    last_error.clear(); return now_ms - start;
}
bool Match::pause(const std::string& reason) {
    if (!valid_ || status != Status::Live) return reject("only live play may pause");
    status = Status::Paused; secure_balls(); emit("stoppage", -1, -1, -1, 0, reason);
    last_error.clear(); return true;
}
bool Match::resume() {
    if (penalty_shot_active()) return reject("serve the reserved penalty shot and defending restart before resume");
    if (!valid_ || (status != Status::Paused && status != Status::QuarterBreak && status != Status::PhaseBreak))
        return reject("there is no resumable stoppage");
    for (const auto& ball : balls) if (ball.conduct_restart_penalty >= 0) {
        const int id = ball.conduct_restart_penalty;
        if (id == 0 || id > static_cast<int>(penalties.size()) || !valid_conduct_award(penalties[id - 1]))
            return reject("invalid queued conduct possession award");
    }
    for (const auto& p : penalties) if (p.penalty_shot_reserved || (p.pending && !valid_conduct_award(p)))
        return reject("administer pending penalties before the next horn");
    if (status == Status::QuarterBreak) { ++quarter; period_elapsed_ms = 0; }
    status = Status::Live;
    for (int i = 0; i < 7; ++i) if (balls[i].phase_active && balls[i].dead_reason == "stoppage") release_ball(i);
    emit("resume", -1, -1, -1, quarter); last_error.clear(); return true;
}
bool Match::restart(int ball, int player) {
    if (penalty_shot_active()) return reject("use the reserved penalty-shot restart");
    if (!valid_ || !ball_index(ball)) return reject("unknown ball");
    if (!available(player)) return reject("player is unavailable");
    auto& b = balls[ball]; const auto& p = players[player];
    if (status != Status::Live || !b.phase_active ||
        (b.dead_reason != "score" && b.dead_reason != "hurley_foul" && b.dead_reason != "penalty" && b.dead_reason != "crown_restart"))
        return reject("ball is not awaiting a possession restart");
    if (p.team != b.restart_team || !eligible(player, ball)) return reject("invalid restart receiver");
    if (b.dead_reason == "score" && phase != Phase::Donnybrook && p.role != Role::Netminder)
        return reject("scoring-ball restart belongs to defending Netminder");
    if (scoring(b.type) && carries_scoring_ball(player)) return reject("restart receiver must first release the carried ball");
    if (scoring(b.type) && !sum_valid(now_ms, config.restart_protection_ms)) return reject("clock overflow");
    const int conduct_penalty = b.conduct_restart_penalty;
    if (conduct_penalty >= 0) {
        int reserved_ball = -1;
        if (conduct_penalty == 0 || conduct_penalty > static_cast<int>(penalties.size()) ||
            !valid_conduct_award(penalties[conduct_penalty - 1], &reserved_ball) || reserved_ball != ball)
            return reject("invalid queued conduct possession award");
    }
    const int crown_penalty = b.crown_restart_penalty;
    release_ball(ball);
    if (scoring(b.type)) { possess(player, ball); b.protection_until = now_ms + config.restart_protection_ms; }
    if (crown_penalty > 0 && crown_penalty <= static_cast<int>(penalties.size())) {
        auto& penalty = penalties[crown_penalty - 1];
        penalty.crown_restoration_pending = false;
        penalty.crown_restoration_receiver = player;
        penalty.disposition = "ordinary No Crown restorative restart served";
        emit("crown_restoration_served", player, ball, p.team, 0, "", crown_penalty);
    }
    b.crown_restart_penalty = -1;
    if (conduct_penalty > 0) {
        auto& penalty = penalties[conduct_penalty - 1];
        penalty.pending = false;
        penalty.disposition = "conduct possession award served by protected restart";
        b.conduct_restart_penalty = -1;
        emit("conduct_possession_award_served", player, ball, p.team, 0, penalty.disposition, conduct_penalty);
        emit("penalty_resolved", penalty.player, penalty.ball, p.team, 0, penalty.disposition, conduct_penalty);
    }
    emit("protected_restart", player, ball); last_error.clear(); return true;
}
bool Match::crown_exit(int ball, const std::array<double, 3>& mark, int responsible_player, bool deliberate_delay) {
    if (!config.enable_legacy_crown_exit) return reject("closed pyramid net: roof contact rebounds, never a Crown exit");
    if (!live_ball(ball)) return false;
    if (chase(balls[ball].type)) return reject("winged balls use chase-envelope recall, not No Crown");
    for (double v : mark) if (!std::isfinite(v)) return reject("Crown Mark must contain finite coordinates in feet");
    if (responsible_player != -1 && !available(responsible_player)) return reject("player is unavailable");
    if (!sum_valid(now_ms, config.crown_return_ms)) return reject("clock overflow");
    dead(ball, "crown"); balls[ball].crown_mark = mark; balls[ball].crown_deadline = now_ms + config.crown_return_ms;
    if (balls[ball].type == BallType::Bludger) hurleys[ball - 5] = Hurley{};
    if (responsible_player >= 0) {
        const int id = record_penalty(responsible_player, deliberate_delay ? "Dead-Roof Delay" : "No Crown",
                                      deliberate_delay ? Severity::Moderate : Severity::Minor, ball);
        if (id > 0 && !deliberate_delay) {
            penalties[id - 1].crown_restoration_pending = true;
            penalties[id - 1].crown_mark = mark;
        }
    }
    emit("crown_exit", responsible_player, ball); last_error.clear(); return true;
}
bool Match::crown_return(int ball) {
    if (!valid_ || !ball_index(ball)) return reject("unknown ball");
    if (status != Status::Live || balls[ball].dead_reason != "crown") return reject("ball is not awaiting neutral crown return");
    release_ball(ball); emit("crown_return", -1, ball); last_error.clear(); return true;
}
bool Match::prepare_crown_restart(int penalty_id) {
    if (!valid_ || status == Status::Live || status == Status::Complete || penalty_id <= 0 ||
        penalty_id > static_cast<int>(penalties.size())) return reject("ordinary Crown administration requires a stoppage");
    auto& penalty = penalties[penalty_id - 1];
    if (penalty.reason != "No Crown" || penalty.severity != Severity::Minor ||
        !penalty.crown_restoration_pending || !ball_index(penalty.ball))
        return reject("penalty has no outstanding ordinary Crown restoration");
    auto& ball = balls[penalty.ball];
    if (!ball.phase_active) return reject("removed ball cannot receive a Crown restart");
    if (penalty_shot_active() && penalty.ball == penalty_shot.ball)
        return reject("ball already belongs to a reserved penalty shot");
    if (ball.conduct_restart_penalty >= 0) return reject("ball already has a conduct possession award");
    if (ball.crown_restart_penalty == penalty_id) return reject("Crown restart is already reserved");
    // One physical ball cannot serve two opposing possession awards at once.
    // Keep later infringements recorded and due until a following stoppage.
    const bool first_administration = penalty.pending;
    penalty.pending = false;
    penalty.disposition = "ordinary No Crown recorded; restorative restart queued";
    const bool earlier_due = std::any_of(penalties.begin(), penalties.end(), [&](const Penalty& earlier) {
        return earlier.id < penalty.id && earlier.ball == penalty.ball && earlier.crown_restoration_pending;
    });
    if (ball.crown_restart_penalty < 0 && !earlier_due) {
        dead(penalty.ball, "crown_restart");
        ball.crown_deadline = -1;
        ball.crown_mark = penalty.crown_mark;
        ball.crown_restart_penalty = penalty.id;
        ball.restart_team = 1 - players[penalty.player].team;
        if (ball.type == BallType::Bludger) hurleys[penalty.ball - 5] = Hurley{};
        emit("crown_restoration_reserved", penalty.player, penalty.ball, ball.restart_team, 0, "", penalty.id);
    }
    if (first_administration) emit("penalty_resolved", penalty.player, penalty.ball, -1, 0, penalty.disposition, penalty.id);
    last_error.clear(); return true;
}
bool Match::valid_conduct_award(const Penalty& penalty, int* award_ball) const {
    if (!penalty.pending || penalty.severity != Severity::Moderate ||
        penalty.id <= 0 || penalty.id > static_cast<int>(penalties.size()) ||
        penalties[penalty.id - 1].id != penalty.id || !player_index(penalty.player) ||
        !team_index(players[penalty.player].team) || penalty.crown_restoration_pending ||
        penalty.disposition != "conduct possession award queued") return false;
    int found = -1;
    for (int i = 0; i < 7; ++i) {
        const auto& ball = balls[i];
        if (ball.conduct_restart_penalty != penalty.id) continue;
        if (found >= 0 || i > 2 || !scoring(ball.type) || !ball.phase_active || ball.live ||
            ball.dead_reason != "penalty" || ball.restart_team != 1 - players[penalty.player].team ||
            ball.crown_restart_penalty >= 0 || ball.crown_deadline >= 0 || ball.timeout_until >= 0 ||
            ball.controller >= 0) return false;
        for (const auto& other : penalties)
            if (other.ball == i && other.crown_restoration_pending) return false;
        found = i;
    }
    if (found < 0) return false;
    if (award_ball) *award_ball = found;
    return true;
}
bool Match::queue_conduct_possession_award(int penalty_id, int ball, int team) {
    if (!valid_ || status == Status::Live || status == Status::Complete ||
        penalty_id <= 0 || penalty_id > static_cast<int>(penalties.size()) ||
        ball < 0 || ball > 2 || !team_index(team))
        return reject("conduct possession award requires a valid stoppage, penalty, scoring ball and team");
    auto& penalty = penalties[penalty_id - 1];
    if (penalty.id != penalty_id || !penalty.pending || penalty.severity != Severity::Moderate ||
        !player_index(penalty.player) || !team_index(players[penalty.player].team) ||
        team != 1 - players[penalty.player].team || penalty.crown_restoration_pending || penalty.penalty_shot_reserved)
        return reject("only a pending Moderate penalty may award possession to the offender's opponents");
    auto& selected = balls[ball];
    if (!selected.phase_active || !scoring(selected.type) || selected.live ||
        selected.dead_reason != "stoppage" || selected.crown_restart_penalty >= 0 ||
        selected.conduct_restart_penalty >= 0 || selected.crown_deadline >= 0 || selected.timeout_until >= 0)
        return reject("the scoring ball must have no existing dead-ball remedy");
    for (const auto& other : balls) if (other.conduct_restart_penalty == penalty_id)
        return reject("the conduct possession award is already queued");
    for (const auto& other : penalties) if (other.ball == ball && other.crown_restoration_pending)
        return reject("an outstanding Crown remedy already owns this ball");
    dead(ball, "penalty");
    selected.restart_team = team;
    selected.conduct_restart_penalty = penalty_id;
    penalty.disposition = "conduct possession award queued";
    emit("conduct_possession_award_queued", penalty.player, ball, team, 0, penalty.disposition, penalty_id);
    last_error.clear(); return true;
}
bool Match::penalty_shot_active() const {
    return penalty_shot.stage != PenaltyShotStage::None && penalty_shot.stage != PenaltyShotStage::Complete;
}
bool Match::valid_shot_stoppage() const {
    if (status == Status::Paused || status == Status::QuarterBreak || status == Status::PhaseBreak)
        return !ending.active;
    if (status != Status::Review || !ending.active || ending.at_ms != now_ms || now_ms < 0)
        return false;
    // Bible 5.7 specifies retesting these four ending rules after restitution.
    // It does not settle conflicting Donnybrook winners after a terminal foul.
    if (ending.reason == "snitch") return phase == Phase::Regulation || phase == Phase::Overtime;
    if (ending.reason == "regulation_horn") return phase == Phase::Regulation;
    return phase == Phase::Overtime &&
        (ending.reason == "overtime_margin" || ending.reason == "overtime_horn");
}
bool Match::valid_penalty_shot() const {
    const auto& shot = penalty_shot;
    if (!valid_ || !penalty_shot_active() ||
        (shot.stage != PenaltyShotStage::Ready && shot.stage != PenaltyShotStage::InFlight &&
         shot.stage != PenaltyShotStage::AwaitingRestart) ||
        !valid_shot_stoppage() || shot.post_termination != (status == Status::Review) ||
        shot.penalty_id <= 0 || shot.penalty_id > static_cast<int>(penalties.size()) ||
        !ball_index(shot.ball) || !team_index(shot.attacking_team) ||
        !eligible(shot.shooter, shot.ball) || !eligible(shot.netminder, shot.ball) ||
        players[shot.shooter].team != shot.attacking_team ||
        players[shot.netminder].team != 1 - shot.attacking_team ||
        (phase != Phase::Donnybrook && players[shot.netminder].role != Role::Netminder) ||
        shot.elapsed_ms < 0 || shot.elapsed_ms > config.penalty_shot_ms)
        return false;
    const auto& penalty = penalties[shot.penalty_id - 1];
    if (penalty.id != shot.penalty_id || !penalty.pending || !penalty.penalty_shot_reserved ||
        penalty.severity != (shot.free_shot ? Severity::Moderate : Severity::Serious) || !player_index(penalty.player) ||
        players[penalty.player].team != 1 - shot.attacking_team || penalty.crown_restoration_pending ||
        (shot.post_termination && (penalty.committed_ms < 0 || penalty.committed_ms > ending.at_ms)))
        return false;
    const auto& offender = players[penalty.player];
    if (!shot.free_shot && (phase == Phase::Donnybrook ? !offender.donnybrook_excluded : offender.removed_until <= now_ms))
        return false;
    const auto& ball = balls[shot.ball];
    if (!ball.phase_active || !scoring(ball.type) || ball.live ||
        ball.crown_restart_penalty >= 0 || ball.conduct_restart_penalty >= 0 ||
        ball.crown_deadline >= 0 || ball.timeout_until >= 0 || ball.protection_until >= 0 ||
        ball.restart_team != 1 - shot.attacking_team ||
        (phase == Phase::Donnybrook && ball.type != BallType::Quark)) return false;
    for (int i = 0; i < 7; ++i) {
        if (balls[i].live || (i != shot.ball && balls[i].controller >= 0)
            || balls[i].conduct_restart_penalty == shot.penalty_id) return false;
    }
    for (const auto& other : penalties) {
        if (other.id != shot.penalty_id && other.penalty_shot_reserved) return false;
        if (other.ball == shot.ball && other.crown_restoration_pending) return false;
    }
    if (shot.stage == PenaltyShotStage::Ready)
        return ball.dead_reason == "penalty_shot" && ball.controller == shot.shooter &&
               shot.released_ms == -1 && shot.outcome == PenaltyShotOutcome::None && shot.awarded_points == 0;
    if (shot.released_ms < -1 || shot.released_ms > shot.elapsed_ms) return false;
    if (shot.stage == PenaltyShotStage::InFlight)
        return ball.dead_reason == "penalty_shot" && ball.controller == -1 && shot.released_ms >= 0 &&
               shot.outcome == PenaltyShotOutcome::None && shot.awarded_points == 0;
    if (ball.dead_reason != "penalty_shot_restart" || ball.controller != -1) return false;
    if (shot.outcome == PenaltyShotOutcome::Goal)
        return shot.released_ms >= 0 && shot.awarded_points ==
            (ball.type == BallType::Quaffle ? config.quaffle_points : config.quark_points);
    return shot.awarded_points == 0 &&
        ((shot.outcome == PenaltyShotOutcome::Miss && shot.released_ms >= 0) ||
         (shot.outcome == PenaltyShotOutcome::Timeout && shot.elapsed_ms == config.penalty_shot_ms));
}
bool Match::start_penalty_shot(int penalty_id, int ball, int shooter, int netminder, bool free_shot) {
    if (!valid_ || penalty_shot_active() || !valid_shot_stoppage() ||
        penalty_id <= 0 || penalty_id > static_cast<int>(penalties.size()) || !ball_index(ball))
        return reject("penalty shot requires an unreserved stoppage or supported provisional ending");
    const auto& penalty = penalties[penalty_id - 1];
    if (status == Status::Review && (penalty.committed_ms < 0 || penalty.committed_ms > ending.at_ms))
        return reject("only pre-termination conduct may receive a shot before certification");
    if (penalty.id != penalty_id || !penalty.pending || penalty.severity != (free_shot ? Severity::Moderate : Severity::Serious) ||
        penalty.penalty_shot_reserved || penalty.crown_restoration_pending || !player_index(penalty.player) ||
        !team_index(players[penalty.player].team)) return reject("penalty severity does not match the requested shot");
    for (const auto& existing_ball : balls)
        if (existing_ball.conduct_restart_penalty == penalty_id)
            return reject("this penalty already owns a possession award");
    const int attacking_team = 1 - players[penalty.player].team;
    // A prior shot's genuine restart may coexist with other unresolved Serious
    // penalties at this same stoppage. Re-secure that completed restart only
    // after all new-shot checks pass, just as the next global whistle would.
    int previous_restart = -1;
    if (penalty_shot.stage == PenaltyShotStage::Complete && ball_index(penalty_shot.ball) &&
        penalty_shot.penalty_id > 0 && penalty_shot.penalty_id <= static_cast<int>(penalties.size())) {
        const auto& prior = penalties[penalty_shot.penalty_id - 1];
        const auto& prior_ball = balls[penalty_shot.ball];
        if (!prior.pending && !prior.penalty_shot_reserved && prior_ball.live &&
            prior_ball.controller == penalty_shot.netminder && prior_ball.dead_reason.empty() &&
            prior_ball.crown_restart_penalty < 0 && prior_ball.conduct_restart_penalty < 0 &&
            prior_ball.timeout_until < 0 && prior_ball.crown_deadline < 0)
            previous_restart = penalty_shot.ball;
    }
    const auto& selected = balls[ball];
    BallType expected = phase == Phase::Donnybrook ? BallType::Quark : BallType::Quaffle;
    if (ball_index(penalty.ball) && scoring(balls[penalty.ball].type)) expected = balls[penalty.ball].type;
    if (phase == Phase::Donnybrook && expected != BallType::Quark)
        return reject("a removed Quaffle remedy in Donnybrook requires external adjudication");
    if (!scoring(selected.type) || selected.type != expected || !selected.phase_active ||
        (ball != previous_restart && (selected.live || selected.controller >= 0 ||
         selected.dead_reason != "stoppage" || selected.protection_until >= 0)) ||
        selected.crown_restart_penalty >= 0 || selected.conduct_restart_penalty >= 0 ||
        selected.crown_deadline >= 0 || selected.timeout_until >= 0)
        return reject("shot ball type or existing dead-ball remedy forbids reservation");
    if (!eligible(shooter, ball) || !eligible(netminder, ball) || shooter == penalty.player ||
        (!free_shot && netminder == penalty.player) || players[shooter].team != attacking_team ||
        players[netminder].team != 1 - attacking_team ||
        (phase != Phase::Donnybrook && players[netminder].role != Role::Netminder) ||
        (carries_scoring_ball(shooter) &&
         (previous_restart < 0 || balls[previous_restart].controller != shooter)) ||
        (carries_scoring_ball(netminder) &&
         (previous_restart < 0 || balls[previous_restart].controller != netminder)))
        return reject("one eligible shooter must face an available defending Netminder");
    for (const auto& other : penalties) {
        if (other.penalty_shot_reserved) return reject("another penalty shot is reserved");
        if (other.ball == ball && other.crown_restoration_pending)
            return reject("outstanding Crown restoration owns this ball");
    }
    for (int i = 0; i < 7; ++i) if (i != previous_restart && (balls[i].live || balls[i].controller >= 0))
        return reject("all balls and their controllers must be stopped before a penalty shot");
    if (!free_shot && !sum_valid(now_ms, config.removal_ms)) return reject("removal clock overflow");
    // All rejection paths precede mutation. Live clocks cannot expire this
    // removal while the independent attempt clock is running.
    if (previous_restart >= 0) dead(previous_restart, "stoppage");
    auto& offender = players[penalty.player];
    if (!free_shot) {
        offender.removed_until = std::max(offender.removed_until, now_ms + config.removal_ms);
        if (phase == Phase::Donnybrook) { offender.donnybrook_excluded = true; offender.removed_until = -1; }
    }
    penalties[penalty_id - 1].penalty_shot_reserved = true;
    penalties[penalty_id - 1].disposition = free_shot
        ? "Moderate free shot reserved; no removal" : "Serious penalty shot reserved; removal active";
    penalty_shot = {};
    penalty_shot.free_shot = free_shot;
    penalty_shot.post_termination = status == Status::Review;
    penalty_shot.stage = PenaltyShotStage::Ready;
    penalty_shot.penalty_id = penalty_id; penalty_shot.ball = ball;
    penalty_shot.shooter = shooter; penalty_shot.netminder = netminder;
    penalty_shot.attacking_team = attacking_team;
    dead(ball, "penalty_shot");
    balls[ball].controller = shooter; balls[ball].restart_team = 1 - attacking_team;
    last_awards.clear();
    emit("penalty_shot_started", shooter, ball, attacking_team, config.penalty_shot_ms, "", penalty_id);
    if (penalty_shot.post_termination)
        emit("post_termination_shot_started", shooter, ball, attacking_team, ending.at_ms, ending.reason, penalty_id);
    if (!free_shot) emit("temporary_removal", penalty.player, ball, players[penalty.player].team,
         phase == Phase::Donnybrook ? -1 : offender.removed_until, "Serious penalty shot", penalty_id);
    last_error.clear(); return true;
}
bool Match::release_penalty_shot(int shooter) {
    if (!valid_penalty_shot() || penalty_shot.stage != PenaltyShotStage::Ready ||
        shooter != penalty_shot.shooter || penalty_shot.elapsed_ms >= config.penalty_shot_ms)
        return reject("only the reserved shooter may release one penalty-shot attempt before timeout");
    penalty_shot.stage = PenaltyShotStage::InFlight;
    penalty_shot.released_ms = penalty_shot.elapsed_ms;
    balls[penalty_shot.ball].controller = -1;
    emit("penalty_shot_released", shooter, penalty_shot.ball, penalty_shot.attacking_team,
         penalty_shot.elapsed_ms, "", penalty_shot.penalty_id);
    last_error.clear(); return true;
}
Millis Match::advance_penalty_shot(Millis delta_ms) {
    if (!valid_penalty_shot() || delta_ms < 0 ||
        (penalty_shot.stage != PenaltyShotStage::Ready && penalty_shot.stage != PenaltyShotStage::InFlight)) {
        reject("only a ready or released penalty shot may advance its nonnegative attempt clock"); return -1;
    }
    const Millis consumed = std::min(delta_ms, config.penalty_shot_ms - penalty_shot.elapsed_ms);
    penalty_shot.elapsed_ms += consumed;
    if (penalty_shot.elapsed_ms >= config.penalty_shot_ms) {
        // Validation above makes this completion infallible; no live match time
        // passes, including when a large caller delta overshoots the deadline.
        complete_penalty_shot(PenaltyShotOutcome::Timeout);
    }
    last_error.clear(); return consumed;
}
bool Match::complete_penalty_shot(PenaltyShotOutcome outcome, const PointEvent& goal) {
    if (!valid_penalty_shot() ||
        (penalty_shot.stage != PenaltyShotStage::Ready && penalty_shot.stage != PenaltyShotStage::InFlight))
        return reject("no unresolved reserved penalty-shot attempt");
    auto& shot = penalty_shot;
    std::int64_t points = 0;
    if (outcome == PenaltyShotOutcome::Timeout) {
        if (shot.elapsed_ms != config.penalty_shot_ms) return reject("attempt clock has not expired");
    } else if (outcome == PenaltyShotOutcome::Goal || outcome == PenaltyShotOutcome::Miss) {
        if (shot.stage != PenaltyShotStage::InFlight || shot.elapsed_ms >= config.penalty_shot_ms)
            return reject("a make or miss requires the one released attempt before timeout");
        if (outcome == PenaltyShotOutcome::Goal) {
            const auto expected = balls[shot.ball].type == BallType::Quaffle ? Hoop::Large : Hoop::Small;
            if (goal.kind != EventKind::Goal || goal.ball != shot.ball ||
                goal.attacking_team != shot.attacking_team ||
                (goal.player != -1 && goal.player != shot.shooter) || goal.hoop != expected ||
                !goal.entire_ball || !goal.forward || goal.teleported)
                return reject("penalty goal lacks matching physical scoring evidence");
            points = balls[shot.ball].type == BallType::Quaffle ? config.quaffle_points : config.quark_points;
            if (!sum_valid(scores[shot.attacking_team], points)) return reject("score overflow");
        }
    } else return reject("unknown penalty-shot outcome");
    shot.outcome = outcome; shot.awarded_points = points;
    shot.stage = PenaltyShotStage::AwaitingRestart;
    dead(shot.ball, "penalty_shot_restart");
    last_awards.clear();
    if (outcome == PenaltyShotOutcome::Goal) {
        scores[shot.attacking_team] += points;
        last_awards.push_back({shot.attacking_team, points, shot.ball, shot.shooter});
        emit("points", shot.shooter, shot.ball, shot.attacking_team, points, "penalty shot", shot.penalty_id);
    }
    emit("penalty_shot_completed", shot.shooter, shot.ball, shot.attacking_team,
         static_cast<int>(outcome), "", shot.penalty_id);
    last_error.clear(); return true;
}
bool Match::restart_penalty_shot(int netminder) {
    if (!valid_penalty_shot() || penalty_shot.stage != PenaltyShotStage::AwaitingRestart ||
        netminder != penalty_shot.netminder || carries_scoring_ball(netminder))
        return reject("reserved penalty shot awaits its defending Netminder's actual restart");
    if (!sum_valid(now_ms, config.restart_protection_ms)) return reject("restart clock overflow");
    auto& shot = penalty_shot;
    auto& penalty = penalties[shot.penalty_id - 1];
    // This custody assignment is the stopped-play equivalent of restart(),
    // with stricter identity and reservation validation. Resume preserves it.
    release_ball(shot.ball);
    balls[shot.ball].controller = netminder;
    balls[shot.ball].protection_until = now_ms + config.restart_protection_ms;
    penalty.pending = false; penalty.penalty_shot_reserved = false;
    penalty.disposition = shot.free_shot
        ? "Moderate free shot served by defending restart; no removal"
        : "Serious penalty shot served by defending Netminder restart; removal active";
    shot.stage = PenaltyShotStage::Complete;
    emit("possession", netminder, shot.ball);
    emit("protected_restart", netminder, shot.ball);
    emit("penalty_shot_restart", netminder, shot.ball, players[netminder].team, 0, "", shot.penalty_id);
    emit("penalty_resolved", penalty.player, penalty.ball, players[netminder].team,
         0, penalty.disposition, shot.penalty_id);
    // Audit the defending restart before evaluating a shot-created ending. A
    // pre-existing ending keeps its event and timestamp; certify() retests it
    // after all owed remedies. Its stopped-play custody survives an OT resume.
    if (shot.post_termination)
        emit("post_termination_shot_served", netminder, shot.ball, players[netminder].team,
             ending.at_ms, ending.reason, shot.penalty_id);
    else if (shot.outcome == PenaltyShotOutcome::Goal && phase == Phase::Donnybrook)
        end("donnybrook", -1, -1, 0, shot.attacking_team);
    else if (shot.outcome == PenaltyShotOutcome::Goal && phase == Phase::Overtime && margin() >= config.overtime_margin)
        end("overtime_margin");
    last_error.clear(); return true;
}
bool Match::recall_chase(int ball) {
    if (!live_ball(ball)) return false;
    if (!chase(balls[ball].type)) return reject("only chase balls may use envelope recall");
    release_ball(ball); emit("chase_recall", -1, ball); last_error.clear(); return true;
}
int Match::record_penalty(int player, const std::string& reason, Severity severity, int ball, Millis committed_ms) {
    if (!valid_ || !player_index(player) || static_cast<int>(severity) < 0 || static_cast<int>(severity) > 4 ||
        (ball != -1 && !ball_index(ball))) { reject("invalid penalty"); return -1; }
    if (committed_ms == -1) committed_ms = now_ms;
    if (committed_ms < 0 || committed_ms > now_ms) { reject("invalid conduct timestamp"); return -1; }
    if (penalties.size() >= static_cast<std::size_t>(std::numeric_limits<int>::max())) { reject("penalty id overflow"); return -1; }
    int id = static_cast<int>(penalties.size()) + 1;
    penalties.push_back({id, player, ball, reason, "", severity, committed_ms, true});
    emit("penalty_pending", player, ball, -1, 0, reason, id);
    if ((severity == Severity::Serious || severity == Severity::Severe || severity == Severity::Catastrophic) && status == Status::Live)
        pause("dangerous_conduct");
    last_error.clear(); return id;
}
bool Match::resolve_penalty(int id, const std::string& disposition, bool apply_removal) {
    if (penalty_shot_active()) return reject("complete the reserved shot and defending restart before manual adjudication");
    if (!valid_ || id <= 0 || id > static_cast<int>(penalties.size()) || disposition.empty() || status == Status::Live ||
        (!penalties[id - 1].pending || penalties[id - 1].penalty_shot_reserved)) return reject("resolve a pending penalty at a stoppage with a disposition");
    for (const auto& ball : balls) if (ball.conduct_restart_penalty == id)
        return reject("serve the queued conduct possession award through an actual protected restart");
    auto& penalty = penalties[id - 1]; auto& p = players[penalty.player];
    if (!apply_removal && (penalty.severity == Severity::Serious || penalty.severity == Severity::Severe))
        return reject("removal and ejection cannot be declined");
    if (penalty.severity == Severity::Catastrophic) return reject("catastrophic forfeit review requires external adjudication");
    if (penalty.severity == Severity::Serious) {
        if (!sum_valid(now_ms, config.removal_ms)) return reject("clock overflow");
        p.removed_until = now_ms + config.removal_ms;
        if (phase == Phase::Donnybrook) { p.donnybrook_excluded = true; p.removed_until = -1; }
    } else if (penalty.severity == Severity::Severe) p.ejected = true;
    penalty.pending = false; penalty.disposition = disposition;
    // An explicit official disposition may decline ordinary restorative
    // possession after advantage; the historical foul remains in the ledger.
    penalty.crown_restoration_pending = false;
    emit("penalty_resolved", penalty.player, penalty.ball, -1, 0, disposition, id); last_error.clear(); return true;
}
bool Match::certify(const std::vector<Adjustment>& adjustments) {
    if (penalty_shot_active()) return reject("reserved penalty shot and restart are outstanding");
    for (const auto& p : penalties) if (p.penalty_shot_reserved)
        return reject("reserved penalty shot cannot be bypassed by certification");
    if (!valid_ || status != Status::Review || !ending.active) return reject("no provisional ending to certify");
    for (const auto& p : penalties) if (p.pending && p.committed_ms <= ending.at_ms)
        return reject("resolve every pre-termination penalty before certification");
    auto projected = scores;
    for (const auto& a : adjustments) {
        if (!team_index(a.team) || a.committed_ms < 0 || a.committed_ms > ending.at_ms || a.reason.empty() ||
            !sum_valid(projected[a.team], a.delta)) return reject("invalid certification adjustment");
        projected[a.team] += a.delta;
    }
    if (projected[0] < 0 || projected[1] < 0) return reject("certified score cannot be negative");
    scores = projected;
    for (const auto& a : adjustments) emit("score_adjustment", -1, -1, a.team, a.delta, a.reason);
    const auto reason = ending.reason;
    if (reason == "snitch") {
        if (players[ending.catcher].role == Role::Scout) reckoner = ending.catcher;
        finish(leader() < 0 ? ending.catching_team : leader());
    } else if (reason == "donnybrook") finish(ending.winning_team);
    else if (reason == "regulation_horn") {
        if (margin() >= config.regulation_margin) finish(leader()); else enter_phase(Phase::Overtime);
    } else if (reason == "overtime_margin") {
        if (margin() >= config.overtime_margin) finish(leader());
        else if (period_elapsed_ms < config.overtime_ms) {
            ending = {}; status = Status::Live;
            for (int i = 0; i < 7; ++i) if (balls[i].dead_reason == "stoppage") release_ball(i);
            emit("overtime_resume_after_review");
        } else if (margin()) finish(leader()); else enter_phase(Phase::Donnybrook);
    } else if (reason == "overtime_horn") {
        if (margin()) finish(leader()); else enter_phase(Phase::Donnybrook);
    }
    last_error.clear(); return true;
}
bool Match::overturn_snitch(const std::string& reason) {
    if (penalty_shot_active()) return reject("complete the reserved shot and defending restart before overturning a catch");
    if (!valid_ || status != Status::Review || !ending.active || ending.reason != "snitch" || reason.empty())
        return reject("no provisional Snitch catch to overturn");
    scores[ending.catching_team] -= ending.catch_points;
    ending = {}; status = Status::Paused; release_ball(4); secure_balls();
    emit("snitch_overturned", -1, -1, -1, 0, reason); last_error.clear(); return true;
}
void Match::enter_phase(Phase next) {
    phase = next; status = Status::PhaseBreak; period_elapsed_ms = 0; ending = {};
    for (int i = 0; i < 7; ++i) {
        auto& b = balls[i];
        b.phase_active = phase == Phase::Overtime || b.type == BallType::Quark || b.type == BallType::Snipe;
        b.timeout_until = b.crown_deadline = -1;
        if (!b.phase_active) {
            for (auto& penalty : penalties) if (penalty.ball == i && penalty.crown_restoration_pending) {
                penalty.crown_restoration_pending = false;
                penalty.disposition = "unserved ordinary possession remedy expired when ball left the phase";
                emit("crown_restoration_expired", penalty.player, i, -1, 0, penalty.disposition, penalty.id);
            }
            b.crown_restart_penalty = -1;
        }
        dead(i, b.phase_active ? (b.crown_restart_penalty > 0 ? "crown_restart" : "stoppage") : "removed");
    }
    hurleys = {};
    if (phase == Phase::Donnybrook)
        for (auto& p : players) if (p.removed_until >= 0) { p.donnybrook_excluded = true; p.removed_until = -1; }
    emit("phase_change", -1, -1, -1, static_cast<int>(phase));
}
void Match::finish(int winning_team) {
    status = Status::Complete; winner = winning_team; secure_balls();
    for (auto& penalty : penalties) if (penalty.crown_restoration_pending) {
        penalty.crown_restoration_pending = false;
        penalty.disposition = "unserved ordinary possession remedy expired with the certified match";
        emit("crown_restoration_expired", penalty.player, penalty.ball, -1, 0, penalty.disposition, penalty.id);
    }
    for (auto& ball : balls) ball.crown_restart_penalty = -1;
    emit("match_certified", reckoner, -1, winner);
}
} // namespace BB

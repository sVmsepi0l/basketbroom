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
        config.crown_return_ms, config.removal_ms, config.restart_protection_ms};
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
    if (!valid_ || (status != Status::Paused && status != Status::QuarterBreak && status != Status::PhaseBreak))
        return reject("there is no resumable stoppage");
    for (const auto& p : penalties) if (p.pending) return reject("administer pending penalties before the next horn");
    if (status == Status::QuarterBreak) { ++quarter; period_elapsed_ms = 0; }
    status = Status::Live;
    for (int i = 0; i < 7; ++i) if (balls[i].phase_active && balls[i].dead_reason == "stoppage") release_ball(i);
    emit("resume", -1, -1, -1, quarter); last_error.clear(); return true;
}
bool Match::restart(int ball, int player) {
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
    emit("protected_restart", player, ball); last_error.clear(); return true;
}
bool Match::crown_exit(int ball, const std::array<double, 3>& mark, int responsible_player, bool deliberate_delay) {
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
    if (!valid_ || id <= 0 || id > static_cast<int>(penalties.size()) || disposition.empty() || status == Status::Live ||
        !penalties[id - 1].pending) return reject("resolve a pending penalty at a stoppage with a disposition");
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

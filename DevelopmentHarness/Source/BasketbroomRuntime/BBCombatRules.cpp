#include "BBCombatRules.h"
#include <algorithm>
#include <limits>

namespace BB {
namespace {
bool player_index(int player) { return player >= 0 && player < CombatPolicy::PlayerCount; }
bool team_value(int team) { return team == 0 || team == 1; }
bool variant_value(CombatVariant variant) {
    return variant == CombatVariant::Regulation || variant == CombatVariant::Bloodbroom;
}
std::uint32_t bit(ConductViolation violation) { return static_cast<std::uint32_t>(violation); }
CombatDecision deny(CombatDenial reason, std::uint64_t id = 0) {
    CombatDecision result; result.denial = reason; result.attack_id = id; return result;
}
CombatDecision accept(std::uint64_t id = 0) {
    CombatDecision result; result.accepted = true; result.attack_id = id; return result;
}
bool can_add(std::int64_t time, std::int64_t delta) {
    return delta >= 0 && time <= std::numeric_limits<std::int64_t>::max() - delta;
}
} // namespace

CombatPolicy::CombatPolicy(const CombatConfig& config, CombatVariant variant)
    : config_(config), variant_(variant), actors_(default_roster()) {
    valid_ = variant_value(variant) && config.mob_window_ms > 0
        && config.max_impediment_ms > 0 && config.pending_attack_ms > 0;
    reset_phase();
}

std::array<CombatActor, CombatPolicy::PlayerCount> CombatPolicy::default_roster() {
    std::array<CombatActor, PlayerCount> result{};
    for (int player = 0; player < PlayerCount; ++player) result[player] = {player / 8, true};
    return result;
}

bool CombatPolicy::configure_roster(const std::array<CombatActor, PlayerCount>& actors) {
    if (!valid_ || now_ != 0 || !attacks_.empty()) return false;
    for (const auto& actor : actors)
        if (!team_value(actor.team) && (actor.team != -1 || actor.eligible)) return false;
    actors_ = actors;
    reset_phase();
    return true;
}

void CombatPolicy::forget_actor(int player) {
    for (int index = 0; index < PlayerCount; ++index) {
        mob_[player][index] = -1;
        mob_[index][player] = -1;
    }
    attacks_.erase(std::remove_if(attacks_.begin(), attacks_.end(), [player](const Attack& attack) {
        return attack.attacker == player || attack.target == player;
    }), attacks_.end());
}

bool CombatPolicy::set_actor(int player, int team, bool eligible, bool new_identity) {
    if (!valid_ || !player_index(player) || (!team_value(team) && (team != -1 || eligible))) return false;
    if (new_identity || actors_[player].team != team) forget_actor(player);
    actors_[player] = {team, eligible};
    return true;
}

int CombatPolicy::active_attackers(int team, int target) const {
    if (!valid_ || !team_value(team) || !player_index(target)) return 0;
    int count = 0;
    for (int attacker = 0; attacker < PlayerCount; ++attacker) {
        const auto at = mob_[target][attacker];
        if (actors_[attacker].team == team && at >= 0 && now_ - at < config_.mob_window_ms) ++count;
    }
    return count;
}

bool CombatPolicy::confirmed_impediment(int attacker, int target) const {
    return std::any_of(attacks_.begin(), attacks_.end(), [&](const Attack& attack) {
        return attack.attacker == attacker && attack.target == target && attack.successful
            && attack.confirmed && attack.impeded_until > now_;
    });
}

CombatDecision CombatPolicy::begin_attack(int attacker, int target, const AttackSpec& spec) {
    if (!valid_) return deny(CombatDenial::InvalidConfiguration);
    if (!player_index(attacker) || !team_value(actors_[attacker].team)) return deny(CombatDenial::InvalidActor);
    if (!player_index(target) || !team_value(actors_[target].team) || (spec.offensive && attacker == target))
        return deny(CombatDenial::InvalidTarget);
    if (!actors_[attacker].eligible || !actors_[target].eligible) return deny(CombatDenial::Unavailable);
    if (!live_) return deny(CombatDenial::NotLive);
    if (!spec.offensive && (spec.stun || spec.impediment || spec.unforgivable
            || spec.physical_hold || spec.aimed_at_head)) return deny(CombatDenial::InvalidSpec);
    if (!spec.offensive) return accept(); // Protego / utility does not join a mob.
    if (!can_add(now_, config_.pending_attack_ms)) return deny(CombatDenial::InvalidTime);
    if (next_id_ == std::numeric_limits<std::uint64_t>::max()) return deny(CombatDenial::IdExhausted);
    prune();
    std::uint32_t candidates = 0;
    if (variant_ == CombatVariant::Regulation) {
        if (spec.unforgivable) candidates |= bit(ConductViolation::Unforgivable);
        if (spec.aimed_at_head) candidates |= bit(ConductViolation::Headshot);
    }
    if (spec.physical_hold) candidates |= bit(ConductViolation::PhysicalHolding);
    if (spec.stun && confirmed_impediment(attacker, target)) candidates |= bit(ConductViolation::DoubleTap);
    const auto previous = mob_[target][attacker];
    const bool already_attacking = previous >= 0 && now_ - previous < config_.mob_window_ms;
    const int participants = active_attackers(actors_[attacker].team, target) + (already_attacking ? 0 : 1);
    if (participants > MobLimit) candidates |= bit(ConductViolation::Mobbing);
    mob_[target][attacker] = now_;
    Attack attack;
    attack.id = next_id_++;
    attack.attacker = attacker; attack.target = target; attack.spec = spec;
    attack.attempt_violations = candidates;
    attack.expires = now_ + config_.pending_attack_ms;
    attacks_.push_back(attack);
    CombatDecision result = accept(attack.id);
    result.attempt_violations = candidates;
    return result;
}

CombatPolicy::Attack* CombatPolicy::find(std::uint64_t id) {
    if (id == 0) return nullptr;
    const auto found = std::find_if(attacks_.begin(), attacks_.end(), [id](const Attack& attack) { return attack.id == id; });
    return found == attacks_.end() ? nullptr : &*found;
}

CombatDecision CombatPolicy::resolve_hit(std::uint64_t id, HitOutcome outcome, bool hit_head,
                                        std::int64_t impediment_ms) {
    if (!valid_) return deny(CombatDenial::InvalidConfiguration, id);
    if (!live_) return deny(CombatDenial::NotLive, id);
    prune();
    Attack* attack = find(id);
    if (!attack) return deny(CombatDenial::UnknownAttack, id);
    if (attack->resolved) return deny(CombatDenial::AlreadyResolved, id);
    if (!actors_[attack->attacker].eligible || !actors_[attack->target].eligible)
        return deny(CombatDenial::Unavailable, id);
    if (outcome != HitOutcome::Miss && outcome != HitOutcome::Blocked
            && outcome != HitOutcome::Contact && outcome != HitOutcome::Impeded)
        return deny(CombatDenial::InvalidOutcome, id);
    const auto duration = impediment_ms == -1 ? config_.max_impediment_ms : impediment_ms;
    if (outcome == HitOutcome::Impeded && (!attack->spec.impediment || duration <= 0
            || duration > config_.max_impediment_ms)) return deny(CombatDenial::InvalidOutcome, id);
    if (outcome == HitOutcome::Impeded && !can_add(now_, duration)) return deny(CombatDenial::InvalidTime, id);
    attack->resolved = true;
    CombatDecision result = accept(id);
    if (outcome == HitOutcome::Miss || outcome == HitOutcome::Blocked) return result;
    // Apply-the-hit policy: accepted remains true even with conduct violations.
    // Headshot depends on the actual impact, not an aim hint that may miss.
    result.violations = attack->attempt_violations & ~bit(ConductViolation::Headshot);
    if (hit_head && variant_ == CombatVariant::Regulation) result.violations |= bit(ConductViolation::Headshot);
    if (outcome == HitOutcome::Impeded) {
        attack->successful = true;
        attack->impeded_until = now_ + duration;
    }
    return result;
}

CombatDecision CombatPolicy::confirm_impediment(std::uint64_t id, int notified_caster) {
    if (!valid_) return deny(CombatDenial::InvalidConfiguration, id);
    Attack* attack = find(id);
    if (!attack) return deny(CombatDenial::UnknownAttack, id);
    if (notified_caster != attack->attacker) return deny(CombatDenial::WrongNotifier, id);
    if (!attack->resolved || !attack->successful) return deny(CombatDenial::NoSuccessfulImpediment, id);
    if (attack->impeded_until <= now_) return deny(CombatDenial::ImpedimentExpired, id);
    if (attack->confirmed) return deny(CombatDenial::AlreadyConfirmed, id);
    attack->confirmed = true;
    return accept(id);
}

bool CombatPolicy::end_impediment(std::uint64_t id) {
    Attack* attack = find(id);
    if (!attack || !attack->resolved || !attack->successful || attack->impeded_until <= now_) return false;
    attack->impeded_until = now_;
    return true;
}

void CombatPolicy::recover_target(int target) {
    if (!player_index(target)) return;
    for (auto& attack : attacks_)
        if (attack.target == target && attack.successful) attack.impeded_until = now_;
}

void CombatPolicy::prune() {
    attacks_.erase(std::remove_if(attacks_.begin(), attacks_.end(), [&](const Attack& attack) {
        return now_ >= attack.expires && now_ >= attack.impeded_until;
    }), attacks_.end());
}

bool CombatPolicy::advance(std::int64_t delta_ms, bool live) {
    if (!valid_ || delta_ms < 0 || (live && !can_add(now_, delta_ms))) return false;
    live_ = live;
    if (live) now_ += delta_ms;
    prune();
    return true;
}

void CombatPolicy::reset_phase() {
    attacks_.clear();
    for (auto& target : mob_) target.fill(-1);
}

bool CombatPolicy::reset_match(CombatVariant variant) {
    if (!valid_ || !variant_value(variant)) return false;
    variant_ = variant;
    now_ = 0;
    reset_phase();
    return true;
}

const char* combat_denial_name(CombatDenial denial) {
    switch (denial) {
    case CombatDenial::None: return "none";
    case CombatDenial::InvalidConfiguration: return "invalid_configuration";
    case CombatDenial::InvalidActor: return "invalid_actor";
    case CombatDenial::InvalidTarget: return "invalid_target";
    case CombatDenial::Unavailable: return "unavailable";
    case CombatDenial::NotLive: return "not_live";
    case CombatDenial::InvalidSpec: return "invalid_spec";
    case CombatDenial::UnknownAttack: return "unknown_attack";
    case CombatDenial::AlreadyResolved: return "already_resolved";
    case CombatDenial::InvalidOutcome: return "invalid_outcome";
    case CombatDenial::NoSuccessfulImpediment: return "no_successful_impediment";
    case CombatDenial::ImpedimentExpired: return "impediment_expired";
    case CombatDenial::WrongNotifier: return "wrong_notifier";
    case CombatDenial::AlreadyConfirmed: return "already_confirmed";
    case CombatDenial::InvalidTime: return "invalid_time";
    case CombatDenial::IdExhausted: return "id_exhausted";
    }
    return "invalid_denial";
}
} // namespace BB

#pragma once
// BB-0 conduct decisions only. Portable C++17; no Unreal, exceptions, scores,
// removals, or invented penalty severities. All mutators belong to the server.
#include <array>
#include <cstdint>
#include <vector>

namespace BB {
enum class CombatVariant : int { Regulation, Bloodbroom };
enum class HitOutcome : int { Miss, Blocked, Contact, Impeded };
enum class ConductViolation : std::uint32_t {
    None = 0, Unforgivable = 1, Headshot = 2, Mobbing = 4,
    DoubleTap = 8, PhysicalHolding = 16
};
enum class CombatDenial : int {
    None, InvalidConfiguration, InvalidActor, InvalidTarget, Unavailable,
    NotLive, InvalidSpec, UnknownAttack, AlreadyResolved,
    InvalidOutcome, NoSuccessfulImpediment, ImpedimentExpired,
    WrongNotifier, AlreadyConfirmed, InvalidTime, IdExhausted
};
struct AttackSpec {
    // Server spell catalogue / collision traits, never RPC-supplied facts.
    bool offensive = true;
    bool stun = false;
    bool impediment = false;
    bool unforgivable = false;
    bool physical_hold = false;
    bool aimed_at_head = false;
};
struct CombatConfig {
    // Provisional playtest values. Three distinct same-team attackers is fixed.
    std::int64_t mob_window_ms = 2000;
    std::int64_t max_impediment_ms = 3000;
    std::int64_t pending_attack_ms = 5000;
};
struct CombatActor {
    int team = -1;
    bool eligible = false;
};
struct CombatDecision {
    // Accepted is mechanical validity, NOT legality: apply a valid hit first,
    // then submit violations for adjudication. No punishment is prescribed here.
    bool accepted = false;
    std::uint64_t attack_id = 0;
    CombatDenial denial = CombatDenial::None;
    // Exactly-once successful-hit evidence. Miss/Blocked never populate this.
    std::uint32_t violations = 0;
    // Cast-time candidates only, never a second penalty instruction. In-flight
    // double-tap/mob decisions are latched here; head region is verified at impact.
    std::uint32_t attempt_violations = 0;
    bool legal() const { return accepted && (violations | attempt_violations) == 0; }
    bool requires_adjudication() const { return violations != 0; }
    bool has(ConductViolation violation) const {
        return (violations & static_cast<std::uint32_t>(violation)) != 0;
    }
};

class CombatPolicy {
public:
    static constexpr int PlayerCount = 16;
    static constexpr int MobLimit = 3;
    explicit CombatPolicy(const CombatConfig& config = CombatConfig{},
                          CombatVariant variant = CombatVariant::Regulation);
    static std::array<CombatActor, PlayerCount> default_roster();
    // IDs identify stable combatants, not positions that can be swapped. Initial
    // configuration only; use set_actor for live authority updates.
    bool configure_roster(const std::array<CombatActor, PlayerCount>& actors);
    // Mark new_identity on admission to a reused roster slot. Stale attack IDs
    // and prior occupant's individual confirmation state must not be inherited.
    bool set_actor(int player, int team, bool eligible, bool new_identity = false);
    CombatDecision begin_attack(int attacker, int target, const AttackSpec& spec);
    // Read-only admission before a delayed effect: exact original caster and
    // target, unresolved receipt, live availability and unexpired lifetime.
    CombatDecision validate_pending_hit(std::uint64_t id, int attacker, int target) const;
    // Resolve the SAME server-bound target once. Contact does not mean impaired.
    // Impeded requires a server-verified successful effect and a catalogue trait;
    // -1 uses the configured maximum, otherwise supply actual remaining life.
    // Later confirmation never retroactively makes an already-launched cast a
    // double-tap. Illegal valid hits remain accepted and report conduct evidence.
    CombatDecision resolve_hit(std::uint64_t attack_id, HitOutcome outcome,
                               bool hit_head = false, std::int64_t impediment_ms = -1);
    // Call only after verified delivery of clear feedback for this exact server
    // success ID to its caster. Neither target nor success/time comes from client.
    CombatDecision confirm_impediment(std::uint64_t attack_id, int notified_caster);
    bool end_impediment(std::uint64_t attack_id);
    void recover_target(int target);
    // Only consumed LIVE milliseconds advance windows. Invalid input is atomic.
    // Also sets live/not-live admission state; returns false for invalid/overflow.
    bool advance(std::int64_t delta_ms, bool live = true);
    void set_live(bool live) { live_ = live; }
    void reset_phase(); // phase change, not an ordinary stoppage
    bool reset_match(CombatVariant variant);
    bool is_valid() const { return valid_; }
    bool is_live() const { return live_; }
    std::int64_t now_ms() const { return now_; }
    CombatVariant variant() const { return variant_; }
    const CombatConfig& config() const { return config_; }
    int active_attackers(int team, int target) const;

private:
    struct Attack {
        std::uint64_t id = 0;
        int attacker = -1, target = -1;
        AttackSpec spec;
        std::uint32_t attempt_violations = 0;
        std::int64_t expires = 0, impeded_until = -1;
        bool resolved = false, successful = false, confirmed = false;
    };
    CombatConfig config_;
    CombatVariant variant_;
    std::array<CombatActor, PlayerCount> actors_;
    // Last accepted attack by [target][attacker]. Repeated attacks occupy one slot.
    std::array<std::array<std::int64_t, PlayerCount>, PlayerCount> mob_;
    std::vector<Attack> attacks_;
    std::int64_t now_ = 0;
    std::uint64_t next_id_ = 1; // never reset/reused across phases or rematches
    bool valid_ = true, live_ = true;
    void prune();
    void forget_actor(int player);
    bool confirmed_impediment(int attacker, int target) const;
    Attack* find(std::uint64_t id);
};
const char* combat_denial_name(CombatDenial denial);
} // namespace BB

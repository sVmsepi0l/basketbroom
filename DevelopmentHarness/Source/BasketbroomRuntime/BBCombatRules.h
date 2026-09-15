#pragma once
// bb-0 conduct decisions only. portable c++17; no unreal, exceptions, scores,
// removals, or invented penalty severities. all mutators belong to the server.
#include <array>
#include <cstdint>
#include <vector>

namespace bb {
enum class combatvariant : int { regulation, bloodbroom };
enum class hitoutcome : int { miss, blocked, contact, impeded };
enum class conductviolation : std::uint32_t {
    none = 0, unforgivable = 1, headshot = 2, mobbing = 4,
    doubletap = 8, physicalholding = 16
};
enum class combatdenial : int {
    none, invalidconfiguration, invalidactor, invalidtarget, unavailable,
    notlive, invalidspec, unknownattack, alreadyresolved,
    invalidoutcome, nosuccessfulimpediment, impedimentexpired,
    wrongnotifier, alreadyconfirmed, invalidtime, idexhausted
};
struct attackspec {
    // server spell catalogue / collision traits, never rpc-supplied facts.
    bool offensive = true;
    bool stun = false;
    bool impediment = false;
    bool unforgivable = false;
    bool physical_hold = false;
    bool aimed_at_head = false;
};
struct combatconfig {
    // provisional playtest values. three distinct same-team attackers is fixed.
    std::int64_t mob_window_ms = 2000;
    std::int64_t max_impediment_ms = 3000;
    std::int64_t pending_attack_ms = 5000;
};
struct combatactor {
    int team = -1;
    bool eligible = false;
};
struct combatdecision {
    // accepted is mechanical validity, not legality: apply a valid hit first,
    // then submit violations for adjudication. no punishment is prescribed here.
    bool accepted = false;
    std::uint64_t attack_id = 0;
    combatdenial denial = CombatDenial::None;
    // exactly-once successful-hit evidence. Miss/Blocked never populate this.
    std::uint32_t violations = 0;
    // cast-time candidates only, never a second penalty instruction. in-flight
    // double-tap/mob decisions are latched here; head region is verified at impact.
    std::uint32_t attempt_violations = 0;
    bool legal() const { return accepted && (violations | attempt_violations) == 0; }
    bool requires_adjudication() const { return violations != 0; }
    bool has(conductviolation violation) const {
        return (violations & static_cast<std::uint32_t>(violation)) != 0;
    }
};

class combatpolicy {
public:
    static constexpr int playercount = 16;
    static constexpr int moblimit = 3;
    explicit combatpolicy(const combatconfig& config = combatconfig{},
                          combatvariant variant = CombatVariant::Regulation);
    static std::array<CombatActor, playercount> default_roster();
    // ids identify stable combatants, not positions that can be swapped. initial
    // configuration only; use set_actor for live authority updates.
    bool configure_roster(const std::array<CombatActor, playercount>& actors);
    // mark new_identity on admission to a reused roster slot. stale attack ids
    // and prior occupant's individual confirmation state must not be inherited.
    bool set_actor(int player, int team, bool eligible, bool new_identity = false);
    combatdecision begin_attack(int attacker, int target, const attackspec& spec);
    // read-only admission before a delayed effect: exact original caster and
    // target, unresolved receipt, live availability and unexpired lifetime.
    combatdecision validate_pending_hit(std::uint64_t id, int attacker, int target) const;
    // resolve the same server-bound target once. contact does not mean impaired.
    // impeded requires a server-verified successful effect and a catalogue trait;
    // -1 uses the configured maximum, otherwise supply actual remaining life.
    // later confirmation never retroactively makes an already-launched cast a
    // double-tap. illegal valid hits remain accepted and report conduct evidence.
    combatdecision resolve_hit(std::uint64_t attack_id, hitoutcome outcome,
                               bool hit_head = false, std::int64_t impediment_ms = -1);
    // call only after verified delivery of clear feedback for this exact server
    // success id to its caster. neither target nor success/time comes from client.
    combatdecision confirm_impediment(std::uint64_t attack_id, int notified_caster);
    bool end_impediment(std::uint64_t attack_id);
    void recover_target(int target);
    // only consumed live milliseconds advance windows. invalid input is atomic.
    // also sets live/not-live admission state; returns false for invalid/overflow.
    bool advance(std::int64_t delta_ms, bool live = true);
    void set_live(bool live) { live_ = live; }
    void reset_phase(); // phase change, not an ordinary stoppage
    bool reset_match(combatvariant variant);
    bool is_valid() const { return valid_; }
    bool is_live() const { return live_; }
    std::int64_t now_ms() const { return now_; }
    combatvariant variant() const { return variant_; }
    const combatconfig& config() const { return config_; }
    int active_attackers(int team, int target) const;

private:
    struct attack {
        std::uint64_t id = 0;
        int attacker = -1, target = -1;
        attackspec spec;
        std::uint32_t attempt_violations = 0;
        std::int64_t expires = 0, impeded_until = -1;
        bool resolved = false, successful = false, confirmed = false;
    };
    combatconfig config_;
    combatvariant variant_;
    std::array<CombatActor, playercount> actors_;
    // last accepted attack by [target][attacker]. repeated attacks occupy one slot.
    std::array<std::array<std::int64_t, playercount>, playercount> mob_;
    std::vector<Attack> attacks_;
    std::int64_t now_ = 0;
    std::uint64_t next_id_ = 1; // never reset/reused across phases or rematches
    bool valid_ = true, live_ = true;
    void prune();
    void forget_actor(int player);
    bool confirmed_impediment(int attacker, int target) const;
    attack* find(std::uint64_t id);
};
const char* combat_denial_name(combatdenial denial);
} // namespace bb

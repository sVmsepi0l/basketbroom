#pragma once
#include "BBRuleEngine.h"

namespace BB {
// Session admission policy, not a change to the sporting rules. Until the
// match tracks durable participant identities, a new person must not inherit
// a departed player's individual restriction merely by taking their slot.
// Occupied also includes transiently unavailable physical CPU actors (stun).
inline int SelectAdmissionSlot(const Match& match, const std::array<bool, 16>& occupied,
                               int preferred_team)
{
    if (!match.is_valid() || preferred_team < 0 || preferred_team > 1) return -1;
    auto clean = [&match, &occupied](int slot)
    {
        const auto& player = match.players[slot];
        if (occupied[slot] || player.ejected || player.donnybrook_excluded || player.removed_until >= 0)
            return false;
        for (const auto& penalty : match.penalties)
            if (penalty.player == slot && (penalty.pending || penalty.crown_restoration_pending))
                return false;
        return true;
    };
    for (int team : {preferred_team, 1 - preferred_team})
    {
        const int ranger = team * 8 + 4;
        if (clean(ranger)) return ranger;
        for (int slot = team * 8; slot < team * 8 + 8; ++slot)
            if (clean(slot)) return slot;
    }
    // All slots are occupied or restricted. Spectating preserves the team
    // remedies and historical sanctions instead of transferring or clearing them.
    return -1;
}
} // namespace BB

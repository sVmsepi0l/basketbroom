#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

namespace BBFlight
{
// Server-owned energy policy. Input carries intent only, never charge or speed.
struct Energy
{
    float charge = 0.f;
    float super_remaining = 0.f;
    float throttle = 0.f;
    float brake = 0.f;
    bool held = false;
    std::array<std::uint64_t, 2> last_reward{};

    bool award(std::uint8_t origin, std::uint64_t event, float amount)
    {
        if (origin >= last_reward.size() || !event || event <= last_reward[origin]
            || !std::isfinite(amount) || amount <= 0.f || amount > (origin == 0 ? 25.f : 15.f)) return false;
        last_reward[origin] = event;
        charge = std::min(100.f, charge + amount);
        return true;
    }
    void input(float acceleration, float braking, bool allowed)
    {
        throttle = std::isfinite(acceleration) ? std::clamp(acceleration, 0.f, 1.f) : 0.f;
        brake = std::isfinite(braking) ? std::clamp(braking, 0.f, 1.f) : 1.f;
        const bool down = throttle > .05f;
        if (!allowed || brake > .01f || !down) super_remaining = 0.f;
        if (allowed && brake <= .01f && down && !held && charge >= 100.f)
        {
            charge = 0.f;
            super_remaining = 2.f;
        }
        // Holding through a stoppage or filling to 100 never manufactures a new press.
        held = down;
    }
    void advance(float seconds, bool allowed)
    {
        if (!std::isfinite(seconds) || seconds <= 0.f) return;
        if (!allowed || brake > .01f || throttle <= .05f) { super_remaining = 0.f; return; }
        if (super_remaining > 0.f) super_remaining = std::max(0.f, super_remaining - seconds);
        else if (charge < 100.f) charge = std::max(0.f, charge - 12.f * throttle * seconds);
    }
    float scale(bool allowed) const
    {
        if (!allowed || throttle <= .05f || brake > .01f) return 1.f;
        if (super_remaining > 0.f) return 1.f + throttle;
        // A full meter waits for release/repress; it is not silently spent as regular boost.
        return charge > 0.f && charge < 100.f ? 1.f + .35f * throttle : 1.f;
    }
    void cancel() { throttle = brake = 0.f; super_remaining = 0.f; held = false; }
};
}

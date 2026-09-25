#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>

// Presentation only. No charge, movement, score or network authority lives here.
namespace BBBroomTrail
{
constexpr std::size_t Capacity = 80;
constexpr double SamplePeriod = 1.0 / 60.0;
constexpr double MaxLifetime = 1.2;
constexpr double MaxFrameGap = .2;
using Vector = std::array<double, 3>;

struct Sample
{
    Vector position{}, right{0, 1, 0}, up{0, 0, 1};
    double time = 0;
};

inline bool finite(const Vector& value)
{
    return std::isfinite(value[0]) && std::isfinite(value[1]) && std::isfinite(value[2]);
}

inline bool normalize_color(std::array<float, 3>& rgb)
{
    for (float value : rgb) if (!std::isfinite(value)) return false;
    for (float& value : rgb) value = std::clamp(value, 0.f, 1.f);
    return true;
}

inline double lifetime(double boost)
{
    return .30 + .85 * std::clamp(boost, 0.0, 1.0);
}

inline double taper(double age, double duration)
{
    if (!std::isfinite(age) || !std::isfinite(duration) || age < 0 || duration <= 0) return 0;
    return std::pow(std::clamp(1.0 - age / duration, 0.0, 1.0), 1.5);
}

class History
{
public:
    std::size_t size() const { return count; }
    const Sample& at(std::size_t index) const { return samples[(first + index) % Capacity]; }
    void clear() { first = count = 0; initialized = false; }

    // Interpolate onto a fixed timeline, not one point per rendered frame.
    // A hitch, clock rewind or displacement inconsistent with normal flight
    // starts a fresh strand rather than drawing across a teleport/respawn.
    bool advance(const Sample& frame, bool emit, double speed)
    {
        if (!std::isfinite(frame.time) || !finite(frame.position) || !finite(frame.right)
            || !finite(frame.up) || !std::isfinite(speed) || speed < 0)
        {
            const bool hadHistory = initialized;
            clear();
            return hadHistory;
        }
        bool discontinuity = false;
        if (initialized)
        {
            const double dt = frame.time - previous.time;
            double distanceSquared = 0;
            for (int axis = 0; axis < 3; ++axis)
                distanceSquared += std::pow(frame.position[axis] - previous.position[axis], 2);
            const double allowedDistance = std::max(350.0, speed * std::max(0.0, dt) * 2.0 + 100.0);
            discontinuity = dt < 0 || dt > MaxFrameGap || distanceSquared > allowedDistance * allowedDistance;
            if (discontinuity) clear();
            else if (dt == 0) return false;
        }
        if (!initialized)
        {
            previous = frame;
            nextTime = frame.time + SamplePeriod;
            initialized = true;
            if (emit) append(frame);
            return discontinuity;
        }
        while (count && frame.time - at(0).time > MaxLifetime)
        {
            first = (first + 1) % Capacity;
            --count;
        }
        if (emit)
        {
            for (int step = 0; step < 16 && nextTime <= frame.time + 1e-8; ++step)
            {
                const double alpha = std::clamp((nextTime - previous.time) / (frame.time - previous.time), 0.0, 1.0);
                Sample point;
                point.time = nextTime;
                for (int axis = 0; axis < 3; ++axis)
                {
                    point.position[axis] = previous.position[axis] + alpha * (frame.position[axis] - previous.position[axis]);
                    point.right[axis] = previous.right[axis] + alpha * (frame.right[axis] - previous.right[axis]);
                    point.up[axis] = previous.up[axis] + alpha * (frame.up[axis] - previous.up[axis]);
                }
                append(point);
                nextTime += SamplePeriod;
            }
        }
        else nextTime = frame.time + SamplePeriod;
        previous = frame;
        return false;
    }

private:
    void append(const Sample& sample)
    {
        if (count == Capacity) { first = (first + 1) % Capacity; --count; }
        samples[(first + count++) % Capacity] = sample;
    }
    std::array<Sample, Capacity> samples{};
    std::size_t first = 0, count = 0;
    Sample previous;
    double nextTime = 0;
    bool initialized = false;
};
}

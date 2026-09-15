#pragma once
#include "CoreMinimal.h"
#include "BBArenaDimensions.generated.h"

// Centimetres. the eave has no horizontal collision plane: the playable volume
// continues into a hollow four-face pyramid, enclosed only by its sloping net.
namespace bbarena
{
inline constexpr double roofrise = apexheight - eaveheight;
inline constexpr double restitution = .75;

inline fplane roofplane(int32 face)
{
    const double slope = roofrise / (face < 2 ? halflength : halfwidth);
    const double sign = face % 2 == 0 ? 1.0 : -1.0;
    const fvector normal = (face < 2 ? fvector(sign * slope, 0, 1)
                                             : fvector(0, sign * slope, 1)).GetSafeNormal();
    return FPlane(Normal.X, Normal.Y, Normal.Z, apexheight * Normal.Z);
}

inline double capsulerooflimit(double x, double y, double radius, double halfheight)
{
    const double sx = roofrise / halflength, sy = roofrise / halfwidth;
    return apexheight - FMath::Max(SX * FMath::Abs(X) + radius * FMath::Sqrt(1.0 + sx * sx),
                                   sy * FMath::Abs(Y) + radius * FMath::Sqrt(1.0 + sy * sy))
                      - FMath::Max(0.0, halfheight - radius);
}

// unlike an apex-height box, this tests the entire capsule against every
// sloped roof face, the side/end nets and the trampoline floor. a one-micron
// tolerance admits numerical contact, never a meaningful excursion outside.
inline bool containscapsule(const fvector& point, double radius, double halfheight,
                            double tolerance = .0001)
{
    if (Point.ContainsNaN() || !FMath::IsFinite(Radius) || !FMath::IsFinite(HalfHeight)
        || radius < 0.0 || halfheight < radius) return false;
    return FMath::Abs(Point.X) + radius <= halflength + tolerance
        && FMath::Abs(Point.Y) + radius <= halfwidth + tolerance
        && Point.Z - halfheight >= -tolerance
        && Point.Z <= CapsuleRoofLimit(Point.X, Point.Y, radius, halfheight) + tolerance;
}

inline bool containssphere(const fvector& point, double radius, double tolerance = .0001)
{
    return containscapsule(point, radius, radius, tolerance);
}

// only provisional venue-relative placements use this. sporting distances,
// goal apertures/heights, rider bodies and equipment retain their own sizes.
inline fvector scalelayout(const fvector& point)
{
    return point * linearscale;
}

inline fvector clampcapsule(const fvector& point, double radius, double halfheight)
{
    fvector result = point;
    Result.X = FMath::Clamp(Result.X, -halflength + radius, halflength - radius);
    Result.Y = FMath::Clamp(Result.Y, -halfwidth + radius, halfwidth - radius);
    Result.Z = FMath::Clamp(Result.Z, halfheight,
        CapsuleRoofLimit(Result.X, Result.Y, radius, halfheight));
    return result;
}

inline fvector clampsphere(const fvector& point, double radius)
{
    return clampcapsule(point, radius, radius);
}

// a sphere lies inside every plane inset by its radius. solving the first
// outward crossing is continuous even at extreme speed, and the intersection
// naturally covers face seams, the apex and the eave/wall junctions.
inline bool sweeproof(const fvector& start, const fvector& end, double radius,
                      float& hittime, fvector& hitnormal)
{
    bool bhit = false;
    const fvector delta = end - start;
    for (int32 face = 0; face < 4; ++face)
    {
        const fplane plane = roofplane(face);
        const fvector Normal(Plane.X, Plane.Y, Plane.Z);
        const double startdistance = Plane.PlaneDot(Start) + radius;
        const double outwardtravel = FVector::DotProduct(Delta, normal);
        if (outwardtravel <= 1.e-10) continue;
        const double time = FMath::Max(0.0, -startdistance / outwardtravel);
        if (time <= static_cast<double>(hittime) && time <= 1.0)
        {
            hittime = static_cast<float>(time);
            hitnormal = -normal;
            bhit = true;
        }
    }
    return bhit;
}

// on an edge several faces can be touched at once. resolve every outward
// component so a rebound cannot immediately escape through the adjacent face.
inline void reboundroof(fvector& velocity, const fvector& point, double radius,
                        double halfheight, double tolerance = 1.0)
{
    for (int32 face = 0; face < 4; ++face)
    {
        const fplane plane = roofplane(face);
        const fvector Normal(Plane.X, Plane.Y, Plane.Z);
        const double support = radius + FMath::Max(0.0, halfheight - radius) * Normal.Z;
        const double outwardspeed = FVector::DotProduct(Velocity, normal);
        if (Plane.PlaneDot(Point) + support >= -tolerance && outwardspeed > 0)
            velocity -= (1.0 + restitution) * outwardspeed * normal;
    }
}
}

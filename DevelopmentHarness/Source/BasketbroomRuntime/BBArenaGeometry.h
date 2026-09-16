#pragma once
#include "CoreMinimal.h"
#include "BBArenaDimensions.generated.h"

// Centimetres. The eave has no horizontal collision plane: the playable volume
// continues into a hollow four-face pyramid, enclosed only by its sloping net.
namespace BBArena
{
inline constexpr double RoofRise = ApexHeight - EaveHeight;
inline constexpr double Restitution = .75;

inline FPlane RoofPlane(int32 Face)
{
    const double Slope = RoofRise / (Face < 2 ? HalfLength : HalfWidth);
    const double Sign = Face % 2 == 0 ? 1.0 : -1.0;
    const FVector Normal = (Face < 2 ? FVector(Sign * Slope, 0, 1)
                                             : FVector(0, Sign * Slope, 1)).GetSafeNormal();
    return FPlane(Normal.X, Normal.Y, Normal.Z, ApexHeight * Normal.Z);
}

inline double CapsuleRoofLimit(double X, double Y, double Radius, double HalfHeight)
{
    const double SX = RoofRise / HalfLength, SY = RoofRise / HalfWidth;
    return ApexHeight - FMath::Max(SX * FMath::Abs(X) + Radius * FMath::Sqrt(1.0 + SX * SX),
                                   SY * FMath::Abs(Y) + Radius * FMath::Sqrt(1.0 + SY * SY))
                      - FMath::Max(0.0, HalfHeight - Radius);
}

// Unlike an apex-height box, this tests the entire capsule against every
// sloped roof face, the side/end nets and the trampoline floor. A one-micron
// tolerance admits numerical contact, never a meaningful excursion outside.
inline bool ContainsCapsule(const FVector& Point, double Radius, double HalfHeight,
                            double Tolerance = .0001)
{
    if (Point.ContainsNaN() || !FMath::IsFinite(Radius) || !FMath::IsFinite(HalfHeight)
        || Radius < 0.0 || HalfHeight < Radius) return false;
    return FMath::Abs(Point.X) + Radius <= HalfLength + Tolerance
        && FMath::Abs(Point.Y) + Radius <= HalfWidth + Tolerance
        && Point.Z - HalfHeight >= -Tolerance
        && Point.Z <= CapsuleRoofLimit(Point.X, Point.Y, Radius, HalfHeight) + Tolerance;
}

inline bool ContainsSphere(const FVector& Point, double Radius, double Tolerance = .0001)
{
    return ContainsCapsule(Point, Radius, Radius, Tolerance);
}

// Only provisional venue-relative placements use this. Sporting distances,
// goal apertures/heights, rider bodies and equipment retain their own sizes.
inline FVector ScaleLayout(const FVector& Point)
{
    return Point * LinearScale;
}

inline FVector ClampCapsule(const FVector& Point, double Radius, double HalfHeight)
{
    FVector Result = Point;
    Result.X = FMath::Clamp(Result.X, -HalfLength + Radius, HalfLength - Radius);
    Result.Y = FMath::Clamp(Result.Y, -HalfWidth + Radius, HalfWidth - Radius);
    Result.Z = FMath::Clamp(Result.Z, HalfHeight,
        CapsuleRoofLimit(Result.X, Result.Y, Radius, HalfHeight));
    return Result;
}

inline FVector ClampSphere(const FVector& Point, double Radius)
{
    return ClampCapsule(Point, Radius, Radius);
}

// A sphere lies inside every plane inset by its radius. Solving the first
// outward crossing is continuous even at extreme speed, and the intersection
// naturally covers face seams, the apex and the eave/wall junctions.
inline bool SweepRoof(const FVector& Start, const FVector& End, double Radius,
                      float& HitTime, FVector& HitNormal)
{
    bool bHit = false;
    const FVector Delta = End - Start;
    for (int32 Face = 0; Face < 4; ++Face)
    {
        const FPlane Plane = RoofPlane(Face);
        const FVector Normal(Plane.X, Plane.Y, Plane.Z);
        const double StartDistance = Plane.PlaneDot(Start) + Radius;
        const double OutwardTravel = FVector::DotProduct(Delta, Normal);
        if (OutwardTravel <= 1.e-10) continue;
        const double Time = FMath::Max(0.0, -StartDistance / OutwardTravel);
        if (Time <= static_cast<double>(HitTime) && Time <= 1.0)
        {
            HitTime = static_cast<float>(Time);
            HitNormal = -Normal;
            bHit = true;
        }
    }
    return bHit;
}

// On an edge several faces can be touched at once. Resolve every outward
// component so a rebound cannot immediately escape through the adjacent face.
inline void ReboundRoof(FVector& Velocity, const FVector& Point, double Radius,
                        double HalfHeight, double Tolerance = 1.0)
{
    for (int32 Face = 0; Face < 4; ++Face)
    {
        const FPlane Plane = RoofPlane(Face);
        const FVector Normal(Plane.X, Plane.Y, Plane.Z);
        const double Support = Radius + FMath::Max(0.0, HalfHeight - Radius) * Normal.Z;
        const double OutwardSpeed = FVector::DotProduct(Velocity, Normal);
        if (Plane.PlaneDot(Point) + Support >= -Tolerance && OutwardSpeed > 0)
            Velocity -= (1.0 + Restitution) * OutwardSpeed * Normal;
    }
}
}

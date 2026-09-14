#pragma once
#include "CoreMinimal.h"

// Centimetres. The eave has no horizontal collision plane: the playable volume
// continues into a hollow four-face pyramid, enclosed only by its sloping net.
namespace BBArena
{
inline constexpr double HalfLength = 6850.8;
inline constexpr double HalfWidth = 3200.4;
inline constexpr double EaveHeight = 4206.24;
inline constexpr double ApexHeight = 6309.36;
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

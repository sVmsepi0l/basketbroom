#include "BBBall.h"
#include "BBMatchState.h"
#include "BBRiderCharacter.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
// The authored hoops are visual toruses without engine collision. Sweep the
// ball against their exact expanded tube so a rim strike cannot become a goal.
bool SweepRims(const FVector& Start, const FVector& End, float BallRadius,
               float& HitTime, FVector& HitNormal)
{
    bool bHit = false;
    const FVector Delta = End - Start;
    for (int32 Side : {-1, 1})
    {
        const double PlaneX = Side * 6400.8;
        for (int32 Hoop = 0; Hoop < 4; ++Hoop)
        {
            const bool bSmall = Hoop == 3;
            const double Tube = bSmall ? 16.0 : 20.0;
            const double Major = (bSmall ? 198.12 : 335.28) + Tube;
            const FVector Center(PlaneX, bSmall ? 0.0 : (Hoop - 1) * 1066.8, bSmall ? 3048.0 : 2103.12);
            const double Expanded = BallRadius + Tube;
            if (FMath::Min(Start.X, End.X) > PlaneX + Expanded || FMath::Max(Start.X, End.X) < PlaneX - Expanded) continue;
            auto ClosestRingPoint = [&Center, Major](const FVector& Point)
            {
                const FVector Radial(0, Point.Y - Center.Y, Point.Z - Center.Z);
                return Center + Radial.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector) * Major;
            };
            // A physics step is at most 1/120 second. Samples spaced at no more
            // than a quarter expanded radius also cover high-speed releases.
            const int32 Samples = FMath::Clamp(FMath::CeilToInt(Delta.Size() / (Expanded * .25)), 1, 32);
            float Previous = 0.f;
            for (int32 Index = 0; Index <= Samples; ++Index)
            {
                const float Time = static_cast<float>(Index) / Samples;
                if (Time > HitTime) break;
                const FVector Point = Start + Delta * Time;
                const FVector Offset = Point - ClosestRingPoint(Point);
                if (Offset.SizeSquared() <= Expanded * Expanded)
                {
                    float Low = Previous, High = Time;
                    for (int32 Refine = 0; Refine < 8; ++Refine)
                    {
                        const float Mid = (Low + High) * .5f;
                        const FVector Probe = Start + Delta * Mid;
                        if (FVector::DistSquared(Probe, ClosestRingPoint(Probe)) <= Expanded * Expanded) High = Mid;
                        else Low = Mid;
                    }
                    const FVector Contact = Start + Delta * High;
                    const FVector Normal = (Contact - ClosestRingPoint(Contact)).GetSafeNormal();
                    if (FVector::DotProduct(Delta, Normal) < 0)
                    {
                        HitTime = High;
                        HitNormal = Normal;
                        bHit = true;
                    }
                    break;
                }
                Previous = Time;
            }
        }
    }
    return bHit;
}
}

ABBBall::ABBBall()
{
    PrimaryActorTick.bCanEverTick = true;
    bReplicates = true;
    bAlwaysRelevant = true;
    SetReplicateMovement(true);
    SetNetUpdateFrequency(30);
    USceneComponent* TransformRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BallRoot"));
    SetRootComponent(TransformRoot);
    TransformRoot->SetMobility(EComponentMobility::Movable);
    Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BallMesh"));
    Mesh->SetupAttachment(TransformRoot);
    Mesh->SetMobility(EComponentMobility::Movable);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere"));
    Mesh->SetStaticMesh(Sphere.Object);
    Mesh->SetCollisionProfileName(TEXT("NoCollision"));
    Mesh->SetCastShadow(true);
    for (const TCHAR* Path : {TEXT("/Basketbroom/Art/Materials/M_BB_BallQuaffle"),
         TEXT("/Basketbroom/Art/Materials/M_BB_BallQuark"), TEXT("/Basketbroom/Art/Materials/M_BB_Copper"),
         TEXT("/Basketbroom/Art/Materials/M_BB_BallSnitch"), TEXT("/Basketbroom/Art/Materials/M_BB_Iron")})
    {
        ConstructorHelpers::FObjectFinder<UMaterialInterface> Material(Path);
        BallMaterials.Add(Material.Object);
    }
}
void ABBBall::BeginPlay()
{
    Super::BeginPlay();
    Match = GetWorld()->GetGameState<ABBMatchState>();
    Home = GetActorLocation();
    LastLocation = Home;
    ChaseTime = BallIndex * 2.4f;
    OnRep_Appearance();
}
void ABBBall::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const
{
    Super::GetLifetimeReplicatedProps(Out);
    DOREPLIFETIME(ABBBall, BallIndex); DOREPLIFETIME(ABBBall, Holder);
    DOREPLIFETIME(ABBBall, CapturingRider); DOREPLIFETIME(ABBBall, CaptureProgress);
    DOREPLIFETIME(ABBBall, bActive); DOREPLIFETIME(ABBBall, ReturnIn);
    DOREPLIFETIME(ABBBall, BallStatus); DOREPLIFETIME(ABBBall, FlightVelocity);
}
FString ABBBall::DisplayName() const
{
    const TCHAR* Names[] = {TEXT("QUAFFLE"), TEXT("QUARK A"), TEXT("QUARK B"), TEXT("SNIPE"), TEXT("SNITCH"), TEXT("BLUDGER A"), TEXT("BLUDGER B")};
    return Names[FMath::Clamp(BallIndex, 0, 6)];
}
void ABBBall::OnRep_Appearance()
{
    Mesh->SetRelativeScale3D(FVector(Radius() / 50.f));
    const int32 MaterialIndex = IsBludger() ? 4 : Kind();
    if (BallMaterials.IsValidIndex(MaterialIndex)) Mesh->SetMaterial(0, BallMaterials[MaterialIndex]);
    SetActorHiddenInGame(!bActive);
}
void ABBBall::ResetBall(FVector Location)
{
    if (!HasAuthority() || Location.ContainsNaN()) return;
    SetActorLocation(Location);
    LastLocation = Location;
    FlightVelocity = FVector::ZeroVector;
    Holder = nullptr;
    CaptureProgress = 0;
    CapturingRider = nullptr;
    Cooldown = .25f;
    ForceNetUpdate();
}
void ABBBall::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!Match) Match = GetWorld()->GetGameState<ABBMatchState>();
    if (!HasAuthority())
    {
        // Interpolate only presentation: the actor root remains the replicated
        // authority transform. Held equipment follows the visible rider each
        // frame, including the local player's predicted camera movement.
        const FVector Target = IsValid(Holder) ? Holder->GetCarryLocation() : GetActorLocation();
        if (IsValid(Holder) || FVector::DistSquared(LastLocation, Target) > FMath::Square(1800.f)) LastLocation = Target;
        else LastLocation = FMath::VInterpTo(LastLocation, Target, DeltaSeconds, 16.f);
        Mesh->SetWorldLocation(LastLocation);
        return;
    }
    if (!Match || !Match->bLive || !bActive) { CaptureProgress = 0; CapturingRider = nullptr; return; }
    Cooldown = FMath::Max(0.f, Cooldown - DeltaSeconds);
    LastLocation = GetActorLocation();
    if (Holder)
    {
        SetActorLocation(Holder->GetCarryLocation());
        if (!IsChase() && GetActorLocation().Z > 4206.24f) Match->NoCrown(this);
        return;
    }
    if (IsChase())
    {
        // Constant bounded speed; copper Snipe is exactly 60% of Snitch speed.
        const float Speed = BallIndex == 3 ? 1020.f : 1700.f;
        ChaseTime += DeltaSeconds * (BallIndex == 3 ? .18f : .30f);
        FVector Target(FMath::Sin(ChaseTime) * 4200.f, FMath::Cos(ChaseTime * 1.31f) * 2300.f,
                       2450.f + FMath::Sin(ChaseTime * .73f) * 1100.f);
        SetActorLocation(FMath::VInterpConstantTo(GetActorLocation(), Target, DeltaSeconds, Speed));
        StepCapture(DeltaSeconds);
    }
    else
    {
        // Fixed maximum physics step keeps the whole-ball goal sweep stable at low FPS.
        float Remaining = FMath::Clamp(DeltaSeconds, 0.f, 1.f);
        while (Remaining > UE_SMALL_NUMBER && bActive && !Holder)
        {
            const float Step = FMath::Min(Remaining, 1.f / 120.f);
            StepFlight(Step);
            Remaining -= Step;
        }
    }
}
void ABBBall::StepCapture(float DeltaSeconds)
{
    if (!HasAuthority() || !IsValid(Match)) return;
    ABBRiderCharacter* Best = nullptr;
    float BestDist = FMath::Square(380.f);
    for (ABBRiderCharacter* Rider : Match->Riders)
    {
        if (!IsValid(Rider) || !Rider->bInteractHeld || !Match->CanInteract(Rider, this)) continue;
        const float Dist = FVector::DistSquared(GetActorLocation(), Rider->GetActorLocation());
        if (Dist < BestDist) { BestDist = Dist; Best = Rider; }
    }
    if (CapturingRider != Best) { CaptureProgress = 0; CapturingRider = Best; }
    if (!Best) { CaptureProgress = 0; return; }
    CaptureProgress = FMath::Min(1.f, CaptureProgress + DeltaSeconds);
    if (CaptureProgress >= 1.f && Cooldown <= 0 && Match->TryCatch(Best, this))
    {
        Cooldown = .25f;
        CaptureProgress = 0;
    }
}
void ABBBall::StepFlight(float Dt)
{
    if (!HasAuthority() || !IsValid(Match)) return;
    FVector Old = GetActorLocation();
    if (FlightVelocity.IsNearlyZero()) return;
    FlightVelocity.Z -= (IsBludger() ? 60.f : 380.f) * Dt;
    FVector P = Old + FlightVelocity * Dt;
    const float R = Radius();
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BasketbroomBallFlight), false, this);
    FCollisionObjectQueryParams StaticObjects;
    StaticObjects.AddObjectTypesToQuery(ECC_WorldStatic);
    FHitResult WorldHit;
    bool bCollision = GetWorld()->SweepSingleByObjectType(WorldHit, Old, P, FQuat::Identity,
        StaticObjects, FCollisionShape::MakeSphere(R), Query);
    float HitTime = bCollision ? WorldHit.Time : 1.f;
    FVector HitNormal = bCollision ? WorldHit.Normal : FVector::ZeroVector;
    ABBRiderCharacter* StruckRider = nullptr;
    if (SweepRims(Old, P, R, HitTime, HitNormal)) bCollision = true;
    if (IsBludger() && Cooldown <= 0 && FlightVelocity.SizeSquared() > FMath::Square(500.f))
    {
        FCollisionObjectQueryParams PawnObjects;
        PawnObjects.AddObjectTypesToQuery(ECC_Pawn);
        FHitResult RiderHit;
        if (GetWorld()->SweepSingleByObjectType(RiderHit, Old, P, FQuat::Identity,
            PawnObjects, FCollisionShape::MakeSphere(R), Query) && RiderHit.Time <= HitTime)
        {
            if (ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(RiderHit.GetActor()))
            {
                if (Match->Riders.Contains(Rider))
                {
                    StruckRider = Rider;
                    HitTime = RiderHit.Time;
                    HitNormal = RiderHit.Normal;
                    bCollision = true;
                }
            }
        }
    }
    if (bCollision)
    {
        P = FMath::Lerp(Old, P, HitTime) + HitNormal * .5f;
        const double IntoSurface = FVector::DotProduct(FlightVelocity, HitNormal);
        if (IntoSurface < 0) FlightVelocity = (FlightVelocity - 2.0 * IntoSurface * HitNormal) * .75f;
        if (StruckRider)
        {
            StruckRider->StunRemaining = FMath::Max(StruckRider->StunRemaining, 1.5f);
            StruckRider->ForceNetUpdate();
            Match->Release(StruckRider, FVector::ZeroVector);
            Cooldown = .7f;
            Match->Say(TEXT("Bludger impact - rider recovers in 1.5 seconds"));
        }
        ForceNetUpdate();
    }
    // Pickup/impact cooldown must not suppress a legitimate short-range goal.
    if (!IsBludger())
    {
        for (int32 Side : {-1, 1})
        {
            const float Plane = Side * (6400.8f + R);
            if (Old.X * Side < Plane * Side && P.X * Side >= Plane * Side)
            {
                float T = (Plane - Old.X) / (P.X - Old.X);
                FVector Cross = FMath::Lerp(Old, P, T);
                bool bGoal = false;
                if (BallIndex == 0)
                    for (float Y : {-1066.8f, 0.f, 1066.8f}) bGoal |= FVector2D(Cross.Y - Y, Cross.Z - 2103.12f).SizeSquared() < FMath::Square(335.28f - R);
                else bGoal = FVector2D(Cross.Y, Cross.Z - 3048.f).SizeSquared() < FMath::Square(198.12f - R);
                if (bGoal) { SetActorLocation(Cross); Match->Goal(this, Side > 0 ? 0 : 1); return; }
            }
        }
    }
    if (FMath::Abs(P.X) > 6850.8f - R) { P.X = FMath::Sign(P.X) * (6850.8f - R); FlightVelocity.X *= -.75f; }
    if (FMath::Abs(P.Y) > 3200.4f - R) { P.Y = FMath::Sign(P.Y) * (3200.4f - R); FlightVelocity.Y *= -.75f; }
    if (P.Z < R) { P.Z = R; FlightVelocity.Z = FMath::Max(390.f, FMath::Abs(FlightVelocity.Z) * .75f); }
    SetActorLocation(P);
    if (P.Z > 4206.24f) Match->NoCrown(this);
}

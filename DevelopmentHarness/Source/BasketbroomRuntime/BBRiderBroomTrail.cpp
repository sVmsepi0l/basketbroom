#include "BBRiderCharacter.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

namespace
{
BBBroomTrail::Vector TrailVector(const FVector& Value) { return {Value.X, Value.Y, Value.Z}; }
FVector TrailVector(const BBBroomTrail::Vector& Value) { return FVector(Value[0], Value[1], Value[2]); }

bool NormalizeTrailColor(FLinearColor& Color)
{
    std::array<float, 3> RGB{Color.R, Color.G, Color.B};
    if (!BBBroomTrail::normalize_color(RGB)) return false;
    Color = FLinearColor(RGB[0], RGB[1], RGB[2], 1.f);
    return true;
}
}

FLinearColor ABBRiderCharacter::GetBroomTrailColor() const
{
    return bUseCustomBroomTrailColor ? CustomBroomTrailColor
        : TeamIndex == 0 ? FLinearColor(.075f, 1.f, .61f) : FLinearColor(1.f, .245f, .045f);
}

void ABBRiderCharacter::SetBroomTrailColor(bool bUseCustomColor, FLinearColor Color)
{
    if (!IsLocallyControlled()) return;
    if (!bUseCustomColor) Color = FLinearColor::White;
    if (!NormalizeTrailColor(Color)) return;
    // Predict only this cosmetic preference. The owned RPC repeats validation;
    // its fields have no influence on team identity or earned boost authority.
    bUseCustomBroomTrailColor = bUseCustomColor;
    CustomBroomTrailColor = Color;
    if (HasAuthority()) ForceNetUpdate();
    else ServerSetBroomTrailColor(bUseCustomColor, Color);
}

void ABBRiderCharacter::ServerSetBroomTrailColor_Implementation(bool bUseCustomColor, FLinearColor Color)
{
    if (!HasAuthority()) return;
    if (!bUseCustomColor) Color = FLinearColor::White;
    if (!NormalizeTrailColor(Color)) return;
    if (bUseCustomBroomTrailColor == bUseCustomColor && CustomBroomTrailColor.Equals(Color, .0001f)) return;
    bUseCustomBroomTrailColor = bUseCustomColor;
    CustomBroomTrailColor = Color;
    ForceNetUpdate();
}

bool ABBRiderCharacter::DevelopmentQueueBroomTrailColor(bool bUseCustomColor, FLinearColor Color, bool bRawServerRPC)
{
#if UE_BUILD_SHIPPING
    return false;
#else
    if (!GetWorld() || GetWorld()->WorldType != EWorldType::PIE || !IsLocallyControlled()
        || !IsPlayerControlled() || PendingDevelopmentTrailColors.Num() >= MaxDevelopmentInputs)
        return false;
    // Preserve malformed payloads here: the ordinary setter/RPC must reject
    // them itself. This queue never writes replicated state or preferences.
    PendingDevelopmentTrailColors.Add({bUseCustomColor, Color, bRawServerRPC});
    return true;
#endif
}

void ABBRiderCharacter::InitializeBroomTrails()
{
    if (GetNetMode() == NM_DedicatedServer) return;
    // Both assets are already used/cooked by native equipment and sporting VFX.
    // The material's verified Tint/Glow parameters and instancing shader flag
    // provide bright original filaments without an external VFX dependency.
    UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Basketbroom/Art/Materials/M_BB_RiderIvory.M_BB_RiderIvory"));
    if (!Cylinder || !Base) return;
    TArray<FTransform> EmptySegments;
    EmptySegments.Init(FTransform(FQuat::Identity, GetActorLocation(), FVector::ZeroVector), BBBroomTrail::Capacity);
    for (int32 Strand = 0; Strand < 3; ++Strand)
    {
        UInstancedStaticMeshComponent* Part = NewObject<UInstancedStaticMeshComponent>(this,
            FName(*FString::Printf(TEXT("BroomTracer%d"), Strand)), RF_Transient);
        AddInstanceComponent(Part);
        Part->SetupAttachment(GetMesh());
        // History remains in the arena's world space as the broom moves on.
        Part->SetAbsolute(true, true, true);
        Part->SetWorldTransform(FTransform::Identity);
        Part->SetMobility(EComponentMobility::Movable);
        Part->SetStaticMesh(Cylinder);
        Part->SetMaterial(0, Base);
        Part->SetIsReplicated(false);
        Part->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Part->SetGenerateOverlapEvents(false);
        Part->SetCanEverAffectNavigation(false);
        Part->SetCastShadow(false);
        Part->SetAffectDynamicIndirectLighting(false);
        Part->SetAffectDistanceFieldLighting(false);
        Part->SetOwnerNoSee(true);
        Part->SetOnlyOwnerSee(false);
        Part->SetCullDistances(0, 40000);
        Part->ComponentTags.Add(TEXT("BB.BroomTracer"));
        Part->ComponentTags.Add(TEXT("BB.RiderVisual"));
        Part->SetVisibility(false);
        Part->RegisterComponent();
        Part->AddInstances(EmptySegments, false, false, false);
        BroomTrailStrands.Add(Part);
        BroomTrailMaterials.Add(Part->CreateDynamicMaterialInstance(0));
    }
    if (USceneComponent* Root = GetRootComponent())
        Root->TransformUpdated.AddWeakLambda(this,
            [this](USceneComponent*, EUpdateTransformFlags, ETeleportType Teleport)
            {
                if (Teleport != ETeleportType::None)
                {
                    // Match restarts/penalty placement use TeleportPhysics,
                    // including short moves below the distance-jump threshold.
                    ClearBroomTrails();
                    ++BroomTrailResetCount;
                }
            });
}

void ABBRiderCharacter::ClearBroomTrails()
{
    BroomTrailHistory.clear();
    BroomTrailVisibleSegments = 0;
    BroomTrailBoostBlend = 0.f;
    for (UInstancedStaticMeshComponent* Part : BroomTrailStrands)
        if (Part) Part->SetVisibility(false);
}

void ABBRiderCharacter::TickBroomTrails(float DeltaSeconds)
{
    if (BroomTrailStrands.Num() != 3 || !GetWorld()) return;
    const FLinearColor Hue = GetBroomTrailColor();
    const float Peak = FMath::Max3(Hue.R, Hue.G, Hue.B);
    const FLinearColor HotCore = FMath::Lerp(Hue, FLinearColor(Peak, Peak, Peak, 1.f), .28f);
    for (int32 Strand = 0; Strand < BroomTrailMaterials.Num(); ++Strand)
        if (UMaterialInstanceDynamic* Material = BroomTrailMaterials[Strand])
        {
            Material->SetVectorParameterValue(TEXT("Tint"), Strand == 0 ? HotCore : Hue);
            Material->SetScalarParameterValue(TEXT("Glow"), (Strand == 0 ? 4.f : 5.f) + 13.f * BroomTrailBoostBlend);
        }
    // Pausing freezes the existing path; a color-picker preview may still change
    // its material. Transformation/hidden riders cannot leave visible residue.
    if (GetWorld()->IsPaused()) return;
    const UCharacterMovementComponent* Movement = GetCharacterMovement();
    if (!Movement || Movement->MovementMode != MOVE_Flying || IsHidden() || TransformationRemaining > 0.f)
    {
        ClearBroomTrails();
        return;
    }
    if (BroomTrailLastTeam != TeamIndex)
    {
        ClearBroomTrails();
        BroomTrailLastTeam = TeamIndex;
    }
    const float Speed = GetVelocity().Size();
    const bool bEmit = FMath::IsFinite(Speed) && Speed > 80.f && !HasSpellMovementLock();
    // These are already replicated authoritative energy outputs; the effect
    // never predicts awards, spends charge or consults another player's input.
    const float TargetBoost = bEmit && CanUseFlightBoost()
        ? (FlightSuperRemaining > 0.f && FlightAccelerationScale > 1.01f ? 1.f
            : .55f * FMath::Clamp((FlightAccelerationScale - 1.f) / .35f, 0.f, 1.f)) : 0.f;
    BroomTrailBoostBlend = FMath::Lerp(BroomTrailBoostBlend, TargetBoost,
        1.f - FMath::Exp(-8.f * FMath::Clamp(DeltaSeconds, 0.f, .2f)));
    const double Now = GetWorld()->GetTimeSeconds();
    const FTransform Mount = GetMesh()->GetComponentTransform();
    // SourceArt/Equipment broom manifest puts the reed tips at X=-209.6 cm,
    // around Z=-15. Start inside that fan, with two narrower outer filaments.
    BBBroomTrail::Sample Head;
    Head.position = TrailVector(Mount.TransformPosition(FVector(-204.f, 0.f, -15.f)));
    Head.right = TrailVector(Mount.GetUnitAxis(EAxis::Y));
    Head.up = TrailVector(Mount.GetUnitAxis(EAxis::Z));
    Head.time = Now;
    if (BroomTrailHistory.advance(Head, bEmit, Speed)) ++BroomTrailResetCount;
    if (!bEmit && BroomTrailHistory.size() == 0)
    {
        BroomTrailVisibleSegments = 0;
        for (UInstancedStaticMeshComponent* Part : BroomTrailStrands) Part->SetVisibility(false);
        return;
    }
    const double Lifetime = BBBroomTrail::lifetime(BroomTrailBoostBlend);
    const float SpeedFade = FMath::Clamp((Speed - 40.f) / 700.f, .15f, 1.f);
    BroomTrailVisibleSegments = 0;
    for (int32 Strand = 0; Strand < 3; ++Strand)
    {
        FTransform Transforms[BBBroomTrail::Capacity];
        for (FTransform& Transform : Transforms)
            Transform = FTransform(FQuat::Identity, TrailVector(Head.position), FVector::ZeroVector);
        int32 Used = 0;
        auto TrailPointPosition = [Now, Lifetime, Strand](const BBBroomTrail::Sample& Point)
        {
            FVector Result = TrailVector(Point.position);
            if (Strand)
            {
                const double Age = FMath::Clamp((Now - Point.time) / Lifetime, 0.0, 1.0);
                const double Side = Strand == 1 ? -1.0 : 1.0;
                Result += TrailVector(Point.right).GetSafeNormal() * Side * (6.5 + 10.0 * Age);
                Result += TrailVector(Point.up).GetSafeNormal() * (FMath::Sin(Point.time * 13.0 + Side) * 3.0 * Age);
            }
            return Result;
        };
        auto Segment = [&](const BBBroomTrail::Sample& A, const BBBroomTrail::Sample& B)
        {
            if (Used >= static_cast<int32>(BBBroomTrail::Capacity)) return;
            const double Fade = BBBroomTrail::taper(Now - (A.time + B.time) * .5, Lifetime);
            const FVector Start = TrailPointPosition(A), End = TrailPointPosition(B), Along = End - Start;
            if (Fade <= .005 || Along.SizeSquared() < 1.) return;
            const double Radius = (Strand == 0 ? 1.6 + 2.2 * BroomTrailBoostBlend
                : .65 + 1.0 * BroomTrailBoostBlend) * Fade * SpeedFade;
            Transforms[Used++] = FTransform(FRotationMatrix::MakeFromZ(Along).ToQuat(),
                (Start + End) * .5, FVector(Radius / 50.0, Radius / 50.0, Along.Size() / 100.0));
        };
        for (std::size_t Index = 1; Index < BroomTrailHistory.size(); ++Index)
        {
            const auto& A = BroomTrailHistory.at(Index - 1);
            const auto& B = BroomTrailHistory.at(Index);
            if (Now - A.time <= Lifetime) Segment(A, B);
        }
        if (bEmit && BroomTrailHistory.size()) Segment(BroomTrailHistory.at(BroomTrailHistory.size() - 1), Head);
        UInstancedStaticMeshComponent* Part = BroomTrailStrands[Strand];
        Part->BatchUpdateInstancesTransforms(0, TArrayView<const FTransform>(Transforms, BBBroomTrail::Capacity), false, true, true);
        Part->SetVisibility(Used > 0);
        BroomTrailVisibleSegments += Used;
    }
}

TArray<float> ABBRiderCharacter::DevelopmentGetBroomTrailState() const
{
#if !UE_BUILD_SHIPPING
    if (GetWorld() && GetWorld()->WorldType == EWorldType::PIE)
    {
        const FLinearColor Color = GetBroomTrailColor();
        return {static_cast<float>(BroomTrailHistory.size()), static_cast<float>(BroomTrailVisibleSegments),
            static_cast<float>(BroomTrailResetCount), BroomTrailBoostBlend,
            static_cast<float>(BBBroomTrail::lifetime(BroomTrailBoostBlend)), Color.R, Color.G, Color.B,
            bUseCustomBroomTrailColor ? 1.f : 0.f, static_cast<float>(BroomTrailStrands.Num())};
    }
#endif
    return {};
}

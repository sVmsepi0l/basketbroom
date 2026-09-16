#include "BBSpellVisual.h"
#include "BBSpellCatalog.h"
#include "CollisionQueryParams.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

ABBSpellVisual::ABBSpellVisual()
{
    PrimaryActorTick.bCanEverTick = true;
    bReplicates = true;
    bAlwaysRelevant = true;
    SetReplicateMovement(false);
    SetNetUpdateFrequency(30.f);
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("SpellVisualRoot")));
    GetRootComponent()->SetMobility(EComponentMobility::Movable);
    Beam = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CastBeam"));
    Impact = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CastImpact"));
    ImpactRays = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ImpactRays"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    // Existing original material is cooked for instancing and exposes Tint/Glow.
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Material(TEXT("/Basketbroom/Art/Materials/M_BB_RiderIvory.M_BB_RiderIvory"));
    Beam->SetStaticMesh(Cylinder.Object);
    Impact->SetStaticMesh(Sphere.Object);
    ImpactRays->SetStaticMesh(Cylinder.Object);
    for (UStaticMeshComponent* Part : {Beam.Get(), Impact.Get(), static_cast<UStaticMeshComponent*>(ImpactRays.Get())})
    {
        Part->SetupAttachment(GetRootComponent());
        Part->SetMobility(EComponentMobility::Movable);
        Part->SetMaterial(0, Material.Object);
        Part->SetCollisionProfileName(TEXT("NoCollision"));
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Part->SetGenerateOverlapEvents(false);
        Part->SetCanEverAffectNavigation(false);
        Part->SetCastShadow(false);
        Part->ComponentTags.Add(TEXT("BB.Spell.Cosmetic"));
        Part->SetVisibility(false);
    }
    for (int32 Index = 0; Index < 12; ++Index)
    {
        const float Angle = Index * UE_TWO_PI / 12.f;
        const FVector Direction(0.f, FMath::Cos(Angle), FMath::Sin(Angle));
        ImpactRays->AddInstance(FTransform(FRotationMatrix::MakeFromZ(Direction).ToQuat(),
            Direction * 28.f, FVector(.018, .018, .18)));
    }
}

ABBSpellVisual* ABBSpellVisual::Spawn(UWorld* World, FVector Start, FVector End, int32 SpellIndex, bool bBlocked)
{
    if (!World || World->GetNetMode() == NM_Client || Start.ContainsNaN() || End.ContainsNaN()
        || SpellIndex < 0 || SpellIndex >= BBSpellCatalog::Count()) return nullptr;
    const FTransform Transform(FRotator::ZeroRotator, (Start + End) * .5f);
    ABBSpellVisual* Visual = World->SpawnActorDeferred<ABBSpellVisual>(StaticClass(), Transform,
        nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!Visual) return nullptr;
    Visual->StartPoint = Start;
    Visual->EndPoint = End;
    Visual->VisualSpellIndex = SpellIndex;
    Visual->bWasBlocked = bBlocked;
    Visual->SetFlags(RF_Transient);
    Visual->FinishSpawning(Transform);
    Visual->ForceNetUpdate();
    return Visual;
}

void ABBSpellVisual::BeginPlay()
{
    Super::BeginPlay();
    GlowMaterial = Beam->CreateDynamicMaterialInstance(0);
    if (GlowMaterial)
    {
        Impact->SetMaterial(0, GlowMaterial);
        ImpactRays->SetMaterial(0, GlowMaterial);
    }
    OnRep_Visual();
    if (HasAuthority()) SetLifeSpan(.8f);
}

void ABBSpellVisual::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABBSpellVisual, StartPoint);
    DOREPLIFETIME(ABBSpellVisual, EndPoint);
    DOREPLIFETIME(ABBSpellVisual, VisualSpellIndex);
    DOREPLIFETIME(ABBSpellVisual, bWasBlocked);
}

void ABBSpellVisual::OnRep_Visual()
{
    const FVector TraceDirection = EndPoint - StartPoint;
    const double TraceLength = TraceDirection.Size();
    const FRotator AimRotation = TraceDirection.IsNearlyZero() ? FRotator::ZeroRotator : TraceDirection.Rotation();
    // Match the owner's visible wand tip. Starting an opaque cylinder at the
    // camera made its near end fill the reticle. Keep the actual trace endpoints
    // unchanged: this offset affects presentation only, never hit detection.
    // Short casts shorten the offset so it cannot extend past a nearby impact.
    const double MuzzleScale = FMath::Min(1.0, TraceLength / 180.0);
    VisualStartPoint = StartPoint + AimRotation.RotateVector(FVector(87, 30, -17) * MuzzleScale);
    // The lateral offset can cross a side wall even when the eye-origin ray
    // reaches its endpoint correctly. Clip only this cosmetic origin against
    // visible geometry; pawn bodies do not obstruct their own equipment.
    if (GetWorld())
    {
        FCollisionQueryParams MuzzleQuery(SCENE_QUERY_STAT(BasketbroomVisualMuzzle), false, this);
        for (TActorIterator<APawn> It(GetWorld()); It; ++It) MuzzleQuery.AddIgnoredActor(*It);
        FHitResult MuzzleHit;
        if (GetWorld()->LineTraceSingleByChannel(MuzzleHit, StartPoint, VisualStartPoint, ECC_Visibility, MuzzleQuery))
        {
            const FVector MuzzleDirection = (VisualStartPoint - StartPoint).GetSafeNormal();
            const double SafeDistance = MuzzleHit.bStartPenetrating ? 0.0 : FMath::Max(0.0, static_cast<double>(MuzzleHit.Distance) - 3.0);
            VisualStartPoint = StartPoint + MuzzleDirection * SafeDistance;
        }
    }
    const FVector Direction = EndPoint - VisualStartPoint;
    BeamLength = Direction.Size();
    Beam->SetWorldLocation((VisualStartPoint + EndPoint) * .5f);
    Beam->SetWorldRotation(FRotationMatrix::MakeFromZ(Direction.GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector)).Rotator());
    Impact->SetWorldLocation(EndPoint);
    ImpactRays->SetWorldLocation(EndPoint);
    ImpactRays->SetWorldRotation(Direction.IsNearlyZero() ? FRotator::ZeroRotator : Direction.Rotation());
    FLinearColor Color(1.f, .18f, .055f);
    if (VisualSpellIndex == 1 || bWasBlocked) Color = FLinearColor(.15f, .58f, 1.f);
    else if (VisualSpellIndex >= 6 && VisualSpellIndex <= 13) Color = FLinearColor(.55f, .18f, 1.f);
    else if (VisualSpellIndex >= 26 && VisualSpellIndex <= 28) Color = FLinearColor(.18f, 1.f, .26f);
    else if (VisualSpellIndex >= 29) Color = FLinearColor(.38f, .8f, 1.f);
    else if (VisualSpellIndex == 19) Color = FLinearColor(.8f, .92f, 1.f);
    if (GlowMaterial) GlowMaterial->SetVectorParameterValue(TEXT("Tint"), Color);
    // Set presentation scale before showing newly spawned/replicated components;
    // default 100 cm primitives must never appear for the first rendered frame.
    UpdateVisualScale();
}

void ABBSpellVisual::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    VisualAge += DeltaSeconds;
    UpdateVisualScale();
}

void ABBSpellVisual::UpdateVisualScale()
{
    const float Remaining = FMath::Clamp(1.f - VisualAge / .55f, 0.f, 1.f);
    const float Width = .004f + .024f * Remaining * Remaining;
    Beam->SetWorldScale3D(FVector(Width, Width, BeamLength / 100.f));
    Impact->SetWorldScale3D(FVector((bWasBlocked ? .28f : .16f) * Remaining));
    ImpactRays->SetWorldScale3D(FVector(1.f + VisualAge * 2.2f));
    if (GlowMaterial) GlowMaterial->SetScalarParameterValue(TEXT("Glow"), Remaining * 2.5f);
    // A nearly eye-level clamped muzzle would recreate the large near-camera
    // cylinder cap. Preserve the recorded impact but omit that short beam.
    const bool bMuzzleClearOfCamera = FVector::DistSquared(VisualStartPoint, StartPoint) >= FMath::Square(35.f);
    Beam->SetVisibility(Remaining > 0.f && BeamLength > 1.f && bMuzzleClearOfCamera);
    Impact->SetVisibility(Remaining > 0.f);
    ImpactRays->SetVisibility(Remaining > 0.f);
}

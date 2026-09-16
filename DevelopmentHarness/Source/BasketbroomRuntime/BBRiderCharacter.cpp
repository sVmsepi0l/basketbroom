#include "BBRiderCharacter.h"
#include "BBArenaGeometry.h"

#include "BBMatchState.h"
#include "BBSpellCatalog.h"
#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/MeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

float UBBFlyingMovementComponent::GetMaxSpeed() const
{
    const ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(GetOwner());
    const ABBMatchState* Match = GetWorld() ? GetWorld()->GetGameState<ABBMatchState>() : nullptr;
    if (Match && Match->bPenaltyShotActive) return Match->CanMoveDuringPenalty(Rider) ? Super::GetMaxSpeed() : 0.f;
    if (Rider && Rider->HasSpellMovementLock()) return 0.f;
    return Super::GetMaxSpeed() * (Rider && Rider->ImpedimentRemaining > 0.f ? .35f : 1.f)
        * (Rider && Rider->CanUseFlightBoost() && FlightThrottle > 12 && FlightBrake < 3 ? Rider->FlightAccelerationScale : 1.f)
        * (1.f - FlightBrake / 255.f);
}

float UBBFlyingMovementComponent::GetMaxAcceleration() const
{
    const ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(GetOwner());
    const ABBMatchState* Match = GetWorld() ? GetWorld()->GetGameState<ABBMatchState>() : nullptr;
    if (Match && Match->bPenaltyShotActive) return Match->CanMoveDuringPenalty(Rider) ? Super::GetMaxAcceleration() : 0.f;
    if (Rider && Rider->HasSpellMovementLock()) return 0.f;
    return Super::GetMaxAcceleration() * (Rider && Rider->ImpedimentRemaining > 0.f ? .35f : 1.f)
        * (Rider && Rider->CanUseFlightBoost() && FlightThrottle > 12 && FlightBrake < 3 ? Rider->FlightAccelerationScale : 1.f)
        * (1.f - FlightBrake / 255.f);
}

void UBBFlyingMovementComponent::PhysFlying(float DeltaTime, int32 Iterations)
{
    const ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(GetOwner());
    const ABBMatchState* Match = GetWorld() ? GetWorld()->GetGameState<ABBMatchState>() : nullptr;
    // Apply before prediction/server movement: a saved move or residual velocity
    // must not carry the shooter off the mark or move a waiting rider.
    if (Match && Match->bPenaltyShotActive && !Match->CanMoveDuringPenalty(Rider))
    {
        StopMovementImmediately();
        return;
    }
    if (Rider && Rider->HasSpellMovementLock() && !(Match && Match->bPenaltyShotActive))
    {
        StopMovementImmediately();
        return;
    }
    const FVector EntryVelocity = Velocity;
    // Sporting Imperio preserves the pawn/controller and normal RPC ownership.
    // Reverse horizontal acceleration inside the shared movement simulation,
    // then restore the caller's input so saved moves cannot be inverted twice.
    const FVector OriginalAcceleration = Acceleration;
    if (Rider && Rider->ImperioRemaining > 0.f && !(Match && Match->bPenaltyShotActive))
    {
        Acceleration.X *= -1.f;
        Acceleration.Y *= -1.f;
    }
    const float PreviousBrake = BrakingDecelerationFlying;
    BrakingDecelerationFlying += FlightBrake / 255.f * 9000.f;
    if (FlightBrake) Velocity *= FMath::Exp(-8.f * FlightBrake / 255.f * DeltaTime);
    Super::PhysFlying(DeltaTime, Iterations);
    BrakingDecelerationFlying = PreviousBrake;
    Acceleration = OriginalAcceleration;
    if (!HasValidData() || !Rider || MovementMode != MOVE_Flying) return;

    const UCapsuleComponent* Capsule = Rider->GetCapsuleComponent();
    const double Radius = Capsule->GetScaledCapsuleRadius();
    const double HalfHeight = Capsule->GetScaledCapsuleHalfHeight();
    const FVector Lower(-BBArena::HalfLength + Radius, -BBArena::HalfWidth + Radius, HalfHeight);
    const FVector Upper(BBArena::HalfLength - Radius, BBArena::HalfWidth - Radius, BBArena::ApexHeight - HalfHeight);
    const FVector Current = UpdatedComponent->GetComponentLocation();
    const FVector Bounded = BBArena::ClampCapsule(Current, Radius, HalfHeight);
    if (!Current.Equals(Bounded, .01))
    {
        // CharacterMovement's sweep handles normal flight into the authored
        // roof. This explicit convex bound also covers prediction correction,
        // high-speed saved moves and missing/late collision geometry.
        FHitResult Hit;
        SafeMoveUpdatedComponent(Bounded - Current, UpdatedComponent->GetComponentQuat(), false, Hit);
    }

    for (int32 Axis = 0; Axis < 3; ++Axis)
    {
        const double Speed = FMath::Max(FMath::Abs(EntryVelocity[Axis]), FMath::Abs(Velocity[Axis]));
        if (Bounded[Axis] <= Lower[Axis] + 3.0 && (EntryVelocity[Axis] < 0 || Velocity[Axis] < 0))
            Velocity[Axis] = Speed * BBArena::Restitution;
        else if (Axis < 2 && Bounded[Axis] >= Upper[Axis] - 3.0 && (EntryVelocity[Axis] > 0 || Velocity[Axis] > 0))
            Velocity[Axis] = -Speed * BBArena::Restitution;
    }
    // Restore the incoming normal component that the physical sweep can have
    // removed, then rebound against every touching sloped face. This runs in
    // native server movement and the client's matching predicted simulation.
    bool bRoofImpact = false;
    for (int32 Face = 0; Face < 4; ++Face)
    {
        const FPlane Plane = BBArena::RoofPlane(Face);
        const FVector Normal(Plane.X, Plane.Y, Plane.Z);
        const double Support = Radius + FMath::Max(0.0, HalfHeight - Radius) * Normal.Z;
        bRoofImpact |= Plane.PlaneDot(Bounded) + Support >= -3.0
            && FVector::DotProduct(EntryVelocity, Normal) > 0;
    }
    if (bRoofImpact)
    {
        FVector Rebound = EntryVelocity;
        BBArena::ReboundRoof(Rebound, Bounded, Radius, HalfHeight, 3.0);
        // Roof/wall seams must satisfy the vertical net at the same time.
        if (FMath::Abs(Bounded.X) >= BBArena::HalfLength - Radius - 3.0 && Rebound.X * Bounded.X > 0) Rebound.X *= -.75;
        if (FMath::Abs(Bounded.Y) >= BBArena::HalfWidth - Radius - 3.0 && Rebound.Y * Bounded.Y > 0) Rebound.Y *= -.75;
        Velocity = Rebound;
    }
}

ABBRiderCharacter::ABBRiderCharacter(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer.SetDefaultSubobjectClass<UBBFlyingMovementComponent>(ACharacter::CharacterMovementComponentName))
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bTickEvenWhenPaused = true;
    bReplicates = true;
    SetReplicateMovement(true);
    SetNetUpdateFrequency(40.0f);
    SetMinNetUpdateFrequency(15.0f);
    bUseControllerRotationPitch = false;
    bUseControllerRotationRoll = false;
    bUseControllerRotationYaw = true;
    BaseEyeHeight = 72.0f;
    GetCapsuleComponent()->InitCapsuleSize(34.0f, 96.0f);

    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->DefaultLandMovementMode = MOVE_Flying;
    Movement->DefaultWaterMovementMode = MOVE_Flying;
    Movement->MaxFlySpeed = 2100.0f;
    Movement->MaxAcceleration = 3600.0f;
    Movement->BrakingDecelerationFlying = 3000.0f;
    Movement->bUseSeparateBrakingFriction = true;
    Movement->BrakingFriction = 0.5f;
    Movement->BrakingFrictionFactor = 1.0f;
    Movement->GravityScale = 0.0f;
    Movement->bOrientRotationToMovement = false;
    Movement->NetworkSmoothingMode = ENetworkSmoothingMode::Exponential;

    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("FlightCamera"));
    Camera->SetupAttachment(GetCapsuleComponent());
    Camera->SetRelativeLocation(FVector(0.0f, 0.0f, BaseEyeHeight));
    Camera->bUsePawnControlRotation = true;
    Camera->FieldOfView = 92.0f;

    // Keep the Character mesh origin/facing unchanged: equipment and the body
    // share native remote-proxy smoothing. The baked flight pose already fits it.
    GetMesh()->SetRelativeLocation(FVector::ZeroVector);
    GetMesh()->SetRelativeRotation(FRotator::ZeroRotator);
    GetMesh()->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    GetMesh()->SetGenerateOverlapEvents(false);
    GetMesh()->SetCanEverAffectNavigation(false);

    static ConstructorHelpers::FObjectFinder<USkeletalMesh> RiderMesh(TEXT("/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"));
    static ConstructorHelpers::FObjectFinder<UAnimSequence> FlightPose(TEXT("/Basketbroom/Art/Characters/A_BB_SeatedFlight_Quinn.A_BB_SeatedFlight_Quinn"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyTeal1(TEXT("/Basketbroom/Art/Characters/MI_BB_Quinn_Teal_01.MI_BB_Quinn_Teal_01"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyTeal2(TEXT("/Basketbroom/Art/Characters/MI_BB_Quinn_Teal_02.MI_BB_Quinn_Teal_02"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyCopper1(TEXT("/Basketbroom/Art/Characters/MI_BB_Quinn_Copper_01.MI_BB_Quinn_Copper_01"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyCopper2(TEXT("/Basketbroom/Art/Characters/MI_BB_Quinn_Copper_02.MI_BB_Quinn_Copper_02"));
    bSkeletalRiderEnabled = RiderMesh.Succeeded() && FlightPose.Succeeded() &&
        BodyTeal1.Succeeded() && BodyTeal2.Succeeded() && BodyCopper1.Succeeded() && BodyCopper2.Succeeded();
    if (bSkeletalRiderEnabled)
    {
        SkeletalTealMaterials = {BodyTeal1.Object, BodyTeal2.Object};
        SkeletalCopperMaterials = {BodyCopper1.Object, BodyCopper2.Object};
        GetMesh()->SetSkeletalMeshAsset(RiderMesh.Object);
        // This persists single-node animation data safely through registration.
        GetMesh()->OverrideAnimationData(FlightPose.Object, true, true, 0.f, 1.f);
        GetMesh()->SetOwnerNoSee(true);
        GetMesh()->SetOnlyOwnerSee(false);
        GetMesh()->SetCastShadow(true);
        GetMesh()->bEnableUpdateRateOptimizations = true;
        GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
        GetMesh()->SetMaterial(0, BodyTeal1.Object);
        GetMesh()->SetMaterial(1, BodyTeal2.Object);
        GetMesh()->ComponentTags.Add(TEXT("BB.SkeletalRider"));
    }

    static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomWoodMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomWood.SM_BB_BroomWood"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomLeatherMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomLeather.SM_BB_BroomLeather"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomBristlesMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomBristles.SM_BB_BroomBristles"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomCopperMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomCopper.SM_BB_BroomCopper"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomAccentMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomAccent.SM_BB_BroomAccent"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> WandWoodMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_WandWood.SM_BB_WandWood"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> WandLeatherMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_WandLeather.SM_BB_WandLeather"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> WandCopperMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_WandCopper.SM_BB_WandCopper"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentWood(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipWood.M_BB_EquipWood"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentLeather(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipLeather.M_BB_EquipLeather"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentBristles(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipBristles.M_BB_EquipBristles"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentCopper(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipCopper.M_BB_EquipCopper"));

    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cone(TEXT("/Engine/BasicShapes/Cone.Cone"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Teal(TEXT("/Basketbroom/Art/Materials/M_BB_RiderTeal.M_BB_RiderTeal"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Copper(TEXT("/Basketbroom/Art/Materials/M_BB_RiderCopper.M_BB_RiderCopper"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Face(TEXT("/Basketbroom/Art/Materials/M_BB_RiderFace.M_BB_RiderFace"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Pants(TEXT("/Basketbroom/Art/Materials/M_BB_RiderPants.M_BB_RiderPants"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Leather(TEXT("/Basketbroom/Art/Materials/M_BB_BroomLeather.M_BB_BroomLeather"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Wood(TEXT("/Basketbroom/Art/Materials/M_BB_BroomWood.M_BB_BroomWood"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Bristles(TEXT("/Basketbroom/Art/Materials/M_BB_RiderBristles.M_BB_RiderBristles"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Ivory(TEXT("/Basketbroom/Art/Materials/M_BB_RiderIvory.M_BB_RiderIvory"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Metal(TEXT("/Basketbroom/Art/Materials/M_BB_Copper.M_BB_Copper"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Light(TEXT("/Basketbroom/Art/Materials/M_BB_TealLight.M_BB_TealLight"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Iron(TEXT("/Basketbroom/Art/Materials/M_BB_Iron.M_BB_Iron"));
    TealMaterial = Teal.Object;
    CopperMaterial = Copper.Object;

    auto Part = [this](const FName Name, UStaticMesh* Shape, UMaterialInterface* Material,
                      const FVector Location, const FVector Scale, const FRotator Rotation,
                      bool bCockpit, bool bUniform = false)
    {
        UStaticMeshComponent* Component = CreateDefaultSubobject<UStaticMeshComponent>(Name);
        Component->SetupAttachment(bCockpit ? static_cast<USceneComponent*>(Camera.Get()) : GetMesh());
        Component->SetStaticMesh(Shape);
        Component->SetMaterial(0, Material);
        Component->SetRelativeLocation(Location);
        Component->SetRelativeScale3D(Scale);
        Component->SetRelativeRotation(Rotation);
        Component->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
        Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Component->SetGenerateOverlapEvents(false);
        Component->SetCanEverAffectNavigation(false);
        Component->SetOnlyOwnerSee(bCockpit);
        Component->SetOwnerNoSee(!bCockpit);
        Component->SetCastShadow(!bCockpit);
        Component->ComponentTags.Add(bCockpit ? TEXT("BB.Cockpit") : TEXT("BB.RiderVisual"));
        if (bUniform)
        {
            Component->ComponentTags.Add(TEXT("BB.Uniform"));
            UniformParts.Add(Component);
        }
        return Component;
    };

    if (!bSkeletalRiderEnabled)
    {
        Part(TEXT("Tunic"), Sphere.Object, Teal.Object, FVector(8, 0, 33), FVector(.42, .46, .69), FRotator(-12, 0, 0), false, true);
        Part(TEXT("Head"), Sphere.Object, Face.Object, FVector(23, 0, 81), FVector(.27, .25, .31), FRotator::ZeroRotator, false);
        Part(TEXT("Helmet"), Sphere.Object, Teal.Object, FVector(21, 0, 92), FVector(.30, .28, .19), FRotator::ZeroRotator, false, true);
        Part(TEXT("ChestMark"), Sphere.Object, Ivory.Object, FVector(30, 0, 40), FVector(.027, .17, .24), FRotator(-12, 0, 0), false);
    }
    // Cosmetic authored equipment shares the existing owner/remote Part settings.
    for (const bool bCockpit : {false, true})
    {
        const FString Prefix = bCockpit ? TEXT("CockpitBroom") : TEXT("Broom");
        const FVector Mount = bCockpit ? FVector(55, 30, -48) : FVector::ZeroVector;
        Part(FName(*(Prefix + TEXT("Wood"))), BroomWoodMesh.Object, EquipmentWood.Object,
             Mount, FVector::OneVector, FRotator::ZeroRotator, bCockpit);
        Part(FName(*(Prefix + TEXT("Leather"))), BroomLeatherMesh.Object, EquipmentLeather.Object,
             Mount, FVector::OneVector, FRotator::ZeroRotator, bCockpit);
        Part(FName(*(Prefix + TEXT("Bristles"))), BroomBristlesMesh.Object, EquipmentBristles.Object,
             Mount, FVector::OneVector, FRotator::ZeroRotator, bCockpit);
        Part(FName(*(Prefix + TEXT("Copper"))), BroomCopperMesh.Object, EquipmentCopper.Object,
             Mount, FVector::OneVector, FRotator::ZeroRotator, bCockpit);
        Part(FName(*(Prefix + TEXT("Accent"))), BroomAccentMesh.Object, Teal.Object,
             Mount, FVector::OneVector, FRotator::ZeroRotator, bCockpit, true);
    }
    for (int32 Side : {-1, 1})
    {
        if (bSkeletalRiderEnabled) continue;
        const FString Prefix = Side < 0 ? TEXT("Left") : TEXT("Right");
        Part(FName(*(Prefix + TEXT("Arm"))), Sphere.Object, Teal.Object, FVector(32, Side * 24, 32), FVector(.66, .15, .17), FRotator(-40, 0, 0), false, true);
        Part(FName(*(Prefix + TEXT("Glove"))), Sphere.Object, Leather.Object, FVector(56, Side * 21, 11), FVector(.17, .14, .15), FRotator::ZeroRotator, false);
        Part(FName(*(Prefix + TEXT("BentLeg"))), Sphere.Object, Pants.Object, FVector(8, Side * 19, -18), FVector(.50, .18, .24), FRotator(-30, 0, 0), false);
        Part(FName(*(Prefix + TEXT("Boot"))), Sphere.Object, Leather.Object, FVector(29, Side * 20, -49), FVector(.25, .20, .48), FRotator(-10, 0, 0), false);
    }

    Part(TEXT("CockpitCharmMount"), Cylinder.Object, EquipmentCopper.Object, FVector(145, 30, -50.5), FVector(.14, .14, .03), FRotator::ZeroRotator, true);
    Part(TEXT("CockpitFlightCharm"), Sphere.Object, Light.Object, FVector(145, 30, -47.6), FVector(.09, .08, .045), FRotator::ZeroRotator, true);

    // Original 44 cm wand: tapered wood, padded grip and copper collar.
    // Cosmetic owner/remote copies use the existing equipment filtering.
    for (bool bCockpit : {false, true})
    {
        const FString Prefix = bCockpit ? TEXT("CockpitWand") : TEXT("RiderWand");
        const FVector Start = bCockpit ? FVector(45, 38, -29) : FVector(43, 10, 14);
        const FVector Direction = (bCockpit ? FVector(42, -8, 12) : FVector(44, 2, 7)).GetSafeNormal();
        const FRotator Rotation = FRotationMatrix::MakeFromZ(Direction).Rotator();
        WandParts.Add(Part(FName(*(Prefix + TEXT("Wood"))), WandWoodMesh.Object,
            EquipmentWood.Object, Start, FVector::OneVector, Rotation, bCockpit));
        WandParts.Add(Part(FName(*(Prefix + TEXT("Grip"))), WandLeatherMesh.Object,
            EquipmentLeather.Object, Start, FVector::OneVector, Rotation, bCockpit));
        WandParts.Add(Part(FName(*(Prefix + TEXT("Collar"))), WandCopperMesh.Object,
            EquipmentCopper.Object, Start, FVector::OneVector, Rotation, bCockpit));
    }
    WandLight = Part(TEXT("WandLumos"), Sphere.Object, Light.Object, FVector(87, 30, -17),
        FVector(.045), FRotator::ZeroRotator, true);
    WandLight->SetVisibility(false);
    WandLamp = CreateDefaultSubobject<UPointLightComponent>(TEXT("WandLumosLamp"));
    WandLamp->SetupAttachment(GetMesh());
    WandLamp->SetRelativeLocation(FVector(88, 12, 21));
    WandLamp->SetLightColor(FLinearColor(.68f, .87f, 1.f));
    WandLamp->SetIntensity(600.f);
    WandLamp->SetAttenuationRadius(450.f);
    WandLamp->SetCastShadows(false);
    WandLamp->SetVisibility(false);
    ShieldVisual = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ProtegoArcs"));
    ShieldVisual->SetupAttachment(GetMesh());
    ShieldVisual->SetStaticMesh(Cylinder.Object);
    // Ivory already carries the cooked instanced-mesh usage flag. Its shared
    // Tint/Glow parameters supply the blue energy without runtime shader edits.
    ShieldVisual->SetMaterial(0, Ivory.Object);
    ShieldVisual->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
    ShieldVisual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ShieldVisual->SetGenerateOverlapEvents(false);
    ShieldVisual->SetCanEverAffectNavigation(false);
    ShieldVisual->SetCastShadow(false);
    ShieldVisual->SetOwnerNoSee(true);
    ShieldVisual->SetOnlyOwnerSee(false);
    ShieldVisual->SetVisibility(false);
    ShieldVisual->ComponentTags.Add(TEXT("BB.Spell.Shield"));
    // Other riders see the surrounding shield. Its world-space great circles
    // must not become large vertical bars through the owner's camera.
    for (int32 Plane = 0; Plane < 3; ++Plane)
        for (int32 Segment = 0; Segment < 16; ++Segment)
        {
            const float A = Segment * UE_TWO_PI / 16.f, B = A + UE_TWO_PI / 20.f;
            auto Point = [Plane](float Angle)
            {
                const float C = FMath::Cos(Angle) * 112.f, S = FMath::Sin(Angle) * 112.f;
                return FVector(Plane == 0 ? 0.f : C, Plane == 1 ? 0.f : (Plane == 0 ? C : S),
                    12.f + (Plane == 2 ? 0.f : S));
            };
            const FVector APos = Point(A), BPos = Point(B), Axis = BPos - APos;
            ShieldVisual->AddInstance(FTransform(FRotationMatrix::MakeFromZ(Axis).ToQuat(),
                (APos + BPos) * .5f, FVector(.022, .022, Axis.Size() / 100.f)));
        }
    CockpitShieldVisual = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("CockpitProtegoArcs"));
    CockpitShieldVisual->SetupAttachment(Camera);
    CockpitShieldVisual->SetStaticMesh(Cylinder.Object);
    CockpitShieldVisual->SetMaterial(0, Ivory.Object);
    CockpitShieldVisual->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
    CockpitShieldVisual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    CockpitShieldVisual->SetGenerateOverlapEvents(false);
    CockpitShieldVisual->SetCanEverAffectNavigation(false);
    CockpitShieldVisual->SetCastShadow(false);
    CockpitShieldVisual->SetOnlyOwnerSee(true);
    CockpitShieldVisual->SetOwnerNoSee(false);
    CockpitShieldVisual->SetVisibility(false);
    CockpitShieldVisual->ComponentTags.Add(TEXT("BB.Spell.Shield.Cockpit"));
    // Four fine corner arcs at the edge of the 92-degree camera view. Neither
    // a diameter nor an arc crosses the reticle, in any look direction.
    for (int32 Corner = 0; Corner < 4; ++Corner)
        for (int32 Segment = 0; Segment < 6; ++Segment)
        {
            const float A = Corner * UE_PI / 2.f + UE_PI / 12.f + Segment * UE_PI / 18.f;
            const float B = A + UE_PI / 24.f;
            auto Point = [](float Angle) { return FVector(100.f, FMath::Cos(Angle) * 92.f, FMath::Sin(Angle) * 48.f); };
            const FVector APos = Point(A), BPos = Point(B), Axis = BPos - APos;
            CockpitShieldVisual->AddInstance(FTransform(FRotationMatrix::MakeFromZ(Axis).ToQuat(),
                (APos + BPos) * .5f, FVector(.006, .006, Axis.Size() / 100.f)));
        }

    // Original provisional Basketbroom tool, about 103 cm overall and 36 cm
    // across the head. The current oversized Bludger is not a physical fit;
    // this pass adds appearance only, without collision or striking behavior.
    // Four instanced mesh layers per view keep the open head/lacing inexpensive.
    for (const bool bCockpit : {false, true})
    {
        const FString Prefix = bCockpit ? TEXT("CockpitHurley") : TEXT("RiderHurley");
        // The owner's presentation sits below the ball cards and to the right
        // of the reticle. Remote equipment retains its authored world scale.
        const FVector Base = bCockpit ? FVector(82, 47, -80) : FVector(48, 25, -10);
        const FRotator Pose = bCockpit ? FRotator(-15, 0, 0) : FRotator(-20, 0, 0);
        auto Layer = [this, bCockpit, &Prefix, Base, Pose](const TCHAR* Suffix, UStaticMesh* Shape, UMaterialInterface* Material)
        {
            UInstancedStaticMeshComponent* Component = CreateDefaultSubobject<UInstancedStaticMeshComponent>(FName(*(Prefix + Suffix)));
            Component->SetupAttachment(bCockpit ? static_cast<USceneComponent*>(Camera.Get()) : GetMesh());
            Component->SetStaticMesh(Shape);
            Component->SetMaterial(0, Material);
            Component->SetRelativeLocation(Base);
            Component->SetRelativeRotation(Pose);
            Component->SetRelativeScale3D(bCockpit ? FVector(.72) : FVector::OneVector);
            Component->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
            Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            Component->SetGenerateOverlapEvents(false);
            Component->SetCanEverAffectNavigation(false);
            Component->SetOnlyOwnerSee(bCockpit);
            Component->SetOwnerNoSee(!bCockpit);
            Component->SetCastShadow(!bCockpit);
            Component->SetVisibility(false);
            Component->ComponentTags.Add(TEXT("BB.Hurley"));
            Component->ComponentTags.Add(bCockpit ? TEXT("BB.Hurley.Owner") : TEXT("BB.Hurley.Remote"));
            HurleyParts.Add(Component);
            return Component;
        };
        UInstancedStaticMeshComponent* Frame = Layer(TEXT("Frame"), Cylinder.Object, Wood.Object);
        UInstancedStaticMeshComponent* Rounded = Layer(TEXT("RoundedFace"), Sphere.Object, Wood.Object);
        UInstancedStaticMeshComponent* Grip = Layer(TEXT("PaddedGrip"), Sphere.Object, Leather.Object);
        UInstancedStaticMeshComponent* Lacing = Layer(TEXT("OpenPocket"), Cylinder.Object, Ivory.Object);
        auto Ellipsoid = [](UInstancedStaticMeshComponent* Component, const FVector& Center, const FVector& Dimensions)
        {
            Component->AddInstance(FTransform(FQuat::Identity, Center, Dimensions / 100.0));
        };
        auto Rod = [](UInstancedStaticMeshComponent* Component, const FVector& A, const FVector& B, double Diameter)
        {
            const FVector Axis = B - A;
            const FQuat Rotation = FQuat::FindBetweenNormals(FVector::UpVector, Axis.GetSafeNormal());
            Component->AddInstance(FTransform(Rotation, (A + B) * .5, FVector(Diameter / 100.0, Diameter / 100.0, Axis.Size() / 100.0)));
        };

        // The oval shaft blends into a solid, rounded, offset lower face.
        Frame->AddInstance(FTransform(FQuat::Identity, FVector(0, 0, 38), FVector(.032, .043, .72)));
        Ellipsoid(Rounded, FVector(0, 1.2, 71), FVector(4.0, 30, 19));
        Ellipsoid(Grip, FVector(0, 0, 20), FVector(4.5, 6.0, 29));
        Ellipsoid(Grip, FVector(0, 0, 2.5), FVector(5.0, 6.5, 5.0));

        auto Outline = [](double Angle)
        {
            return FVector(0, 4 + 16 * FMath::Sin(Angle) + 3 * FMath::Cos(Angle), 84 + 17 * FMath::Cos(Angle));
        };
        constexpr int32 RimSegments = 20;
        for (int32 I = 0; I < RimSegments; ++I)
        {
            const FVector A = Outline(2.0 * PI * I / RimSegments);
            const FVector B = Outline(2.0 * PI * (I + 1) / RimSegments);
            Rod(Frame, A, B, 2.6);
            // Rounded overlaps cover every segment junction; no projecting ends.
            Ellipsoid(Rounded, A, FVector(2.6));
        }

        // Sparse ivory lacing leaves the upper pocket visibly open. Its deepest
        // point is just 3.2 cm behind the sidewall plane; there is no closed cup.
        for (double Z : {80.0, 86.0, 92.0, 98.0})
        {
            const double T = (Z - 84.0) / 17.0;
            const double CenterY = 4.0 + 3.0 * T;
            const double HalfWidth = 16.0 * FMath::Sqrt(1.0 - T * T);
            const FVector Center(3.2, CenterY, Z);
            Rod(Lacing, FVector(0, CenterY - HalfWidth, Z), Center, .75);
            Rod(Lacing, Center, FVector(0, CenterY + HalfWidth, Z), .75);
        }
        for (double T : {-.55, 0.0, .55})
        {
            const double Top = FMath::Sqrt(1.0 - T * T);
            const FVector Low(0, 4.0 + 16.0 * T - 12.0 / 17.0, 80);
            const FVector Middle(3.2, 4.0 + 16.0 * T + 18.0 / 17.0, 90);
            const FVector High(0, 4.0 + 16.0 * T + 3.0 * Top, 84.0 + 17.0 * Top);
            Rod(Lacing, Low, Middle, .75);
            Rod(Lacing, Middle, High, .75);
        }
        // Paired face stripes identify the solid striking area without symbols
        // borrowed from living sporting traditions.
        Rod(Lacing, FVector(-2.05, -6, 70), FVector(-2.05, 8, 72), 1.1);
        Rod(Lacing, FVector(-2.05, -5, 73), FVector(-2.05, 9, 75), 1.1);
    }
}

void ABBRiderCharacter::BeginPlay()
{
    Super::BeginPlay();
    RegisterControllerInputLifecycle();
    LoadControllerSettings();
    if (HasAuthority() || IsLocallyControlled())
    {
        GetCharacterMovement()->SetMovementMode(MOVE_Flying);
    }
    RefreshUniform();
    RefreshHurley();
    InitializeSportSpellVisuals();
    ShieldMaterial = ShieldVisual->CreateDynamicMaterialInstance(0);
    if (ShieldMaterial) ShieldMaterial->SetVectorParameterValue(TEXT("Tint"), FLinearColor(.18f, .58f, 1.f));
    CockpitShieldMaterial = CockpitShieldVisual->CreateDynamicMaterialInstance(0);
    if (CockpitShieldMaterial) CockpitShieldMaterial->SetVectorParameterValue(TEXT("Tint"), FLinearColor(.10f, .40f, .72f));
    RefreshSpellVisuals();
}

void ABBRiderCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABBRiderCharacter, TeamIndex);
    DOREPLIFETIME(ABBRiderCharacter, Position);
    DOREPLIFETIME(ABBRiderCharacter, RosterIndex);
    DOREPLIFETIME(ABBRiderCharacter, bInteractHeld);
    DOREPLIFETIME(ABBRiderCharacter, StunRemaining);
    DOREPLIFETIME(ABBRiderCharacter, SpellCooldownRemaining);
    DOREPLIFETIME(ABBRiderCharacter, ShieldRemaining);
    DOREPLIFETIME(ABBRiderCharacter, ImpedimentRemaining);
    DOREPLIFETIME(ABBRiderCharacter, DisarmRemaining);
    DOREPLIFETIME(ABBRiderCharacter, Vitality);
    DOREPLIFETIME(ABBRiderCharacter, LumosRemaining);
    DOREPLIFETIME(ABBRiderCharacter, RevealRemaining);
    DOREPLIFETIME(ABBRiderCharacter, ConcealRemaining);
    DOREPLIFETIME(ABBRiderCharacter, PetrificusRemaining);
    DOREPLIFETIME(ABBRiderCharacter, TransformationRemaining);
    DOREPLIFETIME(ABBRiderCharacter, ImperioRemaining);
    DOREPLIFETIME(ABBRiderCharacter, FlightBoostCharge);
    DOREPLIFETIME(ABBRiderCharacter, FlightSuperRemaining);
    DOREPLIFETIME(ABBRiderCharacter, FlightAccelerationScale);
}

void ABBRiderCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    TickFlightEnergy(DeltaSeconds);
    const ABBMatchState* Match = GetWorld()->GetGameState<ABBMatchState>();
    const bool bPenaltyKeeperMovement = Match && Match->bPenaltyShotActive && Match->CanMoveDuringPenalty(this);
    if (HasAuthority())
    {
        if (!Match) StunRemaining = FMath::Max(0.0f, StunRemaining - DeltaSeconds);
    }
    if (HasSpellMovementLock() && !bPenaltyKeeperMovement)
    {
        GetCharacterMovement()->StopMovementImmediately();
    }
    if (LastVisualTeam != TeamIndex)
    {
        RefreshUniform();
    }
    RefreshHurley();
    RefreshSpellVisuals();

    APlayerController* Player = Cast<APlayerController>(Controller);
    if (!Player || !Player->IsLocalController())
    {
        return;
    }
    TickControllerInput(Player);
    // Normal-client delivery: HUD marks its draw before a later Tick replies.
    // This does not prove human attention or prevent a modified client withholding.
    const double FeedbackNow = GetWorld()->GetTimeSeconds();
    PendingSpellNotices.RemoveAll([FeedbackNow](const FSpellNotice& Notice)
        { return FeedbackNow - Notice.QueuedAt >= SpellNoticeDeadline; });
    if (ActiveImpedimentAttackId && FeedbackNow - ActiveSpellNoticeQueuedAt >= SpellNoticeDeadline)
    {
        // An expired/unshown notice must never manufacture a confirmation.
        ActiveImpedimentAttackId = 0;
        SpellFeedbackRemaining = 0.f;
    }
    if (ActiveImpedimentAttackId && SpellFeedbackDisplayedAt >= 0.0
        && FeedbackNow - SpellFeedbackDisplayedAt >= .25)
    {
        if (!AcknowledgedImpediments.Contains(ActiveImpedimentAttackId))
        {
            AcknowledgedImpediments.Add(ActiveImpedimentAttackId);
            ServerAcknowledgeImpediment(ActiveImpedimentAttackId);
        }
        ActiveImpedimentAttackId = 0;
        // Drain another critical notice immediately after this one's display
        // obligation, rather than making it wait the full ordinary toast time.
        if (PendingSpellNotices.ContainsByPredicate([](const FSpellNotice& Notice) { return Notice.AttackId != 0; }))
            SpellFeedbackRemaining = 0.f;
    }
    if (SpellFeedbackDisplayedAt >= 0.0 || !ActiveImpedimentAttackId)
        SpellFeedbackRemaining = FMath::Max(0.f, SpellFeedbackRemaining - DeltaSeconds);
    if (SpellFeedbackRemaining <= 0.f && ActiveImpedimentAttackId == 0)
        ShowNextSpellNotice();
#if !UE_BUILD_SHIPPING
    if (GetWorld()->WorldType == EWorldType::PIE && !PendingDevelopmentInputs.IsEmpty())
    {
        // Python reflected calls hold FEditorScriptExecutionGuard, which makes
        // Actor RPC callspace local. Dispatch from normal native Tick so these
        // requests take the same client/server transport path as keyboard input.
        TArray<TPair<int32, int32>> Inputs = MoveTemp(PendingDevelopmentInputs);
        for (const TPair<int32, int32>& Input : Inputs)
        {
            if (Input.Key == -1)
            {
                bDevelopmentInteractHeld = Input.Value != 0;
                if (bDevelopmentInteractHeld) StartInteract();
                else StopInteract();
            }
            else
            {
                SubmitAction(Input.Key, Input.Value);
            }
        }
    }
#endif
    // Reconcile held keys after focus changes and allow Ctrl+W/A/S/D regardless
    // of press order. A plain BindKey chord excludes active modifier keys.
    for (const FKey Key : {EKeys::W, EKeys::S, EKeys::A, EKeys::D, EKeys::SpaceBar, EKeys::LeftControl, EKeys::RightControl})
    {
        if (Player->IsInputKeyDown(Key))
        {
            MovementKeys.Add(Key);
        }
        else
        {
            MovementKeys.Remove(Key);
        }
    }
    if (bLocalInteractHeld && !bDevelopmentInteractHeld && !Player->IsInputKeyDown(EKeys::E)
        && (bGamepadRequiresNeutral || !Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Left)))
    {
        StopInteract();
    }
    const ABBMatchState* InputMatch = GetWorld()->GetGameState<ABBMatchState>();
    if (InputMatch && InputMatch->bPenaltyShotActive)
    {
        bShowRoster = false;
        bShowSpellbook = false;
        if (!InputMatch->CanMoveDuringPenalty(this))
        {
            CastChecked<UBBFlyingMovementComponent>(GetCharacterMovement())->SetFlightInput(0.f, 0.f);
            ConsumeMovementInputVector();
            GetCharacterMovement()->StopMovementImmediately();
            return;
        }
    }
    if (HasSpellMovementLock() && !bPenaltyKeeperMovement)
    {
        CastChecked<UBBFlyingMovementComponent>(GetCharacterMovement())->SetFlightInput(0.f, 0.f);
        return;
    }
    TickFlightControls(Player);
}

void ABBRiderCharacter::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    check(Input);
    BindControllerInput(Input);
    for (const FKey Key : {EKeys::W, EKeys::S, EKeys::A, EKeys::D, EKeys::SpaceBar, EKeys::LeftControl, EKeys::RightControl})
    {
        Input->BindKey(Key, IE_Pressed, this, &ABBRiderCharacter::MovementPressed).bExecuteWhenPaused = true;
        Input->BindKey(Key, IE_Released, this, &ABBRiderCharacter::MovementReleased).bExecuteWhenPaused = true;
    }
    Input->BindAxisKey(EKeys::MouseX, this, &ABBRiderCharacter::LookYaw);
    Input->BindAxisKey(EKeys::MouseY, this, &ABBRiderCharacter::LookPitch);
    // Descending uses Ctrl; interaction must still work while it is held.
    for (bool bShift : {false, true})
    {
        for (bool bControl : {false, true})
        {
            Input->BindKey(FInputChord(EKeys::E, bShift, bControl, false, false), IE_Pressed, this, &ABBRiderCharacter::StartInteract);
            Input->BindKey(FInputChord(EKeys::E, bShift, bControl, false, false), IE_Released, this, &ABBRiderCharacter::ReleaseInteractInput);
            Input->BindKey(FInputChord(EKeys::LeftMouseButton, bShift, bControl, false, false), IE_Pressed, this, &ABBRiderCharacter::ReleaseBall);
            Input->BindKey(FInputChord(EKeys::Q, bShift, bControl, false, false), IE_Pressed, this, &ABBRiderCharacter::CastSelectedSpell);
            Input->BindKey(FInputChord(EKeys::R, bShift, bControl, false, false), IE_Pressed, this, &ABBRiderCharacter::RequestShield);
        }
    }
    for (const FKey Key : {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five, EKeys::Six})
    {
        Input->BindKey(Key, IE_Pressed, this, &ABBRiderCharacter::RequestPosition);
    }
    Input->BindKey(EKeys::T, IE_Pressed, this, &ABBRiderCharacter::RequestTeam);
    Input->BindKey(EKeys::Enter, IE_Pressed, this, &ABBRiderCharacter::RequestReady).bExecuteWhenPaused = true;
    for (const FKey Key : {EKeys::Up, EKeys::Down, EKeys::Left, EKeys::Right})
        Input->BindKey(Key, IE_Pressed, this, &ABBRiderCharacter::MovementPressed).bExecuteWhenPaused = true;
    Input->BindKey(EKeys::P, IE_Pressed, this, &ABBRiderCharacter::RequestStoppage);
    Input->BindKey(EKeys::Tab, IE_Pressed, this, &ABBRiderCharacter::ToggleRoster);
    Input->BindKey(EKeys::Z, IE_Pressed, this, &ABBRiderCharacter::PreviousSpell);
    Input->BindKey(EKeys::X, IE_Pressed, this, &ABBRiderCharacter::NextSpell);
    Input->BindKey(EKeys::B, IE_Pressed, this, &ABBRiderCharacter::RequestBloodbroom);
    Input->BindKey(EKeys::V, IE_Pressed, this, &ABBRiderCharacter::ToggleSpellbook);
    Input->BindKey(EKeys::F6, IE_Pressed, this, &ABBRiderCharacter::RequestFreeShot);
    Input->BindKey(EKeys::F7, IE_Pressed, this, &ABBRiderCharacter::RequestPossessionAward);
    Input->BindKey(EKeys::F8, IE_Pressed, this, &ABBRiderCharacter::RequestPenaltyShot);
    Input->BindKey(EKeys::F9, IE_Pressed, this, &ABBRiderCharacter::RequestEjection);
    Input->BindKey(EKeys::F10, IE_Pressed, this, &ABBRiderCharacter::RequestModerateAdvantage);
    Input->BindKey(EKeys::Escape, IE_Pressed, this, &ABBRiderCharacter::TogglePauseMenu).bExecuteWhenPaused = true;
}

void ABBRiderCharacter::MovementPressed(FKey Key) { bUsingGamepad = false; if (bPauseMenuOpen) { HandlePauseMenuKey(Key); return; } MovementKeys.Add(Key); }
void ABBRiderCharacter::MovementReleased(FKey Key) { MovementKeys.Remove(Key); }
void ABBRiderCharacter::LookYaw(float Value) { if (bPauseMenuOpen) return; if (!FMath::IsNearlyZero(Value)) bUsingGamepad = false; AddControllerYawInput(Value); }
void ABBRiderCharacter::LookPitch(float Value) { if (bPauseMenuOpen) return; if (!FMath::IsNearlyZero(Value)) bUsingGamepad = false; AddControllerPitchInput(-Value); }

void ABBRiderCharacter::StartInteract()
{
    if (!bPauseMenuOpen && !bLocalInteractHeld)
    {
        bLocalInteractHeld = true;
        ServerStartInteract();
    }
}

void ABBRiderCharacter::StopInteract()
{
    bLocalInteractHeld = false;
    ServerStopInteract();
}

void ABBRiderCharacter::ReleaseBall() { SubmitAction(1); }

void ABBRiderCharacter::RequestPosition(FKey Key)
{
    const FKey Positions[] = {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five, EKeys::Six};
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(Positions); ++Index)
    {
        if (Key == Positions[Index])
        {
            SubmitAction(2, Index);
            return;
        }
    }
}

void ABBRiderCharacter::RequestTeam() { SubmitAction(3, TeamIndex == 0 ? 1 : 0); }
void ABBRiderCharacter::RequestReady() { if (bPauseMenuOpen) { HandlePauseMenuKey(EKeys::Enter); return; } SubmitAction(4); }
void ABBRiderCharacter::RequestStoppage() { SubmitAction(5); }
void ABBRiderCharacter::ToggleRoster() { bShowRoster = !bShowRoster; if (bShowRoster) bShowSpellbook = false; }
void ABBRiderCharacter::ToggleSpellbook() { bShowSpellbook = !bShowSpellbook; if (bShowSpellbook) bShowRoster = false; }
void ABBRiderCharacter::PreviousSpell() { SelectedSpell = (SelectedSpell + FMath::Max(1, BBSpellCatalog::Count()) - 1) % FMath::Max(1, BBSpellCatalog::Count()); }
void ABBRiderCharacter::NextSpell() { SelectedSpell = (SelectedSpell + 1) % FMath::Max(1, BBSpellCatalog::Count()); }
void ABBRiderCharacter::CastSelectedSpell() { SubmitAction(6, SelectedSpell); }
void ABBRiderCharacter::RequestShield() { SubmitAction(7); }
void ABBRiderCharacter::RequestBloodbroom() { SubmitAction(8); }
void ABBRiderCharacter::RequestFreeShot() { SubmitAction(12); }
void ABBRiderCharacter::RequestPossessionAward() { SubmitAction(9); }
void ABBRiderCharacter::RequestPenaltyShot() { SubmitAction(10); }
void ABBRiderCharacter::RequestEjection() { SubmitAction(11); }
void ABBRiderCharacter::RequestModerateAdvantage() { SubmitAction(13); }

void ABBRiderCharacter::SubmitAction(int32 Action, int32 Value)
{
    if (IsLocallyControlled() && !bPauseMenuOpen)
    {
        ServerAction(Action, Value, GetAimDirection());
    }
}

bool ABBRiderCharacter::DevelopmentRequestAction(int32 Action, int32 Value)
{
#if UE_BUILD_SHIPPING
    return false;
#else
    if (!GetWorld() || GetWorld()->WorldType != EWorldType::PIE || !IsLocallyControlled()
        || !IsValid(Cast<APlayerController>(GetController())) || Action < 0 || Action > 13
        || (Action == 2 && (Value < 0 || Value > 5))
        || (Action == 3 && (Value < 0 || Value > 1))
        || (Action == 6 && (Value < 0 || Value >= BBSpellCatalog::Count()))
        || PendingDevelopmentInputs.Num() >= MaxDevelopmentInputs)
        return false;
    PendingDevelopmentInputs.Emplace(Action, Value);
    return true;
#endif
}

bool ABBRiderCharacter::DevelopmentSetInteraction(bool bHeld)
{
#if UE_BUILD_SHIPPING
    return false;
#else
    if (!GetWorld() || GetWorld()->WorldType != EWorldType::PIE || !IsLocallyControlled()
        || !IsValid(Cast<APlayerController>(GetController()))
        || PendingDevelopmentInputs.Num() >= MaxDevelopmentInputs)
        return false;
    PendingDevelopmentInputs.Emplace(-1, bHeld ? 1 : 0);
    return true;
#endif
}

void ABBRiderCharacter::ServerStartInteract_Implementation()
{
    if (!HasAuthority() || bInteractHeld || !Controller || HasSpellMovementLock())
    {
        return;
    }
    bInteractHeld = true;
    ForceNetUpdate();
    const double Now = GetWorld()->GetTimeSeconds();
    // Held capture still works when a rapid key repeat is throttled. Stops are
    // never throttled, so the server cannot retain a released interaction.
    if (StunRemaining > 0.0f || Now - LastServerInteractTime < 0.08)
    {
        return;
    }
    LastServerInteractTime = Now;
    if (ABBMatchState* Match = GetWorld()->GetGameState<ABBMatchState>())
    {
        Match->HandleAction(this, 0, 0, GetAimDirection());
    }
}

void ABBRiderCharacter::ServerStopInteract_Implementation()
{
    if (bInteractHeld)
    {
        bInteractHeld = false;
        ForceNetUpdate();
    }
}

void ABBRiderCharacter::ServerAction_Implementation(int32 Action, int32 Value, FVector Aim)
{
    if (!HasAuthority() || !Controller || Action < 0 || Action > 13)
    {
        return;
    }
    if (!FMath::IsFinite(Aim.X) || !FMath::IsFinite(Aim.Y) || !FMath::IsFinite(Aim.Z)
        || !FMath::IsNearlyEqual(Aim.SizeSquared(), 1.0, 0.02))
    {
        return;
    }
    const ABBMatchState* MatchState = GetWorld()->GetGameState<ABBMatchState>();
    const bool bProtectedShotRelease = Action == 1 && MatchState && MatchState->bPenaltyShotActive
        && MatchState->PenaltyShooterSlot == RosterIndex;
    if ((Action <= 1 && HasSpellMovementLock() && !bProtectedShotRelease)
        || (Action == 2 && (Value < 0 || Value > 5))
        || (Action == 3 && (Value < 0 || Value > 1))
        || (Action == 6 && (Value < 0 || Value >= BBSpellCatalog::Count())))
    {
        return;
    }
    const double Now = GetWorld()->GetTimeSeconds();
    if (Now - LastServerActionTime < 0.06)
    {
        return;
    }
    LastServerActionTime = Now;
    if (ABBMatchState* Match = GetWorld()->GetGameState<ABBMatchState>())
    {
        Match->HandleAction(this, Action, Value, Aim.GetSafeNormal());
    }
}

FVector ABBRiderCharacter::GetAimDirection() const
{
    const FVector Aim = GetBaseAimRotation().Vector();
    return Aim.ContainsNaN() ? GetActorForwardVector() : Aim.GetSafeNormal();
}

FVector ABBRiderCharacter::GetCarryLocation() const
{
    const FVector Aim = GetAimDirection();
    const FVector Right = FRotationMatrix(FRotator(0, Aim.Rotation().Yaw, 0)).GetUnitAxis(EAxis::Y);
    // Use the largest held-ball radius so neither authority custody nor the
    // local predicted held visual can protrude through a roof face or wall.
    return BBArena::ClampSphere(GetActorLocation() + FVector(0, 0, BaseEyeHeight - 25.0f)
        + Aim * 175.0f + Right * 35.0f, 65.0);
}

void ABBRiderCharacter::RefreshUniform()
{
    if (bSkeletalRiderEnabled)
    {
        const TArray<TObjectPtr<UMaterialInterface>>& Materials = TeamIndex == 0 ? SkeletalTealMaterials : SkeletalCopperMaterials;
        for (int32 Index = 0; Index < Materials.Num(); ++Index)
            if (Materials[Index]) GetMesh()->SetMaterial(Index, Materials[Index]);
    }
    UMaterialInterface* Material = TeamIndex == 0 ? TealMaterial.Get() : CopperMaterial.Get();
    if (Material)
    {
        for (UStaticMeshComponent* Part : UniformParts)
        {
            if (Part)
            {
                Part->SetMaterial(0, Material);
            }
        }
    }
    LastVisualTeam = TeamIndex;
}

void ABBRiderCharacter::OnRep_TeamIndex() { RefreshUniform(); }

void ABBRiderCharacter::NotifySpellResult(const FString& Message, uint64 ImpedimentAttackId)
{
    if (HasAuthority() && IsValid(Cast<APlayerController>(GetController())))
        ClientSpellResult(Message.Left(256), ImpedimentAttackId);
}

void ABBRiderCharacter::ClientSpellResult_Implementation(const FString& Message, uint64 ImpedimentAttackId)
{
    if (!GetWorld()) return;
    if (ImpedimentAttackId && (AcknowledgedImpediments.Contains(ImpedimentAttackId)
        || ActiveImpedimentAttackId == ImpedimentAttackId
        || PendingSpellNotices.ContainsByPredicate([ImpedimentAttackId](const FSpellNotice& Notice)
            { return Notice.AttackId == ImpedimentAttackId; }))) return;
    const double Now = GetWorld()->GetTimeSeconds();
    PendingSpellNotices.RemoveAll([Now](const FSpellNotice& Notice)
        { return Now - Notice.QueuedAt >= SpellNoticeDeadline; });
    if (ImpedimentAttackId)
    {
        // Critical feedback preempts ordinary traffic immediately. Preserve
        // the interrupted, unacknowledged ID with its original deadline.
        PendingSpellNotices.RemoveAll([](const FSpellNotice& Notice) { return Notice.AttackId == 0; });
        if (ActiveImpedimentAttackId && Now - ActiveSpellNoticeQueuedAt < SpellNoticeDeadline)
            PendingSpellNotices.Insert({SpellFeedback, ActiveImpedimentAttackId, ActiveSpellNoticeQueuedAt}, 0);
        PendingSpellNotices.Insert({Message.Left(256), ImpedimentAttackId, Now}, 0);
        // The normal server rate is well below this burst ceiling. On overflow
        // discard the oldest receipt without ACK, never invent proof for it.
        while (PendingSpellNotices.Num() > MaxCriticalSpellNotices)
        {
            int32 Oldest = 0;
            for (int32 I = 1; I < PendingSpellNotices.Num(); ++I)
                if (PendingSpellNotices[I].QueuedAt < PendingSpellNotices[Oldest].QueuedAt) Oldest = I;
            PendingSpellNotices.RemoveAt(Oldest);
        }
        ActiveImpedimentAttackId = 0;
        SpellFeedbackRemaining = 0.f;
        ShowNextSpellNotice();
        return;
    }
    // Ordinary repeats have no proof obligation. Keep only recent unique
    // notices, and never let them interrupt a pending critical receipt.
    PendingSpellNotices.RemoveAll([&Message](const FSpellNotice& Notice)
        { return Notice.AttackId == 0 && Notice.Message == Message; });
    if (!ActiveImpedimentAttackId && SpellFeedbackRemaining > 0.f && SpellFeedback == Message) return;
    int32 OrdinaryCount = 0;
    for (const FSpellNotice& Notice : PendingSpellNotices) OrdinaryCount += Notice.AttackId == 0 ? 1 : 0;
    while (OrdinaryCount >= MaxOrdinarySpellNotices)
    {
        const int32 Oldest = PendingSpellNotices.IndexOfByPredicate([](const FSpellNotice& Notice) { return Notice.AttackId == 0; });
        if (Oldest == INDEX_NONE) break;
        PendingSpellNotices.RemoveAt(Oldest);
        --OrdinaryCount;
    }
    PendingSpellNotices.Add({Message.Left(256), 0, Now});
    if (SpellFeedbackRemaining <= 0.f && !ActiveImpedimentAttackId) ShowNextSpellNotice();
}

void ABBRiderCharacter::ShowNextSpellNotice()
{
    SpellFeedback.Empty();
    SpellFeedbackDisplayedAt = -1.0;
    if (PendingSpellNotices.IsEmpty()) return;
    FSpellNotice Notice = MoveTemp(PendingSpellNotices[0]);
    PendingSpellNotices.RemoveAt(0);
    SpellFeedback = MoveTemp(Notice.Message);
    ActiveImpedimentAttackId = Notice.AttackId;
    ActiveSpellNoticeQueuedAt = Notice.QueuedAt;
    SpellFeedbackRemaining = 2.25f;
}

void ABBRiderCharacter::MarkSpellFeedbackDisplayed()
{
    if (IsLocallyControlled() && SpellFeedbackRemaining > 0.f && SpellFeedbackDisplayedAt < 0.0 && GetWorld())
        SpellFeedbackDisplayedAt = GetWorld()->GetTimeSeconds();
}

void ABBRiderCharacter::ServerAcknowledgeImpediment_Implementation(uint64 ImpedimentAttackId)
{
    if (!HasAuthority() || !Controller || ImpedimentAttackId == 0) return;
    if (ABBMatchState* Match = GetWorld()->GetGameState<ABBMatchState>())
        Match->ConfirmImpediment(this, ImpedimentAttackId);
}

void ABBRiderCharacter::RefreshSpellVisuals()
{
    for (UStaticMeshComponent* Part : WandParts) if (Part) Part->SetVisibility(DisarmRemaining <= 0.f);
    if (WandLight) WandLight->SetVisibility(LumosRemaining > 0.f && DisarmRemaining <= 0.f);
    if (WandLamp) WandLamp->SetVisibility(LumosRemaining > 0.f && DisarmRemaining <= 0.f);
    if (ShieldVisual) ShieldVisual->SetVisibility(ShieldRemaining > 0.f);
    if (CockpitShieldVisual) CockpitShieldVisual->SetVisibility(ShieldRemaining > 0.f);
    if (ShieldMaterial && ShieldRemaining > 0.f)
        ShieldMaterial->SetScalarParameterValue(TEXT("Glow"), 1.5f + .35f * FMath::Sin(GetWorld()->GetTimeSeconds() * 6.f));
    if (CockpitShieldMaterial && ShieldRemaining > 0.f)
        CockpitShieldMaterial->SetScalarParameterValue(TEXT("Glow"), .65f + .10f * FMath::Sin(GetWorld()->GetTimeSeconds() * 6.f));
    RefreshSportSpellVisuals();
}

void ABBRiderCharacter::RefreshHurley()
{
    const ABBMatchState* Match = GetWorld() ? GetWorld()->GetGameState<ABBMatchState>() : nullptr;
    const bool bShouldShow = Position == 4 && (!Match || Match->Phase != TEXT("DONNYBROOK"));
    if (bHurleyVisible == bShouldShow) return;
    bHurleyVisible = bShouldShow;
    for (UStaticMeshComponent* Part : HurleyParts)
        if (Part) Part->SetVisibility(bShouldShow);
}

void ABBRiderCharacter::OnRep_StunRemaining()
{
    if (HasSpellMovementLock())
    {
        GetCharacterMovement()->StopMovementImmediately();
    }
}

void ABBRiderCharacter::ResetLocalInput()
{
    if (APlayerController* Player = Cast<APlayerController>(Controller))
        if (Player->IsLocalController()) Player->FlushPressedKeys();
    PendingControllerInputs.Reset();
    if (UBBFlyingMovementComponent* Movement = Cast<UBBFlyingMovementComponent>(GetCharacterMovement())) Movement->SetFlightInput(0.f, 0.f);
    GamepadRefereeChoice = 0;
    bGamepadRequiresNeutral = false;
    bObservedViewportFocus = false;
    GetCharacterMovement()->StopMovementImmediately();
    ConsumeMovementInputVector();
    MovementKeys.Empty();
    bLocalInteractHeld = false;
    bDevelopmentInteractHeld = false;
    PendingDevelopmentInputs.Reset();
    bShowRoster = false;
    bShowSpellbook = false;
    PendingSpellNotices.Reset();
    ActiveImpedimentAttackId = 0;
    SpellFeedback.Empty();
    SpellFeedbackRemaining = 0.f;
    SpellFeedbackDisplayedAt = -1.0;
    ActiveSpellNoticeQueuedAt = 0.0;
}

void ABBRiderCharacter::UnPossessed()
{
    if (HasAuthority())
    {
        bInteractHeld = false;
        ForceNetUpdate();
    }
    if (bPauseMenuOpen) ClosePauseMenu();
    ResetLocalInput();
    Super::UnPossessed();
}

void ABBRiderCharacter::PawnClientRestart()
{
    ResetLocalInput();
    Super::PawnClientRestart();
}

#include "BBRiderCharacter.h"

#include "BBMatchState.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Materials/MaterialInterface.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

float UBBFlyingMovementComponent::GetMaxSpeed() const
{
    const ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(GetOwner());
    return Rider && Rider->StunRemaining > 0.0f ? 0.0f : Super::GetMaxSpeed();
}

float UBBFlyingMovementComponent::GetMaxAcceleration() const
{
    const ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(GetOwner());
    return Rider && Rider->StunRemaining > 0.0f ? 0.0f : Super::GetMaxAcceleration();
}

void UBBFlyingMovementComponent::PhysFlying(float DeltaTime, int32 Iterations)
{
    const FVector EntryVelocity = Velocity;
    Super::PhysFlying(DeltaTime, Iterations);
    const ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(GetOwner());
    if (!HasValidData() || !Rider || Rider->StunRemaining > 0.0f || MovementMode != MOVE_Flying) return;

    const UCapsuleComponent* Capsule = Rider->GetCapsuleComponent();
    const double Radius = Capsule->GetScaledCapsuleRadius();
    const double HalfHeight = Capsule->GetScaledCapsuleHalfHeight();
    const FVector Lower(-6850.8 + Radius, -3200.4 + Radius, HalfHeight);
    const FVector Upper(6850.8 - Radius, 3200.4 - Radius, 6309.36 - HalfHeight);
    const FVector Current = UpdatedComponent->GetComponentLocation();
    const FVector Bounded(FMath::Clamp(Current.X, Lower.X, Upper.X),
                          FMath::Clamp(Current.Y, Lower.Y, Upper.Y),
                          FMath::Clamp(Current.Z, Lower.Z, Upper.Z));
    if (!Current.Equals(Bounded, .01))
    {
        FHitResult Hit;
        SafeMoveUpdatedComponent(Bounded - Current, UpdatedComponent->GetComponentQuat(), true, Hit);
    }

    // Lower nets collide physically; open-crown bounds are movement constraints.
    // Both use the same predicted simulation and preserve a controlled rebound.
    for (int32 Axis = 0; Axis < 3; ++Axis)
    {
        const double Speed = FMath::Max(FMath::Abs(EntryVelocity[Axis]), FMath::Abs(Velocity[Axis]));
        if (Bounded[Axis] <= Lower[Axis] + 3.0 && (EntryVelocity[Axis] < 0 || Velocity[Axis] < 0))
            Velocity[Axis] = Speed * .75;
        else if (Bounded[Axis] >= Upper[Axis] - 3.0 && (EntryVelocity[Axis] > 0 || Velocity[Axis] > 0))
            Velocity[Axis] = -Speed * .75;
    }
}

ABBRiderCharacter::ABBRiderCharacter(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer.SetDefaultSubobjectClass<UBBFlyingMovementComponent>(ACharacter::CharacterMovementComponentName))
{
    PrimaryActorTick.bCanEverTick = true;
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

    // The Character mesh component also carries native remote-proxy smoothing.
    // Original primitive body parts attached here inherit that smoothing.
    GetMesh()->SetRelativeLocation(FVector::ZeroVector);
    GetMesh()->SetRelativeRotation(FRotator::ZeroRotator);
    GetMesh()->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);

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

    Part(TEXT("Tunic"), Sphere.Object, Teal.Object, FVector(8, 0, 33), FVector(.42, .46, .69), FRotator(-12, 0, 0), false, true);
    Part(TEXT("Head"), Sphere.Object, Face.Object, FVector(23, 0, 81), FVector(.27, .25, .31), FRotator::ZeroRotator, false);
    Part(TEXT("Helmet"), Sphere.Object, Teal.Object, FVector(21, 0, 92), FVector(.30, .28, .19), FRotator::ZeroRotator, false, true);
    Part(TEXT("ChestMark"), Sphere.Object, Ivory.Object, FVector(30, 0, 40), FVector(.027, .17, .24), FRotator(-12, 0, 0), false);
    Part(TEXT("BroomShaft"), Cylinder.Object, Wood.Object, FVector(25, 0, -8), FVector(.07, .07, 2.70), FRotator(90, 0, 0), false);
    Part(TEXT("BroomBristles"), Cone.Object, Bristles.Object, FVector(-148, 0, -8), FVector(.39, .39, 1.03), FRotator(-90, 0, 0), false);
    Part(TEXT("BroomBinding"), Cylinder.Object, Ivory.Object, FVector(-95, 0, -8), FVector(.115, .115, .13), FRotator(90, 0, 0), false);
    Part(TEXT("BroomNose"), Sphere.Object, Wood.Object, FVector(160, 0, -8), FVector(.13, .079, .079), FRotator::ZeroRotator, false);
    for (int32 Side : {-1, 1})
    {
        const FString Prefix = Side < 0 ? TEXT("Left") : TEXT("Right");
        Part(FName(*(Prefix + TEXT("Arm"))), Sphere.Object, Teal.Object, FVector(32, Side * 24, 32), FVector(.66, .15, .17), FRotator(-40, 0, 0), false, true);
        Part(FName(*(Prefix + TEXT("Glove"))), Sphere.Object, Leather.Object, FVector(56, Side * 21, 11), FVector(.17, .14, .15), FRotator::ZeroRotator, false);
        Part(FName(*(Prefix + TEXT("BentLeg"))), Sphere.Object, Pants.Object, FVector(8, Side * 19, -18), FVector(.50, .18, .24), FRotator(-30, 0, 0), false);
        Part(FName(*(Prefix + TEXT("Boot"))), Sphere.Object, Leather.Object, FVector(29, Side * 20, -49), FVector(.25, .20, .48), FRotator(-10, 0, 0), false);
    }

    Part(TEXT("CockpitShaft"), Cylinder.Object, Wood.Object, FVector(108, 30, -56), FVector(.082, .082, 2.25), FRotator(90, 0, 0), true);
    Part(TEXT("CockpitNose"), Sphere.Object, Wood.Object, FVector(220, 30, -54), FVector(.15, .105, .105), FRotator::ZeroRotator, true);
    Part(TEXT("CockpitGrip"), Cylinder.Object, Leather.Object, FVector(65, 30, -56), FVector(.105, .105, .42), FRotator(90, 0, 0), true);
    Part(TEXT("CockpitCollar"), Cylinder.Object, Metal.Object, FVector(152, 30, -56), FVector(.124, .124, .065), FRotator(90, 0, 0), true);
    Part(TEXT("CockpitCharmMount"), Cube.Object, Iron.Object, FVector(145, 30, -48), FVector(.17, .14, .08), FRotator::ZeroRotator, true);
    Part(TEXT("CockpitFlightCharm"), Sphere.Object, Light.Object, FVector(145, 30, -42), FVector(.12, .11, .065), FRotator::ZeroRotator, true);
    Part(TEXT("CockpitBristles"), Cone.Object, Bristles.Object, FVector(-55, 30, -56), FVector(.4, .4, .75), FRotator(-90, 0, 0), true);
    for (int32 Index = 0; Index < 6; ++Index)
    {
        Part(FName(*FString::Printf(TEXT("CockpitGripWrap%d"), Index)), Cylinder.Object, Metal.Object,
             FVector(47 + Index * 6.5, 30, -56), FVector(.111, .111, .012), FRotator(90, 0, 0), true);
    }
}

void ABBRiderCharacter::BeginPlay()
{
    Super::BeginPlay();
    if (HasAuthority() || IsLocallyControlled())
    {
        GetCharacterMovement()->SetMovementMode(MOVE_Flying);
    }
    RefreshUniform();
}

void ABBRiderCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABBRiderCharacter, TeamIndex);
    DOREPLIFETIME(ABBRiderCharacter, Position);
    DOREPLIFETIME(ABBRiderCharacter, RosterIndex);
    DOREPLIFETIME(ABBRiderCharacter, bInteractHeld);
    DOREPLIFETIME(ABBRiderCharacter, StunRemaining);
}

void ABBRiderCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (HasAuthority())
    {
        StunRemaining = FMath::Max(0.0f, StunRemaining - DeltaSeconds);
    }
    if (StunRemaining > 0.0f)
    {
        GetCharacterMovement()->StopMovementImmediately();
    }
    if (LastVisualTeam != TeamIndex)
    {
        RefreshUniform();
    }

    APlayerController* Player = Cast<APlayerController>(Controller);
    if (!Player || !Player->IsLocalController())
    {
        return;
    }
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
    if (bLocalInteractHeld && !bDevelopmentInteractHeld && !Player->IsInputKeyDown(EKeys::E))
    {
        StopInteract();
    }
    if (StunRemaining > 0.0f)
    {
        return;
    }
    const float Forward = float(MovementKeys.Contains(EKeys::W)) - float(MovementKeys.Contains(EKeys::S));
    const float Right = float(MovementKeys.Contains(EKeys::D)) - float(MovementKeys.Contains(EKeys::A));
    const float Up = float(MovementKeys.Contains(EKeys::SpaceBar))
        - float(MovementKeys.Contains(EKeys::LeftControl) || MovementKeys.Contains(EKeys::RightControl));
    const FRotator AimRotation = GetControlRotation();
    AddMovementInput(AimRotation.Vector(), Forward);
    AddMovementInput(FRotationMatrix(FRotator(0, AimRotation.Yaw, 0)).GetUnitAxis(EAxis::Y), Right);
    AddMovementInput(FVector::UpVector, Up);
}

void ABBRiderCharacter::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    check(Input);
    for (const FKey Key : {EKeys::W, EKeys::S, EKeys::A, EKeys::D, EKeys::SpaceBar, EKeys::LeftControl, EKeys::RightControl})
    {
        Input->BindKey(Key, IE_Pressed, this, &ABBRiderCharacter::MovementPressed);
        Input->BindKey(Key, IE_Released, this, &ABBRiderCharacter::MovementReleased);
    }
    Input->BindAxisKey(EKeys::MouseX, this, &ABBRiderCharacter::LookYaw);
    Input->BindAxisKey(EKeys::MouseY, this, &ABBRiderCharacter::LookPitch);
    // Descending uses Ctrl; interaction must still work while it is held.
    for (bool bShift : {false, true})
    {
        for (bool bControl : {false, true})
        {
            Input->BindKey(FInputChord(EKeys::E, bShift, bControl, false, false), IE_Pressed, this, &ABBRiderCharacter::StartInteract);
            Input->BindKey(FInputChord(EKeys::E, bShift, bControl, false, false), IE_Released, this, &ABBRiderCharacter::StopInteract);
            Input->BindKey(FInputChord(EKeys::LeftMouseButton, bShift, bControl, false, false), IE_Pressed, this, &ABBRiderCharacter::ReleaseBall);
        }
    }
    for (const FKey Key : {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five, EKeys::Six})
    {
        Input->BindKey(Key, IE_Pressed, this, &ABBRiderCharacter::RequestPosition);
    }
    Input->BindKey(EKeys::T, IE_Pressed, this, &ABBRiderCharacter::RequestTeam);
    Input->BindKey(EKeys::Enter, IE_Pressed, this, &ABBRiderCharacter::RequestReady);
    Input->BindKey(EKeys::P, IE_Pressed, this, &ABBRiderCharacter::RequestStoppage);
    Input->BindKey(EKeys::Tab, IE_Pressed, this, &ABBRiderCharacter::ToggleRoster);
}

void ABBRiderCharacter::MovementPressed(FKey Key) { MovementKeys.Add(Key); }
void ABBRiderCharacter::MovementReleased(FKey Key) { MovementKeys.Remove(Key); }
void ABBRiderCharacter::LookYaw(float Value) { AddControllerYawInput(Value); }
void ABBRiderCharacter::LookPitch(float Value) { AddControllerPitchInput(-Value); }

void ABBRiderCharacter::StartInteract()
{
    if (!bLocalInteractHeld)
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
void ABBRiderCharacter::RequestReady() { SubmitAction(4); }
void ABBRiderCharacter::RequestStoppage() { SubmitAction(5); }
void ABBRiderCharacter::ToggleRoster() { bShowRoster = !bShowRoster; }

void ABBRiderCharacter::SubmitAction(int32 Action, int32 Value)
{
    if (IsLocallyControlled())
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
        || !IsValid(Cast<APlayerController>(GetController())) || Action < 0 || Action > 5)
        return false;
    SubmitAction(Action, Value);
    return true;
#endif
}

bool ABBRiderCharacter::DevelopmentSetInteraction(bool bHeld)
{
#if UE_BUILD_SHIPPING
    return false;
#else
    if (!GetWorld() || GetWorld()->WorldType != EWorldType::PIE || !IsLocallyControlled()
        || !IsValid(Cast<APlayerController>(GetController())))
        return false;
    bDevelopmentInteractHeld = bHeld;
    if (bHeld) StartInteract();
    else StopInteract();
    return true;
#endif
}

void ABBRiderCharacter::ServerStartInteract_Implementation()
{
    if (!HasAuthority() || bInteractHeld || !Controller)
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
    if (!HasAuthority() || !Controller || Action < 0 || Action > 5)
    {
        return;
    }
    if (!FMath::IsFinite(Aim.X) || !FMath::IsFinite(Aim.Y) || !FMath::IsFinite(Aim.Z)
        || !FMath::IsNearlyEqual(Aim.SizeSquared(), 1.0, 0.02))
    {
        return;
    }
    if ((Action <= 1 && StunRemaining > 0.0f)
        || (Action == 2 && (Value < 0 || Value > 5))
        || (Action == 3 && (Value < 0 || Value > 1)))
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
    return GetActorLocation() + FVector(0, 0, BaseEyeHeight - 25.0f) + Aim * 175.0f + Right * 35.0f;
}

void ABBRiderCharacter::RefreshUniform()
{
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

void ABBRiderCharacter::OnRep_StunRemaining()
{
    if (StunRemaining > 0.0f)
    {
        GetCharacterMovement()->StopMovementImmediately();
    }
}

void ABBRiderCharacter::ResetLocalInput()
{
    MovementKeys.Empty();
    bLocalInteractHeld = false;
    bDevelopmentInteractHeld = false;
    bShowRoster = false;
}

void ABBRiderCharacter::UnPossessed()
{
    if (HasAuthority())
    {
        bInteractHeld = false;
        ForceNetUpdate();
    }
    ResetLocalInput();
    Super::UnPossessed();
}

void ABBRiderCharacter::PawnClientRestart()
{
    ResetLocalInput();
    Super::PawnClientRestart();
}

#include "BBRiderCharacter.h"
#include "BBMatchState.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Misc/ConfigCacheIni.h"

void ABBRiderCharacter::LoadControllerSettings()
{
    if (!GConfig) return;
    GConfig->GetBool(TEXT("Basketbroom.Controller"), TEXT("InvertAltitude"), bInvertControllerAltitude, GGameUserSettingsIni);
    GConfig->GetBool(TEXT("Basketbroom.Controller"), TEXT("InvertAimY"), bInvertControllerAimY, GGameUserSettingsIni);
}
void ABBRiderCharacter::SetControllerInversion(bool bAltitude, bool bAim)
{
    if (!IsLocallyControlled()) return;
    bInvertControllerAltitude = bAltitude;
    bInvertControllerAimY = bAim;
    if (!GConfig) return;
    GConfig->SetBool(TEXT("Basketbroom.Controller"), TEXT("InvertAltitude"), bAltitude, GGameUserSettingsIni);
    GConfig->SetBool(TEXT("Basketbroom.Controller"), TEXT("InvertAimY"), bAim, GGameUserSettingsIni);
    GConfig->Flush(false, GGameUserSettingsIni);
}
bool ABBRiderCharacter::IsControllerPrecisionAim() const
{
    const APlayerController* Player = Cast<APlayerController>(Controller);
    const ABBMatchState* Match = GetWorld() ? GetWorld()->GetGameState<ABBMatchState>() : nullptr;
    return (Player && Player->IsInputKeyDown(EKeys::Gamepad_LeftThumbstick))
        || (Match && Match->bPenaltyShotActive && Match->PenaltyShooterSlot == RosterIndex);
}
bool ABBRiderCharacter::CanUseFlightBoost() const
{
    const ABBMatchState* Match = GetWorld() ? GetWorld()->GetGameState<ABBMatchState>() : nullptr;
    return Match && !GetWorld()->IsPaused() && !bPauseMenuOpen && Match->bLive && !Match->bPenaltyShotActive && !HasSpellMovementLock()
        && !IsHidden() && (!HasAuthority() || Match->IsActiveFlightParticipant(this));
}
void ABBRiderCharacter::SyncFlightEnergy()
{
    FlightBoostCharge = FlightEnergy.charge;
    FlightSuperRemaining = FlightEnergy.super_remaining;
    FlightAccelerationScale = FlightEnergy.scale(CanUseFlightBoost());
}
bool ABBRiderCharacter::AwardFlightBoost(uint8 OriginKind, uint64 EventId, float Amount)
{
    const ABBMatchState* Match = GetWorld() ? GetWorld()->GetGameState<ABBMatchState>() : nullptr;
    if (!HasAuthority() || !Match || !Match->IsActiveFlightParticipant(this)
        || !FlightEnergy.award(OriginKind, EventId, Amount)) return false;
    SyncFlightEnergy();
    ForceNetUpdate();
    return true;
}
void ABBRiderCharacter::ResetFlightBoost()
{
    if (!HasAuthority()) return;
    FlightEnergy = BBFlight::Energy{};
    LastFlightInputTime = -1.0;
    SyncFlightEnergy();
    ForceNetUpdate();
}
void ABBRiderCharacter::AcceptFlightInput(float Throttle, float Brake)
{
    if (!HasAuthority() || !Controller || !GetWorld()) return;
    FlightEnergy.input(Throttle, Brake, CanUseFlightBoost());
    LastFlightInputTime = GetWorld()->GetTimeSeconds();
    SyncFlightEnergy();
}
void ABBRiderCharacter::TickFlightEnergy(float DeltaSeconds)
{
    if (!HasAuthority()) return;
    // A client that stops supplying validated movement cannot keep burning/using
    // a held boost. Normal CharacterMovement timestamp checks still apply.
    if (!Controller || GetWorld()->GetTimeSeconds() - LastFlightInputTime > .35)
    {
        FlightEnergy.cancel();
        if (UBBFlyingMovementComponent* Movement = Cast<UBBFlyingMovementComponent>(GetCharacterMovement()))
            Movement->FlightThrottle = Movement->FlightBrake = 0;
    }
    FlightEnergy.advance(DeltaSeconds, CanUseFlightBoost());
    SyncFlightEnergy();
}
void ABBRiderCharacter::ClearFlightInput()
{
    if (UBBFlyingMovementComponent* Movement = Cast<UBBFlyingMovementComponent>(GetCharacterMovement()))
        Movement->SetFlightInput(0.f, 0.f);
    FlushOwnedControllerInput();
}
void ABBRiderCharacter::TickFlightControls(APlayerController* Player)
{
    UBBFlyingMovementComponent* Movement = Cast<UBBFlyingMovementComponent>(GetCharacterMovement());
    if (!Movement || !Player) return;
    const bool bSuppressed = bPauseMenuOpen || bGamepadRequiresNeutral || Player->IsPaused()
        || Player->IsMoveInputIgnored();
    const float Throttle = bSuppressed ? 0.f : FMath::Max(0.f, ControllerAxis(EKeys::Gamepad_RightTriggerAxis));
    const float Brake = bSuppressed ? 0.f : FMath::Max(0.f, ControllerAxis(EKeys::Gamepad_LeftTriggerAxis));
    Movement->SetFlightInput(Throttle, Brake);
    if (bSuppressed)
    {
        ConsumeMovementInputVector();
        Movement->StopMovementImmediately();
        return;
    }
    const float Forward = FMath::Clamp(float(MovementKeys.Contains(EKeys::W)) - float(MovementKeys.Contains(EKeys::S))
        + ControllerAxis(EKeys::Gamepad_LeftY) + Throttle, -1.f, 1.f);
    const float Right = FMath::Clamp(float(MovementKeys.Contains(EKeys::D)) - float(MovementKeys.Contains(EKeys::A))
        + ControllerAxis(EKeys::Gamepad_LeftX), -1.f, 1.f);
    const float StickAltitude = IsControllerPrecisionAim() ? 0.f
        : ControllerAxis(EKeys::Gamepad_RightY) * (bInvertControllerAltitude ? -1.f : 1.f);
    const float Up = float(MovementKeys.Contains(EKeys::SpaceBar))
        - float(MovementKeys.Contains(EKeys::LeftControl) || MovementKeys.Contains(EKeys::RightControl)) + StickAltitude;
    const FRotator AimRotation = GetControlRotation();
    // The controller steers horizontally; altitude is independent of camera pitch.
    const FVector ForwardAxis = bUsingGamepad ? FRotator(0, AimRotation.Yaw, 0).Vector() : AimRotation.Vector();
    AddMovementInput(ForwardAxis, Forward * (1.f - Brake));
    AddMovementInput(FRotationMatrix(FRotator(0, AimRotation.Yaw, 0)).GetUnitAxis(EAxis::Y), Right * (1.f - Brake));
    AddMovementInput(FVector::UpVector, FMath::Clamp(Up, -1.f, 1.f) * (1.f - Brake));
}
TArray<float> ABBRiderCharacter::DevelopmentGetFlightState() const
{
#if !UE_BUILD_SHIPPING
    if (GetWorld() && GetWorld()->WorldType == EWorldType::PIE)
    {
        const UBBFlyingMovementComponent* Movement = Cast<UBBFlyingMovementComponent>(GetCharacterMovement());
        return {FlightBoostCharge, FlightSuperRemaining, FlightAccelerationScale,
            Movement ? Movement->FlightThrottle / 255.f : 0.f, Movement ? Movement->FlightBrake / 255.f : 0.f,
            bInvertControllerAltitude ? 1.f : 0.f, bInvertControllerAimY ? 1.f : 0.f,
            bPauseMenuOpen ? 1.f : 0.f};
    }
#endif
    return {};
}

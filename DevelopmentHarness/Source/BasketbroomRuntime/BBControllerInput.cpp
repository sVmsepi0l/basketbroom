#include "BBRiderCharacter.h"

#include "BBMatchState.h"
#include "Components/InputComponent.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/InputSettings.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerInput.h"
#include "GenericPlatform/GenericPlatformInputDeviceMapper.h"
#include "InputKeyEventArgs.h"
#include "Misc/CoreDelegates.h"
#include "UnrealClient.h"

namespace
{
bool IsMappedControllerKey(const FKey Key)
{
    return Key == EKeys::Gamepad_LeftX || Key == EKeys::Gamepad_LeftY
        || Key == EKeys::Gamepad_RightX || Key == EKeys::Gamepad_RightY
        || Key == EKeys::Gamepad_FaceButton_Bottom || Key == EKeys::Gamepad_FaceButton_Right
        || Key == EKeys::Gamepad_FaceButton_Left || Key == EKeys::Gamepad_FaceButton_Top
        || Key == EKeys::Gamepad_RightTrigger || Key == EKeys::Gamepad_RightShoulder
        || Key == EKeys::Gamepad_LeftShoulder || Key == EKeys::Gamepad_Special_Left
        || Key == EKeys::Gamepad_Special_Right || Key == EKeys::Gamepad_DPad_Left
        || Key == EKeys::Gamepad_DPad_Right || Key == EKeys::Gamepad_DPad_Up
        || Key == EKeys::Gamepad_DPad_Down;
}
}

void ABBRiderCharacter::BindControllerInput(UInputComponent* Input)
{
    // AxisConfig performs the existing deadzone, exponent, sensitivity and
    // inversion. No OS transport assumption, duplicate deadzone or global edit.
    Input->BindAxisKey(EKeys::Gamepad_LeftX, this, &ABBRiderCharacter::GamepadMoveAxis);
    Input->BindAxisKey(EKeys::Gamepad_LeftY, this, &ABBRiderCharacter::GamepadMoveAxis);
    Input->BindAxisKey(EKeys::Gamepad_RightX, this, &ABBRiderCharacter::GamepadLookYaw);
    Input->BindAxisKey(EKeys::Gamepad_RightY, this, &ABBRiderCharacter::GamepadLookPitch);
    for (const FKey Key : {EKeys::Gamepad_FaceButton_Bottom, EKeys::Gamepad_FaceButton_Right,
        EKeys::Gamepad_FaceButton_Left, EKeys::Gamepad_FaceButton_Top, EKeys::Gamepad_RightTrigger,
        EKeys::Gamepad_RightShoulder, EKeys::Gamepad_LeftShoulder, EKeys::Gamepad_Special_Left,
        EKeys::Gamepad_Special_Right, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_DPad_Right,
        EKeys::Gamepad_DPad_Up, EKeys::Gamepad_DPad_Down})
    {
        Input->BindKey(Key, IE_Pressed, this, &ABBRiderCharacter::GamepadPressed);
        Input->BindKey(Key, IE_Released, this, &ABBRiderCharacter::GamepadReleased);
    }
    Input->BindKey(EKeys::AnyKey, IE_Pressed, this, &ABBRiderCharacter::ObserveInputDevice).bConsumeInput = false;
}

void ABBRiderCharacter::ObserveInputDevice(FKey Key)
{
    if (Key != EKeys::AnyKey) bUsingGamepad = Key.IsGamepadKey();
}

void ABBRiderCharacter::GamepadMoveAxis(float Value)
{
    if (!bGamepadRequiresNeutral && FMath::IsFinite(Value) && FMath::Abs(Value) > .001f) bUsingGamepad = true;
}

float ABBRiderCharacter::ControllerAxis(const FKey Key) const
{
    const APlayerController* Player = Cast<APlayerController>(Controller);
    if (bGamepadRequiresNeutral || !Player || !Player->PlayerInput) return 0.f;
    // FlushPressedKeys zeros RawValue immediately; its processed Value may
    // otherwise survive until the next input-stack evaluation.
    if (FMath::IsNearlyZero(Player->PlayerInput->GetRawKeyValue(Key))) return 0.f;
    const float Value = Player->PlayerInput->GetKeyValue(Key);
    return FMath::IsFinite(Value) ? FMath::Clamp(Value, -1.f, 1.f) : 0.f;
}

void ABBRiderCharacter::GamepadLookYaw(float Value)
{
    if (bGamepadRequiresNeutral || !FMath::IsFinite(Value) || FMath::IsNearlyZero(Value)) return;
    APlayerController* Player = Cast<APlayerController>(Controller);
    if (!Player || !GetWorld()) return;
    bUsingGamepad = true;
    // Keep the mouse's existing legacy scale intact while making stick speed
    // an explicit degrees/second rate. AxisConfig still controls sensitivity.
    float Scale = 1.f;
    PRAGMA_DISABLE_DEPRECATION_WARNINGS
    if (GetDefault<UInputSettings>()->bEnableLegacyInputScales) Scale = Player->GetDeprecatedInputYawScale();
    PRAGMA_ENABLE_DEPRECATION_WARNINGS
    if (!FMath::IsNearlyZero(Scale)) AddControllerYawInput(Value * GamepadYawDegreesPerSecond * GetWorld()->GetDeltaSeconds() / Scale);
}

void ABBRiderCharacter::GamepadLookPitch(float Value)
{
    if (bGamepadRequiresNeutral || !FMath::IsFinite(Value) || FMath::IsNearlyZero(Value)) return;
    APlayerController* Player = Cast<APlayerController>(Controller);
    if (!Player || !GetWorld()) return;
    bUsingGamepad = true;
    float Scale = 1.f;
    PRAGMA_DISABLE_DEPRECATION_WARNINGS
    if (GetDefault<UInputSettings>()->bEnableLegacyInputScales) Scale = Player->GetDeprecatedInputPitchScale();
    PRAGMA_ENABLE_DEPRECATION_WARNINGS
    if (!FMath::IsNearlyZero(Scale)) AddControllerPitchInput(Value * GamepadPitchDegreesPerSecond * GetWorld()->GetDeltaSeconds() / Scale);
}

void ABBRiderCharacter::SyncGamepadRefereeChoice()
{
    const ABBMatchState* Match = GetWorld() ? GetWorld()->GetGameState<ABBMatchState>() : nullptr;
    const bool bReview = Match && Match->bConductReviewPending;
    const int32 FoulCount = Match ? Match->ConductFoulCount : -1;
    if (!bReview || bReview != bLastConductReviewPending || FoulCount != LastGamepadConductFoulCount)
        GamepadRefereeChoice = 0;
    bLastConductReviewPending = bReview;
    LastGamepadConductFoulCount = FoulCount;
}

void ABBRiderCharacter::GamepadPressed(FKey Key)
{
    bUsingGamepad = true;
    if (bGamepadRequiresNeutral) return;
    SyncGamepadRefereeChoice();
    ABBMatchState* Match = GetWorld() ? GetWorld()->GetGameState<ABBMatchState>() : nullptr;
    if (Key == EKeys::Gamepad_FaceButton_Left) StartInteract();
    else if (Key == EKeys::Gamepad_RightTrigger) ReleaseBall();
    else if (Key == EKeys::Gamepad_RightShoulder) CastSelectedSpell();
    else if (Key == EKeys::Gamepad_LeftShoulder) RequestShield();
    else if (Key == EKeys::Gamepad_FaceButton_Top) ToggleSpellbook();
    else if (Key == EKeys::Gamepad_Special_Left) ToggleRoster();
    else if (Key == EKeys::Gamepad_Special_Right)
    {
        if (Match && Match->bConductReviewPending)
        {
            const int32 Choice = GamepadRefereeChoice;
            GamepadRefereeChoice = 0;
            if (Choice == 1) RequestPossessionAward();
            else if (Choice == 2) RequestEjection();
            // A fresh review and a lone Menu press never choose a sanction.
        }
        else if (Match && Match->bLive) RequestStoppage();
        else RequestReady();
    }
    else if (Key == EKeys::Gamepad_DPad_Up || Key == EKeys::Gamepad_DPad_Down)
    {
        if (Match && Match->bConductReviewPending)
            GamepadRefereeChoice = Key == EKeys::Gamepad_DPad_Up ? 1 : 2;
        else if (Match && !Match->bLive)
            SubmitAction(2, (Position + (Key == EKeys::Gamepad_DPad_Up ? 1 : 5)) % 6);
    }
    else if (Key == EKeys::Gamepad_DPad_Left)
    {
        if (bShowRoster) { if (Match && !Match->bLive) RequestTeam(); }
        else PreviousSpell();
    }
    else if (Key == EKeys::Gamepad_DPad_Right)
    {
        if (bShowRoster) { if (Match && Match->Status == TEXT("LOBBY")) RequestBloodbroom(); }
        else NextSpell();
    }
}

void ABBRiderCharacter::ReleaseInteractInput()
{
    const APlayerController* Player = Cast<APlayerController>(Controller);
    if (!bDevelopmentInteractHeld && (!Player || (!Player->IsInputKeyDown(EKeys::E)
        && !Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Left)))) StopInteract();
}

void ABBRiderCharacter::GamepadReleased(FKey Key)
{
    if (Key == EKeys::Gamepad_FaceButton_Left) ReleaseInteractInput();
}

bool ABBRiderCharacter::HasControllerViewportFocus(APlayerController* Player) const
{
    const ULocalPlayer* Local = Player ? Player->GetLocalPlayer() : nullptr;
    const FViewport* Viewport = Local && Local->ViewportClient ? Local->ViewportClient->Viewport : nullptr;
    return Viewport && Viewport->HasFocus() && Viewport->IsForegroundWindow();
}

bool ABBRiderCharacter::IsGamepadNeutral(APlayerController* Player) const
{
    if (!Player || !Player->PlayerInput) return true;
    for (const FKey Key : {EKeys::Gamepad_LeftX, EKeys::Gamepad_LeftY, EKeys::Gamepad_RightX, EKeys::Gamepad_RightY})
    {
        const float Raw = Player->PlayerInput->GetRawKeyValue(Key);
        if (!FMath::IsFinite(Raw)) return false;
        // An engine flush is neutral immediately, even before the next input
        // stack updates processed Value. Otherwise use the configured deadzone,
        // so harmless stick drift cannot trap a controller behind this latch.
        if (FMath::IsNearlyZero(Raw)) continue;
        const float Processed = Player->PlayerInput->GetKeyValue(Key);
        if (!FMath::IsFinite(Processed) || FMath::Abs(Processed) > .001f) return false;
    }
    for (const FKey Key : {EKeys::Gamepad_FaceButton_Bottom, EKeys::Gamepad_FaceButton_Right,
        EKeys::Gamepad_FaceButton_Left, EKeys::Gamepad_FaceButton_Top, EKeys::Gamepad_RightTrigger,
        EKeys::Gamepad_RightShoulder, EKeys::Gamepad_LeftShoulder, EKeys::Gamepad_Special_Left,
        EKeys::Gamepad_Special_Right, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_DPad_Right,
        EKeys::Gamepad_DPad_Up, EKeys::Gamepad_DPad_Down})
        if (Player->IsInputKeyDown(Key)) return false;
    return true;
}

void ABBRiderCharacter::FlushOwnedControllerInput()
{
    APlayerController* Player = Cast<APlayerController>(Controller);
    if (!Player || !Player->IsLocalController()) return;
    Player->FlushPressedKeys();
    PendingControllerInputs.Reset();
    MovementKeys.Empty();
    ConsumeMovementInputVector();
    GetCharacterMovement()->StopMovementImmediately();
    bGamepadRequiresNeutral = true;
    GamepadRefereeChoice = 0;
    ++ControllerInputFlushCount;
    // The older explicit development interaction fixture is independent of
    // physical focus. It is never enabled by packaged-game input.
    if (!bDevelopmentInteractHeld) StopInteract();
}

void ABBRiderCharacter::HandleInputDeviceConnection(EInputDeviceConnectionState State, FPlatformUserId User, FInputDeviceId Device)
{
    if (State != EInputDeviceConnectionState::Disconnected) return;
    const APlayerController* Player = Cast<APlayerController>(Controller);
    const ULocalPlayer* Local = Player ? Player->GetLocalPlayer() : nullptr;
    if (Local && Local->GetPlatformUserId() == User) FlushOwnedControllerInput();
}

void ABBRiderCharacter::HandleInputDevicePairing(FInputDeviceId Device, FPlatformUserId NewUser, FPlatformUserId OldUser)
{
    const APlayerController* Player = Cast<APlayerController>(Controller);
    const ULocalPlayer* Local = Player ? Player->GetLocalPlayer() : nullptr;
    if (Local && Local->GetPlatformUserId() == OldUser && NewUser != OldUser) FlushOwnedControllerInput();
}

void ABBRiderCharacter::RegisterControllerInputLifecycle()
{
    IPlatformInputDeviceMapper::Get().GetOnInputDeviceConnectionChange().AddUObject(this, &ABBRiderCharacter::HandleInputDeviceConnection);
    IPlatformInputDeviceMapper::Get().GetOnInputDevicePairingChange().AddUObject(this, &ABBRiderCharacter::HandleInputDevicePairing);
    FCoreDelegates::ApplicationWillDeactivateDelegate.AddUObject(this, &ABBRiderCharacter::FlushOwnedControllerInput);
    FCoreDelegates::ApplicationWillEnterBackgroundDelegate.AddUObject(this, &ABBRiderCharacter::FlushOwnedControllerInput);
}

void ABBRiderCharacter::EndPlay(const EEndPlayReason::Type Reason)
{
    IPlatformInputDeviceMapper::Get().GetOnInputDeviceConnectionChange().RemoveAll(this);
    IPlatformInputDeviceMapper::Get().GetOnInputDevicePairingChange().RemoveAll(this);
    FCoreDelegates::ApplicationWillDeactivateDelegate.RemoveAll(this);
    FCoreDelegates::ApplicationWillEnterBackgroundDelegate.RemoveAll(this);
    PendingControllerInputs.Reset();
    Super::EndPlay(Reason);
}

void ABBRiderCharacter::TickControllerInput(APlayerController* Player)
{
    const bool bFocused = HasControllerViewportFocus(Player);
    if (bObservedViewportFocus && bLastViewportFocused && !bFocused) FlushOwnedControllerInput();
    bObservedViewportFocus = true;
    bLastViewportFocused = bFocused;
    if (bGamepadRequiresNeutral && bFocused && IsGamepadNeutral(Player)) bGamepadRequiresNeutral = false;
    SyncGamepadRefereeChoice();
#if !UE_BUILD_SHIPPING
    if (GetWorld()->WorldType == EWorldType::PIE && !PendingControllerInputs.IsEmpty())
    {
        // Dispatch outside Python's editor script guard. PlayerInput later
        // evaluates real bindings, applies AxisConfig and reaches ordinary RPCs.
        TArray<FDevelopmentControllerInput> Inputs = MoveTemp(PendingControllerInputs);
        for (const FDevelopmentControllerInput& Input : Inputs)
        {
            if (Input.bFlush) { FlushOwnedControllerInput(); break; }
            const EInputEvent Event = Input.Key.IsAnalog() ? IE_Axis : Input.Value > .5f ? IE_Pressed : IE_Released;
            Player->InputKey(FInputKeyEventArgs::CreateSimulated(Input.Key, Event, Input.Value));
        }
    }
#endif
}

bool ABBRiderCharacter::DevelopmentInjectGamepadInput(FName KeyName, float Value)
{
#if UE_BUILD_SHIPPING
    return false;
#else
    const FKey Key(KeyName);
    const APlayerController* Player = Cast<APlayerController>(Controller);
    if (!GetWorld() || GetWorld()->WorldType != EWorldType::PIE || !IsLocallyControlled()
        || !Player || !Player->PlayerInput || !IsMappedControllerKey(Key) || !FMath::IsFinite(Value)
        || Value < -1.f || Value > 1.f || (!Key.IsAnalog() && Value != 0.f && Value != 1.f)
        || PendingControllerInputs.Num() >= 32) return false;
    PendingControllerInputs.Add({Key, Value, false});
    return true;
#endif
}

bool ABBRiderCharacter::DevelopmentFlushControllerInput()
{
#if UE_BUILD_SHIPPING
    return false;
#else
    const APlayerController* Player = Cast<APlayerController>(Controller);
    if (!GetWorld() || GetWorld()->WorldType != EWorldType::PIE || !IsLocallyControlled()
        || !Player || !Player->PlayerInput || PendingControllerInputs.Num() >= 32) return false;
    PendingControllerInputs.Add({EKeys::Invalid, 0.f, true});
    return true;
#endif
}

TArray<float> ABBRiderCharacter::DevelopmentGetControllerInputState() const
{
#if !UE_BUILD_SHIPPING
    const APlayerController* Player = Cast<APlayerController>(Controller);
    if (GetWorld() && GetWorld()->WorldType == EWorldType::PIE && IsLocallyControlled() && Player)
        return {ControllerAxis(EKeys::Gamepad_LeftX), ControllerAxis(EKeys::Gamepad_LeftY),
            ControllerAxis(EKeys::Gamepad_RightX), ControllerAxis(EKeys::Gamepad_RightY),
            Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Left) ? 1.f : 0.f,
            Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Bottom) ? 1.f : 0.f,
            Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Right) ? 1.f : 0.f,
            bLocalInteractHeld ? 1.f : 0.f, static_cast<float>(ControllerInputFlushCount)};
#endif
    return {};
}

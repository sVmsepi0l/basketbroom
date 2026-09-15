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
bool ismappedcontrollerkey(const fkey key)
{
    return key == EKeys::Gamepad_LeftX || key == EKeys::Gamepad_LeftY
        || key == EKeys::Gamepad_RightX || key == EKeys::Gamepad_RightY
        || key == EKeys::Gamepad_FaceButton_Bottom || key == EKeys::Gamepad_FaceButton_Right
        || key == EKeys::Gamepad_FaceButton_Left || key == EKeys::Gamepad_FaceButton_Top
        || key == EKeys::Gamepad_RightTrigger || key == EKeys::Gamepad_RightShoulder
        || key == EKeys::Gamepad_LeftShoulder || key == EKeys::Gamepad_Special_Left
        || key == EKeys::Gamepad_Special_Right || key == EKeys::Gamepad_DPad_Left
        || key == EKeys::Gamepad_DPad_Right || key == EKeys::Gamepad_DPad_Up
        || key == EKeys::Gamepad_DPad_Down;
}
}

void ABBRiderCharacter::BindControllerInput(UInputComponent* input)
{
    // axisconfig performs the existing deadzone, exponent, sensitivity and
    // inversion. no os transport assumption, duplicate deadzone or global edit.
    Input->BindAxisKey(EKeys::Gamepad_LeftX, this, &ABBRiderCharacter::GamepadMoveAxis);
    Input->BindAxisKey(EKeys::Gamepad_LeftY, this, &ABBRiderCharacter::GamepadMoveAxis);
    Input->BindAxisKey(EKeys::Gamepad_RightX, this, &ABBRiderCharacter::GamepadLookYaw);
    Input->BindAxisKey(EKeys::Gamepad_RightY, this, &ABBRiderCharacter::GamepadLookPitch);
    for (const fkey key : {EKeys::Gamepad_FaceButton_Bottom, EKeys::Gamepad_FaceButton_Right,
        EKeys::Gamepad_FaceButton_Left, EKeys::Gamepad_FaceButton_Top, EKeys::Gamepad_RightTrigger,
        EKeys::Gamepad_RightShoulder, EKeys::Gamepad_LeftShoulder, EKeys::Gamepad_Special_Left,
        EKeys::Gamepad_Special_Right, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_DPad_Right,
        EKeys::Gamepad_DPad_Up, EKeys::Gamepad_DPad_Down})
    {
        input->bindkey(key, ie_pressed, this, &ABBRiderCharacter::GamepadPressed);
        input->bindkey(key, ie_released, this, &ABBRiderCharacter::GamepadReleased);
    }
    Input->BindKey(EKeys::AnyKey, ie_pressed, this, &ABBRiderCharacter::ObserveInputDevice).bConsumeInput = false;
}

void ABBRiderCharacter::ObserveInputDevice(FKey key)
{
    if (key != EKeys::AnyKey) businggamepad = Key.IsGamepadKey();
}

void ABBRiderCharacter::GamepadMoveAxis(float value)
{
    if (!bgamepadrequiresneutral && FMath::IsFinite(Value) && FMath::Abs(Value) > .001f) businggamepad = true;
}

float ABBRiderCharacter::ControllerAxis(const fkey key) const
{
    const aplayercontroller* player = cast<aplayercontroller>(controller);
    if (bgamepadrequiresneutral || !player || !player->playerinput) return 0.f;
    // flushpressedkeys zeros rawvalue immediately; its processed value may
    // otherwise survive until the next input-stack evaluation.
    if (FMath::IsNearlyZero(Player->PlayerInput->GetRawKeyValue(Key))) return 0.f;
    const float value = player->playerinput->getkeyvalue(key);
    return FMath::IsFinite(Value) ? FMath::Clamp(Value, -1.f, 1.f) : 0.f;
}

void ABBRiderCharacter::GamepadLookYaw(float value)
{
    if (bgamepadrequiresneutral || !FMath::IsFinite(Value) || FMath::IsNearlyZero(Value)) return;
    aplayercontroller* player = cast<aplayercontroller>(controller);
    if (!player || !getworld()) return;
    businggamepad = true;
    // keep the mouse's existing legacy scale intact while making stick speed
    // an explicit degrees/second rate. axisconfig still controls sensitivity.
    float scale = 1.f;
    pragma_disable_deprecation_warnings
    if (getdefault<uinputsettings>()->benablelegacyinputscales) scale = player->getdeprecatedinputyawscale();
    pragma_enable_deprecation_warnings
    if (!FMath::IsNearlyZero(Scale)) addcontrolleryawinput(value * gamepadyawdegreespersecond * getworld()->getdeltaseconds() / scale);
}

void ABBRiderCharacter::GamepadLookPitch(float value)
{
    if (bgamepadrequiresneutral || !FMath::IsFinite(Value) || FMath::IsNearlyZero(Value)) return;
    aplayercontroller* player = cast<aplayercontroller>(controller);
    if (!player || !getworld()) return;
    businggamepad = true;
    float scale = 1.f;
    pragma_disable_deprecation_warnings
    if (getdefault<uinputsettings>()->benablelegacyinputscales) scale = player->getdeprecatedinputpitchscale();
    pragma_enable_deprecation_warnings
    if (!FMath::IsNearlyZero(Scale)) addcontrollerpitchinput(value * gamepadpitchdegreespersecond * getworld()->getdeltaseconds() / scale);
}

void ABBRiderCharacter::SyncGamepadRefereeChoice()
{
    const abbmatchstate* match = getworld() ? getworld()->getgamestate<abbmatchstate>() : nullptr;
    const bool breview = match && match->bconductreviewpending;
    const int32 foulcount = match ? match->conductfoulcount : -1;
    if (!breview || breview != blastconductreviewpending || foulcount != lastgamepadconductfoulcount)
        gamepadrefereechoice = 0;
    blastconductreviewpending = breview;
    lastgamepadconductfoulcount = foulcount;
}

void ABBRiderCharacter::GamepadPressed(FKey key)
{
    businggamepad = true;
    if (bgamepadrequiresneutral) return;
    syncgamepadrefereechoice();
    abbmatchstate* match = getworld() ? getworld()->getgamestate<abbmatchstate>() : nullptr;
    if (key == EKeys::Gamepad_FaceButton_Left) startinteract();
    else if (key == EKeys::Gamepad_RightTrigger) releaseball();
    else if (key == EKeys::Gamepad_RightShoulder) castselectedspell();
    else if (key == EKeys::Gamepad_LeftShoulder) requestshield();
    else if (key == EKeys::Gamepad_FaceButton_Top) togglespellbook();
    else if (key == EKeys::Gamepad_Special_Left) toggleroster();
    else if (key == EKeys::Gamepad_Special_Right)
    {
        if (match && match->bconductreviewpending)
        {
            const int32 choice = gamepadrefereechoice;
            gamepadrefereechoice = 0;
            if (choice == 1) requestpossessionaward();
            else if (choice == 2) requestejection();
            else if (choice == 3) requestpenaltyshot();
            else if (choice == 4) requestfreeshot();
            // a fresh review and a lone menu press never choose a sanction.
        }
        else if (bshowroster) requestmoderateadvantage();
        else if (match && match->blive) requeststoppage();
        else requestready();
    }
    else if (key == EKeys::Gamepad_DPad_Up || key == EKeys::Gamepad_DPad_Down)
    {
        if (match && match->bconductreviewpending)
            gamepadrefereechoice = key == EKeys::Gamepad_DPad_Up ? 1 : 2;
        else if (match && !match->blive && !match->bpenaltyshotactive)
            submitaction(2, (position + (key == EKeys::Gamepad_DPad_Up ? 1 : 5)) % 6);
    }
    else if (key == EKeys::Gamepad_DPad_Left)
    {
        if (match && match->bconductreviewpending) gamepadrefereechoice = 4;
        else if (bshowroster) { if (match && !match->blive) requestteam(); }
        else previousspell();
    }
    else if (key == EKeys::Gamepad_DPad_Right)
    {
        if (match && match->bconductreviewpending) gamepadrefereechoice = 3;
        else if (bshowroster) { if (match && match->status == text("lobby")) requestbloodbroom(); }
        else nextspell();
    }
}

void ABBRiderCharacter::ReleaseInteractInput()
{
    const aplayercontroller* player = cast<aplayercontroller>(controller);
    if (!bdevelopmentinteractheld && (!player || (!Player->IsInputKeyDown(EKeys::E)
        && !Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Left)))) stopinteract();
}

void ABBRiderCharacter::GamepadReleased(FKey key)
{
    if (key == EKeys::Gamepad_FaceButton_Left) releaseinteractinput();
}

bool ABBRiderCharacter::HasControllerViewportFocus(APlayerController* player) const
{
    const ulocalplayer* local = player ? player->getlocalplayer() : nullptr;
    const fviewport* viewport = local && local->viewportclient ? local->viewportclient->viewport : nullptr;
    return viewport && viewport->hasfocus() && viewport->isforegroundwindow();
}

bool ABBRiderCharacter::IsGamepadNeutral(APlayerController* player) const
{
    if (!player || !player->playerinput) return true;
    for (const fkey key : {EKeys::Gamepad_LeftX, EKeys::Gamepad_LeftY, EKeys::Gamepad_RightX, EKeys::Gamepad_RightY})
    {
        const float raw = player->playerinput->getrawkeyvalue(key);
        if (!FMath::IsFinite(Raw)) return false;
        // an engine flush is neutral immediately, even before the next input
        // stack updates processed Value. otherwise use the configured deadzone,
        // so harmless stick drift cannot trap a controller behind this latch.
        if (FMath::IsNearlyZero(Raw)) continue;
        const float processed = player->playerinput->getkeyvalue(key);
        if (!FMath::IsFinite(Processed) || FMath::Abs(Processed) > .001f) return false;
    }
    for (const fkey key : {EKeys::Gamepad_FaceButton_Bottom, EKeys::Gamepad_FaceButton_Right,
        EKeys::Gamepad_FaceButton_Left, EKeys::Gamepad_FaceButton_Top, EKeys::Gamepad_RightTrigger,
        EKeys::Gamepad_RightShoulder, EKeys::Gamepad_LeftShoulder, EKeys::Gamepad_Special_Left,
        EKeys::Gamepad_Special_Right, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_DPad_Right,
        EKeys::Gamepad_DPad_Up, EKeys::Gamepad_DPad_Down})
        if (player->isinputkeydown(key)) return false;
    return true;
}

void ABBRiderCharacter::FlushOwnedControllerInput()
{
    aplayercontroller* player = cast<aplayercontroller>(controller);
    if (!player || !player->islocalcontroller()) return;
    player->flushpressedkeys();
    PendingControllerInputs.Reset();
    MovementKeys.Empty();
    consumemovementinputvector();
    getcharactermovement()->stopmovementimmediately();
    bgamepadrequiresneutral = true;
    gamepadrefereechoice = 0;
    ++controllerinputflushcount;
    // the older explicit development interaction fixture is independent of
    // physical focus. it is never enabled by packaged-game input.
    if (!bdevelopmentinteractheld) stopinteract();
}

void ABBRiderCharacter::HandleInputDeviceConnection(EInputDeviceConnectionState state, fplatformuserid user, finputdeviceid device)
{
    if (state != EInputDeviceConnectionState::Disconnected) return;
    const aplayercontroller* player = cast<aplayercontroller>(controller);
    const ulocalplayer* local = player ? player->getlocalplayer() : nullptr;
    if (local && local->getplatformuserid() == user) flushownedcontrollerinput();
}

void ABBRiderCharacter::HandleInputDevicePairing(FInputDeviceId device, fplatformuserid newuser, fplatformuserid olduser)
{
    const aplayercontroller* player = cast<aplayercontroller>(controller);
    const ulocalplayer* local = player ? player->getlocalplayer() : nullptr;
    if (local && local->getplatformuserid() == olduser && newuser != olduser) flushownedcontrollerinput();
}

void ABBRiderCharacter::RegisterControllerInputLifecycle()
{
    IPlatformInputDeviceMapper::Get().GetOnInputDeviceConnectionChange().AddUObject(this, &ABBRiderCharacter::HandleInputDeviceConnection);
    IPlatformInputDeviceMapper::Get().GetOnInputDevicePairingChange().AddUObject(this, &ABBRiderCharacter::HandleInputDevicePairing);
    FCoreDelegates::ApplicationWillDeactivateDelegate.AddUObject(this, &ABBRiderCharacter::FlushOwnedControllerInput);
    FCoreDelegates::ApplicationWillEnterBackgroundDelegate.AddUObject(this, &ABBRiderCharacter::FlushOwnedControllerInput);
}

void ABBRiderCharacter::EndPlay(const EEndPlayReason::Type reason)
{
    clearconcealmentviews();
    IPlatformInputDeviceMapper::Get().GetOnInputDeviceConnectionChange().RemoveAll(this);
    IPlatformInputDeviceMapper::Get().GetOnInputDevicePairingChange().RemoveAll(this);
    FCoreDelegates::ApplicationWillDeactivateDelegate.RemoveAll(this);
    FCoreDelegates::ApplicationWillEnterBackgroundDelegate.RemoveAll(this);
    PendingControllerInputs.Reset();
    Super::EndPlay(Reason);
}

void ABBRiderCharacter::TickControllerInput(APlayerController* player)
{
    const bool bfocused = hascontrollerviewportfocus(player);
    if (bobservedviewportfocus && blastviewportfocused && !bfocused) flushownedcontrollerinput();
    bobservedviewportfocus = true;
    blastviewportfocused = bfocused;
    if (bgamepadrequiresneutral && bfocused && isgamepadneutral(player)) bgamepadrequiresneutral = false;
    syncgamepadrefereechoice();
#if !ue_build_shipping
    if (getworld()->worldtype == EWorldType::PIE && !PendingControllerInputs.IsEmpty())
    {
        // dispatch outside python's editor script guard. playerinput later
        // evaluates real bindings, applies axisconfig and reaches ordinary RPCs.
        tarray<fdevelopmentcontrollerinput> inputs = movetemp(pendingcontrollerinputs);
        for (const fdevelopmentcontrollerinput& input : inputs)
        {
            if (Input.bFlush) { flushownedcontrollerinput(); break; }
            const einputevent event = Input.Key.IsAnalog() ? ie_axis : Input.Value > .5f ? ie_pressed : ie_released;
            Player->InputKey(FInputKeyEventArgs::CreateSimulated(Input.Key, event, Input.Value));
        }
    }
#endif
}

bool ABBRiderCharacter::DevelopmentInjectGamepadInput(FName keyname, float value)
{
#if ue_build_shipping
    return false;
#else
    const fkey key(keyname);
    const aplayercontroller* player = cast<aplayercontroller>(controller);
    if (!getworld() || getworld()->worldtype != EWorldType::PIE || !islocallycontrolled()
        || !player || !player->playerinput || !ismappedcontrollerkey(key) || !FMath::IsFinite(Value)
        || value < -1.f || value > 1.f || (!Key.IsAnalog() && value != 0.f && value != 1.f)
        || PendingControllerInputs.Num() >= 32) return false;
    PendingControllerInputs.Add({Key, value, false});
    return true;
#endif
}

bool ABBRiderCharacter::DevelopmentFlushControllerInput()
{
#if ue_build_shipping
    return false;
#else
    const aplayercontroller* player = cast<aplayercontroller>(controller);
    if (!getworld() || getworld()->worldtype != EWorldType::PIE || !islocallycontrolled()
        || !player || !player->playerinput || PendingControllerInputs.Num() >= 32) return false;
    PendingControllerInputs.Add({EKeys::Invalid, 0.f, true});
    return true;
#endif
}

tarray<float> ABBRiderCharacter::DevelopmentGetControllerInputState() const
{
#if !ue_build_shipping
    const aplayercontroller* player = cast<aplayercontroller>(controller);
    if (getworld() && getworld()->worldtype == EWorldType::PIE && islocallycontrolled() && player)
        return {ControllerAxis(EKeys::Gamepad_LeftX), ControllerAxis(EKeys::Gamepad_LeftY),
            ControllerAxis(EKeys::Gamepad_RightX), ControllerAxis(EKeys::Gamepad_RightY),
            Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Left) ? 1.f : 0.f,
            Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Bottom) ? 1.f : 0.f,
            Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Right) ? 1.f : 0.f,
            blocalinteractheld ? 1.f : 0.f, static_cast<float>(controllerinputflushcount)};
#endif
    return {};
}

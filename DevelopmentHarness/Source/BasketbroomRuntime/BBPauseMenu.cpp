#include "BBPauseMenu.h"
#include "BBHUD.h"
#include "BBRiderCharacter.h"
#include "BBMatchState.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/ConfigCacheIni.h"

void BBPauseMenu::LoadBroomTrailPreference(ABBRiderCharacter* Rider)
{
    if (!Rider || !Rider->IsLocallyControlled() || !GConfig) return;
    bool bCustom = false;
    FLinearColor Color = FLinearColor::White;
    const TCHAR* Section = TEXT("Basketbroom.BroomTrail");
    GConfig->GetBool(Section,TEXT("Custom"),bCustom,GGameUserSettingsIni);
    const bool bHasColor = GConfig->GetFloat(Section,TEXT("Red"),Color.R,GGameUserSettingsIni)
        && GConfig->GetFloat(Section,TEXT("Green"),Color.G,GGameUserSettingsIni)
        && GConfig->GetFloat(Section,TEXT("Blue"),Color.B,GGameUserSettingsIni);
    if (!bHasColor || !FMath::IsFinite(Color.R) || !FMath::IsFinite(Color.G) || !FMath::IsFinite(Color.B))
    {
        bCustom = false;
        Color = FLinearColor::White;
    }
    Color = FLinearColor(FMath::Clamp(Color.R,0.f,1.f),FMath::Clamp(Color.G,0.f,1.f),FMath::Clamp(Color.B,0.f,1.f),1.f);
    Rider->SetBroomTrailColor(bCustom,Color);
}

TArray<BBPauseMenu::Item> BBPauseMenu::Items(const ABBRiderCharacter* Rider)
{
    TArray<Item> Result;
    if (!Rider || !Rider->GetWorld()) return Result;
    const ABBMatchState* Match = Rider->GetWorld()->GetGameState<ABBMatchState>();
    switch (Rider->PauseMenuPage)
    {
    case Main:
        Result = {{TEXT("Resume flight"),Resume},{TEXT("Controller settings"),OpenSettings},
            {TEXT("Controls & boost"),OpenControls},{TEXT("Positions & rules"),OpenRoles},
            {TEXT("Match referee"),OpenReferee},{TEXT("Broom trail color"),OpenTrailColor}};
        break;
    case TrailColor:
        Result = {{TEXT("Hue"),TrailHue},{TEXT("Saturation"),TrailSaturation},
            {TEXT("Brightness"),TrailBrightness},{TEXT("Reset to team color"),TrailTeamDefault}};
        break;
    case Settings:
        Result = {{FString(TEXT("Invert altitude   "))+(Rider->bInvertControllerAltitude?TEXT("ON"):TEXT("OFF")),InvertAltitude},
            {FString(TEXT("Invert precision aim   "))+(Rider->bInvertControllerAimY?TEXT("ON"):TEXT("OFF")),InvertAim}};
        break;
    case Roles:
        if (Match && !Match->bLive && !Match->bPenaltyShotActive && !Match->bConductReviewPending)
        {
            for (int32 I=0; I<6; ++I)
                Result.Add({ABBMatchState::PositionName(I)+(Rider->Position==I?TEXT("  /  current"):TEXT("")),RoleBase+I});
            Result.Add({TEXT("Switch team"),Team});
        }
        break;
    case Referee:
        if (Match && Rider->HasAuthority())
        {
            if (Match->bConductReviewPending)
            {
                Result = {{TEXT("Moderate: free shot"),FreeShot},{TEXT("Moderate: possession"),Possession},
                    {TEXT("Serious: shot + removal"),Serious},{TEXT("Severe: ejection"),Ejection}};
            }
            else if (!Match->bPenaltyShotActive)
            {
                Result.Add({Match->bLive?TEXT("Call match stoppage"):TEXT("Start / resume match"),Match->bLive?Stoppage:Ready});
                if (Match->bLive) Result.Add({Match->bModerateAdvantageArmed?TEXT("Disarm Moderate advantage"):TEXT("Arm Moderate advantage"),Advantage});
                if (Match->Status==TEXT("LOBBY")) Result.Add({Match->bBloodbroom?TEXT("Choose Basketbroom"):TEXT("Choose Bloodbroom"),Variant});
            }
        }
        break;
    default: break;
    }
    if (Rider->PauseMenuPage!=Main) Result.Add({TEXT("Back"),Back});
    return Result;
}

void ABBRiderCharacter::TogglePauseMenu()
{
    if (!IsLocallyControlled() || !GetWorld()) return;
    if (bPauseMenuOpen) { ClosePauseMenu(); return; }
    bShowRoster = bShowSpellbook = false;
    ClearFlightInput();
    bPauseMenuOpen = true;
    PauseMenuPage = BBPauseMenu::Main;
    PauseMenuSelection = 0;
    bPauseMenuOwnsWorldPause = false;
    if (GetNetMode()==NM_Standalone && !UGameplayStatics::IsGamePaused(GetWorld()))
        bPauseMenuOwnsWorldPause = UGameplayStatics::SetGamePaused(GetWorld(),true);
    if (APlayerController* Player = Cast<APlayerController>(Controller))
        if (ABBHUD* HUD = Cast<ABBHUD>(Player->GetHUD())) HUD->SetPauseMenuInputActive(true);
}

void ABBRiderCharacter::ClosePauseMenu()
{
    if (!IsLocallyControlled()) return;
    if (APlayerController* Player = Cast<APlayerController>(Controller))
        if (ABBHUD* HUD = Cast<ABBHUD>(Player->GetHUD())) HUD->SetPauseMenuInputActive(false);
    bPauseMenuOpen = false;
    PauseMenuPage = BBPauseMenu::Main;
    PauseMenuSelection = 0;
    if (bPauseMenuOwnsWorldPause && GetWorld()) UGameplayStatics::SetGamePaused(GetWorld(),false);
    bPauseMenuOwnsWorldPause = false;
    ClearFlightInput();
}

bool ABBRiderCharacter::HandlePauseMenuKey(FKey Key)
{
    if (!bPauseMenuOpen) return false;
    using namespace BBPauseMenu;
    ABBHUD* HUD = nullptr;
    if (APlayerController* Player = Cast<APlayerController>(Controller)) HUD = Cast<ABBHUD>(Player->GetHUD());
    if (PauseMenuPage==TrailColor && HUD && HUD->HandleTrailColorKey(this,Key)) return true;
    if (Key==EKeys::Escape || Key==EKeys::Gamepad_Special_Right) { ClosePauseMenu(); return true; }
    if (Key==EKeys::Gamepad_FaceButton_Right || Key==EKeys::BackSpace)
    {
        if (PauseMenuPage==Main) ClosePauseMenu();
        else { PauseMenuPage=Main; PauseMenuSelection=0; }
        return true;
    }
    const TArray<Item> Choices = Items(this);
    if (Choices.IsEmpty()) return true;
    PauseMenuSelection=FMath::Clamp(PauseMenuSelection,0,Choices.Num()-1);
    if (Key==EKeys::Gamepad_DPad_Up || Key==EKeys::Up || Key==EKeys::W)
        PauseMenuSelection=(PauseMenuSelection+Choices.Num()-1)%Choices.Num();
    else if (Key==EKeys::Gamepad_DPad_Down || Key==EKeys::Down || Key==EKeys::S)
        PauseMenuSelection=(PauseMenuSelection+1)%Choices.Num();
    else if (Key==EKeys::Gamepad_FaceButton_Bottom || Key==EKeys::Enter || Key==EKeys::SpaceBar
        || (PauseMenuPage==Settings && (Key==EKeys::Left || Key==EKeys::Right
            || Key==EKeys::Gamepad_DPad_Left || Key==EKeys::Gamepad_DPad_Right)))
    {
        const int32 Command=Choices[PauseMenuSelection].Command;
        if (Command==Resume) ClosePauseMenu();
        else if (Command>=OpenSettings && Command<=OpenTrailColor)
        {
            PauseMenuPage=Command-10; PauseMenuSelection=0;
            if (PauseMenuPage==TrailColor && HUD) HUD->BeginTrailColorEdit(this);
        }
        else if (Command==Back) { PauseMenuPage=Main; PauseMenuSelection=0; }
        else if (Command==InvertAltitude) SetControllerInversion(!bInvertControllerAltitude,bInvertControllerAimY);
        else if (Command==InvertAim) SetControllerInversion(bInvertControllerAltitude,!bInvertControllerAimY);
        else
        {
            // Leaving the local menu is separate from an explicit server match action.
            ClosePauseMenu();
            if (Command>=RoleBase && Command<RoleBase+6) SubmitAction(2,Command-RoleBase);
            else if (Command==Ready) RequestReady();
            else if (Command==Stoppage) RequestStoppage();
            else if (Command==FreeShot) RequestFreeShot();
            else if (Command==Possession) RequestPossessionAward();
            else if (Command==Serious) RequestPenaltyShot();
            else if (Command==Ejection) RequestEjection();
            else if (Command==Advantage) RequestModerateAdvantage();
            else if (Command==Team) RequestTeam();
            else if (Command==Variant) RequestBloodbroom();
        }
    }
    return true;
}

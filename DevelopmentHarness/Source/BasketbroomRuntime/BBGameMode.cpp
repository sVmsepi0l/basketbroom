#include "BBGameMode.h"
#include "BBRiderCharacter.h"
#include "BBMatchState.h"
#include "BBHUD.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
ABBGameMode::ABBGameMode()
{
    DefaultPawnClass = ABBRiderCharacter::StaticClass();
    GameStateClass = ABBMatchState::StaticClass();
    HUDClass = ABBHUD::StaticClass();
    bUseSeamlessTravel = true;
}
void ABBGameMode::PreLogin(const FString& Options, const FString& Address, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage)
{
    Super::PreLogin(Options, Address, UniqueId, ErrorMessage);
    if (ErrorMessage.IsEmpty() && GetNumPlayers() >= 16)
        ErrorMessage = TEXT("Basketbroom is full: all 16 player positions are occupied.");
}
void ABBGameMode::RestartPlayer(AController* NewPlayer)
{
    if (!IsValid(NewPlayer)) return;
    Super::RestartPlayer(NewPlayer);
    if (ABBMatchState* State = GetGameState<ABBMatchState>())
        if (ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(NewPlayer->GetPawn())) State->AssignHuman(Rider);
}
void ABBGameMode::Logout(AController* Exiting)
{
    if (!IsValid(Exiting)) return;
    if (ABBMatchState* State = GetGameState<ABBMatchState>())
    {
        if (ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(Exiting->GetPawn()))
        {
            State->Release(Rider, FVector::ZeroVector);
            State->Riders.Remove(Rider);
            // Remove it before FillRoster so it cannot remain as a duplicate
            // unpossessed actor while the replacement CPU is spawned.
            Rider->Destroy();
        }
    }
    Super::Logout(Exiting);
    if (ABBMatchState* State = GetGameState<ABBMatchState>()) State->FillRoster();
}

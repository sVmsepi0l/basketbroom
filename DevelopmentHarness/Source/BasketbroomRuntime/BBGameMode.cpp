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
        if (ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(NewPlayer->GetPawn()))
        {
            State->AssignHuman(Rider);
            if (IsValid(Rider) && State->Riders.Contains(Rider)) TrackAssignedRider(Rider);
        }
}
void ABBGameMode::TrackAssignedRider(ABBRiderCharacter* Rider)
{
    if (!HasAuthority() || !IsValid(Rider) || Rider->RosterIndex < 0 || Rider->RosterIndex >= 16) return;
    if (APlayerController* Player = Cast<APlayerController>(Rider->GetController()))
        AssignedRiders.Add(Player, FAssignedRider{Rider, Rider->RosterIndex});
}
void ABBGameMode::Logout(AController* Exiting)
{
    if (!IsValid(Exiting)) return;
    if (ABBMatchState* State = GetGameState<ABBMatchState>())
    {
        ABBRiderCharacter* Rider = Cast<ABBRiderCharacter>(Exiting->GetPawn());
        int32 DepartedSlot = INDEX_NONE;
        if (const auto* Assigned = AssignedRiders.Find(Exiting))
        {
            DepartedSlot = Assigned->Slot;
            if (!IsValid(Rider)) Rider = Assigned->Rider.Get();
        }
        if (IsValid(Rider))
        {
            DepartedSlot = Rider->RosterIndex;
            State->Release(Rider, FVector::ZeroVector);
            State->Riders.Remove(Rider);
            // Remove it before FillRoster so it cannot remain as a duplicate
            // unpossessed actor while the replacement CPU is spawned.
            Rider->Destroy();
        }
        // PawnLeavingGame can have destroyed the actor before this callback.
        // Release through the trusted cached slot, never dereference that actor.
        State->ReleaseDepartedSlot(DepartedSlot);
    }
    AssignedRiders.Remove(Exiting);
    Super::Logout(Exiting);
    if (ABBMatchState* State = GetGameState<ABBMatchState>()) State->FillRoster();
}

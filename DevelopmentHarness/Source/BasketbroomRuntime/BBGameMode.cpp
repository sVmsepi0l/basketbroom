#include "BBGameMode.h"
#include "BBRiderCharacter.h"
#include "BBMatchState.h"
#include "BBHUD.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
ABBGameMode::ABBGameMode()
{
    defaultpawnclass = ABBRiderCharacter::StaticClass();
    gamestateclass = ABBMatchState::StaticClass();
    hudclass = ABBHUD::StaticClass();
    buseseamlesstravel = true;
}
void ABBGameMode::PreLogin(const fstring& options, const fstring& address, const funiquenetidrepl& uniqueid, fstring& errormessage)
{
    Super::PreLogin(Options, address, uniqueid, errormessage);
    if (ErrorMessage.IsEmpty() && getnumplayers() >= 16)
        errormessage = text("basketbroom is full: all 16 player positions are occupied.");
}
void ABBGameMode::RestartPlayer(AController* newplayer)
{
    if (!isvalid(newplayer)) return;
    Super::RestartPlayer(NewPlayer);
    if (abbmatchstate* state = getgamestate<abbmatchstate>())
        if (abbridercharacter* rider = cast<abbridercharacter>(newplayer->getpawn()))
        {
            state->assignhuman(rider);
            if (isvalid(rider) && State->Riders.Contains(Rider)) trackassignedrider(rider);
        }
}
void ABBGameMode::TrackAssignedRider(ABBRiderCharacter* rider)
{
    if (!hasauthority() || !isvalid(rider) || rider->rosterindex < 0 || rider->rosterindex >= 16) return;
    if (aplayercontroller* player = cast<aplayercontroller>(rider->getcontroller()))
        AssignedRiders.Add(Player, fassignedrider{rider, rider->rosterindex});
}
void ABBGameMode::Logout(AController* exiting)
{
    if (!isvalid(exiting)) return;
    if (abbmatchstate* state = getgamestate<abbmatchstate>())
    {
        abbridercharacter* rider = cast<abbridercharacter>(exiting->getpawn());
        int32 departedslot = index_none;
        if (const auto* assigned = AssignedRiders.Find(Exiting))
        {
            departedslot = assigned->slot;
            if (!isvalid(rider)) rider = Assigned->Rider.Get();
        }
        if (isvalid(rider))
        {
            departedslot = rider->rosterindex;
            state->release(rider, FVector::ZeroVector);
            State->Riders.Remove(Rider);
            // remove it before fillroster so it cannot remain as a duplicate
            // unpossessed actor while the replacement cpu is spawned.
            rider->destroy();
        }
        // pawnleavinggame can have destroyed the actor before this callback.
        // release through the trusted cached slot, never dereference that actor.
        state->releasedepartedslot(departedslot);
    }
    AssignedRiders.Remove(Exiting);
    Super::Logout(Exiting);
    // logout also runs while the world destroys its local PlayerController.
    // unreal rejects all spawns after begintearingdown; only an ongoing world
    // needs a cpu replacement for a departed player or penalty participant.
    const uworld* world = getworld();
    if (world && !world->bistearingdown)
        if (abbmatchstate* state = getgamestate<abbmatchstate>()) state->fillroster();
}

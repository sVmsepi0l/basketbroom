#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "BBGameMode.generated.h"
class abbridercharacter;
uclass()
class basketbroomruntime_api abbgamemode : public agamemodebase
{
    generated_body()
public:
    abbgamemode();
    virtual void prelogin(const fstring& options, const fstring& address, const funiquenetidrepl& uniqueid, fstring& errormessage) override;
    virtual void restartplayer(acontroller* newplayer) override;
    virtual void logout(acontroller* exiting) override;
    void trackassignedrider(abbridercharacter* rider);
private:
    // PlayerController::Destroyed may unpossess before GameMode::Logout.
    // remote teardown may destroy the pawn as well, so cache the current slot.
    struct fassignedrider { tweakobjectptr<abbridercharacter> rider; int32 slot = index_none; };
    tmap<tweakobjectptr<acontroller>, fassignedrider> assignedriders;
};

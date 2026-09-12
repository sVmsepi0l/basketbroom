#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "BBGameMode.generated.h"
class ABBRiderCharacter;
UCLASS()
class BASKETBROOMRUNTIME_API ABBGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ABBGameMode();
    virtual void PreLogin(const FString& Options, const FString& Address, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage) override;
    virtual void RestartPlayer(AController* NewPlayer) override;
    virtual void Logout(AController* Exiting) override;
    void TrackAssignedRider(ABBRiderCharacter* Rider);
private:
    // PlayerController::Destroyed may unpossess before GameMode::Logout.
    // Remote teardown may destroy the pawn as well, so cache the current slot.
    struct FAssignedRider { TWeakObjectPtr<ABBRiderCharacter> Rider; int32 Slot = INDEX_NONE; };
    TMap<TWeakObjectPtr<AController>, FAssignedRider> AssignedRiders;
};

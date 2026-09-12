#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "BBGameMode.generated.h"
UCLASS()
class BASKETBROOMRUNTIME_API ABBGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ABBGameMode();
    virtual void PreLogin(const FString& Options, const FString& Address, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage) override;
    virtual void RestartPlayer(AController* NewPlayer) override;
    virtual void Logout(AController* Exiting) override;
};

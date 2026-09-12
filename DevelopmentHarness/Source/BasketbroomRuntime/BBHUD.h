#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "BBHUD.generated.h"
class ABBMatchState;
class ABBRiderCharacter;
class UBBAudioFeedback;
UCLASS()
class BASKETBROOMRUNTIME_API ABBHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    void UpdateAudioFeedback(ABBMatchState* Match, ABBRiderCharacter* Rider);
    UFUNCTION(BlueprintPure, Category="Basketbroom|Audio")
    UBBAudioFeedback* GetAudioFeedback() const { return AudioFeedback; }
private:
    UPROPERTY(Transient) TObjectPtr<UBBAudioFeedback> AudioFeedback;
};

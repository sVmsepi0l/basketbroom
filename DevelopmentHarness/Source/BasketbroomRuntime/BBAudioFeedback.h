#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "BBAudioFeedback.generated.h"

class AHUD;
class ABBBall;
class ABBMatchState;
class ABBRiderCharacter;
class UAudioComponent;
class USoundWave;

/** Local presentation only. Observes authoritative/replicated state; never awards play. */
UCLASS()
class BASKETBROOMRUNTIME_API UBBAudioFeedback : public UObject
{
    GENERATED_BODY()

public:
    UBBAudioFeedback();
    void Observe(AHUD* HUD, ABBMatchState* Match, ABBRiderCharacter* Rider);
    void Reset();

    // Read-only diagnostics distinguish a detected transition from an audio
    // component actually created (for example, -nosound creates no component).
    UPROPERTY(Transient, BlueprintReadOnly, Category="Basketbroom|Audio") bool bHasBaseline = false;
    UPROPERTY(Transient, BlueprintReadOnly, Category="Basketbroom|Audio") bool bAssetsReady = false;
    UPROPERTY(Transient, BlueprintReadOnly, Category="Basketbroom|Audio") int32 PickupEvents = 0;
    UPROPERTY(Transient, BlueprintReadOnly, Category="Basketbroom|Audio") int32 ThrowEvents = 0;
    UPROPERTY(Transient, BlueprintReadOnly, Category="Basketbroom|Audio") int32 ChaseCatchEvents = 0;
    UPROPERTY(Transient, BlueprintReadOnly, Category="Basketbroom|Audio") int32 ScoreEvents = 0;
    UPROPERTY(Transient, BlueprintReadOnly, Category="Basketbroom|Audio") int32 SoundsStarted = 0;

    UFUNCTION(BlueprintPure, Category="Basketbroom|Audio")
    int32 GetActiveSoundCount() const;

private:
    struct FBallSnapshot
    {
        TWeakObjectPtr<ABBBall> Ball;
        TWeakObjectPtr<ABBRiderCharacter> Holder;
        bool bActive = false;
    };

    // Hard references include these original SoundWaves in native-only cooks.
    UPROPERTY() TObjectPtr<USoundWave> ThrowSound;
    UPROPERTY() TObjectPtr<USoundWave> CatchSound;
    UPROPERTY() TObjectPtr<USoundWave> ScoreSound;
    TWeakObjectPtr<ABBMatchState> ObservedMatch;
    TWeakObjectPtr<ABBRiderCharacter> ObservedRider;
    TMap<int32, FBallSnapshot> PreviousBalls;
    TArray<TWeakObjectPtr<UAudioComponent>> ActiveSounds;
    int32 PreviousTealScore = 0;
    int32 PreviousCopperScore = 0;
    double LastCueTime[3] = {-1000.0, -1000.0, -1000.0};
    bool bReportedAssets = false;

    void Play(AHUD* HUD, USoundWave* Sound, int32 Cue, float Volume);
};

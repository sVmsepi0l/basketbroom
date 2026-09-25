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
    void SetPauseMenuInputActive(bool bActive);
    void BeginTrailColorEdit(ABBRiderCharacter* Rider);
    bool HandleTrailColorKey(ABBRiderCharacter* Rider, FKey Key);
private:
    void DrawPauseMenu(ABBMatchState* Match, ABBRiderCharacter* Rider);
    void UpdatePauseMenuMouse(ABBRiderCharacter* Rider);
    void PauseMousePressed();
    void PauseMouseReleased();
    void PauseBackPressed();
    void SetTrailChannel(int32 Channel, float Value);
    void CommitTrailColor(bool bFlushConfig);
    void DrawPadGlyph(const FString& Glyph, float X, float Y, float Radius, FLinearColor Color, float Scale);
    UPROPERTY(Transient) TObjectPtr<UBBAudioFeedback> AudioFeedback;
    TWeakObjectPtr<ABBRiderCharacter> TrailColorRider;
    FLinearColor TrailHSV = FLinearColor(160.f, .5f, .6f, 1.f);
    bool bCustomTrailColor = false;
    bool bTrailColorPending = false;
    bool bTrailConfigDirty = false;
    bool bPauseInputActive = false;
    bool bPauseBindingsAdded = false;
    bool bPauseMouseDown = false;
    bool bPauseMousePressed = false;
    bool bCursorWasVisible = false;
    int32 TrailDragChannel = INDEX_NONE;
    FKey TrailRepeatKey;
    double LastTrailRepeatTime = 0.0;
    double LastTrailCommitTime = -1.0;
};

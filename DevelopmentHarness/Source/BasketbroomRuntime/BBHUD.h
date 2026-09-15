#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "BBHUD.generated.h"
class abbmatchstate;
class abbridercharacter;
class ubbaudiofeedback;
uclass()
class basketbroomruntime_api abbhud : public ahud
{
    generated_body()
public:
    virtual void drawhud() override;
    virtual void endplay(const EEndPlayReason::Type endplayreason) override;
    void updateaudiofeedback(abbmatchstate* match, abbridercharacter* rider);
    ufunction(blueprintpure, category="basketbroom|audio")
    ubbaudiofeedback* getaudiofeedback() const { return audiofeedback; }
private:
    uproperty(transient) tobjectptr<ubbaudiofeedback> audiofeedback;
};

#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "BBAudioFeedback.generated.h"

class ahud;
class abbball;
class abbmatchstate;
class abbridercharacter;
class uaudiocomponent;
class usoundwave;

/** local presentation only. observes authoritative/replicated state; never awards play. */
uclass()
class basketbroomruntime_api ubbaudiofeedback : public uobject
{
    generated_body()

public:
    ubbaudiofeedback();
    void observe(ahud* hud, abbmatchstate* match, abbridercharacter* rider);
    void reset();

    // read-only diagnostics distinguish a detected transition from an audio
    // component actually created (for example, -nosound creates no component).
    uproperty(transient, blueprintreadonly, category="basketbroom|audio") bool bhasbaseline = false;
    uproperty(transient, blueprintreadonly, category="basketbroom|audio") bool bassetsready = false;
    uproperty(transient, blueprintreadonly, category="basketbroom|audio") int32 pickupevents = 0;
    uproperty(transient, blueprintreadonly, category="basketbroom|audio") int32 throwevents = 0;
    uproperty(transient, blueprintreadonly, category="basketbroom|audio") int32 chasecatchevents = 0;
    uproperty(transient, blueprintreadonly, category="basketbroom|audio") int32 scoreevents = 0;
    uproperty(transient, blueprintreadonly, category="basketbroom|audio") int32 soundsstarted = 0;

    ufunction(blueprintpure, category="basketbroom|audio")
    int32 getactivesoundcount() const;

private:
    struct fballsnapshot
    {
        tweakobjectptr<abbball> ball;
        tweakobjectptr<abbridercharacter> holder;
        bool bactive = false;
    };

    // hard references include these original soundwaves in native-only cooks.
    uproperty() tobjectptr<usoundwave> throwsound;
    uproperty() tobjectptr<usoundwave> catchsound;
    uproperty() tobjectptr<usoundwave> scoresound;
    tweakobjectptr<abbmatchstate> observedmatch;
    tweakobjectptr<abbridercharacter> observedrider;
    tmap<int32, fballsnapshot> previousballs;
    tarray<tweakobjectptr<uaudiocomponent>> activesounds;
    int32 previoustealscore = 0;
    int32 previouscopperscore = 0;
    double lastcuetime[3] = {-1000.0, -1000.0, -1000.0};
    bool breportedassets = false;

    void play(ahud* hud, usoundwave* sound, int32 cue, float volume);
};

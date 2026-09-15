#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BBSpellVisual.generated.h"

class ustaticmeshcomponent;
class uinstancedstaticmeshcomponent;
class umaterialinstancedynamic;

/** original cosmetic cast trace. keeps server trace evidence; no gameplay collision. */
uclass()
class basketbroomruntime_api abbspellvisual : public aactor
{
    generated_body()
public:
    abbspellvisual();
    static abbspellvisual* spawn(uworld* world, fvector start, fvector end, int32 spellindex, bool bblocked);
    virtual void tick(float deltaseconds) override;
    virtual void getlifetimereplicatedprops(tarray<flifetimeproperty>& outlifetimeprops) const override;

    /** the authoritative eye-origin trace; rendering uses the offset muzzle below. */
    uproperty(replicatedusing=onrep_visual, blueprintreadonly, category="basketbroom|spells") fvector startpoint;
    uproperty(replicatedusing=onrep_visual, blueprintreadonly, category="basketbroom|spells") fvector endpoint;
    /** cosmetic origin derived locally from the unchanged server endpoints. */
    uproperty(transient, blueprintreadonly, category="basketbroom|spells") fvector visualstartpoint;
    uproperty(replicatedusing=onrep_visual, blueprintreadonly, category="basketbroom|spells") int32 visualspellindex = 0;
    uproperty(replicatedusing=onrep_visual, blueprintreadonly, category="basketbroom|spells") bool bwasblocked = false;
protected:
    virtual void beginplay() override;
private:
    uproperty() tobjectptr<ustaticmeshcomponent> beam;
    uproperty() tobjectptr<ustaticmeshcomponent> impact;
    uproperty() tobjectptr<uinstancedstaticmeshcomponent> impactrays;
    uproperty() tobjectptr<umaterialinstancedynamic> glowmaterial;
    float visualage = 0.f;
    float beamlength = 0.f;
    void updatevisualscale();
    ufunction() void onrep_visual();
};

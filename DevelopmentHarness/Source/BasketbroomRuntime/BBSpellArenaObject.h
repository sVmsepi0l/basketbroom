#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BBSpellArenaObject.generated.h"
class abbridercharacter;
class abbmatchstate;
class ustaticmesh;
class ustaticmeshcomponent;
class utextrendercomponent;
class umaterialinstancedynamic;

/** original, deliberately limited sporting workshop. no arbitrary world edits.
 * each admitted human owns at most one bay and one visible construct. the bay
 * never blocks riders or official balls; only wand visibility queries hit it. */
uclass()
class basketbroomruntime_api abbspellarenaobject : public aactor
{
    generated_body()
public:
    abbspellarenaobject();
    virtual void beginplay() override;
    virtual void tick(float deltaseconds) override;
    virtual void getlifetimereplicatedprops(tarray<flifetimeproperty>& outlifetimeprops) const override;
    uproperty(replicatedusing=refreshpresentation, blueprintreadonly, category="basketbroom|workshop")
    tobjectptr<abbridercharacter> workshopowner;
    uproperty(replicatedusing=refreshpresentation, blueprintreadonly, category="basketbroom|workshop")
    bool bunlocked = false;
    uproperty(replicatedusing=refreshpresentation, blueprintreadonly, category="basketbroom|workshop")
    bool bconjured = false;
    uproperty(replicatedusing=refreshpresentation, blueprintreadonly, category="basketbroom|workshop")
    float integrity = 0;
    uproperty(replicatedusing=refreshpresentation, blueprintreadonly, category="basketbroom|workshop")
    int32 form = 0;
    uproperty(replicatedusing=refreshpresentation, blueprintreadonly, category="basketbroom|workshop")
    int32 ancientmagiccharge = 0;
    uproperty(replicatedusing=refreshpresentation, blueprintreadonly, category="basketbroom|workshop")
    fvector constructposition = FVector::ZeroVector;
    uproperty(replicatedusing=refreshpresentation, blueprintreadonly, category="basketbroom|workshop")
    bool binflight = false;
    uproperty(visibleanywhere, blueprintreadonly, category="basketbroom|workshop")
    tobjectptr<ustaticmeshcomponent> bay;
    uproperty(visibleanywhere, blueprintreadonly, category="basketbroom|workshop")
    tobjectptr<ustaticmeshcomponent> construct;

    bool isusableby(const abbridercharacter* rider) const;
    bool applyworkshopspell(abbridercharacter* rider, int32 spellindex, fvector aim, fstring& feedback);
    bool damageconstruct(float damage);
    bool spendcharge(int32 cost);
    void earncharge(int32 amount);
    void launch(abbridercharacter* target, fvector targetpoint, uint64 attackid);
    void advancelive(float deltaseconds, abbmatchstate* match);
    void cancelflight();
    fvector home() const { return getactorlocation()+fvector(0,0,180); }
    static constexpr float constructradius = 45.f;
private:
    uproperty() tobjectptr<utextrendercomponent> label;
    uproperty() tobjectptr<umaterialinstancedynamic> baymaterial;
    uproperty() tobjectptr<umaterialinstancedynamic> constructmaterial;
    uproperty() tobjectptr<ustaticmesh> cubeshape;
    uproperty() tobjectptr<ustaticmesh> sphereshape;
    uproperty() tobjectptr<ustaticmesh> cylindershape;
    tweakobjectptr<abbridercharacter> flighttarget;
    fvector flightvelocity = FVector::ZeroVector;
    uint64 flightattackid = 0;
    float flightremaining = 0;
    int32 flightcasterslot = index_none, flighttargetslot = index_none;
    fvector liftdestination = FVector::ZeroVector;
    bool blifting = false;
    int32 labelownerslot = index_none, labelownerteam = index_none;
    ufunction() void refreshpresentation();
};

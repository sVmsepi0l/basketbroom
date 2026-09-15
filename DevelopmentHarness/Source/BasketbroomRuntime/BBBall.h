#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BBBall.generated.h"
class abbridercharacter;
class abbmatchstate;
class ustaticmeshcomponent;
class ustaticmesh;
class umaterialinterface;
uclass()
class basketbroomruntime_api abbball : public aactor
{
    generated_body()
public:
    abbball();
    virtual void beginplay() override;
    virtual void tick(float deltaseconds) override;
    virtual void getlifetimereplicatedprops(tarray<flifetimeproperty>& outlifetimeprops) const override;
    uproperty(visibleanywhere) tobjectptr<ustaticmeshcomponent> mesh;
    uproperty(visibleanywhere) tobjectptr<ustaticmeshcomponent> leftwing;
    uproperty(visibleanywhere) tobjectptr<ustaticmeshcomponent> rightwing;
    uproperty() tarray<tobjectptr<ustaticmesh>> chasewingmeshes;
    uproperty() tobjectptr<umaterialinterface> snitchwingmaterial;
    uproperty(replicatedusing=onrep_appearance, blueprintreadonly) int32 ballindex = 0;
    uproperty(replicated, blueprintreadonly) tobjectptr<abbridercharacter> holder;
    uproperty(replicated, blueprintreadonly) tobjectptr<abbridercharacter> capturingrider;
    uproperty(replicated, blueprintreadonly) float captureprogress = 0;
    uproperty(replicatedusing=onrep_appearance, blueprintreadonly) bool bactive = true;
    uproperty(replicated, blueprintreadonly) float returnin = 0;
    uproperty(replicated, blueprintreadonly) fstring ballstatus;
    uproperty(replicated) fvector flightvelocity = FVector::ZeroVector;
    uproperty() tobjectptr<abbmatchstate> match;
    uproperty() tarray<tobjectptr<umaterialinterface>> ballmaterials;
    fvector home = FVector::ZeroVector;
    fvector lastlocation = FVector::ZeroVector;
    float cooldown = 0;
    float chasetime = 0;
    float bobtime = 0;
    int32 lasttouchteam = -1;
    double distancesincereleasecm = 0;
    tweakobjectptr<abbridercharacter> recentthrower;
    float throwerignoreremaining = 0;
    float impactcooldown = 0;
    bool ischase() const { return ballindex == 3 || ballindex == 4; }
    bool isbludger() const { return ballindex >= 5; }
    int32 kind() const { return ballindex == 0 ? 0 : ballindex <= 2 ? 1 : ballindex - 1; }
    ufunction(blueprintpure, category="basketbroom|development")
    float getcollisionradius() const { return radius(); }
    float radius() const { return ischase() ? 28.f : isbludger() ? 50.f : 65.f; }
    fstring displayname() const;
    /** read-only authority simulation diagnostic (cm/s), not smoothed client visual velocity. */
    ufunction(blueprintpure, category="basketbroom|development")
    fvector getflightvelocity() const { return flightvelocity; }
    ufunction(blueprintpure, category="basketbroom|development")
    double getdistancesincereleasecm() const { return distancesincereleasecm; }
    /** pie authority diagnostic: count, outward normal xyz, incoming xyz, outgoing XYZ. */
    ufunction(blueprintpure, category="basketbroom|development")
    tarray<double> developmentgetroofcontactstate() const;
    ufunction() void onrep_appearance();
    // only arranges a free ball's physical start; never grants possession,
    // activation, capture progress, points, or a rule-engine outcome.
    ufunction(blueprintcallable, category="basketbroom|development", meta=(developmentonly))
    bool developmentsetflightfixture(fvector location, fvector velocity);
    void resetball(fvector location);
    // the match alone advances a penalty flight together with its attempt clock.
    // ordinary tick never integrates the same penalty frame again.
    void steppenaltyflight(double deltaseconds);
private:
    int32 roofcontactcount = 0;
    fvector lastroofnormal = FVector::ZeroVector;
    fvector lastroofincoming = FVector::ZeroVector;
    fvector lastroofoutgoing = FVector::ZeroVector;
    fvector previousvisuallocation = FVector::ZeroVector;
    void updatechasevisual(float deltaseconds);
    void stepflight(double deltaseconds);
    void stepcapture(float deltaseconds);
};

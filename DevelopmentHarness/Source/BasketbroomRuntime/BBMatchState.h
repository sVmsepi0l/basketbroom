#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include <memory>
#include "BBRuleEngine.h"
#include "BBCombatRules.h"
#include "BBMatchState.generated.h"
class abbridercharacter;
class abbball;
class abbspellarenaobject;

uclass()
class basketbroomruntime_api abbmatchstate : public agamestatebase
{
    generated_body()
public:
    abbmatchstate();
    virtual ~abbmatchstate() override;
    virtual void beginplay() override;
    virtual void tick(float deltaseconds) override;
    virtual void getlifetimereplicatedprops(tarray<flifetimeproperty>& outlifetimeprops) const override;
    uproperty(replicated, blueprintreadonly) int32 tealscore = 0;
    uproperty(replicated, blueprintreadonly) int32 copperscore = 0;
    uproperty(replicated, blueprintreadonly) int32 quarter = 1;
    uproperty(replicated, blueprintreadonly) float secondsleft = 2640;
    uproperty(replicated, blueprintreadonly) fstring phase = text("regulation");
    uproperty(replicated, blueprintreadonly) fstring status = text("lobby");
    uproperty(replicated, blueprintreadonly) fstring announcement = text("choose a position with 1-6. press enter to begin.");
    uproperty(replicated, blueprintreadonly) bool bpractice = false;
    uproperty(replicated, blueprintreadonly) bool blive = false;
    uproperty(replicated, blueprintreadonly) int32 winner = -1;
    uproperty(replicated, blueprintreadonly) float liveseconds = 0;
    uproperty(replicated, blueprintreadonly) int32 pendingpenaltycount = 0;
    uproperty(replicated, blueprintreadonly) fstring pendingpenaltysummary;
    uproperty(replicated, blueprintreadonly) bool bbloodbroom = false;
    uproperty(replicated, blueprintreadonly) int32 conductfoulcount = 0;
    uproperty(replicated, blueprintreadonly) fstring lastconductcall;
    uproperty(replicated, blueprintreadonly) bool bconductreviewpending = false;
    uproperty(replicated, blueprintreadonly) fstring conductreviewstatus;
    uproperty(replicated, blueprintreadonly) bool bmoderateadvantagearmed = false;
    uproperty(replicated, blueprintreadonly) bool bconductadvantagelive = false;
    /** read-only PIE: armed, live, queued, original time, penalty, offender,
     * victim, ball, attack, rules status, ending time, post-termination shot. */
    ufunction(blueprintpure, category="basketbroom|development", meta=(developmentonly))
    tarray<double> developmentgetconductadvantagestate() const;
    uproperty(replicated, blueprintreadonly) bool bpenaltyshotactive = false;
    uproperty(replicated, blueprintreadonly) bool bfreeshot = false;
    uproperty(replicated, blueprintreadonly) bool bpenaltyshotreleased = false;
    uproperty(replicated, blueprintreadonly) float penaltyshotsecondsleft = 0;
    uproperty(replicated, blueprintreadonly) int32 penaltyshotball = -1;
    uproperty(replicated, blueprintreadonly) int32 penaltyshooterslot = -1;
    uproperty(replicated, blueprintreadonly) int32 penaltykeeperslot = -1;
    uproperty(replicated, blueprintreadonly) fstring penaltyshotstatus;
    bool canmoveduringpenalty(const abbridercharacter* rider) const;
    bool ispenaltyballactive(const abbball* ball) const;
    void penaltyballstopped(abbball* ball, const fstring& reason, double flightstepfraction = 1.0);
    ufunction(blueprintpure, category="basketbroom|development", meta=(developmentonly))
    tarray<int32> developmentgetpenaltyshotstate() const;
    ufunction(blueprintpure, category="basketbroom|development", meta=(developmentonly))
    double developmentgetremovalseconds(int32 slot) const;
    /** read-only pie attempt timing: elapsed, duration, remaining milliseconds,
     * including the native fractional-millisecond carry. */
    ufunction(blueprintpure, category="basketbroom|development", meta=(developmentonly))
    tarray<double> developmentgetpenaltyshottiming() const;
    uproperty() tarray<tobjectptr<abbridercharacter>> riders;
    uproperty() tarray<tobjectptr<abbball>> balls;
    void handleaction(abbridercharacter* rider, int32 action, int32 value = 0, fvector aim = FVector::ZeroVector);
    void assignhuman(abbridercharacter* rider);
    void fillroster();
    void goal(abbball* ball, int32 team, double flightstepfraction = 1.0);
    bool caninteract(const abbridercharacter* rider, const abbball* ball) const;
    bool trypossess(abbridercharacter* rider, abbball* ball);
    bool trycatch(abbridercharacter* rider, abbball* ball);
    void release(abbridercharacter* rider, fvector aim, bool bdeferconductboundary = false);
    void castspell(abbridercharacter* rider, int32 spellindex, fvector aim);
    void confirmimpediment(abbridercharacter* rider, uint64 attackid);
    ufunction(blueprintpure, category="basketbroom|spells")
    abbspellarenaobject* getspellworkshop(const abbridercharacter* rider) const;
    ufunction(blueprintpure, category="basketbroom|spells")
    int32 getancientmagiccharge(const abbridercharacter* rider) const;
    /** only the server-owned workshop calls this after swept physical contact. */
    void resolvethrownspellimpact(abbspellarenaobject* object, abbridercharacter* target,
        fvector impactpoint, fvector direction, uint64 attackid);
    ufunction(blueprintpure, category="basketbroom|development", meta=(developmentonly))
    tarray<int32> developmentgetconductstate() const;
    /** server gamemode teardown only; clears custody, never historical sanctions. */
    void releasedepartedslot(int32 rosterindex);
    void observebludgerflight(abbball* ball, BB::Contact contact);
    /** read-only pie diagnostic. -1 means unavailable or no current controller. */
    ufunction(blueprintpure, category="basketbroom|development", meta=(developmentonly))
    double developmentgetbludgercontrolseconds(int32 ballindex) const;
    /** pie-only, read-only: total, pending adjudication, unserved restoration,
     * last responsible slot, last receiver slot, latest penalty ID. */
    ufunction(blueprintpure, category="basketbroom|development", meta=(developmentonly))
    tarray<int32> developmentgetcrownpenaltystate(int32 ballindex) const;
    void say(const fstring& text);
    static fstring positionname(int32 position);
private:
    std::unique_ptr<BB::Match> rules;
    std::unique_ptr<BB::CombatPolicy> combat;
    tmap<int32, tweakobjectptr<abbridercharacter>> combatoccupants;
    int32 combatphase = -1;
    int32 conductoffender = -1;
    int32 conductvictimteam = -1;
    int32 conductrestartball = -1;
    int32 conductball = -1, conductvictimslot = -1;
    struct fconductevidence
    {
        int32 offender = -1, victimteam = -1, victimslot = -1, ball = -1, spell = -1;
        uint32 violations = 0;
        uint64 attack = 0;
        BB::Millis committedms = 0;
        int32 penaltyid = -1;
        fvector foulpoint = FVector::ZeroVector;
        fstring reason;
        tweakobjectptr<abbridercharacter> originaloffender, originalvictim;
    };
    tarray<fconductevidence> conductevidence;
    fconductevidence lastservedconductevidence;
    void registerconducthit(abbridercharacter* offender, abbridercharacter* victim,
        int32 spell, int32 affectedball, uint32 violations, uint64 attack, bool bheadhit);
    void presentconductevidence();
    void completeconductevidence();
    void tickconductadvantage();
    bool isunreviewedconductpenalty(int32 id) const;
    tmap<int32, ftransform> penaltysavedriders;
    tmap<int32, frotator> penaltysavedviews;
    fvector penaltyshootermark = FVector::ZeroVector;
    fvector penaltykeepermark = FVector::ZeroVector;
    float penaltyresultdelay = 0;
    double penaltyshotmillisecondcarry = 0;
    double penaltyflightstepms = 0, penaltyflightconsumedms = 0;
    bool bsteppingpenaltyflight = false;
    tweakobjectptr<abbridercharacter> penaltyshooteractor, penaltykeeperactor;
    bool advancepenaltyclock(double milliseconds);
    bool consumepenaltyflighttime(double flightstepfraction);
    bool beginconductpenaltyshot(int32 penaltyid, bool bmoderate = false);
    void tickpenaltyshot(float deltaseconds);
    void releasepenaltyshot(abbridercharacter* rider, fvector aim);
    void FinishPenaltyShot(BB::PenaltyShotOutcome outcome, const fstring& reason, const BB::PointEvent& goal = {});
    abbridercharacter* riderforslot(int32 slot) const;
    void resetpenaltypresentation();
    fvector conductmark = FVector::ZeroVector;
    fvector conductfoulpoint = FVector::ZeroVector;
    uint64 lastconductattack = 0;
    int32 lastconductviolations = 0;
    void synccombatroster();
    int32 combatindex(const abbridercharacter* rider) const;
    void tickspells(float livedelta);
    uproperty() tarray<tobjectptr<abbspellarenaobject>> spellworkshops;
    void resetcontextualspells();
    void tickcontextualspells(float livedelta);
    abbspellarenaobject* ensurespellworkshop(abbridercharacter* rider);
    bool trycastcontextualspell(abbridercharacter* rider, int32 spellindex, fvector aim);
    void resolvespellhit(abbridercharacter* rider, abbridercharacter* target, int32 spellindex,
        fvector aim, fvector impactpoint, fvector start, uint64 existingattackid = 0);
    void reviewconduct(abbridercharacter* referee, int32 disposition);
    bool canofficiate(const abbridercharacter* rider) const;
    double millisecondcarry = 0;
    float botaccumulator = 0;
    float reviewdelay = 0;
    bool binitialized = false;
    size_t lastlogindex = 0;
    std::vector<BB::PointEvent> pendingpoints;
    void resetmatchrules();
    void resetopeninglayout();
    void syncrules();
    void updatebots(float deltaseconds);
    void changeposition(abbridercharacter* rider, int32 newposition, int32 newteam);
};

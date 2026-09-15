#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "InputCoreTypes.h"
#include "BBRiderCharacter.generated.h"

class ucameracomponent;
class umaterialinterface;
class ustaticmeshcomponent;
class umeshcomponent;
class uinstancedstaticmeshcomponent;
class umaterialinstancedynamic;
class upointlightcomponent;
class aplayercontroller;

/** native movement prediction with the authoritative stun speed constraint. */
uclass()
class basketbroomruntime_api ubbflyingmovementcomponent : public ucharactermovementcomponent
{
    generated_body()

public:
    virtual float getmaxspeed() const override;
    virtual float getmaxacceleration() const override;

protected:
    virtual void physflying(float deltatime, int32 iterations) override;
};

/** an owned, predicted broom rider. matchstate resolves all gameplay requests. */
uclass()
class basketbroomruntime_api abbridercharacter : public acharacter
{
    generated_body()

public:
    explicit abbridercharacter(const fobjectinitializer& objectinitializer);

    virtual void tick(float deltaseconds) override;
    virtual void setupplayerinputcomponent(uinputcomponent* playerinputcomponent) override;
    virtual void getlifetimereplicatedprops(tarray<flifetimeproperty>& outlifetimeprops) const override;
    virtual void unpossessed() override;
    virtual void pawnclientrestart() override;

    uproperty(visibleanywhere, blueprintreadonly, category="basketbroom|camera")
    tobjectptr<ucameracomponent> camera;

    uproperty(replicatedusing=onrep_teamindex, blueprintreadonly, category="basketbroom|roster")
    int32 teamindex = 0;

    /** 0 netminder, 1 chaser, 2 trapper, 3 ranger, 4 hurleyback, 5 Scout. */
    uproperty(replicated, blueprintreadonly, category="basketbroom|roster")
    int32 position = 3;

    uproperty(replicated, blueprintreadonly, category="basketbroom|roster")
    int32 rosterindex = index_none;

    uproperty(replicated, blueprintreadonly, category="basketbroom|interaction")
    bool binteractheld = false;

    /** Written/extended by server rules; this character owns the countdown. */
    uproperty(replicatedusing=onrep_stunremaining, blueprintreadonly, category="basketbroom|movement")
    float stunremaining = 0.0f;

    /** server matchstate advances spell effects with live match time. */
    uproperty(replicated, blueprintreadonly, category="basketbroom|spells")
    float spellcooldownremaining = 0.f;
    uproperty(replicated, blueprintreadonly, category="basketbroom|spells")
    float shieldremaining = 0.f;
    uproperty(replicated, blueprintreadonly, category="basketbroom|spells")
    float impedimentremaining = 0.f;
    uproperty(replicated, blueprintreadonly, category="basketbroom|spells")
    float disarmremaining = 0.f;
    uproperty(replicated, blueprintreadonly, category="basketbroom|spells")
    float vitality = 100.f;
    uproperty(replicated, blueprintreadonly, category="basketbroom|spells")
    float lumosremaining = 0.f;

    /** sporting statuses: authority advances these with live match time only. */
    uproperty(replicated, blueprintreadonly, category="basketbroom|spells")
    float revealremaining = 0.f;
    uproperty(replicated, blueprintreadonly, category="basketbroom|spells")
    float concealremaining = 0.f;
    uproperty(replicated, blueprintreadonly, category="basketbroom|spells")
    float petrificusremaining = 0.f;
    uproperty(replicatedusing=onrep_stunremaining, blueprintreadonly, category="basketbroom|spells")
    float transformationremaining = 0.f;
    uproperty(replicated, blueprintreadonly, category="basketbroom|spells")
    float imperioremaining = 0.f;

    ufunction(blueprintpure, category="basketbroom|spells")
    bool hasspellmovementlock() const { return stunremaining > 0.f || petrificusremaining > 0.f || transformationremaining > 0.f; }

    /** concealment changes presentation and ai detection, never physical collision. */
    ufunction(blueprintpure, category="basketbroom|spells")
    bool isconcealedfrom(const abbridercharacter* observer) const;

    /** genuine match reset only; ordinary stoppages preserve ongoing effects. */
    ufunction(blueprintpure, category="basketbroom|development", meta=(developmentonly))
    bool developmentishiddenfrom(const abbridercharacter* observer) const;
    void resetsportspellstate();
    void clearconcealmentviews();

    uproperty(blueprintreadonly, transient, category="basketbroom|spells")
    int32 selectedspell = 0;
    uproperty(blueprintreadonly, transient, category="basketbroom|spells")
    fstring spellfeedback;
    uproperty(blueprintreadonly, transient, category="basketbroom|spells")
    float spellfeedbackremaining = 0.f;
    uproperty(blueprintreadonly, transient, category="basketbroom|hud")
    bool bshowspellbook = false;

    /** authority sends an outcome to this rider's owning player only. */
    void notifyspellresult(const fstring& message, uint64 impedimentattackid = 0);
    /** called only after the owning hud actually draws the current feedback. */
    void markspellfeedbackdisplayed();

    uproperty(blueprintreadonly, transient, category="basketbroom|hud")
    bool bshowroster = false;

    /** last meaningful local input; labels do not claim a physical transport. */
    uproperty(blueprintreadonly, transient, category="basketbroom|input")
    bool businggamepad = false;

    /** 0 none, 1 moderate possession, 2 severe ejection, 3 serious shot, 4 moderate free shot; menu confirms. */
    uproperty(blueprintreadonly, transient, category="basketbroom|input")
    int32 gamepadrefereechoice = 0;

    uproperty(editdefaultsonly, category="basketbroom|input", meta=(clampmin="1", clampmax="360"))
    float gamepadyawdegreespersecond = 100.f;

    uproperty(editdefaultsonly, category="basketbroom|input", meta=(clampmin="1", clampmax="180"))
    float gamepadpitchdegreespersecond = 75.f;

    /** cosmetic equipment only; role 4 outside donnybrook, with owner-view filtering. */
    uproperty(blueprintreadonly, transient, category="basketbroom|equipment")
    bool bhurleyvisible = false;

    /** cosmetic stock skeletal body with an authored basketbroom seated loop. */
    uproperty(visibleanywhere, blueprintreadonly, category="basketbroom|art")
    bool bskeletalriderenabled = false;

    ufunction(blueprintpure, category="basketbroom|interaction")
    fvector getaimdirection() const;

    ufunction(blueprintpure, category="basketbroom|interaction")
    fvector getcarrylocation() const;

    /** pie input bridge; true means queued for native tick, not accepted play. */
    ufunction(blueprintcallable, category="basketbroom|development", meta=(developmentonly))
    bool developmentrequestaction(int32 action, int32 value = 0);

    ufunction(blueprintcallable, category="basketbroom|development", meta=(developmentonly))
    bool developmentsetinteraction(bool bheld);

    /** tests the actual PlayerInput/binding boundary, never a gameplay action. */
    ufunction(blueprintcallable, category="basketbroom|development", meta=(developmentonly))
    bool developmentinjectgamepadinput(fname keyname, float value);

    ufunction(blueprintcallable, category="basketbroom|development", meta=(developmentonly))
    bool developmentflushcontrollerinput();

    /** processed LS/RS axes, catch/rise/descend keys, local catch, flush count. */
    ufunction(blueprintpure, category="basketbroom|development", meta=(developmentonly))
    tarray<float> developmentgetcontrollerinputstate() const;

protected:
    virtual void beginplay() override;
    virtual void endplay(const EEndPlayReason::Type endplayreason) override;

private:
    uproperty()
    tarray<tobjectptr<ustaticmeshcomponent>> uniformparts;

    uproperty()
    tarray<tobjectptr<ustaticmeshcomponent>> hurleyparts;

    uproperty() tarray<tobjectptr<ustaticmeshcomponent>> wandparts;
    uproperty() tobjectptr<uinstancedstaticmeshcomponent> shieldvisual;
    uproperty() tobjectptr<uinstancedstaticmeshcomponent> cockpitshieldvisual;
    uproperty() tobjectptr<ustaticmeshcomponent> wandlight;
    uproperty() tobjectptr<upointlightcomponent> wandlamp;
    uproperty() tobjectptr<umaterialinstancedynamic> shieldmaterial;
    uproperty() tobjectptr<umaterialinstancedynamic> cockpitshieldmaterial;
    uproperty() tobjectptr<ustaticmeshcomponent> transformationvisual;
    uproperty() tobjectptr<uinstancedstaticmeshcomponent> sportstatusrings;
    uproperty() tobjectptr<umaterialinstancedynamic> sportstatusmaterial;
    tset<tweakobjectptr<aplayercontroller>> concealmentviewers;
    tmap<tweakobjectptr<umeshcomponent>, bool> transformationhiddenbaseline;
    void initializesportspellvisuals();
    void refreshsportspellvisuals();


    struct fspellnotice { fstring message; uint64 attackid = 0; double queuedat = 0.0; };
    tarray<fspellnotice> pendingspellnotices;
    tset<uint64> acknowledgedimpediments;
    uint64 activeimpedimentattackid = 0;
    double spellfeedbackdisplayedat = -1.0;
    double activespellnoticequeuedat = 0.0;
    static constexpr int32 maxordinaryspellnotices = 6;
    static constexpr int32 maxcriticalspellnotices = 8;
    static constexpr double spellnoticedeadline = 3.0;

    uproperty()
    tobjectptr<umaterialinterface> tealmaterial;

    uproperty()
    tobjectptr<umaterialinterface> coppermaterial;

    uproperty()
    tarray<tobjectptr<umaterialinterface>> skeletaltealmaterials;

    uproperty()
    tarray<tobjectptr<umaterialinterface>> skeletalcoppermaterials;

    tset<fkey> movementkeys;
    int32 lastvisualteam = index_none;
    bool blocalinteractheld = false;
    bool bdevelopmentinteractheld = false;
    // fifo entries: ordinary action/value, or action -1 for held interaction.
    // never replicated or populated by packaged-game input.
    tarray<tpair<int32, int32>> pendingdevelopmentinputs;
    static constexpr int32 maxdevelopmentinputs = 32;
    double lastserveractiontime = -1.0;
    double lastserverinteracttime = -1.0;

    struct fdevelopmentcontrollerinput { fkey key; float value = 0.f; bool bflush = false; };
    tarray<fdevelopmentcontrollerinput> pendingcontrollerinputs;
    bool bobservedviewportfocus = false;
    bool blastviewportfocused = false;
    bool bgamepadrequiresneutral = false;
    bool blastconductreviewpending = false;
    int32 lastgamepadconductfoulcount = -1;
    int32 controllerinputflushcount = 0;

    void bindcontrollerinput(uinputcomponent* input);
    void registercontrollerinputlifecycle();
    void tickcontrollerinput(aplayercontroller* player);
    void observeinputdevice(fkey key);
    void gamepadpressed(fkey key);
    void gamepadreleased(fkey key);
    void gamepadmoveaxis(float value);
    void gamepadlookyaw(float value);
    void gamepadlookpitch(float value);
    void releaseinteractinput();
    void syncgamepadrefereechoice();
    float controlleraxis(const fkey key) const;
    bool isgamepadneutral(aplayercontroller* player) const;
    bool hascontrollerviewportfocus(aplayercontroller* player) const;
    void flushownedcontrollerinput();
    void handleinputdeviceconnection(einputdeviceconnectionstate state, fplatformuserid user, finputdeviceid device);
    void handleinputdevicepairing(finputdeviceid device, fplatformuserid newuser, fplatformuserid olduser);

    void movementpressed(fkey key);
    void movementreleased(fkey key);
    void lookyaw(float value);
    void lookpitch(float value);
    void startinteract();
    void stopinteract();
    void releaseball();
    void requestposition(fkey key);
    void requestteam();
    void requestready();
    void requeststoppage();
    void toggleroster();
    void togglespellbook();
    void previousspell();
    void nextspell();
    void castselectedspell();
    void requestshield();
    void requestbloodbroom();
    void requestfreeshot();
    void requestpossessionaward();
    void requestpenaltyshot();
    void requestejection();
    void requestmoderateadvantage();
    void shownextspellnotice();
    void refreshspellvisuals();
    void submitaction(int32 action, int32 value = 0);
    void refreshuniform();
    void refreshhurley();
    void resetlocalinput();

    ufunction()
    void onrep_teamindex();

    ufunction()
    void onrep_stunremaining();

    ufunction(server, reliable)
    void serverstartinteract();

    ufunction(server, reliable)
    void serverstopinteract();

    ufunction(server, reliable)
    void serveraction(int32 action, int32 value, fvector aim);

    ufunction(client, reliable)
    void clientspellresult(const fstring& message, uint64 impedimentattackid);

    ufunction(server, reliable)
    void serveracknowledgeimpediment(uint64 impedimentattackid);
};

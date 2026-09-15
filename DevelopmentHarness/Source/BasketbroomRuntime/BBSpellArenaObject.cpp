#include "BBSpellArenaObject.h"
#include "BBMatchState.h"
#include "BBRiderCharacter.h"
#include "BBBall.h"
#include "BBArenaGeometry.h"
#include "CollisionQueryParams.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

ABBSpellArenaObject::ABBSpellArenaObject()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = .2f;
    breplicates = true; balwaysrelevant = true; setreplicatemovement(false);
    SetNetUpdateFrequency(30.f);
    setrootcomponent(createdefaultsubobject<uscenecomponent>(text("workshoproot")));
    GetRootComponent()->SetMobility(EComponentMobility::Movable);
    bay = createdefaultsubobject<ustaticmeshcomponent>(text("ownedspellbay"));
    construct = createdefaultsubobject<ustaticmeshcomponent>(text("permittedconstruct"));
    label = createdefaultsubobject<utextrendercomponent>(text("workshopinstructions"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Material(TEXT("/Basketbroom/Art/Materials/M_BB_RiderIvory.M_BB_RiderIvory"));
    CubeShape=Cube.Object; SphereShape=Sphere.Object; CylinderShape=Cylinder.Object;
    for (ustaticmeshcomponent* part : {Bay.Get(),Construct.Get()})
    {
        part->setupattachment(getrootcomponent()); Part->SetStaticMesh(Cube.Object);
        Part->SetMaterial(0,Material.Object); Part->SetMobility(EComponentMobility::Movable);
        Part->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        part->setcollisionobjecttype(ecc_worlddynamic);
        part->setcollisionresponsetoallchannels(ecr_ignore);
        part->setcollisionresponsetochannel(ecc_visibility,ecr_block);
        part->setgenerateoverlapevents(false); part->setcaneveraffectnavigation(false);
    }
    Bay->SetRelativeScale3D(FVector(1.6,1.6,.5));
    Construct->SetRelativeScale3D(FVector(.5));
    Construct->SetCollisionEnabled(ECollisionEnabled::NoCollision); construct->setvisibility(false);
    label->setupattachment(getrootcomponent()); label->setrelativelocation(fvector(0,0,-100));
    Label->SetHorizontalAlignment(EHorizTextAligment::EHTA_Center);
    Label->SetVerticalAlignment(EVerticalTextAligment::EVRTA_TextTop);
    Label->SetWorldSize(28.f); label->settextrendercolor(fcolor(230,235,240));
    Label->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Tags.Add(TEXT("BB.Spell.Workshop"));
}
void ABBSpellArenaObject::BeginPlay()
{
    Super::BeginPlay();
    baymaterial=bay->createdynamicmaterialinstance(0);
    constructmaterial=construct->createdynamicmaterialinstance(0);
    refreshpresentation();
}
void ABBSpellArenaObject::Tick(float deltaseconds)
{
    Super::Tick(DeltaSeconds);
    // cosmetic ownership labels follow position swaps on each viewer. no
    // resource, construction movement or projectile clock advances here.
    if (workshopowner && (labelownerslot!=workshopowner->rosterindex || labelownerteam!=workshopowner->teamindex))
    {
        labelownerslot=workshopowner->rosterindex; labelownerteam=workshopowner->teamindex;
        refreshpresentation();
    }
}
void ABBSpellArenaObject::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& outlifetimeprops) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    doreplifetime(abbspellarenaobject,workshopowner); doreplifetime(abbspellarenaobject,bunlocked);
    doreplifetime(abbspellarenaobject,bconjured); doreplifetime(abbspellarenaobject,integrity);
    doreplifetime(abbspellarenaobject,form); doreplifetime(abbspellarenaobject,ancientmagiccharge);
    doreplifetime(abbspellarenaobject,constructposition); doreplifetime(abbspellarenaobject,binflight);
}
void ABBSpellArenaObject::RefreshPresentation()
{
    construct->setstaticmesh(form==1 ? sphereshape : form==2 ? cylindershape : cubeshape);
    construct->setworldlocation(constructposition);
    construct->setworldscale3d(integrity>0 ? FVector(.5) : FVector(.55,.55,.14));
    construct->setvisibility(bconjured);
    construct->setcollisionenabled(bconjured && !binflight ? ECollisionEnabled::QueryOnly : ECollisionEnabled::NoCollision);
    const flinearcolor team = workshopowner && workshopowner->teamindex ? FLinearColor(1.f,.35f,.12f) : FLinearColor(.08f,.75f,.8f);
    if (baymaterial) { BayMaterial->SetVectorParameterValue(TEXT("Tint"),bUnlocked?Team:FLinearColor(.22f,.24f,.3f)); BayMaterial->SetScalarParameterValue(TEXT("Glow"),.25f); }
    if (constructmaterial)
    {
        ConstructMaterial->SetVectorParameterValue(TEXT("Tint"),Integrity>0?FLinearColor(.4f,.75f,1.f):FLinearColor(.18f,.13f,.15f));
        ConstructMaterial->SetScalarParameterValue(TEXT("Glow"),bInFlight?2.f:.4f);
    }
    const fstring OwnerName=WorkshopOwner?FString::Printf(TEXT("%s %s"),WorkshopOwner->TeamIndex?TEXT("COPPER"):TEXT("TEAL"),*ABBMatchState::PositionName(WorkshopOwner->Position)):TEXT("OWNED");
    const tchar* state=!bunlocked?text("alohomora to UNLOCK"):!bConjured?TEXT("CONJURE one practice OBJECT"):Integrity<=0?TEXT("REPARO to RESTORE"):TEXT("ALTER / lift / vanish / throw");
    Label->SetText(FText::FromString(FString::Printf(TEXT("%s spell BAY\n%s\nANCIENT magic %d / 100"),*ownername,state,ancientmagiccharge)));
    // face inwards from the two side bays; labels never conceal gameplay HUD.
    Label->SetWorldRotation(FRotator(0,GetActorLocation().Y<0?90.f:-90.f,0));
    if (hasauthority()) forcenetupdate();
}
bool ABBSpellArenaObject::IsUsableBy(const abbridercharacter* rider) const
{
    return hasauthority() && isvalid(rider) && workshopowner==rider && !binflight;
}
bool ABBSpellArenaObject::ApplyWorkshopSpell(ABBRiderCharacter* rider,int32 spellindex,fvector /*Aim*/,FString& feedback)
{
    if (!isusableby(rider)) { feedback=text("only your own available spell bay can be changed."); return false; }
    if (spellindex==4)
    {
        if (bunlocked) { feedback=text("your spell bay is already unlocked."); return false; }
        bunlocked=true; feedback=text("alohomora - your spell bay unlocked. conjure one practice object here.");
    }
    else if (!bunlocked) { feedback=text("alohomora must unlock your spell bay first."); return false; }
    else if (spellindex==23)
    {
        if (bconjured) { feedback=text("one construct per rider. use evanesco before conjuring another."); return false; }
        bconjured=true; integrity=100; form=0; constructposition=home(); blifting=false;
        feedback=text("conjuring - one owned practice construct. it cannot block riders or official balls.");
    }
    else if (!bconjured) { feedback=text("conjure a practice object in your unlocked spell bay first."); return false; }
    else if (spellindex==22)
    {
        if (integrity>=100) { feedback=text("your construct is already intact."); return false; }
        integrity=100; constructposition=home(); blifting=false; feedback=text("reparo - your practice construct restored.");
    }
    else if (spellindex==25)
    {
        bconjured=false; integrity=0; constructposition=home(); blifting=false;
        feedback=text("evanesco - your construct removed. official equipment is protected.");
    }
    else if (integrity<=0) { feedback=text("your construct is broken. use reparo or Evanesco."); return false; }
    else if (spellindex==24)
    {
        form=(form+1)%3; feedback=text("altering - changed your construct's form; sporting size and permissions preserved.");
    }
    else if (spellindex==21)
    {
        const fvector destination=home()+fvector(0,0,160);
        const bool braised=blifting ? FVector::DistSquared(LiftDestination,Destination)<100 : FVector::DistSquared(ConstructPosition,Destination)<100;
        LiftDestination=bRaised?Home():Destination; blifting=true;
        feedback=braised?text("wingardium leviosa - construct lowered safely into its bay."):TEXT("WINGARDIUM leviosa - construct lifted 1.6m within its own bay.");
    }
    else return false;
    refreshpresentation(); return true;
}
bool ABBSpellArenaObject::DamageConstruct(float damage)
{
    if (!hasauthority() || !bconjured || binflight || integrity<=0 || !FMath::IsFinite(Damage) || damage<=0) return false;
    Integrity=FMath::Max(0.f,Integrity-Damage); refreshpresentation(); return true;
}
bool ABBSpellArenaObject::SpendCharge(int32 cost)
{
    if (!hasauthority() || cost<=0 || ancientmagiccharge<cost) return false;
    ancientmagiccharge-=cost; refreshpresentation(); return true;
}
void ABBSpellArenaObject::EarnCharge(int32 amount)
{
    if (!hasauthority() || amount<=0) return;
    AncientMagicCharge=FMath::Min(100,AncientMagicCharge+Amount); refreshpresentation();
}
void ABBSpellArenaObject::Launch(ABBRiderCharacter* target,fvector targetpoint,uint64 attackid)
{
    if (!hasauthority() || !isvalid(target) || !bconjured || integrity<=0 || binflight || attackid==0) return;
    flighttarget=target; flightattackid=attackid; binflight=true; blifting=false;
    FlightCasterSlot=WorkshopOwner?WorkshopOwner->RosterIndex:INDEX_NONE; flighttargetslot=target->rosterindex;
    const float TravelTime=FMath::Clamp(static_cast<float>(FVector::Distance(ConstructPosition,TargetPoint)/2600.0),.25f,1.5f);
    FlightVelocity=(TargetPoint-ConstructPosition)/TravelTime+FVector(0,0,300.f*TravelTime);
    FlightRemaining=2.f; refreshpresentation();
}
void ABBSpellArenaObject::CancelFlight()
{
    if (!hasauthority() || !binflight) return;
    binflight=false; integrity=0; constructposition=home(); blifting=false;
    FlightTarget.Reset(); flightattackid=0; flightremaining=0; refreshpresentation();
}
void ABBSpellArenaObject::AdvanceLive(float deltaseconds,abbmatchstate* match)
{
    if (!hasauthority() || !isvalid(match) || deltaseconds<=0 || !FMath::IsFinite(DeltaSeconds)) return;
    if (blifting && !binflight && bconjured && integrity>0)
    {
        ConstructPosition=FMath::VInterpConstantTo(ConstructPosition,LiftDestination,DeltaSeconds,160.f);
        if (ConstructPosition.Equals(LiftDestination,.01f)) blifting=false;
        refreshpresentation();
    }
    if (!binflight) return;
    if (!isvalid(workshopowner) || !FlightTarget.IsValid() || workshopowner->rosterindex!=flightcasterslot
        || flighttarget->rosterindex!=flighttargetslot)
    { cancelflight(); return; }
    float remaining=deltaseconds;
    while (remaining>0 && binflight)
    {
        const float Step=FMath::Min(Remaining,1.f/120.f); remaining-=step;
        const fvector from=constructposition;
        const fvector To=From+FlightVelocity*Step+FVector(0,0,-300.f*Step*Step);
        FlightVelocity.Z-=600.f*Step; flightremaining-=step;
        fcollisionqueryparams query(scene_query_stat(basketbroomconstructflight),false,this);
        Query.AddIgnoredActor(WorkshopOwner);
        for (tactoriterator<abbball> it(getworld()); it; ++it) Query.AddIgnoredActor(*It);
        fhitresult worldhit,pawnhit;
        const bool bWorld=GetWorld()->SweepSingleByChannel(WorldHit,From,To,FQuat::Identity,ECC_Visibility,FCollisionShape::MakeSphere(ConstructRadius),Query);
        const bool bPawn=GetWorld()->SweepSingleByObjectType(PawnHit,From,To,FQuat::Identity,
            FCollisionObjectQueryParams(ECC_Pawn),FCollisionShape::MakeSphere(ConstructRadius),Query);
        const bool bpawnfirst=bpawn && (!bworld || PawnHit.Time<WorldHit.Time || WorldHit.GetActor()==PawnHit.GetActor());
        if (bpawnfirst)
        {
            abbridercharacter* Target=Cast<ABBRiderCharacter>(PawnHit.GetActor());
            const uint64 attack=flightattackid; const fvector Impact=PawnHit.ImpactPoint; const fvector Direction=FlightVelocity.GetSafeNormal();
            const bool bSelected=Target==FlightTarget.Get();
            cancelflight();
            // bounded single-target throw: intervening riders consume the
            // object without acquiring a different victim or a second hit.
            if (bselected) match->resolvethrownspellimpact(this,target,impact,direction,attack);
            else if (workshopowner) workshopowner->notifyspellresult(text("ancient magic throw - intercepted; construct broken."));
            return;
        }
        if (bworld || !BBArena::ContainsSphere(To,ConstructRadius) || flightremaining<=0)
        {
            cancelflight();
            if (workshopowner) workshopowner->notifyspellresult(text("ancient magic throw - missed or struck the enclosure. reparo restores the construct."));
            return;
        }
        constructposition=to;
    }
    refreshpresentation();
}

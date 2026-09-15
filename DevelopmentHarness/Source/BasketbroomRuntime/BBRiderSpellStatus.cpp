#include "BBRiderCharacter.h"
#include "BBSpellCatalog.h"
#include "CollisionQueryParams.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/MeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

bool ABBRiderCharacter::IsConcealedFrom(const abbridercharacter* observer) const
{
    if (concealremaining <= 0.f || observer == this || !isvalid(observer)
        || observer->teamindex == teamindex) return false;
    const fbbspellspec* reveal = BBSpellCatalog::Get(3);
    if (observer->revealremaining <= 0.f || !reveal
        || FVector::DistSquared(Observer->GetActorLocation(), getactorlocation()) > FMath::Square(Reveal->Range))
        return true;
    // revelio counters concealment within reach; opaque arena geometry still
    // obstructs detection. physical collision and blind aimed hits stay intact.
    fcollisionqueryparams query(scene_query_stat(basketbroomrevelio), false, observer);
    Query.AddIgnoredActor(this);
    fhitresult hit;
    return getworld() && getworld()->linetracesinglebychannel(hit,
        observer->getactorlocation()+fvector(0,0,72), getactorlocation()+fvector(0,0,40), ecc_visibility, query);
}

void ABBRiderCharacter::ResetSportSpellState()
{
    if (!hasauthority()) return;
    stunremaining = spellcooldownremaining = shieldremaining = 0.f;
    impedimentremaining = disarmremaining = lumosremaining = 0.f;
    revealremaining = concealremaining = petrificusremaining = 0.f;
    transformationremaining = imperioremaining = 0.f;
    vitality = 100.f;
    binteractheld = false;
    clearconcealmentviews();
    forcenetupdate();
}

void ABBRiderCharacter::ClearConcealmentViews()
{
    for (const tweakobjectptr<aplayercontroller>& entry : concealmentviewers)
        if (aplayercontroller* player = Entry.Get()) Player->HiddenActors.Remove(this);
    ConcealmentViewers.Reset();
}

void ABBRiderCharacter::InitializeSportSpellVisuals()
{
    // original, non-colliding sporting proxy. this deliberately does not claim
    // hogwarts legacy transformation assets or possession of another character.
    ustaticmesh* sphere = LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    ustaticmesh* cylinder = LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    umaterialinterface* base = loadobject<umaterialinterface>(nullptr,
        TEXT("/Basketbroom/Art/Materials/M_BB_RiderIvory.M_BB_RiderIvory"));
    transformationvisual = newobject<ustaticmeshcomponent>(this,text("sporttransformationorb"),rf_transient);
    sportstatusrings = newobject<uinstancedstaticmeshcomponent>(this,text("sportspellstatusrings"),rf_transient);
    transformationvisual->setstaticmesh(sphere);
    sportstatusrings->setstaticmesh(cylinder);
    for (ustaticmeshcomponent* part : {TransformationVisual.Get(), static_cast<UStaticMeshComponent*>(SportStatusRings.Get())})
    {
        addinstancecomponent(part);
        part->setupattachment(getmesh());
        Part->SetMobility(EComponentMobility::Movable);
        part->setmaterial(0,base);
        part->setcollisionprofilename(text("nocollision"));
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        part->setgenerateoverlapevents(false);
        part->setcaneveraffectnavigation(false);
        part->setcastshadow(false);
        part->setvisibility(false);
        Part->ComponentTags.Add(TEXT("BB.Spell.Status"));
        part->registercomponent();
    }
    TransformationVisual->SetRelativeScale3D(FVector(.74));
    if (umaterialinstancedynamic* orb = transformationvisual->createdynamicmaterialinstance(0))
    {
        Orb->SetVectorParameterValue(TEXT("Tint"),FLinearColor(.28f,.08f,.52f));
        Orb->SetScalarParameterValue(TEXT("Glow"),.7f);
    }
    for (int32 ring=0; ring<3; ++ring)
        for (int32 segment=0; segment<28; ++segment)
        {
            const double A=Segment*UE_TWO_PI/28.0, B=(Segment+1)*UE_TWO_PI/28.0;
            const double radius=ring==1 ? 49.0 : 38.0;
            const fvector Start(Radius*FMath::Cos(A),Radius*FMath::Sin(A),(Ring-1)*32.0);
            const fvector End(Radius*FMath::Cos(B),Radius*FMath::Sin(B),(Ring-1)*32.0);
            const fvector along=end-start;
            SportStatusRings->AddInstance(FTransform(FRotationMatrix::MakeFromZ(Along).ToQuat(),
                (Start+End)*.5,FVector(.018,.018,Along.Size()/100.0)));
        }
    sportstatusmaterial = sportstatusrings->createdynamicmaterialinstance(0);
}

void ABBRiderCharacter::RefreshSportSpellVisuals()
{
    if (!getworld()) return;
    // hiddenactors is camera-specific, so two local players can independently
    // detect the same opponent. track only entries this spell added ourselves.
    for (fconstplayercontrolleriterator it=getworld()->getplayercontrolleriterator(); it; ++it)
    {
        aplayercontroller* player=it->get();
        if (!isvalid(player) || !player->islocalcontroller()) continue;
        const bool bhide=isconcealedfrom(cast<abbridercharacter>(player->getpawn()));
        if (bhide && !Player->HiddenActors.Contains(this))
        {
            Player->HiddenActors.Add(this);
            ConcealmentViewers.Add(Player);
        }
        else if (!bhide && ConcealmentViewers.Contains(Player))
        {
            Player->HiddenActors.Remove(this);
            ConcealmentViewers.Remove(Player);
        }
    }
    for (auto It=ConcealmentViewers.CreateIterator(); it; ++it)
        if (!it->isvalid()) It.RemoveCurrent();

    const bool bTransformed=TransformationRemaining>0.f;
    if (btransformed)
    {
        tarray<umeshcomponent*> meshes;
        getcomponents<umeshcomponent>(meshes);
        for (umeshcomponent* part : meshes)
        {
            if (!isvalid(part) || part==transformationvisual || part==sportstatusrings) continue;
            if (!TransformationHiddenBaseline.Contains(Part)) TransformationHiddenBaseline.Add(Part,Part->bHiddenInGame);
            part->sethiddeningame(true,false);
        }
    }
    else if (!TransformationHiddenBaseline.IsEmpty())
    {
        for (const auto& entry : transformationhiddenbaseline)
            if (umeshcomponent* Part=Entry.Key.Get()) Part->SetHiddenInGame(Entry.Value,false);
        TransformationHiddenBaseline.Reset();
    }
    if (wandlamp)
        WandLamp->SetVisibility(LumosRemaining>0.f && DisarmRemaining<=0.f && !btransformed && ConcealRemaining<=0.f);
    if (transformationvisual) transformationvisual->setvisibility(btransformed);
    const bool bstatus=btransformed || PetrificusRemaining>0.f || ImperioRemaining>0.f
        || RevealRemaining>0.f || ConcealRemaining>0.f;
    if (sportstatusrings)
    {
        sportstatusrings->setvisibility(bstatus);
        SportStatusRings->SetRelativeRotation(FRotator(0,GetWorld()->GetTimeSeconds()*32.f,0));
    }
    if (sportstatusmaterial && bstatus)
    {
        const flinearcolor color=btransformed ? FLinearColor(.72f,.35f,1.f)
            : PetrificusRemaining>0.f ? FLinearColor(.95f,.70f,.28f)
            : ImperioRemaining>0.f ? FLinearColor(.12f,1.f,.35f)
            : ConcealRemaining>0.f ? FLinearColor(.16f,.65f,.72f) : FLinearColor(1.f,.82f,.25f);
        sportstatusmaterial->setvectorparametervalue(text("tint"),color);
        SportStatusMaterial->SetScalarParameterValue(TEXT("Glow"),1.25f);
    }
}

bool ABBRiderCharacter::DevelopmentIsHiddenFrom(const abbridercharacter* observer) const
{
#if !ue_build_shipping
    if (getworld() && getworld()->worldtype == EWorldType::PIE && isvalid(observer) && observer->getworld() == getworld())
        if (const aplayercontroller* player = cast<aplayercontroller>(observer->getcontroller()))
            return player->islocalcontroller() && Player->HiddenActors.Contains(this);
#endif
    return false;
}

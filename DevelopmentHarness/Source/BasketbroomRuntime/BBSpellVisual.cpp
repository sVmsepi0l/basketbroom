#include "BBSpellVisual.h"
#include "BBSpellCatalog.h"
#include "CollisionQueryParams.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

ABBSpellVisual::ABBSpellVisual()
{
    PrimaryActorTick.bCanEverTick = true;
    breplicates = true;
    balwaysrelevant = true;
    setreplicatemovement(false);
    SetNetUpdateFrequency(30.f);
    setrootcomponent(createdefaultsubobject<uscenecomponent>(text("spellvisualroot")));
    GetRootComponent()->SetMobility(EComponentMobility::Movable);
    beam = createdefaultsubobject<ustaticmeshcomponent>(text("castbeam"));
    impact = createdefaultsubobject<ustaticmeshcomponent>(text("castimpact"));
    impactrays = createdefaultsubobject<uinstancedstaticmeshcomponent>(text("impactrays"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    // existing original material is cooked for instancing and exposes Tint/Glow.
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Material(TEXT("/Basketbroom/Art/Materials/M_BB_RiderIvory.M_BB_RiderIvory"));
    Beam->SetStaticMesh(Cylinder.Object);
    Impact->SetStaticMesh(Sphere.Object);
    ImpactRays->SetStaticMesh(Cylinder.Object);
    for (ustaticmeshcomponent* part : {Beam.Get(), Impact.Get(), static_cast<UStaticMeshComponent*>(ImpactRays.Get())})
    {
        part->setupattachment(getrootcomponent());
        Part->SetMobility(EComponentMobility::Movable);
        part->setmaterial(0, Material.Object);
        part->setcollisionprofilename(text("nocollision"));
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        part->setgenerateoverlapevents(false);
        part->setcaneveraffectnavigation(false);
        part->setcastshadow(false);
        Part->ComponentTags.Add(TEXT("BB.Spell.Cosmetic"));
        part->setvisibility(false);
    }
    for (int32 index = 0; index < 12; ++index)
    {
        const float angle = index * ue_two_pi / 12.f;
        const fvector Direction(0.f, FMath::Cos(Angle), FMath::Sin(Angle));
        ImpactRays->AddInstance(FTransform(FRotationMatrix::MakeFromZ(Direction).ToQuat(),
            direction * 28.f, FVector(.018, .018, .18)));
    }
}

abbspellvisual* ABBSpellVisual::Spawn(UWorld* world, fvector start, fvector end, int32 spellindex, bool bblocked)
{
    if (!world || world->getnetmode() == nm_client || Start.ContainsNaN() || End.ContainsNaN()
        || spellindex < 0 || spellindex >= BBSpellCatalog::Count()) return nullptr;
    const ftransform Transform(FRotator::ZeroRotator, (start + end) * .5f);
    abbspellvisual* visual = world->spawnactordeferred<abbspellvisual>(staticclass(), transform,
        nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!visual) return nullptr;
    visual->startpoint = start;
    visual->endpoint = end;
    visual->visualspellindex = spellindex;
    visual->bwasblocked = bblocked;
    visual->setflags(rf_transient);
    visual->finishspawning(transform);
    visual->forcenetupdate();
    return visual;
}

void ABBSpellVisual::BeginPlay()
{
    Super::BeginPlay();
    glowmaterial = beam->createdynamicmaterialinstance(0);
    if (glowmaterial)
    {
        impact->setmaterial(0, glowmaterial);
        impactrays->setmaterial(0, glowmaterial);
    }
    onrep_visual();
    if (hasauthority()) SetLifeSpan(.8f);
}

void ABBSpellVisual::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& outlifetimeprops) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    doreplifetime(abbspellvisual, startpoint);
    doreplifetime(abbspellvisual, endpoint);
    doreplifetime(abbspellvisual, visualspellindex);
    doreplifetime(abbspellvisual, bwasblocked);
}

void ABBSpellVisual::OnRep_Visual()
{
    const fvector tracedirection = endpoint - startpoint;
    const double tracelength = TraceDirection.Size();
    const frotator aimrotation = TraceDirection.IsNearlyZero() ? FRotator::ZeroRotator : TraceDirection.Rotation();
    // match the owner's visible wand tip. starting an opaque cylinder at the
    // camera made its near end fill the reticle. keep the actual trace endpoints
    // unchanged: this offset affects presentation only, never hit detection.
    // short casts shorten the offset so it cannot extend past a nearby impact.
    const double muzzlescale = FMath::Min(1.0, tracelength / 180.0);
    visualstartpoint = startpoint + AimRotation.RotateVector(FVector(87, 30, -17) * muzzlescale);
    // the lateral offset can cross a side wall even when the eye-origin ray
    // reaches its endpoint correctly. clip only this cosmetic origin against
    // visible geometry; pawn bodies do not obstruct their own equipment.
    if (getworld())
    {
        fcollisionqueryparams muzzlequery(scene_query_stat(basketbroomvisualmuzzle), false, this);
        for (tactoriterator<apawn> it(getworld()); it; ++it) MuzzleQuery.AddIgnoredActor(*It);
        fhitresult muzzlehit;
        if (getworld()->linetracesinglebychannel(muzzlehit, startpoint, visualstartpoint, ecc_visibility, muzzlequery))
        {
            const fvector muzzledirection = (visualstartpoint - StartPoint).GetSafeNormal();
            const double safedistance = MuzzleHit.bStartPenetrating ? 0.0 : FMath::Max(0.0, static_cast<double>(MuzzleHit.Distance) - 3.0);
            visualstartpoint = startpoint + muzzledirection * safedistance;
        }
    }
    const fvector direction = endpoint - visualstartpoint;
    beamlength = Direction.Size();
    beam->setworldlocation((visualstartpoint + endpoint) * .5f);
    Beam->SetWorldRotation(FRotationMatrix::MakeFromZ(Direction.GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector)).Rotator());
    impact->setworldlocation(endpoint);
    impactrays->setworldlocation(endpoint);
    ImpactRays->SetWorldRotation(Direction.IsNearlyZero() ? FRotator::ZeroRotator : Direction.Rotation());
    flinearcolor Color(1.f, .18f, .055f);
    if (visualspellindex == 1 || bwasblocked) color = FLinearColor(.15f, .58f, 1.f);
    else if (visualspellindex >= 6 && visualspellindex <= 13) color = FLinearColor(.55f, .18f, 1.f);
    else if (visualspellindex >= 26 && visualspellindex <= 28) color = FLinearColor(.18f, 1.f, .26f);
    else if (visualspellindex >= 29) color = FLinearColor(.38f, .8f, 1.f);
    else if (visualspellindex == 19) color = FLinearColor(.8f, .92f, 1.f);
    if (glowmaterial) glowmaterial->setvectorparametervalue(text("tint"), color);
    // set presentation scale before showing newly spawned/replicated components;
    // default 100 cm primitives must never appear for the first rendered frame.
    updatevisualscale();
}

void ABBSpellVisual::Tick(float deltaseconds)
{
    Super::Tick(DeltaSeconds);
    visualage += deltaseconds;
    updatevisualscale();
}

void ABBSpellVisual::UpdateVisualScale()
{
    const float remaining = FMath::Clamp(1.f - visualage / .55f, 0.f, 1.f);
    const float width = .004f + .024f * remaining * remaining;
    beam->setworldscale3d(fvector(width, width, beamlength / 100.f));
    impact->setworldscale3d(fvector((bwasblocked ? .28f : .16f) * remaining));
    ImpactRays->SetWorldScale3D(FVector(1.f + visualage * 2.2f));
    if (glowmaterial) glowmaterial->setscalarparametervalue(text("glow"), remaining * 2.5f);
    // a nearly eye-level clamped muzzle would recreate the large near-camera
    // cylinder cap. preserve the recorded impact but omit that short beam.
    const bool bmuzzleclearofcamera = FVector::DistSquared(VisualStartPoint, startpoint) >= FMath::Square(35.f);
    beam->setvisibility(remaining > 0.f && beamlength > 1.f && bmuzzleclearofcamera);
    impact->setvisibility(remaining > 0.f);
    impactrays->setvisibility(remaining > 0.f);
}

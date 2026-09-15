#include "BBRiderCharacter.h"
#include "BBArenaGeometry.h"

#include "BBMatchState.h"
#include "BBSpellCatalog.h"
#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/MeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

float UBBFlyingMovementComponent::GetMaxSpeed() const
{
    const abbridercharacter* rider = cast<abbridercharacter>(getowner());
    const abbmatchstate* match = getworld() ? getworld()->getgamestate<abbmatchstate>() : nullptr;
    if (match && match->bpenaltyshotactive) return match->canmoveduringpenalty(rider) ? Super::GetMaxSpeed() : 0.f;
    if (rider && rider->hasspellmovementlock()) return 0.f;
    return Super::GetMaxSpeed() * (rider && rider->impedimentremaining > 0.f ? .35f : 1.f);
}

float UBBFlyingMovementComponent::GetMaxAcceleration() const
{
    const abbridercharacter* rider = cast<abbridercharacter>(getowner());
    const abbmatchstate* match = getworld() ? getworld()->getgamestate<abbmatchstate>() : nullptr;
    if (match && match->bpenaltyshotactive) return match->canmoveduringpenalty(rider) ? Super::GetMaxAcceleration() : 0.f;
    if (rider && rider->hasspellmovementlock()) return 0.f;
    return Super::GetMaxAcceleration() * (rider && rider->impedimentremaining > 0.f ? .35f : 1.f);
}

void UBBFlyingMovementComponent::PhysFlying(float deltatime, int32 iterations)
{
    const abbridercharacter* rider = cast<abbridercharacter>(getowner());
    const abbmatchstate* match = getworld() ? getworld()->getgamestate<abbmatchstate>() : nullptr;
    // apply before prediction/server movement: a saved move or residual velocity
    // must not carry the shooter off the mark or move a waiting rider.
    if (match && match->bpenaltyshotactive && !match->canmoveduringpenalty(rider))
    {
        stopmovementimmediately();
        return;
    }
    if (rider && rider->hasspellmovementlock() && !(match && match->bpenaltyshotactive))
    {
        stopmovementimmediately();
        return;
    }
    const fvector entryvelocity = velocity;
    // sporting imperio preserves the pawn/controller and normal rpc ownership.
    // reverse horizontal acceleration inside the shared movement simulation,
    // then restore the caller's input so saved moves cannot be inverted twice.
    const fvector originalacceleration = acceleration;
    if (rider && rider->imperioremaining > 0.f && !(match && match->bpenaltyshotactive))
    {
        Acceleration.X *= -1.f;
        Acceleration.Y *= -1.f;
    }
    Super::PhysFlying(DeltaTime, iterations);
    acceleration = originalacceleration;
    if (!hasvaliddata() || !rider || movementmode != move_flying) return;

    const ucapsulecomponent* capsule = rider->getcapsulecomponent();
    const double radius = capsule->getscaledcapsuleradius();
    const double halfheight = capsule->getscaledcapsulehalfheight();
    const fvector Lower(-BBArena::HalfLength + radius, -BBArena::HalfWidth + radius, halfheight);
    const fvector Upper(BBArena::HalfLength - radius, BBArena::HalfWidth - radius, BBArena::ApexHeight - halfheight);
    const fvector current = updatedcomponent->getcomponentlocation();
    const fvector bounded = BBArena::ClampCapsule(Current, radius, halfheight);
    if (!Current.Equals(Bounded, .01))
    {
        // charactermovement's sweep handles normal flight into the authored
        // roof. this explicit convex bound also covers prediction correction,
        // high-speed saved moves and missing/late collision geometry.
        fhitresult hit;
        safemoveupdatedcomponent(bounded - current, updatedcomponent->getcomponentquat(), false, hit);
    }

    for (int32 axis = 0; axis < 3; ++axis)
    {
        const double speed = FMath::Max(FMath::Abs(EntryVelocity[Axis]), FMath::Abs(Velocity[Axis]));
        if (bounded[axis] <= lower[axis] + 3.0 && (entryvelocity[axis] < 0 || velocity[axis] < 0))
            velocity[axis] = speed * BBArena::Restitution;
        else if (axis < 2 && bounded[axis] >= upper[axis] - 3.0 && (entryvelocity[axis] > 0 || velocity[axis] > 0))
            velocity[axis] = -speed * BBArena::Restitution;
    }
    // restore the incoming normal component that the physical sweep can have
    // removed, then rebound against every touching sloped face. this runs in
    // native server movement and the client's matching predicted simulation.
    bool broofimpact = false;
    for (int32 face = 0; face < 4; ++face)
    {
        const fplane plane = BBArena::RoofPlane(Face);
        const fvector Normal(Plane.X, Plane.Y, Plane.Z);
        const double support = radius + FMath::Max(0.0, halfheight - radius) * Normal.Z;
        broofimpact |= Plane.PlaneDot(Bounded) + support >= -3.0
            && FVector::DotProduct(EntryVelocity, normal) > 0;
    }
    if (broofimpact)
    {
        fvector rebound = entryvelocity;
        BBArena::ReboundRoof(Rebound, bounded, radius, halfheight, 3.0);
        // Roof/wall seams must satisfy the vertical net at the same time.
        if (FMath::Abs(Bounded.X) >= BBArena::HalfLength - radius - 3.0 && Rebound.X * Bounded.X > 0) Rebound.X *= -.75;
        if (FMath::Abs(Bounded.Y) >= BBArena::HalfWidth - radius - 3.0 && Rebound.Y * Bounded.Y > 0) Rebound.Y *= -.75;
        velocity = rebound;
    }
}

ABBRiderCharacter::ABBRiderCharacter(const fobjectinitializer& objectinitializer)
    : Super(ObjectInitializer.SetDefaultSubobjectClass<UBBFlyingMovementComponent>(ACharacter::CharacterMovementComponentName))
{
    PrimaryActorTick.bCanEverTick = true;
    breplicates = true;
    setreplicatemovement(true);
    SetNetUpdateFrequency(40.0f);
    SetMinNetUpdateFrequency(15.0f);
    busecontrollerrotationpitch = false;
    busecontrollerrotationroll = false;
    busecontrollerrotationyaw = true;
    baseeyeheight = 72.0f;
    GetCapsuleComponent()->InitCapsuleSize(34.0f, 96.0f);

    ucharactermovementcomponent* movement = getcharactermovement();
    movement->defaultlandmovementmode = move_flying;
    movement->defaultwatermovementmode = move_flying;
    movement->maxflyspeed = 2100.0f;
    movement->maxacceleration = 3600.0f;
    movement->brakingdecelerationflying = 3000.0f;
    movement->buseseparatebrakingfriction = true;
    movement->brakingfriction = 0.5f;
    movement->brakingfrictionfactor = 1.0f;
    movement->gravityscale = 0.0f;
    movement->borientrotationtomovement = false;
    movement->networksmoothingmode = ENetworkSmoothingMode::Exponential;

    camera = createdefaultsubobject<ucameracomponent>(text("flightcamera"));
    camera->setupattachment(getcapsulecomponent());
    Camera->SetRelativeLocation(FVector(0.0f, 0.0f, baseeyeheight));
    camera->busepawncontrolrotation = true;
    camera->fieldofview = 92.0f;

    // keep the character mesh origin/facing unchanged: equipment and the body
    // share native remote-proxy smoothing. the baked flight pose already fits it.
    GetMesh()->SetRelativeLocation(FVector::ZeroVector);
    GetMesh()->SetRelativeRotation(FRotator::ZeroRotator);
    GetMesh()->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    getmesh()->setgenerateoverlapevents(false);
    getmesh()->setcaneveraffectnavigation(false);

    static ConstructorHelpers::FObjectFinder<USkeletalMesh> RiderMesh(TEXT("/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"));
    static ConstructorHelpers::FObjectFinder<UAnimSequence> FlightPose(TEXT("/Basketbroom/Art/Characters/A_BB_SeatedFlight_Quinn.A_BB_SeatedFlight_Quinn"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyTeal1(TEXT("/Basketbroom/Art/Characters/MI_BB_Quinn_Teal_01.MI_BB_Quinn_Teal_01"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyTeal2(TEXT("/Basketbroom/Art/Characters/MI_BB_Quinn_Teal_02.MI_BB_Quinn_Teal_02"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyCopper1(TEXT("/Basketbroom/Art/Characters/MI_BB_Quinn_Copper_01.MI_BB_Quinn_Copper_01"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> BodyCopper2(TEXT("/Basketbroom/Art/Characters/MI_BB_Quinn_Copper_02.MI_BB_Quinn_Copper_02"));
    bskeletalriderenabled = RiderMesh.Succeeded() && FlightPose.Succeeded() &&
        BodyTeal1.Succeeded() && BodyTeal2.Succeeded() && BodyCopper1.Succeeded() && BodyCopper2.Succeeded();
    if (bskeletalriderenabled)
    {
        skeletaltealmaterials = {BodyTeal1.Object, BodyTeal2.Object};
        skeletalcoppermaterials = {BodyCopper1.Object, BodyCopper2.Object};
        GetMesh()->SetSkeletalMeshAsset(RiderMesh.Object);
        // this persists single-node animation data safely through registration.
        GetMesh()->OverrideAnimationData(FlightPose.Object, true, true, 0.f, 1.f);
        getmesh()->setownernosee(true);
        getmesh()->setonlyownersee(false);
        getmesh()->setcastshadow(true);
        getmesh()->benableupdaterateoptimizations = true;
        getmesh()->visibilitybasedanimtickoption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
        getmesh()->setmaterial(0, BodyTeal1.Object);
        getmesh()->setmaterial(1, BodyTeal2.Object);
        GetMesh()->ComponentTags.Add(TEXT("BB.SkeletalRider"));
    }

    static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomWoodMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomWood.SM_BB_BroomWood"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomLeatherMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomLeather.SM_BB_BroomLeather"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomBristlesMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomBristles.SM_BB_BroomBristles"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomCopperMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomCopper.SM_BB_BroomCopper"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> BroomAccentMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_BroomAccent.SM_BB_BroomAccent"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> WandWoodMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_WandWood.SM_BB_WandWood"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> WandLeatherMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_WandLeather.SM_BB_WandLeather"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> WandCopperMesh(TEXT("/Basketbroom/Art/Equipment/SM_BB_WandCopper.SM_BB_WandCopper"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentWood(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipWood.M_BB_EquipWood"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentLeather(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipLeather.M_BB_EquipLeather"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentBristles(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipBristles.M_BB_EquipBristles"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> EquipmentCopper(TEXT("/Basketbroom/Art/Equipment/M_BB_EquipCopper.M_BB_EquipCopper"));

    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cone(TEXT("/Engine/BasicShapes/Cone.Cone"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Teal(TEXT("/Basketbroom/Art/Materials/M_BB_RiderTeal.M_BB_RiderTeal"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Copper(TEXT("/Basketbroom/Art/Materials/M_BB_RiderCopper.M_BB_RiderCopper"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Face(TEXT("/Basketbroom/Art/Materials/M_BB_RiderFace.M_BB_RiderFace"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Pants(TEXT("/Basketbroom/Art/Materials/M_BB_RiderPants.M_BB_RiderPants"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Leather(TEXT("/Basketbroom/Art/Materials/M_BB_BroomLeather.M_BB_BroomLeather"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Wood(TEXT("/Basketbroom/Art/Materials/M_BB_BroomWood.M_BB_BroomWood"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Bristles(TEXT("/Basketbroom/Art/Materials/M_BB_RiderBristles.M_BB_RiderBristles"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Ivory(TEXT("/Basketbroom/Art/Materials/M_BB_RiderIvory.M_BB_RiderIvory"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Metal(TEXT("/Basketbroom/Art/Materials/M_BB_Copper.M_BB_Copper"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Light(TEXT("/Basketbroom/Art/Materials/M_BB_TealLight.M_BB_TealLight"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Iron(TEXT("/Basketbroom/Art/Materials/M_BB_Iron.M_BB_Iron"));
    tealmaterial = Teal.Object;
    coppermaterial = Copper.Object;

    auto part = [this](const fname name, ustaticmesh* shape, umaterialinterface* material,
                      const fvector location, const fvector scale, const frotator rotation,
                      bool bcockpit, bool buniform = false)
    {
        ustaticmeshcomponent* component = createdefaultsubobject<ustaticmeshcomponent>(name);
        component->setupattachment(bcockpit ? static_cast<USceneComponent*>(Camera.Get()) : getmesh());
        component->setstaticmesh(shape);
        component->setmaterial(0, material);
        component->setrelativelocation(location);
        component->setrelativescale3d(scale);
        component->setrelativerotation(rotation);
        Component->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
        Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        component->setgenerateoverlapevents(false);
        component->setcaneveraffectnavigation(false);
        component->setonlyownersee(bcockpit);
        component->setownernosee(!bcockpit);
        component->setcastshadow(!bcockpit);
        Component->ComponentTags.Add(bCockpit ? TEXT("BB.Cockpit") : TEXT("BB.RiderVisual"));
        if (buniform)
        {
            Component->ComponentTags.Add(TEXT("BB.Uniform"));
            UniformParts.Add(Component);
        }
        return component;
    };

    if (!bskeletalriderenabled)
    {
        part(text("tunic"), Sphere.Object, Teal.Object, fvector(8, 0, 33), FVector(.42, .46, .69), frotator(-12, 0, 0), false, true);
        part(text("head"), Sphere.Object, Face.Object, fvector(23, 0, 81), FVector(.27, .25, .31), FRotator::ZeroRotator, false);
        part(text("helmet"), Sphere.Object, Teal.Object, fvector(21, 0, 92), FVector(.30, .28, .19), FRotator::ZeroRotator, false, true);
        part(text("chestmark"), Sphere.Object, Ivory.Object, fvector(30, 0, 40), FVector(.027, .17, .24), frotator(-12, 0, 0), false);
    }
    // cosmetic authored equipment shares the existing owner/remote part settings.
    for (const bool bcockpit : {false, true})
    {
        const fstring prefix = bcockpit ? text("cockpitbroom") : text("broom");
        const fvector mount = bcockpit ? fvector(55, 30, -48) : FVector::ZeroVector;
        part(fname(*(prefix + text("wood"))), BroomWoodMesh.Object, EquipmentWood.Object,
             mount, FVector::OneVector, FRotator::ZeroRotator, bcockpit);
        part(fname(*(prefix + text("leather"))), BroomLeatherMesh.Object, EquipmentLeather.Object,
             mount, FVector::OneVector, FRotator::ZeroRotator, bcockpit);
        part(fname(*(prefix + text("bristles"))), BroomBristlesMesh.Object, EquipmentBristles.Object,
             mount, FVector::OneVector, FRotator::ZeroRotator, bcockpit);
        part(fname(*(prefix + text("copper"))), BroomCopperMesh.Object, EquipmentCopper.Object,
             mount, FVector::OneVector, FRotator::ZeroRotator, bcockpit);
        part(fname(*(prefix + text("accent"))), BroomAccentMesh.Object, Teal.Object,
             mount, FVector::OneVector, FRotator::ZeroRotator, bcockpit, true);
    }
    for (int32 side : {-1, 1})
    {
        if (bskeletalriderenabled) continue;
        const fstring prefix = side < 0 ? text("left") : text("right");
        part(fname(*(prefix + text("arm"))), Sphere.Object, Teal.Object, fvector(32, side * 24, 32), FVector(.66, .15, .17), frotator(-40, 0, 0), false, true);
        part(fname(*(prefix + text("glove"))), Sphere.Object, Leather.Object, fvector(56, side * 21, 11), FVector(.17, .14, .15), FRotator::ZeroRotator, false);
        part(fname(*(prefix + text("bentleg"))), Sphere.Object, Pants.Object, fvector(8, side * 19, -18), FVector(.50, .18, .24), frotator(-30, 0, 0), false);
        part(fname(*(prefix + text("boot"))), Sphere.Object, Leather.Object, fvector(29, side * 20, -49), FVector(.25, .20, .48), frotator(-10, 0, 0), false);
    }

    part(text("cockpitcharmmount"), Cylinder.Object, EquipmentCopper.Object, fvector(145, 30, -50.5), FVector(.14, .14, .03), FRotator::ZeroRotator, true);
    part(text("cockpitflightcharm"), Sphere.Object, Light.Object, fvector(145, 30, -47.6), FVector(.09, .08, .045), FRotator::ZeroRotator, true);

    // original 44 cm wand: tapered wood, padded grip and copper collar.
    // cosmetic owner/remote copies use the existing equipment filtering.
    for (bool bcockpit : {false, true})
    {
        const fstring prefix = bcockpit ? text("cockpitwand") : text("riderwand");
        const fvector start = bcockpit ? fvector(45, 38, -29) : fvector(43, 10, 14);
        const fvector direction = (bcockpit ? fvector(42, -8, 12) : fvector(44, 2, 7)).GetSafeNormal();
        const frotator rotation = FRotationMatrix::MakeFromZ(Direction).Rotator();
        WandParts.Add(Part(FName(*(Prefix + text("wood"))), WandWoodMesh.Object,
            EquipmentWood.Object, start, FVector::OneVector, rotation, bcockpit));
        WandParts.Add(Part(FName(*(Prefix + text("grip"))), WandLeatherMesh.Object,
            EquipmentLeather.Object, start, FVector::OneVector, rotation, bcockpit));
        WandParts.Add(Part(FName(*(Prefix + text("collar"))), WandCopperMesh.Object,
            EquipmentCopper.Object, start, FVector::OneVector, rotation, bcockpit));
    }
    wandlight = part(text("wandlumos"), Sphere.Object, Light.Object, fvector(87, 30, -17),
        FVector(.045), FRotator::ZeroRotator, true);
    wandlight->setvisibility(false);
    wandlamp = createdefaultsubobject<upointlightcomponent>(text("wandlumoslamp"));
    wandlamp->setupattachment(getmesh());
    wandlamp->setrelativelocation(fvector(88, 12, 21));
    WandLamp->SetLightColor(FLinearColor(.68f, .87f, 1.f));
    WandLamp->SetIntensity(600.f);
    WandLamp->SetAttenuationRadius(450.f);
    wandlamp->setcastshadows(false);
    wandlamp->setvisibility(false);
    shieldvisual = createdefaultsubobject<uinstancedstaticmeshcomponent>(text("protegoarcs"));
    shieldvisual->setupattachment(getmesh());
    ShieldVisual->SetStaticMesh(Cylinder.Object);
    // ivory already carries the cooked instanced-mesh usage flag. its shared
    // Tint/Glow parameters supply the blue energy without runtime shader edits.
    shieldvisual->setmaterial(0, Ivory.Object);
    ShieldVisual->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
    ShieldVisual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    shieldvisual->setgenerateoverlapevents(false);
    shieldvisual->setcaneveraffectnavigation(false);
    shieldvisual->setcastshadow(false);
    shieldvisual->setownernosee(true);
    shieldvisual->setonlyownersee(false);
    shieldvisual->setvisibility(false);
    ShieldVisual->ComponentTags.Add(TEXT("BB.Spell.Shield"));
    // other riders see the surrounding shield. its world-space great circles
    // must not become large vertical bars through the owner's camera.
    for (int32 plane = 0; plane < 3; ++plane)
        for (int32 segment = 0; segment < 16; ++segment)
        {
            const float a = segment * ue_two_pi / 16.f, b = a + ue_two_pi / 20.f;
            auto point = [plane](float angle)
            {
                const float c = FMath::Cos(Angle) * 112.f, s = FMath::Sin(Angle) * 112.f;
                return fvector(plane == 0 ? 0.f : c, plane == 1 ? 0.f : (plane == 0 ? c : s),
                    12.f + (plane == 2 ? 0.f : s));
            };
            const fvector apos = point(a), bpos = point(b), axis = bpos - apos;
            ShieldVisual->AddInstance(FTransform(FRotationMatrix::MakeFromZ(Axis).ToQuat(),
                (apos + bpos) * .5f, FVector(.022, .022, Axis.Size() / 100.f)));
        }
    cockpitshieldvisual = createdefaultsubobject<uinstancedstaticmeshcomponent>(text("cockpitprotegoarcs"));
    cockpitshieldvisual->setupattachment(camera);
    CockpitShieldVisual->SetStaticMesh(Cylinder.Object);
    cockpitshieldvisual->setmaterial(0, Ivory.Object);
    CockpitShieldVisual->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
    CockpitShieldVisual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    cockpitshieldvisual->setgenerateoverlapevents(false);
    cockpitshieldvisual->setcaneveraffectnavigation(false);
    cockpitshieldvisual->setcastshadow(false);
    cockpitshieldvisual->setonlyownersee(true);
    cockpitshieldvisual->setownernosee(false);
    cockpitshieldvisual->setvisibility(false);
    CockpitShieldVisual->ComponentTags.Add(TEXT("BB.Spell.Shield.Cockpit"));
    // four fine corner arcs at the edge of the 92-degree camera view. neither
    // a diameter nor an arc crosses the reticle, in any look direction.
    for (int32 corner = 0; corner < 4; ++corner)
        for (int32 segment = 0; segment < 6; ++segment)
        {
            const float a = corner * ue_pi / 2.f + ue_pi / 12.f + segment * ue_pi / 18.f;
            const float b = a + ue_pi / 24.f;
            auto point = [](float angle) { return FVector(100.f, FMath::Cos(Angle) * 92.f, FMath::Sin(Angle) * 48.f); };
            const fvector apos = point(a), bpos = point(b), axis = bpos - apos;
            CockpitShieldVisual->AddInstance(FTransform(FRotationMatrix::MakeFromZ(Axis).ToQuat(),
                (apos + bpos) * .5f, FVector(.006, .006, Axis.Size() / 100.f)));
        }

    // original provisional basketbroom tool, about 103 cm overall and 36 cm
    // across the head. the current oversized bludger is not a physical fit;
    // this pass adds appearance only, without collision or striking behavior.
    // four instanced mesh layers per view keep the open head/lacing inexpensive.
    for (const bool bcockpit : {false, true})
    {
        const fstring prefix = bcockpit ? text("cockpithurley") : text("riderhurley");
        // the owner's presentation sits below the ball cards and to the right
        // of the reticle. remote equipment retains its authored world scale.
        const fvector base = bcockpit ? fvector(82, 47, -80) : fvector(48, 25, -10);
        const frotator pose = bcockpit ? frotator(-15, 0, 0) : frotator(-20, 0, 0);
        auto layer = [this, bcockpit, &prefix, base, pose](const tchar* suffix, ustaticmesh* shape, umaterialinterface* material)
        {
            uinstancedstaticmeshcomponent* component = createdefaultsubobject<uinstancedstaticmeshcomponent>(fname(*(prefix + suffix)));
            component->setupattachment(bcockpit ? static_cast<USceneComponent*>(Camera.Get()) : getmesh());
            component->setstaticmesh(shape);
            component->setmaterial(0, material);
            component->setrelativelocation(base);
            component->setrelativerotation(pose);
            component->setrelativescale3d(bcockpit ? FVector(.72) : FVector::OneVector);
            Component->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
            Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            component->setgenerateoverlapevents(false);
            component->setcaneveraffectnavigation(false);
            component->setonlyownersee(bcockpit);
            component->setownernosee(!bcockpit);
            component->setcastshadow(!bcockpit);
            component->setvisibility(false);
            Component->ComponentTags.Add(TEXT("BB.Hurley"));
            Component->ComponentTags.Add(bCockpit ? TEXT("BB.Hurley.Owner") : TEXT("BB.Hurley.Remote"));
            HurleyParts.Add(Component);
            return component;
        };
        uinstancedstaticmeshcomponent* frame = layer(text("frame"), Cylinder.Object, Wood.Object);
        uinstancedstaticmeshcomponent* rounded = layer(text("roundedface"), Sphere.Object, Wood.Object);
        uinstancedstaticmeshcomponent* grip = layer(text("paddedgrip"), Sphere.Object, Leather.Object);
        uinstancedstaticmeshcomponent* lacing = layer(text("openpocket"), Cylinder.Object, Ivory.Object);
        auto ellipsoid = [](uinstancedstaticmeshcomponent* component, const fvector& center, const fvector& dimensions)
        {
            Component->AddInstance(FTransform(FQuat::Identity, center, dimensions / 100.0));
        };
        auto rod = [](uinstancedstaticmeshcomponent* component, const fvector& a, const fvector& b, double diameter)
        {
            const fvector axis = b - a;
            const fquat rotation = FQuat::FindBetweenNormals(FVector::UpVector, Axis.GetSafeNormal());
            component->addinstance(ftransform(rotation, (a + b) * .5, fvector(diameter / 100.0, diameter / 100.0, Axis.Size() / 100.0)));
        };

        // the oval shaft blends into a solid, rounded, offset lower face.
        Frame->AddInstance(FTransform(FQuat::Identity, fvector(0, 0, 38), FVector(.032, .043, .72)));
        ellipsoid(rounded, fvector(0, 1.2, 71), FVector(4.0, 30, 19));
        ellipsoid(grip, fvector(0, 0, 20), FVector(4.5, 6.0, 29));
        ellipsoid(grip, fvector(0, 0, 2.5), FVector(5.0, 6.5, 5.0));

        auto outline = [](double angle)
        {
            return fvector(0, 4 + 16 * FMath::Sin(Angle) + 3 * FMath::Cos(Angle), 84 + 17 * FMath::Cos(Angle));
        };
        constexpr int32 rimsegments = 20;
        for (int32 i = 0; i < rimsegments; ++i)
        {
            const fvector a = Outline(2.0 * pi * i / rimsegments);
            const fvector b = Outline(2.0 * pi * (i + 1) / rimsegments);
            rod(frame, a, b, 2.6);
            // rounded overlaps cover every segment junction; no projecting ends.
            ellipsoid(rounded, a, FVector(2.6));
        }

        // sparse ivory lacing leaves the upper pocket visibly open. its deepest
        // point is just 3.2 cm behind the sidewall plane; there is no closed cup.
        for (double z : {80.0, 86.0, 92.0, 98.0})
        {
            const double t = (z - 84.0) / 17.0;
            const double centery = 4.0 + 3.0 * t;
            const double halfwidth = 16.0 * FMath::Sqrt(1.0 - t * t);
            const fvector Center(3.2, centery, z);
            rod(lacing, fvector(0, centery - halfwidth, z), center, .75);
            rod(lacing, center, fvector(0, centery + halfwidth, z), .75);
        }
        for (double t : {-.55, 0.0, .55})
        {
            const double top = FMath::Sqrt(1.0 - t * t);
            const fvector low(0, 4.0 + 16.0 * t - 12.0 / 17.0, 80);
            const fvector Middle(3.2, 4.0 + 16.0 * t + 18.0 / 17.0, 90);
            const fvector high(0, 4.0 + 16.0 * t + 3.0 * top, 84.0 + 17.0 * top);
            rod(lacing, low, middle, .75);
            rod(lacing, middle, high, .75);
        }
        // paired face stripes identify the solid striking area without symbols
        // borrowed from living sporting traditions.
        rod(lacing, FVector(-2.05, -6, 70), FVector(-2.05, 8, 72), 1.1);
        rod(lacing, FVector(-2.05, -5, 73), FVector(-2.05, 9, 75), 1.1);
    }
}

void ABBRiderCharacter::BeginPlay()
{
    Super::BeginPlay();
    registercontrollerinputlifecycle();
    if (hasauthority() || islocallycontrolled())
    {
        getcharactermovement()->setmovementmode(move_flying);
    }
    refreshuniform();
    refreshhurley();
    initializesportspellvisuals();
    shieldmaterial = shieldvisual->createdynamicmaterialinstance(0);
    if (shieldmaterial) shieldmaterial->setvectorparametervalue(text("tint"), FLinearColor(.18f, .58f, 1.f));
    cockpitshieldmaterial = cockpitshieldvisual->createdynamicmaterialinstance(0);
    if (cockpitshieldmaterial) cockpitshieldmaterial->setvectorparametervalue(text("tint"), FLinearColor(.10f, .40f, .72f));
    refreshspellvisuals();
}

void ABBRiderCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& outlifetimeprops) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    doreplifetime(abbridercharacter, teamindex);
    doreplifetime(abbridercharacter, position);
    doreplifetime(abbridercharacter, rosterindex);
    doreplifetime(abbridercharacter, binteractheld);
    doreplifetime(abbridercharacter, stunremaining);
    doreplifetime(abbridercharacter, spellcooldownremaining);
    doreplifetime(abbridercharacter, shieldremaining);
    doreplifetime(abbridercharacter, impedimentremaining);
    doreplifetime(abbridercharacter, disarmremaining);
    doreplifetime(abbridercharacter, vitality);
    doreplifetime(abbridercharacter, lumosremaining);
    doreplifetime(abbridercharacter, revealremaining);
    doreplifetime(abbridercharacter, concealremaining);
    doreplifetime(abbridercharacter, petrificusremaining);
    doreplifetime(abbridercharacter, transformationremaining);
    doreplifetime(abbridercharacter, imperioremaining);
}

void ABBRiderCharacter::Tick(float deltaseconds)
{
    Super::Tick(DeltaSeconds);
    const abbmatchstate* match = getworld()->getgamestate<abbmatchstate>();
    const bool bpenaltykeepermovement = match && match->bpenaltyshotactive && match->canmoveduringpenalty(this);
    if (hasauthority())
    {
        if (!match) stunremaining = FMath::Max(0.0f, stunremaining - deltaseconds);
    }
    if (hasspellmovementlock() && !bpenaltykeepermovement)
    {
        getcharactermovement()->stopmovementimmediately();
    }
    if (lastvisualteam != teamindex)
    {
        refreshuniform();
    }
    refreshhurley();
    refreshspellvisuals();

    aplayercontroller* player = cast<aplayercontroller>(controller);
    if (!player || !player->islocalcontroller())
    {
        return;
    }
    tickcontrollerinput(player);
    // normal-client delivery: hud marks its draw before a later tick replies.
    // this does not prove human attention or prevent a modified client withholding.
    const double feedbacknow = getworld()->gettimeseconds();
    PendingSpellNotices.RemoveAll([FeedbackNow](const fspellnotice& notice)
        { return feedbacknow - Notice.QueuedAt >= spellnoticedeadline; });
    if (activeimpedimentattackid && feedbacknow - activespellnoticequeuedat >= spellnoticedeadline)
    {
        // an expired/unshown notice must never manufacture a confirmation.
        activeimpedimentattackid = 0;
        spellfeedbackremaining = 0.f;
    }
    if (activeimpedimentattackid && spellfeedbackdisplayedat >= 0.0
        && feedbacknow - spellfeedbackdisplayedat >= .25)
    {
        if (!AcknowledgedImpediments.Contains(ActiveImpedimentAttackId))
        {
            AcknowledgedImpediments.Add(ActiveImpedimentAttackId);
            serveracknowledgeimpediment(activeimpedimentattackid);
        }
        activeimpedimentattackid = 0;
        // drain another critical notice immediately after this one's display
        // obligation, rather than making it wait the full ordinary toast time.
        if (PendingSpellNotices.ContainsByPredicate([](const fspellnotice& notice) { return Notice.AttackId != 0; }))
            spellfeedbackremaining = 0.f;
    }
    if (spellfeedbackdisplayedat >= 0.0 || !activeimpedimentattackid)
        spellfeedbackremaining = FMath::Max(0.f, spellfeedbackremaining - deltaseconds);
    if (spellfeedbackremaining <= 0.f && activeimpedimentattackid == 0)
        shownextspellnotice();
#if !ue_build_shipping
    if (getworld()->worldtype == EWorldType::PIE && !PendingDevelopmentInputs.IsEmpty())
    {
        // python reflected calls hold feditorscriptexecutionguard, which makes
        // actor rpc callspace local. dispatch from normal native tick so these
        // requests take the same client/server transport path as keyboard input.
        tarray<tpair<int32, int32>> inputs = movetemp(pendingdevelopmentinputs);
        for (const tpair<int32, int32>& input : inputs)
        {
            if (Input.Key == -1)
            {
                bdevelopmentinteractheld = Input.Value != 0;
                if (bdevelopmentinteractheld) startinteract();
                else stopinteract();
            }
            else
            {
                SubmitAction(Input.Key, Input.Value);
            }
        }
    }
#endif
    // reconcile held keys after focus changes and allow Ctrl+W/A/S/D regardless
    // of press order. a plain bindkey chord excludes active modifier keys.
    for (const fkey key : {EKeys::W, EKeys::S, EKeys::A, EKeys::D, EKeys::SpaceBar, EKeys::LeftControl, EKeys::RightControl})
    {
        if (player->isinputkeydown(key))
        {
            MovementKeys.Add(Key);
        }
        else
        {
            MovementKeys.Remove(Key);
        }
    }
    if (blocalinteractheld && !bdevelopmentinteractheld && !Player->IsInputKeyDown(EKeys::E)
        && (bgamepadrequiresneutral || !Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Left)))
    {
        stopinteract();
    }
    const abbmatchstate* inputmatch = getworld()->getgamestate<abbmatchstate>();
    if (inputmatch && inputmatch->bpenaltyshotactive)
    {
        bshowroster = false;
        bshowspellbook = false;
        if (!inputmatch->canmoveduringpenalty(this))
        {
            consumemovementinputvector();
            getcharactermovement()->stopmovementimmediately();
            return;
        }
    }
    if (hasspellmovementlock() && !bpenaltykeepermovement)
    {
        return;
    }
    const float forward = FMath::Clamp(float(MovementKeys.Contains(EKeys::W)) - float(MovementKeys.Contains(EKeys::S))
        + ControllerAxis(EKeys::Gamepad_LeftY), -1.f, 1.f);
    const float right = FMath::Clamp(float(MovementKeys.Contains(EKeys::D)) - float(MovementKeys.Contains(EKeys::A))
        + ControllerAxis(EKeys::Gamepad_LeftX), -1.f, 1.f);
    const float up = float(MovementKeys.Contains(EKeys::SpaceBar))
        - float(MovementKeys.Contains(EKeys::LeftControl) || MovementKeys.Contains(EKeys::RightControl))
        + (bgamepadrequiresneutral ? 0.f : float(Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Bottom))
            - float(Player->IsInputKeyDown(EKeys::Gamepad_FaceButton_Right)));
    const frotator aimrotation = getcontrolrotation();
    AddMovementInput(AimRotation.Vector(), forward);
    addmovementinput(frotationmatrix(frotator(0, AimRotation.Yaw, 0)).GetUnitAxis(EAxis::Y), right);
    AddMovementInput(FVector::UpVector, FMath::Clamp(Up, -1.f, 1.f));
}

void ABBRiderCharacter::SetupPlayerInputComponent(UInputComponent* input)
{
    Super::SetupPlayerInputComponent(Input);
    check(input);
    bindcontrollerinput(input);
    for (const fkey key : {EKeys::W, EKeys::S, EKeys::A, EKeys::D, EKeys::SpaceBar, EKeys::LeftControl, EKeys::RightControl})
    {
        input->bindkey(key, ie_pressed, this, &ABBRiderCharacter::MovementPressed);
        input->bindkey(key, ie_released, this, &ABBRiderCharacter::MovementReleased);
    }
    Input->BindAxisKey(EKeys::MouseX, this, &ABBRiderCharacter::LookYaw);
    Input->BindAxisKey(EKeys::MouseY, this, &ABBRiderCharacter::LookPitch);
    // descending uses ctrl; interaction must still work while it is held.
    for (bool bshift : {false, true})
    {
        for (bool bcontrol : {false, true})
        {
            Input->BindKey(FInputChord(EKeys::E, bshift, bcontrol, false, false), ie_pressed, this, &ABBRiderCharacter::StartInteract);
            Input->BindKey(FInputChord(EKeys::E, bshift, bcontrol, false, false), ie_released, this, &ABBRiderCharacter::ReleaseInteractInput);
            Input->BindKey(FInputChord(EKeys::LeftMouseButton, bshift, bcontrol, false, false), ie_pressed, this, &ABBRiderCharacter::ReleaseBall);
            Input->BindKey(FInputChord(EKeys::Q, bshift, bcontrol, false, false), ie_pressed, this, &ABBRiderCharacter::CastSelectedSpell);
            Input->BindKey(FInputChord(EKeys::R, bshift, bcontrol, false, false), ie_pressed, this, &ABBRiderCharacter::RequestShield);
        }
    }
    for (const fkey key : {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five, EKeys::Six})
    {
        input->bindkey(key, ie_pressed, this, &ABBRiderCharacter::RequestPosition);
    }
    Input->BindKey(EKeys::T, ie_pressed, this, &ABBRiderCharacter::RequestTeam);
    Input->BindKey(EKeys::Enter, ie_pressed, this, &ABBRiderCharacter::RequestReady);
    Input->BindKey(EKeys::P, ie_pressed, this, &ABBRiderCharacter::RequestStoppage);
    Input->BindKey(EKeys::Tab, ie_pressed, this, &ABBRiderCharacter::ToggleRoster);
    Input->BindKey(EKeys::Z, ie_pressed, this, &ABBRiderCharacter::PreviousSpell);
    Input->BindKey(EKeys::X, ie_pressed, this, &ABBRiderCharacter::NextSpell);
    Input->BindKey(EKeys::B, ie_pressed, this, &ABBRiderCharacter::RequestBloodbroom);
    Input->BindKey(EKeys::V, ie_pressed, this, &ABBRiderCharacter::ToggleSpellbook);
    Input->BindKey(EKeys::F6, ie_pressed, this, &ABBRiderCharacter::RequestFreeShot);
    Input->BindKey(EKeys::F7, ie_pressed, this, &ABBRiderCharacter::RequestPossessionAward);
    Input->BindKey(EKeys::F8, ie_pressed, this, &ABBRiderCharacter::RequestPenaltyShot);
    Input->BindKey(EKeys::F9, ie_pressed, this, &ABBRiderCharacter::RequestEjection);
    Input->BindKey(EKeys::F10, ie_pressed, this, &ABBRiderCharacter::RequestModerateAdvantage);
}

void ABBRiderCharacter::MovementPressed(FKey key) { businggamepad = false; MovementKeys.Add(Key); }
void ABBRiderCharacter::MovementReleased(FKey key) { MovementKeys.Remove(Key); }
void ABBRiderCharacter::LookYaw(float value) { if (!FMath::IsNearlyZero(Value)) businggamepad = false; addcontrolleryawinput(value); }
void ABBRiderCharacter::LookPitch(float value) { if (!FMath::IsNearlyZero(Value)) businggamepad = false; addcontrollerpitchinput(-value); }

void ABBRiderCharacter::StartInteract()
{
    if (!blocalinteractheld)
    {
        blocalinteractheld = true;
        serverstartinteract();
    }
}

void ABBRiderCharacter::StopInteract()
{
    blocalinteractheld = false;
    serverstopinteract();
}

void ABBRiderCharacter::ReleaseBall() { submitaction(1); }

void ABBRiderCharacter::RequestPosition(FKey key)
{
    const fkey positions[] = {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five, EKeys::Six};
    for (int32 index = 0; index < ue_array_count(positions); ++index)
    {
        if (key == positions[index])
        {
            submitaction(2, index);
            return;
        }
    }
}

void ABBRiderCharacter::RequestTeam() { submitaction(3, teamindex == 0 ? 1 : 0); }
void ABBRiderCharacter::RequestReady() { submitaction(4); }
void ABBRiderCharacter::RequestStoppage() { submitaction(5); }
void ABBRiderCharacter::ToggleRoster() { bshowroster = !bshowroster; if (bshowroster) bshowspellbook = false; }
void ABBRiderCharacter::ToggleSpellbook() { bshowspellbook = !bshowspellbook; if (bshowspellbook) bshowroster = false; }
void ABBRiderCharacter::PreviousSpell() { selectedspell = (selectedspell + FMath::Max(1, BBSpellCatalog::Count()) - 1) % FMath::Max(1, BBSpellCatalog::Count()); }
void ABBRiderCharacter::NextSpell() { selectedspell = (selectedspell + 1) % FMath::Max(1, BBSpellCatalog::Count()); }
void ABBRiderCharacter::CastSelectedSpell() { submitaction(6, selectedspell); }
void ABBRiderCharacter::RequestShield() { submitaction(7); }
void ABBRiderCharacter::RequestBloodbroom() { submitaction(8); }
void ABBRiderCharacter::RequestFreeShot() { submitaction(12); }
void ABBRiderCharacter::RequestPossessionAward() { submitaction(9); }
void ABBRiderCharacter::RequestPenaltyShot() { submitaction(10); }
void ABBRiderCharacter::RequestEjection() { submitaction(11); }
void ABBRiderCharacter::RequestModerateAdvantage() { submitaction(13); }

void ABBRiderCharacter::SubmitAction(int32 action, int32 value)
{
    if (islocallycontrolled())
    {
        serveraction(action, value, getaimdirection());
    }
}

bool ABBRiderCharacter::DevelopmentRequestAction(int32 action, int32 value)
{
#if ue_build_shipping
    return false;
#else
    if (!getworld() || getworld()->worldtype != EWorldType::PIE || !islocallycontrolled()
        || !isvalid(cast<aplayercontroller>(getcontroller())) || action < 0 || action > 13
        || (action == 2 && (value < 0 || value > 5))
        || (action == 3 && (value < 0 || value > 1))
        || (action == 6 && (value < 0 || value >= BBSpellCatalog::Count()))
        || PendingDevelopmentInputs.Num() >= maxdevelopmentinputs)
        return false;
    PendingDevelopmentInputs.Emplace(Action, value);
    return true;
#endif
}

bool ABBRiderCharacter::DevelopmentSetInteraction(bool bheld)
{
#if ue_build_shipping
    return false;
#else
    if (!getworld() || getworld()->worldtype != EWorldType::PIE || !islocallycontrolled()
        || !isvalid(cast<aplayercontroller>(getcontroller()))
        || PendingDevelopmentInputs.Num() >= maxdevelopmentinputs)
        return false;
    PendingDevelopmentInputs.Emplace(-1, bheld ? 1 : 0);
    return true;
#endif
}

void ABBRiderCharacter::ServerStartInteract_Implementation()
{
    if (!hasauthority() || binteractheld || !controller || hasspellmovementlock())
    {
        return;
    }
    binteractheld = true;
    forcenetupdate();
    const double now = getworld()->gettimeseconds();
    // held capture still works when a rapid key repeat is throttled. stops are
    // never throttled, so the server cannot retain a released interaction.
    if (stunremaining > 0.0f || now - lastserverinteracttime < 0.08)
    {
        return;
    }
    lastserverinteracttime = now;
    if (abbmatchstate* match = getworld()->getgamestate<abbmatchstate>())
    {
        match->handleaction(this, 0, 0, getaimdirection());
    }
}

void ABBRiderCharacter::ServerStopInteract_Implementation()
{
    if (binteractheld)
    {
        binteractheld = false;
        forcenetupdate();
    }
}

void ABBRiderCharacter::ServerAction_Implementation(int32 action, int32 value, fvector aim)
{
    if (!hasauthority() || !controller || action < 0 || action > 13)
    {
        return;
    }
    if (!FMath::IsFinite(Aim.X) || !FMath::IsFinite(Aim.Y) || !FMath::IsFinite(Aim.Z)
        || !FMath::IsNearlyEqual(Aim.SizeSquared(), 1.0, 0.02))
    {
        return;
    }
    const abbmatchstate* matchstate = getworld()->getgamestate<abbmatchstate>();
    const bool bprotectedshotrelease = action == 1 && matchstate && matchstate->bpenaltyshotactive
        && matchstate->penaltyshooterslot == rosterindex;
    if ((action <= 1 && hasspellmovementlock() && !bprotectedshotrelease)
        || (action == 2 && (value < 0 || value > 5))
        || (action == 3 && (value < 0 || value > 1))
        || (action == 6 && (value < 0 || value >= BBSpellCatalog::Count())))
    {
        return;
    }
    const double now = getworld()->gettimeseconds();
    if (now - lastserveractiontime < 0.06)
    {
        return;
    }
    lastserveractiontime = now;
    if (abbmatchstate* match = getworld()->getgamestate<abbmatchstate>())
    {
        match->handleaction(this, action, value, Aim.GetSafeNormal());
    }
}

fvector ABBRiderCharacter::GetAimDirection() const
{
    const fvector aim = GetBaseAimRotation().Vector();
    return Aim.ContainsNaN() ? getactorforwardvector() : Aim.GetSafeNormal();
}

fvector ABBRiderCharacter::GetCarryLocation() const
{
    const fvector aim = getaimdirection();
    const fvector right = frotationmatrix(frotator(0, Aim.Rotation().Yaw, 0)).GetUnitAxis(EAxis::Y);
    // use the largest held-ball radius so neither authority custody nor the
    // local predicted held visual can protrude through a roof face or wall.
    return BBArena::ClampSphere(GetActorLocation() + fvector(0, 0, baseeyeheight - 25.0f)
        + aim * 175.0f + right * 35.0f, 65.0);
}

void ABBRiderCharacter::RefreshUniform()
{
    if (bskeletalriderenabled)
    {
        const tarray<tobjectptr<umaterialinterface>>& materials = teamindex == 0 ? skeletaltealmaterials : skeletalcoppermaterials;
        for (int32 index = 0; index < Materials.Num(); ++index)
            if (materials[index]) getmesh()->setmaterial(index, materials[index]);
    }
    umaterialinterface* material = teamindex == 0 ? TealMaterial.Get() : CopperMaterial.Get();
    if (material)
    {
        for (ustaticmeshcomponent* part : uniformparts)
        {
            if (part)
            {
                part->setmaterial(0, material);
            }
        }
    }
    lastvisualteam = teamindex;
}

void ABBRiderCharacter::OnRep_TeamIndex() { refreshuniform(); }

void ABBRiderCharacter::NotifySpellResult(const fstring& message, uint64 impedimentattackid)
{
    if (hasauthority() && isvalid(cast<aplayercontroller>(getcontroller())))
        ClientSpellResult(Message.Left(256), impedimentattackid);
}

void ABBRiderCharacter::ClientSpellResult_Implementation(const fstring& message, uint64 impedimentattackid)
{
    if (!getworld()) return;
    if (impedimentattackid && (AcknowledgedImpediments.Contains(ImpedimentAttackId)
        || activeimpedimentattackid == impedimentattackid
        || PendingSpellNotices.ContainsByPredicate([ImpedimentAttackId](const fspellnotice& notice)
            { return Notice.AttackId == impedimentattackid; }))) return;
    const double now = getworld()->gettimeseconds();
    PendingSpellNotices.RemoveAll([Now](const fspellnotice& notice)
        { return now - Notice.QueuedAt >= spellnoticedeadline; });
    if (impedimentattackid)
    {
        // critical feedback preempts ordinary traffic immediately. preserve
        // the interrupted, unacknowledged id with its original deadline.
        PendingSpellNotices.RemoveAll([](const fspellnotice& notice) { return Notice.AttackId == 0; });
        if (activeimpedimentattackid && now - activespellnoticequeuedat < spellnoticedeadline)
            PendingSpellNotices.Insert({SpellFeedback, activeimpedimentattackid, activespellnoticequeuedat}, 0);
        PendingSpellNotices.Insert({Message.Left(256), impedimentattackid, now}, 0);
        // the normal server rate is well below this burst ceiling. on overflow
        // discard the oldest receipt without ack, never invent proof for it.
        while (PendingSpellNotices.Num() > maxcriticalspellnotices)
        {
            int32 oldest = 0;
            for (int32 i = 1; i < PendingSpellNotices.Num(); ++i)
                if (PendingSpellNotices[I].QueuedAt < PendingSpellNotices[Oldest].QueuedAt) oldest = i;
            PendingSpellNotices.RemoveAt(Oldest);
        }
        activeimpedimentattackid = 0;
        spellfeedbackremaining = 0.f;
        shownextspellnotice();
        return;
    }
    // ordinary repeats have no proof obligation. keep only recent unique
    // notices, and never let them interrupt a pending critical receipt.
    PendingSpellNotices.RemoveAll([&Message](const fspellnotice& notice)
        { return Notice.AttackId == 0 && Notice.Message == message; });
    if (!activeimpedimentattackid && spellfeedbackremaining > 0.f && spellfeedback == message) return;
    int32 ordinarycount = 0;
    for (const fspellnotice& notice : pendingspellnotices) ordinarycount += Notice.AttackId == 0 ? 1 : 0;
    while (ordinarycount >= maxordinaryspellnotices)
    {
        const int32 oldest = PendingSpellNotices.IndexOfByPredicate([](const fspellnotice& notice) { return Notice.AttackId == 0; });
        if (oldest == index_none) break;
        PendingSpellNotices.RemoveAt(Oldest);
        --ordinarycount;
    }
    PendingSpellNotices.Add({Message.Left(256), 0, now});
    if (spellfeedbackremaining <= 0.f && !activeimpedimentattackid) shownextspellnotice();
}

void ABBRiderCharacter::ShowNextSpellNotice()
{
    SpellFeedback.Empty();
    spellfeedbackdisplayedat = -1.0;
    if (PendingSpellNotices.IsEmpty()) return;
    fspellnotice notice = movetemp(pendingspellnotices[0]);
    PendingSpellNotices.RemoveAt(0);
    spellfeedback = MoveTemp(Notice.Message);
    activeimpedimentattackid = Notice.AttackId;
    activespellnoticequeuedat = Notice.QueuedAt;
    spellfeedbackremaining = 2.25f;
}

void ABBRiderCharacter::MarkSpellFeedbackDisplayed()
{
    if (islocallycontrolled() && spellfeedbackremaining > 0.f && spellfeedbackdisplayedat < 0.0 && getworld())
        spellfeedbackdisplayedat = getworld()->gettimeseconds();
}

void ABBRiderCharacter::ServerAcknowledgeImpediment_Implementation(uint64 impedimentattackid)
{
    if (!hasauthority() || !controller || impedimentattackid == 0) return;
    if (abbmatchstate* match = getworld()->getgamestate<abbmatchstate>())
        match->confirmimpediment(this, impedimentattackid);
}

void ABBRiderCharacter::RefreshSpellVisuals()
{
    for (ustaticmeshcomponent* part : wandparts) if (part) part->setvisibility(disarmremaining <= 0.f);
    if (wandlight) wandlight->setvisibility(lumosremaining > 0.f && disarmremaining <= 0.f);
    if (wandlamp) wandlamp->setvisibility(lumosremaining > 0.f && disarmremaining <= 0.f);
    if (shieldvisual) shieldvisual->setvisibility(shieldremaining > 0.f);
    if (cockpitshieldvisual) cockpitshieldvisual->setvisibility(shieldremaining > 0.f);
    if (shieldmaterial && shieldremaining > 0.f)
        shieldmaterial->setscalarparametervalue(text("glow"), 1.5f + .35f * FMath::Sin(GetWorld()->GetTimeSeconds() * 6.f));
    if (cockpitshieldmaterial && shieldremaining > 0.f)
        cockpitshieldmaterial->setscalarparametervalue(text("glow"), .65f + .10f * FMath::Sin(GetWorld()->GetTimeSeconds() * 6.f));
    refreshsportspellvisuals();
}

void ABBRiderCharacter::RefreshHurley()
{
    const abbmatchstate* match = getworld() ? getworld()->getgamestate<abbmatchstate>() : nullptr;
    const bool bshouldshow = position == 4 && (!match || match->phase != text("donnybrook"));
    if (bhurleyvisible == bshouldshow) return;
    bhurleyvisible = bshouldshow;
    for (ustaticmeshcomponent* part : hurleyparts)
        if (part) part->setvisibility(bshouldshow);
}

void ABBRiderCharacter::OnRep_StunRemaining()
{
    if (hasspellmovementlock())
    {
        getcharactermovement()->stopmovementimmediately();
    }
}

void ABBRiderCharacter::ResetLocalInput()
{
    if (aplayercontroller* player = cast<aplayercontroller>(controller))
        if (player->islocalcontroller()) player->flushpressedkeys();
    PendingControllerInputs.Reset();
    gamepadrefereechoice = 0;
    bgamepadrequiresneutral = false;
    bobservedviewportfocus = false;
    getcharactermovement()->stopmovementimmediately();
    consumemovementinputvector();
    MovementKeys.Empty();
    blocalinteractheld = false;
    bdevelopmentinteractheld = false;
    PendingDevelopmentInputs.Reset();
    bshowroster = false;
    bshowspellbook = false;
    PendingSpellNotices.Reset();
    activeimpedimentattackid = 0;
    SpellFeedback.Empty();
    spellfeedbackremaining = 0.f;
    spellfeedbackdisplayedat = -1.0;
    activespellnoticequeuedat = 0.0;
}

void ABBRiderCharacter::UnPossessed()
{
    if (hasauthority())
    {
        binteractheld = false;
        forcenetupdate();
    }
    resetlocalinput();
    Super::UnPossessed();
}

void ABBRiderCharacter::PawnClientRestart()
{
    resetlocalinput();
    Super::PawnClientRestart();
}

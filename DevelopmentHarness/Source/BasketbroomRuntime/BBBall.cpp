#include "BBBall.h"
#include "BBArenaGeometry.h"
#include "BBMatchState.h"
#include "BBRiderCharacter.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
// the authored hoops are visual toruses without engine collision. sweep the
// ball against their exact expanded tube so a rim strike cannot become a goal.
bool sweeprims(const fvector& start, const fvector& end, float ballradius,
               float& hittime, fvector& hitnormal)
{
    bool bhit = false;
    const fvector delta = end - start;
    for (int32 side : {-1, 1})
    {
        const double planex = side * BBArena::GoalPlaneX;
        for (int32 hoop = 0; hoop < 4; ++hoop)
        {
            const bool bsmall = hoop == 3;
            const double tube = bsmall ? 16.0 : 20.0;
            const double major = (bsmall ? BBArena::SmallHoopRadius : BBArena::LargeHoopRadius) + tube;
            const fvector center(planex, bsmall ? 0.0 : (hoop - 1) * BBArena::HoopSpacing, bsmall ? BBArena::SmallHoopHeight : BBArena::LargeHoopHeight);
            const double expanded = ballradius + tube;
            if (FMath::Min(Start.X, End.X) > planex + expanded || FMath::Max(Start.X, End.X) < planex - expanded) continue;
            auto closestringpoint = [&center, major](const fvector& point)
            {
                const fvector radial(0, Point.Y - Center.Y, Point.Z - Center.Z);
                return center + Radial.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector) * major;
            };
            // a physics step is at most 1/120 second. samples spaced at no more
            // than a quarter expanded radius also cover high-speed releases.
            const int32 samples = FMath::Clamp(FMath::CeilToInt(Delta.Size() / (expanded * .25)), 1, 32);
            float previous = 0.f;
            for (int32 index = 0; index <= samples; ++index)
            {
                const float time = static_cast<float>(index) / samples;
                if (time > hittime) break;
                const fvector point = start + delta * time;
                const fvector offset = point - closestringpoint(point);
                if (Offset.SizeSquared() <= expanded * expanded)
                {
                    float low = previous, high = time;
                    for (int32 refine = 0; refine < 8; ++refine)
                    {
                        const float mid = (low + high) * .5f;
                        const fvector probe = start + delta * mid;
                        if (FVector::DistSquared(Probe, closestringpoint(probe)) <= expanded * expanded) high = mid;
                        else low = mid;
                    }
                    const fvector contact = start + delta * high;
                    const fvector normal = (contact - ClosestRingPoint(Contact)).GetSafeNormal();
                    if (FVector::DotProduct(Delta, normal) < 0)
                    {
                        hittime = high;
                        hitnormal = normal;
                        bhit = true;
                    }
                    break;
                }
                previous = time;
            }
        }
    }
    return bhit;
}
}

ABBBall::ABBBall()
{
    PrimaryActorTick.bCanEverTick = true;
    breplicates = true;
    balwaysrelevant = true;
    setreplicatemovement(true);
    setnetupdatefrequency(30);
    uscenecomponent* transformroot = createdefaultsubobject<uscenecomponent>(text("ballroot"));
    setrootcomponent(transformroot);
    TransformRoot->SetMobility(EComponentMobility::Movable);
    mesh = createdefaultsubobject<ustaticmeshcomponent>(text("ballmesh"));
    mesh->setupattachment(transformroot);
    Mesh->SetMobility(EComponentMobility::Movable);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere"));
    Mesh->SetStaticMesh(Sphere.Object);
    mesh->setcollisionprofilename(text("nocollision"));
    mesh->setcastshadow(true);
    leftwing = createdefaultsubobject<ustaticmeshcomponent>(text("leftwing"));
    rightwing = createdefaultsubobject<ustaticmeshcomponent>(text("rightwing"));
    for (ustaticmeshcomponent* wing : {LeftWing.Get(), RightWing.Get()})
    {
        // follow the smoothed ball mesh, retaining authored centimeter scale.
        wing->setupattachment(mesh);
        wing->setabsolute(false, false, true);
        Wing->SetMobility(EComponentMobility::Movable);
        wing->setcollisionprofilename(text("nocollision"));
        wing->setgenerateoverlapevents(false);
        wing->setcaneveraffectnavigation(false);
        wing->setvisibility(false);
    }
    leftwing->setrelativelocation(fvector(0, -50, 0));
    rightwing->setrelativelocation(fvector(0, 50, 0));
    for (const tchar* path : {TEXT("/Basketbroom/Art/Equipment/SM_BB_SnipeWingLeft"),
         TEXT("/Basketbroom/Art/Equipment/SM_BB_SnipeWingRight"),
         TEXT("/Basketbroom/Art/Equipment/SM_BB_SnitchWingLeft"),
         TEXT("/Basketbroom/Art/Equipment/SM_BB_SnitchWingRight")})
    {
        ConstructorHelpers::FObjectFinder<UStaticMesh> wingmesh(path);
        ChaseWingMeshes.Add(WingMesh.Object);
    }
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> WingIvory(TEXT("/Basketbroom/Art/Materials/M_BB_Cream"));
    snitchwingmaterial = WingIvory.Object;
    for (const tchar* path : {TEXT("/Basketbroom/Art/Materials/M_BB_BallQuaffle"),
         TEXT("/Basketbroom/Art/Materials/M_BB_BallQuark"), TEXT("/Basketbroom/Art/Materials/M_BB_Copper"),
         TEXT("/Basketbroom/Art/Materials/M_BB_BallSnitch"), TEXT("/Basketbroom/Art/Materials/M_BB_Iron")})
    {
        ConstructorHelpers::FObjectFinder<UMaterialInterface> material(path);
        BallMaterials.Add(Material.Object);
    }
}
void ABBBall::BeginPlay()
{
    Super::BeginPlay();
    match = getworld()->getgamestate<abbmatchstate>();
    home = getactorlocation();
    lastlocation = home;
    previousvisuallocation = home;
    chasetime = ballindex * 2.4f;
    onrep_appearance();
}
void ABBBall::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& outlifetimeprops) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    doreplifetime(abbball, ballindex); doreplifetime(abbball, holder);
    doreplifetime(abbball, capturingrider); doreplifetime(abbball, captureprogress);
    doreplifetime(abbball, bactive); doreplifetime(abbball, returnin);
    doreplifetime(abbball, ballstatus); doreplifetime(abbball, flightvelocity);
}
fstring ABBBall::DisplayName() const
{
    const tchar* names[] = {text("quaffle"), text("quark a"), text("quark b"), text("snipe"), text("snitch"), text("bludger a"), text("bludger b")};
    return Names[FMath::Clamp(BallIndex, 0, 6)];
}
void ABBBall::OnRep_Appearance()
{
    mesh->setrelativescale3d(fvector(radius() / 50.f));
    const int32 materialindex = isbludger() ? 4 : kind();
    if (BallMaterials.IsValidIndex(MaterialIndex)) mesh->setmaterial(0, ballmaterials[materialindex]);
    const int32 wingindex = ballindex == 3 ? 0 : 2;
    const bool bwingsready = ischase() && ChaseWingMeshes.IsValidIndex(WingIndex + 1)
        && chasewingmeshes[wingindex] && chasewingmeshes[wingindex + 1];
    leftwing->setvisibility(bwingsready);
    rightwing->setvisibility(bwingsready);
    if (bwingsready)
    {
        leftwing->setstaticmesh(chasewingmeshes[wingindex]);
        rightwing->setstaticmesh(chasewingmeshes[wingindex + 1]);
        umaterialinterface* wingmaterial = ballindex == 4 ? SnitchWingMaterial.Get()
            : (BallMaterials.IsValidIndex(2) ? BallMaterials[2].Get() : nullptr);
        leftwing->setmaterial(0, wingmaterial);
        rightwing->setmaterial(0, wingmaterial);
    }
    setactorhiddeningame(!bactive);
}
void ABBBall::UpdateChaseVisual(float deltaseconds)
{
    if (!ischase()) return;
    const fvector location = mesh->getcomponentlocation();
    const fvector travel = location - previousvisuallocation;
    previousvisuallocation = location;
    // cosmetic heading and flap only: neither actor transforms nor the
    // authority's capture sphere, flight velocity, or custody are modified.
    if (Travel.SizeSquared2D() > 1 && Travel.SizeSquared() < FMath::Square(1800.f))
    {
        const frotator heading(0, Travel.Rotation().Yaw, 0);
        Mesh->SetWorldRotation(FMath::RInterpTo(Mesh->GetComponentRotation(), heading, deltaseconds, 7.f));
    }
    const bool bflying = match && match->blive && bactive;
    const float frequency = bflying ? (ballindex == 3 ? 5.f : 7.f) : 1.4f;
    bobtime = FMath::Fmod(BobTime + deltaseconds * frequency * ue_two_pi, ue_two_pi);
    const float flap = FMath::Sin(BobTime) * (bflying ? 34.f : 10.f);
    leftwing->setrelativerotation(frotator(0, 0, -flap));
    rightwing->setrelativerotation(frotator(0, 0, flap));
}
tarray<double> ABBBall::DevelopmentGetRoofContactState() const
{
    if (!hasauthority() || !getworld() || getworld()->worldtype != EWorldType::PIE) return {};
    return {static_cast<double>(roofcontactcount), LastRoofNormal.X, LastRoofNormal.Y, LastRoofNormal.Z,
        LastRoofIncoming.X, LastRoofIncoming.Y, LastRoofIncoming.Z,
        LastRoofOutgoing.X, LastRoofOutgoing.Y, LastRoofOutgoing.Z};
}
bool ABBBall::DevelopmentSetFlightFixture(FVector location, fvector velocity)
{
#if ue_build_shipping
    return false;
#else
    // the explicit runtime checks matter: developmentonly metadata alone is
    // not an authorization boundary for a reflected callable function.
    if (!hasauthority() || !getworld() || getworld()->worldtype != EWorldType::PIE
        || holder || Location.ContainsNaN() || Velocity.ContainsNaN())
        return false;
    if (!setactorlocation(location, false, nullptr, ETeleportType::TeleportPhysics))
        return false;
    lastlocation = location;
    flightvelocity = velocity;
    distancesincereleasecm = 0;
    forcenetupdate();
    return true;
#endif
}
void ABBBall::ResetBall(FVector location)
{
    if (!hasauthority() || Location.ContainsNaN()) return;
    location = BBArena::ClampSphere(Location, radius());
    setactorlocation(location);
    lastlocation = location;
    flightvelocity = FVector::ZeroVector;
    distancesincereleasecm = 0;
    RecentThrower.Reset();
    throwerignoreremaining = impactcooldown = 0;
    holder = nullptr;
    captureprogress = 0;
    capturingrider = nullptr;
    cooldown = .25f;
    forcenetupdate();
}
void ABBBall::Tick(float deltaseconds)
{
    Super::Tick(DeltaSeconds);
    if (!match) match = getworld()->getgamestate<abbmatchstate>();
    updatechasevisual(deltaseconds);
    if (!hasauthority())
    {
        // interpolate only presentation: the actor root remains the replicated
        // authority transform. held equipment follows the visible rider each
        // frame, including the local player's predicted camera movement.
        const fvector target = isvalid(holder) ? holder->getcarrylocation() : getactorlocation();
        if (isvalid(holder) || FVector::DistSquared(LastLocation, target) > FMath::Square(1800.f)) lastlocation = target;
        else lastlocation = FMath::VInterpTo(LastLocation, target, deltaseconds, 16.f);
        mesh->setworldlocation(lastlocation);
        return;
    }
    // match tick owns all penalty time/physics. running even one ordinary
    // flight step here would make deadline outcomes depend on actor tick order.
    if (match && match->bpenaltyshotactive) return;
    if (!match || !match->blive || !bactive) { captureprogress = 0; capturingrider = nullptr; return; }
    cooldown = FMath::Max(0.f, cooldown - deltaseconds);
    lastlocation = getactorlocation();
    if (holder)
    {
        setactorlocation(holder->getcarrylocation());
        return;
    }
    if (ischase())
    {
        // constant bounded speed; copper snipe is exactly 60% of snitch speed.
        const float speed = ballindex == 3 ? 1020.f : 1700.f;
        // widen the route without speeding up either chase ball or its moving
        // target: one larger circuit takes proportionally longer.
        chasetime += deltaseconds * (ballindex == 3 ? .18f : .30f) / BBArena::LinearScale;
        const fvector target = BBArena::ScaleLayout(FVector(
            FMath::Sin(ChaseTime) * 4200.f, FMath::Cos(ChaseTime * 1.31f) * 2300.f,
            2450.f + FMath::Sin(ChaseTime * .73f) * 1100.f));
        SetActorLocation(BBArena::ClampSphere(
            FMath::VInterpConstantTo(GetActorLocation(), target, deltaseconds, speed), radius()));
        stepcapture(deltaseconds);
    }
    else
    {
        // fixed maximum physics step keeps the whole-ball goal sweep stable at low FPS.
        float remaining = FMath::Clamp(DeltaSeconds, 0.f, 1.f);
        while (remaining > ue_small_number && bactive && !holder)
        {
            const float step = FMath::Min(Remaining, 1.f / 120.f);
            stepflight(step);
            remaining -= step;
        }
    }
}
void ABBBall::StepPenaltyFlight(double deltaseconds)
{
    if (!hasauthority() || !isvalid(match) || !match->ispenaltyballactive(this)
        || !match->bpenaltyshotreleased || !bactive || holder || deltaseconds <= 0) return;
    cooldown = FMath::Max(0.f, cooldown - static_cast<float>(deltaseconds));
    lastlocation = getactorlocation();
    stepflight(deltaseconds);
}
void ABBBall::StepCapture(float deltaseconds)
{
    if (!hasauthority() || !isvalid(match)) return;
    abbridercharacter* best = nullptr;
    float bestdist = FMath::Square(380.f);
    for (abbridercharacter* rider : match->riders)
    {
        if (!isvalid(rider) || !rider->binteractheld || !match->caninteract(rider, this)) continue;
        const float dist = FVector::DistSquared(GetActorLocation(), rider->getactorlocation());
        if (dist < bestdist) { bestdist = dist; best = rider; }
    }
    if (capturingrider != best) { captureprogress = 0; capturingrider = best; }
    if (!best) { captureprogress = 0; return; }
    captureprogress = FMath::Min(1.f, captureprogress + deltaseconds);
    if (captureprogress >= 1.f && cooldown <= 0 && match->trycatch(best, this))
    {
        cooldown = .25f;
        captureprogress = 0;
    }
}
void ABBBall::StepFlight(double dt)
{
    if (!hasauthority() || !isvalid(match) || dt <= 0) return;
    throwerignoreremaining = FMath::Max(0.f, throwerignoreremaining - static_cast<float>(dt));
    impactcooldown = FMath::Max(0.f, impactcooldown - static_cast<float>(dt));
    const float r = radius();
    // Spawn/possession fixtures may begin outside the new volume. recover to
    // its nearest vertical interior, preserving identity, custody and velocity.
    const fvector boundedstart = BBArena::ClampSphere(GetActorLocation(), r);
    if (!GetActorLocation().Equals(BoundedStart, .001))
    {
        setactorlocation(boundedstart);
        BBArena::ReboundRoof(FlightVelocity, boundedstart, r, r);
    }
    if (FlightVelocity.IsNearlyZero()) return;
    FlightVelocity.Z -= (isbludger() ? 60.f : 380.f) * dt;
    const bool bpenaltyflight = match->ispenaltyballactive(this) && match->bpenaltyshotreleased;
    double remaining = dt;
    double elapsed = 0;
    // continue the unused portion after a rebound. a bounded contact count
    // prevents pathological overlapping fixtures from hanging a server tick.
    for (int32 bounce = 0; bounce < 12 && remaining > 1.e-9; ++bounce)
    {
        const fvector old = getactorlocation();
        fvector p = old + flightvelocity * remaining;
        fcollisionqueryparams query(scene_query_stat(basketbroomballflight), false, this);
        fcollisionobjectqueryparams staticobjects;
        StaticObjects.AddObjectTypesToQuery(ECC_WorldStatic);
        tarray<fhitresult> worldhits;
        getworld()->sweepmultibyobjecttype(worldhits, old, p, FQuat::Identity,
            staticobjects, FCollisionShape::MakeSphere(R), query);
        fhitresult worldhit;
        bool bcollision = false;
        float hittime = 1.f;
        fvector hitnormal = FVector::ZeroVector;
        for (const fhitresult& hit : worldhits)
        {
            const aactor* surface = Hit.GetActor();
            // the net mesh provides physical collision for native characters.
            // balls use the exact four planes, avoiding triangle back-face,
            // seam and mesh-thickness artifacts or two bounces for one touch.
            if (surface && Surface->ActorHasTag(TEXT("BB.Net.Roof"))) continue;
            if (Hit.Time <= hittime)
            {
                worldhit = hit;
                hittime = Hit.Time;
                hitnormal = Hit.Normal;
                bcollision = true;
            }
        }
        const bool brimhit = sweeprims(old, p, r, hittime, hitnormal);
        if (brimhit) bcollision = true;
        const bool broofhit = BBArena::SweepRoof(Old, p, r, hittime, hitnormal);
        if (broofhit) bcollision = true;
        BB::Contact contact = broofhit ? BB::Contact::Net : brimhit ? BB::Contact::Goal : BB::Contact::None;
        abbridercharacter* struckrider = nullptr;
        abbridercharacter* savingkeeper = nullptr;
        if (bpenaltyflight)
        {
            for (abbridercharacter* rider : match->riders)
                if (isvalid(rider) && rider->rosterindex != match->penaltykeeperslot) Query.AddIgnoredActor(Rider);
            fcollisionobjectqueryparams keeperobjects; KeeperObjects.AddObjectTypesToQuery(ECC_Pawn);
            fhitresult keeperhit;
            if (getworld()->sweepsinglebyobjecttype(keeperhit, old, p, FQuat::Identity,
                keeperobjects, FCollisionShape::MakeSphere(R), query) && KeeperHit.Time <= hittime)
            {
                abbridercharacter* keeper = Cast<ABBRiderCharacter>(KeeperHit.GetActor());
                if (keeper && keeper->rosterindex == match->penaltykeeperslot)
                {
                    savingkeeper = keeper;
                    hittime = KeeperHit.Time;
                    hitnormal = KeeperHit.Normal;
                    bcollision = true;
                }
            }
        }
        if (isbludger() && impactcooldown <= 0 && FlightVelocity.SizeSquared() > FMath::Square(500.f))
        {
            if (throwerignoreremaining > 0 && RecentThrower.IsValid()) Query.AddIgnoredActor(RecentThrower.Get());
            fcollisionobjectqueryparams pawnobjects; PawnObjects.AddObjectTypesToQuery(ECC_Pawn);
            fhitresult riderhit;
            if (getworld()->sweepsinglebyobjecttype(riderhit, old, p, FQuat::Identity,
                pawnobjects, FCollisionShape::MakeSphere(R), query) && RiderHit.Time <= hittime)
            {
                if (abbridercharacter* rider = Cast<ABBRiderCharacter>(RiderHit.GetActor()))
                {
                    if (Match->Riders.Contains(Rider))
                    {
                        struckrider = rider;
                        hittime = RiderHit.Time;
                        hitnormal = RiderHit.Normal;
                        bcollision = true;
                    }
                }
            }
        }
        // compare whole-ball goal passage only with the unobstructed portion
        // before the earliest rim, net, world or keeper contact.
        const fvector travelend = FMath::Lerp(Old, p, hittime);
        if (!isbludger())
        {
            for (int32 side : {-1, 1})
            {
                const double plane = side * (BBArena::GoalPlaneX + r);
                if (Old.X * side < plane * side && TravelEnd.X * side >= plane * side)
                {
                    const double t = (plane - Old.X) / (TravelEnd.X - Old.X);
                    const fvector cross = FMath::Lerp(Old, travelend, t);
                    bool bgoal = false;
                    if (ballindex == 0)
                        for (double y : {-BBArena::HoopSpacing, 0.0, BBArena::HoopSpacing}) bgoal |= FVector2D(Cross.Y - y, Cross.Z - BBArena::LargeHoopHeight).SizeSquared() < FMath::Square(BBArena::LargeHoopRadius - r);
                    else bgoal = FVector2D(Cross.Y, Cross.Z - BBArena::SmallHoopHeight).SizeSquared() < FMath::Square(BBArena::SmallHoopRadius - r);
                    if (bgoal)
                    {
                        distancesincereleasecm += FVector::Distance(Old, cross);
                        setactorlocation(cross);
                        match->goal(this, side > 0 ? 0 : 1, (elapsed + remaining * hittime * t) / dt);
                        return;
                    }
                }
            }
        }
        const double contactfraction = (elapsed + remaining * hittime) / dt;
        if (savingkeeper)
        {
            setactorlocation(travelend);
            match->penaltyballstopped(this, text("saved by the netminder"), contactfraction);
            return;
        }
        if (bcollision)
        {
            p = travelend + hitnormal * .5f;
            if (struckrider)
            {
                contact = BB::Contact::Player;
                struckrider->concealremaining = 0.f;
                struckrider->stunremaining = FMath::Max(StruckRider->StunRemaining, 1.5f);
                struckrider->forcenetupdate();
                match->release(struckrider, FVector::ZeroVector);
                cooldown = impactcooldown = .7f;
                match->say(text("bludger impact - rider recovers in 1.5 seconds"));
            }
            else if (!broofhit && !brimhit)
            {
                const aactor* surface = WorldHit.GetActor();
                if (surface && (Surface->ActorHasTag(TEXT("BB.Goal.Rim")) || Surface->ActorHasTag(TEXT("BB.Support"))))
                    contact = BB::Contact::Goal;
                else if ((surface && Surface->ActorHasTag(TEXT("BB.Floor"))) || (HitNormal.Z > .5 && P.Z < r + 5.f))
                    contact = BB::Contact::Floor;
                else if ((surface && Surface->ActorHasTag(TEXT("BB.Net")))
                    || FMath::Abs(P.X) >= BBArena::HalfLength - r - 5.f || FMath::Abs(P.Y) >= BBArena::HalfWidth - r - 5.f)
                    contact = BB::Contact::Net;
            }
            if (broofhit && !struckrider)
            {
                ++roofcontactcount;
                lastroofnormal = -hitnormal;
                lastroofincoming = flightvelocity;
                BBArena::ReboundRoof(FlightVelocity, travelend, r, r);
                lastroofoutgoing = flightvelocity;
            }
            else
            {
                const double intosurface = FVector::DotProduct(FlightVelocity, hitnormal);
                if (intosurface < 0) flightvelocity = (flightvelocity - 2.0 * intosurface * hitnormal) * BBArena::Restitution;
            }
            forcenetupdate();
        }
        // lower walls and floor keep their existing fallback for incomplete
        // authored collision. the roof is already swept, never a respawn plane.
        if (FMath::Abs(P.X) > BBArena::HalfLength - r) { P.X = FMath::Sign(P.X) * (BBArena::HalfLength - r); FlightVelocity.X *= -.75f; contact = BB::Contact::Net; }
        if (FMath::Abs(P.Y) > BBArena::HalfWidth - r) { P.Y = FMath::Sign(P.Y) * (BBArena::HalfWidth - r); FlightVelocity.Y *= -.75f; contact = BB::Contact::Net; }
        if (P.Z < r) { P.Z = r; FlightVelocity.Z = FMath::Max(390.f, FMath::Abs(FlightVelocity.Z) * .75f); contact = BB::Contact::Floor; }
        p = BBArena::ClampSphere(P, r);
        distancesincereleasecm += FVector::Distance(Old, p);
        setactorlocation(p);
        if (bpenaltyflight && (contact == BB::Contact::Floor || contact == BB::Contact::Net
            || FMath::Abs(P.X) > BBArena::GoalPlaneX + r))
        {
            match->penaltyballstopped(this, broofhit ? text("penalty shot missed - roof net")
                : text("penalty shot missed"), contactfraction);
            return;
        }
        if (isbludger()) match->observebludgerflight(this, contact);
        if (!bcollision) break;
        const double consumed = remaining * hittime;
        elapsed += consumed;
        remaining -= consumed;
    }
}

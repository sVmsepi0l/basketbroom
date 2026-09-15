#include "BBMatchState.h"
#include "BBBall.h"
#include "BBAdmission.h"
#include "BBArenaGeometry.h"
#include "BBGameMode.h"
#include "BBRiderCharacter.h"
#include "BBSpellCatalog.h"
#include "BBSpellVisual.h"
#include "BBSpellArenaObject.h"
#include "CollisionQueryParams.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "Kismet/GameplayStatics.h"
#include "Net/UnrealNetwork.h"

namespace
{
constexpr int32 roles[8] = {0, 1, 1, 2, 3, 4, 4, 5};
fvector startlocation(int32 slot, bool bdonnybrook = false, float capsuleradius = 34.f)
{
    const int32 local = slot % 8;
    const float sign = slot < 8 ? -1.f : 1.f;
    // the whole capsule starts behind its own quarter line. donnybrook
    // instead lines every available rider up behind its own goal plane.
    const float clearance = capsuleradius + 12.f;
    if (bdonnybrook)
        return fvector(sign * (BBArena::GoalPlaneX + clearance),
            (local - 3.5f) * 650.f * BBArena::LinearScale,
            (1400.f + (local % 2) * 180.f) * BBArena::LinearScale);
    if (local == 0) return fvector(sign * (BBArena::GoalPlaneX - 1000.8), 0, BBArena::LargeHoopHeight);
    // provisional tactical spacing staggers the second row so teammates do not
    // obstruct the first-person view while waiting for the opening horn.
    const int32 row = (local - 1) / 3;
    return fvector(sign * (BBArena::GoalPlaneX / 2.0 + clearance + row * 650.f * BBArena::LinearScale),
                   (local == 7 ? 0.f : ((local - 1) % 3 - 1) * 950.f + (row == 1 ? 450.f : 0.f)) * BBArena::LinearScale,
                   (local == 7 ? 2800.f : 1400.f + (local % 3) * 350.f) * BBArena::LinearScale);
}

fvector openingballlocation(int32 index)
{
    // bible 5.2 supplies the lateral marks and snipe altitude. the 1500cm
    // scoring/Bludger launch altitude is a provisional implementation choice;
    // it is not a stated rule. snitch uses the 100ft center launch in section 6.
    const fvector marks[] = {fvector(0,0,1500), FVector(0,-1066.8,1500), FVector(0,1066.8,1500),
        FVector(0,0,670.56), fvector(0,0,3048), FVector(0,-2133.6,1500), FVector(0,2133.6,1500)};
    return Marks[FMath::Clamp(Index, 0, 6)];
}

fvector crownrestartlocation(const BB::Ball& ball)
{
    // a safe mark directly below the recorded exit. the 4m vertical clearance
    // and 3m edge clearance are provisional physical implementation margins.
    // the carry point projects 175cm ahead plus the scoring ball's 65cm radius.
    const double limitx = BBArena::HalfLength - 300.0, limity = BBArena::HalfWidth - 300.0;
    return BBArena::ClampSphere(FVector(
        FMath::Clamp(Ball.crown_mark[0] * 30.48, -limitx, limitx),
        FMath::Clamp(Ball.crown_mark[1] * 30.48, -limity, limity),
        FMath::Clamp(Ball.crown_mark[2] * 30.48 - 400.0, 250.0, BBArena::EaveHeight - 400.0)), 250.0);
}

void placerider(abbridercharacter* rider, const fvector& location, float yaw)
{
    rider->getcharactermovement()->stopmovementimmediately();
    rider->consumemovementinputvector();
    rider->setactorlocationandrotation(location, frotator(0, yaw, 0), false, nullptr, ETeleportType::TeleportPhysics);
    if (acontroller* controller = rider->getcontroller())
    {
        controller->setcontrolrotation(frotator(0, yaw, 0));
        if (aplayercontroller* player = cast<aplayercontroller>(controller))
            player->clientsetrotation(frotator(0, yaw, 0), true);
    }
    rider->forcenetupdate();
}

void clearcrownrestartspace(abbridercharacter* rider, const fvector& mark)
{
    const fvector previous = rider->getactorlocation();
    const float radius = rider->getcapsulecomponent()->getscaledcapsuleradius();
    const float halfheight = rider->getcapsulecomponent()->getscaledcapsulehalfheight();
    fvector direction = (previous - Mark).GetSafeNormal2D(UE_SMALL_NUMBER, FVector::ForwardVector);
    auto pointalong = [&mark, &previous](const fvector& along)
    { return FVector(Mark.X + Along.X * 450.0, Mark.Y + Along.Y * 450.0, Previous.Z); };
    auto inside = [radius, halfheight](const fvector& point)
    { return BBArena::ContainsCapsule(Point, radius, halfheight); };
    fvector destination = pointalong(direction);
    if (!inside(destination)) destination = pointalong(-direction);
    if (!inside(destination)) destination = PointAlong((-Mark).GetSafeNormal2D(UE_SMALL_NUMBER, FVector::ForwardVector));
    destination = BBArena::ClampCapsule(Destination, radius, halfheight);
    // preserve aim and altitude wherever roof clearance permits. clamping at
    // a sloped face can only lower the rider, never push a held ball outside.
    rider->getcharactermovement()->stopmovementimmediately();
    rider->consumemovementinputvector();
    rider->setactorlocation(destination, false, nullptr, ETeleportType::TeleportPhysics);
    rider->forcenetupdate();
}
}
ABBMatchState::ABBMatchState()
{
    PrimaryActorTick.bCanEverTick = true;
    SetNetUpdateFrequency(20.f);
    balwaysrelevant = true;
}
ABBMatchState::~ABBMatchState() = default;
void ABBMatchState::BeginPlay()
{
    Super::BeginPlay();
    if (!hasauthority()) return;
    bpractice = GetWorld()->URL.HasOption(TEXT("Practice"));
    bbloodbroom = GetWorld()->URL.HasOption(TEXT("Bloodbroom"));
    resetmatchrules();
    for (int32 i = 0; i < 7; ++i)
    {
        ftransform Transform(FRotator::ZeroRotator, openingballlocation(i));
        abbball* ball = GetWorld()->SpawnActorDeferred<ABBBall>(ABBBall::StaticClass(), transform, this, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (!ball)
        {
            ue_log(logtemp, error, text("basketbroom could not spawn ball %d; match startup aborted"), i);
            Rules.reset();
            say(text("match could not initialize its equipment."));
            return;
        }
        ball->ballindex = i;
        UGameplayStatics::FinishSpawningActor(Ball, transform);
        Balls.Add(Ball);
    }
    fillroster();
    syncrules();
    status = text("lobby");
}
void ABBMatchState::ResetMatchRules()
{
    if (!hasauthority()) return;
    BB::Config config;
    if (bpractice) { Config.quarter_ms = 180000; Config.snitch_release_ms = 60000; Config.overtime_ms = 120000; }
    rules = std::make_unique<BB::Match>(Config);
    if (!combat) combat = std::make_unique<BB::CombatPolicy>();
    combat->reset_match(bbloodbroom ? BB::CombatVariant::Bloodbroom : BB::CombatVariant::Regulation);
    combat->set_live(false);
    CombatOccupants.Empty(); combatphase = -1;
    conductfoulcount = 0; LastConductCall.Empty();
    bconductreviewpending = false; ConductReviewStatus.Empty();
    bmoderateadvantagearmed = bconductadvantagelive = false; ConductEvidence.Empty(); lastservedconductevidence = {};
    conductoffender = conductvictimteam = conductrestartball = -1;
    lastconductattack = 0; lastconductviolations = 0;
    conductball = conductvictimslot = -1;
    resetpenaltypresentation();
    rules->pause("pregame selection");
    millisecondcarry = 0;
    botaccumulator = reviewdelay = 0;
    lastlogindex = 0;
    PendingPoints.clear();
    binitialized = false;
    blive = false;
    resetcontextualspells();
    for (abbridercharacter* r : riders)
        if (isvalid(r))
        {
            r->resetsportspellstate();
        }
}
void ABBMatchState::ResetOpeningLayout()
{
    if (!hasauthority() || !rules) return;
    const bool bdonnybrook = rules->phase == BB::Phase::Donnybrook;
    for (abbridercharacter* r : riders)
    {
        if (!isvalid(r) || r->rosterindex < 0 || r->rosterindex >= 16) continue;
        const auto& player = rules->players[r->rosterindex];
        if (Player.ejected || Player.donnybrook_excluded || Player.removed_until >= 0) continue;
        r->binteractheld = false;
        placerider(r, startlocation(r->rosterindex, bdonnybrook, r->getcapsulecomponent()->getscaledcapsuleradius()),
                   r->teamindex ? 180.f : 0.f);
    }
    for (abbball* b : balls)
    {
        if (!isvalid(b)) continue;
        // a delayed crown award takes priority over the neutral period layout.
        if (Rules->balls[B->BallIndex].crown_restart_penalty > 0
            || Rules->balls[B->BallIndex].conduct_restart_penalty > 0) continue;
        b->home = openingballlocation(b->ballindex);
        b->lasttouchteam = -1;
        b->chasetime = b->ballindex * 2.4f;
        b->resetball(b->home);
    }
}
void ABBMatchState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& outlifetimeprops) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    doreplifetime(abbmatchstate, tealscore); doreplifetime(abbmatchstate, copperscore);
    doreplifetime(abbmatchstate, quarter); doreplifetime(abbmatchstate, secondsleft);
    doreplifetime(abbmatchstate, phase); doreplifetime(abbmatchstate, status);
    doreplifetime(abbmatchstate, announcement); doreplifetime(abbmatchstate, bpractice);
    doreplifetime(abbmatchstate, blive); doreplifetime(abbmatchstate, winner);
    doreplifetime(abbmatchstate, liveseconds);
    doreplifetime(abbmatchstate, pendingpenaltycount); doreplifetime(abbmatchstate, pendingpenaltysummary);
    doreplifetime(abbmatchstate, bbloodbroom); doreplifetime(abbmatchstate, conductfoulcount);
    doreplifetime(abbmatchstate, lastconductcall); doreplifetime(abbmatchstate, bconductreviewpending);
    doreplifetime(abbmatchstate, conductreviewstatus);
    doreplifetime(abbmatchstate, bmoderateadvantagearmed); doreplifetime(abbmatchstate, bconductadvantagelive);
    doreplifetime(abbmatchstate, bpenaltyshotactive);
    doreplifetime(abbmatchstate, bfreeshot); doreplifetime(abbmatchstate, bpenaltyshotreleased);
    doreplifetime(abbmatchstate, penaltyshotsecondsleft); doreplifetime(abbmatchstate, penaltyshotball);
    doreplifetime(abbmatchstate, penaltyshooterslot); doreplifetime(abbmatchstate, penaltykeeperslot);
    doreplifetime(abbmatchstate, penaltyshotstatus);
}
fstring ABBMatchState::PositionName(int32 position)
{
    const tchar* names[] = {text("netminder"), text("chaser"), text("trapper"), text("ranger"), text("hurleyback"), text("scout")};
    return Names[FMath::Clamp(Position, 0, 5)];
}
void ABBMatchState::Say(const fstring& text) { announcement = text; forcenetupdate(); }
void ABBMatchState::AssignHuman(ABBRiderCharacter* rider)
{
    if (!hasauthority() || !isvalid(rider)) return;
    Riders.RemoveAll([](const abbridercharacter* r) { return !isvalid(r); });
    if (Riders.Contains(Rider) && rider->rosterindex >= 0 && rider->rosterindex < 16) return;
    int32 counts[2] = {0, 0};
    std::array<bool, 16> occupied{};
    for (abbridercharacter* r : riders)
    {
        if (!isvalid(r) || r == rider || r->rosterindex < 0 || r->rosterindex >= 16) continue;
        const bool bhuman = r->isplayercontrolled();
        if (bhuman) ++Counts[FMath::Clamp(R->TeamIndex,0,1)];
        occupied[r->rosterindex] = occupied[r->rosterindex] || bhuman || r->hasspellmovementlock();
    }
    for (const fconductevidence& evidence : conductevidence)
        if (Evidence.Offender >= 0 && Evidence.Offender < 16) Occupied[Evidence.Offender] = true;
    if (bpenaltyshotactive)
    {
        if (penaltyshooterslot >= 0 && penaltyshooterslot < 16) occupied[penaltyshooterslot] = true;
        if (penaltykeeperslot >= 0 && penaltykeeperslot < 16) occupied[penaltykeeperslot] = true;
    }
    const int32 team = counts[0] <= counts[1] ? 0 : 1;
    // the first local login can precede GameState::BeginPlay. there cannot be
    // historical penalties yet; use the clean default roster for that one path.
    const BB::Match initialrules;
    const BB::Match* admissionrules = rules ? Rules.get() : (hasactorbegunplay() ? nullptr : &initialrules);
    const int32 slot = admissionrules ? BB::SelectAdmissionSlot(*AdmissionRules, occupied, team) : index_none;
    if (slot == index_none)
    {
        if (aplayercontroller* player = cast<aplayercontroller>(rider->getcontroller()))
        {
            player->startspectatingonly();
            Player->ClientMessage(TEXT("Spectating: no unrestricted player position is available. rejoin after a position clears or the next match starts."));
        }
        ue_log(logtemp, display, text("basketbroom newcomer is spectating: no unrestricted roster slot is available."));
        Riders.Remove(Rider);
        rider->destroy();
        return;
    }
    for (int32 i = Riders.Num() - 1; i >= 0; --i)
    {
        abbridercharacter* old = riders[i];
        if (isvalid(old) && old != rider && old->rosterindex == slot)
        {
            release(old, FVector::ZeroVector);
            Riders.RemoveAt(I);
            old->destroy();
        }
    }
    rider->rosterindex = slot; rider->teamindex = slot / 8; rider->position = roles[slot % 8];
    Riders.AddUnique(Rider);
    placerider(rider, startlocation(slot), slot < 8 ? 0.f : 180.f);
}
void ABBMatchState::FillRoster()
{
    if (!hasauthority()) return;
    Riders.RemoveAll([](const abbridercharacter* r) { return !isvalid(r); });
    for (int32 i = 0; i < 16; ++i)
    {
        bool found = false;
        for (abbridercharacter* r : riders) found |= r->rosterindex == i;
        if (found) continue;
        factorspawnparameters params; Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        abbridercharacter* r = getworld()->spawnactor<abbridercharacter>(startlocation(i), frotator(0,i < 8 ? 0:180,0), params);
        if (!r) { ue_log(logtemp, error, text("could not fill roster slot %d"), i); continue; }
        r->teamindex = i / 8; r->rosterindex = i; r->position = roles[i % 8];
        r->getcharactermovement()->brunphysicswithnocontroller = true;
        Riders.Add(R);
    }
}
bool ABBMatchState::CanInteract(const abbridercharacter* r, const abbball* b) const
{
    if (!hasauthority() || !rules || !blive || !isvalid(r) || !isvalid(b) || !Riders.Contains(R) || !Balls.Contains(B)
        || !b->bactive || b->ballindex < 0 || b->ballindex >= 7 || !Rules->balls[B->BallIndex].live
        || r->hasspellmovementlock() || r->rosterindex < 0 || r->rosterindex >= 16) return false;
    if (!rules->eligible(r->rosterindex, b->ballindex)) return false;
    const ucapsulecomponent* capsule = r->getcapsulecomponent();
    if (!BBArena::ContainsCapsule(R->GetActorLocation(), capsule->getscaledcapsuleradius(),
                                capsule->getscaledcapsulehalfheight())
        || !BBArena::ContainsSphere(B->GetActorLocation(), b->radius())) return false;
    for (const abbball* other : balls) if (isvalid(other) && other->holder == r && other != b) return false;
    fcollisionqueryparams query(scene_query_stat(basketbroominteraction), false, r);
    Query.AddIgnoredActor(B);
    for (abbspellarenaobject* object : spellworkshops) if (isvalid(object)) Query.AddIgnoredActor(Object);
    fhitresult hit;
    if (getworld()->linetracesinglebychannel(hit, r->getactorlocation(), b->getactorlocation(), ecc_visibility, query)) return false;
    return true;
}
bool ABBMatchState::TryPossess(ABBRiderCharacter* r, abbball* b)
{
    if (!caninteract(r,b) || b->ischase() || b->holder || b->cooldown > 0 || FVector::DistSquared(R->GetActorLocation(),B->GetActorLocation()) > FMath::Square(425.f)) return false;
    if (!rules->possess(r->rosterindex, b->ballindex, b->isbludger())) return false;
    b->holder = r; b->lasttouchteam = r->teamindex; b->flightvelocity = FVector::ZeroVector;
    b->distancesincereleasecm = 0;
    B->RecentThrower.Reset();
    b->throwerignoreremaining = b->impactcooldown = 0;
    b->forcenetupdate();
    return true;
}
bool ABBMatchState::TryCatch(ABBRiderCharacter* r, abbball* b)
{
    if (!caninteract(r,b) || !b->ischase() || b->capturingrider != r || !r->binteractheld || b->captureprogress < 1.f || FVector::DistSquared(R->GetActorLocation(),B->GetActorLocation()) > FMath::Square(380.f)) return false;
    for (const auto& p : pendingpoints) if (P.ball == b->ballindex || P.player == r->rosterindex) return false;
    BB::PointEvent event; Event.kind = BB::EventKind::Catch; Event.ball = b->ballindex; Event.player = r->rosterindex;
    Event.secure_ms = Rules->config.catch_control_ms; Event.by_hand = true; Event.mounted = true;
    const fvector p = r->getactorlocation();
    const ucapsulecomponent* capsule = r->getcapsulecomponent();
    Event.inside_envelope = BBArena::ContainsCapsule(P, capsule->getscaledcapsuleradius(), capsule->getscaledcapsulehalfheight())
        && BBArena::ContainsSphere(B->GetActorLocation(), b->radius());
    if (!Event.inside_envelope) return false;
    PendingPoints.push_back(Event);
    return true;
}
void ABBMatchState::Goal(ABBBall* b, int32 team, double flightstepfraction)
{
    if (hasauthority() && bpenaltyshotactive)
    {
        if (!ispenaltyballactive(b) || !bpenaltyshotreleased || !rules
            || !consumepenaltyflighttime(flightstepfraction)) return;
        BB::PointEvent event; Event.ball = b->ballindex; Event.attacking_team = team;
        Event.player = penaltyshooterslot; Event.hoop = b->ballindex == 0 ? BB::Hoop::Large : BB::Hoop::Small;
        Event.entire_ball = true; Event.forward = true;
        if (team == Rules->penalty_shot.attacking_team)
            FinishPenaltyShot(BB::PenaltyShotOutcome::Goal, text("penalty shot scored"), event);
        else FinishPenaltyShot(BB::PenaltyShotOutcome::Miss, text("penalty shot missed - wrong goal"));
        return;
    }
    if (!hasauthority() || !rules || !blive || !isvalid(b) || !Balls.Contains(B) || team < 0 || team > 1
        || b->ballindex < 0 || b->ballindex > 2 || !Rules->balls[B->BallIndex].live || b->holder || !b->bactive) return;
    for (const auto& p : pendingpoints) if (P.ball == b->ballindex) return;
    BB::PointEvent event; Event.ball = b->ballindex; Event.attacking_team = team;
    Event.hoop = b->ballindex == 0 ? BB::Hoop::Large : BB::Hoop::Small;
    Event.entire_ball = true; Event.forward = true;
    PendingPoints.push_back(Event);
    b->flightvelocity = FVector::ZeroVector; b->cooldown = .25f;
}
void ABBMatchState::Release(ABBRiderCharacter* r, fvector aim, bool bdeferconductboundary)
{
    if (bpenaltyshotactive) { releasepenaltyshot(r, aim); return; }
    if (!hasauthority() || !rules || !isvalid(r) || Aim.ContainsNaN()) return;
    for (abbball* b : balls)
    {
        if (b->holder != r) continue;
        if (!rules->release(r->rosterindex, b->ballindex, true)) continue;
        b->holder = nullptr;
        b->lastlocation = r->getcarrylocation();
        b->setactorlocation(b->lastlocation);
        b->flightvelocity = Aim.IsNearlyZero() ? r->getvelocity() : Aim.GetSafeNormal() * (b->isbludger() ? 5000.f : 4400.f) + r->getvelocity() * .4f;
        b->distancesincereleasecm = 0;
        // a forced zero-aim drop is not a deliberate propulsive act.
        b->recentthrower = Aim.IsNearlyZero() ? nullptr : r;
        b->throwerignoreremaining = .15f;
        b->impactcooldown = 0;
        b->cooldown = .3f;
        b->forcenetupdate();
    }
    if (!bdeferconductboundary) tickconductadvantage();
}
void ABBMatchState::ReleaseDepartedSlot(int32 rosterindex)
{
    if (!hasauthority() || !rules || rosterindex < 0 || rosterindex >= 16) return;
    Riders.RemoveAll([](const abbridercharacter* r) { return !isvalid(r); });
    for (abbball* b : balls)
    {
        if (!isvalid(b) || b->ballindex < 0 || b->ballindex >= 7
            || Rules->balls[B->BallIndex].controller != rosterindex) continue;
        if (!rules->release(rosterindex, b->ballindex, true)) continue;
        // the last authoritative ball transform is safe even after its former
        // rider has been destroyed. this is a neutral drop, not a new throw.
        b->holder = nullptr;
        b->flightvelocity = FVector::ZeroVector;
        b->distancesincereleasecm = 0;
        b->recentthrower = nullptr;
        b->throwerignoreremaining = 0;
        b->impactcooldown = 0;
        b->cooldown = .3f;
        b->forcenetupdate();
    }
    tickconductadvantage(); syncrules();
}
void ABBMatchState::ObserveBludgerFlight(ABBBall* b, BB::Contact contact)
{
    if (!hasauthority() || !rules || !blive || !isvalid(b) || !Balls.Contains(B)
        || !b->isbludger() || b->ballindex > 6 || b->holder) return;
    const auto& state = rules->balls[b->ballindex];
    const auto& hurley = rules->hurleys[b->ballindex - 5];
    if (!State.live || State.controller >= 0 || Hurley.individual_reset) return;
    const double distancefeet = b->distancesincereleasecm / 30.48;
    if (contact == BB::Contact::None && distancefeet < Rules->config.self_toss_reset_distance_ft) return;
    // contestability is established by the existing legal release policy.
    // merely observing an arena collision must not invent that evidence.
    rules->flight_evidence(b->ballindex, distancefeet, contact, Hurley.contestable);
}
double ABBMatchState::DevelopmentGetBludgerControlSeconds(int32 ballindex) const
{
#if ue_build_shipping
    return -1;
#else
    if (!hasauthority() || !getworld() || getworld()->worldtype != EWorldType::PIE
        || !rules || ballindex < 5 || ballindex > 6 || Rules->balls[BallIndex].controller < 0) return -1;
    const auto& hurley = rules->hurleys[ballindex - 5];
    return Hurley.individual_started < 0 ? -1 : (rules->now_ms - Hurley.individual_started) / 1000.0;
#endif
}
tarray<int32> ABBMatchState::DevelopmentGetCrownPenaltyState(int32 ballindex) const
{
    tarray<int32> state = {0, 0, 0, -1, -1, -1};
#if !ue_build_shipping
    if (hasauthority() && getworld() && getworld()->worldtype == EWorldType::PIE && rules)
        for (const auto& penalty : rules->penalties)
            if (Penalty.reason == "no crown" && Penalty.ball == ballindex)
            {
                ++state[0]; state[1] += Penalty.pending ? 1 : 0;
                state[2] += Penalty.crown_restoration_pending ? 1 : 0;
                state[3] = Penalty.player; state[4] = Penalty.crown_restoration_receiver;
                state[5] = Penalty.id;
            }
#endif
    return state;
}
void ABBMatchState::ChangePosition(ABBRiderCharacter* r, int32 newposition, int32 newteam)
{
    if (!hasauthority() || !rules || !isvalid(r) || newposition < 0 || newposition > 5 || newteam < 0 || newteam > 1) return;
    if (blive) { say(text("positions are locked during live play. choose at the next stoppage.")); return; }
    if (bpenaltyshotactive) { say(text("finish the shot before changing positions.")); return; }
    if (bconductreviewpending) { say(text("resolve the bb-0 conduct call before changing positions.")); return; }
    if (rules->status == BB::Status::Review || rules->status == BB::Status::Complete) return;
    if (r->position == newposition && r->teamindex == newteam) return;
    const auto& currentplayer = rules->players[r->rosterindex];
    auto haspendingpenalty = [this](int32 slot)
    {
        for (const auto& penalty : rules->penalties)
            if (Penalty.player == slot && (Penalty.pending || Penalty.crown_restoration_pending)) return true;
        return false;
    };
    if (CurrentPlayer.ejected || CurrentPlayer.donnybrook_excluded || CurrentPlayer.removed_until >= 0)
    { say(text("a removed player cannot change position to bypass a penalty.")); return; }
    if (haspendingpenalty(r->rosterindex)) { say(text("resolve the pending penalty before changing positions.")); return; }
    abbridercharacter* swap = nullptr;
    for (abbridercharacter* other : riders)
        if (isvalid(other) && other != r && other->teamindex == newteam && other->position == newposition && !other->isplayercontrolled()
            && !Rules->players[Other->RosterIndex].ejected && !Rules->players[Other->RosterIndex].donnybrook_excluded
            && Rules->players[Other->RosterIndex].removed_until < 0 && !haspendingpenalty(other->rosterindex)) { swap = other; break; }
    if (!swap) { say(text("that position is occupied or currently restricted.")); return; }
    const int32 oldindex = r->rosterindex;
    r->rosterindex = swap->rosterindex; swap->rosterindex = oldindex;
    for (abbridercharacter* changed : {r, swap})
    {
        changed->teamindex = changed->rosterindex / 8;
        changed->position = roles[changed->rosterindex % 8];
        changed->binteractheld = false;
        placerider(changed, startlocation(changed->rosterindex), changed->teamindex ? 180.f : 0.f);
        if (abbgamemode* gamemode = getworld()->getauthgamemode<abbgamemode>())
            gamemode->trackassignedrider(changed);
    }
    Say(FString::Printf(TEXT("%s selected %s. enter resumes play."), r->teamindex ? text("copper") : text("teal"), *positionname(r->position)));
}
void ABBMatchState::HandleAction(ABBRiderCharacter* r, int32 action, int32 value, fvector aim)
{
    if (!hasauthority() || !rules || !isvalid(r) || !Riders.Contains(R) || r->rosterindex < 0 || r->rosterindex >= 16) return;
    if (bpenaltyshotactive)
    {
        if (action == 1) releasepenaltyshot(r, aim);
        else R->NotifySpellResult(TEXT("Shot: designated shooter throws once; no wandwork, pass or role change."));
        return;
    }
    if (action == 2) { changeposition(r, value, r->teamindex); return; }
    if (action == 3) { changeposition(r, r->position, value); return; }
    if (action == 8)
    {
        if (canofficiate(r) && !binitialized && status == text("lobby"))
        {
            bbloodbroom = !bbloodbroom;
            combat->reset_match(bbloodbroom ? BB::CombatVariant::Bloodbroom : BB::CombatVariant::Regulation);
            combat->set_live(false);
            say(bbloodbroom ? text("bloodbroom - unforgivables and headshots permitted. other bb-0 rules apply.")
                           : text("bb-0 - no unforgivables, headshots, mobbing, double-taps or holding."));
        }
        return;
    }
    if (action == 13)
    {
        if (!canofficiate(r) || bconductreviewpending || bpenaltyshotactive
            || rules->status == BB::Status::Review || rules->status == BB::Status::Complete) return;
        bmoderateadvantagearmed = !bmoderateadvantagearmed;
        say(bmoderateadvantagearmed
            ? TEXT("REFEREE: next basic-cast mobbing may use moderate advantage only if the victim keeps scoring possession without a disable. other fouls stop immediately.")
            : TEXT("REFEREE: moderate advantage preselection off."));
        forcenetupdate(); return;
    }
    if (action >= 9 && action <= 12) { reviewconduct(r, action); return; }
    if (action == 4 || action == 5)
    {
        // listen-server period control belongs to the host. a dedicated server
        // delegates it to the first connected participant below.
        if (!canofficiate(r)) return;
        if (bconductreviewpending)
        {
            if (bconductadvantagelive && action == 5)
            {
                rules->pause("host ended moderate advantage"); tickconductadvantage(); syncrules(); return;
            }
            r->notifyspellresult(text("resolve BB-0: f6 free shot, f7 possession, f8 shot + removal, f9 ejection."));
            return;
        }
        const bool brematch = rules->status == BB::Status::Complete && action == 4;
        if (brematch)
        {
            resetmatchrules();
            fillroster();
        }
        else if (rules->status == BB::Status::Complete) return;
        if (action == 5)
        {
            // finish already observed goals/catches before stopping the clock.
            if (!PendingPoints.empty())
            {
                rules->process_batch(rules->now_ms, pendingpoints);
                PendingPoints.clear();
            }
            if (rules->pause("host requested official stoppage"))
                say(text("official stoppage - choose positions with 1-6. Host: enter to resume."));
            syncrules();
            return;
        }
        const bool bopening = !binitialized || rules->status == BB::Status::QuarterBreak || rules->status == BB::Status::PhaseBreak;
        if (!blive && rules->status != BB::Status::Review && rules->resume())
        {
            if (bopening) resetopeninglayout();
            binitialized = true;
            syncrules();
            say(brematch ? text("rematch live - new regulation match. teams and positions retained.")
                         : text("live - play your position. hold e within 3.8m to secure a chase ball."));
        }
        return;
    }
    if (!blive || r->hasspellmovementlock()) return;
    if (action == 6 || action == 7) { castspell(r, action == 7 ? 1 : value, aim); return; }
    if (action == 0)
    {
        abbball* nearest = nullptr; float distance = FMath::Square(425.f);
        for (abbball* b : balls)
        {
            const float d = FVector::DistSquared(R->GetActorLocation(), b->getactorlocation());
            if (!b->ischase() && !b->holder && caninteract(r,b) && d < distance) { nearest = b; distance = d; }
        }
        if (nearest) trypossess(r,nearest);
    }
    if (action == 1 && !Aim.ContainsNaN() && Aim.IsNormalized()) release(r,aim);
}
void ABBMatchState::Tick(float dt)
{
    Super::Tick(Dt);
    if (!hasauthority() || !rules) return;
    if (bpenaltyshotactive) { tickpenaltyshot(dt); return; }
    if (!PendingPoints.empty())
    {
        if (rules->process_batch(rules->now_ms, pendingpoints))
        {
            for (const auto& award : rules->last_awards) Say(FString::Printf(TEXT("%s +%lld  |  %s"), Award.team == 0 ? text("teal") : text("copper"), static_cast<long long>(Award.points), *Balls[Award.ball]->DisplayName()));
        }
        else ue_log(logtemp, warning, text("basketbroom point batch rejected: %s"), UTF8_TO_TCHAR(Rules->last_error.c_str()));
        PendingPoints.clear();
    }
    tickconductadvantage();
    if (rules->status == BB::Status::Live)
    {
        millisecondcarry += FMath::Max(0.f, dt) * 1000.0;
        const BB::Millis whole = static_cast<BB::Millis>(MillisecondCarry);
        millisecondcarry -= whole;
        const BB::Millis consumed = rules->advance(whole);
        if (consumed > 0)
        {
            combat->advance(consumed);
            tickspells(consumed / 1000.f);
        }
        for (int32 i=0; i<7; ++i)
        {
            auto& state = rules->balls[i];
            abbball* b = balls[i];
            if (State.dead_reason == "crown" && State.crown_deadline - rules->now_ms <= 2000) { rules->crown_return(i); b->flightvelocity = fvector(0,0,-100); }
            if (State.dead_reason == "score" || State.dead_reason == "hurley_foul" || State.dead_reason == "penalty" || State.dead_reason == "crown_restart")
            {
                const bool bcrownrestart = State.dead_reason == "crown_restart";
                const fvector searchmark = i == conductrestartball ? conductmark : bcrownrestart ? crownrestartlocation(state) : b->getactorlocation();
                abbridercharacter* receiver = nullptr;
                double nearestdistance = TNumericLimits<double>::Max();
                for (abbridercharacter* r : riders)
                {
                    if (!isvalid(r) || r->teamindex != State.restart_team) continue;
                    if (i < 3 && !bcrownrestart && i != conductrestartball)
                    {
                        if (r->position == 0 && !r->hasspellmovementlock() && rules->eligible(r->rosterindex, i)) { receiver = r; break; }
                        continue;
                    }
                    if (r->hasspellmovementlock() || !rules->eligible(r->rosterindex, i)) continue;
                    bool balreadyholding = false;
                    for (const abbball* other : balls)
                        if (isvalid(other) && other != b && other->holder == r) { balreadyholding = true; break; }
                    if (balreadyholding) continue;
                    const double distance = FVector::DistSquared(R->GetActorLocation(), searchmark);
                    if (distance < nearestdistance || (distance == nearestdistance
                        && receiver && r->rosterindex < receiver->rosterindex))
                    {
                        receiver = r;
                        nearestdistance = distance;
                    }
                }
                if (receiver && rules->restart(i,receiver->rosterindex))
                {
                    const bool bconductrestart = i == conductrestartball;
                    const fvector mark = bconductrestart ? conductmark : bcrownrestart ? searchmark : fvector((receiver->teamindex == 0 ? -1.f : 1.f) * (BBArena::GoalPlaneX - BBArena::RestartDistance), 0, i == 0 ? BBArena::LargeHoopHeight : BBArena::SmallHoopHeight);
                    placerider(receiver, mark, receiver->teamindex ? 180.f : 0.f);
                    b->resetball(mark + fvector(0,0,80));
                    for (abbridercharacter* other : riders)
                        if (other->teamindex != receiver->teamindex && FVector::DistSquared(Other->GetActorLocation(),Mark) < FMath::Square(396.24f))
                        {
                            if (bcrownrestart || bconductrestart) clearcrownrestartspace(other, mark);
                            else placerider(other, mark + (Other->GetActorLocation()-Mark).GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector) * 450.f, Other->GetActorRotation().Yaw);
                        }
                    if (bconductrestart) conductrestartball = -1;
                }
            }
        }
    }
    // the rules engine explicitly requires a stoppage for administration.
    // resolve before certification/resume, including penalties that caused it.
    if (rules->status != BB::Status::Live)
        for (auto& penalty : rules->penalties)
            if (Penalty.reason == "no crown" && Penalty.crown_restoration_pending)
            {
                if (Rules->prepare_crown_restart(Penalty.id)
                    && Rules->balls[Penalty.ball].crown_restart_penalty == Penalty.id)
                    Balls[Penalty.ball]->ResetBall(CrownRestartLocation(Rules->balls[Penalty.ball]) + fvector(0,0,80));
            }
            else if (Penalty.pending && !IsUnreviewedConductPenalty(Penalty.id) && Penalty.severity != BB::Severity::Catastrophic
                && Penalty.severity != BB::Severity::Serious)
            {
                bool bqueuedconductaward = false;
                for (const auto& ball : rules->balls) bqueuedconductaward |= Ball.conduct_restart_penalty == Penalty.id;
                if (!bqueuedconductaward) Rules->resolve_penalty(Penalty.id,"automatic rules enforcement",true);
            }
    if (rules->status == BB::Status::Review && !bconductreviewpending)
    {
        reviewdelay += dt;
        if (reviewdelay >= 2.f) { rules->certify(); reviewdelay = 0; }
    }
    syncrules();
    if (blive) updatebots(dt);
    else for (abbridercharacter* r : riders)
        if (isvalid(r) && !r->isplayercontrolled())
        {
            r->binteractheld = false;
            r->consumemovementinputvector();
            r->getcharactermovement()->stopmovementimmediately();
        }
}
void ABBMatchState::SyncRules()
{
    if (!rules) return;
    tealscore = static_cast<int32>(rules->scores[0]); copperscore = static_cast<int32>(rules->scores[1]);
    const bool bwaslive = blive;
    quarter = rules->quarter; winner = rules->winner; blive = rules->status == BB::Status::Live;
    synccombatroster();
    if (bwaslive && !blive)
        for (abbball* b : balls) if (isvalid(b)) B->RecentThrower.Reset();
    pendingpenaltycount = 0; PendingPenaltySummary.Empty();
    for (const auto& penalty : rules->penalties)
        if (Penalty.pending || Penalty.crown_restoration_pending)
        {
            ++pendingpenaltycount;
            if (PendingPenaltySummary.IsEmpty())
            {
                const int32 team = Rules->players[Penalty.player].team;
                pendingpenaltysummary = FString::Printf(TEXT("%s | %s %s | %s"),
                    UTF8_TO_TCHAR(Penalty.reason.c_str()), team == 0 ? text("teal") : text("copper"),
                    *PositionName(static_cast<int32>(Rules->players[Penalty.player].role)),
                    Penalty.pending ? text("pending stoppage") : text("restart due"));
            }
        }
    liveseconds = rules->now_ms / 1000.f;
    phase = rules->phase == BB::Phase::Regulation ? text("regulation") : rules->phase == BB::Phase::Overtime ? text("overtime") : text("donnybrook");
    secondsleft = rules->phase == BB::Phase::Donnybrook ? 0.f : FMath::Max(0.f, (rules->phase == BB::Phase::Regulation ? Rules->config.quarter_ms : Rules->config.overtime_ms) / 1000.f - rules->period_elapsed_ms / 1000.f);
    const tchar* labels[] = {text("live"),text("stoppage"),text("quarter break"),text("phase break"),text("certifying result"),text("final")};
    status = binitialized ? labels[static_cast<int>(rules->status)] : text("lobby");
    for (int32 i=0; I<Balls.Num(); ++i)
    {
        abbball* b = balls[i]; const auto& s = rules->balls[i];
        const bool wasactive = b->bactive;
        // at stoppages, keep active equipment visible for orientation.
        b->bactive = S.phase_active && (S.live || S.dead_reason == "stoppage"
            || (bpenaltyshotactive && i == penaltyshotball));
        b->returnin = FMath::Max(0.f, S.timeout_until >= 0 ? (S.timeout_until-Rules->now_ms)/1000.f : S.dead_reason == "scheduled_release" ? (Rules->config.snitch_release_ms-Rules->now_ms)/1000.f : 0.f);
        b->ballstatus = UTF8_TO_TCHAR(S.dead_reason.c_str());
        b->holder = nullptr;
        for (abbridercharacter* r : riders) if (r->rosterindex == S.controller) b->holder = r;
        if (wasactive != b->bactive)
        {
            if (b->bactive && b->ischase()) b->resetball(b->home);
            b->onrep_appearance(); b->forcenetupdate();
        }
    }
    for (abbridercharacter* r : riders)
    {
        if (!isvalid(r) || r->rosterindex < 0 || r->rosterindex >= 16) continue;
        const auto& p = rules->players[r->rosterindex];
        if (P.ejected || P.donnybrook_excluded || P.removed_until >= 0)
        {
            r->stunremaining = 1.f;
            const fvector penaltybox((r->teamindex == 0 ? -1.0 : 1.0) * (BBArena::HalfLength + 349.2), 0, 600);
            if (FVector::DistSquared(R->GetActorLocation(), penaltybox) > 2500.f)
                placerider(r, penaltybox, r->teamindex ? 180.f : 0.f);
        }
    }
    while (lastlogindex < Rules->log.size())
    {
        const auto& log = rules->log[lastlogindex++];
        if (Log.kind == "quarter_horn" || Log.kind == "stoppage" || Log.kind == "phase_transition") say(text("stoppage - change positions with 1-6. host presses enter to resume."));
        if (Log.kind == "snipe_warning") say(text("snipe returns in 10 seconds"));
        if (Log.kind == "snitch_release") say(text("the golden snitch is live - rangers and scouts may capture"));
        if (Log.kind == "hurley_warning") say(text("hurley warning - release before 3 seconds"));
        if (Log.kind == "removal_expired")
            for (abbridercharacter* r : riders)
                if (isvalid(r) && r->rosterindex == Log.player)
                {
                    r->stunremaining = 0.f;
                    placerider(r, startlocation(r->rosterindex), r->teamindex ? 180.f : 0.f);
                }
    }
    if (winner >= 0)
    {
        const fstring result = FString::Printf(TEXT("%s wins  |  %d - %d  |  result certified"), winner == 0 ? text("teal") : text("copper"), tealscore, copperscore);
        if (announcement != result) say(result);
    }
}
void ABBMatchState::UpdateBots(float dt)
{
    for (abbridercharacter* r : riders)
    {
        if (!blive) return;
        if (!isvalid(r) || r->isplayercontrolled() || r->hasspellmovementlock()) continue;
        abbball* held = nullptr; for (abbball* b : balls) if (b->holder == r) held = b;
        fvector target = startlocation(r->rosterindex);
        r->binteractheld = false;
        if (held)
        {
            float sign = r->teamindex == 0 ? 1.f : -1.f;
            fvector goalmark(sign * (BBArena::GoalPlaneX + 99.2),
                held->ballindex == 0 ? ((r->rosterindex % 3)-1) * BBArena::HoopSpacing : 0.0,
                held->ballindex == 0 ? BBArena::LargeHoopHeight : BBArena::SmallHoopHeight);
            target = goalmark - fvector(sign * 2100.f,0,0);
            if (held->isbludger())
            {
                for (abbridercharacter* enemy : riders) if (enemy->teamindex != r->teamindex && !enemy->isconcealedfrom(r)) { goalmark = enemy->getactorlocation(); break; }
                Release(R,(GoalMark-R->GetCarryLocation()).GetSafeNormal());
            }
            else if (r->position == 0 || FVector::DistSquared(R->GetActorLocation(), target) < FMath::Square(500.f))
            {
                const auto& ballrule = rules->balls[held->ballindex];
                if (BallRule.protection_until < 0 || rules->now_ms >= BallRule.protection_until)
                {
                    if (r->position == 0) goalmark = BBArena::ScaleLayout(FVector(Sign * 1000, (r->rosterindex % 2 ? 900 : -900), 1800));
                    fvector to = goalmark - r->getcarrylocation(); const float flight = To.Size()/4400.f;
                    To.Z += .5f * 380.f * flight * flight;
                    Release(R,To.GetSafeNormal());
                }
            }
        }
        else
        {
            abbball* best = nullptr; float bestdist = TNumericLimits<float>::Max();
            for (abbball* b : balls)
            {
                if (!b->bactive || b->holder || !caninteract(r,b)) continue;
                if (b->ballindex == 4)
                {
                    // give the release announcement time to be actionable and
                    // avoid a cpu catch that would knowingly concede the match.
                    if (rules->phase == BB::Phase::Regulation && rules->now_ms < Rules->config.snitch_release_ms + 10000) continue;
                    const auto catchpoints = rules->phase == BB::Phase::Regulation ? Rules->config.snitch_regulation_points : Rules->config.snitch_overtime_points;
                    if (rules->scores[r->teamindex] + catchpoints < rules->scores[1 - r->teamindex]) continue;
                }
                const float d = FVector::DistSquared(B->GetActorLocation(),R->GetActorLocation());
                // netminder guards its own end; other scoring positions share assignments.
                if (r->position == 0 && FMath::Abs(B->GetActorLocation().X - Target.X) > 1700) continue;
                if (d < bestdist) { best = b; bestdist = d; }
            }
            if (best)
            {
                target = best->getactorlocation();
                if (best->ischase()) r->binteractheld = true;
                else trypossess(r,best);
            }
        }
        fvector to = target - r->getactorlocation();
        if (To.Size() > 120) R->AddMovementInput(To.GetSafeNormal(), .7f);
        if (!To.IsNearlyZero()) R->SetActorRotation(FRotator(0,To.Rotation().Yaw,0));
    }
}


void ABBMatchState::PresentConductEvidence()
{
    bconductreviewpending = !ConductEvidence.IsEmpty();
    if (!bconductreviewpending) return;
    const fconductevidence& evidence = conductevidence[0];
    conductoffender = Evidence.Offender; conductvictimteam = Evidence.VictimTeam;
    conductvictimslot = Evidence.VictimSlot; conductball = Evidence.Ball;
    lastconductattack = Evidence.Attack; lastconductviolations = static_cast<int32>(Evidence.Violations);
    lastconductcall = Evidence.Reason; conductfoulpoint = Evidence.FoulPoint;
    conductmark = conductfoulpoint;
    ConductMark.X = FMath::Clamp(ConductMark.X, -BBArena::GoalPlaneX + 500.8, BBArena::GoalPlaneX - 500.8);
    ConductMark.Y = FMath::Clamp(ConductMark.Y, -BBArena::HalfWidth + 500.4, BBArena::HalfWidth - 500.4);
    ConductMark.Z = FMath::Clamp(ConductMark.Z, 400.0, BBArena::EaveHeight - 406.24);
    conductmark = BBArena::ClampSphere(ConductMark, 250.0);
    conductreviewstatus = bconductadvantagelive
        ? text("moderate advantage - offended team keeps scoring possession; original free-shot remedy remains due")
        : Evidence.PenaltyId > 0
            ? text("moderate advantage ended - f6 free shot / f7 possession; result remains provisional")
            : text("playtest referee - f6 free shot / f7 possession / f8 shot + removal / f9 ejection");
}
void ABBMatchState::CompleteConductEvidence()
{
    if (!ConductEvidence.IsEmpty())
    { lastservedconductevidence = conductevidence[0]; ConductEvidence.RemoveAt(0); }
    presentconductevidence();
}
bool ABBMatchState::IsUnreviewedConductPenalty(int32 id) const
{
    return ConductEvidence.ContainsByPredicate([Id](const fconductevidence& evidence) { return Evidence.PenaltyId == id; });
}
void ABBMatchState::RegisterConductHit(ABBRiderCharacter* offender, abbridercharacter* victim,
    int32 spell, int32 affectedball, uint32 violations, uint64 attack, bool bheadhit)
{
    if (!hasauthority() || !rules || !isvalid(offender) || !isvalid(victim) || violations == 0 || attack == 0) return;
    fconductevidence evidence;
    Evidence.Offender = offender->rosterindex; Evidence.VictimTeam = victim->teamindex;
    Evidence.VictimSlot = victim->rosterindex; Evidence.Ball = affectedball; Evidence.Spell = spell;
    Evidence.Violations = violations; Evidence.Attack = attack; Evidence.CommittedMs = rules->now_ms;
    Evidence.FoulPoint = victim->getactorlocation(); Evidence.OriginalOffender = offender; Evidence.OriginalVictim = victim;
    tarray<fstring> reasons;
    if (violations & static_cast<uint32>(BB::ConductViolation::Unforgivable)) Reasons.Add(TEXT("UNFORGIVABLE"));
    if (violations & static_cast<uint32>(BB::ConductViolation::Headshot)) Reasons.Add(TEXT("HEADSHOT"));
    if (violations & static_cast<uint32>(BB::ConductViolation::Mobbing)) Reasons.Add(TEXT("MOB attack > 3"));
    if (violations & static_cast<uint32>(BB::ConductViolation::DoubleTap)) Reasons.Add(TEXT("DOUBLE-TAP"));
    if (violations & static_cast<uint32>(BB::ConductViolation::PhysicalHolding)) Reasons.Add(TEXT("PHYSICAL holding"));
    Evidence.Reason = FString::Join(Reasons, text(" + "));
    // the host preselects this one prospective moderate ruling. it never
    // overrides a dangerous/additional violation or an impaired carrier.
    const bool bqualifies = bmoderateadvantagearmed && ConductEvidence.IsEmpty()
        && rules->status == BB::Status::Live && spell == 0 && !bheadhit
        && violations == static_cast<uint32>(BB::ConductViolation::Mobbing)
        && !victim->hasspellmovementlock() && victim->impedimentremaining <= 0 && victim->vitality > 50.f
        && affectedball >= 0 && affectedball <= 2 && Balls.IsValidIndex(AffectedBall)
        && balls[affectedball]->holder == victim && Rules->balls[AffectedBall].controller == victim->rosterindex;
    bmoderateadvantagearmed = false;
    if (bqualifies)
        Evidence.PenaltyId = Rules->record_penalty(Evidence.Offender, TCHAR_TO_UTF8(*Evidence.Reason),
            BB::Severity::Moderate, Evidence.Ball, Evidence.CommittedMs);
    bconductadvantagelive = bqualifies && Evidence.PenaltyId > 0;
    ConductEvidence.Add(Evidence); ++conductfoulcount;
    presentconductevidence();
    if (!bconductadvantagelive) rules->pause("bb-0 conduct review after applied hit");
    syncrules(); say(bconductadvantagelive ? conductreviewstatus : text("bb-0 FOUL: ") + Evidence.Reason + text(" - hit applied; referee decision due."));
    ue_log(logtemp, display, text("bb0 applied hit evidence: id=%llu caster=%d target=%d spell=%d flags=%u committed=%lld advantage=%d"),
        static_cast<unsigned long long>(attack), Evidence.Offender, Evidence.VictimSlot, spell, violations,
        static_cast<long long>(Evidence.CommittedMs), bconductadvantagelive ? 1 : 0);
}
void ABBMatchState::TickConductAdvantage()
{
    if (!bconductadvantagelive || !rules || ConductEvidence.IsEmpty()) return;
    const fconductevidence& evidence = conductevidence[0];
    bool bretained = false;
    if (Evidence.Ball >= 0 && Evidence.Ball <= 2)
    {
        const BB::Ball& ball = Rules->balls[Evidence.Ball];
        bretained = Ball.live && Ball.controller >= 0 && Ball.controller < 16
            && Rules->players[Ball.controller].team == Evidence.VictimTeam
            && Rules->eligible(Ball.controller, Evidence.Ball);
        if (abbridercharacter* carrier = RiderForSlot(Ball.controller)) bretained &= !carrier->hasspellmovementlock();
        else bretained = false;
    }
    if (rules->status == BB::Status::Live && bretained) return;
    // preserve an already observed terminal event. its pending penalty prevents
    // certification; never rewind its catch, points or original clock.
    if (rules->status == BB::Status::Live) rules->pause("moderate advantage lost: offended team no longer controls affected ball");
    bconductadvantagelive = false; presentconductevidence(); syncrules(); say(conductreviewstatus);
}
tarray<double> ABBMatchState::DevelopmentGetConductAdvantageState() const
{
#if !ue_build_shipping
    if (hasauthority() && rules && getworld() && getworld()->worldtype == EWorldType::PIE)
    {
        const fconductevidence* evidence = !ConductEvidence.IsEmpty() ? &conductevidence[0]
            : LastServedConductEvidence.Attack ? &lastservedconductevidence : nullptr;
        return {bmoderateadvantagearmed ? 1.0 : 0.0, bconductadvantagelive ? 1.0 : 0.0,
            static_cast<double>(ConductEvidence.Num()), evidence ? static_cast<double>(evidence->committedms) : -1.0,
            evidence ? static_cast<double>(evidence->penaltyid) : -1.0, evidence ? static_cast<double>(evidence->offender) : -1.0,
            evidence ? static_cast<double>(evidence->victimslot) : -1.0, evidence ? static_cast<double>(evidence->ball) : -1.0,
            evidence ? static_cast<double>(evidence->attack) : -1.0, static_cast<double>(rules->status),
            Rules->ending.active ? static_cast<double>(Rules->ending.at_ms) : -1.0, Rules->penalty_shot.post_termination ? 1.0 : 0.0};
    }
#endif
    return {};
}

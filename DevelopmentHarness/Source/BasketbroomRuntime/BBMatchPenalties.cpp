#include "BBMatchState.h"
#include "BBBall.h"
#include "BBArenaGeometry.h"
#include "BBRiderCharacter.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"

namespace
{
void positionforshot(abbridercharacter* rider, const fvector& location, const frotator& look)
{
    rider->consumemovementinputvector();
    rider->getcharactermovement()->stopmovementimmediately();
    const ucapsulecomponent* capsule = rider->getcapsulecomponent();
    const fvector bounded = BBArena::ClampCapsule(Location, capsule->getscaledcapsuleradius(), capsule->getscaledcapsulehalfheight());
    rider->setactorlocationandrotation(bounded, frotator(0, Look.Yaw, 0), false, nullptr, ETeleportType::TeleportPhysics);
    if (acontroller* controller = rider->getcontroller())
    {
        controller->setcontrolrotation(look);
        if (aplayercontroller* player = cast<aplayercontroller>(controller)) player->clientsetrotation(look, true);
    }
    rider->binteractheld = false;
    rider->forcenetupdate();
}
}

abbridercharacter* ABBMatchState::RiderForSlot(int32 slot) const
{
    for (abbridercharacter* rider : riders)
        if (isvalid(rider) && rider->rosterindex == slot) return rider;
    return nullptr;
}

void ABBMatchState::ResetPenaltyPresentation()
{
    bpenaltyshotactive = bpenaltyshotreleased = bfreeshot = false;
    penaltyshotsecondsleft = penaltyresultdelay = 0;
    penaltyshotmillisecondcarry = 0;
    penaltyflightstepms = penaltyflightconsumedms = 0; bsteppingpenaltyflight = false;
    PenaltyShooterActor.Reset(); PenaltyKeeperActor.Reset();
    penaltyshotball = penaltyshooterslot = penaltykeeperslot = -1;
    PenaltyShotStatus.Empty(); PenaltySavedRiders.Empty(); PenaltySavedViews.Empty();
}

bool ABBMatchState::CanMoveDuringPenalty(const abbridercharacter* rider) const
{
    return bpenaltyshotactive && penaltyshotsecondsleft > 0 && isvalid(rider)
        && rider->rosterindex == penaltykeeperslot;
}

bool ABBMatchState::IsPenaltyBallActive(const abbball* ball) const
{
    return bpenaltyshotactive && penaltyshotsecondsleft > 0 && isvalid(ball)
        && ball->ballindex == penaltyshotball && Balls.Contains(Ball);
}

bool ABBMatchState::BeginConductPenaltyShot(int32 penaltyid, bool bmoderate)
{
    if (!hasauthority() || !rules || bpenaltyshotactive) return false;
    tarray<int32> candidates;
    // preserve the denied ball type. never replace an existing Crown/goal
    // remedy with a different scoring value merely to make f8 succeed.
    if (conductball == 1 || conductball == 2)
    { Candidates.Add(ConductBall); Candidates.Add(3 - conductball); }
    else if (rules->phase == BB::Phase::Donnybrook) { Candidates.Add(1); Candidates.Add(2); }
    else Candidates.Add(0);
    abbridercharacter* shooter = nullptr;
    abbridercharacter* keeper = nullptr;

    for (int32 ballindex : candidates)
    {
        if (!Balls.IsValidIndex(BallIndex) || !isvalid(balls[ballindex])) continue;
        // donnybrook suspends positions: prefer the usual keeper, then the
        // lowest eligible defending slot as the designated goal defender.
        keeper = nullptr;
        for (abbridercharacter* rider : riders)
            if (isvalid(rider) && rider->teamindex == 1 - conductvictimteam
                && (bmoderate || rider->rosterindex != conductoffender)
                && rules->eligible(rider->rosterindex, ballindex)
                && (rider->position == 0 || rules->phase == BB::Phase::Donnybrook)
                && (!keeper || (rider->position == 0 && keeper->position != 0)
                    || (rider->position == keeper->position && rider->rosterindex < keeper->rosterindex))) keeper = rider;
        if (!keeper) continue;
        shooter = riderforslot(conductvictimslot);
        if (!shooter || shooter->teamindex != conductvictimteam || !rules->eligible(shooter->rosterindex, ballindex)) shooter = nullptr;
        if (!shooter)
            for (abbridercharacter* rider : riders)
                if (isvalid(rider) && rider->teamindex == conductvictimteam && rules->eligible(rider->rosterindex, ballindex)
                    && (!shooter || (rider->isplayercontrolled() && !shooter->isplayercontrolled())
                        || (rider->isplayercontrolled() == shooter->isplayercontrolled() && rider->rosterindex < shooter->rosterindex))) shooter = rider;
        if (!shooter || !rules->start_penalty_shot(penaltyid, ballindex, shooter->rosterindex, keeper->rosterindex, bmoderate)) continue;
        resetpenaltypresentation();
        penaltyshotball = ballindex; penaltyshooterslot = shooter->rosterindex; penaltykeeperslot = keeper->rosterindex;
        bpenaltyshotactive = true; bfreeshot = bmoderate;
        penaltyshotsecondsleft = Rules->config.penalty_shot_ms / 1000.f;
        const float direction = shooter->teamindex == 0 ? 1.f : -1.f;
        const float height = ballindex == 0 ? BBArena::LargeHoopHeight : BBArena::SmallHoopHeight;
        penaltyshootermark = fvector(direction * (BBArena::GoalPlaneX - BBArena::FreeShotDistance), 0, height - 25.f);
        if (bfreeshot)
        {
            // user-confirmed 2026/09/14 interpretation: preserve lateral
            // position and altitude; project backwards to 44ft from the plane.
            penaltyshootermark = conductfoulpoint;
            PenaltyShooterMark.X = direction * FMath::Min(Direction * ConductFoulPoint.X, BBArena::GoalPlaneX - BBArena::FreeShotDistance);
        }
        penaltykeepermark = fvector(direction * (BBArena::GoalPlaneX - 180.f), 0, height);
        for (abbridercharacter* rider : riders)
        {
            if (!isvalid(rider)) continue;
            PenaltySavedRiders.Add(Rider->RosterIndex, rider->getactortransform());
            PenaltySavedViews.Add(Rider->RosterIndex, rider->getcontrolrotation());
            rider->binteractheld = false;
            if (rider != shooter && rider != keeper)
            {
                if (!bfreeshot)
                    positionforshot(rider, BBArena::ScaleLayout(FVector((Rider->RosterIndex % 8 - 3.5f) * 500.f,
                        rider->teamindex == 0 ? -2700.f : 2700.f, 1600.f)), rider->getcontrolrotation());
                else
                {
                    fvector mark = rider->getactorlocation();
                    // nonkeeper defenders remain >=22ft away until release.
                    // move into the arena along x, preserving roof clearance.
                    const double separation = rider->teamindex != shooter->teamindex ? BBArena::RestartDistance : 100.0;
                    if (FVector::DistSquared(Mark, penaltyshootermark) < FMath::Square(Separation))
                        Mark.X = PenaltyShooterMark.X + (PenaltyShooterMark.X > 0 ? -1.f : 1.f) * (separation + 90.f);
                    positionforshot(rider, mark, rider->getcontrolrotation());
                }
            }
        }
        positionforshot(shooter, penaltyshootermark, frotator(0, direction > 0 ? 0 : 180, 0));
        positionforshot(keeper, penaltykeepermark, frotator(0, direction > 0 ? 180 : 0, 0));
        penaltyshooteractor = shooter; penaltykeeperactor = keeper;
        // staged dead-ball administration grants only the rules-authorized ball.
        // frozen vitality, cooldown and disable timers are never cleared.
        balls[ballindex]->resetball(shooter->getcarrylocation());
        penaltyshotstatus = FString::Printf(TEXT("%s - %s shooter vs keeper | one attempt in 5 seconds"),
            bfreeshot ? text("free shot / no removal") : text("penalty shot"),
            conductvictimteam == 0 ? text("teal") : text("copper"));
        if (Rules->penalty_shot.post_termination)
            penaltyshotstatus += text(" | post-termination remedy - result provisional");
        reviewdelay = 0;
        syncrules(); say(penaltyshotstatus); forcenetupdate();
        return true;
    }
    return false;
}

void ABBMatchState::ReleasePenaltyShot(ABBRiderCharacter* rider, fvector aim)
{
    if (!hasauthority() || !rules || !bpenaltyshotactive || !isvalid(rider)
        || rider->rosterindex != penaltyshooterslot || Aim.ContainsNaN() || !Aim.IsNormalized()
        || !Balls.IsValidIndex(PenaltyShotBall) || !rules->release_penalty_shot(rider->rosterindex)) return;
    abbball* ball = balls[penaltyshotball];
    // no movement momentum, passing target, or second custody request belongs
    // to this one-shot procedure. a badly aimed release is an ordinary miss.
    ball->holder = nullptr; ball->setactorlocation(rider->getcarrylocation());
    ball->lastlocation = ball->getactorlocation(); ball->flightvelocity = aim * 4400.f;
    ball->lasttouchteam = rider->teamindex; ball->distancesincereleasecm = 0;
    ball->cooldown = .25f; ball->recentthrower = rider; ball->throwerignoreremaining = .15f;
    bpenaltyshotreleased = true; penaltyshotstatus = bfreeshot ? text("free shot in flight - no second attempt") : text("penalty shot in flight - no second attempt");
    ball->forcenetupdate(); forcenetupdate();
}

void ABBMatchState::FinishPenaltyShot(BB::PenaltyShotOutcome outcome, const fstring& reason, const BB::PointEvent& goal)
{
    if (!hasauthority() || !rules || !bpenaltyshotactive || !rules->complete_penalty_shot(outcome, goal)) return;
    penaltyshotsecondsleft = 0; penaltyresultdelay = 0;
    const fstring shotreason = bfreeshot ? Reason.Replace(TEXT("PENALTY shot"), text("free shot")) : reason;
    if (Balls.IsValidIndex(PenaltyShotBall)) balls[penaltyshotball]->flightvelocity = FVector::ZeroVector;
    penaltyshotstatus = outcome == BB::PenaltyShotOutcome::Goal
        ? FString::Printf(TEXT("%s +%lld | defending restart next"), *shotreason, static_cast<long long>(Rules->penalty_shot.awarded_points))
        : shotreason + text(" | defending restart next");
    syncrules(); say(penaltyshotstatus); forcenetupdate();
}

bool ABBMatchState::AdvancePenaltyClock(double milliseconds)
{
    if (!rules || !FMath::IsFinite(Milliseconds) || milliseconds < 0) return false;
    const auto& shot = rules->penalty_shot;
    if (Shot.stage != BB::PenaltyShotStage::Ready && Shot.stage != BB::PenaltyShotStage::InFlight) return false;
    const double remaining = FMath::Max(0.0,
        Rules->config.penalty_shot_ms - Shot.elapsed_ms - penaltyshotmillisecondcarry);
    // the tolerance is a tenth of a nanosecond: only floating-point arithmetic
    // at the exact deadline is snapped; an actual earlier crossing still counts.
    const bool bdeadline = milliseconds >= remaining - 1.e-7;
    const double total = penaltyshotmillisecondcarry + FMath::Min(Milliseconds, remaining);
    const BB::Millis whole = bdeadline ? Rules->config.penalty_shot_ms - Shot.elapsed_ms
        : static_cast<BB::Millis>(Total);
    if (rules->advance_penalty_shot(whole) < 0) return false;
    penaltyshotmillisecondcarry = bdeadline ? 0 : total - whole;
    penaltyshotsecondsleft = static_cast<float>(FMath::Max(0.0,
        Rules->config.penalty_shot_ms - Shot.elapsed_ms - penaltyshotmillisecondcarry) / 1000.0);
    return true;
}

bool ABBMatchState::ConsumePenaltyFlightTime(double flightstepfraction)
{
    if (!bsteppingpenaltyflight || !rules || !FMath::IsFinite(FlightStepFraction)
        || flightstepfraction < 0 || flightstepfraction > 1 || penaltyflightstepms <= 0) return false;
    const double offset = penaltyflightstepms * flightstepfraction;
    if (offset < penaltyflightconsumedms || !advancepenaltyclock(offset - penaltyflightconsumedms)) return false;
    penaltyflightconsumedms = offset;
    return Rules->penalty_shot.stage == BB::PenaltyShotStage::InFlight;
}

void ABBMatchState::PenaltyBallStopped(ABBBall* ball, const fstring& reason, double flightstepfraction)
{
    if (ispenaltyballactive(ball) && bpenaltyshotreleased && consumepenaltyflighttime(flightstepfraction))
        FinishPenaltyShot(BB::PenaltyShotOutcome::Miss, reason);
}

void ABBMatchState::TickPenaltyShot(float deltaseconds)
{
    if (!rules || !bpenaltyshotactive) return;
    if (!FMath::IsFinite(DeltaSeconds)) return;
    const float dt = FMath::Max(0.f, deltaseconds);
    double remainingframems = dt * 1000.0;
    abbridercharacter* shooter = riderforslot(penaltyshooterslot);
    abbridercharacter* keeper = riderforslot(penaltykeeperslot);
    abbball* ball = Balls.IsValidIndex(PenaltyShotBall) ? Balls[PenaltyShotBall].Get() : nullptr;
    auto& shot = rules->penalty_shot;
    const float direction = Shot.attacking_team == 0 ? 1.f : -1.f;
    // gamemode's genuine disconnect replacements inherit the existing roster
    // reservation. new admissions cannot take either reserved slot. re-stage
    // changed actors without restarting the clock, attempt, effects or ledger.
    if (shooter && PenaltyShooterActor.Get() != shooter)
    {
        positionforshot(shooter, penaltyshootermark, frotator(0, direction > 0 ? 0 : 180, 0));
        penaltyshooteractor = shooter;
        if (ball && Shot.stage == BB::PenaltyShotStage::Ready)
        {
            ball->resetball(shooter->getcarrylocation());
            ball->holder = shooter;
        }
    }
    if (keeper && PenaltyKeeperActor.Get() != keeper)
    {
        positionforshot(keeper, penaltykeepermark, frotator(0, direction > 0 ? 180 : 0, 0));
        penaltykeeperactor = keeper;
    }
    const bool bhadattempt = Shot.stage == BB::PenaltyShotStage::Ready || Shot.stage == BB::PenaltyShotStage::InFlight;
    if (bhadattempt)
    {
        if (shooter)
        {
            shooter->consumemovementinputvector(); shooter->getcharactermovement()->stopmovementimmediately();
            shooter->setactorlocation(penaltyshootermark, false, nullptr, ETeleportType::TeleportPhysics);
        }
        // one authority owns attempt time and flight. each swept physical event
        // consumes its actual fraction of this capped step before adjudication.
        // the ordinary ball actor never integrates penalty flight a second time.
        while (remainingframems > 0 &&
            (Shot.stage == BB::PenaltyShotStage::Ready || Shot.stage == BB::PenaltyShotStage::InFlight))
        {
            const double elapsed = Shot.elapsed_ms + penaltyshotmillisecondcarry;
            const double remainingshotms = FMath::Max(0.0, Rules->config.penalty_shot_ms - elapsed);
            if (remainingshotms <= 1.e-7) { advancepenaltyclock(remainingshotms); break; }
            const bool bcpushooter = shooter && !shooter->isplayercontrolled() && shooter->isactortickenabled() && ball;
            if (bcpushooter && Shot.stage == BB::PenaltyShotStage::Ready && elapsed >= 1250.0)
            {
                const fvector origin = shooter->getcarrylocation();
                const float travel = FMath::Abs(Direction * BBArena::GoalPlaneX - Origin.X) / 4400.f;
                const float offset = penaltyshotball == 0 ? (shooter->rosterindex % 2 ? 180.f : -180.f) : 110.f;
                const fvector target(direction * (BBArena::GoalPlaneX + ball->radius()), offset,
                    (penaltyshotball == 0 ? BBArena::LargeHoopHeight : BBArena::SmallHoopHeight) + 190.f * travel * travel);
                releasepenaltyshot(shooter, (target - Origin).GetSafeNormal());
            }
            double stepms = FMath::Min(RemainingFrameMs, FMath::Min(1000.0 / 120.0, remainingshotms));
            if (bcpushooter && Shot.stage == BB::PenaltyShotStage::Ready && elapsed < 1250.0)
                stepms = FMath::Min(StepMs, 1250.0 - elapsed);
            if (keeper)
            {
                fvector location = keeper->getactorlocation();
                if (!keeper->isplayercontrolled() && keeper->isactortickenabled() && bpenaltyshotreleased && ball)
                {
                    const fvector Target(PenaltyKeeperMark.X, Ball->GetActorLocation().Y, Ball->GetActorLocation().Z);
                    location = FMath::VInterpConstantTo(Location, target, static_cast<float>(stepms / 1000.0), 350.f);
                }
                Location.X = PenaltyKeeperMark.X;
                Location.Y = FMath::Clamp(Location.Y, -1450.0, 1450.0);
                Location.Z = FMath::Clamp(Location.Z, 900.0, 4000.0);
                const ucapsulecomponent* capsule = keeper->getcapsulecomponent();
                location = BBArena::ClampCapsule(Location, capsule->getscaledcapsuleradius(), capsule->getscaledcapsulehalfheight());
                keeper->setactorlocation(location, false, nullptr, ETeleportType::TeleportPhysics);
            }
            penaltyflightstepms = stepms; penaltyflightconsumedms = 0;
            if (ball && Shot.stage == BB::PenaltyShotStage::InFlight)
            {
                bsteppingpenaltyflight = true;
                ball->steppenaltyflight(stepms / 1000.0);
                bsteppingpenaltyflight = false;
            }
            else if (ball && shooter) ball->setactorlocation(shooter->getcarrylocation());
            if (Shot.stage == BB::PenaltyShotStage::Ready || Shot.stage == BB::PenaltyShotStage::InFlight)
            {
                if (!advancepenaltyclock(stepms - penaltyflightconsumedms)) break;
                penaltyflightconsumedms = stepms;
            }
            // only time after an outcome contributes to the presentation delay.
            remainingframems = FMath::Max(0.0, remainingframems - penaltyflightconsumedms);
            penaltyflightstepms = 0;
        }
        if (Shot.stage == BB::PenaltyShotStage::AwaitingRestart && Shot.outcome == BB::PenaltyShotOutcome::Timeout)
        {
            penaltyshotsecondsleft = 0; penaltyresultdelay = 0;
            if (ball) ball->flightvelocity = FVector::ZeroVector;
            penaltyshotstatus = bfreeshot ? text("free shot time expired | defending restart next") : text("penalty shot time expired | defending restart next");
            say(penaltyshotstatus);
        }
    }
    if (Shot.stage == BB::PenaltyShotStage::AwaitingRestart)
    {
        penaltyresultdelay += static_cast<float>(remainingframems / 1000.0);
        if (penaltyresultdelay >= 1.5f && keeper && ball && rules->restart_penalty_shot(keeper->rosterindex))
        {
            for (abbridercharacter* rider : riders)
            {
                if (!isvalid(rider) || rider == keeper) continue;
                if (const ftransform* saved = PenaltySavedRiders.Find(Rider->RosterIndex))
                    positionforshot(rider, saved->getlocation(), PenaltySavedViews.FindRef(Rider->RosterIndex));
            }
            const float restartdirection = keeper->teamindex == 0 ? -1.f : 1.f;
            const fvector restartmark(restartdirection * (BBArena::GoalPlaneX - BBArena::RestartDistance), 0, penaltyshotball == 0 ? BBArena::LargeHoopHeight : BBArena::SmallHoopHeight);
            positionforshot(keeper, restartmark, frotator(0, keeper->teamindex == 0 ? 0 : 180, 0));
            // opponents cannot be restored on top of the protected receiver.
            for (abbridercharacter* other : riders)
                if (isvalid(other) && other->teamindex != keeper->teamindex
                    && FVector::DistSquared(Other->GetActorLocation(), restartmark) < FMath::Square(450.f))
                    positionforshot(other, restartmark + fvector(-restartdirection * 550.f, 0, 0), other->getcontrolrotation());
            ball->resetball(keeper->getcarrylocation());
            bpenaltyshotactive = false; penaltyshotsecondsleft = 0;
            PenaltyShooterActor.Reset(); PenaltyKeeperActor.Reset();
            PenaltySavedRiders.Empty(); PenaltySavedViews.Empty();
            reviewdelay = 0;
            syncrules();
            penaltyshotstatus += rules->status == BB::Status::Review
                ? text(" | restart served; result under review - awaiting certification")
                : text(" | restart served; host enter to resume");
            say(penaltyshotstatus); forcenetupdate(); return;
        }
        if (penaltyresultdelay >= 1.5f)
            penaltyshotstatus = text("defending restart remains due - eligible netminder required");
    }
    syncrules();
    if (bpenaltyshotactive) status = bfreeshot ? text("free shot") : text("penalty shot");
    forcenetupdate();
}

tarray<int32> ABBMatchState::DevelopmentGetPenaltyShotState() const
{
#if !ue_build_shipping
    if (hasauthority() && rules && getworld() && getworld()->worldtype == EWorldType::PIE)
    {
        const auto& shot = rules->penalty_shot;
        const bool valid = Shot.penalty_id > 0 && Shot.penalty_id <= static_cast<int32>(Rules->penalties.size());
        return {Shot.penalty_id, static_cast<int32>(Shot.stage), static_cast<int32>(Shot.outcome), Shot.ball,
            Shot.shooter, Shot.netminder, valid && Rules->penalties[Shot.penalty_id - 1].pending ? 1 : 0,
            static_cast<int32>(Shot.awarded_points), valid ? Rules->penalties[Shot.penalty_id - 1].player : -1};
    }
#endif
    return {};
}

double ABBMatchState::DevelopmentGetRemovalSeconds(int32 slot) const
{
#if !ue_build_shipping
    if (hasauthority() && rules && slot >= 0 && slot < 16 && getworld() && getworld()->worldtype == EWorldType::PIE)
    {
        const auto& player = rules->players[slot];
        if (Player.ejected || Player.donnybrook_excluded) return -2;
        return Player.removed_until >= 0 ? FMath::Max(0.0, (Player.removed_until - rules->now_ms) / 1000.0) : 0;
    }
#endif
    return -1;
}

tarray<double> ABBMatchState::DevelopmentGetPenaltyShotTiming() const
{
#if !ue_build_shipping
    if (hasauthority() && rules && getworld() && getworld()->worldtype == EWorldType::PIE)
    {
        const double elapsed = Rules->penalty_shot.elapsed_ms + penaltyshotmillisecondcarry;
        return {elapsed, static_cast<double>(Rules->config.penalty_shot_ms),
            FMath::Max(0.0, Rules->config.penalty_shot_ms - elapsed)};
    }
#endif
    return {};
}

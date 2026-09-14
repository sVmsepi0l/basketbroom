#include "BBMatchState.h"
#include "BBBall.h"
#include "BBRiderCharacter.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"

namespace
{
void PositionForShot(ABBRiderCharacter* Rider, const FVector& Location, const FRotator& Look)
{
    Rider->ConsumeMovementInputVector();
    Rider->GetCharacterMovement()->StopMovementImmediately();
    Rider->SetActorLocationAndRotation(Location, FRotator(0, Look.Yaw, 0), false, nullptr, ETeleportType::TeleportPhysics);
    if (AController* Controller = Rider->GetController())
    {
        Controller->SetControlRotation(Look);
        if (APlayerController* Player = Cast<APlayerController>(Controller)) Player->ClientSetRotation(Look, true);
    }
    Rider->bInteractHeld = false;
    Rider->ForceNetUpdate();
}
}

ABBRiderCharacter* ABBMatchState::RiderForSlot(int32 Slot) const
{
    for (ABBRiderCharacter* Rider : Riders)
        if (IsValid(Rider) && Rider->RosterIndex == Slot) return Rider;
    return nullptr;
}

void ABBMatchState::ResetPenaltyPresentation()
{
    bPenaltyShotActive = bPenaltyShotReleased = bFreeShot = false;
    PenaltyShotSecondsLeft = PenaltyResultDelay = 0;
    PenaltyShotMillisecondCarry = 0;
    PenaltyFlightStepMs = PenaltyFlightConsumedMs = 0; bSteppingPenaltyFlight = false;
    PenaltyShooterActor.Reset(); PenaltyKeeperActor.Reset();
    PenaltyShotBall = PenaltyShooterSlot = PenaltyKeeperSlot = -1;
    PenaltyShotStatus.Empty(); PenaltySavedRiders.Empty(); PenaltySavedViews.Empty();
}

bool ABBMatchState::CanMoveDuringPenalty(const ABBRiderCharacter* Rider) const
{
    return bPenaltyShotActive && PenaltyShotSecondsLeft > 0 && IsValid(Rider)
        && Rider->RosterIndex == PenaltyKeeperSlot;
}

bool ABBMatchState::IsPenaltyBallActive(const ABBBall* Ball) const
{
    return bPenaltyShotActive && PenaltyShotSecondsLeft > 0 && IsValid(Ball)
        && Ball->BallIndex == PenaltyShotBall && Balls.Contains(Ball);
}

bool ABBMatchState::BeginConductPenaltyShot(int32 PenaltyId, bool bModerate)
{
    if (!HasAuthority() || !Rules || bPenaltyShotActive) return false;
    TArray<int32> Candidates;
    // Preserve the denied ball type. Never replace an existing Crown/goal
    // remedy with a different scoring value merely to make F8 succeed.
    if (ConductBall == 1 || ConductBall == 2)
    { Candidates.Add(ConductBall); Candidates.Add(3 - ConductBall); }
    else if (Rules->phase == BB::Phase::Donnybrook) { Candidates.Add(1); Candidates.Add(2); }
    else Candidates.Add(0);
    ABBRiderCharacter* Shooter = nullptr;
    ABBRiderCharacter* Keeper = nullptr;

    for (int32 BallIndex : Candidates)
    {
        if (!Balls.IsValidIndex(BallIndex) || !IsValid(Balls[BallIndex])) continue;
        // Donnybrook suspends positions: prefer the usual keeper, then the
        // lowest eligible defending slot as the designated goal defender.
        Keeper = nullptr;
        for (ABBRiderCharacter* Rider : Riders)
            if (IsValid(Rider) && Rider->TeamIndex == 1 - ConductVictimTeam
                && (bModerate || Rider->RosterIndex != ConductOffender)
                && Rules->eligible(Rider->RosterIndex, BallIndex)
                && (Rider->Position == 0 || Rules->phase == BB::Phase::Donnybrook)
                && (!Keeper || (Rider->Position == 0 && Keeper->Position != 0)
                    || (Rider->Position == Keeper->Position && Rider->RosterIndex < Keeper->RosterIndex))) Keeper = Rider;
        if (!Keeper) continue;
        Shooter = RiderForSlot(ConductVictimSlot);
        if (!Shooter || Shooter->TeamIndex != ConductVictimTeam || !Rules->eligible(Shooter->RosterIndex, BallIndex)) Shooter = nullptr;
        if (!Shooter)
            for (ABBRiderCharacter* Rider : Riders)
                if (IsValid(Rider) && Rider->TeamIndex == ConductVictimTeam && Rules->eligible(Rider->RosterIndex, BallIndex)
                    && (!Shooter || (Rider->IsPlayerControlled() && !Shooter->IsPlayerControlled())
                        || (Rider->IsPlayerControlled() == Shooter->IsPlayerControlled() && Rider->RosterIndex < Shooter->RosterIndex))) Shooter = Rider;
        if (!Shooter || !Rules->start_penalty_shot(PenaltyId, BallIndex, Shooter->RosterIndex, Keeper->RosterIndex, bModerate)) continue;
        ResetPenaltyPresentation();
        PenaltyShotBall = BallIndex; PenaltyShooterSlot = Shooter->RosterIndex; PenaltyKeeperSlot = Keeper->RosterIndex;
        bPenaltyShotActive = true; bFreeShot = bModerate;
        PenaltyShotSecondsLeft = Rules->config.penalty_shot_ms / 1000.f;
        const float Direction = Shooter->TeamIndex == 0 ? 1.f : -1.f;
        const float Height = BallIndex == 0 ? 2103.12f : 3048.f;
        PenaltyShooterMark = FVector(Direction * (6400.8f - 1341.12f), 0, Height - 25.f);
        if (bFreeShot)
        {
            // User-confirmed 2026-09-14 interpretation: preserve lateral
            // position and altitude; project backwards to 44ft from the plane.
            PenaltyShooterMark = ConductFoulPoint;
            PenaltyShooterMark.X = Direction * FMath::Min(Direction * ConductFoulPoint.X, 6400.8f - 1341.12f);
        }
        PenaltyKeeperMark = FVector(Direction * (6400.8f - 180.f), 0, Height);
        for (ABBRiderCharacter* Rider : Riders)
        {
            if (!IsValid(Rider)) continue;
            PenaltySavedRiders.Add(Rider->RosterIndex, Rider->GetActorTransform());
            PenaltySavedViews.Add(Rider->RosterIndex, Rider->GetControlRotation());
            Rider->bInteractHeld = false;
            if (Rider != Shooter && Rider != Keeper)
            {
                if (!bFreeShot)
                    PositionForShot(Rider, FVector((Rider->RosterIndex % 8 - 3.5f) * 500.f,
                        Rider->TeamIndex == 0 ? -2700.f : 2700.f, 1600.f), Rider->GetControlRotation());
                else
                {
                    FVector Mark = Rider->GetActorLocation();
                    // Nonkeeper defenders remain >=22ft away until release.
                    // Move into the arena along X, preserving roof clearance.
                    const float Separation = Rider->TeamIndex != Shooter->TeamIndex ? 670.56f : 100.f;
                    if (FVector::DistSquared(Mark, PenaltyShooterMark) < FMath::Square(Separation))
                        Mark.X = PenaltyShooterMark.X + (PenaltyShooterMark.X > 0 ? -1.f : 1.f) * (Separation + 90.f);
                    PositionForShot(Rider, Mark, Rider->GetControlRotation());
                }
            }
        }
        PositionForShot(Shooter, PenaltyShooterMark, FRotator(0, Direction > 0 ? 0 : 180, 0));
        PositionForShot(Keeper, PenaltyKeeperMark, FRotator(0, Direction > 0 ? 180 : 0, 0));
        PenaltyShooterActor = Shooter; PenaltyKeeperActor = Keeper;
        // Staged dead-ball administration grants only the rules-authorized ball.
        // Frozen vitality, cooldown and disable timers are never cleared.
        Balls[BallIndex]->ResetBall(Shooter->GetCarryLocation());
        PenaltyShotStatus = FString::Printf(TEXT("%s - %s shooter vs keeper | one attempt in 5 seconds"),
            bFreeShot ? TEXT("FREE SHOT / NO REMOVAL") : TEXT("PENALTY SHOT"),
            ConductVictimTeam == 0 ? TEXT("TEAL") : TEXT("COPPER"));
        SyncRules(); Say(PenaltyShotStatus); ForceNetUpdate();
        return true;
    }
    return false;
}

void ABBMatchState::ReleasePenaltyShot(ABBRiderCharacter* Rider, FVector Aim)
{
    if (!HasAuthority() || !Rules || !bPenaltyShotActive || !IsValid(Rider)
        || Rider->RosterIndex != PenaltyShooterSlot || Aim.ContainsNaN() || !Aim.IsNormalized()
        || !Balls.IsValidIndex(PenaltyShotBall) || !Rules->release_penalty_shot(Rider->RosterIndex)) return;
    ABBBall* Ball = Balls[PenaltyShotBall];
    // No movement momentum, passing target, or second custody request belongs
    // to this one-shot procedure. A badly aimed release is an ordinary miss.
    Ball->Holder = nullptr; Ball->SetActorLocation(Rider->GetCarryLocation());
    Ball->LastLocation = Ball->GetActorLocation(); Ball->FlightVelocity = Aim * 4400.f;
    Ball->LastTouchTeam = Rider->TeamIndex; Ball->DistanceSinceReleaseCm = 0;
    Ball->Cooldown = .25f; Ball->RecentThrower = Rider; Ball->ThrowerIgnoreRemaining = .15f;
    bPenaltyShotReleased = true; PenaltyShotStatus = bFreeShot ? TEXT("FREE SHOT IN FLIGHT - no second attempt") : TEXT("PENALTY SHOT IN FLIGHT - no second attempt");
    Ball->ForceNetUpdate(); ForceNetUpdate();
}

void ABBMatchState::FinishPenaltyShot(BB::PenaltyShotOutcome Outcome, const FString& Reason, const BB::PointEvent& Goal)
{
    if (!HasAuthority() || !Rules || !bPenaltyShotActive || !Rules->complete_penalty_shot(Outcome, Goal)) return;
    PenaltyShotSecondsLeft = 0; PenaltyResultDelay = 0;
    const FString ShotReason = bFreeShot ? Reason.Replace(TEXT("PENALTY SHOT"), TEXT("FREE SHOT")) : Reason;
    if (Balls.IsValidIndex(PenaltyShotBall)) Balls[PenaltyShotBall]->FlightVelocity = FVector::ZeroVector;
    PenaltyShotStatus = Outcome == BB::PenaltyShotOutcome::Goal
        ? FString::Printf(TEXT("%s +%lld | defending restart next"), *ShotReason, static_cast<long long>(Rules->penalty_shot.awarded_points))
        : ShotReason + TEXT(" | defending restart next");
    SyncRules(); Say(PenaltyShotStatus); ForceNetUpdate();
}

bool ABBMatchState::AdvancePenaltyClock(double Milliseconds)
{
    if (!Rules || !FMath::IsFinite(Milliseconds) || Milliseconds < 0) return false;
    const auto& Shot = Rules->penalty_shot;
    if (Shot.stage != BB::PenaltyShotStage::Ready && Shot.stage != BB::PenaltyShotStage::InFlight) return false;
    const double Remaining = FMath::Max(0.0,
        Rules->config.penalty_shot_ms - Shot.elapsed_ms - PenaltyShotMillisecondCarry);
    // The tolerance is a tenth of a nanosecond: only floating-point arithmetic
    // at the exact deadline is snapped; an actual earlier crossing still counts.
    const bool bDeadline = Milliseconds >= Remaining - 1.e-7;
    const double Total = PenaltyShotMillisecondCarry + FMath::Min(Milliseconds, Remaining);
    const BB::Millis Whole = bDeadline ? Rules->config.penalty_shot_ms - Shot.elapsed_ms
        : static_cast<BB::Millis>(Total);
    if (Rules->advance_penalty_shot(Whole) < 0) return false;
    PenaltyShotMillisecondCarry = bDeadline ? 0 : Total - Whole;
    PenaltyShotSecondsLeft = static_cast<float>(FMath::Max(0.0,
        Rules->config.penalty_shot_ms - Shot.elapsed_ms - PenaltyShotMillisecondCarry) / 1000.0);
    return true;
}

bool ABBMatchState::ConsumePenaltyFlightTime(double FlightStepFraction)
{
    if (!bSteppingPenaltyFlight || !Rules || !FMath::IsFinite(FlightStepFraction)
        || FlightStepFraction < 0 || FlightStepFraction > 1 || PenaltyFlightStepMs <= 0) return false;
    const double Offset = PenaltyFlightStepMs * FlightStepFraction;
    if (Offset < PenaltyFlightConsumedMs || !AdvancePenaltyClock(Offset - PenaltyFlightConsumedMs)) return false;
    PenaltyFlightConsumedMs = Offset;
    return Rules->penalty_shot.stage == BB::PenaltyShotStage::InFlight;
}

void ABBMatchState::PenaltyBallStopped(ABBBall* Ball, const FString& Reason, double FlightStepFraction)
{
    if (IsPenaltyBallActive(Ball) && bPenaltyShotReleased && ConsumePenaltyFlightTime(FlightStepFraction))
        FinishPenaltyShot(BB::PenaltyShotOutcome::Miss, Reason);
}

void ABBMatchState::TickPenaltyShot(float DeltaSeconds)
{
    if (!Rules || !bPenaltyShotActive) return;
    if (!FMath::IsFinite(DeltaSeconds)) return;
    const float Dt = FMath::Max(0.f, DeltaSeconds);
    double RemainingFrameMs = Dt * 1000.0;
    ABBRiderCharacter* Shooter = RiderForSlot(PenaltyShooterSlot);
    ABBRiderCharacter* Keeper = RiderForSlot(PenaltyKeeperSlot);
    ABBBall* Ball = Balls.IsValidIndex(PenaltyShotBall) ? Balls[PenaltyShotBall].Get() : nullptr;
    auto& Shot = Rules->penalty_shot;
    const float Direction = Shot.attacking_team == 0 ? 1.f : -1.f;
    // GameMode's genuine disconnect replacements inherit the existing roster
    // reservation. New admissions cannot take either reserved slot. Re-stage
    // changed actors without restarting the clock, attempt, effects or ledger.
    if (Shooter && PenaltyShooterActor.Get() != Shooter)
    {
        PositionForShot(Shooter, PenaltyShooterMark, FRotator(0, Direction > 0 ? 0 : 180, 0));
        PenaltyShooterActor = Shooter;
        if (Ball && Shot.stage == BB::PenaltyShotStage::Ready)
        {
            Ball->ResetBall(Shooter->GetCarryLocation());
            Ball->Holder = Shooter;
        }
    }
    if (Keeper && PenaltyKeeperActor.Get() != Keeper)
    {
        PositionForShot(Keeper, PenaltyKeeperMark, FRotator(0, Direction > 0 ? 180 : 0, 0));
        PenaltyKeeperActor = Keeper;
    }
    const bool bHadAttempt = Shot.stage == BB::PenaltyShotStage::Ready || Shot.stage == BB::PenaltyShotStage::InFlight;
    if (bHadAttempt)
    {
        if (Shooter)
        {
            Shooter->ConsumeMovementInputVector(); Shooter->GetCharacterMovement()->StopMovementImmediately();
            Shooter->SetActorLocation(PenaltyShooterMark, false, nullptr, ETeleportType::TeleportPhysics);
        }
        // One authority owns attempt time and flight. Each swept physical event
        // consumes its actual fraction of this capped step before adjudication.
        // The ordinary ball actor never integrates penalty flight a second time.
        while (RemainingFrameMs > 0 &&
            (Shot.stage == BB::PenaltyShotStage::Ready || Shot.stage == BB::PenaltyShotStage::InFlight))
        {
            const double Elapsed = Shot.elapsed_ms + PenaltyShotMillisecondCarry;
            const double RemainingShotMs = FMath::Max(0.0, Rules->config.penalty_shot_ms - Elapsed);
            if (RemainingShotMs <= 1.e-7) { AdvancePenaltyClock(RemainingShotMs); break; }
            const bool bCpuShooter = Shooter && !Shooter->IsPlayerControlled() && Shooter->IsActorTickEnabled() && Ball;
            if (bCpuShooter && Shot.stage == BB::PenaltyShotStage::Ready && Elapsed >= 1250.0)
            {
                const FVector Origin = Shooter->GetCarryLocation();
                const float Travel = FMath::Abs(Direction * 6400.8f - Origin.X) / 4400.f;
                const float Offset = PenaltyShotBall == 0 ? (Shooter->RosterIndex % 2 ? 180.f : -180.f) : 110.f;
                const FVector Target(Direction * (6400.8f + Ball->Radius()), Offset,
                    (PenaltyShotBall == 0 ? 2103.12f : 3048.f) + 190.f * Travel * Travel);
                ReleasePenaltyShot(Shooter, (Target - Origin).GetSafeNormal());
            }
            double StepMs = FMath::Min(RemainingFrameMs, FMath::Min(1000.0 / 120.0, RemainingShotMs));
            if (bCpuShooter && Shot.stage == BB::PenaltyShotStage::Ready && Elapsed < 1250.0)
                StepMs = FMath::Min(StepMs, 1250.0 - Elapsed);
            if (Keeper)
            {
                FVector Location = Keeper->GetActorLocation();
                if (!Keeper->IsPlayerControlled() && Keeper->IsActorTickEnabled() && bPenaltyShotReleased && Ball)
                {
                    const FVector Target(PenaltyKeeperMark.X, Ball->GetActorLocation().Y, Ball->GetActorLocation().Z);
                    Location = FMath::VInterpConstantTo(Location, Target, static_cast<float>(StepMs / 1000.0), 350.f);
                }
                Location.X = PenaltyKeeperMark.X;
                Location.Y = FMath::Clamp(Location.Y, -1450.0, 1450.0);
                Location.Z = FMath::Clamp(Location.Z, 900.0, 4000.0);
                Keeper->SetActorLocation(Location, false, nullptr, ETeleportType::TeleportPhysics);
            }
            PenaltyFlightStepMs = StepMs; PenaltyFlightConsumedMs = 0;
            if (Ball && Shot.stage == BB::PenaltyShotStage::InFlight)
            {
                bSteppingPenaltyFlight = true;
                Ball->StepPenaltyFlight(StepMs / 1000.0);
                bSteppingPenaltyFlight = false;
            }
            else if (Ball && Shooter) Ball->SetActorLocation(Shooter->GetCarryLocation());
            if (Shot.stage == BB::PenaltyShotStage::Ready || Shot.stage == BB::PenaltyShotStage::InFlight)
            {
                if (!AdvancePenaltyClock(StepMs - PenaltyFlightConsumedMs)) break;
                PenaltyFlightConsumedMs = StepMs;
            }
            // Only time after an outcome contributes to the presentation delay.
            RemainingFrameMs = FMath::Max(0.0, RemainingFrameMs - PenaltyFlightConsumedMs);
            PenaltyFlightStepMs = 0;
        }
        if (Shot.stage == BB::PenaltyShotStage::AwaitingRestart && Shot.outcome == BB::PenaltyShotOutcome::Timeout)
        {
            PenaltyShotSecondsLeft = 0; PenaltyResultDelay = 0;
            if (Ball) Ball->FlightVelocity = FVector::ZeroVector;
            PenaltyShotStatus = bFreeShot ? TEXT("FREE SHOT TIME EXPIRED | defending restart next") : TEXT("PENALTY SHOT TIME EXPIRED | defending restart next");
            Say(PenaltyShotStatus);
        }
    }
    if (Shot.stage == BB::PenaltyShotStage::AwaitingRestart)
    {
        PenaltyResultDelay += static_cast<float>(RemainingFrameMs / 1000.0);
        if (PenaltyResultDelay >= 1.5f && Keeper && Ball && Rules->restart_penalty_shot(Keeper->RosterIndex))
        {
            for (ABBRiderCharacter* Rider : Riders)
            {
                if (!IsValid(Rider) || Rider == Keeper) continue;
                if (const FTransform* Saved = PenaltySavedRiders.Find(Rider->RosterIndex))
                    PositionForShot(Rider, Saved->GetLocation(), PenaltySavedViews.FindRef(Rider->RosterIndex));
            }
            const float RestartDirection = Keeper->TeamIndex == 0 ? -1.f : 1.f;
            const FVector RestartMark(RestartDirection * (6400.8f - 670.56f), 0, PenaltyShotBall == 0 ? 2103.12f : 3048.f);
            PositionForShot(Keeper, RestartMark, FRotator(0, Keeper->TeamIndex == 0 ? 0 : 180, 0));
            // Opponents cannot be restored on top of the protected receiver.
            for (ABBRiderCharacter* Other : Riders)
                if (IsValid(Other) && Other->TeamIndex != Keeper->TeamIndex
                    && FVector::DistSquared(Other->GetActorLocation(), RestartMark) < FMath::Square(450.f))
                    PositionForShot(Other, RestartMark + FVector(-RestartDirection * 550.f, 0, 0), Other->GetControlRotation());
            Ball->ResetBall(Keeper->GetCarryLocation());
            bPenaltyShotActive = false; PenaltyShotSecondsLeft = 0;
            PenaltyShooterActor.Reset(); PenaltyKeeperActor.Reset();
            PenaltySavedRiders.Empty(); PenaltySavedViews.Empty();
            SyncRules();
            PenaltyShotStatus += Rules->status == BB::Status::Review
                ? TEXT(" | restart served; result under review - awaiting certification")
                : TEXT(" | restart served; host ENTER to resume");
            Say(PenaltyShotStatus); ForceNetUpdate(); return;
        }
        if (PenaltyResultDelay >= 1.5f)
            PenaltyShotStatus = TEXT("Defending restart remains due - eligible Netminder required");
    }
    SyncRules();
    if (bPenaltyShotActive) Status = bFreeShot ? TEXT("FREE SHOT") : TEXT("PENALTY SHOT");
    ForceNetUpdate();
}

TArray<int32> ABBMatchState::DevelopmentGetPenaltyShotState() const
{
#if !UE_BUILD_SHIPPING
    if (HasAuthority() && Rules && GetWorld() && GetWorld()->WorldType == EWorldType::PIE)
    {
        const auto& Shot = Rules->penalty_shot;
        const bool Valid = Shot.penalty_id > 0 && Shot.penalty_id <= static_cast<int32>(Rules->penalties.size());
        return {Shot.penalty_id, static_cast<int32>(Shot.stage), static_cast<int32>(Shot.outcome), Shot.ball,
            Shot.shooter, Shot.netminder, Valid && Rules->penalties[Shot.penalty_id - 1].pending ? 1 : 0,
            static_cast<int32>(Shot.awarded_points), Valid ? Rules->penalties[Shot.penalty_id - 1].player : -1};
    }
#endif
    return {};
}

double ABBMatchState::DevelopmentGetRemovalSeconds(int32 Slot) const
{
#if !UE_BUILD_SHIPPING
    if (HasAuthority() && Rules && Slot >= 0 && Slot < 16 && GetWorld() && GetWorld()->WorldType == EWorldType::PIE)
    {
        const auto& Player = Rules->players[Slot];
        if (Player.ejected || Player.donnybrook_excluded) return -2;
        return Player.removed_until >= 0 ? FMath::Max(0.0, (Player.removed_until - Rules->now_ms) / 1000.0) : 0;
    }
#endif
    return -1;
}

TArray<double> ABBMatchState::DevelopmentGetPenaltyShotTiming() const
{
#if !UE_BUILD_SHIPPING
    if (HasAuthority() && Rules && GetWorld() && GetWorld()->WorldType == EWorldType::PIE)
    {
        const double Elapsed = Rules->penalty_shot.elapsed_ms + PenaltyShotMillisecondCarry;
        return {Elapsed, static_cast<double>(Rules->config.penalty_shot_ms),
            FMath::Max(0.0, Rules->config.penalty_shot_ms - Elapsed)};
    }
#endif
    return {};
}

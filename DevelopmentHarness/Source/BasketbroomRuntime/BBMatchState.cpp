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
constexpr int32 Roles[8] = {0, 1, 1, 2, 3, 4, 4, 5};
FVector StartLocation(int32 Slot, bool bDonnybrook = false, float CapsuleRadius = 34.f)
{
    const int32 Local = Slot % 8;
    const float Sign = Slot < 8 ? -1.f : 1.f;
    // The whole capsule starts behind its own quarter line. Donnybrook
    // instead lines every available rider up behind its own goal plane.
    const float Clearance = CapsuleRadius + 12.f;
    if (bDonnybrook)
        return FVector(Sign * (BBArena::GoalPlaneX + Clearance),
            (Local - 3.5f) * 650.f * BBArena::LinearScale,
            (1400.f + (Local % 2) * 180.f) * BBArena::LinearScale);
    if (Local == 0) return FVector(Sign * (BBArena::GoalPlaneX - 1000.8), 0, BBArena::LargeHoopHeight);
    // Provisional tactical spacing staggers the second row so teammates do not
    // obstruct the first-person view while waiting for the opening horn.
    const int32 Row = (Local - 1) / 3;
    return FVector(Sign * (BBArena::GoalPlaneX / 2.0 + Clearance + Row * 650.f * BBArena::LinearScale),
                   (Local == 7 ? 0.f : ((Local - 1) % 3 - 1) * 950.f + (Row == 1 ? 450.f : 0.f)) * BBArena::LinearScale,
                   (Local == 7 ? 2800.f : 1400.f + (Local % 3) * 350.f) * BBArena::LinearScale);
}

FVector OpeningBallLocation(int32 Index)
{
    // Bible 5.2 supplies the lateral marks and Snipe altitude. The 1500cm
    // scoring/Bludger launch altitude is a provisional implementation choice;
    // it is not a stated rule. Snitch uses the 100ft center launch in section 6.
    const FVector Marks[] = {FVector(0,0,1500), FVector(0,-1066.8,1500), FVector(0,1066.8,1500),
        FVector(0,0,670.56), FVector(0,0,3048), FVector(0,-2133.6,1500), FVector(0,2133.6,1500)};
    return Marks[FMath::Clamp(Index, 0, 6)];
}

FVector CrownRestartLocation(const BB::Ball& Ball)
{
    // A safe mark directly below the recorded exit. The 4m vertical clearance
    // and 3m edge clearance are provisional physical implementation margins.
    // The carry point projects 175cm ahead plus the scoring ball's 65cm radius.
    const double LimitX = BBArena::HalfLength - 300.0, LimitY = BBArena::HalfWidth - 300.0;
    return BBArena::ClampSphere(FVector(
        FMath::Clamp(Ball.crown_mark[0] * 30.48, -LimitX, LimitX),
        FMath::Clamp(Ball.crown_mark[1] * 30.48, -LimitY, LimitY),
        FMath::Clamp(Ball.crown_mark[2] * 30.48 - 400.0, 250.0, BBArena::EaveHeight - 400.0)), 250.0);
}

void PlaceRider(ABBRiderCharacter* Rider, const FVector& Location, float Yaw)
{
    Rider->GetCharacterMovement()->StopMovementImmediately();
    Rider->ConsumeMovementInputVector();
    Rider->SetActorLocationAndRotation(Location, FRotator(0, Yaw, 0), false, nullptr, ETeleportType::TeleportPhysics);
    if (AController* Controller = Rider->GetController())
    {
        Controller->SetControlRotation(FRotator(0, Yaw, 0));
        if (APlayerController* Player = Cast<APlayerController>(Controller))
            Player->ClientSetRotation(FRotator(0, Yaw, 0), true);
    }
    Rider->ForceNetUpdate();
}

void ClearCrownRestartSpace(ABBRiderCharacter* Rider, const FVector& Mark)
{
    const FVector Previous = Rider->GetActorLocation();
    const float Radius = Rider->GetCapsuleComponent()->GetScaledCapsuleRadius();
    const float HalfHeight = Rider->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
    FVector Direction = (Previous - Mark).GetSafeNormal2D(UE_SMALL_NUMBER, FVector::ForwardVector);
    auto PointAlong = [&Mark, &Previous](const FVector& Along)
    { return FVector(Mark.X + Along.X * 450.0, Mark.Y + Along.Y * 450.0, Previous.Z); };
    auto Inside = [Radius, HalfHeight](const FVector& Point)
    { return BBArena::ContainsCapsule(Point, Radius, HalfHeight); };
    FVector Destination = PointAlong(Direction);
    if (!Inside(Destination)) Destination = PointAlong(-Direction);
    if (!Inside(Destination)) Destination = PointAlong((-Mark).GetSafeNormal2D(UE_SMALL_NUMBER, FVector::ForwardVector));
    Destination = BBArena::ClampCapsule(Destination, Radius, HalfHeight);
    // Preserve aim and altitude wherever roof clearance permits. Clamping at
    // a sloped face can only lower the rider, never push a held ball outside.
    Rider->GetCharacterMovement()->StopMovementImmediately();
    Rider->ConsumeMovementInputVector();
    Rider->SetActorLocation(Destination, false, nullptr, ETeleportType::TeleportPhysics);
    Rider->ForceNetUpdate();
}
}
ABBMatchState::ABBMatchState()
{
    PrimaryActorTick.bCanEverTick = true;
    SetNetUpdateFrequency(20.f);
    bAlwaysRelevant = true;
}
ABBMatchState::~ABBMatchState() = default;
void ABBMatchState::BeginPlay()
{
    Super::BeginPlay();
    if (!HasAuthority()) return;
    bPractice = GetWorld()->URL.HasOption(TEXT("Practice"));
    bBloodbroom = GetWorld()->URL.HasOption(TEXT("Bloodbroom"));
    ResetMatchRules();
    for (int32 I = 0; I < 7; ++I)
    {
        FTransform Transform(FRotator::ZeroRotator, OpeningBallLocation(I));
        ABBBall* Ball = GetWorld()->SpawnActorDeferred<ABBBall>(ABBBall::StaticClass(), Transform, this, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (!Ball)
        {
            UE_LOG(LogTemp, Error, TEXT("Basketbroom could not spawn ball %d; match startup aborted"), I);
            Rules.reset();
            Say(TEXT("Match could not initialize its equipment."));
            return;
        }
        Ball->BallIndex = I;
        UGameplayStatics::FinishSpawningActor(Ball, Transform);
        Balls.Add(Ball);
    }
    FillRoster();
    SyncRules();
    Status = TEXT("LOBBY");
}
void ABBMatchState::ResetMatchRules()
{
    if (!HasAuthority()) return;
    BB::Config Config;
    if (bPractice) { Config.quarter_ms = 180000; Config.snitch_release_ms = 60000; Config.overtime_ms = 120000; }
    Rules = std::make_unique<BB::Match>(Config);
    if (!Combat) Combat = std::make_unique<BB::CombatPolicy>();
    Combat->reset_match(bBloodbroom ? BB::CombatVariant::Bloodbroom : BB::CombatVariant::Regulation);
    Combat->set_live(false);
    CombatOccupants.Empty(); CombatPhase = -1;
    ConductFoulCount = 0; LastConductCall.Empty();
    bConductReviewPending = false; ConductReviewStatus.Empty();
    bModerateAdvantageArmed = bConductAdvantageLive = false; ConductEvidence.Empty(); LastServedConductEvidence = {};
    ConductOffender = ConductVictimTeam = ConductRestartBall = -1;
    LastConductAttack = 0; LastConductViolations = 0;
    ConductBall = ConductVictimSlot = -1;
    ResetPenaltyPresentation();
    Rules->pause("pregame selection");
    MillisecondCarry = 0;
    BotAccumulator = ReviewDelay = 0;
    LastLogIndex = 0;
    PendingPoints.clear();
    PendingFlightScorers.Empty(); FlightRewardSequence = 0;
    bInitialized = false;
    bLive = false;
    ResetContextualSpells();
    for (ABBRiderCharacter* R : Riders)
        if (IsValid(R))
        {
            R->ResetSportSpellState();
            R->ResetFlightBoost();
        }
}
void ABBMatchState::ResetOpeningLayout()
{
    if (!HasAuthority() || !Rules) return;
    const bool bDonnybrook = Rules->phase == BB::Phase::Donnybrook;
    for (ABBRiderCharacter* R : Riders)
    {
        if (!IsValid(R) || R->RosterIndex < 0 || R->RosterIndex >= 16) continue;
        const auto& Player = Rules->players[R->RosterIndex];
        if (Player.ejected || Player.donnybrook_excluded || Player.removed_until >= 0) continue;
        R->bInteractHeld = false;
        PlaceRider(R, StartLocation(R->RosterIndex, bDonnybrook, R->GetCapsuleComponent()->GetScaledCapsuleRadius()),
                   R->TeamIndex ? 180.f : 0.f);
    }
    for (ABBBall* B : Balls)
    {
        if (!IsValid(B)) continue;
        // A delayed Crown award takes priority over the neutral period layout.
        if (Rules->balls[B->BallIndex].crown_restart_penalty > 0
            || Rules->balls[B->BallIndex].conduct_restart_penalty > 0) continue;
        B->Home = OpeningBallLocation(B->BallIndex);
        B->LastTouchTeam = -1;
        B->ChaseTime = B->BallIndex * 2.4f;
        B->ResetBall(B->Home);
    }
}
void ABBMatchState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABBMatchState, TealScore); DOREPLIFETIME(ABBMatchState, CopperScore);
    DOREPLIFETIME(ABBMatchState, Quarter); DOREPLIFETIME(ABBMatchState, SecondsLeft);
    DOREPLIFETIME(ABBMatchState, Phase); DOREPLIFETIME(ABBMatchState, Status);
    DOREPLIFETIME(ABBMatchState, Announcement); DOREPLIFETIME(ABBMatchState, bPractice);
    DOREPLIFETIME(ABBMatchState, bLive); DOREPLIFETIME(ABBMatchState, Winner);
    DOREPLIFETIME(ABBMatchState, LiveSeconds);
    DOREPLIFETIME(ABBMatchState, PendingPenaltyCount); DOREPLIFETIME(ABBMatchState, PendingPenaltySummary);
    DOREPLIFETIME(ABBMatchState, bBloodbroom); DOREPLIFETIME(ABBMatchState, ConductFoulCount);
    DOREPLIFETIME(ABBMatchState, LastConductCall); DOREPLIFETIME(ABBMatchState, bConductReviewPending);
    DOREPLIFETIME(ABBMatchState, ConductReviewStatus);
    DOREPLIFETIME(ABBMatchState, bModerateAdvantageArmed); DOREPLIFETIME(ABBMatchState, bConductAdvantageLive);
    DOREPLIFETIME(ABBMatchState, bPenaltyShotActive);
    DOREPLIFETIME(ABBMatchState, bFreeShot); DOREPLIFETIME(ABBMatchState, bPenaltyShotReleased);
    DOREPLIFETIME(ABBMatchState, PenaltyShotSecondsLeft); DOREPLIFETIME(ABBMatchState, PenaltyShotBall);
    DOREPLIFETIME(ABBMatchState, PenaltyShooterSlot); DOREPLIFETIME(ABBMatchState, PenaltyKeeperSlot);
    DOREPLIFETIME(ABBMatchState, PenaltyShotStatus);
}
FString ABBMatchState::PositionName(int32 Position)
{
    const TCHAR* Names[] = {TEXT("Netminder"), TEXT("Chaser"), TEXT("Trapper"), TEXT("Ranger"), TEXT("Hurleyback"), TEXT("Scout")};
    return Names[FMath::Clamp(Position, 0, 5)];
}
void ABBMatchState::Say(const FString& Text) { Announcement = Text; ForceNetUpdate(); }
void ABBMatchState::AssignHuman(ABBRiderCharacter* Rider)
{
    if (!HasAuthority() || !IsValid(Rider)) return;
    Riders.RemoveAll([](const ABBRiderCharacter* R) { return !IsValid(R); });
    if (Riders.Contains(Rider) && Rider->RosterIndex >= 0 && Rider->RosterIndex < 16) return;
    int32 Counts[2] = {0, 0};
    std::array<bool, 16> Occupied{};
    for (ABBRiderCharacter* R : Riders)
    {
        if (!IsValid(R) || R == Rider || R->RosterIndex < 0 || R->RosterIndex >= 16) continue;
        const bool bHuman = R->IsPlayerControlled();
        if (bHuman) ++Counts[FMath::Clamp(R->TeamIndex,0,1)];
        Occupied[R->RosterIndex] = Occupied[R->RosterIndex] || bHuman || R->HasSpellMovementLock();
    }
    for (const FConductEvidence& Evidence : ConductEvidence)
        if (Evidence.Offender >= 0 && Evidence.Offender < 16) Occupied[Evidence.Offender] = true;
    if (bPenaltyShotActive)
    {
        if (PenaltyShooterSlot >= 0 && PenaltyShooterSlot < 16) Occupied[PenaltyShooterSlot] = true;
        if (PenaltyKeeperSlot >= 0 && PenaltyKeeperSlot < 16) Occupied[PenaltyKeeperSlot] = true;
    }
    const int32 Team = Counts[0] <= Counts[1] ? 0 : 1;
    // The first local login can precede GameState::BeginPlay. There cannot be
    // historical penalties yet; use the clean default roster for that one path.
    const BB::Match InitialRules;
    const BB::Match* AdmissionRules = Rules ? Rules.get() : (HasActorBegunPlay() ? nullptr : &InitialRules);
    const int32 Slot = AdmissionRules ? BB::SelectAdmissionSlot(*AdmissionRules, Occupied, Team) : INDEX_NONE;
    if (Slot == INDEX_NONE)
    {
        if (APlayerController* Player = Cast<APlayerController>(Rider->GetController()))
        {
            Player->StartSpectatingOnly();
            Player->ClientMessage(TEXT("Spectating: no unrestricted player position is available. Rejoin after a position clears or the next match starts."));
        }
        UE_LOG(LogTemp, Display, TEXT("Basketbroom newcomer is spectating: no unrestricted roster slot is available."));
        Riders.Remove(Rider);
        Rider->Destroy();
        return;
    }
    for (int32 I = Riders.Num() - 1; I >= 0; --I)
    {
        ABBRiderCharacter* Old = Riders[I];
        if (IsValid(Old) && Old != Rider && Old->RosterIndex == Slot)
        {
            Release(Old, FVector::ZeroVector);
            Riders.RemoveAt(I);
            Old->Destroy();
        }
    }
    Rider->RosterIndex = Slot; Rider->TeamIndex = Slot / 8; Rider->Position = Roles[Slot % 8];
    Riders.AddUnique(Rider);
    PlaceRider(Rider, StartLocation(Slot), Slot < 8 ? 0.f : 180.f);
}
void ABBMatchState::FillRoster()
{
    if (!HasAuthority()) return;
    Riders.RemoveAll([](const ABBRiderCharacter* R) { return !IsValid(R); });
    for (int32 I = 0; I < 16; ++I)
    {
        bool Found = false;
        for (ABBRiderCharacter* R : Riders) Found |= R->RosterIndex == I;
        if (Found) continue;
        FActorSpawnParameters Params; Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        ABBRiderCharacter* R = GetWorld()->SpawnActor<ABBRiderCharacter>(StartLocation(I), FRotator(0,I < 8 ? 0:180,0), Params);
        if (!R) { UE_LOG(LogTemp, Error, TEXT("Could not fill roster slot %d"), I); continue; }
        R->TeamIndex = I / 8; R->RosterIndex = I; R->Position = Roles[I % 8];
        R->GetCharacterMovement()->bRunPhysicsWithNoController = true;
        Riders.Add(R);
    }
}
bool ABBMatchState::CanInteract(const ABBRiderCharacter* R, const ABBBall* B) const
{
    if (!HasAuthority() || !Rules || !bLive || !IsValid(R) || !IsValid(B) || !Riders.Contains(R) || !Balls.Contains(B)
        || !B->bActive || B->BallIndex < 0 || B->BallIndex >= 7 || !Rules->balls[B->BallIndex].live
        || R->HasSpellMovementLock() || R->RosterIndex < 0 || R->RosterIndex >= 16) return false;
    if (!Rules->eligible(R->RosterIndex, B->BallIndex)) return false;
    const UCapsuleComponent* Capsule = R->GetCapsuleComponent();
    if (!BBArena::ContainsCapsule(R->GetActorLocation(), Capsule->GetScaledCapsuleRadius(),
                                Capsule->GetScaledCapsuleHalfHeight())
        || !BBArena::ContainsSphere(B->GetActorLocation(), B->Radius())) return false;
    for (const ABBBall* Other : Balls) if (IsValid(Other) && Other->Holder == R && Other != B) return false;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BasketbroomInteraction), false, R);
    Query.AddIgnoredActor(B);
    for (ABBSpellArenaObject* Object : SpellWorkshops) if (IsValid(Object)) Query.AddIgnoredActor(Object);
    FHitResult Hit;
    if (GetWorld()->LineTraceSingleByChannel(Hit, R->GetActorLocation(), B->GetActorLocation(), ECC_Visibility, Query)) return false;
    return true;
}
bool ABBMatchState::TryPossess(ABBRiderCharacter* R, ABBBall* B)
{
    if (!CanInteract(R,B) || B->IsChase() || B->Holder || B->Cooldown > 0 || FVector::DistSquared(R->GetActorLocation(),B->GetActorLocation()) > FMath::Square(425.f)) return false;
    if (!Rules->possess(R->RosterIndex, B->BallIndex, B->IsBludger())) return false;
    B->Holder = R; B->LastTouchTeam = R->TeamIndex; B->FlightVelocity = FVector::ZeroVector;
    B->DistanceSinceReleaseCm = 0;
    B->RecentThrower.Reset();
    B->ThrowerIgnoreRemaining = B->ImpactCooldown = 0;
    B->ForceNetUpdate();
    return true;
}
bool ABBMatchState::TryCatch(ABBRiderCharacter* R, ABBBall* B)
{
    if (!CanInteract(R,B) || !B->IsChase() || B->CapturingRider != R || !R->bInteractHeld || B->CaptureProgress < 1.f || FVector::DistSquared(R->GetActorLocation(),B->GetActorLocation()) > FMath::Square(380.f)) return false;
    for (const auto& P : PendingPoints) if (P.ball == B->BallIndex || P.player == R->RosterIndex) return false;
    BB::PointEvent Event; Event.kind = BB::EventKind::Catch; Event.ball = B->BallIndex; Event.player = R->RosterIndex;
    Event.secure_ms = Rules->config.catch_control_ms; Event.by_hand = true; Event.mounted = true;
    const FVector P = R->GetActorLocation();
    const UCapsuleComponent* Capsule = R->GetCapsuleComponent();
    Event.inside_envelope = BBArena::ContainsCapsule(P, Capsule->GetScaledCapsuleRadius(), Capsule->GetScaledCapsuleHalfHeight())
        && BBArena::ContainsSphere(B->GetActorLocation(), B->Radius());
    if (!Event.inside_envelope) return false;
    PendingPoints.push_back(Event);
    PendingFlightScorers.Add(B->BallIndex, R);
    return true;
}
void ABBMatchState::Goal(ABBBall* B, int32 Team, double FlightStepFraction)
{
    if (HasAuthority() && bPenaltyShotActive)
    {
        if (!IsPenaltyBallActive(B) || !bPenaltyShotReleased || !Rules
            || !ConsumePenaltyFlightTime(FlightStepFraction)) return;
        BB::PointEvent Event; Event.ball = B->BallIndex; Event.attacking_team = Team;
        Event.player = PenaltyShooterSlot; Event.hoop = B->BallIndex == 0 ? BB::Hoop::Large : BB::Hoop::Small;
        Event.entire_ball = true; Event.forward = true;
        if (Team == Rules->penalty_shot.attacking_team)
            FinishPenaltyShot(BB::PenaltyShotOutcome::Goal, TEXT("PENALTY SHOT SCORED"), Event);
        else FinishPenaltyShot(BB::PenaltyShotOutcome::Miss, TEXT("PENALTY SHOT MISSED - wrong goal"));
        return;
    }
    if (!HasAuthority() || !Rules || !bLive || !IsValid(B) || !Balls.Contains(B) || Team < 0 || Team > 1
        || B->BallIndex < 0 || B->BallIndex > 2 || !Rules->balls[B->BallIndex].live || B->Holder || !B->bActive) return;
    for (const auto& P : PendingPoints) if (P.ball == B->BallIndex) return;
    BB::PointEvent Event; Event.ball = B->BallIndex; Event.attacking_team = Team;
    Event.hoop = B->BallIndex == 0 ? BB::Hoop::Large : BB::Hoop::Small;
    Event.entire_ball = true; Event.forward = true;
    PendingPoints.push_back(Event);
    PendingFlightScorers.Add(B->BallIndex, B->RecentThrower);
    B->FlightVelocity = FVector::ZeroVector; B->Cooldown = .25f;
}
void ABBMatchState::Release(ABBRiderCharacter* R, FVector Aim, bool bDeferConductBoundary)
{
    if (bPenaltyShotActive) { ReleasePenaltyShot(R, Aim); return; }
    if (!HasAuthority() || !Rules || !IsValid(R) || Aim.ContainsNaN()) return;
    for (ABBBall* B : Balls)
    {
        if (B->Holder != R) continue;
        if (!Rules->release(R->RosterIndex, B->BallIndex, true)) continue;
        B->Holder = nullptr;
        B->LastLocation = R->GetCarryLocation();
        B->SetActorLocation(B->LastLocation);
        B->FlightVelocity = Aim.IsNearlyZero() ? R->GetVelocity() : Aim.GetSafeNormal() * (B->IsBludger() ? 5000.f : 4400.f) + R->GetVelocity() * .4f;
        B->DistanceSinceReleaseCm = 0;
        // A forced zero-aim drop is not a deliberate propulsive act.
        B->RecentThrower = Aim.IsNearlyZero() ? nullptr : R;
        B->bFlightBoostRewarded = false;
        B->ThrowerIgnoreRemaining = .15f;
        B->ImpactCooldown = 0;
        B->Cooldown = .3f;
        B->ForceNetUpdate();
    }
    if (!bDeferConductBoundary) TickConductAdvantage();
}
void ABBMatchState::ReleaseDepartedSlot(int32 RosterIndex)
{
    if (!HasAuthority() || !Rules || RosterIndex < 0 || RosterIndex >= 16) return;
    Riders.RemoveAll([](const ABBRiderCharacter* R) { return !IsValid(R); });
    for (ABBBall* B : Balls)
    {
        if (!IsValid(B) || B->BallIndex < 0 || B->BallIndex >= 7
            || Rules->balls[B->BallIndex].controller != RosterIndex) continue;
        if (!Rules->release(RosterIndex, B->BallIndex, true)) continue;
        // The last authoritative ball transform is safe even after its former
        // rider has been destroyed. This is a neutral drop, not a new throw.
        B->Holder = nullptr;
        B->FlightVelocity = FVector::ZeroVector;
        B->DistanceSinceReleaseCm = 0;
        B->RecentThrower = nullptr;
        B->ThrowerIgnoreRemaining = 0;
        B->ImpactCooldown = 0;
        B->Cooldown = .3f;
        B->ForceNetUpdate();
    }
    TickConductAdvantage(); SyncRules();
}
void ABBMatchState::ObserveBludgerFlight(ABBBall* B, BB::Contact Contact)
{
    if (!HasAuthority() || !Rules || !bLive || !IsValid(B) || !Balls.Contains(B)
        || !B->IsBludger() || B->BallIndex > 6 || B->Holder) return;
    const auto& State = Rules->balls[B->BallIndex];
    const auto& Hurley = Rules->hurleys[B->BallIndex - 5];
    if (!State.live || State.controller >= 0 || Hurley.individual_reset) return;
    const double DistanceFeet = B->DistanceSinceReleaseCm / 30.48;
    if (Contact == BB::Contact::None && DistanceFeet < Rules->config.self_toss_reset_distance_ft) return;
    // Contestability is established by the existing legal release policy.
    // Merely observing an arena collision must not invent that evidence.
    Rules->flight_evidence(B->BallIndex, DistanceFeet, Contact, Hurley.contestable);
}
double ABBMatchState::DevelopmentGetBludgerControlSeconds(int32 BallIndex) const
{
#if UE_BUILD_SHIPPING
    return -1;
#else
    if (!HasAuthority() || !GetWorld() || GetWorld()->WorldType != EWorldType::PIE
        || !Rules || BallIndex < 5 || BallIndex > 6 || Rules->balls[BallIndex].controller < 0) return -1;
    const auto& Hurley = Rules->hurleys[BallIndex - 5];
    return Hurley.individual_started < 0 ? -1 : (Rules->now_ms - Hurley.individual_started) / 1000.0;
#endif
}
TArray<int32> ABBMatchState::DevelopmentGetCrownPenaltyState(int32 BallIndex) const
{
    TArray<int32> State = {0, 0, 0, -1, -1, -1};
#if !UE_BUILD_SHIPPING
    if (HasAuthority() && GetWorld() && GetWorld()->WorldType == EWorldType::PIE && Rules)
        for (const auto& Penalty : Rules->penalties)
            if (Penalty.reason == "No Crown" && Penalty.ball == BallIndex)
            {
                ++State[0]; State[1] += Penalty.pending ? 1 : 0;
                State[2] += Penalty.crown_restoration_pending ? 1 : 0;
                State[3] = Penalty.player; State[4] = Penalty.crown_restoration_receiver;
                State[5] = Penalty.id;
            }
#endif
    return State;
}
void ABBMatchState::ChangePosition(ABBRiderCharacter* R, int32 NewPosition, int32 NewTeam)
{
    if (!HasAuthority() || !Rules || !IsValid(R) || NewPosition < 0 || NewPosition > 5 || NewTeam < 0 || NewTeam > 1) return;
    if (bLive) { Say(TEXT("Positions are locked during live play. Choose at the next stoppage.")); return; }
    if (bPenaltyShotActive) { Say(TEXT("Finish the shot before changing positions.")); return; }
    if (bConductReviewPending) { Say(TEXT("Resolve the BB-0 conduct call before changing positions.")); return; }
    if (Rules->status == BB::Status::Review || Rules->status == BB::Status::Complete) return;
    if (R->Position == NewPosition && R->TeamIndex == NewTeam) return;
    const auto& CurrentPlayer = Rules->players[R->RosterIndex];
    auto HasPendingPenalty = [this](int32 Slot)
    {
        for (const auto& Penalty : Rules->penalties)
            if (Penalty.player == Slot && (Penalty.pending || Penalty.crown_restoration_pending)) return true;
        return false;
    };
    if (CurrentPlayer.ejected || CurrentPlayer.donnybrook_excluded || CurrentPlayer.removed_until >= 0)
    { Say(TEXT("A removed player cannot change position to bypass a penalty.")); return; }
    if (HasPendingPenalty(R->RosterIndex)) { Say(TEXT("Resolve the pending penalty before changing positions.")); return; }
    ABBRiderCharacter* Swap = nullptr;
    for (ABBRiderCharacter* Other : Riders)
        if (IsValid(Other) && Other != R && Other->TeamIndex == NewTeam && Other->Position == NewPosition && !Other->IsPlayerControlled()
            && !Rules->players[Other->RosterIndex].ejected && !Rules->players[Other->RosterIndex].donnybrook_excluded
            && Rules->players[Other->RosterIndex].removed_until < 0 && !HasPendingPenalty(Other->RosterIndex)) { Swap = Other; break; }
    if (!Swap) { Say(TEXT("That position is occupied or currently restricted.")); return; }
    const int32 OldIndex = R->RosterIndex;
    R->RosterIndex = Swap->RosterIndex; Swap->RosterIndex = OldIndex;
    for (ABBRiderCharacter* Changed : {R, Swap})
    {
        Changed->TeamIndex = Changed->RosterIndex / 8;
        Changed->Position = Roles[Changed->RosterIndex % 8];
        Changed->bInteractHeld = false;
        PlaceRider(Changed, StartLocation(Changed->RosterIndex), Changed->TeamIndex ? 180.f : 0.f);
        if (ABBGameMode* GameMode = GetWorld()->GetAuthGameMode<ABBGameMode>())
            GameMode->TrackAssignedRider(Changed);
    }
    Say(FString::Printf(TEXT("%s selected %s. ENTER resumes play."), R->TeamIndex ? TEXT("Copper") : TEXT("Teal"), *PositionName(R->Position)));
}
void ABBMatchState::HandleAction(ABBRiderCharacter* R, int32 Action, int32 Value, FVector Aim)
{
    if (!HasAuthority() || !Rules || !IsValid(R) || !Riders.Contains(R) || R->RosterIndex < 0 || R->RosterIndex >= 16) return;
    if (bPenaltyShotActive)
    {
        if (Action == 1) ReleasePenaltyShot(R, Aim);
        else R->NotifySpellResult(TEXT("Shot: designated shooter throws once; no wandwork, pass or role change."));
        return;
    }
    if (Action == 2) { ChangePosition(R, Value, R->TeamIndex); return; }
    if (Action == 3) { ChangePosition(R, R->Position, Value); return; }
    if (Action == 8)
    {
        if (CanOfficiate(R) && !bInitialized && Status == TEXT("LOBBY"))
        {
            bBloodbroom = !bBloodbroom;
            Combat->reset_match(bBloodbroom ? BB::CombatVariant::Bloodbroom : BB::CombatVariant::Regulation);
            Combat->set_live(false);
            Say(bBloodbroom ? TEXT("BLOODBROOM - Unforgivables and headshots permitted. Other BB-0 rules apply.")
                           : TEXT("BB-0 - No Unforgivables, headshots, mobbing, double-taps or holding."));
        }
        return;
    }
    if (Action == 13)
    {
        if (!CanOfficiate(R) || bConductReviewPending || bPenaltyShotActive
            || Rules->status == BB::Status::Review || Rules->status == BB::Status::Complete) return;
        bModerateAdvantageArmed = !bModerateAdvantageArmed;
        Say(bModerateAdvantageArmed
            ? TEXT("REFEREE: next basic-cast mobbing may use Moderate advantage only if the victim keeps scoring possession without a disable. Other fouls stop immediately.")
            : TEXT("REFEREE: Moderate advantage preselection off."));
        ForceNetUpdate(); return;
    }
    if (Action >= 9 && Action <= 12) { ReviewConduct(R, Action); return; }
    if (Action == 4 || Action == 5)
    {
        // Listen-server period control belongs to the host. A dedicated server
        // delegates it to the first connected participant below.
        if (!CanOfficiate(R)) return;
        if (bConductReviewPending)
        {
            if (bConductAdvantageLive && Action == 5)
            {
                Rules->pause("host ended Moderate advantage"); TickConductAdvantage(); SyncRules(); return;
            }
            R->NotifySpellResult(TEXT("Resolve BB-0: F6 free shot, F7 possession, F8 shot + removal, F9 ejection."));
            return;
        }
        const bool bRematch = Rules->status == BB::Status::Complete && Action == 4;
        if (bRematch)
        {
            ResetMatchRules();
            FillRoster();
        }
        else if (Rules->status == BB::Status::Complete) return;
        if (Action == 5)
        {
            // Finish already observed goals/catches before stopping the clock.
            if (!PendingPoints.empty())
            {
                FlushPendingPointEvents();
            }
            if (Rules->pause("host requested official stoppage"))
                Say(TEXT("OFFICIAL STOPPAGE - choose positions with 1-6. Host: ENTER to resume."));
            SyncRules();
            return;
        }
        const bool bOpening = !bInitialized || Rules->status == BB::Status::QuarterBreak || Rules->status == BB::Status::PhaseBreak;
        if (!bLive && Rules->status != BB::Status::Review && Rules->resume())
        {
            if (bOpening) ResetOpeningLayout();
            bInitialized = true;
            SyncRules();
            Say(bRematch ? TEXT("REMATCH LIVE - new regulation match. Teams and positions retained.")
                         : TEXT("LIVE - play your position. Hold E within 3.8m to secure a chase ball."));
        }
        return;
    }
    if (!bLive || R->HasSpellMovementLock()) return;
    if (Action == 6 || Action == 7) { CastSpell(R, Action == 7 ? 1 : Value, Aim); return; }
    if (Action == 0)
    {
        ABBBall* Nearest = nullptr; float Distance = FMath::Square(425.f);
        for (ABBBall* B : Balls)
        {
            const float D = FVector::DistSquared(R->GetActorLocation(), B->GetActorLocation());
            if (!B->IsChase() && !B->Holder && CanInteract(R,B) && D < Distance) { Nearest = B; Distance = D; }
        }
        if (Nearest) TryPossess(R,Nearest);
    }
    if (Action == 1 && !Aim.ContainsNaN() && Aim.IsNormalized()) Release(R,Aim);
}
void ABBMatchState::Tick(float Dt)
{
    Super::Tick(Dt);
    if (!HasAuthority() || !Rules) return;
    if (bPenaltyShotActive) { TickPenaltyShot(Dt); return; }
    if (!PendingPoints.empty())
    {
        FlushPendingPointEvents();
    }
    TickConductAdvantage();
    if (Rules->status == BB::Status::Live)
    {
        MillisecondCarry += FMath::Max(0.f, Dt) * 1000.0;
        const BB::Millis Whole = static_cast<BB::Millis>(MillisecondCarry);
        MillisecondCarry -= Whole;
        const BB::Millis Consumed = Rules->advance(Whole);
        if (Consumed > 0)
        {
            Combat->advance(Consumed);
            TickSpells(Consumed / 1000.f);
        }
        for (int32 I=0; I<7; ++I)
        {
            auto& State = Rules->balls[I];
            ABBBall* B = Balls[I];
            if (State.dead_reason == "crown" && State.crown_deadline - Rules->now_ms <= 2000) { Rules->crown_return(I); B->FlightVelocity = FVector(0,0,-100); }
            if (State.dead_reason == "score" || State.dead_reason == "hurley_foul" || State.dead_reason == "penalty" || State.dead_reason == "crown_restart")
            {
                const bool bCrownRestart = State.dead_reason == "crown_restart";
                const FVector SearchMark = I == ConductRestartBall ? ConductMark : bCrownRestart ? CrownRestartLocation(State) : B->GetActorLocation();
                ABBRiderCharacter* Receiver = nullptr;
                double NearestDistance = TNumericLimits<double>::Max();
                for (ABBRiderCharacter* R : Riders)
                {
                    if (!IsValid(R) || R->TeamIndex != State.restart_team) continue;
                    if (I < 3 && !bCrownRestart && I != ConductRestartBall)
                    {
                        if (R->Position == 0 && !R->HasSpellMovementLock() && Rules->eligible(R->RosterIndex, I)) { Receiver = R; break; }
                        continue;
                    }
                    if (R->HasSpellMovementLock() || !Rules->eligible(R->RosterIndex, I)) continue;
                    bool bAlreadyHolding = false;
                    for (const ABBBall* Other : Balls)
                        if (IsValid(Other) && Other != B && Other->Holder == R) { bAlreadyHolding = true; break; }
                    if (bAlreadyHolding) continue;
                    const double Distance = FVector::DistSquared(R->GetActorLocation(), SearchMark);
                    if (Distance < NearestDistance || (Distance == NearestDistance
                        && Receiver && R->RosterIndex < Receiver->RosterIndex))
                    {
                        Receiver = R;
                        NearestDistance = Distance;
                    }
                }
                if (Receiver && Rules->restart(I,Receiver->RosterIndex))
                {
                    const bool bConductRestart = I == ConductRestartBall;
                    const FVector Mark = bConductRestart ? ConductMark : bCrownRestart ? SearchMark : FVector((Receiver->TeamIndex == 0 ? -1.f : 1.f) * (BBArena::GoalPlaneX - BBArena::RestartDistance), 0, I == 0 ? BBArena::LargeHoopHeight : BBArena::SmallHoopHeight);
                    PlaceRider(Receiver, Mark, Receiver->TeamIndex ? 180.f : 0.f);
                    B->ResetBall(Mark + FVector(0,0,80));
                    for (ABBRiderCharacter* Other : Riders)
                        if (Other->TeamIndex != Receiver->TeamIndex && FVector::DistSquared(Other->GetActorLocation(),Mark) < FMath::Square(396.24f))
                        {
                            if (bCrownRestart || bConductRestart) ClearCrownRestartSpace(Other, Mark);
                            else PlaceRider(Other, Mark + (Other->GetActorLocation()-Mark).GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector) * 450.f, Other->GetActorRotation().Yaw);
                        }
                    if (bConductRestart) ConductRestartBall = -1;
                }
            }
        }
    }
    // The rules engine explicitly requires a stoppage for administration.
    // Resolve before certification/resume, including penalties that caused it.
    if (Rules->status != BB::Status::Live)
        for (auto& Penalty : Rules->penalties)
            if (Penalty.reason == "No Crown" && Penalty.crown_restoration_pending)
            {
                if (Rules->prepare_crown_restart(Penalty.id)
                    && Rules->balls[Penalty.ball].crown_restart_penalty == Penalty.id)
                    Balls[Penalty.ball]->ResetBall(CrownRestartLocation(Rules->balls[Penalty.ball]) + FVector(0,0,80));
            }
            else if (Penalty.pending && !IsUnreviewedConductPenalty(Penalty.id) && Penalty.severity != BB::Severity::Catastrophic
                && Penalty.severity != BB::Severity::Serious)
            {
                bool bQueuedConductAward = false;
                for (const auto& Ball : Rules->balls) bQueuedConductAward |= Ball.conduct_restart_penalty == Penalty.id;
                if (!bQueuedConductAward) Rules->resolve_penalty(Penalty.id,"automatic rules enforcement",true);
            }
    if (Rules->status == BB::Status::Review && !bConductReviewPending)
    {
        ReviewDelay += Dt;
        if (ReviewDelay >= 2.f) { Rules->certify(); ReviewDelay = 0; }
    }
    SyncRules();
    if (bLive) UpdateBots(Dt);
    else for (ABBRiderCharacter* R : Riders)
        if (IsValid(R) && !R->IsPlayerControlled())
        {
            R->bInteractHeld = false;
            R->ConsumeMovementInputVector();
            R->GetCharacterMovement()->StopMovementImmediately();
        }
}
void ABBMatchState::SyncRules()
{
    if (!Rules) return;
    TealScore = static_cast<int32>(Rules->scores[0]); CopperScore = static_cast<int32>(Rules->scores[1]);
    const bool bWasLive = bLive;
    Quarter = Rules->quarter; Winner = Rules->winner; bLive = Rules->status == BB::Status::Live;
    SyncCombatRoster();
    if (bWasLive && !bLive)
        for (ABBBall* B : Balls) if (IsValid(B)) B->RecentThrower.Reset();
    PendingPenaltyCount = 0; PendingPenaltySummary.Empty();
    for (const auto& Penalty : Rules->penalties)
        if (Penalty.pending || Penalty.crown_restoration_pending)
        {
            ++PendingPenaltyCount;
            if (PendingPenaltySummary.IsEmpty())
            {
                const int32 Team = Rules->players[Penalty.player].team;
                PendingPenaltySummary = FString::Printf(TEXT("%s | %s %s | %s"),
                    UTF8_TO_TCHAR(Penalty.reason.c_str()), Team == 0 ? TEXT("TEAL") : TEXT("COPPER"),
                    *PositionName(static_cast<int32>(Rules->players[Penalty.player].role)),
                    Penalty.pending ? TEXT("PENDING STOPPAGE") : TEXT("RESTART DUE"));
            }
        }
    LiveSeconds = Rules->now_ms / 1000.f;
    Phase = Rules->phase == BB::Phase::Regulation ? TEXT("REGULATION") : Rules->phase == BB::Phase::Overtime ? TEXT("OVERTIME") : TEXT("DONNYBROOK");
    SecondsLeft = Rules->phase == BB::Phase::Donnybrook ? 0.f : FMath::Max(0.f, (Rules->phase == BB::Phase::Regulation ? Rules->config.quarter_ms : Rules->config.overtime_ms) / 1000.f - Rules->period_elapsed_ms / 1000.f);
    const TCHAR* Labels[] = {TEXT("LIVE"),TEXT("STOPPAGE"),TEXT("QUARTER BREAK"),TEXT("PHASE BREAK"),TEXT("CERTIFYING RESULT"),TEXT("FINAL")};
    Status = bInitialized ? Labels[static_cast<int>(Rules->status)] : TEXT("LOBBY");
    for (int32 I=0; I<Balls.Num(); ++I)
    {
        ABBBall* B = Balls[I]; const auto& S = Rules->balls[I];
        const bool WasActive = B->bActive;
        // At stoppages, keep active equipment visible for orientation.
        B->bActive = S.phase_active && (S.live || S.dead_reason == "stoppage"
            || (bPenaltyShotActive && I == PenaltyShotBall));
        B->ReturnIn = FMath::Max(0.f, S.timeout_until >= 0 ? (S.timeout_until-Rules->now_ms)/1000.f : S.dead_reason == "scheduled_release" ? (Rules->config.snitch_release_ms-Rules->now_ms)/1000.f : 0.f);
        B->BallStatus = UTF8_TO_TCHAR(S.dead_reason.c_str());
        B->Holder = nullptr;
        for (ABBRiderCharacter* R : Riders) if (R->RosterIndex == S.controller) B->Holder = R;
        if (WasActive != B->bActive)
        {
            if (B->bActive && B->IsChase()) B->ResetBall(B->Home);
            B->OnRep_Appearance(); B->ForceNetUpdate();
        }
    }
    for (ABBRiderCharacter* R : Riders)
    {
        if (!IsValid(R) || R->RosterIndex < 0 || R->RosterIndex >= 16) continue;
        const auto& P = Rules->players[R->RosterIndex];
        if (P.ejected || P.donnybrook_excluded || P.removed_until >= 0)
        {
            R->StunRemaining = 1.f;
            const FVector PenaltyBox((R->TeamIndex == 0 ? -1.0 : 1.0) * (BBArena::HalfLength + 349.2), 0, 600);
            if (FVector::DistSquared(R->GetActorLocation(), PenaltyBox) > 2500.f)
                PlaceRider(R, PenaltyBox, R->TeamIndex ? 180.f : 0.f);
        }
    }
    while (LastLogIndex < Rules->log.size())
    {
        const auto& Log = Rules->log[LastLogIndex++];
        if (Log.kind == "quarter_horn" || Log.kind == "stoppage" || Log.kind == "phase_transition") Say(TEXT("Stoppage - change positions with 1-6. Host presses ENTER to resume."));
        if (Log.kind == "snipe_warning") Say(TEXT("SNIPE RETURNS IN 10 SECONDS"));
        if (Log.kind == "snitch_release") Say(TEXT("THE GOLDEN SNITCH IS LIVE - Rangers and Scouts may capture"));
        if (Log.kind == "hurley_warning") Say(TEXT("HURLEY WARNING - release before 3 seconds"));
        if (Log.kind == "removal_expired")
            for (ABBRiderCharacter* R : Riders)
                if (IsValid(R) && R->RosterIndex == Log.player)
                {
                    R->StunRemaining = 0.f;
                    PlaceRider(R, StartLocation(R->RosterIndex), R->TeamIndex ? 180.f : 0.f);
                }
    }
    if (Winner >= 0)
    {
        const FString Result = FString::Printf(TEXT("%s WINS  |  %d - %d  |  result certified"), Winner == 0 ? TEXT("TEAL") : TEXT("COPPER"), TealScore, CopperScore);
        if (Announcement != Result) Say(Result);
    }
}
void ABBMatchState::UpdateBots(float Dt)
{
    for (ABBRiderCharacter* R : Riders)
    {
        if (!bLive) return;
        if (!IsValid(R) || R->IsPlayerControlled() || R->HasSpellMovementLock()) continue;
        ABBBall* Held = nullptr; for (ABBBall* B : Balls) if (B->Holder == R) Held = B;
        FVector Target = StartLocation(R->RosterIndex);
        R->bInteractHeld = false;
        if (Held)
        {
            float Sign = R->TeamIndex == 0 ? 1.f : -1.f;
            FVector GoalMark(Sign * (BBArena::GoalPlaneX + 99.2),
                Held->BallIndex == 0 ? ((R->RosterIndex % 3)-1) * BBArena::HoopSpacing : 0.0,
                Held->BallIndex == 0 ? BBArena::LargeHoopHeight : BBArena::SmallHoopHeight);
            Target = GoalMark - FVector(Sign * 2100.f,0,0);
            if (Held->IsBludger())
            {
                for (ABBRiderCharacter* Enemy : Riders) if (Enemy->TeamIndex != R->TeamIndex && !Enemy->IsConcealedFrom(R)) { GoalMark = Enemy->GetActorLocation(); break; }
                Release(R,(GoalMark-R->GetCarryLocation()).GetSafeNormal());
            }
            else if (R->Position == 0 || FVector::DistSquared(R->GetActorLocation(), Target) < FMath::Square(500.f))
            {
                const auto& BallRule = Rules->balls[Held->BallIndex];
                if (BallRule.protection_until < 0 || Rules->now_ms >= BallRule.protection_until)
                {
                    if (R->Position == 0) GoalMark = BBArena::ScaleLayout(FVector(Sign * 1000, (R->RosterIndex % 2 ? 900 : -900), 1800));
                    FVector To = GoalMark - R->GetCarryLocation(); const float Flight = To.Size()/4400.f;
                    To.Z += .5f * 380.f * Flight * Flight;
                    Release(R,To.GetSafeNormal());
                }
            }
        }
        else
        {
            ABBBall* Best = nullptr; float BestDist = TNumericLimits<float>::Max();
            for (ABBBall* B : Balls)
            {
                if (!B->bActive || B->Holder || !CanInteract(R,B)) continue;
                if (B->BallIndex == 4)
                {
                    // Give the release announcement time to be actionable and
                    // avoid a CPU catch that would knowingly concede the match.
                    if (Rules->phase == BB::Phase::Regulation && Rules->now_ms < Rules->config.snitch_release_ms + 10000) continue;
                    const auto CatchPoints = Rules->phase == BB::Phase::Regulation ? Rules->config.snitch_regulation_points : Rules->config.snitch_overtime_points;
                    if (Rules->scores[R->TeamIndex] + CatchPoints < Rules->scores[1 - R->TeamIndex]) continue;
                }
                const float D = FVector::DistSquared(B->GetActorLocation(),R->GetActorLocation());
                // Netminder guards its own end; other scoring positions share assignments.
                if (R->Position == 0 && FMath::Abs(B->GetActorLocation().X - Target.X) > 1700) continue;
                if (D < BestDist) { Best = B; BestDist = D; }
            }
            if (Best)
            {
                Target = Best->GetActorLocation();
                if (Best->IsChase()) R->bInteractHeld = true;
                else TryPossess(R,Best);
            }
        }
        FVector To = Target - R->GetActorLocation();
        if (To.Size() > 120) R->AddMovementInput(To.GetSafeNormal(), .7f);
        if (!To.IsNearlyZero()) R->SetActorRotation(FRotator(0,To.Rotation().Yaw,0));
    }
}


void ABBMatchState::PresentConductEvidence()
{
    bConductReviewPending = !ConductEvidence.IsEmpty();
    if (!bConductReviewPending) return;
    const FConductEvidence& Evidence = ConductEvidence[0];
    ConductOffender = Evidence.Offender; ConductVictimTeam = Evidence.VictimTeam;
    ConductVictimSlot = Evidence.VictimSlot; ConductBall = Evidence.Ball;
    LastConductAttack = Evidence.Attack; LastConductViolations = static_cast<int32>(Evidence.Violations);
    LastConductCall = Evidence.Reason; ConductFoulPoint = Evidence.FoulPoint;
    ConductMark = ConductFoulPoint;
    ConductMark.X = FMath::Clamp(ConductMark.X, -BBArena::GoalPlaneX + 500.8, BBArena::GoalPlaneX - 500.8);
    ConductMark.Y = FMath::Clamp(ConductMark.Y, -BBArena::HalfWidth + 500.4, BBArena::HalfWidth - 500.4);
    ConductMark.Z = FMath::Clamp(ConductMark.Z, 400.0, BBArena::EaveHeight - 406.24);
    ConductMark = BBArena::ClampSphere(ConductMark, 250.0);
    ConductReviewStatus = bConductAdvantageLive
        ? TEXT("MODERATE ADVANTAGE - offended team keeps scoring possession; original free-shot remedy remains due")
        : Evidence.PenaltyId > 0
            ? TEXT("MODERATE ADVANTAGE ENDED - F6 free shot / F7 possession; result remains provisional")
            : TEXT("PLAYTEST REFEREE - F6 free shot / F7 possession / F8 shot + removal / F9 ejection");
}
void ABBMatchState::CompleteConductEvidence()
{
    if (!ConductEvidence.IsEmpty())
    { LastServedConductEvidence = ConductEvidence[0]; ConductEvidence.RemoveAt(0); }
    PresentConductEvidence();
}
bool ABBMatchState::IsUnreviewedConductPenalty(int32 Id) const
{
    return ConductEvidence.ContainsByPredicate([Id](const FConductEvidence& Evidence) { return Evidence.PenaltyId == Id; });
}
void ABBMatchState::RegisterConductHit(ABBRiderCharacter* Offender, ABBRiderCharacter* Victim,
    int32 Spell, int32 AffectedBall, uint32 Violations, uint64 Attack, bool bHeadHit)
{
    if (!HasAuthority() || !Rules || !IsValid(Offender) || !IsValid(Victim) || Violations == 0 || Attack == 0) return;
    FConductEvidence Evidence;
    Evidence.Offender = Offender->RosterIndex; Evidence.VictimTeam = Victim->TeamIndex;
    Evidence.VictimSlot = Victim->RosterIndex; Evidence.Ball = AffectedBall; Evidence.Spell = Spell;
    Evidence.Violations = Violations; Evidence.Attack = Attack; Evidence.CommittedMs = Rules->now_ms;
    Evidence.FoulPoint = Victim->GetActorLocation(); Evidence.OriginalOffender = Offender; Evidence.OriginalVictim = Victim;
    TArray<FString> Reasons;
    if (Violations & static_cast<uint32>(BB::ConductViolation::Unforgivable)) Reasons.Add(TEXT("UNFORGIVABLE"));
    if (Violations & static_cast<uint32>(BB::ConductViolation::Headshot)) Reasons.Add(TEXT("HEADSHOT"));
    if (Violations & static_cast<uint32>(BB::ConductViolation::Mobbing)) Reasons.Add(TEXT("MOB ATTACK > 3"));
    if (Violations & static_cast<uint32>(BB::ConductViolation::DoubleTap)) Reasons.Add(TEXT("DOUBLE-TAP"));
    if (Violations & static_cast<uint32>(BB::ConductViolation::PhysicalHolding)) Reasons.Add(TEXT("PHYSICAL HOLDING"));
    Evidence.Reason = FString::Join(Reasons, TEXT(" + "));
    // The host preselects this one prospective Moderate ruling. It never
    // overrides a dangerous/additional violation or an impaired carrier.
    const bool bQualifies = bModerateAdvantageArmed && ConductEvidence.IsEmpty()
        && Rules->status == BB::Status::Live && Spell == 0 && !bHeadHit
        && Violations == static_cast<uint32>(BB::ConductViolation::Mobbing)
        && !Victim->HasSpellMovementLock() && Victim->ImpedimentRemaining <= 0 && Victim->Vitality > 50.f
        && AffectedBall >= 0 && AffectedBall <= 2 && Balls.IsValidIndex(AffectedBall)
        && Balls[AffectedBall]->Holder == Victim && Rules->balls[AffectedBall].controller == Victim->RosterIndex;
    bModerateAdvantageArmed = false;
    if (bQualifies)
        Evidence.PenaltyId = Rules->record_penalty(Evidence.Offender, TCHAR_TO_UTF8(*Evidence.Reason),
            BB::Severity::Moderate, Evidence.Ball, Evidence.CommittedMs);
    bConductAdvantageLive = bQualifies && Evidence.PenaltyId > 0;
    ConductEvidence.Add(Evidence); ++ConductFoulCount;
    PresentConductEvidence();
    if (!bConductAdvantageLive) Rules->pause("BB-0 conduct review after applied hit");
    SyncRules(); Say(bConductAdvantageLive ? ConductReviewStatus : TEXT("BB-0 FOUL: ") + Evidence.Reason + TEXT(" - hit applied; referee decision due."));
    UE_LOG(LogTemp, Display, TEXT("BB0 applied hit evidence: id=%llu caster=%d target=%d spell=%d flags=%u committed=%lld advantage=%d"),
        static_cast<unsigned long long>(Attack), Evidence.Offender, Evidence.VictimSlot, Spell, Violations,
        static_cast<long long>(Evidence.CommittedMs), bConductAdvantageLive ? 1 : 0);
}
void ABBMatchState::TickConductAdvantage()
{
    if (!bConductAdvantageLive || !Rules || ConductEvidence.IsEmpty()) return;
    const FConductEvidence& Evidence = ConductEvidence[0];
    bool bRetained = false;
    if (Evidence.Ball >= 0 && Evidence.Ball <= 2)
    {
        const BB::Ball& Ball = Rules->balls[Evidence.Ball];
        bRetained = Ball.live && Ball.controller >= 0 && Ball.controller < 16
            && Rules->players[Ball.controller].team == Evidence.VictimTeam
            && Rules->eligible(Ball.controller, Evidence.Ball);
        if (ABBRiderCharacter* Carrier = RiderForSlot(Ball.controller)) bRetained &= !Carrier->HasSpellMovementLock();
        else bRetained = false;
    }
    if (Rules->status == BB::Status::Live && bRetained) return;
    // Preserve an already observed terminal event. Its pending penalty prevents
    // certification; never rewind its catch, points or original clock.
    if (Rules->status == BB::Status::Live) Rules->pause("Moderate advantage lost: offended team no longer controls affected ball");
    bConductAdvantageLive = false; PresentConductEvidence(); SyncRules(); Say(ConductReviewStatus);
}
TArray<double> ABBMatchState::DevelopmentGetConductAdvantageState() const
{
#if !UE_BUILD_SHIPPING
    if (HasAuthority() && Rules && GetWorld() && GetWorld()->WorldType == EWorldType::PIE)
    {
        const FConductEvidence* Evidence = !ConductEvidence.IsEmpty() ? &ConductEvidence[0]
            : LastServedConductEvidence.Attack ? &LastServedConductEvidence : nullptr;
        return {bModerateAdvantageArmed ? 1.0 : 0.0, bConductAdvantageLive ? 1.0 : 0.0,
            static_cast<double>(ConductEvidence.Num()), Evidence ? static_cast<double>(Evidence->CommittedMs) : -1.0,
            Evidence ? static_cast<double>(Evidence->PenaltyId) : -1.0, Evidence ? static_cast<double>(Evidence->Offender) : -1.0,
            Evidence ? static_cast<double>(Evidence->VictimSlot) : -1.0, Evidence ? static_cast<double>(Evidence->Ball) : -1.0,
            Evidence ? static_cast<double>(Evidence->Attack) : -1.0, static_cast<double>(Rules->status),
            Rules->ending.active ? static_cast<double>(Rules->ending.at_ms) : -1.0, Rules->penalty_shot.post_termination ? 1.0 : 0.0};
    }
#endif
    return {};
}

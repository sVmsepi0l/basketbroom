#include "BBMatchState.h"
#include "BBBall.h"
#include "BBRiderCharacter.h"
#include "CollisionQueryParams.h"
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
FVector StartLocation(int32 Slot)
{
    const int32 Local = Slot % 8;
    const float Sign = Slot < 8 ? -1.f : 1.f;
    return FVector(Sign * (Local == 0 ? 5400.f : 3700.f - Local * 260.f),
                   (Local % 3 - 1) * 950.f, Local == 7 ? 2800.f : 1400.f + (Local % 3) * 350.f);
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
    BB::Config Config;
    if (bPractice) { Config.quarter_ms = 180000; Config.snitch_release_ms = 60000; Config.overtime_ms = 120000; }
    Rules = std::make_unique<BB::Match>(Config);
    Rules->pause("pregame selection");
    const FVector Homes[] = {FVector(-2000,0,1500), FVector(-500,-850,1800), FVector(500,850,1800),
        FVector(0,0,2103.12), FVector(0,0,3048), FVector(1000,-1400,1900), FVector(-1000,1400,1900)};
    for (int32 I = 0; I < 7; ++I)
    {
        FTransform Transform(FRotator::ZeroRotator, Homes[I]);
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
void ABBMatchState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const
{
    Super::GetLifetimeReplicatedProps(Out);
    DOREPLIFETIME(ABBMatchState, TealScore); DOREPLIFETIME(ABBMatchState, CopperScore);
    DOREPLIFETIME(ABBMatchState, Quarter); DOREPLIFETIME(ABBMatchState, SecondsLeft);
    DOREPLIFETIME(ABBMatchState, Phase); DOREPLIFETIME(ABBMatchState, Status);
    DOREPLIFETIME(ABBMatchState, Announcement); DOREPLIFETIME(ABBMatchState, bPractice);
    DOREPLIFETIME(ABBMatchState, bLive); DOREPLIFETIME(ABBMatchState, Winner);
    DOREPLIFETIME(ABBMatchState, LiveSeconds);
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
    for (ABBRiderCharacter* R : Riders) if (IsValid(R) && R != Rider && R->IsPlayerControlled()) ++Counts[FMath::Clamp(R->TeamIndex,0,1)];
    const int32 Team = Counts[0] <= Counts[1] ? 0 : 1;
    int32 Slot = Team * 8 + 4; // Ranger is the most flexible opening position.
    auto HumanInSlot = [this, Rider](int32 Index) { for (ABBRiderCharacter* R : Riders) if (IsValid(R) && R != Rider && R->RosterIndex == Index && R->IsPlayerControlled()) return true; return false; };
    if (HumanInSlot(Slot))
    {
        Slot = INDEX_NONE;
        for (int32 Offset = 0; Offset < 16; ++Offset)
        {
            const int32 Candidate = (Team * 8 + Offset) % 16;
            if (!HumanInSlot(Candidate)) { Slot = Candidate; break; }
        }
    }
    if (Slot == INDEX_NONE)
    {
        if (APlayerController* Player = Cast<APlayerController>(Rider->GetController())) Player->StartSpectatingOnly();
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
        || R->StunRemaining > 0 || R->RosterIndex < 0 || R->RosterIndex >= 16) return false;
    if (!Rules->eligible(R->RosterIndex, B->BallIndex)) return false;
    for (const ABBBall* Other : Balls) if (IsValid(Other) && Other->Holder == R && Other != B) return false;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BasketbroomInteraction), false, R);
    Query.AddIgnoredActor(B);
    FHitResult Hit;
    if (GetWorld()->LineTraceSingleByChannel(Hit, R->GetActorLocation(), B->GetActorLocation(), ECC_Visibility, Query)) return false;
    return true;
}
bool ABBMatchState::TryPossess(ABBRiderCharacter* R, ABBBall* B)
{
    if (!CanInteract(R,B) || B->IsChase() || B->Holder || B->Cooldown > 0 || FVector::DistSquared(R->GetActorLocation(),B->GetActorLocation()) > FMath::Square(425.f)) return false;
    if (!Rules->possess(R->RosterIndex, B->BallIndex, B->IsBludger())) return false;
    B->Holder = R; B->LastTouchTeam = R->TeamIndex; B->FlightVelocity = FVector::ZeroVector;
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
    Event.inside_envelope = FMath::Abs(P.X) < 6850.8f && FMath::Abs(P.Y) < 3200.4f && P.Z <= 6309.36f && P.Z > 0;
    if (!Event.inside_envelope) return false;
    PendingPoints.push_back(Event);
    return true;
}
void ABBMatchState::Goal(ABBBall* B, int32 Team)
{
    if (!HasAuthority() || !Rules || !bLive || !IsValid(B) || !Balls.Contains(B) || Team < 0 || Team > 1
        || B->BallIndex < 0 || B->BallIndex > 2 || !Rules->balls[B->BallIndex].live || B->Holder || !B->bActive) return;
    for (const auto& P : PendingPoints) if (P.ball == B->BallIndex) return;
    BB::PointEvent Event; Event.ball = B->BallIndex; Event.attacking_team = Team;
    Event.hoop = B->BallIndex == 0 ? BB::Hoop::Large : BB::Hoop::Small;
    Event.entire_ball = true; Event.forward = true;
    PendingPoints.push_back(Event);
    B->FlightVelocity = FVector::ZeroVector; B->Cooldown = .25f;
}
void ABBMatchState::Release(ABBRiderCharacter* R, FVector Aim)
{
    if (!HasAuthority() || !Rules || !IsValid(R) || Aim.ContainsNaN()) return;
    for (ABBBall* B : Balls)
    {
        if (B->Holder != R) continue;
        if (!Rules->release(R->RosterIndex, B->BallIndex, true)) continue;
        B->Holder = nullptr;
        B->LastLocation = R->GetCarryLocation();
        B->SetActorLocation(B->LastLocation);
        B->FlightVelocity = Aim.IsNearlyZero() ? R->GetVelocity() : Aim.GetSafeNormal() * (B->IsBludger() ? 5000.f : 4400.f) + R->GetVelocity() * .4f;
        B->Cooldown = .3f;
        B->ForceNetUpdate();
    }
}
void ABBMatchState::NoCrown(ABBBall* B)
{
    if (!HasAuthority() || !Rules || !bLive || !IsValid(B) || !Balls.Contains(B) || B->IsChase()) return;
    const FVector P = B->GetActorLocation();
    if (Rules->crown_exit(B->BallIndex, {P.X / 30.48, P.Y / 30.48, 138.0}))
    {
        B->Holder = nullptr; B->FlightVelocity = FVector::ZeroVector;
        B->SetActorLocation(FVector(P.X, P.Y, 4110.f));
        Say(B->DisplayName() + TEXT(" - NO CROWN. Returning below the roofline."));
        SyncRules();
    }
}
void ABBMatchState::ChangePosition(ABBRiderCharacter* R, int32 NewPosition, int32 NewTeam)
{
    if (!HasAuthority() || !Rules || !IsValid(R) || NewPosition < 0 || NewPosition > 5 || NewTeam < 0 || NewTeam > 1) return;
    if (bLive) { Say(TEXT("Positions are locked during live play. Choose at the next stoppage.")); return; }
    if (Rules->status == BB::Status::Review || Rules->status == BB::Status::Complete) return;
    if (R->Position == NewPosition && R->TeamIndex == NewTeam) return;
    const auto& CurrentPlayer = Rules->players[R->RosterIndex];
    auto HasPendingPenalty = [this](int32 Slot)
    {
        for (const auto& Penalty : Rules->penalties) if (Penalty.player == Slot && Penalty.pending) return true;
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
    if (!Swap) { Say(TEXT("That position is occupied by another player.")); return; }
    const int32 OldIndex = R->RosterIndex;
    R->RosterIndex = Swap->RosterIndex; Swap->RosterIndex = OldIndex;
    for (ABBRiderCharacter* Changed : {R, Swap})
    {
        Changed->TeamIndex = Changed->RosterIndex / 8;
        Changed->Position = Roles[Changed->RosterIndex % 8];
        Changed->bInteractHeld = false;
        PlaceRider(Changed, StartLocation(Changed->RosterIndex), Changed->TeamIndex ? 180.f : 0.f);
    }
    Say(FString::Printf(TEXT("%s selected %s. ENTER resumes play."), R->TeamIndex ? TEXT("Copper") : TEXT("Teal"), *PositionName(R->Position)));
}
void ABBMatchState::HandleAction(ABBRiderCharacter* R, int32 Action, int32 Value, FVector Aim)
{
    if (!HasAuthority() || !Rules || !IsValid(R) || !Riders.Contains(R) || R->RosterIndex < 0 || R->RosterIndex >= 16) return;
    if (Action == 2) { ChangePosition(R, Value, R->TeamIndex); return; }
    if (Action == 3) { ChangePosition(R, R->Position, Value); return; }
    if (Action == 4 || Action == 5)
    {
        // Listen-server period control belongs to the host. A dedicated server
        // delegates it to the first connected participant below.
        bool bCanStart = R->IsLocallyControlled();
        if (GetNetMode() == NM_DedicatedServer)
        {
            // A dedicated server has no local player. Give its first connected
            // participant period control, with stable PlayerState ordering.
            int32 FirstPlayerId = MAX_int32;
            for (ABBRiderCharacter* Other : Riders)
                if (IsValid(Other) && Other->IsPlayerControlled() && Other->GetPlayerState())
                    FirstPlayerId = FMath::Min(FirstPlayerId, Other->GetPlayerState()->GetPlayerId());
            bCanStart = R->GetPlayerState() && R->GetPlayerState()->GetPlayerId() == FirstPlayerId;
        }
        if (!bCanStart) return;
        if (Rules->status == BB::Status::Complete) return;
        if (Action == 5)
        {
            // Finish already observed goals/catches before stopping the clock.
            if (!PendingPoints.empty())
            {
                Rules->process_batch(Rules->now_ms, PendingPoints);
                PendingPoints.clear();
            }
            if (Rules->pause("host requested official stoppage"))
                Say(TEXT("OFFICIAL STOPPAGE - choose positions with 1-6. Host: ENTER to resume."));
            SyncRules();
            return;
        }
        if (!bLive && Rules->status != BB::Status::Review && Rules->resume()) { bInitialized = true; Say(TEXT("LIVE - play your position. Hold E within 3.8m to secure a chase ball.")); SyncRules(); }
        return;
    }
    if (!bLive || R->StunRemaining > 0) return;
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
    if (!PendingPoints.empty())
    {
        if (Rules->process_batch(Rules->now_ms, PendingPoints))
        {
            for (const auto& Award : Rules->last_awards) Say(FString::Printf(TEXT("%s +%lld  |  %s"), Award.team == 0 ? TEXT("TEAL") : TEXT("COPPER"), static_cast<long long>(Award.points), *Balls[Award.ball]->DisplayName()));
        }
        else UE_LOG(LogTemp, Warning, TEXT("Basketbroom point batch rejected: %s"), UTF8_TO_TCHAR(Rules->last_error.c_str()));
        PendingPoints.clear();
    }
    if (Rules->status == BB::Status::Live)
    {
        MillisecondCarry += FMath::Max(0.f, Dt) * 1000.0;
        const BB::Millis Whole = static_cast<BB::Millis>(MillisecondCarry);
        MillisecondCarry -= Whole;
        Rules->advance(Whole);
        for (int32 I=0; I<7; ++I)
        {
            auto& State = Rules->balls[I];
            ABBBall* B = Balls[I];
            if (State.dead_reason == "crown" && State.crown_deadline - Rules->now_ms <= 2000) { Rules->crown_return(I); B->FlightVelocity = FVector(0,0,-100); }
            if (State.dead_reason == "score" || State.dead_reason == "hurley_foul" || State.dead_reason == "penalty")
            {
                ABBRiderCharacter* Receiver = nullptr;
                for (ABBRiderCharacter* R : Riders) if (R->TeamIndex == State.restart_team && (I < 3 ? R->Position == 0 : R->Position == 4)) { Receiver = R; break; }
                if (Receiver && Rules->restart(I,Receiver->RosterIndex))
                {
                    const FVector Mark((Receiver->TeamIndex == 0 ? -1.f : 1.f) * (6400.8f - 670.56f), 0, I == 0 ? 2103.12f : 3048.f);
                    PlaceRider(Receiver, Mark, Receiver->TeamIndex ? 180.f : 0.f);
                    B->ResetBall(Mark + FVector(0,0,80));
                    for (ABBRiderCharacter* Other : Riders)
                        if (Other->TeamIndex != Receiver->TeamIndex && FVector::DistSquared(Other->GetActorLocation(),Mark) < FMath::Square(396.24f))
                            PlaceRider(Other, Mark + (Other->GetActorLocation()-Mark).GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector) * 450.f, Other->GetActorRotation().Yaw);
                }
            }
            if (I >= 5 && State.live && State.controller < 0 && B->FlightVelocity.Size() > 300) Rules->flight_evidence(I, (B->GetActorLocation()-B->LastLocation).Size()/30.48, BB::Contact::None, true);
        }
    }
    // The rules engine explicitly requires a stoppage for administration.
    // Resolve before certification/resume, including penalties that caused it.
    if (Rules->status != BB::Status::Live)
        for (auto& Penalty : Rules->penalties)
            if (Penalty.pending && Penalty.severity != BB::Severity::Catastrophic)
                Rules->resolve_penalty(Penalty.id,"automatic rules enforcement",true);
    if (Rules->status == BB::Status::Review)
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
    Quarter = Rules->quarter; Winner = Rules->winner; bLive = Rules->status == BB::Status::Live;
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
        B->bActive = S.phase_active && (S.live || S.dead_reason == "stoppage");
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
            const FVector PenaltyBox(R->TeamIndex == 0 ? -7200 : 7200, 0, 600);
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
        if (!IsValid(R) || R->IsPlayerControlled() || R->StunRemaining > 0) continue;
        ABBBall* Held = nullptr; for (ABBBall* B : Balls) if (B->Holder == R) Held = B;
        FVector Target = StartLocation(R->RosterIndex);
        R->bInteractHeld = false;
        if (Held)
        {
            float Sign = R->TeamIndex == 0 ? 1.f : -1.f;
            FVector GoalMark(Sign * 6500.f, Held->BallIndex == 0 ? ((R->RosterIndex % 3)-1) * 1066.8f : 0.f, Held->BallIndex == 0 ? 2103.12f : 3048.f);
            Target = GoalMark - FVector(Sign * 2100.f,0,0);
            if (Held->IsBludger())
            {
                for (ABBRiderCharacter* Enemy : Riders) if (Enemy->TeamIndex != R->TeamIndex) { GoalMark = Enemy->GetActorLocation(); break; }
                Release(R,(GoalMark-R->GetCarryLocation()).GetSafeNormal());
            }
            else if (R->Position == 0 || FVector::DistSquared(R->GetActorLocation(), Target) < FMath::Square(500.f))
            {
                const auto& BallRule = Rules->balls[Held->BallIndex];
                if (BallRule.protection_until < 0 || Rules->now_ms >= BallRule.protection_until)
                {
                    if (R->Position == 0) GoalMark = FVector(Sign * 1000, (R->RosterIndex % 2 ? 900 : -900), 1800);
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

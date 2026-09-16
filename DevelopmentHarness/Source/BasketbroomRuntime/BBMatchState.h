#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include <memory>
#include "BBRuleEngine.h"
#include "BBCombatRules.h"
#include "BBMatchState.generated.h"
class ABBRiderCharacter;
class ABBBall;
class ABBSpellArenaObject;

UCLASS()
class BASKETBROOMRUNTIME_API ABBMatchState : public AGameStateBase
{
    GENERATED_BODY()
public:
    ABBMatchState();
    virtual ~ABBMatchState() override;
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 TealScore = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 CopperScore = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 Quarter = 1;
    UPROPERTY(Replicated, BlueprintReadOnly) float SecondsLeft = 2640;
    UPROPERTY(Replicated, BlueprintReadOnly) FString Phase = TEXT("REGULATION");
    UPROPERTY(Replicated, BlueprintReadOnly) FString Status = TEXT("LOBBY");
    UPROPERTY(Replicated, BlueprintReadOnly) FString Announcement = TEXT("Choose a position with 1-6. Press ENTER to begin.");
    UPROPERTY(Replicated, BlueprintReadOnly) bool bPractice = false;
    UPROPERTY(Replicated, BlueprintReadOnly) bool bLive = false;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 Winner = -1;
    UPROPERTY(Replicated, BlueprintReadOnly) float LiveSeconds = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 PendingPenaltyCount = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) FString PendingPenaltySummary;
    UPROPERTY(Replicated, BlueprintReadOnly) bool bBloodbroom = false;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 ConductFoulCount = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) FString LastConductCall;
    UPROPERTY(Replicated, BlueprintReadOnly) bool bConductReviewPending = false;
    UPROPERTY(Replicated, BlueprintReadOnly) FString ConductReviewStatus;
    UPROPERTY(Replicated, BlueprintReadOnly) bool bModerateAdvantageArmed = false;
    UPROPERTY(Replicated, BlueprintReadOnly) bool bConductAdvantageLive = false;
    /** Read-only PIE: armed, live, queued, original time, penalty, offender,
     * victim, ball, attack, rules status, ending time, post-termination shot. */
    UFUNCTION(BlueprintPure, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    TArray<double> DevelopmentGetConductAdvantageState() const;
    UPROPERTY(Replicated, BlueprintReadOnly) bool bPenaltyShotActive = false;
    UPROPERTY(Replicated, BlueprintReadOnly) bool bFreeShot = false;
    UPROPERTY(Replicated, BlueprintReadOnly) bool bPenaltyShotReleased = false;
    UPROPERTY(Replicated, BlueprintReadOnly) float PenaltyShotSecondsLeft = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 PenaltyShotBall = -1;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 PenaltyShooterSlot = -1;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 PenaltyKeeperSlot = -1;
    UPROPERTY(Replicated, BlueprintReadOnly) FString PenaltyShotStatus;
    bool CanMoveDuringPenalty(const ABBRiderCharacter* Rider) const;
    bool IsPenaltyBallActive(const ABBBall* Ball) const;
    void PenaltyBallStopped(ABBBall* Ball, const FString& Reason, double FlightStepFraction = 1.0);
    UFUNCTION(BlueprintPure, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    TArray<int32> DevelopmentGetPenaltyShotState() const;
    UFUNCTION(BlueprintPure, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    double DevelopmentGetRemovalSeconds(int32 Slot) const;
    /** Read-only PIE attempt timing: elapsed, duration, remaining milliseconds,
     * including the native fractional-millisecond carry. */
    UFUNCTION(BlueprintPure, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    TArray<double> DevelopmentGetPenaltyShotTiming() const;
    UPROPERTY() TArray<TObjectPtr<ABBRiderCharacter>> Riders;
    UPROPERTY() TArray<TObjectPtr<ABBBall>> Balls;
    void HandleAction(ABBRiderCharacter* Rider, int32 Action, int32 Value = 0, FVector Aim = FVector::ZeroVector);
    void AssignHuman(ABBRiderCharacter* Rider);
    void FillRoster();
    void Goal(ABBBall* Ball, int32 Team, double FlightStepFraction = 1.0);
    bool CanInteract(const ABBRiderCharacter* Rider, const ABBBall* Ball) const;
    bool IsActiveFlightParticipant(const ABBRiderCharacter* Rider) const;
    void AwardBludgerFlightBoost(ABBBall* Ball, ABBRiderCharacter* Target, FVector ContactPoint);
    bool TryPossess(ABBRiderCharacter* Rider, ABBBall* Ball);
    bool TryCatch(ABBRiderCharacter* Rider, ABBBall* Ball);
    void Release(ABBRiderCharacter* Rider, FVector Aim, bool bDeferConductBoundary = false);
    void CastSpell(ABBRiderCharacter* Rider, int32 SpellIndex, FVector Aim);
    void ConfirmImpediment(ABBRiderCharacter* Rider, uint64 AttackId);
    UFUNCTION(BlueprintPure, Category="Basketbroom|Spells")
    ABBSpellArenaObject* GetSpellWorkshop(const ABBRiderCharacter* Rider) const;
    UFUNCTION(BlueprintPure, Category="Basketbroom|Spells")
    int32 GetAncientMagicCharge(const ABBRiderCharacter* Rider) const;
    /** Only the server-owned workshop calls this after swept physical contact. */
    void ResolveThrownSpellImpact(ABBSpellArenaObject* Object, ABBRiderCharacter* Target,
        FVector ImpactPoint, FVector Direction, uint64 AttackId);
    UFUNCTION(BlueprintPure, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    TArray<int32> DevelopmentGetConductState() const;
    /** Server GameMode teardown only; clears custody, never historical sanctions. */
    void ReleaseDepartedSlot(int32 RosterIndex);
    void ObserveBludgerFlight(ABBBall* Ball, BB::Contact Contact);
    /** Read-only PIE diagnostic. -1 means unavailable or no current controller. */
    UFUNCTION(BlueprintPure, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    double DevelopmentGetBludgerControlSeconds(int32 BallIndex) const;
    /** PIE-only, read-only: total, pending adjudication, unserved restoration,
     * last responsible slot, last receiver slot, latest penalty ID. */
    UFUNCTION(BlueprintPure, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    TArray<int32> DevelopmentGetCrownPenaltyState(int32 BallIndex) const;
    void Say(const FString& Text);
    static FString PositionName(int32 Position);
private:
    std::unique_ptr<BB::Match> Rules;
    std::unique_ptr<BB::CombatPolicy> Combat;
    TMap<int32, TWeakObjectPtr<ABBRiderCharacter>> CombatOccupants;
    int32 CombatPhase = -1;
    int32 ConductOffender = -1;
    int32 ConductVictimTeam = -1;
    int32 ConductRestartBall = -1;
    int32 ConductBall = -1, ConductVictimSlot = -1;
    struct FConductEvidence
    {
        int32 Offender = -1, VictimTeam = -1, VictimSlot = -1, Ball = -1, Spell = -1;
        uint32 Violations = 0;
        uint64 Attack = 0;
        BB::Millis CommittedMs = 0;
        int32 PenaltyId = -1;
        FVector FoulPoint = FVector::ZeroVector;
        FString Reason;
        TWeakObjectPtr<ABBRiderCharacter> OriginalOffender, OriginalVictim;
    };
    TArray<FConductEvidence> ConductEvidence;
    FConductEvidence LastServedConductEvidence;
    void RegisterConductHit(ABBRiderCharacter* Offender, ABBRiderCharacter* Victim,
        int32 Spell, int32 AffectedBall, uint32 Violations, uint64 Attack, bool bHeadHit);
    void PresentConductEvidence();
    void CompleteConductEvidence();
    void TickConductAdvantage();
    bool IsUnreviewedConductPenalty(int32 Id) const;
    TMap<int32, FTransform> PenaltySavedRiders;
    TMap<int32, FRotator> PenaltySavedViews;
    FVector PenaltyShooterMark = FVector::ZeroVector;
    FVector PenaltyKeeperMark = FVector::ZeroVector;
    float PenaltyResultDelay = 0;
    double PenaltyShotMillisecondCarry = 0;
    double PenaltyFlightStepMs = 0, PenaltyFlightConsumedMs = 0;
    bool bSteppingPenaltyFlight = false;
    TWeakObjectPtr<ABBRiderCharacter> PenaltyShooterActor, PenaltyKeeperActor;
    bool AdvancePenaltyClock(double Milliseconds);
    bool ConsumePenaltyFlightTime(double FlightStepFraction);
    bool BeginConductPenaltyShot(int32 PenaltyId, bool bModerate = false);
    void TickPenaltyShot(float DeltaSeconds);
    void ReleasePenaltyShot(ABBRiderCharacter* Rider, FVector Aim);
    void FinishPenaltyShot(BB::PenaltyShotOutcome Outcome, const FString& Reason, const BB::PointEvent& Goal = {});
    ABBRiderCharacter* RiderForSlot(int32 Slot) const;
    void ResetPenaltyPresentation();
    FVector ConductMark = FVector::ZeroVector;
    FVector ConductFoulPoint = FVector::ZeroVector;
    uint64 LastConductAttack = 0;
    int32 LastConductViolations = 0;
    void SyncCombatRoster();
    int32 CombatIndex(const ABBRiderCharacter* Rider) const;
    void TickSpells(float LiveDelta);
    UPROPERTY() TArray<TObjectPtr<ABBSpellArenaObject>> SpellWorkshops;
    void ResetContextualSpells();
    void TickContextualSpells(float LiveDelta);
    ABBSpellArenaObject* EnsureSpellWorkshop(ABBRiderCharacter* Rider);
    bool TryCastContextualSpell(ABBRiderCharacter* Rider, int32 SpellIndex, FVector Aim);
    void ResolveSpellHit(ABBRiderCharacter* Rider, ABBRiderCharacter* Target, int32 SpellIndex,
        FVector Aim, FVector ImpactPoint, FVector Start, uint64 ExistingAttackId = 0);
    void ReviewConduct(ABBRiderCharacter* Referee, int32 Disposition);
    bool CanOfficiate(const ABBRiderCharacter* Rider) const;
    double MillisecondCarry = 0;
    float BotAccumulator = 0;
    float ReviewDelay = 0;
    bool bInitialized = false;
    size_t LastLogIndex = 0;
    std::vector<BB::PointEvent> PendingPoints;
    TMap<int32, TWeakObjectPtr<ABBRiderCharacter>> PendingFlightScorers;
    uint64 FlightRewardSequence = 0;
    bool FlushPendingPointEvents();
    void ResetMatchRules();
    void ResetOpeningLayout();
    void SyncRules();
    void UpdateBots(float DeltaSeconds);
    void ChangePosition(ABBRiderCharacter* Rider, int32 NewPosition, int32 NewTeam);
};

#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include <memory>
#include "BBRuleEngine.h"
#include "BBMatchState.generated.h"
class ABBRiderCharacter;
class ABBBall;

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
    UPROPERTY() TArray<TObjectPtr<ABBRiderCharacter>> Riders;
    UPROPERTY() TArray<TObjectPtr<ABBBall>> Balls;
    void HandleAction(ABBRiderCharacter* Rider, int32 Action, int32 Value = 0, FVector Aim = FVector::ZeroVector);
    void AssignHuman(ABBRiderCharacter* Rider);
    void FillRoster();
    void Goal(ABBBall* Ball, int32 Team);
    bool CanInteract(const ABBRiderCharacter* Rider, const ABBBall* Ball) const;
    bool TryPossess(ABBRiderCharacter* Rider, ABBBall* Ball);
    bool TryCatch(ABBRiderCharacter* Rider, ABBBall* Ball);
    void Release(ABBRiderCharacter* Rider, FVector Aim);
    void NoCrown(ABBBall* Ball);
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
    double MillisecondCarry = 0;
    float BotAccumulator = 0;
    float ReviewDelay = 0;
    bool bInitialized = false;
    size_t LastLogIndex = 0;
    std::vector<BB::PointEvent> PendingPoints;
    void ResetMatchRules();
    void ResetOpeningLayout();
    void SyncRules();
    void UpdateBots(float DeltaSeconds);
    void ChangePosition(ABBRiderCharacter* Rider, int32 NewPosition, int32 NewTeam);
};

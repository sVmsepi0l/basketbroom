#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BBBall.generated.h"
class ABBRiderCharacter;
class ABBMatchState;
class UStaticMeshComponent;
class UMaterialInterface;
UCLASS()
class BASKETBROOMRUNTIME_API ABBBall : public AActor
{
    GENERATED_BODY()
public:
    ABBBall();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Mesh;
    UPROPERTY(ReplicatedUsing=OnRep_Appearance, BlueprintReadOnly) int32 BallIndex = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) TObjectPtr<ABBRiderCharacter> Holder;
    UPROPERTY(Replicated, BlueprintReadOnly) TObjectPtr<ABBRiderCharacter> CapturingRider;
    UPROPERTY(Replicated, BlueprintReadOnly) float CaptureProgress = 0;
    UPROPERTY(ReplicatedUsing=OnRep_Appearance, BlueprintReadOnly) bool bActive = true;
    UPROPERTY(Replicated, BlueprintReadOnly) float ReturnIn = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) FString BallStatus;
    UPROPERTY(Replicated) FVector FlightVelocity = FVector::ZeroVector;
    UPROPERTY() TObjectPtr<ABBMatchState> Match;
    UPROPERTY() TArray<TObjectPtr<UMaterialInterface>> BallMaterials;
    FVector Home = FVector::ZeroVector;
    FVector LastLocation = FVector::ZeroVector;
    float Cooldown = 0;
    float ChaseTime = 0;
    float BobTime = 0;
    int32 LastTouchTeam = -1;
    bool IsChase() const { return BallIndex == 3 || BallIndex == 4; }
    bool IsBludger() const { return BallIndex >= 5; }
    int32 Kind() const { return BallIndex == 0 ? 0 : BallIndex <= 2 ? 1 : BallIndex - 1; }
    float Radius() const { return IsChase() ? 28.f : IsBludger() ? 50.f : 65.f; }
    FString DisplayName() const;
    UFUNCTION() void OnRep_Appearance();
    void ResetBall(FVector Location);
private:
    void StepFlight(float DeltaSeconds);
    void StepCapture(float DeltaSeconds);
};

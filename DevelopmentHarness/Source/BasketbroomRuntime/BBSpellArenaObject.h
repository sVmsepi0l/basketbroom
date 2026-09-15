#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BBSpellArenaObject.generated.h"
class ABBRiderCharacter;
class ABBMatchState;
class UStaticMesh;
class UStaticMeshComponent;
class UTextRenderComponent;
class UMaterialInstanceDynamic;

/** Original, deliberately limited sporting workshop. No arbitrary world edits.
 * Each admitted human owns at most one bay and one visible construct. The bay
 * never blocks riders or official balls; only wand visibility queries hit it. */
UCLASS()
class BASKETBROOMRUNTIME_API ABBSpellArenaObject : public AActor
{
    GENERATED_BODY()
public:
    ABBSpellArenaObject();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
    UPROPERTY(ReplicatedUsing=RefreshPresentation, BlueprintReadOnly, Category="Basketbroom|Workshop")
    TObjectPtr<ABBRiderCharacter> WorkshopOwner;
    UPROPERTY(ReplicatedUsing=RefreshPresentation, BlueprintReadOnly, Category="Basketbroom|Workshop")
    bool bUnlocked = false;
    UPROPERTY(ReplicatedUsing=RefreshPresentation, BlueprintReadOnly, Category="Basketbroom|Workshop")
    bool bConjured = false;
    UPROPERTY(ReplicatedUsing=RefreshPresentation, BlueprintReadOnly, Category="Basketbroom|Workshop")
    float Integrity = 0;
    UPROPERTY(ReplicatedUsing=RefreshPresentation, BlueprintReadOnly, Category="Basketbroom|Workshop")
    int32 Form = 0;
    UPROPERTY(ReplicatedUsing=RefreshPresentation, BlueprintReadOnly, Category="Basketbroom|Workshop")
    int32 AncientMagicCharge = 0;
    UPROPERTY(ReplicatedUsing=RefreshPresentation, BlueprintReadOnly, Category="Basketbroom|Workshop")
    FVector ConstructPosition = FVector::ZeroVector;
    UPROPERTY(ReplicatedUsing=RefreshPresentation, BlueprintReadOnly, Category="Basketbroom|Workshop")
    bool bInFlight = false;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Basketbroom|Workshop")
    TObjectPtr<UStaticMeshComponent> Bay;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Basketbroom|Workshop")
    TObjectPtr<UStaticMeshComponent> Construct;

    bool IsUsableBy(const ABBRiderCharacter* Rider) const;
    bool ApplyWorkshopSpell(ABBRiderCharacter* Rider, int32 SpellIndex, FVector Aim, FString& Feedback);
    bool DamageConstruct(float Damage);
    bool SpendCharge(int32 Cost);
    void EarnCharge(int32 Amount);
    void Launch(ABBRiderCharacter* Target, FVector TargetPoint, uint64 AttackId);
    void AdvanceLive(float DeltaSeconds, ABBMatchState* Match);
    void CancelFlight();
    FVector Home() const { return GetActorLocation()+FVector(0,0,180); }
    static constexpr float ConstructRadius = 45.f;
private:
    UPROPERTY() TObjectPtr<UTextRenderComponent> Label;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> BayMaterial;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> ConstructMaterial;
    UPROPERTY() TObjectPtr<UStaticMesh> CubeShape;
    UPROPERTY() TObjectPtr<UStaticMesh> SphereShape;
    UPROPERTY() TObjectPtr<UStaticMesh> CylinderShape;
    TWeakObjectPtr<ABBRiderCharacter> FlightTarget;
    FVector FlightVelocity = FVector::ZeroVector;
    uint64 FlightAttackId = 0;
    float FlightRemaining = 0;
    int32 FlightCasterSlot = INDEX_NONE, FlightTargetSlot = INDEX_NONE;
    FVector LiftDestination = FVector::ZeroVector;
    bool bLifting = false;
    int32 LabelOwnerSlot = INDEX_NONE, LabelOwnerTeam = INDEX_NONE;
    UFUNCTION() void RefreshPresentation();
};

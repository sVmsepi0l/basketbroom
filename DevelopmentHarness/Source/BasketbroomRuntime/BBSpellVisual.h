#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BBSpellVisual.generated.h"

class UStaticMeshComponent;
class UInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;

/** Original cosmetic cast trace. Keeps server trace evidence; no gameplay collision. */
UCLASS()
class BASKETBROOMRUNTIME_API ABBSpellVisual : public AActor
{
    GENERATED_BODY()
public:
    ABBSpellVisual();
    static ABBSpellVisual* Spawn(UWorld* World, FVector Start, FVector End, int32 SpellIndex, bool bBlocked);
    virtual void Tick(float DeltaSeconds) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    /** The authoritative eye-origin trace; rendering uses the offset muzzle below. */
    UPROPERTY(ReplicatedUsing=OnRep_Visual, BlueprintReadOnly, Category="Basketbroom|Spells") FVector StartPoint;
    UPROPERTY(ReplicatedUsing=OnRep_Visual, BlueprintReadOnly, Category="Basketbroom|Spells") FVector EndPoint;
    /** Cosmetic origin derived locally from the unchanged server endpoints. */
    UPROPERTY(Transient, BlueprintReadOnly, Category="Basketbroom|Spells") FVector VisualStartPoint;
    UPROPERTY(ReplicatedUsing=OnRep_Visual, BlueprintReadOnly, Category="Basketbroom|Spells") int32 VisualSpellIndex = 0;
    UPROPERTY(ReplicatedUsing=OnRep_Visual, BlueprintReadOnly, Category="Basketbroom|Spells") bool bWasBlocked = false;
protected:
    virtual void BeginPlay() override;
private:
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Beam;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Impact;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> ImpactRays;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> GlowMaterial;
    float VisualAge = 0.f;
    float BeamLength = 0.f;
    void UpdateVisualScale();
    UFUNCTION() void OnRep_Visual();
};

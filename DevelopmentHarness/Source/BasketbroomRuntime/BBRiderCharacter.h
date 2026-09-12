#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "InputCoreTypes.h"
#include "BBRiderCharacter.generated.h"

class UCameraComponent;
class UMaterialInterface;
class UStaticMeshComponent;

/** Native movement prediction with the authoritative stun speed constraint. */
UCLASS()
class BASKETBROOMRUNTIME_API UBBFlyingMovementComponent : public UCharacterMovementComponent
{
    GENERATED_BODY()

public:
    virtual float GetMaxSpeed() const override;
    virtual float GetMaxAcceleration() const override;

protected:
    virtual void PhysFlying(float DeltaTime, int32 Iterations) override;
};

/** An owned, predicted broom rider. MatchState resolves all gameplay requests. */
UCLASS()
class BASKETBROOMRUNTIME_API ABBRiderCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    explicit ABBRiderCharacter(const FObjectInitializer& ObjectInitializer);

    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
    virtual void UnPossessed() override;
    virtual void PawnClientRestart() override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Basketbroom|Camera")
    TObjectPtr<UCameraComponent> Camera;

    UPROPERTY(ReplicatedUsing=OnRep_TeamIndex, BlueprintReadOnly, Category="Basketbroom|Roster")
    int32 TeamIndex = 0;

    /** 0 Netminder, 1 Chaser, 2 Trapper, 3 Ranger, 4 Hurleyback, 5 Scout. */
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Roster")
    int32 Position = 3;

    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Roster")
    int32 RosterIndex = INDEX_NONE;

    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Interaction")
    bool bInteractHeld = false;

    /** Written/extended by server rules; this Character owns the countdown. */
    UPROPERTY(ReplicatedUsing=OnRep_StunRemaining, BlueprintReadOnly, Category="Basketbroom|Movement")
    float StunRemaining = 0.0f;

    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|HUD")
    bool bShowRoster = false;

    /** Cosmetic equipment only; role 4 outside Donnybrook, with owner-view filtering. */
    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|Equipment")
    bool bHurleyVisible = false;

    /** Cosmetic stock skeletal body with an authored Basketbroom seated loop. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Basketbroom|Art")
    bool bSkeletalRiderEnabled = false;

    UFUNCTION(BlueprintPure, Category="Basketbroom|Interaction")
    FVector GetAimDirection() const;

    UFUNCTION(BlueprintPure, Category="Basketbroom|Interaction")
    FVector GetCarryLocation() const;

    /** PIE input bridge; true means queued for native Tick, not accepted play. */
    UFUNCTION(BlueprintCallable, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    bool DevelopmentRequestAction(int32 Action, int32 Value = 0);

    UFUNCTION(BlueprintCallable, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    bool DevelopmentSetInteraction(bool bHeld);

protected:
    virtual void BeginPlay() override;

private:
    UPROPERTY()
    TArray<TObjectPtr<UStaticMeshComponent>> UniformParts;

    UPROPERTY()
    TArray<TObjectPtr<UStaticMeshComponent>> HurleyParts;

    UPROPERTY()
    TObjectPtr<UMaterialInterface> TealMaterial;

    UPROPERTY()
    TObjectPtr<UMaterialInterface> CopperMaterial;

    UPROPERTY()
    TArray<TObjectPtr<UMaterialInterface>> SkeletalTealMaterials;

    UPROPERTY()
    TArray<TObjectPtr<UMaterialInterface>> SkeletalCopperMaterials;

    TSet<FKey> MovementKeys;
    int32 LastVisualTeam = INDEX_NONE;
    bool bLocalInteractHeld = false;
    bool bDevelopmentInteractHeld = false;
    // FIFO entries: ordinary action/value, or action -1 for held interaction.
    // Never replicated or populated by packaged-game input.
    TArray<TPair<int32, int32>> PendingDevelopmentInputs;
    static constexpr int32 MaxDevelopmentInputs = 32;
    double LastServerActionTime = -1.0;
    double LastServerInteractTime = -1.0;

    void MovementPressed(FKey Key);
    void MovementReleased(FKey Key);
    void LookYaw(float Value);
    void LookPitch(float Value);
    void StartInteract();
    void StopInteract();
    void ReleaseBall();
    void RequestPosition(FKey Key);
    void RequestTeam();
    void RequestReady();
    void RequestStoppage();
    void ToggleRoster();
    void SubmitAction(int32 Action, int32 Value = 0);
    void RefreshUniform();
    void RefreshHurley();
    void ResetLocalInput();

    UFUNCTION()
    void OnRep_TeamIndex();

    UFUNCTION()
    void OnRep_StunRemaining();

    UFUNCTION(Server, Reliable)
    void ServerStartInteract();

    UFUNCTION(Server, Reliable)
    void ServerStopInteract();

    UFUNCTION(Server, Reliable)
    void ServerAction(int32 Action, int32 Value, FVector Aim);
};

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "InputCoreTypes.h"
#include "BBFlightNetwork.h"
#include "BBFlightPolicy.h"
#include "BBRiderCharacter.generated.h"

class UCameraComponent;
class UMaterialInterface;
class UStaticMeshComponent;
class UMeshComponent;
class UInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;
class UPointLightComponent;
class APlayerController;

/** Native movement prediction with the authoritative stun speed constraint. */
UCLASS()
class BASKETBROOMRUNTIME_API UBBFlyingMovementComponent : public UCharacterMovementComponent
{
    GENERATED_BODY()

public:
    UBBFlyingMovementComponent();
    virtual float GetMaxSpeed() const override;
    virtual FNetworkPredictionData_Client* GetPredictionData_Client() const override;
    virtual void MoveAutonomous(float ClientTimeStamp, float DeltaTime, uint8 CompressedFlags, const FVector& NewAccel) override;
    void SetFlightInput(float Throttle, float Brake);
    uint8 FlightThrottle = 0, FlightBrake = 0;
    FBBFlightMoveContainer FlightNetworkMoves;
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

    /** Server MatchState advances spell effects with live match time. */
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Spells")
    float SpellCooldownRemaining = 0.f;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Spells")
    float ShieldRemaining = 0.f;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Spells")
    float ImpedimentRemaining = 0.f;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Spells")
    float DisarmRemaining = 0.f;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Spells")
    float Vitality = 100.f;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Spells")
    float LumosRemaining = 0.f;

    /** Sporting statuses: authority advances these with live match time only. */
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Spells")
    float RevealRemaining = 0.f;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Spells")
    float ConcealRemaining = 0.f;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Spells")
    float PetrificusRemaining = 0.f;
    UPROPERTY(ReplicatedUsing=OnRep_StunRemaining, BlueprintReadOnly, Category="Basketbroom|Spells")
    float TransformationRemaining = 0.f;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Spells")
    float ImperioRemaining = 0.f;

    UFUNCTION(BlueprintPure, Category="Basketbroom|Spells")
    bool HasSpellMovementLock() const { return StunRemaining > 0.f || PetrificusRemaining > 0.f || TransformationRemaining > 0.f; }

    /** Concealment changes presentation and AI detection, never physical collision. */
    UFUNCTION(BlueprintPure, Category="Basketbroom|Spells")
    bool IsConcealedFrom(const ABBRiderCharacter* Observer) const;

    /** Genuine match reset only; ordinary stoppages preserve ongoing effects. */
    UFUNCTION(BlueprintPure, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    bool DevelopmentIsHiddenFrom(const ABBRiderCharacter* Observer) const;
    void ResetSportSpellState();
    void ClearConcealmentViews();

    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|Spells")
    int32 SelectedSpell = 0;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|Spells")
    FString SpellFeedback;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|Spells")
    float SpellFeedbackRemaining = 0.f;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|HUD")
    bool bShowSpellbook = false;

    /** Authority sends an outcome to this rider's owning player only. */
    void NotifySpellResult(const FString& Message, uint64 ImpedimentAttackId = 0);
    /** Called only after the owning HUD actually draws the current feedback. */
    void MarkSpellFeedbackDisplayed();

    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|HUD")
    bool bShowRoster = false;

    /** Last meaningful local input; labels do not claim a physical transport. */
    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|Input")
    bool bUsingGamepad = false;

    /** 0 none, 1 Moderate possession, 2 Severe ejection, 3 Serious shot, 4 Moderate free shot; Menu confirms. */
    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|Input")
    int32 GamepadRefereeChoice = 0;

    UPROPERTY(EditDefaultsOnly, Category="Basketbroom|Input", meta=(ClampMin="1", ClampMax="360"))
    float GamepadYawDegreesPerSecond = 100.f;

    UPROPERTY(EditDefaultsOnly, Category="Basketbroom|Input", meta=(ClampMin="1", ClampMax="180"))
    float GamepadPitchDegreesPerSecond = 75.f;

    /** Server-approved energy. Clients send only analog intent in saved movement. */
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Flight") float FlightBoostCharge = 0.f;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Flight") float FlightSuperRemaining = 0.f;
    UPROPERTY(Replicated, BlueprintReadOnly, Category="Basketbroom|Flight") float FlightAccelerationScale = 1.f;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|Input") bool bInvertControllerAltitude = false;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|Input") bool bInvertControllerAimY = false;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|HUD") bool bPauseMenuOpen = false;
    bool bPauseMenuOwnsWorldPause = false;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|HUD") int32 PauseMenuSelection = 0;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Basketbroom|HUD") int32 PauseMenuPage = 0;
    UFUNCTION(BlueprintCallable, Category="Basketbroom|Input") void SetControllerInversion(bool bAltitude, bool bAim);
    void TogglePauseMenu();
    void ClosePauseMenu();
    bool HandlePauseMenuKey(FKey Key);
    void ClearFlightInput();
    bool AwardFlightBoost(uint8 OriginKind, uint64 EventId, float Amount);
    void ResetFlightBoost();
    void AcceptFlightInput(float Throttle, float Brake);
    bool CanUseFlightBoost() const;
    bool IsControllerPrecisionAim() const;
    UFUNCTION(BlueprintPure, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    TArray<float> DevelopmentGetFlightState() const;

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

    /** Tests the actual PlayerInput/binding boundary, never a gameplay action. */
    UFUNCTION(BlueprintCallable, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    bool DevelopmentInjectGamepadInput(FName KeyName, float Value);

    UFUNCTION(BlueprintCallable, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    bool DevelopmentFlushControllerInput();

    /** Processed LS/RS axes, catch/rise/descend keys, local catch, flush count. */
    UFUNCTION(BlueprintPure, Category="Basketbroom|Development", meta=(DevelopmentOnly))
    TArray<float> DevelopmentGetControllerInputState() const;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UPROPERTY()
    TArray<TObjectPtr<UStaticMeshComponent>> UniformParts;

    UPROPERTY()
    TArray<TObjectPtr<UStaticMeshComponent>> HurleyParts;

    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> WandParts;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> ShieldVisual;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> CockpitShieldVisual;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> WandLight;
    UPROPERTY() TObjectPtr<UPointLightComponent> WandLamp;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> ShieldMaterial;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> CockpitShieldMaterial;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> TransformationVisual;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> SportStatusRings;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> SportStatusMaterial;
    TSet<TWeakObjectPtr<APlayerController>> ConcealmentViewers;
    TMap<TWeakObjectPtr<UMeshComponent>, bool> TransformationHiddenBaseline;
    void InitializeSportSpellVisuals();
    void RefreshSportSpellVisuals();


    struct FSpellNotice { FString Message; uint64 AttackId = 0; double QueuedAt = 0.0; };
    TArray<FSpellNotice> PendingSpellNotices;
    TSet<uint64> AcknowledgedImpediments;
    uint64 ActiveImpedimentAttackId = 0;
    double SpellFeedbackDisplayedAt = -1.0;
    double ActiveSpellNoticeQueuedAt = 0.0;
    static constexpr int32 MaxOrdinarySpellNotices = 6;
    static constexpr int32 MaxCriticalSpellNotices = 8;
    static constexpr double SpellNoticeDeadline = 3.0;

    UPROPERTY()
    TObjectPtr<UMaterialInterface> TealMaterial;

    UPROPERTY()
    TObjectPtr<UMaterialInterface> CopperMaterial;

    UPROPERTY()
    TArray<TObjectPtr<UMaterialInterface>> SkeletalTealMaterials;

    UPROPERTY()
    TArray<TObjectPtr<UMaterialInterface>> SkeletalCopperMaterials;

    BBFlight::Energy FlightEnergy;
    double LastFlightInputTime = -1.0;
    void TickFlightEnergy(float DeltaSeconds);
    void SyncFlightEnergy();
    void LoadControllerSettings();
    void TickFlightControls(APlayerController* Player);
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

    struct FDevelopmentControllerInput { FKey Key; float Value = 0.f; bool bFlush = false; };
    TArray<FDevelopmentControllerInput> PendingControllerInputs;
    bool bObservedViewportFocus = false;
    bool bLastViewportFocused = false;
    bool bGamepadRequiresNeutral = false;
    bool bLastConductReviewPending = false;
    int32 LastGamepadConductFoulCount = -1;
    int32 ControllerInputFlushCount = 0;

    void BindControllerInput(UInputComponent* Input);
    void RegisterControllerInputLifecycle();
    void TickControllerInput(APlayerController* Player);
    void ObserveInputDevice(FKey Key);
    void GamepadPressed(FKey Key);
    void GamepadReleased(FKey Key);
    void GamepadMoveAxis(float Value);
    void GamepadLookYaw(float Value);
    void GamepadLookPitch(float Value);
    void ReleaseInteractInput();
    void SyncGamepadRefereeChoice();
    float ControllerAxis(const FKey Key) const;
    bool IsGamepadNeutral(APlayerController* Player) const;
    bool HasControllerViewportFocus(APlayerController* Player) const;
    void FlushOwnedControllerInput();
    void HandleInputDeviceConnection(EInputDeviceConnectionState State, FPlatformUserId User, FInputDeviceId Device);
    void HandleInputDevicePairing(FInputDeviceId Device, FPlatformUserId NewUser, FPlatformUserId OldUser);

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
    void ToggleSpellbook();
    void PreviousSpell();
    void NextSpell();
    void CastSelectedSpell();
    void RequestShield();
    void RequestBloodbroom();
    void RequestFreeShot();
    void RequestPossessionAward();
    void RequestPenaltyShot();
    void RequestEjection();
    void RequestModerateAdvantage();
    void ShowNextSpellNotice();
    void RefreshSpellVisuals();
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

    UFUNCTION(Client, Reliable)
    void ClientSpellResult(const FString& Message, uint64 ImpedimentAttackId);

    UFUNCTION(Server, Reliable)
    void ServerAcknowledgeImpediment(uint64 ImpedimentAttackId);
};

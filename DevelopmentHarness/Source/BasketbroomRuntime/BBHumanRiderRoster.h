#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "GameFramework/Actor.h"
#include "BBHumanRiderRoster.generated.h"

class UAnimSequence;
class UMaterialInterface;

/** Explicit garment-only mapping, filled after inspecting the assembled actor. */
USTRUCT(BlueprintType)
struct BASKETBROOMRUNTIME_API FBBHumanGarmentBinding
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FName ComponentName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FName MaterialSlotName;
    /** Verified LOD slot index; NAME-only bindings still require a unique name. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 MaterialSlotIndex = INDEX_NONE;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TObjectPtr<UMaterialInterface> TealMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TObjectPtr<UMaterialInterface> CopperMaterial;
};

/** Presentation only. ActorClass already contains the accepted fitted outfit. */
USTRUCT(BlueprintType)
struct BASKETBROOMRUNTIME_API FBBHumanRiderVariant
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TSubclassOf<AActor> ActorClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FName BodyComponentName;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TObjectPtr<UAnimSequence> FlightAnimation;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FTransform RelativeTransform = FTransform::Identity;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<FBBHumanGarmentBinding> Garments;
};

/** Optional, shared presentation data. Runtime copies mappings and never edits it. */
UCLASS(BlueprintType)
class BASKETBROOMRUNTIME_API UBBHumanRiderRoster : public UDataAsset
{
    GENERATED_BODY()

public:
    /** Ordered appearance identities, independent of the rider's team index. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Basketbroom|Art")
    TArray<FBBHumanRiderVariant> Variants;
};

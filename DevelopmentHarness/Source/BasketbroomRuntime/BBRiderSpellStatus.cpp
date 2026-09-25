#include "BBRiderCharacter.h"
#include "BBSpellCatalog.h"
#include "CollisionQueryParams.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/MeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

bool ABBRiderCharacter::IsConcealedFrom(const ABBRiderCharacter* Observer) const
{
    if (ConcealRemaining <= 0.f || Observer == this || !IsValid(Observer)
        || Observer->TeamIndex == TeamIndex) return false;
    const FBBSpellSpec* Reveal = BBSpellCatalog::Get(3);
    if (Observer->RevealRemaining <= 0.f || !Reveal
        || FVector::DistSquared(Observer->GetActorLocation(), GetActorLocation()) > FMath::Square(Reveal->Range))
        return true;
    // Revelio counters concealment within reach; opaque arena geometry still
    // obstructs detection. Physical collision and blind aimed hits stay intact.
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BasketbroomRevelio), false, Observer);
    Query.AddIgnoredActor(this);
    FHitResult Hit;
    return GetWorld() && GetWorld()->LineTraceSingleByChannel(Hit,
        Observer->GetActorLocation()+FVector(0,0,72), GetActorLocation()+FVector(0,0,40), ECC_Visibility, Query);
}

void ABBRiderCharacter::ResetSportSpellState()
{
    if (!HasAuthority()) return;
    StunRemaining = SpellCooldownRemaining = ShieldRemaining = 0.f;
    ImpedimentRemaining = DisarmRemaining = LumosRemaining = 0.f;
    RevealRemaining = ConcealRemaining = PetrificusRemaining = 0.f;
    TransformationRemaining = ImperioRemaining = 0.f;
    Vitality = 100.f;
    bInteractHeld = false;
    ClearConcealmentViews();
    ForceNetUpdate();
}

void ABBRiderCharacter::ClearConcealmentViews()
{
    for (const auto& Entry : ConcealmentViewers)
        if (APlayerController* Player = Entry.Key.Get())
            for (const TWeakObjectPtr<AActor>& Actor : Entry.Value)
                if (AActor* Hidden = Actor.Get()) Player->HiddenActors.Remove(Hidden);
    ConcealmentViewers.Reset();
}

void ABBRiderCharacter::InitializeSportSpellVisuals()
{
    // Original, non-colliding sporting proxy. This deliberately does not claim
    // Hogwarts Legacy transformation assets or possession of another character.
    UStaticMesh* Sphere = LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Basketbroom/Art/Materials/M_BB_RiderIvory.M_BB_RiderIvory"));
    TransformationVisual = NewObject<UStaticMeshComponent>(this,TEXT("SportTransformationOrb"),RF_Transient);
    SportStatusRings = NewObject<UInstancedStaticMeshComponent>(this,TEXT("SportSpellStatusRings"),RF_Transient);
    TransformationVisual->SetStaticMesh(Sphere);
    SportStatusRings->SetStaticMesh(Cylinder);
    for (UStaticMeshComponent* Part : {TransformationVisual.Get(), static_cast<UStaticMeshComponent*>(SportStatusRings.Get())})
    {
        AddInstanceComponent(Part);
        Part->SetupAttachment(GetMesh());
        Part->SetMobility(EComponentMobility::Movable);
        Part->SetMaterial(0,Base);
        Part->SetCollisionProfileName(TEXT("NoCollision"));
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Part->SetGenerateOverlapEvents(false);
        Part->SetCanEverAffectNavigation(false);
        Part->SetCastShadow(false);
        Part->SetVisibility(false);
        Part->ComponentTags.Add(TEXT("BB.Spell.Status"));
        Part->RegisterComponent();
    }
    TransformationVisual->SetRelativeScale3D(FVector(.74));
    if (UMaterialInstanceDynamic* Orb = TransformationVisual->CreateDynamicMaterialInstance(0))
    {
        Orb->SetVectorParameterValue(TEXT("Tint"),FLinearColor(.28f,.08f,.52f));
        Orb->SetScalarParameterValue(TEXT("Glow"),.7f);
    }
    for (int32 Ring=0; Ring<3; ++Ring)
        for (int32 Segment=0; Segment<28; ++Segment)
        {
            const double A=Segment*UE_TWO_PI/28.0, B=(Segment+1)*UE_TWO_PI/28.0;
            const double Radius=Ring==1 ? 49.0 : 38.0;
            const FVector Start(Radius*FMath::Cos(A),Radius*FMath::Sin(A),(Ring-1)*32.0);
            const FVector End(Radius*FMath::Cos(B),Radius*FMath::Sin(B),(Ring-1)*32.0);
            const FVector Along=End-Start;
            SportStatusRings->AddInstance(FTransform(FRotationMatrix::MakeFromZ(Along).ToQuat(),
                (Start+End)*.5,FVector(.018,.018,Along.Size()/100.0)));
        }
    SportStatusMaterial = SportStatusRings->CreateDynamicMaterialInstance(0);
}

void ABBRiderCharacter::RefreshSportSpellVisuals()
{
    if (!GetWorld()) return;
    // HiddenActors is camera-specific, so two local players can independently
    // detect the same opponent. Track only entries this spell added ourselves.
    for (auto It=ConcealmentViewers.CreateIterator(); It; ++It)
    {
        APlayerController* Player=It.Key().Get();
        if (!IsValid(Player) || !Player->IsLocalController()
            || !IsConcealedFrom(Cast<ABBRiderCharacter>(Player->GetPawn())))
        {
            if (IsValid(Player))
                for (const TWeakObjectPtr<AActor>& Actor : It.Value())
                    if (AActor* Hidden=Actor.Get()) Player->HiddenActors.Remove(Hidden);
            It.RemoveCurrent();
        }
    }
    TArray<AActor*> CosmeticActors;
    GetHumanCosmeticActors(CosmeticActors);
    TArray<AActor*> HiddenActors=CosmeticActors;
    HiddenActors.Add(this);
    for (FConstPlayerControllerIterator It=GetWorld()->GetPlayerControllerIterator(); It; ++It)
    {
        APlayerController* Player=It->Get();
        if (!IsValid(Player) || !Player->IsLocalController()) continue;
        const bool bHide=IsConcealedFrom(Cast<ABBRiderCharacter>(Player->GetPawn()));
        if (bHide)
            for (AActor* Actor : HiddenActors)
                if (IsValid(Actor) && !Player->HiddenActors.Contains(Actor))
                {
                    Player->HiddenActors.Add(Actor);
                    ConcealmentViewers.FindOrAdd(Player).Add(Actor);
                }
    }

    const bool bTransformed=TransformationRemaining>0.f;
    if (bTransformed)
    {
        TArray<UMeshComponent*> Meshes;
        GetComponents<UMeshComponent>(Meshes);
        TArray<UPrimitiveComponent*> Primitives;
        for (UMeshComponent* MeshPart : Meshes) Primitives.Add(MeshPart);
        for (AActor* Actor : CosmeticActors)
        {
            TArray<UPrimitiveComponent*> Parts;
            Actor->GetComponents(Parts);
            Primitives.Append(Parts);
        }
        for (UPrimitiveComponent* Part : Primitives)
        {
            if (!IsValid(Part) || Part==TransformationVisual || Part==SportStatusRings) continue;
            if (!TransformationHiddenBaseline.Contains(Part)) TransformationHiddenBaseline.Add(Part,Part->bHiddenInGame);
            Part->SetHiddenInGame(true,false);
        }
    }
    else if (!TransformationHiddenBaseline.IsEmpty())
    {
        for (const auto& Entry : TransformationHiddenBaseline)
            if (UPrimitiveComponent* Part=Entry.Key.Get()) Part->SetHiddenInGame(Entry.Value,false);
        TransformationHiddenBaseline.Reset();
    }
    if (WandLamp)
        WandLamp->SetVisibility(LumosRemaining>0.f && DisarmRemaining<=0.f && !bTransformed && ConcealRemaining<=0.f);
    if (TransformationVisual) TransformationVisual->SetVisibility(bTransformed);
    const bool bStatus=bTransformed || PetrificusRemaining>0.f || ImperioRemaining>0.f
        || RevealRemaining>0.f || ConcealRemaining>0.f;
    if (SportStatusRings)
    {
        SportStatusRings->SetVisibility(bStatus);
        SportStatusRings->SetRelativeRotation(FRotator(0,GetWorld()->GetTimeSeconds()*32.f,0));
    }
    if (SportStatusMaterial && bStatus)
    {
        const FLinearColor Color=bTransformed ? FLinearColor(.72f,.35f,1.f)
            : PetrificusRemaining>0.f ? FLinearColor(.95f,.70f,.28f)
            : ImperioRemaining>0.f ? FLinearColor(.12f,1.f,.35f)
            : ConcealRemaining>0.f ? FLinearColor(.16f,.65f,.72f) : FLinearColor(1.f,.82f,.25f);
        SportStatusMaterial->SetVectorParameterValue(TEXT("Tint"),Color);
        SportStatusMaterial->SetScalarParameterValue(TEXT("Glow"),1.25f);
    }
}

bool ABBRiderCharacter::DevelopmentIsHiddenFrom(const ABBRiderCharacter* Observer) const
{
#if !UE_BUILD_SHIPPING
    if (GetWorld() && GetWorld()->WorldType == EWorldType::PIE && IsValid(Observer) && Observer->GetWorld() == GetWorld())
        if (const APlayerController* Player = Cast<APlayerController>(Observer->GetController()))
        {
            if (!Player->IsLocalController() || !Player->HiddenActors.Contains(this)) return false;
            TArray<AActor*> Actors;
            GetHumanCosmeticActors(Actors);
            for (AActor* Actor : Actors)
                if (!Player->HiddenActors.Contains(Actor)) return false;
            return true;
        }
#endif
    return false;
}

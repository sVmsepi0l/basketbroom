#include "BBSpellArenaObject.h"
#include "BBMatchState.h"
#include "BBRiderCharacter.h"
#include "BBBall.h"
#include "BBArenaGeometry.h"
#include "CollisionQueryParams.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

ABBSpellArenaObject::ABBSpellArenaObject()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = .2f;
    bReplicates = true; bAlwaysRelevant = true; SetReplicateMovement(false);
    SetNetUpdateFrequency(30.f);
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("WorkshopRoot")));
    GetRootComponent()->SetMobility(EComponentMobility::Movable);
    Bay = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("OwnedSpellBay"));
    Construct = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PermittedConstruct"));
    Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("WorkshopInstructions"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Material(TEXT("/Basketbroom/Art/Materials/M_BB_RiderIvory.M_BB_RiderIvory"));
    CubeShape=Cube.Object; SphereShape=Sphere.Object; CylinderShape=Cylinder.Object;
    for (UStaticMeshComponent* Part : {Bay.Get(),Construct.Get()})
    {
        Part->SetupAttachment(GetRootComponent()); Part->SetStaticMesh(Cube.Object);
        Part->SetMaterial(0,Material.Object); Part->SetMobility(EComponentMobility::Movable);
        Part->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        Part->SetCollisionObjectType(ECC_WorldDynamic);
        Part->SetCollisionResponseToAllChannels(ECR_Ignore);
        Part->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
        Part->SetGenerateOverlapEvents(false); Part->SetCanEverAffectNavigation(false);
    }
    Bay->SetRelativeScale3D(FVector(1.6,1.6,.5));
    Construct->SetRelativeScale3D(FVector(.5));
    Construct->SetCollisionEnabled(ECollisionEnabled::NoCollision); Construct->SetVisibility(false);
    Label->SetupAttachment(GetRootComponent()); Label->SetRelativeLocation(FVector(0,0,-100));
    Label->SetHorizontalAlignment(EHorizTextAligment::EHTA_Center);
    Label->SetVerticalAlignment(EVerticalTextAligment::EVRTA_TextTop);
    Label->SetWorldSize(28.f); Label->SetTextRenderColor(FColor(230,235,240));
    Label->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Tags.Add(TEXT("BB.Spell.Workshop"));
}
void ABBSpellArenaObject::BeginPlay()
{
    Super::BeginPlay();
    BayMaterial=Bay->CreateDynamicMaterialInstance(0);
    ConstructMaterial=Construct->CreateDynamicMaterialInstance(0);
    RefreshPresentation();
}
void ABBSpellArenaObject::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    // Cosmetic ownership labels follow position swaps on each viewer. No
    // resource, construction movement or projectile clock advances here.
    if (WorkshopOwner && (LabelOwnerSlot!=WorkshopOwner->RosterIndex || LabelOwnerTeam!=WorkshopOwner->TeamIndex))
    {
        LabelOwnerSlot=WorkshopOwner->RosterIndex; LabelOwnerTeam=WorkshopOwner->TeamIndex;
        RefreshPresentation();
    }
}
void ABBSpellArenaObject::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABBSpellArenaObject,WorkshopOwner); DOREPLIFETIME(ABBSpellArenaObject,bUnlocked);
    DOREPLIFETIME(ABBSpellArenaObject,bConjured); DOREPLIFETIME(ABBSpellArenaObject,Integrity);
    DOREPLIFETIME(ABBSpellArenaObject,Form); DOREPLIFETIME(ABBSpellArenaObject,AncientMagicCharge);
    DOREPLIFETIME(ABBSpellArenaObject,ConstructPosition); DOREPLIFETIME(ABBSpellArenaObject,bInFlight);
}
void ABBSpellArenaObject::RefreshPresentation()
{
    Construct->SetStaticMesh(Form==1 ? SphereShape : Form==2 ? CylinderShape : CubeShape);
    Construct->SetWorldLocation(ConstructPosition);
    Construct->SetWorldScale3D(Integrity>0 ? FVector(.5) : FVector(.55,.55,.14));
    Construct->SetVisibility(bConjured);
    Construct->SetCollisionEnabled(bConjured && !bInFlight ? ECollisionEnabled::QueryOnly : ECollisionEnabled::NoCollision);
    const FLinearColor Team = WorkshopOwner && WorkshopOwner->TeamIndex ? FLinearColor(1.f,.35f,.12f) : FLinearColor(.08f,.75f,.8f);
    if (BayMaterial) { BayMaterial->SetVectorParameterValue(TEXT("Tint"),bUnlocked?Team:FLinearColor(.22f,.24f,.3f)); BayMaterial->SetScalarParameterValue(TEXT("Glow"),.25f); }
    if (ConstructMaterial)
    {
        ConstructMaterial->SetVectorParameterValue(TEXT("Tint"),Integrity>0?FLinearColor(.4f,.75f,1.f):FLinearColor(.18f,.13f,.15f));
        ConstructMaterial->SetScalarParameterValue(TEXT("Glow"),bInFlight?2.f:.4f);
    }
    const FString OwnerName=WorkshopOwner?FString::Printf(TEXT("%s %s"),WorkshopOwner->TeamIndex?TEXT("COPPER"):TEXT("TEAL"),*ABBMatchState::PositionName(WorkshopOwner->Position)):TEXT("OWNED");
    const TCHAR* State=!bUnlocked?TEXT("ALOHOMORA TO UNLOCK"):!bConjured?TEXT("CONJURE ONE PRACTICE OBJECT"):Integrity<=0?TEXT("REPARO TO RESTORE"):TEXT("ALTER / LIFT / VANISH / THROW");
    Label->SetText(FText::FromString(FString::Printf(TEXT("%s SPELL BAY\n%s\nANCIENT MAGIC %d / 100"),*OwnerName,State,AncientMagicCharge)));
    // Face inwards from the two side bays; labels never conceal gameplay HUD.
    Label->SetWorldRotation(FRotator(0,GetActorLocation().Y<0?90.f:-90.f,0));
    if (HasAuthority()) ForceNetUpdate();
}
bool ABBSpellArenaObject::IsUsableBy(const ABBRiderCharacter* Rider) const
{
    return HasAuthority() && IsValid(Rider) && WorkshopOwner==Rider && !bInFlight;
}
bool ABBSpellArenaObject::ApplyWorkshopSpell(ABBRiderCharacter* Rider,int32 SpellIndex,FVector /*Aim*/,FString& Feedback)
{
    if (!IsUsableBy(Rider)) { Feedback=TEXT("Only your own available spell bay can be changed."); return false; }
    if (SpellIndex==4)
    {
        if (bUnlocked) { Feedback=TEXT("Your spell bay is already unlocked."); return false; }
        bUnlocked=true; Feedback=TEXT("ALOHOMORA - your spell bay unlocked. Conjure one practice object here.");
    }
    else if (!bUnlocked) { Feedback=TEXT("ALOHOMORA must unlock your spell bay first."); return false; }
    else if (SpellIndex==23)
    {
        if (bConjured) { Feedback=TEXT("One construct per rider. Use Evanesco before conjuring another."); return false; }
        bConjured=true; Integrity=100; Form=0; ConstructPosition=Home(); bLifting=false;
        Feedback=TEXT("CONJURING - one owned practice construct. It cannot block riders or official balls.");
    }
    else if (!bConjured) { Feedback=TEXT("Conjure a practice object in your unlocked spell bay first."); return false; }
    else if (SpellIndex==22)
    {
        if (Integrity>=100) { Feedback=TEXT("Your construct is already intact."); return false; }
        Integrity=100; ConstructPosition=Home(); bLifting=false; Feedback=TEXT("REPARO - your practice construct restored.");
    }
    else if (SpellIndex==25)
    {
        bConjured=false; Integrity=0; ConstructPosition=Home(); bLifting=false;
        Feedback=TEXT("EVANESCO - your construct removed. Official equipment is protected.");
    }
    else if (Integrity<=0) { Feedback=TEXT("Your construct is broken. Use Reparo or Evanesco."); return false; }
    else if (SpellIndex==24)
    {
        Form=(Form+1)%3; Feedback=TEXT("ALTERING - changed your construct's form; sporting size and permissions preserved.");
    }
    else if (SpellIndex==21)
    {
        const FVector Destination=Home()+FVector(0,0,160);
        const bool bRaised=bLifting ? FVector::DistSquared(LiftDestination,Destination)<100 : FVector::DistSquared(ConstructPosition,Destination)<100;
        LiftDestination=bRaised?Home():Destination; bLifting=true;
        Feedback=bRaised?TEXT("WINGARDIUM LEVIOSA - construct lowered safely into its bay."):TEXT("WINGARDIUM LEVIOSA - construct lifted 1.6m within its own bay.");
    }
    else return false;
    RefreshPresentation(); return true;
}
bool ABBSpellArenaObject::DamageConstruct(float Damage)
{
    if (!HasAuthority() || !bConjured || bInFlight || Integrity<=0 || !FMath::IsFinite(Damage) || Damage<=0) return false;
    Integrity=FMath::Max(0.f,Integrity-Damage); RefreshPresentation(); return true;
}
bool ABBSpellArenaObject::SpendCharge(int32 Cost)
{
    if (!HasAuthority() || Cost<=0 || AncientMagicCharge<Cost) return false;
    AncientMagicCharge-=Cost; RefreshPresentation(); return true;
}
void ABBSpellArenaObject::EarnCharge(int32 Amount)
{
    if (!HasAuthority() || Amount<=0) return;
    AncientMagicCharge=FMath::Min(100,AncientMagicCharge+Amount); RefreshPresentation();
}
void ABBSpellArenaObject::Launch(ABBRiderCharacter* Target,FVector TargetPoint,uint64 AttackId)
{
    if (!HasAuthority() || !IsValid(Target) || !bConjured || Integrity<=0 || bInFlight || AttackId==0) return;
    FlightTarget=Target; FlightAttackId=AttackId; bInFlight=true; bLifting=false;
    FlightCasterSlot=WorkshopOwner?WorkshopOwner->RosterIndex:INDEX_NONE; FlightTargetSlot=Target->RosterIndex;
    const float TravelTime=FMath::Clamp(static_cast<float>(FVector::Distance(ConstructPosition,TargetPoint)/2600.0),.25f,1.5f);
    FlightVelocity=(TargetPoint-ConstructPosition)/TravelTime+FVector(0,0,300.f*TravelTime);
    FlightRemaining=2.f; RefreshPresentation();
}
void ABBSpellArenaObject::CancelFlight()
{
    if (!HasAuthority() || !bInFlight) return;
    bInFlight=false; Integrity=0; ConstructPosition=Home(); bLifting=false;
    FlightTarget.Reset(); FlightAttackId=0; FlightRemaining=0; RefreshPresentation();
}
void ABBSpellArenaObject::AdvanceLive(float DeltaSeconds,ABBMatchState* Match)
{
    if (!HasAuthority() || !IsValid(Match) || DeltaSeconds<=0 || !FMath::IsFinite(DeltaSeconds)) return;
    if (bLifting && !bInFlight && bConjured && Integrity>0)
    {
        ConstructPosition=FMath::VInterpConstantTo(ConstructPosition,LiftDestination,DeltaSeconds,160.f);
        if (ConstructPosition.Equals(LiftDestination,.01f)) bLifting=false;
        RefreshPresentation();
    }
    if (!bInFlight) return;
    if (!IsValid(WorkshopOwner) || !FlightTarget.IsValid() || WorkshopOwner->RosterIndex!=FlightCasterSlot
        || FlightTarget->RosterIndex!=FlightTargetSlot)
    { CancelFlight(); return; }
    float Remaining=DeltaSeconds;
    while (Remaining>0 && bInFlight)
    {
        const float Step=FMath::Min(Remaining,1.f/120.f); Remaining-=Step;
        const FVector From=ConstructPosition;
        const FVector To=From+FlightVelocity*Step+FVector(0,0,-300.f*Step*Step);
        FlightVelocity.Z-=600.f*Step; FlightRemaining-=Step;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(BasketbroomConstructFlight),false,this);
        Query.AddIgnoredActor(WorkshopOwner);
        for (TActorIterator<ABBBall> It(GetWorld()); It; ++It) Query.AddIgnoredActor(*It);
        FHitResult WorldHit,PawnHit;
        const bool bWorld=GetWorld()->SweepSingleByChannel(WorldHit,From,To,FQuat::Identity,ECC_Visibility,FCollisionShape::MakeSphere(ConstructRadius),Query);
        const bool bPawn=GetWorld()->SweepSingleByObjectType(PawnHit,From,To,FQuat::Identity,
            FCollisionObjectQueryParams(ECC_Pawn),FCollisionShape::MakeSphere(ConstructRadius),Query);
        const bool bPawnFirst=bPawn && (!bWorld || PawnHit.Time<WorldHit.Time || WorldHit.GetActor()==PawnHit.GetActor());
        if (bPawnFirst)
        {
            ABBRiderCharacter* Target=Cast<ABBRiderCharacter>(PawnHit.GetActor());
            const uint64 Attack=FlightAttackId; const FVector Impact=PawnHit.ImpactPoint; const FVector Direction=FlightVelocity.GetSafeNormal();
            const bool bSelected=Target==FlightTarget.Get();
            CancelFlight();
            // Bounded single-target throw: intervening riders consume the
            // object without acquiring a different victim or a second hit.
            if (bSelected) Match->ResolveThrownSpellImpact(this,Target,Impact,Direction,Attack);
            else if (WorkshopOwner) WorkshopOwner->NotifySpellResult(TEXT("ANCIENT MAGIC THROW - intercepted; construct broken."));
            return;
        }
        if (bWorld || !BBArena::ContainsSphere(To,ConstructRadius) || FlightRemaining<=0)
        {
            CancelFlight();
            if (WorkshopOwner) WorkshopOwner->NotifySpellResult(TEXT("ANCIENT MAGIC THROW - missed or struck the enclosure. Reparo restores the construct."));
            return;
        }
        ConstructPosition=To;
    }
    RefreshPresentation();
}

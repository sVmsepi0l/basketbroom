#include "BBMatchState.h"
#include "BBBall.h"
#include "BBArenaGeometry.h"
#include "BBRiderCharacter.h"
#include "BBSpellCatalog.h"
#include "BBSpellVisual.h"
#include "BBSpellArenaObject.h"
#include "EngineUtils.h"
#include "Components/StaticMeshComponent.h"
#include "Kismet/GameplayStatics.h"
#include "CollisionQueryParams.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerState.h"

bool ABBMatchState::CanOfficiate(const ABBRiderCharacter* Rider) const
{
    if (!HasAuthority() || !IsValid(Rider) || !Rider->IsPlayerControlled()) return false;
    if (GetNetMode() != NM_DedicatedServer) return Rider->IsLocallyControlled();
    int32 FirstPlayerId = MAX_int32;
    for (const ABBRiderCharacter* Other : Riders)
        if (IsValid(Other) && Other->IsPlayerControlled() && Other->GetPlayerState())
            FirstPlayerId = FMath::Min(FirstPlayerId, Other->GetPlayerState()->GetPlayerId());
    return Rider->GetPlayerState() && Rider->GetPlayerState()->GetPlayerId() == FirstPlayerId;
}

void ABBMatchState::SyncCombatRoster()
{
    if (!Combat || !Rules) return;
    const int32 CurrentPhase = static_cast<int32>(Rules->phase);
    if (CombatPhase != CurrentPhase)
    {
        Combat->reset_phase(); CombatPhase = CurrentPhase;
        for (ABBSpellArenaObject* Object : SpellWorkshops) if (IsValid(Object)) Object->CancelFlight();
    }
    Combat->set_live(Rules->status == BB::Status::Live);
    // Combat identity belongs to the rider across a position swap. Roster slots
    // remain the rules engine's discipline/position keys, not confirmation IDs.
    for (int32 Id=0; Id<16; ++Id)
    {
        ABBRiderCharacter* Occupant = CombatOccupants.FindRef(Id).Get();
        if (!IsValid(Occupant) || !Riders.Contains(Occupant))
        {
            CombatOccupants.Remove(Id);
            Combat->set_actor(Id,-1,false,true);
        }
    }
    for (ABBRiderCharacter* Rider : Riders)
    {
        if (!IsValid(Rider) || Rider->RosterIndex < 0 || Rider->RosterIndex >= 16) continue;
        int32 Id = CombatIndex(Rider);
        const bool bNew = Id == INDEX_NONE;
        if (bNew)
            for (int32 Free=0; Free<16; ++Free)
                if (!CombatOccupants.Contains(Free)) { Id=Free; CombatOccupants.Add(Id,Rider); break; }
        if (Id == INDEX_NONE) continue;
        const auto& P = Rules->players[Rider->RosterIndex];
        // Stun is validated separately for casting. A stunned target must remain
        // hittable so that a forbidden follow-up really takes effect before review.
        const bool bEligible = !P.ejected && !P.donnybrook_excluded && P.removed_until < 0;
        Combat->set_actor(Id, P.team, bEligible, bNew);
    }
}

int32 ABBMatchState::CombatIndex(const ABBRiderCharacter* Rider) const
{
    for (const auto& Entry : CombatOccupants) if (Entry.Value.Get() == Rider) return Entry.Key;
    return INDEX_NONE;
}

void ABBMatchState::TickSpells(float LiveDelta)
{
    if (!HasAuthority() || !Combat || LiveDelta <= 0) return;
    TickContextualSpells(LiveDelta);
    if (!bLive || (bConductReviewPending && !bConductAdvantageLive)) return;
    for (ABBRiderCharacter* R : Riders)
    {
        if (!IsValid(R)) continue;
        R->StunRemaining = FMath::Max(0.f, R->StunRemaining-LiveDelta);
        R->SpellCooldownRemaining = FMath::Max(0.f, R->SpellCooldownRemaining-LiveDelta);
        R->ShieldRemaining = FMath::Max(0.f, R->ShieldRemaining-LiveDelta);
        R->DisarmRemaining = FMath::Max(0.f, R->DisarmRemaining-LiveDelta);
        R->RevealRemaining = FMath::Max(0.f, R->RevealRemaining-LiveDelta);
        R->ConcealRemaining = FMath::Max(0.f, R->ConcealRemaining-LiveDelta);
        R->PetrificusRemaining = FMath::Max(0.f, R->PetrificusRemaining-LiveDelta);
        R->TransformationRemaining = FMath::Max(0.f, R->TransformationRemaining-LiveDelta);
        R->ImperioRemaining = FMath::Max(0.f, R->ImperioRemaining-LiveDelta);
        const bool bWasImpeded = R->ImpedimentRemaining > 0;
        R->ImpedimentRemaining = FMath::Max(0.f, R->ImpedimentRemaining-LiveDelta);
        if (bWasImpeded && R->ImpedimentRemaining == 0) Combat->recover_target(CombatIndex(R));
        if (R->StunRemaining <= 0) R->Vitality = FMath::Min(100.f, R->Vitality+LiveDelta*4.f);
    }
}

void ABBMatchState::ConfirmImpediment(ABBRiderCharacter* Rider, uint64 AttackId)
{
    if (!HasAuthority() || !Combat || !IsValid(Rider) || !Riders.Contains(Rider)) return;
    // The policy binds this receipt to an actual successful server attack and
    // that attack's caster. RPC callers cannot provide a victim or hit timestamp.
    Combat->confirm_impediment(AttackId, CombatIndex(Rider));
}

void ABBMatchState::CastSpell(ABBRiderCharacter* R, int32 SpellIndex, FVector Aim)
{
    const FBBSpellSpec* Spell = BBSpellCatalog::Get(SpellIndex);
    if (!HasAuthority() || !Rules || !Combat || !IsValid(R) || !Riders.Contains(R)
        || !Spell || !bLive || Rules->status != BB::Status::Live || (bConductReviewPending && !bConductAdvantageLive)
        || R->RosterIndex < 0 || R->RosterIndex >= 16 || Aim.ContainsNaN() || !Aim.IsNormalized()) return;
    if (!PendingPoints.empty())
    {
        // A spell request must not erase a legal ball event already observed.
        FlushPendingPointEvents();
        TickConductAdvantage(); SyncRules();
        if (Rules->status != BB::Status::Live) return;
    }
    SyncCombatRoster();
    const auto& Player = Rules->players[R->RosterIndex];
    if (Player.ejected || Player.donnybrook_excluded || Player.removed_until >= 0 || R->HasSpellMovementLock()) return;
    if (!BBSpellCatalog::IsImplemented(SpellIndex)) { R->NotifySpellResult(Spell->Description); return; }
    if (R->DisarmRemaining > 0) { R->NotifySpellResult(TEXT("Wand disarmed - recovering.")); return; }
    if (R->SpellCooldownRemaining > 0) { R->NotifySpellResult(TEXT("Wand recovering.")); return; }
    if (Spell->Effect == EBBSpellEffect::Workshop || Spell->Effect == EBBSpellEffect::Throw)
    {
        if (TryCastContextualSpell(R,SpellIndex,Aim)) R->SpellCooldownRemaining=Spell->Cooldown;
        R->ForceNetUpdate(); return;
    }
    if (Spell->Effect == EBBSpellEffect::Ancient)
    {
        ABBSpellArenaObject* Workshop=EnsureSpellWorkshop(R);
        if (!Workshop || !Workshop->SpendCharge(100))
        { R->NotifySpellResult(TEXT("ANCIENT MAGIC needs 100 charge. Legal applied enemy hits earn 20; objects and Ancient Magic cannot farm charge.")); return; }
    }
    R->SpellCooldownRemaining = Spell->Cooldown;
    if (Spell->Effect == EBBSpellEffect::Shield)
    {
        R->ShieldRemaining = 1.f;
        R->NotifySpellResult(TEXT("PROTEGO - shield raised.")); R->ForceNetUpdate(); return;
    }
    if (Spell->Effect == EBBSpellEffect::Light)
    {
        R->LumosRemaining = R->LumosRemaining > 0 ? 0.f : 1.f;
        R->NotifySpellResult(R->LumosRemaining > 0 ? TEXT("LUMOS") : TEXT("NOX")); R->ForceNetUpdate(); return;
    }

    if (Spell->Effect == EBBSpellEffect::Reveal)
    {
        R->RevealRemaining = 6.f;
        R->NotifySpellResult(TEXT("REVELIO - concealed opponents visible within 22m for 6 live seconds."));
        R->ForceNetUpdate(); return;
    }
    if (Spell->Effect == EBBSpellEffect::Conceal)
    {
        R->ConcealRemaining = 6.f;
        R->LumosRemaining = 0.f;
        R->NotifySpellResult(TEXT("DISILLUSIONMENT - concealed for 6 live seconds. Attacks and hits break concealment."));
        R->ForceNetUpdate(); return;
    }

    const FVector Start = R->GetActorLocation()+FVector(0,0,72);
    FVector End = Start+Aim*Spell->Range;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BasketbroomWand), false, R);
    // Other riders' workshop ornaments cannot be used as wand shields.
    for (ABBSpellArenaObject* Object : SpellWorkshops)
        if (IsValid(Object) && Object->WorkshopOwner!=R) Query.AddIgnoredActor(Object);
    // First clip the ray against visible world geometry. Pawn collision is queried
    // separately because Unreal's Pawn profile can ignore the Visibility channel.
    FHitResult Obstruction;
    const bool bObstructed = GetWorld()->LineTraceSingleByChannel(Obstruction, Start, End, ECC_Visibility, Query);
    if (bObstructed)
    {
        End = Obstruction.ImpactPoint;
        if (ABBSpellArenaObject* Object=Cast<ABBSpellArenaObject>(Obstruction.GetActor()))
        {
            R->ConcealRemaining=0.f;
            const bool bDamaged=Object->WorkshopOwner==R && Obstruction.GetComponent()==Object->Construct
                && Object->DamageConstruct(Spell->Damage);
            ABBSpellVisual::Spawn(GetWorld(),Start,End,SpellIndex,false);
            R->NotifySpellResult(bDamaged ? TEXT("Practice construct damaged. Reparo restores it; no Ancient Magic charge from objects.")
                : TEXT("This spell cannot change that workshop part. Official sporting equipment remains protected."));
            R->ForceNetUpdate(); return;
        }
    }
    FHitResult Hit;
    const bool bHit = GetWorld()->SweepSingleByObjectType(Hit, Start, End, FQuat::Identity,
        FCollisionObjectQueryParams(ECC_Pawn), FCollisionShape::MakeSphere(8.f), Query);
    ABBRiderCharacter* Target = bHit ? Cast<ABBRiderCharacter>(Hit.GetActor()) : nullptr;
    // A swept sphere extends beyond its endpoint. Do not let its radius reach a
    // rider through the geometry that clipped the original wand ray.
    if (Target && bObstructed && Obstruction.GetActor() != Target && Hit.Distance+8.f >= Obstruction.Distance)
        Target = nullptr;
    // Determine stealth eligibility before this attempted hostile cast breaks
    // concealment. Detection is server-derived; clients supply only their aim.
    const bool bBodyBind = Spell->Effect == EBBSpellEffect::BodyBind;
    bool bStealthEligible = false;
    if (bBodyBind && IsValid(Target))
    {
        const FVector ToCaster = R->GetActorLocation()-Target->GetActorLocation();
        const FVector TargetForward = Target->GetAimDirection().GetSafeNormal2D();
        bStealthEligible = R->IsConcealedFrom(Target)
            && ToCaster.SizeSquared() <= FMath::Square(Spell->Range)
            && FVector::DotProduct(TargetForward, ToCaster.GetSafeNormal2D()) < -.5f;
    }
    R->ConcealRemaining = 0.f;
    if (!IsValid(Target) || Target == R || !Riders.Contains(Target))
    {
        ABBSpellVisual::Spawn(GetWorld(),Start,End,SpellIndex,false);
        R->NotifySpellResult(BBSpellCatalog::Name(SpellIndex)+TEXT(" - missed.")); R->ForceNetUpdate(); return;
    }
    if (bBodyBind && !bStealthEligible)
    {
        R->NotifySpellResult(TEXT("PETRIFICUS - requires concealment, a target within 3.5m, and approach from behind."));
        R->ForceNetUpdate(); return;
    }
    ResolveSpellHit(R,Target,SpellIndex,Aim,Hit.ImpactPoint,Start);
}

void ABBMatchState::ResolveSpellHit(ABBRiderCharacter* R,ABBRiderCharacter* Target,int32 SpellIndex,
    FVector Aim,FVector ImpactPoint,FVector Start,uint64 ExistingAttackId)
{
    const FBBSpellSpec* Spell=BBSpellCatalog::Get(SpellIndex);
    if (!HasAuthority() || !Rules || !Combat || !Spell || !bLive || Rules->status!=BB::Status::Live
        || (bConductReviewPending && !bConductAdvantageLive) || !IsValid(R) || !IsValid(Target) || R==Target
        || !Riders.Contains(R) || !Riders.Contains(Target) || Aim.ContainsNaN() || !Aim.IsNormalized()
        || ImpactPoint.ContainsNaN()) return;
    SyncCombatRoster();
    for (const ABBRiderCharacter* Rider : {R,Target})
    {
        if (Rider->RosterIndex<0 || Rider->RosterIndex>=16) return;
        const auto& Player=Rules->players[Rider->RosterIndex];
        if (Player.ejected || Player.donnybrook_excluded || Player.removed_until>=0) return;
    }
    const FVector End=ImpactPoint;
    // Capsule upper region is a provisional server hit zone, not a head-bone
    // accuracy claim. Skeletal animation remains cosmetic and non-colliding.
    const bool bHead = End.Z-Target->GetActorLocation().Z > 65.f;
    BB::AttackSpec Spec;
    Spec.stun = Spell->bStun; Spec.impediment = Spell->bImpediment;
    Spec.unforgivable = Spell->bUnforgivable; Spec.aimed_at_head = bHead;
    BB::CombatDecision Cast;
    if (ExistingAttackId) Cast=Combat->validate_pending_hit(ExistingAttackId,CombatIndex(R),CombatIndex(Target));
    else Cast=Combat->begin_attack(CombatIndex(R),CombatIndex(Target),Spec);
    if (!Cast.accepted)
    {
        R->NotifySpellResult(TEXT("Target is not in live play.")); R->ForceNetUpdate(); return;
    }
    const bool bBlocked = Target->ShieldRemaining > 0 && !Spell->bUnforgivable;
    ABBSpellVisual::Spawn(GetWorld(),Start,End,SpellIndex,bBlocked);
    if (bBlocked)
    {
        Combat->resolve_hit(Cast.attack_id,BB::HitOutcome::Blocked,bHead);
        R->NotifySpellResult(TEXT("PROTEGO - target blocked the hit."));
        Target->NotifySpellResult(TEXT("PROTEGO - hit blocked.")); R->ForceNetUpdate(); return;
    }

    // Remember the denied scoring ball before a stun drops it. This is an
    // observed target context, not a client-selected restitution value.
    int32 AffectedScoringBall = -1;
    for (const ABBBall* Ball : Balls)
        if (IsValid(Ball) && Ball->BallIndex <= 2 && Ball->Holder == Target) AffectedScoringBall = Ball->BallIndex;
    // Apply the authoritative effect before recording/refereeing any violation.
    Target->ConcealRemaining = 0.f;
    Target->Vitality = FMath::Max(0.f,Target->Vitality-Spell->Damage);
    switch (Spell->Effect)
    {
    case EBBSpellEffect::Stun: Target->StunRemaining = FMath::Max(Target->StunRemaining,1.2f); break;
    case EBBSpellEffect::BodyBind:
        Target->PetrificusRemaining = FMath::Max(Target->PetrificusRemaining,2.5f);
        Target->StunRemaining = FMath::Max(Target->StunRemaining,2.5f); break;
    case EBBSpellEffect::Transform:
        Target->TransformationRemaining = FMath::Max(Target->TransformationRemaining,3.f);
        Target->ImpedimentRemaining = FMath::Max(Target->ImpedimentRemaining,3.f);
        Target->ShieldRemaining = Target->LumosRemaining = 0.f; break;
    case EBBSpellEffect::Confuse:
        Target->ImperioRemaining = FMath::Max(Target->ImperioRemaining,3.f); break;
    case EBBSpellEffect::Slow: Target->ImpedimentRemaining = FMath::Max(Target->ImpedimentRemaining,3.f); break;
    case EBBSpellEffect::Freeze:
        Target->ImpedimentRemaining = FMath::Max(Target->ImpedimentRemaining,1.5f);
        Target->StunRemaining = FMath::Max(Target->StunRemaining,1.5f); break;
    case EBBSpellEffect::Lift:
        Target->ImpedimentRemaining = FMath::Max(Target->ImpedimentRemaining,2.f);
        Target->GetCharacterMovement()->AddImpulse(FVector(0,0,650),true); break;
    case EBBSpellEffect::Pull:
        Target->GetCharacterMovement()->AddImpulse((R->GetActorLocation()-Target->GetActorLocation()).GetSafeNormal()*1000.f,true); break;
    case EBBSpellEffect::Ancient:
    case EBBSpellEffect::Throw:
    case EBBSpellEffect::Push: Target->GetCharacterMovement()->AddImpulse(Aim*1200.f,true); break;
    case EBBSpellEffect::Down: Target->GetCharacterMovement()->AddImpulse(FVector(0,0,-1000),true); break;
    case EBBSpellEffect::Flip: Target->GetCharacterMovement()->AddImpulse(FVector(0,0,1000),true); break;
    case EBBSpellEffect::Disarm: Target->DisarmRemaining = FMath::Max(Target->DisarmRemaining,2.5f); break;
    case EBBSpellEffect::Knockout: Target->StunRemaining = FMath::Max(Target->StunRemaining,6.f); break;
    case EBBSpellEffect::Curse: Target->StunRemaining = FMath::Max(Target->StunRemaining,2.f); break;
    default: break;
    }
    if (Target->Vitality <= 0)
    {
        Target->StunRemaining = FMath::Max(Target->StunRemaining,3.f);
        Target->Vitality = 50.f;
    }
    if (Target->HasSpellMovementLock())
    {
        Target->GetCharacterMovement()->StopMovementImmediately();
        Target->bInteractHeld = false;
        // Resolve this actual hit receipt before a lost-possession whistle
        // freezes Combat; otherwise the applied illegal hit would lose its call.
        Release(Target,FVector::ZeroVector,true);
    }
    const auto Decision = Combat->resolve_hit(Cast.attack_id, Spell->bImpediment ? BB::HitOutcome::Impeded : BB::HitOutcome::Contact,
        bHead, Spell->bImpediment ? FMath::CeilToInt(Target->ImpedimentRemaining*1000.f) : -1);
    // Only accepted, legal hostile rider contact earns a resource. No friendly
    // farming, blocked/missed casts, practice objects or Ancient Magic loops.
    if (Decision.legal() && Target->TeamIndex!=R->TeamIndex && SpellIndex!=29 && SpellIndex!=30)
        if (ABBSpellArenaObject* Workshop=EnsureSpellWorkshop(R)) Workshop->EarnCharge(20);
    Target->ForceNetUpdate(); R->ForceNetUpdate();
    R->NotifySpellResult(BBSpellCatalog::Name(SpellIndex)+(Spell->bImpediment ? TEXT(" HIT - target impeded. No follow-up stun.") : TEXT(" HIT")),
        Spell->bImpediment && Decision.accepted ? Cast.attack_id : 0);
    Target->NotifySpellResult(TEXT("Hit by ")+BBSpellCatalog::Name(SpellIndex));
    if (!Decision.requires_adjudication()) { TickConductAdvantage(); return; }

    RegisterConductHit(R,Target,SpellIndex,AffectedScoringBall,Decision.violations,Cast.attack_id,bHead);
}

ABBSpellArenaObject* ABBMatchState::GetSpellWorkshop(const ABBRiderCharacter* Rider) const
{
    if (!IsValid(Rider) || !GetWorld()) return nullptr;
    // Clients discover independently replicated actors; they do not rely on an
    // authority-only array or on a client-provided object reference.
    for (TActorIterator<ABBSpellArenaObject> It(GetWorld()); It; ++It)
        if (It->WorkshopOwner==Rider) return *It;
    return nullptr;
}
int32 ABBMatchState::GetAncientMagicCharge(const ABBRiderCharacter* Rider) const
{
    const ABBSpellArenaObject* Object=GetSpellWorkshop(Rider);
    return Object ? Object->AncientMagicCharge : 0;
}
ABBSpellArenaObject* ABBMatchState::EnsureSpellWorkshop(ABBRiderCharacter* Rider)
{
    if (!HasAuthority() || !IsValid(Rider) || !Riders.Contains(Rider) || !Rider->IsPlayerControlled()) return nullptr;
    if (ABBSpellArenaObject* Existing=GetSpellWorkshop(Rider)) return Existing;
    if (Rider->RosterIndex<0 || Rider->RosterIndex>=16 || SpellWorkshops.Num()>=16) return nullptr;
    // Original, named side bays occupy provisional tactical space. They never
    // change the arena, hoop geometry or ball/rider collision responses.
    const FVector Location((Rider->RosterIndex%8-3.5)*1100.0,
        (Rider->TeamIndex?1.0:-1.0)*(BBArena::HalfWidth-400.0),1450.0);
    const FTransform Transform(FRotator::ZeroRotator,Location);
    ABBSpellArenaObject* Object=GetWorld()->SpawnActorDeferred<ABBSpellArenaObject>(ABBSpellArenaObject::StaticClass(),
        Transform,this,nullptr,ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!Object) return nullptr;
    Object->WorkshopOwner=Rider; Object->ConstructPosition=Location+FVector(0,0,180);
    Object->SetFlags(RF_Transient); Object->FinishSpawning(Transform);
    SpellWorkshops.Add(Object); Object->ForceNetUpdate(); return Object;
}
void ABBMatchState::ResetContextualSpells()
{
    if (!HasAuthority()) return;
    for (ABBSpellArenaObject* Object : SpellWorkshops) if (IsValid(Object)) Object->Destroy();
    SpellWorkshops.Empty();
}
void ABBMatchState::TickContextualSpells(float LiveDelta)
{
    if (!HasAuthority() || !bLive || LiveDelta<=0) return;
    for (int32 I=SpellWorkshops.Num()-1; I>=0; --I)
    {
        ABBSpellArenaObject* Object=SpellWorkshops[I];
        if (!IsValid(Object) || !IsValid(Object->WorkshopOwner) || !Riders.Contains(Object->WorkshopOwner)
            || !Object->WorkshopOwner->IsPlayerControlled())
        {
            if (IsValid(Object)) Object->Destroy();
            SpellWorkshops.RemoveAt(I); continue;
        }
        Object->AdvanceLive(LiveDelta,this);
        // A physical throw can itself create a conduct stoppage. Never advance
        // a second projectile beyond that adjudication boundary in this tick.
        if (!bLive || (bConductReviewPending && !bConductAdvantageLive)) return;
    }
    for (ABBRiderCharacter* Rider : Riders)
        if (IsValid(Rider) && Rider->IsPlayerControlled()) EnsureSpellWorkshop(Rider);
}
bool ABBMatchState::TryCastContextualSpell(ABBRiderCharacter* R,int32 SpellIndex,FVector Aim)
{
    const FBBSpellSpec* Spell=BBSpellCatalog::Get(SpellIndex);
    ABBSpellArenaObject* Owned=EnsureSpellWorkshop(R);
    if (!Spell || !Owned) { R->NotifySpellResult(TEXT("No available owned spell bay.")); return false; }
    const FVector Start=R->GetActorLocation()+FVector(0,0,72);
    if (SpellIndex!=30)
    {
        FHitResult Hit;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(BasketbroomWorkshop),false,R);
        GetWorld()->LineTraceSingleByChannel(Hit,Start,Start+Aim*Spell->Range,ECC_Visibility,Query);
        ABBSpellArenaObject* Object=Cast<ABBSpellArenaObject>(Hit.GetActor());
        const bool bBaySpell=SpellIndex==4 || SpellIndex==23;
        if (Object!=Owned || Hit.GetComponent()!=(bBaySpell?Owned->Bay.Get():Owned->Construct.Get()))
        {
            R->NotifySpellResult(bBaySpell?TEXT("Aim at your own side-bay locker within 9m. Official equipment is protected.")
                :TEXT("Aim at your own practice construct within 9m. Other riders and official equipment are protected."));
            return false;
        }
        FString Feedback;
        const bool bApplied=Owned->ApplyWorkshopSpell(R,SpellIndex,Aim,Feedback);
        if (bApplied) ABBSpellVisual::Spawn(GetWorld(),Start,Hit.ImpactPoint,SpellIndex,false);
        R->NotifySpellResult(Feedback); return bApplied;
    }
    if (!Owned->IsUsableBy(R) || !Owned->bConjured || Owned->Integrity<=0
        || FVector::DistSquared(Start,Owned->ConstructPosition)>FMath::Square(600.f))
    { R->NotifySpellResult(TEXT("ANCIENT MAGIC THROW needs your intact, available construct within 6m.")); return false; }
    if (Owned->AncientMagicCharge<25)
    { R->NotifySpellResult(TEXT("ANCIENT MAGIC THROW needs 25 charge. Legal enemy rider hits earn 20; practice objects earn none.")); return false; }
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BasketbroomConstructLaunch),false,R);
    for (ABBSpellArenaObject* Object : SpellWorkshops) if (IsValid(Object)) Query.AddIgnoredActor(Object);
    FHitResult Access;
    if (GetWorld()->LineTraceSingleByChannel(Access,Start,Owned->ConstructPosition,ECC_Visibility,Query))
    { R->NotifySpellResult(TEXT("Your construct is obstructed.")); return false; }
    FVector End=Start+Aim*Spell->Range;
    FHitResult Wall,Hit;
    const bool bWall=GetWorld()->LineTraceSingleByChannel(Wall,Start,End,ECC_Visibility,Query);
    if (bWall) End=Wall.ImpactPoint;
    const bool bHit=GetWorld()->SweepSingleByObjectType(Hit,Start,End,FQuat::Identity,
        FCollisionObjectQueryParams(ECC_Pawn),FCollisionShape::MakeSphere(8.f),Query);
    ABBRiderCharacter* Target=bHit?Cast<ABBRiderCharacter>(Hit.GetActor()):nullptr;
    if (!IsValid(Target) || Target==R || !Riders.Contains(Target)
        || (bWall && Wall.GetActor()!=Target && Hit.Distance+8.f>=Wall.Distance))
    { R->NotifySpellResult(TEXT("ANCIENT MAGIC THROW - aim at one live rider within 30m. No charge spent.")); return false; }
    BB::AttackSpec Spec; Spec.aimed_at_head=Hit.ImpactPoint.Z-Target->GetActorLocation().Z>65.f;
    const auto Attack=Combat->begin_attack(CombatIndex(R),CombatIndex(Target),Spec);
    if (!Attack.accepted)
    { R->NotifySpellResult(TEXT("Target is not in live play.")); return false; }
    if (!Owned->SpendCharge(25)) return false;
    R->ConcealRemaining=0.f;
    Owned->Launch(Target,Hit.ImpactPoint,Attack.attack_id);
    R->NotifySpellResult(TEXT("ANCIENT MAGIC THROW - construct launched; world and riders can intercept. Reparo after impact."));
    return true;
}
void ABBMatchState::ResolveThrownSpellImpact(ABBSpellArenaObject* Object,ABBRiderCharacter* Target,
    FVector ImpactPoint,FVector Direction,uint64 AttackId)
{
    if (!HasAuthority() || !IsValid(Object) || !SpellWorkshops.Contains(Object) || !IsValid(Object->WorkshopOwner)
        || GetSpellWorkshop(Object->WorkshopOwner)!=Object || AttackId==0) return;
    ResolveSpellHit(Object->WorkshopOwner,Target,30,Direction,ImpactPoint,Object->Home(),AttackId);
}

void ABBMatchState::ReviewConduct(ABBRiderCharacter* Referee, int32 Disposition)
{
    if (!CanOfficiate(Referee) || !Rules || !bConductReviewPending || Rules->status == BB::Status::Live
        || ConductOffender < 0 || ConductOffender >= 16 || ConductEvidence.IsEmpty()) return;
    if (Disposition < 9 || Disposition > 12 || bPenaltyShotActive) return;
    const bool bEject = Disposition == 11, bFree = Disposition == 12, bShot = Disposition == 10 || bFree;
    const FConductEvidence Evidence = ConductEvidence[0];
    if (Evidence.PenaltyId > 0 && (bEject || (bShot && !bFree)))
    {
        Referee->NotifySpellResult(TEXT("This host-selected Moderate advantage owes F6 free shot or F7 possession; a later separate foul keeps its own ruling."));
        return;
    }
    if (!bShot && !bEject && Rules->status == BB::Status::Review)
    {
        Referee->NotifySpellResult(TEXT("Post-termination possession cannot resume live play; serve the owed F6 free shot before certification."));
        return;
    }
    // Keep original observed identity, ball and time. The host selects a tier
    // for an unclassified foul, or serves the previously selected Moderate.
    const BB::Match Previous = *Rules;
    const int Id = Evidence.PenaltyId > 0 ? Evidence.PenaltyId
        : Rules->record_penalty(Evidence.Offender,TCHAR_TO_UTF8(*Evidence.Reason),
            bEject ? BB::Severity::Severe : bShot && !bFree ? BB::Severity::Serious : BB::Severity::Moderate,
            Evidence.Ball,Evidence.CommittedMs);
    bool bApplied = false;
    if (bEject) bApplied = Id > 0 && Rules->resolve_penalty(Id,"host BB-0 playtest referee: ejection",true);
    else if (bShot) bApplied = Id > 0 && BeginConductPenaltyShot(Id,bFree);
    else
    {
        for (int32 BallIndex : {0,1,2})
            if (Id > 0 && Rules->queue_conduct_possession_award(Id,BallIndex,ConductVictimTeam))
            { bApplied = true; ConductRestartBall = BallIndex; break; }
    }
    if (!bApplied)
    {
        *Rules = Previous;
        Referee->NotifySpellResult(TEXT("That disposition cannot be served now; conduct review remains pending."));
        return;
    }
    ConductEvidence[0].PenaltyId = Id;
    CompleteConductEvidence();
    if (bShot) { SyncRules(); Say(PenaltyShotStatus); return; }
    if (!bConductReviewPending)
        ConductReviewStatus = bEject ? TEXT("EJECTION SERVED - Host: ENTER to resume")
                                    : TEXT("POSSESSION AWARD QUEUED - Host: ENTER to serve restart");
    SyncRules(); Say(ConductReviewStatus);
}

TArray<int32> ABBMatchState::DevelopmentGetConductState() const
{
#if !UE_BUILD_SHIPPING
    if (HasAuthority() && GetWorld() && GetWorld()->WorldType == EWorldType::PIE)
        return {ConductFoulCount,bConductReviewPending ? 1 : 0,ConductOffender,LastConductViolations,
            static_cast<int32>(FMath::Min<uint64>(LastConductAttack,MAX_int32)),ConductRestartBall};
#endif
    return {};
}

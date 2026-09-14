#include "BBMatchState.h"
#include "BBBall.h"
#include "BBRiderCharacter.h"
#include "BBSpellCatalog.h"
#include "BBSpellVisual.h"
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
    if (CombatPhase != CurrentPhase) { Combat->reset_phase(); CombatPhase = CurrentPhase; }
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
    for (ABBRiderCharacter* R : Riders)
    {
        if (!IsValid(R)) continue;
        R->SpellCooldownRemaining = FMath::Max(0.f, R->SpellCooldownRemaining-LiveDelta);
        R->ShieldRemaining = FMath::Max(0.f, R->ShieldRemaining-LiveDelta);
        R->DisarmRemaining = FMath::Max(0.f, R->DisarmRemaining-LiveDelta);
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
        || !Spell || !bLive || Rules->status != BB::Status::Live || bConductReviewPending
        || R->RosterIndex < 0 || R->RosterIndex >= 16 || Aim.ContainsNaN() || !Aim.IsNormalized()) return;
    if (!PendingPoints.empty())
    {
        // A spell request must not erase a legal ball event already observed.
        Rules->process_batch(Rules->now_ms, PendingPoints);
        PendingPoints.clear(); SyncRules();
        if (Rules->status != BB::Status::Live) return;
    }
    SyncCombatRoster();
    const auto& Player = Rules->players[R->RosterIndex];
    if (Player.ejected || Player.donnybrook_excluded || Player.removed_until >= 0 || R->StunRemaining > 0) return;
    if (!BBSpellCatalog::IsImplemented(SpellIndex)) { R->NotifySpellResult(Spell->Description); return; }
    if (R->DisarmRemaining > 0) { R->NotifySpellResult(TEXT("Wand disarmed - recovering.")); return; }
    if (R->SpellCooldownRemaining > 0) { R->NotifySpellResult(TEXT("Wand recovering.")); return; }
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

    const FVector Start = R->GetActorLocation()+FVector(0,0,72);
    FVector End = Start+Aim*Spell->Range;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BasketbroomWand), false, R);
    // First clip the ray against visible world geometry. Pawn collision is queried
    // separately because Unreal's Pawn profile can ignore the Visibility channel.
    FHitResult Obstruction;
    const bool bObstructed = GetWorld()->LineTraceSingleByChannel(Obstruction, Start, End, ECC_Visibility, Query);
    if (bObstructed)
        End = Obstruction.ImpactPoint;
    FHitResult Hit;
    const bool bHit = GetWorld()->SweepSingleByObjectType(Hit, Start, End, FQuat::Identity,
        FCollisionObjectQueryParams(ECC_Pawn), FCollisionShape::MakeSphere(8.f), Query);
    ABBRiderCharacter* Target = bHit ? Cast<ABBRiderCharacter>(Hit.GetActor()) : nullptr;
    // A swept sphere extends beyond its endpoint. Do not let its radius reach a
    // rider through the geometry that clipped the original wand ray.
    if (Target && bObstructed && Obstruction.GetActor() != Target && Hit.Distance+8.f >= Obstruction.Distance)
        Target = nullptr;
    if (!IsValid(Target) || Target == R || !Riders.Contains(Target))
    {
        ABBSpellVisual::Spawn(GetWorld(),Start,End,SpellIndex,false);
        R->NotifySpellResult(BBSpellCatalog::Name(SpellIndex)+TEXT(" - missed.")); R->ForceNetUpdate(); return;
    }
    End = Hit.ImpactPoint;
    // Capsule upper region is a provisional server hit zone, not a head-bone
    // accuracy claim. Skeletal animation remains cosmetic and non-colliding.
    const bool bHead = End.Z-Target->GetActorLocation().Z > 65.f;
    BB::AttackSpec Spec;
    Spec.stun = Spell->bStun; Spec.impediment = Spell->bImpediment;
    Spec.unforgivable = Spell->bUnforgivable; Spec.aimed_at_head = bHead;
    const auto Cast = Combat->begin_attack(CombatIndex(R),CombatIndex(Target),Spec);
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
    Target->Vitality = FMath::Max(0.f,Target->Vitality-Spell->Damage);
    switch (Spell->Effect)
    {
    case EBBSpellEffect::Stun: Target->StunRemaining = FMath::Max(Target->StunRemaining,1.2f); break;
    case EBBSpellEffect::Slow: Target->ImpedimentRemaining = FMath::Max(Target->ImpedimentRemaining,3.f); break;
    case EBBSpellEffect::Freeze:
        Target->ImpedimentRemaining = FMath::Max(Target->ImpedimentRemaining,1.5f);
        Target->StunRemaining = FMath::Max(Target->StunRemaining,1.5f); break;
    case EBBSpellEffect::Lift:
        Target->ImpedimentRemaining = FMath::Max(Target->ImpedimentRemaining,2.f);
        Target->GetCharacterMovement()->AddImpulse(FVector(0,0,650),true); break;
    case EBBSpellEffect::Pull:
        Target->GetCharacterMovement()->AddImpulse((R->GetActorLocation()-Target->GetActorLocation()).GetSafeNormal()*1000.f,true); break;
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
    if (Target->StunRemaining > 0)
    {
        Target->GetCharacterMovement()->StopMovementImmediately();
        Target->bInteractHeld = false;
        Release(Target,FVector::ZeroVector);
    }
    const auto Decision = Combat->resolve_hit(Cast.attack_id, Spell->bImpediment ? BB::HitOutcome::Impeded : BB::HitOutcome::Contact,
        bHead, Spell->bImpediment ? FMath::CeilToInt(Target->ImpedimentRemaining*1000.f) : -1);
    Target->ForceNetUpdate(); R->ForceNetUpdate();
    R->NotifySpellResult(BBSpellCatalog::Name(SpellIndex)+(Spell->bImpediment ? TEXT(" HIT - target impeded. No follow-up stun.") : TEXT(" HIT")),
        Spell->bImpediment && Decision.accepted ? Cast.attack_id : 0);
    Target->NotifySpellResult(TEXT("Hit by ")+BBSpellCatalog::Name(SpellIndex));
    if (!Decision.requires_adjudication()) return;

    TArray<FString> Reasons;
    if (Decision.has(BB::ConductViolation::Unforgivable)) Reasons.Add(TEXT("UNFORGIVABLE"));
    if (Decision.has(BB::ConductViolation::Headshot)) Reasons.Add(TEXT("HEADSHOT"));
    if (Decision.has(BB::ConductViolation::Mobbing)) Reasons.Add(TEXT("MOB ATTACK > 3"));
    if (Decision.has(BB::ConductViolation::DoubleTap)) Reasons.Add(TEXT("DOUBLE-TAP"));
    if (Decision.has(BB::ConductViolation::PhysicalHolding)) Reasons.Add(TEXT("PHYSICAL HOLDING"));
    ++ConductFoulCount; LastConductAttack = Cast.attack_id;
    LastConductViolations = static_cast<int32>(Decision.violations);
    LastConductCall = FString::Join(Reasons,TEXT(" + "));
    ConductOffender = R->RosterIndex; ConductVictimTeam = 1-R->TeamIndex;
    ConductVictimSlot = Target->RosterIndex; ConductBall = AffectedScoringBall;
    ConductMark = Target->GetActorLocation();
    ConductMark.X = FMath::Clamp(ConductMark.X,-5900.f,5900.f);
    ConductMark.Y = FMath::Clamp(ConductMark.Y,-2700.f,2700.f);
    ConductMark.Z = FMath::Clamp(ConductMark.Z,400.f,3800.f);
    bConductReviewPending = true;
    ConductReviewStatus = TEXT("PLAYTEST REFEREE - Host: F7 possession / F8 shot + removal / F9 ejection");
    Rules->pause("BB-0 conduct review after applied hit");
    SyncRules();
    Say(TEXT("BB-0 FOUL: ")+LastConductCall+TEXT(" - hit applied; referee decision due."));
    UE_LOG(LogTemp,Display,TEXT("BB0 applied hit then review: id=%llu caster=%d target=%d spell=%d flags=%d"),
        static_cast<unsigned long long>(Cast.attack_id),R->RosterIndex,Target->RosterIndex,SpellIndex,LastConductViolations);
}

void ABBMatchState::ReviewConduct(ABBRiderCharacter* Referee, int32 Disposition)
{
    if (!CanOfficiate(Referee) || !Rules || !bConductReviewPending || Rules->status == BB::Status::Live
        || ConductOffender < 0 || ConductOffender >= 16) return;
    if (Disposition < 9 || Disposition > 11 || bPenaltyShotActive) return;
    const bool bEject = Disposition == 11, bShot = Disposition == 10;
    // Host-selected playtest severity; no automatic foul-to-tier mapping.
    // A Serious removal must accompany an actual reserved shot and restart.
    const BB::Match Previous = *Rules;
    const int Id = Rules->record_penalty(ConductOffender,TCHAR_TO_UTF8(*LastConductCall),
        bEject ? BB::Severity::Severe : bShot ? BB::Severity::Serious : BB::Severity::Moderate, ConductBall);
    bool bApplied = false;
    if (bEject) bApplied = Id > 0 && Rules->resolve_penalty(Id,"host BB-0 playtest referee: ejection",true);
    else if (bShot) bApplied = Id > 0 && BeginConductPenaltyShot(Id);
    else
    {
        // Preserve an existing goal/Crown remedy. Prefer the Quaffle, then an
        // available Quark; a foul must not force ejection just because ball 0
        // was already awaiting its own legitimate restart.
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
    bConductReviewPending = false;
    if (bShot) { SyncRules(); Say(PenaltyShotStatus); return; }
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

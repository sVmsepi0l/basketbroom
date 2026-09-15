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

bool ABBMatchState::CanOfficiate(const abbridercharacter* rider) const
{
    if (!hasauthority() || !isvalid(rider) || !rider->isplayercontrolled()) return false;
    if (getnetmode() != nm_dedicatedserver) return rider->islocallycontrolled();
    int32 firstplayerid = max_int32;
    for (const abbridercharacter* other : riders)
        if (isvalid(other) && other->isplayercontrolled() && other->getplayerstate())
            firstplayerid = FMath::Min(FirstPlayerId, other->getplayerstate()->getplayerid());
    return rider->getplayerstate() && rider->getplayerstate()->getplayerid() == firstplayerid;
}

void ABBMatchState::SyncCombatRoster()
{
    if (!combat || !rules) return;
    const int32 currentphase = static_cast<int32>(rules->phase);
    if (combatphase != currentphase)
    {
        combat->reset_phase(); combatphase = currentphase;
        for (abbspellarenaobject* object : spellworkshops) if (isvalid(object)) object->cancelflight();
    }
    combat->set_live(rules->status == BB::Status::Live);
    // combat identity belongs to the rider across a position swap. roster slots
    // remain the rules engine's discipline/position keys, not confirmation IDs.
    for (int32 id=0; id<16; ++id)
    {
        abbridercharacter* occupant = CombatOccupants.FindRef(Id).Get();
        if (!isvalid(occupant) || !Riders.Contains(Occupant))
        {
            CombatOccupants.Remove(Id);
            combat->set_actor(id,-1,false,true);
        }
    }
    for (abbridercharacter* rider : riders)
    {
        if (!isvalid(rider) || rider->rosterindex < 0 || rider->rosterindex >= 16) continue;
        int32 id = combatindex(rider);
        const bool bnew = id == index_none;
        if (bnew)
            for (int32 free=0; free<16; ++free)
                if (!CombatOccupants.Contains(Free)) { id=free; CombatOccupants.Add(Id,Rider); break; }
        if (id == index_none) continue;
        const auto& p = rules->players[rider->rosterindex];
        // stun is validated separately for casting. a stunned target must remain
        // hittable so that a forbidden follow-up really takes effect before review.
        const bool beligible = !P.ejected && !P.donnybrook_excluded && P.removed_until < 0;
        combat->set_actor(id, P.team, beligible, bnew);
    }
}

int32 ABBMatchState::CombatIndex(const abbridercharacter* rider) const
{
    for (const auto& entry : combatoccupants) if (Entry.Value.Get() == rider) return Entry.Key;
    return index_none;
}

void ABBMatchState::TickSpells(float livedelta)
{
    if (!hasauthority() || !combat || livedelta <= 0) return;
    tickcontextualspells(livedelta);
    if (!blive || (bconductreviewpending && !bconductadvantagelive)) return;
    for (abbridercharacter* r : riders)
    {
        if (!isvalid(r)) continue;
        r->stunremaining = FMath::Max(0.f, r->stunremaining-livedelta);
        r->spellcooldownremaining = FMath::Max(0.f, r->spellcooldownremaining-livedelta);
        r->shieldremaining = FMath::Max(0.f, r->shieldremaining-livedelta);
        r->disarmremaining = FMath::Max(0.f, r->disarmremaining-livedelta);
        r->revealremaining = FMath::Max(0.f, r->revealremaining-livedelta);
        r->concealremaining = FMath::Max(0.f, r->concealremaining-livedelta);
        r->petrificusremaining = FMath::Max(0.f, r->petrificusremaining-livedelta);
        r->transformationremaining = FMath::Max(0.f, r->transformationremaining-livedelta);
        r->imperioremaining = FMath::Max(0.f, r->imperioremaining-livedelta);
        const bool bwasimpeded = r->impedimentremaining > 0;
        r->impedimentremaining = FMath::Max(0.f, r->impedimentremaining-livedelta);
        if (bwasimpeded && r->impedimentremaining == 0) combat->recover_target(combatindex(r));
        if (r->stunremaining <= 0) r->vitality = FMath::Min(100.f, R->Vitality+LiveDelta*4.f);
    }
}

void ABBMatchState::ConfirmImpediment(ABBRiderCharacter* rider, uint64 attackid)
{
    if (!hasauthority() || !combat || !isvalid(rider) || !Riders.Contains(Rider)) return;
    // the policy binds this receipt to an actual successful server attack and
    // that attack's caster. rpc callers cannot provide a victim or hit timestamp.
    combat->confirm_impediment(attackid, combatindex(rider));
}

void ABBMatchState::CastSpell(ABBRiderCharacter* r, int32 spellindex, fvector aim)
{
    const fbbspellspec* spell = BBSpellCatalog::Get(SpellIndex);
    if (!hasauthority() || !rules || !combat || !isvalid(r) || !Riders.Contains(R)
        || !spell || !blive || rules->status != BB::Status::Live || (bconductreviewpending && !bconductadvantagelive)
        || r->rosterindex < 0 || r->rosterindex >= 16 || Aim.ContainsNaN() || !Aim.IsNormalized()) return;
    if (!PendingPoints.empty())
    {
        // a spell request must not erase a legal ball event already observed.
        rules->process_batch(rules->now_ms, pendingpoints);
        PendingPoints.clear(); tickconductadvantage(); syncrules();
        if (rules->status != BB::Status::Live) return;
    }
    synccombatroster();
    const auto& player = rules->players[r->rosterindex];
    if (Player.ejected || Player.donnybrook_excluded || Player.removed_until >= 0 || r->hasspellmovementlock()) return;
    if (!BBSpellCatalog::IsImplemented(SpellIndex)) { r->notifyspellresult(spell->description); return; }
    if (r->disarmremaining > 0) { r->notifyspellresult(text("wand disarmed - recovering.")); return; }
    if (r->spellcooldownremaining > 0) { r->notifyspellresult(text("wand recovering.")); return; }
    if (spell->effect == EBBSpellEffect::Workshop || spell->effect == EBBSpellEffect::Throw)
    {
        if (trycastcontextualspell(r,spellindex,aim)) r->spellcooldownremaining=spell->cooldown;
        r->forcenetupdate(); return;
    }
    if (spell->effect == EBBSpellEffect::Ancient)
    {
        abbspellarenaobject* workshop=ensurespellworkshop(r);
        if (!workshop || !workshop->spendcharge(100))
        { r->notifyspellresult(text("ancient magic needs 100 charge. legal applied enemy hits earn 20; objects and ancient magic cannot farm charge.")); return; }
    }
    r->spellcooldownremaining = spell->cooldown;
    if (spell->effect == EBBSpellEffect::Shield)
    {
        r->shieldremaining = 1.f;
        r->notifyspellresult(text("protego - shield raised.")); r->forcenetupdate(); return;
    }
    if (spell->effect == EBBSpellEffect::Light)
    {
        r->lumosremaining = r->lumosremaining > 0 ? 0.f : 1.f;
        r->notifyspellresult(r->lumosremaining > 0 ? text("lumos") : text("nox")); r->forcenetupdate(); return;
    }

    if (spell->effect == EBBSpellEffect::Reveal)
    {
        r->revealremaining = 6.f;
        r->notifyspellresult(text("revelio - concealed opponents visible within 22m for 6 live seconds."));
        r->forcenetupdate(); return;
    }
    if (spell->effect == EBBSpellEffect::Conceal)
    {
        r->concealremaining = 6.f;
        r->lumosremaining = 0.f;
        r->notifyspellresult(text("disillusionment - concealed for 6 live seconds. attacks and hits break concealment."));
        r->forcenetupdate(); return;
    }

    const fvector start = r->getactorlocation()+fvector(0,0,72);
    fvector end = start+aim*spell->range;
    fcollisionqueryparams query(scene_query_stat(basketbroomwand), false, r);
    // other riders' workshop ornaments cannot be used as wand shields.
    for (abbspellarenaobject* object : spellworkshops)
        if (isvalid(object) && object->workshopowner!=r) Query.AddIgnoredActor(Object);
    // first clip the ray against visible world geometry. pawn collision is queried
    // separately because unreal's pawn profile can ignore the visibility channel.
    fhitresult obstruction;
    const bool bobstructed = getworld()->linetracesinglebychannel(obstruction, start, end, ecc_visibility, query);
    if (bobstructed)
    {
        end = Obstruction.ImpactPoint;
        if (abbspellarenaobject* Object=Cast<ABBSpellArenaObject>(Obstruction.GetActor()))
        {
            R->ConcealRemaining=0.f;
            const bool bdamaged=object->workshopowner==r && Obstruction.GetComponent()==Object->Construct
                && object->damageconstruct(spell->damage);
            ABBSpellVisual::Spawn(GetWorld(),Start,End,SpellIndex,false);
            r->notifyspellresult(bdamaged ? text("practice construct damaged. reparo restores it; no ancient magic charge from objects.")
                : text("this spell cannot change that workshop part. official sporting equipment remains protected."));
            r->forcenetupdate(); return;
        }
    }
    fhitresult hit;
    const bool bhit = getworld()->sweepsinglebyobjecttype(hit, start, end, FQuat::Identity,
        fcollisionobjectqueryparams(ecc_pawn), FCollisionShape::MakeSphere(8.f), query);
    abbridercharacter* target = bhit ? Cast<ABBRiderCharacter>(Hit.GetActor()) : nullptr;
    // a swept sphere extends beyond its endpoint. do not let its radius reach a
    // rider through the geometry that clipped the original wand ray.
    if (target && bobstructed && Obstruction.GetActor() != target && Hit.Distance+8.f >= Obstruction.Distance)
        target = nullptr;
    // determine stealth eligibility before this attempted hostile cast breaks
    // concealment. detection is server-derived; clients supply only their aim.
    const bool bbodybind = spell->effect == EBBSpellEffect::BodyBind;
    bool bstealtheligible = false;
    if (bbodybind && isvalid(target))
    {
        const fvector tocaster = r->getactorlocation()-target->getactorlocation();
        const fvector targetforward = Target->GetAimDirection().GetSafeNormal2D();
        bstealtheligible = r->isconcealedfrom(target)
            && ToCaster.SizeSquared() <= FMath::Square(Spell->Range)
            && FVector::DotProduct(TargetForward, ToCaster.GetSafeNormal2D()) < -.5f;
    }
    r->concealremaining = 0.f;
    if (!isvalid(target) || target == r || !Riders.Contains(Target))
    {
        ABBSpellVisual::Spawn(GetWorld(),Start,End,SpellIndex,false);
        R->NotifySpellResult(BBSpellCatalog::Name(SpellIndex)+TEXT(" - missed.")); r->forcenetupdate(); return;
    }
    if (bbodybind && !bstealtheligible)
    {
        r->notifyspellresult(text("petrificus - requires concealment, a target within 3.5m, and approach from behind."));
        r->forcenetupdate(); return;
    }
    ResolveSpellHit(R,Target,SpellIndex,Aim,Hit.ImpactPoint,Start);
}

void ABBMatchState::ResolveSpellHit(ABBRiderCharacter* r,abbridercharacter* target,int32 spellindex,
    fvector aim,fvector impactpoint,fvector start,uint64 existingattackid)
{
    const fbbspellspec* Spell=BBSpellCatalog::Get(SpellIndex);
    if (!hasauthority() || !rules || !combat || !spell || !blive || Rules->status!=BB::Status::Live
        || (bconductreviewpending && !bconductadvantagelive) || !isvalid(r) || !isvalid(target) || r==target
        || !Riders.Contains(R) || !Riders.Contains(Target) || Aim.ContainsNaN() || !Aim.IsNormalized()
        || ImpactPoint.ContainsNaN()) return;
    synccombatroster();
    for (const abbridercharacter* rider : {r,target})
    {
        if (rider->rosterindex<0 || rider->rosterindex>=16) return;
        const auto& player=rules->players[rider->rosterindex];
        if (Player.ejected || Player.donnybrook_excluded || Player.removed_until>=0) return;
    }
    const fvector end=impactpoint;
    // capsule upper region is a provisional server hit zone, not a head-bone
    // accuracy claim. skeletal animation remains cosmetic and non-colliding.
    const bool bhead = End.Z-Target->GetActorLocation().Z > 65.f;
    BB::AttackSpec spec;
    Spec.stun = spell->bstun; Spec.impediment = spell->bimpediment;
    Spec.unforgivable = spell->bunforgivable; Spec.aimed_at_head = bhead;
    BB::CombatDecision cast;
    if (existingattackid) cast=combat->validate_pending_hit(existingattackid,combatindex(r),combatindex(target));
    else cast=combat->begin_attack(combatindex(r),combatindex(target),spec);
    if (!Cast.accepted)
    {
        r->notifyspellresult(text("target is not in live play.")); r->forcenetupdate(); return;
    }
    const bool bblocked = target->shieldremaining > 0 && !spell->bunforgivable;
    ABBSpellVisual::Spawn(GetWorld(),Start,End,SpellIndex,bBlocked);
    if (bblocked)
    {
        Combat->resolve_hit(Cast.attack_id,BB::HitOutcome::Blocked,bHead);
        r->notifyspellresult(text("protego - target blocked the hit."));
        target->notifyspellresult(text("protego - hit blocked.")); r->forcenetupdate(); return;
    }

    // remember the denied scoring ball before a stun drops it. this is an
    // observed target context, not a client-selected restitution value.
    int32 affectedscoringball = -1;
    for (const abbball* ball : balls)
        if (isvalid(ball) && ball->ballindex <= 2 && ball->holder == target) affectedscoringball = ball->ballindex;
    // apply the authoritative effect before recording/refereeing any violation.
    target->concealremaining = 0.f;
    target->vitality = FMath::Max(0.f,Target->Vitality-Spell->Damage);
    switch (spell->effect)
    {
    case EBBSpellEffect::Stun: target->stunremaining = FMath::Max(Target->StunRemaining,1.2f); break;
    case EBBSpellEffect::BodyBind:
        target->petrificusremaining = FMath::Max(Target->PetrificusRemaining,2.5f);
        target->stunremaining = FMath::Max(Target->StunRemaining,2.5f); break;
    case EBBSpellEffect::Transform:
        target->transformationremaining = FMath::Max(Target->TransformationRemaining,3.f);
        target->impedimentremaining = FMath::Max(Target->ImpedimentRemaining,3.f);
        target->shieldremaining = target->lumosremaining = 0.f; break;
    case EBBSpellEffect::Confuse:
        target->imperioremaining = FMath::Max(Target->ImperioRemaining,3.f); break;
    case EBBSpellEffect::Slow: target->impedimentremaining = FMath::Max(Target->ImpedimentRemaining,3.f); break;
    case EBBSpellEffect::Freeze:
        target->impedimentremaining = FMath::Max(Target->ImpedimentRemaining,1.5f);
        target->stunremaining = FMath::Max(Target->StunRemaining,1.5f); break;
    case EBBSpellEffect::Lift:
        target->impedimentremaining = FMath::Max(Target->ImpedimentRemaining,2.f);
        target->getcharactermovement()->addimpulse(fvector(0,0,650),true); break;
    case EBBSpellEffect::Pull:
        Target->GetCharacterMovement()->AddImpulse((R->GetActorLocation()-Target->GetActorLocation()).GetSafeNormal()*1000.f,true); break;
    case EBBSpellEffect::Ancient:
    case EBBSpellEffect::Throw:
    case EBBSpellEffect::Push: Target->GetCharacterMovement()->AddImpulse(Aim*1200.f,true); break;
    case EBBSpellEffect::Down: target->getcharactermovement()->addimpulse(fvector(0,0,-1000),true); break;
    case EBBSpellEffect::Flip: target->getcharactermovement()->addimpulse(fvector(0,0,1000),true); break;
    case EBBSpellEffect::Disarm: target->disarmremaining = FMath::Max(Target->DisarmRemaining,2.5f); break;
    case EBBSpellEffect::Knockout: target->stunremaining = FMath::Max(Target->StunRemaining,6.f); break;
    case EBBSpellEffect::Curse: target->stunremaining = FMath::Max(Target->StunRemaining,2.f); break;
    default: break;
    }
    if (target->vitality <= 0)
    {
        target->stunremaining = FMath::Max(Target->StunRemaining,3.f);
        target->vitality = 50.f;
    }
    if (target->hasspellmovementlock())
    {
        target->getcharactermovement()->stopmovementimmediately();
        target->binteractheld = false;
        // resolve this actual hit receipt before a lost-possession whistle
        // freezes combat; otherwise the applied illegal hit would lose its call.
        Release(Target,FVector::ZeroVector,true);
    }
    const auto decision = Combat->resolve_hit(Cast.attack_id, spell->bimpediment ? BB::HitOutcome::Impeded : BB::HitOutcome::Contact,
        bhead, spell->bimpediment ? FMath::CeilToInt(Target->ImpedimentRemaining*1000.f) : -1);
    // only accepted, legal hostile rider contact earns a resource. no friendly
    // farming, blocked/missed casts, practice objects or ancient magic loops.
    if (Decision.legal() && target->teamindex!=r->teamindex && spellindex!=29 && spellindex!=30)
        if (abbspellarenaobject* workshop=ensurespellworkshop(r)) workshop->earncharge(20);
    target->forcenetupdate(); r->forcenetupdate();
    R->NotifySpellResult(BBSpellCatalog::Name(SpellIndex)+(Spell->bImpediment ? text(" hit - target impeded. no follow-up stun.") : text(" hit")),
        spell->bimpediment && Decision.accepted ? Cast.attack_id : 0);
    target->notifyspellresult(text("hit by ")+BBSpellCatalog::Name(SpellIndex));
    if (!Decision.requires_adjudication()) { tickconductadvantage(); return; }

    RegisterConductHit(R,Target,SpellIndex,AffectedScoringBall,Decision.violations,Cast.attack_id,bHead);
}

abbspellarenaobject* ABBMatchState::GetSpellWorkshop(const abbridercharacter* rider) const
{
    if (!isvalid(rider) || !getworld()) return nullptr;
    // clients discover independently replicated actors; they do not rely on an
    // authority-only array or on a client-provided object reference.
    for (tactoriterator<abbspellarenaobject> it(getworld()); it; ++it)
        if (it->workshopowner==rider) return *it;
    return nullptr;
}
int32 ABBMatchState::GetAncientMagicCharge(const abbridercharacter* rider) const
{
    const abbspellarenaobject* object=getspellworkshop(rider);
    return object ? object->ancientmagiccharge : 0;
}
abbspellarenaobject* ABBMatchState::EnsureSpellWorkshop(ABBRiderCharacter* rider)
{
    if (!hasauthority() || !isvalid(rider) || !Riders.Contains(Rider) || !rider->isplayercontrolled()) return nullptr;
    if (abbspellarenaobject* existing=getspellworkshop(rider)) return existing;
    if (rider->rosterindex<0 || rider->rosterindex>=16 || SpellWorkshops.Num()>=16) return nullptr;
    // original, named side bays occupy provisional tactical space. they never
    // change the arena, hoop geometry or ball/rider collision responses.
    const fvector Location((Rider->RosterIndex%8-3.5)*1100.0,
        (Rider->TeamIndex?1.0:-1.0)*(BBArena::HalfWidth-400.0),1450.0);
    const ftransform Transform(FRotator::ZeroRotator,Location);
    abbspellarenaobject* Object=GetWorld()->SpawnActorDeferred<ABBSpellArenaObject>(ABBSpellArenaObject::StaticClass(),
        Transform,this,nullptr,ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!object) return nullptr;
    object->workshopowner=rider; object->constructposition=location+fvector(0,0,180);
    object->setflags(rf_transient); object->finishspawning(transform);
    SpellWorkshops.Add(Object); object->forcenetupdate(); return object;
}
void ABBMatchState::ResetContextualSpells()
{
    if (!hasauthority()) return;
    for (abbspellarenaobject* object : spellworkshops) if (isvalid(object)) object->destroy();
    SpellWorkshops.Empty();
}
void ABBMatchState::TickContextualSpells(float livedelta)
{
    if (!hasauthority() || !blive || livedelta<=0) return;
    for (int32 I=SpellWorkshops.Num()-1; i>=0; --i)
    {
        abbspellarenaobject* object=spellworkshops[i];
        if (!isvalid(object) || !isvalid(object->workshopowner) || !Riders.Contains(Object->WorkshopOwner)
            || !object->workshopowner->isplayercontrolled())
        {
            if (isvalid(object)) object->destroy();
            SpellWorkshops.RemoveAt(I); continue;
        }
        object->advancelive(livedelta,this);
        // a physical throw can itself create a conduct stoppage. never advance
        // a second projectile beyond that adjudication boundary in this tick.
        if (!blive || (bconductreviewpending && !bconductadvantagelive)) return;
    }
    for (abbridercharacter* rider : riders)
        if (isvalid(rider) && rider->isplayercontrolled()) ensurespellworkshop(rider);
}
bool ABBMatchState::TryCastContextualSpell(ABBRiderCharacter* r,int32 spellindex,fvector aim)
{
    const fbbspellspec* Spell=BBSpellCatalog::Get(SpellIndex);
    abbspellarenaobject* owned=ensurespellworkshop(r);
    if (!spell || !owned) { r->notifyspellresult(text("no available owned spell bay.")); return false; }
    const fvector start=r->getactorlocation()+fvector(0,0,72);
    if (spellindex!=30)
    {
        fhitresult hit;
        fcollisionqueryparams query(scene_query_stat(basketbroomworkshop),false,r);
        getworld()->linetracesinglebychannel(hit,start,start+aim*spell->range,ecc_visibility,query);
        abbspellarenaobject* Object=Cast<ABBSpellArenaObject>(Hit.GetActor());
        const bool bbayspell=spellindex==4 || spellindex==23;
        if (object!=owned || Hit.GetComponent()!=(bBaySpell?Owned->Bay.Get():Owned->Construct.Get()))
        {
            r->notifyspellresult(bbayspell?text("aim at your own side-bay locker within 9m. official equipment is protected.")
                :TEXT("Aim at your own practice construct within 9m. other riders and official equipment are protected."));
            return false;
        }
        fstring feedback;
        const bool bapplied=owned->applyworkshopspell(r,spellindex,aim,feedback);
        if (bapplied) ABBSpellVisual::Spawn(GetWorld(),Start,Hit.ImpactPoint,SpellIndex,false);
        r->notifyspellresult(feedback); return bapplied;
    }
    if (!owned->isusableby(r) || !owned->bconjured || owned->integrity<=0
        || FVector::DistSquared(Start,Owned->ConstructPosition)>FMath::Square(600.f))
    { r->notifyspellresult(text("ancient magic throw needs your intact, available construct within 6m.")); return false; }
    if (owned->ancientmagiccharge<25)
    { r->notifyspellresult(text("ancient magic throw needs 25 charge. legal enemy rider hits earn 20; practice objects earn none.")); return false; }
    fcollisionqueryparams query(scene_query_stat(basketbroomconstructlaunch),false,r);
    for (abbspellarenaobject* object : spellworkshops) if (isvalid(object)) Query.AddIgnoredActor(Object);
    fhitresult access;
    if (getworld()->linetracesinglebychannel(access,start,owned->constructposition,ecc_visibility,query))
    { r->notifyspellresult(text("your construct is obstructed.")); return false; }
    fvector end=start+aim*spell->range;
    fhitresult wall,hit;
    const bool bwall=getworld()->linetracesinglebychannel(wall,start,end,ecc_visibility,query);
    if (bwall) End=Wall.ImpactPoint;
    const bool bHit=GetWorld()->SweepSingleByObjectType(Hit,Start,End,FQuat::Identity,
        FCollisionObjectQueryParams(ECC_Pawn),FCollisionShape::MakeSphere(8.f),Query);
    abbridercharacter* Target=bHit?Cast<ABBRiderCharacter>(Hit.GetActor()):nullptr;
    if (!isvalid(target) || target==r || !Riders.Contains(Target)
        || (bwall && Wall.GetActor()!=Target && Hit.Distance+8.f>=Wall.Distance))
    { r->notifyspellresult(text("ancient magic throw - aim at one live rider within 30m. no charge spent.")); return false; }
    BB::AttackSpec spec; Spec.aimed_at_head=Hit.ImpactPoint.Z-Target->GetActorLocation().Z>65.f;
    const auto attack=combat->begin_attack(combatindex(r),combatindex(target),spec);
    if (!Attack.accepted)
    { r->notifyspellresult(text("target is not in live play.")); return false; }
    if (!owned->spendcharge(25)) return false;
    R->ConcealRemaining=0.f;
    Owned->Launch(Target,Hit.ImpactPoint,Attack.attack_id);
    r->notifyspellresult(text("ancient magic throw - construct launched; world and riders can intercept. reparo after impact."));
    return true;
}
void ABBMatchState::ResolveThrownSpellImpact(ABBSpellArenaObject* object,abbridercharacter* target,
    fvector impactpoint,fvector direction,uint64 attackid)
{
    if (!hasauthority() || !isvalid(object) || !SpellWorkshops.Contains(Object) || !isvalid(object->workshopowner)
        || getspellworkshop(object->workshopowner)!=object || attackid==0) return;
    resolvespellhit(object->workshopowner,target,30,direction,impactpoint,object->home(),attackid);
}

void ABBMatchState::ReviewConduct(ABBRiderCharacter* referee, int32 disposition)
{
    if (!canofficiate(referee) || !rules || !bconductreviewpending || rules->status == BB::Status::Live
        || conductoffender < 0 || conductoffender >= 16 || ConductEvidence.IsEmpty()) return;
    if (disposition < 9 || disposition > 12 || bpenaltyshotactive) return;
    const bool beject = disposition == 11, bfree = disposition == 12, bshot = disposition == 10 || bfree;
    const fconductevidence evidence = conductevidence[0];
    if (Evidence.PenaltyId > 0 && (beject || (bshot && !bfree)))
    {
        referee->notifyspellresult(text("this host-selected moderate advantage owes f6 free shot or f7 possession; a later separate foul keeps its own ruling."));
        return;
    }
    if (!bshot && !beject && rules->status == BB::Status::Review)
    {
        referee->notifyspellresult(text("post-termination possession cannot resume live play; serve the owed f6 free shot before certification."));
        return;
    }
    // keep original observed identity, ball and time. the host selects a tier
    // for an unclassified foul, or serves the previously selected Moderate.
    const BB::Match previous = *rules;
    const int id = Evidence.PenaltyId > 0 ? Evidence.PenaltyId
        : Rules->record_penalty(Evidence.Offender,TCHAR_TO_UTF8(*Evidence.Reason),
            beject ? BB::Severity::Severe : bshot && !bfree ? BB::Severity::Serious : BB::Severity::Moderate,
            Evidence.Ball,Evidence.CommittedMs);
    bool bapplied = false;
    if (beject) bapplied = id > 0 && rules->resolve_penalty(id,"host bb-0 playtest referee: ejection",true);
    else if (bshot) bapplied = id > 0 && beginconductpenaltyshot(id,bfree);
    else
    {
        for (int32 ballindex : {0,1,2})
            if (id > 0 && rules->queue_conduct_possession_award(id,ballindex,conductvictimteam))
            { bapplied = true; conductrestartball = ballindex; break; }
    }
    if (!bapplied)
    {
        *rules = previous;
        referee->notifyspellresult(text("that disposition cannot be served now; conduct review remains pending."));
        return;
    }
    ConductEvidence[0].PenaltyId = id;
    completeconductevidence();
    if (bshot) { syncrules(); say(penaltyshotstatus); return; }
    if (!bconductreviewpending)
        conductreviewstatus = beject ? text("ejection served - Host: enter to resume")
                                    : text("possession award queued - Host: enter to serve restart");
    syncrules(); say(conductreviewstatus);
}

tarray<int32> ABBMatchState::DevelopmentGetConductState() const
{
#if !ue_build_shipping
    if (hasauthority() && getworld() && getworld()->worldtype == EWorldType::PIE)
        return {conductfoulcount,bconductreviewpending ? 1 : 0,conductoffender,lastconductviolations,
            static_cast<int32>(FMath::Min<uint64>(LastConductAttack,MAX_int32)),ConductRestartBall};
#endif
    return {};
}

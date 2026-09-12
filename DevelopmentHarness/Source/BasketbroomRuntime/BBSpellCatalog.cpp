#include "BBSpellCatalog.h"

namespace
{
using E = EBBSpellEffect;
const FBBSpellSpec Spells[] = {
    {TEXT("Basic Cast"), E::Impact, .4f, 3000, 8, false,false,false, TEXT("Quick bolt. Depletes vitality; aim below the head.")},
    {TEXT("Protego"), E::Shield, 2.f, 0, 0, false,false,false, TEXT("One-second shield. R casts directly. Curses pierce it.")},
    {TEXT("Stupefy"), E::Stun, 2.f, 3000, 0, false,true,false, TEXT("Stuns for 1.2 seconds. No stun after a confirmed impediment.")},
    {TEXT("Revelio"), E::Context, 0, 0, 0, false,false,false, TEXT("Needs a revealable world target; arena adapter pending.")},
    {TEXT("Alohomora"), E::Context, 0, 0, 0, false,false,false, TEXT("Needs a locked world object; arena adapter pending.")},
    {TEXT("Petrificus Totalus"), E::Context, 0, 0, 0, false,true,false, TEXT("Stealth takedown conditions and animation pending.")},
    {TEXT("Accio"), E::Pull, 1.5f, 2200, 0, false,false,false, TEXT("Pulls a rider toward the caster. Does not grab chase balls.")},
    {TEXT("Depulso"), E::Push, 1.5f, 2200, 0, false,false,false, TEXT("Pushes a rider away; physical arena bounds still apply.")},
    {TEXT("Descendo"), E::Down, 1.5f, 2200, 8, false,false,false, TEXT("Drives a rider downward into the rebound envelope.")},
    {TEXT("Flipendo"), E::Flip, 1.5f, 2200, 0, false,false,false, TEXT("Deflects a rider upward. Full flip animation pending.")},
    {TEXT("Arresto Momentum"), E::Slow, 1.5f, 3000, 0, true,false,false, TEXT("Slows flight for 3 seconds. Provisional impediment category.")},
    {TEXT("Glacius"), E::Freeze, 2.f, 2600, 0, true,false,false, TEXT("Freezes for 1.5 seconds. Provisional impediment category.")},
    {TEXT("Levioso"), E::Lift, 2.f, 2600, 0, true,false,false, TEXT("Lifts and slows for 2 seconds. Provisional impediment category.")},
    {TEXT("Transformation"), E::Context, 0, 0, 0, false,false,false, TEXT("Rider transformation and reversal adapter pending.")},
    {TEXT("Incendio"), E::Impact, 1.2f, 700, 30, false,false,false, TEXT("Short-range fire hit. Vitality damage, no lingering burn yet.")},
    {TEXT("Confringo"), E::Impact, 1.5f, 3400, 22, false,false,false, TEXT("Long-range fire bolt. No splash or burn in this build.")},
    {TEXT("Diffindo"), E::Impact, 2.f, 2800, 35, false,false,false, TEXT("Focused cutting hit. One target in this build.")},
    {TEXT("Expelliarmus"), E::Disarm, 1.5f, 2800, 5, false,false,false, TEXT("Disables target wandwork for 2.5 seconds.")},
    {TEXT("Bombarda"), E::Push, 2.5f, 2800, 40, false,false,false, TEXT("Heavy impact and knockback. Splash adapter pending.")},
    {TEXT("Lumos"), E::Light, .3f, 0, 0, false,false,false, TEXT("Toggle wand light. Does not count toward mob attacks.")},
    {TEXT("Disillusionment"), E::Context, 0, 0, 0, false,false,false, TEXT("Concealment, target visibility and counters pending.")},
    {TEXT("Wingardium Leviosa"), E::Context, 0, 0, 0, false,false,false, TEXT("Needs a legal movable world object; adapter pending.")},
    {TEXT("Reparo"), E::Context, 0, 0, 0, false,false,false, TEXT("Needs a repairable world object; adapter pending.")},
    {TEXT("Conjuring Spell"), E::Context, 0, 0, 0, false,false,false, TEXT("Needs a supported construction space; adapter pending.")},
    {TEXT("Altering Spell"), E::Context, 0, 0, 0, false,false,false, TEXT("Needs a conjured editable world object; adapter pending.")},
    {TEXT("Evanesco"), E::Context, 0, 0, 0, false,false,false, TEXT("Needs a removable conjured object; adapter pending.")},
    {TEXT("Avada Kedavra"), E::Knockout, 6.f, 2800, 100, false,false,true, TEXT("Prototype: six-second knockout. Illegal outside Bloodbroom.")},
    {TEXT("Crucio"), E::Curse, 4.f, 2800, 25, false,false,true, TEXT("Prototype: two-second disable. Illegal outside Bloodbroom.")},
    {TEXT("Imperio"), E::Context, 0, 0, 0, false,false,true, TEXT("Mind-control, player ownership and counterplay adapter pending.")},
    {TEXT("Ancient Magic"), E::Context, 0, 0, 0, false,false,false, TEXT("Meter, finisher and sporting adaptation pending.")},
    {TEXT("Ancient Magic Throw"), E::Context, 0, 0, 0, false,false,false, TEXT("Needs a legal throwable world object; adapter pending.")}
};
}
int32 BBSpellCatalog::Count() { return UE_ARRAY_COUNT(Spells); }
const FBBSpellSpec* BBSpellCatalog::Get(int32 Index) { return Index >= 0 && Index < Count() ? &Spells[Index] : nullptr; }
FString BBSpellCatalog::Name(int32 Index) { const auto* S=Get(Index); return S ? S->Name : TEXT("Unknown spell"); }
FString BBSpellCatalog::Description(int32 Index) { const auto* S=Get(Index); return S ? S->Description : TEXT("Unknown spell"); }
bool BBSpellCatalog::IsImplemented(int32 Index) { const auto* S=Get(Index); return S && S->Effect != E::Context; }

#include "BBSpellCatalog.h"

namespace
{
using E = EBBSpellEffect;
const FBBSpellSpec Spells[] = {
    {TEXT("Basic Cast"), E::Impact, .4f, 3000, 8, false,false,false, TEXT("Quick bolt. Depletes vitality; aim below the head.")},
    {TEXT("Protego"), E::Shield, 2.f, 0, 0, false,false,false, TEXT("One-second shield. R casts directly. Curses pierce it.")},
    {TEXT("Stupefy"), E::Stun, 2.f, 3000, 0, false,true,false, TEXT("Stuns for 1.2 seconds. No stun after a confirmed impediment.")},
    {TEXT("Revelio"), E::Reveal, 2.f, 2200, 0, false,false,false, TEXT("Reveal concealed opponents within 22m for 6 live seconds. Does not see through walls.")},
    {TEXT("Alohomora"), E::Workshop, .5f, 900, 0, false,false,false, TEXT("Within 9m, aim at your side-bay locker to unlock it. No world doors or official equipment edits.")},
    {TEXT("Petrificus Totalus"), E::BodyBind, 3.f, 350, 0, false,true,false, TEXT("Concealed, within 3.5m and behind a rider: bind for 2.5s. Protego blocks; no double-taps.")},
    {TEXT("Accio"), E::Pull, 1.5f, 2200, 0, false,false,false, TEXT("Pulls a rider toward the caster. Does not grab chase balls.")},
    {TEXT("Depulso"), E::Push, 1.5f, 2200, 0, false,false,false, TEXT("Pushes a rider away; physical arena bounds still apply.")},
    {TEXT("Descendo"), E::Down, 1.5f, 2200, 8, false,false,false, TEXT("Drives a rider downward into the rebound envelope.")},
    {TEXT("Flipendo"), E::Flip, 1.5f, 2200, 0, false,false,false, TEXT("Deflects a rider upward. Full flip animation pending.")},
    {TEXT("Arresto Momentum"), E::Slow, 1.5f, 3000, 0, true,false,false, TEXT("Slows flight for 3 seconds. Provisional impediment category.")},
    {TEXT("Glacius"), E::Freeze, 2.f, 2600, 0, true,false,false, TEXT("Freezes for 1.5 seconds. Provisional impediment category.")},
    {TEXT("Levioso"), E::Lift, 2.f, 2600, 0, true,false,false, TEXT("Lifts and slows for 2 seconds. Provisional impediment category.")},
    {TEXT("Transformation"), E::Transform, 4.f, 2400, 0, true,false,false, TEXT("Sport adaptation: 3s orb form; drops ball, locks flight, catch and wand. Protego blocks.")},
    {TEXT("Incendio"), E::Impact, 1.2f, 700, 30, false,false,false, TEXT("Short-range fire hit. Vitality damage, no lingering burn yet.")},
    {TEXT("Confringo"), E::Impact, 1.5f, 3400, 22, false,false,false, TEXT("Long-range fire bolt. No splash or burn in this build.")},
    {TEXT("Diffindo"), E::Impact, 2.f, 2800, 35, false,false,false, TEXT("Focused cutting hit. One target in this build.")},
    {TEXT("Expelliarmus"), E::Disarm, 1.5f, 2800, 5, false,false,false, TEXT("Disables target wandwork for 2.5 seconds.")},
    {TEXT("Bombarda"), E::Push, 2.5f, 2800, 40, false,false,false, TEXT("Heavy impact and knockback. Splash adapter pending.")},
    {TEXT("Lumos"), E::Light, .3f, 0, 0, false,false,false, TEXT("Toggle wand light. Does not count toward mob attacks.")},
    {TEXT("Disillusionment"), E::Conceal, 2.f, 0, 0, false,false,false, TEXT("Conceal for 6 live seconds. Casting at riders or taking a hit breaks it. Revelio counters.")},
    {TEXT("Wingardium Leviosa"), E::Workshop, .6f, 900, 0, false,false,false, TEXT("Aim at your intact construct within 9m: lift/lower it 1.6m inside its own bay. Never moves official balls.")},
    {TEXT("Reparo"), E::Workshop, 1.f, 900, 0, false,false,false, TEXT("Aim at your damaged or broken bay construct within 9m to restore it. Does not heal riders.")},
    {TEXT("Conjuring Spell"), E::Workshop, 1.f, 900, 0, false,false,false, TEXT("Aim at your unlocked bay within 9m to create one nonblocking practice construct. One per rider.")},
    {TEXT("Altering Spell"), E::Workshop, .6f, 900, 0, false,false,false, TEXT("Aim at your intact bay construct within 9m: cube, sphere or cylinder. Size and permissions stay fixed.")},
    {TEXT("Evanesco"), E::Workshop, .6f, 900, 0, false,false,false, TEXT("Aim at your bay construct within 9m to remove it. Cannot erase opponents, goals, nets or official equipment.")},
    {TEXT("Avada Kedavra"), E::Knockout, 6.f, 2800, 100, false,false,true, TEXT("Prototype: six-second knockout. Illegal outside Bloodbroom.")},
    {TEXT("Crucio"), E::Curse, 4.f, 2800, 25, false,false,true, TEXT("Prototype: two-second disable. Illegal outside Bloodbroom.")},
    {TEXT("Imperio"), E::Confuse, 4.f, 2800, 0, false,false,true, TEXT("Sport adaptation: reverse horizontal flight input for 3s. Keep look/up/down control. Unforgivable.")},
    {TEXT("Ancient Magic"), E::Ancient, 4.f, 2600, 55, false,false,false, TEXT("100 charge: 55-vitality pulse plus push. Legal enemy hits earn 20. Protego blocks; BB-0 still applies.")},
    {TEXT("Ancient Magic Throw"), E::Throw, 2.f, 3000, 35, false,false,false, TEXT("25 charge: within 6m of your intact construct, aim at a rider to launch it. Swept flight, Protego and BB-0 apply.")}
};
}
int32 BBSpellCatalog::Count() { return UE_ARRAY_COUNT(Spells); }
const FBBSpellSpec* BBSpellCatalog::Get(int32 Index) { return Index >= 0 && Index < Count() ? &Spells[Index] : nullptr; }
FString BBSpellCatalog::Name(int32 Index) { const auto* S=Get(Index); return S ? S->Name : TEXT("Unknown spell"); }
FString BBSpellCatalog::Description(int32 Index) { const auto* S=Get(Index); return S ? S->Description : TEXT("Unknown spell"); }
bool BBSpellCatalog::IsImplemented(int32 Index) { const auto* S=Get(Index); return S && S->Effect != E::Context; }

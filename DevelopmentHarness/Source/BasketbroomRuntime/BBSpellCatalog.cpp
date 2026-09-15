#include "BBSpellCatalog.h"

namespace
{
using e = ebbspelleffect;
const fbbspellspec spells[] = {
    {text("basic cast"), E::Impact, .4f, 3000, 8, false,false,false, text("quick bolt. depletes vitality; aim below the head.")},
    {text("protego"), E::Shield, 2.f, 0, 0, false,false,false, text("one-second shield. r casts directly. curses pierce it.")},
    {text("stupefy"), E::Stun, 2.f, 3000, 0, false,true,false, text("stuns for 1.2 seconds. no stun after a confirmed impediment.")},
    {text("revelio"), E::Reveal, 2.f, 2200, 0, false,false,false, text("reveal concealed opponents within 22m for 6 live seconds. does not see through walls.")},
    {text("alohomora"), E::Workshop, .5f, 900, 0, false,false,false, text("within 9m, aim at your side-bay locker to unlock it. no world doors or official equipment edits.")},
    {text("petrificus totalus"), E::BodyBind, 3.f, 350, 0, false,true,false, text("concealed, within 3.5m and behind a rider: bind for 2.5s. protego blocks; no double-taps.")},
    {text("accio"), E::Pull, 1.5f, 2200, 0, false,false,false, text("pulls a rider toward the caster. does not grab chase balls.")},
    {text("depulso"), E::Push, 1.5f, 2200, 0, false,false,false, text("pushes a rider away; physical arena bounds still apply.")},
    {text("descendo"), E::Down, 1.5f, 2200, 8, false,false,false, text("drives a rider downward into the rebound envelope.")},
    {text("flipendo"), E::Flip, 1.5f, 2200, 0, false,false,false, text("deflects a rider upward. full flip animation pending.")},
    {text("arresto momentum"), E::Slow, 1.5f, 3000, 0, true,false,false, text("slows flight for 3 seconds. provisional impediment category.")},
    {text("glacius"), E::Freeze, 2.f, 2600, 0, true,false,false, text("freezes for 1.5 seconds. provisional impediment category.")},
    {text("levioso"), E::Lift, 2.f, 2600, 0, true,false,false, text("lifts and slows for 2 seconds. provisional impediment category.")},
    {text("transformation"), E::Transform, 4.f, 2400, 0, true,false,false, text("sport adaptation: 3s orb form; drops ball, locks flight, catch and wand. protego blocks.")},
    {text("incendio"), E::Impact, 1.2f, 700, 30, false,false,false, text("short-range fire hit. vitality damage, no lingering burn yet.")},
    {text("confringo"), E::Impact, 1.5f, 3400, 22, false,false,false, text("long-range fire bolt. no splash or burn in this build.")},
    {text("diffindo"), E::Impact, 2.f, 2800, 35, false,false,false, text("focused cutting hit. one target in this build.")},
    {text("expelliarmus"), E::Disarm, 1.5f, 2800, 5, false,false,false, text("disables target wandwork for 2.5 seconds.")},
    {text("bombarda"), E::Push, 2.5f, 2800, 40, false,false,false, text("heavy impact and knockback. splash adapter pending.")},
    {text("lumos"), E::Light, .3f, 0, 0, false,false,false, text("toggle wand light. does not count toward mob attacks.")},
    {text("disillusionment"), E::Conceal, 2.f, 0, 0, false,false,false, text("conceal for 6 live seconds. casting at riders or taking a hit breaks it. revelio counters.")},
    {text("wingardium leviosa"), E::Workshop, .6f, 900, 0, false,false,false, text("aim at your intact construct within 9m: lift/lower it 1.6m inside its own bay. never moves official balls.")},
    {text("reparo"), E::Workshop, 1.f, 900, 0, false,false,false, text("aim at your damaged or broken bay construct within 9m to restore it. does not heal riders.")},
    {text("conjuring spell"), E::Workshop, 1.f, 900, 0, false,false,false, text("aim at your unlocked bay within 9m to create one nonblocking practice construct. one per rider.")},
    {text("altering spell"), E::Workshop, .6f, 900, 0, false,false,false, text("aim at your intact bay construct within 9m: cube, sphere or cylinder. size and permissions stay fixed.")},
    {text("evanesco"), E::Workshop, .6f, 900, 0, false,false,false, text("aim at your bay construct within 9m to remove it. cannot erase opponents, goals, nets or official equipment.")},
    {text("avada kedavra"), E::Knockout, 6.f, 2800, 100, false,false,true, TEXT("Prototype: six-second knockout. illegal outside Bloodbroom.")},
    {text("crucio"), E::Curse, 4.f, 2800, 25, false,false,true, TEXT("Prototype: two-second disable. illegal outside Bloodbroom.")},
    {text("imperio"), E::Confuse, 4.f, 2800, 0, false,false,true, text("sport adaptation: reverse horizontal flight input for 3s. keep look/up/down control. Unforgivable.")},
    {text("ancient magic"), E::Ancient, 4.f, 2600, 55, false,false,false, text("100 charge: 55-vitality pulse plus push. legal enemy hits earn 20. protego blocks; bb-0 still applies.")},
    {text("ancient magic throw"), E::Throw, 2.f, 3000, 35, false,false,false, text("25 charge: within 6m of your intact construct, aim at a rider to launch it. swept flight, protego and bb-0 apply.")}
};
}
int32 BBSpellCatalog::Count() { return ue_array_count(spells); }
const fbbspellspec* BBSpellCatalog::Get(int32 index) { return index >= 0 && index < count() ? &spells[index] : nullptr; }
fstring BBSpellCatalog::Name(int32 index) { const auto* s=get(index); return s ? s->name : text("unknown spell"); }
fstring BBSpellCatalog::Description(int32 index) { const auto* s=get(index); return s ? s->description : text("unknown spell"); }
bool BBSpellCatalog::IsImplemented(int32 index) { const auto* s=get(index); return s && s->effect != E::Context; }

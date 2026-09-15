# Native wandplay and BB-0 playtest

This is the UE5.8 sporting adapter for the [new BB-0 direction](bb0-contact-and-spells.md).
It is not Hogwarts Legacy's native spell system and does not complete the Creator
Kit integration. The full allowed repertoire is retained in the
[spell catalog](../Rules/spell_catalog.json); implementation availability is a
separate question.

## Controls

- **Q:** cast the selected spell along the reticle.
- **Z / X:** select the previous or next entry. **V:** open the spellbook.
- **R:** cast Protego without changing selection.
- **B:** host toggles Basketbroom/Bloodbroom in the initial lobby only.
- **F7 / F8 / F9:** host resolves a pending conduct call with possession, a
  Serious penalty shot plus removal, or ejection. These remain host-selected
  playtest choices, not automatic severity assignments.

The existing flight, ball, role and team controls remain. Bloodbroom keeps the
same ball/clock format and waives only the Unforgivable and headshot prohibitions.
It does not change mobbing or double-tap decisions. Physical holding has no
player ability in this build; the portable conduct policy prohibits it in both
variants, but physical holding detection is not integrated.

## Available sporting adaptations

Twenty-three spell-menu actions have native sporting behavior. Five new actions
are detailed in [Sprint 3 spellwork](native-sport-spells.md): Revelio,
Disillusionment, Petrificus Totalus, Transformation and Imperio. The prior
eighteen remain: Basic Cast, Protego, Stupefy, Accio,
Depulso, Descendo, Flipendo, Arresto Momentum, Glacius, Levioso, Incendio,
Confringo, Diffindo, Expelliarmus, Bombarda, Lumos, Avada Kedavra and Crucio.

These are provisional sporting effects. Damage drains regenerating vitality;
zero vitality causes a three-second knockout and restores fifty vitality.
Avada Kedavra currently causes a six-second knockout, not a death simulation.
Crucio applies a two-second disable. Force spells apply native movement impulses;
Flipendo does not yet animate a full flip. Elemental spells have no splash,
lingering damage or advanced combos. Stupefy is directly castable in this
playtest; the base game's Protego-counter activation is not reproduced yet.

Arresto Momentum slows flight to 35% for three seconds. Glacius freezes for
1.5 seconds; Levioso lifts and slows for two seconds. These three control effects
are provisionally treated as impediments for double-tap detection. This does not
rename Arresto Momentum to Impedimenta or establish that their lore definitions
are interchangeable. Stupefy is a stun; it does not itself create an impediment
confirmation record. Protego shields for one second; Unforgivables bypass it.
Expelliarmus disables wandwork for 2.5 seconds; Lumos toggles a real point light.
Cooldowns, ranges, vitality and durations are playtest tuning in `BBSpellCatalog.cpp`.

The spellbook also shows six remaining base spells and the two Ancient
Magic actions, marked **ADAPTER DUE / LATER**. They are allowed repertoire with
unimplemented target/context adapters, not forbidden BB-0 spells. Beast-care
tools are cataloged separately. CPU teammates still play the ball game and do
not autonomously cast spells.

## Authority, evidence and limitations

The owning rider sends only a spell index and normalized aim. The server checks
live status, rider eligibility, cooldown, disarm and stun, uses a server-derived
cast origin, clips against visible world geometry, then sweeps against rider
capsules. Clients do not choose a victim, report damage or provide hit timestamps.
Spell visuals replicate their endpoints and have no gameplay collision.

Hits resolve immediately; the visible beam is cosmetic, not a travelling
projectile. There is no latency rewind. The upper capsule region, more than
65 cm above the rider origin, is the provisional head zone. This is not
skeletal head-bone precision. Native mob evidence currently starts with a traced
target contact (including a shielded attempt), so misses with no identified
target do not establish mob membership. Bludger head regions and ordinary body
contact are not wired into the new wand-call adapter yet.

The portable policy uses at most three distinct same-team attackers per target
within a provisional two seconds of live time. It retains server-minted attack
IDs, rejects duplicate resolutions and freezes its windows at stoppages. A
double-tap requires an active successful impediment and prior clear feedback
to that caster. In the normal client, the HUD draws the server notice and a
later native Tick acknowledges that ID after 0.25 seconds. The server binds the
receipt to its original successful cast. This is a normal-client delivery
protocol, not proof of human attention or protection against a modified client
withholding acknowledgments. Cross-teammate awareness is not implemented.

Critical feedback preempts ordinary notices. Queues are bounded; stale receipts
expire without invented acknowledgments. Combat identity follows a rider across
position swaps. New occupants cannot inherit an old rider's confirmation IDs.
Match/phase resets clear relevant conduct state; ordinary stoppages preserve it.
The new sporting status timers retain their remaining duration through quarter
breaks and clear on a genuine match reset.

## Applied hit, then referee decision

An illegal hit has its real effect first. The adapter then records one combined
call and pauses play, even when several definitions apply. The pending call
blocks resumption and position changes. Host authority is checked on the server;
a remote client cannot choose the variant or serve a referee disposition.

F7 chooses a Moderate possession award, preferring the Quaffle and then a free
Quark. Donnybrook has only the Quarks. It reserves the ball without overwriting an existing remedy. The
penalty remains pending while the award is queued. On resumption, an eligible
opponent receives a protected restart near the recorded hit location; only
then is the penalty marked served. Certification cannot skip an unserved award.
If every active scoring ball already has a remedy, the review stays pending.
Deferring an award until a later stoppage is not implemented; F9 must not be
treated as a required substitute for an appropriate possession disposition.

F9 chooses a Severe ejection through the existing rules engine. The offender
is unavailable for the rest of that match and cannot change positions to escape
the sanction. These manual choices do not establish canonical BB-0 severity tiers.
F8 now provides the [Serious penalty-shot flow](native-penalty-shots.md) in both
variants. Moderate free shots, automatic severity/escalation, terminal-event
restorative shots, match reports and Catastrophic adjudication remain incomplete.

The [wandplay validation receipt](native-wandplay-validation.md) records **212
passing checks: 130 portable and 82 native**, including the separate regulation,
Bloodbroom and spell-network runs. It identifies tested behavior, fixture limits
and the separate standalone-package/physical-UI outcome. Those historical eighteen-adapter receipts do not certify the five newer
[Sprint 3 adapters](native-sport-spells.md), which have a separate runtime suite.

# native wandplay and bb-0 playtest

this is the UE5.8 sporting adapter for the [new bb-0 direction](bb0-contact-and-spells.md).
it is not hogwarts legacy's native spell system and does not complete the creator
kit integration. the full allowed repertoire is retained in the
[spell catalog](../Rules/spell_catalog.json); implementation availability is a
separate question.

## controls

- **Q:** cast the selected spell along the reticle.
- **z / X:** select the previous or next entry. **V:** open the spellbook.
- **R:** cast protego without changing selection.
- **B:** host toggles Basketbroom/Bloodbroom in the initial lobby only.
- **f7 / f8 / F9:** host resolves a pending conduct call with possession, a
  serious penalty shot plus removal, or ejection. these remain host-selected
  playtest choices, not automatic severity assignments.

the existing flight, ball, role and team controls remain. bloodbroom keeps the
same ball/clock format and waives only the unforgivable and headshot prohibitions.
it does not change mobbing or double-tap decisions. physical holding has no
player ability in this build; the portable conduct policy prohibits it in both
variants, but physical holding detection is not integrated.

## available sporting adaptations

twenty-three spell-menu actions have native sporting behavior. five new actions
are detailed in [sprint 3 spellwork](native-sport-spells.md): revelio,
disillusionment, petrificus totalus, transformation and Imperio. the prior
eighteen remain: basic cast, protego, stupefy, accio,
depulso, descendo, flipendo, arresto momentum, glacius, levioso, incendio,
confringo, diffindo, expelliarmus, bombarda, lumos, avada kedavra and Crucio.

these are provisional sporting effects. damage drains regenerating vitality;
zero vitality causes a three-second knockout and restores fifty vitality.
avada kedavra currently causes a six-second knockout, not a death simulation.
crucio applies a two-second disable. force spells apply native movement impulses;
flipendo does not yet animate a full flip. elemental spells have no splash,
lingering damage or advanced combos. stupefy is directly castable in this
playtest; the base game's protego-counter activation is not reproduced yet.

arresto momentum slows flight to 35% for three seconds. glacius freezes for
1.5 seconds; levioso lifts and slows for two seconds. these three control effects
are provisionally treated as impediments for double-tap detection. this does not
rename arresto momentum to impedimenta or establish that their lore definitions
are interchangeable. stupefy is a stun; it does not itself create an impediment
confirmation record. protego shields for one second; unforgivables bypass it.
expelliarmus disables wandwork for 2.5 seconds; lumos toggles a real point light.
cooldowns, ranges, vitality and durations are playtest tuning in `BBSpellCatalog.cpp`.

the spellbook also shows six remaining base spells and the two ancient
magic actions, marked **adapter due / LATER**. they are allowed repertoire with
unimplemented target/context adapters, not forbidden bb-0 spells. beast-care
tools are cataloged separately. cpu teammates still play the ball game and do
not autonomously cast spells.

## authority, evidence and limitations

the owning rider sends only a spell index and normalized aim. the server checks
live status, rider eligibility, cooldown, disarm and stun, uses a server-derived
cast origin, clips against visible world geometry, then sweeps against rider
capsules. clients do not choose a victim, report damage or provide hit timestamps.
spell visuals replicate their endpoints and have no gameplay collision.

hits resolve immediately; the visible beam is cosmetic, not a travelling
projectile. there is no latency rewind. the upper capsule region, more than
65 cm above the rider origin, is the provisional head zone. this is not
skeletal head-bone precision. native mob evidence currently starts with a traced
target contact (including a shielded attempt), so misses with no identified
target do not establish mob membership. bludger head regions and ordinary body
contact are not wired into the new wand-call adapter yet.

the portable policy uses at most three distinct same-team attackers per target
within a provisional two seconds of live time. it retains server-minted attack
ids, rejects duplicate resolutions and freezes its windows at stoppages. a
double-tap requires an active successful impediment and prior clear feedback
to that caster. in the normal client, the hud draws the server notice and a
later native tick acknowledges that id after 0.25 seconds. the server binds the
receipt to its original successful cast. this is a normal-client delivery
protocol, not proof of human attention or protection against a modified client
withholding acknowledgments. cross-teammate awareness is not implemented.

critical feedback preempts ordinary notices. queues are bounded; stale receipts
expire without invented acknowledgments. combat identity follows a rider across
position swaps. new occupants cannot inherit an old rider's confirmation IDs.
Match/phase resets clear relevant conduct state; ordinary stoppages preserve it.
the new sporting status timers retain their remaining duration through quarter
breaks and clear on a genuine match reset.

## applied hit, then referee decision

an illegal hit has its real effect first. the adapter then records one combined
call and pauses play, even when several definitions apply. the pending call
blocks resumption and position changes. host authority is checked on the server;
a remote client cannot choose the variant or serve a referee disposition.

f7 chooses a moderate possession award, preferring the quaffle and then a free
Quark. donnybrook has only the Quarks. it reserves the ball without overwriting an existing remedy. the
penalty remains pending while the award is queued. on resumption, an eligible
opponent receives a protected restart near the recorded hit location; only
then is the penalty marked served. certification cannot skip an unserved award.
if every active scoring ball already has a remedy, the review stays pending.
deferring an award until a later stoppage is not implemented; f9 must not be
treated as a required substitute for an appropriate possession disposition.

f9 chooses a severe ejection through the existing rules engine. the offender
is unavailable for the rest of that match and cannot change positions to escape
the sanction. these manual choices do not establish canonical bb-0 severity tiers.
f8 now provides the [serious penalty-shot flow](native-penalty-shots.md) in both
variants. moderate free shots, automatic severity/escalation, terminal-event
restorative shots, match reports and catastrophic adjudication remain incomplete.

the [wandplay validation receipt](native-wandplay-validation.md) records **212
passing checks: 130 portable and 82 native**, including the separate regulation,
bloodbroom and spell-network runs. it identifies tested behavior, fixture limits
and the separate standalone-package/physical-UI outcome. those historical eighteen-adapter receipts do not certify the five newer
[sprint 3 adapters](native-sport-spells.md), which have a separate runtime suite.

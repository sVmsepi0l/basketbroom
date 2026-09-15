# Sprint 3 sporting spell adapters

The UE5.8 prototype now implements 23 of the 31 spell-menu actions. Five new
adapters extend [native wandplay](native-wandplay.md) without changing stable
catalog indices or claiming Hogwarts Legacy's combat implementation. Their
numbers and restrictions are provisional sporting tuning, not new BB-0 laws.

## New player actions

- **Revelio (3):** six live seconds of detecting concealed opponents within
  22 metres, with a two-second shared wand cooldown. World geometry obstructs
  detection. It does not reveal locked objects, collectibles or quest data.
- **Disillusionment (20):** six live seconds of concealment from opposing
  players, with a two-second shared cooldown. Self and teammates still see the
  rider. Casting at another rider, including a miss or rejected stealth attempt,
  breaks concealment. An applied wand hit also breaks the target's concealment;
  a blocked hit does not. Activating concealment extinguishes Lumos. Carried
  equipment balls remain separate visible actors; physical collisions and blind
  aimed hits continue to work. This is visual camouflage, not invulnerability.
- **Petrificus Totalus (5):** a concealed caster within 3.5 metres must approach
  from behind the target's aim direction. The target's forward direction dotted
  with target-to-caster horizontal direction must be below -0.5; the target's
  active, in-range Revelio defeats that condition. An accepted hit binds for
  2.5 live seconds, halts flight and drops held equipment. Protego blocks it.
  The shared cooldown is three seconds. It counts as a stun for the existing
  post-confirmed-impediment prohibition. This does not reproduce the base
  game's stealth takedown animation or lethal enemy outcomes.
- **Transformation (13):** a hit within 24 metres places a rider in a purple
  sporting orb form for three live seconds. Flight, wandwork and ball interaction
  are locked, held equipment is dropped, and shield/light are cleared. The
  collision capsule and owned pawn stay intact. Protego blocks the effect.
  The shared cooldown is four seconds. It provisionally counts as an impediment,
  so the existing genuine HUD confirmation flow protects against a follow-up stun.
- **Imperio (28):** a hit within 28 metres reverses horizontal flight acceleration
  for three live seconds, with a four-second shared cooldown. Looking, ascending,
  descending, ball actions and wand choices remain controlled by the player.
  Keyboard and controller flight share the same native movement simulation.
  Releasing horizontal input brakes normally; the effect expires automatically.
  No pawn possession, controller transfer, team reassignment or network ownership
  transfer occurs. This is explicitly an input-confusion sport adaptation, not
  full mind control. As an Unforgivable, it bypasses Protego and applies before
  regulation review. Bloodbroom permits the curse while retaining every other
  shared conduct restriction.

## Status, presentation and lifecycle

All five status timers replicate from authority and advance with consumed live
match time. Stoppages and active free/penalty shots freeze them. Opening a new
match clears them; ordinary stoppages and quarter breaks retain them. Existing protected
shot/restart movement overrides remain in place. Position swaps carry the rider's
statuses instead of giving an escape from an effect.

Concealment uses each local player's hidden-actor list, so independent local
viewers can see different results. The spell owns only the entries it adds and
cleans them up on expiry, reset or EndPlay. Rider status rings show reveal,
concealment, binding and confusion when the rider is visible to that viewer.
Transformation hides the original meshes without changing their visibility or
collision configuration, shows a noncolliding original orb and rings, and restores
the saved hidden flags on recovery. These are readable prototype effects;
final character art and cinematic spell animation remain in development.

## Validation procedure and limits

After compiling and loading the new native module, run
`Tools/test_native_sport_spells.py` through the existing editor bridge once with
`{"variant":"regulation","max_wall_seconds":420}` and once in a fresh PIE world
with `{"variant":"bloodbroom","max_wall_seconds":420}`. The suite owns and ends
its world and publishes atomic receipts under
`.local/native-sport-spells-{variant}-results.json`.

Each run plans 21 checks: real per-view concealment, detection range/occlusion,
cast/hit reveal, rejected and successful stealth conditions, actual possession
drops, shield counterplay, transformed collision/presentation and action locks,
frozen timers, recovery, Imperio movement/ownership and mode-dependent review,
stopped action denial, genuine quarter-boundary preservation/recovery, and remaining contextual
spells. Fixture transforms, component ticks, real AddMovementInput and accelerated
world ticks arrange the test. No effect timer, hit receipt, possession, score,
conduct decision or rule clock is injected. `--list` and syntax checks do not
claim runtime success; the final receipts establish that separately. Network
replication, packaged rendering, physical input devices and genuine rematch cleanup
need their own checks.

Eight actions remain contextual: Alohomora, Wingardium Leviosa, Reparo, Conjuring,
Altering, Evanesco, Ancient Magic and Ancient Magic Throw. World construction,
object permissions, repair/lock state, throwables and Ancient Magic resources
need real adapters. CPU wand tactics, advanced elemental effects and the full
Creator Kit integration also remain outstanding.

## Separate network coverage

`Tools/test_native_sport_spell_network.py` passed 12 checks in two separate local
PIE worlds. Its four spell adapters are Disillusionment, Revelio, Transformation
and Imperio: real owning-client requests, replicated timers and concealment,
transformation drop/action locks, stopped-time preservation, Imperio movement
and ownership, and rejection of remote free-shot adjudication. The final case
checks fixture settings and PIE cleanup. The receipt is
`.local/native-sport-spell-network-results.json`.

This suite never casts Petrificus Totalus. Its network cast, binding status and
double-tap behavior remain untested by this receipt, although the separate
single-world suite exercises its stealth conditions and actual binding. Two
PIE worlds in one editor process also do not certify separate machines, adverse
latency, packet loss, physical controller transport or Hogwarts Legacy multiplayer.

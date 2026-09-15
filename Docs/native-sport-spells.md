# sprint 3 sporting spell adapters

this sprint initially implemented 23 of the 31 spell-menu actions. these five
adapters extend [native wandplay](native-wandplay.md) without changing stable
catalog indices or claiming hogwarts legacy's combat implementation. their
numbers and restrictions are provisional sporting tuning, not new bb-0 laws.

## new player actions

- **revelio (3):** six live seconds of detecting concealed opponents within
  22 metres, with a two-second shared wand cooldown. world geometry obstructs
  detection. it does not reveal locked objects, collectibles or quest data.
- **disillusionment (20):** six live seconds of concealment from opposing
  players, with a two-second shared cooldown. self and teammates still see the
  rider. casting at another rider, including a miss or rejected stealth attempt,
  breaks concealment. an applied wand hit also breaks the target's concealment;
  a blocked hit does not. activating concealment extinguishes Lumos. carried
  equipment balls remain separate visible actors; physical collisions and blind
  aimed hits continue to work. this is visual camouflage, not invulnerability.
- **petrificus totalus (5):** a concealed caster within 3.5 metres must approach
  from behind the target's aim direction. the target's forward direction dotted
  with target-to-caster horizontal direction must be below -0.5; the target's
  active, in-range revelio defeats that condition. an accepted hit binds for
  2.5 live seconds, halts flight and drops held equipment. protego blocks it.
  the shared cooldown is three seconds. it counts as a stun for the existing
  post-confirmed-impediment prohibition. this does not reproduce the base
  game's stealth takedown animation or lethal enemy outcomes.
- **transformation (13):** a hit within 24 metres places a rider in a purple
  sporting orb form for three live seconds. flight, wandwork and ball interaction
  are locked, held equipment is dropped, and shield/light are cleared. the
  collision capsule and owned pawn stay intact. protego blocks the effect.
  the shared cooldown is four seconds. it provisionally counts as an impediment,
  so the existing genuine hud confirmation flow protects against a follow-up stun.
- **imperio (28):** a hit within 28 metres reverses horizontal flight acceleration
  for three live seconds, with a four-second shared cooldown. looking, ascending,
  descending, ball actions and wand choices remain controlled by the player.
  keyboard and controller flight share the same native movement simulation.
  releasing horizontal input brakes normally; the effect expires automatically.
  no pawn possession, controller transfer, team reassignment or network ownership
  transfer occurs. this is explicitly an input-confusion sport adaptation, not
  full mind control. as an unforgivable, it bypasses protego and applies before
  regulation review. bloodbroom permits the curse while retaining every other
  shared conduct restriction.

## status, presentation and lifecycle

all five status timers replicate from authority and advance with consumed live
match time. stoppages and active free/penalty shots freeze them. opening a new
match clears them; ordinary stoppages and quarter breaks retain them. existing protected
shot/restart movement overrides remain in place. position swaps carry the rider's
statuses instead of giving an escape from an effect.

concealment uses each local player's hidden-actor list, so independent local
viewers can see different results. the spell owns only the entries it adds and
cleans them up on expiry, reset or EndPlay. rider status rings show reveal,
concealment, binding and confusion when the rider is visible to that viewer.
transformation hides the original meshes without changing their visibility or
collision configuration, shows a noncolliding original orb and rings, and restores
the saved hidden flags on recovery. these are readable prototype effects;
final character art and cinematic spell animation remain in development.

## validation procedure and limits

after compiling and loading the new native module, run
`Tools/test_native_sport_spells.py` through the existing editor bridge once with
`{"variant":"regulation","max_wall_seconds":420}` and once in a fresh pie world
with `{"variant":"bloodbroom","max_wall_seconds":420}`. the suite owns and ends
its world and publishes atomic receipts under
`.local/native-sport-spells-{variant}-results.json`.

each run plans 21 checks: real per-view concealment, detection range/occlusion,
cast/hit reveal, rejected and successful stealth conditions, actual possession
drops, shield counterplay, transformed collision/presentation and action locks,
frozen timers, recovery, imperio movement/ownership and mode-dependent review,
stopped action denial, genuine quarter-boundary preservation/recovery, and remaining contextual
spells. fixture transforms, component ticks, real addmovementinput and accelerated
world ticks arrange the test. no effect timer, hit receipt, possession, score,
conduct decision or rule clock is injected. `--list` and syntax checks do not
claim runtime success; the final receipts establish that separately. network
replication, packaged rendering, physical input devices and genuine rematch cleanup
need their own checks.

the remaining eight contextual actions now have separate [bounded workshop and
resource adapters](native-contextual-spells.md): alohomora, wingardium leviosa,
reparo, conjuring, altering, evanesco, ancient magic and ancient magic Throw.
their dedicated tests establish their own validation, separate from the five
status adapters documented here. cpu wand tactics, advanced elemental effects
and the full creator kit integration remain outstanding.

## separate network coverage

`Tools/test_native_sport_spell_network.py` passed 12 checks in two separate local
pie worlds. its four spell adapters are disillusionment, revelio, transformation
and Imperio: real owning-client requests, replicated timers and concealment,
transformation drop/action locks, stopped-time preservation, imperio movement
and ownership, and rejection of remote free-shot adjudication. the final case
checks fixture settings and pie cleanup. the receipt is
`.local/native-sport-spell-network-results.json`.

this suite never casts petrificus Totalus. its network cast, binding status and
double-tap behavior remain untested by this receipt, although the separate
single-world suite exercises its stealth conditions and actual binding. two
pie worlds in one editor process also do not certify separate machines, adverse
latency, packet loss, physical controller transport or hogwarts legacy multiplayer.

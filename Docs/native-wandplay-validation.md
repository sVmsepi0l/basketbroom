# native wandplay validation — 2026/09/12

> **historical roof evidence:** the crown reservation used by this milestone predates the user’s 2026/09/14 [closed pyramid-net amendment](pyramid-net.md). these original results remain historical evidence of their named builds; they do not validate the replacement roof. current native matches cannot create no crown exit reservations.

the bb-0 wandplay and controller milestone has **229 passing checks: 130 portable
c++ cases and 99 native unreal pie checks**. every receipt listed below has `status: passed`;
the native reports have zero failed and zero not run. these are separate,
bounded runs with overlapping coverage, not 229 distinct features or one full
match. the spell/conduct suites account for 30 native checks; controller input
adds 17 checks to the earlier 212-check milestone.

the runtime reports identify **unreal engine
`5.8.1-56057345+++UE5+Release-5.8`** on windows and the owned
`/Basketbroom/Maps/BB_Regulation` map. they exercise the compiled
`basketbroomruntime` module. [wandplay behavior and controls](native-wandplay.md)
describe the implementation; [bb-0 decisions](bb0-contact-and-spells.md) separate
confirmed user rules from provisional tuning and referee choices.

## passing receipts

paths are relative to the repository root. `.local` receipts are local generated
evidence and may be replaced by another run; they are not published test assets.

- **68 portable core-rule cases:** `.local/native-rules/results.json`, produced
  by `Tools/test_native_rules.py`. includes the 54 reference scenarios plus
  native-rule extensions. this run used msvc `14.51.36231`.
- **38 portable bb-0 conduct cases:** `.local/native-combat-rules/results.json`,
  produced by `Tools/test_native_combat_rules.py`, also using msvc
  `14.51.36231`. covers variant exceptions, attacker counting, hit outcomes,
  confirmation ownership/order, expiry, stoppages and identity/reset semantics.
- **24 portable possession-award cases:**
  `.local/native-conduct-awards/results.json`, produced by
  `Tools/test_native_conduct_awards.py` using the installed creator kit's
  bundled `g++.exe`. covers rejected/atomic reservations, protected existing
  remedies, pending certification, permitted resume and actual one-time service.
- **35 native gameplay checks, 13.032 seconds:**
  `.local/native-playable-test-results.json`, from
  `Tools/test_native_playable.py`. rechecks the native roster, clocks, roles,
  flight, ball collisions, goals and chase contract.
- **17 native general networking checks, 8.735 seconds:**
  `.local/native-network-test-results.json`, from
  `Tools/test_native_network.py`. rechecks local client requests, authority,
  movement, scoring and ball possession/release replication.
- **17 native regulation spell checks, 44.891 seconds:**
  `.local/native-spell-test-results.json`, from `Tools/test_native_spells.py`
  with `variant: regulation`.
- **3 native bloodbroom checks, 17.172 seconds:**
  `.local/native-bloodbroom-spell-test-results.json`, from the same helper with
  `variant: bloodbroom`.
- **10 native spell networking checks, 55.890 seconds:**
  `.local/native-spell-network-test-results.json`, from
  `Tools/test_native_spell_network.py`.
- **17 native controller input checks, 14.172 seconds:**
  `.local/native-controller-test-results.json`, from
  `Tools/test_native_controller.py`. simulated gamepad events enter ordinary
  playerinput and gameplay bindings. see [controller validation](controller-support.md)
  for the input-test correction and the separate unverified USB/Bluetooth scope.

the latest gameplay and single-world spell reruns recorded a 764,416-byte
controller/VFX DLL. both network suites passed on that loaded build. a final
neutral-latch correction made reconnect behaviour respect the configured stick
deadzone; the controller suite then passed on its 764,928-byte DLL. their
receipts preserve individual timestamps and world provenance. the total does
not assert that every suite ran against one identical binary. earlier receipts
were copied into `.local/bb0-before-controller/`. the earlier 54 python-reference
tests and historical six-suite 96-check milestone are not added to this total.

## what the wandplay runs observed

the regulation fixture used two actual local humans in one native world. it
observed torso damage, a genuine miss that spent cooldown, physical side-net
occlusion and protego blocking an actual hit. an unimplemented contextual spell
reported its pending adapter without producing a combat effect. arresto reduced
measured native flight speed from about 727 to 252 cm/s under matching input.
accio, depulso, descendo, flipendo and levioso produced directional movement
while retaining flying; the affected rider retained vertical input and the
chase ceiling.

actual owner hud drawing and a later native receipt preceded the forbidden
stupefy follow-up. the stun took effect before the double-tap review paused
play. the fixture observed frozen live effect timers, rejection of enter while
review was pending, f7 remaining pending until actual opposing possession, and
a headshot reducing vitality from 100 to 92 before review. f9 moved the offender
to the penalty area; role changes and subsequent casting could not escape the
ejection.

bloodbroom could be selected in the initial lobby and was locked after kickoff.
an unforgivable head hit bypassed protego without those two ordinary prohibitions
producing a foul. a confirmed-impediment follow-up still produced DOUBLE-TAP.
this does not add exceptions for mobbing or physical holding.

the spell network run used distinct listen-server and client pie worlds. a real
client basic cast produced replicated vitality of approximately 92.584 and
92.556; protego blocked the host's bolt, with native block feedback and unchanged
target vitality. stupefy and arresto effects and their recovery replicated.
the remote client could neither select bloodbroom nor adjudicate the pending
call. a host headshot produced 92 vitality and the same referee stoppage in both
worlds.

for f7 fallback, an actual free quaffle roof exit created a crown reservation.
the ordinary headshot paused play while that reservation was active. f7 kept
the quaffle reserved and queued quark 1 with one pending penalty. only the real
restart cleared that penalty and gave the opposing client quark possession in
both worlds. the quaffle then returned neutrally, with unchanged scores and
the client still holding its awarded Quark.

## fixture and cleanup boundaries

requests enter the guarded development fifo and are dispatched from normal
native rider tick through the same action path as ordinary input. tests do not
write vitality, effect timers, rule state, scores, penalties or possession, and
do not fabricate hit-confirmation receipts. CPU/unused equipment isolation and
explicit positions exist only in disposable pie worlds. the spell network test
arranges positions in both views, so it makes no movement-replication claim;
the separate general network suite covers its own movement scenario.

the single-world spell runs use 0.5x world time and the network spell run uses
0.25x. they suspend local controller look updates and wait for the cached owner
camera direction to settle before queueing each aimed cast. earlier failed
fixtures are retained in `.local/native-spell-test-first-run.json` and
`.local/native-spell-test-camera-cache-run.json`: setting control rotation and
queueing a cast in the same callback could use the previous frame's camera aim.
the final passes followed the fixture correction; their miss assertions were
not waived.

single-world receipts record restored controller look ticks, removed extra
local players, restored dilation and an endplay request. their report alone is
not a separate assertion that teardown had finished. the network suite's final
check explicitly observed no pie worlds and restoration of managed settings
and dilation. the python net-mode enum was unavailable, so its report separately
flags restoration of the play net mode selected through the editor UI.

the hud receipt is evidence of normal-client delivery, not proof of human
attention or protection against a modified client withholding acknowledgments.
network double-tap acknowledgement was not asserted; that evidence belongs to
the single-world tests. these runs do not establish human key timing, visual
quality, audio, match balance, sustained performance, remote-machine latency,
loss, reconnects, dedicated-server operation or sixteen human participants.

## scope and remaining work at this milestone

the september 12 build had **18 implemented sporting adapters and 13 pending adapters**
among its 31 choices. that pending group contained eleven base spells and both
ancient magic actions. current source has [23 sporting adapters and eight pending actions](native-sport-spells.md); the earlier receipts here do not validate those later additions. the broader source catalog separately includes three
beast-care tools. the passing suites exercise selected adapters and contracts;
they do not independently validate every implemented spell.

the adapters are provisional arena behaviors, not full hogwarts legacy spell
parity. contextual targets, stealth, transformations, construction, mind control,
ancient magic, detailed animation, elemental splash/lingering effects and the
base game's protego-counter activation of stupefy remain unfinished. cpu riders
do not cast autonomously. head detection uses an upper capsule region rather
than a skeletal head; cross-teammate awareness, physical holding detection and
Bludger/body-contact integration with the new wand calls remain incomplete.
the mob window and impediment categories remain provisional.

illegal hits apply before the limited host referee decision. F7/F9 are manual
playtest dispositions, not final automatic bb-0 severity judgments. penalty-shot
execution, serious and catastrophic adjudication, escalation, terminal-event
restoration and match reporting remain unfinished. if all scoring balls already
have remedies, review remains pending; deferring the award is not implemented.
the UE5.8 result does not establish spell integration, entrance travel or
multiplayer in the UE4.27 hogwarts legacy creator kit port.

## standalone package and physical ui

package `development-20260912-125404-221` completed under ue 5.8.1 in 37.50 seconds
with automationtool exit code zero. its executable is
`.local/Build/Development-20260912-125404-221/Windows/BasketbroomDev.exe`;
the complete build log is recorded in `.local/latest-package.json` and
`.local/bb0-package.log`.

the visible standalone practice launch was inspected with ordinary keyboard
input: a fresh 0–0 lobby, all 31 spellbook choices with availability labels,
Z/X selection and descriptions, v opening/closing, b switching both variants,
enter starting live play, r raising protego with its cooldown/status feedback,
and q producing basic cast miss feedback. cpu ball play continued during this
smoke test. this was not a controlled manual hit or multiplayer test.

the first inspection found oversized central first-person spell/shield visuals.
after rebuilding, ordinary R/Q input in live pie showed fine peripheral shield
segments with an open centre and a cast beam starting at the visible wand tip.
the large central disk was absent. this is a visual smoke check, not a graphics
performance measurement.

`Install-DesktopShortcut.ps1` created and read back
`C:\Users\bigdi\Desktop\Basketbroom.lnk`. launching that actual shortcut opened
the same completed package into a fresh practice lobby. it invokes the stable
repository `Play.ps1 -practice` with a hidden powershell launcher and follows
future completed package manifests. no execution policy was changed.

the later controller/VFX package `development-20260912-134800-592` completed
in **60.19 seconds**, with automationtool exit code zero. it is now selected by
`.local/latest-package.json`; the shortcut was refreshed and launched this exact
package into a fresh 0–0 practice lobby. packaged gameinput initialized
successfully with runtime `3.1.26100.6879`, and its prerequisite msi was staged.
receipts are `.local/controller-package.log` and
`.local/controller-packaged-backend-startup.json`.
after the user clicked allow on windows security's network-access prompt, the
packaged manual check completed: scout selection, spellbook opening/closing,
live kickoff, protego with a clear reticle, basic cast with a wand-tip beam and
miss feedback, and stoppage/resume all responded to ordinary keyboard input.
cpu scoring advanced. alt+f4 closed the game normally and its log recorded a
clean exit. launching the desktop shortcut again produced a fresh 0–0 ranger
lobby with a 3:00 practice clock and no repeated windows prompt.
`.local/controller-packaged-smoke.json` records this separate smoke
check; it adds no cases to the automated total. physical USB/Bluetooth input is
still unverified. see the
[controller playtest](controller-support.md) for the complete control layout.

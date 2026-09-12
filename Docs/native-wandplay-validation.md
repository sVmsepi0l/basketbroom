# Native wandplay validation — 2026-09-12

The BB-0 wandplay and controller milestone has **229 passing checks: 130 portable
C++ cases and 99 native Unreal PIE checks**. Every receipt listed below has `status: passed`;
the native reports have zero failed and zero not run. These are separate,
bounded runs with overlapping coverage, not 229 distinct features or one full
match. The spell/conduct suites account for 30 native checks; controller input
adds 17 checks to the earlier 212-check milestone.

The runtime reports identify **Unreal Engine
`5.8.1-56057345+++UE5+Release-5.8`** on Windows and the owned
`/Basketbroom/Maps/BB_Regulation` map. They exercise the compiled
`BasketbroomRuntime` module. [Wandplay behavior and controls](native-wandplay.md)
describe the implementation; [BB-0 decisions](bb0-contact-and-spells.md) separate
confirmed user rules from provisional tuning and referee choices.

## Passing receipts

Paths are relative to the repository root. `.local` receipts are local generated
evidence and may be replaced by another run; they are not published test assets.

- **68 portable core-rule cases:** `.local/native-rules/results.json`, produced
  by `Tools/test_native_rules.py`. Includes the 54 reference scenarios plus
  native-rule extensions. This run used MSVC `14.51.36231`.
- **38 portable BB-0 conduct cases:** `.local/native-combat-rules/results.json`,
  produced by `Tools/test_native_combat_rules.py`, also using MSVC
  `14.51.36231`. Covers variant exceptions, attacker counting, hit outcomes,
  confirmation ownership/order, expiry, stoppages and identity/reset semantics.
- **24 portable possession-award cases:**
  `.local/native-conduct-awards/results.json`, produced by
  `Tools/test_native_conduct_awards.py` using the installed Creator Kit's
  bundled `g++.exe`. Covers rejected/atomic reservations, protected existing
  remedies, pending certification, permitted resume and actual one-time service.
- **35 native gameplay checks, 13.032 seconds:**
  `.local/native-playable-test-results.json`, from
  `Tools/test_native_playable.py`. Rechecks the native roster, clocks, roles,
  flight, ball collisions, goals and chase contract.
- **17 native general networking checks, 8.735 seconds:**
  `.local/native-network-test-results.json`, from
  `Tools/test_native_network.py`. Rechecks local client requests, authority,
  movement, scoring and ball possession/release replication.
- **17 native regulation spell checks, 44.891 seconds:**
  `.local/native-spell-test-results.json`, from `Tools/test_native_spells.py`
  with `variant: regulation`.
- **3 native Bloodbroom checks, 17.172 seconds:**
  `.local/native-bloodbroom-spell-test-results.json`, from the same helper with
  `variant: bloodbroom`.
- **10 native spell networking checks, 55.890 seconds:**
  `.local/native-spell-network-test-results.json`, from
  `Tools/test_native_spell_network.py`.
- **17 native controller input checks, 14.172 seconds:**
  `.local/native-controller-test-results.json`, from
  `Tools/test_native_controller.py`. Simulated gamepad events enter ordinary
  PlayerInput and gameplay bindings. See [controller validation](controller-support.md)
  for the input-test correction and the separate unverified USB/Bluetooth scope.

The latest gameplay and single-world spell reruns recorded a 764,416-byte
controller/VFX DLL. Both network suites passed on that loaded build. A final
neutral-latch correction made reconnect behaviour respect the configured stick
deadzone; the controller suite then passed on its 764,928-byte DLL. Their
receipts preserve individual timestamps and world provenance. The total does
not assert that every suite ran against one identical binary. Earlier receipts
were copied into `.local/bb0-before-controller/`. The earlier 54 Python-reference
tests and historical six-suite 96-check milestone are not added to this total.

## What the wandplay runs observed

The regulation fixture used two actual local humans in one native world. It
observed torso damage, a genuine miss that spent cooldown, physical side-net
occlusion and Protego blocking an actual hit. An unimplemented contextual spell
reported its pending adapter without producing a combat effect. Arresto reduced
measured native flight speed from about 727 to 252 cm/s under matching input.
Accio, Depulso, Descendo, Flipendo and Levioso produced directional movement
while retaining Flying; the affected rider retained vertical input and the
chase ceiling.

Actual owner HUD drawing and a later native receipt preceded the forbidden
Stupefy follow-up. The stun took effect before the DOUBLE-TAP review paused
play. The fixture observed frozen live effect timers, rejection of Enter while
review was pending, F7 remaining pending until actual opposing possession, and
a headshot reducing vitality from 100 to 92 before review. F9 moved the offender
to the penalty area; role changes and subsequent casting could not escape the
ejection.

Bloodbroom could be selected in the initial lobby and was locked after kickoff.
An Unforgivable head hit bypassed Protego without those two ordinary prohibitions
producing a foul. A confirmed-impediment follow-up still produced DOUBLE-TAP.
This does not add exceptions for mobbing or physical holding.

The spell network run used distinct listen-server and client PIE worlds. A real
client Basic Cast produced replicated vitality of approximately 92.584 and
92.556; Protego blocked the host's bolt, with native BLOCK feedback and unchanged
target vitality. Stupefy and Arresto effects and their recovery replicated.
The remote client could neither select Bloodbroom nor adjudicate the pending
call. A host headshot produced 92 vitality and the same referee stoppage in both
worlds.

For F7 fallback, an actual free Quaffle roof exit created a Crown reservation.
The ordinary headshot paused play while that reservation was active. F7 kept
the Quaffle reserved and queued Quark 1 with one pending penalty. Only the real
restart cleared that penalty and gave the opposing client Quark possession in
both worlds. The Quaffle then returned neutrally, with unchanged scores and
the client still holding its awarded Quark.

## Fixture and cleanup boundaries

Requests enter the guarded development FIFO and are dispatched from normal
native rider Tick through the same action path as ordinary input. Tests do not
write vitality, effect timers, rule state, scores, penalties or possession, and
do not fabricate hit-confirmation receipts. CPU/unused equipment isolation and
explicit positions exist only in disposable PIE worlds. The spell network test
arranges positions in both views, so it makes no movement-replication claim;
the separate general network suite covers its own movement scenario.

The single-world spell runs use 0.5x world time and the network spell run uses
0.25x. They suspend local controller look updates and wait for the cached owner
camera direction to settle before queueing each aimed cast. Earlier failed
fixtures are retained in `.local/native-spell-test-first-run.json` and
`.local/native-spell-test-camera-cache-run.json`: setting control rotation and
queueing a cast in the same callback could use the previous frame's camera aim.
The final passes followed the fixture correction; their miss assertions were
not waived.

Single-world receipts record restored controller look ticks, removed extra
local players, restored dilation and an EndPlay request. Their report alone is
not a separate assertion that teardown had finished. The network suite's final
check explicitly observed no PIE worlds and restoration of managed settings
and dilation. The Python net-mode enum was unavailable, so its report separately
flags restoration of the Play Net Mode selected through the editor UI.

The HUD receipt is evidence of normal-client delivery, not proof of human
attention or protection against a modified client withholding acknowledgments.
Network double-tap acknowledgement was not asserted; that evidence belongs to
the single-world tests. These runs do not establish human key timing, visual
quality, audio, match balance, sustained performance, remote-machine latency,
loss, reconnects, dedicated-server operation or sixteen human participants.

## Implemented scope and remaining work

The native menu has **18 implemented sporting adapters and 13 pending adapters**
among its 31 choices. The pending group contains eleven base spells and both
Ancient Magic actions. The broader source catalog separately includes three
beast-care tools. The passing suites exercise selected adapters and contracts;
they do not independently validate every implemented spell.

The adapters are provisional arena behaviors, not full Hogwarts Legacy spell
parity. Contextual targets, stealth, transformations, construction, mind control,
Ancient Magic, detailed animation, elemental splash/lingering effects and the
base game's Protego-counter activation of Stupefy remain unfinished. CPU riders
do not cast autonomously. Head detection uses an upper capsule region rather
than a skeletal head; cross-teammate awareness, physical holding detection and
Bludger/body-contact integration with the new wand calls remain incomplete.
The mob window and impediment categories remain provisional.

Illegal hits apply before the limited host referee decision. F7/F9 are manual
playtest dispositions, not final automatic BB-0 severity judgments. Penalty-shot
execution, Serious and Catastrophic adjudication, escalation, terminal-event
restoration and match reporting remain unfinished. If all scoring balls already
have remedies, review remains pending; deferring the award is not implemented.
The UE5.8 result does not establish spell integration, entrance travel or
multiplayer in the UE4.27 Hogwarts Legacy Creator Kit port.

## Standalone package and physical UI

Package `Development-20260912-125404-221` completed under UE 5.8.1 in 37.50 seconds
with AutomationTool exit code zero. Its executable is
`.local/Build/Development-20260912-125404-221/Windows/BasketbroomDev.exe`;
the complete build log is recorded in `.local/latest-package.json` and
`.local/bb0-package.log`.

The visible standalone practice launch was inspected with ordinary keyboard
input: a fresh 0–0 lobby, all 31 spellbook choices with availability labels,
Z/X selection and descriptions, V opening/closing, B switching both variants,
Enter starting live play, R raising Protego with its cooldown/status feedback,
and Q producing Basic Cast miss feedback. CPU ball play continued during this
smoke test. This was not a controlled manual hit or multiplayer test.

The first inspection found oversized central first-person spell/shield visuals.
After rebuilding, ordinary R/Q input in live PIE showed fine peripheral shield
segments with an open centre and a cast beam starting at the visible wand tip.
The large central disk was absent. This is a visual smoke check, not a graphics
performance measurement.

`Install-DesktopShortcut.ps1` created and read back
`C:\Users\bigdi\Desktop\Basketbroom.lnk`. Launching that actual shortcut opened
the same completed package into a fresh practice lobby. It invokes the stable
repository `Play.ps1 -Practice` with a hidden PowerShell launcher and follows
future completed package manifests. No execution policy was changed.

The later controller/VFX package `Development-20260912-134800-592` completed
in **60.19 seconds**, with AutomationTool exit code zero. It is now selected by
`.local/latest-package.json`; the shortcut was refreshed and launched this exact
package into a fresh 0–0 practice lobby. Packaged GameInput initialized
successfully with runtime `3.1.26100.6879`, and its prerequisite MSI was staged.
Receipts are `.local/controller-package.log` and
`.local/controller-packaged-backend-startup.json`.
After the user clicked Allow on Windows Security's network-access prompt, the
packaged manual check completed: Scout selection, spellbook opening/closing,
live kickoff, Protego with a clear reticle, Basic Cast with a wand-tip beam and
miss feedback, and stoppage/resume all responded to ordinary keyboard input.
CPU scoring advanced. Alt+F4 closed the game normally and its log recorded a
clean exit. Launching the desktop shortcut again produced a fresh 0–0 Ranger
lobby with a 3:00 practice clock and no repeated Windows prompt.
`.local/controller-packaged-smoke.json` records this separate smoke
check; it adds no cases to the automated total. Physical USB/Bluetooth input is
still unverified. See the
[controller playtest](controller-support.md) for the complete control layout.

# controller playtest

the standalone ue 5.8 game uses the same gameplay authority for keyboard and
gamepad input. wired and bluetooth are device connection methods; once windows
and unreal expose the controller as a supported gamepad, the game uses the same
bindings for both. physical USB/Bluetooth testing is still required and must be
reported separately from synthetic unreal input tests.

## layout

button names below use the xbox layout. on a playstation pad, the equivalent
face buttons are cross (a), circle (b), square (x), and triangle (y);
L1/R1 correspond to LB/RB and r2 to RT. native compatibility depends on the
windows input backend, not just these button equivalents.

- left stick flies; right stick looks and aims.
- hold a to rise or b to descend.
- hold x to grab or catch; rt throws the held ball.
- rb casts the selected spell; lb raises Protego.
- d-pad Left/Right selects spells. y opens or closes the spellbook.
- menu starts or resumes play, pauses a live match, or starts a rematch.
- view opens or closes the position guide. d-pad Up/Down changes position at
  stoppages, subject to eligibility.
- with the position guide explicitly open, d-pad left switches team and d-pad
  right toggles bloodbroom in the initial lobby. close the guide to return those
  buttons to spell selection.
- during a conduct review, the host selects **moderate free shot** with d-pad
  left, **moderate possession** with d-pad up, **serious** (shot and removal)
  with d-pad right, or **severe** (ejection) with d-pad down, then presses menu
  to confirm. opening a review selects no disposition. choosing a direction
  alone does not apply a penalty. keyboard F6/F7/F8/F9 request those respective
  host dispositions. the free shot adds no removal.

the hud changes its hints after gamepad input. Keyboard/mouse controls remain
available. stick movement is analog; camera rotation uses elapsed time rather
than adding a fixed angle every frame. focus loss, unpossession and controller
disconnection must clear held movement and catch input.

## penalty-shot controls

the same protected shot controls apply in basketbroom and Bloodbroom. sprint 3
also uses them for the moderate free shot: its stopped five-second attempt,
no-wand/no-pass/no-second-attempt restrictions and defending restart are explicit
prototype administration choices, not newly canonical rules. see the
[sprint 3 handoff](sprint-3-spells-graphics.md) for scope and final validation status.
the hud identifies the selected ball and point value, designated shooter and
keeper, and five-second attempt timer. the clock covers aiming and ball flight.
the normal match clock and combat-effect clocks remain frozen through the shot.

the shooter uses the right stick to aim and rt to release once, while movement
is locked at the mark. the keeper alone may fly inside the restricted goal area
and save by blocking the ball with their body. every other rider stays in place
and may look around. no wandwork, passes, role changes or second attempt are
allowed; menu cannot resume the match during the active procedure. after the
brief decision display, the defending keeper receives the protected restart
and the host may use menu to resume unless the shot triggers result review. after
certification, menu starts a new match. keyboard equivalents are mouse/LMB for
the shot, standard flight keys for the keeper, and enter for resume or rematch.

existing stuns and impediments are preserved rather than cleared. the designated
shooter's release and keeper's movement are narrowly allowed during the protected
procedure; the normal effects apply again when play resumes. these controls do
not imply that every penalty severity or all bloodbroom rules are implemented.

## windows input backend

the project enables **gameinputwindows** and selects **gameinput alone** as its
preferred controller API. its gameinput dependency is enabled by the plugin.
`xinputdevice` stays enabled in the project so a future explicit fallback can
select it, but it does not receive gamepad input under the default preference.
ue 5.8 marks gameinputwindows beta and the preferred-api selector experimental.

`DevelopmentHarness/Config/DefaultInput.ini` contains:

```ini
[/Script/Engine.InputSettings]
benablepreferredinputapipreferences=true
defaultpreferredinputapilist=gameinput

[gameinputplatformsettings_windows gameinputplatformsettings]
bprocessgamepad=true
bprocesscontroller=false
bprocessrawinput=false
bprocesskeyboard=false
bprocessmouse=false
```

`defaultpreferredinputapilist` is a scalar string of allowed api names, not an
array or an ordered fallback list. listing `gameinput,xinput` would enable both
and risk duplicate events. the windows platform settings explicitly enable the
standard gamepad processor; desktop defaults otherwise disable it. Generic/raw
controller processors remain disabled, and windows retains its ordinary
keyboard/mouse path. an editor `preferredinputapioverride` or saved
`[gamepadapipreference] preferredapi` takes precedence over the project default;
backend verification must inspect the effective choice.

`DevelopmentHarness/Config/DefaultEngine.ini` also contains:

```ini
[gameinput]
includeredistfiles=true
```

this directs unreal's windows packaging code to include
`Engine/Extras/Redist/en-us/GameInputRedist.msi` and mark the packaged bootstrap
for its prerequisite handling. the installed engine bundles the header and
`GameInput.lib`; its minimum runtime is **3.1.26100.6879**. this machine's
`System32/GameInputRedist.dll` meets that version, and the redist service was
running at inspection. this change does not run an installer or alter Windows.
other pcs still need the runtime; including its installer is not evidence that
it has been installed on those PCs. see [microsoft's redistribution guidance](https://learn.microsoft.com/en-us/xbox/gdk/docs/features/common/input/overviews/input-nuget?view=gdk-2604).

the installed gameinput runtime includes standard gamepad mappings labeled ps4
controller and ps5 Controller. this makes native playstation support plausible
without the separate windualshock plugin's unavailable libscepad dependencies.
it does not establish compatibility for every controller revision, connection
transport, touchpad, motion sensor or advanced haptic feature. gameinput maps
supported devices into the same unreal gamepad keys used by this layout.
[microsoft documents how device mappings determine available interfaces](https://learn.microsoft.com/en-us/gaming/gdk/docs/features/common/input/hardware/input-hardware-interfaces?view=gdk-2510).

if gameinput cannot initialize, keyboard and mouse remain available; there is
**no automatic xinput fallback** in this configuration. a deliberate fallback
would select only `xinput` and restart the application. neither real usb nor
bluetooth input, hotplug/reconnection, or absence of hardware-level duplicate
events has been verified by this configuration change. editor and packaged
startup logs and physical device checks remain separate evidence.

## validation status

the 2026/09/14 source adds an eighteenth controller case: d-pad right must
select serious during a real conduct review without applying a penalty,
starting a shot, changing the score or selecting another spell. the test then
chooses moderate and exercises the existing separate menu confirmation. this
eighteen-case suite passed on 2026/09/14 with zero failures or skipped cases.
the preserved receipt is `.local/penalty-validation-solo-20260914-141926/02-native-controller-test-results.json`.
this run precedes the final result-message-only patch; the dated 17-case evidence
and totals below remain historical and do not include the new case.

on 2026/09/12, **17 controller checks passed in 14.172 seconds**, with zero failed
and zero not run, under `5.8.1-56057345+++UE5+Release-5.8`. the receipt is
`.local/native-controller-test-results.json`, produced by
`Tools/test_native_controller.py` in the owned `bb_regulation` pie world. it
records the loaded native dll's size and timestamp.

these checks inject simulated gamepad events through
`FInputKeyEventArgs::CreateSimulated`, `PlayerController::InputKey` and ordinary
`playerinput` bindings. native controller ticks remain enabled. the fixture
arranges temporary pie transforms, component ticks and world time; it does not
write gameplay actions, effects, custody or penalties directly. axis transitions
use separate frames and releases are observed, avoiding same-frame accumulation
of a positive sample and its zero release.

the passing cases cover rejected invalid input, contextual roster/team/variant
controls, role and spell selection, match start/pause/resume, the stick deadzone,
partial-speed flight, strafe and vertical flight, time-scaled aiming and upward
pitch. they also observe actual spell damage, protego, ball pickup/release, an
explicit referee choice followed by separate confirmation, and a possession
award remaining queued until its real restart. the shared engine flush clears
axes, catch input and ghost flight. cleanup records restored time dilation and
an owned endplay request; this receipt does not independently assert completed
teardown.

the milestone total is **229 passing checks: the existing 212 wandplay/rules
checks plus these 17 controller checks**, comprising 130 portable c++ cases and
99 native unreal checks. the current gameplay (35), regulation spells (17),
bloodbroom (3), general networking (17) and spell networking (10) receipts also
passed with no failures or skipped cases; their paths and scope are listed in
[wandplay validation](native-wandplay-validation.md). these are separate bounded
runs with overlapping coverage. the final controller run followed the neutral
latch's processed-deadzone correction; this total does not claim one identical
binary across every run or 229 distinct features.

separately, `.local/controller-backend-startup.json` records successful editor
creation of `igameinput`, detection of runtime `3.1.26100.6879`, and registration
of the gamepad connection callback. this proves backend startup, while the
simulated tests prove the unreal input and gameplay bindings.

standalone package `development-20260912-134800-592` completed in 60.19 seconds
with automationtool exit code zero. its actual shortcut launch displayed a fresh
practice lobby. `.local/controller-packaged-backend-startup.json` records
successful packaged `igameinput` initialization using runtime
`3.1.26100.6879` and the gamepad callback. the package contains
`Windows/Engine/Extras/Redist/en-us/GameInputRedist.msi`.
after the user clicked allow on the windows network-access prompt, ordinary
keyboard input verified scout selection, spellbook opening/closing, match start,
protego, basic cast, and stoppage/resume in this package. the shield kept the
reticle clear and the cast originated at the visible wand tip. cpu scoring
continued. alt+f4 closed the game normally, with a clean exit in its log.
`.local/controller-packaged-smoke.json` records the observations and limits.
this manual smoke check adds no cases to the 229 automated-check total.

in a subsequent physical check on 2026/09/12, windows detected the user's sony
dualsense (vid `054c`, pid `0ce6`) over USB. the same packaged build registered
it through gameinput as a gamepad on device 1, platform user 0. the user confirmed
that pressing triangle opened the spellbook. this is actual hardware button
delivery, separate from the simulated checks above; the local receipt is
`.local/dualsense-hardware-playtest.json`.

the remaining usb flight/button checks and bluetooth pairing/input are pending.
hardware disconnect/reconnect, focus transitions, rumble, device-specific glyphs
and remote gamepad ownership/replication remain unverified. exercising the shared
flush does not simulate an actual hardware disconnect.

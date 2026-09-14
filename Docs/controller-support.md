# Controller playtest

The standalone UE 5.8 game uses the same gameplay authority for keyboard and
gamepad input. Wired and Bluetooth are device connection methods; once Windows
and Unreal expose the controller as a supported gamepad, the game uses the same
bindings for both. Physical USB/Bluetooth testing is still required and must be
reported separately from synthetic Unreal input tests.

## Layout

Button names below use the Xbox layout. On a PlayStation pad, the equivalent
face buttons are Cross (A), Circle (B), Square (X), and Triangle (Y);
L1/R1 correspond to LB/RB and R2 to RT. Native compatibility depends on the
Windows input backend, not just these button equivalents.

- Left stick flies; right stick looks and aims.
- Hold A to rise or B to descend.
- Hold X to grab or catch; RT throws the held ball.
- RB casts the selected spell; LB raises Protego.
- D-pad Left/Right selects spells. Y opens or closes the spellbook.
- Menu starts or resumes play, pauses a live match, or starts a rematch.
- View opens or closes the position guide. D-pad Up/Down changes position at
  stoppages, subject to eligibility.
- With the position guide explicitly open, D-pad Left switches team and D-pad
  Right toggles Bloodbroom in the initial lobby. Close the guide to return those
  buttons to spell selection.
- During a conduct review, the host selects **Moderate free shot** with D-pad
  Left, **Moderate possession** with D-pad Up, **Serious** (shot and removal)
  with D-pad Right, or **Severe** (ejection) with D-pad Down, then presses Menu
  to confirm. Opening a review selects no disposition. Choosing a direction
  alone does not apply a penalty. Keyboard F6/F7/F8/F9 request those respective
  host dispositions. The free shot adds no removal.

The HUD changes its hints after gamepad input. Keyboard/mouse controls remain
available. Stick movement is analog; camera rotation uses elapsed time rather
than adding a fixed angle every frame. Focus loss, unpossession and controller
disconnection must clear held movement and catch input.

## Penalty-shot controls

The same protected shot controls apply in Basketbroom and Bloodbroom. Sprint 3
also uses them for the Moderate free shot: its stopped five-second attempt,
no-wand/no-pass/no-second-attempt restrictions and defending restart are explicit
prototype administration choices, not newly canonical rules. See the
[sprint 3 handoff](sprint-3-spells-graphics.md) for scope and final validation status.
The HUD identifies the selected ball and point value, designated shooter and
keeper, and five-second attempt timer. The clock covers aiming and ball flight.
The normal match clock and combat-effect clocks remain frozen through the shot.

The shooter uses the right stick to aim and RT to release once, while movement
is locked at the mark. The keeper alone may fly inside the restricted goal area
and save by blocking the ball with their body. Every other rider stays in place
and may look around. No wandwork, passes, role changes or second attempt are
allowed; Menu cannot resume the match during the active procedure. After the
brief decision display, the defending keeper receives the protected restart
and the host may use Menu to resume unless the shot triggers result review. After
certification, Menu starts a new match. Keyboard equivalents are mouse/LMB for
the shot, standard flight keys for the keeper, and Enter for resume or rematch.

Existing stuns and impediments are preserved rather than cleared. The designated
shooter's release and keeper's movement are narrowly allowed during the protected
procedure; the normal effects apply again when play resumes. These controls do
not imply that every penalty severity or all Bloodbroom rules are implemented.

## Windows input backend

The project enables **GameInputWindows** and selects **GameInput alone** as its
preferred controller API. Its GameInput dependency is enabled by the plugin.
`XInputDevice` stays enabled in the project so a future explicit fallback can
select it, but it does not receive gamepad input under the default preference.
UE 5.8 marks GameInputWindows beta and the preferred-API selector experimental.

`DevelopmentHarness/Config/DefaultInput.ini` contains:

```ini
[/Script/Engine.InputSettings]
bEnablePreferredInputAPIPreferences=True
DefaultPreferredInputAPIList=GameInput

[GameInputPlatformSettings_Windows GameInputPlatformSettings]
bProcessGamepad=True
bProcessController=False
bProcessRawInput=False
bProcessKeyboard=False
bProcessMouse=False
```

`DefaultPreferredInputAPIList` is a scalar string of allowed API names, not an
array or an ordered fallback list. Listing `GameInput,XInput` would enable both
and risk duplicate events. The Windows platform settings explicitly enable the
standard gamepad processor; desktop defaults otherwise disable it. Generic/raw
controller processors remain disabled, and Windows retains its ordinary
keyboard/mouse path. An editor `PreferredInputAPIOverride` or saved
`[GamepadAPIPreference] PreferredAPI` takes precedence over the project default;
backend verification must inspect the effective choice.

`DevelopmentHarness/Config/DefaultEngine.ini` also contains:

```ini
[GameInput]
IncludeRedistFiles=True
```

This directs Unreal's Windows packaging code to include
`Engine/Extras/Redist/en-us/GameInputRedist.msi` and mark the packaged bootstrap
for its prerequisite handling. The installed engine bundles the header and
`GameInput.lib`; its minimum runtime is **3.1.26100.6879**. This machine's
`System32/GameInputRedist.dll` meets that version, and the redist service was
running at inspection. This change does not run an installer or alter Windows.
Other PCs still need the runtime; including its installer is not evidence that
it has been installed on those PCs. See [Microsoft's redistribution guidance](https://learn.microsoft.com/en-us/xbox/gdk/docs/features/common/input/overviews/input-nuget?view=gdk-2604).

The installed GameInput runtime includes standard gamepad mappings labeled PS4
Controller and PS5 Controller. This makes native PlayStation support plausible
without the separate WinDualShock plugin's unavailable LibScePad dependencies.
It does not establish compatibility for every controller revision, connection
transport, touchpad, motion sensor or advanced haptic feature. GameInput maps
supported devices into the same Unreal gamepad keys used by this layout.
[Microsoft documents how device mappings determine available interfaces](https://learn.microsoft.com/en-us/gaming/gdk/docs/features/common/input/hardware/input-hardware-interfaces?view=gdk-2510).

If GameInput cannot initialize, keyboard and mouse remain available; there is
**no automatic XInput fallback** in this configuration. A deliberate fallback
would select only `XInput` and restart the application. Neither real USB nor
Bluetooth input, hotplug/reconnection, or absence of hardware-level duplicate
events has been verified by this configuration change. Editor and packaged
startup logs and physical device checks remain separate evidence.

## Validation status

The 2026-09-14 source adds an eighteenth controller case: D-pad Right must
select Serious during a real conduct review without applying a penalty,
starting a shot, changing the score or selecting another spell. The test then
chooses Moderate and exercises the existing separate Menu confirmation. This
eighteen-case suite passed on 2026-09-14 with zero failures or skipped cases.
The preserved receipt is `.local/penalty-validation-solo-20260914-141926/02-native-controller-test-results.json`.
This run precedes the final result-message-only patch; the dated 17-case evidence
and totals below remain historical and do not include the new case.

On 2026-09-12, **17 controller checks passed in 14.172 seconds**, with zero failed
and zero not run, under `5.8.1-56057345+++UE5+Release-5.8`. The receipt is
`.local/native-controller-test-results.json`, produced by
`Tools/test_native_controller.py` in the owned `BB_Regulation` PIE world. It
records the loaded native DLL's size and timestamp.

These checks inject simulated gamepad events through
`FInputKeyEventArgs::CreateSimulated`, `PlayerController::InputKey` and ordinary
`PlayerInput` bindings. Native controller ticks remain enabled. The fixture
arranges temporary PIE transforms, component ticks and world time; it does not
write gameplay actions, effects, custody or penalties directly. Axis transitions
use separate frames and releases are observed, avoiding same-frame accumulation
of a positive sample and its zero release.

The passing cases cover rejected invalid input, contextual roster/team/variant
controls, role and spell selection, match start/pause/resume, the stick deadzone,
partial-speed flight, strafe and vertical flight, time-scaled aiming and upward
pitch. They also observe actual spell damage, Protego, ball pickup/release, an
explicit referee choice followed by separate confirmation, and a possession
award remaining queued until its real restart. The shared engine flush clears
axes, catch input and ghost flight. Cleanup records restored time dilation and
an owned EndPlay request; this receipt does not independently assert completed
teardown.

The milestone total is **229 passing checks: the existing 212 wandplay/rules
checks plus these 17 controller checks**, comprising 130 portable C++ cases and
99 native Unreal checks. The current gameplay (35), regulation spells (17),
Bloodbroom (3), general networking (17) and spell networking (10) receipts also
passed with no failures or skipped cases; their paths and scope are listed in
[wandplay validation](native-wandplay-validation.md). These are separate bounded
runs with overlapping coverage. The final controller run followed the neutral
latch's processed-deadzone correction; this total does not claim one identical
binary across every run or 229 distinct features.

Separately, `.local/controller-backend-startup.json` records successful editor
creation of `IGameInput`, detection of runtime `3.1.26100.6879`, and registration
of the gamepad connection callback. This proves backend startup, while the
simulated tests prove the Unreal input and gameplay bindings.

Standalone package `Development-20260912-134800-592` completed in 60.19 seconds
with AutomationTool exit code zero. Its actual shortcut launch displayed a fresh
practice lobby. `.local/controller-packaged-backend-startup.json` records
successful packaged `IGameInput` initialization using runtime
`3.1.26100.6879` and the gamepad callback. The package contains
`Windows/Engine/Extras/Redist/en-us/GameInputRedist.msi`.
After the user clicked Allow on the Windows network-access prompt, ordinary
keyboard input verified Scout selection, spellbook opening/closing, match start,
Protego, Basic Cast, and stoppage/resume in this package. The shield kept the
reticle clear and the cast originated at the visible wand tip. CPU scoring
continued. Alt+F4 closed the game normally, with a clean exit in its log.
`.local/controller-packaged-smoke.json` records the observations and limits.
This manual smoke check adds no cases to the 229 automated-check total.

In a subsequent physical check on 2026-09-12, Windows detected the user's Sony
DualSense (VID `054c`, PID `0ce6`) over USB. The same packaged build registered
it through GameInput as a gamepad on device 1, platform user 0. The user confirmed
that pressing Triangle opened the spellbook. This is actual hardware button
delivery, separate from the simulated checks above; the local receipt is
`.local/dualsense-hardware-playtest.json`.

The remaining USB flight/button checks and Bluetooth pairing/input are pending.
Hardware disconnect/reconnect, focus transitions, rumble, device-specific glyphs
and remote gamepad ownership/replication remain unverified. Exercising the shared
flush does not simulate an actual hardware disconnect.

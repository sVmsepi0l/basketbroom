# Basketbroom multiplayer implementation findings

Inspected and exercised in UE 5.8.1. The native runtime in `DevelopmentHarness/Source/BasketbroomRuntime` passed all 17 same-process listen-server/client checks on 2026/09/12, including client flight, pickup, and throw replication. Two separate packaged processes also passed physical loopback checks for role selection, host authority, shared result/rematch, matching stoppage state and graceful client departure. These are distinct, bounded checks; remote-machine play, latency, full regulation matches, and Hogwarts Legacy multiplayer remain unverified. The retained training mode is local gameplay.

> **Roof amendment — 2026/09/14:** The current standalone runtime uses the [closed pyramid net](pyramid-net.md) in both modes. The dated Crown-based admission/departure and earlier networking evidence below is historical and is not proof of the replacement roof or its behavior under latency.

## What the installed authoring API supports

`Tools/net_graph.py` provides checked helpers for replicated Blueprint members, RepNotify function graphs, and Actor replication defaults. It does not modify the existing game assets on import. Python remains an authoring dependency, never a packaged runtime dependency.

`BlueprintEditorLibrary.set_blueprint_variable_replication` accepts `BlueprintVariableReplication.REPLICATED` and `REP_NOTIFY`. The implementation sets the Blueprint variable flags and automatically creates `OnRep_<VariableName>` for RepNotify. The helper checks the readback and graph creation. Existing local functions can author the OnRep presentation through `bp_graph.Graph`.

`Actor.bReplicates`, `bReplicateMovement`, `bAlwaysRelevant`, and `bOnlyRelevantToOwner` are public editable defaults on the generated class default object. The helper compiles, writes those defaults, and checks in-memory readback. Disk reload and multi-process tests are still required before those settings count as validated behavior. Replicating transforms alone does not add client movement prediction or client-to-server control to DefaultPawn.

Example authoring sequence for a new, separate UE5 network-state Blueprint:

```python
import unreal

from bp_graph import Graph, create_blueprint
from net_graph import replicated_member, configure_actor_replication

bp = create_blueprint('/Basketbroom/Network/BP_BBNetState', unreal.GameStateBase)
g = Graph(bp)
replicated_member(g, 'TealScore', 'int', 0, notify=True)
replicated_member(g, 'CopperScore', 'int', 0, notify=True)
replicated_member(g, 'MatchPhase', 'int', 0, notify=True)
configure_actor_replication(bp, always_relevant=True, save=True)
```

This snippet configures metadata only. A server must still own the rule simulation and score writes, and clients must render state from their own replicated GameState.

## RPC authoring boundary

The installed public Python API can create `K2Node_CustomEvent`, but it cannot complete an arbitrary reliable server event with typed parameters:

- `UK2Node_Event::FunctionFlags` is a plain `UPROPERTY()` without Edit or BlueprintVisible access. `set_editor_property('FunctionFlags', ...)` is rejected by `PropertyAccessUtil::CanSetPropertyValue` because the property is protected from editor scripting. Snake-case aliases do not change that access rule.
- `UK2Node_EditablePinBase::UserDefinedPins` is a native array of shared pin descriptors. `CreateUserDefinedPin` is a C++ method without UFUNCTION exposure. `BlueprintGraphEditor.add_graph_input_parameter` accepts function-entry graphs; it does not add custom-event parameters.
- `BlueprintGraphEditor` exposes pure/const/public/protected/private/exec function controls, but no server/client/multicast/reliability setter.

The Blueprint editor itself supports the Replicates and Reliable controls through its Details customization. A small native editor module can expose the same operations as UFUNCTION helpers. A native gameplay base class can instead declare typed RPCs and expose validated Blueprint extension events. Both are legitimate routes; there is no implemented RPC helper in `net_graph.py` pretending to overcome the API boundary. [Epic RPC documentation](https://dev.epicgames.com/documentation/unreal-engine/remote-procedure-calls-in-unreal-engine).

For a native editor helper, match the installed editor's behavior: validate graph ownership and event-name uniqueness, modify the Blueprint/node transactionally, preserve unrelated function flags, set one network direction plus `FUNC_Net`, set or clear `FUNC_NetReliable`, create typed output parameters, reconstruct the node, and mark the Blueprint structurally modified. Reject overriding an inherited RPC with conflicting flags. Compile and inspect the resulting generated UFunction before saving.

The installed flags are `FUNC_Net=0x40`, `FUNC_NetReliable=0x80`, `FUNC_NetServer=0x00200000`, `FUNC_NetClient=0x01000000`, and `FUNC_NetMulticast=0x4000`. Their numeric values explain the engine path; writing raw flags through unsupported property access is not the implementation plan.

## Server authority and flight

Use a separate network broom based on `ACharacter` with `CharacterMovement` in `MOVE_Flying`. Preserve the current camera and broom visuals as components. Start with stock flying movement, configured acceleration/deceleration, collision capsule, and server-defined movement limits. The owning client supplies movement input to CharacterMovement. Its native saved-move protocol predicts locally, sends moves through the Character RPC path, applies server correction, replays unacknowledged input, and smooths remote proxies. The installed CharacterMovement header documents this path around `ServerMovePacked` and `ClientAdjustPosition`; its `PhysFlying` implements the flying mode. [Epic character movement documentation](https://dev.epicgames.com/documentation/unreal-engine/understanding-networked-movement-in-the-character-movement-component-for-unreal-engine?lang=en-US).

Do not port the training manager's per-frame player `SetActorLocation` clamp into the network player. Such teleports are outside ordinary predicted movement. Enforce the arena through movement collision/server constraints and issue explicit authoritative corrections for actual out-of-bounds resets. Custom boost, stun, or broom movement states must be represented in the saved-move protocol if they change predicted movement; use a native CharacterMovement extension when necessary.

Separate responsibilities as follows:

- **GameMode, server only:** registration, regulation phase transitions, start/restart, team/role assignment, substitutions, authoritative rule decisions, win conditions, and reconnect policy.
- **GameState, replicated:** phase, team scores, synchronized phase end time, chase-ball state, possession summaries, penalties, and enough state for late joiners. Replicate a server time/end timestamp rather than trusting each client's independent countdown.
- **PlayerState, replicated:** stable player identity, team, role, and match statistics. Do not reuse Actor's inherited networking `Role`; use the already adopted `PlayerRole` name.
- **Owned Character or PlayerController:** sparse client requests such as pickup, throw, ready, and substitution. The server resolves the requester from ownership and validates phase, assigned role, distance, line of sight, current holder, cooldown, and bounded aim data. Clients never submit a score or accepted catch result.
- **Ball actors, server authority:** free/held/released transitions, trajectory, goal crossing, catches, and respawns. Replicate holder identity and authoritative ball state. Render smooth client motion between updates; do not run independent score logic on clients.
- **Bots, server only:** existing pursuit/decision work moves behind authority checks. Clients receive actor movement and presentation state.
- **HUD/audio/VFX, local presentation:** read the local player's PlayerState and replicated GameState. Use transient cosmetic events only for effects; persistent score/possession state must survive missed packets and late join.

A client must send a Server RPC through an actor it owns; an unowned ball or match actor is not the request entry point. Use reliable RPCs for low-frequency discrete requests and avoid per-tick reliable traffic. Server validation and idempotency still matter even when transport is reliable. [Actor ownership and connection](https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-owner-and-owning-connection-in-unreal-engine), [RPC reliability](https://dev.epicgames.com/documentation/unreal-engine/remote-procedure-calls-in-unreal-engine).

## Toolchain requirements on this machine

The active `.uproject` includes the compiled `BasketbroomRuntime` module. Native Editor and Win64 Development game compilation and packaging succeeded with Visual Studio 2026, MSVC **14.51.36257**, Windows SDK **26100**, and the .NET Framework **4.8 SDK**. The missing-toolchain finding from the initial content-only investigation is resolved. Unreal also includes .NET SDK **10.0.203** under `Engine/Binaries/ThirdParty/DotNet/10.0/win-x64`.

Install a supported Visual Studio C++ toolchain with Desktop development with C++, Game development with C++, x64/x86 MSVC tools, and a Windows 11 SDK. Epic's UE 5.8 guide lists Visual Studio 2022 17.14+ or Visual Studio 2026 18.0+ and recommends VS 2026 for general development. [Epic Visual Studio setup](https://dev.epicgames.com/documentation/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine).

For another workstation, the installed `Engine/Config/Windows/Windows_SDK.json` distinguishes preferred compiler families from allowed versions. The successfully used 14.51.36257 is outside its preferred families and outside its banned ranges:

- Preferred MSVC families: 14.50 or 14.44. Select **14.50.35723+** or **14.44.35211+** within those families; earlier patches are explicitly banned.
- The local configuration also bans MSVC 14.39 and 14.40–14.43. Do not select a compiler just because it is newer than the nominal minimum 14.38.33130.
- Its main Windows SDK is 10.0.22621.0; use 22621 or a supported newer SDK such as 26100. The local lower admission threshold is 19041, but that is not the preferred installation target.

The implemented standalone runtime contains the network Character, validated server requests, native GameMode/GameState, roster ownership, and authoritative ball rules. Use `Build-Native.ps1` to compile the Editor target, reopen the editor to load the DLL, then use `Package.ps1` to build/cook the game. For a standalone dedicated-server target, first confirm availability of the required server binaries; Epic's documented dedicated-server setup uses a source engine build. [Epic dedicated server setup](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-dedicated-servers-in-unreal-engine).

The passing results below use the compiled module, with connection smoke also running the packaged native executable.

## Native rider implementation

`BBRiderCharacter.h/.cpp` now implement the agreed native route. `ABBRiderCharacter` uses `MOVE_Flying`, a 2100 cm/s maximum speed, 3600 cm/s² acceleration, a capsule, a local camera/cockpit, and an animated stock Quinn body with original broom/equipment attached to the Character mesh for remote movement smoothing. The authored seated loop and team materials are documented in `skeletal-rider-art.md`. `UBBFlyingMovementComponent` preserves CharacterMovement's native protocol and constrains maximum speed/acceleration while the replicated stun is active. Its `PhysFlying` also enforces the end/side bounds and the [four sloping pyramid roof faces](pyramid-net.md) on both authority and predicted owner, using whole-capsule support and a controlled rebound. The provisional 207-foot height is the central apex, not a flat ceiling; the 138-foot eave plane has no horizontal barrier. Physical lower and roof nets collide normally. Authoritative ball flight uses the matching analytic roof planes; held visuals use the same containment. The Character owns the server's stun countdown.

The rider replicates `TeamIndex`, `Position`, `RosterIndex`, `bInteractHeld`, and `StunRemaining`. Team changes refresh visible uniform materials. Key bindings need no project input mapping: WASD, Space/Ctrl, mouse, E press/release, left click, 1–6, T, Enter, P, and Tab. P requests an official stoppage; Tab only changes local help visibility.

Owned reliable RPCs update the held interaction or forward discrete requests to `ABBMatchState::HandleAction`: 0 pickup, 1 throw, 2 position, 3 team, 4 ready, 5 official stoppage. The rider rejects non-finite/non-unit aim, invalid action/role/team ranges, stunned pickup/throw, and excessively rapid actions; MatchState enforces semantic rules and resolves continuous held capture on the server. Match start/stoppage requests are restricted to the local host, or the first connected participant on a dedicated server. Interaction stops are never throttled. Native builds and bounded interactive checks across two packaged processes pass; manual ball contests and the adverse-network scenarios below still need validation.

Two development-only Blueprint calls submit input through these same request paths: `DevelopmentRequestAction` and `DevelopmentSetInteraction`. Both require a locally controlled PlayerController in a PIE world and reject Shipping builds. Their boolean result means the input entered a bounded 32-entry FIFO, never that the server accepted the gameplay result. Native Rider Tick dispatches the FIFO in order through the ordinary input/RPC methods. This deferred dispatch is necessary because Python's `FEditorScriptExecutionGuard` forces Actor RPC callspace to local execution during reflected calls (`PyUtil.cpp:644`, `Actor.cpp:5469`); the test must leave that guard before sending network requests. Keyboard input remains immediate. A held-interaction fixture must explicitly clear its hold during cleanup, and unpossession/restart clears queued input. No rules or score setter is exposed by this bridge.

The current closed roof also passed dedicated two-world rebound checks in both modes; see [pyramid-net validation](pyramid-net-validation.md) for evidence and limits.

## Remaining runtime proof

1. Host plus one separate client: each possesses a different Character, both move, and each sees the other's movement. Repeat as separate packaged processes rather than relying only on one-process PIE.
2. Simultaneous pickup requests for one ball: exactly one server-approved holder; rejection arrives without client-side score or possession divergence.
3. Client throw and legal goal: server assigns the score once, all clients agree, and a late joiner receives the current score/clock/holder state.
4. Invalid or repeated requests: wrong player, excessive distance, disallowed role, stale possession, phase mismatch, and cooldown violations leave authoritative state unchanged.
5. Network emulation: latency, packet loss, disconnection, rejoin, and possession changes while updates are in flight. Check corrections and ball interpolation, not only final scores.
6. Expand to 16 participant slots and the complete regulation rules only after the two-player authoritative loop passes. Verify CPU substitution and match-end behavior on the server and every client.

Passing the existing single-player, bot, or native-flight checks is not evidence of network correctness.

## Same-process local network validation

`Tools/test_native_network.py` runs 17 asynchronous checks. Run it through the UE5 editor bridge after compiling the native module and staging `BB_Regulation`, with all earlier PIE tests stopped. Results go to `.local/native-network-test-results.json`; `--list` outside Unreal only prints the plan. A `started` bridge response is not a pass: wait for the report's final status.

The installed UE5.8 binary does not generate a Python wrapper for the net-mode enum; even reading `PlayNetMode` fails conversion. Record the current **Play Net Mode** in the editor UI, select **Play As Listen Server**, and pass `{"settings_already_configured": true}` to the bridge request. Restore that UI selection afterward. The suite leaves that enum untouched and reports the external restoration requirement. `Tools/probe_native_play_settings.py` provides a read-only diagnosis of the installed API.

The suite temporarily changes the three publicly editable, readable `LevelEditorPlaySettings` properties `RunUnderOneProcess=true`, `PlayNumberOfClients=2`, and `bLaunchSeparateServer=false`. It keeps them stable through asynchronous startup and restores them during cleanup, including failed runs. `EditorLevelLibrary.get_pie_worlds` enumerates actual PIE world contexts, with startup observations written to the report. The test requires two distinct worlds, exactly one authoritative GameState, two distinct human PlayerState IDs, and matching sixteen-slot rosters. It never changes protected engine or gameplay fields.

Owned client input goes through the native development hooks and ordinary reliable server RPCs. Checks observe a replicated pregame role change and held interaction, rejection of client start/pause requests, accepted host start/stoppage, and matching phases and clocks. A server-only free-ball fixture launches the Quaffle through a large hoop; ordinary native flight and scoring must award exactly 13 points and replicate that result once. The corresponding fixture call on the client must fail. Client `AddMovementInput` then travels through CharacterMovement saved moves: the latest observed server displacement was 1,236.07 cm, with a 94.94 cm client/server difference at the sampled frame (the check requires less than 150 cm). The fixture then waits for movement to settle. Client pickup produces matching possession in both worlds, and client throw releases that possession with an observed 4,407.29 cm/s flight velocity in both worlds. These measurements do not establish precise reconciliation or correction under latency. CPU movement and other equipment are isolated only inside the disposable server PIE world to make these cases deterministic. Cleanup ends both worlds and verifies restoration of the settings controlled by the script; the operator restores the net-mode UI selection separately.

This is **local networking inside one editor process**, with a real client/server authority boundary. All 17 checks passed in 9.625 seconds on 2026/09/12 after the combined art and admission/disconnect build. The corrected pickup fixture enables native ball Tick for 0.4 seconds so the 0.25-second kickoff cooldown expires normally; frozen equipment had kept that grace period active indefinitely. That failure was in fixture timing and did not establish a replication defect. This suite does not establish LAN/internet, remote-machine, movement prediction or reconciliation under latency, packet-loss, late-join, 16-human, or Hogwarts Legacy multiplayer support. Keep the adverse-network scenarios above as remaining validation. The separate eleven passing native audio checks establish local event/component behavior; they do not validate remote audio timing or packet-loss behavior.

## Admission and departure evidence

New humans receive a balanced, unrestricted CPU slot. The admission policy
excludes pending/restorative penalties, removal, ejection, Donnybrook exclusion
and physical stun. If every available slot is restricted, the newcomer becomes
a spectator. Historical sanctions and the opponent's remedies remain on their
original slots. Ten portable policy cases pass through actual rule transitions.

`Tools/test_native_admission.py` passed **7/7 in 30.984 seconds** on 2026/09/12.
Public local-player creation/removal and actual Crown/Bludger interactions
verified unique CPU refill, clean-slot selection, allowed role changes, retention
and eventual restoration of the original Crown remedy, and spectator-only
admission when all remaining CPU slots were unavailable. The owned PIE world,
its time dilation and temporary local players were cleaned up.

`Tools/test_native_disconnect.py` passed **7/7 in 6.110 seconds** on the same
combined build. A real local client changed its role (slot 12 to 9), incurred a
Crown foul through a released Quark, picked up a second Quark and executed
Unreal's ordinary `disconnect`. The server retained sixteen unique slots,
replaced the departing human with a CPU, released the held ball and preserved
the earlier foul/remedy and scores. The remaining host then acquired the
released ball through the actual rules/input path, proving core custody was
cleared as well as its replicated visual holder. GameMode remembers the current
slot through swaps because Unreal can destroy/unpossess the pawn before Logout.

Reports are `.local/native-admission-test-results.json`,
`.local/native-disconnect-test-results.json` and
`.local/native-admission-rules/results.json`. These are local lifecycle checks;
they do not establish persistent account identity, remote-machine reconnection,
abrupt transport loss/timeout, host migration or Hogwarts Legacy multiplayer.

## Packaged connection and launcher

`Tools/test_packaged_network.ps1` starts two hidden native Development game processes with null rendering and audio, verifies the server actually binds only `127.0.0.1`, then requires server connection acceptance, a uniquely tagged join, successful join, client welcome, and completed regulation-map loading. It stops only its own processes after checking executable path and creation time. The 2026/09/12 combined native package `Development-20260912-092259-936` passed in 24.004 seconds with no logged engine/network errors; evidence is under `.local/packaged-network/20260912-092514-172-15e37b37/`. Both owned processes were stopped successfully. This automated smoke covers connection and travel; the subsequent interactive run has its own evidence below.

`Multiplayer.ps1` now prefers the latest native package, with `-EditorGame` available for development. `-Mode LocalTest -Practice` opens two visible windows on loopback and waits for the host's listening log before starting the client. `-Mode Host` and `-Mode Join -Address <host>` support direct addresses; remote connections remain to be tested. `Local-Multiplayer.cmd` opens the local practice pair. The host presses Enter after players choose positions.

## Physical two-process gameplay evidence

Package **`Development-20260912-093008-251`** was exercised through two visible
native processes on September 12. The local practice run is
`.local/Multiplayer/20260912-093603-884`, using loopback port **18780**.
`.local/packaged-multiplayer-controls-20260912.json` records the physical keyboard
and visible UI observations, with no gameplay-state injection:

- Client **5** selected Copper/Hurleyback; the host saw the replicated role
  message. Client **Enter** did not start the lobby. Host **Enter** did, and the
  client received LIVE clock, equipment and score state. Client **P** did not
  stop live play.
- Both views reached the same certified Copper win, **Teal 113–Copper 417**, in
  quarter one at **01:45**. Client **Enter** did not rematch. Host **Enter**
  started a live rematch; the host view showed **0–0, 03:00, LIVE**. The client's
  initial reset frame was not directly observed.
- Host **P** then stopped at **02:54**, **Teal 87–Copper 0**. The client matched
  the stoppage status, clock and scores, and retained Copper/Hurleyback.
- Client **Alt+F4** disconnected cleanly. The host still showed **02:54, 87–0**;
  host **Enter** resumed play, reaching **02:47, Teal 87–Copper 69**, before the
  host also exited with **Alt+F4**.

Both logs contain normal viewport-close exit requests, object-system shutdown
and final exit lines. The host logged connection cleanup when the client left.
Final exits were **09:43:14 client** and **09:43:44 host** local time. The log
review found no engine/network errors or network warnings. Logs corroborate
connection/process lifecycle; displayed role, authority and score observations
come from the physical UI pass.

This establishes the listed interactive behavior across two real local processes.
It does not establish manual pickup/throw/catch, a held-ball departure in the
packaged run, remote-machine connectivity, adverse-network behavior, full-length
regulation, sixteen human participants or sustained performance. Held-ball
departure and remedy preservation remain separately scoped PIE evidence above.

## Hogwarts Legacy boundary

The installed Hogwarts Legacy Creator Kit uses UE 4.27.2 and its supported mod route rejects runtime DLLs. The UE5 native module and UE5 `.uasset` files cannot simply be shipped through that content-mod pipeline. The existing Creator Kit findings describe a separate content/Blueprint port and map-entry integration. Shared rules/data and original art can inform both builds; transport code, engine assets, and gameplay integration require separate implementations. Nothing in this inspection establishes supported multiplayer integration for Hogwarts Legacy. See [creator-kit-findings.md](creator-kit-findings.md).

## Local source evidence

- `Engine/Source/Editor/BlueprintEditorLibrary/Public/BlueprintEditorLibrary.h`: `EBlueprintVariableReplication`, `GetBlueprintVariableReplication`, `SetBlueprintVariableReplication`.
- `Engine/Source/Editor/BlueprintEditorLibrary/Private/BlueprintEditorLibrary.cpp`: replication implementation at lines 1659–1756.
- `Engine/Source/Editor/BlueprintGraph/Classes/K2Node_Event.h`: `FunctionFlags` declaration; `K2Node_EditablePinBase.h`: custom parameter storage and native pin-creation API.
- `Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyAccessUtil.cpp`: editor property access guard around line 724.
- `Engine/Source/Editor/Kismet/Private/BlueprintDetailsCustomization.cpp`: custom-event replication UI and reliable flag mutation around lines 4659 and 6251.
- `Engine/Source/Runtime/Engine/Classes/GameFramework/CharacterMovementComponent.h`: predicted movement, saved moves, server RPC, correction, and replay contract around lines 2384–2567.
- `Engine/Source/Runtime/Engine/Private/FloatingPawnMovement.cpp`: local movement loop without CharacterMovement's client move protocol.
- `Engine/Config/Windows/Windows_SDK.json`: installed compiler/SDK preferences and banned patch ranges.

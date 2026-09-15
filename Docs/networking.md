# basketbroom multiplayer implementation findings

inspected and exercised in ue 5.8.1. the native runtime in `DevelopmentHarness/Source/BasketbroomRuntime` passed all 17 same-process listen-server/client checks on 2026/09/12, including client flight, pickup, and throw replication. two separate packaged processes also passed physical loopback checks for role selection, host authority, shared result/rematch, matching stoppage state and graceful client departure. these are distinct, bounded checks; remote-machine play, latency, full regulation matches, and hogwarts legacy multiplayer remain unverified. the retained training mode is local gameplay.

> **roof amendment — 2026/09/14:** the current standalone runtime uses the [closed pyramid net](pyramid-net.md) in both modes. the dated crown-based admission/departure and earlier networking evidence below is historical and is not proof of the replacement roof or its behavior under latency.

## what the installed authoring api supports

`Tools/net_graph.py` provides checked helpers for replicated blueprint members, repnotify function graphs, and actor replication defaults. it does not modify the existing game assets on import. python remains an authoring dependency, never a packaged runtime dependency.

`BlueprintEditorLibrary.set_blueprint_variable_replication` accepts `BlueprintVariableReplication.REPLICATED` and `REP_NOTIFY`. the implementation sets the blueprint variable flags and automatically creates `onrep_<variablename>` for RepNotify. the helper checks the readback and graph creation. existing local functions can author the onrep presentation through `bp_graph.Graph`.

`Actor.bReplicates`, `breplicatemovement`, `balwaysrelevant`, and `bonlyrelevanttoowner` are public editable defaults on the generated class default object. the helper compiles, writes those defaults, and checks in-memory readback. disk reload and multi-process tests are still required before those settings count as validated behavior. replicating transforms alone does not add client movement prediction or client-to-server control to DefaultPawn.

example authoring sequence for a new, separate ue5 network-state Blueprint:

```python
import unreal

from bp_graph import graph, create_blueprint
from net_graph import replicated_member, configure_actor_replication

bp = create_blueprint('/Basketbroom/Network/BP_BBNetState', unreal.GameStateBase)
g = graph(bp)
replicated_member(g, 'tealscore', 'int', 0, notify=true)
replicated_member(g, 'copperscore', 'int', 0, notify=true)
replicated_member(g, 'matchphase', 'int', 0, notify=true)
configure_actor_replication(bp, always_relevant=true, save=true)
```

this snippet configures metadata only. a server must still own the rule simulation and score writes, and clients must render state from their own replicated GameState.

## rpc authoring boundary

the installed public python api can create `k2node_customevent`, but it cannot complete an arbitrary reliable server event with typed parameters:

- `UK2Node_Event::FunctionFlags` is a plain `uproperty()` without edit or blueprintvisible access. `set_editor_property('functionflags', ...)` is rejected by `PropertyAccessUtil::CanSetPropertyValue` because the property is protected from editor scripting. snake-case aliases do not change that access rule.
- `UK2Node_EditablePinBase::UserDefinedPins` is a native array of shared pin descriptors. `createuserdefinedpin` is a c++ method without ufunction exposure. `BlueprintGraphEditor.add_graph_input_parameter` accepts function-entry graphs; it does not add custom-event parameters.
- `blueprintgrapheditor` exposes pure/const/public/protected/private/exec function controls, but no server/client/multicast/reliability setter.

the blueprint editor itself supports the replicates and reliable controls through its details customization. a small native editor module can expose the same operations as ufunction helpers. a native gameplay base class can instead declare typed rpcs and expose validated blueprint extension events. both are legitimate routes; there is no implemented rpc helper in `net_graph.py` pretending to overcome the api boundary. [epic rpc documentation](https://dev.epicgames.com/documentation/unreal-engine/remote-procedure-calls-in-unreal-engine).

for a native editor helper, match the installed editor's behavior: validate graph ownership and event-name uniqueness, modify the Blueprint/node transactionally, preserve unrelated function flags, set one network direction plus `func_net`, set or clear `func_netreliable`, create typed output parameters, reconstruct the node, and mark the blueprint structurally modified. reject overriding an inherited rpc with conflicting flags. compile and inspect the resulting generated ufunction before saving.

the installed flags are `func_net=0x40`, `func_netreliable=0x80`, `func_netserver=0x00200000`, `func_netclient=0x01000000`, and `FUNC_NetMulticast=0x4000`. their numeric values explain the engine path; writing raw flags through unsupported property access is not the implementation plan.

## server authority and flight

use a separate network broom based on `acharacter` with `charactermovement` in `MOVE_Flying`. preserve the current camera and broom visuals as components. start with stock flying movement, configured acceleration/deceleration, collision capsule, and server-defined movement limits. the owning client supplies movement input to CharacterMovement. its native saved-move protocol predicts locally, sends moves through the character rpc path, applies server correction, replays unacknowledged input, and smooths remote proxies. the installed charactermovement header documents this path around `servermovepacked` and `clientadjustposition`; its `physflying` implements the flying mode. [epic character movement documentation](https://dev.epicgames.com/documentation/unreal-engine/understanding-networked-movement-in-the-character-movement-component-for-unreal-engine?lang=en-US).

do not port the training manager's per-frame player `setactorlocation` clamp into the network player. such teleports are outside ordinary predicted movement. enforce the arena through movement collision/server constraints and issue explicit authoritative corrections for actual out-of-bounds resets. custom boost, stun, or broom movement states must be represented in the saved-move protocol if they change predicted movement; use a native charactermovement extension when necessary.

separate responsibilities as follows:

- **gamemode, server only:** registration, regulation phase transitions, start/restart, team/role assignment, substitutions, authoritative rule decisions, win conditions, and reconnect policy.
- **gamestate, replicated:** phase, team scores, synchronized phase end time, chase-ball state, possession summaries, penalties, and enough state for late joiners. replicate a server time/end timestamp rather than trusting each client's independent countdown.
- **playerstate, replicated:** stable player identity, team, role, and match statistics. do not reuse actor's inherited networking `role`; use the already adopted `playerrole` name.
- **owned character or PlayerController:** sparse client requests such as pickup, throw, ready, and substitution. the server resolves the requester from ownership and validates phase, assigned role, distance, line of sight, current holder, cooldown, and bounded aim data. clients never submit a score or accepted catch result.
- **ball actors, server authority:** free/held/released transitions, trajectory, goal crossing, catches, and respawns. replicate holder identity and authoritative ball state. render smooth client motion between updates; do not run independent score logic on clients.
- **bots, server only:** existing pursuit/decision work moves behind authority checks. clients receive actor movement and presentation state.
- **HUD/audio/VFX, local presentation:** read the local player's playerstate and replicated GameState. use transient cosmetic events only for effects; persistent score/possession state must survive missed packets and late join.

a client must send a server rpc through an actor it owns; an unowned ball or match actor is not the request entry point. use reliable rpcs for low-frequency discrete requests and avoid per-tick reliable traffic. server validation and idempotency still matter even when transport is reliable. [actor ownership and connection](https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-owner-and-owning-connection-in-unreal-engine), [rpc reliability](https://dev.epicgames.com/documentation/unreal-engine/remote-procedure-calls-in-unreal-engine).

## toolchain requirements on this machine

the active `.uproject` includes the compiled `basketbroomruntime` module. native editor and win64 development game compilation and packaging succeeded with visual studio 2026, msvc **14.51.36257**, windows sdk **26100**, and the .NET framework **4.8 SDK**. the missing-toolchain finding from the initial content-only investigation is resolved. unreal also includes .NET sdk **10.0.203** under `Engine/Binaries/ThirdParty/DotNet/10.0/win-x64`.

install a supported visual studio c++ toolchain with desktop development with c++, game development with c++, x64/x86 msvc tools, and a windows 11 SDK. epic's ue 5.8 guide lists visual studio 2022 17.14+ or visual studio 2026 18.0+ and recommends vs 2026 for general development. [epic visual studio setup](https://dev.epicgames.com/documentation/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine).

for another workstation, the installed `Engine/Config/Windows/Windows_SDK.json` distinguishes preferred compiler families from allowed versions. the successfully used 14.51.36257 is outside its preferred families and outside its banned ranges:

- preferred msvc families: 14.50 or 14.44. select **14.50.35723+** or **14.44.35211+** within those families; earlier patches are explicitly banned.
- the local configuration also bans msvc 14.39 and 14.40–14.43. do not select a compiler just because it is newer than the nominal minimum 14.38.33130.
- its main windows sdk is 10.0.22621.0; use 22621 or a supported newer sdk such as 26100. the local lower admission threshold is 19041, but that is not the preferred installation target.

the implemented standalone runtime contains the network character, validated server requests, native GameMode/GameState, roster ownership, and authoritative ball rules. use `Build-Native.ps1` to compile the editor target, reopen the editor to load the dll, then use `Package.ps1` to build/cook the game. for a standalone dedicated-server target, first confirm availability of the required server binaries; epic's documented dedicated-server setup uses a source engine build. [epic dedicated server setup](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-dedicated-servers-in-unreal-engine).

the passing results below use the compiled module, with connection smoke also running the packaged native executable.

## native rider implementation

`BBRiderCharacter.h/.cpp` now implement the agreed native route. `abbridercharacter` uses `move_flying`, a 2100 cm/s maximum speed, 3600 cm/s² acceleration, a capsule, a local camera/cockpit, and an animated stock quinn body with original broom/equipment attached to the character mesh for remote movement smoothing. the authored seated loop and team materials are documented in `skeletal-rider-art.md`. `ubbflyingmovementcomponent` preserves charactermovement's native protocol and constrains maximum speed/acceleration while the replicated stun is active. its `physflying` also enforces the end/side bounds and the [four sloping pyramid roof faces](pyramid-net.md) on both authority and predicted owner, using whole-capsule support and a controlled rebound. the provisional 207-foot height is the central apex, not a flat ceiling; the 138-foot eave plane has no horizontal barrier. physical lower and roof nets collide normally. authoritative ball flight uses the matching analytic roof planes; held visuals use the same containment. the character owns the server's stun countdown.

the rider replicates `teamindex`, `position`, `rosterindex`, `binteractheld`, and `StunRemaining`. team changes refresh visible uniform materials. key bindings need no project input mapping: wasd, Space/Ctrl, mouse, e press/release, left click, 1–6, t, enter, p, and Tab. p requests an official stoppage; tab only changes local help visibility.

owned reliable rpcs update the held interaction or forward discrete requests to `ABBMatchState::HandleAction`: 0 pickup, 1 throw, 2 position, 3 team, 4 ready, 5 official stoppage. the rider rejects non-finite/non-unit aim, invalid action/role/team ranges, stunned pickup/throw, and excessively rapid actions; matchstate enforces semantic rules and resolves continuous held capture on the server. match start/stoppage requests are restricted to the local host, or the first connected participant on a dedicated server. interaction stops are never throttled. native builds and bounded interactive checks across two packaged processes pass; manual ball contests and the adverse-network scenarios below still need validation.

two development-only blueprint calls submit input through these same request paths: `developmentrequestaction` and `DevelopmentSetInteraction`. both require a locally controlled playercontroller in a pie world and reject shipping builds. their boolean result means the input entered a bounded 32-entry fifo, never that the server accepted the gameplay result. native rider tick dispatches the fifo in order through the ordinary input/RPC methods. this deferred dispatch is necessary because python's `feditorscriptexecutionguard` forces actor rpc callspace to local execution during reflected calls (`PyUtil.cpp:644`, `Actor.cpp:5469`); the test must leave that guard before sending network requests. keyboard input remains immediate. a held-interaction fixture must explicitly clear its hold during cleanup, and unpossession/restart clears queued input. no rules or score setter is exposed by this bridge.

the current closed roof also passed dedicated two-world rebound checks in both modes; see [pyramid-net validation](pyramid-net-validation.md) for evidence and limits.

## remaining runtime proof

1. host plus one separate client: each possesses a different character, both move, and each sees the other's movement. repeat as separate packaged processes rather than relying only on one-process PIE.
2. simultaneous pickup requests for one ball: exactly one server-approved holder; rejection arrives without client-side score or possession divergence.
3. client throw and legal goal: server assigns the score once, all clients agree, and a late joiner receives the current score/clock/holder state.
4. invalid or repeated requests: wrong player, excessive distance, disallowed role, stale possession, phase mismatch, and cooldown violations leave authoritative state unchanged.
5. network emulation: latency, packet loss, disconnection, rejoin, and possession changes while updates are in flight. check corrections and ball interpolation, not only final scores.
6. expand to 16 participant slots and the complete regulation rules only after the two-player authoritative loop passes. verify cpu substitution and match-end behavior on the server and every client.

passing the existing single-player, bot, or native-flight checks is not evidence of network correctness.

## same-process local network validation

`Tools/test_native_network.py` runs 17 asynchronous checks. run it through the ue5 editor bridge after compiling the native module and staging `bb_regulation`, with all earlier pie tests stopped. results go to `.local/native-network-test-results.json`; `--list` outside unreal only prints the plan. a `started` bridge response is not a pass: wait for the report's final status.

the installed UE5.8 binary does not generate a python wrapper for the net-mode enum; even reading `playnetmode` fails conversion. record the current **play net mode** in the editor ui, select **play as listen server**, and pass `{"settings_already_configured": true}` to the bridge request. restore that ui selection afterward. the suite leaves that enum untouched and reports the external restoration requirement. `Tools/probe_native_play_settings.py` provides a read-only diagnosis of the installed API.

the suite temporarily changes the three publicly editable, readable `leveleditorplaysettings` properties `rununderoneprocess=true`, `playnumberofclients=2`, and `bLaunchSeparateServer=false`. it keeps them stable through asynchronous startup and restores them during cleanup, including failed runs. `EditorLevelLibrary.get_pie_worlds` enumerates actual pie world contexts, with startup observations written to the report. the test requires two distinct worlds, exactly one authoritative gamestate, two distinct human playerstate ids, and matching sixteen-slot rosters. it never changes protected engine or gameplay fields.

owned client input goes through the native development hooks and ordinary reliable server RPCs. checks observe a replicated pregame role change and held interaction, rejection of client start/pause requests, accepted host start/stoppage, and matching phases and clocks. a server-only free-ball fixture launches the quaffle through a large hoop; ordinary native flight and scoring must award exactly 13 points and replicate that result once. the corresponding fixture call on the client must fail. client `addmovementinput` then travels through charactermovement saved moves: the latest observed server displacement was 1,236.07 cm, with a 94.94 cm client/server difference at the sampled frame (the check requires less than 150 cm). the fixture then waits for movement to settle. client pickup produces matching possession in both worlds, and client throw releases that possession with an observed 4,407.29 cm/s flight velocity in both worlds. these measurements do not establish precise reconciliation or correction under latency. cpu movement and other equipment are isolated only inside the disposable server pie world to make these cases deterministic. cleanup ends both worlds and verifies restoration of the settings controlled by the script; the operator restores the net-mode ui selection separately.

this is **local networking inside one editor process**, with a real client/server authority boundary. all 17 checks passed in 9.625 seconds on 2026/09/12 after the combined art and admission/disconnect build. the corrected pickup fixture enables native ball tick for 0.4 seconds so the 0.25-second kickoff cooldown expires normally; frozen equipment had kept that grace period active indefinitely. that failure was in fixture timing and did not establish a replication defect. this suite does not establish LAN/internet, remote-machine, movement prediction or reconciliation under latency, packet-loss, late-join, 16-human, or hogwarts legacy multiplayer support. keep the adverse-network scenarios above as remaining validation. the separate eleven passing native audio checks establish local event/component behavior; they do not validate remote audio timing or packet-loss behavior.

## admission and departure evidence

new humans receive a balanced, unrestricted cpu slot. the admission policy
excludes pending/restorative penalties, removal, ejection, donnybrook exclusion
and physical stun. if every available slot is restricted, the newcomer becomes
a spectator. historical sanctions and the opponent's remedies remain on their
original slots. ten portable policy cases pass through actual rule transitions.

`Tools/test_native_admission.py` passed **7/7 in 30.984 seconds** on 2026/09/12.
public local-player creation/removal and actual Crown/Bludger interactions
verified unique cpu refill, clean-slot selection, allowed role changes, retention
and eventual restoration of the original crown remedy, and spectator-only
admission when all remaining cpu slots were unavailable. the owned pie world,
its time dilation and temporary local players were cleaned up.

`Tools/test_native_disconnect.py` passed **7/7 in 6.110 seconds** on the same
combined build. a real local client changed its role (slot 12 to 9), incurred a
crown foul through a released quark, picked up a second quark and executed
unreal's ordinary `disconnect`. the server retained sixteen unique slots,
replaced the departing human with a cpu, released the held ball and preserved
the earlier foul/remedy and scores. the remaining host then acquired the
released ball through the actual rules/input path, proving core custody was
cleared as well as its replicated visual holder. gamemode remembers the current
slot through swaps because unreal can destroy/unpossess the pawn before Logout.

reports are `.local/native-admission-test-results.json`,
`.local/native-disconnect-test-results.json` and
`.local/native-admission-rules/results.json`. these are local lifecycle checks;
they do not establish persistent account identity, remote-machine reconnection,
abrupt transport loss/timeout, host migration or hogwarts legacy multiplayer.

## packaged connection and launcher

`Tools/test_packaged_network.ps1` starts two hidden native development game processes with null rendering and audio, verifies the server actually binds only `127.0.0.1`, then requires server connection acceptance, a uniquely tagged join, successful join, client welcome, and completed regulation-map loading. it stops only its own processes after checking executable path and creation time. the 2026/09/12 combined native package `development-20260912-092259-936` passed in 24.004 seconds with no logged engine/network errors; evidence is under `.local/packaged-network/20260912-092514-172-15e37b37/`. both owned processes were stopped successfully. this automated smoke covers connection and travel; the subsequent interactive run has its own evidence below.

`Multiplayer.ps1` now prefers the latest native package, with `-editorgame` available for development. `-mode localtest -practice` opens two visible windows on loopback and waits for the host's listening log before starting the client. `-mode host` and `-mode join -address <host>` support direct addresses; remote connections remain to be tested. `Local-Multiplayer.cmd` opens the local practice pair. the host presses enter after players choose positions.

## physical two-process gameplay evidence

package **`development-20260912-093008-251`** was exercised through two visible
native processes on september 12. the local practice run is
`.local/Multiplayer/20260912-093603-884`, using loopback port **18780**.
`.local/packaged-multiplayer-controls-20260912.json` records the physical keyboard
and visible ui observations, with no gameplay-state injection:

- client **5** selected Copper/Hurleyback; the host saw the replicated role
  message. client **enter** did not start the lobby. host **enter** did, and the
  client received live clock, equipment and score state. client **p** did not
  stop live play.
- both views reached the same certified copper win, **teal 113–copper 417**, in
  quarter one at **01:45**. client **enter** did not rematch. host **enter**
  started a live rematch; the host view showed **0–0, 03:00, LIVE**. the client's
  initial reset frame was not directly observed.
- host **p** then stopped at **02:54**, **teal 87–copper 0**. the client matched
  the stoppage status, clock and scores, and retained Copper/Hurleyback.
- client **alt+f4** disconnected cleanly. the host still showed **02:54, 87–0**;
  host **enter** resumed play, reaching **02:47, teal 87–copper 69**, before the
  host also exited with **Alt+F4**.

both logs contain normal viewport-close exit requests, object-system shutdown
and final exit lines. the host logged connection cleanup when the client left.
final exits were **09:43:14 client** and **09:43:44 host** local time. the log
review found no engine/network errors or network warnings. logs corroborate
connection/process lifecycle; displayed role, authority and score observations
come from the physical ui pass.

this establishes the listed interactive behavior across two real local processes.
it does not establish manual pickup/throw/catch, a held-ball departure in the
packaged run, remote-machine connectivity, adverse-network behavior, full-length
regulation, sixteen human participants or sustained performance. held-ball
departure and remedy preservation remain separately scoped pie evidence above.

## hogwarts legacy boundary

the installed hogwarts legacy creator kit uses ue 4.27.2 and its supported mod route rejects runtime DLLs. the ue5 native module and ue5 `.uasset` files cannot simply be shipped through that content-mod pipeline. the existing creator kit findings describe a separate content/Blueprint port and map-entry integration. shared rules/data and original art can inform both builds; transport code, engine assets, and gameplay integration require separate implementations. nothing in this inspection establishes supported multiplayer integration for hogwarts Legacy. see [creator-kit-findings.md](creator-kit-findings.md).

## local source evidence

- `Engine/Source/Editor/BlueprintEditorLibrary/Public/BlueprintEditorLibrary.h`: `eblueprintvariablereplication`, `getblueprintvariablereplication`, `SetBlueprintVariableReplication`.
- `Engine/Source/Editor/BlueprintEditorLibrary/Private/BlueprintEditorLibrary.cpp`: replication implementation at lines 1659–1756.
- `Engine/Source/Editor/BlueprintGraph/Classes/K2Node_Event.h`: `functionflags` declaration; `K2Node_EditablePinBase.h`: custom parameter storage and native pin-creation API.
- `Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyAccessUtil.cpp`: editor property access guard around line 724.
- `Engine/Source/Editor/Kismet/Private/BlueprintDetailsCustomization.cpp`: custom-event replication ui and reliable flag mutation around lines 4659 and 6251.
- `Engine/Source/Runtime/Engine/Classes/GameFramework/CharacterMovementComponent.h`: predicted movement, saved moves, server rpc, correction, and replay contract around lines 2384–2567.
- `Engine/Source/Runtime/Engine/Private/FloatingPawnMovement.cpp`: local movement loop without charactermovement's client move protocol.
- `Engine/Config/Windows/Windows_SDK.json`: installed compiler/SDK preferences and banned patch ranges.

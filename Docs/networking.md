# Basketbroom multiplayer implementation findings

Inspected against the installed UE 5.8.1 source and reflected Python API on 2026-09-10. The existing playable training build is local gameplay. A separate native network runtime is under construction in `DevelopmentHarness/Source/BasketbroomRuntime`; source code alone does not establish working multiplayer. The helpers described here do not validate multiplayer, regulation rules, or Hogwarts Legacy network integration.

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

The current harness is a content-only `.uproject`, and the Basketbroom plugin has no native module. Checks of standard Visual Studio/Windows SDK locations, registration keys, and PATH did not find a usable C++ compiler or Windows SDK. A nonstandard installation remains possible; UnrealBuildTool's actual detection is the final test. Unreal includes .NET SDK **10.0.203** under `Engine/Binaries/ThirdParty/DotNet/10.0/win-x64`.

Install a supported Visual Studio C++ toolchain with Desktop development with C++, Game development with C++, x64/x86 MSVC tools, and a Windows 11 SDK. Epic's UE 5.8 guide lists Visual Studio 2022 17.14+ or Visual Studio 2026 18.0+ and recommends VS 2026 for general development. [Epic Visual Studio setup](https://dev.epicgames.com/documentation/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine).

The exact installed `Engine/Config/Windows/Windows_SDK.json` is stricter about some compiler patches than a broad version label:

- Preferred MSVC families: 14.50 or 14.44. Select **14.50.35723+** or **14.44.35211+** within those families; earlier patches are explicitly banned.
- The local configuration also bans MSVC 14.39 and 14.40–14.43. Do not select a compiler just because it is newer than the nominal minimum 14.38.33130.
- Its main Windows SDK is 10.0.22621.0; use 22621 or a supported newer SDK such as 26100. The local lower admission threshold is 19041, but that is not the preferred installation target.

The maintainable standalone implementation is a runtime module containing the network Character, validated server requests, GameMode/GameState/PlayerState, and authoritative ball rules. An optional Editor module exposes the missing graph-authoring operations if the final gameplay is intended to remain Blueprint-based. Generate project targets, compile `Development Editor Win64`, load the module, then build/cook the game. For a standalone dedicated-server target, first confirm availability of the required server binaries; Epic's documented dedicated-server setup uses a source engine build. [Epic dedicated server setup](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-dedicated-servers-in-unreal-engine).

No software was installed and no native module was built by this investigation.

## Native rider implementation

`BBRiderCharacter.h/.cpp` now implement the agreed native route. `ABBRiderCharacter` uses `MOVE_Flying`, a 2100 cm/s maximum speed, 3600 cm/s² acceleration, a capsule, a local camera/cockpit, and original mounted-rider primitives attached to the Character mesh for remote movement smoothing. `UBBFlyingMovementComponent` preserves CharacterMovement's native protocol and constrains maximum speed/acceleration while the replicated stun is active. Its `PhysFlying` also enforces the end/side bounds and 207-foot ceiling on both authority and predicted owner, with a controlled rebound; physical lower nets still collide normally. The Character owns the server's stun countdown.

The rider replicates `TeamIndex`, `Position`, `RosterIndex`, `bInteractHeld`, and `StunRemaining`. Team changes refresh visible uniform materials. Key bindings need no project input mapping: WASD, Space/Ctrl, mouse, E press/release, left click, 1–6, T, Enter, P, and Tab. P requests an official stoppage; Tab only changes local help visibility.

Owned reliable RPCs update the held interaction or forward discrete requests to `ABBMatchState::HandleAction`: 0 pickup, 1 throw, 2 position, 3 team, 4 ready, 5 official stoppage. The rider rejects non-finite/non-unit aim, invalid action/role/team ranges, stunned pickup/throw, and excessively rapid actions; MatchState enforces semantic rules and resolves continuous held capture on the server. Match start/stoppage requests are restricted to the local host, or the first connected participant on a dedicated server. Interaction stops are never throttled. The runtime still requires a successful native build and the separate-process proof below before being described as functioning multiplayer.

Two development-only Blueprint calls submit input through these same request paths: `DevelopmentRequestAction` and `DevelopmentSetInteraction`. Both require a locally controlled PlayerController in a PIE world and reject Shipping builds. Their boolean result means the request was submitted, never that the server accepted the gameplay result. A held-interaction fixture must explicitly clear its hold during cleanup. No rules or score setter is exposed by this bridge.

## Required runtime proof

1. Host plus one separate client: each possesses a different Character, both move, and each sees the other's movement. Repeat as separate packaged processes rather than relying only on one-process PIE.
2. Simultaneous pickup requests for one ball: exactly one server-approved holder; rejection arrives without client-side score or possession divergence.
3. Client throw and legal goal: server assigns the score once, all clients agree, and a late joiner receives the current score/clock/holder state.
4. Invalid or repeated requests: wrong player, excessive distance, disallowed role, stale possession, phase mismatch, and cooldown violations leave authoritative state unchanged.
5. Network emulation: latency, packet loss, disconnection, rejoin, and possession changes while updates are in flight. Check corrections and ball interpolation, not only final scores.
6. Expand to 16 participant slots and the complete regulation rules only after the two-player authoritative loop passes. Verify CPU substitution and match-end behavior on the server and every client.

Passing the existing single-player, bot, or native-flight checks is not evidence of network correctness.

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

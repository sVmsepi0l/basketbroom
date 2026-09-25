# Native Creator Kit broom investigation — 2026-09-25

The disposable native PIE test now verifies **actual native mount association**: the game's native mount query identifies `BROOM_FLYING`, and the native player is attached to the same House broom capsule returned by `get_broom`. The association remains observed for 16 seconds. Usable flight is **not established** because no movement input was tested. The overall probe remains failed on the separate UI eligibility and inventory-load checks; it does not certify complete native broom controls or the standalone controls inside Hogwarts Legacy.

All observations below are from the installed licensee Creator Kit 4.27 project, owned `Basketbroom_DungeonMap` PIE, and its native `BP_Biped_Player_C` with character ID `Player0`. They are not UE5 harness results. No persistent gameplay assets were authored by this investigation.

## Saved probes and scope

- `Tools/probe_hlck_broom_gates.py` reads native inventory, tool, UI, lock, and reflected API state without modifying play state.
- `Tools/test_hlck_broom_inventory.py` defaults to a read-only preflight. `{"execute":true}` performs a bounded disposable inventory/use test. `{"execute":true,"request_native_mount":true,"observe_seconds":20}` additionally requests one native mount transition on the verified live House item created by normal inventory use. The optional observation duration is bounded to 0–20 seconds; the phase always ends by 20 seconds.
- The harness retains the exact PIE world, player, controller, and inventory component. It refuses unsaved editor work, an existing active tool/mount, unsupported initial inventory, another equipped broom, or another map/project/mod. It restores exact original broom counts and the two observed locks, compares protected file hashes, checks for dirty packages, then stops only its retained PIE.
- It does not save assets or player progress, edit SQLite or mod SQL, inject controls, force flight flags, or manually spawn a substitute broom actor. Editor Python is test scaffolding, not packaged gameplay.

## Confirmed inventory behavior

The actual inventory ID is `BroomHouse`. The tool record's lookup name `item_BroomHouse` is a different identifier. The observed native record is:

`/Game/Gameplay/ToolSet/Items/InventoryItems/Broom/DA_BroomHouseItem.DA_BroomHouseItem`

The normal runtime setup call is `InventoryManagerInterface.adjust_count("Player0", "BroomHouse", 1, holder_id="BroomStorage")`. In the empty test inventory, the game's logic equips this first broom automatically: `ActiveBroom` becomes 1 and `BroomStorage` remains 0. Both `Vendor_Broom_Acquired` and `BroomAvailable` change from locked to unlocked. The native adjustment returns **0**, which is the unaccepted remainder, not the quantity granted. Native `CanAddItemToInventory` likewise interprets a zero `CanAddItem` result as success. The harness verifies before/after counts rather than interpreting zero as failure.

`GetCount(Player0, BroomHouse, ActorBackpack)` is an aggregate player inventory query. It also returns 1 for the equipped broom. Adding it to `ActiveBroom` counts the same item twice. Quantity and cleanup accounting now use only the exact physical `ActiveBroom` and `BroomStorage` holders; the aggregate count is recorded separately. Read-only inspection of this installed DLL found the special Player0/ActorBackpack branch in native `GetCount` at RVA `0x161080e`, under function RVA `0x1610280`; the explicit-holder branch at `0x1610887` adds an exact `HolderID` predicate. These offsets are evidence for this installed binary, not portable API addresses or instructions to call native memory.

The empty `InventoryFilter()` is a struct, not an enum. `get_inventory_text_bp(..., item_type_id="Broom", specified_holder_only=True)` returns an empty UI result array in these tests even while exact-holder count is 1 and normal item use succeeds. Do not treat that UI list as proof that inventory is absent. The current guard for preserving a preexisting broom will fail closed if normal use transfers it and the exact original holder cannot be restored using an observed inventory result; that preexisting-item restoration path has not yet been exercised.

## Ordinary use result

Receipt: `.local/hlck/native-broom-inventory-tests/20260925-100300-66dc7a76/result.json`.

After the real grant and automatic unlocks, `load_inventory_item_by_name("BroomHouse", "ActiveBroom")` and `use_inventory_item_by_name(...)` both return true. Across later ticks, ordinary use creates the real `BP_BroomHouseItem_C_0` active tool in the retained PIE. No `FlyingBroom` appears within the 20-second observation window. Both UI eligibility calls remain false. The test fails rather than treating successful item use as successful flight. Exact inventory, lock, protected-file, dirty-package, and PIE cleanup checks pass.

## Native transition result

Transition receipt: `.local/hlck/native-broom-inventory-tests/20260925-100610-5d7a2d58/result.json`, completed at `2026-09-25T10:06:36Z`.

This test again grants exactly one broom and automatically unlocks both locks. Load returns false in this run; use returns true and produces the real native House item. Its `BroomItemTool` class, exact House record identity, and ownership by the retained player's inventory component are checked before calling `spawn_and_mount_broom(True, True)` once at `10:06:18.579730Z`.

The next observations establish actual native progress:

- At world time 17.560 seconds, `BP_FlyingBroomProp_House_C_0` exists and the player's `mounted_or_transitioning` query becomes true.
- At world time 18.311 seconds, `BP_FlyingBroomCapsule_House_C_0` exists with `/Script/Phoenix.FlyingBroomMovementComponent`.
- At the final observation, world time 34.285 seconds, both native actors remain. The movement component reports `is_flying=false`; the player remains `mounted_or_transitioning=true`; the controller still controls the native biped. `can_use_broom(True)` and `can_use_broom(False)` remain false throughout.

The saved harness result is **failed**, with no accepted settled-flight check. That status does **not** establish that the native transition failed. No movement input was tested. The harness's controller-possession plus generic `is_flying` condition is provisional, not a verified Hogwarts mount contract. It is equally incorrect to report that no native broom spawned: both native prop and capsule were observed. The script now labels that verification limitation explicitly; the historical receipt is preserved unchanged.

Read-only inspection gives a concrete native association criterion to investigate: the installed `MountZoneVolumeBase.get_broom(pawn)` wrapper at RVA `0x24d6fb0` calls native RVA `0x160ff40`, which calls imported `AActor::GetAttachParentActor` and returns that parent if it is a `FlyingBroom`. The import is resolved from this DLL's import table at VA `0x182fb8f48`. Thus the game has an explicit biped-to-broom attachment route; controller transfer is not established as a required success condition. Reflected `attach_player_to_broom_on_mount` documentation likewise describes attaching the biped to the broom. The report did not sample this attachment, so it cannot distinguish a fully associated idle mount from an unfinished transition. `get_mount_type(pawn)` is also a reflected read-only association query, documented to return no result if the pawn is not mounted.

The captured `FlyingBroomMovementComponent.is_flying` documentation is the generic navigation-movement definition (moving through non-fluid volume without resting on ground). No game-specific override or requirement that this be true on a stationary/hovering native broom has been verified. Neither a false value nor retention of the biped controller alone establishes a broken mount. A later test needs actual native association and a bounded real movement-input observation, then restoration and dismount, before usable flight can be accepted.

The observer was consequently corrected to report `actual_native_mount_association_settled`: the native `get_broom` result and biped attachment parent must both identify the same observed native capsule with `FlyingBroomMovementComponent`, `get_mount_type` must return a result, and the native mounted/transitioning state must remain true for at least two seconds. Controller possession and `is_flying` are diagnostics only. The separate `mount_association_result` can pass while inventory/UI gates keep the combined result failed. Neither result certifies responsive flight; `flight_input_tested` remains false. The older `test_hlck_native_broom.py` observer also used the unvalidated possession/`is_flying` criterion and must not be used to claim that a native transition failed.

The first corrected-observer attempt, `.local/hlck/native-broom-inventory-tests/20260925-101602-47cbeee5/result.json`, stopped after grant because Windows denied an atomic receipt replacement while a reader held the report. This was a report I/O failure before mounting, not a flight failure. All six cleanup checks passed. The initial native association queries ran successfully and returned no mount before activation. Receipt publishing now retries transient Windows locks for at most 310 ms, keeps the last complete report on permanent failure, and uses a unique temporary file. Extracted-method file tests verified transient recovery and permanent-failure preservation/cleanup. This uses the existing `native_test_receipts` retry protocol with older Creator Kit Python compatibility.

All six cleanup checks are true: total quantity restored, exact holder counts restored, original lock states restored, installed databases and mod SQL unchanged, no dirty packages, and owned PIE stopped. Starting and ending physical broom counts are zero. Native spawned actors are discarded with the owned PIE.

## Corrected native association result

Final receipt: `.local/hlck/native-broom-inventory-tests/20260925-102050-e7679b4a/result.json`, completed at `2026-09-25T10:21:15.484048Z` (the receipt records the equivalent local `06:21:15.484048-04:00`).

The single native mount call at `10:20:58Z` is recorded against the verified live House item, its exact `DA_BroomHouseItem` record, and the retained biped's `InventoryToolSetComponent`. The corrected `actual_native_mount_association_settled` check passes at `10:21:00.735872Z`. Across 65 sampled frames from world time 10.292 through 26.292 seconds, the native association and biped attachment parent both identify `BP_FlyingBroomCapsule_House_C_0`, and the native mount type is `<MountTypes.BROOM_FLYING: 0>`. The mounted/transitioning query stays true; the capsule has the native `FlyingBroomMovementComponent`.

The controller remains on the biped and generic `is_flying()` remains false throughout that association. This is observed evidence that those two old requirements are unsuitable as mandatory checks for native mount association. No real flight-input test was performed: the report explicitly records `flight_input_tested=false`. Association is verified; acceleration, steering, climbing, braking, boost, responsive controls, and ordinary dismount remain unverified.

The combined report correctly remains **failed**, while `mount_association_result` is **passed**. Nine checks are true and two are false:

- `native_can_use_broom=false`: both UI eligibility variants are already false after inventory and both locks are ready, before mounting. Their later false values cannot alone diagnose an active mount, but the pre-mount false result remains unresolved.
- `native_inventory_load_succeeded=false`: the explicit load call returns false. The subsequent ordinary use call returns true and creates the real House item. The meaning of the earlier false load result has not been established; it is retained rather than reclassified as success.

There is no runtime exception or timeout in this corrected run. All six cleanup checks pass again, including exact original physical holders/quantity, both original locks, unchanged installed database and mod SQL hashes, no dirty packages, and stopped owned PIE. No receipt-publication error recurred after the retry fix.

The next concrete native test should start from this verified association, send a brief normal game flight input through the retained biped/controller, then release it and observe displacement/velocity of the associated capsule and rider together. It must not require possessing the capsule, teleport either actor, or set flying flags. Keep the existing 20-second bound, exact cleanup, and explicit separation between movement proof and the still-false UI/load checks. Normal dismount and return of the biped's attachment/mount type should be a separately observed step. Investigate the pre-mount UI gate and explicit-load return value through their real native callbacks before declaring the whole native broom flow complete.

## Remaining gates and the next bounded investigation

`UIManager.get_ui_manager_pure()` returns the live native UI singleton. Its `game_player_controller` matches the retained PIE controller; no pause/menu transition is active. A class default object is not a substitute for this live manager. This observation supports future pause-menu work but does not prove complete native menu integration.

Removing the inventory/lock prerequisite is insufficient to make `can_use_broom` true. Read-only inspection of its installed native implementation confirms additional calls through `PlayerMountOverlapManager`, including the path taken when the avatar check argument is false. The exact false subgate has **not** been identified. No `NoMountZoneVolume` actors were present in the inspected dungeon, so a claim that an overlapping no-mount volume caused the failure is unsupported. No verified live getter for the mount-overlap manager has yet been found; do not query its class default object or mutate internal flags as a workaround.

The next investigation should use the native association receipt, inspect the normal House tool's transition callbacks and character/ability state, and identify the actual environmental gate. Observe later ticks and real flight movement before declaring success. Preserve the same one-world guards and cleanup. Do not repeat grants, use guessed console commands, teleport the pawn, or loosen success criteria merely to make the test pass.

One earlier read-only probe incorrectly passed `item_BroomDarkWizard1` to `UIBlueprintFunctionLibrary.is_spell_or_tool_blacklisted`. That caused the native Ensure at `UIBlueprintFunctionLibrary.cpp:1508` (tool record lookup failed). Its returned false was not valid blacklist evidence. The call has been removed from the probe; do not repeat it without first verifying the identifier expected by that helper.

## Persistent mod work still required

The installed content examples `MM_ExampleGameplayMod` and `AC_ExampleGameplayMod` under `/PhoenixUGC/GameplayMod/Blueprints/` remain the candidate supported route for an arena-scoped compiled Blueprint adapter. A native graph must implement and test the lifecycle and restoration before this becomes persistent gameplay. Automated graph authoring compatible with the installed Creator Kit has not yet been established. The editor-only Python harness must not be presented as a cloud-cooked mod implementation. See `Docs/hogwarts-integration.md` for the established content-only/cloud-cook boundary and separate UE5 build.

## Evidence integrity

Reports remain private local artifacts outside Git. SHA-256 at the time of this note:

- `native-broom-gates.json`: `ddbf25a413ae0023998f7aabbe722a32b8da103f0c5dd86bb91ac5c6be36c9fa`
- `20260925-100300-66dc7a76/result.json`: `5b0840f5fd262cdc023e001e8d79a53530e72fcccd846bc61a6ecf14f74b04a5`
- `20260925-100610-5d7a2d58/result.json`: `350dd734b87cc07881fa5c86117ed7f200c37a3778bb5c3320cb2fe4ff38bff7`
- `20260925-102050-e7679b4a/result.json`: `e758433cd2bc1fdd5820839a5847396f6f327427bcf9030a4b4133c423368ec2`

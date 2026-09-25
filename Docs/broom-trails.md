# broom tracers

The native prototype adds three original emissive filaments from the broom's
rear reed fan. Team defaults are mint and copper. The pause menu's trail-color
picker can override the tracer hue; clothing and team identity stay independent.
The local color preference is saved and reapplied after possession, then sent
through the owning rider's validated cosmetic RPC.

Normal flight leaves a short tapered path. Spending earned partial charge with
R2 makes it brighter and longer; an active full-charge super boost extends it
further. The effect only reads existing replicated flight outputs and never
awards or spends energy itself. L2 braking lets the residual path fade out.

The path uses a fixed 60 Hz sampler, at most 80 points, and three instanced draw
components with at most 240 segments in total per rider. Lifetime ranges from
0.30 to 1.15 seconds. Geometry has no collision, overlap, navigation, shadow, or
indirect-lighting influence. The original material already used by equipment
and sporting effects supplies the neon emission; no third-party VFX assets are
required. The owner's path is hidden from their first-person view. Other riders
and independent cameras can see it. Concealment hides it per viewer;
Transformation clears it. Pausing freezes existing geometry while color edits
can still update its hue.

Teleports, respawn placement, large network jumps, clock rewinds and long frame
gaps discard old samples instead of drawing a beam across the arena.

## verification

`Tools/test_broom_trail_policy.py` compiles the same native sampler/color code
used by the game. Its 16 cases cover frame-rate independence, bounds, expiry,
teleports, hitches, invalid input, lifetime/taper, and RGB validation. `--list`
only lists the plan and does not run or certify these checks.

In PIE, `DevelopmentGetBroomTrailState()` returns: sample count, visible segment
count, discontinuity count, boost blend, lifetime in seconds, effective red,
green and blue, custom-color flag, and strand component count. Expected limits
are 80 samples, 240 segments and three components (`BroomTracer0` through `2`).
The existing sporting-spell suite also checks Transformation masks and
concealment through actual player spell actions.

`Tools/test_native_trail_color.py` owns a fresh PIE session and sends simulated
gamepad events through the real `PlayerController::InputKey` and `PlayerInput`
bindings. Its eight checks cover Options and D-pad navigation into the picker,
each HSV channel, an idle edit flushed to the actual local INI, Circle/Options
back and resume with a live clock, local possession loading the saved custom
color, and Triangle restoring and saving team default. It refuses to edit an
existing custom preference. An interrupted run reports incomplete cleanup; use
Flight Journal > Broom trail color > Triangle before rerunning.

The September 25, 2026 UE5.8.1 run passed all eight checks in 17.2 seconds and
restored team default. That run observed disk persistence and a same-process
possession reload. The runner now also repossesses in the same callback, without
an intervening unpossessed pawn tick, to exercise the possession lifecycle.
Submit it through the editor bridge from a stopped native arena and keep the
PIE viewport focused. Read `.local/native-trail-color-results.json` for the final
result; the bridge's `started` response is not a test result.
Optional bridge arguments `visual_hold_seconds` (0 by default, capped at 30)
and `capture_preview: true` hold the first opened picker for inspection and
capture its owned game viewport to `.local/native-trail-picker-preview.png`.
The report records complete PNG dimensions with visual review pending; image
creation does not certify appearance or readability.

`Tools/test_native_trail_network.py` plans nine checks in three local PIE worlds:
the listen server, an editing client, and a separate observing client. It checks
the owning public setter and a valid raw Server RPC, rejects raw NaN and both
infinities, rejects a nonowner's public setter, replicates the team-color reset,
preserves gameplay identity and boost state, restores the original temporary
cosmetic state, and ends PIE with managed play settings restored. It uses the
existing network runner's listen-server configuration and restoration flow;
its result is `.local/native-trail-network-results.json`. The completed run
passed all nine checks in 6.1 seconds with all 16 riders present in each world.
The expanded field exceeded the previous default Character relevance distance;
the finite 16-rider roster is now always network relevant. No preference file is
edited. Python's editor script guard forces direct Actor RPC calls to execute
locally, so a bounded PIE-only request queue dispatches from native Tick through
the actual public setter or Server RPC. It never writes results directly.
The temporary editor listen-server setting was restored to standalone afterward.

These are simulated input checks, not physical DualSense/USB/Bluetooth or
process-relaunch evidence. Mouse dragging, rendered appearance, packaged
performance, and replication between separate machines still require their own runtime
checks. A passing portable sampler test alone does not establish those results.

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

Rendered appearance, packaged performance, remote color replication, and the
full controller picker still require their own runtime checks. A passing
portable sampler test alone does not establish those results.

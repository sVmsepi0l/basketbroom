# Arena volume expansion

**Requested September 15, 2026. Status: pending implementation.** The user requested a **40–50% increase in enclosed arena volume**. This applies to Basketbroom and Bloodbroom in the standalone UE 5.8 game and the native Creator Kit port.

Use **45% more volume** as the initial target. Uniform scaling of the enclosure is the implementation default: `scale = (1.45)^(1/3) = 1.13185119596`, or approximately **13.19% more length, width and height**. These are planned geometry changes; the current package and passed native Play receipt still use the pre-expansion arena.

## Measurement

Measure the actual enclosed space from the trampoline floor through the hollow pyramidion roof. The current shared geometry in [BBArenaGeometry.h](../DevelopmentHarness/Source/BasketbroomRuntime/BBArenaGeometry.h) has half-length 6850.8 cm, half-width 3200.4 cm, eaves at 4206.24 cm and an apex at 6309.36 cm. Its enclosed volume is:

`V = (2 * HalfLength) * (2 * HalfWidth) * (EaveHeight + (ApexHeight - EaveHeight) / 3)`

The finished volume must be between `1.40 * V` and `1.50 * V`, targeting `1.45 * V`. Use the enclosing net's footprint for this measurement; the historical 420-foot goal-to-goal distance omits the space behind the goal planes. Preserve the upward-pointing, hollow four-face cap and the rebound behavior established by the [pyramid-net amendment](pyramid-net.md).

## Implementation and acceptance

- Update the shared dimensions, generated floor/wall/roof geometry, collision, authoritative ball and rider bounds, owner prediction, held balls and Snipe/Snitch paths together. The visual enclosure and playable bounds must agree.
- Reposition arena-dependent goals, spawn locations, restart markers and gameplay zones coherently. Player/ball/broom size, hoop aperture sizes and sporting distances are separate parameters; the arena scale factor must not automatically multiply them. The confirmed Moderate free-shot minimum remains 44 feet from the attacking goal plane, with sideways position and altitude retained.
- Apply the same enclosure to Basketbroom and Bloodbroom and update the affected training geometry. Check flight room, goal visibility, chase capture, shot/restart placement and rebound behavior in both modes.
- Reimport original sources into the native Creator Kit, update only the owned arena geometry and required placements, then recheck roof faces/seams/apex, native player spawn and exit setup. Preserve unrelated scene content and registration data. UE 5 packages are not a port mechanism.
- Verify the measured volume ratio, real collision and gameplay bounds before creating a new Windows package. Keep the current native Play and roof receipts as evidence of the earlier dimensions; the enlarged arena needs fresh results.

The current source geometry, rules configuration, assets and packaged game have not yet been resized. This amendment records the requested development work and its default interpretation.

# Arena volume expansion

**Requested September 15, 2026. Status: pending implementation.** The user requested a **40–50% increase in enclosed arena volume**. This applies to Basketbroom and Bloodbroom in the standalone UE 5.8 game and the native Creator Kit port.

Use **45% more volume** as the initial target. Uniform scaling of the enclosure is the implementation default: `scale = (1.45)^(1/3) = 1.13185119596`, or approximately **13.19% more length, width and height**. These are planned geometry changes; the current package and passed native Play receipt still use the pre-expansion arena.

## Measurement

Measure the actual enclosed space from the trampoline floor through the hollow pyramidion roof. The current shared geometry in [BBArenaGeometry.h](../DevelopmentHarness/Source/BasketbroomRuntime/BBArenaGeometry.h) has half-length 6850.8 cm, half-width 3200.4 cm, eaves at 4206.24 cm and an apex at 6309.36 cm. Its enclosed volume is:

`V = (2 * HalfLength) * (2 * HalfWidth) * (EaveHeight + (ApexHeight - EaveHeight) / 3)`

The finished volume must be between `1.40 * V` and `1.50 * V`, targeting `1.45 * V`. Use the enclosing net's footprint for this measurement; the historical 420-foot goal-to-goal distance omits the space behind the goal planes. Preserve the upward-pointing, hollow four-face cap and the rebound behavior established by the [pyramid-net amendment](pyramid-net.md).

## Source audit before implementation

The September 15 source audit resolved an important naming difference: `BBArenaGeometry.h::HalfLength` is the **end-net plane**, while `build_arena.py::HALF_LENGTH` is the **goal plane**. The existing 450 cm behind-goal bay belongs to the enclosed footprint. Scale the goal-plane placement and bay depth together; adding an unchanged 450 cm after scaling the pitch would miss the uniform-volume target.

At the 45% target, enclosure half-length is 7754.086173 cm, half-width 3622.376568 cm, eaves 4760.837775 cm and apex 7141.256662 cm. The goal planes move to ±7244.753135 cm and bay depth becomes 509.333038 cm. The enclosed volume is approximately 430374.351 m³ before and 624042.809 m³ after. These remain **planned dimensions**, not a description of the saved maps.

Use explicit goal-plane and end-net constants across the C++ runtime and source generator. Preserve current hoop apertures, 35-foot hoop spacing and 69/100-foot hoop-center heights, along with the fixed 44-foot free-shot minimum, 22-foot restart offset and 13-foot exclusion distance. Reposition arena-dependent scenery and marks selectively; do not scale the whole world or the riders and equipment.

The implementation must replace duplicated geometry in ball scoring, match admissions/openings, bot approaches, penalty-shot targets and conduct-mark bounds. Training has separate Blueprint generators: its current 3140 cm side-ball limit should become half-width minus the actual ball radius. Active collision and network tests also contain fixed dimensions and goal-adjacent fixtures that must move with the venue. Retired Crown-rule tests are historical evidence, not active geometry specifications.

Native expansion needs its own bounded staging receipt. The existing roof stage covers only four roof meshes, one material and two maps; it cannot claim preservation for changed floors, walls or goal placements. Extend the verified map-amendment chain used by the arena, dungeon and anchor inspectors. Keep the native PlayerStart and exit where they are if their clearance checks remain valid, preserve existing material edits, and retain all pre-expansion receipts.

## Implementation and acceptance

- Update the shared dimensions, generated floor/wall/roof geometry, collision, authoritative ball and rider bounds, owner prediction, held balls and Snipe/Snitch paths together. The visual enclosure and playable bounds must agree.
- Reposition arena-dependent goals, spawn locations, restart markers and gameplay zones coherently. Player/ball/broom size, hoop aperture sizes and sporting distances are separate parameters; the arena scale factor must not automatically multiply them. The confirmed Moderate free-shot minimum remains 44 feet from the attacking goal plane, with sideways position and altitude retained.
- Apply the same enclosure to Basketbroom and Bloodbroom and update the affected training geometry. Check flight room, goal visibility, chase capture, shot/restart placement and rebound behavior in both modes.
- Reimport original sources into the native Creator Kit, update only the owned arena geometry and required placements, then recheck roof faces/seams/apex, native player spawn and exit setup. Preserve unrelated scene content and registration data. UE 5 packages are not a port mechanism.
- Verify the measured volume ratio, real collision and gameplay bounds before creating a new Windows package. Keep the current native Play and roof receipts as evidence of the earlier dimensions; the enlarged arena needs fresh results.

The current source geometry, rules configuration, assets and packaged game have not yet been resized. This amendment records the requested development work and its default interpretation.

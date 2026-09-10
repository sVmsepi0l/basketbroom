# Basketbroom art direction and current rendering pass

The target is a convincing, readable broom-sport venue at twilight: weathered
basalt, dark iron, aged copper, restrained team colors and a clear playing
surface. The center of attention is the flying ball and the illuminated scoring
aperture. Strong shape, material scale and lighting take priority over bloom.

This pass improves the playable prototype. It does not make the primitive-based
riders or the venue equivalent to a finished AAA production. It still needs
authored character art, animation, richer surface maps and visual playtesting.

## Implemented authoring changes

- An original generated basalt albedo is imported into Unreal and sampled with
  world-space triplanar projection. Stone detail keeps a consistent 220 cm tile
  size on architecture, with a larger scale on distant terrain. It is an actual
  material asset, not an image substituted for a game screenshot.
- Stone, iron, copper, teal trim and the trampoline have restrained spatial
  variation in roughness. Only one noise octave is used. There is no runtime
  tessellation or parallax mapping in this pass.
- The goal bodies are metal, with narrow inset luminous rings. Separate hidden
  collision padding retains the established aperture and rebound geometry.
- Masonry courses, coping, support collars, base bolts, diagonal bracing,
  handrails, and 770 individual seat backs provide scale and construction detail.
  Repeated details are combined into five meshes rather than hundreds of actors.
- A continuous irregular ridgeline replaces the cone-shaped mountains. A second
  mesh contains 148 asymmetric layered conifers. Both remain beyond the court,
  have no collision, and are excluded from ray-tracing and distance-field
  lighting. These are background silhouettes, not close-up foliage assets.
- A gradient twilight dome and restrained height/volumetric fog establish depth.
  The cool directional key has soft shadows; six court lights and four warm gate
  lanterns do not cast additional shadows or volumetric shadows. Motion blur is
  disabled for readable flight. Reflection and ambient-occlusion settings are
  bounded instead of set to cinematic quality.

`Tools/build_arena.py` builds the complete venue. `Tools/polish_scene.py` updates
the existing arena in place, importing the new source assets and replacing only
tagged scenery/detail actors. It leaves match, ball, player and bot actors intact.
All decorative shapes persist the **NoCollision** profile before setting their
collision mode. Physical floor, rim and net bodies retain **BlockAll**.

## Hardware and performance target

The development machine was inspected on September 10, 2026: Unreal Engine
5.8.1, NVIDIA GeForce RTX 3060, 12,288 MiB VRAM, driver 616.92. VRAM was read from
`nvidia-smi`; Windows' legacy `AdapterRAM` property truncated it to about 4 GB.

The intended baseline is 1080p at 60 FPS, with a 16.7 ms total frame budget. This
is a target, not a measured result of this graphics pass. Start at High or below
and profile a full bot scrimmage; do not select Cinematic merely because it has
the largest setting. Epic describes High as the 60 FPS Lumen tier and recommends
profiling the individual GPU passes. [Epic Lumen performance guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-performance-guide-for-unreal-engine)

The scene scripts do not change the project's rendering backend or force
hardware ray tracing, Lumen, virtual shadow maps, or Nanite. Those choices need
project configuration, restart/recook, and measured comparisons. The current
source meshes are modest in size: 78,824 triangulated faces across all 14 arena
source assets, before scene instancing. This is not a whole-scene draw-call or
GPU-cost measurement.

Volumetric fog is intentionally thin, with a 14,500 cm view distance and reduced
local-light contribution. Its cost depends on scalability and must be measured.
Keep volumetric shadows off on local lights; Epic documents their added cost.
[Epic volumetric fog documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/volumetric-fog-in-unreal-engine)

## Validation and next art work

Source validation checked finite mesh coordinates, valid polygon indices, an
unobstructed terrain inner radius of 9,000 cm, and unchanged pitch, goal and net
dimensions. Python syntax compilation passed. The pass then ran successfully in
the installed UE5.8.1 editor: 18 materials, nine new meshes and the texture were
imported/rebuilt, and the arena saved. Material compilation produced no shader
errors in the inspected log. A second run replaced its prior detail actors
without duplicating them.

Real editor captures from the authored hero and flight cameras were inspected.
The first render prompted a reduction in court lighting and an unlit net
material to eliminate sparkling strands. The revised flight view preserves
clear goal and ball silhouettes. Local review images are
`.local/art-review/hero.png` and `.local/art-review/flight.png`; these are actual
Unreal scene captures, not generated mockups. A saved-map reload audit verified
all 19 checked decorative mesh actors retain NoCollision, including the visual
net and sky dome. Close-up texture repetition, native gameplay integration and
frame-time profiling remain to be checked; these captures do not prove 60 FPS
or final production art quality.

The most valuable next assets are a rigged rider with seated flight animations;
an authored broom with grip, bindings and bristles; modular beveled stone/metal
architecture; normal/roughness maps authored for the material geometry; and
foliage with LODs. Character silhouette and motion currently limit perceived
quality more than another expensive lighting feature. Avoid making promises
that a rendering switch alone will supply those missing assets.

Future third-party art should come from the official [Fab marketplace](https://www.fab.com/),
with each asset's license, engine compatibility, texture resolution, triangle
count, LODs and animation skeleton reviewed before integration. No third-party
assets were acquired or licensed in this pass. Original geometry and the texture
below can continue to be improved without adding an asset dependency.

## Texture provenance

- File: `SourceArt/Textures/T_BB_Basalt_Albedo.png`.
- Generated with the built-in image generation tool; no external image reference.
- Actual source dimensions: 1254 × 1254. The Unreal texture build stretches it to
  a power-of-two size for a full mip chain; maximum texture size is 2048.
- The generator was asked for a seamless tile, but absence of visible repetition
  seams still requires an in-engine material check. This is an albedo image;
  no scanned physical roughness or normal data is claimed.

The generation prompt was:

> Use case: photorealistic-natural. Asset type: seamless square tileable
> base-color texture for a real-time Unreal Engine game arena, not a scene render
> or mockup. Generate a single 2048x2048 original weathered blue-grey basalt stone
> surface albedo. Flat orthographic close-up, fills the entire canvas edge-to-edge,
> seamless repeat on all four edges. A continuous natural fine-grained basalt
> surface with subtle dark mineral flecks, delicate micro pits and faint worn
> chisel abrasion, restrained uneven cool grey tonal variation. Approximately 2
> square metres of material. No bricks, mortar, grout lines, large cracks,
> recognizable repeated shapes, moss, grass, text, logos, frames, perspective,
> shadows, highlights, lighting gradient, or directional illumination. Even
> cross-polarized photographic texture scan appearance. Medium neutral bluish
> grey for physically based tinting in engine. This is only a material source
> texture, not a finished game screenshot.

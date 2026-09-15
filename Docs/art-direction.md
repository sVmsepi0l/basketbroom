# basketbroom art direction and current rendering pass

the target is a convincing, readable broom-sport venue at twilight: weathered
basalt, dark iron, aged copper, restrained team colors and a clear playing
surface. the center of attention is the flying ball and the illuminated scoring
aperture. strong shape, material scale and lighting take priority over bloom.

this pass improves the playable prototype. it does not make the primitive-based
riders or the venue equivalent to a finished aaa production. it still needs
authored character art, animation, richer surface maps and visual playtesting.

## implemented authoring changes

- an original generated basalt albedo is imported into unreal and sampled with
  world-space triplanar projection. stone detail keeps a consistent 220 cm tile
  size on architecture, with a larger scale on distant terrain. it is an actual
  material asset, not an image substituted for a game screenshot.
- stone, iron, copper, teal trim and the trampoline have restrained spatial
  variation in roughness. only one noise octave is used. there is no runtime
  tessellation or parallax mapping in this pass.
- the goal bodies are metal, with narrow inset luminous rings. separate hidden
  collision padding retains the established aperture and rebound geometry.
- masonry courses, coping, support collars, base bolts, diagonal bracing,
  handrails, and 770 individual seat backs provide scale and construction detail.
  repeated details are combined into five meshes rather than hundreds of actors.
- a continuous irregular ridgeline replaces the cone-shaped mountains. a second
  mesh contains 148 asymmetric layered conifers. both remain beyond the court,
  have no collision, and are excluded from ray-tracing and distance-field
  lighting. these are background silhouettes, not close-up foliage assets.
- a gradient twilight dome and restrained height/volumetric fog establish depth.
  the cool directional key has soft shadows; six court lights and four warm gate
  lanterns do not cast additional shadows or volumetric shadows. motion blur is
  disabled for readable flight. reflection and ambient-occlusion settings are
  bounded instead of set to cinematic quality.

`Tools/build_arena.py` builds the complete venue. `Tools/polish_scene.py` updates
the existing arena in place, importing the new source assets and replacing only
tagged scenery/detail actors. it leaves match, ball, player and bot actors intact.
all decorative shapes persist the **nocollision** profile before setting their
collision mode. physical floor, rim and net bodies retain **BlockAll**.

## hardware and performance target

the development machine was inspected on september 10, 2026: unreal engine
5.8.1, nvidia geforce rtx 3060, 12,288 mib vram, driver 616.92. vram was read from
`nvidia-smi`; windows' legacy `adapterram` property truncated it to about 4 GB.

the intended baseline is 1080p at 60 fps, with a 16.7 ms total frame budget. this
is a target, not a measured result of this graphics pass. start at high or below
and profile a full bot scrimmage; do not select cinematic merely because it has
the largest setting. epic describes high as the 60 fps lumen tier and recommends
profiling the individual gpu passes. [epic lumen performance guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-performance-guide-for-unreal-engine)

the scene scripts do not change the project's rendering backend or force
hardware ray tracing, lumen, virtual shadow maps, or Nanite. those choices need
project configuration, restart/recook, and measured comparisons. the current
source meshes are modest in size: 78,824 triangulated faces across all 14 arena
source assets, before scene instancing. this is not a whole-scene draw-call or
gpu-cost measurement.

volumetric fog is intentionally thin, with a 14,500 cm view distance and reduced
local-light contribution. its cost depends on scalability and must be measured.
keep volumetric shadows off on local lights; epic documents their added cost.
[epic volumetric fog documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/volumetric-fog-in-unreal-engine)

## validation and next art work

source validation checked finite mesh coordinates, valid polygon indices, an
unobstructed terrain inner radius of 9,000 cm, and unchanged pitch, goal and net
dimensions. python syntax compilation passed. the pass then ran successfully in
the installed UE5.8.1 editor: 18 materials, nine new meshes and the texture were
imported/rebuilt, and the arena saved. material compilation produced no shader
errors in the inspected log. a second run replaced its prior detail actors
without duplicating them.

real editor captures from the authored hero and flight cameras were inspected.
the first render prompted a reduction in court lighting and an unlit net
material to eliminate sparkling strands. the revised flight view preserves
clear goal and ball silhouettes. local review images are
`.local/art-review/hero.png` and `.local/art-review/flight.png`; these are actual
unreal scene captures, not generated mockups. a saved-map reload audit verified
all 19 checked decorative mesh actors retain nocollision, including the visual
net and sky dome. close-up texture repetition, native gameplay integration and
frame-time profiling remain to be checked; these captures do not prove 60 fps
or final production art quality.

the most valuable next assets are a rigged rider with seated flight animations;
an authored broom with grip, bindings and bristles; modular beveled stone/metal
architecture; normal/roughness maps authored for the material geometry; and
foliage with LODs. character silhouette and motion currently limit perceived
quality more than another expensive lighting feature. avoid making promises
that a rendering switch alone will supply those missing assets.

future third-party art should come from the official [fab marketplace](https://www.fab.com/),
with each asset's license, engine compatibility, texture resolution, triangle
count, lods and animation skeleton reviewed before integration. no third-party
assets were acquired or licensed in this pass. original geometry and the texture
below can continue to be improved without adding an asset dependency.

## texture provenance

- File: `SourceArt/Textures/T_BB_Basalt_Albedo.png`.
- generated with the built-in image generation tool; no external image reference.
- actual source dimensions: 1254 × 1254. the unreal texture build stretches it to
  a power-of-two size for a full mip chain; maximum texture size is 2048.
- the generator was asked for a seamless tile, but absence of visible repetition
  seams still requires an in-engine material check. this is an albedo image;
  no scanned physical roughness or normal data is claimed.

the generation prompt was:

> use case: photorealistic-natural. asset type: seamless square tileable
> base-color texture for a real-time unreal engine game arena, not a scene render
> or mockup. generate a single 2048x2048 original weathered blue-grey basalt stone
> surface albedo. flat orthographic close-up, fills the entire canvas edge-to-edge,
> seamless repeat on all four edges. a continuous natural fine-grained basalt
> surface with subtle dark mineral flecks, delicate micro pits and faint worn
> chisel abrasion, restrained uneven cool grey tonal variation. approximately 2
> square metres of material. no bricks, mortar, grout lines, large cracks,
> recognizable repeated shapes, moss, grass, text, logos, frames, perspective,
> shadows, highlights, lighting gradient, or directional illumination. even
> cross-polarized photographic texture scan appearance. medium neutral bluish
> grey for physically based tinting in engine. this is only a material source
> texture, not a finished game screenshot.

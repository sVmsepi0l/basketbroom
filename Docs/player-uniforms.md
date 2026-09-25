# player uniform skins

the september 25 uniform pass uses forest service mint with a restrained phthalo
green influence (`#8abfa3`) and copper with a small canary-yellow contribution
(`#bb7831`). these are the user's new colors. the internal `Teal` asset/team
identifiers stay intact so existing roster, replication and saved references
continue to work.

the installed quinn mannequin now receives an original woven flight uniform
shader: a colored jersey, dark trousers and side panels, light chest/collar
piping, and darker leather glove, boot and waist regions. the mathematical weave
adds restrained surface relief and roughness variation, fading out with distance
to limit shimmer. tailoring masks use the mesh's pre-skinned coordinates so they
follow the seated animation rather than sliding as the rider moves.

both material slots keep their own installed quinn normal and ambient-occlusion
maps. the stock maps are referenced locally in their original paths; they are
not copied into source art. the new material is nonmetallic. it uses no added
glow and does not change player visibility, collision, input, team selection,
rules or bloodbroom behavior. existing equipment team accents receive the same
identity tint while retaining their original graph and illumination settings.

this is a material and uniform pass on the stock mannequin, not new human
character geometry, face textures or a finished wardrobe. the native hogwarts
legacy character continues to use its separate appearance system. no ue5 asset
is staged into the creator kit by this tool.

## reproducible staging

`SourceArt/Characters/player_uniforms.json` records the original palette and
surface settings. `Tools/stage_player_uniforms.py` defaults to read-only
preflight. in the stopped, clean ue5.8 basketbroom editor, run it through the
bridge with `{"dry_run":false}` to author the uniform. it saves exactly seven
owned packages: one material parent, four existing team instances and two team
accent materials. before editing, it backs up every existing output; afterward,
it checks that all other plugin packages remain byte-identical. it refuses a
different project, engine, active play session, unsaved work or an unrecognized
material at the destination. attempt receipts and backups live under
`.local/player-uniform-stage`.

the earlier `stage_skeletal_rider.py` respects the newer uniform ownership tag,
so rebuilding the flight loop does not repaint these garments. regenerating the
old primitive training riders also uses the updated mint/copper identity.

`Tools/probe_player_uniforms.py` reads the seven saved packages and checks the
recipe identity, shader outputs, skeletal usage, team palette, per-slot normal/AO
bindings and accent tint. `probe_native_rider_art.py` checks actual runtime
material assignments on all sixteen riders. `test_native_equipment_visual.py`
provides real viewport captures of both teams for visual review. asset checks
alone do not establish visual quality, packaged appearance or frame rate.

## validation

source syntax checks passed. the final ue5.8 stage at
`20260925-101037-149861-b4eb72ce` compiled and saved all seven intended packages.
the receipt is `.local/player-uniform-stage/20260925-101037-149861-b4eb72ce/result.json`.
all other plugin packages stayed byte-identical, and no map, mesh or animation
was saved. the saved-asset probe passed for all seven packages.

the first pass exposed a texture sampler mismatch: the installed quinn MRA maps
require a linear-color sampler, rather than the masks-compression sampler. that
was corrected before visual approval. the stage now rejects reported shader
compile errors before saving, as well as checking connected material outputs.

the modern local-position node uses the pre-skinning origin. unreal documents a
gpu skin-cache limitation for that origin. the tested editor reports skin-cache
mode 1 but compiled skin-cache shaders 0 and ray tracing 0; no renderer setting
was changed. enabling skin-cache shaders or ray tracing later requires a new
uniform rendering check. the first actual two-team preview confirmed cloth
and trim rendering, then prompted a small
copper correction from `#d49344` (too golden in the venue lighting) to
`#bb7831`: traditional copper with approximately four percent canary yellow.
the final stage and render review use that corrected palette.

the equipment viewport check passed all ten cases, including actual material
assignments on all sixteen riders. the root assistant inspected all four
captures from run `1790331039489677500`: mint and copper third-person views,
owner first-person equipment, and owner first-person hud. the stock-mannequin
uniform appearance was accepted for this prototype: the teams are distinct,
cloth, boots and piping are visible, and no fallback material was observed.
the hud capture predates the current hud palette rebuild, so it does not certify
the final hud colors. that capture acceptance concerns ue5 play-in-editor
rendering; the later packaged acceptance is recorded separately below.

`Docs/validation-player-uniforms-20260925.json` records report, final recipe and
image hashes, case names, review scope and these limits. three reports, the
final palette recipe and all four captures were copied without moving the
originals into the unique read-only local archive
`.local/validation-archive/20260925-101312-550-uniforms-01562a5169914133ba09d036bd994a95/`.
the source stage receipt still says `saved_pending_visual_review` because it
precedes the subsequent review; the separate validation index records the
completed prototype visual acceptance without rewriting that historical receipt.

## promoted prototype package

candidate `Development-20260925-062224-613` was accepted and promoted to the
desktop launcher on september 25. its own direct review confirmed the uniforms
rendered without visible fallback materials in all three arena maps. redrock
regulation and redwoods bloodbroom entered live play; classic was verified only
through rendering and the lobby. the packaged pause journal showed playstation
symbols, l2/r2 prompts and mint accents after the hud rebuild.

`Docs/validation-package-20260925.json` records candidate-specific visual and
loopback receipts, the promotion and retained previous pointer. this promoted
build still uses quinn mannequin geometry. the user's subsequent request for
realistic adult hogwarts-style characters is work in progress and is not
implemented or accepted by this uniform/material checkpoint.

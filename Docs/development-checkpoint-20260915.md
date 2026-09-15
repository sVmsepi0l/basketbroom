# development checkpoint — 2026/09/15

this is an unfinished development checkpoint on `sprint-3-spells-graphics`, after user reported 4% remaining usage. continue the authorized full regulation, spellwork, hogwarts integration and two environment/art tracks. do not treat this checkpoint as a completed game or release.

## implemented and compiled

- all eight remaining standalone contextual spell adapters: owned workshop unlock/conjure/alter/levitate/damage/repair/vanish, earned ancient magic meter, pulse and physical swept throw. see native-contextual-spells.md. gameplay tuning remains provisional.
- terminal Moderate/Serious restitution and conservative, explicit host-selected moderate advantage. original immutable foul evidence survives endings and subsequent incidents; lost possession stops advantage; owed remedies block certification. f10 toggles the one-use safe basic-cast mobbing adjudication; controller view opens roster then menu toggles. see native-restitution.md for precise gates and the unfinished live acceptance recipe.
- UE5.8.1 basketbroomdeveditor compilation succeeded, 2026/09/15 13:27 UTC. Log: `.local/ue5/spells-advantage-editor-build.log`. new runtime pie, game-target build and package were not run.
- portable evidence: 40 combat cases; 28 new restitution cases; 13 environment source/guard cases; 5 existing spell fixture cases. these are not live gameplay proof.

## new arenas and visual defect

- both owned maps bb_redrock and bb_redwoods staged: 30 original source meshes, 19 materials, 3 original imagegen albedos and 2 maps. stage receipt `.local/environment-stage/20260915-131953-509706-d0c0c143/result.json`; manifest sha256 `98d305f26e5c56e261ae5095f639962108c1df31a9a88ec9db03a7bc6e014265`. original regulation bytes preserved; actual sporting collision checks passed before save and after reload.
- source albedos are actually 1254x1254, not the requested 2048. prompts, modes, hashes and dimensions: `SourceArt/Environments/Textures/provenance.json`. they are base color only, not scanned pbr sets.
- redrock loaded into genuine pie with old compiled runtime and correct HUD/7 balls. no live match was started. actual views `.local/environment-renders/20260915-092314-redrock.png` and `redrock-front.png` expose obstructed cliff views. investigate imported obj handedness/Y mirror by comparing asymmetric imported bounds to source (rr_overhang, rw_ocean); do not declare final art or conceal an import error by moving a camera.
- new maps have not received visual acceptance, gameplay acceptance or packaging. review redwoods as well. root-owned `preview_arena_environment.py` editor screenshot stayed queued until pie drew; prefer native_play_session capture in an actual preview session.
- new launcher arena selection resolves Classic/Redrock/Redwoods. existing desktop shortcut still resolves the earlier tested classic package. new explicit arena .cmd launchers require a future package containing both maps; editor paths can be planned with -EditorGame. Package.ps1 now requires and cooks both maps. test_packaged_network.ps1 accepts -arena but new arena network runs are not done.

## native hogwarts

- native creator kit pid20652 was left open with user's normal play session. actual inventory observer passed: player has native house broom, inventory tool usage allowed, wand active. no persistent native match adapter has been implemented in this checkpoint.
- probe scripts and fresh reports under `.local/hlck` record observed native APIs. native broom preflight succeeded. the actual retained test `.local/hlck/native-broom-tests/20260915-133030-485578-dec0bc8a/result.json` then called activate_tool once but received no valid broomitemtool; it failed before mount or input. cleanup confirmed original player possession and tools restored. no native mount/flight claim.
- there appear to be duplicate native editor bridge callbacks: each execute request yielded two attempt directories milliseconds apart; the second reported an existing observer, while the first genuinely ran. fix bridge registration/idempotence before more native mutations. inspect actual first-attempt receipts, not only the last mailbox response. native test observer is finished.
- native kit stays on its mandatory UE4.27.2 licensee engine; standalone runtime is UE5.8. never copy ue5 assets/DLL into native mod. native graph editing is not yet exposed through verified kit python apis; persistent runtime integration remains work.

## resume sequence

1. read latest broom/axis diagnostic script receipts (Tools/repair_arena_environment_axes.py dry_run is prepared but not run) and this checkpoint; check repo/editor state. ue5 was cleanly closed and mailbox reset to read-only probe_editor_checkpoint.py. do not close native kit casually or replay a quit request.
2. Fix/prove environment import orientation, restage only owned assets, view real shots in both settings and refine art.
3. run Tools/test_native_contextual_spells.py separately with variant regulation and bloodbroom, max_wall_seconds540;20 planned cases per run. finish and run native restitution ordinary-input acceptance described in native-restitution.md. do not inject scores/penalties/endings to manufacture a pass.
4. run relevant shared rules/spells/controller regressions, genuine rematch and new contextual network replication checks. preserve initial state and exact test receipts.
5. build game, package both venues, test actual packaged graphics and host/client map travel (both modes), then update current validation docs. existing tested package remains the user fallback until this passes.
6. continue native broom/flight proof and persistent match integration through supported native assets/APIs. full regulation, network acceptance, hogwarts match integration and final art remain unfinished.

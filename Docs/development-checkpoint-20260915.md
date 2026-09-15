# Development checkpoint — 2026-09-15

This is an unfinished development checkpoint on `sprint-3-spells-graphics`, after user reported 4% remaining usage. Continue the authorized full regulation, spellwork, Hogwarts integration and two environment/art tracks. Do not treat this checkpoint as a completed game or release.

## Implemented and compiled

- All eight remaining standalone contextual spell adapters: owned workshop unlock/conjure/alter/levitate/damage/repair/vanish, earned Ancient Magic meter, pulse and physical swept throw. See native-contextual-spells.md. Gameplay tuning remains provisional.
- Terminal Moderate/Serious restitution and conservative, explicit host-selected Moderate advantage. Original immutable foul evidence survives endings and subsequent incidents; lost possession stops advantage; owed remedies block certification. F10 toggles the one-use safe Basic-Cast mobbing adjudication; controller View opens roster then Menu toggles. See native-restitution.md for precise gates and the unfinished live acceptance recipe.
- UE5.8.1 BasketbroomDevEditor compilation succeeded, 2026-09-15 13:27 UTC. Log: `.local/ue5/spells-advantage-editor-build.log`. New runtime PIE, game-target build and package were NOT run.
- Portable evidence: 40 combat cases; 28 new restitution cases; 13 environment source/guard cases; 5 existing spell fixture cases. These are not live gameplay proof.

## New arenas and visual defect

- Both owned maps BB_Redrock and BB_Redwoods staged: 30 original source meshes, 19 materials, 3 original imagegen albedos and 2 maps. Stage receipt `.local/environment-stage/20260915-131953-509706-d0c0c143/result.json`; manifest SHA256 `98d305f26e5c56e261ae5095f639962108c1df31a9a88ec9db03a7bc6e014265`. Original regulation bytes preserved; actual sporting collision checks passed before save and after reload.
- Source albedos are actually 1254x1254, not the requested 2048. Prompts, modes, hashes and dimensions: `SourceArt/Environments/Textures/provenance.json`. They are base color only, not scanned PBR sets.
- Redrock loaded into genuine PIE with old compiled runtime and correct HUD/7 balls. No live match was started. Actual views `.local/environment-renders/20260915-092314-redrock.png` and `redrock-front.png` expose obstructed cliff views. Investigate imported OBJ handedness/Y mirror by comparing asymmetric imported bounds to source (RR_Overhang, RW_Ocean); do not declare final art or conceal an import error by moving a camera.
- New maps have NOT received visual acceptance, gameplay acceptance or packaging. Review redwoods as well. Root-owned `preview_arena_environment.py` editor screenshot stayed queued until PIE drew; prefer native_play_session capture in an actual preview session.
- New launcher Arena selection resolves Classic/Redrock/Redwoods. Existing desktop shortcut still resolves the earlier tested Classic package. New explicit arena .cmd launchers require a future package containing both maps; editor paths can be planned with -EditorGame. Package.ps1 now requires and cooks both maps. test_packaged_network.ps1 accepts -Arena but new arena network runs are NOT done.

## Native Hogwarts

- Native Creator Kit PID20652 was left open with user's normal Play session. Actual inventory observer passed: player has native house broom, inventory tool usage allowed, wand active. No persistent native match adapter has been implemented in this checkpoint.
- Probe scripts and fresh reports under `.local/hlck` record observed native APIs. Native broom preflight succeeded. The actual retained test `.local/hlck/native-broom-tests/20260915-133030-485578-dec0bc8a/result.json` then called activate_tool once but received no valid BroomItemTool; it failed before mount or input. Cleanup confirmed original player possession and tools restored. No native mount/flight claim.
- There appear to be duplicate native editor bridge callbacks: each execute request yielded two attempt directories milliseconds apart; the second reported an existing observer, while the first genuinely ran. Fix bridge registration/idempotence before more native mutations. Inspect actual first-attempt receipts, not only the last mailbox response. Native test observer is finished.
- Native Kit stays on its mandatory UE4.27.2 licensee engine; standalone runtime is UE5.8. Never copy UE5 assets/DLL into native mod. Native graph editing is not yet exposed through verified Kit Python APIs; persistent runtime integration remains work.

## Resume sequence

1. Read latest broom/axis diagnostic script receipts (Tools/repair_arena_environment_axes.py dry_run is prepared but NOT run) and this checkpoint; check repo/editor state. UE5 was cleanly closed and mailbox reset to read-only probe_editor_checkpoint.py. Do not close native Kit casually or replay a quit request.
2. Fix/prove environment import orientation, restage only owned assets, view real shots in both settings and refine art.
3. Run Tools/test_native_contextual_spells.py separately with variant regulation and bloodbroom, max_wall_seconds540;20 planned cases per run. Finish and run native restitution ordinary-input acceptance described in native-restitution.md. Do not inject scores/penalties/endings to manufacture a pass.
4. Run relevant shared rules/spells/controller regressions, genuine rematch and new contextual network replication checks. Preserve initial state and exact test receipts.
5. Build game, package both venues, test actual packaged graphics and host/client map travel (both modes), then update current validation docs. Existing tested package remains the user fallback until this passes.
6. Continue native broom/flight proof and persistent match integration through supported native assets/APIs. Full regulation, network acceptance, Hogwarts match integration and final art remain unfinished.

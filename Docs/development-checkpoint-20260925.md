# Development checkpoint — 2026-09-25

Resumed on `sprint-4-art-gphx` at `409d22e` (merge of pull request #13 from `sprint-3-debugging`). The working tree was clean at the initial recovery inspection. The user requested continued development and another arena enlargement, described as “double the size.” An optional clarification was offered; work proceeded with the stated assumption of twice September 16's floor area at fixed height and aspect ratio. This is a second amendment, not a rerun of September 16's enlargement.

## Recovered checkpoint

The September 16 candidate remains on disk and its packaging log records success. At the initial recovery inspection, all five report hashes and case lists in `Docs/validation-20260916.json` matched their local evidence: 19 controller, 11 flight, 20 spell cases in each match mode and 22 portable flight policy cases. Arena and environment staging success hashes also matched at that point. Today's runs subsequently replaced rolling report filenames and success pointers; they must not be assumed still to contain the September 16 evidence. See `Docs/development-checkpoint-20260916.md` for the historical packaging/network evidence and its limits.

Candidate manifest: `.local/PackageWork/Development-20260916-035952-025/package-result.json`.

Candidate executable: `.local/Build/Development-20260916-035952-025/Windows/BasketbroomDev.exe`.

At initial recovery the desktop launcher selected `.local/Build/Development-20260915-081623-488/Windows/BasketbroomDev.exe`; it was preserved until the new candidate completed acceptance later in this session. Two preserved September 16 candidate loopback tests prove connection, join and map travel only; they do not certify gameplay replication or Bloodbroom activation. Prior visual observations were recovered from session notes, with startup logs still present, but a separate persisted September 16 visual acceptance receipt was not found.

## Saved enlargement and builds

All four UE5 arenas were amended, saved and reloaded with exact preservation and collision checks: `.local/arena-expansion-stage/20260925-093616-657683-2932e724/results.json`. Both scenery variants were restaged with zero source-geometry intrusions and preserved sporting actors: `.local/environment-stage/20260925-093719-049631-8f07149f/result.json`.

Both native Creator Kit maps are also enlarged, saved and reloaded: `.local/hlck/arena-resize-stage/20260925-094124-611556-dc696f76/result.json`. Native staging preserves current materials and non-target actors. It changes only two owned maps and ten original mesh assets; installed game maps, databases and dungeon registration remain unchanged. An initial preflight rejected unchanged meshes' historical LF/CRLF source hashes. The correction requires the exact pinned historical provenance and verifies both byte forms; changed meshes retain strict revision hashes.

The UE5.8.1 editor and game builds succeeded (`.local/ue5/build-20260925.log`, `.local/ue5/game-build-20260925.log`). Portable checks passed: 55 rules, 23 resize and 13 environment cases. All 11 real-input flight checks passed in enlarged Redrock, including real goal/Bludger charge, L2 brake, R2 acceleration/boost, inversion and pause. Two earlier attempts lost viewport focus; a bounded operator focus grace period allowed the test to run without bypassing gameplay input guards.

The 35 playable integration cases also passed, covering match/role transitions, actual whole-ball goals, rim and reverse-crossing rejection, pyramid roof and side-net behavior, ball custody, and Snipe catch progress. All 20 contextual spell cases passed in each of regulation and Bloodbroom. These are standalone UE5 tests through the C++ gameplay implementation, not proof that those features work inside Hogwarts Legacy.

Native Creator Kit passed 20 read-only dungeon inspection checks and 16 observed PIE checks for the owned world, possessed native player, settled services, registration and exit interaction components. No travel or input was injected by the observer, and these checks do not prove native broom mounting or a complete native match. The amendment predecessor validator was corrected to recognize a preserved editor resave only when its recorded actor/component/game-mode identity matches the predecessor; its eight portable regression cases passed.

## Preserved validation evidence

`Docs/validation-20260925.json` indexes the six passed gameplay/inspection reports and three successful staging reports with SHA-256 hashes, scope and case names. Exact copies were archived under `.local/validation-archive/20260925-095807-311-9021b040e74d41138a9cabce6a04adb3/` before writing the index. The archive uses a unique directory and read-only files; future test runs may overwrite the original rolling paths without replacing these copies. The archive remains local and ignored by Git; the compact hash/case index is tracked.

## Player uniforms and giant redwoods

The final mint/copper uniform palette was staged in seven owned material packages, and the seven-asset configuration probe and ten equipment/viewport checks passed. The root assistant directly accepted all four captured prototype views. `Docs/validation-player-uniforms-20260925.json` indexes the immutable local reports, final recipe and images. The owner HUD image predates the HUD palette rebuild and does not certify its final colors. This is a material pass on the stock mannequin, with native Hogwarts appearance still separate.

The coastal grove now retains 49 trees with eight selected giants at exactly three times their prior scale, twenty medium trees and twenty-one original-size trees. Positions/yaw and shared meshes are preserved; no mesh instances or triangles were added. All 2,772,322 transformed redwood triangles cleared the protected arena envelope with zero intrusions, and all seventeen portable environment checks passed.

The final environment stage `.local/environment-stage/20260925-102023-131022-71635645/result.json` saved/reloaded both venue maps with source-map and content-scope preservation. The root assistant directly accepted the actual giant-redwoods hero preview for this prototype. `Docs/validation-environments-20260925.json` indexes exact read-only stage, manifest and preview copies, including review limits. This editor composition check is not a packaged frame-rate or gameplay check; native Creator Kit scenery is outside the giant-tree amendment.

## Package acceptance and promotion — completed

The enlarged-arena candidate `.local/PackageWork/Development-20260925-055521-668/package-result.json` finished successfully and passed both loopback checks, limited to connection/join/map travel. It was subsequently superseded by the player-uniform and giant-tree changes.

Candidate `.local/PackageWork/Development-20260925-062224-613/package-result.json` finished successfully with AutomationTool exit code 0 (53 seconds) and passed its own bounded acceptance. All three maps rendered the enlarged court, uniforms and equipment. Redrock regulation entered live play with a running clock, observed AI score 69 and an opened spellbook. Redwoods Bloodbroom entered live play with observed ball custody/AI score 69; the pause journal showed PlayStation symbols, L2/R2 prompts and mint accents, and resumed successfully. Classic was verified through rendering and the lobby only: concurrent user input blocked the attempted live-start check, so no Classic live-play claim is made.

The final candidate's Redrock and Redwoods loopback receipts passed: `.local/packaged-network/20260925-062355-356-fe818321/result.json` and `.local/packaged-network/20260925-062355-530-125f81a9/result.json`. Their scope remains connection, tagged join and map travel; they do not certify gameplay replication or remote multiplayer. Direct visual acceptance is `.local/package-visual-acceptance-20260925-062224-613.json`.

The accepted candidate was promoted at `2026-09-25T10:29:09.8194659Z`. The desktop launcher now selects `.local/Build/Development-20260925-062224-613/Windows/BasketbroomDev.exe`. Promotion and the retained previous pointer are under `.local/package-promotions/20260925-102909-772-e28cca76c916408493343653ebb20e8d/`. `Docs/validation-package-20260925.json` indexes exact archived manifest, visual/network/promotion evidence and supporting logs. Candidate, promotion and actual launcher-pointer hashes matched during archive. The Classic visual log remained open by the game and was referenced rather than copied; the direct review receipt records its narrower scope.

## Next safe milestone

The user subsequently requested realistic adult Hogwarts-style characters. That addition is in progress; the promoted build still uses the stock Quinn mannequin with the new uniform materials. Do not present the uniform pass as completed realistic human characters. Keep the accepted package available while developing and validating that next art milestone.

The earlier preserved PIE gameplay checks precede the player-material and giant-tree changes; they remain separate from the explicitly scoped packaged checks above. `Tools/Promote-Package.ps1` passed twelve isolated file checks and performed the actual promotion with a retained previous-pointer backup.

Continue complete regulation, remaining spellwork, multiplayer, native Hogwarts broom/menu/match integration and final art after the enlarged arena is playable. Standalone UE5 evidence does not establish native Creator Kit integration. Save checkpoints with explicit test scope, limitations and package status; keep videos, generated builds and private local reports outside Git.

# Development checkpoint — 2026-09-25

Resumed on `sprint-4-art-gphx` at `409d22e` (merge of pull request #13 from `sprint-3-debugging`). The working tree was clean at the initial recovery inspection. The user requested continued development and another arena enlargement, described as “double the size.” An optional clarification was offered; work proceeded with the stated assumption of twice September 16's floor area at fixed height and aspect ratio. This is a second amendment, not a rerun of September 16's enlargement.

## Recovered checkpoint

The September 16 candidate remains on disk and its packaging log records success. At the initial recovery inspection, all five report hashes and case lists in `Docs/validation-20260916.json` matched their local evidence: 19 controller, 11 flight, 20 spell cases in each match mode and 22 portable flight policy cases. Arena and environment staging success hashes also matched at that point. Today's runs subsequently replaced rolling report filenames and success pointers; they must not be assumed still to contain the September 16 evidence. See `Docs/development-checkpoint-20260916.md` for the historical packaging/network evidence and its limits.

Candidate manifest: `.local/PackageWork/Development-20260916-035952-025/package-result.json`.

Candidate executable: `.local/Build/Development-20260916-035952-025/Windows/BasketbroomDev.exe`.

The desktop launcher still selects `.local/Build/Development-20260915-081623-488/Windows/BasketbroomDev.exe`. Neither the candidate nor the package pointer was changed during recovery. Two preserved candidate loopback tests prove connection, join and map travel only; they do not certify gameplay replication or Bloodbroom activation. Prior visual observations were recovered from session notes, with startup logs still present, but a separate persisted visual acceptance receipt was not found.

## Saved enlargement and builds

All four UE5 arenas were amended, saved and reloaded with exact preservation and collision checks: `.local/arena-expansion-stage/20260925-093616-657683-2932e724/results.json`. Both scenery variants were restaged with zero source-geometry intrusions and preserved sporting actors: `.local/environment-stage/20260925-093719-049631-8f07149f/result.json`.

Both native Creator Kit maps are also enlarged, saved and reloaded: `.local/hlck/arena-resize-stage/20260925-094124-611556-dc696f76/result.json`. Native staging preserves current materials and non-target actors. It changes only two owned maps and ten original mesh assets; installed game maps, databases and dungeon registration remain unchanged. An initial preflight rejected unchanged meshes' historical LF/CRLF source hashes. The correction requires the exact pinned historical provenance and verifies both byte forms; changed meshes retain strict revision hashes.

The UE5.8.1 editor and game builds succeeded (`.local/ue5/build-20260925.log`, `.local/ue5/game-build-20260925.log`). Portable checks passed: 55 rules, 23 resize and 13 environment cases. All 11 real-input flight checks passed in enlarged Redrock, including real goal/Bludger charge, L2 brake, R2 acceleration/boost, inversion and pause. Two earlier attempts lost viewport focus; a bounded operator focus grace period allowed the test to run without bypassing gameplay input guards.

The 35 playable integration cases also passed, covering match/role transitions, actual whole-ball goals, rim and reverse-crossing rejection, pyramid roof and side-net behavior, ball custody, and Snipe catch progress. All 20 contextual spell cases passed in each of regulation and Bloodbroom. These are standalone UE5 tests through the C++ gameplay implementation, not proof that those features work inside Hogwarts Legacy.

Native Creator Kit passed 20 read-only dungeon inspection checks and 16 observed PIE checks for the owned world, possessed native player, settled services, registration and exit interaction components. No travel or input was injected by the observer, and these checks do not prove native broom mounting or a complete native match. The amendment predecessor validator was corrected to recognize a preserved editor resave only when its recorded actor/component/game-mode identity matches the predecessor; its eight portable regression cases passed.

## Preserved validation evidence

`Docs/validation-20260925.json` indexes the six passed gameplay/inspection reports and three successful staging reports with SHA-256 hashes, scope and case names. Exact copies were archived under `.local/validation-archive/20260925-095807-311-9021b040e74d41138a9cabce6a04adb3/` before writing the index. The archive uses a unique directory and read-only files; future test runs may overwrite the original rolling paths without replacing these copies. The archive remains local and ignored by Git; the compact hash/case index is tracked.

## Package acceptance and promotion — pending

The enlarged-arena candidate `.local/PackageWork/Development-20260925-055521-668/package-result.json` finished successfully with AutomationTool exit code 0. It includes regulation, Redrock and Redwoods. Both candidate loopback checks passed, limited to connection/join/map travel; visual review is underway. The user then requested player textures/skins, so this candidate may be superseded by a build containing those changes.

Final visual acceptance and desktop promotion must identify the newest accepted candidate after the player materials are included. Record that manifest, corresponding network/visual receipt paths and promotion receipt here when complete. The desktop pointer has not been changed as part of this evidence archive.

## Next safe milestone

Finish the player materials, build a new candidate with `Package.ps1 -NoPromote`, record candidate-specific gameplay and visual acceptance, then promote using `Tools/Promote-Package.ps1`. Its 12 isolated file-only tests passed; it validates candidate-specific evidence, keeps the previous launcher pointer, and replaces it atomically. The preserved gameplay checks above precede the player-material changes; do not label them as testing a later package.

Continue complete regulation, remaining spellwork, multiplayer, native Hogwarts broom/menu/match integration and final art after the enlarged arena is playable. Standalone UE5 evidence does not establish native Creator Kit integration. Save checkpoints with explicit test scope, limitations and package status; keep videos, generated builds and private local reports outside Git.

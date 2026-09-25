# Development checkpoint — 2026-09-25

Resumed on `sprint-4-art-gphx` at `409d22e` (merge of pull request #13 from `sprint-3-debugging`). The working tree was clean at the initial recovery inspection. The user requested continued development and another arena enlargement, described as “double the size.” An optional clarification was offered; work proceeded with the stated assumption of twice September 16's floor area at fixed height and aspect ratio. This is a second amendment, not a rerun of September 16's enlargement.

## Recovered checkpoint

The September 16 candidate remains on disk and its packaging log records success. All five report hashes and case lists in `Docs/validation-20260916.json` match their local evidence: 19 controller, 11 flight, 20 spell cases in each match mode and 22 portable flight policy cases. Arena and environment staging success hashes also match. See `Docs/development-checkpoint-20260916.md` for the recovered packaging/network evidence and its limits.

Candidate manifest: `.local/PackageWork/Development-20260916-035952-025/package-result.json`.

Candidate executable: `.local/Build/Development-20260916-035952-025/Windows/BasketbroomDev.exe`.

The desktop launcher still selects `.local/Build/Development-20260915-081623-488/Windows/BasketbroomDev.exe`. Neither the candidate nor the package pointer was changed during recovery. Two preserved candidate loopback tests prove connection, join and map travel only; they do not certify gameplay replication or Bloodbroom activation. Prior visual observations were recovered from session notes, with startup logs still present, but a separate persisted visual acceptance receipt was not found.

## Saved enlargement and builds

All four UE5 arenas were amended, saved and reloaded with exact preservation and collision checks: `.local/arena-expansion-stage/20260925-093616-657683-2932e724/results.json`. Both scenery variants were restaged with zero source-geometry intrusions and preserved sporting actors: `.local/environment-stage/20260925-093719-049631-8f07149f/result.json`.

Both native Creator Kit maps are also enlarged, saved and reloaded: `.local/hlck/arena-resize-stage/20260925-094124-611556-dc696f76/result.json`. Native staging preserves current materials and non-target actors. It changes only two owned maps and ten original mesh assets; installed game maps, databases and dungeon registration remain unchanged. An initial preflight rejected unchanged meshes' historical LF/CRLF source hashes. The correction requires the exact pinned historical provenance and verifies both byte forms; changed meshes retain strict revision hashes.

The UE5.8.1 editor and game builds succeeded (`.local/ue5/build-20260925.log`, `.local/ue5/game-build-20260925.log`). Portable checks passed: 55 rules, 23 resize and 13 environment cases. All 11 real-input flight checks passed in enlarged Redrock, including real goal/Bludger charge, L2 brake, R2 acceleration/boost, inversion and pause. Two earlier attempts lost viewport focus; a bounded operator focus grace period allowed the test to run without bypassing gameplay input guards. A new package is pending and the desktop pointer has not changed.

## Next safe milestone

Finish real scoring, roof and both-mode checks in the enlarged arena. Build a new candidate with `Package.ps1 -NoPromote`, record gameplay and visual acceptance, then promote using `Tools/Promote-Package.ps1`. Its 12 isolated file-only tests passed; it validates candidate-specific evidence, keeps the previous launcher pointer, and replaces it atomically.

Continue complete regulation, remaining spellwork, multiplayer, native Hogwarts broom/menu/match integration and final art after the enlarged arena is playable. Standalone UE5 evidence does not establish native Creator Kit integration. Save checkpoints with explicit test scope, limitations and package status; keep videos, generated builds and private local reports outside Git.

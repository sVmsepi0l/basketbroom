# Playable training build validation

Validated locally on 2026-09-10 with Unreal Engine 5.8.1, Windows 11.

- 54 Python rule-reference tests passed. These exercise the separate rules
  kernel, including rules not yet implemented in the playable training game.
- 15 Play In Editor gameplay checks passed: playable pawn, clock, scoring in
  both directions, ball/hoop matching, rim clearance, rebounds, No Crown,
  chase-ball movement and timeout, and match expiry.
- 15 Play In Editor AI checks passed: roster and references, autonomous
  possession and scoring, isolated Quaffle and Quark shooting cycles,
  protection of human-held possession, and stopping at match end.
- 4 flight checks passed after saving, unloading and reloading the arena:
  clear spawn/corridors, correct actual spawn, horizontal movement, and
  vertical movement with native collision enabled.
- The complete seven-stage authoring pipeline completed successfully.
- Win64 Development cooking, staging, packaging and archiving succeeded.
  The packaged executable was launched through Play.ps1 and displayed a live
  scrimmage independently of Unreal Editor.
- Interactive input checks verified E pickup, mouse aiming, mouse throwing,
  and a 13-point Quaffle goal. The HUD and arena were visually inspected.

Tests run against PIE copies and stop or restore those copies. They do not
assign scores during observed AI shot cycles. Flight tests inject native pawn
movement input; physical keyboard timing and flight feel still need human
playtesting. Audio assets and Blueprint event wiring were built, but the mix
has not undergone a listening session. Chase capture difficulty and match
balance also need playtesting.

The test reports in `.local/` describe individual runs and are regenerated.
This record is a milestone check, not a guarantee for later edits. Re-run
`test_playable.py`, `test_bots.py` and `test_flight.py` in the editor after
rebuilding. Read README.md for the implemented scope and remaining features.

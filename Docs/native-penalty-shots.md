# Free shots and Serious penalty shots — Basketbroom and Bloodbroom

Both variants share the same host-selected Serious remedy: a penalty shot plus
three minutes of live-time removal. Bloodbroom still waives only Unforgivables
and headshots; it retains double-taps, mobbing, holding and the shared sporting
rules. This feature does not choose automatic severity tiers for those fouls.

## Playtest controls and sequence

After an applied illegal spell hit creates the referee stoppage, the host can
select **F6: Moderate free shot**, **F7: possession**, **F8: Serious shot plus
removal**, or **F9: ejection**. With a controller, D-pad Left/Up/Right/Down selects
those choices; Menu confirms. Clients cannot select the match variant or serve
the referee's decision. Sprint 3's final native/package validation is pending
its [handoff receipt](sprint-3-spells-graphics.md); the dated results below remain
historical Serious-shot evidence.

F8 reserves a scoring ball and begins a five-second attempt. A denied Quaffle or
Quark chance retains its ball type; otherwise the default is the Quaffle. A
second Quark can supply the same type if the first has a prior remedy, but the
adapter never substitutes a different point value merely to force a shot.
Existing goal and conduct reservations retain priority.

The harmed rider is preferred when legally eligible to handle that ball.
Otherwise the adapter selects an eligible teammate, preferring a human. The
shooter starts at the central 44-foot mark, aligned with the relevant hoop; the
opposing Netminder alone can defend. Other riders are temporarily parked out of
the lane and returned after the attempt. The shot uses actual native flight,
whole-ball hoop geometry, rim collision and a sweep against the keeper capsule.

The shooter aims and throws once with the ordinary throw control. The shooter
stays at the mark; the keeper can move across the goal area. No wandwork, pass,
second attempt, team/position change or global resume is accepted during the
attempt. CPU participants use a small shot/defense routine. Its decisions are
provisional playtest behavior, not final competitive AI.

The five seconds include ball flight. A make awards the ordinary **13 or 37**
points once. A save, missed goal/end boundary, floor/net contact or expiry ends
the attempt without points. The [pyramid roof net](pyramid-net.md) is a net-contact miss; crossing its former 138-foot eave plane alone leaves the attempt live. Rim deflection remains part of that same flight.
After the short result hold, the defending Netminder receives actual protected
custody before the penalty is marked served. The match stays stopped until the
host resumes it, unless the shot has caused a result review.

The main match clock, ball release/return clocks, spell effects and removal
clock all remain frozen during the attempt. Participant shot controls temporarily
operate despite frozen combat disables; the underlying effect timers are not
cleared or shortened. The offender remains unavailable during removal and cannot
escape it by changing positions. Removal resumes with live play. In Donnybrook,
this remedy uses a Quark and removal becomes phase exclusion.

## Moderate free shots added in sprint 3

F6 reserves one restorative free shot with **no new removal**. It retains the
affected Quaffle/Quark type; otherwise the default is the Quaffle, or a Quark in
Donnybrook. Existing goal/remedy reservations keep priority. The harmed eligible
rider is preferred, with an eligible teammate as fallback. A keeper responsible
for the Moderate foul may still defend; Donnybrook permits an eligible designated
goal defender because positional restrictions are suspended.

The user confirmed on September 14, 2026 that the minimum **44-foot** placement
is measured along pitch **X** from the attacking goal plane. Move backward only
when needed, preserving the actual foul's **Y and Z**. Nonkeeper defenders remain
at least **22 feet** from the shooter until release. The original foul point is
stored separately from the older possession-award clamps.

The adapter currently reuses the stopped **five-second** single-attempt procedure,
keeper defense, no wandwork/pass/second attempt, frozen effect clocks and actual
protected defending restart described above. Other participants remain unable to
move throughout it. **These free-shot timing and administration restrictions are
prototype choices, not additions declared canonical in the v0.1 bible.**
The user's X-only placement interpretation is separate from those choices. A
single penalty cannot reserve both a free shot and a possession award in either
ordering direction. Moderate and Serious remedies keep distinct removal state.

## Scope and remaining work

For Serious penalties, the 44-foot mark, five-second attempt and three-minute
removal are existing provisional alpha defaults from the design reference. Goal-area movement limits,
CPU shot selection, keeper reaction speed and result-display time need playtesting.

Host-selected Moderate free shots and the Serious path are implemented in source.
Pre-termination remedies can now run during Snitch, regulation-horn, overtime-
margin and overtime-horn review, with the original event and clock preserved;
see [post-termination restitution](native-restitution.md) for scope and evidence.
The native source now includes a narrow host-selected F10 Moderate advantage
route to retain an actual pre-ending foul; its native gameplay acceptance is
still pending and must not be inferred from the portable results.
Automatic escalation, comprehensive contact detection, unavailable-Netminder
replacement decisions and Catastrophic adjudication remain separate work. A
terminal Donnybrook conflict or unavailable defending Netminder is rejected
without clearing the owed remedy. Generic portable
`resolve_penalty` remains an external-official API for unreserved penalties;
the native adapter does not auto-dismiss Serious penalties.

## Reproduction and evidence

`Tools/test_native_penalty_shots.py` exercises the portable state machine.
`Tools/test_native_penalty_shots_playable.py` runs native make/miss/timeout cases
in fresh PIE sessions for both variants. `Tools/test_native_penalty_shots_network.py`
uses distinct listen-server/client worlds. The native fixtures send ordinary
guarded action requests; physical staging is recorded separately from actual
custody, hit, goal, penalty and restart outcomes.

Local results live under `.local/native-penalty-*`. Their timestamps and binary
provenance identify each run; prior controller/wandplay counts are historical
milestones and should not be silently added to a new total.

### 2026/09/14 native validation

The penalty implementation build succeeded under UE 5.8.1. Its runtime DLL SHA-256 is
`d4d79e306b7a966178032e6887c1189aec4f9006cb3de14e1763bc71e2df9f61`.
The following bounded runs have no failed or skipped checks:

- **104 gameplay checks:** both modes, a Quaffle make, Quark make, Quark miss and
  Quaffle timeout in each; `.local/penalty-validation-matrix-20260914-142949/`.
- **60 edge/lifecycle checks:** native full-ball crossing before, exactly at and
  after the deadline; admission during the attempt; real shooter and keeper
  replacement; `.local/penalty-validation-edges-20260914-143206/`. These deadline
  cases explicitly arrange a free ball after its real release. Exact expiry
  produces a timeout; only a crossing before expiry scores.
- **20 penalty-network checks:** an owning client takes a real Quark shot in
  each mode; host-only decisions, frozen clocks, score and protected restart
  replicate; `.local/penalty-validation-network-20260914-142509/`.
- **27 existing network regressions:** role/match and spell/BB-0 replication;
  `.local/penalty-validation-network_regressions-20260914-142636/`.

The network fixtures use two actual local PIE worlds. Because this installed
engine omits Python's Play Net Mode enum, the ordinary saved editor setting was
backed up, changed with the editor closed, loaded for the test, and restored to
Standalone afterward. Reports use `settings_source="editor_config"`; this is
separate from screen automation. No firewall or account setting was changed.

An earlier build of the same gameplay code, before the final result-message-only
change, also passed **73 existing gameplay/controller/spell checks** (35 + 18 +
17 regulation + 3 Bloodbroom); `.local/penalty-validation-solo-20260914-141926/`.
Portable MSVC `/W4 /WX` checks passed **35 new shot scenarios**, **68 existing
rules scenarios** and **24 conduct-award scenarios**. These are overlapping
bounded checks, not a count of unique features or complete regulation coverage.

The first boundary run exposed a test assertion that required the first frame
to straddle the entire remaining clock. Native scoring was correct; the fixture
now checks the observed remaining time before each actual frame. A subsequent
concurrent report-read race was corrected with atomic publication of fully
enriched JSON receipts. The final 104/60 results use that corrected protocol;
earlier failed receipts remain preserved. Five receipt I/O fault checks also
passed. Actual ready/result HUD captures were reviewed, including the visible
Bloodbroom label, correct score and defending-restart message.

Native terminal OT/Donnybrook shot transitions are covered in the portable
engine tests; their full rendered native match sequence is not yet separately
verified. Physical controller testing and separate-machine networking remain
outside these automated runs.

### Packaged build and lifecycle follow-up

`Development-20260914-144048-436` completed with AutomationTool exit 0 in 28.19
seconds. `Play.ps1` and the existing desktop shortcut select this local package;
`Bloodbroom.cmd` selects Bloodbroom practice. The two-process loopback checks
passed in both launch variants. They prove connection and map travel, not
remote multiplayer or packaged penalty interactions; their receipts are
`.local/packaged-network/20260914-144430-122-59f7bd1c/result.json` and
`.local/packaged-network/20260914-144451-137-50209fb5/result.json`.

A rendered shutdown check exposed replacement spawning after `BeginTearingDown`.
`BBGameMode::Logout` now keeps ordinary departure cleanup but skips replacement
spawns once the world is tearing down. The rebuilt editor DLL SHA-256 is
`776394362fca494dfe30bf45e4cbb7673eefa8a7e8145cd205c5a6b590795b8d`.
Both actual participant-replacement cases passed again (20 checks) on this
build; `.local/penalty-validation-lifecycle-20260914-144332/`.

A separate test-harness process-start race was fixed by retaining the original
creation handle and waiting for executable/start-time metadata. Cleanup never
selects a process by name. Nine identity-failure checks and 15 launch-plan
checks passed before the real packaged loopback reruns. Old failed receipts
and the exact abandoned-server cleanup receipt are retained.

The final ordinary-renderer startup check passed in **both modes**: actual
1600x900 screenshots showed the correct variant, arena and roster HUD, with
no engine errors and natural process exit 0. The reviewed receipt is
`.local/packaged-plain-visual-20260914-145237/result.json`. This verifies startup
and rendering, not a new physical-input or packaged-shot playtest. The screen
control helper was unavailable; no new USB/Bluetooth hardware claim is made.

Optional CSV-based capture instrumentation reproduced late process exit 777003
(Unreal's crash-reporting-thread exception code), even though its screenshots
were written and the game log closed normally. Removing only `-NOINI` did not
resolve it. Ordinary rendering, single startup screenshots and timed exit pass
without CSV instrumentation. Those failed diagnostic runs are preserved rather
than reclassified as successful. This remains a limitation of that diagnostic
path; no production crash-report setting was disabled. The completed promotional
video and its existing capture pipeline were not changed.

The consolidated local milestone receipt is `.local/penalty-milestone-final.json`.

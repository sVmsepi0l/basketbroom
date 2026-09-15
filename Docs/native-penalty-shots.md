# free shots and serious penalty shots — basketbroom and bloodbroom

both variants share the same host-selected serious remedy: a penalty shot plus
three minutes of live-time removal. bloodbroom still waives only unforgivables
and headshots; it retains double-taps, mobbing, holding and the shared sporting
rules. this feature does not choose automatic severity tiers for those fouls.

## playtest controls and sequence

after an applied illegal spell hit creates the referee stoppage, the host can
select **F6: moderate free shot**, **F7: possession**, **F8: serious shot plus
removal**, or **F9: ejection**. with a controller, d-pad Left/Up/Right/Down selects
those choices; menu confirms. clients cannot select the match variant or serve
the referee's decision. sprint 3's final native/package validation is pending
its [handoff receipt](sprint-3-spells-graphics.md); the dated results below remain
historical serious-shot evidence.

f8 reserves a scoring ball and begins a five-second attempt. a denied quaffle or
quark chance retains its ball type; otherwise the default is the Quaffle. a
second quark can supply the same type if the first has a prior remedy, but the
adapter never substitutes a different point value merely to force a shot.
existing goal and conduct reservations retain priority.

the harmed rider is preferred when legally eligible to handle that ball.
otherwise the adapter selects an eligible teammate, preferring a human. the
shooter starts at the central 44-foot mark, aligned with the relevant hoop; the
opposing netminder alone can defend. other riders are temporarily parked out of
the lane and returned after the attempt. the shot uses actual native flight,
whole-ball hoop geometry, rim collision and a sweep against the keeper capsule.

the shooter aims and throws once with the ordinary throw control. the shooter
stays at the mark; the keeper can move across the goal area. no wandwork, pass,
second attempt, team/position change or global resume is accepted during the
attempt. cpu participants use a small shot/defense routine. its decisions are
provisional playtest behavior, not final competitive AI.

the five seconds include ball flight. a make awards the ordinary **13 or 37**
points once. a save, missed goal/end boundary, floor/net contact or expiry ends
the attempt without points. the [pyramid roof net](pyramid-net.md) is a net-contact miss; crossing its former 138-foot eave plane alone leaves the attempt live. rim deflection remains part of that same flight.
after the short result hold, the defending netminder receives actual protected
custody before the penalty is marked served. the match stays stopped until the
host resumes it, unless the shot has caused a result review.

the main match clock, ball release/return clocks, spell effects and removal
clock all remain frozen during the attempt. participant shot controls temporarily
operate despite frozen combat disables; the underlying effect timers are not
cleared or shortened. the offender remains unavailable during removal and cannot
escape it by changing positions. removal resumes with live play. in donnybrook,
this remedy uses a quark and removal becomes phase exclusion.

## moderate free shots added in sprint 3

f6 reserves one restorative free shot with **no new removal**. it retains the
affected Quaffle/Quark type; otherwise the default is the quaffle, or a quark in
Donnybrook. existing goal/remedy reservations keep priority. the harmed eligible
rider is preferred, with an eligible teammate as fallback. a keeper responsible
for the moderate foul may still defend; donnybrook permits an eligible designated
goal defender because positional restrictions are suspended.

the user confirmed on september 14, 2026 that the minimum **44-foot** placement
is measured along pitch **x** from the attacking goal plane. move backward only
when needed, preserving the actual foul's **y and Z**. nonkeeper defenders remain
at least **22 feet** from the shooter until release. the original foul point is
stored separately from the older possession-award clamps.

the adapter currently reuses the stopped **five-second** single-attempt procedure,
keeper defense, no wandwork/pass/second attempt, frozen effect clocks and actual
protected defending restart described above. other participants remain unable to
move throughout it. **these free-shot timing and administration restrictions are
prototype choices, not additions declared canonical in the v0.1 bible.**
the user's x-only placement interpretation is separate from those choices. a
single penalty cannot reserve both a free shot and a possession award in either
ordering direction. moderate and serious remedies keep distinct removal state.

## scope and remaining work

for serious penalties, the 44-foot mark, five-second attempt and three-minute
removal are existing provisional alpha defaults from the design reference. goal-area movement limits,
cpu shot selection, keeper reaction speed and result-display time need playtesting.

host-selected moderate free shots and the serious path are implemented in source.
pre-termination remedies can now run during snitch, regulation-horn, overtime-
margin and overtime-horn review, with the original event and clock preserved;
see [post-termination restitution](native-restitution.md) for scope and evidence.
the native source now includes a narrow host-selected f10 moderate advantage
route to retain an actual pre-ending foul; its native gameplay acceptance is
still pending and must not be inferred from the portable results.
automatic escalation, comprehensive contact detection, unavailable-netminder
replacement decisions and catastrophic adjudication remain separate work. a
terminal donnybrook conflict or unavailable defending netminder is rejected
without clearing the owed remedy. generic portable
`resolve_penalty` remains an external-official api for unreserved penalties;
the native adapter does not auto-dismiss serious penalties.

## reproduction and evidence

`Tools/test_native_penalty_shots.py` exercises the portable state machine.
`Tools/test_native_penalty_shots_playable.py` runs native make/miss/timeout cases
in fresh pie sessions for both variants. `Tools/test_native_penalty_shots_network.py`
uses distinct listen-server/client worlds. the native fixtures send ordinary
guarded action requests; physical staging is recorded separately from actual
custody, hit, goal, penalty and restart outcomes.

local results live under `.local/native-penalty-*`. their timestamps and binary
provenance identify each run; prior controller/wandplay counts are historical
milestones and should not be silently added to a new total.

### 2026/09/14 native validation

the penalty implementation build succeeded under ue 5.8.1. its runtime dll sha-256 is
`d4d79e306b7a966178032e6887c1189aec4f9006cb3de14e1763bc71e2df9f61`.
the following bounded runs have no failed or skipped checks:

- **104 gameplay checks:** both modes, a quaffle make, quark make, quark miss and
  quaffle timeout in each; `.local/penalty-validation-matrix-20260914-142949/`.
- **60 edge/lifecycle checks:** native full-ball crossing before, exactly at and
  after the deadline; admission during the attempt; real shooter and keeper
  replacement; `.local/penalty-validation-edges-20260914-143206/`. these deadline
  cases explicitly arrange a free ball after its real release. exact expiry
  produces a timeout; only a crossing before expiry scores.
- **20 penalty-network checks:** an owning client takes a real quark shot in
  each mode; host-only decisions, frozen clocks, score and protected restart
  replicate; `.local/penalty-validation-network-20260914-142509/`.
- **27 existing network regressions:** role/match and spell/BB-0 replication;
  `.local/penalty-validation-network_regressions-20260914-142636/`.

the network fixtures use two actual local pie worlds. because this installed
engine omits python's play net mode enum, the ordinary saved editor setting was
backed up, changed with the editor closed, loaded for the test, and restored to
standalone afterward. reports use `settings_source="editor_config"`; this is
separate from screen automation. no firewall or account setting was changed.

an earlier build of the same gameplay code, before the final result-message-only
change, also passed **73 existing gameplay/controller/spell checks** (35 + 18 +
17 regulation + 3 bloodbroom); `.local/penalty-validation-solo-20260914-141926/`.
portable msvc `/W4 /WX` checks passed **35 new shot scenarios**, **68 existing
rules scenarios** and **24 conduct-award scenarios**. these are overlapping
bounded checks, not a count of unique features or complete regulation coverage.

the first boundary run exposed a test assertion that required the first frame
to straddle the entire remaining clock. native scoring was correct; the fixture
now checks the observed remaining time before each actual frame. a subsequent
concurrent report-read race was corrected with atomic publication of fully
enriched json receipts. the final 104/60 results use that corrected protocol;
earlier failed receipts remain preserved. five receipt I/O fault checks also
passed. actual ready/result hud captures were reviewed, including the visible
bloodbroom label, correct score and defending-restart message.

native terminal OT/Donnybrook shot transitions are covered in the portable
engine tests; their full rendered native match sequence is not yet separately
verified. physical controller testing and separate-machine networking remain
outside these automated runs.

### packaged build and lifecycle follow-up

`development-20260914-144048-436` completed with automationtool exit 0 in 28.19
seconds. `Play.ps1` and the existing desktop shortcut select this local package;
`Bloodbroom.cmd` selects bloodbroom practice. the two-process loopback checks
passed in both launch variants. they prove connection and map travel, not
remote multiplayer or packaged penalty interactions; their receipts are
`.local/packaged-network/20260914-144430-122-59f7bd1c/result.json` and
`.local/packaged-network/20260914-144451-137-50209fb5/result.json`.

a rendered shutdown check exposed replacement spawning after `BeginTearingDown`.
`BBGameMode::Logout` now keeps ordinary departure cleanup but skips replacement
spawns once the world is tearing down. the rebuilt editor dll sha-256 is
`776394362fca494dfe30bf45e4cbb7673eefa8a7e8145cd205c5a6b590795b8d`.
both actual participant-replacement cases passed again (20 checks) on this
build; `.local/penalty-validation-lifecycle-20260914-144332/`.

a separate test-harness process-start race was fixed by retaining the original
creation handle and waiting for executable/start-time metadata. cleanup never
selects a process by name. nine identity-failure checks and 15 launch-plan
checks passed before the real packaged loopback reruns. old failed receipts
and the exact abandoned-server cleanup receipt are retained.

the final ordinary-renderer startup check passed in **both modes**: actual
1600x900 screenshots showed the correct variant, arena and roster hud, with
no engine errors and natural process exit 0. the reviewed receipt is
`.local/packaged-plain-visual-20260914-145237/result.json`. this verifies startup
and rendering, not a new physical-input or packaged-shot playtest. the screen
control helper was unavailable; no new USB/Bluetooth hardware claim is made.

optional csv-based capture instrumentation reproduced late process exit 777003
(unreal's crash-reporting-thread exception code), even though its screenshots
were written and the game log closed normally. removing only `-noini` did not
resolve it. ordinary rendering, single startup screenshots and timed exit pass
without csv instrumentation. those failed diagnostic runs are preserved rather
than reclassified as successful. this remains a limitation of that diagnostic
path; no production crash-report setting was disabled. the completed promotional
video and its existing capture pipeline were not changed.

the consolidated local milestone receipt is `.local/penalty-milestone-final.json`.

# Basketbroom rules reference

This is an engine-independent executable reference for the supplied development
draft, not an embedded Python dependency for Hogwarts Legacy. Port these state
transitions into authoritative Creator Kit Blueprints. Use the tests as acceptance
cases. Geometry, scores and timings come from `alpha_rules.json`; the unchanged
source is `../Docs/basketbroom_rules_bible_v0.1.md`.

## Run

From the repository root with Python 3.10 or later (standard library only):

```powershell
python -m unittest discover -s Rules -v
python -m Rules.replay Rules/examples/simultaneous_snitch.json
```

On this workstation, if `python` resolves to the Windows Store alias, substitute:

```powershell
& 'C:\Users\bigdi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s Rules -v
```

## Authority contract

- Every time value is an integer number of **live milliseconds**, accumulated
  from the opening horn. A global pause, break or review consumes no live time.
  Pass scaled elapsed time for a faster playtest; canonical JSON durations stay
  44 minutes per quarter and 22 minutes for overtime.
- Construct `Match()` to open regulation with sixteen correctly distributed
  riders and six live balls. `snitch` is active but dead until its scheduled
  22-minute release. Ball IDs are `quaffle`, `quark_1`, `quark_2`, `snipe`,
  `snitch`, `bludger_1`, `bludger_2`; team IDs are `A` and `B`.
- Submit complete same-timestamp groups with `process_batch(at_ms, events)`.
  Never submit simultaneous scores in separate calls. Submit all earlier point
  events before `advance(delta_ms)`. The host chooses one stable timestamp
  resolution; this reference does not impose physics substep size.
- Goal events identify the **team attacking the crossed goal**, independent of
  the last toucher. Required evidence is `entire_ball: true` and `forward: true`.
  Only the proper hoop and physical traversal score. Wrong hoops stay live.
- Catch events identify the player and provide `secure_ms`, `by_hand`, `mounted`,
  and `inside_envelope`. A host must establish those facts continuously from
  authoritative simulation. Client-reported booleans are not sufficient.
- `advance` stops at the first global stoppage/horn and returns consumed time.
  Do not discard its return value when implementing a wall-clock accumulator.
  At a horn's exact timestamp, a goal is too late. A failed `process_batch`
  rolls back the entire command, including its attempted time advance.
- Endings enter `status: review`. Resolve pending penalties and call `certify()`
  before showing a winner. Certified pre-termination score adjustments can
  change the winner, enter overtime/Donnybrook, or resume overtime below 150.
  Adjustments are official corrections/remedies, never ordinary scoring input.
- Quarter and phase transitions wait for `resume()`. A pending penalty blocks
  the next horn. Donnybrook neutralizes opposing simultaneous winning events
  and resets all three surviving balls.
- `snapshot()` returns detached JSON-ready state for seven-ball UI, possession,
  timers, score, phase, penalties, and provisional/certified outcomes.
  `log` is an append-only sequence of deterministic events with live timestamps.

### Point event example

```python
from Rules import Match

match = Match()
match.process_batch(1000, [
    {"kind": "goal", "ball": "quaffle", "attacking_team": "A",
     "hoop": "large", "entire_ball": True, "forward": True},
    {"kind": "goal", "ball": "quark_1", "attacking_team": "B",
     "hoop": "small", "entire_ball": True, "forward": True},
])
assert match.snapshot()["scores"] == {"A": 13, "B": 37}
```

## Other host commands

`possess` / `release` validate role authority and one-ball limits. Bludger
possession requires `inspected_hurley=True`; short self-tosses retain the original
individual clock, and passes retain cumulative team control. `flight_evidence`
and `opponent_challenge` certify reset conditions; the host must distinguish
contestable flight from private banks. The individual timer warns at two seconds
and faults at three; team secured possession faults at six. Routine strike/tip
contacts below 0.5 seconds should never call `possess`.

`crown_exit(ball, mark, responsible_player)` records a mark in feet, makes only
that non-winged ball dead, and records a pending sanction. Call `crown_return`
when the host has performed a safe neutral re-entry. Missing the three-second
target triggers a safety stoppage. `recall_chase` performs a neutral winged-ball
envelope recall without points or a No Crown penalty.

`restart` awards a scored ball to the defending Netminder and exposes a
three-second protected interval. The host enforces geometry and the 13-foot
exclusion. A Netminder holding another ball must release it first. Bludger
restarts are free-flight releases to the eligible opposing Hurleyback.

`record_penalty`, `resolve_penalty`, `pause`, `resume`, `certify`, and
`overturn_snitch` provide an explicit officiating path. Penalty dispositions are
logged; Serious removal and Severe ejection cannot be declined. The reference
does not choose an official's judgment or invent automatic chase-catch points.

## Implemented and intentionally outside the reference

Covered by executable tests: canonical values; opening schedule; all score
types; role and possession limits; one-second catch evidence; Snipe cycling and
pause semantics; regulation, overtime, Donnybrook and certification; exact horn
ordering; simultaneous goal/catch outcomes; losing Reckoner; No Crown delayed
penalties; Hurley individual/team clocks and laundering cases; replay and clock
chunk independence.

The engine adapter still owns continuous geometry, collision/ball identity,
flight physics, capture evidence, safe launches/restarts, player return through
the gate, substitutions and ejection replacements, equipment inspection,
foul judgment/escalation, free/penalty-shot simulation, wandplay, and networking.
Removal expiry clears rule ineligibility; the adapter must additionally require
the official return signal and gate. Catastrophic forfeit decisions deliberately
require external adjudication. The source's inherited BB-0 movement/contact/hit
rules were not supplied and are not silently represented as implemented here.

Every provisional value remains explicitly marked `needs_playtest` in JSON.
No generic renderer or tabletop recommendation in the source overrides the
user's request to build a functioning Creator Kit mod.

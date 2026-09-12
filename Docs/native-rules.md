# Native regulation rules

`DevelopmentHarness/Source/BasketbroomRuntime/BBRuleEngine.h` and `.cpp` implement the deterministic regulation engine in standard C++17. They have no Unreal dependencies, network transport, runtime Python, or exception-based error handling. This is a port of `Rules/basketbroom.py`; it does not claim that the game scene already invokes every rule.

## Authority API

Create a `BB::Match` on the authoritative game instance. Call its methods with verified observations; replicate a presentation of its public state to clients. Client input is a request, not permission to set scores or certify a catch. Public fields support inspection and controlled tests; gameplay should mutate them through the commands. Do not change `config`, roster, or clock fields during a running match.

- Teams are `0` and `1`. Player slots `0..7` and `8..15` each contain Netminder, Chaser, Chaser, Trapper, Ranger, Hurleyback, Hurleyback, Scout. `Role` values are `0..5` in that order. `configure_roster` validates the eight-role distribution before play.
- Balls are `0` Quaffle, `1/2` Quarks, `3` Snipe, `4` Snitch, `5/6` Bludgers. Absent player/team references and unset deadlines use `-1`.
- Commands return `bool` and put a rejection explanation in `last_error`. `record_penalty` returns a positive ID or `-1`; `advance` returns consumed live milliseconds or `-1`. `certify` returns success, and the resulting `winner` is read from state. A successful certification may start overtime rather than finish the match.
- `PointEvent` defaults all required evidence to false. Fill `Goal` evidence (`attacking_team`, matching `hoop`, `entire_ball`, `forward`, `teleported`) or `Catch` evidence (`player`, `secure_ms`, `by_hand`, `mounted`, `inside_envelope`). `process_batch(at_ms, events)` applies simultaneous point events atomically, including clock advancement and the audit log. Rejected batches leave state unchanged except `last_error`.
- Use cumulative integer **live** milliseconds. Submit all completed point events at a timestamp together, before advancing beyond them. The exact horn wins over an event at that timestamp. `advance` stops at stoppages, so a caller must use its returned consumption rather than assume an entire frame delta elapsed. A stopped match consumes zero live time. The input adapter must reject fractional/invalid external timestamps before converting them to the C++ integer type.

## Implemented behavior

The default `Config` matches the adjudication constants in `Rules/alpha_rules.json`: four 44-minute quarters; 22-minute overtime and Snitch release; 13/37/69-point scoring; 150/300-point Snitch catches; and the 150-point termination margins. Own goals credit the supplied attacking direction. Both Quarks and the Quaffle resolve independently, with defending-Netminder protected restarts.

Eligibility, single scoring-ball possession, inspected Hurleys, one Bludger per Hurleyback, Ranger capture restrictions, and the one-second secure chase catch are enforced. The Snipe times out for three live minutes with a ten-second warning. Global stoppages freeze these clocks; quarter breaks preserve the timeout, while a new phase resets it.

Hurley control includes the two-second warning, three-second individual limit, six-second cumulative team relay limit, ten-foot individual self-toss reset, contestable-flight reset, private-bank rejection, and opponent challenges. Individual and team clocks are separate. No Crown kills only the affected non-winged ball, preserves its return mark, supports neutral return, retains delayed discipline, and stops play if the three-second return target is missed.

Final calls enter review, and pending pre-termination penalties block certification. Audited integer score adjustments can change a winner or undo an overtime threshold. A Snitch catcher may lose; an exact tie favors the catching team, and only a Scout earns the Reckoner. Overturned Snitch catches preserve other simultaneous points. Donnybrook retains only the two Quarks and Snipe, suspends position restrictions, excludes players with unexpired removals, and voids opposing simultaneous winning events.

Penalty records support minor, moderate, serious, severe, and catastrophic conduct. Serious conduct pauses play and applies a timed removal at adjudication; severe conduct ejects. Neither removal nor ejection can be declined. A serious removal during Donnybrook becomes exclusion for that phase.

## Verification

Run `python Tools/test_native_rules.py --compiler <compiler>` with `g++`, `clang++`, or MSVC available. On Windows, `--vcvars <vcvars64.bat>` loads the compiler environment only into the test child process. `--emit-only` generates a driver and explicitly reports `not_run`.

The harness contains **60 native scenarios**: one port of each of the 54 Python reference scenarios, plus six checks for zero-index player control, double chase capture, atomic correction validation, severe/catastrophic discipline, invalid indices/nonfinite evidence, and integer overflow. Clock chunking and repeated replay compare the complete public state and event payloads. Temporary sources, binaries, compilation output, and results are written under `.local/native-rules`.

On 2026-09-10, the suite compiled with the locally bundled GCC using C++17, warnings as errors, and exceptions disabled; **60/60 passed**. The compiler is at `C:/Program Files/HogwartsLegacyCreatorKit/Engine/Binaries/ThirdParty/perl/c/bin/g++.exe`. This validates portable rules behavior; it does not substitute for the Unreal module build, replicated gameplay, or packaged-game integration tests.

## Explicit limits

Geometry, collisions, flight, envelope membership, continuous secure-control evidence, credible player challenges, inspected equipment, and simultaneous event grouping are certified by the authoritative gameplay adapter. Geometry constants other than the self-toss distance remain in the shared rules data and are not duplicated in this non-physics engine. The C++ default configuration is explicit; it does not parse JSON automatically.

As in the reference, penalties require a human/host adjudication description. Free-shot execution, restitution choices, substitutions/ejection replacement timing, and catastrophic forfeiture adjudication are not automated. Catastrophic penalties remain pending and block resumption/certification until a separate adjudication mechanism exists. The rules engine has no match-server discovery, persistence, authentication, or anti-cheat transport.

`LogEvent` provides stable sequence/time, kind, actor/ball/team, numeric value, reason, and penalty ID. It is a compact native audit record rather than the Python log's nested JSON schema; complete source evidence, crown coordinates, and penalty objects are available in state or must be retained by the adapter. Copying `Match` makes an independent state snapshot; serialization is the adapter's responsibility.

UE 4.27 Creator Kit compatibility of the surrounding gameplay remains separate. Portable C++ source alone does not create a permitted native Hogwarts Legacy mod module or supply its missing multiplayer integration.

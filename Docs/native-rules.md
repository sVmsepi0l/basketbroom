# native regulation rules

`DevelopmentHarness/Source/BasketbroomRuntime/BBRuleEngine.h` and `.cpp` implement the deterministic regulation engine in standard C++17. they have no unreal dependencies, network transport, runtime python, or exception-based error handling. this is a port of `Rules/basketbroom.py`; it does not claim that the game scene already invokes every rule.

## authority api

create a `BB::Match` on the authoritative game instance. call its methods with verified observations; replicate a presentation of its public state to clients. client input is a request, not permission to set scores or certify a catch. public fields support inspection and controlled tests; gameplay should mutate them through the commands. do not change `config`, roster, or clock fields during a running match.

- teams are `0` and `1`. player slots `0..7` and `8..15` each contain netminder, chaser, chaser, trapper, ranger, hurleyback, hurleyback, Scout. `role` values are `0..5` in that order. `configure_roster` validates the eight-role distribution before play.
- balls are `0` quaffle, `1/2` quarks, `3` snipe, `4` snitch, `5/6` Bludgers. absent player/team references and unset deadlines use `-1`.
- commands return `bool` and put a rejection explanation in `last_error`. `record_penalty` returns a positive id or `-1`; `advance` returns consumed live milliseconds or `-1`. `certify` returns success, and the resulting `winner` is read from state. a successful certification may start overtime rather than finish the match.
- `pointevent` defaults all required evidence to false. fill `goal` evidence (`attacking_team`, matching `hoop`, `entire_ball`, `forward`, `teleported`) or `catch` evidence (`player`, `secure_ms`, `by_hand`, `mounted`, `inside_envelope`). `process_batch(at_ms, events)` applies simultaneous point events atomically, including clock advancement and the audit log. rejected batches leave state unchanged except `last_error`.
- use cumulative integer **live** milliseconds. submit all completed point events at a timestamp together, before advancing beyond them. the exact horn wins over an event at that timestamp. `advance` stops at stoppages, so a caller must use its returned consumption rather than assume an entire frame delta elapsed. a stopped match consumes zero live time. the input adapter must reject fractional/invalid external timestamps before converting them to the c++ integer type.

## implemented behavior

the default `config` uses the current closed-roof policy and the adjudication constants in `Rules/alpha_rules.json`: four 44-minute quarters; 22-minute overtime and snitch release; 13/37/69-point scoring; 150/300-point snitch catches; and the 150-point termination margins. own goals credit the supplied attacking direction. both quarks and the quaffle resolve independently, with defending-netminder protected restarts.

eligibility, single scoring-ball possession, inspected hurleys, one bludger per hurleyback, ranger capture restrictions, and the one-second secure chase catch are enforced. the snipe times out for three live minutes with a ten-second warning. global stoppages freeze these clocks; quarter breaks preserve the timeout, while a new phase resets it.

hurley control includes the two-second warning, three-second individual limit, six-second cumulative team relay limit, ten-foot individual self-toss reset, contestable-flight reset, private-bank rejection, and opponent challenges. individual and team clocks are separate. the current arena has a [closed pyramid net](pyramid-net.md): ordinary roof contact rebounds and cannot create a no crown exit, dead ball or return reservation. the portable c++ and python crown apis remain only for historical fixtures that explicitly set `enable_legacy_crown_exit=true`; the default is `false`. native basketbroom and bloodbroom use the closed roof and do not opt into that legacy procedure.

final calls enter review, and pending pre-termination penalties block certification. [post-termination restitution](native-restitution.md) permits a real moderate free shot or serious penalty shot plus defending restart during Snitch/horn/overtime-margin review, before retesting the original ending. audited integer score adjustments can also change a winner or undo an overtime threshold. a snitch catcher may lose; an exact tie favors the catching team, and only a scout earns the Reckoner. overturned snitch catches preserve other simultaneous points. donnybrook retains only the two quarks and snipe, suspends position restrictions, excludes players with unexpired removals, and voids opposing simultaneous winning events.

penalty records support minor, moderate, serious, severe, and catastrophic conduct. serious conduct pauses play and applies a timed removal at adjudication; severe conduct ejects. neither removal nor ejection can be declined. a serious removal during donnybrook becomes exclusion for that phase.

## verification

the 2026/09/14 [pyramid-net amendment](pyramid-net.md) supersedes historical crown assertions. current portable runs explicitly label legacy fixtures; the dated results below are retained as observations of their original builds, not new-roof evidence.

run `python Tools/test_native_rules.py --compiler <compiler>` with `g++`, `clang++`, or msvc available. on windows, `--vcvars <vcvars64.bat>` loads the compiler environment only into the test child process. `--emit-only` generates a driver and explicitly reports `not_run`.

the original 2026/09/10 harness contained **60 native scenarios**: one port of each of the 54 python reference scenarios, plus six checks for zero-index player control, double chase capture, atomic correction validation, severe/catastrophic discipline, invalid indices/nonfinite evidence, and integer overflow. clock chunking and repeated replay compare the complete public state and event payloads. temporary sources, binaries, compilation output, and results are written under `.local/native-rules`.

on 2026/09/10, the suite compiled with the locally bundled gcc using c++17, warnings as errors, and exceptions disabled; **60/60 passed**. the compiler is at `C:/Program Files/HogwartsLegacyCreatorKit/Engine/Binaries/ThirdParty/perl/c/bin/g++.exe`. this validates portable rules behavior; it does not substitute for the unreal module build, replicated gameplay, or packaged-game integration tests.

## explicit limits

geometry, collisions, flight, envelope membership, continuous secure-control evidence, credible player challenges, inspected equipment, and simultaneous event grouping are certified by the authoritative gameplay adapter. geometry constants other than the self-toss distance remain in the shared rules data and are not duplicated in this non-physics engine. the c++ default configuration is explicit; it does not parse json automatically.

as in the reference, penalties require a human/host adjudication description. the [native shot flow](native-penalty-shots.md) implements host-selected moderate free shots and serious penalty shots, including supported provisional-ending review. severity selection, disputed donnybrook terminal restitution, complete substitutions/ejection replacement timing, and catastrophic forfeiture adjudication are not automated. catastrophic penalties remain pending and block resumption/certification until a separate adjudication mechanism exists. the rules engine has no match-server discovery, persistence, authentication, or anti-cheat transport.

`logevent` provides stable sequence/time, kind, actor/ball/team, numeric value, reason, and penalty ID. it is a compact native audit record rather than the python log's nested json schema; complete source evidence, legacy crown coordinates when explicitly enabled, and penalty objects are available in state or must be retained by the adapter. copying `match` makes an independent state snapshot; serialization is the adapter's responsibility.

ue 4.27 creator kit compatibility of the surrounding gameplay remains separate. portable c++ source alone does not create a permitted native hogwarts legacy mod module or supply its missing multiplayer integration.

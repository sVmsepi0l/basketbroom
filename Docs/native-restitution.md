# Post-termination restitution

Bible section 5.7 requires a free or penalty shot owed for pre-termination
conduct to be completed before the winner is certified. Basketbroom and
Bloodbroom now share that procedure in the C++ regulation engine.

A host-selected Moderate free shot or Serious penalty shot may start during
review of a Snitch catch, final regulation horn, overtime 150-point threshold,
or overtime horn. Conduct must have occurred at or before the original ending
timestamp. The shot uses the existing physical attempt, ordinary 13/37-point
value and defending-Netminder restart. The penalty stays pending through that
restart. The final decision cannot bypass it by resuming, certifying, overwriting
the reserved penalty with a text disposition or overturning the Snitch mid-shot.

The original ending event, catcher and live timestamp remain intact. Global
match time, ball return/release timers, effects and removal timers stay frozen
while the shot's independent attempt clock runs. A Serious removal remains due;
a Moderate free shot adds none. Multiple remedies may be served sequentially,
with one active reservation and a separate audit record for each.

After all pre-termination penalties have been addressed, certification applies
the existing ending rule to the adjusted score:

- A Snitch catch still ends the match. Higher score wins, with an exact tie
  favoring the original catching team; Reckoner remains Scout-only.
- The regulation horn wins only at a margin of at least 150; otherwise overtime
  follows.
- An overtime threshold still wins at 150 or more. If restoration lowers it
  below 150 and time remains, overtime resumes at the original timestamp with
  the defending restart and its protection intact.
- An overtime horn wins at any nonzero lead; a tie enters Donnybrook.

The native shot status labels post-termination remedies as provisional. The
short certification display delay begins again after the defending restart.
These are native adapter source changes; portable results alone do not prove
that a real ending/contact sequence has been delivered by the game adapter.

## Explicit limits

The bible does not resolve a post-termination Donnybrook foul whose restorative
shot conflicts with its first winning event. That case remains pending for
explicit adjudication. Existing goal, Crown or conduct reservations are never
silently overwritten; an unreserved second Quark can supply the same ball type,
but a blocked Quaffle cannot be replaced with a higher-value Quark. An unavailable
defending Netminder also leaves the remedy pending. The implementation does not
invent replacement rights, automatic severity escalation or retrospective catch
points.

The native adapter now has an explicit host playtest advantage route described
below. The ordinary immediate-stop path still resolves already observed points
before a new direct spell and refuses a new hit after the match ends. This
feature does not move post-whistle scoring back into live play. The native
Hogwarts match adapter remains separate from the UE5 runtime.

## Host-selected Moderate advantage — native source added

Bible section 6.1 permits a lesser foul to be signaled while the nonoffending
team retains meaningful advantage; it requires a whistle when advantage is lost
or the offending team controls the affected ball. Dangerous Serious, Severe and
Catastrophic conduct still requires an immediate stoppage. BB-0 does not provide
an automatic confirmed severity mapping for each violation.

The new **F10** host control therefore makes an explicit, one-use *playtest
referee selection*. With a controller, open the roster with View and press Menu.
It proposes Moderate advantage for the next otherwise qualifying basic-cast
mobbing foul. It is off by default and can be toggled off before the next foul.
Any actual foul consumes the preselection. It only continues play when all of
these conservative prototype eligibility conditions hold:

- The hit is Basic Cast and its only violation is the fourth teammate's mobbing
  contact. Actual head-region impacts, including in Bloodbroom, do not qualify.
- The victim has no movement disable or impediment and remains above 50 vitality.
- The victim still genuinely controls the affected Quaffle or Quark.
- No earlier incident is awaiting adjudication.

These gates are intentionally limited prototype administration, not newly
confirmed sport definitions of danger or an automatic tier for all mobbing.
All other applied illegal hits stop play as before. During qualified advantage,
the original offender/victim identities, ball, foul location, attack ID and live
timestamp are retained. A pending Moderate penalty is recorded immediately and
cannot be auto-resolved by the match tick. Legal spells and ball play continue.

This first implementation retains advantage only while the offended team keeps
actual scoring-ball custody. A release/drop, unavailable carrier, official
stoppage, another illegal hit or natural ending closes that window. A second
illegal hit is applied, stops play and gets its own evidence record without
overwriting the first incident. Loss-of-custody checks run synchronously after
ordinary release, disconnect and completed hit resolution; the hit receipt is
recorded before a forced drop can freeze combat. The existing F6 free-shot/F7
possession choices then serve the explicitly selected Moderate remedy. At a
terminal review, F6 is required because ordinary possession cannot resume an
ended match. The host cannot turn this already selected Moderate incident into
a second higher-tier package; a separate queued foul retains its own ruling.

A natural Snitch catch or horn preserves the pending original penalty, which
blocks certification until the real free shot and defending restart finish.
The read-only `DevelopmentGetConductAdvantageState` diagnostic exposes the
original event mapping and ending time for an independent native test.

### Pending native acceptance — exact ordinary-input recipe

**No native advantage/restitution gameplay run has passed yet.** The C++ source
is ready for the root agent's UE build. `Tools/test_native_restitution.py` remains
portable proof only; an automated `test_native_restitution_playable.py` has not
been completed. Do not describe the following recipe as executed evidence.

1. Launch a disposable `BB_Regulation` PIE world with ordinary `?Practice=1`
   options; verify `bPractice`, the 180-second quarter and initially scheduled
   60-second Snitch. Preserve/restore existing editor options and own the PIE.
2. Use ordinary lobby controls to select host Scout. Create three further real
   local players sequentially with `GameplayStatics.create_player`, then ordinary
   role/team requests to put all four humans on Teal. Four local players fit the
   installed default split-screen limit; no fifth controller is necessary.
3. Park unused CPU copies and disable their movement only in the disposable
   fixture. An opposing CPU Chaser at approximately `(-400, 0, 1872)` must acquire
   the Quaffle through actual native AI pickup from a nearby free-ball fixture.
   Keep that rider away from its shooting mark so ordinary AI retains custody.
4. Advance only the owned world's time dilation to reach the actual 60-live-
   second Snitch release, then return to slow sampling. Do not write rule time,
   ball activation, scores, capture progress, penalties or ending state.
5. Host sends Action 13/F10. Arrange each real caster in turn on a horizontal
   torso ray, approximately `(-1200, 0, 1800)` toward that carrier, and send
   ordinary Basic Cast (Action 6, spell 0). Move prior casters out of the ray.
   All four distinct teammates must actually hit within the existing two-live-
   second mob window; leave host as fourth attacker. Observe 4 damages, exactly
   one Mobbing call, consumed arming, live advantage, retained native custody
   and an actual pending Moderate penalty with the original event diagnostic.
6. Keep the offended carrier's genuine custody. The host holds ordinary chase
   input and follows the real released Snitch with disposable actor transforms;
   observe nonzero partial progress and the actual one-second catch. Verify the
   150-point score, natural Review, original penalty/time preserved and no winner
   certification after more than the usual two-second review display delay.
7. Host sends F6/Action 12. The harmed eligible CPU Chaser should be the actual
   shooter with the Quaffle. Enable its native actor tick so the existing CPU
   shot routine takes its one physical attempt at 1.25 attempt seconds. Keep the
   real defending human Netminder clear of the shot lane through actor geometry.
   Observe release, flight, ordinary 13-point goal, unchanged live/ending time,
   zero new removal, and actual defending restart before certification.
8. Verify final score 150–13 and the original catching team's certified result.
   Repeat in Bloodbroom. Separate follow-up cases must challenge nonhost arming,
   safety-ineligible hits, lost advantage and a second incident queue before any
   broader multiplayer/complete-regulation claim.


## Verification, September 15, 2026

`Tools/test_native_restitution.py` compiled with MSVC C++17 `/W4 /WX`: **28 of
28 scenarios passed**. It checks winner flips, the capture tie rule, each ending
retest, clock preservation, sequential remedies, actual restart requirements,
reserved-shot bypass rejection, and explicitly unsupported cases. Its report is
`.local/native-restitution/results.json`.

The existing portable regulation (**69**), Serious-shot (**35**) and Moderate-
free-shot (**12**) scenarios also passed on the changed engine. Their existing
reports are in `.local/native-rules`, `.local/native-penalty-shots` and
`.local/native-free-shots`. These are overlapping behavior suites, not a count
of unique game features or proof of rendered, packaged or network play.

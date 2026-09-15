# post-termination restitution

bible section 5.7 requires a free or penalty shot owed for pre-termination
conduct to be completed before the winner is certified. basketbroom and
bloodbroom now share that procedure in the c++ regulation engine.

a host-selected moderate free shot or serious penalty shot may start during
review of a snitch catch, final regulation horn, overtime 150-point threshold,
or overtime horn. conduct must have occurred at or before the original ending
timestamp. the shot uses the existing physical attempt, ordinary 13/37-point
value and defending-netminder restart. the penalty stays pending through that
restart. the final decision cannot bypass it by resuming, certifying, overwriting
the reserved penalty with a text disposition or overturning the snitch mid-shot.

the original ending event, catcher and live timestamp remain intact. global
match time, ball return/release timers, effects and removal timers stay frozen
while the shot's independent attempt clock runs. a serious removal remains due;
a moderate free shot adds none. multiple remedies may be served sequentially,
with one active reservation and a separate audit record for each.

after all pre-termination penalties have been addressed, certification applies
the existing ending rule to the adjusted score:

- a snitch catch still ends the match. higher score wins, with an exact tie
  favoring the original catching team; reckoner remains Scout-only.
- the regulation horn wins only at a margin of at least 150; otherwise overtime
  follows.
- an overtime threshold still wins at 150 or more. if restoration lowers it
  below 150 and time remains, overtime resumes at the original timestamp with
  the defending restart and its protection intact.
- an overtime horn wins at any nonzero lead; a tie enters Donnybrook.

the native shot status labels post-termination remedies as provisional. the
short certification display delay begins again after the defending restart.
these are native adapter source changes; portable results alone do not prove
that a real ending/contact sequence has been delivered by the game adapter.

## explicit limits

the bible does not resolve a post-termination donnybrook foul whose restorative
shot conflicts with its first winning event. that case remains pending for
explicit adjudication. existing goal, crown or conduct reservations are never
silently overwritten; an unreserved second quark can supply the same ball type,
but a blocked quaffle cannot be replaced with a higher-value Quark. an unavailable
defending netminder also leaves the remedy pending. the implementation does not
invent replacement rights, automatic severity escalation or retrospective catch
points.

the native adapter now has an explicit host playtest advantage route described
below. the ordinary immediate-stop path still resolves already observed points
before a new direct spell and refuses a new hit after the match ends. this
feature does not move post-whistle scoring back into live play. the native
hogwarts match adapter remains separate from the ue5 runtime.

## host-selected moderate advantage — native source added

bible section 6.1 permits a lesser foul to be signaled while the nonoffending
team retains meaningful advantage; it requires a whistle when advantage is lost
or the offending team controls the affected ball. dangerous serious, severe and
catastrophic conduct still requires an immediate stoppage. bb-0 does not provide
an automatic confirmed severity mapping for each violation.

the new **f10** host control therefore makes an explicit, one-use *playtest
referee selection*. with a controller, open the roster with view and press Menu.
it proposes moderate advantage for the next otherwise qualifying basic-cast
mobbing foul. it is off by default and can be toggled off before the next foul.
any actual foul consumes the preselection. it only continues play when all of
these conservative prototype eligibility conditions hold:

- the hit is basic cast and its only violation is the fourth teammate's mobbing
  contact. actual head-region impacts, including in bloodbroom, do not qualify.
- the victim has no movement disable or impediment and remains above 50 vitality.
- the victim still genuinely controls the affected quaffle or Quark.
- no earlier incident is awaiting adjudication.

these gates are intentionally limited prototype administration, not newly
confirmed sport definitions of danger or an automatic tier for all mobbing.
all other applied illegal hits stop play as before. during qualified advantage,
the original offender/victim identities, ball, foul location, attack id and live
timestamp are retained. a pending moderate penalty is recorded immediately and
cannot be auto-resolved by the match tick. legal spells and ball play continue.

this first implementation retains advantage only while the offended team keeps
actual scoring-ball custody. a release/drop, unavailable carrier, official
stoppage, another illegal hit or natural ending closes that window. a second
illegal hit is applied, stops play and gets its own evidence record without
overwriting the first incident. loss-of-custody checks run synchronously after
ordinary release, disconnect and completed hit resolution; the hit receipt is
recorded before a forced drop can freeze combat. the existing f6 free-shot/F7
possession choices then serve the explicitly selected moderate remedy. at a
terminal review, f6 is required because ordinary possession cannot resume an
ended match. the host cannot turn this already selected moderate incident into
a second higher-tier package; a separate queued foul retains its own ruling.

a natural snitch catch or horn preserves the pending original penalty, which
blocks certification until the real free shot and defending restart finish.
the read-only `developmentgetconductadvantagestate` diagnostic exposes the
original event mapping and ending time for an independent native test.

### pending native acceptance — exact ordinary-input recipe

**no native advantage/restitution gameplay run has passed yet.** the c++ source
is ready for the root agent's ue build. `Tools/test_native_restitution.py` remains
portable proof only; an automated `test_native_restitution_playable.py` has not
been completed. do not describe the following recipe as executed evidence.

1. launch a disposable `bb_regulation` pie world with ordinary `?practice=1`
   options; verify `bpractice`, the 180-second quarter and initially scheduled
   60-second Snitch. Preserve/restore existing editor options and own the PIE.
2. use ordinary lobby controls to select host Scout. create three further real
   local players sequentially with `GameplayStatics.create_player`, then ordinary
   role/team requests to put all four humans on Teal. four local players fit the
   installed default split-screen limit; no fifth controller is necessary.
3. park unused cpu copies and disable their movement only in the disposable
   fixture. an opposing cpu chaser at approximately `(-400, 0, 1872)` must acquire
   the quaffle through actual native ai pickup from a nearby free-ball fixture.
   keep that rider away from its shooting mark so ordinary ai retains custody.
4. advance only the owned world's time dilation to reach the actual 60-live-
   second snitch release, then return to slow sampling. do not write rule time,
   ball activation, scores, capture progress, penalties or ending state.
5. host sends action 13/F10. arrange each real caster in turn on a horizontal
   torso ray, approximately `(-1200, 0, 1800)` toward that carrier, and send
   ordinary basic cast (action 6, spell 0). move prior casters out of the ray.
   all four distinct teammates must actually hit within the existing two-live-
   second mob window; leave host as fourth attacker. observe 4 damages, exactly
   one mobbing call, consumed arming, live advantage, retained native custody
   and an actual pending moderate penalty with the original event diagnostic.
6. keep the offended carrier's genuine custody. the host holds ordinary chase
   input and follows the real released snitch with disposable actor transforms;
   observe nonzero partial progress and the actual one-second catch. verify the
   150-point score, natural review, original penalty/time preserved and no winner
   certification after more than the usual two-second review display delay.
7. host sends F6/Action 12. the harmed eligible cpu chaser should be the actual
   shooter with the Quaffle. enable its native actor tick so the existing cpu
   shot routine takes its one physical attempt at 1.25 attempt seconds. keep the
   real defending human netminder clear of the shot lane through actor geometry.
   observe release, flight, ordinary 13-point goal, unchanged live/ending time,
   zero new removal, and actual defending restart before certification.
8. verify final score 150–13 and the original catching team's certified result.
   repeat in Bloodbroom. separate follow-up cases must challenge nonhost arming,
   safety-ineligible hits, lost advantage and a second incident queue before any
   broader multiplayer/complete-regulation claim.


## verification, september 15, 2026

`Tools/test_native_restitution.py` compiled with msvc c++17 `/W4 /WX`: **28 of
28 scenarios passed**. it checks winner flips, the capture tie rule, each ending
retest, clock preservation, sequential remedies, actual restart requirements,
reserved-shot bypass rejection, and explicitly unsupported cases. its report is
`.local/native-restitution/results.json`.

the existing portable regulation (**69**), serious-shot (**35**) and moderate-
free-shot (**12**) scenarios also passed on the changed engine. their existing
reports are in `.local/native-rules`, `.local/native-penalty-shots` and
`.local/native-free-shots`. these are overlapping behavior suites, not a count
of unique game features or proof of rendered, packaged or network play.

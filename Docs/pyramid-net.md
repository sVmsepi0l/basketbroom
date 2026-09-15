# closed pyramid net — basketbroom and bloodbroom

the 2026/09/14 user amendment replaces the open roof and no crown exit procedure
with a stout, hollow, upward-pointing pyramidion net. this applies to both
basketbroom and Bloodbroom. balls remain inside the arena and rebound from the
sloping roof; crossing the former roofline does not kill, respawn or return a
ball, drop possession, or create a no crown foul.

## shape and provisional dimensions

four triangular net faces rise from the rectangular perimeter to one central
apex. there is no horizontal collision surface across the eave and no solid
interior: riders and balls can enter the space under the pyramid.

- eave height: **138 ft / 4206.24 cm** above the floor.
- apex height: **207 ft / 6309.36 cm** above the floor.
- rise above the eave: **69 ft / 2103.12 cm**.
- eave rectangle: **x ±6850.8 cm, y ±3200.4 cm**, centered over the arena.

the heights and rise reuse the prototype's existing altitude dimensions and
remain **provisional playtest values**. the four slopes use the same central
apex, including at their seams and the wall junctions. the visible structure
uses netting and supporting ribs. it is not a solid pyramid or a flat ceiling.

the september 15 [arena-volume expansion](arena-volume-expansion.md) requests 40–50% more enclosed space, targeting 45%. that work is pending; the dimensions above describe the current validated roof.

## native gameplay behavior

`BBArenaGeometry.h` provides the shared plane and containment equations. the
server continuously sweeps each free scoring ball and bludger as a whole sphere
against the four sloping faces, then continues the unused portion of that
flight step after the rebound. roof restitution is **0.75 along the normal**;
tangential motion is preserved on a single face. multiple touching faces are
resolved together at ridges and the apex so they cannot leave a gap.

the collision mesh serves native CharacterMovement. balls use the analytic
roof planes and ignore the tagged roof mesh in their generic world sweep,
avoiding a second bounce from the same contact. rider capsules use the same
sloping containment in server movement and owner prediction. held balls stay
inside the net, including when the rider aims upward. snipe and snitch movement
is also confined to this closed volume; their normal catches, scheduled
releases and return timers remain distinct from roof contact.

the goal, rim and keeper checks retain their actual flight ordering. during a
serious penalty shot, touching the roof is a **net-contact miss** with no points;
the normal defending restart follows. merely passing the old 138-foot plane
leaves the attempt live. the shot clock uses the contact's fraction of the
physics step. bloodbroom uses the same arena and shot procedure; its exceptions
remain unforgivables and headshots, not unrestricted sporting conduct.

## reproduce and inspect

after compiling the native editor module, `Tools/stage_pyramid_net.py` installs
the targeted roof assets in the existing regulation and training maps through
the ue 5.8 editor bridge. it requires a stopped, clean editor, preserves unrelated
actors, and stores backups and staging receipts under `.local`. this is a
standalone ue 5.8 stage; it does not publish or validate a creator kit port.

`Tools/test_native_pyramid_net.py` exercises actual native flight, ordinary
pickup and rider movement in a disposable pie world. run it separately with
`BRIDGE_ARGS={"variant":"regulation"}` and `{"variant":"bloodbroom"}`. optional
`capture_screenshots:true` requests rendered evidence. the native penalty-shot
suite also accepts `outcome:"roof"`. read each report's final status; a planned
or started test is not a passing test. the parent milestone receipt records
completed runs and package provenance separately.

`ABBBall::DevelopmentGetRoofContactState` is a read-only authority pie diagnostic:
contact count, last outward normal, and incoming/outgoing velocity. it does not
set a collision result, custody, score or clock.

## superseded material

the v0.1 rules bible and dated validation receipts retain historical open-roof
wording and results. this amendment supersedes their no crown, crown mark,
roof-exit return, dead-roof delay and exterior chase-envelope provisions wherever
they depend on an open roof. it does not remove ordinary delay, contact or
other sporting rules.

the portable c++ and python rules engines default to the closed net. their old
crown api is available only to explicitly opted-in historical fixtures with
`enable_legacy_crown_exit=true`; it is not an alternate native game mode. the
retired `Tools/test_native_crown.py` and `Tools/test_native_crown_edges.py` entry
points return **not_run** before starting pie and retain their old case lists
for reference. new retirement receipts use separate files, preserving old
result files. historical passes do not validate the new roof.

full regulation, remaining spellwork, hogwarts legacy integration, remote
multiplayer validation and final art remain separate ongoing work. this roof
amendment does not establish a cloud-cooked or playable hogwarts legacy mod.

validation results and scope: [pyramid-net validation](pyramid-net-validation.md).

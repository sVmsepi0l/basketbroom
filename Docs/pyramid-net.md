# Closed pyramid net — Basketbroom and Bloodbroom

The 2026-09-14 user amendment replaces the open roof and No Crown exit procedure
with a stout, hollow, upward-pointing pyramidion net. This applies to both
Basketbroom and Bloodbroom. Balls remain inside the arena and rebound from the
sloping roof; crossing the former roofline does not kill, respawn or return a
ball, drop possession, or create a No Crown foul.

## Shape and provisional dimensions

Four triangular net faces rise from the rectangular perimeter to one central
apex. There is no horizontal collision surface across the eave and no solid
interior: riders and balls can enter the space under the pyramid.

- Eave height: **138 ft / 4206.24 cm** above the floor.
- Apex height: **207 ft / 6309.36 cm** above the floor.
- Rise above the eave: **69 ft / 2103.12 cm**.
- Eave rectangle: **X ±6850.8 cm, Y ±3200.4 cm**, centered over the arena.

The heights and rise reuse the prototype's existing altitude dimensions and
remain **provisional playtest values**. The four slopes use the same central
apex, including at their seams and the wall junctions. The visible structure
uses netting and supporting ribs. It is not a solid pyramid or a flat ceiling.

## Native gameplay behavior

`BBArenaGeometry.h` provides the shared plane and containment equations. The
server continuously sweeps each free scoring ball and Bludger as a whole sphere
against the four sloping faces, then continues the unused portion of that
flight step after the rebound. Roof restitution is **0.75 along the normal**;
tangential motion is preserved on a single face. Multiple touching faces are
resolved together at ridges and the apex so they cannot leave a gap.

The collision mesh serves native CharacterMovement. Balls use the analytic
roof planes and ignore the tagged roof mesh in their generic world sweep,
avoiding a second bounce from the same contact. Rider capsules use the same
sloping containment in server movement and owner prediction. Held balls stay
inside the net, including when the rider aims upward. Snipe and Snitch movement
is also confined to this closed volume; their normal catches, scheduled
releases and return timers remain distinct from roof contact.

The goal, rim and keeper checks retain their actual flight ordering. During a
Serious penalty shot, touching the roof is a **net-contact miss** with no points;
the normal defending restart follows. Merely passing the old 138-foot plane
leaves the attempt live. The shot clock uses the contact's fraction of the
physics step. Bloodbroom uses the same arena and shot procedure; its exceptions
remain Unforgivables and headshots, not unrestricted sporting conduct.

## Reproduce and inspect

After compiling the native Editor module, `Tools/stage_pyramid_net.py` installs
the targeted roof assets in the existing regulation and training maps through
the UE 5.8 editor bridge. It requires a stopped, clean editor, preserves unrelated
actors, and stores backups and staging receipts under `.local`. This is a
standalone UE 5.8 stage; it does not publish or validate a Creator Kit port.

`Tools/test_native_pyramid_net.py` exercises actual native flight, ordinary
pickup and rider movement in a disposable PIE world. Run it separately with
`BRIDGE_ARGS={"variant":"regulation"}` and `{"variant":"bloodbroom"}`. Optional
`capture_screenshots:true` requests rendered evidence. The native penalty-shot
suite also accepts `outcome:"roof"`. Read each report's final status; a planned
or started test is not a passing test. The parent milestone receipt records
completed runs and package provenance separately.

`ABBBall::DevelopmentGetRoofContactState` is a read-only authority PIE diagnostic:
contact count, last outward normal, and incoming/outgoing velocity. It does not
set a collision result, custody, score or clock.

## Superseded material

The v0.1 rules bible and dated validation receipts retain historical open-roof
wording and results. This amendment supersedes their No Crown, Crown Mark,
roof-exit return, Dead-Roof Delay and exterior chase-envelope provisions wherever
they depend on an open roof. It does not remove ordinary delay, contact or
other sporting rules.

The portable C++ and Python rules engines default to the closed net. Their old
Crown API is available only to explicitly opted-in historical fixtures with
`enable_legacy_crown_exit=true`; it is not an alternate native game mode. The
retired `Tools/test_native_crown.py` and `Tools/test_native_crown_edges.py` entry
points return **not_run** before starting PIE and retain their old case lists
for reference. New retirement receipts use separate files, preserving old
result files. Historical passes do not validate the new roof.

Full regulation, remaining spellwork, Hogwarts Legacy integration, remote
multiplayer validation and final art remain separate ongoing work. This roof
amendment does not establish a cloud-cooked or playable Hogwarts Legacy mod.

Validation results and scope: [pyramid-net validation](pyramid-net-validation.md).

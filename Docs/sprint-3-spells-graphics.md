# Sprint 3: spells, regulation and flight equipment

Sprint 3 adds five sporting spell adapters, a host-selected Moderate free shot, original broom/wand art and a guarded source update for the native Hogwarts Legacy Creator Kit arena. Both Basketbroom and Bloodbroom share the new standalone gameplay. The native gameplay, multiplayer and packaged startup checks pass. The new Windows package is selected by the existing desktop shortcut; the exact scope and remaining native-kit work are recorded below.

## Spellwork

The standalone UE 5.8 runtime implements **23 of the 31 spell-menu actions**. The five additions are:

- **Revelio:** detects concealed opponents within 22 metres for six live seconds, with opaque geometry still blocking detection.
- **Disillusionment:** conceals a rider from opponents for six live seconds. Teammates can still see them; offensive casts, applied wand hits and Bludger hits break concealment. Physical collision and blind aimed hits still work, and official balls remain visible.
- **Petrificus Totalus:** requires concealment, an approach from behind and a target within 3.5 metres. It binds for 2.5 live seconds and drops held equipment. Protego and active nearby Revelio provide counterplay. It counts as a stun for the confirmed-impediment double-tap rule.
- **Transformation:** turns the rider's presentation into a sporting orb for three live seconds, drops held equipment and locks flight, wandwork and ball interaction. The same pawn, collision capsule and controller remain. Protego blocks it.
- **Imperio:** reverses horizontal flight acceleration for three live seconds. Looking, vertical controls and player ownership remain intact. This is an input-confusion sport adaptation, not full mind control. Its hit applies before an Unforgivable review in Basketbroom; Bloodbroom permits that curse.

Select spells with **Z/X**, cast with **Q**, raise Protego with **R**, and open the spellbook with **V**. On a gamepad, use **D-pad Left/Right**, **RB**, **LB** and **Y** respectively outside the position guide or referee review. On DualSense those shoulder and face controls correspond to **R1**, **L1** and **Triangle**.

Status timers replicate from authority and consume live match time. Stoppages, quarter breaks and protected shot administration freeze remaining effects; a new match clears them. The bound timer and flight lock use the same live-time authority. Status rings, a transformation orb and per-view concealment provide prototype feedback. See [sporting spell adapters](native-sport-spells.md) for durations, counterplay, lifecycle details and test scope.

Eight actions remain contextual: **Alohomora, Wingardium Leviosa, Reparo, Conjuring, Altering, Evanesco, Ancient Magic and Ancient Magic Throw**. Their world objects, permissions and resources still need real adapters. Existing effects also need further animation, elemental/splash behavior, balance and CPU wand tactics. This does not claim parity with Hogwarts Legacy's combat system.

## Moderate free shots

After an illegal wand hit has taken effect and produced a BB-0 review, the host may now press **F6** for a **Moderate free shot with no new removal**. On a controller, **D-pad Left selects the free shot and Menu confirms**. Selecting the direction alone does not apply a sanction. The other choices remain F7/D-pad Up for possession, F8/D-pad Right for a Serious shot plus removal, and F9/D-pad Down for ejection. Non-host clients cannot serve the decision.

The free shot preserves the affected Quaffle or Quark type and its ordinary **13 or 37 points**. If no carried scoring ball was involved, the default is the Quaffle; Donnybrook uses a Quark. An eligible harmed rider is preferred as shooter, then an eligible teammate. The defending Netminder may defend; in Donnybrook an eligible designated goal defender can fill that role. A Moderate offense by the keeper does not itself remove that keeper.

On September 14, 2026, the user confirmed how to interpret the reference's 44-foot placement: retain the actual foul's lateral position and altitude, and move the shot backward along the pitch **X axis only** if necessary to stay at least **44 feet from the attacking goal plane**. This is a minimum distance to the goal plane, not a radial distance from a hoop center. The original foul point is retained separately from the older possession-award placement clamps. Nonkeeper defenders are placed at least **22 feet from the shooter until release**.

For this first playable adapter, free shots reuse a **stopped five-second attempt**, including aim and flight. The shooter remains at the mark and may release once; the keeper may move within the goal area. Other participants remain movement-locked through the procedure. Wandwork, passes, another attempt, role/team changes and global resume are blocked. Rim deflection can continue the same flight; a keeper save, net/floor contact, wrong goal or timeout ends it without points. A made goal awards its normal value once. After the result hold, the defending keeper receives an actual protected restart before the remedy is complete, then the host resumes play.

**The stopped clock, five-second free-shot limit, no-wand/no-pass/no-second-attempt restrictions, participant movement locks and defending-restart procedure are prototype administration choices.** They are not newly canonical rules from the v0.1 bible. The minimum-44-foot X placement is the user's specific interpretation; further free-shot timing and live-rebound behavior still need playtesting. These distinctions do not change the existing Serious remedy's separate three-live-minute removal or Donnybrook exclusion.

A single pending Moderate penalty cannot reserve both a possession award and a free shot. Both ordering directions reject duplicate packages atomically. Existing goals and unrelated queued remedies retain their reservations. Frozen spell effects are preserved through the protected shot, with narrow shooter-release and keeper-movement overrides; the shot does not cure them.

Bloodbroom waives Unforgivables and headshots only. Mobbing, confirmed-impediment double-taps, physical holding, ball/position restrictions and other sporting rules remain shared. Host choices remain a playtest referee interface, not automatic foul severity or complete regulation officiating. See [native shots](native-penalty-shots.md).

## Graphics and Creator Kit work

The original equipment pass supplies layered broom and wand meshes for wood, leather, copper, bristles and team trim. Owner and remote views reuse the same assets and existing mounts. These props remain noncolliding cosmetic equipment; the pass does not change flight physics or claim a measured performance improvement. The source/staging contract is in [original flight equipment](../SourceArt/Equipment/broom_equipment.md). Final rider costumes, character models, arena environment work, animation and lighting remain in development; this is not a completed AAA art pass.

The UE 5.8 standalone game and licensee UE 4.27 Creator Kit mod remain separate builds. This sprint prepares a guarded, original-OBJ roof update for the two existing native kit maps while preserving their ownership, dungeon anchors, registered entrance and SQL. Source and safeguard tests are available; native staging, the corrected player/exit observer and actual entry/return must be evidenced separately. No UE 5 package is copied into the kit. See [Hogwarts sprint 3](hogwarts-sprint3.md) and the [integration record](hogwarts-integration.md).

## Validation and package handoff

The expanded portable free-shot suite passes **12/12 cases** with the same-penalty reservation fixes. Its scope is the native rules state machine; it does not test actor placement, rendering, input devices or network transport. Existing historical milestone counts elsewhere in the repository identify their own earlier builds and must not be added to this sprint's total.

The September 14 native runs passed **313 gameplay/presentation checks** and **69 multiplayer checks**, with no failed or unrun checks in the selected final receipts. The gameplay group contains sporting spells in both modes (42), Moderate free-shot outcomes in both modes (120), a high-altitude Quark free shot (15), Serious-shot regressions in both modes (52), existing playable/controller/spell checks (74), and equipment validation (10). The network group contains the new four-adapter spell suite (12), Moderate free shots in both modes (20), and existing roster/gameplay, spell and Serious-shot regressions (37). **Petrificus has solo gameplay coverage but no explicit network cast/status test yet.** Multiplayer uses actual separate server and client worlds in one editor process; external latency, remote Internet connectivity and load remain untested.

Portable native rules checks also passed: free shots 12, Serious shots 35, general rules 69, combat conduct 38 and admission 10. The Python reference rules suite passed 55 tests. These counts describe this revision's completed runs, not the historical milestone counts in other documents.

Gameplay receipts live under `.local/sprint3-validation-{suite}-20260914-*`. Their per-run records retain exact module hashes. The final editor module SHA-256 is `2d3606eec4a3031c5a5992c3c96e0b69c64d7119e86a55405481b3cd41f57416`; its final runs include Serious shots, equipment and all 69 network checks. Earlier solo/free-shot runs used the same gameplay implementation before the final cosmetic charm-mount and shared-shot wording adjustments. The original receipts are retained, rather than claiming those earlier runs used the later binary.

The owner, teal-team and copper-team equipment captures were visually inspected after the final mount adjustment. The hands and feet meet their supports, team trim and layered props render correctly, and first-person equipment leaves the central flight view clear. `.local/sprint3-equipment-visual-review.json` retains the image and report hashes. These are actual rendered frames; they do not establish final character/arena art or a performance target.

Windows package `Development-20260914-184824-051` built and cooked successfully with UE 5.8.1. `.local/latest-package.json` now selects it for the existing desktop shortcut. Actual rendered startup and clean exit passed for regulation, Bloodbroom and training at 1600 x 900, with no fatal, assertion, ensure, travel or network errors in their logs. All three screenshots were visually inspected: readable mode-appropriate HUD, complete pyramidion net and correctly rendered geometry/materials. Training retains its separate earlier Blueprint equipment. These are startup/render checks, not packaged input or complete-match proofs. The immutable startup receipt and separate image-hash review are in `.local/sprint3-packaged-visual-20260914-184933/`.

Two-process packaged loopback join and map travel also passed with both regulation and Bloodbroom launch options. Receipts are `.local/packaged-network/20260914-184949-569-75510ee7/result.json` and `.local/packaged-network/20260914-185010-678-77fd895b/result.json`. These narrow checks do not themselves prove variant replication, gameplay correctness, remote connectivity or latency behavior. The editor closed cleanly and its prior standalone Play setting was restored.

Physical DualSense USB/Bluetooth coverage remains separate from synthetic Unreal input and the previously confirmed USB spellbook button. The native Creator Kit roof authoring and true-Play checks also remain separate from the standalone results above; see [Hogwarts sprint 3](hogwarts-sprint3.md).

Full regulation still needs the remaining restitution/adjudication paths, post-termination restorative play, contact detection and autonomous match behavior. External multiplayer conditions, complete Hogwarts gameplay integration and final art also remain open. The sprint advances those tracks without claiming they are finished.

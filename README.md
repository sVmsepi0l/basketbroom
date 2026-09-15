# basketbroom
#### yankee arena quidditch w/ spellcasting
##### [ig: basketbroom](https://instagram.com/basketbroom)
![](Docs/Logo/basketbroom-logo_20260914.png)

----

a first-person broomsport alpha built in **unreal engine 5.8**. the active native
game has two opposing eight-rider teams, selectable positions, seven balls, broom flight,
ballistic goals, continuous chase catches, and regulation match state in an
original arena enclosed by a hollow pyramid net. the native editor and windows development game build
successfully. focused gameplay, opening, rematch, bludger, local networking,
and audio suites pass. two packaged processes also share role changes, scores,
stoppages, certified results and host rematches in local play. full regulation,
remote multiplayer validation, and final art remain in development.

----

![actual UE5.8 flight in the expanded pyramid-net arena](Docs/Screenshots/arena-expanded-flight.png)

the active project is `DevelopmentHarness/BasketbroomDev.uproject`. the folder
name is historical: this is now a standalone UE5.8 game project. it is not an
installable hogwarts legacy mod. creator kit research and the original mod
port remain in `Docs/` and `Mod/`; UE5.8 assets are not compatible
with hogwarts legacy's creator kit engine.

the creator kit port now has a saved dungeon, native return actor and registered
entrance SQL. launching the kit through epic resolved its wb sign-in failure.
the enlarged dungeon passes 17 live creator kit checks for native player spawn,
mod tables, exit setup and an advancing game clock, followed by clean shutdown. actual entry/return
interaction and match gameplay remain in development. see
[hogwarts sprint 3](Docs/hogwarts-sprint3.md) for the evidence and next steps.

![](Docs/Logo/bloodbroom-logo_20260914.png)

the arena now has [45% more enclosed volume](Docs/arena-volume-expansion.md)
in basketbroom, bloodbroom, training and the creator kit port. the enclosure is
13.19% longer, wider and taller; rider/ball sizes, hoop measurements and fixed
free-shot distances are preserved. the september 15 windows package includes
the expansion, with 142 focused gameplay checks, two-mode local connection
checks and rendered startup checks passing.

## play

double-click **Play.cmd**, or run the command below from this repository.
the launcher prefers the latest local packaged windows build, which does not
require unreal Editor. the current package contains the native regulation alpha
and the earlier training map. build output is local and is not committed to Git.

from a powershell terminal in this repository:

```powershell
.\Play.ps1
.\Play.ps1 -practice
.\Play.ps1 -bloodbroom -practice
.\Play.ps1 -mode training
```

**Practice.cmd** opens the accelerated native match. **Bloodbroom.cmd** opens
that practice match in bloodbroom mode. **Local-Multiplayer.cmd** opens a packaged
host and client on this computer with practice clocks.

`Play.ps1 -bloodbroom` selects bloodbroom with ordinary clocks; add `-practice`
for accelerated clocks. it uses the native regulation map and cannot be combined
with `-mode Training`. add `-plan` to inspect the launch command without opening
the game.

for a desktop launcher, run `./Install-DesktopShortcut.ps1` in PowerShell. it
creates **basketbroom** on your current windows desktop and opens practice mode
through this checkout's `Play.ps1`, so later completed local packages are used
automatically. run it again to refresh the shortcut and package icon. keep this
checkout in place; unrelated same-named shortcuts are preserved, and the
installer does not change windows security settings.

the default `-mode auto` uses the latest package and its native regulation map.
`-practice` uses accelerated native clocks: three-minute quarters and a snitch
release after one minute of live play. `-mode training` selects the retained
five-minute blueprint scrimmage described below. these open a 1600 × 900 game
window. if no local package exists,
the launcher uses an installed unreal engine **5.8** editor in game mode.
use `-editorgame` to force that mode, or change the window size:

```powershell
.\Play.ps1 -width 1920 -height 1080
.\Play.ps1 -editorgame -engineroot 'D:\Epic Games\UE_5.8'
```

click inside the game window to take control. `alt+f4` closes the game.

- **w / a / s / D:** fly forward, left, backward and right.
- **Mouse:** look and aim. forward flight follows your view.
- **space / left Ctrl:** rise and descend.
- **E:** pick up a nearby free ball permitted for your position.
- **left mouse button:** throw the ball along your aim; account for its drop.
- **hold E:** remain within **3.8 meters** of a snipe or snitch for **one continuous second** as a ranger or Scout. release any carried ball first; the hud shows range and capture progress.
- **1–6:** choose netminder, chaser, trapper, ranger, hurleyback, or scout during the lobby or a stoppage.
- **T:** switch teams during the lobby or a stoppage. **Tab:** show the position guide.
- **Enter:** host starts/resumes play, or starts a new match after the certified final result. **P:** host calls a stoppage.
- **Q:** cast. **z / X:** select a spell. **R:** Protego. **V:** spellbook.
- **B:** host selects bloodbroom in the initial lobby. **f6 / f7 / f8 / F9:** host serves a pending bb-0 call with a moderate free shot, possession, a serious shot plus removal, or ejection in the playtest referee interface.

gamepad bindings and their validation status are documented in
[controller support](Docs/controller-support.md). the four-minute prototype
showcase includes all six positions and actual **3840 × 2160, 16:9, 60 fps** gameplay with automated camera
and gameplay staging; see the [capture and edit workflow](Docs/gameplay-promo.md).

you begin in a ranger slot and can choose another position before play.
put the red-orange **quaffle** through a large hoop for **13** points or a purple
**quark** through the small upper hoop for **37**. catch the copper **snipe** for
**69**; it returns after three live minutes. the golden **snitch** awards **150**
in regulation or **300** in overtime; final results follow the rules engine's
phase and review logic. regulation retains four **44-minute quarters**, with
the snitch scheduled after **22 minutes** of live play. practice releases it
after **one minute**. the snipe travels at 60% of the snitch's speed.

capture progress resets on release or a range break. ordinary scoring positions
carry quaffles and quarks; hurleybacks handle bludgers; rangers and scouts chase.
role and team changes are locked while play is live.
rematches retain teams and selected positions while resetting scores, clocks,
equipment, and the opening layout. ordinary stoppages preserve field positions;
new quarters and phases use their defined opening layouts.

## what is implemented

the [bb-0 wandplay adapter](Docs/native-wandplay.md) and [sprint 3 spellwork](Docs/native-sport-spells.md)
implement **23 of 31 spell-menu actions**, including revelio, disillusionment,
petrificus totalus, transformation and sporting Imperio. the spellbook retains
eight contextual actions with their adapters marked pending. vitality, wand/shield
visuals and conduct review follow applied hits. bloodbroom waives unforgivables
and headshots only; other sporting restrictions remain shared. spell tuning and
referee choices remain provisional. see the [sprint 3 handoff](Docs/sprint-3-spells-graphics.md)
for current controls, completed gameplay/network/package validation and remaining work.

`DevelopmentHarness/Source/BasketbroomRuntime/` now supplies the enabled native
c++ runtime: charactermovement broom flight, authority-owned balls, the sixteen
roster slots, position/team selection, host start/stoppage, goal and capture
resolution, and replicated hud state. it spawns one quaffle, two quarks, one
snipe, one scheduled snitch, and two Bludgers. goal checks require the whole ball
to clear the appropriate hoop. the [closed pyramid net](Docs/pyramid-net.md)
replaces the old no crown return: balls rebound off four sloping roof faces and
remain in play in both basketbroom and Bloodbroom. the former 138-foot roofline
is now an open interior eave plane, with the provisional apex at 207 feet.
riders and held/chase balls share the closed arena bounds. existing dated
validation receipts retain their original build scope; the amendment describes
the replacement native checks.

the venue, team colors, broom cockpit and hud use generated original assets.
sprint 3 also supplies [original layered broom and wand art](SourceArt/Equipment/broom_equipment.md);
its final rendered/package validation belongs to the sprint handoff.
riders now use epic's locally staged quinn mannequin with an authored seated
flight animation and team materials. python authors saved unreal assets; native matches run in C++. native
pickup, throw, goal, and snipe-catch events trigger original synthesized sounds.
the retained training mode runs in compiled blueprints and has four original
sounds for throw, score, catch, and bounce feedback.

the current visual pass adds an original basalt texture, material variation,
stadium masonry/seating, terrain, trees, metal goal rims and twilight lighting.
the latest pass adds animated skeletal riders and original flapping copper
snipe and ivory snitch wings. both teams and both chase balls have been rendered
and inspected in the native game. see `Docs/skeletal-rider-art.md` and
`Docs/chase-equipment-art.md` for reproducible asset setup and current limits.
the original hurley prop has also passed native rendering checks. its
approximately 103 cm overall length and open shallow
pocket are provisional: the current oversized bludger does not physically fit.
this visual addition does not implement striking or certify equipment dimensions.

the [native shot flow](Docs/native-penalty-shots.md) includes a host-selected
**moderate free shot without removal** and the separate serious shot plus
live-time removal in both modes. f6, or d-pad left then menu during a review,
selects the free shot. it preserves the foul's lateral position and altitude,
projects backward along x only when needed for the minimum 44-foot goal-plane
distance, and keeps nonkeeper defenders at least 22 feet away until release.
its stopped five-second attempt, restricted participant actions and protected
keeper restart are explicit prototype administration choices. full regulation
still needs post-termination restorative shots, full spell parity, and complete
officiating/adjudication flows. the rules engine has broader phase and penalty
coverage than the current in-game presentation. sport-specific animation,
finished character assets, match balance, and audio mixing need further work.
passing the focused native checks does not certify every regulation phase or
autonomous match behavior.

## retained training mode

use `Play.ps1 -mode training` for `/Basketbroom/Maps/BB_Arena`. you occupy teal's
ranger slot for a five-minute scrimmage with fifteen bots and five balls. both
chase balls are available immediately; the snitch ends that training game.
**r** restarts it. this mode uses simplified rules, permits training pickups
from bots, and has no live bludgers or position switching. its ranger hud shows
chase distances, hold progress, a projected target label, and an off-screen hint.
earlier standalone training packages remain available in the local build folder.

## native builds and multiplayer development

earlier baseline validation recorded **68 c++ scenarios**, including the
54 reference cases, and **35/35** native unreal integration checks in one
authority pie world. that milestone's combined native run passed
**96/96** checks across gameplay, admission, disconnect, networking, opening and
snitch suites. native editor compilation and win64
development compilation/cooking/packaging succeeded using visual studio 2026,
msvc **14.51.36257**, windows sdk **26100**, and the .NET framework **4.8 SDK**.
the regulation map is staged and enabled. packaged native startup and a
two-process loopback connection passed. native visual/input review is separate
from these automated checks.

to prepare another machine and rebuild the native editor target:

```powershell
.\Install-BuildTools.ps1
.\Build-Native.ps1
```

windows may require administrator approval for microsoft's signed installer.
after compilation, reopen the editor and run `Tools/stage_regulation.py` as
needed. reproduce the locally staged epic mannequin dependencies and authored
rider assets using `Tools/stage_skeletal_rider.py` as described in
`Docs/skeletal-rider-art.md`; those stock dependencies are not stored in Git.
use `Multiplayer.ps1 -mode localtest` for a
listen server and loopback client, `-mode host`, or `-mode join -address <host>`.
add `-bloodbroom` to **host** or **localtest** to select that match variant, for
example `./Multiplayer.ps1 -mode localtest -bloodbroom -Practice`. joining players
inherit the server's variant; `-mode join -bloodbroom` is rejected. both host and
client command plans can be inspected with `-plan` without starting a process.
all seventeen same-process networking checks pass, including client flight,
pickup, and throw replication. the launcher prefers the
native package; use `-editorgame` to force unreal's development game mode.
remote transport, latency, and gameplay across separate processes still need
validation beyond the passing packaged connection check. LAN/direct ip
comes first; Steam/Epic discovery, authentication, and invites are not implemented.
see `Docs/native-validation.md`, `Docs/native-rules.md`, and `Docs/networking.md`.

## open and rebuild

```powershell
.\Open-Editor.ps1
```

the active native map is `/Basketbroom/Maps/BB_Regulation`; the training map is
`/Basketbroom/Maps/BB_Arena`. generated assets are stored in
`DevelopmentHarness/Plugins/Basketbroom/Content/`, mounted as `/Basketbroom`.
the project's python and editor scripting utilities plugins are enabled.
these authoring plugins are restricted to editor targets.

to rebuild from the checked-in authoring sources, save your editor work, stop
play in editor, open **output log**, choose **python** in its command selector,
and run:

```python
import runpy; runpy.run_path(r"C:\Git\basketbroom\Tools\build_all.py", run_name="__main__")
```

adjust the path if you cloned elsewhere. this regenerates the owned training
blueprints and arena assets in dependency order:

1. `build_audio`: original source wavs and imported sound assets.
2. `build_gameplay`: match, balls and player flight, including sound triggers.
3. `build_arena`: meshes, materials, venue and lighting.
4. `build_hud`: scoreboard, controls and match result.
5. `stage_game`: game mode, player start, five balls and cockpit.
6. `build_bots`: rider movement, possession and shooting.
7. `stage_bots`: mounted visuals and the fifteen-bot roster.

the builder saves the assets and arena, and writes progress/results to
`.local/build-all-results.json`. generated blueprint graphs are replaced;
edit their python sources to preserve changes across rebuilds. arena builders
replace their tagged actors and retain unrelated untagged venue actors.
after training authoring, run `Tools/stage_regulation.py` to select and stage
the native map again. recompile c++ changes with `Build-Native.ps1`; the python
authoring pipeline does not compile native source.

to package saved assets into a windows executable:

```powershell
.\Package.ps1
```

with the native module enabled, packaging builds the native game target and
cooks both regulation and training maps. the earlier content-only training
packaging path uses UE5.8's installed game binary when the module is disabled.
each run creates a new `.local/Build/Development-<timestamp>/Windows`
directory and updates the launcher's latest-package pointer on success. keep
the entire `windows` folder together when copying a build. `-plan` checks inputs
without cooking; `-configuration shipping` selects a shipping build.

## checks and source layout

with python 3.10 or later, these checks run without Unreal:

```powershell
python -m unittest discover -s rules -v
python -m compileall -q tools rules
```

completed checks include **54 python rule-reference tests**, **68 portable c++
rules scenarios**, **35 native gameplay checks**, **19 practice Snitch/rematch
checks**, **11 opening-layout checks**, **9 bludger checks**, **17 local network
checks**, **7 admission checks**, **7 disconnect checks**, and **11 native audio checks**. the retained
training mode also passed **15 gameplay**, **15 ai**, and **4 flight** checks;
its final chase hud rebuild was rechecked and packaged. these suites have
different scopes: reference rules do not exercise unreal actors, and authority
pie results do not establish remote networking.
`Tools/test_playable.py` exercises training gameplay in unreal play in editor, while
`Tools/test_bots.py` provides separate ai integration checks for the roster,
possession and blueprint shooting behavior. `Tools/test_flight.py` reloads the
training map, checks spawn clearance, verifies the real player spawn, and measures
horizontal and vertical pawn movement with collision enabled.

`Tools/test_native_playable.py` verifies roster/roles, host controls, movement
bounds, ball physics, goals, eligibility, and snipe capture in the native map.
`Tools/test_native_network.py` exercises two pie worlds in one editor process.
`Tools/test_native_audio.py` observes sound assets, gameplay-triggered audio
components, suppression of repeated cues, and component cleanup; it does not
verify speaker output or the subjective mix. `Tools/test_native_snitch.py`
passed its separate practice release/catch/result/rematch suite: timed release
at 60 live seconds, hold/reset behavior, a 150-point catch, winner certification,
and a clean host rematch that retains the roster. that
suite slows pie time to 0.1x and follows the snitch during capture; it does not
validate normal-speed physical chasing or the 22-minute regulation release.
`Tools/test_native_openings.py` follows actual practice clocks through four
quarters, overtime, and donnybrook, carrying a 37–37 tie created by two real
quark goals. `Tools/test_native_bludgers.py` checks control-clock resets, impact
clearance, and opposing-hurleyback restarts in isolated pie fixtures.
training interactive checks verified e pickup, mouse release, a 13-point goal,
mouse aim, and packaged startup. those observations are not native packaged
validation. september 12 native packaged checks exercised physical **6/T**
position/team selection, **tab** help, and host **P/Enter** stoppage/resume.
the final package also passed two-process loopback checks for client **5**
hurleyback selection, host-only controls, matching final results and stoppage
state, host rematch, and continued play after a graceful client departure.
manual chase capture, remote networking, flight feel and the audio mix still
need further playtesting.
the [4k landscape prototype showcase](Docs/gameplay-promo.md) records current
native features and their observed outcomes; it does not claim final art or
completed hogwarts legacy integration.
see `Docs/validation.md` for evidence and limits; local reports describe individual
runs and do not guarantee that every later rebuild passes.

- `Tools/`: unreal authoring, staging and editor test scripts.
- `SourceArt/Arena/`: deterministic source geometry and the arena manifest.
- `SourceArt/Audio/`: original, reproducible synthesized wav sources.
- `SourceArt/Textures/`: original generated stone texture and provenance.
- `Rules/`: executable rules reference and tests; see `Rules/README.md`.
- `Docs/basketbroom_rules_bible_v0.1.md`: supplied design reference.
- `DevelopmentHarness/`: active UE5.8 project and generated playable content.
- `Mod/`: UE4.27 creator kit port sources and native assets, separate from the UE5.8 game. see `Docs/hogwarts-integration.md`; no playable/published mod is claimed.

if `python` resolves to the windows store alias on this workstation, the bundled
interpreter is at
`C:\Users\bigdi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.

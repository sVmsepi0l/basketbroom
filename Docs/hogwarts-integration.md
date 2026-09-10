# Basketbroom: Hogwarts Legacy integration

Verified 2026-09-10 against the installed Creator Kit, the supplied tutorial snapshots, and current publisher/CurseForge documentation.

**The UE 5.8 game and a Hogwarts Legacy mod are separate builds.** The practical Creator Kit route is a single-player arena content mod with Blueprint gameplay and bots. A full networked Hogwarts Legacy match is not a verified capability of the official kit. This repository contains original port sources and native Creator Kit art assets; it does not yet contain a playable or published Hogwarts Legacy Basketbroom match.

## Engine and runtime boundary

The standalone game uses `DevelopmentHarness/BasketbroomDev.uproject`, Unreal 5.8.1, and native Blueprint assets under that project's `Plugins/Basketbroom`. Its packaged executable runs independently of Hogwarts Legacy.

The installed Creator Kit is at `C:/Program Files/HogwartsLegacyCreatorKit`. Its `Engine/Build/Build.version` reports **4.27.2**, `IsLicenseeVersion=1`, branch `++UE4+Release-4.27`, and compatible changelist `17155196`. Its project is `PhoenixGame/Phoenix.uproject`; its editor is `Engine/Binaries/Win64/UE4Editor.exe`. This is a game-specific engine and project, not stock UE 4.27.

UE 5.8 `.uasset` and `.umap` files cannot be loaded by the older kit. Changing version strings, copying packages, or running the UE 5.8 graph builder in the kit is not a supported port. Reimport original sources, rebuild materials and runtime graphs in the kit, and save native 4.27 packages. Epic documents the one-way version compatibility of saved assets. [Epic migration guide](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-migration-guide).

Reusable sources here are the original `SourceArt/Arena/*.obj`, `SourceArt/Audio/*.wav`, arena dimensions, and `Rules/alpha_rules.json`. The Python rules implementation is a reference for porting state transitions and fixtures; it is not game runtime code. UE 5.8 Blueprint graphs, pawn/input plumbing, physics tuning, widgets, and lighting require a separate implementation and validation. The kit's rendering path also requires its own materials, LODs, lighting, and collision; UE 5 rendering features do not transfer with geometry.

## What the installed kit actually provides

`Phoenix.uproject` enables Python editor scripting and Editor Scripting Utilities, discovers plugins under `Mods`, and includes the game's precompiled modules. The supplied `PhoenixGame/Source` contains editor resources rather than a buildable copy of the game. `Plugins/ModSupport/ModSupport.uplugin` loads `PhoenixUGC`, the CurseForge integration plugins, and account services for Win64. `Plugins/PhoenixUGC/PhoenixUGC.uplugin` has runtime and editor modules.

The installed Dungeon Mod template contains these exact asset paths:

- `/PhoenixUGC/DungeonMod/Maps/PLUGIN_NAME_DungeonMap`
- `/PhoenixUGC/DungeonMod/Data/DT_PLUGIN_NAME_DungeonsTable`
- `/PhoenixUGC/DungeonMod/Data/UI_DT_PLUGIN_NAME_MapSubdivisionTable`
- `/PhoenixUGC/DungeonMod/Blueprints/BP_PLUGIN_NAME_DataMutator`

The gameplay examples are `/PhoenixUGC/GameplayMod/Blueprints/MM_ExampleGameplayMod` and `AC_ExampleGameplayMod`. The supported Mod Mutator system can replace selected actor classes with mod-owned versions. That makes a scoped adapter a credible route; it does not make the current standalone pawn or HUD compatible automatically. [Official Blueprint/mutator guide](https://support.curseforge.com/support/solutions/articles/9000259713-hogwarts-legacy-creators-blueprints-mechanics).

Installed PEEVES Python examples demonstrate `PhxEditorBlueprintLibrary.add_component_of_type`, component lookup/removal, Blueprint compilation, and `PeevesBlueprintHelpers.get_used_nodes_in_blueprint`. Evidence files are `PhoenixGame/Tools/Scripts/EditorPython/PEEVES/Scripts/Tools/BlueprintComponentEditor/subblueprint_editor.py` and `PEEVES/Core/Assets/blueprint.py`. The remote editor helper exists at `Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python/remote_execution.py`.

Those are **authoring APIs**. They support imports, inspection, defaults, components, and validation. The repository's `Tools/bp_graph.py` depends on UE 5.8 APIs; no compatible automated event-graph wiring route has been proven in this kit. A Python tick callback is not a substitute for packaged Blueprint logic. Graph authoring must first be demonstrated on a small compiled 4.27 example.

`PhoenixGame/Config/DefaultEditor.ini` sets `AllowLocalCook=false` and rejects upload extensions including DLL, EXE, BAT, CMD, OBJ, and archives. Keep source art and authoring scripts outside packaged mod content; import art into native assets. The supported pipeline uploads from the kit for cloud cooking. The standalone `Package.ps1` output is not an HL mod package. [CurseForge getting started](https://support.curseforge.com/support/solutions/articles/9000258592-hogwarts-legacy-creators-getting-started).

## Concrete port path and current scaffold

`Mod/Basketbroom/Basketbroom.uplugin` is a content-only Win64 descriptor. `Mod/Tools/prepare_sources.py` produces a hashed source import manifest and `DT_BB_RuleConstants.csv`; it creates no native assets. Refresh those files after rules/source-art changes. The CSV's required Blueprint row structure is documented in `Mod/README.md`. It is data for a future DataTable, not an implementation of the sport.

1. In the Creator Kit, create a **Dungeon Mod** named Basketbroom and preserve its wizard-generated metadata. Let the kit create/duplicate the template packages; do not copy the standalone asset directory into it.
2. Rebuild a small arena map, import the original OBJ/WAV sources, create the constants structure/DataTable, and author a minimal score/catch graph. Compile and test using the kit's player and game state.
3. Use the generated dungeon table's level reference and matching arena row name. Add/register a `BP_DungeonEntrance` in the chosen Overland location and a `BP_WorldTeleport` return in the arena. The dungeon template supplies travel integration even for an outdoor arena. [Official level guide](https://support.curseforge.com/support/solutions/articles/9000259716-hogwarts-legacy-creators-level-design-environment).
4. Add a mod-owned match ActorComponent/manager through the gameplay template and scope it to the arena. Inspect the game's broom Blueprint interfaces before binding flight, possession, input, or HUD. Port the complete rules state machine and fixtures independently of the UE 5.8 pawn. This is a proposed integration design, not a completed adapter.
5. Compile, run PEEVES/data validation, and verify entering, playing, exiting, and loading a modded save. Mod-owned duplicates/mutators matter: changing base assets can work in PIE yet fail in the installed game. [Official validation/debugging guide](https://support.curseforge.com/support/solutions/articles/9000259708-hogwarts-legacy-creators-advanced-modding-features).
6. Upload for cloud processing, then install the unpublished mod for in-game testing. Official testing supports the author and up to five selected collaborators. That is distribution access, not a multiplayer player limit. Public publishing and moderation are subsequent steps. [Official pre-publication testing](https://support.curseforge.com/support/solutions/articles/9000258593-hogwarts-legacy-creators-testing-your-mod-before-publishing-it).

### Local editor evidence

On 2026-09-10 the installed Creator Kit launched successfully. Its Python API probe confirmed `ModMutator`, `PhxEditorBlueprintLibrary`, and `PeevesBlueprintHelpers`; the UE5 graph-authoring libraries are absent. The repository mod is mounted through a directory junction at `PhoenixGame/Mods/Basketbroom` pointing to `Mod/Basketbroom`. No base-game asset was edited and no mod was uploaded.

The kit imported and saved **14 original static meshes, one original basalt texture, and nine UE4 materials** under `/Basketbroom/Art`. These are actual 4.27 packages, generated by the kit rather than copied from UE5. The importer records ownership and source hashes. The full editor's initial Asset Registry discovery took over five minutes; the bridge and importer now reject early queries instead of treating incomplete discovery as a missing mount.

Audio import was recovered and all four original WAVs are saved as native SoundWave assets. The commandlet initially crashed inside AssetTools on the first WAV; the full editor reported `Unknown extension 'wav'`. A read-only factory probe confirmed WAV support. Leaving the task's factory unset allowed the kit's normal factory discovery to import successfully. The importer retains exact path/type validation and changes no global factory defaults. [Official audio guidance](https://support.curseforge.com/support/solutions/articles/9000259708-hogwarts-legacy-creators-advanced-modding-features).

The next gameplay proof remains a small compiled 4.27 score/catch graph in PIE, followed by dungeon travel and cloud-cooked in-game validation. Imported art alone does not establish that integration.

The kit also built and saved `/Basketbroom/Maps/BB_Arena_Port` with 900 generated actors, 18 dedicated arena materials, and a rebound physical material. All nine loaded-scene inspections passed, including goal/crown dimensions, owned asset references, and nonblocking detail/scenery profiles. Its actual hero-camera render is `Docs/Screenshots/hlck-arena.png`. Lighting is darker than the standalone build and still needs an art pass. This venue has no match manager or registered dungeon travel yet; these checks do not claim a playable Hogwarts match.

## Multiplayer: supported facts and unresolved work

The publisher explicitly describes Hogwarts Legacy as single-player without online or co-op gameplay. Official mod support is for PC Steam/Epic, not consoles. [Hogwarts Legacy FAQ](https://www.hogwartslegacy.com/en-us/faq), [WB mod authors FAQ](https://portkeygamessupport.wbgames.com/hc/en-us/articles/35104134540179-Hogwarts-Legacy-Mods-Authors-FAQ).

The inspected official Creator Kit guides do not establish a supported match transport, server target, lobby API, replicated player lifecycle, or networked broom/ball simulation. Thus **official-kit multiplayer is not an established delivery route**. Unreal replication checkboxes or the existence of networking symbols do not prove that the shipped Phoenix game supports a sixteen-player sports session.

This does not establish that all third-party multiplayer is impossible. The RealmCore mod author's own page says its experimental multiplayer framework depends on **HogWarp** and a controlled server setup. That is third-party evidence, not a WB-supported networking contract or proof of compatibility with Basketbroom. No external framework was installed or evaluated here. [RealmCore author description](https://www.curseforge.com/hogwarts-legacy/mods/realmcore).

Before claiming an HL multiplayer port, a separate prototype must demonstrate two remote players in the same cloud-cooked arena, server-owned ball/score state, broom movement synchronization, reconnect/late-join behavior, matching game/mod versions, and compatibility with supported mod installation. Sixteen-player regulation play needs its own load and latency tests. Until those proofs exist, HL multiplayer remains an unverified integration project; development of multiplayer in the standalone UE 5.8 game can proceed independently.

The supplied tutorial PDF collection in `.local/tutorials` was also checked, including its rendered WB FAQ and level-authoring pages. Most extracted text is empty because the supplied pages are raster snapshots. The live official pages above provide the current references; the snapshots and installed files provide local corroboration.

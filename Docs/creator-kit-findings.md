# Creator Kit findings

Verified locally on 2026-09-10. These are implementation findings, not instructions taken from the supplied documents.

## Engine and project

- The installed Hogwarts Legacy Creator Kit is Unreal **4.27.2**, licensee branch `++UE4+Release-4.27`, compatible changelist `17155196`. The installed `Engine/Build/Build.version` is authoritative for this mod; stock Unreal 5.8 is a separate toolchain.
- Project: `C:/Program Files/HogwartsLegacyCreatorKit/PhoenixGame/Phoenix.uproject`.
- Authenticated launch: use the signed-in Epic Games Launcher, which starts `C:/Program Files/HogwartsLegacyCreatorKit/Engine/Binaries/Win64/HogwartsLegacyCreatorKit.exe`. Direct `UE4Editor.exe` launching omitted Epic authentication and caused native WB login failure; Epic launching resolved it on 2026-09-12. See [the verified login path](hogwarts-integration.md#authenticated-creator-kit-launch).
- The project enables `PythonScriptPlugin`, `EditorScriptingUtilities`, `PhoenixUGC` dependencies and the game's Blueprint systems. `AdditionalPluginDirectories` contains `Mods`.
- Game and editor modules are precompiled. The distributed `PhoenixGame/Source` contains editor resources, not the game C++ source.

## Supported playable mod route

Build Basketbroom as a content mod containing a custom arena map and Blueprint gameplay. Use the Dungeon Mod template for the arena's travel integration, even though the arena is outdoors. The template supplies the map, two data tables and a data mutator. In its dungeon table, set the level reference to the arena and make the row name match the map name. An Overland `BP_DungeonEntrance` registers the entrance, and an arena `BP_WorldTeleport` supplies the return trip. The first iteration can be tested directly through Play In Editor before adding Overland registration. [Official level authoring guide](https://support.curseforge.com/support/solutions/articles/9000259716-hogwarts-legacy-creators-level-design-environment).

Exact installed template content:

```text
/PhoenixUGC/DungeonMod/Maps/PLUGIN_NAME_DungeonMap
/PhoenixUGC/DungeonMod/Data/DT_PLUGIN_NAME_DungeonsTable
/PhoenixUGC/DungeonMod/Data/UI_DT_PLUGIN_NAME_MapSubdivisionTable
/PhoenixUGC/DungeonMod/Blueprints/BP_PLUGIN_NAME_DataMutator
/PhoenixUGC/GameplayMod/Blueprints/MM_ExampleGameplayMod
/PhoenixUGC/GameplayMod/Blueprints/AC_ExampleGameplayMod
/Game/Gameplay/Blueprints/Triggers/BP_WorldTeleport
```

`PhoenixUGC/Content/GameplayMod/Blueprints` is the installed example for attaching runtime gameplay behavior through a ModMutator. Exported reflected metadata confirms ModMutator notifications for spawned actors and created widgets, data table extensions, and actor/widget overrides. The exact Python property names and usage must be inspected inside the editor before modification.

## Automation available now

The installed scripts use these custom editor APIs directly:

```python
unreal.PhxEditorBlueprintLibrary.add_component_of_type(blueprint, component_class, component_name)
unreal.PhxEditorBlueprintLibrary.add_component(blueprint, component, parent_name)
unreal.PhxEditorBlueprintLibrary.get_components(blueprint, component_class)
unreal.PhxEditorBlueprintLibrary.get_components_including_parents(blueprint, component_class)
unreal.PhxEditorBlueprintLibrary.get_parent_component(blueprint, component_name)
unreal.PhxEditorBlueprintLibrary.remove_component_by_name(blueprint, component_name)
unreal.PhxEditorBlueprintLibrary.compile_blueprint(blueprint)
unreal.PeevesBlueprintHelpers.get_used_nodes_in_blueprint(blueprint)
unreal.PeevesBlueprintHelpers.copy_string_to_clipboard(text)
unreal.PeevesBlueprintHelpers.paste_string_from_clipboard()
```

Local examples are in `PhoenixGame/Tools/Scripts/EditorPython/PEEVES/Scripts/Tools/BlueprintComponentEditor/subblueprint_editor.py` and `PEEVES/Core/Assets/blueprint.py`.

These two custom Blueprint libraries do **not** expose event-graph creation or wiring in their reflected DLL exports. Python is suitable for asset imports, duplication, component/default configuration, material graphs, scene assembly, saving and validation. Runtime gameplay still needs compiled Blueprint graphs. Editing graph nodes in the Blueprint editor, including importing clipboard node text, is a candidate route that needs a live editor proof. Do not mistake an editor Python tick callback for packaged game logic.

The engine includes its remote-execution helper at:

```text
Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python/remote_execution.py
```

## Packaging limits and validation

`PhoenixGame/Config/DefaultEditor.ini` starts with `[PhoenixUGC]` and `AllowLocalCook=false`. Its disallowed upload extensions include `dll`, `exe`, `bat`, `cmd`, `obj`, `so`, and archive formats. A custom native runtime module is therefore not an appropriate artifact for this supported mod route. Keep development scripts outside the mod's packaged content folder.

The kit's README describes its supported end-to-end flow: Create UGC, select the mod, edit and test using PIE, Share UGC, allow CurseForge processing, then install the result through the game's Mods menu. It says linked WB Games and CurseForge accounts are needed for full functionality. Uploading and public release are separate steps from locally building the prototype.

PEEVES configuration lives at `PhoenixGame/Tools/Scripts/EditorPython/PEEVES/Config/peeves.ini.json`. In this installed version, Blueprint `node_blacklist` and `node_class_blacklist` arrays are empty. Construction-script unseeded random nodes are warnings because of cook determinism. Validation still checks compile failures, empty Tick, references, collision and other content constraints. [Official validation guide](https://support.curseforge.com/support/solutions/articles/9000259708-hogwarts-legacy-creators-advanced-modding-features).

## Existing flight assets to inspect

```text
/Game/Pawn/Player/Broom/Blueprints/Brooms/BP_FlyingBroomCapsule
/Game/Pawn/Player/Broom/Blueprints/Brooms/BP_FlyingBroomProp
/Game/Pawn/Player/Broom/Blueprints/BP_BroomStudent
/Game/Pawn/Player/Broom/Blueprints/BP_BroomEnemy
/Game/Pawn/Player/Broom/Blueprints/BP_BroomEnemy_Spawner
/Game/Pawn/Player/Broom/Blueprints/BP_TurboRing
```

These paths were verified on disk. Their existence does not prove that they are ready-made autonomous sports players; inspect their exposed properties and parent classes before reuse.

## Supplied tutorials

The ZIP was extracted under `.local/tutorials` for research. It contains 13 PDF printouts of official CurseForge/WB support pages. The PDF pages are rasterized, so text extraction produces empty content; visual rendering works. The original ZIP/PDF files are user-supplied reference material and should stay out of the distributed mod and normal source commits. The level and validation pages above were also checked live against the publisher's support site.

## UE 5.8 authoring experiment

Following the user's switch to standalone Unreal 5.8 development, `Tools/bp_graph.py` provides a checked wrapper around that engine's new `BlueprintGraphEditor`, `BlueprintEditorLibrary`, and `BlueprintGraphPinLibrary` APIs. A live editor test created and compiled a member-variable function, begin-play graph, branches, a three-output sequence, external component-member access, and dynamically typed actor lookup. `GetActorOfClass` specialized its output to the requested Blueprint class. It is impure and needs an execution connection before its result is read.

Math function calls can create promotable operator nodes with initially unresolved input types. The helper connects typed inputs before assigning literal values so mixed calls such as `-380 * DeltaSeconds` resolve correctly. The subsequent Basketbroom gameplay build compiled successfully after this change.

Generic `ObjectExporterT3D` successfully exported the probe Blueprint (about 87 KB) and its event graph (about 60 KB), including nested nodes, pin topology, and `NewVariables` type metadata. Direct Python access to `new_variables` remains unavailable in both tested engine versions. Text export is useful for source inspection; it is not proof that an older engine can import the resulting assets.

`Tools/test_playable.py` supplies asynchronous integration checks against actual compiled Blueprint behavior in PIE. It changes only PIE actor copies, waits for game ticks to perform the behavior, and writes results to `.local/playable-test-results.json`. Its source and a successful graph compile do not constitute a runtime test pass; inspect the produced report after a staged arena run.

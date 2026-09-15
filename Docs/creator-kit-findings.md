# creator kit findings

verified locally on 2026/09/10. these are implementation findings, not instructions taken from the supplied documents.

## engine and project

- the installed hogwarts legacy creator kit is unreal **4.27.2**, licensee branch `++UE4+Release-4.27`, compatible changelist `17155196`. the installed `Engine/Build/Build.version` is authoritative for this mod; stock unreal 5.8 is a separate toolchain.
- Project: `C:/Program Files/HogwartsLegacyCreatorKit/PhoenixGame/Phoenix.uproject`.
- authenticated launch: use the signed-in epic games launcher, which starts `C:/Program Files/HogwartsLegacyCreatorKit/Engine/Binaries/Win64/HogwartsLegacyCreatorKit.exe`. direct `UE4Editor.exe` launching omitted epic authentication and caused native wb login failure; epic launching resolved it on 2026/09/12. see [the verified login path](hogwarts-integration.md#authenticated-creator-kit-launch).
- the project enables `pythonscriptplugin`, `editorscriptingutilities`, `phoenixugc` dependencies and the game's blueprint systems. `additionalplugindirectories` contains `Mods`.
- game and editor modules are precompiled. the distributed `PhoenixGame/Source` contains editor resources, not the game c++ source.

## supported playable mod route

build basketbroom as a content mod containing a custom arena map and blueprint gameplay. use the dungeon mod template for the arena's travel integration, even though the arena is outdoors. the template supplies the map, two data tables and a data mutator. in its dungeon table, set the level reference to the arena and make the row name match the map name. an overland `bp_dungeonentrance` registers the entrance, and an arena `bp_worldteleport` supplies the return trip. the first iteration can be tested directly through play in editor before adding overland registration. [official level authoring guide](https://support.curseforge.com/support/solutions/articles/9000259716-hogwarts-legacy-creators-level-design-environment).

exact installed template content:

```text
/PhoenixUGC/DungeonMod/Maps/PLUGIN_NAME_DungeonMap
/PhoenixUGC/DungeonMod/Data/DT_PLUGIN_NAME_DungeonsTable
/PhoenixUGC/DungeonMod/Data/UI_DT_PLUGIN_NAME_MapSubdivisionTable
/PhoenixUGC/DungeonMod/Blueprints/BP_PLUGIN_NAME_DataMutator
/PhoenixUGC/GameplayMod/Blueprints/MM_ExampleGameplayMod
/PhoenixUGC/GameplayMod/Blueprints/AC_ExampleGameplayMod
/Game/Gameplay/Blueprints/Triggers/BP_WorldTeleport
```

`PhoenixUGC/Content/GameplayMod/Blueprints` is the installed example for attaching runtime gameplay behavior through a ModMutator. exported reflected metadata confirms modmutator notifications for spawned actors and created widgets, data table extensions, and actor/widget overrides. the exact python property names and usage must be inspected inside the editor before modification.

## automation available now

the installed scripts use these custom editor apis directly:

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

local examples are in `PhoenixGame/Tools/Scripts/EditorPython/PEEVES/Scripts/Tools/BlueprintComponentEditor/subblueprint_editor.py` and `PEEVES/Core/Assets/blueprint.py`.

these two custom blueprint libraries do **not** expose event-graph creation or wiring in their reflected dll exports. python is suitable for asset imports, duplication, component/default configuration, material graphs, scene assembly, saving and validation. runtime gameplay still needs compiled blueprint graphs. editing graph nodes in the blueprint editor, including importing clipboard node text, is a candidate route that needs a live editor proof. do not mistake an editor python tick callback for packaged game logic.

the engine includes its remote-execution helper at:

```text
Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python/remote_execution.py
```

## packaging limits and validation

`PhoenixGame/Config/DefaultEditor.ini` starts with `[phoenixugc]` and `AllowLocalCook=false`. its disallowed upload extensions include `dll`, `exe`, `bat`, `cmd`, `obj`, `so`, and archive formats. a custom native runtime module is therefore not an appropriate artifact for this supported mod route. keep development scripts outside the mod's packaged content folder.

the kit's readme describes its supported end-to-end flow: create ugc, select the mod, edit and test using pie, share ugc, allow curseforge processing, then install the result through the game's mods menu. it says linked wb games and curseforge accounts are needed for full functionality. uploading and public release are separate steps from locally building the prototype.

peeves configuration lives at `PhoenixGame/Tools/Scripts/EditorPython/PEEVES/Config/peeves.ini.json`. in this installed version, blueprint `node_blacklist` and `node_class_blacklist` arrays are empty. construction-script unseeded random nodes are warnings because of cook determinism. validation still checks compile failures, empty tick, references, collision and other content constraints. [official validation guide](https://support.curseforge.com/support/solutions/articles/9000259708-hogwarts-legacy-creators-advanced-modding-features).

## existing flight assets to inspect

```text
/Game/Pawn/Player/Broom/Blueprints/Brooms/BP_FlyingBroomCapsule
/Game/Pawn/Player/Broom/Blueprints/Brooms/BP_FlyingBroomProp
/Game/Pawn/Player/Broom/Blueprints/BP_BroomStudent
/Game/Pawn/Player/Broom/Blueprints/BP_BroomEnemy
/Game/Pawn/Player/Broom/Blueprints/BP_BroomEnemy_Spawner
/Game/Pawn/Player/Broom/Blueprints/BP_TurboRing
```

these paths were verified on disk. their existence does not prove that they are ready-made autonomous sports players; inspect their exposed properties and parent classes before reuse.

## supplied tutorials

the zip was extracted under `.local/tutorials` for research. it contains 13 pdf printouts of official CurseForge/WB support pages. the pdf pages are rasterized, so text extraction produces empty content; visual rendering works. the original ZIP/PDF files are user-supplied reference material and should stay out of the distributed mod and normal source commits. the level and validation pages above were also checked live against the publisher's support site.

## ue 5.8 authoring experiment

following the user's switch to standalone unreal 5.8 development, `Tools/bp_graph.py` provides a checked wrapper around that engine's new `blueprintgrapheditor`, `blueprinteditorlibrary`, and `blueprintgraphpinlibrary` APIs. a live editor test created and compiled a member-variable function, begin-play graph, branches, a three-output sequence, external component-member access, and dynamically typed actor lookup. `getactorofclass` specialized its output to the requested blueprint class. it is impure and needs an execution connection before its result is read.

math function calls can create promotable operator nodes with initially unresolved input types. the helper connects typed inputs before assigning literal values so mixed calls such as `-380 * deltaseconds` resolve correctly. the subsequent basketbroom gameplay build compiled successfully after this change.

generic `objectexportert3d` successfully exported the probe blueprint (about 87 kb) and its event graph (about 60 kb), including nested nodes, pin topology, and `newvariables` type metadata. direct python access to `new_variables` remains unavailable in both tested engine versions. text export is useful for source inspection; it is not proof that an older engine can import the resulting assets.

`Tools/test_playable.py` supplies asynchronous integration checks against actual compiled blueprint behavior in PIE. it changes only pie actor copies, waits for game ticks to perform the behavior, and writes results to `.local/playable-test-results.json`. its source and a successful graph compile do not constitute a runtime test pass; inspect the produced report after a staged arena run.

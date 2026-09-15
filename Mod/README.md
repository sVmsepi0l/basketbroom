# hogwarts legacy arena port

this contains a native **creator kit arena, registered dungeon, and original art/audio assets**, not yet an installable or playable hogwarts legacy match. the working standalone ue 5.8 game is in `developmentharness`; its binary assets must not be copied here.

`Basketbroom/Basketbroom.uplugin` is a content-only win64 plugin descriptor. the repo plugin is already mounted and its supported dungeon mod template assets have been duplicated and configured natively. choose the existing **basketbroom** with **set active mod**; do not recreate it with the wizard. preserve account/platform metadata subsequently authored by the kit.

run `python Mod/Tools/prepare_sources.py` from the repository to refresh `SourceData/port-manifest.json` and `SourceData/DT_BB_RuleConstants.csv` from the current rules and original OBJ/WAV/PNG sources. the manifest currently contains 14 arena meshes, four original sound cues, and the original basalt texture. it records sha-256 hashes, obj topology counts, audio format/peak checks, png dimensions/CRC checks, intended import paths, and native assets still missing. development scripts, manifests, csv sources, and source art stay outside the mod's packaged `Basketbroom/Content` directory.

run `python Mod/Tools/import_sources.py --validate-sources` for read-only source validation with ordinary Python. it calls no unreal apis and creates no content. the source helper supports the creator kit's python 3.7 syntax.

after mounting this repository's `Mod/Basketbroom` directory at the creator kit's `PhoenixGame/Mods/Basketbroom`, restarting the kit, and waiting for its initial asset scan, run this in the full creator kit python console:

```python
import sys
sys.path.insert(0, r"C:\Git\basketbroom\Mod\Tools")
import import_sources
result = import_sources.build()
```

the helper checks ue **4.27**, the phoenix project, the physical mod directory (junctions are supported), and the `/Basketbroom` mount before writing. it imports only manifest-listed original OBJ/WAV/PNG files. it keeps the authored centimeter coordinates and z-up basis, creates no automatic collision or lightmap uvs, and creates nine simple ue4 materials with a world-projected basalt texture. it does not create or compile a gameplay blueprint, load a map, cook, upload, or modify base-game assets. the non-power-of-two 1254-square texture is retained as supplied; ue4 texture streaming/mip quality, mesh collision, lods, lightmaps, and lighting still require a separate arena pass.

for a first mesh-only smoke test, use `import_sources.build(asset_names=["SM_BB_LargeHoop"], create_materials=False)`. normal `build()` resumes after that test. each completed asset is saved with importer ownership and source-hash metadata, and progress is written to `.local/hlck/import-result.json`. matching imports are skipped on another run; `force=true` refreshes importer-owned assets. existing assets without this helper's ownership metadata are preserved and cause an explicit failure. material authoring can be omitted with `create_materials=false`; if that api is absent, the report records the omission.

the helper uses epic's public [UE4.27 AssetImportTask](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AssetImportTask?application_version=4.27), [FbxImportUI](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/FbxImportUI?application_version=4.27), [EditorAssetLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorAssetLibrary?application_version=4.27), and [MaterialEditingLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialEditingLibrary?application_version=4.27) APIs. source validation does not establish a successful live import; the import report records the actual editor outcome.

on 2026/09/10, the full creator kit successfully imported all 19 sources and nine materials. wav tasks use the kit's normal factory discovery; explicitly assigning soundfactory fails in this kit. the importer records progress atomically and tolerates brief windows report-reader locks.

after importing, run `import build_arena_port; build_arena_port.build()` to create `/Basketbroom/Maps/BB_Arena_Port`. this was built and saved in the actual UE4.27 kit with 900 generated actors, 18 separate arena materials, and a rebound physical material. the helper shares original geometry placement with the ue5 authoring script, but creates new 4.27 packages. it protects existing maps with an ownership marker, preserves unrelated actors, and never edits base-game packages. the source arena remains separate from the registered dungeon below; neither has match gameplay yet.

on 2026/09/12, `Tools/stage_hlck_dungeon.py` saved a separate `/Basketbroom/Maps/Basketbroom_DungeonMap`, both native dungeon datatables, a data mutator with two verified table extensions, and owned entrance/exit blueprint copies. the compiled entrance default points to the owned dungeon row. native exit/entry anchors are saved, and read-only validation passes 27/27 live checks. the original arena file is unchanged.

`Tools/register_hlck_dungeon.py` successfully registered one native transient entrance through the public beaconmanager api while basketbroom was active. [ModEdits.sql](Basketbroom/Content/ModEdits.sql) is the only content file changed by registration. the return spawn and map beacon are east of the hogwarts quidditch gate at `(329400, -466800, -85380.66)` cm, yaw `180`. the native loader recreates the stock entrance from sql; no installed overland map was saved. live database readback, independent in-memory sql validation, installed database/map hash checks and empty dirty-package checks passed. actual entry/return, navigation/minimap, match gameplay and cloud-cooked operation remain unverified. see [the integration evidence](../Docs/hogwarts-integration.md).

normal play on the owned dungeon visibly spawned the native robed character on the field. automated runtime assertions remain **not_run** because the observer failed during the editor-to-pie transition; that fixture is fixed and covered by cpu-only cleanup regressions, without another live run. the large first-play shader queue left less than 1 gb of physical memory free at one sample, so the exact session was ended through the supported api and the kit closed. all mod content and installed maps remained unchanged. only `PhoenixDynData.sqlite` changed during native startup; its preserved post-close copy passes sqlite integrity checking, consistent with the inspected native dynamic-database cache path. no installed database was restored. prepare shader caches and a bounded memory plan before another play attempt.

to import the constants csv in the **4.27 creator kit**, first create the blueprint structure `st_bb_ruleconstant` with `value` (float), `unit` (string), and `rulepath` (String). import the csv as a datatable using that structure. the first column is the row name. no structure or datatable asset has been created yet. numeric constants do not implement adjudication; port and test the state transitions separately.

see [the integration findings](../Docs/hogwarts-integration.md) for verified limits, the native template paths, and the steps required before a playable mod can be claimed.

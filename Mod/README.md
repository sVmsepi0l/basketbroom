# Hogwarts Legacy arena port

This contains a native **Creator Kit arena and original art/audio assets**, not yet an installable or playable Hogwarts Legacy match. The working standalone UE 5.8 game is in `DevelopmentHarness`; its binary assets must not be copied here.

`Basketbroom/Basketbroom.uplugin` is a content-only Win64 plugin descriptor. The Creator Kit's **Dungeon Mod** wizard must create its actual mod assets and platform metadata. Preserve any metadata the wizard adds.

Run `python Mod/Tools/prepare_sources.py` from the repository to refresh `SourceData/port-manifest.json` and `SourceData/DT_BB_RuleConstants.csv` from the current rules and original OBJ/WAV/PNG sources. The manifest currently contains 14 arena meshes, four original sound cues, and the original basalt texture. It records SHA-256 hashes, OBJ topology counts, audio format/peak checks, PNG dimensions/CRC checks, intended import paths, and native assets still missing. Development scripts, manifests, CSV sources, and source art stay outside the mod's packaged `Basketbroom/Content` directory.

Run `python Mod/Tools/import_sources.py --validate-sources` for read-only source validation with ordinary Python. It calls no Unreal APIs and creates no content. The source helper supports the Creator Kit's Python 3.7 syntax.

After mounting this repository's `Mod/Basketbroom` directory at the Creator Kit's `PhoenixGame/Mods/Basketbroom`, restarting the kit, and waiting for its initial asset scan, run this in the full Creator Kit Python console:

```python
import sys
sys.path.insert(0, r"C:\Git\basketbroom\Mod\Tools")
import import_sources
result = import_sources.build()
```

The helper checks UE **4.27**, the Phoenix project, the physical mod directory (junctions are supported), and the `/Basketbroom` mount before writing. It imports only manifest-listed original OBJ/WAV/PNG files. It keeps the authored centimeter coordinates and Z-up basis, creates no automatic collision or lightmap UVs, and creates nine simple UE4 materials with a world-projected basalt texture. It does not create or compile a gameplay Blueprint, load a map, cook, upload, or modify base-game assets. The non-power-of-two 1254-square texture is retained as supplied; UE4 texture streaming/mip quality, mesh collision, LODs, lightmaps, and lighting still require a separate arena pass.

For a first mesh-only smoke test, use `import_sources.build(asset_names=["SM_BB_LargeHoop"], create_materials=False)`. Normal `build()` resumes after that test. Each completed asset is saved with importer ownership and source-hash metadata, and progress is written to `.local/hlck/import-result.json`. Matching imports are skipped on another run; `force=True` refreshes importer-owned assets. Existing assets without this helper's ownership metadata are preserved and cause an explicit failure. Material authoring can be omitted with `create_materials=False`; if that API is absent, the report records the omission.

The helper uses Epic's public [UE4.27 AssetImportTask](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AssetImportTask?application_version=4.27), [FbxImportUI](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/FbxImportUI?application_version=4.27), [EditorAssetLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorAssetLibrary?application_version=4.27), and [MaterialEditingLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialEditingLibrary?application_version=4.27) APIs. Source validation does not establish a successful live import; the import report records the actual editor outcome.

On 2026-09-10, the full Creator Kit successfully imported all 19 sources and nine materials. WAV tasks use the kit's normal factory discovery; explicitly assigning SoundFactory fails in this kit. The importer records progress atomically and tolerates brief Windows report-reader locks.

After importing, run `import build_arena_port; build_arena_port.build()` to create `/Basketbroom/Maps/BB_Arena_Port`. This was built and saved in the actual UE4.27 kit with 900 generated actors, 18 separate arena materials, and a rebound physical material. The helper shares original geometry placement with the UE5 authoring script, but creates new 4.27 packages. It protects existing maps with an ownership marker, preserves unrelated actors, and never edits base-game packages. The venue currently has no match manager, dungeon registration, entrance/exit travel, or verified in-game gameplay.

To import the constants CSV in the **4.27 Creator Kit**, first create the Blueprint structure `ST_BB_RuleConstant` with `Value` (Float), `Unit` (String), and `RulePath` (String). Import the CSV as a DataTable using that structure. The first column is the row name. No structure or DataTable asset has been created yet. Numeric constants do not implement adjudication; port and test the state transitions separately.

See [the integration findings](../Docs/hogwarts-integration.md) for verified limits, the native template paths, and the steps required before a playable mod can be claimed.

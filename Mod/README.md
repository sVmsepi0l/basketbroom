# Hogwarts Legacy port sources

This is a **source scaffold**, not an installable or playable Hogwarts Legacy mod. The working standalone UE 5.8 game is in `DevelopmentHarness`; its binary assets must not be copied here.

`Basketbroom/Basketbroom.uplugin` is a content-only Win64 plugin descriptor. The Creator Kit's **Dungeon Mod** wizard must create its actual mod assets and platform metadata. Preserve any metadata the wizard adds.

Run `python Mod/Tools/prepare_sources.py` from the repository to refresh `SourceData/port-manifest.json` and `SourceData/DT_BB_RuleConstants.csv` from the current rules and original OBJ/WAV sources. The manifest records hashes, intended import paths, and native assets still missing. Development scripts, manifests, CSV sources, and OBJ files stay outside the mod's packaged `Basketbroom/Content` directory.

To import the constants CSV in the **4.27 Creator Kit**, first create the Blueprint structure `ST_BB_RuleConstant` with `Value` (Float), `Unit` (String), and `RulePath` (String). Import the CSV as a DataTable using that structure. The first column is the row name. No structure or DataTable asset has been created yet. Numeric constants do not implement adjudication; port and test the state transitions separately.

See [the integration findings](../Docs/hogwarts-integration.md) for verified limits, the native template paths, and the steps required before a playable mod can be claimed.

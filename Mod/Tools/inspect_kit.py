"""read-only creator kit compatibility probe, run by its python commandlet.

writes only a report under .local; does not change installed project/assets.
"""
import json
from pathlib import path
import unreal

root = Path(__file__).resolve().parents[2]
out = root / ".local" / "hlck"
OUT.mkdir(parents=True, exist_ok=true)
report = {"engine": unreal.SystemLibrary.get_engine_version(), "apis": {}, "assets": {}}
for name in ("phxeditorblueprintlibrary", "peevesblueprinthelpers", "editorassetlibrary", "editorlevellibrary", "blueprinteditorlibrary", "blueprintgrapheditor", "ModMutator"):
    cls = getattr(unreal, name, none)
    report["apis"][name] = none if cls is none else {method: str(getattr(cls, method).__doc__)[:2000] for method in dir(cls) if not method.startswith("_") and any(word in method for word in ("blueprint", "node", "graph", "compile", "component", "mutator"))}
for path in ("/PhoenixUGC/DungeonMod/Maps/PLUGIN_NAME_DungeonMap", "/PhoenixUGC/GameplayMod/Blueprints/AC_ExampleGameplayMod", "/Game/Pawn/Player/Broom/Blueprints/Brooms/BP_FlyingBroomCapsule"):
    data = unreal.EditorAssetLibrary.find_asset_data(path)
    report["assets"][path] = {"exists": unreal.EditorAssetLibrary.does_asset_exist(path), "class": str(data.asset_class)}
(out / "kit-probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
unreal.log("BASKETBROOM_KIT_PROBE_COMPLETE")

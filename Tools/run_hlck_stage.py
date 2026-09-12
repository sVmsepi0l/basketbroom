"""Run a checked Creator Kit stage through the local editor bridge."""
from pathlib import Path
import importlib
import sys
import unreal
ROOT = Path(__file__).resolve().parents[1]
if not unreal.SystemLibrary.get_engine_version().startswith("4.27."):
    raise RuntimeError("This stage runs only in Hogwarts Legacy Creator Kit")
sys.path.insert(0,str(ROOT / "Mod" / "Tools"))
args = globals().get("BRIDGE_ARGS", {})
registry_loading = unreal.AssetRegistryHelpers.get_asset_registry().is_loading_assets()
if args.get("operation", "inspect") in ("import", "arena"):
    if registry_loading:
        raise RuntimeError("Creator Kit is still discovering assets; retry after the initial scan completes")
    module = importlib.reload(importlib.import_module("import_sources"))
    if args.get("operation") == "arena":
        module = importlib.reload(importlib.import_module("build_arena_port"))
        RESULT = module.build()
    else:
        RESULT = module.build(asset_names=args.get("asset_names"), create_materials=args.get("create_materials",True))
else:
    RESULT = {"engine":unreal.SystemLibrary.get_engine_version(),
        "project":unreal.Paths.get_project_file_path(),
        "asset_registry_loading":registry_loading,
        "mod_mounted":None if registry_loading else unreal.EditorAssetLibrary.does_directory_exist("/Basketbroom")}

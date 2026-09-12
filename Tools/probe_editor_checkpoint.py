"""Read-only inventory of unsaved Unreal packages before a development restart."""
import json
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
LABEL = "hlck" if unreal.SystemLibrary.get_engine_version().startswith("4.") else "ue5"
RESULT = {
    "engine": unreal.SystemLibrary.get_engine_version(),
    "project": unreal.Paths.project_dir(),
    "dirty_maps": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    "dirty_content": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
    "read_only": True,
}
path = ROOT / ".local" / LABEL / "editor-checkpoint.json"
path.write_text(json.dumps(RESULT, indent=2) + "\n", encoding="utf-8")

"""Read-only inventory of unsaved Unreal packages before a development restart."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
LABEL = "hlck" if unreal.SystemLibrary.get_engine_version().startswith("4.") else "ue5"
RESULT = {
    "sampled_utc": datetime.now(timezone.utc).isoformat(),
    "process_id": os.getpid(),
    "engine": unreal.SystemLibrary.get_engine_version(),
    "project": unreal.Paths.project_dir(),
    "dirty_maps": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    "dirty_content": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
    "editor_world": unreal.EditorLevelLibrary.get_editor_world().get_path_name() if unreal.EditorLevelLibrary.get_editor_world() else None,
    "pie_worlds": [world.get_path_name() for world in unreal.EditorLevelLibrary.get_pie_worlds(True)],
    "read_only": True,
}
mod_manager = getattr(unreal, "GameModManagerSubsystem", None)
if mod_manager is not None:
    RESULT["has_active_editor_mod"] = bool(mod_manager.has_active_editor_mod_bp())
    RESULT["active_mod"] = str(mod_manager.get_active_mod_name_bp())
    RESULT["active_mod_content_path"] = str(mod_manager.get_active_mod_content_path_bp())
path = ROOT / ".local" / LABEL / "editor-checkpoint.json"
path.write_text(json.dumps(RESULT, indent=2) + "\n", encoding="utf-8")

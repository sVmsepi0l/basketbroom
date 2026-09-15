"""Read-only native editor context and reflected shader-readiness API inventory."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import unreal

ROOT = Path(__file__).resolve().parents[1]
project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.get_project_file_path())).resolve()
if project != Path(r"C:\Program Files\HogwartsLegacyCreatorKit\PhoenixGame\Phoenix.uproject").resolve():
    raise RuntimeError("Expected the installed Creator Kit project")
world = unreal.EditorLevelLibrary.get_editor_world()
RESULT = {
    "sampled_utc": datetime.now(timezone.utc).isoformat(),
    "process_id": os.getpid(), "read_only": True,
    "active_mod": str(unreal.GameModManagerSubsystem.get_active_mod_name_bp()),
    "editor_world": world.get_path_name() if world else None,
    "pie_worlds": [w.get_path_name() for w in unreal.EditorLevelLibrary.get_pie_worlds(True)],
    "shader_api": {}, "mod_api": {},
}
for class_name in dir(unreal):
    if not any(word in class_name.lower() for word in ("shader", "automation")):
        continue
    cls = getattr(unreal, class_name)
    methods = {}
    for name in dir(cls):
        if any(word in name.lower() for word in ("shader", "compiling", "compile", "loading")):
            member = getattr(cls, name, None)
            if callable(member):
                methods[name] = str(getattr(member, "__doc__", ""))
    if methods:
        RESULT["shader_api"][class_name] = methods
for name in dir(unreal.GameModManagerSubsystem):
    if "mod" in name.lower() and not name.startswith("_"):
        member = getattr(unreal.GameModManagerSubsystem, name, None)
        if callable(member):
            RESULT["mod_api"][name] = str(getattr(member, "__doc__", ""))
RESULT["mod_selection_api"] = {}
for class_name in dir(unreal):
    if not (class_name in ("GameModManagerSubsystem", "ModSupportBPFunctionLibrary") or class_name.startswith(("UGC", "ModAuth", "PhoenixUGC"))):
        continue
    cls = getattr(unreal, class_name)
    methods = {}
    for name in dir(cls):
        if "mod" in name.lower() and any(word in name.lower() for word in ("select", "active", "set_", "open", "edit")):
            member = getattr(cls, name, None)
            if callable(member):
                methods[name] = str(getattr(member, "__doc__", ""))
    if methods:
        RESULT["mod_selection_api"][class_name] = methods
RESULT["wait_options_api"] = str(getattr(getattr(unreal, "AutomationWaitForLoadingOptions", None), "__doc__", ""))
report = ROOT / ".local/hlck/startup-api.json"
report.write_text(json.dumps(RESULT, indent=2) + "\n", encoding="utf-8")
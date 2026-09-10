"""Read-only inspection of UE5.8 reflected PIE settings and network enum."""
import json
from pathlib import Path
import unreal

enum_class = getattr(unreal, "PlayNetMode", None)
enum_values = {}
if enum_class is not None:
    for name in dir(enum_class):
        if name.startswith("_"):
            continue
        value = getattr(enum_class, name)
        if not callable(value):
            enum_values[name] = {"repr": repr(value), "str": str(value), "type": str(type(value))}
settings_class = unreal.load_class(None, "/Script/UnrealEd.LevelEditorPlaySettings")
settings = unreal.get_default_object(settings_class) if settings_class else None
properties = {}
if settings:
    for name in ("PlayNetMode", "play_net_mode", "RunUnderOneProcess", "run_under_one_process",
                 "PlayNumberOfClients", "play_number_of_clients", "bLaunchSeparateServer", "launch_separate_server"):
        try:
            value = settings.get_editor_property(name)
            properties[name] = {"repr": repr(value), "str": str(value), "type": str(type(value))}
        except Exception as error:
            properties[name] = {"error": str(error)}
RESULT = {"engine": unreal.SystemLibrary.get_engine_version(),
          "enum_doc": getattr(enum_class, "__doc__", None), "enum_values": enum_values,
          "enum_names": dir(enum_class) if enum_class else [], "settings": properties,
          "settings_doc": getattr(settings_class, "__doc__", None)}
destination = Path(__file__).resolve().parents[1] / ".local" / "native-play-settings-probe.json"
destination.write_text(json.dumps(RESULT, indent=2, default=str) + "\n", encoding="utf-8")

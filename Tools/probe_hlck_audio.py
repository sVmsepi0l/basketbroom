"""Read-only reflection of the installed Creator Kit's audio import factories.

Run through the editor bridge after asset discovery finishes. This creates only
transient factory objects; it imports, changes, and saves no content or defaults.
ScriptFactoryCanImport is deliberately not called: it is a Blueprint event,
not a Python exposure of the native FactoryCanImport virtual implementation.
"""
import json
from pathlib import Path

import unreal


def _value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "get_path_name"):
        return value.get_path_name()
    try:
        return [_value(item) for item in value]
    except TypeError:
        return str(value)


def _properties(obj):
    result = {"object": obj.get_path_name()}
    for key in ("formats", "editor_import", "supported_class", "create_new",
                "text", "edit_after_new", "import_priority", "auto_create_cue"):
        try:
            result[key] = _value(obj.get_editor_property(key))
        except Exception as error:
            result[key + "_unavailable"] = str(error)
    return result


def inspect():
    version = str(unreal.SystemLibrary.get_engine_version())
    if not version.startswith("4.27."):
        raise RuntimeError("This diagnostic targets the Creator Kit UE4.27 build")
    names = sorted(name for name in dir(unreal)
                   if "Factory" in name and any(part in name for part in ("Sound", "Audio", "Wave")))
    result = {
        "engine": version,
        "project": unreal.Paths.get_project_file_path(),
        "asset_registry_loading": unreal.AssetRegistryHelpers.get_asset_registry().is_loading_assets(),
        "audio_factory_classes": names,
        "factories": {},
    }
    # TextureFactory is a control: this importer is also used for the port's PNG.
    for name in sorted(set(names + ["SoundFactory", "TextureFactory"])):
        row = result["factories"][name] = {}
        try:
            cls = getattr(unreal, name)
            row["class_doc"] = (cls.__doc__ or "")[:12000]
            row["default"] = _properties(unreal.get_default_object(cls))
        except Exception as error:
            row["default_error"] = str(error)
        try:
            row["instance"] = _properties(getattr(unreal, name)())
        except Exception as error:
            row["instance_error"] = str(error)
    destination = Path(__file__).resolve().parents[1] / ".local" / "hlck" / "audio-factory-probe.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


RESULT = inspect()

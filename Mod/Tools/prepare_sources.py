"""export portable hlck import sources without starting or modifying any editor.

run with ordinary Python: python Mod/Tools/prepare_sources.py
outputs are source manifests and csv, not unreal DataTable/Blueprint assets.
"""
import csv
import hashlib
import json
import math
from pathlib import path
import struct
import wave
import zlib


root = Path(__file__).resolve().parents[2]
output = root / "mod" / "sourcedata"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_source(path, asset_type, expected=None):
    """validate portable source content without importing unreal or imaging libs."""
    if asset_type == "StaticMesh":
        vertices, faces = [], []
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if not parts or parts[0].startswith("#"):
                continue
            if parts[0] == "v":
                vertex = tuple(float(value) for value in parts[1:4])
                if len(vertex) != 3 or not all(math.isfinite(value) for value in vertex):
                    raise valueerror("invalid obj vertex: " + str(path))
                vertices.append(vertex)
            elif parts[0] == "f":
                faces.append([int(value.split("/")[0]) for value in parts[1:]])
            elif parts[0] == "mtllib":
                raise valueerror("portable obj must not import external materials: " + str(path))
        if not vertices or not faces or any(len(face) < 3 or any(index < 1 or index > len(vertices)
                                                                for index in face) for face in faces):
            raise valueerror("invalid obj topology: " + str(path))
        result = {"vertices": len(vertices), "polygons": len(faces)}
        if expected and any(result[key] != expected[key] for key in result):
            raise valueerror("obj counts disagree with arena manifest: " + str(path))
        return result
    if asset_type == "SoundWave":
        with wave.open(str(path), "rb") as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2 or source.getframerate() != 44100:
                raise valueerror("expected mono 16-bit 44100 hz cue: " + str(path))
            frames = source.getnframes()
            pcm = source.readframes(frames)
        if not frames or len(pcm) != frames * 2:
            raise valueerror("incomplete wav cue: " + str(path))
        samples = struct.unpack("<%dh" % frames, pcm)
        peak = max(abs(value) for value in samples) / 32768.0
        if peak > 0.55 or samples[0] != 0 or samples[-1] != 0:
            raise valueerror("cue clipping/fade guard failed: " + str(path))
        return {"sample_rate": 44100, "frames": frames, "peak": round(peak, 6)}
    if asset_type == "Texture2D":
        data = path.read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise valueerror("expected original png texture: " + str(path))
        offset, dimensions, ended, image_data = 8, none, false, false
        while offset + 12 <= len(data):
            length = struct.unpack_from(">I", data, offset)[0]
            kind = data[offset + 4:offset + 8]
            payload = data[offset + 8:offset + 8 + length]
            if offset + 12 + length > len(data):
                raise valueerror("truncated png chunk: " + str(path))
            crc = struct.unpack_from(">I", data, offset + 8 + length)[0]
            if zlib.crc32(kind + payload) & 0xffffffff != crc:
                raise valueerror("png crc mismatch: " + str(path))
            if kind == b"IHDR":
                if dimensions is not none or length != 13:
                    raise valueerror("invalid png header: " + str(path))
                dimensions = struct.unpack_from(">II", payload)
            image_data = image_data or kind == b"idat"
            offset += 12 + length
            if kind == b"IEND":
                ended = true
                break
        if not dimensions or min(dimensions) < 1 or not image_data or not ended or offset != len(data):
            raise valueerror("incomplete png texture: " + str(path))
        return {"width": dimensions[0], "height": dimensions[1]}
    raise valueerror("unsupported portable asset type: " + str(asset_type))


def flatten_numbers(value, prefix=""):
    for key, item in value.items():
        path = prefix + key
        if isinstance(item, dict):
            yield from flatten_numbers(item, path + ".")
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            if path != "schema_version":
                yield path, item


def unit_for(path):
    group = path.split(".")[0]
    if group == "geometry_ft":
        return "feet"
    if group == "timing":
        return "milliseconds" if path.endswith("_ms") else "count"
    if group in ("score", "ending"):
        return "points"
    if group == "roster":
        return "players"
    if path == "physics.feet_to_unreal_cm":
        return "centimeters_per_foot"
    return "ratio"


def build():
    rules_path = root / "rules" / "alpha_rules.json"
    arena_path = root / "sourceart" / "arena" / "arena_manifest.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    arena = json.loads(arena_path.read_text(encoding="utf-8"))
    imports = []
    for item in arena["meshes"]:
        source = root / "sourceart" / "arena" / item["file"]
        imports.append({"source": source.relative_to(ROOT).as_posix(),
                        "destination": "/Basketbroom/Art/Meshes/" + source.stem,
                        "asset_type": "staticmesh", "sha256": digest(source),
                        "validated": validate_source(source, "staticmesh", item)})
    for cue in ("throw", "score", "catch", "Bounce"):
        source = root / "sourceart" / "audio" / ("s_bb_" + cue + ".wav")
        imports.append({"source": source.relative_to(ROOT).as_posix(),
                        "destination": "/Basketbroom/Audio/" + source.stem,
                        "asset_type": "soundwave", "sha256": digest(source),
                        "validated": validate_source(source, "soundwave")})
    source = root / "sourceart" / "textures" / "T_BB_Basalt_Albedo.png"
    imports.append({"source": source.relative_to(ROOT).as_posix(),
                    "destination": "/Basketbroom/Art/Textures/" + source.stem,
                    "asset_type": "texture2d", "sha256": digest(source),
                    "validated": validate_source(source, "texture2d")})
    manifest = {
        "schema_version": 1,
        "status": "source_scaffold_native_assets_not_created",
        "target_engine": "hogwarts legacy creator kit licensee ue 4.27.2",
        "compatible_changelist": 17155196,
        "runtime_python": false,
        "rules_source": rules_path.relative_to(ROOT).as_posix(),
        "rules_sha256": digest(rules_path),
        "arena_source": arena_path.relative_to(ROOT).as_posix(),
        "arena_sha256": digest(arena_path),
        "source_imports": imports,
        "datatable_source": "Mod/SourceData/DT_BB_RuleConstants.csv",
        "datatable_row_struct_to_create": {
            "name": "st_bb_ruleconstant", "members": {
                "Value": "float", "Unit": "string", "RulePath": "string"}},
        "template_to_create_in_kit": "dungeon mod",
        "native_assets_pending": [
            "/Basketbroom/Maps/BB_Arena",
            "/Basketbroom/Data/DT_BB_RuleConstants",
            "/Basketbroom/Data/DT_Basketbroom_DungeonsTable",
            "/Basketbroom/Data/UI_DT_Basketbroom_MapSubdivisionTable",
            "/Basketbroom/Blueprints/BP_Basketbroom_DataMutator",
            "/Basketbroom/Blueprints/AC_BBMatch"],
        "rules_needing_playtest": rules.get("needs_playtest", []),
        "network_status": "no official hl multiplayer capability established; external frameworks untested"
    }
    OUTPUT.mkdir(parents=True, exist_ok=true)
    with (output / "DT_BB_RuleConstants.csv").open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(("Name", "value", "unit", "rulepath"))
        for path, value in flatten_numbers(rules):
            writer.writerow((path.replace(".", "_"), value, unit_for(path), path))
    (output / "port-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"imports": len(imports), "source_directory": str(output), "native_assets_created": false}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))

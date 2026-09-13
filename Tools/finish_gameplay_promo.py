"""Add illustrated bookends to verified native 4K60 Basketbroom gameplay.

Production: --gameplay take.mp4 --art plate.png --output-dir folder --name name
Use --prepare-only with --art to review the editable layout and PNG posters
before the gameplay file is ready. --layout accepts a previously emitted JSON.
--preflight creates a short, clearly labelled synthetic test in a fresh folder.

Only bookends are video-encoded. All 10,800 gameplay video packets/frames pass
through stream copy; no interpolation or duplicated gameplay frames. Gameplay
audio is shifted by exactly six seconds without gain changes, then encoded once
to stereo AAC with silence around it. Official link icons are composited from
the supplied PNGs, proportionally and without recolouring or drawing substitutes.
Requires FFmpeg/ffprobe, Pillow, and the supplied static Google Sans
Flex 72pt Black font. Every intro/outro text style uses that exact weight900 face.
"""

from __future__ import annotations

import argparse
from array import array
import copy
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

from PIL import Image, ImageFont


ROOT = Path(__file__).resolve().parents[1]
BRANDS = ROOT / "SourceArt/Promo/BrandIcons"
FONTS = ROOT / "SourceArt/Promo/Fonts"
FONT = FONTS / "GoogleSansFlex_72pt-Black.ttf"
FONT_FAMILY = "Google Sans Flex 72pt Black"
FONT_SHA256 = "2c74c29ab728c089dff8c5b36d3dc21f8858bbdb7c5fa410574faf98ff59c3e1"
WIDTH, HEIGHT, FPS = 3840, 2160, 60
INTRO, GAMEPLAY, OUTRO = 6, 180, 12
ICON_NAMES = {
    "instagram": "instagram-glyph-white.png", "x": "x-logo-white.png",
    "curseforge": "curseforge-logo-white.png", "website": "website-globe-white.png",
    "github": "github-invertocat-white.png",
}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command, *, cwd=None, log=None):
    if log:
        with Path(log).open("x", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError("FFmpeg failed; inspect " + str(log))
        return ""
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:])
    return result.stdout


def probe(ffprobe, path):
    return json.loads(run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))


def media_contract(data, width, height, seconds, *, audio=True):
    videos = [s for s in data["streams"] if s["codec_type"] == "video"]
    audios = [s for s in data["streams"] if s["codec_type"] == "audio"]
    if len(videos) != 1 or (audio and len(audios) != 1):
        raise ValueError("Expected one video stream and one gameplay audio stream")
    video = videos[0]
    if (video["width"], video["height"]) != (width, height):
        raise ValueError("Gameplay must already have the native target dimensions; no gameplay scaling is allowed")
    if video["codec_name"] != "h264" or video.get("profile") != "High" or video.get("pix_fmt") != "yuv420p":
        raise ValueError("Require H.264 High, 8-bit yuv420p for lossless video stream concatenation")
    if Fraction(video["avg_frame_rate"]) != FPS or Fraction(video["r_frame_rate"]) != FPS:
        raise ValueError("Require real constant 60 fps gameplay; no frame duplication/interpolation is performed")
    if int(video.get("nb_frames", -1)) != round(seconds * FPS):
        raise ValueError("Unexpected video frame count")
    if abs(float(video["duration"]) - seconds) > 1 / FPS / 2:
        raise ValueError("Unexpected video duration")
    if video.get("sample_aspect_ratio", "1:1") not in ("1:1", "N/A"):
        raise ValueError("Require square pixels")
    timebase = Fraction(video["time_base"])
    if timebase.numerator != 1 or timebase.denominator % FPS:
        raise ValueError("Video timebase must express exact 60 fps frames")
    if abs(float(video.get("start_time", 0))) > 1 / FPS / 2:
        raise ValueError("Video must begin at timestamp zero")
    if audio:
        sound = audios[0]
        if int(sound["sample_rate"]) != 48000 or sound["channels"] != 2:
            raise ValueError("Require 48 kHz stereo gameplay audio")
        if abs(float(sound.get("start_time", 0))) > 1 / 48000:
            raise ValueError("Gameplay audio must begin at timestamp zero")
        if abs(float(sound["duration"]) - seconds) > .025:
            raise ValueError("Audio and video durations differ")
    return video


def default_layout():
    labels = ["instagram @basketbroom", "x @basketbroom", "curseforge.com/members/basketbroom",
              "basketbroom.fun", "github.com/svmsepi0l"]
    destinations = {row["brand"]: row["url"] for row in json.loads((BRANDS / "sources.json").read_text(encoding="utf-8"))["destinations"]}
    return {
        "schema": 1, "canvas": [WIDTH, HEIGHT], "art_fit": "cover_center",
        "title": {"text": "basketbroom", "x": 200, "y": 390, "size": 320, "max_width": 1900},
        "description": {"lines": ["an aerial team sport of broom flight,", "ball play and spellwork."],
                        "x": 210, "y": 680, "size": 109, "line_spacing": 96, "max_width": 1900},
        "header_panel": {"x": 160, "y": 350, "width": 2050, "height": 540, "opacity": 0.0},
        "links_panel": {"x": 180, "y": 1040, "width": 1880, "height": 760, "opacity": .66},
        "badge_panel": {"x": 2290, "y": 1400, "width": 1330, "height": 400, "opacity": .60},
        "links": [{"brand": brand, "text": label, "url": destinations[brand], "x": 240,
                   "y": 1100 + index * 130, "icon_size": 112 if brand == "curseforge" else 72,
                   "icon_area": 72, "text_x": 352, "size": 84}
                  for index, (brand, label) in enumerate(zip(ICON_NAMES, labels))],
        "badge": {"x": 2350, "y": 1460, "size": 78, "line_spacing": 76,
                  "lines": ["hogwarts legacy creator kit", "mod in development"],
                  "prototype": "prototype built in unreal engine 5.8", "prototype_y": 1655, "prototype_size": 60},
        "fade_in_seconds": .55, "fade_out_seconds": .45,
        "note": "Coordinates are editable 3840x2160 presentation pixels; the explicit requested left positions take precedence over approximate safe-margin guidance.",
    }


def normalize_display_text(layout):
    """Lowercase visible copy only; destinations, font names and paths keep case."""
    layout = copy.deepcopy(layout)
    layout["title"]["text"] = layout["title"]["text"].lower()
    layout["description"]["lines"] = [line.lower() for line in layout["description"]["lines"]]
    for row in layout["links"]:
        row["text"] = row["text"].lower()
    layout["badge"]["lines"] = [line.lower() for line in layout["badge"]["lines"]]
    layout["badge"]["prototype"] = layout["badge"]["prototype"].lower()
    return layout


def ass_text(text):
    if any(c in text for c in "{}\\\r\n"):
        raise ValueError("Use separate layout lines; ASS override syntax is not allowed in text")
    return text


def ass_time(seconds):
    ticks = round(seconds * 100)
    return f"{ticks // 360000}:{ticks // 6000 % 60:02}:{ticks // 100 % 60:02}.{ticks % 100:02}"


def validate_layout(layout):
    if layout.get("canvas") != [WIDTH, HEIGHT] or layout.get("art_fit") not in ("cover_center", "contain"):
        raise ValueError("Layout needs a 3840x2160 canvas and cover_center or contain art fit")
    if not FONT.is_file() or sha(FONT) != FONT_SHA256:
        raise ValueError("The approved static Google Sans Flex Black font is missing or changed")
    data = FONT.read_bytes()
    tables = {data[index:index + 4]: int.from_bytes(data[index + 8:index + 12], "big")
              for index in range(12, 12 + 16 * int.from_bytes(data[4:6], "big"), 16)}
    weight_offset = tables[b"OS/2"] + 4
    if b"fvar" in tables or int.from_bytes(data[weight_offset:weight_offset + 2], "big") != 900:
        raise ValueError("Bookends require the actual static weight900 face, not synthesized bold")
    for key in ("header_panel", "links_panel", "badge_panel"):
        box = layout[key]
        if not 0 <= box["opacity"] <= 1 or min(box["x"], box["y"], box["width"], box["height"]) < 0:
            raise ValueError("Invalid text panel")
        if box["x"] + box["width"] > WIDTH or box["y"] + box["height"] > HEIGHT:
            raise ValueError("Text panel exceeds canvas")
    if [row["brand"] for row in layout["links"]] != list(ICON_NAMES):
        raise ValueError("Keep the five distinct brand/destination rows")
    for value in (layout["fade_in_seconds"], layout["fade_out_seconds"]):
        if not math.isfinite(value) or not 0 < value <= 1:
            raise ValueError("Bookend fades must be gentle, positive and at most one second")


def make_ass(path, layout, duration, outro, width_scale):
    title = layout["title"]
    size = int(title["size"])
    while ImageFont.truetype(str(FONT), size).getlength(title["text"]) * width_scale > title["max_width"] and size > 40:
        size -= 1
    font = ImageFont.truetype(str(FONT), size)
    if font.getlength(title["text"]) * width_scale > title["max_width"]:
        raise ValueError("Title does not fit")
    metrics = [{"text": title["text"], "font": FONT_FAMILY, "weight": 900, "requested_size": title["size"],
                "render_size": size, "calibrated_visible_width": round(font.getlength(title["text"]) * width_scale, 2)}]
    lines = []
    def text(value, x, y, fontsize, style="Body", max_width=None):
        width = ImageFont.truetype(str(FONT), int(fontsize)).getlength(value) * width_scale
        if x < 0 or y < 0 or x + width > WIDTH - 140 or y + fontsize * 1.5 > HEIGHT - 140:
            raise ValueError("Text exceeds safe canvas: " + value)
        if max_width is not None and width > max_width:
            raise ValueError("Text exceeds its panel: " + value)
        lines.append(f"Dialogue: 0,0:00:00.00,{ass_time(duration)},{style},,0,0,0,,{{\\an7\\pos({x},{y})\\fs{fontsize}}}" + ass_text(value))
    text(title["text"], title["x"], title["y"], size, "Title", title["max_width"])
    description = layout["description"]
    for index, value in enumerate(description["lines"]):
        text(value, description["x"], description["y"] + index * description["line_spacing"], description["size"], max_width=description["max_width"])
    if outro:
        for row in layout["links"]:
            text(row["text"], row["text_x"], row["y"], row["size"], max_width=layout["links_panel"]["x"] + layout["links_panel"]["width"] - row["text_x"] - 45)
        badge = layout["badge"]
        for index, value in enumerate(badge["lines"]):
            text(value, badge["x"], badge["y"] + index * badge["line_spacing"], badge["size"], "Badge", 1240)
        text(badge["prototype"], badge["x"], badge["prototype_y"], badge["prototype_size"], max_width=1240)
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 3840
PlayResY: 2160
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Google Sans Flex 72pt Black,200,&H00E9F0F5,&H00FFFFFF,&HA010151B,&H00000000,0,0,0,0,100,100,0,0,1,1,0,7,0,0,0,1
Style: Body,Google Sans Flex 72pt Black,78,&H00DFE5EA,&H00FFFFFF,&HA010151B,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Badge,Google Sans Flex 72pt Black,56,&H00E9F0F5,&H00FFFFFF,&HA010151B,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8-sig")
    return metrics


def measure_ass_font(ffmpeg, output, name, font_directory, layout):
    """Measure real libass ink bounds; its font-size metric differs from Pillow."""
    title = layout["title"]
    path = output / f"{name}-font-measure.ass"
    text = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 3840
PlayResY: 2160
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, Bold, Italic, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Measure,{FONT_FAMILY},{title['size']},&H00FFFFFF,0,0,100,100,0,0,1,0,0,7,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Measure,,0,0,0,,{{\\an7\\pos({title['x']},{title['y']})}}{ass_text(title['text'])}
"""
    path.write_text(text, encoding="utf-8-sig")
    png = output / f"{name}-font-measure.png"
    log = output / f"{name}-font-measure.log"
    run([ffmpeg, "-hide_banner", "-nostdin", "-n", "-f", "lavfi", "-i", "color=black:s=3840x2160:r=1:d=1",
         "-vf", f"ass=filename={path.name}:fontsdir={font_directory.name},format=rgb24", "-frames:v", "1", "-c:v", "png", "-threads", "1", str(png)], cwd=output, log=log)
    with Image.open(png) as image:
        bounds = image.convert("L").getbbox()
    if not bounds or bounds[2] >= WIDTH - 1 or bounds[3] >= HEIGHT - 1:
        raise ValueError("Title measurement is empty or clipped")
    selected = [line for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if "fontselect:" in line]
    if not selected or any("-> GoogleSansFlex72pt-Black," not in line for line in selected):
        raise RuntimeError("libass selected an unintended font fallback")
    measured = bounds[2] - bounds[0]
    pillow_width = ImageFont.truetype(str(FONT), int(title["size"])).getlength(title["text"])
    return {"measurement": "Actual libass raster ink bounds on a black calibration frame", "title_ink_bbox": list(bounds),
            "title_visible_width": measured, "pillow_to_libass_width_scale": measured / pillow_width,
            "font_selection_verified": True, "postscript_name": "GoogleSansFlex72pt-Black"}


def posters(ffmpeg, art, output, name, layout):
    with Image.open(art) as image:
        dimensions = list(image.size)
    assets = json.loads((BRANDS / "sources.json").read_text(encoding="utf-8"))
    approved = {Path(row["file"]).name: row["sha256"] for row in assets["assets"]}
    font_directory = output / f"{name}-fonts"
    font_directory.mkdir()
    shutil.copy2(FONT, font_directory / FONT.name)
    for path in FONTS.iterdir():
        if path.is_file() and path.suffix.lower() in (".txt", ".json", ".md"):
            shutil.copy2(path, font_directory / path.name)
    font_measurement = measure_ass_font(ffmpeg, output, name, font_directory, layout)
    icons = []
    for key, filename in ICON_NAMES.items():
        path = BRANDS / filename
        if sha(path) != approved[filename]:
            raise ValueError("Official/source icon differs from its recorded provenance: " + filename)
        with Image.open(path) as image:
            if image.format != "PNG" or "A" not in image.getbands():
                raise ValueError("Expected the supplied transparent PNG icon")
            icons.append({"brand": key, "path": str(path), "sha256": sha(path), "dimensions": list(image.size)})
    title_metrics = None
    for part, duration in (("intro", INTRO), ("outro", OUTRO)):
        ass = output / f"{name}-{part}.ass"
        title_metrics = make_ass(ass, layout, duration, part == "outro", font_measurement["pillow_to_libass_width_scale"])
        command = [ffmpeg, "-hide_banner", "-nostdin", "-n", "-i", str(art)]
        if part == "outro":
            for icon in icons:
                command += ["-i", icon["path"]]
        fitting = (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,crop={WIDTH}:{HEIGHT}"
                   if layout["art_fit"] == "cover_center" else
                   f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease:flags=lanczos,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0x090F16")
        filters = [f"[0:v]{fitting},setsar=1,format=rgba[art]"]
        previous = "art"
        for key in ("header_panel",) + (("links_panel", "badge_panel") if part == "outro" else ()):
            box = layout[key]
            current = key
            filters.append(f"[{previous}]drawbox=x={box['x']}:y={box['y']}:w={box['width']}:h={box['height']}:color=0x080F19@{box['opacity']}:t=fill[{current}]")
            previous = current
        if part == "outro":
            for index, row in enumerate(layout["links"]):
                size = row["icon_size"]
                filters.append(f"[{index+1}:v]scale={size}:{size}:force_original_aspect_ratio=decrease:flags=lanczos,format=rgba[icon{index}]")
                area = row.get("icon_area", 72)
                filters.append(f"[{previous}][icon{index}]overlay=x={row['x']}+({area}-overlay_w)/2:y={row['y']}+({area}-overlay_h)/2:shortest=1[linked{index}]")
                previous = f"linked{index}"
        filters.append(f"[{previous}]ass=filename={ass.name}:fontsdir={font_directory.name},format=rgb24[poster]")
        graph = output / f"{name}-{part}-composite.txt"
        graph.write_text(";\n".join(filters) + "\n", encoding="utf-8")
        command += ["-filter_complex", ";".join(filters), "-map", "[poster]", "-frames:v", "1", "-c:v", "png", "-threads", "1", str(output / f"{name}-{part}.png")]
        run(command, cwd=output, log=output / f"{name}-{part}-poster.log")
    sx, sy = WIDTH / dimensions[0], HEIGHT / dimensions[1]
    scale = max(sx, sy) if layout["art_fit"] == "cover_center" else min(sx, sy)
    return {"art": str(art), "art_sha256": sha(art), "native_art_dimensions": dimensions,
            "art_fit": layout["art_fit"], "art_scale_factor": scale, "art_resized": dimensions != [WIDTH, HEIGHT],
            "art_upscaled": scale > 1, "art_center_crop_pixels_before_scaling":
            [max(0, dimensions[0] - WIDTH / scale), max(0, dimensions[1] - HEIGHT / scale)],
            "art_resize_disclosure": "The raster illustration may be resized/cropped for bookends only. Gameplay remains native resolution.",
            "same_art_used_for_both_ends": True, "icons": icons, "brand_sources_sha256": sha(BRANDS / "sources.json"),
            "icons_redrawn_or_recoloured": False, "title_metrics": title_metrics,
            "font_render_measurement": font_measurement,
            "font": {"file": str(FONT), "family": FONT_FAMILY, "weight": 900, "sha256": sha(FONT),
                     "static_font": True, "applies_to": "all intro/outro title, description, link and badge text",
                     "editable_font_copy": str(font_directory / FONT.name)}}


def packet_fingerprints(ffprobe, path):
    data = json.loads(run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_packets", "-show_data_hash", "sha256",
                           "-show_entries", "packet=data_hash,flags,pts_time,duration_time,pos,size", "-of", "json", str(path)]))
    return data["packets"]


def avcc_content_without_parameter_sets(path, packet):
    with Path(path).open("rb") as stream:
        stream.seek(int(packet["pos"]))
        data = stream.read(int(packet["size"]))
    units, position = [], 0
    while position < len(data):
        if position + 4 > len(data):
            raise RuntimeError("Incomplete H.264 packet length")
        length = int.from_bytes(data[position:position + 4], "big")
        position += 4
        if length <= 0 or position + length > len(data):
            raise RuntimeError("Expected standard four-byte AVCC NAL lengths")
        unit = data[position:position + length]
        position += length
        if unit[0] & 31 not in (7, 8):
            units.append(unit)
    return units


def verify_copied_packets(ffprobe, source, final, intro_frames, gameplay_frames):
    original = packet_fingerprints(ffprobe, source)
    result = packet_fingerprints(ffprobe, final)[intro_frames:intro_frames + gameplay_frames]
    if len(original) != gameplay_frames or len(result) != gameplay_frames:
        raise RuntimeError("Gameplay packet/frame count changed during concatenation")
    # The concat demuxer's H.264 conversion can insert in-band SPS/PPS on key
    # packets. Non-key packet payloads must remain byte-identical; for modified
    # key packets compare every NAL except SPS/PPS, including the picture data.
    key_header_differences = []
    for index, (before, after) in enumerate(zip(original, result)):
        if abs(float(after["pts_time"]) - float(before["pts_time"]) - intro_frames / FPS) > 2e-5:
            raise RuntimeError("Gameplay timestamps were altered or reordered")
        if before["data_hash"] != after["data_hash"]:
            if "K" not in before.get("flags", "") or "K" not in after.get("flags", ""):
                raise RuntimeError("A non-key gameplay packet payload changed")
            if avcc_content_without_parameter_sets(source, before) != avcc_content_without_parameter_sets(final, after):
                raise RuntimeError("A key gameplay picture payload changed beyond SPS/PPS insertion")
            key_header_differences.append(index)
    return {"original_gameplay_packets": len(original), "copied_gameplay_packets": len(result),
            "timestamp_shift_seconds": intro_frames / FPS, "non_key_payloads_identical": True,
            "all_gameplay_picture_payloads_identical": True,
            "key_packets_with_sps_pps_differences_only": key_header_differences,
            "proof_scope": "Video was stream-copied, without a decoder/filter/encoder. Every gameplay timestamp and encoded picture payload checked; automatic H.264 SPS/PPS insertion is the only permitted packet difference."}


def finish(args, *, test_spec=None):
    width, height, intro, gameplay, outro = test_spec or (WIDTH, HEIGHT, INTRO, GAMEPLAY, OUTRO)
    output = args.output_dir.resolve()
    name = args.name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}", name):
        raise ValueError("Use a plain filename stem containing letters, digits, underscores or hyphens")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.glob(name + "-*")) or (output / (name + ".mp4")).exists():
        raise FileExistsError("This output name already exists; choose a fresh name. Nothing will be overwritten.")
    art = args.art.resolve()
    if not art.is_file():
        raise ValueError("Provide the final artwork file")
    source_probe = None
    if not args.prepare_only:
        if not args.gameplay or not args.gameplay.is_file():
            raise ValueError("Provide the completed, validated native 60 fps gameplay MP4")
        source_probe = probe(args.ffprobe, args.gameplay)
        video = media_contract(source_probe, width, height, gameplay)
    layout = json.loads(args.layout.read_text(encoding="utf-8-sig")) if args.layout else default_layout()
    layout = normalize_display_text(layout)
    validate_layout(layout)
    layout_path = output / f"{name}-layout.json"
    layout_path.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
    receipt = {"status": "prepared", "synthetic_preflight": test_spec is not None,
               "created_utc": datetime.now(timezone.utc).isoformat(), "layout": str(layout_path),
               "duration_seconds": intro + gameplay + outro, "fps": FPS, "resolution": [width, height],
               "sections": {"intro": intro, "gameplay": gameplay, "outro": outro},
               "editorial_display_text_case": "lowercase; destination URLs and font identifiers retain their original case",
               "publishing": "Local output only; nothing uploaded"}
    receipt.update(posters(args.ffmpeg, art, output, name, layout))
    receipt_path = output / f"{name}-production.json"
    if args.prepare_only:
        receipt["export_validation"] = "not_run; poster/layout preparation only"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return receipt
    timescale = Fraction(video["time_base"]).denominator
    level = str(video["level"] / 10)
    segments = []
    commands = []
    for part, duration in (("intro", intro), ("outro", outro)):
        path = output / f"{name}-{part}.mp4"
        fade_in = min(layout["fade_in_seconds"], duration / 3)
        fade_out = min(layout["fade_out_seconds"], duration / 3)
        encoder = (["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "17", "-b:v", "0"]
                   if args.encoder == "h264_nvenc" else ["-c:v", "libx264", "-preset", "fast", "-crf", "16"])
        command = [args.ffmpeg, "-hide_banner", "-nostdin", "-n", "-loop", "1", "-framerate", str(FPS), "-i", str(output / f"{name}-{part}.png"),
                   "-an", "-frames:v", str(round(duration * FPS)), "-vf",
                   f"scale={width}:{height}:flags=lanczos:in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p,fade=t=in:st=0:d={fade_in},fade=t=out:st={duration-fade_out}:d={fade_out}"]
        command += encoder + ["-profile:v", "high", "-level:v", level, "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-video_track_timescale", str(timescale), "-movflags", "+faststart", str(path)]
        commands.append(command)
        run(command, log=output / f"{name}-{part}-encode.log")
        bookend_video = media_contract(probe(args.ffprobe, path), width, height, duration, audio=False)
        if bookend_video["time_base"] != video["time_base"]:
            raise RuntimeError("Bookend and gameplay video timebases differ")
        segments.append(path)
    # A video-only remux prevents source audio packet duration/padding from
    # affecting concat's section boundaries. No video decoder is invoked.
    middle = output / f"{name}-gameplay-copy.mp4"
    command = [args.ffmpeg, "-hide_banner", "-nostdin", "-n", "-i", str(args.gameplay.resolve()), "-map", "0:v:0", "-c:v", "copy", "-an", "-video_track_timescale", str(timescale), str(middle)]
    commands.append(command)
    run(command, log=output / f"{name}-gameplay-copy.log")
    concat = output / f"{name}-concat.txt"
    concat.write_text("\n".join("file '" + path.name + "'" for path in (segments[0], middle, segments[1])) + "\n", encoding="utf-8")
    final = output / f"{name}.mp4"
    total = intro + gameplay + outro
    audio_graph = f"[1:a:0]atrim=start=0:end={gameplay},asetpts=PTS-STARTPTS,adelay={round(intro*48000)}S:all=1,apad=whole_dur={total},atrim=duration={total}[audio]"
    command = [args.ffmpeg, "-hide_banner", "-nostdin", "-n", "-f", "concat", "-safe", "1", "-i", str(concat), "-i", str(args.gameplay.resolve()),
               "-filter_complex", audio_graph, "-map", "0:v:0", "-map", "[audio]", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2",
               "-video_track_timescale", str(timescale), "-movflags", "+faststart", "-metadata", "title=Basketbroom gameplay showcase", str(final)]
    commands.append(command)
    run(command, cwd=output, log=output / f"{name}-finish.log")
    result_probe = probe(args.ffprobe, final)
    final_video = media_contract(result_probe, width, height, total)
    if final_video["time_base"] != video["time_base"]:
        raise RuntimeError("Final video timebase differs from the gameplay source")
    packets = verify_copied_packets(args.ffprobe, args.gameplay.resolve(), final, round(intro * FPS), round(gameplay * FPS))
    receipt.update(status="complete", output=str(final), output_sha256=sha(final), gameplay=str(args.gameplay.resolve()),
                   gameplay_sha256=sha(args.gameplay), gameplay_probe=source_probe, final_probe=result_probe,
                   verification=packets, commands=commands, video_processing="Bookends encoded; gameplay video stream-copy only. No optical interpolation, frame doubling or gameplay scaling.",
                   audio={"format": "AAC 48 kHz stereo, 320 kbps", "leading_silence_seconds": intro, "trailing_silence_seconds": outro,
                          "gameplay_shift_samples": round(intro * 48000), "gain_or_effect_changes": False,
                          "encoding_disclosure": "Gameplay audio decoded and encoded once to AAC for sample-aligned silence padding. It is not a bit-identical copy of a lossy source track."},
                   subjective_art_and_playback_review="not_performed_by_this_script")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def preflight(args):
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Preflight requires an empty output directory")
    art = output / "synthetic-test-plate.png"
    Image.new("RGB", (WIDTH, HEIGHT), (23, 31, 42)).save(art)
    gameplay = output / "synthetic-gameplay.mp4"
    run([args.ffmpeg, "-hide_banner", "-nostdin", "-n", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=60:duration=2",
         "-f", "lavfi", "-i", "aevalsrc=0.08*sin(2*PI*440*t)|0.08*sin(2*PI*440*t):s=48000:d=2",
         "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(gameplay)])
    args.gameplay, args.art, args.encoder = gameplay, art, "libx264"
    result = finish(args, test_spec=(640, 360, .25, 2, .5))
    def audio_pcm(path):
        decoded = subprocess.run([args.ffmpeg, "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "f32le", "-c:a", "pcm_f32le", "-"], capture_output=True)
        if decoded.returncode:
            raise RuntimeError(decoded.stderr.decode(errors="replace"))
        values = array("f")
        values.frombytes(decoded.stdout)
        return values
    original_audio = audio_pcm(gameplay)[:2 * 48000 * 2]
    final_audio = audio_pcm(result["output"])
    shifted = final_audio[round(.25 * 48000) * 2:round(2.25 * 48000) * 2]
    if len(shifted) != len(original_audio):
        raise RuntimeError("Synthetic shifted audio length mismatch")
    energy_a = sum(value * value for value in original_audio)
    energy_b = sum(value * value for value in shifted)
    correlation = sum(a * b for a, b in zip(original_audio, shifted)) / math.sqrt(energy_a * energy_b)
    rms_error = math.sqrt(sum((a - b) ** 2 for a, b in zip(original_audio, shifted)) / len(shifted))
    # AAC can have a short transform tail at silence boundaries; inspect silence
    # 30 ms away from those edges and disclose the unavoidable lossy re-encode.
    quiet = final_audio[:round(.22 * 48000) * 2] + final_audio[round(2.28 * 48000) * 2:round(2.75 * 48000) * 2]
    if correlation < .995 or rms_error > .003 or max(map(abs, quiet)) > 1e-4:
        raise RuntimeError("Synthetic audio shift/silence preservation failed")
    result["preflight_audio"] = {"sample_shift": 12000, "correlation_after_aac_encode": correlation,
                                  "rms_error_after_aac_encode": rms_error, "silence_peak_away_from_aac_edges": max(map(abs, quiet))}
    rejected = False
    try:
        media_contract(probe(args.ffprobe, gameplay), WIDTH, HEIGHT, GAMEPLAY)
    except ValueError:
        rejected = True
    if not rejected:
        raise RuntimeError("Production unexpectedly accepted synthetic non-4K/short gameplay")
    result["preflight_rejects_nonproduction_gameplay"] = True
    result["preflight_note"] = "Synthetic 2.75-second fixture only; not a final promotional export or generated-art review."
    path = output / f"{args.name}-production.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gameplay", type=Path)
    parser.add_argument("--art", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--name", default="basketbroom-gameplay-promo")
    parser.add_argument("--layout", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--encoder", choices=("h264_nvenc", "libx264"), default="h264_nvenc")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe"))
    args = parser.parse_args()
    if not args.ffmpeg or not args.ffprobe:
        parser.error("FFmpeg and ffprobe must be installed or supplied explicitly")
    if args.preflight and (args.prepare_only or args.gameplay or args.art):
        parser.error("Preflight supplies its own short synthetic inputs")
    if not args.preflight and not args.art:
        parser.error("--art is required")
    result = preflight(args) if args.preflight else finish(args)
    print(json.dumps({key: result[key] for key in ("status", "synthetic_preflight", "duration_seconds", "fps", "resolution")}, indent=2))


if __name__ == "__main__":
    main()

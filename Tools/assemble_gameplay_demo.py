"""Encode native UE gameplay frames into clean and lightly captioned 4K masters.

Example (ordinary bundled Python, not Unreal Python):
  python Tools/assemble_gameplay_demo.py --capture .local/gameplay-demo/take-01/capture.json \
    --manifest .local/gameplay-demo-director.json \
    --audio .local/gameplay-demo/basketbroom-prototype-demo-audio.wav

The utility verifies contiguous native-size source frames and encoded stream
dimensions/frame count/duration. It never scales up a smaller source. No source
frames are deleted. Outputs are local review artifacts, never uploaded.
"""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def jpeg_dimensions(path):
    with path.open("rb") as stream:
        if stream.read(2) != b"\xff\xd8":
            raise ValueError("Not a JPEG: " + str(path))
        while True:
            marker = stream.read(1)
            if not marker:
                raise ValueError("JPEG frame header incomplete: " + str(path))
            if marker != b"\xff":
                continue
            marker = stream.read(1)
            while marker == b"\xff":
                marker = stream.read(1)
            if marker in (b"\xd8", b"\xd9", b"\x00"):
                continue
            size = struct.unpack(">H", stream.read(2))[0]
            if marker[0] in (0xC0, 0xC1, 0xC2):
                _, height, width = struct.unpack(">BHH", stream.read(5))
                return width, height
            stream.seek(size - 2, 1)


def run(command, cwd=None, log=None):
    if log:
        with log.open("w", encoding="utf-8") as output:
            result = subprocess.run(command, cwd=cwd, stdout=output, stderr=subprocess.STDOUT, text=True)
        if result.returncode:
            raise RuntimeError("Encoding failed; inspect " + str(log))
        return None
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def ass_time(seconds):
    value = max(0, int(round(float(seconds) * 100)))
    return "%d:%02d:%02d.%02d" % (value // 360000, value // 6000 % 60, value // 100 % 60, value % 100)


def ass_text(value):
    return str(value).replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", r"\N")


def make_captions(manifest, path, duration):
    shots = manifest.get("shots", manifest.get("timeline", []))
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 3840
PlayResY: 2160
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Chapter,Segoe UI,58,&H00FFFFFF,&H00FFFFFF,&H70201914,&H9019120D,-1,0,0,0,100,100,0,0,3,16,0,7,120,120,360,1
Style: Note,Segoe UI,34,&H00D7E1E4,&H00FFFFFF,&H70201914,&H9019120D,0,0,0,0,100,100,0,0,3,12,0,7,120,120,438,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    captions = []
    for shot in shots:
        start = float(shot.get("start", shot.get("start_seconds", 0)))
        end = min(float(shot.get("end", shot.get("end_seconds", duration))), start + 5.0, duration)
        if end <= start:
            continue
        title = shot.get("title", shot.get("name", ""))
        subtitle = shot.get("subtitle", shot.get("caption", ""))
        if not title:
            continue
        for style, value in (("Chapter", title), ("Note", subtitle)):
            if value:
                lines.append("Dialogue: 0,%s,%s,%s,,0,0,0,,{\\fad(200,250)}%s" %
                             (ass_time(start), ass_time(end), style, ass_text(value)))
        captions.append({"start": start, "end": end, "title": title, "subtitle": subtitle})
    if not captions:
        raise ValueError("Director manifest contains no shot captions")
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8-sig")
    return captions


def inspect_media(ffprobe, path, width, height, fps, frame_count, audio_required):
    data = json.loads(run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    videos = [stream for stream in data["streams"] if stream["codec_type"] == "video"]
    if len(videos) != 1:
        raise ValueError("Expected exactly one encoded video stream")
    video = videos[0]
    if (video["width"], video["height"]) != (width, height):
        raise ValueError("Encoded video resolution mismatch")
    if int(video.get("nb_frames", -1)) != frame_count:
        raise ValueError("Encoded frame count mismatch: " + str(video.get("nb_frames")))
    numerator, denominator = map(int, video["avg_frame_rate"].split("/"))
    if abs(numerator / denominator - fps) > 0.001:
        raise ValueError("Encoded frame rate mismatch")
    if abs(float(video["duration"]) - frame_count / fps) > 0.04:
        raise ValueError("Encoded duration mismatch")
    if audio_required and not any(stream["codec_type"] == "audio" for stream in data["streams"]):
        raise ValueError("Expected an audio stream")
    return data


def validate_manifest(manifest, capture, duration, fps):
    """Prevent a completed take from receiving another rehearsal's edit cues."""
    if manifest.get("status") != "complete" or manifest.get("rehearsal", True):
        raise ValueError("Director manifest must describe a completed non-rehearsal take")
    origin = manifest.get("capture_origin_game_seconds")
    capture_origin = capture.get("start_game_seconds")
    if (not isinstance(origin, (int, float)) or not isinstance(capture_origin, (int, float))
            or not math.isfinite(origin) or not math.isfinite(capture_origin)
            or abs(origin - capture_origin) > 1 / fps + 1e-6):
        raise ValueError("Director and capture time origins do not match within one fixed frame")
    if float(manifest.get("duration_seconds", 0)) < duration - 1 / fps - 1e-6:
        raise ValueError("Director manifest does not cover the requested export duration")
    source = manifest.get("capture", {})
    for name in ("output", "frames"):
        if name in source and str(Path(source[name]).resolve()).casefold() != str(Path(capture[name]).resolve()).casefold():
            raise ValueError("Director belongs to a different capture " + name + " path")
    if "fps" in source and int(source["fps"]) != fps:
        raise ValueError("Director and capture frame rates differ")
    if "resolution" in source and source["resolution"] != capture["resolution"]:
        raise ValueError("Director and capture native resolutions differ")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".local/gameplay-demo")
    parser.add_argument("--name", default="basketbroom-prototype-4k")
    parser.add_argument("--duration", type=float, default=180)
    parser.add_argument("--encoder", choices=("h264_nvenc", "libx264"), default="h264_nvenc")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    parser.add_argument("--clean-only", action="store_true")
    args = parser.parse_args()
    if not args.ffmpeg:
        raise RuntimeError("ffmpeg must be installed or passed explicitly")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.name):
        raise ValueError("Output name may contain only letters, numbers, underscores and hyphens")
    if not 0 < args.duration <= 600:
        raise ValueError("Duration must be positive and no greater than 600 seconds")
    ffprobe = str(Path(args.ffmpeg).with_name("ffprobe.exe" if Path(args.ffmpeg).suffix.lower() == ".exe" else "ffprobe"))
    capture = json.loads(args.capture.read_text(encoding="utf-8-sig"))
    directory = Path(capture["frames"])
    frames = sorted(directory.glob("frame_*.jpg"))
    width, height = map(int, capture["resolution"])
    fps = int(capture["fps"])
    count = round(args.duration * fps)
    protocol = capture.get("protocol", {})
    if capture.get("status") != "captured" or protocol.get("failure_reason"):
        raise ValueError("Source capture did not finish successfully")
    if protocol.get("actual_resource_size") != [width, height]:
        raise ValueError("Source capture must verify its actual native render resource dimensions")
    if not frames:
        raise ValueError("Source capture contains no frames")
    if any(int(protocol.get(name, -1)) != len(frames) for name in ("frames_captured", "frames_written")):
        raise ValueError("Native captured/written counts do not match the complete source frame sequence")
    if len(frames) < count:
        if count - len(frames) < fps:
            # The request is approximately three minutes. Preserve genuine
            # captured boundary frames instead of padding or repeating footage.
            count = len(frames)
        else:
            raise ValueError("Insufficient native frames: %d available, %d requested" % (len(frames), count))
    first = int(re.fullmatch(r"frame_(\d+)\.jpg", frames[0].name).group(1))
    if first != 0:
        raise ValueError("Source must begin with frame zero so video, captions and audio share one origin")
    for index, frame in enumerate(frames[:count]):
        if frame.name != "frame_%06d.jpg" % (first + index):
            raise ValueError("Source frame gap at " + frame.name)
        if jpeg_dimensions(frame) != (width, height):
            raise ValueError("Source frame native resolution mismatch: " + str(frame))
    manifest = None
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        validate_manifest(manifest, capture, count / fps, fps)
    elif not args.clean_only:
        raise ValueError("Captioned review cut requires --manifest, or use --clean-only")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    clean = output / (args.name + "-clean.mp4")
    review = output / (args.name + "-review.mp4")
    if clean.exists() or (not args.clean_only and review.exists()):
        raise ValueError("Output already exists; choose a new --name or --output-dir")
    if args.audio and not args.audio.is_file():
        raise FileNotFoundError(args.audio)
    encoding = (["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "17", "-b:v", "0"]
                if args.encoder == "h264_nvenc" else ["-c:v", "libx264", "-preset", "fast", "-crf", "16"])
    common = encoding + ["-pix_fmt", "yuv420p", "-profile:v", "high", "-color_range", "tv",
                         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart"]
    command = [args.ffmpeg, "-hide_banner", "-nostdin", "-n", "-framerate", str(fps), "-start_number", str(first),
               "-i", str(directory / "frame_%06d.jpg")]
    if args.audio:
        command += ["-i", str(args.audio.resolve())]
    command += ["-map", "0:v:0", "-frames:v", str(count), "-t", str(count / fps), "-vf",
                "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p"]
    if args.audio:
        command += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"]
    command += common + ["-metadata", "title=Basketbroom prototype - native 4K gameplay", str(clean)]
    run(command, log=output / (args.name + "-clean-encode.log"))
    clean_probe = inspect_media(ffprobe, clean, width, height, fps, count, bool(args.audio))
    receipt = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_capture": str(args.capture.resolve()),
               "source_frames": str(directory), "source_frames_available": len(frames), "source_frames_used": count,
               "all_used_frame_dimensions_verified": True, "upscaled": False, "source_first_frame": first,
               "width": width, "height": height, "fps": fps, "duration_seconds": count / fps,
               "requested_duration_seconds": args.duration, "boundary_frames_padded": False,
               "clean": str(clean), "clean_probe": clean_probe,
               "director_manifest": str(args.manifest.resolve()) if args.manifest else None,
               "director_origin_game_seconds": manifest["capture_origin_game_seconds"] if manifest else None,
               "audio": str(args.audio.resolve()) if args.audio else None,
               "audio_note": "Edited sound mix from the game's original cues, aligned to recorded gameplay event timestamps; not a live system/microphone recording" if args.audio else "Silent source master"}
    if not args.clean_only:
        subtitles = output / (args.name + "-captions.ass")
        receipt["captions"] = make_captions(manifest, subtitles, count / fps)
        review_command = [args.ffmpeg, "-hide_banner", "-nostdin", "-n", "-i", str(clean), "-map", "0:v:0",
                          "-map", "0:a?", "-frames:v", str(count), "-vf", "ass=filename='" + subtitles.name + "'",
                          "-c:a", "copy"] + common + ["-metadata", "title=Basketbroom prototype - review cut", str(review)]
        run(review_command, cwd=output, log=output / (args.name + "-review-encode.log"))
        receipt["review"] = str(review)
        receipt["review_probe"] = inspect_media(ffprobe, review, width, height, fps, count, bool(args.audio))
    receipt_path = output / (args.name + "-export.json")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in ("clean", "width", "height", "fps", "duration_seconds")}, indent=2))
    print("Export receipt: " + str(receipt_path))


if __name__ == "__main__":
    main()

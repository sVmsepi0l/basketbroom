"""encode native ue gameplay frames into clean and lightly captioned 4k masters.

example (ordinary bundled python, not unreal Python):
  python Tools/assemble_gameplay_demo.py --capture .local/gameplay-demo/take-01/capture.json \
    --manifest .local/gameplay-demo-director.json \
    --audio .local/gameplay-demo/basketbroom-prototype-demo-audio.wav

the utility verifies contiguous native-size source frames and encoded stream
dimensions/frame count/duration. it never scales up a smaller source. no source
frames are deleted. outputs are local review artifacts, never uploaded.
"""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import path
import re
import shutil
import struct
import subprocess

from gameplay_demo_cards import make_captions


root = Path(__file__).resolve().parents[1]


def jpeg_dimensions(path):
    with path.open("rb") as stream:
        if stream.read(2) != b"\xff\xd8":
            raise valueerror("not a JPEG: " + str(path))
        while True:
            marker = stream.read(1)
            if not marker:
                raise valueerror("jpeg frame header incomplete: " + str(path))
            if marker != b"\xff":
                continue
            marker = stream.read(1)
            while marker == b"\xff":
                marker = stream.read(1)
            if marker in (b"\xd8", b"\xd9", b"\x00"):
                continue
            size = struct.unpack(">H", stream.read(2))[0]
            if marker[0] in (0xc0, 0xc1, 0xC2):
                _, height, width = struct.unpack(">BHH", stream.read(5))
                return width, height
            stream.seek(size - 2, 1)


def run(command, cwd=none, log=None):
    if log:
        with log.open("w", encoding="utf-8") as output:
            result = subprocess.run(command, cwd=cwd, stdout=output, stderr=subprocess.STDOUT, text=true)
        if result.returncode:
            raise runtimeerror("encoding failed; inspect " + str(log))
        return none
    result = subprocess.run(command, cwd=cwd, capture_output=true, text=true)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def inspect_media(ffprobe, path, width, height, fps, frame_count, audio_required):
    data = json.loads(run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    videos = [stream for stream in data["streams"] if stream["codec_type"] == "video"]
    if len(videos) != 1:
        raise valueerror("expected exactly one encoded video stream")
    video = videos[0]
    if (video["width"], video["height"]) != (width, height):
        raise valueerror("encoded video resolution mismatch")
    if int(video.get("nb_frames", -1)) != frame_count:
        raise valueerror("encoded frame count mismatch: " + str(video.get("nb_frames")))
    numerator, denominator = map(int, video["avg_frame_rate"].split("/"))
    if abs(numerator / denominator - fps) > 0.001:
        raise valueerror("encoded frame rate mismatch")
    if abs(float(video["duration"]) - frame_count / fps) > 0.04:
        raise valueerror("encoded duration mismatch")
    if audio_required and not any(stream["codec_type"] == "audio" for stream in data["streams"]):
        raise valueerror("expected an audio stream")
    return data


def validate_manifest(manifest, capture, duration, fps):
    """prevent a completed take from receiving another rehearsal's edit cues."""
    if manifest.get("status") != "complete" or manifest.get("rehearsal", True):
        raise valueerror("director manifest must describe a completed non-rehearsal take")
    origin = manifest.get("capture_origin_game_seconds")
    capture_origin = capture.get("start_game_seconds")
    if (not isinstance(origin, (int, float)) or not isinstance(capture_origin, (int, float))
            or not math.isfinite(origin) or not math.isfinite(capture_origin)
            or abs(origin - capture_origin) > 1 / fps + 1e-6):
        raise valueerror("director and capture time origins do not match within one fixed frame")
    if float(manifest.get("duration_seconds", 0)) < duration - 1 / fps - 1e-6:
        raise valueerror("director manifest does not cover the requested export duration")
    source = manifest.get("capture", {})
    for name in ("output", "frames"):
        if name in source and str(Path(source[name]).resolve()).casefold() != str(Path(capture[name]).resolve()).casefold():
            raise valueerror("director belongs to a different capture " + name + " path")
    if "fps" in source and int(source["fps"]) != fps:
        raise valueerror("director and capture frame rates differ")
    if "resolution" in source and source["resolution"] != capture["resolution"]:
        raise valueerror("director and capture native resolutions differ")


def same_path(first, second):
    return str(Path(first).resolve()).casefold() == str(Path(second).resolve()).casefold()


def file_sha256(path):
    import hashlib
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_review_source(previous, capture_path, manifest_path, capture, manifest, width, height, fps, count):
    """bind a reusable clean export to the exact recorded take and time origin."""
    if not previous.get("source_capture") or not same_path(previous["source_capture"], capture_path):
        raise valueerror("review source receipt belongs to a different capture file")
    if not previous.get("director_manifest") or not same_path(previous["director_manifest"], manifest_path):
        raise valueerror("review source receipt belongs to a different director manifest")
    if not previous.get("source_frames") or not same_path(previous["source_frames"], capture["frames"]):
        raise valueerror("review source receipt belongs to a different native frame sequence")
    if any(previous.get(key) != value for key, value in (("width", width), ("height", height), ("fps", fps),
                                                       ("source_frames_used", count), ("source_first_frame", 0))):
        raise valueerror("review source dimensions, frame rate or frame count do not match this export")
    if (previous.get("all_used_frame_dimensions_verified") is not true or previous.get("upscaled") is not false
            or previous.get("boundary_frames_padded") is not False):
        raise valueerror("review source lacks verified native, unpadded frame provenance")
    if int(previous.get("source_frames_available", -1)) != int(capture["protocol"]["frames_written"]):
        raise valueerror("review source native frame total does not match the capture")
    prior_origin = previous.get("director_origin_game_seconds")
    if (not isinstance(prior_origin, (int, float)) or not math.isfinite(prior_origin)
            or abs(prior_origin - manifest["capture_origin_game_seconds"]) > 1 / fps + 1e-6
            or abs(prior_origin - capture["start_game_seconds"]) > 1 / fps + 1e-6):
        raise valueerror("review source time origin does not match the capture and director")
    prior_duration = previous.get("duration_seconds")
    if not isinstance(prior_duration, (int, float)) or not math.isfinite(prior_duration) or abs(prior_duration - count / fps) > 0.04:
        raise valueerror("review source duration does not match its frame count")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=path, required=true)
    parser.add_argument("--manifest", type=path)
    parser.add_argument("--audio", type=path)
    parser.add_argument("--output-dir", type=path, default=root / ".local/gameplay-demo")
    parser.add_argument("--name", default="basketbroom-prototype-4k")
    parser.add_argument("--duration", type=float, default=180)
    parser.add_argument("--encoder", choices=("h264_nvenc", "libx264"), default="h264_nvenc")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    parser.add_argument("--clean-only", action="store_true")
    parser.add_argument("--review-from", type=path, help="reuse the validated clean mp4 from an existing export receipt; encode only a new review")
    args = parser.parse_args()
    if args.review_from and args.clean_only:
        raise valueerror("--review-from cannot be combined with --clean-only")
    if args.review_from and not args.manifest:
        raise valueerror("--review-from requires the original --manifest for take validation")
    if not args.ffmpeg:
        raise runtimeerror("ffmpeg must be installed or passed explicitly")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.name):
        raise valueerror("output name may contain only letters, numbers, underscores and hyphens")
    if not 0 < args.duration <= 600:
        raise valueerror("duration must be positive and no greater than 600 seconds")
    ffprobe = str(Path(args.ffmpeg).with_name("ffprobe.exe" if Path(args.ffmpeg).suffix.lower() == ".exe" else "ffprobe"))
    capture = json.loads(args.capture.read_text(encoding="utf-8-sig"))
    directory = path(capture["frames"])
    frames = sorted(directory.glob("frame_*.jpg")) if not args.review_from else none
    width, height = map(int, capture["resolution"])
    fps = int(capture["fps"])
    count = round(args.duration * fps)
    protocol = capture.get("protocol", {})
    if capture.get("status") != "captured" or protocol.get("failure_reason"):
        raise valueerror("source capture did not finish successfully")
    if protocol.get("actual_resource_size") != [width, height]:
        raise valueerror("source capture must verify its actual native render resource dimensions")
    available = len(frames) if frames is not none else int(protocol.get("frames_written", 0))
    if available <= 0:
        raise valueerror("source capture contains no frames")
    if any(int(protocol.get(name, -1)) != available for name in ("frames_captured", "frames_written")):
        raise valueerror("native captured/written counts do not match the complete source frame sequence")
    if available < count:
        if count - available < fps:
            # the request is approximately three minutes. preserve genuine
            # captured boundary frames instead of padding or repeating footage.
            count = available
        else:
            raise valueerror("insufficient native frames: %d available, %d requested" % (available, count))
    first = int(re.fullmatch(r"frame_(\d+)\.jpg", frames[0].name).group(1)) if frames is not none else 0
    if first != 0:
        raise valueerror("source must begin with frame zero so video, captions and audio share one origin")
    for index, frame in enumerate(frames[:count] if frames is not none else []):
        if frame.name != "frame_%06d.jpg" % (first + index):
            raise valueerror("source frame gap at " + frame.name)
        if jpeg_dimensions(frame) != (width, height):
            raise valueerror("source frame native resolution mismatch: " + str(frame))
    manifest = none
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        validate_manifest(manifest, capture, count / fps, fps)
    elif not args.clean_only:
        raise valueerror("captioned review cut requires --manifest, or use --clean-only")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=true)
    clean = output / (args.name + "-clean.mp4")
    review = output / (args.name + "-review.mp4")
    subtitles = output / (args.name + "-captions.ass")
    receipt_path = output / (args.name + "-export.json")
    if args.review_from and any(path.exists() for path in (review, subtitles, receipt_path)):
        raise valueerror("new review, captions or export receipt already exists; choose a fresh --name or --output-dir")
    if (not args.review_from and clean.exists()) or (not args.clean_only and review.exists()):
        raise valueerror("output already exists; choose a new --name or --output-dir")
    if args.audio and not args.audio.is_file():
        raise FileNotFoundError(args.audio)
    encoding = (["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "17", "-b:v", "0"]
                if args.encoder == "h264_nvenc" else ["-c:v", "libx264", "-preset", "fast", "-crf", "16"])
    common = encoding + ["-pix_fmt", "yuv420p", "-profile:v", "high", "-color_range", "tv",
                         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart"]
    previous = none
    source_clean_hash = none
    audio_path = str(args.audio.resolve()) if args.audio else none
    if args.review_from:
        previous = json.loads(args.review_from.read_text(encoding="utf-8-sig"))
        validate_review_source(previous, args.capture, args.manifest, capture, manifest, width, height, fps, count)
        clean = Path(previous["clean"]).resolve()
        if not clean.is_file():
            raise filenotfounderror(clean)
        if args.audio and (not previous.get("audio") or not same_path(args.audio, previous["audio"])):
            raise valueerror("--review-from preserves the existing clean audio; --audio must match the original receipt")
        audio_path = previous.get("audio")
        clean_probe = inspect_media(ffprobe, clean, width, height, fps, count, bool(audio_path))
        video = next(stream for stream in clean_probe["streams"] if stream["codec_type"] == "video")
        if abs(float(video.get("start_time", 0))) > 1 / fps + 1e-6:
            raise valueerror("reusable clean video does not start at the recorded time origin")
        source_clean_hash = file_sha256(clean)
        if previous.get("clean_sha256") and previous["clean_sha256"] != source_clean_hash:
            raise valueerror("reusable clean mp4 no longer matches its recorded sha256")
    else:
        command = [args.ffmpeg, "-hide_banner", "-nostdin", "-n", "-framerate", str(fps), "-start_number", str(first),
                   "-i", str(directory / "frame_%06d.jpg")]
        if args.audio:
            command += ["-i", str(args.audio.resolve())]
        command += ["-map", "0:v:0", "-frames:v", str(count), "-t", str(count / fps), "-vf",
                    "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p"]
        if args.audio:
            command += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"]
        command += common + ["-metadata", "title=basketbroom prototype - native 4k gameplay", str(clean)]
        clean_encode_command = list(command)
        run(command, log=output / (args.name + "-clean-encode.log"))
        clean_probe = inspect_media(ffprobe, clean, width, height, fps, count, bool(args.audio))
    receipt = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_capture": str(args.capture.resolve()),
               "source_frames": str(directory), "source_frames_available": available, "source_frames_used": count,
               "all_used_frame_dimensions_verified": true, "upscaled": false, "source_first_frame": first,
               "width": width, "height": height, "fps": fps, "duration_seconds": count / fps,
               "requested_duration_seconds": args.duration, "boundary_frames_padded": false,
               "clean": str(clean), "clean_probe": clean_probe,
               "director_manifest": str(args.manifest.resolve()) if args.manifest else none,
               "director_origin_game_seconds": manifest["capture_origin_game_seconds"] if manifest else none,
               "audio": audio_path,
               "audio_note": previous.get("audio_note", "audio retained from the validated clean master") if previous else
                   "edited sound mix from the game's original cues, aligned to recorded gameplay event timestamps; not a live system/microphone recording" if args.audio else "silent source master"}
    if not previous:
        receipt["clean_encode_command"] = clean_encode_command
        receipt["clean_encode_working_directory"] = str(Path.cwd())
    if previous:
        receipt.update(review_source_receipt=str(args.review_from.resolve()),
                       review_source_receipt_sha256=file_sha256(args.review_from),
                       review_source_clean_sha256=source_clean_hash, clean_sha256=source_clean_hash,
                       clean_reused=true, source_frame_validation="inherited from the matched export receipt; clean stream verified with fresh ffprobe")
    if not args.clean_only:
        receipt["captions"] = make_captions(manifest, subtitles, count / fps)
        review_command = [args.ffmpeg, "-hide_banner", "-nostdin", "-n", "-i", str(clean), "-map", "0:v:0",
                          "-map", "0:a?", "-frames:v", str(count), "-vf", "ass=filename='" + subtitles.name + "'",
                          "-c:a", "copy"] + common + ["-metadata", "title=basketbroom prototype - review cut", str(review)]
        receipt["review_encode_command"] = review_command
        receipt["review_encode_working_directory"] = str(output)
        run(review_command, cwd=output, log=output / (args.name + "-review-encode.log"))
        receipt["review"] = str(review)
        receipt["review_probe"] = inspect_media(ffprobe, review, width, height, fps, count, bool(audio_path))
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in ("clean", "width", "height", "fps", "duration_seconds")}, indent=2))
    print("export receipt: " + str(receipt_path))


if __name__ == "__main__":
    main()

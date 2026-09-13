"""Edit original repository cues onto the observed gameplay-demo timeline.

An edited soundtrack, not captured Unreal output. No music, microphone, system
audio, or external assets. Native gains follow BBAudioFeedback.cpp; incidental
goals are quieter. Requires NumPy. Manifest example:
{"status":"complete","duration_seconds":180,"events":[{"time_seconds":8.25,"event":"throw"},
 {"time_seconds":10.5,"event":"goal","ball_index":0,"featured":true}]}
Times are seconds from video frame zero, not the live match clock. Requests and
unmapped events remain silent; the director must record observed outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import wave

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "SourceArt" / "Audio"
RATE = 48000
CHANNELS = 2
PEAK_CEILING = 10 ** (-1.0 / 20.0)
CUE_FILES = {name: f"S_BB_{name.title()}.wav" for name in ("throw", "score", "catch", "bounce")}
# Pickup, throw, catch and score match native BBAudioFeedback::Observe gains.
# Bounce is an original training cue, used only for an observed bounce event.
EVENT_CUES = {
    "quaffle_pickup": (("catch", .34),), "quark_pickup": (("catch", .34),),
    "bludger_pickup": (("catch", .34),), "pickup": (("catch", .34),),
    "throw": (("throw", .55),), "quaffle_throw": (("throw", .55),),
    "quark_throw": (("throw", .55),), "bludger_throw": (("throw", .55),),
    "goal": (("score", .48),),
    "snipe_catch": (("catch", .42), ("score", .48)),
    "snitch_catch": (("catch", .42), ("score", .48)),
    "bounce": (("bounce", .36),),
}


def number(value, label, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    value = float(value)
    if not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f"{label} must be finite and in [{lower}, {upper}]")
    return value


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cue(name):
    path = (SOURCE / CUE_FILES[name]).resolve()
    if not path.is_relative_to(SOURCE.resolve()):
        raise ValueError("Cue resolved outside original repository audio")
    with wave.open(str(path), "rb") as source:
        if source.getcomptype() != "NONE" or source.getsampwidth() != 2:
            raise ValueError(f"Expected original PCM16 source: {path}")
        channels, rate, frames = source.getnchannels(), source.getframerate(), source.getnframes()
        if channels not in (1, 2) or rate <= 0 or frames <= 0:
            raise ValueError(f"Invalid source format: {path}")
        samples = np.frombuffer(source.readframes(frames), dtype="<i2").astype(np.float32)
        samples = samples.reshape(-1, channels) / 32768.0
    output_frames = round(frames * RATE / rate)
    positions = np.arange(output_frames, dtype=np.float64) * rate / RATE
    resampled = np.empty((output_frames, channels), dtype=np.float32)
    for channel in range(channels):
        resampled[:, channel] = np.interp(positions, np.arange(frames), samples[:, channel], right=0.0)
    return resampled, {
        "path": str(path.relative_to(ROOT)), "sha256": sha256(path),
        "source_rate": rate, "source_channels": channels, "source_frames": frames,
        "mix_frames": output_frames,
    }


def mix(manifest_path, output_path, duration=None, receipt_path=None):
    manifest_path, output_path = Path(manifest_path).resolve(), Path(output_path).resolve()
    receipt_path = Path(receipt_path).resolve() if receipt_path else output_path.with_suffix(".mix.json")
    if output_path.suffix.lower() != ".wav":
        raise ValueError("Output must be a .wav file")
    if (output_path == manifest_path or output_path.is_relative_to(SOURCE.resolve())
            or receipt_path in (output_path, manifest_path) or receipt_path.is_relative_to(SOURCE.resolve())):
        raise ValueError("Outputs must not overwrite original audio or the event manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("events"), list):
        raise ValueError("Manifest must contain an events list")
    if manifest.get("status") != "complete" or manifest.get("rehearsal") is True:
        raise ValueError("Director manifest is not a completed observed capture")
    duration = number(duration if duration is not None else manifest.get("duration_seconds", 180),
                      "duration_seconds", .01, 600)
    frames = round(duration * RATE)
    buffer = np.zeros((frames, CHANNELS), dtype=np.float32)
    cues, sources, placements, ignored, events, identities = {}, {}, [], [], [], set()
    for index, event in enumerate(manifest["events"]):
        if not isinstance(event, dict) or not isinstance(event.get("event"), str):
            raise ValueError(f"Event {index} needs an event name")
        name = event["event"]
        time = number(event.get("time_seconds"), f"Event {index} time_seconds", 0, math.inf)
        if event.get("observed") is False or name not in EVENT_CUES or time >= frames / RATE:
            reason = "not_observed" if event.get("observed") is False else "no_original_cue" if name not in EVENT_CUES else "outside_audio_frames"
            ignored.append({"index": index, "event": name, "time_seconds": time, "reason": reason})
            continue
        identity = event.get("event_id", event.get("id"))
        if identity is not None:
            identity = str(identity)
            if identity in identities:
                raise ValueError(f"Duplicate observed event identity: {identity}")
            identities.add(identity)
        gain = number(event.get("audio_gain", 1.0), f"Event {index} audio_gain", 0, 2)
        pan = number(event.get("pan", 0.0), f"Event {index} pan", -1, 1)
        featured = event.get("featured", False)
        if not isinstance(featured, bool):
            raise ValueError(f"Event {index} featured must be a boolean")
        events.append((time, index, name, event, gain, pan, featured))
    for time, index, name, event, event_gain, pan, featured in sorted(events):
        start = round(time * RATE)
        editorial_gain = .35 if name == "goal" and not featured else 1.0
        for cue_name, native_gain in EVENT_CUES[name]:
            if cue_name not in cues:
                cues[cue_name], sources[cue_name] = load_cue(cue_name)
            cue = cues[cue_name]
            angle = (pan + 1.0) * math.pi / 4.0
            weights = np.array([math.cos(angle), math.sin(angle)], dtype=np.float32)
            stereo = cue * weights if cue.shape[1] == 1 else cue * (weights * math.sqrt(2.0))
            count, gain = min(cue.shape[0], frames - start), native_gain * event_gain * editorial_gain
            buffer[start:start + count] += stereo[:count] * gain
            placements.append({
                "event_index": index, "event": name, "ball_index": event.get("ball_index"),
                "cue": CUE_FILES[cue_name], "time_seconds": time, "start_sample": start,
                "quantized_time_seconds": start / RATE, "frames_mixed": count,
                "trimmed_at_video_end": count < cue.shape[0], "featured": featured, "gain": gain, "pan": pan,
            })
    if not placements:
        raise ValueError("No observed events map to repository cues; refusing to label silence as a demo mix")
    # A cue clipped by the end of the edit must not produce an abrupt PCM edge.
    fade_frames = min(frames, round(.01 * RATE))
    buffer[-fade_frames:] *= np.linspace(1.0, 0.0, fade_frames, dtype=np.float32)[:, None]
    peak_before = float(np.max(np.abs(buffer)))
    master_gain = min(1.0, PEAK_CEILING / peak_before) if peak_before > 0 else 1.0
    buffer *= master_gain
    peak = float(np.max(np.abs(buffer)))
    rms = float(np.sqrt(np.mean(np.square(buffer, dtype=np.float64))))
    pcm = np.rint(buffer * 32767.0).astype("<i2")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as output:
        output.setnchannels(CHANNELS)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(pcm.tobytes())
    with wave.open(str(output_path), "rb") as check:
        if (check.getnchannels(), check.getsampwidth(), check.getframerate(), check.getnframes()) != (2, 2, RATE, frames):
            raise RuntimeError("Written audio format differs from the requested stereo mix")
    result = {
        "status": "complete", "audio_type": "edited_repository_cue_mix", "raw_engine_audio": False,
        "microphone_or_system_audio": False, "external_music_or_assets": False, "wind_layer": None,
        "note": "Sparse edited game-cue soundtrack synchronized to observed director events; not raw engine output.",
        "manifest": str(manifest_path), "manifest_sha256": sha256(manifest_path),
        "output": str(output_path), "output_sha256": sha256(output_path),
        "sample_rate": RATE, "channels": CHANNELS, "pcm_bits": 16, "frames": frames,
        "duration_seconds": frames / RATE, "time_origin": "video frame zero / director capture origin",
        "source_resampling": "linear interpolation to 48000 Hz", "sources": sources,
        "end_fade_seconds": fade_frames / RATE,
        "placements": placements, "ignored_events": ignored, "peak_before_master": peak_before,
        "master_gain": master_gain, "sample_peak_dbfs": 20 * math.log10(peak) if peak else None,
        "rms_dbfs": 20 * math.log10(rms) if rms else None,
        "clipped_samples": int(np.count_nonzero(np.abs(buffer) >= 1.0)),
        "subjective_listening_check": "not_performed_by_this_script",
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / ".local/gameplay-demo-director.json")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/gameplay-demo/basketbroom-prototype-demo-audio.wav")
    parser.add_argument("--duration", type=float, help="Exact video duration; otherwise uses manifest duration_seconds")
    parser.add_argument("--receipt", type=Path, help="Default: output filename with .mix.json suffix")
    args = parser.parse_args()
    result = mix(args.manifest, args.output, args.duration, args.receipt)
    print(json.dumps({key: result[key] for key in ("status", "output", "duration_seconds", "sample_rate",
                                                 "channels", "sample_peak_dbfs", "clipped_samples")}, indent=2))


if __name__ == "__main__":
    main()

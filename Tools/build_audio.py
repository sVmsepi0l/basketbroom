"""Synthesize and import Basketbroom's original, lightweight game sounds.

Generate the reproducible source WAVs with ordinary Python (no Unreal needed):
    python Tools/build_audio.py --generate-source

Inside the Basketbroom UE 5.8 editor, import this module and call build().
The imported SoundWave assets live in /Basketbroom/Audio and have no runtime
Python dependency. All source audio is original deterministic synthesis.
"""

import argparse
import json
import math
from pathlib import Path
import random
import struct
import wave


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "SourceArt" / "Audio"
DESTINATION = "/Basketbroom/Audio"
SAMPLE_RATE = 44100
TAU = 2.0 * math.pi


def _bell(t, frequency, decay):
    """A rounded fundamental with a faint, inharmonic glass overtone."""
    if t < 0:
        return 0.0
    attack = min(1.0, t / 0.006)
    return attack * (
        math.sin(TAU * frequency * t) * math.exp(-t / decay)
        + 0.18 * math.sin(TAU * frequency * 2.756 * t) * math.exp(-t / (decay * 0.4))
    )


def _throw():
    duration = 0.18
    rng = random.Random(22050)
    slow = fast = 0.0
    samples = []
    for i in range(round(SAMPLE_RATE * duration)):
        t = i / SAMPLE_RATE
        u = t / duration
        noise = rng.uniform(-1.0, 1.0)
        # Difference of two low passes removes the bass and abrasive hiss.
        fast += (0.17 + 0.34 * u) * (noise - fast)
        slow += 0.055 * (noise - slow)
        envelope = math.sin(math.pi * u) ** 1.5
        airy = (fast - slow) * envelope
        air_tone = 0.035 * math.sin(TAU * (600 * t + 2100 * t * t)) * envelope
        samples.append(airy + air_tone)
    return samples


def _score():
    duration = 0.65
    notes = ((0.0, 659.255), (0.135, 830.609), (0.27, 987.767))
    return [sum(_bell(i / SAMPLE_RATE - start, hz, 0.15) for start, hz in notes)
            for i in range(round(SAMPLE_RATE * duration))]


def _catch():
    duration = 0.5
    notes = ((0.0, 1318.51), (0.055, 1975.53), (0.115, 2637.02))
    samples = []
    for i in range(round(SAMPLE_RATE * duration)):
        t = i / SAMPLE_RATE
        sparkle = sum(_bell(t - start, hz, 0.09) for start, hz in notes)
        shimmer = 0.14 * math.sin(TAU * 3951.07 * t) * math.exp(-t / 0.11)
        samples.append(sparkle + shimmer)
    return samples


def _bounce():
    duration = 0.08
    rng = random.Random(22051)
    samples = []
    for i in range(round(SAMPLE_RATE * duration)):
        t = i / SAMPLE_RATE
        # Integrating this downward pitch sweep keeps phase continuous.
        phase = TAU * (110 * t + 1.65 * (1.0 - math.exp(-t / 0.011)))
        body = math.sin(phase) * math.exp(-t / 0.021)
        pluck = 0.1 * rng.uniform(-1.0, 1.0) * math.exp(-t / 0.003)
        samples.append(body + pluck)
    return samples


CUES = (
    ("S_BB_Throw", _throw, 0.38),
    ("S_BB_Score", _score, 0.50),
    ("S_BB_Catch", _catch, 0.42),
    ("S_BB_Bounce", _bounce, 0.36),
)


def _pcm16(samples, peak):
    """Remove DC and gently fade both edges before setting a bounded peak."""
    if not samples or not 0.0 < peak <= 0.55:
        raise ValueError("Audio must have samples and a peak in (0, 0.55].")
    mean = sum(samples) / len(samples)
    attack = max(1, round(SAMPLE_RATE * 0.002))
    release = max(1, round(SAMPLE_RATE * 0.012))
    final_index = len(samples) - 1
    faded = [(value - mean) * min(1.0, i / attack, (final_index - i) / release)
             for i, value in enumerate(samples)]
    scale = peak / max(abs(value) for value in faded)
    # Truncate rather than round so quantization cannot exceed the peak bound.
    integers = [int(value * scale * 32767) for value in faded]
    return struct.pack("<%dh" % len(integers), *integers)


def generate_source():
    """Write mono PCM16 WAVs and return their exact, reusable source paths."""
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, synth, peak in CUES:
        path = SOURCE_DIR / (name + ".wav")
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(SAMPLE_RATE)
            output.writeframes(_pcm16(synth(), peak))
        paths[name] = str(path)
    return paths


def build():
    """Regenerate source audio, import/reimport all four assets, and save."""
    try:
        import unreal
    except ImportError as error:
        raise RuntimeError("Run build() inside the Basketbroom UE 5.8 editor; "
                           "use --generate-source for source WAVs only.") from error

    source_paths = generate_source()
    tasks = []
    for name, filename in source_paths.items():
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", filename)
        task.set_editor_property("destination_path", DESTINATION)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", True)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

    imported = {}
    for name in source_paths:
        object_path = "%s/%s.%s" % (DESTINATION, name, name)
        sound = unreal.load_asset(object_path)
        if sound is None or not isinstance(sound, unreal.SoundWave):
            raise RuntimeError("Expected imported SoundWave: " + object_path)
        if not unreal.EditorAssetLibrary.save_loaded_asset(sound, only_if_is_dirty=False):
            raise RuntimeError("Could not save imported audio: " + object_path)
        imported[name] = sound.get_path_name()
    unreal.log("BASKETBROOM_AUDIO_COMPLETE " + json.dumps(imported, sort_keys=True))
    return imported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate-source", action="store_true",
                        help="Generate deterministic WAV sources without Unreal Engine.")
    args = parser.parse_args()
    RESULT = generate_source() if args.generate_source else build()
    print(json.dumps(RESULT, indent=2))

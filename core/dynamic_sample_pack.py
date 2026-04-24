"""Dynamic sample pack generator that synthesizes genre-appropriate drum samples.

Instead of requiring pre-recorded WAV files, this module generates
appropriate drum one-shots on-the-fly based on the target genre. Each genre
gets carefully tuned synthesis parameters to match its sonic character.
"""

from __future__ import annotations

import math
import random
import struct
import wave
from array import array
from pathlib import Path


# ---------------------------------------------------------------------------
# Genre-specific synthesis recipes
# ---------------------------------------------------------------------------

GENRE_RECIPES: dict[str, dict[str, dict]] = {
    "trap": {
        "kick": {"freq_start": 160, "freq_end": 38, "decay": 8.5, "click": 0.18, "dist": 1.4, "dur": 0.50},
        "snare": {"tone_freq": 200, "tone_decay": 14, "noise_decay": 22, "noise_mix": 0.80, "dur": 0.22},
        "hats_closed": {"decay": 60, "brightness": 0.92, "dur": 0.06},
        "hats_open": {"decay": 14, "brightness": 0.88, "dur": 0.28},
        "perc": {"freq": 800, "decay": 24, "noise_mix": 0.30, "dur": 0.14},
    },
    "drill": {
        "kick": {"freq_start": 155, "freq_end": 40, "decay": 9.0, "click": 0.22, "dist": 1.5, "dur": 0.48},
        "snare": {"tone_freq": 210, "tone_decay": 12, "noise_decay": 26, "noise_mix": 0.85, "dur": 0.20},
        "hats_closed": {"decay": 55, "brightness": 0.95, "dur": 0.05},
        "hats_open": {"decay": 12, "brightness": 0.90, "dur": 0.32},
        "perc": {"freq": 750, "decay": 22, "noise_mix": 0.35, "dur": 0.13},
    },
    "boom_bap": {
        "kick": {"freq_start": 140, "freq_end": 45, "decay": 7.0, "click": 0.12, "dist": 1.1, "dur": 0.42},
        "snare": {"tone_freq": 180, "tone_decay": 10, "noise_decay": 18, "noise_mix": 0.72, "dur": 0.26},
        "hats_closed": {"decay": 50, "brightness": 0.70, "dur": 0.07},
        "hats_open": {"decay": 16, "brightness": 0.65, "dur": 0.24},
        "perc": {"freq": 580, "decay": 20, "noise_mix": 0.40, "dur": 0.16},
    },
    "lofi": {
        "kick": {"freq_start": 130, "freq_end": 42, "decay": 6.5, "click": 0.08, "dist": 0.9, "dur": 0.38},
        "snare": {"tone_freq": 170, "tone_decay": 11, "noise_decay": 16, "noise_mix": 0.65, "dur": 0.24},
        "hats_closed": {"decay": 48, "brightness": 0.55, "dur": 0.07},
        "hats_open": {"decay": 18, "brightness": 0.50, "dur": 0.22},
        "perc": {"freq": 520, "decay": 18, "noise_mix": 0.45, "dur": 0.18},
    },
    "phonk": {
        "kick": {"freq_start": 170, "freq_end": 36, "decay": 9.5, "click": 0.25, "dist": 1.8, "dur": 0.52},
        "snare": {"tone_freq": 220, "tone_decay": 13, "noise_decay": 28, "noise_mix": 0.78, "dur": 0.18},
        "hats_closed": {"decay": 65, "brightness": 0.96, "dur": 0.05},
        "hats_open": {"decay": 11, "brightness": 0.94, "dur": 0.30},
        "perc": {"freq": 900, "decay": 26, "noise_mix": 0.28, "dur": 0.12},
    },
    "house": {
        "kick": {"freq_start": 145, "freq_end": 50, "decay": 7.5, "click": 0.20, "dist": 1.2, "dur": 0.46},
        "snare": {"tone_freq": 195, "tone_decay": 15, "noise_decay": 20, "noise_mix": 0.68, "dur": 0.20},
        "hats_closed": {"decay": 58, "brightness": 0.82, "dur": 0.06},
        "hats_open": {"decay": 13, "brightness": 0.78, "dur": 0.26},
        "perc": {"freq": 700, "decay": 22, "noise_mix": 0.32, "dur": 0.15},
    },
    "acoustic": {
        "kick": {"freq_start": 90, "freq_end": 60, "decay": 12, "click": 0.4, "dist": 0.8, "dur": 0.3},
        "snare": {"tone_freq": 250, "tone_decay": 18, "noise_decay": 12, "noise_mix": 0.6, "dur": 0.25},
        "hats_closed": {"decay": 30, "brightness": 0.70, "dur": 0.08},
        "hats_open": {"decay": 10, "brightness": 0.65, "dur": 0.35},
        "perc": {"freq": 600, "decay": 15, "noise_mix": 0.50, "dur": 0.15},
    },
}

SAMPLE_RATE = 44_100


# ---------------------------------------------------------------------------
# Synthesis functions
# ---------------------------------------------------------------------------

def _synth_kick(params: dict, seed: int) -> array:
    sr = SAMPLE_RATE
    dur = params.get("dur", 0.45)
    n = int(dur * sr)
    freq_start = params.get("freq_start", 150)
    freq_end = params.get("freq_end", 40)
    decay = params.get("decay", 8.5)
    click_amount = params.get("click", 0.18)
    distortion = params.get("dist", 1.4)

    out = array("f")
    for i in range(n):
        t = i / sr
        env = math.exp(-decay * t)
        freq = freq_end + (freq_start - freq_end) * math.exp(-18 * t)
        body = math.sin(2 * math.pi * freq * t)
        click = math.sin(2 * math.pi * 1800 * t) * math.exp(-50 * t)
        sample = (body * env * distortion) + (click * click_amount)
        sample = math.tanh(sample)  # soft clip
        out.append(sample)
    return out


def _synth_snare(params: dict, seed: int) -> array:
    sr = SAMPLE_RATE
    dur = params.get("dur", 0.22)
    n = int(dur * sr)
    tone_freq = params.get("tone_freq", 200)
    tone_decay = params.get("tone_decay", 14)
    noise_decay = params.get("noise_decay", 22)
    noise_mix = params.get("noise_mix", 0.78)

    rng = random.Random(seed)
    out = array("f")
    for i in range(n):
        t = i / sr
        noise = rng.uniform(-1.0, 1.0) * math.exp(-noise_decay * t)
        tone = math.sin(2 * math.pi * tone_freq * t) * math.exp(-tone_decay * t)
        out.append((noise * noise_mix) + (tone * (1.0 - noise_mix * 0.5)))
    return out


def _synth_hats(params: dict, seed: int) -> array:
    sr = SAMPLE_RATE
    dur = params.get("dur", 0.08)
    n = int(dur * sr)
    decay = params.get("decay", 55)
    brightness = params.get("brightness", 0.85)

    rng = random.Random(seed)
    out = array("f")
    last = 0.0
    for i in range(n):
        t = i / sr
        noise = rng.uniform(-1.0, 1.0)
        # High-pass filter for brightness
        hp = noise - last * (1.0 - brightness * 0.15)
        last = noise
        out.append(hp * math.exp(-decay * t) * 0.6)
    return out


def _synth_perc(params: dict, seed: int) -> array:
    sr = SAMPLE_RATE
    dur = params.get("dur", 0.14)
    n = int(dur * sr)
    freq = params.get("freq", 700)
    decay = params.get("decay", 22)
    noise_mix = params.get("noise_mix", 0.30)

    rng = random.Random(seed)
    out = array("f")
    for i in range(n):
        t = i / sr
        noise = rng.uniform(-0.8, 0.8) * math.exp(-decay * t)
        tone = math.sin(2 * math.pi * freq * t) * math.exp(-decay * 0.8 * t)
        out.append((tone * (1.0 - noise_mix)) + (noise * noise_mix))
    return out


SYNTH_MAP = {
    "kick": _synth_kick,
    "snare": _synth_snare,
    "hats_closed": _synth_hats,
    "hats_open": _synth_hats,
    "perc": _synth_perc,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_sample_pack(genre: str, output_dir: Path, seed: int = 42) -> Path:
    """Generate a genre-appropriate sample pack and write to disk.

    Returns the output directory path, ready to be passed to SamplePack().
    """
    recipe = GENRE_RECIPES.get(genre, GENRE_RECIPES["trap"])
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for stem_key, params in recipe.items():
        synth_fn = SYNTH_MAP.get(stem_key)
        if synth_fn is None:
            continue
        audio = synth_fn(params, seed)
        _normalize(audio, 0.92)
        path = output_dir / f"{stem_key}.wav"
        _write_wav(path, audio)

    return output_dir


def get_available_genres() -> list[str]:
    """Return all genres with synthesis recipes."""
    return sorted(GENRE_RECIPES.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(audio: array, ceiling: float = 0.92) -> None:
    peak = max((abs(s) for s in audio), default=0.0)
    if peak <= 0:
        return
    scale = min(1.0, ceiling / peak)
    if scale == 1.0:
        return
    for i, s in enumerate(audio):
        audio[i] = s * scale


def _write_wav(path: Path, audio: array) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for s in audio:
            clipped = max(-1.0, min(1.0, s))
            frames.extend(struct.pack("<h", int(clipped * 32767)))
        wf.writeframes(frames)

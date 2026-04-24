from __future__ import annotations

import struct
import wave
from array import array
from pathlib import Path


class SamplePack:
    FILE_MAP = {
        "kick": "kick.wav",
        "snare": "snare.wav",
        "hats_closed": "hats_closed.wav",
        "hats_open": "hats_open.wav",
        "perc": "perc.wav",
    }

    def __init__(self, root: Path, target_sample_rate: int):
        self.root = root
        self.target_sample_rate = target_sample_rate
        self.samples: dict[str, array] = {}
        self._load()

    def get(self, stem_key: str) -> array | None:
        return self.samples.get(stem_key)

    def describe(self) -> str:
        available = sorted(self.samples.keys())
        return f"{self.root.name} ({', '.join(available)})" if available else f"{self.root.name} (empty)"

    def _load(self) -> None:
        if not self.root.exists():
            raise FileNotFoundError(f"Sample pack folder not found: {self.root}")
        for key, filename in self.FILE_MAP.items():
            path = self.root / filename
            if path.exists():
                self.samples[key] = self._read_wav(path)

    def _read_wav(self, path: Path) -> array:
        with wave.open(str(path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            raw = wav_file.readframes(frame_count)

        if sample_width != 2:
            raise ValueError(f"Sample pack file must be 16-bit PCM WAV: {path}")

        ints = struct.unpack("<" + ("h" * (len(raw) // 2)), raw)
        mono = array("f")
        if channels == 1:
            mono.extend(sample / 32768.0 for sample in ints)
        else:
            for index in range(0, len(ints), channels):
                mono.append(sum(ints[index:index + channels]) / (channels * 32768.0))

        if sample_rate != self.target_sample_rate:
            mono = self._resample_linear(mono, sample_rate, self.target_sample_rate)
        return mono

    def _resample_linear(self, source: array, source_rate: int, target_rate: int) -> array:
        if source_rate == target_rate or len(source) < 2:
            return source
        ratio = target_rate / source_rate
        target_length = max(1, int(len(source) * ratio))
        output = array("f")
        for idx in range(target_length):
            position = idx / ratio
            left = int(position)
            right = min(left + 1, len(source) - 1)
            frac = position - left
            sample = source[left] * (1.0 - frac) + source[right] * frac
            output.append(sample)
        return output

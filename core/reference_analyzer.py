from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReferenceProfile:
    source_path: Path
    bpm: int
    key_root: str
    scale: str
    energy: float
    brightness: float
    genre_hint: str

    @property
    def summary(self) -> str:
        return (
            f"{self.source_path.name} -> {self.genre_hint}, {self.bpm} BPM, "
            f"{self.key_root} {self.scale}, energy {self.energy:.2f}"
        )


class ReferenceAnalyzer:
    ROOTS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    MAJOR_TEMPLATE = {0, 2, 4, 5, 7, 9, 11}
    MINOR_TEMPLATE = {0, 2, 3, 5, 7, 8, 10}

    def analyze(self, path: Path) -> ReferenceProfile:
        if path.suffix.lower() != ".wav":
            raise ValueError("Reference analysis currently supports WAV files only.")
        samples, sample_rate = self._read_wav_mono(path)
        if not samples:
            raise ValueError(f"Reference file {path} contains no audio samples.")

        bpm, energy = self._estimate_tempo_and_energy(samples, sample_rate)
        key_root, scale = self._estimate_key(samples, sample_rate)
        brightness = self._estimate_brightness(samples)
        genre_hint = self._infer_genre(bpm, brightness, energy)
        return ReferenceProfile(
            source_path=path,
            bpm=bpm,
            key_root=key_root,
            scale=scale,
            energy=energy,
            brightness=brightness,
            genre_hint=genre_hint,
        )

    def _read_wav_mono(self, path: Path) -> tuple[list[float], int]:
        with wave.open(str(path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            raw = wav_file.readframes(frame_count)

        if sample_width != 2:
            raise ValueError("Only 16-bit PCM WAV files are supported for reference analysis.")

        ints = struct.unpack("<" + ("h" * (len(raw) // 2)), raw)
        if channels == 1:
            mono = [sample / 32768.0 for sample in ints]
        else:
            mono = []
            for index in range(0, len(ints), channels):
                mono.append(sum(ints[index:index + channels]) / (channels * 32768.0))

        max_seconds = 45
        max_samples = sample_rate * max_seconds
        return mono[:max_samples], sample_rate

    def _estimate_tempo_and_energy(self, samples: list[float], sample_rate: int) -> tuple[int, float]:
        frame_size = 1024
        hop = 512
        if len(samples) < frame_size:
            return 120, 0.5

        energies = []
        for start in range(0, len(samples) - frame_size, hop):
            frame = samples[start:start + frame_size]
            energy = sum(sample * sample for sample in frame) / frame_size
            energies.append(energy)

        onset = [max(0.0, energies[i] - energies[i - 1]) for i in range(1, len(energies))]
        if not onset:
            return 120, 0.5

        best_bpm = 120
        best_score = float("-inf")
        for bpm in range(70, 171):
            lag = max(1, round((60 * sample_rate) / (bpm * hop)))
            if lag >= len(onset):
                continue
            score = 0.0
            for index in range(lag, len(onset)):
                score += onset[index] * onset[index - lag]
            if score > best_score:
                best_score = score
                best_bpm = bpm

        avg_energy = sum(energies) / len(energies)
        normalized_energy = min(1.0, math.sqrt(max(0.0, avg_energy)) * 6)
        return best_bpm, normalized_energy

    def _estimate_brightness(self, samples: list[float]) -> float:
        if len(samples) < 2:
            return 0.5
        zero_crossings = 0
        for left, right in zip(samples, samples[1:]):
            if (left >= 0 > right) or (left < 0 <= right):
                zero_crossings += 1
        rate = zero_crossings / max(1, len(samples) - 1)
        return min(1.0, rate * 8)

    def _estimate_key(self, samples: list[float], sample_rate: int) -> tuple[str, str]:
        if len(samples) < 4096:
            return "C", "minor"

        start = len(samples) // 3
        window_size = min(16384, len(samples) - start)
        window = samples[start:start + window_size]
        if len(window) < 4096:
            return "C", "minor"

        hann = [0.5 - 0.5 * math.cos((2 * math.pi * n) / (len(window) - 1)) for n in range(len(window))]
        windowed = [sample * hann[idx] for idx, sample in enumerate(window)]

        pitch_scores = [0.0] * 12
        for midi_note in range(36, 85):
            frequency = 440.0 * (2 ** ((midi_note - 69) / 12))
            magnitude = self._goertzel(windowed, sample_rate, frequency)
            pitch_scores[midi_note % 12] += magnitude

        best_root = 0
        best_scale = "minor"
        best_score = float("-inf")
        for root in range(12):
            major_score = self._template_score(pitch_scores, root, self.MAJOR_TEMPLATE)
            minor_score = self._template_score(pitch_scores, root, self.MINOR_TEMPLATE)
            if major_score > best_score:
                best_score = major_score
                best_root = root
                best_scale = "major"
            if minor_score > best_score:
                best_score = minor_score
                best_root = root
                best_scale = "minor"

        return self.ROOTS[best_root], best_scale

    def _goertzel(self, samples: list[float], sample_rate: int, frequency: float) -> float:
        w = (2.0 * math.pi * frequency) / sample_rate
        coeff = 2.0 * math.cos(w)
        s_prev = 0.0
        s_prev2 = 0.0
        for sample in samples:
            s = sample + coeff * s_prev - s_prev2
            s_prev2 = s_prev
            s_prev = s
        real = s_prev - s_prev2 * math.cos(w)
        imag = s_prev2 * math.sin(w)
        return math.sqrt(real * real + imag * imag)

    def _template_score(self, pitch_scores: list[float], root: int, template: set[int]) -> float:
        score = 0.0
        for pitch_class, magnitude in enumerate(pitch_scores):
            interval = (pitch_class - root) % 12
            score += magnitude if interval in template else -magnitude * 0.35
        return score

    def _infer_genre(self, bpm: int, brightness: float, energy: float) -> str:
        if 120 <= bpm <= 130 and brightness > 0.22:
            return "house"
        if bpm >= 136 and brightness > 0.26 and energy > 0.45:
            return "phonk"
        if bpm >= 138 and brightness <= 0.30:
            return "drill"
        if bpm >= 128:
            return "trap"
        if bpm <= 90 and brightness < 0.20:
            return "lofi"
        if bpm <= 100:
            return "boom_bap"
        return "trap"

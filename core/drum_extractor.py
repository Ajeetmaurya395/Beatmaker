from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import struct
import wave

from core.reference_analyzer import ReferenceAnalyzer

try:
    import librosa  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    librosa = None


@dataclass(frozen=True)
class DrumPattern:
    kick: list[int]
    snare: list[int]
    hats: list[tuple[int, bool]]
    perc: list[int]
    bpm: int
    bars: int
    source_method: str

    def to_dict(self) -> dict:
        return {
            "kick": self.kick,
            "snare": self.snare,
            "hats": [[step, is_open] for step, is_open in self.hats],
            "perc": self.perc,
            "bpm": self.bpm,
            "bars": self.bars,
            "source_method": self.source_method,
        }


class DrumPatternExtractor:
    def __init__(self):
        self.reference_analyzer = ReferenceAnalyzer()

    def extract(self, audio_path: Path, bpm_hint: int | None = None) -> DrumPattern:
        if librosa is not None:
            try:
                return self._extract_with_librosa(audio_path, bpm_hint)
            except Exception:
                pass
        return self._extract_fallback(audio_path, bpm_hint)

    def _extract_with_librosa(self, audio_path: Path, bpm_hint: int | None = None) -> DrumPattern:
        y, sr = librosa.load(str(audio_path), sr=None, mono=True)
        y = y[: sr * 30]
        if len(y) == 0:
            raise ValueError("No audio available for drum extraction.")

        y_percussive = librosa.effects.percussive(y)
        onset_frames = librosa.onset.onset_detect(y=y_percussive, sr=sr, units="frames")
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        onset_env = librosa.onset.onset_strength(y=y_percussive, sr=sr)
        tempo = bpm_hint or int(round(float(librosa.feature.tempo(onset_envelope=onset_env, sr=sr)[0])))
        tempo = max(60, min(180, tempo))

        if len(onset_frames) == 0:
            raise ValueError("No onsets detected.")

        spectral_centroids = librosa.feature.spectral_centroid(y=y_percussive, sr=sr)[0]
        rms = librosa.feature.rms(y=y_percussive)[0]

        kick: list[int] = []
        snare: list[int] = []
        hats: list[tuple[int, bool]] = []
        perc: list[int] = []

        sixteenth = 60.0 / tempo / 4.0
        bars = 2
        max_time = min(len(y) / sr, bars * 4 * (60.0 / tempo))
        for frame, onset_time in zip(onset_frames, onset_times):
            if onset_time >= max_time:
                continue
            step = int(round(onset_time / sixteenth)) % (bars * 16)
            centroid = spectral_centroids[min(frame, len(spectral_centroids) - 1)]
            level = rms[min(frame, len(rms) - 1)]

            if centroid < 900 and level > 0.04:
                kick.append(step % 16)
            elif centroid < 2800:
                if step % 16 in {4, 12, 10} or level > 0.08:
                    snare.append(step % 16)
                else:
                    perc.append(step % 16)
            else:
                hats.append((step % 16, centroid > 5200))

        return self._normalize_pattern(kick, snare, hats, perc, tempo, bars, "librosa")

    def _extract_fallback(self, audio_path: Path, bpm_hint: int | None = None) -> DrumPattern:
        profile = self.reference_analyzer.analyze(audio_path)
        tempo = bpm_hint or profile.bpm
        groove = profile.groove_steps or [0, 4, 8, 12]
        kick = [step for step in groove if step in {0, 2, 4, 6, 8, 10, 12, 14}] or [0, 8, 12]
        snare = profile.backbeat_steps or [4, 12]
        hats = sorted(set((step, False) for step in groove + [s for s in range(0, 16, 2)]))
        perc = sorted(set(step for step in groove if step not in {0, 4, 8, 12})) or [3, 7, 11, 15]
        return self._normalize_pattern(kick, snare, hats, perc, tempo, 1, "fallback")

    def _normalize_pattern(
        self,
        kick: list[int],
        snare: list[int],
        hats: list[tuple[int, bool]],
        perc: list[int],
        bpm: int,
        bars: int,
        source_method: str,
    ) -> DrumPattern:
        kick = sorted({step % 16 for step in kick}) or [0, 8, 12]
        snare = sorted({step % 16 for step in snare}) or [4, 12]
        hats = sorted({(step % 16, is_open) for step, is_open in hats}) or [(step, False) for step in range(0, 16, 2)]
        perc = sorted({step % 16 for step in perc})
        return DrumPattern(
            kick=kick,
            snare=snare,
            hats=hats,
            perc=perc,
            bpm=bpm,
            bars=bars,
            source_method=source_method,
        )

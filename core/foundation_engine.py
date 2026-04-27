from __future__ import annotations

import base64
import io
import json
import struct
import urllib.error
import urllib.request
import wave
from array import array
from dataclasses import dataclass

from core.beat_spec import BeatSpec


@dataclass(frozen=True)
class FoundationStemResult:
    stem: str
    audio: array
    prompt: str
    bars: int
    provider: str


class FoundationVoiceEngine:
    STEM_FAMILIES = {
        "bass_808": ("Bass", "Sub Bass"),
        "chords": ("Synth", "Pad"),
        "lead": ("Synth", "Lead"),
    }

    STEM_NOTATION = {
        "bass_808": "Notation: Root Motion, Low Register, Locked Groove",
        "chords": "Notation: Sustained Chords, Smooth Voice Leading",
        "lead": "Notation: Melodic Phrase, Sparse Hooks, Clear Cadence",
    }

    def __init__(self, base_url: str | None, timeout_seconds: int = 180):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def generate_stems(
        self,
        spec: BeatSpec,
        swarm_state: dict | None = None,
        tags: list[str] | None = None,
        stems: tuple[str, ...] = ("bass_808", "chords", "lead"),
    ) -> tuple[dict[str, array], dict]:
        if not self.enabled:
            return {}, {"enabled": False, "reason": "no_base_url"}

        rendered: dict[str, array] = {}
        metadata: dict[str, dict] = {}
        swarm_state = swarm_state or {}
        tags = list(tags or [])
        sample_traits = list(swarm_state.get("sample_traits") or [])
        loop_bars = self._preferred_loop_bars(spec)

        for stem in stems:
            prompt = self._build_prompt(spec, stem, tags, sample_traits, swarm_state, loop_bars)
            payload = {
                "prompt": prompt,
                "stem": stem,
                "bpm": spec.bpm,
                "bars": loop_bars,
                "key_root": spec.key_root,
                "scale": spec.scale,
                "genre": spec.genre,
                "tags": tags,
                "sample_traits": sample_traits,
            }
            try:
                result = self._request_stem(payload)
            except Exception as exc:
                metadata[stem] = {
                    "provider": "foundation_remote",
                    "status": "failed",
                    "error": str(exc),
                    "prompt": prompt,
                    "bars": loop_bars,
                }
                continue

            rendered[stem] = self._fit_loop_to_song(result.audio, spec, result.bars)
            metadata[stem] = {
                "provider": result.provider,
                "status": "ok",
                "prompt": result.prompt,
                "bars": result.bars,
            }

        return rendered, {
            "enabled": True,
            "base_url": self.base_url,
            "loop_bars": loop_bars,
            "stems": metadata,
        }

    def _request_stem(self, payload: dict) -> FoundationStemResult:
        assert self.base_url is not None
        request = urllib.request.Request(
            url=f"{self.base_url}/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                content_type = response.headers.get("Content-Type", "")
                body = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Foundation provider HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Foundation provider unavailable: {exc.reason}") from exc

        if "audio/wav" in content_type or "audio/x-wav" in content_type:
            audio = self._decode_wav_bytes(body)
            return FoundationStemResult(
                stem=payload["stem"],
                audio=audio,
                prompt=payload["prompt"],
                bars=int(payload["bars"]),
                provider="foundation_remote",
            )

        data = json.loads(body.decode("utf-8"))
        audio_b64 = data.get("audio_base64")
        if not audio_b64:
            raise RuntimeError("Foundation provider did not return audio_base64 or WAV content.")
        audio = self._decode_wav_bytes(base64.b64decode(audio_b64))
        return FoundationStemResult(
            stem=data.get("stem", payload["stem"]),
            audio=audio,
            prompt=data.get("prompt", payload["prompt"]),
            bars=int(data.get("bars", payload["bars"])),
            provider=data.get("provider", "foundation_remote"),
        )

    def _build_prompt(
        self,
        spec: BeatSpec,
        stem: str,
        tags: list[str],
        sample_traits: list[str],
        swarm_state: dict,
        loop_bars: int,
    ) -> str:
        family, sub_family = self.STEM_FAMILIES.get(stem, ("Synth", "Texture"))
        layered: list[str] = [family, sub_family]

        timbre_tags: list[str] = []
        for tag in list(sample_traits) + list(tags):
            normalized = tag.replace("_", " ").title()
            if normalized not in timbre_tags:
                timbre_tags.append(normalized)

        if spec.genre == "hindi_indie":
            timbre_tags.extend(["Warm", "Airy", "Boutique"])
        elif spec.genre == "house":
            timbre_tags.extend(["Bright", "Wide", "Energetic"])
        elif spec.genre == "drill":
            timbre_tags.extend(["Dark", "Tight", "Aggressive"])

        unique_timbres: list[str] = []
        for item in timbre_tags:
            if item not in unique_timbres:
                unique_timbres.append(item)

        layered.extend(unique_timbres[:5])
        layered.append(self.STEM_NOTATION.get(stem, "Notation: Structured Loop"))
        layered.append(f"BPM {spec.bpm}")
        layered.append(f"{loop_bars} Bars")
        layered.append(f"Key {spec.key_root} {spec.scale.title()}")
        if swarm_state.get("critic_feedback"):
            layered.append(f"Constraint: {swarm_state['critic_feedback']}")
        return ", ".join(layered)

    def _preferred_loop_bars(self, spec: BeatSpec) -> int:
        if spec.total_bars >= 16:
            return 4
        if spec.total_bars >= 8:
            return 2
        return max(1, spec.total_bars)

    def _fit_loop_to_song(self, audio: array, spec: BeatSpec, loop_bars: int, sample_rate: int = 44_100) -> array:
        loop_seconds = (loop_bars * 4 / spec.bpm) * 60
        target_seconds = (spec.total_beats / spec.bpm) * 60 + 1.5
        target_samples = int(target_seconds * sample_rate)
        if not audio:
            return array("f", [0.0]) * target_samples
        if loop_seconds <= 0 or len(audio) >= target_samples:
            return array("f", list(audio[:target_samples]) + [0.0] * max(0, target_samples - len(audio)))
        out = array("f")
        while len(out) < target_samples:
            out.extend(audio)
        if len(out) > target_samples:
            del out[target_samples:]
        return out

    def _decode_wav_bytes(self, data: bytes) -> array:
        with wave.open(io.BytesIO(data), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            raw = wav_file.readframes(wav_file.getnframes())
        if sample_width != 2:
            raise RuntimeError("Foundation provider returned non-16-bit PCM audio.")
        ints = struct.unpack("<" + ("h" * (len(raw) // 2)), raw)
        output = array("f")
        if channels == 1:
            output.extend(sample / 32768.0 for sample in ints)
        else:
            for index in range(0, len(ints), channels):
                output.append(sum(ints[index:index + channels]) / (channels * 32768.0))
        return output

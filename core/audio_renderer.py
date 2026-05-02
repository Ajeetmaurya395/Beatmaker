from __future__ import annotations

import math
import random
import struct
import wave
from array import array
from pathlib import Path

from core.beat_spec import BeatSpec, NoteEvent
from core.sample_pack import SamplePack


class AudioRenderer:
    SAMPLE_RATE = 44_100

    STEM_GAIN = {
        "kick": 1.00,
        "snare": 0.78,
        "hats": 0.35,
        "perc": 0.30,
        "bass_808": 0.90,
        "chords": 0.32,
        "lead": 0.26,
    }

    # Hindi Indie: guitar/piano carries emotion, lead is a ghost pad, drums are gentle
    STEM_GAIN_HINDI_INDIE = {
        "kick": 0.55,
        "snare": 0.40,
        "hats": 0.18,
        "perc": 0.14,
        "bass_808": 0.60,
        "chords": 0.72,
        "lead": 0.08,
    }

    HINDI_INDIE_CUES = (
        "aditya rikhari",
        "aditya",
        "rikhari",
        "hindi indie",
        "indie acoustic",
        "indie pop",
        "moody acoustic",
    )

    def render_stem(self, stem: str, events: list[NoteEvent], spec: BeatSpec, sample_pack: SamplePack | None = None) -> array:
        total_seconds = (spec.total_beats / spec.bpm) * 60 + 1.5
        total_samples = int(total_seconds * self.SAMPLE_RATE)
        buffer = array("f", [0.0]) * total_samples

        gain_table = self.STEM_GAIN_HINDI_INDIE if self._is_hindi_indie(spec) else self.STEM_GAIN
        stem_gain = gain_table.get(stem, 0.35)

        for index, event in enumerate(events):
            start_sample = max(0, int((event.start_beat / spec.bpm) * 60 * self.SAMPLE_RATE))
            samples = self._render_event(stem, event, spec, index, sample_pack)
            for offset, sample in enumerate(samples):
                buffer_index = start_sample + offset
                if buffer_index >= total_samples:
                    break
                buffer[buffer_index] += sample * stem_gain

        self._normalize(buffer, ceiling=0.92)
        return buffer

    def write_wav(self, path: Path, audio: array) -> None:
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.SAMPLE_RATE)

            frames = bytearray()
            for sample in audio:
                clipped = max(-1.0, min(1.0, sample))
                frames.extend(struct.pack("<h", int(clipped * 32767)))
            wav_file.writeframes(frames)

    def read_wav(self, path: Path) -> array:
        with wave.open(str(path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frame_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            raw = wav_file.readframes(frame_count)

        if sample_width != 2:
            raise ValueError(f"Unsupported WAV sample width in {path}")
        if frame_rate != self.SAMPLE_RATE:
            raise ValueError(f"Expected {self.SAMPLE_RATE}Hz WAV at {path}, got {frame_rate}")

        ints = struct.unpack("<" + ("h" * (len(raw) // 2)), raw)
        output = array("f")
        if channels == 1:
            output.extend(sample / 32768.0 for sample in ints)
        else:
            for index in range(0, len(ints), channels):
                output.append(sum(ints[index:index + channels]) / (channels * 32768.0))
        return output

    def mix(self, stem_buffers: dict[str, array]) -> array:
        max_len = max((len(buffer) for buffer in stem_buffers.values()), default=0)
        mix = array("f", [0.0]) * max_len
        for buffer in stem_buffers.values():
            for idx, sample in enumerate(buffer):
                mix[idx] += sample
        self._normalize(mix, ceiling=0.90)
        return mix

    def _render_event(
        self,
        stem: str,
        event: NoteEvent,
        spec: BeatSpec,
        index: int,
        sample_pack: SamplePack | None,
    ) -> array:
        duration_seconds = max(0.05, event.duration_beats * 60 / spec.bpm)
        is_hindi_indie = self._is_hindi_indie(spec)
        if stem == "kick":
            duration_seconds = min(0.55, max(0.18 if is_hindi_indie else 0.22, duration_seconds))
        elif stem == "snare":
            duration_seconds = min(0.28, max(0.10 if is_hindi_indie else 0.12, duration_seconds))
        elif stem == "hats":
            duration_seconds = 0.18 if is_hindi_indie else 0.24 if event.pitch == 46 else 0.08
        elif stem == "perc":
            duration_seconds = 0.14 if is_hindi_indie else 0.18

        sample_count = max(1, int(duration_seconds * self.SAMPLE_RATE))
        if sample_pack and stem in {"kick", "snare", "hats", "perc"}:
            sample_key = stem
            if stem == "hats":
                sample_key = "hats_open" if event.pitch == 46 else "hats_closed"
            rendered = sample_pack.get(sample_key)
            if rendered is not None:
                return array("f", rendered)

        render_fn = {
            "kick": self._kick,
            "snare": self._snare,
            "hats": self._hats,
            "perc": self._perc,
            "bass_808": self._bass_808,
            "chords": self._poly_synth,
            "lead": self._lead,
        }.get(stem, self._poly_synth)
        return render_fn(event, sample_count, spec, index)

    def _kick(self, event: NoteEvent, sample_count: int, spec: BeatSpec, index: int) -> array:
        audio = array("f")
        for sample_idx in range(sample_count):
            t = sample_idx / self.SAMPLE_RATE
            env = math.exp(-9.5 * t)
            freq = 42 + (120 * math.exp(-18 * t))
            body = math.sin(2 * math.pi * freq * t)
            click = math.sin(2 * math.pi * 1600 * t) * math.exp(-45 * t)
            audio.append((body * env * 1.2) + (click * 0.15))
        return audio

    def _snare(self, event: NoteEvent, sample_count: int, spec: BeatSpec, index: int) -> array:
        rng = random.Random(spec.seed + index * 17 + event.pitch)
        audio = array("f")
        for sample_idx in range(sample_count):
            t = sample_idx / self.SAMPLE_RATE
            noise = rng.uniform(-1.0, 1.0) * math.exp(-28 * t)
            tone = math.sin(2 * math.pi * 190 * t) * math.exp(-16 * t)
            audio.append((noise * 0.75) + (tone * 0.28))
        return audio

    def _hats(self, event: NoteEvent, sample_count: int, spec: BeatSpec, index: int) -> array:
        rng = random.Random(spec.seed + index * 31 + event.pitch)
        decay = 20 if event.pitch == 46 else 55
        audio = array("f")
        last = 0.0
        for sample_idx in range(sample_count):
            t = sample_idx / self.SAMPLE_RATE
            noise = rng.uniform(-1.0, 1.0)
            high = noise - last * 0.88
            last = noise
            audio.append(high * math.exp(-decay * t) * 0.55)
        return audio

    def _perc(self, event: NoteEvent, sample_count: int, spec: BeatSpec, index: int) -> array:
        rng = random.Random(spec.seed + index * 43 + event.pitch)
        audio = array("f")
        prompt = spec.prompt.lower()
        is_jhankar = any(word in prompt for word in ("bollywood", "hindi", "jhankar", "sizzle"))

        for sample_idx in range(sample_count):
            t = sample_idx / self.SAMPLE_RATE
            if is_jhankar:
                # Jhankar sizzle - bright noise with high-freq tone
                noise = rng.uniform(-1.0, 1.0) * math.exp(-32 * t)
                tone = math.sin(2 * math.pi * 1200 * t) * math.exp(-25 * t)
                audio.append((noise * 0.6 + tone * 0.4) * 0.8)
            else:
                noise = rng.uniform(-0.8, 0.8) * math.exp(-24 * t)
                tone = math.sin(2 * math.pi * 660 * t) * math.exp(-18 * t)
                audio.append((tone * 0.35) + (noise * 0.25))
        return audio

    def _bass_808(self, event: NoteEvent, sample_count: int, spec: BeatSpec, index: int) -> array:
        freq = self._midi_to_hz(event.pitch)
        audio = array("f")
        prompt = spec.prompt.lower()
        is_soft = any(word in prompt for word in ("lofi", "acoustic", "chill", "jazz", "mellow"))
        is_desi = any(word in prompt for word in ("bollywood", "hindi", "desi", "tabla"))
        is_hindi_indie = self._is_hindi_indie(spec)

        for sample_idx in range(sample_count):
            t = sample_idx / self.SAMPLE_RATE
            if is_hindi_indie:
                attack = min(1.0, t / 0.03)
                env = attack * math.exp(-4.8 * t)
                wave_value = math.sin(2 * math.pi * freq * t)
                wave_value += 0.06 * math.sin(2 * math.pi * freq * 2 * t)
                audio.append(wave_value * env * 0.62)
            elif is_desi:
                # Tabla-style 808 slide (Bayan deep slide)
                attack = min(1.0, t / 0.02)
                env = attack * math.exp(-3.2 * t)
                # Fast initial pitch bend for the 'bayan' swipe effect
                bend = freq * (1.0 + 0.45 * math.exp(-12 * t))
                wave_value = math.sin(2 * math.pi * bend * t)
                # Dayan-style higher harmonic ring at start
                wave_value += 0.15 * math.sin(2 * math.pi * bend * 4.5 * t) * math.exp(-35 * t)
                audio.append(math.tanh(wave_value * env * 1.5))
            elif is_soft:
                # Warm upright/muted bass — slow attack, gentle decay, no pitch bend
                attack = min(1.0, t / 0.03)
                env = attack * math.exp(-4.5 * t)
                wave_value = math.sin(2 * math.pi * freq * t)
                # Triangle harmonic for warmth
                wave_value += 0.08 * math.sin(2 * math.pi * freq * 2 * t)
                audio.append(wave_value * env * 0.7)
            else:
                # Punchy 808 with pitch bend
                attack = min(1.0, t / 0.015)
                env = attack * math.exp(-2.8 * t)
                bend = freq * (1.0 + 0.18 * math.exp(-8 * t))
                wave_value = math.sin(2 * math.pi * bend * t)
                wave_value += 0.12 * math.sin(2 * math.pi * bend * 2 * t)
                audio.append(math.tanh(wave_value * env * 1.7))
        return audio

    def _poly_synth(self, event: NoteEvent, sample_count: int, spec: BeatSpec, index: int) -> array:
        freq = self._midi_to_hz(event.pitch)
        audio = array("f")
        
        preset = None
        if spec.synth_presets and "chords" in spec.synth_presets:
            preset = spec.synth_presets["chords"]

        # Default fallback if no preset is provided
        if not preset:
            preset = {"wave": "sine", "attack": 0.05, "decay": 0.2, "sustain": 0.55, "release": 0.3, "tremolo": 0.0, "harmonics": 2, "detune": 0.005, "brightness": 0.5}

        for sample_idx in range(sample_count):
            t = sample_idx / self.SAMPLE_RATE
            
            env = self._adsr(t, sample_count / self.SAMPLE_RATE, preset["attack"], preset["decay"], preset["sustain"], preset["release"])
            
            # Tremolo
            vib = 1.0
            if preset.get("tremolo", 0.0) > 0:
                vib = 1.0 - (preset["tremolo"] * math.sin(2 * math.pi * 4.0 * t))
                
            # Waveform generation
            wave_type = preset.get("wave", "sine")
            if wave_type == "sine":
                fundamental = math.sin(2 * math.pi * freq * t)
            elif wave_type == "square":
                val = math.sin(2 * math.pi * freq * t)
                fundamental = 0.6 if val >= 0 else -0.6
            elif wave_type == "saw":
                fundamental = 2.0 * ((freq * t) % 1.0) - 1.0
            elif wave_type == "triangle":
                fundamental = math.asin(math.sin(2 * math.pi * freq * t)) * (2.0 / math.pi)
            else:
                fundamental = math.sin(2 * math.pi * freq * t)
                
            # Harmonics
            harmonics = 0.0
            num_harmonics = preset.get("harmonics", 0)
            brightness = preset.get("brightness", 0.5)
            if num_harmonics > 0:
                for i in range(2, 2 + num_harmonics):
                    harmonics += (math.sin(2 * math.pi * freq * i * t) / (i * (2.0 - brightness))) * math.exp(-5 * t)
                    
            # Detune
            detune = 0.0
            detune_amt = preset.get("detune", 0.0)
            if detune_amt > 0:
                detune1 = math.sin(2 * math.pi * (freq * (1.0 - detune_amt)) * t)
                detune2 = math.sin(2 * math.pi * (freq * (1.0 + detune_amt)) * t)
                detune = (detune1 + detune2) * 0.25
                
            sample = (fundamental * 0.6 + harmonics * 0.2 + detune) * env * vib * 0.7
            audio.append(sample)
            
        return audio

    def _lead(self, event: NoteEvent, sample_count: int, spec: BeatSpec, index: int) -> array:
        freq = self._midi_to_hz(event.pitch)
        audio = array("f")
        
        preset = None
        if spec.synth_presets and "lead" in spec.synth_presets:
            preset = spec.synth_presets["lead"]

        # Default fallback if no preset is provided
        if not preset:
            preset = {"wave": "sine", "attack": 0.01, "decay": 0.10, "sustain": 0.48, "release": 0.14, "tremolo": 0.0, "harmonics": 1, "detune": 0.0, "brightness": 0.5}

        for sample_idx in range(sample_count):
            t = sample_idx / self.SAMPLE_RATE
            
            env = self._adsr(t, sample_count / self.SAMPLE_RATE, preset["attack"], preset["decay"], preset["sustain"], preset["release"])
            
            # Tremolo/Vibrato
            vib = 1.0
            if preset.get("tremolo", 0.0) > 0:
                vib = 1.0 + (preset["tremolo"] * math.sin(2 * math.pi * 5.5 * t))
                
            # Waveform generation
            wave_type = preset.get("wave", "sine")
            if wave_type == "sine":
                fundamental = math.sin(2 * math.pi * freq * vib * t)
            elif wave_type == "square":
                val = math.sin(2 * math.pi * freq * vib * t)
                fundamental = 0.6 if val >= 0 else -0.6
            elif wave_type == "saw":
                fundamental = 2.0 * ((freq * vib * t) % 1.0) - 1.0
            elif wave_type == "triangle":
                fundamental = math.asin(math.sin(2 * math.pi * freq * vib * t)) * (2.0 / math.pi)
            else:
                fundamental = math.sin(2 * math.pi * freq * vib * t)
                
            # Harmonics
            harmonics = 0.0
            num_harmonics = preset.get("harmonics", 0)
            brightness = preset.get("brightness", 0.5)
            if num_harmonics > 0:
                for i in range(2, 2 + num_harmonics):
                    harmonics += (math.sin(2 * math.pi * freq * vib * i * t) / (i * (2.0 - brightness))) * math.exp(-10 * t)
                    
            # Detune
            detune = 0.0
            detune_amt = preset.get("detune", 0.0)
            if detune_amt > 0:
                detune1 = math.sin(2 * math.pi * (freq * vib * (1.0 - detune_amt)) * t)
                detune2 = math.sin(2 * math.pi * (freq * vib * (1.0 + detune_amt)) * t)
                detune = (detune1 + detune2) * 0.25
                
            sample = (fundamental * 0.5 + harmonics * 0.3 + detune) * env * 0.8
            audio.append(sample)
            
        return audio

    def _normalize(self, audio: array, ceiling: float) -> None:
        peak = max((abs(sample) for sample in audio), default=0.0)
        if peak <= 0:
            return
        scale = min(1.0, ceiling / peak)
        if scale == 1.0:
            return
        for idx, sample in enumerate(audio):
            audio[idx] = sample * scale

    def _adsr(
        self,
        t: float,
        total_duration: float,
        attack: float,
        decay: float,
        sustain: float,
        release: float,
    ) -> float:
        release_start = max(attack + decay, total_duration - release)
        if t < attack:
            return t / attack if attack else 1.0
        if t < attack + decay:
            progress = (t - attack) / decay if decay else 1.0
            return 1.0 - progress * (1.0 - sustain)
        if t < release_start:
            return sustain
        if t >= total_duration:
            return 0.0
        progress = (t - release_start) / max(release, 0.001)
        return sustain * max(0.0, 1.0 - progress)

    def _midi_to_hz(self, midi_note: int) -> float:
        return 440.0 * (2 ** ((midi_note - 69) / 12))

    def _is_hindi_indie(self, spec: BeatSpec) -> bool:
        prompt = spec.prompt.lower()
        return spec.genre == "hindi_indie" or any(cue in prompt for cue in self.HINDI_INDIE_CUES)

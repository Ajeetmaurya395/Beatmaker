from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass

from core.beat_spec import BeatSpec, Section
from core.reference_analyzer import ReferenceProfile
from core.taste_profile import TasteProfileManager


@dataclass(frozen=True)
class GenrePreset:
    genre: str
    bpm_range: tuple[int, int]
    swing: float
    sections: tuple[tuple[str, int, float], ...]


class PromptEngineer:
    ROOT_NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    STEMS = ("kick", "snare", "hats", "perc", "bass_808", "chords", "lead")

    GENRE_PRESETS = (
        (("trap", "808", "metro", "future", "dark trap"), GenrePreset(
            genre="trap",
            bpm_range=(130, 150),
            swing=0.08,
            sections=(
                ("intro", 4, 0.45),
                ("hook", 8, 0.90),
                ("verse", 8, 0.72),
                ("hook", 8, 0.95),
                ("outro", 4, 0.35),
            ),
        )),
        (("drill", "uk drill", "ny drill"), GenrePreset(
            genre="drill",
            bpm_range=(138, 146),
            swing=0.11,
            sections=(
                ("intro", 4, 0.48),
                ("hook", 8, 0.92),
                ("verse", 8, 0.75),
                ("hook", 8, 0.98),
                ("outro", 4, 0.38),
            ),
        )),
        (("boom bap", "boombap", "grimy", "sampled"), GenrePreset(
            genre="boom_bap",
            bpm_range=(84, 96),
            swing=0.18,
            sections=(
                ("intro", 4, 0.45),
                ("loop", 8, 0.80),
                ("verse", 8, 0.75),
                ("hook", 8, 0.88),
                ("outro", 4, 0.35),
            ),
        )),
        (("lofi", "lo-fi", "chillhop", "jazzy"), GenrePreset(
            genre="lofi",
            bpm_range=(70, 88),
            swing=0.14,
            sections=(
                ("intro", 4, 0.35),
                ("loop", 8, 0.55),
                ("variation", 8, 0.65),
                ("loop", 8, 0.58),
                ("outro", 4, 0.30),
            ),
        )),
        (("acoustic", "unplugged", "guitar", "folk"), GenrePreset(
            genre="lofi",
            bpm_range=(75, 100),
            swing=0.12,
            sections=(
                ("intro", 4, 0.30),
                ("verse", 8, 0.50),
                ("hook", 8, 0.65),
                ("verse", 8, 0.55),
                ("outro", 4, 0.25),
            ),
        )),
        (("phonk", "drift", "cowbell"), GenrePreset(
            genre="phonk",
            bpm_range=(136, 154),
            swing=0.07,
            sections=(
                ("intro", 4, 0.42),
                ("drop", 8, 0.94),
                ("variation", 8, 0.86),
                ("drop", 8, 1.00),
                ("outro", 4, 0.40),
            ),
        )),
        (("house", "afro house", "tech house", "garage"), GenrePreset(
            genre="house",
            bpm_range=(120, 130),
            swing=0.04,
            sections=(
                ("intro", 8, 0.40),
                ("groove", 8, 0.72),
                ("drop", 8, 0.92),
                ("break", 8, 0.55),
                ("drop", 8, 0.96),
                ("outro", 8, 0.32),
            ),
        )),
    )

    def build_spec(
        self,
        prompt: str,
        bpm_override: int | None = None,
        seed: int | None = None,
        total_bars_override: int | None = None,
        structure_override: str | None = None,
        reference_profile: ReferenceProfile | None = None,
        taste_profile: TasteProfileManager | None = None,
    ) -> BeatSpec:
        prompt_lower = prompt.lower()
        stable_seed = seed if seed is not None else self._seed_from_prompt(prompt)
        rng = random.Random(stable_seed)

        preset = self._detect_genre(prompt_lower, reference_profile, taste_profile, rng)
        bpm = (
            bpm_override
            or self._extract_bpm(prompt_lower)
            or (reference_profile.bpm if reference_profile else None)
            or (taste_profile.preferred_bpm(rng) if taste_profile else None)
            or rng.randint(*preset.bpm_range)
        )
        key_root, scale = self._extract_key(prompt_lower, rng, reference_profile, taste_profile)
        sections = self._resolve_sections(
            preset=preset,
            total_bars_override=total_bars_override,
            structure_override=structure_override,
            reference_profile=reference_profile,
            taste_profile=taste_profile,
            rng=rng,
        )
        learned_summary = self._learned_summary(taste_profile, preset.genre)

        return BeatSpec(
            prompt=prompt.strip(),
            genre=preset.genre,
            bpm=bpm,
            key_root=key_root,
            scale=scale,
            swing=preset.swing,
            seed=stable_seed,
            stems=list(self.STEMS),
            sections=sections,
            reference_summary=reference_profile.summary if reference_profile else None,
            learned_summary=learned_summary,
        )

    def _detect_genre(
        self,
        prompt: str,
        reference_profile: ReferenceProfile | None,
        taste_profile: TasteProfileManager | None,
        rng: random.Random,
    ) -> GenrePreset:
        for keywords, preset in self.GENRE_PRESETS:
            if any(keyword in prompt for keyword in keywords):
                return preset
        if reference_profile:
            for keywords, preset in self.GENRE_PRESETS:
                if reference_profile.genre_hint == preset.genre:
                    return preset
        if taste_profile:
            preferred = taste_profile.preferred_genre(rng)
            if preferred:
                for keywords, preset in self.GENRE_PRESETS:
                    if preferred == preset.genre:
                        return preset
        return GenrePreset(
            genre="trap",
            bpm_range=(128, 145),
            swing=0.08,
            sections=(
                ("intro", 4, 0.40),
                ("hook", 8, 0.88),
                ("verse", 8, 0.72),
                ("hook", 8, 0.94),
                ("outro", 4, 0.35),
            ),
        )

    def _extract_bpm(self, prompt: str) -> int | None:
        # Match '90 bpm', '90bpm'
        match = re.search(r"\b(\d{2,3})\s*bpm\b", prompt)
        if match:
            bpm = int(match.group(1))
            return bpm if 55 <= bpm <= 180 else None
        # Match 'tempo around 90', 'tempo of 120', 'at 140'
        match = re.search(r"(?:tempo|bpm|at)\s+(?:around|of|~)?\s*(\d{2,3})\b", prompt)
        if match:
            bpm = int(match.group(1))
            return bpm if 55 <= bpm <= 180 else None
        # Match 'around 90 bpm' or just a standalone number near 'bpm'
        match = re.search(r"(?:around|about|~)\s*(\d{2,3})\b", prompt)
        if match:
            bpm = int(match.group(1))
            return bpm if 55 <= bpm <= 180 else None
        return None

    def _extract_key(
        self,
        prompt: str,
        rng: random.Random,
        reference_profile: ReferenceProfile | None,
        taste_profile: TasteProfileManager | None,
    ) -> tuple[str, str]:
        compact_match = re.search(r"\b([a-gA-G])([#b]?)(maj|major|min|minor|m)\b", prompt)
        spaced_match = re.search(r"\b([a-gA-G])([#b]?)\s+(major|minor|maj|min)\b", prompt)

        match = compact_match or spaced_match
        if match:
            root = match.group(1).upper() + match.group(2).lower()
            mode = match.group(3).lower()
            return self._normalize_root(root), "major" if mode.startswith("maj") else "minor"

        if reference_profile:
            return reference_profile.key_root, reference_profile.scale

        if taste_profile:
            preferred = taste_profile.preferred_key(rng)
            if preferred:
                return preferred

        scale = "minor" if any(word in prompt for word in ("dark", "moody", "sad", "grim", "night")) else "major"
        return rng.choice(self.ROOT_NOTES), scale

    def _resolve_sections(
        self,
        preset: GenrePreset,
        total_bars_override: int | None,
        structure_override: str | None,
        reference_profile: ReferenceProfile | None,
        taste_profile: TasteProfileManager | None,
        rng: random.Random,
    ) -> list[Section]:
        if structure_override:
            return self._parse_structure(structure_override)

        if taste_profile:
            learned = taste_profile.preferred_structure(preset.genre, rng)
            if learned:
                sections = self._parse_structure(learned.replace("|", ","))
                return self._resize_sections(sections, total_bars_override) if total_bars_override else sections

        sections = [Section(name=name, bars=bars, energy=energy) for name, bars, energy in preset.sections]
        if reference_profile:
            sections = [
                Section(
                    name=section.name,
                    bars=section.bars,
                    energy=max(0.2, min(1.0, (section.energy * 0.7) + (reference_profile.energy * 0.3))),
                )
                for section in sections
            ]
        if total_bars_override:
            return self._resize_sections(sections, total_bars_override)
        return sections

    def _parse_structure(self, structure: str) -> list[Section]:
        sections: list[Section] = []
        chunks = [chunk.strip() for chunk in structure.split(",") if chunk.strip()]
        if not chunks:
            raise ValueError("Structure override was provided but empty.")
        for index, chunk in enumerate(chunks):
            if ":" not in chunk:
                raise ValueError(f"Invalid structure segment '{chunk}'. Use name:bars format.")
            name, raw_bars = [part.strip() for part in chunk.split(":", 1)]
            bars = int(raw_bars)
            if bars <= 0:
                raise ValueError("Each structure section must have at least 1 bar.")
            default_energy = {
                "intro": 0.4,
                "hook": 0.92,
                "chorus": 0.92,
                "verse": 0.72,
                "drop": 0.97,
                "break": 0.50,
                "loop": 0.68,
                "variation": 0.76,
                "outro": 0.34,
            }.get(name.lower(), 0.62 + min(0.18, index * 0.03))
            sections.append(Section(name=name.lower(), bars=bars, energy=default_energy))
        return sections

    def _resize_sections(self, sections: list[Section], total_bars: int) -> list[Section]:
        if total_bars <= 0:
            raise ValueError("Bar override must be greater than 0.")
        current_total = sum(section.bars for section in sections)
        if current_total == total_bars:
            return sections
        raw_sizes = [(section.bars / current_total) * total_bars for section in sections]
        resized = [max(1, int(size)) for size in raw_sizes]

        while sum(resized) < total_bars:
            idx = max(range(len(sections)), key=lambda i: raw_sizes[i] - resized[i])
            resized[idx] += 1
        while sum(resized) > total_bars:
            idx = max(range(len(sections)), key=lambda i: resized[i] - raw_sizes[i])
            if resized[idx] > 1:
                resized[idx] -= 1
            else:
                break

        return [
            Section(name=section.name, bars=bars, energy=section.energy)
            for section, bars in zip(sections, resized)
        ]

    def _learned_summary(self, taste_profile: TasteProfileManager | None, genre: str) -> str | None:
        if not taste_profile:
            return None
        summary = taste_profile.summary()
        return f"{summary}, active_genre={genre}"

    def _normalize_root(self, value: str) -> str:
        normalized = value[0].upper() + value[1:].lower()
        flat_map = {
            "Db": "C#",
            "Eb": "D#",
            "Gb": "F#",
            "Ab": "G#",
            "Bb": "A#",
        }
        return flat_map.get(normalized, normalized)

    def _seed_from_prompt(self, prompt: str) -> int:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]
        return int(digest, 16)

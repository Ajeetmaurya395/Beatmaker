from __future__ import annotations

import random
from dataclasses import dataclass

from core.beat_spec import BeatSpec, NoteEvent
from core.pattern_utils import drum_steps_from_pattern
from core.taste_profile import TasteProfileManager


@dataclass(frozen=True)
class SectionMarker:
    name: str
    start_bar: int
    bars: int
    energy: float


class ArrangementBuilder:
    STEM_SEED_BASES = {
        "kick": 101,
        "snare": 211,
        "hats": 307,
        "perc": 401,
        "bass_808": 503,
        "chords": 601,
        "lead": 701,
    }

    ROOT_TO_SEMITONE = {
        "C": 0,
        "C#": 1,
        "D": 2,
        "D#": 3,
        "E": 4,
        "F": 5,
        "F#": 6,
        "G": 7,
        "G#": 8,
        "A": 9,
        "A#": 10,
        "B": 11,
    }

    DRUM_PITCHES = {
        "kick": 36,
        "snare": 38,
        "hats_closed": 42,
        "hats_open": 46,
        "perc": 39,
    }

    SCALE_INTERVALS = {
        "major": [0, 2, 4, 5, 7, 9, 11],
        "minor": [0, 2, 3, 5, 7, 8, 10],
    }

    PROGRESSIONS = {
        "major": ([0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 4, 3]),
        "minor": ([0, 5, 3, 4], [0, 3, 5, 4], [0, 4, 3, 5]),
    }

    def build(
        self,
        spec: BeatSpec,
        taste_profile: TasteProfileManager | None = None,
        stem_seed_overrides: dict[str, int] | None = None,
        humanize_amounts: dict[str, float] | None = None,
    ) -> tuple[dict[str, list[NoteEvent]], list[SectionMarker]]:
        markers: list[SectionMarker] = []
        events: dict[str, list[NoteEvent]] = {stem: [] for stem in spec.stems}
        stem_seed_overrides = stem_seed_overrides or {}
        humanize_amounts = humanize_amounts or {}

        start_bar = 0
        for section_index, section in enumerate(spec.sections):
            markers.append(
                SectionMarker(
                    name=section.name,
                    start_bar=start_bar,
                    bars=section.bars,
                    energy=section.energy,
                )
            )
            for bar_offset in range(section.bars):
                bar_number = start_bar + bar_offset
                section_seed = spec.seed + (section_index * 997) + bar_offset
                kick_rng = self._stem_rng(section_seed, "kick", stem_seed_overrides)
                snare_rng = self._stem_rng(section_seed, "snare", stem_seed_overrides)
                hats_rng = self._stem_rng(section_seed, "hats", stem_seed_overrides)
                perc_rng = self._stem_rng(section_seed, "perc", stem_seed_overrides)
                bass_rng = self._stem_rng(section_seed, "bass_808", stem_seed_overrides)
                chord_rng = self._stem_rng(section_seed, "chords", stem_seed_overrides)
                lead_rng = self._stem_rng(section_seed, "lead", stem_seed_overrides)
                chord_degree = self._progression_degree(spec, section_index, bar_offset)
                self._add_drum_bar(
                    events,
                    spec,
                    section.energy,
                    bar_number,
                    kick_rng,
                    snare_rng,
                    hats_rng,
                    perc_rng,
                    taste_profile,
                )
                self._add_bass_bar(events, spec, section.energy, chord_degree, bar_number, bass_rng)
                self._add_chord_bar(events, spec, section.energy, chord_degree, bar_number, chord_rng)
                self._add_lead_bar(events, spec, section.energy, chord_degree, bar_number, lead_rng)
            start_bar += section.bars

        for stem_events in events.values():
            stem_events.sort(key=lambda event: (event.start_beat, event.pitch))
        self._apply_humanize(events, spec, humanize_amounts)

        return events, markers

    def _add_drum_bar(
        self,
        events: dict[str, list[NoteEvent]],
        spec: BeatSpec,
        energy: float,
        bar_number: int,
        kick_rng: random.Random,
        snare_rng: random.Random,
        hats_rng: random.Random,
        perc_rng: random.Random,
        taste_profile: TasteProfileManager | None,
    ) -> None:
        base = bar_number * 4
        kick_steps = self._kick_pattern(spec.genre, energy, kick_rng, taste_profile)
        snare_steps = self._snare_pattern(spec.genre, energy, snare_rng, taste_profile)
        hat_steps = self._hat_pattern(spec.genre, energy, hats_rng, taste_profile)
        perc_steps = self._perc_pattern(spec.genre, energy, perc_rng, taste_profile)

        for step in kick_steps:
            events["kick"].append(
                NoteEvent(
                    pitch=self.DRUM_PITCHES["kick"],
                    start_beat=base + self._step_to_beat(step, spec.swing),
                    duration_beats=0.25,
                    velocity=112 if step in (0, 8) else 96,
                )
            )

        for step in snare_steps:
            events["snare"].append(
                NoteEvent(
                    pitch=self.DRUM_PITCHES["snare"],
                    start_beat=base + self._step_to_beat(step, spec.swing),
                    duration_beats=0.25,
                    velocity=114,
                )
            )

        for step, is_open in hat_steps:
            events["hats"].append(
                NoteEvent(
                    pitch=self.DRUM_PITCHES["hats_open" if is_open else "hats_closed"],
                    start_beat=base + self._step_to_beat(step, spec.swing),
                    duration_beats=0.5 if is_open else 0.125,
                    velocity=72 if is_open else 64 + (step % 4) * 4,
                )
            )

        for step in perc_steps:
            events["perc"].append(
                NoteEvent(
                    pitch=self.DRUM_PITCHES["perc"],
                    start_beat=base + self._step_to_beat(step, spec.swing),
                    duration_beats=0.25,
                    velocity=68 + int(energy * 28),
                )
            )

    def _add_bass_bar(
        self,
        events: dict[str, list[NoteEvent]],
        spec: BeatSpec,
        energy: float,
        chord_degree: int,
        bar_number: int,
        rng: random.Random,
    ) -> None:
        root = self._scale_note(spec, chord_degree, octave=2)
        fifth = self._scale_note(spec, chord_degree + 4, octave=2)
        base = bar_number * 4

        if spec.genre in {"house"}:
            patterns = [
                [
                    (0.0, 0.75, root),
                    (1.0, 0.75, fifth),
                    (2.0, 0.75, root),
                    (3.0, 0.75, fifth),
                ],
                [
                    (0.0, 0.5, root),
                    (1.0, 0.75, fifth),
                    (2.0, 0.5, root),
                    (2.75, 0.75, fifth),
                ],
            ]
            pattern = rng.choice(patterns)
        else:
            patterns = [
                [
                    (0.0, 1.25, root),
                    (1.5, 0.5, fifth if energy > 0.7 else root),
                    (2.0, 0.9, root),
                    (3.25, 0.5, root + 12 if spec.genre == "phonk" and energy > 0.85 else fifth),
                ]
            ]
            if spec.genre == "boom_bap":
                patterns = [[(0.0, 1.5, root), (2.0, 1.5, fifth)]]
            else:
                patterns.append(
                    [
                        (0.0, 1.0, root),
                        (1.0, 0.5, fifth),
                        (2.0, 1.0, root),
                        (3.0, 0.75, fifth),
                    ]
                )
                if spec.genre in {"trap", "phonk", "drill"}:
                    patterns.append(
                        [
                            (0.0, 1.0, root),
                            (1.75, 0.25, root + 12),
                            (2.0, 1.0, root),
                            (3.0, 0.75, fifth),
                        ]
                    )
            pattern = rng.choice(patterns)
        for start, duration, pitch in pattern:
            if energy < 0.45 and start > 2.5:
                continue
            if rng.random() < 0.08 and start not in {0.0, 2.0}:
                continue
            events["bass_808"].append(
                NoteEvent(
                    pitch=pitch,
                    start_beat=base + start,
                    duration_beats=duration,
                    velocity=92 + int(energy * 20),
                )
            )

    def _add_chord_bar(
        self,
        events: dict[str, list[NoteEvent]],
        spec: BeatSpec,
        energy: float,
        chord_degree: int,
        bar_number: int,
        rng: random.Random,
    ) -> None:
        base = bar_number * 4
        octave = 4 + (1 if spec.genre in {"phonk"} and rng.random() < 0.2 else 0)
        chord = list(self._triad(spec, chord_degree, octave=octave))
        inversion = rng.choice([0, 0, 1, 2])
        for _ in range(inversion):
            moved = chord.pop(0)
            chord.append(moved + 12)
        if spec.genre == "house":
            starts = rng.choice([(0.0, 2.0), (0.0, 1.5, 3.0)])
            duration = 1.75
        elif spec.genre == "lofi":
            starts = rng.choice([(0.0,), (0.0, 2.0)])
            duration = 3.8
        else:
            starts = rng.choice([(0.0,), (0.0, 2.0)])
            duration = 3.5 if energy < 0.8 else 2.75

        for start in starts:
            for pitch in chord:
                events["chords"].append(
                    NoteEvent(
                        pitch=pitch,
                        start_beat=base + start,
                        duration_beats=duration,
                        velocity=54 + int(energy * 20),
                    )
                )

    def _add_lead_bar(
        self,
        events: dict[str, list[NoteEvent]],
        spec: BeatSpec,
        energy: float,
        chord_degree: int,
        bar_number: int,
        rng: random.Random,
    ) -> None:
        if energy < 0.45 and spec.genre not in {"lofi"}:
            return

        base = bar_number * 4
        scale_pool = [self._scale_note(spec, chord_degree + offset, octave=5) for offset in (0, 2, 4, 6)]
        rhythm = {
            "trap": [0.5, 1.25, 2.0, 3.0],
            "drill": [0.75, 1.5, 2.5, 3.25],
            "boom_bap": [1.0, 2.25, 3.0],
            "lofi": [0.0, 1.5, 3.0],
            "phonk": [0.25, 1.0, 2.0, 2.75, 3.5],
            "house": [0.0, 0.75, 1.5, 2.25, 3.0],
        }.get(spec.genre, [0.5, 1.5, 2.5, 3.0])

        for idx, start in enumerate(rhythm):
            if idx > 1 and energy < 0.6 and rng.random() < 0.4:
                continue
            pitch = scale_pool[(idx + bar_number) % len(scale_pool)]
            if spec.genre == "phonk" and idx % 2 == 1:
                pitch += 12
            events["lead"].append(
                NoteEvent(
                    pitch=pitch,
                    start_beat=base + start,
                    duration_beats=0.4 if spec.genre in {"trap", "drill", "phonk"} else 0.75,
                    velocity=58 + int(energy * 26),
                )
            )

    def _kick_pattern(
        self,
        genre: str,
        energy: float,
        rng: random.Random,
        taste_profile: TasteProfileManager | None,
    ) -> list[int]:
        learned = self._drum_pattern_from_profile("kick", genre, rng, taste_profile)
        if learned:
            return self._mutate_steps(learned, energy, rng)
        base = {
            "trap": [0, 7, 10, 12],
            "drill": [0, 6, 9, 12],
            "boom_bap": [0, 5, 8, 11],
            "lofi": [0, 6, 10],
            "phonk": [0, 4, 8, 10, 12],
            "house": [0, 4, 8, 12],
        }.get(genre, [0, 7, 10, 12])
        steps = list(base)
        if energy > 0.78:
            extra = rng.choice([3, 14, 15])
            if extra not in steps:
                steps.append(extra)
        return sorted(steps)

    def _snare_pattern(
        self,
        genre: str,
        energy: float,
        rng: random.Random,
        taste_profile: TasteProfileManager | None,
    ) -> list[int]:
        learned = self._drum_pattern_from_profile("snare", genre, rng, taste_profile)
        if learned:
            return self._mutate_steps(learned, energy, rng, keep_backbeat=True)
        steps = [4, 12]
        if genre == "phonk":
            steps = [4, 10, 12]
        elif genre == "drill" and energy > 0.82:
            steps = [4, 11, 12]
        if genre == "boom_bap" and rng.random() > 0.5:
            steps.append(15)
        return steps

    def _hat_pattern(
        self,
        genre: str,
        energy: float,
        rng: random.Random,
        taste_profile: TasteProfileManager | None,
    ) -> list[tuple[int, bool]]:
        learned = self._hat_pattern_from_profile(genre, rng, taste_profile)
        if learned:
            return self._mutate_hats(learned, energy, rng)
        if genre in {"trap", "drill", "phonk"}:
            steps = [(step, False) for step in range(0, 16, 2)]
            for roll_start in (6, 14):
                if energy > 0.7 or rng.random() > 0.5:
                    steps.extend([(roll_start, False), (roll_start + 1, False)])
            if energy > 0.82:
                steps.append((11, True))
            return sorted(set(steps))
        if genre == "house":
            return [(step, False) for step in range(2, 16, 2)] + [(15, True)]
        return [(step, False) for step in range(0, 16, 4)] + [(10, True)]

    def _perc_pattern(
        self,
        genre: str,
        energy: float,
        rng: random.Random,
        taste_profile: TasteProfileManager | None,
    ) -> list[int]:
        learned = self._drum_pattern_from_profile("perc", genre, rng, taste_profile)
        if learned:
            return self._mutate_steps(learned, energy, rng)
        choices = {
            "trap": [3, 11, 15],
            "drill": [2, 7, 13],
            "boom_bap": [7, 15],
            "lofi": [6, 14],
            "phonk": [3, 7, 11, 15],
            "house": [6, 10, 14],
        }.get(genre, [7, 15])
        steps = [step for step in choices if energy > 0.6 or step < 12]
        if energy > 0.88 and rng.random() > 0.4:
            steps.append(rng.choice([1, 5, 9, 13]))
        return sorted(set(steps))

    def _progression_degree(self, spec: BeatSpec, section_index: int, bar_offset: int) -> int:
        progression = self.PROGRESSIONS[spec.scale][section_index % len(self.PROGRESSIONS[spec.scale])]
        return progression[bar_offset % len(progression)]

    def _triad(self, spec: BeatSpec, degree: int, octave: int) -> tuple[int, int, int]:
        return (
            self._scale_note(spec, degree, octave),
            self._scale_note(spec, degree + 2, octave),
            self._scale_note(spec, degree + 4, octave),
        )

    def _scale_note(self, spec: BeatSpec, degree: int, octave: int) -> int:
        intervals = self.SCALE_INTERVALS[spec.scale]
        root = 12 * (octave + 1) + self.ROOT_TO_SEMITONE[spec.key_root]
        octave_offset, scale_index = divmod(degree, len(intervals))
        return root + intervals[scale_index] + (12 * octave_offset)

    def _step_to_beat(self, step: int, swing: float) -> float:
        beat = step / 4
        if step % 2 == 1:
            beat += swing * 0.25
        return beat

    def _stem_rng(
        self,
        base_seed: int,
        stem: str,
        stem_seed_overrides: dict[str, int],
    ) -> random.Random:
        offset = self.STEM_SEED_BASES.get(stem, 0) + stem_seed_overrides.get(stem, 0)
        return random.Random(base_seed + offset)

    def _drum_pattern_from_profile(
        self,
        stem: str,
        genre: str,
        rng: random.Random,
        taste_profile: TasteProfileManager | None,
    ) -> list[int] | None:
        if not taste_profile:
            return None
        pattern = taste_profile.preferred_pattern(stem, genre, rng)
        if not pattern:
            return None
        parsed = drum_steps_from_pattern(pattern)
        return parsed if parsed else None

    def _hat_pattern_from_profile(
        self,
        genre: str,
        rng: random.Random,
        taste_profile: TasteProfileManager | None,
    ) -> list[tuple[int, bool]] | None:
        if not taste_profile:
            return None
        pattern = taste_profile.preferred_pattern("hats", genre, rng)
        if not pattern:
            return None
        parsed = drum_steps_from_pattern(pattern, hats=True)
        return parsed if parsed else None

    def _mutate_steps(
        self,
        steps: list[int],
        energy: float,
        rng: random.Random,
        keep_backbeat: bool = False,
    ) -> list[int]:
        mutated = sorted(set(steps))
        if energy > 0.82 and rng.random() < 0.55:
            mutated.append(rng.choice([1, 3, 6, 9, 14, 15]))
        if energy < 0.45 and len(mutated) > 2:
            removable = [step for step in mutated if not keep_backbeat or step not in {4, 12}]
            if removable:
                mutated.remove(rng.choice(removable))
        return sorted(set(mutated))

    def _mutate_hats(
        self,
        steps: list[tuple[int, bool]],
        energy: float,
        rng: random.Random,
    ) -> list[tuple[int, bool]]:
        mutated = list(dict.fromkeys(steps))
        if energy > 0.8 and rng.random() < 0.45:
            mutated.extend([(rng.choice([5, 6, 13, 14]), False), (rng.choice([7, 15]), False)])
        return sorted(set(mutated))

    def _apply_humanize(
        self,
        events: dict[str, list[NoteEvent]],
        spec: BeatSpec,
        humanize_amounts: dict[str, float],
    ) -> None:
        for stem, amount in humanize_amounts.items():
            if amount <= 0 or stem not in events:
                continue
            rng = random.Random(spec.seed + self.STEM_SEED_BASES.get(stem, 0) + 999)
            adjusted: list[NoteEvent] = []
            for event in events[stem]:
                offset = (rng.random() - 0.5) * amount
                velocity_shift = round((rng.random() - 0.5) * (18 * amount * 10))
                new_start = max(0.0, event.start_beat + offset)
                new_duration = max(0.05, event.duration_beats * (1.0 + ((rng.random() - 0.5) * amount)))
                new_velocity = max(1, min(127, event.velocity + velocity_shift))
                adjusted.append(
                    NoteEvent(
                        pitch=event.pitch,
                        start_beat=new_start,
                        duration_beats=new_duration,
                        velocity=new_velocity,
                    )
                )
            adjusted.sort(key=lambda event: (event.start_beat, event.pitch))
            events[stem] = adjusted

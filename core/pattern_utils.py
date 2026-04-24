from __future__ import annotations

from collections import Counter, defaultdict

from core.beat_spec import BeatSpec, NoteEvent, Section


def structure_signature(sections: list[Section]) -> str:
    return "|".join(f"{section.name}:{section.bars}" for section in sections)


def summarize_patterns(spec: BeatSpec, events_by_stem: dict[str, list[NoteEvent]]) -> dict[str, dict[str, int]]:
    summaries: dict[str, dict[str, int]] = {}
    for stem, events in events_by_stem.items():
        grouped: dict[int, list[str]] = defaultdict(list)
        for event in events:
            bar = int(event.start_beat // 4)
            beat_in_bar = event.start_beat - (bar * 4)
            grouped[bar].append(_token_for_event(stem, beat_in_bar, event.duration_beats, event.pitch))

        counts = Counter()
        for bar in range(spec.total_bars):
            tokens = sorted(grouped.get(bar, []))
            pattern = ",".join(tokens) if tokens else "_"
            counts[pattern] += 1
        summaries[stem] = dict(counts)
    return summaries


def drum_steps_from_pattern(pattern: str, hats: bool = False) -> list[int] | list[tuple[int, bool]]:
    if not pattern or pattern == "_":
        return [] if not hats else []
    tokens = [token.strip() for token in pattern.split(",") if token.strip()]
    if hats:
        parsed: list[tuple[int, bool]] = []
        for token in tokens:
            if token.endswith("o") or token.endswith("c"):
                parsed.append((int(token[:-1]), token.endswith("o")))
        return parsed
    return [int(token) for token in tokens if token.isdigit()]


def _token_for_event(stem: str, beat_in_bar: float, duration: float, pitch: int) -> str:
    if stem in {"kick", "snare", "perc"}:
        return str(int(round(beat_in_bar * 4)))
    if stem == "hats":
        step = int(round(beat_in_bar * 4))
        suffix = "o" if pitch == 46 else "c"
        return f"{step}{suffix}"
    start = round(beat_in_bar, 2)
    dur = round(duration, 2)
    return f"{start:.2f}/{dur:.2f}"

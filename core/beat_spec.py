from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Section:
    name: str
    bars: int
    energy: float


@dataclass(frozen=True)
class BeatSpec:
    prompt: str
    genre: str
    bpm: int
    key_root: str
    scale: str
    swing: float
    seed: int
    stems: list[str]
    sections: list[Section]
    reference_summary: str | None = None
    learned_summary: str | None = None
    synth_presets: dict[str, dict] | None = None

    @property
    def total_bars(self) -> int:
        return sum(section.bars for section in self.sections)

    @property
    def total_beats(self) -> int:
        return self.total_bars * 4

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BeatSpec":
        sections = [Section(**section) for section in data["sections"]]
        return cls(
            prompt=data["prompt"],
            genre=data["genre"],
            bpm=data["bpm"],
            key_root=data["key_root"],
            scale=data["scale"],
            swing=data["swing"],
            seed=data["seed"],
            stems=list(data["stems"]),
            sections=sections,
            reference_summary=data.get("reference_summary"),
            learned_summary=data.get("learned_summary"),
            synth_presets=data.get("synth_presets"),
        )


@dataclass(frozen=True)
class NoteEvent:
    pitch: int
    start_beat: float
    duration_beats: float
    velocity: int

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.duration_beats

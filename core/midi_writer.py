from __future__ import annotations

import struct
from pathlib import Path

from core.beat_spec import NoteEvent


class MidiWriter:
    TICKS_PER_BEAT = 480

    STEM_CHANNELS = {
        "kick": 9,
        "snare": 9,
        "hats": 9,
        "perc": 9,
        "bass_808": 0,
        "chords": 1,
        "lead": 2,
    }

    def write_stem(self, path: Path, stem: str, events: list[NoteEvent], bpm: int) -> None:
        track_data = bytearray()
        track_data.extend(self._meta_event(0, 0x03, stem.encode("utf-8")))
        track_data.extend(self._meta_event(0, 0x51, self._tempo_bytes(bpm)))
        track_data.extend(self._meta_event(0, 0x58, bytes([4, 2, 24, 8])))

        midi_events: list[tuple[int, int, bytes]] = []
        channel = self.STEM_CHANNELS.get(stem, 0)
        for event in events:
            start_tick = max(0, round(event.start_beat * self.TICKS_PER_BEAT))
            end_tick = max(start_tick + 1, round(event.end_beat * self.TICKS_PER_BEAT))
            note_on = bytes([0x90 | channel, event.pitch & 0x7F, event.velocity & 0x7F])
            note_off = bytes([0x80 | channel, event.pitch & 0x7F, 0x00])
            midi_events.append((start_tick, 1, note_on))
            midi_events.append((end_tick, 0, note_off))

        midi_events.sort(key=lambda item: (item[0], item[1], item[2]))

        last_tick = 0
        for tick, _priority, payload in midi_events:
            delta = tick - last_tick
            track_data.extend(self._varlen(delta))
            track_data.extend(payload)
            last_tick = tick

        track_data.extend(self._meta_event(0, 0x2F, b""))

        header = struct.pack(">4sLHHH", b"MThd", 6, 0, 1, self.TICKS_PER_BEAT)
        track_chunk = struct.pack(">4sL", b"MTrk", len(track_data)) + track_data
        path.write_bytes(header + track_chunk)

    def _tempo_bytes(self, bpm: int) -> bytes:
        microseconds_per_beat = round(60_000_000 / bpm)
        return microseconds_per_beat.to_bytes(3, "big")

    def _meta_event(self, delta: int, meta_type: int, data: bytes) -> bytes:
        return self._varlen(delta) + bytes([0xFF, meta_type]) + self._varlen(len(data)) + data

    def _varlen(self, value: int) -> bytes:
        buffer = value & 0x7F
        out = bytearray([buffer])
        value >>= 7
        while value:
            out.insert(0, (value & 0x7F) | 0x80)
            value >>= 7
        return bytes(out)

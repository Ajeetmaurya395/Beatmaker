from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.arrangement import SectionMarker
from core.audio_renderer import AudioRenderer
from core.beat_spec import BeatSpec, NoteEvent
from core.midi_writer import MidiWriter
from core.pattern_utils import structure_signature, summarize_patterns
from core.sample_pack import SamplePack


@dataclass(frozen=True)
class ExportBundle:
    bundle_dir: Path
    preview_mix_path: Path
    stem_audio_paths: list[Path]
    midi_paths: list[Path]
    manifest_path: Path
    reference_summary: str | None
    updated_stem: str | None = None


class ProjectExporter:
    def __init__(self, output_root: Path):
        self.output_root = output_root
        self.audio_renderer = AudioRenderer()
        self.midi_writer = MidiWriter()

    def export(
        self,
        spec: BeatSpec,
        events_by_stem: dict[str, list[NoteEvent]],
        markers: list[SectionMarker],
        sample_pack: SamplePack | None = None,
    ) -> ExportBundle:
        bundle_dir = self._bundle_dir(spec)
        stems_dir = bundle_dir / "stems"
        midi_dir = bundle_dir / "midi"
        stems_dir.mkdir(parents=True, exist_ok=True)
        midi_dir.mkdir(parents=True, exist_ok=True)

        stem_audio_paths: list[Path] = []
        midi_paths: list[Path] = []
        rendered_stems = {}
        pattern_summary = summarize_patterns(spec, events_by_stem)

        for stem in spec.stems:
            events = events_by_stem.get(stem, [])
            midi_path = midi_dir / f"{stem}.mid"
            self.midi_writer.write_stem(midi_path, stem, events, spec.bpm)
            midi_paths.append(midi_path)

            audio = self.audio_renderer.render_stem(stem, events, spec, sample_pack=sample_pack)
            rendered_stems[stem] = audio
            wav_path = stems_dir / f"{stem}.wav"
            self.audio_renderer.write_wav(wav_path, audio)
            stem_audio_paths.append(wav_path)

        preview_mix_path = bundle_dir / "preview_mix.wav"
        mix = self.audio_renderer.mix(rendered_stems)
        self.audio_renderer.write_wav(preview_mix_path, mix)

        markers_path = bundle_dir / "arrangement_markers.csv"
        markers_path.write_text(
            "name,start_bar,bars,energy\n"
            + "\n".join(
                f"{marker.name},{marker.start_bar},{marker.bars},{marker.energy:.2f}"
                for marker in markers
            )
            + "\n",
            encoding="utf-8",
        )

        readme_path = bundle_dir / "README.txt"
        readme_path.write_text(
            "\n".join(
                [
                    "FL Studio import guide",
                    "",
                    "1. Drag the WAV files from stems/ into the Playlist or Channel Rack.",
                    "2. Import matching MIDI files from midi/ if you want to swap sounds.",
                    "3. Use arrangement_markers.csv as a quick section reference.",
                    "4. preview_mix.wav is only a rough sketch mix for auditioning.",
                    f"5. Sample pack: {sample_pack.describe() if sample_pack else 'synth fallback'}",
                    f"6. Reference: {spec.reference_summary or 'none'}",
                    f"7. Learned profile: {spec.learned_summary or 'none'}",
                ]
            ),
            encoding="utf-8",
        )

        manifest_path = bundle_dir / "project.json"
        manifest = {
            "spec": spec.to_dict(),
            "markers": [
                {
                    "name": marker.name,
                    "start_bar": marker.start_bar,
                    "bars": marker.bars,
                    "energy": marker.energy,
                }
                for marker in markers
            ],
            "stems": {
                stem: {
                    "note_count": len(events_by_stem.get(stem, [])),
                    "wav": str((stems_dir / f"{stem}.wav").name),
                    "midi": str((midi_dir / f"{stem}.mid").name),
                }
                for stem in spec.stems
            },
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "render": {
                "sample_pack": sample_pack.describe() if sample_pack else None,
                "sample_pack_name": sample_pack.root.name if sample_pack else None,
                "sample_pack_path": str(sample_pack.root) if sample_pack else None,
                "reference_summary": spec.reference_summary,
                "learned_summary": spec.learned_summary,
            },
            "analysis": {
                "structure_signature": structure_signature(spec.sections),
                "pattern_summary": pattern_summary,
            },
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return ExportBundle(
            bundle_dir=bundle_dir,
            preview_mix_path=preview_mix_path,
            stem_audio_paths=stem_audio_paths,
            midi_paths=midi_paths,
            manifest_path=manifest_path,
            reference_summary=spec.reference_summary,
        )

    def update_bundle_stem(
        self,
        bundle_dir: Path,
        spec: BeatSpec,
        markers: list[SectionMarker],
        events_by_stem: dict[str, list[NoteEvent]],
        target_stem: str,
        sample_pack: SamplePack | None = None,
        variation: str | None = None,
    ) -> ExportBundle:
        bundle_dir = Path(bundle_dir)
        manifest_path = bundle_dir / "project.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        stems_dir = bundle_dir / "stems"
        midi_dir = bundle_dir / "midi"

        pattern_summary = manifest.setdefault("analysis", {}).setdefault("pattern_summary", {})
        pattern_summary.update(summarize_patterns(spec, {target_stem: events_by_stem.get(target_stem, [])}))

        midi_path = midi_dir / f"{target_stem}.mid"
        self.midi_writer.write_stem(midi_path, target_stem, events_by_stem.get(target_stem, []), spec.bpm)

        audio = self.audio_renderer.render_stem(
            target_stem,
            events_by_stem.get(target_stem, []),
            spec,
            sample_pack=sample_pack,
        )
        wav_path = stems_dir / f"{target_stem}.wav"
        self.audio_renderer.write_wav(wav_path, audio)

        stem_buffers = {}
        for stem in spec.stems:
            stem_path = stems_dir / f"{stem}.wav"
            stem_buffers[stem] = self.audio_renderer.read_wav(stem_path)
        mix = self.audio_renderer.mix(stem_buffers)
        preview_mix_path = bundle_dir / "preview_mix.wav"
        self.audio_renderer.write_wav(preview_mix_path, mix)

        markers_path = bundle_dir / "arrangement_markers.csv"
        markers_path.write_text(
            "name,start_bar,bars,energy\n"
            + "\n".join(
                f"{marker.name},{marker.start_bar},{marker.bars},{marker.energy:.2f}"
                for marker in markers
            )
            + "\n",
            encoding="utf-8",
        )

        manifest["spec"] = spec.to_dict()
        manifest["markers"] = [
            {
                "name": marker.name,
                "start_bar": marker.start_bar,
                "bars": marker.bars,
                "energy": marker.energy,
            }
            for marker in markers
        ]
        manifest["stems"][target_stem]["note_count"] = len(events_by_stem.get(target_stem, []))
        manifest["generated_at"] = datetime.now().isoformat(timespec="seconds")
        render = manifest.setdefault("render", {})
        render["sample_pack"] = sample_pack.describe() if sample_pack else render.get("sample_pack")
        render["sample_pack_name"] = sample_pack.root.name if sample_pack else render.get("sample_pack_name")
        render["sample_pack_path"] = str(sample_pack.root) if sample_pack else render.get("sample_pack_path")

        history = manifest.setdefault("history", [])
        history.append(
            {
                "type": "regen",
                "stem": target_stem,
                "variation": variation,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
        )
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return ExportBundle(
            bundle_dir=bundle_dir,
            preview_mix_path=preview_mix_path,
            stem_audio_paths=[stems_dir / f"{stem}.wav" for stem in spec.stems],
            midi_paths=[midi_dir / f"{stem}.mid" for stem in spec.stems],
            manifest_path=manifest_path,
            reference_summary=spec.reference_summary,
            updated_stem=target_stem,
        )

    def _bundle_dir(self, spec: BeatSpec) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "-", spec.prompt.lower()).strip("-")[:48] or "beat"
        bundle_dir = self.output_root / f"{timestamp}-{slug}"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        return bundle_dir

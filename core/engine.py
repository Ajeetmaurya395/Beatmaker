from __future__ import annotations

from pathlib import Path
import json

from core.arrangement import ArrangementBuilder
from core.beat_spec import BeatSpec
from core.project_exporter import ExportBundle, ProjectExporter
from core.prompt_engineer import PromptEngineer
from core.reference_analyzer import ReferenceAnalyzer
from core.sample_pack import SamplePack
from core.taste_profile import TasteProfileManager


class BeatmakerEngine:
    def __init__(self, output_root: Path, data_root: Path = Path("data")):
        self.prompt_engineer = PromptEngineer()
        self.arrangement_builder = ArrangementBuilder()
        self.exporter = ProjectExporter(output_root=output_root)
        self.reference_analyzer = ReferenceAnalyzer()
        self.taste_profile = TasteProfileManager(data_root=data_root)

    def generate(
        self,
        prompt: str,
        bpm_override: int | None = None,
        seed: int | None = None,
        total_bars_override: int | None = None,
        structure_override: str | None = None,
        sample_pack_dir: Path | None = None,
        reference_path: Path | None = None,
    ) -> ExportBundle:
        reference_profile = self.reference_analyzer.analyze(reference_path) if reference_path else None
        spec = self.prompt_engineer.build_spec(
            prompt=prompt,
            bpm_override=bpm_override,
            seed=seed,
            total_bars_override=total_bars_override,
            structure_override=structure_override,
            reference_profile=reference_profile,
            taste_profile=self.taste_profile,
        )
        events_by_stem, markers = self.arrangement_builder.build(spec, taste_profile=self.taste_profile)
        sample_pack = SamplePack(sample_pack_dir, self.exporter.audio_renderer.SAMPLE_RATE) if sample_pack_dir else None
        return self.exporter.export(spec, events_by_stem, markers, sample_pack=sample_pack)

    def regenerate_stem(
        self,
        bundle_dir: Path,
        stem: str,
        variation: str = "medium",
        sample_pack_dir: Path | None = None,
    ) -> ExportBundle:
        manifest_path = self._resolve_manifest(bundle_dir)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        spec = BeatSpec.from_dict(manifest["spec"])
        if stem not in spec.stems:
            raise ValueError(f"Unknown stem '{stem}'. Available stems: {', '.join(spec.stems)}")

        resolved_sample_pack_dir = sample_pack_dir
        if resolved_sample_pack_dir is None:
            stored = manifest.get("render", {}).get("sample_pack_path")
            if stored:
                resolved_sample_pack_dir = Path(stored)
        sample_pack = (
            SamplePack(resolved_sample_pack_dir, self.exporter.audio_renderer.SAMPLE_RATE)
            if resolved_sample_pack_dir
            else None
        )

        stem_seed_overrides, humanize_amounts = self._regen_profile(stem, variation)
        events_by_stem, markers = self.arrangement_builder.build(
            spec,
            taste_profile=self.taste_profile,
            stem_seed_overrides=stem_seed_overrides,
            humanize_amounts=humanize_amounts,
        )
        return self.exporter.update_bundle_stem(
            bundle_dir=manifest_path.parent,
            spec=spec,
            markers=markers,
            events_by_stem=events_by_stem,
            target_stem=stem,
            sample_pack=sample_pack,
            variation=variation,
        )

    def _resolve_manifest(self, bundle_dir: Path) -> Path:
        bundle_dir = Path(bundle_dir)
        if bundle_dir.is_file():
            return bundle_dir
        manifest_path = bundle_dir / "project.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Could not find project.json in {bundle_dir}")
        return manifest_path

    def _regen_profile(self, stem: str, variation: str) -> tuple[dict[str, int], dict[str, float]]:
        variation_map = {
            "low": (0, 0.05),
            "medium": (173, 0.09),
            "high": (997, 0.14),
        }
        if variation not in variation_map:
            raise ValueError("Variation must be one of: low, medium, high")
        seed_offset, humanize_amount = variation_map[variation]
        stem_seed_overrides = {stem: seed_offset} if seed_offset else {}
        humanize_amounts = {stem: humanize_amount}
        return stem_seed_overrides, humanize_amounts

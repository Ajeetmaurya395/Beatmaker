from __future__ import annotations

from pathlib import Path
import json
import random
import hashlib

from core.arrangement import ArrangementBuilder
from core.beat_spec import BeatSpec
from core.drum_extractor import DrumPatternExtractor
from core.dynamic_sample_pack import generate_sample_pack
from core.foundation_engine import FoundationVoiceEngine
from core.pattern_library import PatternLibraryManager
from core.project_exporter import ExportBundle, ProjectExporter
from core.prompt_engineer import PromptEngineer
from core.reference_analyzer import ReferenceAnalyzer
from core.reference_source import ReferenceSourceResolver
from core.sample_pack import SamplePack
from core.swarm import AutonomousProducerSwarm
from core.taste_profile import TasteProfileManager


class BeatmakerEngine:
    def __init__(self, output_root: Path, data_root: Path = Path("data")):
        self.prompt_engineer = PromptEngineer()
        self.arrangement_builder = ArrangementBuilder()
        self.exporter = ProjectExporter(output_root=output_root)
        self.reference_analyzer = ReferenceAnalyzer()
        self.reference_source = ReferenceSourceResolver(data_root / "reference_cache")
        self.taste_profile = TasteProfileManager(data_root=data_root)
        self.pattern_library = PatternLibraryManager(data_root=data_root)
        self.drum_extractor = DrumPatternExtractor()
        self.swarm = AutonomousProducerSwarm()

    def generate(
        self,
        prompt: str,
        bpm_override: int | None = None,
        seed: int | None = None,
        deterministic: bool = False,
        total_bars_override: int | None = None,
        structure_override: str | None = None,
        sample_pack_dir: Path | None = None,
        reference_path: str | Path | None = None,
        taste_strength: float = 0.35,
        reference_mode: str = "inspire",
        tags: list[str] | None = None,
        voice_provider: str = "local",
        foundation_url: str | None = None,
    ) -> ExportBundle:
        prompt_seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
        preference_rng = random.Random(seed if seed is not None else prompt_seed)
        explicit_style_cue = self._has_explicit_style_cue(prompt)
        normalized_tags = self.pattern_library.normalize_tags(tags or [])
        if not normalized_tags:
            normalized_tags = self.pattern_library.extract_tags_from_text(prompt)
            if not explicit_style_cue:
                normalized_tags = self.pattern_library.normalize_tags(
                    [*normalized_tags, *self.taste_profile.preferred_tags(preference_rng, limit=3)]
                )
        if not normalized_tags and not explicit_style_cue:
            normalized_tags = self.pattern_library.normalize_tags(self.taste_profile.preferred_tags(preference_rng, limit=3))
        prompt_for_spec = self._prompt_with_tags(prompt, normalized_tags)
        reference_profile = None
        pattern_hints = None
        if reference_path:
            resolved_reference = self.reference_source.resolve(reference_path)
            reference_profile = self.reference_analyzer.analyze(resolved_reference)
            drum_pattern = self.drum_extractor.extract(resolved_reference, bpm_hint=reference_profile.bpm)
            source_kind = "url" if str(reference_path).startswith(("http://", "https://")) else "file"
            reference_profile = type(reference_profile)(
                source_path=reference_profile.source_path,
                source_kind=source_kind,
                duration_seconds=reference_profile.duration_seconds,
                bpm=reference_profile.bpm,
                key_root=reference_profile.key_root,
                scale=reference_profile.scale,
                energy=reference_profile.energy,
                brightness=reference_profile.brightness,
                genre_hint=reference_profile.genre_hint,
                groove_steps=reference_profile.groove_steps,
                backbeat_steps=reference_profile.backbeat_steps,
            )
            pattern_hints = self._pattern_hints_from_drum_pattern(drum_pattern) or self._pattern_hints_from_reference(reference_profile)
        swarm_state = self.swarm.plan(
            prompt=prompt,
            taste_profile=self.taste_profile,
            pattern_library=self.pattern_library,
            reference_profile=reference_profile,
            tags=normalized_tags,
            seed=seed if seed is not None else prompt_seed,
        )
        normalized_tags = self.pattern_library.normalize_tags([*normalized_tags, *swarm_state.get("tags", [])])
        prompt_for_spec = self._prompt_with_tags(prompt, normalized_tags)
        spec = self.prompt_engineer.build_spec(
            prompt=prompt_for_spec,
            bpm_override=bpm_override or swarm_state.get("bpm"),
            seed=seed,
            deterministic=deterministic,
            total_bars_override=total_bars_override,
            structure_override=structure_override or swarm_state.get("structure"),
            genre_override=swarm_state.get("genre"),
            key_override=(swarm_state["key_root"], swarm_state["scale"]) if swarm_state.get("key_root") and swarm_state.get("scale") else None,
            reference_profile=reference_profile,
            taste_profile=self.taste_profile,
            taste_strength=taste_strength,
            reference_mode=reference_mode,
        )
        if pattern_hints is None:
            prompt_tags = self.pattern_library.extract_tags_from_text(prompt_for_spec)
            combined_tags = self.pattern_library.normalize_tags([*prompt_tags, *normalized_tags])
            pattern_hints = self._pattern_hints_from_library(spec.genre, spec.seed, combined_tags)
        if pattern_hints is None and swarm_state.get("drum_pattern"):
            pattern_hints = self._pattern_hints_from_drum_pattern(swarm_state["drum_pattern"])
        events_by_stem, markers = self.arrangement_builder.build(
            spec,
            taste_profile=self.taste_profile,
            pattern_hints=pattern_hints,
            progression_override=swarm_state.get("chord_progression"),
        )
        if sample_pack_dir is None:
            auto_pack_root = self.exporter.output_root / "_auto_packs"
            auto_pack_root.mkdir(parents=True, exist_ok=True)
            sample_pack_genre = swarm_state.get("sample_pack_genre") or self._choose_sample_pack_genre(spec, normalized_tags, preference_rng)
            sample_traits = self._merge_unique(
                swarm_state.get("sample_traits", []),
                self.taste_profile.preferred_sample_traits(preference_rng, limit=4),
            )
            auto_pack_dir = auto_pack_root / f"{sample_pack_genre}-{spec.seed}"
            if not auto_pack_dir.exists():
                generate_sample_pack(sample_pack_genre, auto_pack_dir, spec.seed, trait_tags=sample_traits + normalized_tags)
            sample_pack_dir = auto_pack_dir
        sample_pack = SamplePack(sample_pack_dir, self.exporter.audio_renderer.SAMPLE_RATE) if sample_pack_dir else None
        rendered_stem_overrides = None
        provider_metadata = {"voice_provider": voice_provider}
        if voice_provider == "foundation_remote":
            foundation = FoundationVoiceEngine(base_url=foundation_url)
            foundation_stems, foundation_meta = foundation.generate_stems(
                spec=spec,
                swarm_state=swarm_state,
                tags=normalized_tags,
            )
            if foundation_stems:
                rendered_stem_overrides = foundation_stems
            provider_metadata["foundation"] = foundation_meta

        return self.exporter.export(
            spec,
            events_by_stem,
            markers,
            sample_pack=sample_pack,
            planner_state=swarm_state,
            rendered_stem_overrides=rendered_stem_overrides,
            provider_metadata=provider_metadata,
        )

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

    def _pattern_hints_from_reference(self, profile) -> dict[str, list[int] | list[tuple[int, bool]]]:
        groove = profile.groove_steps or [0, 4, 8, 12]
        backbeat = profile.backbeat_steps or [4, 12]
        hats = sorted(set((step, False) for step in groove + [step + 1 for step in groove if step + 1 < 16]))
        perc = sorted(set(step for step in groove if step not in {0, 4, 8, 12}))
        return {
            "kick": [step for step in groove if step in {0, 2, 4, 6, 8, 10, 12, 14}] or [0, 8, 12],
            "snare": backbeat,
            "hats": hats,
            "perc": perc or [3, 7, 11, 15],
        }

    def _pattern_hints_from_drum_pattern(self, pattern) -> dict[str, list[int] | list[tuple[int, bool]]] | None:
        if not pattern:
            return None
        if isinstance(pattern, dict):
            return {
                "kick": list(pattern.get("kick", [])),
                "snare": list(pattern.get("snare", [])),
                "hats": [tuple(item) for item in pattern.get("hats", [])],
                "perc": list(pattern.get("perc", [])),
            }
        return {
            "kick": list(pattern.kick),
            "snare": list(pattern.snare),
            "hats": list(pattern.hats),
            "perc": list(pattern.perc),
        }

    def _pattern_hints_from_library(
        self,
        genre: str,
        seed: int,
        prompt_tags: list[str] | None = None,
    ) -> dict[str, list[int] | list[tuple[int, bool]]] | None:
        payload = self.pattern_library.search_by_tags(random.Random(seed), tags=prompt_tags, genre=genre)
        if not payload:
            return None
        drum_pattern = payload.get("drum_pattern")
        if drum_pattern:
            return {
                "kick": list(drum_pattern.get("kick") or [0, 8, 12]),
                "snare": list(drum_pattern.get("snare") or [4, 12]),
                "hats": [tuple(item) for item in (drum_pattern.get("hats") or [(step, False) for step in range(0, 16, 2)])],
                "perc": list(drum_pattern.get("perc") or [3, 7, 11, 15]),
            }
        groove = payload.get("groove_steps") or [0, 4, 8, 12]
        backbeat = payload.get("backbeat_steps") or [4, 12]
        return {
            "kick": [step for step in groove if step in {0, 2, 4, 6, 8, 10, 12, 14}] or [0, 8, 12],
            "snare": backbeat,
            "hats": sorted(set((step, False) for step in groove)),
            "perc": sorted(set(step for step in groove if step not in {0, 4, 8, 12})) or [3, 7, 11, 15],
        }

    def _prompt_with_tags(self, prompt: str, tags: list[str]) -> str:
        if not tags:
            return prompt
        prompt_lower = prompt.lower()
        tag_phrases: list[str] = []
        phrase_map = {
            "aditya_rikhari_like": "aditya rikhari",
            "hindi_indie": "hindi indie",
            "moody": "moody",
            "lofi": "lofi",
            "desi": "desi",
            "boom_bap": "boom bap",
            "bolly_trap": "bollywood trap",
            "ritviz_like": "ritviz style desi house",
        }
        for tag in tags:
            phrase = phrase_map.get(tag, tag.replace("_", " "))
            if phrase not in prompt_lower:
                tag_phrases.append(phrase)
        if not tag_phrases:
            return prompt
        return f"{prompt} [{' '.join(tag_phrases)}]"

    def _choose_sample_pack_genre(
        self,
        spec,
        tags: list[str],
        rng: random.Random,
    ) -> str:
        tag_set = set(tags)
        if "aditya_rikhari_like" in tag_set or "hindi_indie" in tag_set:
            return "hindi_indie"
        if "ritviz_like" in tag_set:
            return "house"
        if "bolly_trap" in tag_set or "desi" in tag_set:
            return "bollywood" if spec.bpm < 120 else "house"
        preferred_tags = set(self.taste_profile.preferred_tags(rng, limit=3))
        if "hindi_indie" in preferred_tags and spec.genre in {"lofi", "boom_bap", "hindi_indie"}:
            return "hindi_indie"
        return spec.genre

    def _has_explicit_style_cue(self, prompt: str) -> bool:
        prompt_lower = prompt.lower()
        cues = (
            "trap",
            "drill",
            "phonk",
            "house",
            "club",
            "dance",
            "bounce",
            "bollywood",
            "hindi indie",
            "aditya",
            "rikhari",
            "ritviz",
            "boom bap",
            "lofi",
            "acoustic",
            "indie pop",
            "street",
        )
        return any(cue in prompt_lower for cue in cues)

    def _merge_unique(self, *groups: list[str]) -> list[str]:
        merged: list[str] = []
        for group in groups:
            for item in group:
                if item not in merged:
                    merged.append(item)
        return merged

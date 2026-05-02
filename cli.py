from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from core.env_utils import load_env_file
from core.engine import BeatmakerEngine
from core.drum_extractor import DrumPatternExtractor
from core.pattern_library import PatternLibraryManager
from core.reference_analyzer import ReferenceAnalyzer
from core.reference_source import ReferenceSourceResolver
from core.taste_profile import TasteProfileManager


def main() -> None:
    load_env_file()
    argv = sys.argv[1:]
    commands = {"generate", "ingest", "rate", "profile", "regen"}
    if not argv or argv[0] not in commands:
        argv = ["generate", *argv]

    parser = argparse.ArgumentParser(
        description="Lightweight local beatmaker with FL-ready stems and taste learning"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate a beat export bundle")
    generate_parser.add_argument("--prompt", type=str, required=True, help="Describe the beat")
    generate_parser.add_argument("--bpm", type=int, help="Override the inferred BPM")
    generate_parser.add_argument("--seed", type=int, help="Optional seed for deterministic results")
    generate_parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Use a prompt-derived seed when --seed is not provided",
    )
    generate_parser.add_argument("--bars", type=int, help="Override total bars")
    generate_parser.add_argument(
        "--structure",
        type=str,
        help="Explicit arrangement, e.g. 'intro:4,hook:8,verse:16,hook:8,outro:4'",
    )
    generate_parser.add_argument(
        "--sample-pack",
        type=str,
        help="Folder containing kick.wav, snare.wav, hats_closed.wav, hats_open.wav, perc.wav",
    )
    generate_parser.add_argument(
        "--reference",
        type=str,
        help="Local WAV path or a supported URL reference source",
    )
    generate_parser.add_argument(
        "--reference-mode",
        type=str,
        default="inspire",
        choices=("inspire", "replicate"),
        help="Loosely guide from the reference or more closely clone its tempo/key/energy shape",
    )
    generate_parser.add_argument(
        "--taste-strength",
        type=float,
        default=0.35,
        help="How strongly your learned profile should bias generation, from 0.0 to 1.0",
    )
    generate_parser.add_argument(
        "--tags",
        type=str,
        help="Optional comma-separated style tags such as 'aditya_rikhari_like,hindi_indie,moody'",
    )
    generate_parser.add_argument(
        "--voice-provider",
        type=str,
        default="local",
        choices=("local", "foundation_remote"),
        help="Use the built-in renderer or a Foundation-1 compatible remote voice provider for melodic stems",
    )
    generate_parser.add_argument(
        "--foundation-url",
        type=str,
        help="Base URL for a Foundation-1 compatible remote generation service",
    )
    generate_parser.add_argument("--output-dir", type=str, default="outputs", help="Export bundle directory")
    generate_parser.add_argument("--data-dir", type=str, default="data", help="Learning/profile data directory")

    ingest_parser = subparsers.add_parser("ingest", help="Learn from your reference WAV files")
    ingest_parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="A WAV file, a folder containing WAV files, or a supported URL",
    )
    ingest_parser.add_argument(
        "--tags",
        type=str,
        help="Comma-separated tags such as 'hindi_indie,moody,bolly_trap'",
    )
    ingest_parser.add_argument("--data-dir", type=str, default="data", help="Learning/profile data directory")

    rate_parser = subparsers.add_parser("rate", help="Record feedback for a generated beat bundle")
    rate_parser.add_argument("--bundle", type=str, required=True, help="Path to the bundle folder or project.json")
    rate_parser.add_argument(
        "--feedback",
        type=str,
        required=True,
        choices=("favorite", "like", "skip", "dislike"),
        help="How strongly this beat matches your taste",
    )
    rate_parser.add_argument("--data-dir", type=str, default="data", help="Learning/profile data directory")

    profile_parser = subparsers.add_parser("profile", help="Show the current learned taste profile summary")
    profile_parser.add_argument("--data-dir", type=str, default="data", help="Learning/profile data directory")

    regen_parser = subparsers.add_parser("regen", help="Regenerate only one stem inside an existing bundle")
    regen_parser.add_argument("--bundle", type=str, required=True, help="Path to the bundle folder or project.json")
    regen_parser.add_argument(
        "--stem",
        type=str,
        required=True,
        choices=("kick", "snare", "hats", "perc", "bass_808", "chords", "lead"),
        help="Which stem to replace",
    )
    regen_parser.add_argument(
        "--variation",
        type=str,
        default="medium",
        choices=("low", "medium", "high"),
        help="Low keeps the same vibe with humanization; high changes the pattern more aggressively",
    )
    regen_parser.add_argument(
        "--sample-pack",
        type=str,
        help="Optional sample pack override. If omitted, the bundle's stored pack is reused when available.",
    )
    regen_parser.add_argument("--data-dir", type=str, default="data", help="Learning/profile data directory")

    args = parser.parse_args(argv)

    if args.command == "generate":
        engine = BeatmakerEngine(output_root=Path(args.output_dir), data_root=Path(args.data_dir))
        bundle = engine.generate(
            prompt=args.prompt,
            bpm_override=args.bpm,
            seed=args.seed,
            deterministic=args.deterministic,
            total_bars_override=args.bars,
            structure_override=args.structure,
            sample_pack_dir=Path(args.sample_pack).expanduser() if args.sample_pack else None,
            reference_path=args.reference,
            taste_strength=args.taste_strength,
            reference_mode=args.reference_mode,
            tags=parse_tags(args.tags),
            voice_provider=args.voice_provider,
            foundation_url=args.foundation_url or os.getenv("FOUNDATION_URL"),
        )

        print("\n=== Beat Export Complete ===")
        print(f"Bundle: {bundle.bundle_dir}")
        print(f"Preview mix: {bundle.preview_mix_path}")
        if bundle.reference_summary:
            print(f"Reference: {bundle.reference_summary}")
        print(f"Manifest: {bundle.manifest_path}")
        print("WAV stems:")
        for stem_path in bundle.stem_audio_paths:
            print(f"  - {stem_path}")
        print("MIDI stems:")
        for midi_path in bundle.midi_paths:
            print(f"  - {midi_path}")
        return

    if args.command == "ingest":
        manager = TasteProfileManager(data_root=Path(args.data_dir))
        pattern_library = PatternLibraryManager(data_root=Path(args.data_dir))
        analyzer = ReferenceAnalyzer()
        drum_extractor = DrumPatternExtractor()
        resolver = ReferenceSourceResolver(Path(args.data_dir) / "reference_cache")
        tags = pattern_library.normalize_tags(parse_tags(args.tags))
        if looks_like_url(args.input):
            paths = [resolver.resolve(args.input)]
        else:
            paths = expand_wavs(Path(args.input).expanduser())
        if not paths:
            raise SystemExit("No reference sources found to ingest.")
        print(f"Ingesting {len(paths)} reference file(s)...")
        for path in paths:
            profile = analyzer.analyze(path)
            resolved_tags = tags or pattern_library.auto_tags_for_profile(profile)
            summary = manager.ingest_reference(profile, tags=resolved_tags)
            drum_pattern = drum_extractor.extract(path, bpm_hint=profile.bpm)
            pattern_path = pattern_library.add_reference(profile, tags=resolved_tags, drum_pattern=drum_pattern)
            print(f"  - {summary}")
            print(f"    tags: {', '.join(resolved_tags) if resolved_tags else 'none'}")
            print(f"    pattern: {pattern_path}")
        print(manager.summary())
        return

    if args.command == "rate":
        manager = TasteProfileManager(data_root=Path(args.data_dir))
        result = manager.record_feedback(Path(args.bundle).expanduser(), args.feedback)
        print(result)
        print(manager.summary())
        return

    if args.command == "profile":
        manager = TasteProfileManager(data_root=Path(args.data_dir))
        print(manager.summary())
        return

    if args.command == "regen":
        engine = BeatmakerEngine(output_root=Path("outputs"), data_root=Path(args.data_dir))
        bundle = engine.regenerate_stem(
            bundle_dir=Path(args.bundle).expanduser(),
            stem=args.stem,
            variation=args.variation,
            sample_pack_dir=Path(args.sample_pack).expanduser() if args.sample_pack else None,
        )
        print("\n=== Stem Regenerated ===")
        print(f"Bundle: {bundle.bundle_dir}")
        print(f"Updated stem: {bundle.updated_stem}")
        print(f"Preview mix: {bundle.preview_mix_path}")
        print(f"Manifest: {bundle.manifest_path}")
        return


def expand_wavs(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        return []
    return sorted(candidate for candidate in path.rglob("*.wav") if candidate.is_file())


def looks_like_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [chunk.strip() for chunk in raw.split(",") if chunk.strip()]


if __name__ == "__main__":
    main()

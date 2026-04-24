from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.engine import BeatmakerEngine
from core.reference_analyzer import ReferenceAnalyzer
from core.taste_profile import TasteProfileManager


def main() -> None:
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
        help="Path to a WAV reference track to influence BPM, key, scale, energy, and genre hint",
    )
    generate_parser.add_argument("--output-dir", type=str, default="outputs", help="Export bundle directory")
    generate_parser.add_argument("--data-dir", type=str, default="data", help="Learning/profile data directory")

    ingest_parser = subparsers.add_parser("ingest", help="Learn from your reference WAV files")
    ingest_parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="A WAV file or a folder containing WAV files",
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
            total_bars_override=args.bars,
            structure_override=args.structure,
            sample_pack_dir=Path(args.sample_pack).expanduser() if args.sample_pack else None,
            reference_path=Path(args.reference).expanduser() if args.reference else None,
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
        analyzer = ReferenceAnalyzer()
        paths = expand_wavs(Path(args.input).expanduser())
        if not paths:
            raise SystemExit("No WAV files found to ingest.")
        print(f"Ingesting {len(paths)} reference file(s)...")
        for path in paths:
            summary = manager.ingest_reference(analyzer.analyze(path))
            print(f"  - {summary}")
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


if __name__ == "__main__":
    main()

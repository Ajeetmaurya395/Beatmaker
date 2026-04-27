from __future__ import annotations

import json
import math
from pathlib import Path
import random

from core.pattern_utils import structure_signature
from core.reference_analyzer import ReferenceProfile


class TasteProfileManager:
    STEMS = ("kick", "snare", "hats", "perc", "bass_808", "chords", "lead")
    FEEDBACK_WEIGHTS = {
        "favorite": 3.0,
        "like": 1.5,
        "skip": 0.75,
        "dislike": 1.5,
    }

    def __init__(self, data_root: Path = Path("data")):
        self.data_root = Path(data_root)
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.profile_path = self.data_root / "taste_profile.json"
        self.profile = self._load_or_create()

    def ingest_reference(
        self,
        profile: ReferenceProfile,
        source_type: str = "reference",
        tags: list[str] | None = None,
    ) -> str:
        stats = self.profile["stats"]
        self._bump(stats["genre_scores"], profile.genre_hint, 1.0)
        self._bump(stats["bpm_scores"], str(profile.bpm), 1.0)
        self._bump(stats["key_scores"], f"{profile.key_root} {profile.scale}", 1.0)
        self._bump(stats["energy_scores"], self._bucket(profile.energy), 1.0)
        for tag in tags or []:
            self._bump(stats["tag_scores"], tag, 1.0)
        for trait in self._sample_traits_for_reference(profile):
            self._bump(stats["sample_trait_scores"], trait, 1.0)

        self.profile["history"].append(
            {
                "type": source_type,
                "source": str(profile.source_path),
                "summary": profile.summary,
                "source_kind": getattr(profile, "source_kind", "file"),
                "tags": list(tags or []),
            }
        )
        self._save()
        return profile.summary

    def record_feedback(self, bundle_dir: Path, feedback: str) -> str:
        if feedback not in self.FEEDBACK_WEIGHTS:
            raise ValueError(f"Unsupported feedback '{feedback}'.")

        manifest_path = self._resolve_manifest(bundle_dir)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        weight = self.FEEDBACK_WEIGHTS[feedback]
        positive = feedback in {"favorite", "like"}
        target = self.profile["stats"] if positive else self.profile["avoids"]

        spec = manifest["spec"]
        render = manifest.get("render", {})
        analysis = manifest.get("analysis", {})
        genre = spec["genre"]
        bpm = str(spec["bpm"])
        key_name = f"{spec['key_root']} {spec['scale']}"
        struct_sig = analysis.get("structure_signature") or structure_signature_from_manifest(spec)

        self._bump(target["genre_scores"], genre, weight)
        self._bump(target["bpm_scores"], bpm, weight)
        self._bump(target["key_scores"], key_name, weight)
        self._bump(target["structure_scores"], struct_sig, weight)
        self._bump_nested(target["genre_structure_scores"], genre, struct_sig, weight)

        sample_pack_name = render.get("sample_pack_name")
        if sample_pack_name:
            self._bump(target["sample_pack_scores"], sample_pack_name, weight)

        for stem, patterns in analysis.get("pattern_summary", {}).items():
            for pattern, count in patterns.items():
                weighted = weight * max(1, count)
                self._bump_nested(target["pattern_scores"][stem], genre, pattern, weighted)

        self.profile["history"].append(
            {
                "type": "feedback",
                "feedback": feedback,
                "bundle": str(manifest_path.parent),
                "prompt": spec["prompt"],
            }
        )
        self._save()
        
        # RLHF / DPO Preference Logging
        score_map = {
            "favorite": 1.0,
            "like": 0.5,
            "skip": -0.5,
            "dislike": -1.0
        }
        if feedback in score_map:
            dpo_file = self.data_root / "dpo_pairs.jsonl"
            import time
            with open(dpo_file, "a", encoding="utf-8") as f:
                pair = {
                    "timestamp": time.time(),
                    "prompt": spec.get("prompt", ""),
                    "genre": spec.get("genre", ""),
                    "bpm": spec.get("bpm", 120),
                    "key": f"{spec.get('key_root', 'C')} {spec.get('scale', 'minor')}",
                    "sections": spec.get("sections", []),
                    "score": score_map[feedback]
                }
                f.write(json.dumps(pair) + "\n")
                
        return f"{feedback} recorded for {manifest_path.parent.name}"

    def preferred_genre(self, rng: random.Random) -> str | None:
        return self._weighted_choice(
            self.profile["stats"]["genre_scores"],
            self.profile["avoids"]["genre_scores"],
            rng,
        )

    def preferred_bpm(self, rng: random.Random) -> int | None:
        value = self._weighted_choice(
            self.profile["stats"]["bpm_scores"],
            self.profile["avoids"]["bpm_scores"],
            rng,
        )
        return int(value) if value is not None else None

    def preferred_key(self, rng: random.Random) -> tuple[str, str] | None:
        value = self._weighted_choice(
            self.profile["stats"]["key_scores"],
            self.profile["avoids"]["key_scores"],
            rng,
        )
        if not value:
            return None
        root, scale = value.split(" ", 1)
        return root, scale

    def preferred_structure(self, genre: str, rng: random.Random) -> str | None:
        return self._weighted_choice(
            self.profile["stats"]["genre_structure_scores"].get(genre, {}),
            self.profile["avoids"]["genre_structure_scores"].get(genre, {}),
            rng,
        ) or self._weighted_choice(
            self.profile["stats"]["structure_scores"],
            self.profile["avoids"]["structure_scores"],
            rng,
        )

    def preferred_pattern(self, stem: str, genre: str, rng: random.Random) -> str | None:
        if stem not in self.STEMS:
            return None
        return self._weighted_choice(
            self.profile["stats"]["pattern_scores"][stem].get(genre, {}),
            self.profile["avoids"]["pattern_scores"][stem].get(genre, {}),
            rng,
        )

    def preferred_sample_pack(self, rng: random.Random) -> str | None:
        return self._weighted_choice(
            self.profile["stats"]["sample_pack_scores"],
            self.profile["avoids"]["sample_pack_scores"],
            rng,
        )

    def preferred_tags(self, rng: random.Random, limit: int = 3) -> list[str]:
        return self._top_choices(
            self.profile["stats"]["tag_scores"],
            self.profile["avoids"]["tag_scores"],
            rng,
            limit=limit,
        )

    def preferred_sample_traits(self, rng: random.Random, limit: int = 3) -> list[str]:
        return self._top_choices(
            self.profile["stats"]["sample_trait_scores"],
            self.profile["avoids"]["sample_trait_scores"],
            rng,
            limit=limit,
        )

    def summary(self) -> str:
        rng = random.Random(7)
        genre = self.preferred_genre(rng) or "none"
        bpm = self.preferred_bpm(rng)
        key = self.preferred_key(rng)
        tags = ",".join(self.preferred_tags(rng, limit=2)) or "none"
        traits = ",".join(self.preferred_sample_traits(rng, limit=2)) or "none"
        structures = len(self.profile["stats"]["structure_scores"])
        history = len(self.profile["history"])
        return (
            f"profile={self.profile_path.name}, genre={genre}, "
            f"bpm={bpm if bpm is not None else 'none'}, "
            f"key={' '.join(key) if key else 'none'}, "
            f"tags={tags}, traits={traits}, "
            f"structures={structures}, entries={history}"
        )

    def _resolve_manifest(self, bundle_dir: Path) -> Path:
        bundle_dir = Path(bundle_dir)
        if bundle_dir.is_file():
            return bundle_dir
        manifest_path = bundle_dir / "project.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Could not find project.json in {bundle_dir}")
        return manifest_path

    def _load_or_create(self) -> dict:
        if self.profile_path.exists():
            return json.loads(self.profile_path.read_text(encoding="utf-8"))
        profile = self._empty_profile()
        self.profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        return profile

    def _save(self) -> None:
        self.profile_path.write_text(json.dumps(self.profile, indent=2), encoding="utf-8")

    def _empty_profile(self) -> dict:
        return {
            "version": 1,
            "stats": self._empty_stat_block(),
            "avoids": self._empty_stat_block(),
            "history": [],
        }

    def _empty_stat_block(self) -> dict:
        return {
            "genre_scores": {},
            "bpm_scores": {},
            "key_scores": {},
            "energy_scores": {},
            "tag_scores": {},
            "sample_trait_scores": {},
            "structure_scores": {},
            "genre_structure_scores": {},
            "sample_pack_scores": {},
            "pattern_scores": {stem: {} for stem in self.STEMS},
        }

    def _bump(self, mapping: dict[str, float], key: str, amount: float) -> None:
        mapping[key] = round(mapping.get(key, 0.0) + amount, 4)

    def _bump_nested(self, mapping: dict[str, dict[str, float]], key: str, nested_key: str, amount: float) -> None:
        bucket = mapping.setdefault(key, {})
        bucket[nested_key] = round(bucket.get(nested_key, 0.0) + amount, 4)

    def _weighted_choice(
        self,
        positives: dict[str, float],
        negatives: dict[str, float],
        rng: random.Random,
    ) -> str | None:
        candidates = {}
        for key in set(positives) | set(negatives):
            positive_score = math.log1p(max(0.0, positives.get(key, 0.0)))
            negative_score = math.log1p(max(0.0, negatives.get(key, 0.0))) * 0.9
            score = positive_score - negative_score
            if score > 0.0:
                candidates[key] = score
        if not candidates:
            return None

        total = sum(candidates.values())
        threshold = rng.random() * total
        running = 0.0
        for key, score in sorted(candidates.items()):
            running += score
            if running >= threshold:
                return key
        return next(iter(candidates))

    def _top_choices(
        self,
        positives: dict[str, float],
        negatives: dict[str, float],
        rng: random.Random,
        limit: int,
    ) -> list[str]:
        candidates: list[tuple[float, str]] = []
        for key in set(positives) | set(negatives):
            positive_score = math.log1p(max(0.0, positives.get(key, 0.0)))
            negative_score = math.log1p(max(0.0, negatives.get(key, 0.0))) * 0.9
            score = positive_score - negative_score
            if score > 0.0:
                candidates.append((score, key))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return [key for _score, key in candidates[:limit]]

    def _sample_traits_for_reference(self, profile: ReferenceProfile) -> list[str]:
        traits: list[str] = []
        if profile.brightness < 0.2:
            traits.append("warm")
        if profile.brightness > 0.28:
            traits.append("bright")
        if profile.energy < 0.4:
            traits.append("soft")
        if profile.energy > 0.65:
            traits.append("punchy")
        if profile.bpm <= 100:
            traits.append("laid_back")
        if profile.genre_hint == "hindi_indie":
            traits.extend(["airy", "organic"])
        if profile.genre_hint == "bollywood":
            traits.extend(["bright", "wide"])
        return sorted(set(traits))

    def _bucket(self, value: float, step: float = 0.05) -> str:
        snapped = round(round(value / step) * step, 2)
        return f"{snapped:.2f}"


def structure_signature_from_manifest(spec: dict) -> str:
    return "|".join(f"{section['name']}:{section['bars']}" for section in spec.get("sections", []))

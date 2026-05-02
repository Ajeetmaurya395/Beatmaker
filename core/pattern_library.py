from __future__ import annotations

import json
import random
from pathlib import Path

from core.reference_analyzer import ReferenceProfile
from core.drum_extractor import DrumPattern


class PatternLibraryManager:
    TAG_ALIASES = {
        "desi": {"desi", "bollywood", "indian", "hindi"},
        "hindi_indie": {"hindi_indie", "hindi indie", "prateek", "kuhad", "prateek kuhad", "aditya_rikhari_like", "aditya", "rikhari", "aditya rikhari"},
        "aditya_rikhari_like": {"aditya_rikhari_like", "aditya", "rikhari", "aditya rikhari"},
        "bolly_trap": {"bolly_trap", "bollywood trap", "desi trap"},
        "ritviz_like": {"ritviz_like", "ritviz", "desi_house", "desi house"},
        "moody": {"moody", "sad", "dark", "night", "melancholy"},
        "lofi": {"lofi", "lo-fi", "chillhop", "jazzy"},
        "phonk": {"phonk", "drift", "cowbell"},
        "drill": {"drill", "uk_drill", "ny_drill"},
        "trap": {"trap", "808"},
    }

    def __init__(self, data_root: Path = Path("data")):
        self.root = Path(data_root) / "patterns"
        self.root.mkdir(parents=True, exist_ok=True)

    def add_reference(
        self,
        profile: ReferenceProfile,
        tags: list[str] | None = None,
        drum_pattern: DrumPattern | None = None,
    ) -> Path:
        genre_dir = self.root / profile.genre_hint
        genre_dir.mkdir(parents=True, exist_ok=True)
        out_path = genre_dir / f"{profile.source_path.stem}.json"
        normalized_tags = self.normalize_tags(tags or [])
        payload = {
            "source": str(profile.source_path),
            "source_kind": profile.source_kind,
            "duration_seconds": profile.duration_seconds,
            "genre": profile.genre_hint,
            "bpm": profile.bpm,
            "key_root": profile.key_root,
            "scale": profile.scale,
            "energy": profile.energy,
            "brightness": profile.brightness,
            "groove_steps": profile.groove_steps,
            "backbeat_steps": profile.backbeat_steps,
            "tags": normalized_tags,
            "drum_pattern": drum_pattern.to_dict() if drum_pattern else None,
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return out_path

    def auto_tags_for_profile(self, profile: ReferenceProfile) -> list[str]:
        label = profile.source_path.stem.lower()
        tags: list[str] = [profile.genre_hint]
        if profile.genre_hint in {"hindi_indie", "bollywood"}:
            tags.append("desi")
        if profile.scale == "minor" or profile.energy < 0.5:
            tags.append("moody")
        if profile.genre_hint == "lofi":
            tags.append("lofi")
        if profile.genre_hint == "house":
            tags.append("ritviz_like")
        if any(word in label for word in ("aditya", "rikhari")):
            tags.extend(["hindi_indie", "aditya_rikhari_like"])
        if any(word in label for word in ("prateek", "kuhad", "indie", "acoustic", "unplugged")):
            tags.extend(["hindi_indie", "acoustic"])
        if any(word in label for word in ("ritviz", "dance")):
            tags.extend(["ritviz_like", "desi"])
        if any(word in label for word in ("bollywood", "hindi", "desi", "jhankar")):
            tags.extend(["desi"])
        return self.normalize_tags(tags)

    def retrieve(self, genre: str, rng: random.Random, tags: list[str] | None = None) -> dict | None:
        genre_dir = self.root / genre
        if not genre_dir.exists():
            return None
        items = sorted(genre_dir.glob("*.json"))
        if not items:
            return None
        if tags:
            tagged = []
            for item in items:
                try:
                    payload = json.loads(item.read_text(encoding="utf-8"))
                except Exception:
                    continue
                item_tags = set(payload.get("tags", []))
                if item_tags.intersection(tags):
                    tagged.append((item, payload))
        if tagged:
            return rng.choice(tagged)[1]
        item = rng.choice(items)
        return json.loads(item.read_text(encoding="utf-8"))

    def search_by_tags(
        self,
        rng: random.Random,
        tags: list[str] | None = None,
        genre: str | None = None,
    ) -> dict | None:
        normalized_tags = self.normalize_tags(tags or [])
        expanded_tags = self._expand_tags(normalized_tags)
        candidates = []
        for item in sorted(self.root.rglob("*.json")):
            try:
                payload = json.loads(item.read_text(encoding="utf-8"))
            except Exception:
                continue
            score = 0
            item_tags = set(self.normalize_tags(payload.get("tags", [])))
            if genre and payload.get("genre") == genre:
                score += 2
            if expanded_tags:
                overlap = item_tags.intersection(expanded_tags)
                score += len(overlap) * 3
                if payload.get("genre") in expanded_tags:
                    score += 2
            if score > 0:
                candidates.append((score, payload))
        if not candidates:
            return self.retrieve(genre, rng, normalized_tags) if genre else None
        max_score = max(score for score, _payload in candidates)
        best = [payload for score, payload in candidates if score == max_score]
        return rng.choice(best)

    def extract_tags_from_text(self, text: str) -> list[str]:
        text_lower = text.lower()
        tags = []
        for canonical, aliases in self.TAG_ALIASES.items():
            if any(self._matches_alias(text_lower, alias) for alias in aliases):
                tags.append(canonical)
        return self.normalize_tags(tags)

    def normalize_tags(self, tags: list[str]) -> list[str]:
        normalized = []
        exact_keys = {base.lower().replace(" ", "_") for base in self.TAG_ALIASES}
        for raw in tags:
            tag = raw.strip().lower().replace(" ", "_")
            if not tag:
                continue
            if tag in exact_keys:
                normalized.append(tag)
                continue
            canonical = None
            for base, aliases in self.TAG_ALIASES.items():
                alias_tokens = {alias.lower().replace(" ", "_") for alias in aliases}
                if tag in alias_tokens:
                    canonical = base
                    break
            normalized.append(canonical or tag)
        return sorted(set(normalized))

    def _expand_tags(self, tags: list[str]) -> set[str]:
        expanded = set(tags)
        for tag in tags:
            aliases = self.TAG_ALIASES.get(tag)
            if aliases:
                expanded.update(self.normalize_tags(list(aliases)))
        return expanded

    def _matches_alias(self, text: str, alias: str) -> bool:
        normalized_alias = alias.lower().replace("_", " ").strip()
        if " " in normalized_alias:
            return normalized_alias in text
        tokens = [token.strip("[](),.!?;:'\"") for token in text.split()]
        return normalized_alias in tokens

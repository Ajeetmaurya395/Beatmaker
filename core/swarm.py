from __future__ import annotations

import hashlib
import random
from typing import TypedDict

from core.pattern_library import PatternLibraryManager
from core.reference_analyzer import ReferenceProfile
from core.taste_profile import TasteProfileManager


class MoodAnalysis(TypedDict):
    valence: float
    arousal: float
    genre: str


class MusicState(TypedDict, total=False):
    prompt: str
    mood_analysis: MoodAnalysis
    bpm: int
    key_root: str
    scale: str
    genre: str
    structure: str
    chord_progression: list[int]
    drum_pattern: dict[str, list[int] | list[tuple[int, bool]]]
    sample_paths: dict[str, str]
    sample_pack_genre: str
    sample_traits: list[str]
    tags: list[str]
    critic_feedback: str
    approved: bool
    retry_count: int


class AutonomousProducerSwarm:
    ROOTS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    BPM_BY_GENRE = {
        "trap": (130, 150),
        "drill": (138, 148),
        "boom_bap": (82, 96),
        "lofi": (70, 88),
        "house": (120, 128),
        "phonk": (136, 152),
        "bollywood": (92, 116),
        "hindi_indie": (74, 98),
    }
    STRUCTURES = {
        "trap": ("intro:4,hook:8,verse:8,hook:8,outro:4", "intro:4,verse:8,hook:8,verse:8,hook:8"),
        "drill": ("intro:4,hook:8,verse:8,hook:8,outro:4", "intro:4,verse:8,hook:8,verse:8,hook:8"),
        "boom_bap": ("intro:4,loop:8,verse:8,hook:8,outro:4", "intro:4,verse:8,verse:8,hook:8,outro:4"),
        "lofi": ("intro:4,loop:8,variation:8,loop:8,outro:4", "intro:4,loop:8,loop:8,variation:8,outro:4"),
        "house": ("intro:8,groove:8,drop:8,break:8,drop:8,outro:8", "intro:8,groove:8,groove:8,drop:8,outro:8"),
        "phonk": ("intro:4,drop:8,variation:8,drop:8,outro:4", "intro:4,drop:8,drop:8,variation:8,outro:4"),
        "bollywood": ("alap:4,mukhda:8,antara:8,mukhda:8,outro:4", "intro:4,verse:8,hook:8,verse:8,hook:8"),
        "hindi_indie": ("intro:4,verse:8,hook:8,verse:8,hook:8,outro:4", "intro:4,verse:8,verse:8,hook:8,outro:4"),
    }
    PROGRESSIONS = {
        "major": ([0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 4, 3]),
        "minor": ([0, 5, 3, 4], [0, 3, 5, 4], [0, 4, 3, 5]),
    }
    DRUM_FAMILIES = {
        "trap": (
            {"kick": [0, 7, 10, 12], "snare": [4, 12], "hats": [(step, False) for step in range(0, 16, 2)], "perc": [3, 11, 15]},
            {"kick": [0, 6, 10, 13], "snare": [4, 11, 12], "hats": [(0, False), (2, False), (4, False), (6, False), (8, False), (10, False), (12, False), (14, False), (15, False)], "perc": [1, 7, 13]},
        ),
        "drill": (
            {"kick": [0, 6, 9, 12], "snare": [4, 12], "hats": [(0, False), (2, False), (4, False), (6, False), (8, False), (10, False), (12, False), (14, False), (15, False)], "perc": [2, 7, 13]},
            {"kick": [0, 7, 11, 14], "snare": [4, 10, 12], "hats": [(0, False), (3, False), (4, False), (6, False), (8, False), (11, False), (12, False), (14, False)], "perc": [1, 6, 12]},
        ),
        "lofi": (
            {"kick": [0, 6, 10], "snare": [4, 12], "hats": [(0, False), (4, False), (8, False), (12, False)], "perc": [6, 14]},
            {"kick": [0, 8], "snare": [4, 12, 15], "hats": [(2, False), (6, False), (10, False), (14, False)], "perc": [3, 11]},
        ),
        "house": (
            {"kick": [0, 4, 8, 12], "snare": [4, 12], "hats": [(2, False), (4, False), (6, False), (8, False), (10, False), (12, False), (14, False), (15, True)], "perc": [6, 10, 14]},
            {"kick": [0, 4, 10, 12], "snare": [4, 11, 12], "hats": [(0, False), (2, False), (4, False), (6, False), (8, False), (10, False), (12, False), (14, False), (15, True)], "perc": [3, 7, 11, 15]},
        ),
        "phonk": (
            {"kick": [0, 4, 8, 10, 12], "snare": [4, 10, 12], "hats": [(step, False) for step in range(0, 16, 2)], "perc": [3, 7, 11, 15]},
            {"kick": [0, 3, 8, 10, 14], "snare": [4, 9, 12], "hats": [(0, False), (2, False), (4, False), (6, False), (8, False), (10, False), (12, False), (14, False), (15, False)], "perc": [1, 5, 9, 13]},
        ),
        "bollywood": (
            {"kick": [0, 8, 12], "snare": [4, 12], "hats": [(0, False), (4, False), (8, False), (12, False)], "perc": [3, 7, 11, 15]},
            {"kick": [0, 6, 10, 12], "snare": [4, 10, 12], "hats": [(2, False), (6, False), (10, False), (14, False)], "perc": [2, 7, 13]},
        ),
        "hindi_indie": (
            {"kick": [0, 10], "snare": [8], "hats": [(0, False), (4, False), (8, False), (12, False)], "perc": [6, 14]},
            {"kick": [0, 8], "snare": [8, 15], "hats": [(2, False), (6, False), (10, False), (14, False)], "perc": [5, 13]},
        ),
    }

    def plan(
        self,
        prompt: str,
        taste_profile: TasteProfileManager,
        pattern_library: PatternLibraryManager,
        reference_profile: ReferenceProfile | None = None,
        tags: list[str] | None = None,
        seed: int | None = None,
        max_retries: int = 2,
    ) -> MusicState:
        rng_seed = seed if seed is not None else int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
        state: MusicState = {
            "prompt": prompt,
            "tags": pattern_library.normalize_tags(tags or []),
            "retry_count": 0,
            "approved": False,
            "sample_paths": {},
        }
        state = self._director_node(state, taste_profile, pattern_library, reference_profile, rng_seed)
        for retry_count in range(max_retries + 1):
            state["retry_count"] = retry_count
            state = self._theorist_node(state, rng_seed + retry_count)
            state = self._curator_node(state, taste_profile, rng_seed + retry_count)
            state = self._critic_node(state)
            if state.get("approved"):
                break
        return state

    def _director_node(
        self,
        state: MusicState,
        taste_profile: TasteProfileManager,
        pattern_library: PatternLibraryManager,
        reference_profile: ReferenceProfile | None,
        seed: int,
    ) -> MusicState:
        prompt = state["prompt"].lower()
        rng = random.Random(seed)
        tags = pattern_library.normalize_tags(list(state.get("tags", [])))
        prompt_tags = pattern_library.extract_tags_from_text(prompt)
        preferred_tags = taste_profile.preferred_tags(rng, limit=3) if not self._has_explicit_genre_word(prompt) else []
        tags = pattern_library.normalize_tags([*tags, *prompt_tags, *preferred_tags])

        valence = 0.55
        arousal = 0.55
        if any(word in prompt for word in ("sad", "moody", "dark", "night", "heartbreak", "late night")):
            valence -= 0.22
        if any(word in prompt for word in ("soft", "gentle", "airy", "warm", "dreamy")):
            arousal -= 0.16
        if any(word in prompt for word in ("hard", "aggressive", "club", "bounce", "heavy", "festival")):
            arousal += 0.22
        if any(word in prompt for word in ("happy", "uplifting", "bright", "summer", "romantic")):
            valence += 0.16
        valence = max(0.0, min(1.0, valence))
        arousal = max(0.0, min(1.0, arousal))

        genre = self._choose_genre(prompt, tags, taste_profile, reference_profile, rng, valence, arousal)
        bpm_low, bpm_high = self.BPM_BY_GENRE.get(genre, (90, 130))
        bpm = reference_profile.bpm if reference_profile else round(bpm_low + ((bpm_high - bpm_low) * arousal))
        scale = reference_profile.scale if reference_profile else ("minor" if valence < 0.58 else "major")
        key_root = reference_profile.key_root if reference_profile else self.ROOTS[(seed + int(valence * 11)) % len(self.ROOTS)]
        structure_options = self.STRUCTURES.get(genre, self.STRUCTURES["trap"])
        structure = structure_options[1] if arousal < 0.45 else structure_options[0]
        state["mood_analysis"] = {"valence": valence, "arousal": arousal, "genre": genre}
        state["genre"] = genre
        state["bpm"] = int(bpm)
        state["scale"] = scale
        state["key_root"] = key_root
        state["structure"] = structure
        state["tags"] = tags
        return state

    def _theorist_node(self, state: MusicState, seed: int) -> MusicState:
        rng = random.Random(seed + (state.get("retry_count", 0) * 101))
        genre = state.get("genre", "trap")
        scale = state.get("scale", "minor")
        progression_pool = self.PROGRESSIONS["minor" if scale == "minor" else "major"]
        progression_index = self._pick_index(state["prompt"], f"{genre}-progression", len(progression_pool), state.get("retry_count", 0))
        progression = list(progression_pool[progression_index])
        drum_families = self.DRUM_FAMILIES.get(genre, self.DRUM_FAMILIES["trap"])
        family_index = self._pick_index(state["prompt"], f"{genre}-drums", len(drum_families), state.get("retry_count", 0))
        chosen_family = drum_families[family_index]

        if state.get("retry_count", 0) > 0 and state.get("mood_analysis", {}).get("arousal", 0.5) < 0.45:
            chosen_family = dict(chosen_family)
            chosen_family["hats"] = list(chosen_family["hats"])[:4]
            chosen_family["perc"] = list(chosen_family["perc"])[:2]

        if rng.random() < 0.25 and genre not in {"hindi_indie", "house"}:
            progression = progression[1:] + progression[:1]

        state["chord_progression"] = progression
        state["drum_pattern"] = {
            "kick": list(chosen_family["kick"]),
            "snare": list(chosen_family["snare"]),
            "hats": list(chosen_family["hats"]),
            "perc": list(chosen_family["perc"]),
        }
        return state

    def _curator_node(self, state: MusicState, taste_profile: TasteProfileManager, seed: int) -> MusicState:
        rng = random.Random(seed)
        genre = state.get("genre", "trap")
        tags = set(state.get("tags", []))
        preferred_traits = taste_profile.preferred_sample_traits(rng, limit=4)
        traits = set(preferred_traits)
        mood = state.get("mood_analysis", {})
        if mood.get("valence", 0.5) < 0.5:
            traits.add("warm")
        if mood.get("arousal", 0.5) < 0.5:
            traits.add("soft")
        else:
            traits.add("punchy")
        if genre == "hindi_indie":
            traits.update({"airy", "organic"})
        if genre == "house":
            traits.add("bright")
        if genre == "bollywood":
            traits.update({"bright", "wide"})

        sample_pack_genre = genre
        if "aditya_rikhari_like" in tags or "hindi_indie" in tags:
            sample_pack_genre = "hindi_indie"
        elif "ritviz_like" in tags:
            sample_pack_genre = "house"
        elif "desi" in tags and genre in {"lofi", "boom_bap"}:
            sample_pack_genre = "hindi_indie"

        state["sample_pack_genre"] = sample_pack_genre
        state["sample_traits"] = sorted(traits)
        return state

    def _critic_node(self, state: MusicState) -> MusicState:
        feedback: list[str] = []
        approved = True
        progression = state.get("chord_progression", [])
        drum_pattern = state.get("drum_pattern", {})
        genre = state.get("genre", "trap")
        mood = state.get("mood_analysis", {"valence": 0.5, "arousal": 0.5})

        if not progression or any(degree < 0 or degree > 6 for degree in progression):
            approved = False
            feedback.append("Invalid progression degrees; reroll theory.")

        hats = drum_pattern.get("hats", [])
        kick = drum_pattern.get("kick", [])
        perc = drum_pattern.get("perc", [])

        if mood.get("arousal", 0.5) < 0.45 and len(hats) > 5:
            approved = False
            feedback.append("Too many hats for a soft groove.")
        if mood.get("arousal", 0.5) > 0.7 and len(kick) < 3:
            approved = False
            feedback.append("Kick pattern underpowered for high-energy prompt.")
        if genre == "hindi_indie" and state.get("sample_pack_genre") != "hindi_indie":
            approved = False
            feedback.append("Hindi indie lane should use the Hindi indie sample palette.")
        if genre == "hindi_indie" and len(perc) > 2 and mood.get("arousal", 0.5) < 0.5:
            approved = False
            feedback.append("Percussion is too busy for an intimate Hindi indie beat.")

        if approved:
            feedback.append("Critic approved progression, groove, and palette.")
        state["approved"] = approved
        state["critic_feedback"] = " ".join(feedback)
        return state

    def _choose_genre(
        self,
        prompt: str,
        tags: list[str],
        taste_profile: TasteProfileManager,
        reference_profile: ReferenceProfile | None,
        rng: random.Random,
        valence: float,
        arousal: float,
    ) -> str:
        if any(cue in prompt for cue in ("club", "dance", "summer party", "festival", "bounce")):
            return "house"
        if any(cue in prompt for cue in ("drill", "street", "aggressive", "menacing")):
            return "drill" if arousal > 0.6 else "trap"
        if any(cue in prompt for cue in ("late night", "dreamy", "warm", "soft")):
            return "hindi_indie" if "desi" in set(tags) else "lofi"
        if any(cue in prompt for cue in ("acoustic", "indie", "guitar", "aditya", "rikhari", "romantic")):
            return "hindi_indie"
        if any(cue in prompt for cue in ("bollywood", "jhankar", "desi pop")):
            return "bollywood"
        tag_set = set(tags)
        if reference_profile:
            return reference_profile.genre_hint
        if "aditya_rikhari_like" in tag_set or "hindi_indie" in tag_set:
            return "hindi_indie"
        if "ritviz_like" in tag_set:
            return "house"
        if "bolly_trap" in tag_set:
            return "bollywood" if arousal < 0.65 else "trap"
        preferred = taste_profile.preferred_genre(rng)
        if preferred and not self._has_explicit_genre_word(prompt):
            return preferred
        if arousal < 0.38 and valence < 0.58:
            return "hindi_indie" if "desi" in tag_set else "lofi"
        if arousal > 0.72:
            return "house" if "club" in prompt or "dance" in prompt else "drill"
        return "trap" if arousal > 0.58 else "boom_bap"

    def _has_explicit_genre_word(self, prompt: str) -> bool:
        return any(
            cue in prompt
            for cue in (
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
                "street",
            )
        )

    def _pick_index(self, prompt: str, lane: str, count: int, retry_count: int) -> int:
        if count <= 1:
            return 0
        digest = hashlib.sha256(f"{prompt.lower()}|{lane}|{retry_count}".encode("utf-8")).hexdigest()[:8]
        return int(digest, 16) % count

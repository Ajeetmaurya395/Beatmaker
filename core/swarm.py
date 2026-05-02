from __future__ import annotations

import hashlib
import json
import os
import random
from typing import TypedDict

from pydantic import BaseModel, Field

try:
    import instructor
    from groq import Groq
except Exception:
    instructor = None
    Groq = None

try:
    import music21
except Exception:
    music21 = None

from core.pattern_library import PatternLibraryManager
from core.reference_analyzer import ReferenceProfile
from core.taste_profile import TasteProfileManager
from core.theory_validator import validate_chords
from core.vector_library import SemanticPresetLibrary


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
    swing_factor: float
    drum_pattern: dict[str, list[int] | list[tuple[int, bool]]]
    sample_paths: dict[str, str]
    sample_pack_genre: str
    sample_traits: list[str]
    tags: list[str]
    critic_feedback: str
    approved: bool
    retry_count: int
    synth_presets: dict[str, dict]


class DrumPatternBlueprint(BaseModel):
    kick: list[int] = Field(description="Step indices for the kick drum (0-15)")
    snare: list[int] = Field(description="Step indices for the snare drum (0-15)")
    hats: list[tuple[int, bool]] = Field(description="Step indices for the hi-hats (0-15) and whether they are open (True) or closed (False)")
    perc: list[int] = Field(description="Step indices for percussion elements (0-15)")


class MusicalTheoryBlueprint(BaseModel):
    key_root: str = Field(description="The root note of the key (e.g., C, D#, F)")
    scale: str = Field(description="The scale (major or minor)")
    bpm: int = Field(description="The tempo in Beats Per Minute")
    chord_progression: list[int] = Field(description="A list of integers representing the scale degrees of the chord progression (0-indexed, so 0 is the root chord, 3 is the IV chord, 4 is the V chord, etc.)")
    swing_factor: float = Field(description="The amount of swing to apply (0.0 to 0.3) to give it human feel")
    drum_pattern: DrumPatternBlueprint = Field(description="The 16-step drum pattern for the beat")
    reasoning: str = Field(description="A brief explanation of the musical choices made to achieve the requested mood and genre.")


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
        preferred_tags = (
            taste_profile.preferred_tags(rng, limit=2)
            if not self._has_explicit_genre_word(prompt) and not prompt_tags
            else []
        )
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
        prompt = state.get("prompt", "")
        genre = state.get("genre", "trap")
        mood = state.get("mood_analysis", {})
        critic_feedback = state.get("critic_feedback", "")
        retry_count = state.get("retry_count", 0)

        blueprint = self._query_theorist_llm(
            prompt=prompt,
            genre=genre,
            mood=mood,
            critic_feedback=critic_feedback,
            seed=seed + (retry_count * 101),
        )

        state["key_root"] = blueprint.key_root
        state["scale"] = blueprint.scale
        state["bpm"] = blueprint.bpm
        state["chord_progression"] = blueprint.chord_progression
        state["swing_factor"] = blueprint.swing_factor
        state["drum_pattern"] = {
            "kick": blueprint.drum_pattern.kick,
            "snare": blueprint.drum_pattern.snare,
            "hats": blueprint.drum_pattern.hats,
            "perc": blueprint.drum_pattern.perc,
        }
        return state

    def _query_theorist_llm(
        self, prompt: str, genre: str, mood: dict, critic_feedback: str, seed: int
    ) -> MusicalTheoryBlueprint:
        # The Startup Move: Temperature Control
        # High Temperature for artistic "Indie/Bollywood" experimentation
        # Low Temperature for corporate/background beats
        temperature = 0.7 if genre in {"hindi_indie", "bollywood", "house"} else 0.3
        
        system_prompt = f"""You are a master music producer.
Analyze the user's prompt and output ONLY valid JSON matching this schema:
{{
  "key_root": "C",
  "scale": "minor",
  "bpm": 92,
  "chord_progression": [0, 5, 3, 4],
  "swing_factor": 0.08,
  "drum_pattern": {{
    "kick": [0, 8, 12],
    "snare": [4, 12],
    "hats": [[0, false], [2, false], [4, false], [6, false], [8, false], [10, false], [12, false], [14, false]],
    "perc": [3, 7, 11]
  }},
  "reasoning": "short explanation"
}}

Rules:
- chord_progression must use 0-indexed scale degrees from 0 to 6 only.
- key_root must be one of C, C#, D, D#, E, F, F#, G, G#, A, A#, B.
- scale must be "major" or "minor".
- bpm must be between 70 and 160.
- hats must be a list of [step, is_open] pairs where step is 0-15 and is_open is true/false.
- Do not include markdown fences.

User Prompt: {prompt}
Target Genre: {genre}
Mood Valence: {mood.get('valence', 0.5)}
Mood Arousal: {mood.get('arousal', 0.5)}

{f"CRITIC FEEDBACK: {critic_feedback} (Please self-correct your draft based on this feedback)" if critic_feedback else ""}
"""
        api_key = os.environ.get("GROQ_API_KEY")
        if Groq and api_key:
            try:
                client = Groq(api_key=api_key)
                if instructor:
                    wrapped = instructor.from_groq(client)
                    blueprint = wrapped.chat.completions.create(
                        model="llama3-70b-8192",
                        response_model=MusicalTheoryBlueprint,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"Compose a beat for: {prompt}"}
                        ],
                        temperature=temperature,
                    )
                    return blueprint

                completion = client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Compose a beat for: {prompt}"}
                    ],
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
                content = completion.choices[0].message.content or "{}"
                return MusicalTheoryBlueprint.model_validate_json(content)
            except Exception as e:
                print(f"Groq LLM generation failed: {e}. Falling back to mock generator.")

        # Fallback simulated reasoning based on genre and mood
        rng = random.Random(seed)
        is_sad = mood.get("valence", 0.5) < 0.5
        scale = "minor" if is_sad else "major"
        key_root = rng.choice(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])
        
        if genre == "hindi_indie":
            prog = [0, 4, 5, 3] if not is_sad else [0, 5, 3, 4]
            kick, snare = [0, 10], [8]
            hats = [(0, False), (4, False), (8, False), (12, False)]
        elif genre == "house":
            prog = [0, 3, 4, 3] if is_sad else [0, 5, 3, 4]
            kick, snare = [0, 4, 8, 12], [4, 12]
            hats = [(2, False), (6, False), (10, False), (14, False)]
        else: # trap/drill default
            prog = [0, 3, 5, 4] if is_sad else [0, 4, 5, 3]
            kick, snare = [0, 7, 10, 12], [4, 12]
            hats = [(i, False) for i in range(0, 16, 2)]

        return MusicalTheoryBlueprint(
            key_root=key_root,
            scale=scale,
            bpm=rng.randint(80, 150),
            chord_progression=prog,
            swing_factor=0.15 if genre in {"boom_bap", "lofi"} else 0.05,
            drum_pattern=DrumPatternBlueprint(
                kick=kick,
                snare=snare,
                hats=hats,
                perc=[3, 7, 11]
            ),
            reasoning=f"Selected {key_root} {scale} to match the {'sad' if is_sad else 'happy'} mood. Adjusted temperature to {temperature} for {genre}."
        )

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
        
        # 1. Semantic Search for Synth Presets
        preset_lib = SemanticPresetLibrary()
        mood_str = "dark moody" if mood.get("valence", 0.5) < 0.5 else "bright happy"
        energy_str = "aggressive loud" if mood.get("arousal", 0.5) > 0.6 else "soft chill"
        chords_query = f"{genre} {mood_str} {energy_str} chords piano synth {state.get('prompt', '')}"
        lead_query = f"{genre} {mood_str} {energy_str} lead melody pad {state.get('prompt', '')}"
        
        chords_preset = preset_lib.search(chords_query, top_k=1)[0]
        lead_preset = preset_lib.search(lead_query, top_k=1)[0]
        
        if lead_preset["id"] == chords_preset["id"]:
            lead_fallback = preset_lib.search(lead_query, top_k=2)
            if len(lead_fallback) > 1:
                lead_preset = lead_fallback[1]

        state["synth_presets"] = {
            "chords": chords_preset["params"],
            "lead": lead_preset["params"]
        }
        
        return state

    def _critic_node(self, state: MusicState) -> MusicState:
        feedback: list[str] = []
        approved = True
        progression = state.get("chord_progression", [])
        key_root = state.get("key_root", "C")
        scale = state.get("scale", "minor")
        drum_pattern = state.get("drum_pattern", {})
        genre = state.get("genre", "trap")
        mood = state.get("mood_analysis", {"valence": 0.5, "arousal": 0.5})

        # 1. Run theory validation (The Critic's Ear)
        is_valid, error = validate_chords(key_root, scale, progression, genre=genre)
        
        if not is_valid:
            approved = False
            feedback.append(f"The previous chord progression was invalid: {error}. Please generate a new one.")

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
            if "hindi_indie" in set(tags) or "aditya_rikhari_like" in set(tags):
                return "hindi_indie"
            return "lofi"
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

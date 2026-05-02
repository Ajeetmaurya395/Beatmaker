import json
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    SentenceTransformer = None
    cosine_similarity = None

# A mock database of detailed synth parameters.
# In a real app, this would be loaded from a JSON/Vector DB.
PRESET_DB = [
    {
        "id": "warm_lofi_rhodes",
        "description": "Warm lofi rhodes electric piano with soft attack and tremolo. Perfect for jazz, chillhop, and late night study beats.",
        "params": {"wave": "sine", "attack": 0.08, "decay": 0.3, "sustain": 0.5, "release": 0.6, "tremolo": 0.2, "harmonics": 2, "detune": 0.002, "brightness": 0.4}
    },
    {
        "id": "moody_grand_piano",
        "description": "A dark, moody acoustic grand piano with strong fundamentals and soft highs. Great for emotional or sad beats.",
        "params": {"wave": "sine", "attack": 0.02, "decay": 0.45, "sustain": 0.25, "release": 0.5, "tremolo": 0.0, "harmonics": 3, "detune": 0.001, "brightness": 0.5}
    },
    {
        "id": "aggressive_supersaw",
        "description": "Aggressive, wide, and bright supersaw lead. Ideal for hard trap, drill, phonk, or high-energy club bounce.",
        "params": {"wave": "saw", "attack": 0.01, "decay": 0.2, "sustain": 0.6, "release": 0.3, "tremolo": 0.0, "harmonics": 6, "detune": 0.012, "brightness": 0.9}
    },
    {
        "id": "hindi_indie_acoustic",
        "description": "Soft nylon string acoustic guitar pluck. Very intimate and organic. Ideal for romantic aditya rikhari style hindi indie.",
        "params": {"wave": "triangle", "attack": 0.04, "decay": 0.35, "sustain": 0.1, "release": 0.4, "tremolo": 0.0, "harmonics": 4, "detune": 0.003, "brightness": 0.6}
    },
    {
        "id": "bollywood_string_ensemble",
        "description": "Rich sweeping Bollywood string ensemble pad. Wide, dramatic, and emotional.",
        "params": {"wave": "saw", "attack": 0.15, "decay": 0.2, "sustain": 0.85, "release": 0.5, "tremolo": 0.1, "harmonics": 5, "detune": 0.008, "brightness": 0.75}
    },
    {
        "id": "shimmering_house_pad",
        "description": "Bright digital shimmering pad. Perfect for dance, summer party, and house beats.",
        "params": {"wave": "square", "attack": 0.05, "decay": 0.15, "sustain": 0.7, "release": 0.4, "tremolo": 0.05, "harmonics": 8, "detune": 0.005, "brightness": 0.85}
    },
    {
        "id": "dark_drone_bass",
        "description": "A slow, evolving dark drone pad. Good for cinematic or very moody drill backgrounds.",
        "params": {"wave": "sine", "attack": 0.4, "decay": 0.3, "sustain": 0.8, "release": 0.8, "tremolo": 0.02, "harmonics": 2, "detune": 0.004, "brightness": 0.3}
    }
]


class SemanticPresetLibrary:
    def __init__(self):
        self.presets = PRESET_DB
        self.model = None
        self.embeddings = None

    def _initialize_model(self):
        if not SentenceTransformer:
            print("Warning: sentence-transformers not installed. Semantic search disabled.")
            return

        if self.model is None:
            # Load a tiny, fast embedding model (downloads ~20MB on first run)
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            descriptions = [p["description"] for p in self.presets]
            self.embeddings = self.model.encode(descriptions)

    def search(self, query: str, top_k: int = 1) -> list[dict]:
        """Perform semantic vector search for the best preset."""
        if not SentenceTransformer:
            # Fallback to simple keyword matching if vector library not installed
            return self._keyword_search(query, top_k)

        self._initialize_model()
        query_emb = self.model.encode([query])
        similarities = cosine_similarity(query_emb, self.embeddings)[0]
        
        # Sort by similarity
        best_indices = similarities.argsort()[-top_k:][::-1]
        
        results = []
        for idx in best_indices:
            preset = self.presets[idx].copy()
            preset["score"] = float(similarities[idx])
            results.append(preset)
            
        return results

    def _keyword_search(self, query: str, top_k: int) -> list[dict]:
        """Dumb fallback if ML libraries are unavailable."""
        query_words = set(query.lower().split())
        scored = []
        for preset in self.presets:
            desc_words = set(preset["description"].lower().split())
            score = len(query_words.intersection(desc_words))
            scored.append((score, preset))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for s, p in scored[:top_k]]

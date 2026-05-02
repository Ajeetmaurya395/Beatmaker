from __future__ import annotations

try:
    import music21
except Exception:
    music21 = None


def validate_chords(key_root: str, scale: str, progression: list[int], genre: str = "trap") -> tuple[bool, str]:
    """
    Validates if the chord progression fits the key.
    Accepts the engine's 0-indexed degrees (0-6).
    Returns (is_valid, error_message).
    """
    if not progression:
        return False, "Chord progression is empty."

    for degree in progression:
        if degree < 0 or degree > 6:
            return False, f"Degree {degree} is out of bounds for a 0-indexed scale (must be 0-6)."

    if music21 is None:
        return True, "music21 unavailable; skipped strict harmony validation."

    try:
        key_obj = music21.key.Key(key_root, scale.lower())
        for degree in progression:
            pitch = key_obj.pitchFromDegree(degree + 1)
            if pitch is None:
                return False, f"Chord degree {degree} produced an invalid pitch in {key_root} {scale}."
        if genre in {"hindi_indie", "bollywood"} and len(set(progression)) < 2:
            return False, "Progression is too static for the requested genre."
        return True, ""
    except Exception as exc:
        return False, f"Music Theory Error: {exc}"

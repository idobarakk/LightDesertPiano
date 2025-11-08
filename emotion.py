"""
Emotion mapping between harmony and visuals.

We keep a tiny 4D vector (joy, melancholy, tension, blues) that summarizes
the emotional feel. Chords push it quickly; scales (key) nudge it slowly.
This vector then biases colors and accent strength without hard jumps.
"""

from typing import Tuple, Optional, Dict
from config import (
    EMOTION_CHORD_VECTORS,
    EMOTION_SCALE_VECTORS,
    EMOTION_CHORD_WEIGHT,
    EMOTION_SCALE_WEIGHT,
)


# Emotion vector: (joy, melancholy, tension, blues)
Emotion = Tuple[float, float, float, float]


# Chord qualities to emotion contributions (imported from config)
CHORD_TO_VEC: Dict[str, Emotion] = EMOTION_CHORD_VECTORS


# Scale/mode to emotion contributions (imported from config)
SCALE_TO_VEC: Dict[str, Emotion] = EMOTION_SCALE_VECTORS


def _normalize(v: Emotion) -> Emotion:
    """Ensure the vector sums to 1 (if non-zero), for consistent blending."""
    s = sum(v)
    if s <= 1e-9:
        return (0.0, 0.0, 0.0, 0.0)
    return (v[0] / s, v[1] / s, v[2] / s, v[3] / s)


def ema(old: Emotion, target: Emotion, alpha: float) -> Emotion:
    """Exponential moving average for smooth emotional changes."""
    return (
        old[0] + alpha * (target[0] - old[0]),
        old[1] + alpha * (target[1] - old[1]),
        old[2] + alpha * (target[2] - old[2]),
        old[3] + alpha * (target[3] - old[3]),
    )


def combine(chord_quality: Optional[str], scale_mode: Optional[str], w_chord: float = EMOTION_CHORD_WEIGHT, w_scale: float = EMOTION_SCALE_WEIGHT) -> Emotion:
    """Combine chord and scale contributions into a target emotion vector.

    - chord_quality: 'maj', 'min', 'dom7', etc., or None
    - scale_mode: 'major', 'minor', 'blues', etc., or None
    - weights tune how strongly chord vs scale affect the target.
    """
    chord_vec = CHORD_TO_VEC.get(chord_quality, (0.0, 0.0, 0.0, 0.0))
    scale_vec = SCALE_TO_VEC.get(scale_mode, (0.0, 0.0, 0.0, 0.0))
    weighted = (
        w_chord * chord_vec[0] + w_scale * scale_vec[0],
        w_chord * chord_vec[1] + w_scale * scale_vec[1],
        w_chord * chord_vec[2] + w_scale * scale_vec[2],
        w_chord * chord_vec[3] + w_scale * scale_vec[3],
    )
    return _normalize(weighted)


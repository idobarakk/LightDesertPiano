"""
Harmony utilities: detect the chord you are holding right now (fast) and the
overall key/scale you are implying over the last few seconds (slow).

Concepts in plain terms:
- A chord is the current shape under the fingers (e.g., Major, Minor, 7th).
  We detect it quickly but only accept a change if it is stable for a short
  time (to avoid flicker during transitions) and we hold it briefly once
  accepted (so visuals feel intentional).
- A scale (or key center) is the "atmosphere" suggested by recent notes.
  We estimate it over a 2–4s window so the background color feels coherent.

Returned types use pitch class numbers (0..11) where 0=C, 1=C#, 2=D, ... 11=B.
"""

from collections import deque
from typing import Dict, Tuple, Optional, Deque, List
from enum import IntEnum
import time


class PitchClass(IntEnum):
    """Named pitch classes so roots are readable (C=0 .. B=11)."""
    C = 0
    C_SHARP = 1
    D = 2
    D_SHARP = 3
    E = 4
    F = 5
    F_SHARP = 6
    G = 7
    G_SHARP = 8
    A = 9
    A_SHARP = 10
    B = 11


Chord = Tuple[PitchClass, str, float]  # (root, quality, confidence)
Scale = Tuple[PitchClass, str, float]  # (root, mode, confidence)


# Chord definitions are inversion-invariant interval sets from the root.
QUALITY_INTERVALS = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "dom7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
}


# Scale templates are sets of notes relative to a root.
SCALE_TEMPLATES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],  # natural minor (aeolian)
    "major_pent": [0, 2, 4, 7, 9],
    "minor_pent": [0, 3, 5, 7, 10],
    "blues": [0, 3, 5, 6, 7, 10],
}


def _pitch_classes(active_notes: Dict[int, int]) -> Dict[int, int]:
    """Collapse absolute MIDI notes to pitch classes 0..11.

    Keeps the maximum velocity observed per pitch class, so strong notes weigh
    more when scoring chords.
    """
    pcs: Dict[int, int] = {}
    for note, vel in active_notes.items():
        pc = note % 12
        pcs[pc] = max(pcs.get(pc, 0), vel)
    return pcs


def _score_quality_for_root(pcs: Dict[int, int], root_pc: int, intervals: List[int]) -> float:
    """Score how well current pitch classes match a chord built on root_pc.

    The score blends:
    - coverage: fraction of required chord tones present
    - precision: fraction of sounding pcs that belong to the chord set
    """
    hits = 0
    total = len(intervals)
    for iv in intervals:
        pc = (root_pc + iv) % 12
        if pc in pcs:
            hits += 1
    coverage = hits / max(total, 1)
    # Weight by how many active pcs belong to the chord set (precision)
    chord_set = { (root_pc + iv) % 12 for iv in intervals }
    precision = sum(1 for pc in pcs if pc in chord_set) / max(len(pcs), 1)
    return 0.7 * coverage + 0.3 * precision


def detect_chord(active_notes: Dict[int, int], now: Optional[float] = None) -> Optional[Chord]:
    """Detect the current chord from the held notes.

    - Input: dict of MIDI note -> velocity for active (held) notes
    - Output: (root_pc, quality, confidence) or None if not enough info
    - We try each present pitch class as a root and score qualities in
      QUALITY_INTERVALS; we also test the bass note as root hint.
    """
    if not active_notes or len(active_notes) < 2:
        return None
    pcs = _pitch_classes(active_notes)
    if len(pcs) < 2:
        return None

    # Use lowest note as root hint if available
    bass_note = min(active_notes.keys()) if active_notes else None
    bass_pc = (bass_note % 12) if bass_note is not None else None  # low note hints root

    best: Optional[Chord] = None
    # Try each present pc as a root candidate, try all qualities
    candidates = set(pcs.keys())
    if bass_pc is not None:
        candidates.add(bass_pc)

    for root_pc in candidates:
        for quality, intervals in QUALITY_INTERVALS.items():
            score = _score_quality_for_root(pcs, root_pc, intervals)  # coverage+precision
            # Require at least a triad coverage ~0.5
            if score < 0.5:
                continue
            if best is None or score > best[2]:
                best = (PitchClass(root_pc), quality, score)

    return best


def _pc_histogram(events: Deque[Tuple[float, int, bool, int]], now: float, window_s: float) -> List[float]:
    """Build a recency-weighted histogram of pitch classes over a time window."""
    hist = [0.0] * 12
    cutoff = now - window_s
    for ts, note, is_on, vel in events:
        if ts < cutoff:
            continue
        if is_on:
            pc = note % 12
            # recency-weighting: linear decay
            w = max(0.0, (ts - cutoff) / window_s)
            hist[pc] += (vel / 127.0) * (0.5 + 0.5 * w)
    return hist


def _rotate_template(template: List[int], root_pc: int) -> set:
    # Shift a scale template to a given root pitch class
    return { (root_pc + t) % 12 for t in template }


def detect_scale(events: Deque[Tuple[float, int, bool, int]], now: Optional[float] = None, window_s: float = 3.0) -> Optional[Scale]:
    """Estimate the current key/scale from recent notes.

    - Input: recent events deque, now timestamp, and window size (seconds)
    - Output: (root_pc, mode, confidence) with confidence in [0..1]
    - Method: match a histogram of recent pitch classes to a small set of
      templates (Major, Minor, Pentatonic, Blues) across 12 roots.
    """
    if now is None:
        now = time.time()
    if not events:
        return None
    hist = _pc_histogram(events, now, window_s)
    if sum(hist) < 1e-6:
        return None

    best: Optional[Scale] = None
    for mode, templ in SCALE_TEMPLATES.items():
        for root_pc in range(12):  # test all possible roots C..B
            templ_set = _rotate_template(templ, root_pc)
            in_sum = sum(hist[pc] for pc in templ_set)
            total = sum(hist)
            coverage = in_sum / total
            if best is None or coverage > best[2]:
                best = (PitchClass(root_pc), mode, coverage)
    return best


class ChordTracker:
    """Maintains chord stability and hold logic.

    Purpose: avoid flicker when the player transitions between chords.

    - stability_ms: candidate chord must persist for at least this duration
      before we accept it as "the chord".
    - hold_ms: once a chord is accepted, keep it at least this long before
      allowing a change, unless the new chord is much more confident.
    """

    def __init__(self, stability_ms: int = 300, hold_ms: int = 800):
        self.stability_ms = stability_ms
        self.hold_ms = hold_ms
        self.current: Optional[Chord] = None
        self.candidate: Optional[Chord] = None
        self.candidate_since: Optional[float] = None
        self.last_change: Optional[float] = None

    def update(self, active_notes: Dict[int, int], now: Optional[float] = None) -> Tuple[Optional[Chord], bool]:
        """Update tracker with current active notes and return (chord, changed).

        - chord: (root_pc, quality, confidence) or None
        - changed: True only when we accept a new chord (for triggering accents)
        """
        if now is None:
            now = time.time()
        cand = detect_chord(active_notes, now)
        changed = False
        if cand is None:
            # allow decay but keep current until silence persists
            self.candidate = None
            self.candidate_since = None
            return self.current, changed

        if self.candidate is None or cand[:2] != (self.candidate[0], self.candidate[1]):
            self.candidate = cand
            self.candidate_since = now
        else:
            # same candidate continues; check stability window
            if (now - (self.candidate_since or now)) * 1000 >= self.stability_ms:
                # respect hold time before switching away from current
                if self.current is None or (now - (self.last_change or 0)) * 1000 >= self.hold_ms:
                    if self.current is None or cand[2] >= (self.current[2] + 0.05):
                        if self.current is None or (cand[0], cand[1]) != (self.current[0], self.current[1]):
                            changed = True
                        self.current = cand
                        self.last_change = now
        return self.current, changed


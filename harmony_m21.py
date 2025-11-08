"""
music21-powered chord/scale tracker for real-time ticks.

Design goals:
- Update every tick with the current snapshot of active notes (like existing engine).
- Be robust to inversions and left-hand bass with right-hand arpeggios.
- Keep latency tiny: use short arpeggio latch for chord; use sliding window for key.

API:
- ChordTrackerM21.update(active_notes: Dict[int, int], now: float | None) -> (Chord|None, changed: bool)
- ChordTrackerM21.scale: Optional[Scale] is kept up-to-date internally

Notes:
- active_notes is a snapshot; to better capture arpeggios, we internally latch
  newly pressed notes for a very short window (e.g., 300 ms) and include them
  when building the chord sent to music21. This avoids changing the engine API.
- Key detection uses a separate 2–4s window of recent note-on events and
  music21's key analyzer.
"""

from typing import Dict, Optional, Tuple, Deque, List
from collections import deque
import time

try:
    from music21 import note as m21_note
    from music21 import chord as m21_chord
    from music21 import stream as m21_stream
except Exception:  # pragma: no cover - runtime guard if music21 missing
    m21_note = None  # type: ignore
    m21_chord = None  # type: ignore
    m21_stream = None  # type: ignore

from harmony import PitchClass, Chord, Scale
from config import (
    CHORD_MIN_PITCH_CLASSES,
    SCALE_MIN_PITCH_CLASSES,
    CHORD_STABILITY_MS,
    CHORD_HOLD_MS,
    CHORD_ARPEGGIO_WINDOW_MS,
    CHORD_M21_SCALE_WINDOW_S,
    ENGINE_SCALE_REFRESH_INTERVAL_S,
)


_M21_KIND_TO_QUALITY = {
    'major': 'maj',
    'minor': 'min',
    'dominant-seventh': 'dom7',
    'major-seventh': 'maj7',
    'minor-seventh': 'min7',
    'suspended-second': 'sus2',
    'suspended-fourth': 'sus4',
    'diminished': 'dim',
    'augmented': 'aug',
}


def _quality_from_m21(ch: "m21_chord.Chord") -> Optional[str]:
    # Prefer robust parsing from commonName (available across music21 versions)
    s = (getattr(ch, 'commonName', None) or '').lower()
    if not s:
        return None
    if 'dominant seventh' in s:
        return 'dom7'
    if 'major seventh' in s:
        return 'maj7'
    if 'minor seventh' in s:
        return 'min7'
    if 'diminished' in s:
        return 'dim'
    if 'augmented' in s:
        return 'aug'
    if 'suspended second' in s or 'sus2' in s:
        return 'sus2'
    if 'suspended fourth' in s or 'sus4' in s:
        return 'sus4'
    if 'minor' in s:
        return 'min'
    if 'major' in s:
        return 'maj'
    return None


def _m21_chord_from_midis(midi_notes: List[int]):
    if m21_chord is None or m21_note is None or not midi_notes:
        return None
    return m21_chord.Chord([m21_note.Note(n) for n in midi_notes])


class ChordTrackerM21:
    """music21-backed chord tracker with stability/hold and key estimation.

    - stability_ms: candidate must persist this long before acceptance
    - hold_ms: hold accepted chord at least this long before next change
    - chord_arp_window_ms: include note-ons from the recent short window to
      capture arpeggios when forming the music21 chord input
    - scale_window_s: length of sliding window for key detection
    """

    def __init__(
        self,
        stability_ms: int = CHORD_STABILITY_MS,
        hold_ms: int = CHORD_HOLD_MS,
        chord_arp_window_ms: int = CHORD_ARPEGGIO_WINDOW_MS,
        scale_window_s: float = CHORD_M21_SCALE_WINDOW_S,
    ):
        self.stability_ms = stability_ms
        self.hold_ms = hold_ms
        self.chord_arp_window_ms = chord_arp_window_ms
        self.scale_window_s = scale_window_s

        self.current: Optional[Chord] = None
        self.candidate: Optional[Tuple[PitchClass, str]] = None
        self.candidate_since: Optional[float] = None
        self.last_change: Optional[float] = None

        # For detecting new note-ons from snapshots
        self._prev_active: set[int] = set()

        # Short arpeggio latch and longer key window
        self._arp_notes: Deque[Tuple[float, int]] = deque(maxlen=256)
        self._key_notes: Deque[Tuple[float, int]] = deque(maxlen=2048)

        self.scale: Optional[Scale] = None
        self._last_scale_refresh: float = 0.0
        self._scale_refresh_s: float = ENGINE_SCALE_REFRESH_INTERVAL_S

    def _ingest_snapshot(self, active_notes: Dict[int, int], now: float) -> None:
        current_set = set(active_notes.keys())
        new_on = [n for n in current_set if n not in self._prev_active]
        if new_on:
            for n in new_on:
                self._arp_notes.append((now, n))
                self._key_notes.append((now, n))
        self._prev_active = current_set

        # Trim windows
        arp_cutoff = now - (self.chord_arp_window_ms / 1000.0)
        while self._arp_notes and self._arp_notes[0][0] < arp_cutoff:
            self._arp_notes.popleft()
        key_cutoff = now - self.scale_window_s
        while self._key_notes and self._key_notes[0][0] < key_cutoff:
            self._key_notes.popleft()

    def _detect_chord(self, active_notes: Dict[int, int], now: float) -> Optional[Chord]:
        if m21_chord is None:
            return None
        # Build union of current actives + arpeggio latch, but require distinct pitch classes
        midi_notes: List[int] = list(active_notes.keys())
        midi_notes.extend(n for _, n in self._arp_notes)
        pcs = sorted({ n % 12 for n in midi_notes })
        # Require minimum distinct pitch classes to avoid ambiguity
        if len(pcs) < CHORD_MIN_PITCH_CLASSES:
            return None
        # Normalize to single octave to improve analysis stability
        norm_midis = [60 + pc for pc in pcs]  # C4-based
        ch = _m21_chord_from_midis(norm_midis)
        if ch is None:
            return None
        try:
            root_pitch = ch.root()
        except Exception:
            root_pitch = None
        if root_pitch is None:
            return None
        root_pc = PitchClass(root_pitch.midi % 12)
        quality = _quality_from_m21(ch) or 'maj'
        return (root_pc, quality, 1.0)

    def _maybe_refresh_scale(self, now: float) -> None:
        if m21_stream is None:
            return
        if now - self._last_scale_refresh < self._scale_refresh_s:
            return
        midi_notes = [n for _, n in self._key_notes]
        if not midi_notes:
            self.scale = None
            self._last_scale_refresh = now
            return
        uniq_pcs = {n % 12 for n in midi_notes}
        # Require enough diversity to avoid spurious key flips
        if len(uniq_pcs) < SCALE_MIN_PITCH_CLASSES:
            self._last_scale_refresh = now
            return
        try:
            s = m21_stream.Stream([m21_note.Note(n) for n in midi_notes])
            k = s.analyze('key')
            tonic_pc = PitchClass(k.tonic.midi % 12)
            mode = k.mode if k.mode in ('major', 'minor') else ('major' if k.mode == 'ionian' else 'minor')
            # Tie-break with current chord to reduce relative major/minor flips
            if self.current is not None:
                chord_root, chord_quality, _ = self.current
                if isinstance(chord_root, PitchClass):
                    if chord_quality in ('min', 'min7'):
                        # Prefer minor on chord root if detected key is relative major
                        rel_major_pc = PitchClass((int(chord_root) + 3) % 12)
                        if mode == 'major' and tonic_pc == rel_major_pc:
                            tonic_pc = chord_root
                            mode = 'minor'
                    elif chord_quality in ('maj', 'maj7', 'dom7'):
                        # Prefer major on chord root if detected key is relative minor
                        rel_minor_pc = PitchClass((int(chord_root) + 9) % 12)
                        if mode == 'minor' and tonic_pc == rel_minor_pc:
                            tonic_pc = chord_root
                            mode = 'major'
            self.scale = (tonic_pc, mode, 1.0)
        except Exception:
            # leave previous scale if analysis fails
            pass
        finally:
            self._last_scale_refresh = now

    def update(self, active_notes: Dict[int, int], now: Optional[float] = None) -> Tuple[Optional[Chord], bool]:
        if now is None:
            now = time.time()

        # Ingest snapshot and maintain windows
        self._ingest_snapshot(active_notes, now)

        detected = self._detect_chord(active_notes, now)
        self._maybe_refresh_scale(now)

        changed = False
        if detected is None:
            # Clear candidate when insufficient info; keep current
            self.candidate = None
            self.candidate_since = None
            return self.current, changed

        root_quality = (detected[0], detected[1])
        if self.candidate is None or self.candidate != root_quality:
            self.candidate = root_quality
            self.candidate_since = now
            return self.current, changed

        # Candidate continues — check stability
        if self.candidate_since is None or (now - self.candidate_since) * 1000 < self.stability_ms:
            return self.current, changed

        # Hold rule
        if self.last_change is not None and (now - self.last_change) * 1000 < self.hold_ms:
            return self.current, changed

        # Accept
        prev_root_quality = None if self.current is None else (self.current[0], self.current[1])
        changed = prev_root_quality != root_quality
        self.current = (detected[0], detected[1], 1.0)
        self.last_change = now
        return self.current, changed



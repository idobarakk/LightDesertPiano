import mido
from collections import deque, Counter
from typing import List, Tuple

from music21 import note as m21_note, chord as m21_chord, stream as m21_stream


MIDI_PATH = "midi_player/midi_files/coldplay.mid"
CAPTURE_SECONDS = 10.0
ARP_WINDOW_S = 0.6
STEP_S = 0.25


def collect_first_10s_notes(path: str) -> List[Tuple[float, int]]:
    mid = mido.MidiFile(path)
    t = 0.0
    events: List[Tuple[float, int]] = []  # (time_s, midi_note) for note_on
    for msg in mid:  # respects .time as delta seconds
        t += msg.time
        if msg.type == 'note_on' and getattr(msg, 'velocity', 0) > 0:
            events.append((t, msg.note))
        if t >= CAPTURE_SECONDS:
            break
    return events


def analyze_key(events: List[Tuple[float, int]]):
    if not events:
        return None
    notes = [m21_note.Note(n) for _, n in events]
    s = m21_stream.Stream(notes)
    try:
        k = s.analyze('key')
        return f"{k.tonic.name} {k.mode}"
    except Exception:
        return None


def detect_chord_in_window(events: List[Tuple[float, int]], center_t: float, window_s: float):
    lo = center_t - window_s
    pcs = sorted({ n % 12 for t, n in events if t >= lo and t <= center_t })
    if len(pcs) < 3:
        return None
    # normalize to single octave for stable analysis
    norm_midis = [60 + pc for pc in pcs]
    ch = m21_chord.Chord([m21_note.Note(n) for n in norm_midis])
    try:
        root = ch.root()
    except Exception:
        return None
    if root is None:
        return None
    common = (ch.commonName or '').lower()
    # craft a simple label
    if 'minor seventh' in common:
        qual = 'min7'
    elif 'major seventh' in common:
        qual = 'maj7'
    elif 'dominant seventh' in common:
        qual = 'dom7'
    elif 'minor' in common:
        qual = 'min'
    elif 'major' in common:
        qual = 'maj'
    elif 'diminished' in common:
        qual = 'dim'
    elif 'augmented' in common:
        qual = 'aug'
    else:
        qual = common or '-'
    return f"{root.name} {qual}"


def main():
    events = collect_first_10s_notes(MIDI_PATH)
    if not events:
        print("No events captured.")
        return

    # Chronological event list
    print("=== First 10s events (note_on) ===")
    for t, n in events:
        try:
            name = m21_note.Note(n).nameWithOctave
        except Exception:
            name = str(n)
        print(f"t={t:6.3f}s  {name:>4} ({n})")
    print(f"Total events: {len(events)}\n")

    # Aggregate notes
    all_notes = [n for _, n in events]
    pcs = [n % 12 for n in all_notes]
    pc_names = [m21_note.Note(60 + pc).name for pc in pcs]
    counts = Counter(pc_names)
    print("=== First 10s note summary ===")
    print("Unique MIDI notes:", sorted(set(all_notes)))
    print("Pitch-class counts:", dict(sorted(counts.items())))

    # Key over first 10 seconds
    key = analyze_key(events)
    print("Estimated key (first 10s):", key)

    # Chord timeline (every STEP_S)
    print("\n=== Chord timeline (every %.2fs, window %.2fs) ===" % (STEP_S, ARP_WINDOW_S))
    t_start = events[0][0]
    t_end = min(CAPTURE_SECONDS, events[-1][0])
    t = STEP_S
    while t <= t_end:
        ch = detect_chord_in_window(events, t, ARP_WINDOW_S)
        label = ch or '-'
        print(f"t={t:5.2f}s  chord={label}")
        t += STEP_S


if __name__ == "__main__":
    main()



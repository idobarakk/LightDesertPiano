import time
from collections import deque

from harmony_m21 import ChordTrackerM21
from harmony import PitchClass


def simulate_event_stream(seqs, step_s=0.1, title: str = ""):
    """seqs: list of (duration_s, notes_this_step: list[int])

    Prints a header for clarity and a summary after the run.
    Returns a dict with unique chords/keys observed and last values.
    """
    if title:
        print(f"\n=== {title} ===")
    tracker = ChordTrackerM21(stability_ms=60, hold_ms=180, chord_arp_window_ms=350, scale_window_s=3.0)
    t0 = time.time()
    now = t0
    seen_chords, seen_keys = [], []
    for dur, notes in seqs:
        steps = max(1, int(dur / step_s))
        for _ in range(steps):
            now = time.time()
            # Build active snapshot for this step (simulate held notes)
            active = {n: 100 for n in notes}
            chord, _changed = tracker.update(active, now)
            key = tracker.scale

            def pc_name(pc):
                return PitchClass(pc).name.replace('_SHARP', '#') if pc is not None else '-'

            chord_str = '-'
            if chord:
                chord_str = f"{pc_name(chord[0])} {chord[1]}"

            key_str = '-'
            if key:
                key_str = f"{pc_name(key[0])} {key[1]}"

            print(f"notes={notes} | chord={chord_str} | key={key_str}")
            if chord_str != '-':
                seen_chords.append(chord_str)
            if key_str != '-':
                seen_keys.append(key_str)
            time.sleep(step_s)

    # Summary
    last_chord = seen_chords[-1] if seen_chords else '-'
    last_key = seen_keys[-1] if seen_keys else '-'
    uniq_chords = sorted(set(seen_chords))
    uniq_keys = sorted(set(seen_keys))
    print("--- Summary:")
    print(f"Chords observed: {uniq_chords}")
    print(f"Keys observed:   {uniq_keys}")
    print(f"Final chord/key: {last_chord} | {last_key}")
    return {
        'chords': uniq_chords,
        'keys': uniq_keys,
        'last_chord': last_chord,
        'last_key': last_key,
    }


def simulate_lh_rh(left_hand_notes, right_sequences, step_s=0.2, title: str = ""):
    """Simulate held left-hand chord with right-hand arpeggio patterns.

    - left_hand_notes: list[int] held across all steps
    - right_sequences: list of tuples (duration_s, right_notes_this_step)
    """
    if title:
        print(f"\n=== {title} ===")
    tracker = ChordTrackerM21(stability_ms=60, hold_ms=180, chord_arp_window_ms=350, scale_window_s=3.0)
    now = time.time()
    seen_chords, seen_keys = [], []
    for dur, right_notes in right_sequences:
        steps = max(1, int(dur / step_s))
        for _ in range(steps):
            now = time.time()
            active = {n: 100 for n in (list(left_hand_notes) + list(right_notes))}
            chord, _ = tracker.update(active, now)
            key = tracker.scale

            def pc_name(pc):
                return PitchClass(pc).name.replace('_SHARP', '#') if pc is not None else '-'

            chord_str = '-'
            if chord:
                chord_str = f"{pc_name(chord[0])} {chord[1]}"

            key_str = '-'
            if key:
                key_str = f"{pc_name(key[0])} {key[1]}"

            print(f"LH={left_hand_notes} RH={right_notes} | chord={chord_str} | key={key_str}")
            if chord_str != '-':
                seen_chords.append(chord_str)
            if key_str != '-':
                seen_keys.append(key_str)
            time.sleep(step_s)
    # Summary
    last_chord = seen_chords[-1] if seen_chords else '-'
    last_key = seen_keys[-1] if seen_keys else '-'
    uniq_chords = sorted(set(seen_chords))
    uniq_keys = sorted(set(seen_keys))
    print("--- Summary:")
    print(f"Chords observed: {uniq_chords}")
    print(f"Keys observed:   {uniq_keys}")
    print(f"Final chord/key: {last_chord} | {last_key}")
    return {
        'chords': uniq_chords,
        'keys': uniq_keys,
        'last_chord': last_chord,
        'last_key': last_key,
    }


def main():
    # Test 1: E minor arpeggio then block chord
    seqs = [
        (1.2, [47]),   # B
        (1.2, [52]),   # E
        (1.2, [55]),   # G
        (1.2, [47, 52, 55]),  # block chord
    ]
    simulate_event_stream(seqs, step_s=0.2, title="Test 1: Single-hand arpeggio (E minor)")

    print("---")
    # Test 2: A minor arpeggio
    seqs2 = [
        (1.0, [57]),
        (1.0, [60]),
        (1.0, [64]),
        (1.0, [57, 60, 64]),
    ]
    simulate_event_stream(seqs2, step_s=0.2, title="Test 2: Single-hand arpeggio (A minor)")

    print("--- LH/RH ---")
    # Left hand E minor low, right hand arpeggiates E minor triad high
    lh = [40, 43, 47]  # E2, G2, B2
    rh_seq = [
        (1.0, [64]),      # E4
        (1.0, [67]),      # G4
        (1.0, [71]),      # B4
        (1.0, [64, 67, 71]),  # block RH triad
        (1.0, [71, 67, 64]),  # descending arpeggio
    ]
    simulate_lh_rh(lh, rh_seq, step_s=0.2, title="Test 3: Held LH chord + RH arpeggio (E minor)")

    print("--- Mixed ranges (no LH/RH knowledge) ---")
    # Interleave low and high notes without holding LH explicitly; rely on arp latch
    mixed_seq = [
        (0.8, [40]),   # E2
        (0.8, [71]),   # B4
        (0.8, [43]),   # G2
        (0.8, [64]),   # E4
        (0.8, [47]),   # B2
        (0.8, [67]),   # G4
        (1.2, [40, 43, 47, 64, 67, 71]),  # cluster
    ]
    simulate_event_stream(mixed_seq, step_s=0.2, title="Test 4: Mixed ranges (no LH/RH knowledge)")

    print("--- Inversions (E min): E-G-B, G-B-E, B-E-G ---")
    inversions = [
        (1.0, [40, 43, 47]),  # E-G-B
        (1.0, [43, 47, 52]),  # G-B-E
        (1.0, [47, 52, 55]),  # B-E-G
        (1.0, [40, 43, 47]),
    ]
    simulate_event_stream(inversions, step_s=0.2, title="Test 5: Inversions (E-G-B, G-B-E, B-E-G)")

    print("\n=== Long key identification streams ===")
    # Helper: simulate longer one-note steps drawn from a scale
    def simulate_key_stream(root_name: str, mode: str, start_midi: int, steps: int, step_s: float, title: str):
        # Build scale MIDI set over a couple octaves
        # Supported: minor (aeolian), major (ionian)
        if mode == 'minor':
            intervals = [0, 2, 3, 5, 7, 8, 10]
        else:
            intervals = [0, 2, 4, 5, 7, 9, 11]
        scale_notes = []
        for octave in range(0, 3):
            base = start_midi + 12 * octave
            for iv in intervals:
                n = base + iv
                if 36 <= n <= 84:
                    scale_notes.append(n)

        # Build sequence rotating through scale tones
        seq = []
        idx = 0
        for _ in range(steps):
            seq.append((step_s, [scale_notes[idx % len(scale_notes)]]))
            idx += 1

        simulate_event_stream(seq, step_s=step_s, title=title)

    # Test 6: E natural minor long stream
    simulate_key_stream('E', 'minor', start_midi=40, steps=40, step_s=0.15, title='Test 6: Long stream in E minor')

    # Test 7: C major long stream, to see distinct key
    simulate_key_stream('C', 'major', start_midi=48, steps=40, step_s=0.15, title='Test 7: Long stream in C major')

    # Test 8: Modulation E minor -> C major within one run (two segments)
    print("\n=== Test 8: Modulation E minor -> C major ===")
    seq_mod = []
    # E minor segment
    e_minor_ints = [0, 2, 3, 5, 7, 8, 10]
    e_base = 40
    e_scale = [e_base + iv for iv in e_minor_ints] + [e_base + 12 + iv for iv in e_minor_ints]
    for i in range(30):
        seq_mod.append((0.12, [e_scale[i % len(e_scale)]]))
    # C major segment
    c_major_ints = [0, 2, 4, 5, 7, 9, 11]
    c_base = 48
    c_scale = [c_base + iv for iv in c_major_ints] + [c_base + 12 + iv for iv in c_major_ints]
    for i in range(30):
        seq_mod.append((0.12, [c_scale[i % len(c_scale)]]))
    simulate_event_stream(seq_mod, step_s=0.12, title='Test 8: Modulation E minor -> C major (single run)')


if __name__ == '__main__':
    main()



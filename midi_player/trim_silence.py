import os
from pathlib import Path
from typing import List, Tuple

import mido


def find_first_note_tick(mid: mido.MidiFile) -> int:
    """Return earliest absolute tick of a note_on with velocity > 0 across all tracks.

    If none found, returns 0 (no trimming).
    """
    earliest = None
    for track in mid.tracks:
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            if not getattr(msg, 'is_meta', False) and msg.type == 'note_on' and getattr(msg, 'velocity', 0) > 0:
                if earliest is None or abs_tick < earliest:
                    earliest = abs_tick
                    # can't break; a later track might have an even earlier note
    return int(earliest or 0)


def trim_leading_silence(mid: mido.MidiFile, cut_tick: int) -> mido.MidiFile:
    """Create a new MidiFile with leading time up to cut_tick removed.

    - Meta/CC/Program messages that occur before cut_tick are moved to time 0 (order preserved).
    - Events at/after cut_tick are shifted left by cut_tick ticks.
    - Tempo/time-signature/etc remain in place; the last tempo before cut becomes effective at t=0.
    """
    if cut_tick <= 0:
        return mid.copy()

    out = mido.MidiFile(type=mid.type, ticks_per_beat=mid.ticks_per_beat)
    for track in mid.tracks:
        new_track = mido.MidiTrack()
        # First pass: compute new absolute ticks per message
        abs_tick = 0
        pre_msgs: List[mido.Message] = []
        post_msgs: List[Tuple[int, mido.Message]] = []
        for msg in track:
            abs_tick += msg.time
            if abs_tick < cut_tick:
                # Keep messages before first note: move them to t=0 (delta=0), preserve order
                # Skip any initial delta time by resetting time to 0 later
                pre_msgs.append(msg.copy(time=0))
            else:
                new_abs = abs_tick - cut_tick
                post_msgs.append((int(new_abs), msg.copy()))

        # Second pass: rebuild with proper delta times
        # 1) prepend preserved pre-intro messages at t=0
        for pm in pre_msgs:
            pm.time = 0
            new_track.append(pm)

        # 2) append post-cut messages with shifted times
        last_tick = 0
        for new_abs, msg in post_msgs:
            delta = new_abs - last_tick
            if delta < 0:
                delta = 0  # guard against any rounding issues
            msg.time = int(delta)
            new_track.append(msg)
            last_tick = new_abs

        out.tracks.append(new_track)

    return out


def process_directory(in_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(in_dir.glob('*.mid')):
        try:
            mid = mido.MidiFile(src)
            cut_tick = find_first_note_tick(mid)
            if cut_tick <= 0:
                # nothing to trim; copy as-is
                trimmed = mid
                action = 'copied'
            else:
                trimmed = trim_leading_silence(mid, cut_tick)
                action = f'trimmed(cut={cut_tick} ticks)'
            dst = out_dir / src.name
            trimmed.save(dst)
            print(f"{src.name}: {action} -> {dst.name}")
        except Exception as e:
            print(f"{src.name}: ERROR {e}")


if __name__ == '__main__':
    project_root = Path(__file__).resolve().parents[1]
    in_dir = project_root / 'midi_player' / 'archive_3'
    out_dir = project_root / 'midi_player' / 'archive_3_trimmed'
    process_directory(in_dir, out_dir)



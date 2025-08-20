"""
Real-time engine that glues MIDI input to harmony detection, emotion, and
simple per-zone visual overrides.

Design goals (musician-friendly):
- React quickly to the chord you play (fast layer), but avoid flicker by
  requiring short stability and a minimum hold time.
- Evolve the background mood from the key/scale suggested by the last few
  seconds (slow layer), so colors feel coherent.
- Keep outputs tiny: brightness, speed, and accent intensity. Behaviors can
  choose to respect these overrides.
"""

from typing import Deque, Tuple, Optional, Dict
from collections import deque
import time

from harmony import detect_scale, ChordTracker, Chord, Scale, PitchClass
from emotion import Emotion, combine, ema as ema_vec


def pitch_class_to_hue(pc: PitchClass) -> float:
    """Convert pitch class to hue (0-360 degrees) using chromatic circle.
    
    Maps C=0° (red), C#=30°, D=60°, ..., B=330° around the color wheel.
    """
    return (int(pc) * 30) % 360


def apply_emotion_to_color(base_hue: float, warmth_bias: float, saturation_boost: int) -> Tuple[int, int, int]:
    """Apply emotion biasing to a base hue and convert to RGB.
    
    - base_hue: 0-360 degrees from pitch class
    - warmth_bias: -1 (cool) to +1 (warm), shifts hue toward red/blue
    - saturation_boost: 0-50 extra saturation from tension
    """
    import colorsys
    
    # Apply warmth bias: positive shifts toward red (0°), negative toward blue (240°)
    if warmth_bias > 0:
        # Shift toward red/orange (warm)
        hue_shift = warmth_bias * 30  # up to +30° shift
        biased_hue = (base_hue + hue_shift) % 360
    else:
        # Shift toward blue/teal (cool)
        hue_shift = abs(warmth_bias) * 60  # up to 60° shift toward blue
        biased_hue = (base_hue + 240 - hue_shift) % 360
    
    # Base saturation and value, boosted by tension
    saturation = min(1.0, 0.8 + saturation_boost / 100.0)  # 0.8-1.0 range
    value = 0.9  # keep brightness high
    
    # Convert HSV to RGB
    r, g, b = colorsys.hsv_to_rgb(biased_hue / 360.0, saturation, value)
    return (int(r * 255), int(g * 255), int(b * 255))


class RTState:
    """Runtime state wrapper living alongside `modules.State`.

    Tracks:
    - events: recent MIDI notes (for scale estimation and note rate)
    - vel_s: smoothed playing strength (velocity)
    - rate_s: smoothed note-on rate (how busy you play)
    - chord_tracker: fast chord with stability/hold
    - scale: slow key estimate over a rolling window
    - emotion: 4D feel vector updated every tick
    - overrides: tiny per-zone hints: bg.brightness, runner.speed, mon.intensity
    """

    def __init__(self, scale_window_s: float = 3.0):
        self.events: Deque[Tuple[float, int, bool, int]] = deque()  # (ts, note, is_on, velocity)
        self.vel_s: float = 0.0
        self.rate_s: float = 0.0
        self.last_rate_calc_ts: float = 0.0
        self.event_count_window: Deque[float] = deque()  # timestamps of recent NoteOn

        self.chord_tracker = ChordTracker(stability_ms=300, hold_ms=800)
        self.scale: Optional[Scale] = None
        self.scale_window_s = scale_window_s
        self.last_scale_refresh: float = 0.0

        self.emotion: Emotion = (0.0, 0.0, 0.0, 0.0)

        # Visual overrides computed by engine; behaviors can respect these if present
        self.overrides: Dict[str, Dict[str, object]] = {  # zone -> params
            'bg': {}, 'mon': {}, 'runner': {}
        }

    def ingest_midi(self, midi_event, active_notes: Dict[int, int]):
        """Ingest a raw MIDI message and update recent-note windows and energy.

        - midi_event: object with isNoteOn/off(), getNoteNumber(), getVelocity()
        - active_notes: reference to current held notes (for velocity averaging)
        """
        ts = time.time()
        # rtmidi API: duck-typed access; caller ensures isNoteOn/off checks
        if midi_event.isNoteOn():
            note = midi_event.getNoteNumber()
            vel = midi_event.getVelocity()
            self.events.append((ts, note, True, vel))
            self.event_count_window.append(ts)
        elif midi_event.isNoteOff():
            note = midi_event.getNoteNumber()
            self.events.append((ts, note, False, 0))

        # Trim windows
        cutoff = ts - self.scale_window_s
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()
        while self.event_count_window and self.event_count_window[0] < ts - 1.0:
            self.event_count_window.popleft()

        # Update smoothed velocity toward current average
        if active_notes:
            avg_vel = sum(active_notes.values()) / len(active_notes)
        else:
            avg_vel = 0.0
        self.vel_s = self.vel_s + 0.2 * (avg_vel - self.vel_s)

        # Note-on rate per second (EMA)
        inst_rate = len(self.event_count_window)
        self.rate_s = self.rate_s + 0.2 * (inst_rate - self.rate_s)

    def tick(self, active_notes: Dict[int, int]):
        """Run one render tick: chord/scale updates, emotion blend, overrides."""
        now = time.time()
        # Update chord with stability/hold logic
        chord, chord_changed = self.chord_tracker.update(active_notes, now)

        # Periodic scale refresh
        if now - self.last_scale_refresh >= 1.0:
            sc = detect_scale(self.events, now=now, window_s=self.scale_window_s)
            if sc is not None:
                self.scale = sc
            self.last_scale_refresh = now

        # Update emotion vector
        chord_quality = chord[1] if chord else None
        scale_mode = self.scale[1] if self.scale else None
        target = combine(chord_quality, scale_mode, w_chord=0.6, w_scale=0.5)
        self.emotion = ema_vec(self.emotion, target, alpha=0.15)

        # Compute per-zone overrides using emotion vector for color biasing
        joy, melancholy, tension, blues = self.emotion
        
        # Color biasing from emotion (for behaviors to use)
        warmth_bias = joy - melancholy  # +1 = very warm, -1 = very cool
        saturation_boost = int(tension * 50)  # tension increases vividness (0-50)
        
        # Accent strength from emotion
        accent_multiplier = 1.0 + tension * 0.5  # tension makes accents stronger
        
        self.overrides['bg'] = {
            'brightness': int(max(0, min(255, self.vel_s))),
            'warmth_bias': warmth_bias,  # for hue shifting toward warm/cool
            'saturation_boost': saturation_boost,  # for more vivid colors
            'chord_root': chord[0] if chord else None,  # current chord root for color
            'scale_root': self.scale[0] if self.scale else None,  # key root for color
        }
        self.overrides['runner'] = {
            'speed': int(max(0, min(255, self.rate_s * 20))),  # scale rate to SX range
            'warmth_bias': warmth_bias,
            'chord_root': chord[0] if chord else None,
        }
        if chord_changed and chord:
            self.overrides['mon'] = {
                'intensity': int(160 * max(0.0, min(1.0, chord[2])) * accent_multiplier),
                'chord_root': chord[0],  # for chord-specific accent colors
                'chord_quality': chord[1],  # maj/min/dom7 for color tinting
            }
        else:
            # allow behaviors to decay intensity themselves
            self.overrides['mon'] = {}


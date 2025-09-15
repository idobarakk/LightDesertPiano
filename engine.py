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
import logging
import math

from harmony import Chord, Scale, PitchClass
from harmony_m21 import ChordTrackerM21
from emotion import Emotion, combine, ema as ema_vec

# Dedicated logger for emotion/behavior diagnostics
emo_log = logging.getLogger("emotion")


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


class MonLinReg:
    """Linear regression-based brightness estimator for monuments.

    - Tracks derivatives (trends) of rate and velocity using linear regression
    - Brightness goes "mad" on changes, scaled by magnitude
    - Handles velocity noise while capturing rate stability
    - Simple softmax normalization to 0-255 range
    """

    def __init__(self, window_size: int = 10) -> None:
        self.window_size = window_size
        self.rate_history: Deque[float] = deque(maxlen=window_size)
        self.vel_history: Deque[float] = deque(maxlen=window_size)
        self.time_points = list(range(window_size))  # [0, 1, 2, ..., window_size-1]
        self.brightness_smooth: float = 100.0  # smoothed output

    def _linear_regression_slope(self, values: Deque[float]) -> float:
        """Calculate slope of linear regression line through recent values."""
        if len(values) < 3:
            return 0.0
        
        n = len(values)
        x_points = self.time_points[-n:]  # use last n time points
        y_values = list(values)
        
        # Linear regression: slope = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
        sum_x = sum(x_points)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_points, y_values))
        sum_x2 = sum(x * x for x in x_points)
        
        denominator = n * sum_x2 - sum_x * sum_x
        if abs(denominator) < 1e-6:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope

    def step(self, pace: float, vel: float, pace_variance: float = 0.0) -> int:
        # Add current values to history
        self.rate_history.append(pace)  # now tracking pace instead of rate
        self.vel_history.append(vel)
        
        # Calculate derivatives (slopes) using linear regression
        pace_derivative = self._linear_regression_slope(self.rate_history)
        vel_derivative = self._linear_regression_slope(self.vel_history)
        
        # Calculate magnitudes: both change magnitude AND current value magnitude
        pace_change_magnitude = abs(pace_derivative)  # how big is the pace change?
        vel_change_magnitude = abs(vel_derivative)    # how big is the velocity change?
        
        pace_value_magnitude = pace                   # how big is current pace?
        vel_value_magnitude = vel / 127.0             # how big is current velocity? (normalized)
        
        # Add pace variance as a third factor (captures rhythmic instability)
        variance_factor = min(1.0, pace_variance * 10.0)  # scale variance to 0-1
        
        # Combine: change_magnitude * value_magnitude = total impact
        # Both matter: big changes at high values = maximum "madness"
        pace_impact = pace_change_magnitude * (1.0 + pace_value_magnitude)
        vel_impact = vel_change_magnitude * (1.0 + vel_value_magnitude * 2.0)  # velocity more sensitive
        variance_impact = variance_factor * 2.0  # rhythmic chaos adds to madness
        
        # Total change signal - "madness" factor
        total_change = pace_impact * 0.4 + vel_impact * 0.5 + variance_impact * 0.1
        
        # Softmax-like normalization to 0-1 range
        # Higher values → closer to 1, but never quite reaches it
        change_normalized = 1.0 - math.exp(-total_change * 3.0)  # 3.0 is sensitivity
        
        # Target brightness based on change
        target_brightness = 30 + change_normalized * 225  # 30-255 range
        
        # Smooth the output to avoid jitter
        alpha = 0.15  # smoothing factor
        self.brightness_smooth += alpha * (target_brightness - self.brightness_smooth)
        
        return int(max(15, min(255, self.brightness_smooth)))


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
        
        # Pace tracking system
        self.note_intervals: Deque[float] = deque(maxlen=10)  # time between consecutive notes
        self.last_note_time: float = 0.0
        self.pace_s: float = 0.0  # smoothed pace (inverse of interval)
        self.pace_variance: float = 0.0  # how much pace is changing

        # music21-backed tracker with short arpeggio latch and longer key window
        self.chord_tracker = ChordTrackerM21(
            stability_ms=60,
            hold_ms=180,
            chord_arp_window_ms=350,
            scale_window_s=5.0,
        )
        self.scale: Optional[Scale] = None
        self.scale_window_s = scale_window_s
        self.last_scale_refresh: float = 0.0

        self.emotion: Emotion = (0.0, 0.0, 0.0, 0.0)

        # Monuments brightness estimator
        self.mon_linreg = MonLinReg(window_size=8)

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
            
            # Track pace (time intervals between notes)
            if self.last_note_time > 0:
                interval = ts - self.last_note_time
                if interval > 0.01:  # ignore very rapid repeats (< 10ms)
                    self.note_intervals.append(interval)
            self.last_note_time = ts
        elif midi_event.isNoteOff():
            note = midi_event.getNoteNumber()
            self.events.append((ts, note, False, 0))

        # Trim windows
        cutoff = ts - self.scale_window_s
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()
        while self.event_count_window and self.event_count_window[0] < ts - 3.0:
            self.event_count_window.popleft()

        # Update smoothed velocity toward current average
        if active_notes:
            avg_vel = sum(active_notes.values()) / len(active_notes)
        else:
            avg_vel = 0.0
        self.vel_s = self.vel_s + 0.2 * (avg_vel - self.vel_s)

        # Note-on rate per second (EMA) - now over 3-second window
        inst_rate = len(self.event_count_window) / 3.0  # normalize by window size
        self.rate_s = self.rate_s + 0.15 * (inst_rate - self.rate_s)  # slower EMA for stability
        
        # Calculate pace metrics from note intervals
        if len(self.note_intervals) >= 3:
            # Current pace = inverse of average recent interval (notes per second)
            avg_interval = sum(self.note_intervals) / len(self.note_intervals)
            current_pace = 1.0 / max(0.01, avg_interval)  # prevent division by zero
            self.pace_s = self.pace_s + 0.2 * (current_pace - self.pace_s)
            
            # Pace variance = how much intervals are changing (captures acceleration/deceleration)
            if len(self.note_intervals) >= 5:
                recent_intervals = list(self.note_intervals)[-5:]
                interval_variance = sum((x - avg_interval) ** 2 for x in recent_intervals) / len(recent_intervals)
                self.pace_variance = self.pace_variance + 0.1 * (interval_variance - self.pace_variance)
        else:
            # Not enough data yet
            self.pace_s = 0.0
            self.pace_variance = 0.0

    def _adaptive_energy_brightness(self) -> int:
        """Change-based brightness with style-adaptive sensitivity."""
        
        # Calculate current musical energy (rate + velocity + chord complexity)
        rate_energy = self.rate_s
        velocity_energy = self.vel_s / 127.0  # normalize velocity
        chord_complexity = min(1.0, len(getattr(self, '_last_active_notes', {})) / 6.0)
        current_energy = rate_energy * 0.5 + velocity_energy * 3.0 + chord_complexity * 2.0
        
        # Update long-term style EMA (very slow, tracks musical style)
        style_alpha = 0.001  # ~17 minute time constant for style adaptation
        self.rate_style_ema = self.rate_style_ema + style_alpha * (self.rate_s - self.rate_style_ema)
        
        # Calculate energy change (gradient)
        energy_change = current_energy - self.energy_previous
        self.energy_previous = current_energy
        
        # Style-based sensitivity: higher baseline rate = lower sensitivity to changes
        # Ballads (rate ~2): high sensitivity (~40)
        # Rock (rate ~8): medium sensitivity (~15) 
        # Jazz (rate ~12): low sensitivity (~10)
        style_sensitivity = max(5.0, 50.0 / max(1.0, self.rate_style_ema))
        
        # Apply change with style-based scaling
        brightness_change = energy_change * style_sensitivity
        
        # Update brightness with change, but keep it bounded
        self.brightness_current += brightness_change * 0.3  # damping factor
        self.brightness_current = max(50.0, min(230.0, self.brightness_current))  # clamp range
        
        # Slow drift back toward base level (prevents runaway)
        base_drift = (self.brightness_base - self.brightness_current) * 0.01
        self.brightness_current += base_drift
        
        return int(self.brightness_current)

    def tick(self, active_notes: Dict[int, int]):
        """Run one render tick: chord/scale updates, emotion blend, overrides."""
        now = time.time()
        
        # Store active notes for energy calculation
        self._last_active_notes = active_notes
        
        # Update chord with stability/hold logic
        chord, chord_changed = self.chord_tracker.update(active_notes, now)
        
        # Periodic scale refresh: mirror tracker's current scale
        if now - self.last_scale_refresh >= 1.0:
            sc = getattr(self.chord_tracker, 'scale', None)
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
            'brightness': int(max(0, min(255, self.vel_s // 2))),
            'warmth_bias': warmth_bias,  # for hue shifting toward warm/cool
            'saturation_boost': saturation_boost,  # for more vivid colors
            'chord_root': chord[0] if chord else None,  # current chord root for color
            'scale_root': self.scale[0] if self.scale else None,  # key root for color
        }
        self.overrides['runner'] = {
            'speed': int(max(0, min(255, self.vel_s))),  # scale rate to SX range
            'warmth_bias': warmth_bias,
            'chord_root': chord[0] if chord else None,
        }
        # Monument: pace-aware change detection brightness
        brightness_scaled = self.mon_linreg.step(self.pace_s, self.vel_s, self.pace_variance)
        
        self.overrides['mon'] = {
            'brightness': brightness_scaled,  # sophisticated rate-to-brightness mapping
            'chord_root': chord[0] if chord else None,  # for chord-specific colors
            'chord_quality': chord[1] if chord else None,  # maj/min/dom7 for color tinting
        }

        # Emotion-to-behavior diagnostics (concise)
        if chord_changed or (now - (getattr(self, '_last_emolog', 0.0))) >= 1.0:
            self._last_emolog = now
            em = tuple(round(x, 2) for x in self.emotion)
            scale_str = f"{self.scale[0].name if self.scale else '-'}:{scale_mode}" if self.scale else "-"
            chord_str = f"{chord[0].name}:{chord_quality}:{chord[2]:.2f}" if chord else "-"

            # Predicted colors (match behaviors)
            # bg color from scale_root + emotion
            if self.scale is not None:
                bg_hue = pitch_class_to_hue(self.scale[0])
                bg_rgb = apply_emotion_to_color(bg_hue, warmth_bias, saturation_boost)
            else:
                bg_rgb = None
            # runner color from chord_root + emotion (half saturation boost)
            if chord is not None:
                run_hue = pitch_class_to_hue(chord[0])
                run_rgb = apply_emotion_to_color(run_hue, warmth_bias, saturation_boost // 2)
            else:
                run_rgb = None
            # mon color based on current chord; apply quality tint like behaviors
            mon_rgb = None
            mon_ov = self.overrides.get('mon', {})
            if isinstance(mon_ov, dict) and chord is not None:
                mon_hue = pitch_class_to_hue(chord[0])
                q = chord_quality or 'maj'
                if q == 'min':
                    mon_hue = (mon_hue + 240) % 360
                elif q == 'dom7':
                    mon_hue = (mon_hue + 45) % 360
                elif q in ['dim', 'aug']:
                    mon_hue = (mon_hue + 300) % 360
                mon_rgb = apply_emotion_to_color(mon_hue, 0.0, 30)

            emo_log.info(
                f"[EMO] vec={em} rate={self.rate_s:.2f} vel={self.vel_s:.1f} pace={self.pace_s:.2f} pvar={self.pace_variance:.3f} | "
                f"bg(br={self.overrides['bg']['brightness']}, warm={warmth_bias:.2f}, sat+={saturation_boost}, rgb={bg_rgb}) "
                f"runner(spd={self.overrides['runner']['speed']}, rgb={run_rgb}) "
                f"mon(br={mon_ov.get('brightness', 0)}, rgb={mon_rgb}) | "
                f"scale={scale_str} chord={chord_str}"
            )


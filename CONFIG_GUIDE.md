# Configuration Guide

This guide explains all the hyperparameters in `config.py` and how they affect the system's behavior.

## Quick Start

All tunable parameters are now centralized in `config.py`. To adjust the system's behavior:

1. Open `config.py`
2. Find the parameter you want to adjust (organized by subsystem)
3. Modify the value
4. Restart the application

## Parameter Categories

### Visual System
Controls general LED behavior and brightness ranges.

- `VELOCITY_MAX_VAL`: Maximum velocity for LED brightness scaling (255)
- `STORM_BG_BRIGHTNESS_MIN_VAL`: Minimum ambient brightness for background (15)

### Engine - Timing Windows
Controls how far back the system looks for analysis.

- `ENGINE_SCALE_WINDOW_S`: Scale/key detection window (3.0s)
- `ENGINE_SCALE_REFRESH_INTERVAL_S`: How often to refresh scale (1.5s)
- `ENGINE_RATE_WINDOW_S`: Window for counting note events (3.0s)

### Engine - Smoothing (EMA Alphas)
Controls how quickly the system responds to changes. Higher = more reactive, lower = more stable.

- `ENGINE_VELOCITY_SMOOTHING_ALPHA`: Velocity adaptation speed (0.2)
- `ENGINE_RATE_SMOOTHING_ALPHA`: Note rate adaptation speed (0.15)
- `ENGINE_PACE_SMOOTHING_ALPHA`: Inter-note timing adaptation (0.2)
- `ENGINE_PACE_VARIANCE_SMOOTHING_ALPHA`: Rhythmic instability adaptation (0.1)
- `ENGINE_EMOTION_SMOOTHING_ALPHA`: Emotional state changes (0.15)

### Monument Brightness
Controls the "change detector" that makes monuments pop on musical changes.

- `MONUMENT_BRIGHTNESS_WINDOW_SIZE`: Regression analysis window (8 samples)
- `MONUMENT_BRIGHTNESS_SMOOTHING_ALPHA`: Output smoothing (0.15)
- `MONUMENT_BRIGHTNESS_MIN/MAX`: Brightness range (30-255)
- `MONUMENT_CHANGE_SENSITIVITY`: Change detection sensitivity (3.0)
- `PACE_MIN_INTERVAL_S`: Minimum interval to track (0.01s)

### Color Mapping
Controls how emotions affect colors.

- `COLOR_WARMTH_SHIFT_WARM_DEG`: Hue shift toward warm colors (30°)
- `COLOR_WARMTH_SHIFT_COOL_DEG`: Hue shift toward cool colors (60°)
- `COLOR_BASE_SATURATION`: Base color saturation (0.8)
- `COLOR_TENSION_SATURATION_BOOST_MAX`: Max saturation boost from tension (50)
- `COLOR_BASE_VALUE`: Base brightness for colors (0.9)

### Harmony Detection - Chord Scoring
Controls how chords are detected and scored.

- `CHORD_MIN_SCORE`: Minimum score to accept a chord (0.5)
- `CHORD_SCORE_COVERAGE_WEIGHT`: Weight for chord coverage (0.7)
- `CHORD_SCORE_PRECISION_WEIGHT`: Weight for precision (0.3)

### Harmony Detection - Stability & Hold
Controls how quickly chords change to avoid flicker.

- `CHORD_STABILITY_MS`: How long a chord must persist (60ms)
- `CHORD_HOLD_MS`: How long to hold accepted chord (180ms)
- `CHORD_CONFIDENCE_MIN_SWITCH`: Min confidence to switch chords (0.60)
- `CHORD_CONFIDENCE_DELTA_SAME`: Improvement needed to reaffirm (0.02)

### Harmony Detection - music21 Tracker
Controls the music21-based chord/scale detection.

- `CHORD_ARPEGGIO_WINDOW_MS`: Arpeggio latch window (350ms)
- `CHORD_M21_SCALE_WINDOW_S`: Scale detection window (5.0s)
- `CHORD_MIN_PITCH_CLASSES`: Min pitch classes for chord (3)
- `SCALE_MIN_PITCH_CLASSES`: Min pitch classes for scale (4)

### Scale Detection
Controls key/scale estimation from recent notes.

- `SCALE_DETECTION_WINDOW_S`: Histogram analysis window (3.0s)
- `SCALE_HISTOGRAM_BASE_WEIGHT`: Base weight for histogram (0.5)
- `SCALE_HISTOGRAM_RECENCY_WEIGHT`: Recency weight (0.5)

### Emotion System
Controls how chord/scale qualities map to emotions.

- `EMOTION_CHORD_WEIGHT`: Chord influence on emotion (0.6)
- `EMOTION_SCALE_WEIGHT`: Scale influence on emotion (0.5)
- `EMOTION_CHORD_VECTORS`: Emotion signatures for chord qualities
- `EMOTION_SCALE_VECTORS`: Emotion signatures for scale modes

### Behaviors - Monument Zone
Controls monument-specific visual parameters.

- `MONUMENT_CHORD_HUE_SHIFT_MINOR`: Hue shift for minor chords (240°)
- `MONUMENT_CHORD_HUE_SHIFT_DOM7`: Hue shift for dom7 chords (45°)
- `MONUMENT_CHORD_HUE_SHIFT_TENSION`: Hue shift for dim/aug (300°)
- `MONUMENT_FIXED_SATURATION_BOOST`: Fixed saturation accent (30)

### Behaviors - Runner Zone
Controls runner effect selection and colors.

- `RUNNER_SPEED_THRESHOLD_SLOW`: Threshold for slow effect (85)
- `RUNNER_SPEED_THRESHOLD_MEDIUM`: Threshold for medium effect (170)
- `RUNNER_EFFECT_SLOW/MEDIUM/HIGH`: Effect configurations (name, index, speed)
- `RUNNER_DEFAULT_BRIGHTNESS`: Default brightness (50)
- `RUNNER_SATURATION_DIVISOR`: Saturation subtlety factor (2)

### System - Timing & Threading
Controls system-level timing parameters.

- `VISUAL_TICK_RATE_S`: Visual render loop rate (0.05s = 20Hz)
- `MIDI_EVENT_QUEUE_SIZE`: Event buffer size (2048)
- `MIDI_POLL_TIMEOUT_MS`: MIDI polling timeout (1ms)
- `MAIN_LOOP_SLEEP_S`: CPU yield sleep time (0.005s)
- `LED_TASK_TIMEOUT_S`: LED task timeout (0.5s)

### Sleep Mode
Controls ambient visuals when no one is playing.

- `SLEEP_MODE_TIMEOUT_S`: Inactivity timeout before sleep mode (10.0s)
- `SLEEP_MODE_BG_ON`: Background on/off in sleep mode (False)
- `SLEEP_MODE_MON_EFFECT`: Monument effect in sleep mode ("Perlin Move", 147)
- `SLEEP_MODE_RUNNER_EFFECT`: Runner effect in sleep mode ("Theater", 13)
- `SLEEP_MODE_MON_SPEED/INTENSITY/BRIGHTNESS/COLOR`: Monument visual parameters (red-orange)
- `SLEEP_MODE_RUNNER_SPEED/INTENSITY/BRIGHTNESS`: Runner visual parameters

Note: Runner colors flow naturally from the effect; monument uses warm red-orange for ambient glow.

### Logging
Controls diagnostic output.

- `LOG_MIDI_EVENTS`: Enable MIDI event logging (False)
- `EMOTION_LOG_INTERVAL_S`: Emotion diagnostic interval (1.0s)

### MIDI State
Controls MIDI note range and analysis.

- `MIDI_MIN_KEY`: Minimum MIDI note (36 = C2)
- `MIDI_MAX_KEY`: Maximum MIDI note (84 = C6)
- `MIDI_NUM_INTERVALS`: Number of intervals for grouping (6)

## Tuning Tips

### Making the system more responsive
- Increase smoothing alphas (closer to 1.0)
- Decrease stability/hold times
- Increase change sensitivity

### Making the system more stable
- Decrease smoothing alphas (closer to 0.0)
- Increase stability/hold times
- Decrease change sensitivity

### Adjusting color vibrancy
- Increase `COLOR_BASE_SATURATION`
- Increase `COLOR_TENSION_SATURATION_BOOST_MAX`
- Adjust hue shift degrees for more dramatic color changes

### Fine-tuning chord detection
- Adjust `CHORD_MIN_SCORE` for stricter/looser detection
- Modify `CHORD_STABILITY_MS` for faster/slower chord changes
- Adjust `CHORD_ARPEGGIO_WINDOW_MS` for better arpeggio capture

### Adjusting monument brightness behavior
- Increase `MONUMENT_CHANGE_SENSITIVITY` for more dramatic pops
- Adjust `MONUMENT_BRIGHTNESS_MIN/MAX` for brightness range
- Modify `MONUMENT_BRIGHTNESS_WINDOW_SIZE` for smoother/sharper response

### Customizing sleep mode
- Adjust `SLEEP_MODE_TIMEOUT_S` for faster/slower sleep activation
- Change `SLEEP_MODE_MON_EFFECT` or `SLEEP_MODE_RUNNER_EFFECT` to different WLED effects
- Modify `SLEEP_MODE_MON_COLOR` for different monument ambient colors (default: red-orange)
- Adjust speed/intensity/brightness for different ambient moods
- Set `SLEEP_MODE_BG_ON = True` to keep background on during sleep

## Emotion Vectors

Emotion vectors are 4D tuples: `(joy, melancholy, tension, blues)`

Each dimension ranges from 0.0 to 1.0 and represents the emotional "signature" of a chord quality or scale mode.

### Chord Quality Examples
- Major: `(1.0, 0.0, 0.1, 0.1)` - Very joyful, minimal other emotions
- Minor: `(0.1, 1.0, 0.1, 0.1)` - Very melancholic
- Dominant 7th: `(0.3, 0.1, 0.1, 1.0)` - Bluesy with some joy
- Diminished: `(0.2, 0.1, 1.0, 0.1)` - High tension

### Scale Mode Examples
- Major: `(0.7, 0.0, 0.1, 0.2)` - Happy and bright
- Minor: `(0.1, 0.7, 0.1, 0.2)` - Sad and dark
- Blues: `(0.2, 0.2, 0.1, 0.9)` - Very bluesy

You can customize these vectors to create your own emotional mappings!


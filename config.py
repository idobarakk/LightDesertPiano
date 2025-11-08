"""
Centralized configuration for all hyperparameters and constants.

This file contains all tunable parameters that control the behavior of the
emotion-based visual system. Parameters are organized by subsystem for clarity.

TUNING GUIDE:
- Timing parameters (ms/s): Control responsiveness vs stability
- Smoothing alphas (0-1): Higher = more reactive, lower = more stable
- Thresholds: Control when effects trigger or change
- Weights: Control relative importance of different factors
"""

# =============================================================================
# VISUAL SYSTEM - General LED behavior
# =============================================================================

# Maximum velocity value for LED brightness scaling
VELOCITY_MAX_VAL = 255

# Minimum brightness for storm background (always-on ambient level)
STORM_BG_BRIGHTNESS_MIN_VAL = 15


# =============================================================================
# ENGINE - Real-time state tracking and smoothing
# =============================================================================

# --- Timing Windows ---
# How far back to look for scale/key detection (seconds)
ENGINE_SCALE_WINDOW_S = 3.0

# How often to refresh scale detection (seconds)
ENGINE_SCALE_REFRESH_INTERVAL_S = 1.5

# Window for counting recent note-on events (seconds)
ENGINE_RATE_WINDOW_S = 3.0

# --- Smoothing Parameters (EMA alphas: 0=no change, 1=instant) ---
# Velocity smoothing: how quickly average velocity adapts
ENGINE_VELOCITY_SMOOTHING_ALPHA = 0.2

# Note rate smoothing: how quickly note-per-second rate adapts
ENGINE_RATE_SMOOTHING_ALPHA = 0.15

# Pace smoothing: how quickly inter-note timing adapts
ENGINE_PACE_SMOOTHING_ALPHA = 0.2

# Pace variance smoothing: how quickly rhythmic instability metric adapts
ENGINE_PACE_VARIANCE_SMOOTHING_ALPHA = 0.1

# Emotion vector smoothing: how quickly emotional state changes
ENGINE_EMOTION_SMOOTHING_ALPHA = 0.15

# --- Monument Brightness (Linear Regression Change Detector) ---
# Window size for regression analysis (number of samples)
MONUMENT_BRIGHTNESS_WINDOW_SIZE = 8

# Brightness output smoothing factor
MONUMENT_BRIGHTNESS_SMOOTHING_ALPHA = 0.15

# Brightness range (min, max)
MONUMENT_BRIGHTNESS_MIN = 30
MONUMENT_BRIGHTNESS_MAX = 255

# Sensitivity multiplier for change detection (higher = more reactive)
MONUMENT_CHANGE_SENSITIVITY = 3.0

# Minimum interval between notes to track (seconds, ignore very rapid repeats)
PACE_MIN_INTERVAL_S = 0.01

# --- Emotion to Color Mapping ---
# Warmth bias hue shift range (degrees, positive = toward red/warm)
COLOR_WARMTH_SHIFT_WARM_DEG = 30  # shift toward red/orange when joyful
COLOR_WARMTH_SHIFT_COOL_DEG = 60  # shift toward blue/teal when melancholy

# Base saturation for colors (0-1)
COLOR_BASE_SATURATION = 0.8

# Saturation boost from tension (0-50 range)
COLOR_TENSION_SATURATION_BOOST_MAX = 50

# Base value/brightness for colors (0-1)
COLOR_BASE_VALUE = 0.9


# =============================================================================
# HARMONY DETECTION - Chord and scale tracking
# =============================================================================

# --- Chord Detection Scoring ---
# Minimum score to consider a chord valid (0-1, coverage+precision blend)
CHORD_MIN_SCORE = 0.5

# Weight for chord coverage vs precision in scoring
CHORD_SCORE_COVERAGE_WEIGHT = 0.7
CHORD_SCORE_PRECISION_WEIGHT = 0.3

# --- Chord Tracker (Stability & Hold) ---
# How long a chord must persist before being accepted (milliseconds)
CHORD_STABILITY_MS = 60

# How long to hold an accepted chord before allowing change (milliseconds)
CHORD_HOLD_MS = 180

# Minimum confidence to switch to a different chord (0-1)
CHORD_CONFIDENCE_MIN_SWITCH = 0.60

# Confidence improvement required to reaffirm same chord (0-1)
CHORD_CONFIDENCE_DELTA_SAME = 0.02

# --- music21-based Chord Tracker ---
# Arpeggio latch window: include recent note-ons for chord detection (milliseconds)
CHORD_ARPEGGIO_WINDOW_MS = 350

# Scale detection window for music21 tracker (seconds)
CHORD_M21_SCALE_WINDOW_S = 5.0

# Minimum distinct pitch classes required for chord detection
CHORD_MIN_PITCH_CLASSES = 3

# Minimum distinct pitch classes required for scale detection
SCALE_MIN_PITCH_CLASSES = 4

# --- Scale Detection ---
# Default window for scale histogram analysis (seconds)
SCALE_DETECTION_WINDOW_S = 3.0

# Recency weight blend for scale histogram (0.5 = half base, half recency-weighted)
SCALE_HISTOGRAM_BASE_WEIGHT = 0.5
SCALE_HISTOGRAM_RECENCY_WEIGHT = 0.5


# =============================================================================
# EMOTION SYSTEM - Chord/scale quality to emotion mapping
# =============================================================================

# --- Emotion Blending Weights ---
# How strongly chord quality affects target emotion (0-1)
EMOTION_CHORD_WEIGHT = 0.6

# How strongly scale mode affects target emotion (0-1)
EMOTION_SCALE_WEIGHT = 0.5

# --- Emotion Vectors: (joy, melancholy, tension, blues) ---
# Each tuple represents the emotional "signature" of a chord quality or scale mode

EMOTION_CHORD_VECTORS = {
    "maj": (1.0, 0.0, 0.1, 0.1),      # Major: joyful, bright
    "maj7": (1.0, 0.0, 0.1, 0.1),     # Major 7th: joyful, jazzy
    "min": (0.1, 1.0, 0.1, 0.1),      # Minor: melancholic, dark
    "min7": (0.1, 1.0, 0.1, 0.1),     # Minor 7th: melancholic, jazzy
    "dom7": (0.3, 0.1, 0.1, 1.0),     # Dominant 7th: bluesy, tension
    "sus2": (0.5, 0.2, 0.2, 0.1),     # Suspended 2nd: floating, ambiguous
    "sus4": (0.5, 0.2, 0.2, 0.1),     # Suspended 4th: floating, ambiguous
    "dim": (0.2, 0.1, 1.0, 0.1),      # Diminished: tense, unstable
    "aug": (0.4, 0.1, 0.8, 0.1),      # Augmented: tense, weird
}

EMOTION_SCALE_VECTORS = {
    "major": (0.7, 0.0, 0.1, 0.2),        # Major scale: happy, bright
    "minor": (0.1, 0.7, 0.1, 0.2),        # Minor scale: sad, dark
    "major_pent": (0.6, 0.0, 0.1, 0.3),   # Major pentatonic: open, folk
    "minor_pent": (0.1, 0.6, 0.1, 0.3),   # Minor pentatonic: bluesy, rock
    "blues": (0.2, 0.2, 0.1, 0.9),        # Blues scale: bluesy, gritty
}


# =============================================================================
# BEHAVIORS - Zone-specific visual parameters
# =============================================================================

# --- Monument (mon) Zone ---
# Chord quality hue shifts (degrees) for different chord types
MONUMENT_CHORD_HUE_SHIFT_MINOR = 240   # shift toward blue for minor
MONUMENT_CHORD_HUE_SHIFT_DOM7 = 45     # shift toward amber for dom7
MONUMENT_CHORD_HUE_SHIFT_TENSION = 300 # shift toward magenta for dim/aug

# Fixed saturation boost for monument accents (not emotion-scaled)
MONUMENT_FIXED_SATURATION_BOOST = 30

# --- Background (bg) Zone ---
# (Uses engine-provided scale color with full emotion biasing)
# No additional parameters needed - driven entirely by engine

# --- Runner Zone ---
# Speed thresholds for effect selection (0-255 scale)
RUNNER_SPEED_THRESHOLD_SLOW = 85   # Below this: slow effect (Android)
RUNNER_SPEED_THRESHOLD_MEDIUM = 170 # Below this: medium effect (Chase)
# Above medium threshold: high effect (Chase 3)

# Runner effect configurations: (name, index, speed)
RUNNER_EFFECT_SLOW = ("Android", 27, 80)
RUNNER_EFFECT_MEDIUM = ("Chase", 28, 120)
RUNNER_EFFECT_HIGH = ("Chase 3", 54, 180)

# Default brightness when engine doesn't provide one
RUNNER_DEFAULT_BRIGHTNESS = 50

# Saturation boost divisor for runner (makes it subtler than monument)
RUNNER_SATURATION_DIVISOR = 2


# =============================================================================
# SYSTEM - Timing and threading
# =============================================================================

# Visual render loop rate (seconds between ticks)
VISUAL_TICK_RATE_S = 0.05  # 20 Hz

# MIDI event queue size (number of events to buffer)
MIDI_EVENT_QUEUE_SIZE = 2048

# MIDI input polling timeout (milliseconds)
MIDI_POLL_TIMEOUT_MS = 1

# Small sleep in main loop to yield CPU (seconds)
MAIN_LOOP_SLEEP_S = 0.005

# LED task timeout when waiting for completion (seconds)
LED_TASK_TIMEOUT_S = 0.5


# =============================================================================
# LOGGING - Diagnostic output control
# =============================================================================

# Enable/disable MIDI event logging (note on/off messages)
LOG_MIDI_EVENTS = False

# Emotion diagnostic logging interval (seconds, 0 = only on chord change)
EMOTION_LOG_INTERVAL_S = 1.0


# =============================================================================
# MIDI STATE - Note range and intervals
# =============================================================================

# MIDI note range for state tracking
MIDI_MIN_KEY = 36  # C2
MIDI_MAX_KEY = 84  # C6

# Number of intervals for note grouping/analysis
MIDI_NUM_INTERVALS = 6


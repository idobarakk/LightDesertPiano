"""
Zone behaviors: translate musical state into WLED effect parameters.

ARCHITECTURE CHANGE: Storm functions now use the NEW emotion-based engine exclusively.
The old per-note reactive behavior has been commented out and replaced with:

- storm_mon: Chord-change accents with emotion-scaled intensity and quality-based colors
- storm_bg: Scale-based mood canvas with emotion biasing (warmth/coolness, saturation)  
- storm_runner: Chord-reactive motion with engine-controlled speed (note rate, not velocity)

Other vibe functions (rainbow, spring, summer) still use the old architecture for now.
The real-time engine (state.rt) provides chord/scale detection, emotion vectors, and
color mapping. If no engine is present, storm functions use minimal fallbacks.
"""

from modules import State, Effect, Note2Color
import math

from config import (
    VELOCITY_MAX_VAL,
    STORM_BG_BRIGHTNESS_MIN_VAL,
    MONUMENT_CHORD_HUE_SHIFT_MINOR,
    MONUMENT_CHORD_HUE_SHIFT_DOM7,
    MONUMENT_CHORD_HUE_SHIFT_TENSION,
    MONUMENT_FIXED_SATURATION_BOOST,
    RUNNER_SPEED_THRESHOLD_SLOW,
    RUNNER_SPEED_THRESHOLD_MEDIUM,
    RUNNER_EFFECT_SLOW,
    RUNNER_EFFECT_MEDIUM,
    RUNNER_EFFECT_HIGH,
    RUNNER_DEFAULT_BRIGHTNESS,
    RUNNER_SATURATION_DIVISOR,
    SLEEP_MODE_BG_ON,
    SLEEP_MODE_MON_EFFECT,
    SLEEP_MODE_MON_SPEED,
    SLEEP_MODE_MON_INTENSITY,
    SLEEP_MODE_MON_BRIGHTNESS,
    SLEEP_MODE_MON_COLOR,
    SLEEP_MODE_RUNNER_EFFECT,
    SLEEP_MODE_RUNNER_SPEED,
    SLEEP_MODE_RUNNER_INTENSITY,
    SLEEP_MODE_RUNNER_BRIGHTNESS,
)


def at_least(state: State, num_active_notes: int):
    return len(state.active_notes2velocity) >= num_active_notes


def storm_mon(state: State, effect: Effect):
    """Monument zone: always on; rate controls brightness; chord colors from engine."""
    
    # Always on
    effect.is_on = 1
    
    # Check for sleep mode
    rt = getattr(state, 'rt', None)
    is_sleep_mode = getattr(rt, 'is_sleep_mode', False) if rt else False
    
    if is_sleep_mode:
        # Sleep mode: Perlin Move effect with red-orange ambient visuals
        effect.name, effect.index = SLEEP_MODE_MON_EFFECT
        effect.speed = SLEEP_MODE_MON_SPEED
        effect.intensity = SLEEP_MODE_MON_INTENSITY
        effect.brightness = SLEEP_MODE_MON_BRIGHTNESS
        effect.primary_color = SLEEP_MODE_MON_COLOR
        return
    
    # Active mode: restore Solid effect if needed
    if effect.index != 0:  # If not already Solid
        effect.name = 'Solid'
        effect.index = 0
    
    # NEW ARCHITECTURE: Driven entirely by emotion engine
    if rt and 'mon' in rt.overrides:
        ov = rt.overrides['mon']

        # Rate controls brightness (note activity level)
        effect.brightness = ov.get('brightness', 0)

        # Chord-specific colors with quality-based tinting
        if 'chord_root' in ov and ov['chord_root'] is not None:
            from engine import pitch_class_to_hue, apply_emotion_to_color
            base_hue = pitch_class_to_hue(ov['chord_root'])

            chord_quality = ov.get('chord_quality', 'maj')
            if chord_quality == 'min':
                base_hue = (base_hue + MONUMENT_CHORD_HUE_SHIFT_MINOR) % 360
            elif chord_quality == 'dom7':
                base_hue = (base_hue + MONUMENT_CHORD_HUE_SHIFT_DOM7) % 360
            elif chord_quality in ['dim', 'aug']:
                base_hue = (base_hue + MONUMENT_CHORD_HUE_SHIFT_TENSION) % 360

            effect.primary_color = apply_emotion_to_color(base_hue, 0.0, MONUMENT_FIXED_SATURATION_BOOST)
        else:
            # Default color when no chord detected
            effect.primary_color = (100, 100, 100)
    else:
        # No engine available - minimal fallback
        effect.brightness = STORM_BG_BRIGHTNESS_MIN_VAL
        effect.primary_color = (100, 100, 100)


def storm_bg(state: State, effect: Effect):
    """Background zone: Solid effect with scale/key color and emotion biasing."""
    
    # Check for sleep mode
    rt = getattr(state, 'rt', None)
    is_sleep_mode = getattr(rt, 'is_sleep_mode', False) if rt else False
    
    if is_sleep_mode:
        # Sleep mode: background turns off
        effect.is_on = int(SLEEP_MODE_BG_ON)
        return
    
    # Always on for background mood (when not in sleep mode)
    effect.is_on = 1
    
    # OLD BEHAVIOR (commented out - replaced by emotion engine):
    # effect.brightness = max(STORM_BG_BRIGHTNESS_MIN_VAL, min(VELOCITY_MAX_VAL, state.avg_velocity))
    # if len(state.active_notes2velocity) > 0:
    #     note2color = [Note2Color.blue_to_white(state, note) for note in state.active_notes2velocity.keys()]
    #     rgb = [sum(dim) // len(dim) for dim in zip(*note2color)]
    #     effect.primary_color = rgb
    # else:
    #     effect.reset()
    
    # NEW ARCHITECTURE: Driven entirely by emotion engine
    if rt and 'bg' in rt.overrides:
        ov = rt.overrides['bg']
        
        # Engine-controlled brightness (smoothed velocity)
        # effect.brightness = ov.get('brightness', STORM_BG_BRIGHTNESS_MIN_VAL)
        
        # Scale-based colors with emotion biasing
        if 'scale_root' in ov and ov['scale_root'] is not None:
            from engine import pitch_class_to_hue, apply_emotion_to_color
            base_hue = pitch_class_to_hue(ov['scale_root'])
            warmth_bias = ov.get('warmth_bias', 0.0)  # Joy/Melancholy balance
            saturation_boost = ov.get('saturation_boost', 0)  # Tension boost
            effect.primary_color = apply_emotion_to_color(base_hue, warmth_bias, saturation_boost)
        else:
            # Fallback: neutral blue if no scale detected yet
            effect.primary_color = (0, 100, 200)
    else:
        # No engine available - use minimal fallback
        effect.brightness = STORM_BG_BRIGHTNESS_MIN_VAL
        effect.primary_color = (0, 0, 255)  # Default blue

# from itertools import cycle
# iterations = cycle([13,14])

def storm_runner(state: State, effect: Effect):
    """Runner zone: rate selects effect (slow/medium/high) and chord sets color."""
    
    # Check for sleep mode
    rt = getattr(state, 'rt', None)
    is_sleep_mode = getattr(rt, 'is_sleep_mode', False) if rt else False
    
    if is_sleep_mode:
        # Sleep mode: Theater effect with soft ambient visuals
        effect.is_on = 1
        effect.name, effect.index = SLEEP_MODE_RUNNER_EFFECT
        effect.speed = SLEEP_MODE_RUNNER_SPEED
        effect.intensity = SLEEP_MODE_RUNNER_INTENSITY
        effect.brightness = SLEEP_MODE_RUNNER_BRIGHTNESS
        return
    
    # Active mode: effect will be set by engine logic below
    
    # OLD BEHAVIOR (commented out - replaced by emotion engine):
    # effect.is_on = int(at_least(state=state, num_active_notes=1))
    # if effect.is_on:
    #     effect.speed = state.avg_velocity
    #     effect.intensity = state.avg_notes
    
    # NEW ARCHITECTURE: Driven entirely by emotion engine
    if rt and 'runner' in rt.overrides:
        ov = rt.overrides['runner']
        
        # Engine controls on/off based on musical activity
        # effect.is_on = int(at_least(state=state, num_active_notes=1))

        effect.is_on = 1
        
        if effect.is_on:
            # Rate-based effect selection: choose among three WLED effects
            ov_speed = int(ov.get('speed', 0))  # 0..255 scaled from note rate
            if ov_speed < RUNNER_SPEED_THRESHOLD_SLOW:
                # Slow
                effect.name, effect.index, effect.speed = RUNNER_EFFECT_SLOW
            elif ov_speed < RUNNER_SPEED_THRESHOLD_MEDIUM:
                # Medium
                effect.name, effect.index, effect.speed = RUNNER_EFFECT_MEDIUM
            else:
                # High
                effect.name, effect.index, effect.speed = RUNNER_EFFECT_HIGH

            effect.brightness = ov.get('brightness', RUNNER_DEFAULT_BRIGHTNESS)
            
            # Chord-based colors for reactive movement
            if 'chord_root' in ov and ov['chord_root'] is not None:
                from engine import pitch_class_to_hue, apply_emotion_to_color
                base_hue = pitch_class_to_hue(ov['chord_root'])
                warmth_bias = ov.get('warmth_bias', 0.0)  # Emotion-based warmth
                # Runners get less saturation boost (more subtle than monuments)
                saturation_boost = ov.get('saturation_boost', 0) // RUNNER_SATURATION_DIVISOR
                effect.primary_color = apply_emotion_to_color(base_hue, warmth_bias, saturation_boost)
            else:
                # Fallback: neutral color if no chord detected
                effect.primary_color = (100, 100, 100)
    else:
        # No engine available - turn off
        effect.is_on = 0

def rainbow_mon(state: State, effect: Effect):
    effect.is_on = int(at_least(state=state, num_active_notes=1))
    if effect.is_on:
        effect.intensity = state.avg_velocity


def rainbow_bg(state: State, effect: Effect):
    effect.brightness = max(STORM_BG_BRIGHTNESS_MIN_VAL, min(VELOCITY_MAX_VAL, state.avg_velocity))


def rainbow_runner(state: State, effect: Effect):
    effect.is_on = int(at_least(state=state, num_active_notes=1))

    if effect.is_on and state.active_notes2velocity:
        # Get the first active note for color
        first_note = list(state.active_notes2velocity.keys())[0]
        r, g, b = Note2Color.circumference_color(state, first_note)
        effect.primary_color = (r, g, b)
        
        effect.speed = state.avg_velocity
        effect.brightness = state.avg_velocity
        effect.intensity = state.avg_notes


def spring_mon(state: State, effect: Effect):
    # Spring mon: random on segments when any note is played
    effect.is_on = int(at_least(state=state, num_active_notes=1))
    if effect.is_on:
        effect.intensity = state.avg_velocity


def spring_bg(state: State, effect: Effect):
    effect.brightness = max(STORM_BG_BRIGHTNESS_MIN_VAL, min(VELOCITY_MAX_VAL, state.avg_velocity))


def spring_runner(state: State, effect: Effect):
    effect.is_on = int(at_least(state=state, num_active_notes=1))

    if effect.is_on:
        effect.brightness = state.avg_velocity
        effect.speed = state.avg_velocity


def summer_mon(state: State, effect: Effect):
    # Summer mon is always on (4 segments), velocity controls speed
    effect.is_on = 1
    effect.speed = state.avg_velocity


def summer_bg(state: State, effect: Effect):
    effect.brightness = max(STORM_BG_BRIGHTNESS_MIN_VAL, min(VELOCITY_MAX_VAL, state.avg_velocity))


def summer_runner(state: State, effect: Effect):
    effect.is_on = int(at_least(state=state, num_active_notes=1))

    if effect.is_on:
        # Choose summer colors: red/orange/yellow/white
        summer_colors = [(255, 0, 0), (255, 165, 0), (255, 255, 0), (255, 255, 255)]
        # Use velocity to determine color intensity
        color_index = (state.avg_velocity // 64) % len(summer_colors)
        effect.primary_color = summer_colors[color_index]
        effect.brightness = state.avg_velocity

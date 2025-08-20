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

from globals import VELOCITY_MAX_VAL, STORM_BG_BRIGHTNESS_MIN_VAL
import math


def at_least(state: State, num_active_notes: int):
    return len(state.active_notes2velocity) >= num_active_notes


def storm_mon(state: State, effect: Effect):
    """Monument zone: chord-change accents with emotion-driven intensity and colors."""
    
    # OLD BEHAVIOR (commented out - replaced by emotion engine):
    # effect.is_on = int(at_least(state=state, num_active_notes=4) and state.avg_velocity >= (VELOCITY_MAX_VAL // 2))
    
    # NEW ARCHITECTURE: Driven entirely by emotion engine
    rt = getattr(state, 'rt', None)
    if rt and 'mon' in rt.overrides:
        ov = rt.overrides['mon']
        
        # Engine controls on/off and intensity based on chord changes and emotion
        effect.is_on = 1 if 'intensity' in ov and ov['intensity'] > 0 else 0
        
        if effect.is_on:
            effect.intensity = ov['intensity']  # Emotion-scaled intensity
            
            # Chord-specific accent colors with quality-based tinting
            if 'chord_root' in ov and ov['chord_root'] is not None:
                from engine import pitch_class_to_hue, apply_emotion_to_color
                base_hue = pitch_class_to_hue(ov['chord_root'])
                
                # Quality-based color tinting for musical meaning
                chord_quality = ov.get('chord_quality', 'maj')
                if chord_quality == 'min':
                    base_hue = (base_hue + 240) % 360  # shift toward blue for minor
                elif chord_quality == 'dom7':
                    base_hue = (base_hue + 45) % 360   # shift toward amber for dom7
                elif chord_quality in ['dim', 'aug']:
                    base_hue = (base_hue + 300) % 360  # shift toward magenta for tension
                
                # High saturation for monuments (accents should be vivid)
                effect.primary_color = apply_emotion_to_color(base_hue, 0.0, 30)
    else:
        # No engine available - turn off
        effect.is_on = 0


def storm_bg(state: State, effect: Effect):
    """Background zone: stable mood canvas driven by scale/key and emotion."""
    
    # Always on for background mood
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
    rt = getattr(state, 'rt', None)
    if rt and 'bg' in rt.overrides:
        ov = rt.overrides['bg']
        
        # Engine-controlled brightness (smoothed velocity)
        effect.brightness = ov.get('brightness', STORM_BG_BRIGHTNESS_MIN_VAL)
        
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


def storm_runner(state: State, effect: Effect):
    """Runner zone: motion and pace driven by note rate and chord colors."""
    
    # OLD BEHAVIOR (commented out - replaced by emotion engine):
    # effect.is_on = int(at_least(state=state, num_active_notes=1))
    # if effect.is_on:
    #     effect.speed = state.avg_velocity
    #     effect.intensity = state.avg_notes
    
    # NEW ARCHITECTURE: Driven entirely by emotion engine
    rt = getattr(state, 'rt', None)
    if rt and 'runner' in rt.overrides:
        ov = rt.overrides['runner']
        
        # Engine controls on/off based on musical activity
        effect.is_on = int(at_least(state=state, num_active_notes=1))
        
        if effect.is_on:
            # Engine-controlled speed (based on note rate, not velocity)
            effect.speed = ov.get('speed', 50)  # Smoothed note rate
            effect.intensity = state.avg_notes  # Keep this from old behavior for now
            
            # Chord-based colors for reactive movement
            if 'chord_root' in ov and ov['chord_root'] is not None:
                from engine import pitch_class_to_hue, apply_emotion_to_color
                base_hue = pitch_class_to_hue(ov['chord_root'])
                warmth_bias = ov.get('warmth_bias', 0.0)  # Emotion-based warmth
                # Runners get less saturation boost (more subtle than monuments)
                saturation_boost = ov.get('saturation_boost', 0) // 2
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

from modules import State, Effect, Note2Color

from globals import VELOCITY_MAX_VAL, STORM_BG_BRIGHTNESS_MIN_VAL
import math


def at_least(state: State, num_active_notes: int):
    return len(state.active_notes2velocity) >= num_active_notes


def storm_mon(state: State, effect: Effect):
    effect.is_on = int(at_least(state=state, num_active_notes=4) and state.avg_velocity >= (VELOCITY_MAX_VAL // 2))


def storm_bg(state: State, effect: Effect):
    effect.brightness = max(STORM_BG_BRIGHTNESS_MIN_VAL, min(VELOCITY_MAX_VAL, state.avg_velocity))

    if len(state.active_notes2velocity) > 0:
        note2color = [Note2Color.blue_to_white(state, note) for note in state.active_notes2velocity.keys()]
        rgb = [sum(dim) // len(dim) for dim in zip(*note2color)]
        effect.primary_color = rgb
    else:
        effect.reset()


def storm_runner(state: State, effect: Effect):
    effect.is_on = int(at_least(state=state, num_active_notes=1))

    if effect.is_on:
        effect.speed = state.avg_velocity
        effect.intensity = state.avg_notes

def rainbow_mon(state: State, effect: Effect):
    effect.is_on = int(at_least(state=state, num_active_notes=1))


def rainbow_bg(state: State, effect: Effect):
    effect.brightness = max(min(VELOCITY_MAX_VAL, ))


def rainbow_runner(state: State, effect: Effect):
    pass


def spring_mon(state: State, effect: Effect):
    effect.is_on = int(at_least(state=state, num_active_notes=4) and state.avg_velocity >= (VELOCITY_MAX_VAL // 2))


def spring_bg(state: State, effect: Effect):
    effect.brightness = max(min(VELOCITY_MAX_VAL, ))


def spring_runner(state: State, effect: Effect):
    pass


def summer_mon(state: State, effect: Effect):
    effect.is_on = int(at_least(state=state, num_active_notes=4) and state.avg_velocity >= (VELOCITY_MAX_VAL // 2))


def summer_bg(state: State, effect: Effect):
    effect.brightness = max(min(VELOCITY_MAX_VAL, ))


def summer_runner(state: State, effect: Effect):
    pass

from modules import Vibe, State, Effect, VibeController, LEDZone
import asyncio
import rtmidi
import time
from globals import STORM_BG_BRIGHTNESS_MIN_VAL
from behaviors import storm_mon, storm_bg, storm_runner, rainbow_mon, rainbow_bg, rainbow_runner, spring_mon, spring_bg, spring_runner, summer_mon, summer_bg, summer_runner
from utils import connect_devices, system_report
from engine import RTState

"""
Entry point: sets up vibes/zones, ingests MIDI quickly, runs a fixed-rate
render loop (~20 Hz), and lets behaviors translate state to WLED params.

We attach a small real-time engine at `state.rt` that:
- smooths velocity and note rate,
- tracks chord (fast, with stability/hold),
- estimates the key/scale (slow, from recent notes),
- maintains a tiny 4D emotion vector,
- provides minimal per-zone overrides for brightness/speed/accents.
"""


def init_vibes() -> VibeController:
    controller = VibeController()

    storm = Vibe()
    controller.add_vibe('storm', storm)
    storm.add_zone('mon',
                   LEDZone(effect=Effect(name='Rocktaves', index=185, speed=100, intensity=100), behavior=storm_mon))
    storm.add_zone('bg',
                   LEDZone(effect=Effect(name='Blurz', index=163, is_on=1, brightness=STORM_BG_BRIGHTNESS_MIN_VAL,
                                         primary_color=(0, 0, 255)), behavior=storm_bg))
    storm.add_zone('runner',
                   LEDZone(effect=Effect(name='Chase', index=28, primary_color=(255, 0, 255)), behavior=storm_runner))

    # rainbow = Vibe()
    # controller.add_vibe('rainbow', rainbow)
    # rainbow.add_zone('mon',
    #                  LEDZone(effect=Effect(name='Glitter', index=103, primary_color=(255, 255, 255)), behavior=rainbow_mon))
    # rainbow.add_zone('bg',
    #                  LEDZone(effect=Effect(name='Blurz', index=163, is_on=1, primary_color=(173, 216, 230), secondary_color=(255, 255, 255)), behavior=rainbow_bg))
    # rainbow.add_zone('runner',
    #                  LEDZone(effect=Effect(name='Chase', index=33), behavior=rainbow_runner))

    # spring = Vibe()
    # controller.add_vibe('spring', spring)
    # spring.add_zone('mon',
    #                 LEDZone(effect=Effect(name='Glitter', index=103, primary_color=(0, 255, 0), secondary_color=(255, 255, 255)), behavior=spring_mon))
    # spring.add_zone('bg',
    #                 LEDZone(effect=Effect(name='Chase', index=60, is_on=1, speed=23, intensity=60, primary_color=(255, 255, 0)), behavior=spring_bg))
    # spring.add_zone('runner',
    #                 LEDZone(effect=Effect(name='Chase', index=140, primary_color=(0, 0, 255)), behavior=spring_runner))

    # summer = Vibe()
    # controller.add_vibe('summer', summer)
    # summer.add_zone('mon',
    #                 LEDZone(effect=Effect(name='Sunrise', index=104, is_on=1), behavior=summer_mon))
    # summer.add_zone('bg',
    #                 LEDZone(effect=Effect(name='Tri-Fade', index=56, is_on=1, speed=10, primary_color=(255, 255, 0), secondary_color=(255, 0, 0), third_color=(255, 165, 0)), behavior=summer_bg))
    # summer.add_zone('runner',
    #                 LEDZone(effect=Effect(name='Solid', index=0), behavior=summer_runner))

    return controller


async def main():
    state = State(min_key_val=36, max_key_val=84, num_intervals=6)
    # Attach real-time engine without changing State class definition
    state.rt = RTState(scale_window_s=3.0)
    vibe_controller = init_vibes()
    connect_devices(vibe_controller)

    midi_in = rtmidi.RtMidiIn()
    ports = range(midi_in.getPortCount())

    if ports:
        for i in ports:
            print(midi_in.getPortName(i))
        midi_in.openPort(0)

        # await vibe_controller.set_random_vibe()
        await vibe_controller.set_specific_vibe('storm')
        system_report(vibe_controller)

        # Fixed-rate render with fast MIDI ingestion
        last_tick = time.time()
        while True:
            m = midi_in.getMessage(0.001)  # fast poll
            if m:
                state.update(m)
                state.rt.ingest_midi(m, state.active_notes2velocity)

            now = time.time()
            if now - last_tick >= 0.05:  # ~20 Hz
                state.rt.tick(state.active_notes2velocity)
                await vibe_controller.fire(state)
                last_tick = now
    else:
        print('NO MIDI INPUT PORTS!')


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

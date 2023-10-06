from modules import Vibe, State, Effect, VibeController, LEDZone
import asyncio
import rtmidi
from globals import STORM_BG_BRIGHTNESS_MIN_VAL
from behaviors import storm_mon, storm_bg, storm_runner
from utils import connect_devices, system_report


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
    #
    # spring = Vibe()
    # controller.add_vibe('spring', spring)
    #
    # summer = Vibe()
    # controller.add_vibe('summer', summer)

    # summer.add_zone('runner', LEDZone(effect=Effect(name='Solid', index=0), behavior=)

    return controller


async def main():
    state = State(min_key_val=36, max_key_val=84, num_intervals=6)
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

        # TODO: recovery from router restart
        while True:
            m = midi_in.getMessage(0.01)  # some timeout in ms
            if m:
                state.update(m)
                await vibe_controller.fire(state)
    else:
        print('NO MIDI INPUT PORTS!')


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

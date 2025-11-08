from modules import Vibe, State, Effect, VibeController, LEDZone
import asyncio
import rtmidi
import time
import logging
import threading
import queue
from config import (
    STORM_BG_BRIGHTNESS_MIN_VAL,
    ENGINE_SCALE_WINDOW_S,
    VISUAL_TICK_RATE_S,
    MIDI_EVENT_QUEUE_SIZE,
    MIDI_POLL_TIMEOUT_MS,
    MAIN_LOOP_SLEEP_S,
    LED_TASK_TIMEOUT_S,
    LOG_MIDI_EVENTS,
    MIDI_MIN_KEY,
    MIDI_MAX_KEY,
    MIDI_NUM_INTERVALS,
)
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

ARCHITECTURE: Uses parallel execution with workers:
- MIDI input thread: polls MIDI port and pushes events to queue
- Main async loop: drains queue at fixed rate (~20 Hz) and updates visuals
- Non-blocking LED updates using asyncio tasks
"""


def init_vibes() -> VibeController:
    controller = VibeController()

    storm = Vibe()
    controller.add_vibe('storm', storm)
    
    # Monument: start with Solid; brightness will follow velocity via behavior
    storm.add_zone('mon',
                   LEDZone(effect=Effect(name='Solid', index=0, speed=100, intensity=100, is_on=1),
                          behavior=storm_mon))
    # Background: use Solid for a clear canvas (color set by engine scale)
    storm.add_zone('bg',
                   LEDZone(effect=Effect(name='Solid', index=0, is_on=1,
                                         brightness=STORM_BG_BRIGHTNESS_MIN_VAL,
                                         primary_color=(0, 0, 255)),
                          behavior=storm_bg))
    # Runner: initial effect (slow tier). Behavior will switch by rate.
    storm.add_zone('runner',
                   LEDZone(effect=Effect(name='Android', index=27, primary_color=(255, 0, 255),
                                          transition_time=0),
                          behavior=storm_runner))

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
    """Main loop for live MIDI input with parallel processing."""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Logger levels: show emotion diagnostics, suppress chord logs
    logging.getLogger('emotion').setLevel(logging.INFO)
    logging.getLogger('chord.system').setLevel(logging.INFO)
    logging.getLogger('chord.tracker').setLevel(logging.INFO)
    
    # Initialize visual system
    state = State(min_key_val=MIDI_MIN_KEY, max_key_val=MIDI_MAX_KEY, num_intervals=MIDI_NUM_INTERVALS)
    state.rt = RTState(scale_window_s=ENGINE_SCALE_WINDOW_S)  # Emotion-based engine
    vibe_controller = init_vibes()
    connect_devices(vibe_controller)

    # Check for MIDI input ports
    midi_in = rtmidi.RtMidiIn()
    port_count = midi_in.getPortCount()
    
    if port_count == 0:
        print('❌ NO MIDI INPUT PORTS FOUND!')
        print('   Please connect a MIDI device and try again.')
        return
    
    # List available ports
    print("🎹 Available MIDI Input Ports:")
    for i in range(port_count):
        print(f"  [{i}] {midi_in.getPortName(i)}")
    
    # Open first port (or modify to select specific port)
    port_to_use = 0
    print(f"\n🔌 Opening MIDI port {port_to_use}: {midi_in.getPortName(port_to_use)}")
    midi_in.openPort(port_to_use)
    
    await vibe_controller.set_specific_vibe('storm')
    system_report(vibe_controller)
    
    print("🌟 Starting live MIDI input with emotion-based visuals (parallel)...")
    print("   MIDI input runs in separate thread; visuals run at fixed rate.")
    print("   Press Ctrl+C to stop.\n")

    # Thread-safe queue for MIDI events from the input thread
    event_queue: "queue.Queue[rtmidi.MidiMessage | None]" = queue.Queue(maxsize=MIDI_EVENT_QUEUE_SIZE)
    
    def midi_input_worker():
        """Worker thread that polls MIDI input and pushes to queue."""
        try:
            while True:
                m = midi_in.getMessage(MIDI_POLL_TIMEOUT_MS)
                if m:
                    if LOG_MIDI_EVENTS:
                        if m.isNoteOn():
                            print(f"♪ Note ON:  {m.getNoteNumber()} (vel: {m.getVelocity()})")
                        elif m.isNoteOff():
                            print(f"♪ Note OFF: {m.getNoteNumber()}")
                    
                    # Push to visuals queue (drop oldest if full)
                    try:
                        event_queue.put_nowait(m)
                    except queue.Full:
                        try:
                            _ = event_queue.get_nowait()
                            event_queue.put_nowait(m)
                        except queue.Empty:
                            pass
        except KeyboardInterrupt:
            pass
        finally:
            # Signal completion
            try:
                event_queue.put_nowait(None)
            except Exception:
                pass
    
    # Start MIDI input thread
    midi_thread = threading.Thread(target=midi_input_worker, name="midi-input", daemon=True)
    midi_thread.start()
    
    # Visuals loop (fixed-rate), non-blocking LED sends
    last_tick = time.time()
    led_task = None
    running = True
    
    try:
        while running:
            # Drain events quickly
            drained = 0
            while True:
                try:
                    m = event_queue.get_nowait()
                except queue.Empty:
                    break
                if m is None:
                    running = False
                    break
                state.update(m)
                state.rt.ingest_midi(m, state.active_notes2velocity)
                drained += 1
            
            # Fixed-rate visuals
            now = time.time()
            if now - last_tick >= VISUAL_TICK_RATE_S:
                state.rt.tick(state.active_notes2velocity)
                # Fire LED updates without blocking the timing loop; drop if previous still running
                if led_task is None or led_task.done():
                    led_task = asyncio.create_task(vibe_controller.fire(state))
                last_tick = now
            
            # Small sleep to yield
            await asyncio.sleep(MAIN_LOOP_SLEEP_S)
    
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        running = False
    
    # Wait for any pending LED task to finish briefly
    if led_task is not None:
        try:
            await asyncio.wait_for(led_task, timeout=LED_TASK_TIMEOUT_S)
        except Exception:
            pass
    
    print("👋 MIDI input stopped!")


if __name__ == "__main__":
    print("🎹 Live MIDI Input with Emotion-Based Visuals")
    print("=" * 50)
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

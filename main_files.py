from modules import Vibe, State, Effect, VibeController, LEDZone
import asyncio
import time
import mido
import fluidsynth
from globals import STORM_BG_BRIGHTNESS_MIN_VAL
from behaviors import storm_mon, storm_bg, storm_runner, rainbow_mon, rainbow_bg, rainbow_runner, spring_mon, spring_bg, spring_runner, summer_mon, summer_bg, summer_runner
from utils import connect_devices, system_report
from engine import RTState
from midi_adapter import MidoToRtMidiAdapter
import logging
import threading
import queue

LOG_MIDI_EVENTS = False

"""
MIDI File Playback Mode: Play MIDI files with FluidSynth audio and visual effects.

Loads and plays MIDI files through FluidSynth for audio output while simultaneously
driving the emotion-based visual system. Great for testing the system with known
musical content and demonstrating different emotional responses.

Available MIDI files:
- coldplay.mid, mozart.mid, piano_man.mid, stand_by_me.mid
- stair_h.mid (Stairway to Heaven), funk_demo_song.mid
- soft.mid, soft2.mid, touch_me.mid
"""


def init_vibes() -> VibeController:
    controller = VibeController()

    storm = Vibe()
    controller.add_vibe('storm', storm)

    # storm.add_zone('mon',
    #                LEDZone(effect=Effect(name='Rocktaves', index=185, speed=100, intensity=100), behavior=storm_mon))

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

    return controller


async def main():
    """Main loop for MIDI file playback with audio and visuals."""

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Logger levels: show emotion diagnostics, suppress chord logs
    logging.getLogger('emotion').setLevel(logging.INFO)
    logging.getLogger('chord.system').setLevel(logging.INFO)
    logging.getLogger('chord.tracker').setLevel(logging.INFO)
    
    # Configuration - change these to try different files
    sf2_path = "midi_player/virtual_synth/FluidR3_GM.sf2"
    mid_path = "midi_player/midi_files/coldplay.mid"  # Change this file as needed

    # mid_path = "midi_player/archive_3/midi 3.mid"

    # mid_path = "midi_player/archive_3_trimmed/midi 2.mid"

    
    print(f"🎵 Loading MIDI file: {mid_path}")
    print(f"🔊 Using soundfont: {sf2_path}")
    
    # Initialize FluidSynth for audio output
    fs = fluidsynth.Synth()
    fs.start(driver="coreaudio")
    sfid = fs.sfload(sf2_path)
    fs.program_select(0, sfid, 0, 0)
    

    # Load MIDI file
    mid = mido.MidiFile(mid_path)
    print(f"📊 MIDI file loaded: {len(mid.tracks)} tracks, {mid.length:.1f} seconds")

    # Initialize visual system
    state = State(min_key_val=36, max_key_val=84, num_intervals=6)
    state.rt = RTState(scale_window_s=3.0)  # Emotion-based engine
    vibe_controller = init_vibes()
    connect_devices(vibe_controller)

    await vibe_controller.set_specific_vibe('storm')
    system_report(vibe_controller)

    print("🌟 Starting playback with emotion-based visuals (decoupled)...")
    print("   Audio plays in its own thread; visuals run at a fixed rate.")

    # Thread-safe queue for MIDI events from the audio thread
    event_queue: "queue.Queue[MidoToRtMidiAdapter]" = queue.Queue(maxsize=2048)

    def playback_worker():
        try:
            for msg in mid.play():
                m = MidoToRtMidiAdapter(msg)
                if m:
                    # Audio first: keep this tight and non-blocking
                    if m.isNoteOn():
                        fs.noteon(0, m.getNoteNumber(), m.getVelocity())
                        if LOG_MIDI_EVENTS:
                            print(f"♪ Note ON:  {m.getNoteNumber()} (vel: {m.getVelocity()})")
                    elif m.isNoteOff():
                        fs.noteoff(0, m.getNoteNumber())
                        if LOG_MIDI_EVENTS:
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
        finally:
            # Signal completion
            try:
                event_queue.put_nowait(None)  # type: ignore
            except Exception:
                pass

    # Start audio playback thread
    t = threading.Thread(target=playback_worker, name="midi-audio", daemon=True)
    t.start()

    # Visuals loop (fixed-rate), non-blocking LED sends
    last_tick = time.time()
    led_task = None
    running = True
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
        if now - last_tick >= 0.05:  # ~20 Hz
            state.rt.tick(state.active_notes2velocity)
            # Fire LED updates without blocking the timing loop; drop if previous still running
            if led_task is None or led_task.done():
                led_task = asyncio.create_task(vibe_controller.fire(state))
            last_tick = now

        # Small sleep to yield
        await asyncio.sleep(0.005)

    # Wait for any pending LED task to finish briefly
    if led_task is not None:
        try:
            await asyncio.wait_for(led_task, timeout=0.5)
        except Exception:
            pass
    print("🎵 Playback finished!")
    fs.delete()  # Clean up FluidSynth


if __name__ == "__main__":
    print("🎹 MIDI File Player with Emotion-Based Visuals")
    print("=" * 50)
    
    # List available MIDI files
    import os
    midi_dir = "midi_player/midi_files"
    if os.path.exists(midi_dir):
        print("Available MIDI files:")
        for f in sorted(os.listdir(midi_dir)):
            if f.endswith('.mid'):
                print(f"  - {f}")
        print()
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

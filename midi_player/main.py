import mido
import fluidsynth

def stream_with_embedded_synth(mid_path, sf2_path):
    fs = fluidsynth.Synth()
    fs.start(driver="coreaudio")

    sfid = fs.sfload(sf2_path)
    fs.program_select(0, sfid, 0, 0)

    mid = mido.MidiFile(mid_path)
    for msg in mid.play():
        if msg.type == 'note_on':
            fs.noteon(0, msg.note, msg.velocity)
            #debug for me
            print(msg.note, msg.velocity)
        elif msg.type == 'note_off':
            fs.noteoff(0, msg.note)
            print(msg.note)
    fs.delete()

if __name__ == "__main__":
    stream_with_embedded_synth(
        mid_path="./midi_files/stand_by_me.mid",
        sf2_path="./virtual_synth/FluidR3_GM.sf2"
    )

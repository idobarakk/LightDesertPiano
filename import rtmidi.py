import rtmidi
import requests

# requests.get('http://10.0.0.28/win&A=255')
midiin = rtmidi.RtMidiIn()

def print_message(midi):
    if midi.isNoteOn():
        print('ON: ', midi.getMidiNoteName(midi.getNoteNumber()), midi.getVelocity())
        requests.get(f'http://4.3.2.1/win&A={midi.getVelocity()}&TT=')
    elif midi.isNoteOff():
        print('OFF:', midi.getMidiNoteName(midi.getNoteNumber()))
        requests.get('http://4.3.2.1/win&A=0&TT=')
    elif midi.isController():
        print('CONTROLLER', midi.getControllerNumber(), midi.getControllerValue())

ports = range(midiin.getPortCount())
if ports:
    for i in ports:
        print(midiin.getPortName(i))
    # print("Opening port 0!") 
    # midiin.openPort(0)
    midiin.openPort(0)
    print(f"Port {i}: {midiin.getPortName(i)}")
    while True:
        m = midiin.getMessage(250) # some timeout in ms
        if m:
            print_message(m)
else:
    print('NO MIDI INPUT PORTS!')
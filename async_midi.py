import rtmidi
import asyncio
import aiohttp

ip = "192.168.31.209"
ip2= "192.168.31.65"

midiin = rtmidi.RtMidiIn()
active_notes = set()  # Store active note numbers
def color(note_number):
    numOfNotes = 84-48
    if note_number<54:
        Red = 255
        Blue = 0
        Green = int(255*(note_number-48)/6)
    elif note_number<60: 
        Red = int(255*(60-note_number)/6)
        Blue = 0
        Green = 255
    elif note_number<66: 
        Red = 0
        Blue = int(255*(note_number-60)/6)
        Green = 255
    elif note_number<72: 
        Red = 0
        Blue = 255
        Green = int(255*(72-note_number)/6)
    elif note_number<78: 
        Red = int(255*(note_number-72)/6)
        Blue = 255
        Green = 0
    elif note_number<=84: 
        Red = 255
        Blue = int(255*(84-note_number)/6)
        Green = 0
    return Red,Green,Blue

async def send_request(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                print(f"Request sent successfully: {url}")

async def send_request2(url2):
    async with aiohttp.ClientSession() as session:
        async with session.get(url2) as response:
            if response.status == 200:
                print(f"Request sent successfully: {url2}")

async def process_midi_events():
    ports = range(midiin.getPortCount())
    if ports:
        for i in ports:
            print(midiin.getPortName(i))
        midiin.openPort(0)
        print(f"Port {i}: {midiin.getPortName(i)}")
        while True:
            m = midiin.getMessage(250)  # some timeout in ms
            if m:
                await handle_midi_message(m)
    else:
        print('NO MIDI INPUT PORTS!')

async def handle_midi_message(midi):
    global active_notes
    
    if midi.isNoteOn():
        note_number = midi.getNoteNumber()
        active_notes.add(note_number)
        velocity = midi.getVelocity()
        Re,Gr,Bl = color(note_number)
        url = f'http://192.168.31.209/win&A={velocity}&R={Re}&B={Bl}&G={Gr}&R2={Gr}&B2={Re}&G2={Bl}&TT=50&FX=28'
        url2 = f'http://192.168.31.65/win&A={velocity}&R={Re}&B={Bl}&G={Gr}&R2={Gr}&B2={Re}&G2={Bl}&TT=50&FX=28'
        await send_request(url)
        print(f'ON: Note {note_number}, Velocity: {velocity}')
        await send_request2(url2)
        print(f'ON2: Note {note_number}, Velocity: {velocity}')
    elif midi.isNoteOff():
        note_number = midi.getNoteNumber()
        active_notes.discard(note_number)
        if not active_notes:
            url = f'http://192.168.31.209/win&A=10&TT=750&FX=38'
            url2 = f'http://192.168.31.65/win&A=10&TT=750&FX=38'
            await send_request(url)
            await send_request2(url2)
        print(f'OFF: Note {note_number}')
    elif midi.isController():
        controller_number = midi.getControllerNumber()
        controller_value = midi.getControllerValue()
        print(f'CONTROLLER {controller_number}, Value: {controller_value}')

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_midi_events())

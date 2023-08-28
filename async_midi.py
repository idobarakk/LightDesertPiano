import rtmidi
import asyncio
import aiohttp

ip = "192.168.0.121"
ip2= "192.168.0.121"

numOfKeys= 48
minKeyValue = 36
maxKeyValue = 84
interval = numOfKeys/6
intervals =[]

for i in range(1,7,1):
    intervals.append((i*interval)+minKeyValue)


midiin = rtmidi.RtMidiIn()
active_notes = set()  # Store active note numbers
active_velocity =set()
def color(note_number):
    if note_number<intervals[0]:
        Red = 255
        Blue = 0
        Green = int(255*(note_number-minKeyValue)/interval)
    elif note_number<intervals[1]:
        Red = int(255*(intervals[1]-note_number)/interval)
        Blue = 0
        Green = 255
    elif note_number<intervals[2]:
        Red = 0
        Blue = int(255*(note_number-intervals[2])/interval)
        Green = 255
    elif note_number<intervals[3]:
        Red = 0
        Blue = 255
        Green = int(255*(intervals[3]-note_number)/interval)
    elif note_number<intervals[4]:
        Red = int(255*(note_number-intervals[4])/interval)
        Blue = 255
        Green = 0
    elif note_number<=intervals[5]:
        Red = 255
        Blue = int(255*(intervals[5]-note_number)/interval)
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
        #print(f"Port {i}: {midiin.getPortName(i)}")
        while True:
            m = midiin.getMessage(25)  # some timeout in ms
            if m:
                await handle_midi_message(m)
    else:
        print('NO MIDI INPUT PORTS!')

async def handle_midi_message(midi):
    global active_notes
    global active_velocity
    
    if midi.isNoteOn():
        note_number = midi.getNoteNumber()
        active_notes.add(note_number)
        velocity = midi.getVelocity()
        active_velocity.add(velocity)
        Re,Gr,Bl = color(note_number)


       # url = f'http://{ip}/win&A={velocity}&R={Re}&B={Bl}&G={Gr}&R2={Gr}&B2={Re}&G2={Bl}&TT=50'
        url2 = f'http://{ip2}/win&A={velocity}&R={Re}&B={Bl}&G={Gr}&R2={Gr}&B2={Re}&G2={Bl}&TT=50'

        #await send_request(url)
        #print(f'ON: Note {note_number}, Velocity: {velocity}')
        # await send_request2(url2)
        #print(f'ON2: Note {note_number}, Velocity: {velocity}')

    elif midi.isNoteOff():
        note_number = midi.getNoteNumber()
        active_notes.discard(note_number)
        if not active_velocity:
            active_velocity.pop()
        #print(active_notes)
        if not active_notes:
            url = f'http://{ip}/win&A=0&TT=0&FX='
            url2 = f'http://{ip2}/win&A=0&TT=0&FX=38'
            await send_request(url)
            #await send_request2(url2)
       # print(f'OFF: Note {note_number}')
    if active_notes:
        total_velocity = sum(active_velocity) // len(active_notes)
        red_sum = green_sum = blue_sum = 0

        for note in active_notes:
            r, g, b = color(note)
            red_sum += r
            green_sum += g
            blue_sum += b

        red_avg = red_sum // len(active_notes)
        green_avg = green_sum // len(active_notes)
        blue_avg = blue_sum // len(active_notes)

        url = f'http://{ip}/win&A={total_velocity}&R={red_avg}&B={blue_avg}&G={green_avg}&R2={green_avg}&B2={red_avg}&G2={blue_avg}&TT=50'
        #url2 = f'http://{ip2}/win&A={velocity}&R={Re}&B={Bl}&G={Gr}&R2={Gr}&B2={Re}&G2={Bl}&TT=50'
        await send_request(url)
        # await send_request2(url2)
        # print(f'Active notes: {active_notes} {total_velocity} B={blue_avg}&G={green_avg}&R2={green_avg} ')

    elif midi.isController():
        controller_number = midi.getControllerNumber()
        controller_value = midi.getControllerValue()
        print(f'CONTROLLER {controller_number}, Value: {controller_value}')

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_midi_events())

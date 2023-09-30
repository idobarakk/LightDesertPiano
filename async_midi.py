import rtmidi
import asyncio
import aiohttp
from FX import FXBuild
# Storm
#Mon - 185 - condition to on:  >= multi note on (Over 4 notes) + over 50% velocity
#BG - 163 - always ON - Brigthness - velocity, color - notr (in blue to white range) (we need to set constant Spped and intensity)
#Runner - 28 - condition to on: >= one note on , color magenta , velocity-> speed , multi nots ->intesity

# rainbow -
#Mon - 103 - condition to on any note  - Velocity -> Intensity , color -> glitter: white, bg: random on each note
#BG - 163 - always ON - ALWAYS ON - color bg light blue - FX color - white
#Runner - 33 - condition to on: >= one note on , note -> color, velocity -> speed + brithness, multi nots ->intesity

# spring -MAYBE ADD RED
#Mon - 103 - 4 segments - condition to on any note: random on segments  - Velocity -> Intensity , color -> green /fx color-white
#BG - 60 always ON - Brigthness - velocity , color -  yellow\white spring vibe, speed 23 , intesity 60
#Runner - 140 - condition to on: >= one note, color blue \ white , velocity -> brightness + speed

# summer -MAYBE ADD RED
#Mon - 104 (Sunrise) - 4 segments always on (effect apply on each segment, speed + random on each segment=[seed+r]) - Velocity -> speed=seed
#BG - 56 (Tri-Fade) always ON - Brigthness - velocity , color -  [yellow,red,orange], speed - constant (slow)
#Runner - 0 (Solid) - condition to on: >= one note, color red/orange/yellow/white , velocity -> brightness

ip = "192.168.1.136"
ip2 = "192.168.1.147"

numOfKeys= 48  # num of Piano Keys
minKeyValue = 36 # lowest Key note num
maxKeyValue = 84 # lowest Key note num
interval = numOfKeys/6 # num of key per interval
fxs ={"chase":28,"Juggles":130,"Strobe":23}

# name : FX num , FX color, bgn color, speed, width brightness
wait_fxs ={"Colortwinkles":[74,"","",10,""]}

chaseOnBlack = FXBuild("chase",28,"",[0,0,0],200,"","")
solid = FXBuild("solid", 0, "","","","","")

#piano 6 section - acordding to HSV Coloe RGB graph
intervals =[]
for i in range(1,7,1):
    intervals.append((i*interval)+minKeyValue)

midiin = rtmidi.RtMidiIn()

# ****** We need to change it to dic **********
active_notes = {}  # Store active note numbers
#active_velocity =set() # Store active note Velocity


#full color circle
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
                pass
                #print(f"Request sent successfully: {url}")

async def send_request2(url2):
    async with aiohttp.ClientSession() as session:
        async with session.get(url2) as response:
            if response.status == 200:
               pass
                #print(f"Request sent successfully: {url2}")

async def process_midi_events():
    ports = range(midiin.getPortCount())
    if ports:
        for i in ports:
            print(midiin.getPortName(i))
        midiin.openPort(0)
        print(f"Port {i}: {midiin.getPortName(i)}")

        # set fx setting
        url = f'http://{ip}/win&A=0&TT=50&FX={chaseOnBlack.index}&SX={chaseOnBlack.speed}&R2={chaseOnBlack.bgcolor[0]}&G2={chaseOnBlack.bgcolor[1]}&B2={chaseOnBlack.bgcolor[2]}'
        url2 = f'http://{ip2}/win&A=0&TT=50&FX={solid.index}'
        await send_request(url)
        await send_request(url2)

        while True:
            m = midiin.getMessage(0.01)# some timeout in ms
            if m:
                await handle_midi_message(m)
    else:
        print('NO MIDI INPUT PORTS!')

async def handle_midi_message(midi):

    global active_notes
    #global active_velocity



    if midi.isNoteOn():
        note_number = midi.getNoteNumber()
        velocity = midi.getVelocity()
        active_notes[note_number] = velocity
        #active_velocity.add(velocity)
        R,G,B = color(note_number)

        print(velocity)
        url = f'http://{ip}/win&A={active_notes[note_number]}&R={R}&G={G}&B={B}&IX=2'
        url2 = f'http://{ip2}/win&A={active_notes[note_number]}&R={R}&G={G}&B={B}&IX=2'

        #await send_request(url)
        #print(f'ON: Note {note_number}, Velocity: {velocity}')
        # await send_request2(url2)
        #print(f'ON2: Note {note_number}, Velocity: {velocity}')

    elif midi.isNoteOff():
        note_number = midi.getNoteNumber()
        del active_notes[note_number]
        #print(active_notes)
        if not active_notes:
            url = f'http://{ip}/win&A=0&TT=0'
            url2 =  f'http://{ip2}/win&A=0&TT=0'
            await send_request(url)
            await send_request2(url2)
       # print(f'OFF: Note {note_number}')
    if active_notes:
        total_velocity = sum(active_notes.values()) // len(active_notes.keys())
        red_sum = green_sum = blue_sum = 0

        for note in active_notes:
            r, g, b = color(note)
            red_sum += r
            green_sum += g
            blue_sum += b

        red_avg = red_sum // len(active_notes.keys())
        green_avg = green_sum // len(active_notes.keys())
        blue_avg = blue_sum // len(active_notes.keys())

        url = f'http://{ip}/win&A={total_velocity}&R={red_avg}&B={blue_avg}&G={green_avg}&TT=50&'
        url2 = f'http://{ip2}/win&A={total_velocity}&R={red_avg}&B={blue_avg}&G={green_avg}&&TT=50&'
        await send_request(url)
        await send_request2(url2)
        #print(f'Active notes: {active_notes} {total_velocity} B={blue_avg}&G={green_avg}&R2={green_avg} ')

    elif midi.isController():
        controller_number = midi.getControllerNumber()
        controller_value = midi.getControllerValue()
        #print(f'CONTROLLER {controller_number}, Value: {controller_value}')

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_midi_events())

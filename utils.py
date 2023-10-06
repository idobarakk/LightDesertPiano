import aiohttp
import asyncio
from typing import List
import warnings
import json

async def send_request(session, url):
    async with session.get(url) as response:
        return response.status


async def parallel_update_led(urls: List[str]):
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session, url) for url in urls]
        await asyncio.gather(*tasks)


def connect_devices(vibe_controller, file_path='./device_conf.json'):
    "Pre: vibes are set"
    with open(file_path) as f:
        conf = json.load(f)

        for vibe in vibe_controller.vibes.values():
            for name in conf.keys():
                if conf[name]:
                    vibe.set_connection(name, conf[name])
                else:
                    warnings.warn(f"Zone {name} isn't configured")


def system_report(vibe_controller):
    print(f"-Leading Vibe = [{vibe_controller.lead_vibe}]")
    for vibe_name, vibe in vibe_controller.vibes.items():
        print(f"--Reporting on vibe [{vibe_name}]--")
        for zone_name, zone in vibe.zones.items():
            connections = zone.connections if zone.is_connected() else 'No Connections'
            print(f"---Found zone [{zone_name}] with effect=[{zone.effect.name}], devices-connected={connections}")


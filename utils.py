import aiohttp
import asyncio
from typing import List, Optional, Dict
import warnings
import json
import logging
from collections import defaultdict

# Configure logger for device connection issues
logger = logging.getLogger('device_connection')

# Track unavailable devices to reduce log spam
_unavailable_devices: Dict[str, int] = defaultdict(int)
_warning_threshold = 3  # Only log first 3 failures, then every 100th

async def send_request(session, url, timeout=2.0):
    """
    Send HTTP request to LED device.
    Returns (success: bool, status: Optional[int], url: str)
    """
    try:
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        async with session.get(url, timeout=timeout_obj) as response:
            # Reset failure count on success
            if url in _unavailable_devices:
                del _unavailable_devices[url]
            return (True, response.status, url)
    except asyncio.TimeoutError:
        _unavailable_devices[url] += 1
        count = _unavailable_devices[url]
        if count <= _warning_threshold or count % 100 == 0:
            logger.warning(f"⏱️  Timeout connecting to device: {url} (failure #{count})")
        return (False, None, url)
    except aiohttp.ClientConnectorError as e:
        _unavailable_devices[url] += 1
        count = _unavailable_devices[url]
        if count <= _warning_threshold or count % 100 == 0:
            logger.warning(f"🔌 Cannot connect to device: {url} (failure #{count})")
        return (False, None, url)
    except Exception as e:
        _unavailable_devices[url] += 1
        count = _unavailable_devices[url]
        if count <= _warning_threshold or count % 100 == 0:
            logger.warning(f"⚠️  Error connecting to device: {url} - {str(e)} (failure #{count})")
        return (False, None, url)


async def parallel_update_led(urls: List[str], timeout=2.0):
    """
    Send HTTP requests to LED devices in parallel.
    Continues even if some devices are unavailable.
    """
    if not urls:
        return
    
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session, url, timeout) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        successful = 0
        failed = 0
        for result in results:
            if isinstance(result, Exception):
                failed += 1
                logger.error(f"❌ Unexpected error: {result}")
            elif isinstance(result, tuple):
                success, status, url = result
                if success:
                    successful += 1
                else:
                    failed += 1
        
       # Only log summary if there are failures and it's not too frequent
        if failed > 0:
            # Log summary occasionally (every 50 updates with failures)
            if not hasattr(parallel_update_led, '_summary_counter'):
                parallel_update_led._summary_counter = 0
            parallel_update_led._summary_counter += 1
            if parallel_update_led._summary_counter % 50 == 0:
                logger.info(f"📊 Device status: {successful} successful, {failed} unavailable (continuing with available devices)")


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


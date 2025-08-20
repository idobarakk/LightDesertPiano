from typing import Optional, Callable, Tuple, List, Dict
from dataclasses import dataclass, field, fields, asdict
import urllib.parse
import random
from utils import parallel_update_led


class State:
    """Minimal musical state extracted directly from MIDI events.

    Kept intentionally small: active notes (for chord), average velocity and
    note index (for simple mappings), and precomputed intervals (for color
    mapping helpers). A real-time engine may be attached at runtime as
    `state.rt` to provide higher-level features (chord/scale/emotion).
    """
    def __init__(self, min_key_val=36, max_key_val=84, num_intervals=6):
        self.active_notes2velocity = {}
        self.min_key_val = min_key_val
        self.max_key_val = max_key_val
        self.num_of_keys = max_key_val - min_key_val
        self.num_intervals = num_intervals
        # TODO: change interval to interval array. (This definition is only true when all intervals have the same size)
        self.interval = self.num_of_keys / 6

        interval_size = self.num_of_keys / self.num_intervals
        intervals = []
        for i in range(1, self.num_intervals + 1):
            intervals.append((i * interval_size) + self.min_key_val)
        self.intervals = intervals

        self.avg_notes = 0
        self.avg_velocity = 0

        self.history = {}

    def update(self, midi) -> None:
        """Update active notes from a single MIDI message (note on/off)."""
        note_number = midi.getNoteNumber()
        if midi.isNoteOn():
            velocity = midi.getVelocity()
            self.active_notes2velocity[note_number] = velocity
        elif midi.isNoteOff():
            del self.active_notes2velocity[note_number]

        self.reduce_stats_()

    def reduce_stats_(self):
        """Compute simple averages from currently held notes.

        - avg_notes: average note number (rough register/centroid)
        - avg_velocity: average velocity (how hard you currently play)
        """
        if len(self.active_notes2velocity) > 0:
            self.avg_notes = sum(self.active_notes2velocity.keys()) // len(self.active_notes2velocity)
            self.avg_velocity = sum(self.active_notes2velocity.values()) // len(self.active_notes2velocity)


def request_alias(name: str) -> dict:
    return {'alias': name}


@dataclass
class Effect:
    name: str
    index: int = field(default=None, metadata=request_alias("FX"))
    is_on: int = field(default=0, metadata=request_alias("T"))
    brightness: int = field(default=0, metadata=request_alias("A"))
    transition_time: int = field(default=50, metadata=request_alias("TT"))
    speed: Optional[int] = field(default=None, metadata=request_alias("SX"))
    intensity: Optional[int] = field(default=None, metadata=request_alias("IX"))

    # mark list values with #L_ alias.
    primary_color: Tuple[int, int, int] = field(default=None, metadata=request_alias("#L_R,G,B"))
    secondary_color: Tuple[int, int, int] = field(default=None, metadata=request_alias("#L_R2,G2,B2"))
    third_color: Tuple[int, int, int] = field(default=None, metadata=request_alias("#L_R3,G3,B3"))

    def __post_init__(self):
        # Store a deep copy of the non-None initial state
        self._snapshot = asdict(self)
        self._initial_state = {k: v for k, v in asdict(self).items() if v is not None and k not in ['name', 'index']}

    def reset(self):
        for f in fields(self):
            if f.name in self._initial_state:
                setattr(self, f.name, self._initial_state[f.name])

    def get_changed_fields(self):
        current_state = asdict(self)
        changed_params = [key for key in current_state if current_state[key] != self._snapshot[key]]
        self._snapshot = current_state
        return changed_params

    def build_request_str(self, is_init=False) -> str:
        dataclass_fields = fields(self)

        changed_fields = self.get_changed_fields() if not is_init else None
        # If nothing changed and not initializing, skip sending
        if not is_init and not changed_fields:
            return None

        fields_dict = {
            f.metadata.get('alias', f.name): getattr(self, f.name)
            for f in dataclass_fields
            if is_init or f.name in changed_fields or f.name in ['name', 'index']
        }

        fields_dict = {k: v for k, v in fields_dict.items() if v is not None}

        # dealing with lists
        fields_dict = Effect.convert_list_values(fields_dict)

        encoded_fields = {k: urllib.parse.quote_plus(str(v)) for k, v in fields_dict.items()}

        query_string = '&'.join(f"{k}={v}" for k, v in encoded_fields.items())

        return query_string

    @staticmethod
    def convert_list_values(data: Dict) -> Dict:
        """Convert WLED list encodings like '#L_R,G,B' into individual keys.

        WLED expects colors as separate R,G,B params; we store tuples and
        map them here to the right aliases.
        """
        result = {}
        for key, val in data.items():
            if key.startswith("#L_"):
                keys = key.split("_")[1].split(",")
                for k, v in zip(keys, val):
                    result[k] = v
            else:
                result[key] = val
        return result


BehaviorType = Callable[[State, Effect], None]


class LEDZone:
    def __init__(self, effect: Effect, behavior: BehaviorType):
        self.effect = effect
        self.behavior = behavior
        self.connections = None

    def compute_properties(self, state: State) -> str:
        if state:
            self.behavior(state, self.effect)
        return self.effect.build_request_str(is_init=state is None)

    def set_connection(self, ips: List[str]):
        self.connections = ips

    def is_connected(self):
        return bool(self.connections)


class Vibe:
    def __init__(self):
        self.zones = {}
        # self.connections = {}

    def add_zone(self, name: str, zone: LEDZone):
        self.zones[name] = zone

    def set_connection(self, name: str, ips: List[str]):
        if name not in self.zones:
            raise ValueError(f"Zone {name} isnt within the current added zones")

        self.zones[name].set_connection(ips)

    def compute_http_requests(self, state: State) -> List[str]:
        urls = []
        for zone in self.zones.values():
            if zone.is_connected():
                props_str = zone.compute_properties(state)
                if props_str:
                    urls.extend([f"http://{ip}/win&{props_str}" for ip in zone.connections])

        return urls


class VibeController:
    def __init__(self):
        self.vibes = {}
        self.lead_vibe = None

    def add_vibe(self, name: str, vibe: Vibe):
        self.vibes[name] = vibe

    async def fire(self, state: State = None):
        if self.lead_vibe:
            vibe = self.vibes[self.lead_vibe]

            requests_urls = vibe.compute_http_requests(state)
            if requests_urls:
                print(requests_urls)
                await parallel_update_led(requests_urls)

        else:
            raise ValueError("No lead vibe selected")

    async def set_random_vibe(self):
        self.lead_vibe = random.choice(list(self.vibes.keys()))
        await self.fire()

    async def set_specific_vibe(self, name: str):
        if name not in self.vibes:
            raise ValueError(f'Vibe {name} isnt within the current added vibes')
        self.lead_vibe = name
        await self.fire()


class Note2Color:

    @staticmethod
    def blue_to_white(state: State, note_number: int):
        "maps note number from blue to white in a straight line"
        note = max(state.min_key_val, min(note_number, state.max_key_val))

        ratio = (note - state.min_key_val) / (state.max_key_val - state.min_key_val)

        intensity = int(255 * ratio)

        return intensity, intensity, 255

    @staticmethod
    def circumference_color(state: State, note_number: int):
        "maps note number into the outer ring of the color circle (from RED to RED)"
        if note_number < state.intervals[0]:
            Red = 255
            Blue = 0
            Green = int(255 * (note_number - state.min_key_val) / state.interval)
        elif note_number < state.intervals[1]:
            Red = int(255 * (state.intervals[1] - note_number) / state.interval)
            Blue = 0
            Green = 255
        elif note_number < state.intervals[2]:
            Red = 0
            Blue = int(255 * (note_number - state.intervals[2]) / state.interval)
            Green = 255
        elif note_number < state.intervals[3]:
            Red = 0
            Blue = 255
            Green = int(255 * (state.intervals[3] - note_number) / state.interval)
        elif note_number < state.intervals[4]:
            Red = int(255 * (note_number - state.intervals[4]) / state.interval)
            Blue = 255
            Green = 0
        elif note_number <= state.intervals[5]:
            Red = 255
            Blue = int(255 * (state.intervals[5] - note_number) / state.interval)
            Green = 0
        return Red, Green, Blue

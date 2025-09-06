"""
MIDI Message Adapter: Convert mido messages to rtmidi-like API

This adapter allows seamless integration between file-based MIDI playback (mido)
and live MIDI input (rtmidi) by providing a unified interface.
"""

class MidoToRtMidiAdapter:
    """
    Adapter class that wraps mido.Message objects to provide rtmidi-like API.
    
    Usage:
        mido_msg = mido.Message('note_on', note=60, velocity=100)
        rtmidi_like = MidoToRtMidiAdapter(mido_msg)
        
        if rtmidi_like.isNoteOn():
            print(f"Note {rtmidi_like.getNote()} with velocity {rtmidi_like.getVelocity()}")
    """
    
    def __init__(self, mido_message):
        """
        Initialize adapter with a mido message.
        
        Args:
            mido_message: mido.Message object from file playback
        """
        self.msg = mido_message
        
    def isNoteOn(self):
        """Check if message is a note on event"""
        return self.msg.type == 'note_on' and getattr(self.msg, 'velocity', 0) > 0
    
    def isNoteOff(self):
        """Check if message is a note off event (including note_on with velocity 0)"""
        return (self.msg.type == 'note_off' or 
                (self.msg.type == 'note_on' and getattr(self.msg, 'velocity', 0) == 0))
    
    def isController(self):
        """Check if message is a control change event"""
        return self.msg.type == 'control_change'
    
    def isProgramChange(self):
        """Check if message is a program change event"""
        return self.msg.type == 'program_change'
    
    def isPitchBend(self):
        """Check if message is a pitch bend event"""
        return self.msg.type == 'pitchwheel'
    
    def getType(self):
        """Get message type as integer (MIDI status byte style)"""
        # Map mido types to MIDI status byte ranges
        type_map = {
            'note_off': 0x80,
            'note_on': 0x90,
            'polytouch': 0xA0,
            'control_change': 0xB0,
            'program_change': 0xC0,
            'aftertouch': 0xD0,
            'pitchwheel': 0xE0,
        }
        base_type = type_map.get(self.msg.type, 0x90)  # default to note_on
        channel = getattr(self.msg, 'channel', 0)
        return base_type + channel
    
    def getNoteNumber(self):
        """Get MIDI note number (0-127)"""
        return getattr(self.msg, 'note', 60)  # default to middle C
    
    
    def getVelocity(self):
        """Get note velocity (0-127)"""
        return getattr(self.msg, 'velocity', 100)
    
    def getController(self):
        """Get control change controller number"""
        return getattr(self.msg, 'control', 0)
    
    def getControllerValue(self):
        """Get control change value"""
        return getattr(self.msg, 'value', 0)
    
    def getChannel(self):
        """Get MIDI channel (0-15)"""
        return getattr(self.msg, 'channel', 0)
    
    def getProgram(self):
        """Get program change program number"""
        return getattr(self.msg, 'program', 0)
    
    def getPitch(self):
        """Get pitch bend value"""
        return getattr(self.msg, 'pitch', 0)
    
    def getTime(self):
        """Get message timestamp (for mido compatibility)"""
        return getattr(self.msg, 'time', 0)
    
    # Additional methods for compatibility with various MIDI libraries
    def getData1(self):
        """Get first data byte (note number for note messages, controller for CC)"""
        if self.msg.type in ['note_on', 'note_off']:
            return self.getNote()
        elif self.msg.type == 'control_change':
            return self.getController()
        elif self.msg.type == 'program_change':
            return self.getProgram()
        return 0
    
    def getData2(self):
        """Get second data byte (velocity for note messages, value for CC)"""
        if self.msg.type in ['note_on', 'note_off']:
            return self.getVelocity()
        elif self.msg.type == 'control_change':
            return self.getControllerValue()
        return 0
    
    def getStatusByte(self):
        """Get complete MIDI status byte"""
        return self.getType()
    
    def __str__(self):
        """String representation for debugging"""
        return f"MidoAdapter({self.msg})"
    
    def __repr__(self):
        return self.__str__()
    
    # Pass-through access to original mido message if needed
    @property 
    def original_message(self):
        """Access to the original mido message"""
        return self.msg


class FileToLiveMIDIBridge:
    """
    Bridge class to convert file-based MIDI playback to live MIDI input format.
    
    This allows you to use the same processing pipeline for both file playback
    and live MIDI input.
    """
    
    def __init__(self, midi_file_path):
        """
        Initialize bridge with a MIDI file.
        
        Args:
            midi_file_path: Path to MIDI file to play
        """
        import mido
        self.midi_file = mido.MidiFile(midi_file_path)
        self.messages = iter(self.midi_file.play())
    
    def getMessage(self, timeout=0.001):
        """
        Get next message in rtmidi getMessage() style.
        
        Args:
            timeout: Timeout in seconds (for compatibility, not used in file playback)
            
        Returns:
            MidoToRtMidiAdapter instance or None if no message available
        """
        try:
            mido_msg = next(self.messages)
            return MidoToRtMidiAdapter(mido_msg)
        except StopIteration:
            return None
    
    def hasMessage(self):
        """Check if there are more messages available"""
        # This is tricky with iterators, so we'll return True and let getMessage handle it
        return True


# Example usage and testing
if __name__ == "__main__":
    import mido
    
    # Test the adapter with various message types
    test_messages = [
        mido.Message('note_on', note=60, velocity=100, channel=0),
        mido.Message('note_off', note=60, velocity=0, channel=0),
        mido.Message('control_change', control=7, value=127, channel=0),
        mido.Message('program_change', program=42, channel=0)
    ]
    
    print("Testing MidoToRtMidiAdapter:")
    print("-" * 40)
    
    for msg in test_messages:
        adapter = MidoToRtMidiAdapter(msg)
        print(f"Original: {msg}")
        print(f"  isNoteOn(): {adapter.isNoteOn()}")
        print(f"  isNoteOff(): {adapter.isNoteOff()}")
        print(f"  isController(): {adapter.isController()}")
        print(f"  getType(): 0x{adapter.getType():02X}")
        print(f"  getData1(): {adapter.getData1()}")
        print(f"  getData2(): {adapter.getData2()}")
        print()

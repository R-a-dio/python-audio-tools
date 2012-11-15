"""Implements a crossfader for pcmreaders, based on PCMCat"""

import audiotools
import audiotools.pcm
import audiotools.fader
import audiotools.text

class PCMCrossFader(audiotools.PCMReader):
    """Small class based on PCMConcat that overlaps each pcmreader with the
    previous and applies a fadein and fadeout effect."""
    def __init__(self, pcmreaders, fade=3.0, convert_on_mismatch=True):
        """pcmreaders is an iterator of PCMReader objects. Each PCMReader
        should have a total_samples attribute like a PCMReaderProgress or a
        custom set total_samples.
        
        warning: Inaccurate total_samples values will result in broken
                 crossfading and care should be taken in setting it if not
                 getting the value from the source.
                 
        note: This crossfading is implemented without any buffering. This
              brings some requirements to the table such as an accurate
              total samples value set to each pcmreader in the chain.
              
              We could lift this restriction by implementing buffering inside
              the class.
        """
        self.reader_queue = pcmreaders
        self.convert_on_mismatch = convert_on_mismatch
        self.fade = fade
        
        # Indicates if we are currently fading
        # False = No fading, True = fading, None = Don't fade at all
        self.fading = False
        
        
        self.sample_rate = None
        self.channels = None
        self.channel_mask = None
        self.bits_per_sample = None
        self.current = None
        try:
            self.current = self.fetch_next()
        except StopIteration:
            from .text import ERR_NO_PCMREADERS
            raise ValueError(ERR_NO_PCMREADERS)
        
        self.sample_rate = self.current.sample_rate
        self.channels = self.current.channels
        self.channel_mask = self.current.channel_mask
        self.bits_per_sample = self.current.bits_per_sample
        
    def read(self, pcm_frames):
        try:
            s = self.current.read(pcm_frames)
            if (len(s) > 0):
                if self.current.current_frames > self.current.target_frames:
                    if self.fading == None:
                        return s
                    elif self.fading == False:
                        # Find the offset
                        offset = int(self.current.current_frames - self.current.target_frames)
                        frame_count = (len(s) - offset) / self.channels

                        result, fade = s.split(frame_count)
                        try:
                            self.next = self.fetch_next()
                        except StopIteration:
                            self.fading = None
                        else:
                            self.fading = True
                        
                        if self.fading == True:
                            new_frames = self.next.read(offset/self.channels)

                            mixed = mix([fade, new_frames], self.channels,
                                    self.bits_per_sample)
                        
                            result += mixed
                        
                            return result
                        else:
                            return s
                    else:
                        new_frames = self.next.read(len(s)/self.channels)

                        return mix([s, new_frames], self.channels,
                                   self.bits_per_sample)
                return s
            else:
                self.current.close()
                self.current = self.next
                if self.fading == None:
                    raise StopIteration()
                else:
                    self.fading = False
                return self.read(pcm_frames)
        except StopIteration:
            return audiotools.pcm.from_list([],
                                 self.channels,
                                 self.bits_per_sample,
                                 True)
    
    def close(self):
        pass
    
    def fetch_next(self):
        """Fetches the next pcmreader in the iterable, we use a method to
        do some additional checks on the new pcmreader.
        
        if convert_on_mismatch is True this wraps the new pcmreader in a
        PCMConverter instance set to the first pcmreaders format.
        
        This method also wraps the reader in a BufferedPCMReader for accurate
        frame sizes"""
        new_pcmreader = self.reader_queue.next()
        total_frames = new_pcmreader.total_frames
        try:
            self.check_format(new_pcmreader)
        except ValueError:
            if not self.convert_on_mismatch:
                raise
            if self.current: # Check if current is none
                new_pcmreader = audiotools.PCMConverter(new_pcmreader,
                                                    sample_rate=self.sample_rate,
                                                    channels=self.channels,
                                                    channel_mask=self.channel_mask,
                                                    bits_per_sample=self.bits_per_sample)
        # Wrap it in faders
        new_pcmreader = audiotools.fader.FadeIn(new_pcmreader,
                                                total_frames,
                                                fade=self.fade)
        new_pcmreader = audiotools.fader.FadeOut(new_pcmreader,
                                                 total_frames,
                                                 fade=self.fade,
                                                 buffered=True)
        # And wrap it in a buffered reader to top it off
        return new_pcmreader
    
    def check_format(self, other):
        """Compares the current pcmreader with `other` for equal
        sample rate, channels, channel mask and bits per sample.
        """
        if self.sample_rate != other.sample_rate:
            raise ValueError(audiotools.text.ERR_SAMPLE_RATE_MISMATCH)
        elif self.channels != other.channels:
            raise ValueError(audiotools.text.ERR_CHANNEL_COUNT_MISMATCH)
        elif self.channel_mask != other.channel_mask:
            raise ValueError(audiotools.text.ERR_CHANNEL_COUNT_MASK_MISMATCH)
        elif self.bits_per_sample != other.bits_per_sample:
            raise ValueError(audiotools.text.ERR_BPS_MISMATCH)
        return True
    
def mix(frames, channels, bits_per_sample):
    """Accepts a list of FrameLists and adds them together"""
    def mixing(*samples):
        result = 0
        for sample in samples:
            result += sample if sample else 0
        return result
    return audiotools.pcm.from_list(map(mixing, *frames),
                                    channels, bits_per_sample, True)
            
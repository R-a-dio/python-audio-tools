"""Module that includes tools to fade in or out a track"""
import audiotools
import audiotools.pcm
import itertools
    
    
def create_pairwise(channels=2):
    def pairwise(iterable):
        a = iter(iterable)
        return itertools.izip(*[a]*channels)
    return pairwise
    
class Fade(object):
    """Base class for FadeOut and FadeIn does nothing"""
    def __init__(self, pcmreader, total_frames, current_frames=0,
                 fade=3.0):
        super(Fade, self).__init__()
        self.__read__ = pcmreader.read
        self.__close__ = pcmreader.close
        self.sample_rate = pcmreader.sample_rate
        self.channels = pcmreader.channels
        self.channel_mask = pcmreader.channel_mask
        self.bits_per_sample = pcmreader.bits_per_sample
        self.current_frames = current_frames
        self.total_frames = total_frames
        self.fade = fade
        
        self.pairwise = create_pairwise(self.channels)
        
    def read(self, pcm_frames):
        return self.__read__(pcm_frames)
        
    def close(self):
        self.__close__()
        
class FadeOut(Fade):
    """Fades out a track `fade` seconds from the end of the track.
    """
    def __init__(self, pcmreader, total_frames, current_frames=0,
                 fade=3.0):
        super(FadeOut, self).__init__(pcmreader, total_frames,
                current_frames=current_frames, fade=fade)
        self._current_increment = 1.0
        self.target_frames = self.total_frames - (self.sample_rate * fade)
        self._increment = 1.0 / (self.sample_rate * fade)
        
    def read(self, pcm_frames):
        frame = self.__read__(pcm_frames)
        if (self.current_frames + frame.frames) > self.target_frames:
            new_frame = []
            for samples in self.pairwise(frame):
                self.current_frames += 1
                if self.current_frames > self.target_frames:
                    for sample in samples:
                        new_frame.append(sample * self._current_increment)
                    self._current_increment -= self._increment
                else:
                    new_frame.extend(samples)
            frame = audiotools.pcm.from_list(new_frame, self.channels,
                                             self.bits_per_sample, True)
        else:
            self.current_frames += frame.frames
        return frame
        
        
class FadeIn(Fade):
    """Fades in a track `fade` seconds from the start of the track."""
    def __init__(self, pcmreader, total_frames, current_frames=0,
                 fade=3.0):
        super(FadeIn, self).__init__(pcmreader, total_frames,
                current_frames=current_frames, fade=fade)
        self._current_increment = 0.0
        self.target_frames = self.sample_rate * fade
        self._increment = 1.0 / self.target_frames
        
    def read(self, pcm_frames):
        frame = self.__read__(pcm_frames)
        if self.current_frames < self.target_frames:
            new_frame = []
            for samples in self.pairwise(frame):
                self.current_frames += 1
                if self.current_frames < self.target_frames:
                    for sample in samples:
                        new_frame.append(sample * self._current_increment)
                    self._current_increment += self._increment
                else:
                    new_frame.extend(samples)
            frame = audiotools.pcm.from_list(new_frame, self.channels,
                                             self.bits_per_sample, True)
        else:
            self.current_frames += frame.frames
        return frame
        
def to_fade_in(audiofile, fade=3.0):
    """Wraps an audiofile in a FadeIn class with `fade` seconds of fading."""
    if not fade:
        return audiofile.to_pcm()
    else:
        return FadeIn(audiofile.to_pcm(),
                      audiofile.total_frames(),
                      fade=fade)
                      
def to_fade_out(audiofile, fade=3.0):
    """Wraps an audiofile in a FadeOut class with `fade` seconds of fading."""
    if not fade:
        return audiofile.to_pcm()
    else:
        return FadeOut(audiofile.to_pcm(),
                       audiofile.total_frames(),
                       fade=fade)
 
def to_fade_both(audiofile, fade_in=3.0, fade_out=3.0):
    """Wraps an audiofile in a FadeIn and FadeOut class with respective
    seconds of fading in and out."""
    return FadeOut(FadeIn(audiofile.to_pcm(),
                  audiofile.total_frames(),
                  fade=fade_in), audiofile.total_frames(), fade=fade_out)

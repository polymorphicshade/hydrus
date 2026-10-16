from hydrus.core import HydrusTime

from hydrus.client import ClientGlobals as CG

# a slideshow of 0 seconds plays each file once through, without looping, and moves on as soon as it is done
# a file with nothing to play, like an image, stays up for the still period, like it would in a playlist
SLIDESHOW_PERIOD_ONCE_THROUGH = 0.0

# how long a file with no duration stays up if there is no slideshow duration in the options to use
DEFAULT_STILL_PERIOD_S = 5.0

def ConvertSlideshowPeriodToPretty( period: float ) -> str:
    
    if period == SLIDESHOW_PERIOD_ONCE_THROUGH:
        
        return 'each file once through'
        
    
    return HydrusTime.TimeDeltaToPrettyTimeDelta( period )
    

def GetStillPeriod() -> float:
    
    # the first of the user's slideshow durations, the one the slideshow button starts with
    slideshow_durations = CG.client_controller.new_options.GetSlideshowDurations()
    
    if len( slideshow_durations ) > 0:
        
        return slideshow_durations[0]
        
    
    return DEFAULT_STILL_PERIOD_S
    

def SlideshowPeriodIsValid( period: float ) -> bool:
    
    return period >= 0.0
    

from hydrus.client.media import ClientMediaScriptedEvents

# a freeze holds playback on a frame for a while when playback gets to a point in a file, like a pause written into it. each file has its own, saved in the db

# ( timestamp_ms, duration_ms )
PlaybackFreeze = tuple[ int, int ]

MIN_PLAYBACK_FREEZE_DURATION_MS = 100
MAX_PLAYBACK_FREEZE_DURATION_MS = 3600 * 1000

def ConvertPlaybackFreezeDurationToString( duration_ms: int ) -> str:
    
    return f'{duration_ms / 1000:g}s'
    

def GetPlaybackFreezeToHold( freezes: list[ PlaybackFreeze ], last_timestamp_ms: float | None, current_timestamp_ms: float, duration_ms: int | None ) -> PlaybackFreeze | None:
    
    # the first freeze that normal playback went past since the last check. it goes by the same rules as scripted events, so seeking past one, or scanning through it while paused, does not hold
    # if playback went past two at once, the caller carries on from this one's point, so the other one holds when playback starts again
    passed_freezes = ClientMediaScriptedEvents.GetScriptedEventsToRun( freezes, last_timestamp_ms, current_timestamp_ms, duration_ms )
    
    if len( passed_freezes ) == 0:
        
        return None
        
    
    return passed_freezes[0]
    

def NormalisePlaybackFreezes( freezes: list[ PlaybackFreeze ] ) -> list[ PlaybackFreeze ]:
    
    # a point has one freeze, and a later one for the same point wins
    timestamps_to_durations = {}
    
    for ( timestamp_ms, duration_ms ) in freezes:
        
        timestamps_to_durations[ int( timestamp_ms ) ] = int( duration_ms )
        
    
    return sorted( timestamps_to_durations.items() )
    

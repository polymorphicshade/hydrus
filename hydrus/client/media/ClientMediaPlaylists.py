import bisect
import collections.abc
import random

from hydrus.core import HydrusNumbers
from hydrus.core import HydrusTime

# playlists are named, ordered lists of files. each item is a whole file, or just the span between two timestamps of it
# they live in the db. these are the bits of logic the gui and the db share

# playback that jumps back more than this from near the end of an item has looped round to the start
PLAYLIST_LOOP_DETECTION_MS = 1000

# after we send a player to the start of an item, it counts as there if it is no more than a little before, or it has played on a bit from it
PLAYLIST_SEEK_LANDED_BEFORE_MS = 250
PLAYLIST_SEEK_LANDED_AFTER_MS = 1000

# when we cannot tell how long a frame is, like for audio, we guess this
PLAYLIST_DEFAULT_FRAME_DURATION_MS = 1000 / 30

# playback times do not land exactly on frames, so the last frame counts as up when it is this close
PLAYLIST_LAST_FRAME_SLACK_MS = 5

# ( playlist_id, name, num_items )
PlaylistSummary = tuple[ int, str, int ]

# how many times each item plays before the playlist moves on
PLAYLIST_ITEM_LOOP_ONCE = 0 # the normal way: once through
PLAYLIST_ITEM_LOOP_TIMES = 1 # a number of times through
PLAYLIST_ITEM_LOOP_SECONDS = 2 # round and round for a time, like a slideshow, moving on when the time is up even part way through

def ConvertPlaylistItemLoopToString( loop_type: int, loop_times: int, loop_seconds: float ) -> str:
    
    if loop_type == PLAYLIST_ITEM_LOOP_TIMES:
        
        return f'{HydrusNumbers.ToHumanInt( loop_times )} times'
        
    elif loop_type == PLAYLIST_ITEM_LOOP_SECONDS:
        
        return f'for {HydrusTime.TimeDeltaToPrettyTimeDelta( loop_seconds )}'
        
    
    return 'once'
    

def PlaylistItemShouldPlayAgain( loop_type: int, loop_times: int, passes_done: int ) -> bool:
    
    # a time through an item just ended. whether it goes round again rather than on to the next item. passes_done counts the one that just ended
    if loop_type == PLAYLIST_ITEM_LOOP_TIMES:
        
        return passes_done < loop_times
        
    elif loop_type == PLAYLIST_ITEM_LOOP_SECONDS:
        
        # it goes round until its time is up
        return True
        
    
    return False
    

def PlaylistItemTimeIsUp( loop_type: int, loop_seconds: float, play_time_s: float ) -> bool:
    
    return loop_type == PLAYLIST_ITEM_LOOP_SECONDS and play_time_s >= loop_seconds
    

def FilterPlaylistsByName( playlists: collections.abc.Iterable[ PlaylistSummary ], filter_text: str ) -> list[ PlaylistSummary ]:
    
    # a simple, case-insensitive 'contains'
    filter_text = filter_text.strip().lower()
    
    return [ playlist for playlist in playlists if filter_text in playlist[1].lower() ]
    

def GetNextPlaylistIndex( index: int, num_items: int, direction: int, loop: bool ) -> int | None:
    
    # None means we ran off the end and are not looping
    if num_items == 0:
        
        return None
        
    
    next_index = index + direction
    
    if 0 <= next_index < num_items:
        
        return next_index
        
    
    if not loop:
        
        return None
        
    
    return next_index % num_items
    

def GenerateShuffledPlaylistOrder( num_items: int, first_index: int | None = None, avoid_first_index: int | None = None ) -> list[ int ]:
    
    # a random order to play the items in, as indices into the playlist. first_index, if given, goes first
    # otherwise, we try not to start on avoid_first_index, so going round again does not play the same item twice in a row
    order = list( range( num_items ) )
    
    random.shuffle( order )
    
    if first_index is not None:
        
        order.remove( first_index )
        order.insert( 0, first_index )
        
    elif avoid_first_index is not None and num_items > 1 and order[0] == avoid_first_index:
        
        swap_position = random.randrange( 1, num_items )
        
        ( order[0], order[ swap_position ] ) = ( order[ swap_position ], order[0] )
        
    
    return order
    

def GetPlaylistFrameDurationMS( duration_ms: int | None, num_frames: int | None ) -> float:
    
    if duration_ms is None or duration_ms <= 0 or num_frames is None or num_frames <= 1:
        
        return PLAYLIST_DEFAULT_FRAME_DURATION_MS
        
    
    # something silly, like a one-frame-a-minute video, should not hold things up, and 5ms is as fine as the playlist ticks
    return max( 5.0, min( duration_ms / num_frames, 1000.0 ) )
    

def GetPlaylistItemLastFrameTimeLeftMS( item_end_ms: int | None, current_timestamp_ms: float, frame_duration_ms: float ) -> float | None:
    
    # when the frame up now is the item's last one, how much longer it should stay up before the next item goes on. None if it is not the last frame yet
    # going on to the next item right when this runs out, rather than waiting to see the player loop round to the start, means you never see the start again
    if item_end_ms is None:
        
        return None
        
    
    time_left_ms = item_end_ms - current_timestamp_ms
    
    if time_left_ms > frame_duration_ms + PLAYLIST_LAST_FRAME_SLACK_MS:
        
        return None
        
    
    return max( 0.0, time_left_ms )
    

def GetPlaylistIndexAfterRemoval( index: int, kept_indices: list[ int ] ) -> int:
    
    # where an index ends up once only the kept_indices (sorted) are left. if it went, it is whatever came after it, round to the start at the end
    return bisect.bisect_left( kept_indices, index ) % len( kept_indices )
    

def GetPlaylistItemSpanFromABLoop( a_ms: int | None, b_ms: int | None ) -> tuple[ int | None, int | None ]:
    
    # an A-B repeat is only running once B is set, and a missing A means the start of the file
    if b_ms is None:
        
        return ( None, None )
        
    
    start_ms = 0 if a_ms is None else a_ms
    
    if start_ms >= b_ms:
        
        return ( None, None )
        
    
    return ( start_ms, b_ms )
    

def GetUpcomingPlaylistIndex( index: int, num_items: int, loop: bool, shuffle_order: list[ int ] | None, shuffle_position: int ) -> int | None:
    
    # the item that will play after this one, without changing anything. None if there is not one, or we cannot know yet
    if shuffle_order is None:
        
        return GetNextPlaylistIndex( index, num_items, 1, loop )
        
    
    next_position = shuffle_position + 1
    
    if next_position >= len( shuffle_order ):
        
        # going round again gets a fresh random order, which is not drawn until we get there
        return None
        
    
    return shuffle_order[ next_position ]
    

def NormalisePlaylistName( name: str ) -> str:
    
    return ' '.join( name.split() )
    

def RemapPlaylistOrderAfterRemoval( order: list[ int ], position: int, kept_indices: list[ int ] ) -> tuple[ list[ int ], int ]:
    
    # a play order, and our position in it, once only the kept_indices (sorted) are left. if the item at the position went, the position is whatever came after it, round to the start at the end
    old_indices_to_new_indices = { old_index : new_index for ( new_index, old_index ) in enumerate( kept_indices ) }
    
    new_order = [ old_indices_to_new_indices[ index ] for index in order if index in old_indices_to_new_indices ]
    
    new_position = len( [ index for index in order[ : position ] if index in old_indices_to_new_indices ] ) % len( new_order )
    
    return ( new_order, new_position )
    

def PlaylistSeekHasLanded( current_timestamp_ms: int, target_ms: int ) -> bool:
    
    return target_ms - PLAYLIST_SEEK_LANDED_BEFORE_MS <= current_timestamp_ms <= target_ms + PLAYLIST_SEEK_LANDED_AFTER_MS
    

def PlaylistItemIsDone(
    end_ms: int | None,
    duration_ms: int | None,
    current_timestamp_ms: int,
    last_timestamp_ms: int | None,
    had_played_once_at_start: bool,
    has_played_once_through: bool
) -> bool:
    
    # a span is done when playback runs over its end
    if end_ms is not None and current_timestamp_ms >= end_ms:
        
        return True
        
    
    # a whole-file item is done when the file plays through. a span that runs to the end of the file gets caught here too
    if has_played_once_through and not had_played_once_at_start:
        
        return True
        
    
    # when the file had already played through (the same file twice in a row), we have to catch it looping round to the start ourselves
    if last_timestamp_ms is not None and current_timestamp_ms + PLAYLIST_LOOP_DETECTION_MS < last_timestamp_ms:
        
        item_end_ms = end_ms if end_ms is not None else duration_ms
        
        # a jump back from anywhere else is the user seeking
        if item_end_ms is not None and last_timestamp_ms >= item_end_ms - PLAYLIST_LOOP_DETECTION_MS:
            
            return True
            
        
    
    return False
    

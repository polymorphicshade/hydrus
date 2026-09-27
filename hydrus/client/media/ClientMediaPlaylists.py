import collections.abc

# playlists are named, ordered lists of files. each item is a whole file, or just the span between two timestamps of it
# they live in the db. these are the bits of logic the gui and the db share

# playback that jumps back more than this from near the end of an item has looped round to the start
PLAYLIST_LOOP_DETECTION_MS = 1000

# after we send a player to the start of an item, it counts as there if it is no more than a little before, or it has played on a bit from it
PLAYLIST_SEEK_LANDED_BEFORE_MS = 250
PLAYLIST_SEEK_LANDED_AFTER_MS = 1000

# ( playlist_id, name, num_items )
PlaylistSummary = tuple[ int, str, int ]

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
    

def GetPlaylistItemSpanFromABLoop( a_ms: int | None, b_ms: int | None ) -> tuple[ int | None, int | None ]:
    
    # an A-B repeat is only running once B is set, and a missing A means the start of the file
    if b_ms is None:
        
        return ( None, None )
        
    
    start_ms = 0 if a_ms is None else a_ms
    
    if start_ms >= b_ms:
        
        return ( None, None )
        
    
    return ( start_ms, b_ms )
    

def NormalisePlaylistName( name: str ) -> str:
    
    return ' '.join( name.split() )
    

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
    

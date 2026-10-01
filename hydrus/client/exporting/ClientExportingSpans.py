from hydrus.core import HydrusTime

# an export span is the part of a file between the media viewer's A and B repeat points, as ( start_ms, end_ms )

def GetExportSpanFromABLoop( a_ms: int | None, b_ms: int | None ) -> tuple[ int, int ] | None:
    
    # both A and B have to be set to cut a part out. otherwise it is the whole file
    if a_ms is None or b_ms is None:
        
        return None
        
    
    if a_ms >= b_ms:
        
        return None
        
    
    return ( int( a_ms ), int( b_ms ) )
    

def GetExportSpanDurationMS( span_ms: tuple[ int, int ] | None, duration_ms: int | None ) -> int | None:
    
    # how long the export will be
    if span_ms is None:
        
        return duration_ms
        
    
    ( start_ms, end_ms ) = span_ms
    
    if duration_ms is not None and duration_ms > 0:
        
        # B can be a little past the end of the file
        end_ms = min( end_ms, duration_ms )
        
    
    return max( 0, end_ms - start_ms )
    

def GetExportSpanFFMPEGInputArgs( span_ms: tuple[ int, int ] | None ) -> list[ str ]:
    
    # these go before the '-i', so ffmpeg seeks to the start and stops reading at the end. the output starts at zero
    if span_ms is None:
        
        return []
        
    
    ( start_ms, end_ms ) = span_ms
    
    return [ '-ss', f'{start_ms / 1000:.3f}', '-t', f'{( end_ms - start_ms ) / 1000:.3f}' ]
    

def ConvertExportSpanTimeToPrettyString( timestamp_ms: int ) -> str:
    
    # 1:02:03.456, 2:03.456, or 3.456
    timestamp_ms = int( timestamp_ms )
    
    hours = timestamp_ms // 3600000
    minutes = ( timestamp_ms % 3600000 ) // 60000
    seconds = ( timestamp_ms % 60000 ) // 1000
    ms = timestamp_ms % 1000
    
    if hours > 0:
        
        return f'{hours}:{minutes:0>2}:{seconds:0>2}.{ms:0>3}'
        
    elif minutes > 0:
        
        return f'{minutes}:{seconds:0>2}.{ms:0>3}'
        
    
    return f'{seconds}.{ms:0>3}'
    

def ConvertExportSpanToPrettyString( span_ms: tuple[ int, int ] ) -> str:
    
    ( start_ms, end_ms ) = span_ms
    
    return f'{ConvertExportSpanTimeToPrettyString( start_ms )} to {ConvertExportSpanTimeToPrettyString( end_ms )} ({HydrusTime.MillisecondsDurationToPrettyTime( end_ms - start_ms )})'
    

def GetExportSpanFilenameSuffix( span_ms: tuple[ int, int ] | None ) -> str:
    
    # so a clip's default filename says which part it is, and does not clash with the whole file's
    if span_ms is None:
        
        return ''
        
    
    ( start_ms, end_ms ) = span_ms
    
    return f'_{start_ms / 1000:.3f}s-{end_ms / 1000:.3f}s'
    

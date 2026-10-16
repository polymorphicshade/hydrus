# a file can have A-B repeat loops saved on it, so one can be put back on with a click, rather than marking A and B again. each file has its own, saved in the db

# ( a_ms, b_ms ). a loop saved from an A-B repeat with no A starts at the start, so a_ms is 0
ABLoop = tuple[ int, int ]

# an A-B repeat loop has to be at least this long
MIN_AB_LOOP_DURATION_MS = 100

def ABLoopIsValid( ab_loop: ABLoop ) -> bool:
    
    ( a_ms, b_ms ) = ab_loop
    
    return a_ms >= 0 and b_ms - a_ms >= MIN_AB_LOOP_DURATION_MS
    

def AddABLoop( ab_loops: list[ ABLoop ], ab_loop: ABLoop ) -> list[ ABLoop ]:
    
    return NormaliseABLoops( list( ab_loops ) + [ ab_loop ] )
    

def ConvertABRepeatToABLoop( a_ms: int | None, b_ms: int | None ) -> ABLoop | None:
    
    # what the media viewer's A-B repeat saves as. None if it is not looping
    if b_ms is None:
        
        return None
        
    
    ab_loop = ( 0 if a_ms is None else int( a_ms ), int( b_ms ) )
    
    if not ABLoopIsValid( ab_loop ):
        
        return None
        
    
    return ab_loop
    

def NormaliseABLoops( ab_loops: list[ ABLoop ] ) -> list[ ABLoop ]:
    
    # in order, and the same loop is only saved once
    return sorted( { ( int( a_ms ), int( b_ms ) ) for ( a_ms, b_ms ) in ab_loops } )
    

def RemoveABLoop( ab_loops: list[ ABLoop ], ab_loop: ABLoop ) -> list[ ABLoop ]:
    
    return [ existing_ab_loop for existing_ab_loop in NormaliseABLoops( ab_loops ) if existing_ab_loop != tuple( ab_loop ) ]
    

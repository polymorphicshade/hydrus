import collections.abc

# a screen location is a named spot on a particular monitor that a media viewer can snap to
# ( name, screen_name, x, y, width, height ). x and y are the window's top-left, frame included, relative to the top-left of the screen. width and height are the window's inside size
ScreenLocation = tuple[ str, str, int, int, int, int ]

# ( screen_name, x, y, width, height ), the screen's geometry on the whole desktop
ScreenGeometry = tuple[ str, int, int, int, int ]

# a window's top-left can sit this far off its screen. windows snapped to an edge have their frame a few pixels off it
MAX_SCREEN_OVERHANG = 32

def ConvertScreenLocationToPretty( screen_location: ScreenLocation ) -> str:
    
    ( name, screen_name, x, y, width, height ) = screen_location
    
    return f'{name}: {width}x{height} at {x},{y} on {screen_name}'
    

def GetScreenLocationError( screen_location: ScreenLocation, other_names: collections.abc.Collection[ str ] ) -> str | None:
    
    ( name, screen_name, x, y, width, height ) = screen_location
    
    if name == '':
        
        return 'Please enter a name!'
        
    
    # names are not case-sensitive
    if name.lower() in { other_name.lower() for other_name in other_names }:
        
        return f'There is already a screen location called "{name}"!'
        
    
    if width < 1 or height < 1:
        
        return 'The width and height have to be at least 1!'
        
    
    return None
    

def GetTargetGeometry( screen_location: ScreenLocation, screens: collections.abc.Sequence[ ScreenGeometry ] ) -> tuple[ bool, int, int, int, int ]:
    
    # returns ( found_the_screen, x, y, width, height ) on the whole desktop
    # if the monitor is not connected right now, we use the first screen, which should be the primary
    # the top-left is kept on (or just off) the screen, in case the screen we end up on is smaller than the one it was saved on
    ( name, screen_name, x, y, width, height ) = screen_location
    
    matching_screens = [ screen for screen in screens if screen[0] == screen_name ]
    
    found_the_screen = len( matching_screens ) > 0
    
    if found_the_screen:
        
        screen = matching_screens[0]
        
    else:
        
        screen = screens[0]
        
    
    ( screen_name, screen_x, screen_y, screen_width, screen_height ) = screen
    
    x = max( - MAX_SCREEN_OVERHANG, min( x, screen_width - MAX_SCREEN_OVERHANG ) )
    y = max( - MAX_SCREEN_OVERHANG, min( y, screen_height - MAX_SCREEN_OVERHANG ) )
    
    return ( found_the_screen, screen_x + x, screen_y + y, width, height )
    

def NormaliseScreenLocationName( name: str ) -> str:
    
    return ' '.join( name.split() )
    

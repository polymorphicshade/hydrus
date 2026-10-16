import collections.abc

from hydrus.client import ClientData

# the media viewer remembers each file's zoom and pan for each screen it is shown on, so a media viewer moved to another monitor puts the file back how it was there
# screens go by the name Qt gives them, like '\\.\DISPLAY1' or a monitor's model name. a zoom saved for ANY_SCREEN, which every zoom was from before they were per screen, is for the screens that have none of their own

ANY_SCREEN = ''

# ( zoom, center ). a None zoom is the normal default zoom, and a None center is centered
ScreenZoom = tuple[ float | None, tuple[ float, float ] | None ]

DEFAULT_SCREEN_ZOOM: ScreenZoom = ( None, None )

def ConvertScreenZoomToPretty( screen_zoom: ScreenZoom ) -> str:
    
    ( zoom, center ) = screen_zoom
    
    zoom_text = 'default zoom' if zoom is None else f'{ClientData.ConvertZoomToPercentage( zoom )} zoom'
    pan_text = 'centered' if center is None else 'panned'
    
    return f'{zoom_text}, {pan_text}'
    

def GetScreenZoom( screen_zooms: dict[ str, ScreenZoom ], screen_name: str ) -> ScreenZoom:
    
    # a screen's own, or else the one for any screen, or else the default
    if screen_name in screen_zooms:
        
        return screen_zooms[ screen_name ]
        
    
    return screen_zooms.get( ANY_SCREEN, DEFAULT_SCREEN_ZOOM )
    

def GetScreenZoomChoices( connected_screen_names: collections.abc.Sequence[ str ], current_screen_name: str, screen_zooms: dict[ str, ScreenZoom ] ) -> list[ tuple[ str, str ] ]:
    
    # ( label, screen_name ) for the media viewer's menu: the screens connected now, in order, and then any others the file has a zoom saved for
    other_screen_names = sorted( screen_name for screen_name in screen_zooms if screen_name != ANY_SCREEN and screen_name not in connected_screen_names )
    
    choices = []
    
    for screen_name in list( connected_screen_names ) + other_screen_names:
        
        notes = []
        
        if screen_name == current_screen_name:
            
            notes.append( 'this screen' )
            
        
        if screen_name not in connected_screen_names:
            
            notes.append( 'not connected' )
            
        
        label = screen_name if len( notes ) == 0 else f'{screen_name} ({", ".join( notes )})'
        
        label = f'{label}: {ConvertScreenZoomToPretty( GetScreenZoom( screen_zooms, screen_name ) )}'
        
        choices.append( ( label, screen_name ) )
        
    
    return choices
    

def SetScreenZoom( screen_zooms: dict[ str, ScreenZoom ], screen_name: str, screen_zoom: ScreenZoom ):
    
    # like the db does it. a screen at the default keeps a row of its own, so it does not fall back to the one for any screen
    if screen_name == ANY_SCREEN and screen_zoom == DEFAULT_SCREEN_ZOOM:
        
        screen_zooms.pop( ANY_SCREEN, None )
        
    else:
        
        screen_zooms[ screen_name ] = screen_zoom
        
        

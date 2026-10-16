from hydrus.client.gui import ClientGUIMediaViewerABRepeat
from hydrus.client.gui import ClientGUIScreenLocations

# the screens, which one each media viewer that is open now is on, and showing a file how it is zoomed and panned on another screen, for the Client API

def ApplyOpenMediaViewersScreenZoom( screen_name: str, canvas_key: bytes | None = None ) -> int:
    
    # like the media viewer's screen->zoom and pan as on menu, for one media viewer, or all of them with no canvas_key. returns how many it was done for
    canvas_windows = ClientGUIMediaViewerABRepeat.GetOpenMediaViewerCanvases()
    
    if canvas_key is not None:
        
        canvas_windows = [ canvas_window for canvas_window in canvas_windows if canvas_window.GetCanvasKey() == canvas_key ]
        
    
    for canvas_window in canvas_windows:
        
        canvas_window.ApplyScreenZoom( screen_name )
        
    
    return len( canvas_windows )
    

def GetScreensAPIInfo() -> dict:
    
    # the main screen goes first
    screens = [ { 'screen_name' : screen_name, 'x' : x, 'y' : y, 'width' : width, 'height' : height, 'primary' : i == 0 } for ( i, ( screen_name, x, y, width, height ) ) in enumerate( ClientGUIScreenLocations.GetCurrentScreenGeometries() ) ]
    
    media_viewers = [ canvas_window.GetScreenAPIInfo() for canvas_window in ClientGUIMediaViewerABRepeat.GetOpenMediaViewerCanvases() ]
    
    return { 'screens' : screens, 'media_viewers' : media_viewers }
    

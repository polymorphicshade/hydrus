import re

from qtpy import QtGui as QG

from hydrus.client import ClientGlobals as CG

# the media viewer that was opened last can have a background of its own colour, magenta to start with, so you can tell which one it is when you have a few open

DEFAULT_HIGHLIGHT_COLOUR = '#FF00FF'

HIGHLIGHT_COLOUR_RE = re.compile( r'^#?([0-9a-fA-F]{6})$' )

def NormaliseHighlightColour( colour: str ) -> str | None:
    
    # '#ff00ff' or 'ff00ff' to '#FF00FF'. anything else is None
    if not isinstance( colour, str ):
        
        return None
        
    
    m = HIGHLIGHT_COLOUR_RE.match( colour.strip() )
    
    if m is None:
        
        return None
        
    
    return '#' + m.group( 1 ).upper()
    

def ConvertQColourToHighlightColour( colour: QG.QColor ) -> str:
    
    return '#{:02X}{:02X}{:02X}'.format( colour.red(), colour.green(), colour.blue() )
    

def GetHighlightIsOn() -> bool:
    
    return CG.client_controller.new_options.GetBoolean( 'highlight_last_opened_media_viewer' )
    

def GetHighlightColour() -> str:
    
    colour = NormaliseHighlightColour( CG.client_controller.new_options.GetString( 'last_opened_media_viewer_highlight_colour' ) )
    
    if colour is None:
        
        return DEFAULT_HIGHLIGHT_COLOUR
        
    
    return colour
    

def GetHighlightQColour() -> QG.QColor:
    
    return QG.QColor( GetHighlightColour() )
    

def GetLastOpenedMediaViewerCanvas():
    
    # the canvas of the media viewer that was opened last and is still open, or None
    from hydrus.client.gui import ClientGUIMediaViewerABRepeat
    
    canvas_windows = ClientGUIMediaViewerABRepeat.GetOpenMediaViewerCanvases()
    
    if len( canvas_windows ) == 0:
        
        return None
        
    
    return canvas_windows[-1]
    

def CanvasIsHighlighted( canvas ) -> bool:
    
    if not GetHighlightIsOn():
        
        return False
        
    
    return canvas is not None and canvas is GetLastOpenedMediaViewerCanvas()
    

def NotifyMediaViewersChanged():
    
    # a media viewer was opened or closed, or the options changed, so the one with the highlight may be a different one now
    CG.client_controller.pub( 'notify_media_viewer_highlight_changed' )
    

def SetHighlight( highlight_is_on: bool | None = None, colour: str | None = None ):
    
    new_options = CG.client_controller.new_options
    
    if highlight_is_on is not None:
        
        new_options.SetBoolean( 'highlight_last_opened_media_viewer', highlight_is_on )
        
    
    if colour is not None:
        
        normalised_colour = NormaliseHighlightColour( colour )
        
        if normalised_colour is None:
            
            raise ValueError( f'"{colour}" is not a colour like #FF00FF!' )
            
        
        new_options.SetString( 'last_opened_media_viewer_highlight_colour', normalised_colour )
        
    
    CG.client_controller.Write( 'serialisable', new_options )
    
    NotifyMediaViewersChanged()
    

def GetHighlightAPIInfo() -> dict:
    
    canvas = GetLastOpenedMediaViewerCanvas()
    
    return {
        'highlight_last_opened' : GetHighlightIsOn(),
        'colour' : GetHighlightColour(),
        'last_opened_canvas_key' : None if canvas is None else canvas.GetCanvasKey().hex()
    }
    

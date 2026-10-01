import json

from hydrus.client import ClientScreenLocations

# a media viewer layout is the media viewer windows that were open at some point: what file each one was on, where its window was, and how it was zoomed and panned
# it is saved as json, so it can go in a file and come back later

MEDIA_VIEWER_LAYOUT_JSON_KEY = 'hydrus_media_viewer_layout'
MEDIA_VIEWER_LAYOUT_JSON_VERSION = 1

# a media viewer opened from a big search page browses a lot of files. a layout keeps this many of them, around the one it is on
MEDIA_VIEWER_LAYOUT_MAX_HASHES = 1000

def GetHashesAroundCurrent( hashes: list[ bytes ], current_hash: bytes, max_num_hashes: int ) -> list[ bytes ]:
    
    # up to max_num_hashes of them, in order, with the current one as near the middle as it can be
    if len( hashes ) <= max_num_hashes:
        
        return list( hashes )
        
    
    if current_hash in hashes:
        
        index = hashes.index( current_hash )
        
    else:
        
        index = 0
        
    
    start = max( 0, min( index - max_num_hashes // 2, len( hashes ) - max_num_hashes ) )
    
    return hashes[ start : start + max_num_hashes ]
    

class MediaViewerLayout( object ):
    
    def __init__(
        self,
        hashes: list[ bytes ],
        current_hash: bytes,
        screen_name: str,
        x: int,
        y: int,
        width: int,
        height: int,
        maximised: bool = False,
        fullscreen: bool = False,
        relative_zoom: float | None = None,
        center: tuple[ float, float ] | None = None,
        playback_ms: int | None = None
    ):
        
        # hashes are the files the window browses through, in order. current_hash is the one it was on
        self.hashes = list( hashes )
        self.current_hash = current_hash
        
        # x and y are the window's top-left relative to the top-left of its screen, like a screen location. width and height are its inside size
        # a maximised or fullscreen window has the size and place it goes back to when it is a normal window again
        self.screen_name = screen_name
        self.x = int( x )
        self.y = int( y )
        self.width = int( width )
        self.height = int( height )
        self.maximised = maximised
        self.fullscreen = fullscreen
        
        # the zoom is relative to the zoom that fits the file in the window, and the center is the part of the file in the middle of the window, as a fraction of its width and height, so they follow the window's size
        # None for the zoom means the file's usual zoom, and None for the center means centered
        self.relative_zoom = relative_zoom
        self.center = None if center is None else ( float( center[0] ), float( center[1] ) )
        
        # where playback was, for a video or audio
        self.playback_ms = playback_ms
        
    
    def __eq__( self, other ):
        
        if isinstance( other, MediaViewerLayout ):
            
            return self.__dict__ == other.__dict__
            
        
        return NotImplemented
        
    
    def __repr__( self ):
        
        return f'MediaViewerLayout({self.__dict__})'
        
    
    def GetScreenLocation( self ) -> ClientScreenLocations.ScreenLocation:
        
        return ( '', self.screen_name, self.x, self.y, self.width, self.height )
        
    
    def ToDict( self ) -> dict:
        
        return {
            'hashes' : [ hash.hex() for hash in self.hashes ],
            'current_hash' : self.current_hash.hex(),
            'window' : {
                'screen' : self.screen_name,
                'x' : self.x,
                'y' : self.y,
                'width' : self.width,
                'height' : self.height,
                'maximised' : self.maximised,
                'fullscreen' : self.fullscreen
            },
            'zoom' : self.relative_zoom,
            'center' : None if self.center is None else list( self.center ),
            'playback_ms' : self.playback_ms
        }
        
    
    @staticmethod
    def STATICCreateFromDict( d: dict ) -> 'MediaViewerLayout':
        
        # raises ValueError if it is not a media viewer
        try:
            
            hashes = [ bytes.fromhex( hash_hex ) for hash_hex in d[ 'hashes' ] ]
            current_hash = bytes.fromhex( d[ 'current_hash' ] )
            
            window = d[ 'window' ]
            
            screen_name = str( window[ 'screen' ] )
            x = int( window[ 'x' ] )
            y = int( window[ 'y' ] )
            width = int( window[ 'width' ] )
            height = int( window[ 'height' ] )
            maximised = bool( window.get( 'maximised', False ) )
            fullscreen = bool( window.get( 'fullscreen', False ) )
            
            relative_zoom = d.get( 'zoom', None )
            
            if relative_zoom is not None:
                
                relative_zoom = float( relative_zoom )
                
            
            center = d.get( 'center', None )
            
            if center is not None:
                
                ( center_x, center_y ) = center
                
                center = ( float( center_x ), float( center_y ) )
                
            
            playback_ms = d.get( 'playback_ms', None )
            
            if playback_ms is not None:
                
                playback_ms = int( playback_ms )
                
            
        except ( KeyError, TypeError, ValueError, AttributeError ) as e:
            
            raise ValueError( f'A media viewer in the layout could not be read: {e}' )
            
        
        if current_hash not in hashes:
            
            hashes.append( current_hash )
            
        
        if width < 1 or height < 1:
            
            raise ValueError( 'A media viewer in the layout has no size!' )
            
        
        if relative_zoom is not None and relative_zoom <= 0:
            
            relative_zoom = None
            
        
        return MediaViewerLayout( hashes, current_hash, screen_name, x, y, width, height, maximised = maximised, fullscreen = fullscreen, relative_zoom = relative_zoom, center = center, playback_ms = playback_ms )
        
    

def ConvertMediaViewerLayoutsToJSON( media_viewer_layouts: list[ MediaViewerLayout ] ) -> str:
    
    d = {
        MEDIA_VIEWER_LAYOUT_JSON_KEY : MEDIA_VIEWER_LAYOUT_JSON_VERSION,
        'media_viewers' : [ media_viewer_layout.ToDict() for media_viewer_layout in media_viewer_layouts ]
    }
    
    return json.dumps( d, indent = 2 )
    

def ConvertJSONToMediaViewerLayouts( text: str ) -> list[ MediaViewerLayout ]:
    
    # raises ValueError if it is not a media viewer layout
    try:
        
        d = json.loads( text )
        
    except json.JSONDecodeError as e:
        
        raise ValueError( f'That is not json: {e}' )
        
    
    if not isinstance( d, dict ) or MEDIA_VIEWER_LAYOUT_JSON_KEY not in d:
        
        raise ValueError( 'That is not a hydrus media viewer layout!' )
        
    
    media_viewers = d.get( 'media_viewers', [] )
    
    if not isinstance( media_viewers, list ):
        
        raise ValueError( 'That media viewer layout has no list of media viewers!' )
        
    
    return [ MediaViewerLayout.STATICCreateFromDict( media_viewer ) for media_viewer in media_viewers ]
    

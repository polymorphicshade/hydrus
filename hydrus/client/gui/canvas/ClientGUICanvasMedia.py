import itertools
import math
import time
import typing

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusGlobals as HG
from hydrus.core import HydrusNumbers
from hydrus.core import HydrusTime
from hydrus.core.files import HydrusFileHandling
from hydrus.core.files.images import HydrusImageHandling

from hydrus.client import ClientApplicationCommand as CAC
from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientRendering
from hydrus.client import ClientUgoiraHandling
from hydrus.client.gui import ClientGUIAsync
from hydrus.client.gui import ClientGUIExceptionHandling
from hydrus.client.gui import ClientGUIFunctions
from hydrus.client.gui import ClientGUIMenus
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIShortcuts
from hydrus.client.gui import ClientGUITopLevelWindows
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.canvas import ClientGUIMPV
from hydrus.client.gui.canvas import ClientGUIQtMediaPlayer
from hydrus.client.gui.canvas import ClientGUITransparency
from hydrus.client.gui.executables import ClientGUIExecutableActions
from hydrus.client.gui.media import ClientGUIMediaAudioEffects
from hydrus.client.gui.media import ClientGUIMediaControls
from hydrus.client.gui.media import ClientGUIMediaVolume
from hydrus.client.media import ClientMedia
from hydrus.client.media import ClientMediaResult
from hydrus.client.media import ClientMediaScriptedEvents
from hydrus.client.media import ClientMediaSingle

ZOOM_CENTERPOINT_MEDIA_CENTER = 0
ZOOM_CENTERPOINT_VIEWER_CENTER = 1
ZOOM_CENTERPOINT_MOUSE = 2
ZOOM_CENTERPOINT_MEDIA_TOP_LEFT = 3

ZOOM_CENTERPOINT_TYPES = ( ZOOM_CENTERPOINT_VIEWER_CENTER, ZOOM_CENTERPOINT_MOUSE, ZOOM_CENTERPOINT_MEDIA_CENTER, ZOOM_CENTERPOINT_MEDIA_TOP_LEFT )

zoom_centerpoints_str_lookup = {}

zoom_centerpoints_str_lookup[ ZOOM_CENTERPOINT_MEDIA_CENTER ] = 'media center'
zoom_centerpoints_str_lookup[ ZOOM_CENTERPOINT_VIEWER_CENTER ] = 'viewer center'
zoom_centerpoints_str_lookup[ ZOOM_CENTERPOINT_MOUSE ] = 'mouse (or viewer center if mouse outside)'
zoom_centerpoints_str_lookup[ ZOOM_CENTERPOINT_MEDIA_TOP_LEFT ] = 'media top-left'

MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE = 0
MEDIA_VIEWER_ZOOM_TYPE_CANVAS = 1
MEDIA_VIEWER_ZOOM_TYPE_100 = 2
MEDIA_VIEWER_ZOOM_TYPE_FILL_X = 3
MEDIA_VIEWER_ZOOM_TYPE_FILL_Y = 4
MEDIA_VIEWER_ZOOM_TYPE_FILL_AUTO = 5

MEDIA_VIEWER_ZOOM_TYPES = ( MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE, MEDIA_VIEWER_ZOOM_TYPE_100, MEDIA_VIEWER_ZOOM_TYPE_CANVAS, MEDIA_VIEWER_ZOOM_TYPE_FILL_X, MEDIA_VIEWER_ZOOM_TYPE_FILL_Y, MEDIA_VIEWER_ZOOM_TYPE_FILL_AUTO )

media_viewer_zoom_type_str_lookup = {
    MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE : 'default for filetype',
    MEDIA_VIEWER_ZOOM_TYPE_CANVAS : 'canvas fit',
    MEDIA_VIEWER_ZOOM_TYPE_100 : '100% zoom',
    MEDIA_VIEWER_ZOOM_TYPE_FILL_X : 'fill horizontally',
    MEDIA_VIEWER_ZOOM_TYPE_FILL_Y : 'fill vertically',
    MEDIA_VIEWER_ZOOM_TYPE_FILL_AUTO : 'canvas fill'
}

media_viewer_zoom_type_description_lookup = {
    MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE : 'Allow the per-filetype rules to apply, no override.',
    MEDIA_VIEWER_ZOOM_TYPE_CANVAS : 'Fit the media to the viewer, so it is as big as it can be.',
    MEDIA_VIEWER_ZOOM_TYPE_100 : 'Set the zoom level to 100%.',
    MEDIA_VIEWER_ZOOM_TYPE_FILL_X : 'Scale the media to fill the viewer width, even if that means it overflows.',
    MEDIA_VIEWER_ZOOM_TYPE_FILL_Y : 'Scale the media to fill the viewer height, even if that means it overflows.',
    MEDIA_VIEWER_ZOOM_TYPE_FILL_AUTO : 'Scale the media up to completely fill the whole viewer, even if that means it overflows.'
}

media_viewer_zoom_type_to_cac_simple_commands = {
    MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE : CAC.SIMPLE_ZOOM_DEFAULT_VIEWER_CENTER,
    MEDIA_VIEWER_ZOOM_TYPE_CANVAS : CAC.SIMPLE_ZOOM_CANVAS_VIEWER_CENTER,
    MEDIA_VIEWER_ZOOM_TYPE_100 : CAC.SIMPLE_ZOOM_100_CENTER,
    MEDIA_VIEWER_ZOOM_TYPE_FILL_X : CAC.SIMPLE_ZOOM_CANVAS_FILL_X_VIEWER_CENTER,
    MEDIA_VIEWER_ZOOM_TYPE_FILL_Y : CAC.SIMPLE_ZOOM_CANVAS_FILL_Y_VIEWER_CENTER,
    MEDIA_VIEWER_ZOOM_TYPE_FILL_AUTO : CAC.SIMPLE_ZOOM_CANVAS_FILL_AUTO_VIEWER_CENTER
}

OPEN_EXTERNALLY_BUTTON_SIZE = ( 200, 45 )
OPEN_EXTERNALLY_MAX_THUMBNAIL_SIZE = ( 200, 200 )

# anything shorter than this is not a useful loop, and mpv's 'rewind loop' damaged-file detection gets twitchy if we restart near 0 many times a second
MIN_AB_LOOP_DURATION_MS = 100

# players take a moment to land a seek, so after we jump over a skip we give them this long before trying again
PLAYBACK_SKIP_SEEK_GRACE_PERIOD_S = 0.5

def ConvertPlaybackTimestampToString( timestamp_ms: int ) -> str:
    
    ( hours, remainder_ms ) = divmod( int( timestamp_ms ), 3600000 )
    ( minutes, remainder_ms ) = divmod( remainder_ms, 60000 )
    ( seconds, milliseconds ) = divmod( remainder_ms, 1000 )
    
    if hours > 0:
        
        return f'{hours}:{minutes:0>2}:{seconds:0>2}.{milliseconds:0>3}'
        
    
    return f'{minutes}:{seconds:0>2}.{milliseconds:0>3}'
    

def ParsePlaybackTimestampString( text: str ) -> int:
    
    # the other way from ConvertPlaybackTimestampToString. takes '1:02:03.456', '2:05.5', '75', and so on. raises ValueError
    parts = text.strip().split( ':' )
    
    if len( parts ) > 3 or True in ( part.strip() == '' for part in parts ):
        
        raise ValueError( f'Could not parse "{text}" as a point in playback!' )
        
    
    seconds = float( parts[-1] )
    minutes = int( parts[-2] ) if len( parts ) >= 2 else 0
    hours = int( parts[-3] ) if len( parts ) >= 3 else 0
    
    if not math.isfinite( seconds ) or seconds < 0 or minutes < 0 or hours < 0:
        
        raise ValueError( f'Could not parse "{text}" as a point in playback!' )
        
    
    return int( round( ( ( ( hours * 60 ) + minutes ) * 60 + seconds ) * 1000 ) )
    

def MediaHasPlayback( media: ClientMediaSingle.MediaSingle ):
    
    return media.HasDuration() or media.GetMime() == HC.ANIMATION_UGOIRA
    

def MergePlaybackSkips( skips: list[ tuple[ int, int ] ] ) -> list[ tuple[ int, int ] ]:
    
    # overlapping or touching skips become one, so a jump never lands inside another skip
    
    merged_skips = []
    
    for ( start_ms, end_ms ) in sorted( skips ):
        
        if len( merged_skips ) > 0 and start_ms <= merged_skips[-1][1]:
            
            ( previous_start_ms, previous_end_ms ) = merged_skips.pop()
            
            merged_skips.append( ( previous_start_ms, max( previous_end_ms, end_ms ) ) )
            
        else:
            
            merged_skips.append( ( start_ms, end_ms ) )
            
        
    
    return merged_skips
    

def ConvertFrameStartToPlaybackPointMS( frame_start_ms: float ) -> int:
    
    # A, zoom timestamps, and the like are the start of a frame. rounding down means playback is at or past the point as soon as that frame is up
    # the round first stops float fuzz like 999.9999999 from knocking a whole ms off
    return int( math.floor( round( frame_start_ms, 3 ) ) )
    

def ConvertFrameToABLoopPointBMS( frame_start_ms: float, frame_duration_ms: float ) -> int:
    
    # B is in the last frame the loop shows. we put it in the middle of that frame, well clear of both its edges, so no rounding or frame-length guesswork can push it into a neighbour
    # the native renderer shows the frame B is in and then loops, and mpv loops when it gets to a frame that starts after B
    return ConvertFrameStartToPlaybackPointMS( frame_start_ms + max( 0.0, frame_duration_ms ) / 2 )
    

def GetFrameIndexAtPlaybackPoint( point_ms: float, num_frames: int, get_frame_start_ms: typing.Callable[ [ int ], float ] ) -> int:
    
    # the first frame that starts at or after this point. for a point from the start of a frame, that is the frame it came from, and for a B, it is the frame after
    # half a ms of slack covers the rounding down. a point after the start of the last frame gives num_frames
    lo = 0
    hi = num_frames
    
    while lo < hi:
        
        mid = ( lo + hi ) // 2
        
        if get_frame_start_ms( mid ) < point_ms - 0.5:
            
            lo = mid + 1
            
        else:
            
            hi = mid
            
        
    
    return lo
    

# ( timestamp_ms, relative_zoom, center_x, center_y ). relative_zoom is relative to the zoom that fits the file in the window
# center_x and center_y are the point of the file in the middle of the window, as a fraction of its width and height. None for both means centered
ZoomTimestamp = tuple[ int, float, float | None, float | None ]

def ConvertZoomTimestampRowsToRelative( rows: list[ tuple[ int, float, bool, float | None, float | None ] ], canvas_zoom: float ) -> tuple[ list[ ZoomTimestamp ], bool ]:
    
    # zoom timestamps are relative to the zoom that fits the file in the window. ones from before that are the plain zoom, which we take as being for the window as it is now
    # returns the zoom timestamps, and whether any needed converting
    zoom_timestamps = []
    
    converted_some = False
    
    for ( timestamp_ms, zoom, zoom_is_relative, center_x, center_y ) in rows:
        
        if not zoom_is_relative:
            
            zoom = zoom / canvas_zoom
            
            converted_some = True
            
        
        zoom_timestamps.append( ( timestamp_ms, zoom, center_x, center_y ) )
        
    
    return ( zoom_timestamps, converted_some )
    

def GetMediaPosForZoomCenter( canvas_size: tuple[ int, int ], media_size: tuple[ int, int ], center: tuple[ float, float ] ) -> tuple[ int, int ]:
    
    # where the media goes so the point of it at center, as a fraction of its width and height, is in the middle of the canvas
    ( canvas_width, canvas_height ) = canvas_size
    ( media_width, media_height ) = media_size
    ( center_x, center_y ) = center
    
    return ( round( ( canvas_width / 2 ) - ( center_x * media_width ) ), round( ( canvas_height / 2 ) - ( center_y * media_height ) ) )
    

def GetZoomCenter( canvas_size: tuple[ int, int ], media_pos: tuple[ int, int ], media_size: tuple[ int, int ] ) -> tuple[ float, float ]:
    
    # the point of the media in the middle of the canvas, as a fraction of its width and height. zoom timestamps save their pan like this, so it follows the window's size like their zoom does
    ( canvas_width, canvas_height ) = canvas_size
    ( media_x, media_y ) = media_pos
    ( media_width, media_height ) = media_size
    
    center_x = 0.5 if media_width <= 0 else ( ( canvas_width / 2 ) - media_x ) / media_width
    center_y = 0.5 if media_height <= 0 else ( ( canvas_height / 2 ) - media_y ) / media_height
    
    return ( center_x, center_y )
    

def GetZoomTimestampAt( zoom_timestamps: list[ ZoomTimestamp ], timestamp_ms: float ) -> ZoomTimestamp | None:
    
    # the zoom timestamp that playback is under at this point, which is the last one at or before it. None means we are before the first one
    
    current_zoom_timestamp = None
    
    for zoom_timestamp in sorted( zoom_timestamps, key = lambda zoom_timestamp: zoom_timestamp[0] ):
        
        if zoom_timestamp[0] > timestamp_ms:
            
            break
            
        
        current_zoom_timestamp = zoom_timestamp
        
    
    return current_zoom_timestamp
    

def CalculateCanvasMediaSize( media, canvas_size: QC.QSize, show_action ):
    
    canvas_width = canvas_size.width()
    canvas_height = canvas_size.height()
    
    '''if ClientGUICanvasMedia.ShouldHaveAnimationBar( media, show_action ):
        
        animated_scanbar_height = CG.client_controller.new_options.GetInteger( 'animated_scanbar_height' )
        
        canvas_height -= animated_scanbar_height
        '''
    
    canvas_width = max( canvas_width, 80 )
    canvas_height = max( canvas_height, 60 )
    
    return ( canvas_width, canvas_height )
    

def ConvertRotationToPrettyString( rotation: int ) -> str:
    
    return f'{rotation}\u00b0'
    

# the orientations the media viewer's right-click menu offers. anything else is 'custom'
ORIENTATION_MENU_ROTATIONS = ( 0, 90, 180, 270 )

def NormaliseRotation( rotation: float ) -> int:
    
    # whole degrees clockwise, 0 to 359
    return int( round( rotation ) ) % 360
    

def GetRotatedBoundingSize( width: float, height: float, rotation: int ) -> tuple[ float, float ]:
    
    # the size of the box a width x height rectangle fits in once it is turned this many degrees
    rotation = NormaliseRotation( rotation )
    
    if rotation in ( 0, 180 ):
        
        return ( width, height )
        
    elif rotation in ( 90, 270 ):
        
        return ( height, width )
        
    
    radians = math.radians( rotation )
    
    c = abs( math.cos( radians ) )
    s = abs( math.sin( radians ) )
    
    return ( width * c + height * s, width * s + height * c )
    

def GetUnrotatedSizeInBoundingSize( bounding_width: float, bounding_height: float, media_width: float, media_height: float, rotation: int ) -> tuple[ float, float ]:
    
    # the other way: how big the media is, before it is turned, when its turned box is this big
    ( unit_bounding_width, unit_bounding_height ) = GetRotatedBoundingSize( media_width, media_height, rotation )
    
    zoom = min( bounding_width / unit_bounding_width, bounding_height / unit_bounding_height )
    
    return ( media_width * zoom, media_height * zoom )
    

def CalculateCanvasZooms( canvas_size: QC.QSize, canvas_type: int, device_pixel_ratio: float, media, show_action, rotation: int = 0 ) -> dict[ int, int ]:
    
    zoom_types_to_zooms = {
        MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE : 1.0,
        MEDIA_VIEWER_ZOOM_TYPE_CANVAS : 1.0,
        MEDIA_VIEWER_ZOOM_TYPE_FILL_AUTO : 1.0,
        MEDIA_VIEWER_ZOOM_TYPE_FILL_X : 1.0,
        MEDIA_VIEWER_ZOOM_TYPE_FILL_Y : 1.0,
        MEDIA_VIEWER_ZOOM_TYPE_100 : 1.0
    }
    
    if media is None:
        
        return zoom_types_to_zooms
        
    
    if show_action in ( CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW_ON_ACTIVATION_OPEN_EXTERNALLY, CC.MEDIA_VIEWER_ACTION_SHOW_OPEN_EXTERNALLY_BUTTON, CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW ):
        
        return zoom_types_to_zooms
        
    
    new_options = CG.client_controller.new_options
    
    ( media_width, media_height ) = CalculateMediaSize( media, 1.0, rotation = rotation )
    
    ( canvas_width, canvas_height ) = CalculateCanvasMediaSize( media, canvas_size, show_action )
    
    raw_canvas_width = canvas_width * device_pixel_ratio
    raw_canvas_height = canvas_height * device_pixel_ratio
    
    width_zoom = raw_canvas_width / media_width
    
    height_zoom = raw_canvas_height / media_height
    
    canvas_zoom = min( ( width_zoom, height_zoom ) )
    
    image_aspect = media_width / media_height
    canvas_aspect = raw_canvas_width / raw_canvas_height
    
    #overfill the canvas
    if image_aspect > canvas_aspect:
        
        fill_auto_zoom = height_zoom
        
    else:
        
        fill_auto_zoom = width_zoom
        
    
    zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ] = canvas_zoom
    zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_FILL_X ] = width_zoom
    zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_FILL_Y ] = height_zoom
    zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_FILL_AUTO ] = fill_auto_zoom
    
    #
    
    mime = media.GetMime()
    
    ( media_scale_up, media_scale_down, preview_scale_up, preview_scale_down, exact_zooms_only, scale_up_quality, scale_down_quality ) = new_options.GetMediaZoomOptions( mime )
    
    if exact_zooms_only:
        
        max_regular_zoom = 1.0
        
        if canvas_zoom > 1.0:
            
            while max_regular_zoom * 2 < canvas_zoom:
                
                max_regular_zoom *= 2
                
            
        elif canvas_zoom < 1.0:
            
            while max_regular_zoom > canvas_zoom:
                
                max_regular_zoom /= 2
                
            
        
    else:
        
        regular_zooms = new_options.GetMediaZooms()
        
        valid_regular_zooms = [ zoom for zoom in regular_zooms if zoom < canvas_zoom ]
        
        if len( valid_regular_zooms ) > 0:
            
            max_regular_zoom = max( valid_regular_zooms )
            
        else:
            
            max_regular_zoom = canvas_zoom
            
        
    
    if media.GetMime() in HC.AUDIO:
        
        scale_up_action = CC.MEDIA_VIEWER_SCALE_100
        scale_down_action = CC.MEDIA_VIEWER_SCALE_TO_CANVAS
        
    elif canvas_type == CC.CANVAS_PREVIEW:
        
        scale_up_action = preview_scale_up
        scale_down_action = preview_scale_down
        
    else:
        
        scale_up_action = media_scale_up
        scale_down_action = media_scale_down
        
    
    can_be_scaled_down = media_width > raw_canvas_width or media_height > raw_canvas_height
    can_be_scaled_up = media_width < raw_canvas_width and media_height < raw_canvas_height
    
    #
    
    if can_be_scaled_up:
        
        scale_action = scale_up_action
        
    elif can_be_scaled_down:
        
        scale_action = scale_down_action
        
    else:
        
        scale_action = CC.MEDIA_VIEWER_SCALE_100
        
    
    if scale_action == CC.MEDIA_VIEWER_SCALE_100:
        
        default_zoom = 1.0
        
    elif scale_action == CC.MEDIA_VIEWER_SCALE_MAX_REGULAR:
        
        default_zoom = max_regular_zoom
        
    else:
        
        default_zoom = canvas_zoom
        
    
    zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE ] = default_zoom
    
    return zoom_types_to_zooms
    

def CalculateMediaContainerSize( media, device_pixel_ratio: float, zoom, show_action, rotation: int = 0 ) -> QC.QSize:
    
    if show_action in ( CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW_ON_ACTIVATION_OPEN_EXTERNALLY, CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW ):
        
        raise Exception( 'This media should not be shown in the media viewer!' )
        
    elif show_action == CC.MEDIA_VIEWER_ACTION_SHOW_OPEN_EXTERNALLY_BUTTON:
        
        ( width, height ) = OPEN_EXTERNALLY_BUTTON_SIZE
        
        # Note that this handles a zipfile default thumb too. by sending None resolution to GetThumbnailResolution, it falls back to default dimensions
        # imperfect, but overall fine for most situations
        
        bounding_dimensions = CG.client_controller.options[ 'thumbnail_dimensions' ]
        thumbnail_scale_type = CG.client_controller.new_options.GetInteger( 'thumbnail_scale_type' )
        
        # we want the device independant size here, not actual pixels, so want to keep this 100
        #thumbnail_dpr_percent = CG.client_controller.new_options.GetInteger( 'thumbnail_dpr_percent' )
        thumbnail_dpr_percent = 100
        
        ( thumb_width, thumb_height ) = HydrusImageHandling.GetThumbnailResolution( media.GetResolution(), bounding_dimensions, thumbnail_scale_type, thumbnail_dpr_percent )
        
        height = height + min( OPEN_EXTERNALLY_MAX_THUMBNAIL_SIZE[1], thumb_height )
        
        return QC.QSize( width, height )
        
    else:
        
        ( raw_media_width, raw_media_height ) = CalculateMediaSize( media, zoom, rotation = rotation )
        
        media_width = int( raw_media_width / device_pixel_ratio )
        media_height = int( raw_media_height / device_pixel_ratio )
        
        return QC.QSize( media_width, media_height )
        
    

def CalculateMediaSize( media, zoom, rotation: int = 0 ):
    
    # a rotated file takes up the box it fits in once it is turned
    if media.GetMime() in HC.AUDIO or not media.HasUsefulResolution():
        
        ( original_width, original_height ) = ( 360, 240 )
        
        if zoom >= 1:
            
            # audio player can only be scaled down, not up
            return ( original_width, original_height )
            
        
    else:
        
        ( original_width, original_height ) = GetRotatedBoundingSize( *media.GetResolution(), rotation )
        
    
    media_width = int( round( zoom * original_width ) )
    media_height = int( round( zoom * original_height ) )
    
    media_width = max( 1, media_width )
    media_height = max( 1, media_height )
    
    return ( media_width, media_height )
    

def ShouldHaveAnimationBar( media, show_action ):
    
    if media is None:
        
        return False
        
    
    if show_action not in ( CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_MPV, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_QTMEDIAPLAYER ):
        
        return False
        
    
    if not media.HasDuration() and media.GetMime() is not HC.ANIMATION_UGOIRA:
        
        return False
        
    
    is_animation = media.GetMime() in HC.VIEWABLE_ANIMATIONS
    is_audio = media.GetMime() in HC.AUDIO
    is_video = media.GetMime() in HC.VIDEO
    
    if show_action in ( CC.MEDIA_VIEWER_ACTION_SHOW_WITH_MPV, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_QTMEDIAPLAYER ):
        
        if is_animation or is_audio or is_video:
            
            return True
            
        
    elif show_action == CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE:
        
        if is_animation or is_video:
            
            return True
            
        
    
    return False
    

def WeAreExpectingToLoadThisMediaFile( media_result: ClientMediaResult.MediaResult, canvas_type: int ) -> bool:
    
    ( media_show_action, media_start_paused, media_start_with_embed ) = ClientMedia.GetShowAction( media_result, canvas_type )
    
    if media_show_action in ( CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_MPV, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_QTMEDIAPLAYER ):
        
        return True
        
    
    return False
    

class Animation( CAC.ApplicationCommandProcessorMixin, QW.QWidget ):
    
    launchMediaViewer = QC.Signal()
    
    def __init__( self, parent, canvas_type, background_colour_generator ):
        
        super().__init__( parent )
        
        self._canvas_type = canvas_type
        self._background_colour_generator = background_colour_generator
        
        # pass up un-button-pressed mouse moves to parent, which wants to do cursor show/hide
        self.setMouseTracking( True )
        
        self._media = None
        
        self._last_device_pixel_ratio = self.devicePixelRatio()
        
        self._have_drawn_background_once = False
        self._playthrough_count = 0
        
        self._num_frames = 1
        
        self._frame_durations_ms = None
        self._duration_ms = None
        
        self._stop_for_slideshow = False
        
        self._current_frame_index = 0
        self._current_frame_drawn = False
        self._current_timestamp_ms = None
        self._next_frame_due_at = HydrusTime.GetNowPrecise()
        self._slow_frame_score = 1.0
        
        self._paused = True
        
        self._ab_loop_a_ms: int | None = None
        self._ab_loop_b_ms: int | None = None
        
        self._video_container = None
        
        self._canvas_qt_pixmap = None
        
        # degrees clockwise. we are the size of the box the turned frames fit in
        self._rotation = 0
        
        if self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES:
            
            shortcut_set = 'media_viewer_media_window'
            
        else:
            
            shortcut_set = 'preview_media_window'
            
        
        self._my_shortcut_handler = ClientGUIShortcuts.ShortcutsHandler( self, self, [ shortcut_set ], catch_mouse = True )
        
    
    def _ABLoopWantsToJumpBack( self, next_frame_index: int ) -> bool:
        
        if self._ab_loop_b_ms is None or self._video_container is None or not self._video_container.IsInitialised():
            
            return False
            
        
        if next_frame_index == 0:
            
            # B is at the very end, or the user seeked past it--either way, wrap round to A, not the start
            return True
            
        
        # like mpv, we only loop when normal playback runs over B. a user seek past B is left alone
        current_frame_timestamp_ms = self._video_container.GetTimestampMS( self._current_frame_index )
        next_frame_timestamp_ms = self._video_container.GetTimestampMS( next_frame_index )
        
        return current_frame_timestamp_ms <= self._ab_loop_b_ms < next_frame_timestamp_ms
        
    
    def _ClearCanvasBitmap( self ):
        
        if self._canvas_qt_pixmap is not None:
            
            self._canvas_qt_pixmap = None
            
        
    
    def _GetRawPixelSize( self ) -> QC.QSize:
        
        return self.size() * self.devicePixelRatio()
        
    
    def _GetRenderRawPixelSize( self ) -> QC.QSize:
        
        # the size the frames are rendered at. when they are turned, that is a different shape to us
        my_raw_size = self._GetRawPixelSize()
        
        if self._rotation == 0 or self._media is None or None in self._media.GetResolution():
            
            return my_raw_size
            
        
        ( media_width, media_height ) = self._media.GetResolution()
        
        ( width, height ) = GetUnrotatedSizeInBoundingSize( my_raw_size.width(), my_raw_size.height(), media_width, media_height, self._rotation )
        
        return QC.QSize( max( 1, round( width ) ), max( 1, round( height ) ) )
        
    
    def _GetFrameIndexAtPlaybackPoint( self, point_ms: int ) -> int:
        
        frame_index = GetFrameIndexAtPlaybackPoint( point_ms, self._num_frames, self._video_container.GetTimestampMS )
        
        return max( 0, min( frame_index, self._num_frames - 1 ) )
        
    
    def _JumpToABLoopStart( self ):
        
        a_ms = 0 if self._ab_loop_a_ms is None else self._ab_loop_a_ms
        
        frame_index = self._GetFrameIndexAtPlaybackPoint( a_ms )
        
        self._current_frame_index = frame_index
        self._current_timestamp_ms = self._video_container.GetTimestampMS( frame_index )
        
        self._video_container.GetReadyForFrame( frame_index )
        
    
    def _ReinitForResizeOrDPRChange( self ):
        
        my_raw_size = self._GetRenderRawPixelSize()
        
        my_raw_width = my_raw_size.width()
        my_raw_height = my_raw_size.height()
        
        self._ClearCanvasBitmap()
        
        self._last_device_pixel_ratio = self.devicePixelRatio()
        
        self._current_frame_drawn = False
        self._have_drawn_background_once = False
        
        self.update()
        
        if self._media is not None:
            
            ( media_width, media_height ) = self._media.GetResolution()
            
            if self._video_container is not None:
                
                ( renderer_width, renderer_height ) = self._video_container.GetSize()
                
                we_just_zoomed_in = my_raw_width > renderer_width or my_raw_height > renderer_height
                we_just_zoomed_out = my_raw_width < renderer_width or my_raw_height < renderer_height
                
                if we_just_zoomed_in:
                    
                    if self._video_container.IsScaled():
                        
                        target_width = min( media_width, my_raw_width )
                        target_height = min( media_height, my_raw_height )
                        
                        self._video_container.Stop()
                        
                        self._video_container = ClientRendering.RasterContainerVideo( self._media, ( target_width, target_height ), init_position = self._current_frame_index, frame_durations_ms = self._frame_durations_ms )
                        
                    
                elif we_just_zoomed_out:
                    
                    if my_raw_width < media_width or my_raw_height < media_height: # i.e. new zoom is scaled
                        
                        self._video_container.Stop()
                        
                        self._video_container = ClientRendering.RasterContainerVideo( self._media, ( my_raw_width, my_raw_height ), init_position = self._current_frame_index, frame_durations_ms = self._frame_durations_ms )
                        
                    
                
            
        
    
    def _TryToDrawCanvasBitmap( self ):
        
        my_raw_size = self._GetRawPixelSize()
        
        my_raw_width = my_raw_size.width()
        my_raw_height = my_raw_size.height()
        
        render_raw_size = self._GetRenderRawPixelSize()
        
        if self._video_container is None:
            
            self._video_container = ClientRendering.RasterContainerVideo( self._media, ( render_raw_size.width(), render_raw_size.height() ), init_position = self._current_frame_index, frame_durations_ms = self._frame_durations_ms )
            
        
        if not self._video_container.HasFrame( self._current_frame_index ):
            
            return
            
        
        if self._canvas_qt_pixmap is None:
            
            self._canvas_qt_pixmap = CG.client_controller.bitmap_manager.GetQtPixmap( my_raw_width, my_raw_height )
            
        
        self._canvas_qt_pixmap.setDevicePixelRatio( self.devicePixelRatio() )
        
        painter = QG.QPainter( self._canvas_qt_pixmap )
        
        # this makes transparency work nice, so just force it
        self._DrawABlankFrame( painter )
        
        current_frame = self._video_container.GetFrame( self._current_frame_index )
        
        current_frame_image = current_frame.GetQtImage()
        
        painter.setRenderHint( QG.QPainter.RenderHint.SmoothPixmapTransform, True )

        # note we draw to self.rect(), which is in DPR coordinates. the pixmap needs to be DPR'd by here mate, this caught us up before
        if self._rotation == 0:
            
            painter.drawImage( self.rect(), current_frame_image )
            
        else:
            
            # turned about our middle
            my_dpr = self.devicePixelRatio()
            
            ( width, height ) = ( render_raw_size.width() / my_dpr, render_raw_size.height() / my_dpr )
            
            painter.translate( self.width() / 2, self.height() / 2 )
            painter.rotate( self._rotation )
            
            painter.drawImage( QC.QRectF( - width / 2, - height / 2, width, height ), current_frame_image )
            
        
        self._current_frame_drawn = True
        
        next_frame_duration_s = HydrusTime.SecondiseMSFloat( self._video_container.GetDurationMS( self._current_frame_index ) )
        
        next_frame_ideally_due = self._next_frame_due_at + next_frame_duration_s
        
        if HydrusTime.TimeHasPassedPrecise( next_frame_ideally_due ):
            
            self._next_frame_due_at = HydrusTime.GetNowPrecise() + next_frame_duration_s
            
        else:
            
            self._next_frame_due_at = next_frame_ideally_due
            
        
    
    def _DrawABlankFrame( self, painter ):
        
        if self._background_colour_generator.CanDoTransparencyCheckerboard() and self._media is not None and self._media.GetFileInfoManager().has_transparency:
            
            if CG.client_controller.new_options.GetBoolean( 'draw_transparency_checkerboard_as_greenscreen' ):
                
                brush = ClientGUITransparency.MakeGreenscreenBrush()
                
            else:
                
                brush = ClientGUITransparency.MakeCheckerboardBrush( int( 16 * self.devicePixelRatio() ) )
                
            
        else:
            
            brush = QG.QBrush( self._background_colour_generator.GetColour() )
            
        
        painter.setBackground( brush )
        
        painter.eraseRect( painter.viewport() )
        
        self._have_drawn_background_once = True
        
    
    def ClearMedia( self ):
        
        self.SetMedia( None )
        
    
    def CurrentFrame( self ):
        
        return self._current_frame_index
        
    
    def GetCurrentFrameStartAndDurationMS( self ) -> tuple[ float, float ] | None:
        
        if self._video_container is None or not self._video_container.IsInitialised():
            
            return None
            
        
        return ( self._video_container.GetTimestampMS( self._current_frame_index ), self._video_container.GetDurationMS( self._current_frame_index ) )
        
    
    def GetAnimationBarStatus( self ):
        
        if self._video_container is None:
            
            buffer_indices = None
            
        else:
            
            buffer_indices = self._video_container.GetBufferIndices()
            
            if self._current_timestamp_ms is None and self._video_container.IsInitialised():
                
                self._current_timestamp_ms = self._video_container.GetTimestampMS( self._current_frame_index )
                
            
        
        return ( self._current_frame_index, self._current_timestamp_ms, self._paused, buffer_indices )
        
    
    def GotoFrame( self, frame_index, pause_afterwards = True ):
        
        if self._video_container is not None and self._video_container.IsInitialised():
            
            if frame_index != self._current_frame_index:
                
                self._current_frame_index = frame_index
                self._current_timestamp_ms = None
                
                self._next_frame_due_at = HydrusTime.GetNowPrecise()
                
                self._video_container.GetReadyForFrame( self._current_frame_index )
                
                self._current_frame_drawn = False
                
                self.update()
                
            
            if pause_afterwards:
                
                self._paused = True
                
            
        
    
    def GotoTimestamp( self, timestamp_ms, round_direction, pause_afterwards = True ):
        
        if self._video_container is not None and self._video_container.IsInitialised():
            
            frame_index = self._video_container.GetFrameIndex( timestamp_ms )
            
            if frame_index == self._current_frame_index:
                
                frame_index += round_direction
                
            
            frame_index = max( 0, frame_index )
            
            if frame_index > self._media.GetNumFrames() - 1:
                
                frame_index = 0
                
            
            self.GotoFrame( frame_index, pause_afterwards = pause_afterwards )
            
        
    
    def HasPlayedOnceThrough( self ):
        
        return self._playthrough_count > 0
        
    
    def IsPaused( self ):
        
        return self._paused
        
    
    def paintEvent( self, event ):
        
        try:
            
            if self.devicePixelRatio() != self._last_device_pixel_ratio:
                
                self._ReinitForResizeOrDPRChange()
                
            
            if not self._current_frame_drawn:
                
                self._TryToDrawCanvasBitmap()
                
            
            painter = QG.QPainter( self )
            
            if self._canvas_qt_pixmap is None:
                
                self._DrawABlankFrame( painter )
                
            else:
                
                painter.drawPixmap( self.rect(), self._canvas_qt_pixmap )
                
            
        except Exception as e:
            
            ClientGUIExceptionHandling.HandlePaintEventException( self, e )
            
        
    
    def Pause( self ):
        
        self._paused = True
        
    
    def PausePlay( self ):
        
        self._paused = not self._paused
        
    
    def Play( self ):
        
        self._paused = False
        
    
    def ProcessApplicationCommand( self, command: CAC.ApplicationCommand ) -> bool:
        
        command_matched = True
        
        if command.IsSimpleCommand():
            
            action = command.GetSimpleAction()
            
            if action == CAC.SIMPLE_PAUSE_MEDIA:
                
                self.Pause()
                
            elif action == CAC.SIMPLE_PAUSE_PLAY_MEDIA:
                
                self.PausePlay()
                
            elif action == CAC.SIMPLE_MEDIA_SEEK_DELTA:
                
                ( direction, duration_ms ) = command.GetSimpleData()
                
                self.SeekDelta( direction, duration_ms )
                
            elif action == CAC.SIMPLE_CLOSE_MEDIA_VIEWER and self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES:
                
                self.window().close()
                
            elif action == CAC.SIMPLE_LAUNCH_MEDIA_VIEWER and self._canvas_type == CC.CANVAS_PREVIEW:
                
                self.launchMediaViewer.emit()
                
            else:
                
                command_matched = False
                
            
        else:
            
            command_matched = False
            
        
        return command_matched
        
    
    def resizeEvent( self, event ):
        
        size = self.size()
        
        my_raw_width = size.width()
        my_raw_height = size.height()
        
        if my_raw_width > 0 and my_raw_height > 0:
            
            if size != event.oldSize():
                
                self._ReinitForResizeOrDPRChange()
                
            
        
    
    def SetRotation( self, rotation: int ):
        
        if rotation == self._rotation:
            
            return
            
        
        self._rotation = rotation
        
        self._ReinitForResizeOrDPRChange()
        
    
    def SeekDelta( self, direction, duration_ms ):
        
        if self._current_timestamp_ms is not None and self._video_container is not None and self._video_container.IsInitialised():
            
            new_ts = max( 0, self._current_timestamp_ms + ( direction * duration_ms ) )
            
            self.GotoTimestamp( new_ts, direction, pause_afterwards = False )
            
        
    
    def SeekPastPlaybackSkip( self, timestamp_ms: int ):
        
        if self._video_container is not None and self._video_container.IsInitialised():
            
            # the first frame that is not in the skip. a skip that runs off the end lands on the last frame, so the normal wrap-around to the start still counts the playthrough
            frame_index = self._GetFrameIndexAtPlaybackPoint( timestamp_ms )
            
            self.GotoFrame( frame_index, pause_afterwards = False )
            
        
    
    def SetABLoop( self, a_ms: int | None, b_ms: int | None ):
        
        self._ab_loop_a_ms = a_ms
        self._ab_loop_b_ms = b_ms
        
    
    def SetBackgroundColourGenerator( self, background_colour_generator ):
        
        self._background_colour_generator = background_colour_generator
        
    
    def StopForSlideshow( self, value ):
        
        self._stop_for_slideshow = value
        
    
    def SetMedia( self, media: ClientMediaSingle.MediaSingle | None, start_paused = False ):
        
        if media == self._media:
            
            return
            
        
        self._media = media
        
        self.SetABLoop( None, None )
        
        self._ClearCanvasBitmap()
        
        self._have_drawn_background_once = False
        self._playthrough_count = 0
        
        self._stop_for_slideshow = False
        
        self._current_frame_index = int( ( self._num_frames - 1 ) * HC.options[ 'animation_start_position' ] )
        self._current_frame_drawn = False
        self._current_timestamp_ms = None
        self._next_frame_due_at = HydrusTime.GetNowPrecise()
        self._slow_frame_score = 1.0
        
        self._paused = start_paused
        
        if self._video_container is not None:
            
            self._video_container.Stop()
            
        
        self._video_container = None
        
        self._frame_durations_ms = None
        self._duration_ms = None
        
        if self._media is None:
            
            self._num_frames = 1
            
            CG.client_controller.gui.UnregisterAnimationUpdateWindow( self )
            
        else:
            
            self._num_frames = self._media.GetNumFrames()
            
            if self._num_frames == 0 or self._num_frames is None:
                
                self._num_frames = 1
                
            
            self._duration_ms = self._media.GetDurationMS()
            
            if self._media.GetMime() == HC.ANIMATION_UGOIRA:
                
                self._frame_durations_ms = ClientUgoiraHandling.GetFrameDurationsMSUgoira( media.GetMediaResult() )
                
            
            if self._duration_ms is None and self._frame_durations_ms is not None:
                
                self._duration_ms = sum( self._frame_durations_ms )
                
            
            CG.client_controller.gui.RegisterAnimationUpdateWindow( self )
            
            self.update()
            
        
        
    def GetDurationMS( self ):
        
        return self._duration_ms
        
    
    def GetNumFrames( self ):
        
        return self._num_frames
        
    
    def TakeSnapshot( self, path: str, callback: typing.Callable[ [ Exception | None ], None ] ):
        
        # rendering the frame again takes a moment, so this works in the background and calls back from there, with an error if it did not work
        if self._media is None:
            
            CG.client_controller.CallToThread( callback, Exception( 'There is no frame to take a snapshot of!' ) )
            
            return
            
        
        media = self._media
        frame_index = self._current_frame_index
        frame_durations_ms = self._frame_durations_ms
        
        def do_it():
            
            try:
                
                # the frames we show are scaled to fit the canvas, so we render this one again at its own resolution
                video_container = ClientRendering.RasterContainerVideo( media, init_position = frame_index, frame_durations_ms = frame_durations_ms )
                
                try:
                    
                    give_up_time = HydrusTime.GetNowFloat() + 60
                    
                    while not video_container.HasFrame( frame_index ):
                        
                        if HG.started_shutdown:
                            
                            raise Exception( 'The client is shutting down!' )
                            
                        
                        if HydrusTime.TimeHasPassedFloat( give_up_time ):
                            
                            raise Exception( 'Rendering the frame took too long!' )
                            
                        
                        time.sleep( 0.05 )
                        
                    
                    qt_image = video_container.GetFrame( frame_index ).GetQtImage()
                    
                    if not qt_image.save( path, 'PNG' ):
                        
                        raise Exception( f'Could not save the snapshot to "{path}"!' )
                        
                    
                finally:
                    
                    video_container.Stop()
                    
                
            except Exception as e:
                
                callback( e )
                
                return
                
            
            callback( None )
            
        
        CG.client_controller.CallToThread( do_it )
        
    
    def TIMERAnimationUpdate( self ):
        
        if self._media is None:
            
            return
            
        
        try:
            
            if self.isVisible():
                
                if self._current_frame_drawn:
                    
                    if not self._paused and HydrusTime.TimeHasPassedPrecise( self._next_frame_due_at ):
                        
                        num_frames = self._media.GetNumFrames()
                        
                        next_frame_index = ( self._current_frame_index + 1 ) % num_frames
                        
                        if self._ABLoopWantsToJumpBack( next_frame_index ):
                            
                            self._JumpToABLoopStart()
                            
                        elif next_frame_index == 0:
                            
                            self._playthrough_count += 1
                            
                            do_times_to_play_animation_pause = False
                            
                            if self._media.GetMime() in HC.VIEWABLE_ANIMATIONS and not CG.client_controller.new_options.GetBoolean( 'always_loop_gifs' ):
                                
                                times_to_play_animation = self._video_container.GetTimesToPlayAnimation()
                                
                                # 0 is infinite
                                if times_to_play_animation != 0 and self._playthrough_count >= times_to_play_animation:
                                    
                                    do_times_to_play_animation_pause = True
                                    
                                
                            
                            if self._stop_for_slideshow or do_times_to_play_animation_pause:
                                
                                self._paused = True
                                
                            else:
                                
                                self._current_frame_index = next_frame_index
                                self._current_timestamp_ms = 0
                                
                            
                        else:
                            
                            self._current_frame_index = next_frame_index
                            
                            if self._current_timestamp_ms is not None and self._video_container is not None and self._video_container.IsInitialised():
                                
                                duration_ms = self._video_container.GetDurationMS( self._current_frame_index - 1 )
                                
                                self._current_timestamp_ms += duration_ms
                                
                            
                        
                        self._current_frame_drawn = False
                        
                    
                
                if self._video_container is not None:
                    
                    if not self._current_frame_drawn:
                        
                        if self._video_container.HasFrame( self._current_frame_index ):
                            
                            self.update()
                            
                        
                    
                
            
        except Exception as e:
            
            CG.client_controller.gui.UnregisterAnimationUpdateWindow( self )
            
            raise
            
        
    

class AnimationBar( QW.QWidget ):
    
    def __init__( self, parent ):
        
        super().__init__( parent )
        
        self._qss_colours = {
            'hab_border' : QG.QColor( 0, 0, 0 ),
            'hab_background' : QG.QColor( 240, 240, 240 ),
            'hab_nub' : QG.QColor( 96, 96, 96 )
        }
        
        self.setObjectName( 'HydrusAnimationBar' )
        
        self.setCursor( QG.QCursor( QC.Qt.CursorShape.ArrowCursor ) )
        
        self.setSizePolicy( QW.QSizePolicy.Policy.Fixed, QW.QSizePolicy.Policy.Fixed )
        
        self._media_window = None
        self._duration_ms = 1000
        self._num_frames = 1
        self._last_drawn_info = None
        self._next_draw_info = None
        self._show_gubbins = True
        
        self._show_text = True
        
        self._currently_in_a_drag = False
        self._it_was_playing_before_drag = False
        
    
    def _DoAnimationStatusUpdate( self ):
        
        if self._CurrentMediaWindowIsBad():
            
            return
            
        
        # we must never call this method in the paintEvent
        current_animation_bar_status = self._media_window.GetAnimationBarStatus()
        
        if self._last_drawn_info != current_animation_bar_status:
            
            self._next_draw_info = current_animation_bar_status
            
            self.update()
            
        
    
    def _DrawBlank( self, painter ):
        
        self.setProperty( 'playing', False )
        
        background_colour = self._qss_colours[ 'hab_background' ]
        
        painter.setBackground( background_colour )
        
        painter.eraseRect( painter.viewport() )
        
    
    def _GetXFromFrameIndex( self, index, width_offset = 0 ):
        
        if self._num_frames is None or self._num_frames < 2:
            
            return 0
            
        
        my_width = self.size().width()
        
        return int( ( my_width - width_offset ) * index / ( self._num_frames - 1 ) )
        
    
    def _GetXFromTimestamp( self, timestamp_ms, width_offset = 0 ):
        
        my_width = self.size().width()
        
        return int( ( my_width - width_offset ) * timestamp_ms / self._duration_ms )
        
    
    def _CurrentMediaWindowIsBad( self ):
        
        if self._media_window is None:
            
            return True
            
        
        if not QP.isValid( self._media_window ):
            
            self.ClearMedia()
            
            return True
            
        
        return False
        
    
    def _Redraw( self, painter ):
        
        # making an extra note here: do not under any circumstances query the mpv window during our paint event
        # it leads to the QBackingStore::endPaint() errors when mpv is unhappy/unloaded
        # always fetch that info and handle various error states in the TIMERAnimationUpdate and just draw cached info here
        
        ( current_frame_index, current_timestamp_ms, paused, buffer_indices )  = self._next_draw_info
        
        self.setProperty( 'playing', not paused )
        
        my_width = self.size().width()
        my_height = self.size().height()
        
        background_colour = self._qss_colours[ 'hab_background' ]
        
        if paused:
            
            background_colour = ClientGUIFunctions.GetLighterDarkerColour( background_colour )
            
        
        painter.setBackground( QG.QBrush( background_colour ) )
        
        painter.eraseRect( painter.viewport() )
        
        #
        
        if self._show_gubbins:
            
            if buffer_indices is not None:
                
                ( start_index, rendered_to_index, end_index ) = buffer_indices
                
                if ClientRendering.FrameIndexOutOfRange( rendered_to_index, start_index, end_index ):
                    
                    rendered_to_index = start_index
                    
                
                start_x = self._GetXFromFrameIndex( start_index )
                rendered_to_x = self._GetXFromFrameIndex( rendered_to_index )
                end_x = self._GetXFromFrameIndex( end_index )
                
                if start_x != rendered_to_x:
                    
                    rendered_colour = ClientGUIFunctions.GetDifferentLighterDarkerColour( background_colour )
                    
                    if rendered_to_x > start_x:
                        
                        painter.fillRect( start_x, 0, rendered_to_x - start_x, my_height, rendered_colour )
                        
                    else:
                        
                        painter.fillRect( start_x, 0, my_width - start_x, my_height, rendered_colour )
                        
                        painter.fillRect( 0, 0, rendered_to_x, my_height, rendered_colour )
                        
                    
                
                if rendered_to_x != end_x:
                    
                    to_be_rendered_colour = ClientGUIFunctions.GetDifferentLighterDarkerColour( background_colour, 1 )
                    
                    if end_x > rendered_to_x:
                        
                        painter.fillRect( rendered_to_x, 0, end_x - rendered_to_x, my_height, to_be_rendered_colour )
                        
                    else:
                        
                        painter.fillRect( rendered_to_x, 0, my_width - rendered_to_x, my_height, to_be_rendered_colour )
                        
                        painter.fillRect( 0, 0, end_x, my_height, to_be_rendered_colour )
                        
                    
                
            
            animated_scanbar_nub_width = CG.client_controller.new_options.GetInteger( 'animated_scanbar_nub_width' )
            
            num_frames_are_useful = self._num_frames is not None and self._num_frames > 1
            
            nub_x = None
            
            if num_frames_are_useful and current_frame_index is not None:
                
                nub_x = self._GetXFromFrameIndex( current_frame_index, width_offset = animated_scanbar_nub_width )
                
            elif self._duration_ms is not None and current_timestamp_ms is not None:
                
                nub_x = self._GetXFromTimestamp( current_timestamp_ms, width_offset = animated_scanbar_nub_width )
                
            
            if nub_x is not None:
                
                painter.fillRect( nub_x, 0, animated_scanbar_nub_width, my_height, self._qss_colours[ 'hab_nub' ] )
                
            
            #
            
            if self._show_text:
                
                progress_strings = []
                
                if num_frames_are_useful:
                    
                    progress_strings.append( HydrusNumbers.ValueRangeToPrettyString( current_frame_index + 1, self._num_frames ) )
                    
                
                if current_timestamp_ms is not None:
                    
                    progress_strings.append( HydrusTime.ValueRangeToScanbarTimestampsMS( current_timestamp_ms, self._duration_ms ) )
                    
                
                s = ' - '.join( progress_strings )
                
                if len( s ) > 0:
                    
                    ( text_size, s ) = ClientGUIFunctions.GetTextSizeFromPainter( painter, s )
                    
                    x = my_width - text_size.width() - 3
                    y = round( ( my_height - text_size.height() ) / 2 )
                    
                    ClientGUIFunctions.DrawText( painter, x, y, s )
                    
                
            
        
        #
        
        painter.setBrush( QC.Qt.BrushStyle.NoBrush )
        
        painter.setPen( QG.QPen( self._qss_colours[ 'hab_border' ] ) )
        
        painter.drawRect( 0, 0, my_width - 1, my_height - 1 )
        
    
    def _ScanToCurrentMousePos( self, precise = True ):
        
        my_width = self.size().width()
        
        mouse_pos = self.mapFromGlobal( ClientGUIFunctions.GetMousePos() )
        
        animated_scanbar_nub_width = CG.client_controller.new_options.GetInteger( 'animated_scanbar_nub_width' )
        
        compensated_x_position = mouse_pos.x() - ( animated_scanbar_nub_width / 2 )
        
        proportion = ( compensated_x_position ) / ( my_width - animated_scanbar_nub_width )
        
        proportion = max( proportion, 0.0 )
        proportion = min( 1.0, proportion )
        
        self.update()
        
        if isinstance( self._media_window, Animation ):
            
            current_frame_index = int( proportion * ( self._num_frames - 1 ) + 0.5 )
            
            self._media_window.GotoFrame( current_frame_index )
            
        elif isinstance( self._media_window, ( ClientGUIMPV.MPVWidget, ClientGUIQtMediaPlayer.QtMediaPlayer ) ):
            
            time_index_ms = int( proportion * self._duration_ms )
            
            self._media_window.Seek( time_index_ms, precise = precise )
            
        
    
    def ClearMedia( self ):
        
        self._media_window = None
        self._show_gubbins = True
        
        CG.client_controller.gui.UnregisterAnimationUpdateWindow( self )
        
        self.update()
        
    
    def DoingADrag( self ):
        
        return self._currently_in_a_drag
        
    
    def mouseMoveEvent( self, event ):
        
        if self._CurrentMediaWindowIsBad():
            
            return
            
        
        CC.CAN_HIDE_MOUSE = False
        
        if self._currently_in_a_drag:
            
            if event.buttons() == QC.Qt.MouseButton.NoButton:
                
                self._currently_in_a_drag = False
                
                return
                
            
            self._ScanToCurrentMousePos( precise = False )
            
        
    
    def mousePressEvent( self, event ):
        
        if self._CurrentMediaWindowIsBad():
            
            return
            
        
        CC.CAN_HIDE_MOUSE = False
        
        self._it_was_playing_before_drag = not self._media_window.IsPaused()
        
        if self._it_was_playing_before_drag:
            
            self._media_window.Pause()
            
        
        self._currently_in_a_drag = True
        
        self._ScanToCurrentMousePos( precise = True )
        
    
    def mouseReleaseEvent( self, event ):
        
        CC.CAN_HIDE_MOUSE = True
        
        if self._currently_in_a_drag:
            
            if self._it_was_playing_before_drag:
                
                if not self._CurrentMediaWindowIsBad():
                    
                    self._media_window.Play()
                    
                
            
            self._currently_in_a_drag = False
            
            # have this if you want to play around with the 'non-precise on drag', but in the first test it didn't work out nice IRL
            # self._ScanToCurrentMousePos( precise = True )
            
        
    
    def paintEvent( self, event ):
        
        try:
            
            painter = QG.QPainter( self )
            
            if self._CurrentMediaWindowIsBad() or self._next_draw_info is None:
                
                self._DrawBlank( painter )
                
                self._next_draw_info = None
                
            else:
                
                self._Redraw( painter )
                
            
            self._last_drawn_info = self._next_draw_info
            
        except Exception as e:
            
            ClientGUIExceptionHandling.HandlePaintEventException( self, e )
            
        
    
    def setGubbinsVisible( self, show: bool ):
        
        self._show_gubbins = show
        
        self._DoAnimationStatusUpdate()
        
        self.update()
        
    
    def SetMediaAndWindow( self, media, media_window, ):
        
        self._media_window = media_window
        
        num_frames = media.GetNumFrames()
        
        if num_frames is None:
            
            self._num_frames = num_frames
            
        else:
            
            self._num_frames = max( num_frames, 1 )
        
        duration_ms = media.GetDurationMS()
        
        if duration_ms is None and isinstance( media_window, Animation ):
            
            duration_ms = media_window.GetDurationMS()
            
        
        self._duration_ms = max( duration_ms, 1 )
        
        self._currently_in_a_drag = False
        self._it_was_playing_before_drag = False
        
        CG.client_controller.gui.RegisterAnimationUpdateWindow( self )
        
        self._next_draw_info = None
        
        self._show_gubbins = True
        
        self._DoAnimationStatusUpdate()
        
        self.update()
        
    
    def SetShowText( self, show_text: bool ):
        
        self._show_text = show_text
        
    
    def TIMERAnimationUpdate( self ):
        
        if self._CurrentMediaWindowIsBad():
            
            self.ClearMedia()
            
            return
            
        
        self._DoAnimationStatusUpdate()
        
    
    def get_hab_background( self ):
        
        return self._qss_colours[ 'hab_background' ]
        
    
    def get_hab_border( self ):
        
        return self._qss_colours[ 'hab_border' ]
        
    
    def get_hab_nub( self ):
        
        return self._qss_colours[ 'hab_nub' ]
        
    
    def set_hab_background( self, colour ):
        
        self._qss_colours[ 'hab_background' ] = colour
        
    
    def set_hab_border( self, colour ):
        
        self._qss_colours[ 'hab_border' ] = colour
        
    
    def set_hab_nub( self, colour ):
        
        self._qss_colours[ 'hab_nub' ] = colour
        
    
    hab_border = QC.Property( QG.QColor, get_hab_border, set_hab_border )
    hab_background = QC.Property( QG.QColor, get_hab_background, set_hab_background )
    hab_nub = QC.Property( QG.QColor, get_hab_nub, set_hab_nub )
    

# cribbing from here https://doc.qt.io/qt-5/layout.html#how-to-write-a-custom-layout-manager
class MediaContainerLayout( QW.QLayout ):
    
    def __init__( self, static_image ):
        
        super().__init__()
        
        self._static_image = static_image
        
        self._layout_items = [ static_image ]
        
    

class MediaContainer( QW.QWidget ):
    
    launchMediaViewer = QC.Signal()
    readyForNeighbourPrefetch = QC.Signal()
    haveDestroyedAllMediaWindows = QC.Signal()
    sendApplicationCommand = QC.Signal( CAC.ApplicationCommand )
    
    zoomChanged = QC.Signal( int, float )
    abLoopChanged = QC.Signal( object, object )
    muteStateChanged = QC.Signal()
    volumeChanged = QC.Signal()
    
    def __init__( self, parent, canvas, canvas_type, background_colour_generator, additional_event_filter: QC.QObject ):
        
        super().__init__( parent )
        
        self._canvas_type = canvas_type
        self._canvas = canvas
        
        if HC.PLATFORM_MACOS and not HG.macos_antiflicker_test:
            
            # does modern macOS still go 100% CPU when this is off?
            # yes :^(
            # try again with more layout tech on the full canvas
            
            self.setAttribute( QC.Qt.WidgetAttribute.WA_OpaquePaintEvent, True )
            
        
        self._background_colour_generator = background_colour_generator
        
        self.setSizePolicy( QW.QSizePolicy.Policy.Fixed, QW.QSizePolicy.Policy.Fixed )
        
        self._media = None
        self._deferred_set_media_call: HydrusData.Call | None = None
        self._show_action = CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW
        self._start_paused = False
        self._start_with_embed = False
        
        self._current_zoom = 1.0
        
        # the sub-pixel part of the last zoom reposition, carried over so small zoom steps stay anchored on the zoom centerpoint
        self._zoom_position_delta_remainder = ( 0.0, 0.0 )
        
        # a-b repeat. None for 'a' means the start of the media. the loop is active whenever 'b' is set
        self._ab_loop_a_ms: int | None = None
        self._ab_loop_b_ms: int | None = None
        
        # spans of the current file that playback jumps over. each file has its own, saved in the db
        self._playback_skips: list[ tuple[ int, int ] ] = []
        self._playback_skips_load_id = 0
        self._last_playback_skip_seek: tuple[ tuple[ int, int ], float ] | None = None
        
        # zooms, and pans, to change to at points in playback. each file has its own, saved in the db
        # only the media viewer does them. the preview is too small, and the duplicate filter wants to keep the zoom the same between the files it compares
        self._does_zoom_timestamps = self._canvas_type in ( CC.CANVAS_MEDIA_VIEWER, CC.CANVAS_MEDIA_VIEWER_ARCHIVE_DELETE )
        self._zoom_timestamps: list[ ZoomTimestamp ] = []
        self._zoom_timestamps_load_id = 0
        
        # the zoom timestamp we last zoomed to. None means the zoom the file starts at
        self._current_zoom_timestamp: ZoomTimestamp | None = None
        self._current_zoom_timestamp_needs_reapply = False
        self._zoom_timestamps_last_check_was_playing = False
        self._zoom_timestamps_stopped_at_end = False
        self._zoom_timestamps_have_checked = False
        
        # shell commands to run at points in playback, as ( timestamp_ms, command ). each file has its own, saved in the db
        # only the media viewer does them, not the preview or the duplicate filter
        self._does_scripted_events = self._canvas_type in ( CC.CANVAS_MEDIA_VIEWER, CC.CANVAS_MEDIA_VIEWER_ARCHIVE_DELETE )
        self._scripted_events: list[ ClientMediaScriptedEvents.ScriptedEvent ] = []
        self._scripted_events_load_id = 0
        
        # named points in a video to jump to. just videos, and just the media viewer
        self._does_segments = self._canvas_type in ( CC.CANVAS_MEDIA_VIEWER, CC.CANVAS_MEDIA_VIEWER_ARCHIVE_DELETE )
        
        # where playback was at the last check, so we can see what it went past. None means we have not seen it playing yet
        self._scripted_events_last_timestamp_ms: float | None = None
        
        # the zoom the user last set on the current file, which the media viewer opens it at next time. each file has its own, saved in the db
        # the duplicate filter is left out, since it wants to keep the zoom the same between the files it compares
        self._remembers_file_zooms = self._canvas_type in ( CC.CANVAS_MEDIA_VIEWER, CC.CANVAS_MEDIA_VIEWER_ARCHIVE_DELETE )
        self._saved_zoom: float | None = None
        self._saved_zoom_load_id = 0
        
        # after a move to a screen location, the file sits at the default zoom until the user zooms or we go to another file. its saved zoom stays in the db for next time
        self._holding_default_zoom = False
        
        # degrees clockwise that the current file is turned. each file has its own, saved in the db
        self._rotation = 0
        self._rotation_load_id = 0
        
        # where the next file should start playing, as ( media, start_ms ). a playlist sets this for a part of a file, so the player never shows what comes before it
        self._next_media_start: tuple[ ClientMediaSingle.MediaSingle, int | None ] | None = None
        
        # a playlist can load what is coming next into a spare, hidden mpv player, paused at its start, so when it is time, we just swap it in and hit play
        self._standby_mpv_widget: ClientGUIMPV.MPVWidget | None = None
        self._standby_media: ClientMediaSingle.MediaSingle | None = None
        self._standby_start_ms: int | None = None
        
        # the standby file's saved zoom and zoom timestamp rows, looked up ahead of time, so its zoom is right from the first frame. ( hash, saved_zoom, zoom_timestamp_rows ). None until they come back
        self._standby_zoom_data: tuple[ bytes, float | None, list ] | None = None
        self._standby_zoom_data_load_id = 0
        self._standby_zoom_data_hash: bytes | None = None
        
        # what the new file got from that, waiting for its zoom to be set up. ( load_id, value )
        self._saved_zoom_from_standby: tuple[ int, float | None ] | None = None
        self._zoom_timestamp_rows_from_standby: tuple[ int, list ] | None = None
        
        self._zoom_types_to_zooms = {
            MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE : 1.0,
            MEDIA_VIEWER_ZOOM_TYPE_CANVAS : 1.0,
            MEDIA_VIEWER_ZOOM_TYPE_FILL_AUTO : 1.0,
            MEDIA_VIEWER_ZOOM_TYPE_FILL_X : 1.0,
            MEDIA_VIEWER_ZOOM_TYPE_FILL_Y : 1.0,
            MEDIA_VIEWER_ZOOM_TYPE_100 : 1.0
        }
        
        self._current_zoom_type = self._GetDefaultZoomType()
        
        self._closing_mpv_widgets = []
        self._closing_qt_media_players = []
        self._close_check_timer = QC.QTimer()
        self._close_check_timer.timeout.connect( self._CheckClosingWidgets )
        
        self._media_window = None
        self._tie_media_window_to_pauseplay_state = self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES and CG.client_controller.new_options.GetBoolean( 'always_start_media_windows_tied_to_pauseplay_state' )
        self._window_always_on_top_update_timer = QC.QTimer( self )
        self._window_always_on_top_update_timer.setSingleShot( True )
        self._window_always_on_top_update_timer.timeout.connect( self._UpdateWindowAlwaysOnTop )
        
        self._embed_button = EmbedButton( self, self._background_colour_generator )
        self._embed_button_widget_event_filter = QP.WidgetEventFilter( self._embed_button )
        self._embed_button_widget_event_filter.EVT_LEFT_DOWN( self.EventEmbedButton )
        
        # pass up un-button-pressed mouse moves to parent, which wants to do cursor show/hide
        self.setMouseTracking( True )
        
        self._additional_event_filter = additional_event_filter
        
        self._animation_window = Animation( self, self._canvas_type, self._background_colour_generator )
        
        self._static_image_window = StaticImage( self, self._canvas_type, self._background_colour_generator )
        
        self._static_image_window.readyForNeighbourPrefetch.connect( self.readyForNeighbourPrefetch )
        
        self._controls_bar = QW.QWidget( self )
        self._controls_bar_show_full = True
        
        # we establish this guy here but the canvas owns it. not elegant but we want to ensure 'C++ already deleted' stuff works in correct order
        self._qt_media_player_graphics_view_mouse_move_catcher = ClientGUIQtMediaPlayer.GraphicsViewViewportMouseMoveCatcher( self._canvas )
        
        # We need this to force-fill some blanks at times
        self.setAutoFillBackground( True )
        
        self._has_per_player_mute_state = False
        self._per_player_mute_state = False
        
        self._has_per_player_volume = False
        self._per_player_volume = 100
        
        if self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES:
            
            # a new media viewer starts with whatever mute and volume the last one was set to
            # the mute is stored as 0/1 so that None can mean 'nothing set yet, follow the options'
            last_mute = CG.client_controller.new_options.GetNoneableInteger( 'media_viewer_last_mute' )
            
            if last_mute is not None:
                
                self._has_per_player_mute_state = True
                self._per_player_mute_state = bool( last_mute )
                
            
            last_volume = CG.client_controller.new_options.GetNoneableInteger( 'media_viewer_last_volume' )
            
            if last_volume is not None:
                
                self._has_per_player_volume = True
                self._per_player_volume = last_volume
                
            
        
        # these live and die with this container, so they end when the media viewer closes
        self._audio_effects = ClientGUIMediaAudioEffects.AudioEffects()
        
        # in a media viewer, the mute button and volume slider only affect this window
        per_player_audio_owner = self if self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES else None
        
        self._animation_bar = AnimationBar( self._controls_bar )
        self._volume_control = ClientGUIMediaControls.VolumeControl( self._controls_bar, self._canvas_type, direction = 'up', per_player_audio_owner = per_player_audio_owner )
        
        self._volume_control.setCursor( QC.Qt.CursorShape.ArrowCursor )
        
        #
        
        hbox = QP.HBoxLayout( margin = 0, spacing = 0 )
        
        QP.AddToLayout( hbox, self._animation_bar, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        QP.AddToLayout( hbox, self._volume_control, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        self._controls_bar.setLayout( hbox )
        
        #
        
        self._animation_window.hide()
        
        self._controls_bar.hide()
        
        self._static_image_window.hide()
        self._embed_button.hide()
        
        self.hide()
        
        CG.client_controller.sub( self, 'NotifyAudioMuteOptionsChanged', 'notify_new_audio_mute_options' )
        CG.client_controller.sub( self, 'NotifyAudioVolumeOptionsChanged', 'new_audio_volume' )
        CG.client_controller.sub( self, 'Pause', 'pause_all_media' )
        CG.client_controller.sub( self, 'NotifyNewPlaybackSkips', 'new_file_playback_skips' )
        CG.client_controller.sub( self, 'NotifyNewZoomTimestamps', 'new_file_zoom_timestamps' )
        CG.client_controller.sub( self, 'NotifyNewScriptedEvents', 'new_file_scripted_events' )
        CG.client_controller.sub( self, 'NotifyAllSavedZoomsReset', 'reset_all_file_zooms' )
        
    
    def _CheckPlaybackSkips( self ):
        
        if len( self._playback_skips ) == 0 or self._media is None or not self.CurrentlyPresentingMediaWithDuration():
            
            return
            
        
        # an a-b loop is the user focusing on one part of the file, so it wins. this also lets them watch a skip they just added from it
        if self._ab_loop_b_ms is not None:
            
            return
            
        
        animation_bar_status = self._media_window.GetAnimationBarStatus()
        
        if animation_bar_status is None:
            
            return
            
        
        ( current_frame_index, current_timestamp_ms, paused, buffer_indices ) = animation_bar_status
        
        # while paused, the user can scan through a skip to look at it
        if paused or current_timestamp_ms is None:
            
            return
            
        
        for skip in self._playback_skips:
            
            ( start_ms, end_ms ) = skip
            
            if start_ms <= current_timestamp_ms < end_ms:
                
                if self._last_playback_skip_seek is not None:
                    
                    ( last_skip, last_seek_time ) = self._last_playback_skip_seek
                    
                    if last_skip == skip and not HydrusTime.TimeHasPassedFloat( last_seek_time + PLAYBACK_SKIP_SEEK_GRACE_PERIOD_S ):
                        
                        return
                        
                    
                
                self._last_playback_skip_seek = ( skip, HydrusTime.GetNowPrecise() )
                
                self._SeekPastPlaybackSkip( end_ms )
                
                return
                
            
        
    
    def _CheckScriptedEvents( self ):
        
        if len( self._scripted_events ) == 0 or self._media is None or not self.CurrentlyPresentingMediaWithDuration():
            
            return
            
        
        animation_bar_status = self._media_window.GetAnimationBarStatus()
        
        if animation_bar_status is None:
            
            return
            
        
        ( current_frame_index, current_timestamp_ms, paused, buffer_indices ) = animation_bar_status
        
        if current_timestamp_ms is None:
            
            return
            
        
        if paused:
            
            # scanning around while paused does not run anything. playback carries on from wherever it is when it unpauses
            if self._scripted_events_last_timestamp_ms is not None:
                
                self._scripted_events_last_timestamp_ms = current_timestamp_ms
                
            
            return
            
        
        last_timestamp_ms = self._scripted_events_last_timestamp_ms
        
        self._scripted_events_last_timestamp_ms = current_timestamp_ms
        
        for ( timestamp_ms, command ) in ClientMediaScriptedEvents.GetScriptedEventsToRun( self._scripted_events, last_timestamp_ms, current_timestamp_ms, self._media.GetDurationMS() ):
            
            ClientMediaScriptedEvents.RunScriptedEventCommand( command )
            
        
    
    def _CheckZoomTimestamps( self ):
        
        if len( self._zoom_timestamps ) == 0 or self._media is None or not self.CurrentlyPresentingMediaWithDuration() or not self.IsZoomable():
            
            return
            
        
        animation_bar_status = self._media_window.GetAnimationBarStatus()
        
        if animation_bar_status is None:
            
            return
            
        
        ( current_frame_index, current_timestamp_ms, paused, buffer_indices ) = animation_bar_status
        
        if current_timestamp_ms is None:
            
            return
            
        
        was_playing = self._zoom_timestamps_last_check_was_playing
        
        self._zoom_timestamps_last_check_was_playing = not paused
        
        # when media that plays a set number of times finishes, it stops on its last frame. media that loops goes back to the start, which the timestamps handle by themselves
        num_frames = self._media.GetNumFrames()
        
        at_last_frame = num_frames is not None and num_frames > 1 and current_frame_index >= num_frames - 1
        
        if self._zoom_timestamps_stopped_at_end:
            
            if paused and at_last_frame:
                
                return
                
            
            self._zoom_timestamps_stopped_at_end = False
            
        
        if paused and was_playing and at_last_frame:
            
            # the end of playback, so back to the zoom the file started at
            self._zoom_timestamps_stopped_at_end = True
            
            zoom_timestamp = None
            
        else:
            
            zoom_timestamp = GetZoomTimestampAt( self._zoom_timestamps, current_timestamp_ms )
            
            # the file opening counts as playback, even if it opens paused, so a zoom timestamp at the start still happens
            first_check = not self._zoom_timestamps_have_checked
            
            self._zoom_timestamps_have_checked = True
            
            if paused and not first_check:
                
                # we only zoom in normal playback. while paused, e.g. when the user drags the scanbar (which pauses), we just keep up with where we are
                # when playback carries on, the zoom stays as it is until playback gets to the next zoom timestamp
                self._current_zoom_timestamp = zoom_timestamp
                
                # but a resize resets the zoom, so that still puts the one we are in back on. if we are not in one, the resize already did what we would
                if self._current_zoom_timestamp_needs_reapply:
                    
                    if zoom_timestamp is None:
                        
                        self._current_zoom_timestamp_needs_reapply = False
                        
                    else:
                        
                        self._ZoomToZoomTimestamp( zoom_timestamp )
                        
                    
                
                return
                
            
        
        # the zoom the file starts at does not need putting back after a resize, since the resize already did that
        needs_reapply = self._current_zoom_timestamp_needs_reapply and zoom_timestamp is not None
        
        if zoom_timestamp != self._current_zoom_timestamp or needs_reapply:
            
            self._ZoomToZoomTimestamp( zoom_timestamp )
            
        
    
    def _CheckClosingWidgets( self ):
        
        for mpv_widget in list( self._closing_mpv_widgets ):
            
            if mpv_widget.ReadyForDestruction():
                
                mpv_widget.deleteLater()
                
                self._closing_mpv_widgets.remove( mpv_widget )
                
            
        
        for qt_media_player in list( self._closing_qt_media_players ):
            
            qt_media_player.TryToUnload()
            
            if qt_media_player.IsCompletelyUnloaded():
                
                qt_media_player.deleteLater()
                
                self._closing_qt_media_players.remove( qt_media_player )
                
            
        
        if len( self._closing_mpv_widgets ) + len( self._closing_qt_media_players ) == 0:
            
            self.haveDestroyedAllMediaWindows.emit()
            
            self._close_check_timer.stop()
            
        
    
    def _DestroyOrHideThisMediaWindow( self, media_window ):
        
        if media_window is not None:
            
            launch_media_viewer_classes = ( Animation, ClientGUIMPV.MPVWidget, StaticImage, ClientGUIQtMediaPlayer.QtMediaPlayer )
            
            media_window.removeEventFilter( self._additional_event_filter )
            
            if isinstance( media_window, launch_media_viewer_classes ):
                
                try:
                    
                    media_window.launchMediaViewer.disconnect( self.launchMediaViewer )
                    
                except RuntimeError:
                    
                    pass # lmao, weird 'Failed to disconnect signal launchMediaViewer()' error I couldn't figure out, I guess some out-of-order deleteLater gubbins
                    
                
                media_window.ClearMedia()
                
                if isinstance( media_window, StaticImage ):
                    
                    media_window.repaint()
                    
                
                media_window.hide()
                
                if isinstance( media_window, ClientGUIMPV.MPVWidget ):
                    
                    mpv_widget = media_window
                    
                    # our audio effects belong to us, so the next user of this pooled widget should not hear them
                    mpv_widget.SetAudioFilterGraph( '' )
                    
                    if CG.client_controller.new_options.GetBoolean( 'mpv_destruction_test' ):
                        
                        mpv_widget.StartCleanBeforeDestroy()
                        
                        self._closing_mpv_widgets.append( mpv_widget )
                        
                        mpv_widget.readyForDestruction.connect( self._CheckClosingWidgets )
                        
                    else:
                        
                        CG.client_controller.gui.ReleaseMPVWidget( mpv_widget )
                        
                    
                
                if isinstance( media_window, ClientGUIQtMediaPlayer.QtMediaPlayer ):
                    
                    qt_media_player = media_window
                    
                    if True:
                        
                        self._closing_qt_media_players.append( qt_media_player )
                        
                        self._close_check_timer.start( 500 )
                        
                    else:
                        
                        # TODO: Delete this when you are happy with the new media container deletion responsibility
                        CG.client_controller.gui.ReleaseQtMediaPlayer( qt_media_player )
                        
                    
                
            else:
                
                media_window.deleteLater()
                
            
        
    
    def _GetCurrentMuteState( self ):
        
        if self._has_per_player_mute_state:
            
            return self._per_player_mute_state
            
        else:
            
            return ClientGUIMediaVolume.GetCorrectCurrentMute( self._canvas_type )
            
        
    
    def _GetCurrentVolume( self ) -> int:
        
        if self._has_per_player_volume:
            
            return self._per_player_volume
            
        else:
            
            return ClientGUIMediaVolume.GetCorrectCurrentVolume( self._canvas_type )
            
        
    
    def _GetCurrentPlaybackTimestampMS( self ) -> int | None:
        
        if not self.CurrentlyPresentingMediaWithDuration():
            
            return None
            
        
        animation_bar_status = self._media_window.GetAnimationBarStatus()
        
        if animation_bar_status is None:
            
            return None
            
        
        ( current_frame_index, current_timestamp_ms, paused, buffer_indices ) = animation_bar_status
        
        if current_timestamp_ms is None:
            
            return None
            
        
        return int( current_timestamp_ms )
        
    
    def _GetCurrentFrameStartAndDurationMS( self ) -> tuple[ float, float ] | None:
        
        # the frame on screen, so A-B loops and zoom timestamps land on frames, not somewhere between them
        if not self.CurrentlyPresentingMediaWithDuration():
            
            return None
            
        
        if isinstance( self._media_window, Animation ):
            
            return self._media_window.GetCurrentFrameStartAndDurationMS()
            
        
        animation_bar_status = self._media_window.GetAnimationBarStatus()
        
        if animation_bar_status is None:
            
            return None
            
        
        ( current_frame_index, current_timestamp_ms, paused, buffer_indices ) = animation_bar_status
        
        if current_timestamp_ms is None:
            
            return None
            
        
        # mpv and Qt do not tell us how long each frame is, so we go with the average. audio has no frames at all
        num_frames = self._media.GetNumFrames()
        duration_ms = self._media.GetDurationMS()
        
        if num_frames is None or num_frames < 2 or duration_ms is None or duration_ms <= 0:
            
            frame_duration_ms = 0.0
            
        else:
            
            frame_duration_ms = duration_ms / num_frames
            
        
        if isinstance( self._media_window, ClientGUIQtMediaPlayer.QtMediaPlayer ) and frame_duration_ms > 0:
            
            # Qt's time runs smoothly through each frame, so we go back to the start of the one we are in
            frame_start_ms = math.floor( round( current_timestamp_ms / frame_duration_ms, 6 ) ) * frame_duration_ms
            
        else:
            
            # mpv's time is the start of the frame it is on
            frame_start_ms = current_timestamp_ms
            
        
        return ( frame_start_ms, frame_duration_ms )
        
    
    def _GetDefaultZoomType( self ):
        
        if self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES:
            
            return CG.client_controller.new_options.GetInteger( 'media_viewer_default_zoom_type_override' )
            
        else:
            
            return CG.client_controller.new_options.GetInteger( 'preview_default_zoom_type_override' )
            
        
    
    def _GetFineZoomLimits( self ):
        
        possible_zooms = CG.client_controller.new_options.GetMediaZooms()
        
        possible_zooms.append( self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ] )
        
        return ( min( possible_zooms ), max( possible_zooms ) )
        
    
    def _GetMaxZoomDimension( self ):
        
        if self._show_action in ( CC.MEDIA_VIEWER_ACTION_SHOW_WITH_MPV, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_QTMEDIAPLAYER ) or isinstance( self._media_window, Animation ):
            
            return 8000
            
        else:
            
            return 32000
            
        
    
    def _GetZoomWithinMaxDimension( self, zoom: float ) -> float:
        
        my_dpr = self.devicePixelRatio()
        
        media_window_size = CalculateMediaContainerSize( self._media, my_dpr, zoom, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE, rotation = self._rotation )
        
        max_zoom_dimension = self._GetMaxZoomDimension()
        
        if media_window_size.width() > max_zoom_dimension or media_window_size.height() > max_zoom_dimension:
            
            limit_max_zoom_types_to_zooms = CalculateCanvasZooms( QC.QSize( max_zoom_dimension, max_zoom_dimension ), self._canvas_type, my_dpr, self._media, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE, rotation = self._rotation )
            
            zoom = limit_max_zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]
            
        
        return zoom
        
    
    def _LoadPlaybackSkips( self ):
        
        self._playback_skips_load_id += 1
        
        load_id = self._playback_skips_load_id
        
        self._SetPlaybackSkips( [] )
        
        if self._media is None or not MediaHasPlayback( self._media ):
            
            return
            
        
        hash = self._media.GetHash()
        
        def work_callable():
            
            return CG.client_controller.Read( 'file_playback_skips', hash )
            
        
        def publish_callable( skips ):
            
            # the media changed, or the skips were edited, while we were waiting
            if load_id != self._playback_skips_load_id:
                
                return
                
            
            self._SetPlaybackSkips( skips )
            
        
        job = ClientGUIAsync.AsyncQtJob( self, work_callable, publish_callable )
        
        job.start()
        
    
    def _ApplyZoomDataFromStandby( self ):
        
        # the new file's zoom is set up now, so what we looked up ahead of time can go on, before it is shown
        if self._saved_zoom_from_standby is not None:
            
            ( load_id, saved_zoom ) = self._saved_zoom_from_standby
            
            self._saved_zoom_from_standby = None
            
            if load_id == self._saved_zoom_load_id:
                
                self._SetLoadedSavedZoom( saved_zoom )
                
            
        
        if self._zoom_timestamp_rows_from_standby is not None:
            
            ( load_id, zoom_timestamp_rows ) = self._zoom_timestamp_rows_from_standby
            
            self._zoom_timestamp_rows_from_standby = None
            
            if load_id == self._zoom_timestamps_load_id:
                
                self._SetLoadedZoomTimestampRows( zoom_timestamp_rows )
                
            
        
    
    def _ClearStandbyZoomData( self ):
        
        # anything still on its way is out of date
        self._standby_zoom_data_load_id += 1
        
        self._standby_zoom_data = None
        self._standby_zoom_data_hash = None
        
    
    def _GetStandbyZoomData( self, hash: bytes ) -> tuple[ float | None, list ] | None:
        
        if self._standby_zoom_data is None:
            
            return None
            
        
        ( standby_hash, saved_zoom, zoom_timestamp_rows ) = self._standby_zoom_data
        
        if standby_hash != hash:
            
            return None
            
        
        return ( saved_zoom, zoom_timestamp_rows )
        
    
    def _LoadStandbyZoomData( self, media: ClientMediaSingle.MediaSingle ):
        
        hash = media.GetHash()
        
        # we have them, or they are on their way
        if self._standby_zoom_data_hash == hash:
            
            return
            
        
        self._standby_zoom_data_load_id += 1
        
        load_id = self._standby_zoom_data_load_id
        
        self._standby_zoom_data = None
        self._standby_zoom_data_hash = hash
        
        remembers_file_zooms = self._remembers_file_zooms
        does_zoom_timestamps = self._does_zoom_timestamps and MediaHasPlayback( media )
        
        def work_callable():
            
            saved_zoom = CG.client_controller.Read( 'file_viewer_zoom', hash ) if remembers_file_zooms else None
            zoom_timestamp_rows = CG.client_controller.Read( 'file_zoom_timestamps', hash ) if does_zoom_timestamps else []
            
            return ( saved_zoom, zoom_timestamp_rows )
            
        
        def publish_callable( result ):
            
            # we moved on to something else while we were waiting
            if load_id != self._standby_zoom_data_load_id:
                
                return
                
            
            ( saved_zoom, zoom_timestamp_rows ) = result
            
            self._standby_zoom_data = ( hash, saved_zoom, zoom_timestamp_rows )
            
        
        job = ClientGUIAsync.AsyncQtJob( self, work_callable, publish_callable )
        
        job.start()
        
    
    def _PopNextMediaStartMS( self ) -> int | None:
        
        if self._next_media_start is None:
            
            return None
            
        
        ( media, start_ms ) = self._next_media_start
        
        self._next_media_start = None
        
        if media != self._media:
            
            return None
            
        
        return start_ms
        
    
    def _ReleaseStandbyMPVWidget( self ):
        
        if self._standby_mpv_widget is None:
            
            return
            
        
        mpv_widget = self._standby_mpv_widget
        
        self._standby_mpv_widget = None
        self._standby_media = None
        self._standby_start_ms = None
        
        # like any mpv window we are done with, it goes back in the pool, with nothing loaded
        mpv_widget.ClearMedia()
        
        mpv_widget.hide()
        
        mpv_widget.SetAudioFilterGraph( '' )
        
        if CG.client_controller.new_options.GetBoolean( 'mpv_destruction_test' ):
            
            mpv_widget.StartCleanBeforeDestroy()
            
            self._closing_mpv_widgets.append( mpv_widget )
            
            mpv_widget.readyForDestruction.connect( self._CheckClosingWidgets )
            
        else:
            
            CG.client_controller.gui.ReleaseMPVWidget( mpv_widget )
            
        
    
    def _SetLoadedSavedZoom( self, zoom: float | None ):
        
        self._saved_zoom = zoom
        
        if self._saved_zoom is not None and self.IsZoomable() and not self._holding_default_zoom:
            
            self._SetZoom( self._GetZoomWithinMaxDimension( self._saved_zoom ) )
            
            self.ResetCenterPosition()
            
            # a zoom timestamp we are already in wins over this
            self._current_zoom_timestamp_needs_reapply = True
            
        
    
    def _SetLoadedZoomTimestampRows( self, rows ):
        
        canvas_zoom = self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]
        
        if self.IsZoomable() and canvas_zoom > 0:
            
            ( zoom_timestamps, converted_some ) = ConvertZoomTimestampRowsToRelative( rows, canvas_zoom )
            
            if converted_some:
                
                # old ones become relative once, for good
                self._SaveZoomTimestamps( zoom_timestamps )
                
                return
                
            
        else:
            
            # we cannot work out what old ones should be yet, so we leave them in the db for next time
            zoom_timestamps = [ ( timestamp_ms, zoom, center_x, center_y ) for ( timestamp_ms, zoom, zoom_is_relative, center_x, center_y ) in rows if zoom_is_relative ]
            
        
        self._SetZoomTimestamps( zoom_timestamps )
        
    
    def _TakeStandbyMPVWidget( self, media: ClientMediaSingle.MediaSingle, start_ms: int | None ) -> ClientGUIMPV.MPVWidget | None:
        
        # the standby player, if it has this file waiting at this start. if it has something else, that is no good to us now
        if self._standby_mpv_widget is None:
            
            return None
            
        
        if self._standby_media == media and ( self._standby_start_ms or 0 ) == ( start_ms or 0 ):
            
            mpv_widget = self._standby_mpv_widget
            
            self._standby_mpv_widget = None
            self._standby_media = None
            self._standby_start_ms = None
            
            return mpv_widget
            
        
        self._ReleaseStandbyMPVWidget()
        
        return None
        
    
    def _ApplyRotationToMediaWindow( self ):
        
        if isinstance( self._media_window, ( StaticImage, Animation, ClientGUIMPV.MPVWidget, ClientGUIQtMediaPlayer.QtMediaPlayer ) ):
            
            self._media_window.SetRotation( self._rotation )
            
        
    
    def _GetMediaResolution( self ) -> tuple[ float, float ]:
        
        # the file's resolution as it is shown, so on its side if it is turned
        resolution = self._media.GetResolution()
        
        if self._rotation == 0 or None in resolution:
            
            return resolution
            
        
        return GetRotatedBoundingSize( resolution[0], resolution[1], self._rotation )
        
    
    def _LoadRotation( self ):
        
        self._rotation_load_id += 1
        
        load_id = self._rotation_load_id
        
        self._rotation = 0
        
        self._ApplyRotationToMediaWindow()
        
        if not self.CanRotate():
            
            return
            
        
        hash = self._media.GetHash()
        
        def work_callable():
            
            return CG.client_controller.Read( 'file_viewer_rotation', hash )
            
        
        def publish_callable( rotation ):
            
            # the media changed, or the user turned it, while we were waiting
            if load_id != self._rotation_load_id:
                
                return
                
            
            if rotation != 0:
                
                self._SetRotation( rotation )
                
            
        
        job = ClientGUIAsync.AsyncQtJob( self, work_callable, publish_callable )
        
        job.start()
        
    
    def _SetRotation( self, rotation: float ):
        
        self._rotation = NormaliseRotation( rotation )
        
        self._ApplyRotationToMediaWindow()
        
        # it is a different shape now, so it fits the window differently
        self.ZoomReinit()
        
        self.ResetCenterPosition()
        
        self.update()
        
    
    def _LoadSavedZoom( self ):
        
        self._saved_zoom_load_id += 1
        
        load_id = self._saved_zoom_load_id
        
        self._saved_zoom = None
        self._saved_zoom_from_standby = None
        
        self._holding_default_zoom = False
        
        if self._media is None or not self._remembers_file_zooms:
            
            return
            
        
        hash = self._media.GetHash()
        
        standby_zoom_data = self._GetStandbyZoomData( hash )
        
        if standby_zoom_data is not None:
            
            # we looked it up ahead of time, so it goes on as soon as the new file's zoom is set up, before it is shown
            ( saved_zoom, zoom_timestamp_rows ) = standby_zoom_data
            
            self._saved_zoom_from_standby = ( load_id, saved_zoom )
            
            return
            
        
        def work_callable():
            
            return CG.client_controller.Read( 'file_viewer_zoom', hash )
            
        
        def publish_callable( zoom ):
            
            # the media changed, or the user zoomed, while we were waiting
            if load_id != self._saved_zoom_load_id:
                
                return
                
            
            self._SetLoadedSavedZoom( zoom )
            
        
        job = ClientGUIAsync.AsyncQtJob( self, work_callable, publish_callable )
        
        job.start()
        
    
    def _LoadScriptedEvents( self ):
        
        self._scripted_events_load_id += 1
        
        load_id = self._scripted_events_load_id
        
        self._SetScriptedEvents( [] )
        
        self._scripted_events_last_timestamp_ms = None
        
        if self._media is None or not self._does_scripted_events or not MediaHasPlayback( self._media ):
            
            return
            
        
        hash = self._media.GetHash()
        
        def work_callable():
            
            return CG.client_controller.Read( 'file_scripted_events', hash )
            
        
        def publish_callable( scripted_events ):
            
            # the media changed, or the scripted events were edited, while we were waiting
            if load_id != self._scripted_events_load_id:
                
                return
                
            
            self._SetScriptedEvents( scripted_events )
            
        
        job = ClientGUIAsync.AsyncQtJob( self, work_callable, publish_callable )
        
        job.start()
        
    
    def _LoadZoomTimestamps( self ):
        
        self._zoom_timestamps_load_id += 1
        
        load_id = self._zoom_timestamps_load_id
        
        self._SetZoomTimestamps( [] )
        
        self._current_zoom_timestamp = None
        self._current_zoom_timestamp_needs_reapply = False
        self._zoom_timestamps_last_check_was_playing = False
        self._zoom_timestamps_stopped_at_end = False
        self._zoom_timestamps_have_checked = False
        self._zoom_timestamp_rows_from_standby = None
        
        if self._media is None or not self._does_zoom_timestamps or not MediaHasPlayback( self._media ):
            
            return
            
        
        hash = self._media.GetHash()
        
        standby_zoom_data = self._GetStandbyZoomData( hash )
        
        if standby_zoom_data is not None:
            
            # we looked them up ahead of time. they go on once the new file's zoom is set up, since old ones are converted using it
            ( saved_zoom, zoom_timestamp_rows ) = standby_zoom_data
            
            self._zoom_timestamp_rows_from_standby = ( load_id, zoom_timestamp_rows )
            
            return
            
        
        def work_callable():
            
            return CG.client_controller.Read( 'file_zoom_timestamps', hash )
            
        
        def publish_callable( rows ):
            
            # the media changed, or the zoom timestamps were edited, while we were waiting
            if load_id != self._zoom_timestamps_load_id:
                
                return
                
            
            self._SetLoadedZoomTimestampRows( rows )
            
        
        job = ClientGUIAsync.AsyncQtJob( self, work_callable, publish_callable )
        
        job.start()
        
    
    def _MakeMediaWindow( self ):
        
        old_media_window = self._media_window
        
        do_neighbour_prefetch_emit = True
        
        if self._show_action == CC.MEDIA_VIEWER_ACTION_SHOW_WITH_MPV and not ClientGUIMPV.MPV_IS_AVAILABLE:
            
            self._show_action = CC.MEDIA_VIEWER_ACTION_SHOW_OPEN_EXTERNALLY_BUTTON
            
            HydrusData.ShowText( 'MPV is not available!' )
            
        elif self._show_action == CC.MEDIA_VIEWER_ACTION_SHOW_WITH_QTMEDIAPLAYER and not ClientGUIQtMediaPlayer.QT_MULTIMEDIA_IS_AVAILABLE:
            
            self._show_action = CC.MEDIA_VIEWER_ACTION_SHOW_OPEN_EXTERNALLY_BUTTON
            
            HydrusData.ShowText( 'QtMediaPlayer is not available!' )
            
        
        if self._show_action in ( CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW_ON_ACTIVATION_OPEN_EXTERNALLY, CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW ):
            
            raise Exception( 'This media should not be shown in the media viewer!' )
            
        elif self._show_action == CC.MEDIA_VIEWER_ACTION_SHOW_OPEN_EXTERNALLY_BUTTON:
            
            self._media_window = OpenExternallyPanel( self, self._media )
            
        elif self._show_action == CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE:
            
            if self._media.IsStaticImage():
                
                if None in self._media.GetResolution():
                    
                    raise Exception( 'This media has no resolution!' )
                    
                
                if isinstance( self._media_window, StaticImage ):
                    
                    self._media_window.hide()
                    
                else:
                    
                    self._media_window = self._static_image_window
                    
                
                self._media_window.SetMedia( self._media )
                
                do_neighbour_prefetch_emit = False
                
            else:
                
                if isinstance( self._media_window, Animation ):
                    
                    self._media_window.hide()
                    
                else:
                    
                    self._media_window = self._animation_window
                    
                
                self._media_window.SetMedia( self._media, start_paused = self._start_paused )
                
                self._media_window.lower()
                
            
        else:
            
            # ok we are making a clever media player
            
            start_ms = self._PopNextMediaStartMS()
            
            came_from_standby = False
            
            if self._show_action == CC.MEDIA_VIEWER_ACTION_SHOW_WITH_MPV:
                
                standby_mpv_widget = self._TakeStandbyMPVWidget( self._media, start_ms )
                
                if standby_mpv_widget is not None:
                    
                    # this file is already loaded and sitting at its start, so there is nothing to wait for
                    self._media_window = standby_mpv_widget
                    
                    self._media_window.SetMute( self._GetCurrentMuteState() )
                    self._media_window.SetVolume( self._GetCurrentVolume() )
                    self._media_window.SetAudioFilterGraph( self._audio_effects.GetFilterGraph() )
                    
                    came_from_standby = True
                    
                elif not CG.client_controller.new_options.GetBoolean( 'persist_media_window_mpv' ) or not isinstance( old_media_window, ClientGUIMPV.MPVWidget ):
                    
                    self._media_window = CG.client_controller.gui.GetMPVWidget( self )
                    
                    self._media_window.amInitialised.connect( self._NotifyMPVInitialised )
                    
                    self._media_window.SetCanvasType( self._canvas_type )
                    
                    self._media_window.SetMute( self._GetCurrentMuteState() )
                    self._media_window.SetVolume( self._GetCurrentVolume() )
                    self._media_window.SetAudioFilterGraph( self._audio_effects.GetFilterGraph() )
                    
                    self._media_window.SetMedia( self._media, start_paused = self._start_paused, start_ms = start_ms )
                    
                
            elif self._show_action == CC.MEDIA_VIEWER_ACTION_SHOW_WITH_QTMEDIAPLAYER:
                
                if not CG.client_controller.new_options.GetBoolean( 'persist_media_window_qt_media_player' ) or not isinstance( old_media_window, ClientGUIQtMediaPlayer.QtMediaPlayer ):
                    
                    self._media_window = ClientGUIQtMediaPlayer.QtMediaPlayer( self, self._canvas_type, self.parentWidget(), self._background_colour_generator )
                    
                    self._media_window.SetMute( self._GetCurrentMuteState() )
                    self._media_window.SetVolume( self._GetCurrentVolume() )
                    
                    self._media_window.InstallMouseMoveCatcher( self._qt_media_player_graphics_view_mouse_move_catcher )
                    
                
            
            if isinstance( self._media_window, ClientGUIMPV.MPVWidget ):
                
                # a standby player already has this file, so this does nothing
                self._media_window.SetMedia( self._media, start_paused = self._start_paused, start_ms = start_ms )
                
            else:
                
                self._media_window.SetMedia( self._media, start_paused = self._start_paused )
                
            
            if came_from_standby and not self._start_paused:
                
                self._media_window.Play()
                
            
            self._media_window.lower()
            
        
        if ShouldHaveAnimationBar( self._media, self._show_action ):
            
            self._animation_bar.SetMediaAndWindow( self._media, self._media_window )
            
        else:
            
            self._animation_bar.ClearMedia()
            
        
        self._ShowHideControlBar()
        
        media_window_changed = old_media_window != self._media_window
        
        # this has to go after setcanvastype on the mpv window so the filters are in the correct order
        if media_window_changed:
            
            self._media_window.installEventFilter( self._additional_event_filter )
            
            launch_media_viewer_classes = ( Animation, ClientGUIMPV.MPVWidget, StaticImage, ClientGUIQtMediaPlayer.QtMediaPlayer )
            
            if isinstance( self._media_window, launch_media_viewer_classes ):
                
                self._media_window.launchMediaViewer.connect( self.launchMediaViewer )
                
            
            self._DestroyOrHideThisMediaWindow( old_media_window )
            
            # this forces a flush of the last valid background bmp, so we don't get a flicker of a file from five files ago when we last saw a static image
            self.repaint()
            
        
        if do_neighbour_prefetch_emit:
            
            self.readyForNeighbourPrefetch.emit()
            
        
    
    def _MoveDelta( self, delta: QC.QPoint ):
        
        if delta.isNull():
            
            return
            
        
        self.move( self.pos() + delta )
        
    
    def _MoveToZoomCenter( self, center: tuple[ float, float ] ):
        
        canvas_size = self.parentWidget().size()
        my_size = self.sizeHint()
        
        ( x, y ) = GetMediaPosForZoomCenter( ( canvas_size.width(), canvas_size.height() ), ( my_size.width(), my_size.height() ), center )
        
        ideal_pos = QC.QPoint( x, y )
        
        if ideal_pos != self.pos():
            
            self.move( ideal_pos )
            
        
        # a window of a very different shape could leave the file off the side
        self.RescueIfOffScreen()
        
    
    def _NotifyMPVInitialised( self ):
        
        if self._deferred_set_media_call is not None:
            
            if self.isVisible():
                
                self._deferred_set_media_call()
                
            
            self._deferred_set_media_call = None
            
        
    
    def _SetABLoop( self, a_ms: int | None, b_ms: int | None ):
        
        self._ab_loop_a_ms = a_ms
        self._ab_loop_b_ms = b_ms
        
        if self.CurrentlyPresentingMediaWithDuration():
            
            self._media_window.SetABLoop( a_ms, b_ms )
            
        
        self.abLoopChanged.emit( a_ms, b_ms )
        
    
    def _SavePlaybackSkips( self, skips: list[ tuple[ int, int ] ] ):
        
        if self._media is None:
            
            return
            
        
        hash = self._media.GetHash()
        
        # anything we are still loading is now out of date
        self._playback_skips_load_id += 1
        
        self._SetPlaybackSkips( skips )
        
        CG.client_controller.Write( 'file_playback_skips', hash, skips )
        
        # other viewers, like the preview, may be showing this file too
        CG.client_controller.pub( 'new_file_playback_skips', hash, skips )
        
    
    def _SaveZoom( self ):
        
        if self._media is None or not self._remembers_file_zooms:
            
            return
            
        
        # zooming back to where the file would start anyway means it does not need its own any more
        default_zoom = self._zoom_types_to_zooms[ self._GetDefaultZoomType() ]
        
        if self._current_zoom == default_zoom:
            
            zoom = None
            
        else:
            
            zoom = self._current_zoom
            
        
        # anything we are still loading is now out of date
        self._saved_zoom_load_id += 1
        
        self._saved_zoom = zoom
        
        self._holding_default_zoom = False
        
        CG.client_controller.Write( 'file_viewer_zoom', self._media.GetHash(), zoom )
        
    
    def _SaveZoomTimestamps( self, zoom_timestamps: list[ ZoomTimestamp ] ):
        
        if self._media is None:
            
            return
            
        
        hash = self._media.GetHash()
        
        # anything we are still loading is now out of date
        self._zoom_timestamps_load_id += 1
        
        self._SetZoomTimestamps( zoom_timestamps )
        
        CG.client_controller.Write( 'file_zoom_timestamps', hash, self._zoom_timestamps )
        
        # other media viewers may be showing this file too
        CG.client_controller.pub( 'new_file_zoom_timestamps', hash, self._zoom_timestamps )
        
    
    def _SeekPastPlaybackSkip( self, end_ms: int ):
        
        if isinstance( self._media_window, Animation ):
            
            self._media_window.SeekPastPlaybackSkip( end_ms )
            
        elif isinstance( self._media_window, ( ClientGUIMPV.MPVWidget, ClientGUIQtMediaPlayer.QtMediaPlayer ) ):
            
            duration_ms = self._media.GetDurationMS()
            
            # a skip that runs off the end goes back to the start. the players count that as a playthrough, so slideshows and 'play x times' still work
            if duration_ms is not None and end_ms >= duration_ms:
                
                end_ms = 0
                
            
            self._media_window.Seek( end_ms )
            
        
    
    def _SetPlaybackSkips( self, skips: list[ tuple[ int, int ] ] ):
        
        self._playback_skips = [ tuple( skip ) for skip in skips ]
        self._last_playback_skip_seek = None
        
        self._UpdateAnimationUpdateRegistration()
        
    
    def _SetScriptedEvents( self, scripted_events: list[ ClientMediaScriptedEvents.ScriptedEvent ] ):
        
        self._scripted_events = sorted( tuple( scripted_event ) for scripted_event in scripted_events )
        
        self._UpdateAnimationUpdateRegistration()
        
    
    def _SetZoomTimestamps( self, zoom_timestamps: list[ ZoomTimestamp ] ):
        
        self._zoom_timestamps = sorted( ( tuple( zoom_timestamp ) for zoom_timestamp in zoom_timestamps ), key = lambda zoom_timestamp: zoom_timestamp[0] )
        
        self._UpdateAnimationUpdateRegistration()
        
    
    def _SetZoom( self, zoom: float, move_delta = None ):
        
        self._current_zoom = zoom
        
        size_hint = self.sizeHint()
        
        if self.size() != size_hint:
            
            if move_delta is not None and not move_delta.isNull():
                
                if isinstance( self._media_window, ClientGUIMPV.MPVWidget ) and CG.client_controller.new_options.GetBoolean( 'do_not_setgeometry_on_an_mpv' ):
                    
                    self._MoveDelta( move_delta )
                    self.resize( size_hint )
                    
                else:
                    
                    self.setGeometry( QC.QRect( self.pos() + move_delta, size_hint ) )
                    
                
            else:
                
                self.resize( size_hint )
                
            
            self._SizeAndPositionChildren()
            
            if HC.PLATFORM_MACOS:
                
                self.update()
                
            
        else:
            
            if move_delta is not None:
                
                self._MoveDelta( move_delta )
                
            
        
        self.zoomChanged.emit( self._current_zoom_type, self._current_zoom )
        
    
    def _ShowHideControlBar( self ):
        
        is_near = False
        show_small_instead_of_hiding = None
        force_show = False
        
        if not ShouldHaveAnimationBar( self._media, self._show_action ):
            
            should_show_controls = False
            
        else:
            
            is_near = self.MouseIsNearAnimationBar()
            
            if CG.client_controller.new_options.GetBoolean( 'animated_scanbar_pop_in_requires_focus' ):
                
                current_focus_tlw = QW.QApplication.activeWindow()
                
                if current_focus_tlw != self.window():
                    
                    is_near = False
                    
                
            
            show_small_instead_of_hiding = CG.client_controller.new_options.GetNoneableInteger( 'animated_scanbar_hide_height' ) is not None
            force_show = self._volume_control.PopupIsVisible() or self._animation_bar.DoingADrag() or CG.client_controller.new_options.GetBoolean( 'force_animation_scanbar_show' )
            
            should_show_controls = is_near or show_small_instead_of_hiding or force_show
            
        
        if should_show_controls:
            
            should_show_full = is_near or force_show
            
            if should_show_full != self._controls_bar_show_full:
                
                self._controls_bar_show_full = should_show_full
                
                self._animation_bar.SetShowText( self._controls_bar_show_full )
                
                self._volume_control.setEnabled( self._controls_bar_show_full )
                
                self._SizeAndPositionChildren()
                
                # TODO: investigate this
                # ok we do seem to have a flicker here, most obvious when going from small to full size on a quick animation. we get a frame of where the top half was before. some bitmap memory issue I guess
                # a forced repaint of the animation bar here does not fix it, so I suspect this is related to the disconnected layout nonsense I am doing
                # TODO: if and when fixed, investigate if setGubbinsVisible is still a useful thing
                
            
            do_layout = False
            
            if self._controls_bar.isHidden():
                
                self._controls_bar.setVisible( True )
                self._controls_bar.raise_()
                
                self._animation_bar.setGubbinsVisible( True )
                self._animation_bar.repaint() # this is probably not needed
                
                do_layout = True
                
            
            should_show_volume = self.ShouldHaveVolumeControl()
            
            volume_currently_visible = not self._volume_control.isHidden()
            
            if volume_currently_visible != should_show_volume:
                
                self._volume_control.setVisible( should_show_volume )
                
                do_layout = True
                
            
            self._controls_bar.layout()
            
        else:
            
            if not self._controls_bar.isHidden():
                
                # ok, repaint here forces a clear paint event NOW, before we hide.
                # this ensures that when we show again, we won't have the nub in the wrong place for a frame before it repaints
                # we'll have no nub, but this is less noticeable
                
                self._animation_bar.setGubbinsVisible( False )
                self._animation_bar.repaint() # this is probably not needed
                
                self._controls_bar.setVisible( False )
                
                self._volume_control.setVisible( False )
                
                self._controls_bar.layout() # this is probably not needed
                
            
        
    
    def _SizeAndPositionChildren( self ):
        
        if self._media is not None:
            
            self._embed_button.setFixedSize( self.size() )
            self._embed_button.move( QC.QPoint( 0, 0 ) )
            
            if self._media_window is not None:
                
                self._media_window.setFixedSize( self.size() )
                self._media_window.move( QC.QPoint( 0, 0 ) )
                
            
            controls_bar_rect = self.GetIdealControlsBarRect( full_size = self._controls_bar_show_full )
            
            if controls_bar_rect.size() != self._controls_bar.size():
                
                self._controls_bar.setFixedSize( controls_bar_rect.size() )
                
            
            self._controls_bar.move( controls_bar_rect.topLeft() )
            
        
    
    def _TryToChangeZoom( self, new_zoom, zoom_center_type_override = None ):
        
        if not self.IsZoomable():
            
            return
            
        
        my_size = self.size()
        
        my_width = my_size.width()
        my_height = my_size.height()
        
        my_dpr = self.devicePixelRatio()
        
        new_media_window_size = CalculateMediaContainerSize( self._media, my_dpr, new_zoom, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE, rotation = self._rotation )
        
        new_my_width = new_media_window_size.width()
        new_my_height = new_media_window_size.height()
        
        max_zoom_dimension = self._GetMaxZoomDimension()
        
        if new_my_width > max_zoom_dimension or new_my_height > max_zoom_dimension:
            
            limit_max_zoom_types_to_zooms = CalculateCanvasZooms( QC.QSize( max_zoom_dimension, max_zoom_dimension ), self._canvas_type, my_dpr, self._media, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE, rotation = self._rotation )
            
            new_zoom = limit_max_zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]
            
            new_media_window_size = CalculateMediaContainerSize( self._media, my_dpr, new_zoom, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE, rotation = self._rotation )
            
            new_my_width = new_media_window_size.width()
            new_my_height = new_media_window_size.height()
            
        
        if new_zoom == self._current_zoom:
            
            # to handle a change in zoom type but no zoom
            self.zoomChanged.emit( self._current_zoom_type, self._current_zoom )
            
            return
            
        
        canvas_size = self.parentWidget().size()
        
        old_size_bigger = canvas_size.width() < my_width or canvas_size.height() < my_height
        new_size_fits = canvas_size.width() >= new_my_width and canvas_size.height() >= new_my_height
        
        #
        
        zoom_position_delta = QC.QPoint( 0, 0 )
        
        if my_width > 0 and my_height > 0:
            
            if zoom_center_type_override is None:
                
                zoom_center_type = CG.client_controller.new_options.GetInteger( 'media_viewer_zoom_center' )
                
            else:
                
                zoom_center_type = zoom_center_type_override
                
            
            my_pos = self.pos()
            
            # viewer center is the default
            zoom_centerpoint = QC.QPoint( canvas_size.width() // 2, canvas_size.height() // 2 )
            
            if zoom_center_type == ZOOM_CENTERPOINT_MEDIA_CENTER:
                
                zoom_centerpoint = my_pos + QC.QPoint( my_width // 2, my_height // 2 )
                
            elif zoom_center_type == ZOOM_CENTERPOINT_MEDIA_TOP_LEFT:
                
                zoom_centerpoint = my_pos
                
            elif zoom_center_type == ZOOM_CENTERPOINT_MOUSE:
                
                mouse_pos = self.parentWidget().mapFromGlobal( ClientGUIFunctions.GetMousePos() )
                
                if self.parent().rect().contains( mouse_pos ):
                    
                    zoom_centerpoint = mouse_pos
                    
                
            
            # probably a simpler way to calc this, but hey
            widths_centerpoint_is_from_pos = ( zoom_centerpoint.x() - my_pos.x() ) / my_width
            heights_centerpoint_is_from_pos = ( zoom_centerpoint.y() - my_pos.y() ) / my_height
            
            zoom_width_delta = my_width - new_my_width
            zoom_height_delta = my_height - new_my_height
            
            ( remainder_x, remainder_y ) = self._zoom_position_delta_remainder
            
            float_zoom_position_delta_x = ( zoom_width_delta * widths_centerpoint_is_from_pos ) + remainder_x
            float_zoom_position_delta_y = ( zoom_height_delta * heights_centerpoint_is_from_pos ) + remainder_y
            
            zoom_position_delta = QC.QPoint( round( float_zoom_position_delta_x ), round( float_zoom_position_delta_y ) )
            
            # when zooming one pixel at a time, the ideal move is always a fraction of a pixel, so we carry that over or the media drifts away from the centerpoint
            self._zoom_position_delta_remainder = ( float_zoom_position_delta_x - zoom_position_delta.x(), float_zoom_position_delta_y - zoom_position_delta.y() )
            
        
        #
        
        # ok we had a crazy problem where after showing and hiding an mpv window, some rendering flag gets set which caused move/resize calls to be repainted immediately after call, causing move/resize flicker
        # so now we set the geometry in one weird trick, and it seems Qt at the C++ level wraps it into the same update with that mystery flag on
        self._SetZoom( new_zoom, move_delta = zoom_position_delta )
        
        self.RescueIfOffScreen()
        
        # everything that comes through here is the user zooming
        self._SaveZoom()
        
        # due to the foolish 'giganto window' system for large zooms, some auto-update stuff doesn't work right if the convas rect is contained by the media rect, so do a refresh here
        if new_zoom > self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]:
            
            self.update()
            
        
    
    def _ZoomToZoomTimestamp( self, zoom_timestamp: ZoomTimestamp | None ):
        
        if zoom_timestamp is None:
            
            # the zoom the file starts at, centered
            self.ZoomReinit()
            
            self.ResetCenterPosition()
            
        else:
            
            ( timestamp_ms, relative_zoom, center_x, center_y ) = zoom_timestamp
            
            # relative to the zoom that fits the file in the window, so a smaller window gets a smaller zoom. a resize puts it back on, at the new size
            zoom = relative_zoom * self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]
            
            self._SetZoom( self._GetZoomWithinMaxDimension( zoom ) )
            
            if center_x is None or center_y is None:
                
                # from before we saved the pan
                self.ResetCenterPosition()
                
            else:
                
                # the same part of the file in the middle of the window, whatever its size
                self._MoveToZoomCenter( ( center_x, center_y ) )
                
            
        
        self.update()
        
        # after ZoomReinit, which asks for a reapply
        self._current_zoom_timestamp = zoom_timestamp
        self._current_zoom_timestamp_needs_reapply = False
        
    
    def _UpdateAnimationUpdateRegistration( self ):
        
        # we only need to watch playback when there is something to skip, zoom, or run
        if len( self._playback_skips ) > 0 or len( self._zoom_timestamps ) > 0 or len( self._scripted_events ) > 0:
            
            CG.client_controller.gui.RegisterAnimationUpdateWindow( self )
            
        else:
            
            CG.client_controller.gui.UnregisterAnimationUpdateWindow( self )
            
        
    
    def _UpdateMediaWindowAudioEffects( self ):
        
        # only mpv can do audio effects
        if isinstance( self._media_window, ClientGUIMPV.MPVWidget ):
            
            self._media_window.SetAudioFilterGraph( self._audio_effects.GetFilterGraph() )
            
        
    
    def _UpdateMediaWindowMute( self ):
        
        muteable_window_classes = ( ClientGUIMPV.MPVWidget, ClientGUIQtMediaPlayer.QtMediaPlayer )
        
        if isinstance( self._media_window, muteable_window_classes ):
            
            mute_state_to_set = self._GetCurrentMuteState()
            
            self._media_window.SetMute( mute_state_to_set )
            
        
    
    def _UpdateMediaWindowVolume( self ):
        
        audio_window_classes = ( ClientGUIMPV.MPVWidget, ClientGUIQtMediaPlayer.QtMediaPlayer )
        
        if isinstance( self._media_window, audio_window_classes ):
            
            self._media_window.SetVolume( self._GetCurrentVolume() )
            
        
    
    def _UpdateWindowAlwaysOnTop( self, wait_for_double_click = False ):
        
        if not self._tie_media_window_to_pauseplay_state:
            
            self._window_always_on_top_update_timer.stop()
            
            return
            
        
        always_on_top = self.CurrentlyPresentingMediaWithDuration() and not self._media_window.IsPaused()
        
        if always_on_top == self._canvas.IsAlwaysOnTop():
            
            self._window_always_on_top_update_timer.stop()
            
            return
            
        
        if wait_for_double_click:
            
            if not self._window_always_on_top_update_timer.isActive():
                
                double_click_interval = QW.QApplication.instance().doubleClickInterval()
                
                self._window_always_on_top_update_timer.start( double_click_interval )
                
            
            return
            
        
        self._window_always_on_top_update_timer.stop()
        
        action = CAC.SIMPLE_WINDOW_ALWAYS_ON_TOP_ON if always_on_top else CAC.SIMPLE_WINDOW_ALWAYS_ON_TOP_OFF
        
        self.sendApplicationCommand.emit( CAC.ApplicationCommand.STATICCreateSimpleCommand( action ) )
        
    
    def AddPlayerMenus( self, menu: QW.QMenu ):
        
        player_menu = ClientGUIMenus.GenerateMenu( menu )
        
        ClientGUIMenus.AppendMenuLabel( player_menu, f'This is a {self.GetCurrentMediaPlayerLabel()}.' )
        
        ClientGUIMenus.AppendMenu( menu, player_menu, 'player' )
        
        if isinstance( self._media_window, ClientGUIQtMediaPlayer.QtMediaPlayer ):
            
            self._media_window.AddPlayerMenus( menu )
            
        
    
    def BeginDrag( self ):
        
        self.parentWidget().BeginDrag()
        
    
    def CanConsiderAClose( self ):
        
        return self.ReadyToSwitchMedia()
        
    
    def AddPlaybackSkip( self, start_ms: int, end_ms: int ):
        
        self._SavePlaybackSkips( MergePlaybackSkips( self._playback_skips + [ ( start_ms, end_ms ) ] ) )
        
    
    def ClearABLoopPoints( self ):
        
        self._SetABLoop( None, None )
        
    
    def ClearMedia( self ):
        
        self._media = None
        
        self._next_media_start = None
        
        self._ReleaseStandbyMPVWidget()
        
        self._ClearStandbyZoomData()
        
        self._SetABLoop( None, None )
        
        self._LoadPlaybackSkips()
        
        self._LoadScriptedEvents()
        
        self._LoadSavedZoom()
        
        self._LoadZoomTimestamps()
        
        self._animation_bar.ClearMedia()
        
        self._controls_bar.hide()
        
        self._DestroyOrHideThisMediaWindow( self._media_window )
        
        self._media_window = None
        
        self._UpdateWindowAlwaysOnTop()

        CG.client_controller.gui.UnregisterUIUpdateWindow( self )
        
        self.hide()
        
    
    def CanTakeSnapshot( self ) -> bool:
        
        if self._media is None or self._media.GetMime() in HC.AUDIO:
            
            return False
            
        
        return isinstance( self._media_window, ( Animation, ClientGUIMPV.MPVWidget, ClientGUIQtMediaPlayer.QtMediaPlayer ) )
        
    
    def CanRotate( self ) -> bool:
        
        return self._media is not None and self.IsZoomable() and self._media.GetMime() not in HC.AUDIO and self._media.HasUsefulResolution()
        
    
    def ClearPlaybackSkips( self ):
        
        self._SavePlaybackSkips( [] )
        
    
    def ClearZoomTimestamps( self ):
        
        self._SaveZoomTimestamps( [] )
        
        # the zoom stays where it is. it goes back to normal next time the file is opened
        self._current_zoom_timestamp = None
        
    
    def CurrentlyPresentingMediaWithDuration( self ):
        
        return isinstance( self._media_window, ( Animation, ClientGUIMPV.MPVWidget, ClientGUIQtMediaPlayer.QtMediaPlayer ) )
        
    
    def DeleteZoomTimestamp( self, timestamp_ms: int ):
        
        self._SaveZoomTimestamps( [ zoom_timestamp for zoom_timestamp in self._zoom_timestamps if zoom_timestamp[0] != timestamp_ms ] )
        
        # the zoom stays where it is, like a clear. we note which one we are under now, so the next check does not zoom to it
        current_zoom_timestamp = None
        
        if self.CurrentlyPresentingMediaWithDuration():
            
            animation_bar_status = self._media_window.GetAnimationBarStatus()
            
            if animation_bar_status is not None and animation_bar_status[1] is not None:
                
                current_zoom_timestamp = GetZoomTimestampAt( self._zoom_timestamps, animation_bar_status[1] )
                
            
        
        self._current_zoom_timestamp = current_zoom_timestamp
        self._current_zoom_timestamp_needs_reapply = False
        
    
    def DoEdgePan( self, pan_type: int ):
        
        if self._media is None:
            
            return
            
        
        canvas_size = self.parentWidget().size()
        my_size = self.size()
        my_pos = self.pos()
        
        delta_x = 0
        delta_y = 0
        
        if pan_type == CAC.SIMPLE_PAN_TOP_EDGE:
            
            delta_y = - my_pos.y()
            
        elif pan_type == CAC.SIMPLE_PAN_LEFT_EDGE:
            
            delta_x = - my_pos.x()
            
        elif pan_type == CAC.SIMPLE_PAN_BOTTOM_EDGE:
            
            delta_y = canvas_size.height() - ( my_pos.y() + my_size.height() )
            
        elif pan_type == CAC.SIMPLE_PAN_RIGHT_EDGE:
            
            delta_x = canvas_size.width() - ( my_pos.x() + my_size.width() )
            
        elif pan_type == CAC.SIMPLE_PAN_VERTICAL_CENTER:
            
            delta_y = round( canvas_size.height() / 2 ) - ( my_pos.y() + round( my_size.height() / 2 ) )
            
        elif pan_type == CAC.SIMPLE_PAN_HORIZONTAL_CENTER:
            
            delta_x = round( canvas_size.width() / 2 ) - ( my_pos.x() + round( my_size.width() / 2 ) )
            
        
        delta = QC.QPoint( delta_x, delta_y )
        
        self._MoveDelta( delta )
        
    
    def DoManualPan( self, delta_x_step, delta_y_step ):
        
        if self._media is None:
            
            return
            
        
        canvas_size = self.parentWidget().size()
        my_size = self.size()
        
        x_pan_distance = min( canvas_size.width(), my_size.width() ) // 12
        y_pan_distance = min( canvas_size.height(), my_size.height() ) // 12
        
        delta_x = delta_x_step * x_pan_distance
        delta_y = delta_y_step * y_pan_distance
        
        delta = QC.QPoint( delta_x, delta_y )
        
        self._MoveDelta( delta )
        
    
    def EventEmbedButton( self, event ):
        
        self._embed_button.hide()
        
        self._MakeMediaWindow()
        
        self._SizeAndPositionChildren()
        
        if self._media_window is not None:
            
            self._media_window.show()
            
        
    
    def FlipPerPlayerMuteState( self ):
        
        # flip what the user is actually hearing, which may be a global/media viewer mute if we have no override yet
        self.SetPerPlayerMuteState( not self._GetCurrentMuteState() )
        
    
    def GetCurrentMediaPlayerLabel( self ) -> str:
        
        class_to_desc_dict = {
            StaticImage : 'Hydrus Native Static Image',
            Animation : 'Hydrus Native Animation Player',
            ClientGUIQtMediaPlayer.QtMediaPlayer : 'QtMediaPlayer',
            ClientGUIMPV.MPVWidget : 'MPV Embed Player',
            EmbedButton : 'Embed Button',
            OpenExternallyPanel : 'Open Externally Panel'
        }
        
        for ( class_type, desc_str ) in class_to_desc_dict.items():
            
            if isinstance( self._media_window, class_type ):
                
                return desc_str
                
            
        
        return 'Unknown Media Player - let hydev know please'
        
    
    def ForgetSavedZoom( self ):
        
        if self._media is None or not self._remembers_file_zooms:
            
            return
            
        
        self._saved_zoom_load_id += 1
        
        self._saved_zoom = None
        
        CG.client_controller.Write( 'file_viewer_zoom', self._media.GetHash(), None )
        
        self.ZoomReinit()
        
        self.ResetCenterPosition()
        
    
    def GetCanvasZoom( self ) -> float:
        
        return self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]
        
    
    def GetRotation( self ) -> int:
        
        return self._rotation
        
    
    def GetCurrentZoom( self ) -> float:
        
        return self._current_zoom
        
    
    def GetCurrentView( self ) -> tuple[ float, tuple[ float, float ] ] | None:
        
        # the zoom, relative to the zoom that fits the file in the window, and the part of the file in the middle of the window, as a fraction of its width and height
        # these follow the window's size, like zoom timestamps. None if the file is not zoomable
        canvas_zoom = self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]
        
        if self._media is None or not self.IsZoomable() or canvas_zoom <= 0:
            
            return None
            
        
        canvas_size = self.parentWidget().size()
        my_pos = self.pos()
        my_size = self.size()
        
        center = GetZoomCenter( ( canvas_size.width(), canvas_size.height() ), ( my_pos.x(), my_pos.y() ), ( my_size.width(), my_size.height() ) )
        
        return ( self._current_zoom / canvas_zoom, center )
        
    
    def GetIdealControlsBarRect( self, full_size = True ):
        
        my_size = self.size()
        
        my_width = my_size.width()
        my_height = my_size.height()
        
        if full_size:
            
            animated_scanbar_height = CG.client_controller.new_options.GetInteger( 'animated_scanbar_height' )
            
        else:
            
            animated_scanbar_height = CG.client_controller.new_options.GetNoneableInteger( 'animated_scanbar_hide_height' )
            
            if animated_scanbar_height is None:
                
                animated_scanbar_height = 5
                
            
        
        return QC.QRect(
            QC.QPoint( 0, my_height - animated_scanbar_height ),
            QC.QSize( my_width, animated_scanbar_height )
        )
        
    
    def GetABLoop( self ) -> tuple[ int | None, int | None ]:
        
        return ( self._ab_loop_a_ms, self._ab_loop_b_ms )
        
    
    def GetAudioEffects( self ) -> ClientGUIMediaAudioEffects.AudioEffects:
        
        return self._audio_effects
        
    
    def GetCurrentMuteState( self ) -> bool:
        
        return self._GetCurrentMuteState()
        
    
    def GetCurrentVolume( self ) -> int:
        
        return self._GetCurrentVolume()
        
    
    def GetPerPlayerMuteState( self ):
        
        return self._per_player_mute_state
        
    
    def GetCurrentPlaybackPointMS( self ) -> int | None:
        
        # the start of the frame on screen, which is the point a zoom timestamp or scripted event made now goes at
        frame_start_and_duration = self._GetCurrentFrameStartAndDurationMS()
        
        if frame_start_and_duration is None:
            
            return None
            
        
        ( frame_start_ms, frame_duration_ms ) = frame_start_and_duration
        
        return ConvertFrameStartToPlaybackPointMS( frame_start_ms )
        
    
    def GetCurrentPlaybackTimestampMS( self ) -> int | None:
        
        return self._GetCurrentPlaybackTimestampMS()
        
    
    def GetMedia( self ) -> ClientMediaSingle.MediaSingle | None:
        
        # this can be behind the canvas's media for a moment, while a switch waits for the old media to be ready to go
        return self._media
        
    
    def GetPlaybackSkips( self ) -> list[ tuple[ int, int ] ]:
        
        return list( self._playback_skips )
        
    
    def GetScriptedEvents( self ) -> list[ ClientMediaScriptedEvents.ScriptedEvent ]:
        
        return list( self._scripted_events )
        
    
    def GetZoomTimestamps( self ) -> list[ ZoomTimestamp ]:
        
        return list( self._zoom_timestamps )
        
    
    def GetTieMediaWindowOnTopToPausePlayState( self ):
        
        return self._tie_media_window_to_pauseplay_state
        
    
    def GotoPreviousOrNextFrame( self, direction ):
        
        if self._media is not None:
            
            if ShouldHaveAnimationBar( self._media, self._show_action ):
                
                if isinstance( self._media_window, Animation ):
                    
                    current_frame_index = self._media_window.CurrentFrame()
                    
                    num_frames = self._media.GetNumFrames()
                    
                    if direction == 1:
                        
                        if current_frame_index == num_frames - 1:
                            
                            current_frame_index = 0
                            
                        else:
                            
                            current_frame_index += 1
                            
                        
                    else:
                        
                        if current_frame_index == 0:
                            
                            current_frame_index = num_frames - 1
                            
                        else:
                            
                            current_frame_index -= 1
                            
                        
                    
                    self._media_window.GotoFrame( current_frame_index )
                    
                elif isinstance( self._media_window, ( ClientGUIMPV.MPVWidget, ClientGUIQtMediaPlayer.QtMediaPlayer ) ):
                    
                    self._media_window.GotoPreviousOrNextFrame( direction )
                    
                
            
        
    
    def HasPerPlayerMuteState( self ):
        
        return self._has_per_player_mute_state
        
    
    def HasPlayedOnceThrough( self ):
        
        if self.CurrentlyPresentingMediaWithDuration():
            
            return self._media_window.HasPlayedOnceThrough()
            
        
        return True
        
    
    def HasSavedZoom( self ):
        
        return self._saved_zoom is not None
        
    
    def IsAtMaxZoom( self ):
        
        possible_zooms = CG.client_controller.new_options.GetMediaZooms()
        
        max_zoom = max( possible_zooms )
        
        max_zoom_dimension = self._GetMaxZoomDimension()
        
        return self._current_zoom == max_zoom or self.width() == max_zoom_dimension or self.height() == max_zoom_dimension
        
    
    def IsMuted( self ):
        
        if isinstance( self._media_window, ( ClientGUIMPV.MPVWidget, ClientGUIQtMediaPlayer.QtMediaPlayer ) ):
            
            return self._media_window.IsMuted()
            
        else:
            
            return ClientGUIMediaVolume.GetCorrectCurrentMute( self._canvas_type )
        
    
    def IsPaused( self ):
        
        if self.CurrentlyPresentingMediaWithDuration():
            
            return self._media_window.IsPaused()
            
        
        return False
        
    
    def IsUsingMPV( self ):
        
        return isinstance( self._media_window, ClientGUIMPV.MPVWidget )
        
    
    def IsZoomable( self ):
        
        if self._media is None:
            
            return False
            
        
        return self._show_action not in ( CC.MEDIA_VIEWER_ACTION_SHOW_OPEN_EXTERNALLY_BUTTON, CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW_ON_ACTIVATION_OPEN_EXTERNALLY, CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW )
        
    
    def minimumSizeHint( self ) -> QC.QSize:
        
        return self.sizeHint()
        
    
    def MouseIsNearAnimationBar( self ):
        
        if self._media is None:
            
            return False
            
        
        if ShouldHaveAnimationBar( self._media, self._show_action ):
            
            if not ClientGUIFunctions.MouseIsOverWidget( self._canvas ):
                
                return False
                
            
            # there's some minor update stuff here now the scanbar can be hidden. its geometry may not update until later, so we need to map coordinates from widgets we know are in view instead!
            
            container_mouse_pos = self.mapFromGlobal( ClientGUIFunctions.GetMousePos() )
            
            controls_bar_rect = self.GetIdealControlsBarRect()
            
            buffer = 100
            
            test_rect = controls_bar_rect.adjusted( -buffer // 2, -buffer, buffer // 2, buffer // 5 )
            
            return test_rect.contains( container_mouse_pos )
            
        
        return False
        
    
    def MoveDelta( self, delta: QC.QPoint ):
        
        self._MoveDelta( delta )
        
    
    def NotifyAllSavedZoomsReset( self, clear_file_viewer_zooms: bool, clear_zoom_timestamps: bool ):
        
        if self._media is None:
            
            return
            
        
        if clear_file_viewer_zooms and self._remembers_file_zooms:
            
            # anything we are still loading is now out of date
            self._saved_zoom_load_id += 1
            
            if self._saved_zoom is not None:
                
                self._saved_zoom = None
                
                # like 'forget this file's zoom', we go back to the normal default zoom
                if self.IsZoomable():
                    
                    self.ZoomReinit()
                    
                    self.ResetCenterPosition()
                    
                
            
        
        if clear_zoom_timestamps and self._does_zoom_timestamps:
            
            self._zoom_timestamps_load_id += 1
            
            self._SetZoomTimestamps( [] )
            
            # like 'clear zoom timestamps', the zoom stays where it is. it goes back to normal next time the file is opened
            self._current_zoom_timestamp = None
            
        
    
    def NotifyAudioMuteOptionsChanged( self ):
        
        if not self._has_per_player_mute_state:
            
            self._UpdateMediaWindowMute()
            
            self.muteStateChanged.emit()
            
        
    
    def NotifyAudioVolumeOptionsChanged( self ):
        
        if not self._has_per_player_volume:
            
            self._UpdateMediaWindowVolume()
            
            self.volumeChanged.emit()
            
        
    
    def NotifyNewPlaybackSkips( self, hash: bytes, skips: list[ tuple[ int, int ] ] ):
        
        if self._media is not None and self._media.GetHash() == hash:
            
            self._playback_skips_load_id += 1
            
            self._SetPlaybackSkips( skips )
            
        
    
    def NotifyNewScriptedEvents( self, hash: bytes, scripted_events: list[ ClientMediaScriptedEvents.ScriptedEvent ] ):
        
        if self._media is not None and self._media.GetHash() == hash and self._does_scripted_events:
            
            self._scripted_events_load_id += 1
            
            # we carry on from where playback is, so a new one just behind us does not run until next time round
            self._SetScriptedEvents( scripted_events )
            
        
    
    def NotifyNewZoomTimestamps( self, hash: bytes, zoom_timestamps: list[ ZoomTimestamp ] ):
        
        if self._media is not None and self._media.GetHash() == hash and self._does_zoom_timestamps:
            
            self._zoom_timestamps_load_id += 1
            
            self._SetZoomTimestamps( zoom_timestamps )
            
        
        if self._standby_zoom_data_hash == hash:
            
            # what we looked up ahead of time is out of date. the file will look them up itself when it comes on
            self._ClearStandbyZoomData()
            
        
    
    def Pause( self ):
        
        if self._media is not None:
            
            if self.CurrentlyPresentingMediaWithDuration():
                
                self._media_window.Pause()
                
            
        
    
    def PausePlay( self ):
        
        if self._media is not None:
            
            if self.CurrentlyPresentingMediaWithDuration():
                
                self._media_window.PausePlay()
            
        
    
    def PreloadMedia( self, media: ClientMediaSingle.MediaSingle, start_ms: int | None ):
        
        # get what is coming next ready, so when it is time to show it, there is nothing to wait for
        if media == self._media:
            
            return
            
        
        self._LoadStandbyZoomData( media )
        
        if self._standby_media == media and ( self._standby_start_ms or 0 ) == ( start_ms or 0 ):
            
            return
            
        
        self._ReleaseStandbyMPVWidget()
        
        ( show_action, start_paused, start_with_embed ) = ClientMedia.GetShowAction( media.GetMediaResult(), self._canvas_type )
        
        # only mpv can sit there with a file loaded, out of sight. the others are quick enough to load, or stay as they are
        if show_action != CC.MEDIA_VIEWER_ACTION_SHOW_WITH_MPV or start_with_embed or not ClientGUIMPV.MPV_IS_AVAILABLE:
            
            return
            
        
        # the first time, this makes a new mpv window, which takes a moment. after that, they come from the pool
        mpv_widget = CG.client_controller.gui.GetMPVWidget( self )
        
        mpv_widget.hide()
        
        mpv_widget.amInitialised.connect( self._NotifyMPVInitialised )
        
        mpv_widget.SetCanvasType( self._canvas_type )
        
        # it sits paused at its start, and quiet, until it is swapped in
        mpv_widget.SetMute( self._GetCurrentMuteState() )
        mpv_widget.SetVolume( self._GetCurrentVolume() )
        mpv_widget.SetAudioFilterGraph( self._audio_effects.GetFilterGraph() )
        
        mpv_widget.SetMedia( media, start_paused = True, start_ms = start_ms )
        
        self._standby_mpv_widget = mpv_widget
        self._standby_media = media
        self._standby_start_ms = start_ms
        
    
    def ReadyToDestroy( self ):
        
        return len( self._closing_mpv_widgets ) + len( self._closing_qt_media_players ) == 0
        
    
    def ReadyToSwitchMedia( self ):
        
        if isinstance( self._media_window, ClientGUIMPV.MPVWidget ):
            
            return self._media_window.IsInitialised()
            
        else:
            
            return True
            
        
    
    def RescueIfOffScreen( self ):
        
        my_ideal_size = self.sizeHint()
        
        canvas_rect = self.parentWidget().rect()
        ideal_media_rect = QC.QRect( self.pos(), my_ideal_size )
        
        if not canvas_rect.intersects( ideal_media_rect ):
            
            # up/down
            
            height_buffer = min( ideal_media_rect.height(), self.height() // 5 )
            
            if ideal_media_rect.bottom() < canvas_rect.top():
                
                ideal_media_rect.moveBottom( canvas_rect.top() + height_buffer )
                
            elif ideal_media_rect.top() > canvas_rect.bottom():
                
                ideal_media_rect.moveTop( canvas_rect.bottom() - height_buffer )
                
            
            # left/right
            
            width_buffer = min( ideal_media_rect.width(), self.width() // 5 )
            
            if ideal_media_rect.right() < canvas_rect.left():
                
                ideal_media_rect.moveRight( canvas_rect.left() + width_buffer )
                
            elif ideal_media_rect.left() > canvas_rect.right():
                
                ideal_media_rect.moveLeft( canvas_rect.right() - width_buffer )
                
            
        
        ideal_pos = ideal_media_rect.topLeft()
        
        if ideal_pos != self.pos():
            
            self.move( ideal_pos )
            
        
    
    def ResetCenterPosition( self ):
        
        if self._media is None:
            
            return
            
        
        canvas_size = self.parentWidget().size()
        
        ideal_size = self.sizeHint()
        
        x = ( canvas_size.width() - ideal_size.width() ) // 2
        y = ( canvas_size.height() - ideal_size.height() ) // 2
        
        ideal_pos =  QC.QPoint( x, y )
        
        if ideal_pos != self.pos():
            
            self.move( ideal_pos )
            
        
    
    def ResetZoomToDefault( self ):
        
        if self._media is None:
            
            return
            
        
        # the default zoom for now, over the file's saved zoom and any zoom timestamp we are in. this holds through the resizes that follow a window move
        self._holding_default_zoom = True
        
        self.ZoomReinit()
        
        self.ResetCenterPosition()
        
    
    def resizeEvent( self, event ):
        
        if self._media is not None:
            
            self._SizeAndPositionChildren()
            
        
    
    def SeekDelta( self, direction, duration_ms ):
        
        if self._media is not None:
            
            if self.CurrentlyPresentingMediaWithDuration():
                
                self._media_window.SeekDelta( direction, duration_ms )
                
            
        
    
    def SetCurrentView( self, relative_zoom: float, center: tuple[ float, float ] | None ) -> bool:
        
        # the other side of GetCurrentView. False if the file is not ready to be zoomed yet
        canvas_zoom = self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]
        
        if self._media is None or not self.IsZoomable() or canvas_zoom <= 0:
            
            return False
            
        
        # a saved zoom still on its way would undo this
        self._saved_zoom_load_id += 1
        
        self._SetZoom( self._GetZoomWithinMaxDimension( relative_zoom * canvas_zoom ) )
        
        if center is None:
            
            self.ResetCenterPosition()
            
        else:
            
            self._MoveToZoomCenter( center )
            
        
        self.update()
        
        return True
        
    
    def SeekTo( self, timestamp_ms: int ):
        
        if self._media is None:
            
            return
            
        
        if isinstance( self._media_window, Animation ):
            
            # this goes to the frame and keeps playing, which is just what we want here too
            self._media_window.SeekPastPlaybackSkip( timestamp_ms )
            
        elif isinstance( self._media_window, ( ClientGUIMPV.MPVWidget, ClientGUIQtMediaPlayer.QtMediaPlayer ) ):
            
            self._media_window.Seek( timestamp_ms )
            
        
    
    def SetABLoopPointA( self ):
        
        frame_start_and_duration = self._GetCurrentFrameStartAndDurationMS()
        
        if frame_start_and_duration is None:
            
            return
            
        
        ( frame_start_ms, frame_duration_ms ) = frame_start_and_duration
        
        # the frame on screen is the first one the loop shows
        a_ms = ConvertFrameStartToPlaybackPointMS( frame_start_ms )
        
        b_ms = self._ab_loop_b_ms
        
        # the newest point wins. if it makes the loop backwards or too short, the other point is dropped
        if b_ms is not None and b_ms - a_ms < MIN_AB_LOOP_DURATION_MS:
            
            b_ms = None
            
        
        self._SetABLoop( a_ms, b_ms )
        
    
    def SetABLoopPointB( self ):
        
        frame_start_and_duration = self._GetCurrentFrameStartAndDurationMS()
        
        if frame_start_and_duration is None:
            
            return
            
        
        ( frame_start_ms, frame_duration_ms ) = frame_start_and_duration
        
        # the frame on screen is the last one the loop shows
        b_ms = ConvertFrameToABLoopPointBMS( frame_start_ms, frame_duration_ms )
        
        if b_ms < MIN_AB_LOOP_DURATION_MS:
            
            return
            
        
        a_ms = self._ab_loop_a_ms
        
        # the newest point wins. if it makes the loop backwards or too short, the other point is dropped and we loop from the start
        if a_ms is not None and b_ms - a_ms < MIN_AB_LOOP_DURATION_MS:
            
            a_ms = None
            
        
        self._SetABLoop( a_ms, b_ms )
        
    
    def SetAudioEffects( self, audio_effects: ClientGUIMediaAudioEffects.AudioEffects ):
        
        self._audio_effects = audio_effects
        
        self._UpdateMediaWindowAudioEffects()
        
    
    def SetBackgroundColourGenerator( self, background_colour_generator ):
        
        self._background_colour_generator = background_colour_generator
        
        self._embed_button.SetBackgroundColourGenerator( self._background_colour_generator )
        self._animation_window.SetBackgroundColourGenerator( self._background_colour_generator )
        self._static_image_window.SetBackgroundColourGenerator( self._background_colour_generator )
        
    
    def SetMedia( self, media: ClientMediaSingle.MediaSingle, maintain_zoom, maintain_zoom_type, maintain_pan, start_paused = None ):
        
        if not self.ReadyToSwitchMedia():
            
            self._deferred_set_media_call = HydrusData.Call( self.SetMedia, media, maintain_zoom, maintain_zoom_type, maintain_pan, start_paused = start_paused )
            
            return
            
        
        previous_media = self._media
        
        self._media = media
        
        ( self._show_action, self._start_paused, self._start_with_embed ) = ClientMedia.GetShowAction( self._media.GetMediaResult(), self._canvas_type )
        
        if start_paused is not None:
            
            self._start_paused = start_paused
            
        
        if self._show_action in ( CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW_ON_ACTIVATION_OPEN_EXTERNALLY, CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW ):
            
            self._show_action = CC.MEDIA_VIEWER_ACTION_SHOW_OPEN_EXTERNALLY_BUTTON
            
        
        if self._start_with_embed:
            
            self._animation_bar.ClearMedia()
            
            self._controls_bar.hide()
            
            self._DestroyOrHideThisMediaWindow( self._media_window )
            
            self._media_window = None
            
            self._embed_button.SetMedia( self._media )
            
            self._embed_button.show()
            
        else:
            
            self._embed_button.hide()
            
            self._MakeMediaWindow()
            
        
        self._next_media_start = None
        
        # loop points belong to the file they were marked on
        self._SetABLoop( None, None )
        
        self._LoadPlaybackSkips()
        
        self._LoadScriptedEvents()
        
        # like the zoom, the last file's rotation goes, and the new file's comes in a moment later
        self._LoadRotation()
        
        # this clears the last file's zoom before we set up the new one, and then the new file's zoom comes in a moment later
        self._LoadSavedZoom()
        
        self._LoadZoomTimestamps()
        
        if maintain_zoom and previous_media is not None:
            
            self.ZoomMaintainingZoom( previous_media )
            
        elif maintain_zoom_type:
            
            self.ZoomToZoomType()
            
        else:
            
            self.ZoomReinit()
            
        
        if previous_media is None or not maintain_pan:
            
            self.ResetCenterPosition()
            
        
        self._ApplyZoomDataFromStandby()
        
        # it was for this file, or it is out of date
        self._ClearStandbyZoomData()
        
        self._SizeAndPositionChildren()
        
        if self._media_window is not None:
            
            self._media_window.show()
            
        
        CG.client_controller.gui.RegisterUIUpdateWindow( self )
        
        self.show()
        
        self._UpdateWindowAlwaysOnTop()
        
    
    def SetNextMediaStartMS( self, media: ClientMediaSingle.MediaSingle, start_ms: int | None ):
        
        # the next time we get this file, start playing it here
        self._next_media_start = ( media, start_ms )
        
    
    def SetRotation( self, rotation: float ):
        
        # the user turning the file. it stays like this every time it is shown
        if not self.CanRotate():
            
            return
            
        
        # anything we are still loading is now out of date
        self._rotation_load_id += 1
        
        self._SetRotation( rotation )
        
        CG.client_controller.Write( 'file_viewer_rotation', self._media.GetHash(), self._rotation )
        
    
    def ShouldHaveVolumeControl( self ):
        
        if self._media is None:
            
            return False
            
        
        return isinstance( self._media_window, ( ClientGUIMPV.MPVWidget, ClientGUIQtMediaPlayer.QtMediaPlayer ) ) and self._media.HasAudio()
        
    
    def SetPerPlayerMuteState( self, mute_state: bool | None ):
        
        if mute_state is None:
            
            self._has_per_player_mute_state = False
            
        else:
            
            self._has_per_player_mute_state = True
            self._per_player_mute_state = mute_state
            
        
        if self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES:
            
            # 'stop forcing' clears this, so new media viewers go back to following the options
            CG.client_controller.new_options.SetNoneableInteger( 'media_viewer_last_mute', None if mute_state is None else int( mute_state ) )
            
        
        self._UpdateMediaWindowMute()
        
        self.muteStateChanged.emit()
        
    
    def SetPerPlayerVolume( self, volume: int | None ):
        
        if volume is None:
            
            self._has_per_player_volume = False
            
        else:
            
            self._has_per_player_volume = True
            self._per_player_volume = volume
            
            if self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES:
                
                CG.client_controller.new_options.SetNoneableInteger( 'media_viewer_last_volume', volume )
                
            
        
        self._UpdateMediaWindowVolume()
        
        self.volumeChanged.emit()
        
    
    def SetTieMediaWindowOnTopToPausePlayState( self, tie_media_window_to_pauseplay_state: bool ):
        
        self._tie_media_window_to_pauseplay_state = tie_media_window_to_pauseplay_state
        
        if self._tie_media_window_to_pauseplay_state:
            
            self._UpdateWindowAlwaysOnTop()
            
        else:
            
            always_on_top = CG.client_controller.new_options.GetBoolean( 'always_start_media_viewers_always_on_top' )
            
            action = CAC.SIMPLE_WINDOW_ALWAYS_ON_TOP_ON if always_on_top else CAC.SIMPLE_WINDOW_ALWAYS_ON_TOP_OFF
            
            self.sendApplicationCommand.emit( CAC.ApplicationCommand.STATICCreateSimpleCommand( action ) )
            
        
    
    def sizeHint(self) -> QC.QSize:
        
        if self._media is None or self._show_action in ( CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW_ON_ACTIVATION_OPEN_EXTERNALLY, CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW ):
            
            return QC.QSize( 0, 0 )
            
        
        my_dpr = self.devicePixelRatio()
        
        return CalculateMediaContainerSize( self._media, my_dpr, self._current_zoom, self._show_action, rotation = self._rotation )
        
    
    def SizeSelfToMedia( self ):
        
        if self._media is None:
            
            return
            
        
        media_size = self._media_window.size()
        media_width = media_size.width()
        media_height = media_size.height()
        
        if media_width is None or media_height is None:
            
            return
            
        
        media_win_pos = self._media_window.mapToGlobal( QC.QPoint( 0, 0 ) )
        
        frame_geometry = self.window().frameGeometry()
        window_geometry = self.window().geometry()
        title_bar_offset = frame_geometry.top() - window_geometry.top()
        
        adjusted_pos = QC.QPoint( media_win_pos.x(), media_win_pos.y() + title_bar_offset )
        
        if not CG.client_controller.new_options.GetBoolean( 'disable_get_safe_position_test' ):
            
            ( adjusted_pos, silenced_message ) = ClientGUITopLevelWindows.GetSafePosition( adjusted_pos, 'media_window_size_self_to_media' )
            
        
        self.window().showNormal()
        
        self.window().resize( media_width, media_height )
        self.window().move( adjusted_pos )
        
        self.ResetCenterPosition()
        self._SizeAndPositionChildren()
        
    
    def StopForSlideshow( self, value ):
        
        if self.CurrentlyPresentingMediaWithDuration():
            
            self._media_window.StopForSlideshow( value )
            
        
    
    def ZoomByPercent( self, percent_delta: int, zoom_center_type_override = None ):
        
        if not self.IsZoomable() or percent_delta == 0:
            
            return
            
        
        ( min_zoom, max_zoom ) = self._GetFineZoomLimits()
        
        current_percent = self._current_zoom * 100
        
        # we snap to whole percents, so 37.4% goes to 38% or 37%. the little fudge soaks up float noise like 38.00000000000001
        if percent_delta > 0:
            
            new_zoom = min( ( math.floor( current_percent + 0.0001 ) + percent_delta ) / 100, max_zoom )
            
        else:
            
            new_zoom = max( ( math.ceil( current_percent - 0.0001 ) + percent_delta ) / 100, min_zoom )
            
        
        if ( new_zoom - self._current_zoom ) * percent_delta <= 0:
            
            return
            
        
        self._TryToChangeZoom( new_zoom, zoom_center_type_override = zoom_center_type_override )
        
    
    def ZoomByPixels( self, pixel_delta: int, zoom_center_type_override = None ):
        
        if not self.IsZoomable() or pixel_delta == 0:
            
            return
            
        
        # this deliberately ignores 'exact zooms only'--the user is explicitly asking for fine control
        
        if self._media.GetMime() in HC.AUDIO or not self._media.HasUsefulResolution():
            
            # fine zoom makes no sense here, so fall back to the normal steps
            
            if pixel_delta > 0:
                
                self.ZoomIn( zoom_center_type_override = zoom_center_type_override )
                
            else:
                
                self.ZoomOut( zoom_center_type_override = zoom_center_type_override )
                
            
            return
            
        
        ( min_zoom, max_zoom ) = self._GetFineZoomLimits()
        
        my_dpr = self.devicePixelRatio()
        
        ( original_width, original_height ) = self._GetMediaResolution()
        
        # we step the longer side, so that is the one that changes one pixel at a time
        step_on_width = original_width >= original_height
        
        original_dimension = original_width if step_on_width else original_height
        
        def get_dimension( zoom ):
            
            size = CalculateMediaContainerSize( self._media, my_dpr, zoom, CC.MEDIA_VIEWER_ACTION_SHOW_WITH_NATIVE, rotation = self._rotation )
            
            return size.width() if step_on_width else size.height()
            
        
        current_dimension = get_dimension( self._current_zoom )
        
        step = 1 if pixel_delta > 0 else -1
        
        ( current_raw_width, current_raw_height ) = CalculateMediaSize( self._media, self._current_zoom, rotation = self._rotation )
        
        raw_dimension = current_raw_width if step_on_width else current_raw_height
        
        # with a non-1 dpr, not every raw pixel count is a new on-screen size, so walk the raw pixels until the on-screen size has moved enough
        while True:
            
            raw_dimension += step
            
            new_zoom = raw_dimension / original_dimension
            
            if step > 0 and new_zoom >= max_zoom:
                
                new_zoom = max_zoom
                
                break
                
            
            if step < 0 and new_zoom <= min_zoom:
                
                new_zoom = min_zoom
                
                break
                
            
            new_dimension = get_dimension( new_zoom )
            
            if ( new_dimension - current_dimension ) * step >= abs( pixel_delta ):
                
                break
                
            
        
        if ( new_zoom - self._current_zoom ) * step <= 0:
            
            return
            
        
        self._TryToChangeZoom( new_zoom, zoom_center_type_override = zoom_center_type_override )
        
    
    def ZoomIn( self, zoom_center_type_override = None ):
        
        if not self.IsZoomable():
            
            return
            
        
        ( media_scale_up, media_scale_down, preview_scale_up, preview_scale_down, exact_zooms_only, scale_up_quality, scale_down_quality ) = CG.client_controller.new_options.GetMediaZoomOptions( self._media.GetMime() )
        
        possible_zooms = CG.client_controller.new_options.GetMediaZooms()
        
        if exact_zooms_only:
            
            exact_zoom = 1.0
            
            if exact_zoom <= self._current_zoom:
                
                while exact_zoom <= self._current_zoom:
                    
                    exact_zoom *= 2
                    
                
            else:
                
                while exact_zoom / 2 > self._current_zoom:
                    
                    exact_zoom /= 2
                    
                
            
            max_zoom = max( possible_zooms )
            
            if exact_zoom > max_zoom:
                
                return
                
            
            possible_zooms = [ exact_zoom ]
            
        
        possible_zooms.append( self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ] )
        
        bigger_zooms = [ zoom for zoom in possible_zooms if zoom > self._current_zoom ]
        
        if len( bigger_zooms ) > 0:
            
            new_zoom = min( bigger_zooms )
            
            self._TryToChangeZoom( new_zoom, zoom_center_type_override = zoom_center_type_override )
            
        
    
    def ZoomMaintainingZoom( self, previous_media: ClientMediaSingle.MediaSingle ):
        
        if self._media is None:
            
            return
            
        
        if previous_media is None or not previous_media.HasUsefulResolution() or not self._media.HasUsefulResolution():
            
            self.ZoomReinit()
            
            return
            
        
        # set up canvas zoom
        
        canvas_size = self.parentWidget().size()
        
        my_dpr = self.devicePixelRatio()
        
        ( media_show_action, media_start_paused, media_start_with_embed ) = ClientMedia.GetShowAction( self._media.GetMediaResult(), self._canvas_type )
        
        if media_show_action in ( CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW_ON_ACTIVATION_OPEN_EXTERNALLY, CC.MEDIA_VIEWER_ACTION_SHOW_OPEN_EXTERNALLY_BUTTON, CC.MEDIA_VIEWER_ACTION_DO_NOT_SHOW ):
            
            self.ZoomReinit()
            
            return
            
        
        self._zoom_types_to_zooms = CalculateCanvasZooms( canvas_size, self._canvas_type, my_dpr, self._media, media_show_action, rotation = self._rotation )
        
        previous_current_zoom = self._current_zoom
        
        ( previous_show_action, previous_start_paused, previous_start_with_embed ) = ClientMedia.GetShowAction( previous_media.GetMediaResult(), self._canvas_type )
        
        previous_zoom_types_to_zooms = CalculateCanvasZooms( canvas_size, self._canvas_type, my_dpr, previous_media, previous_show_action )
        
        # previously, we always matched width, but this causes a problem in dupe viewer when B has a little watermark on the bottom, spilling below bottom of screen
        # I think in future we will have more options regarding all this, and this method will change significantly
        # however for now we really just want a hardcoded ok solution for all situations, so let's just hook on default canvas zoom situation
        
        ( previous_width, previous_height ) = CalculateMediaSize( previous_media, self._current_zoom )
        
        ( previous_media_100_width, previous_media_100_height ) = previous_media.GetResolution()
        ( current_media_100_width, current_media_100_height ) = self._GetMediaResolution()
        
        width_locked_zoom = previous_width / current_media_100_width
        height_locked_zoom = previous_height / current_media_100_height
        
        width_locked_size = CalculateMediaContainerSize( self._media, my_dpr, width_locked_zoom, media_show_action, rotation = self._rotation )
        height_locked_size = CalculateMediaContainerSize( self._media, my_dpr, height_locked_zoom, media_show_action, rotation = self._rotation )
        
        # if landscape, go height, portrait, go width
        if previous_media_100_width > previous_media_100_height and current_media_100_width > current_media_100_height:
            
            lock_height = True
            
        elif previous_media_100_width < previous_media_100_height and current_media_100_width < current_media_100_height:
            
            lock_height = False
            
        else:
            
            # for weird stuff, we'll choose the smaller of the two ratios
            
            width_difference = max( previous_media_100_width, current_media_100_width ) / min( previous_media_100_width, current_media_100_width )
            height_difference = max( previous_media_100_height, current_media_100_height ) / min( previous_media_100_height, current_media_100_height )
            
            lock_height = height_difference <= width_difference
            
        
        # however we don't want to accidentally zoom in if the media we are switching to is larger. it'll spill over the bottom of the canvas
        # therefore let's have a little safety check
        
        if previous_current_zoom == previous_zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE ] and previous_current_zoom <= previous_zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ] * 1.05:
            
            # we were looking at the default zoom, near or at canvas edge(s), probably hadn't zoomed before switching comparison
            # we want to make sure our comparison does not spill over the canvas edge
            
            close_to_vertical_edge = canvas_size.height() * 0.95 <= self.height() <= canvas_size.height() * 1.05
            vertical_spillover_could_be_deceptive = self.height() < width_locked_size.height() < self.height() * 1.1
            
            # locking by width will spill over bottom of screen
            if close_to_vertical_edge and vertical_spillover_could_be_deceptive:
                
                lock_height = True
                
            
            close_to_horizontal_edge = canvas_size.width() * 0.95 <= self.width() <= canvas_size.width() * 1.05
            horizontal_spillover_could_be_deceptive = self.width() < height_locked_size.width() < self.width() * 1.1
            
            # locking by height will spill over right of screen
            if close_to_horizontal_edge and horizontal_spillover_could_be_deceptive:
                
                lock_height = False
                
            
        
        if lock_height:
            
            current_zoom = height_locked_zoom
            
        else:
            
            current_zoom = width_locked_zoom
            
        
        self._SetZoom( current_zoom )
        
    
    def Zoom100( self, zoom_center_type_override = None ):
        
        self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_100
        
        self._TryToChangeZoom( 1.0, zoom_center_type_override = zoom_center_type_override )
        
    
    def ZoomCanvas( self, zoom_center_type_override = None ):
        
        self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_CANVAS

        self._TryToChangeZoom( self._zoom_types_to_zooms[ self._current_zoom_type ], zoom_center_type_override = zoom_center_type_override )
        
    
    def ZoomCanvasFillX( self, zoom_center_type_override = None ):
        
        self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_FILL_X

        self._TryToChangeZoom( self._zoom_types_to_zooms[ self._current_zoom_type ], zoom_center_type_override = zoom_center_type_override )
        
    
    def ZoomCanvasFillY( self, zoom_center_type_override = None ):
        
        self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_FILL_Y

        self._TryToChangeZoom( self._zoom_types_to_zooms[ self._current_zoom_type ], zoom_center_type_override = zoom_center_type_override )
        
    
    def ZoomCanvasFillAuto( self, zoom_center_type_override = None ):
        
        self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_FILL_AUTO

        self._TryToChangeZoom( self._zoom_types_to_zooms[ self._current_zoom_type ], zoom_center_type_override = zoom_center_type_override )
        
    
    def ZoomDefault( self, zoom_center_type_override = None ):
        
        self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE
        
        self._TryToChangeZoom( self._zoom_types_to_zooms[ self._current_zoom_type ], zoom_center_type_override = zoom_center_type_override )
        
    
    def ZoomMax( self ):
        
        if not self.IsZoomable():
            
            return
            
        
        possible_zooms = CG.client_controller.new_options.GetMediaZooms()
        
        max_zoom = max( possible_zooms )
        
        ( media_scale_up, media_scale_down, preview_scale_up, preview_scale_down, exact_zooms_only, scale_up_quality, scale_down_quality ) = CG.client_controller.new_options.GetMediaZoomOptions( self._media.GetMime() )
        
        if exact_zooms_only:
            
            exact_zoom = 1.0
            
            while exact_zoom * 2 <= max_zoom:
                
                exact_zoom *= 2
                
            
            max_zoom = exact_zoom
            
        
        new_zoom = max_zoom
        
        if self._current_zoom != new_zoom:
            
            self._TryToChangeZoom( new_zoom )
            
        
    
    def ZoomOut( self, zoom_center_type_override = None ):
        
        if not self.IsZoomable():
            
            return
            
        
        ( media_scale_up, media_scale_down, preview_scale_up, preview_scale_down, exact_zooms_only, scale_up_quality, scale_down_quality ) = CG.client_controller.new_options.GetMediaZoomOptions( self._media.GetMime() )
        
        if exact_zooms_only:
            
            exact_zoom = 1.0
            
            if exact_zoom < self._current_zoom:
                
                while exact_zoom * 2 < self._current_zoom:
                    
                    exact_zoom *= 2
                    
                
            else:
                
                while exact_zoom >= self._current_zoom:
                    
                    exact_zoom /= 2
                    
                
            
            possible_zooms = [ exact_zoom ]
            
        else:
            
            possible_zooms = CG.client_controller.new_options.GetMediaZooms()
            
        
        possible_zooms.append( self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ] )
        
        smaller_zooms = [ zoom for zoom in possible_zooms if zoom < self._current_zoom ]
        
        if len( smaller_zooms ) > 0:
            
            new_zoom = max( smaller_zooms )
            
            self._TryToChangeZoom( new_zoom, zoom_center_type_override = zoom_center_type_override )
            
        
    
    def ZoomReinit( self ):
        
        if self._media is None:
            
            return
            
        
        # this is a resize or a new file. if we are in a zoom timestamp, it needs to go back on, unless we are holding the default zoom
        self._current_zoom_timestamp_needs_reapply = not self._holding_default_zoom
        
        canvas_size = self.parentWidget().size()
        my_dpr = self.devicePixelRatio()
        
        self._zoom_types_to_zooms = CalculateCanvasZooms( canvas_size, self._canvas_type, my_dpr, self._media, self._show_action, rotation = self._rotation )
        
        self._current_zoom_type = self._GetDefaultZoomType()
        
        zoom = self._zoom_types_to_zooms[ self._current_zoom_type ]
        
        # a file with its own zoom keeps it, e.g. when the media viewer window is resized
        if self._saved_zoom is not None and not self._holding_default_zoom:
            
            zoom = self._GetZoomWithinMaxDimension( self._saved_zoom )
            
        
        self._SetZoom( zoom )
        
    
    def ZoomSwitch( self, zoom_center_type_override = None ):
        
        if not self.IsZoomable():
            
            return
            
        
        if self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ] == 1.0 and self._current_zoom == 1.0:
            
            return
            
        
        if self._current_zoom == 1.0:
            
            new_zoom = self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]

            self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_CANVAS
            
        else:
            
            new_zoom = 1.0
            
            self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_100
        
        self._TryToChangeZoom( new_zoom, zoom_center_type_override = zoom_center_type_override )
        
        if new_zoom <= self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]:
            
            self.ResetCenterPosition()

    def ZoomSwitchCanvasThenFill( self, zoom_center_type_override = None ):
        
        if not self.IsZoomable():
            
            return
            
        
        if self._current_zoom == 1.0:
            
            new_zoom = self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]

            self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_CANVAS
            
        elif self._current_zoom_type == MEDIA_VIEWER_ZOOM_TYPE_CANVAS:
            
            new_zoom = self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_FILL_AUTO ]
            
            self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_FILL_AUTO
            
        else:
            
            new_zoom = 1.0

            self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_100
            
        
        self._TryToChangeZoom( new_zoom, zoom_center_type_override = zoom_center_type_override )
        
        self.ResetCenterPosition()
        
    
    def ZoomSwitch100Max( self ):
        
        self.ZoomSwitchMax( 1.0 )
        
    
    def ZoomSwitchCanvasMax( self ):
        
        self.ZoomSwitchMax( self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ] )
        
    
    def ZoomSwitchMax( self, switch_base: float ):
        
        if not self.IsZoomable():
            
            return
            
        
        if self._current_zoom == switch_base:
            
            possible_zooms = CG.client_controller.new_options.GetMediaZooms()
            
            max_zoom = max( possible_zooms )
            
            ( media_scale_up, media_scale_down, preview_scale_up, preview_scale_down, exact_zooms_only, scale_up_quality, scale_down_quality ) = CG.client_controller.new_options.GetMediaZoomOptions( self._media.GetMime() )
            
            if exact_zooms_only:
                
                exact_zoom = 1.0
                
                while exact_zoom * 2 <= max_zoom:
                    
                    exact_zoom *= 2
                    
                
                max_zoom = exact_zoom
                
            
            new_zoom = max_zoom

            self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_CANVAS
            
        else:
            
            new_zoom = switch_base

            self._current_zoom_type = MEDIA_VIEWER_ZOOM_TYPE_100
            
        
        self._TryToChangeZoom( new_zoom )
        
        if new_zoom == switch_base:
            
            self.ResetCenterPosition()
            
        
    def ZoomToZoomPercent ( self, new_zoom, zoom_center_type_override = None  ):
        
        self._TryToChangeZoom( new_zoom, zoom_center_type_override )
        
    
    def ZoomToZoomType( self, zoom_type = None ):
        
        if zoom_type is None:
            
            zoom_type = self._current_zoom_type
            
        
        if self._media is None:
            
            return
            
        
        # set up canvas zoom
        
        canvas_size = self.parentWidget().size()
        
        my_dpr = self.devicePixelRatio()
        
        ( media_show_action, media_start_paused, media_start_with_embed ) = ClientMedia.GetShowAction( self._media.GetMediaResult(), self._canvas_type )
        
        self._zoom_types_to_zooms = CalculateCanvasZooms( canvas_size, self._canvas_type, my_dpr, self._media, media_show_action, rotation = self._rotation )
        
        self._current_zoom_type = zoom_type
        
        self._SetZoom( self._zoom_types_to_zooms[ self._current_zoom_type ] )
        
    
    def SaveZoomTimestamp( self ) -> bool:
        
        # the current zoom, at the current point in playback. returns False if we are not at a point in playback
        if self._media is None or not self._does_zoom_timestamps or not self.CurrentlyPresentingMediaWithDuration():
            
            return False
            
        
        frame_start_and_duration = self._GetCurrentFrameStartAndDurationMS()
        
        if frame_start_and_duration is None:
            
            return False
            
        
        ( frame_start_ms, frame_duration_ms ) = frame_start_and_duration
        
        # the zoom happens as the frame on screen comes up
        timestamp_ms = ConvertFrameStartToPlaybackPointMS( frame_start_ms )
        
        canvas_zoom = self._zoom_types_to_zooms[ MEDIA_VIEWER_ZOOM_TYPE_CANVAS ]
        
        if canvas_zoom <= 0:
            
            return False
            
        
        # saved relative to the zoom that fits the file in the window, and with the pan as the part of the file in the middle of the window, so it follows the window's size
        canvas_size = self.parentWidget().size()
        my_pos = self.pos()
        my_size = self.size()
        
        ( center_x, center_y ) = GetZoomCenter( ( canvas_size.width(), canvas_size.height() ), ( my_pos.x(), my_pos.y() ), ( my_size.width(), my_size.height() ) )
        
        zoom_timestamp = ( timestamp_ms, self._current_zoom / canvas_zoom, center_x, center_y )
        
        # one at the same point is replaced
        zoom_timestamps = [ existing for existing in self._zoom_timestamps if existing[0] != timestamp_ms ]
        
        zoom_timestamps.append( zoom_timestamp )
        
        self._SaveZoomTimestamps( zoom_timestamps )
        
        # we are already there, so there is nothing to zoom to
        self._current_zoom_timestamp = zoom_timestamp
        self._current_zoom_timestamp_needs_reapply = False
        
        return True
        
    
    def SupportsScriptedEvents( self ) -> bool:
        
        return self._media is not None and self._does_scripted_events and MediaHasPlayback( self._media )
        
    
    def SupportsSegments( self ) -> bool:
        
        return self._media is not None and self._does_segments and self._media.GetMime() in HC.VIDEO and MediaHasPlayback( self._media )
        
    
    def SupportsZoomTimestamps( self ) -> bool:
        
        return self._media is not None and self._does_zoom_timestamps and MediaHasPlayback( self._media )
        
    
    def TakeSnapshot( self, path: str, callback: typing.Callable[ [ Exception | None ], None ] ):
        
        # saves the current frame to path as a png. callback is called from a worker thread when that is done, with an error if it did not work
        if not self.CanTakeSnapshot():
            
            CG.client_controller.CallToThread( callback, Exception( 'This media has no frame to take a snapshot of!' ) )
            
            return
            
        
        if isinstance( self._media_window, Animation ):
            
            # the native renderer works in the background and calls back for itself
            self._media_window.TakeSnapshot( path, callback )
            
            return
            
        
        # mpv and Qt are quick, so they save it right now, while this frame is still up
        try:
            
            self._media_window.TakeSnapshot( path )
            
        except Exception as e:
            
            CG.client_controller.CallToThread( callback, e )
            
            return
            
        
        CG.client_controller.CallToThread( callback, None )
        
        
    
    def TIMERAnimationUpdate( self ):
        
        self._CheckPlaybackSkips()
        
        self._CheckZoomTimestamps()
        
        self._CheckScriptedEvents()
        
    
    def TIMERUIUpdate( self ):
        
        self._ShowHideControlBar()
        self._UpdateWindowAlwaysOnTop( wait_for_double_click = True )
        
    

class EmbedButton( QW.QWidget ):
    
    def __init__( self, parent, background_colour_generator ):
        
        super().__init__( parent )
        
        self._background_colour_generator = background_colour_generator
        
        self._media = None
        
        self._thumbnail_qt_pixmap = None
        
        self.setCursor( QG.QCursor( QC.Qt.CursorShape.PointingHandCursor ) )
        
        CG.client_controller.sub( self, 'update', 'notify_new_colourset' )
        CG.client_controller.sub( self, 'update', 'notify_new_stylesheet' )
        
    
    def _Redraw( self, painter ):
        
        my_size = self.size()
        
        my_width = my_size.width()
        my_height = my_size.height()
        
        center_x = my_width // 2
        center_y = my_height // 2
        radius = min( 50, center_x, center_y ) - 5
        
        new_options = CG.client_controller.new_options
        
        colour = self._background_colour_generator.GetColour()
        
        painter.setBackground( QG.QBrush( colour ) )
        
        painter.eraseRect( painter.viewport() )
        
        if self._thumbnail_qt_pixmap is not None:
            
            scale = my_width / self._thumbnail_qt_pixmap.width()
            
            painter.setTransform( QG.QTransform().scale( scale, scale ) )
            
            painter.drawPixmap( 0, 0, self._thumbnail_qt_pixmap )
            
            painter.setTransform( QG.QTransform().scale( 1.0, 1.0 ) )
            
        
        painter.setBrush( QG.QBrush( QG.QPalette().color( QG.QPalette.ColorRole.Button ) ) )
        
        painter.drawEllipse( QC.QPointF( center_x, center_y ), radius, radius )
        
        painter.setBrush( QG.QBrush( QG.QPalette().color( QG.QPalette.ColorRole.Window ) ) )
        
        # play symbol is a an equilateral triangle
        
        triangle_side = radius * 0.8
        
        half_triangle_side = int( triangle_side // 2 )
        
        cos30 = 0.866
        
        triangle_width = triangle_side * cos30
        
        third_triangle_width = int( triangle_width // 3 )
        
        points = []
        
        points.append( QC.QPoint( center_x - third_triangle_width, center_y - half_triangle_side ) )
        points.append( QC.QPoint( center_x + third_triangle_width * 2, center_y ) )
        points.append( QC.QPoint( center_x - third_triangle_width, center_y + half_triangle_side ) )
        
        painter.drawPolygon( QG.QPolygon( points ) )
        
        #
        
        painter.setPen( QG.QPen( QG.QPalette().color( QG.QPalette.ColorRole.Shadow ) ) )

        painter.setBrush( QC.Qt.BrushStyle.NoBrush )
        
        painter.drawRect( 0, 0, my_width, my_height )
        
    
    def ClearMedia( self ):
        
        self.SetMedia( None )
        
    
    def paintEvent( self, event ):
        
        try:
            
            painter = QG.QPainter( self )
            
            self._Redraw( painter )
            
        except Exception as e:
            
            ClientGUIExceptionHandling.HandlePaintEventException( self, e )
            
        
    
    def SetBackgroundColourGenerator( self, background_colour_generator ):
        
        self._background_colour_generator = background_colour_generator
        
    
    def SetMedia( self, media ):
        
        self._media = media
        
        if self._media is None:
            
            needs_thumb = False
            
        else:
            
            needs_thumb = self._media.GetLocationsManager().IsLocal() and self._media.GetMime() in HC.MIMES_WITH_THUMBNAILS
            
        
        if needs_thumb:
            
            display_media_result = self._media.GetDisplayMediaResult()
            
            if display_media_result is None:
                
                self._thumbnail_qt_pixmap = None
                
            else:
                
                thumbnail_path = CG.client_controller.client_files_manager.GetThumbnailPath( display_media_result )
                
                thumbnail_mime = HydrusFileHandling.GetThumbnailMime( thumbnail_path )
                
                self._thumbnail_qt_pixmap = ClientRendering.GenerateHydrusBitmap( thumbnail_path, thumbnail_mime ).GetQtPixmap()
                
                self.update()
                
            
        else:
            
            self._thumbnail_qt_pixmap = None
            
        
    

class OpenExternallyPanel( QW.QWidget ):
    
    def __init__( self, parent, media ):
        
        super().__init__( parent )
        
        self._new_options = CG.client_controller.new_options
        
        self._media = media
        
        vbox = QP.VBoxLayout()
        
        if self._media.GetLocationsManager().IsLocal():
            
            display_media_result = media.GetDisplayMediaResult()
            
            if display_media_result is not None:
                
                qt_pixmap = CG.client_controller.thumbnails_cache.GetThumbnail( display_media_result ).GetQtPixmap()
                
                thumbnail_dpr_percent = CG.client_controller.new_options.GetInteger( 'thumbnail_dpr_percent' )
                
                if thumbnail_dpr_percent != 100:
                    
                    qt_pixmap.setDevicePixelRatio( thumbnail_dpr_percent / 100 )
                    
                
                if qt_pixmap.width() > OPEN_EXTERNALLY_MAX_THUMBNAIL_SIZE[0] or qt_pixmap.height() > OPEN_EXTERNALLY_MAX_THUMBNAIL_SIZE[1]:
                    
                    qt_pixmap.scaled( OPEN_EXTERNALLY_MAX_THUMBNAIL_SIZE[0], OPEN_EXTERNALLY_MAX_THUMBNAIL_SIZE[1], QC.Qt.AspectRatioMode.KeepAspectRatio, QC.Qt.TransformationMode.SmoothTransformation )
                    
                
                thumbnail_window = QW.QLabel( self, pixmap = qt_pixmap )
                
                QP.AddToLayout( vbox, thumbnail_window, CC.FLAGS_CENTER )
                
            
        
        m_text = HC.mime_string_lookup[ media.GetMime() ]
        
        button = QW.QPushButton( 'open {} externally'.format( m_text ), self )
        
        button.setFocusPolicy( QC.Qt.FocusPolicy.NoFocus )
        
        QP.AddToLayout( vbox, button, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.setLayout( vbox )
        
        self.setCursor( QG.QCursor( QC.Qt.CursorShape.PointingHandCursor ) )
        
        button.clicked.connect( self.LaunchFile )
        
    
    def mousePressEvent( self, event ):
        
        if not ( event.modifiers() & ( QC.Qt.KeyboardModifier.ShiftModifier | QC.Qt.KeyboardModifier.ControlModifier | QC.Qt.KeyboardModifier.AltModifier ) ) and event.button() == QC.Qt.MouseButton.LeftButton:
            
            self.LaunchFile()
            
        else:
            
            event.ignore()
            
        
    
    def LaunchFile( self ):
        
        try:
            
            ClientGUIExecutableActions.OpenExternallySingleFileDefault( self, self._media.GetMediaResult() )
            
        except Exception as e:
            
            ClientGUIDialogsMessage.ShowInformation( self, f'Sorry, could not open that file: {e}' )
            
        
    

class StaticImage( CAC.ApplicationCommandProcessorMixin, QW.QWidget ):
    
    launchMediaViewer = QC.Signal()
    readyForNeighbourPrefetch = QC.Signal()
    
    def __init__( self, parent, canvas_type, background_colour_generator ):
        
        super().__init__( parent )
        
        self._canvas_type = canvas_type
        self._background_colour_generator = background_colour_generator
        
        if HC.PLATFORM_MACOS and not HG.macos_antiflicker_test:
            
            self.setAttribute( QC.Qt.WidgetAttribute.WA_OpaquePaintEvent, True )
            
        
        # pass up un-button-pressed mouse moves to parent, which wants to do cursor show/hide
        self.setMouseTracking( True )
        
        self._media = None
        
        self._image_renderer = None
        
        self._last_device_pixel_ratio = self.devicePixelRatio()
        
        self._image_tiles_cache = CG.client_controller.image_tiles_cache
        
        self._canvas_tiles = {}
        
        self._is_rendered = False
        
        self._raw_canvas_tile_size = QC.QSize( 768, 768 )
        self._device_canvas_tile_size = self._raw_canvas_tile_size / self._last_device_pixel_ratio
        
        self._zoom = 1.0
        
        # degrees clockwise. we are the size of the box the turned image fits in. a turned image is drawn in one go, not in tiles
        self._rotation = 0
        self._rotated_pixmap = None
        self._rotated_pixmap_size = None
        
        if self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES:
            
            shortcut_set = 'media_viewer_media_window'
            
        else:
            
            shortcut_set = 'preview_media_window'
            
        
        self._my_shortcut_handler = ClientGUIShortcuts.ShortcutsHandler( self, self, [ shortcut_set ], catch_mouse = True )
        
        CG.client_controller.sub( self, 'NotifyImageTileCacheCleared', 'clear_image_tile_cache' )
        CG.client_controller.sub( self, 'NotifyImageCacheCleared', 'clear_image_cache' )
        
    
    def _ClearCanvasTileCache( self ):
        
        my_raw_size = self._GetRawPixelSize()
        
        if self._media is None or self.width() == 0 or self.height() == 0:
            
            self._zoom = 1.0
            tile_dimension = 0
            
        else:
            
            ( media_width, media_height ) = self._media.GetResolution()
            
            self._zoom = my_raw_size.width() / media_width
            
            # it is most convenient to have tiles that line up with the current zoom ratio
            # 768 is a convenient size for meaty GPU blitting, but as a number it doesn't make for nice multiplication
            
            # a 'nice' size is one that divides nicely by our zoom, so that integer translations between canvas and native res aren't losing too much in the float remainder
            
            # the trick of going ( 123456 // 16 ) * 16 to give you a nice multiple of 16 does not work with floats like 1.4 lmao.
            # what we can do instead is phrase 1.4 as 7/5 and use 7 as our int. any number cleanly divisible by 7 is cleanly divisible by 1.4
            
            ideal_tile_dimension = CG.client_controller.new_options.GetInteger( 'ideal_tile_dimension' )
            
            nice_number = HydrusData.GetNicelyDivisibleNumberForZoom( self._zoom / self.devicePixelRatio(), ideal_tile_dimension )
            
            if nice_number == -1:
                
                # we are in extreme zoom land. nice multiples are impossible with reasonable size tiles, so we'll have to settle for some problems
                # a future solution is to get a bigger zoom and scale down
                # a future solution is to just make overlapping screen covering tiles and never deal with seams lmao
                
                tile_dimension = ideal_tile_dimension
                
            else:
                
                tile_dimension = ( ideal_tile_dimension // nice_number ) * nice_number
                
            
            tile_dimension = max( min( tile_dimension, 2048 ), 1 )
            
            if HG.canvas_tile_outline_mode:
                
                HydrusData.ShowText( '{} from zoom {} and nice number {}'.format( tile_dimension, self._zoom, nice_number ) )
                
            
        
        self._raw_canvas_tile_size = QC.QSize( tile_dimension, tile_dimension )
        
        self._canvas_tiles = {}
        
        self._rotated_pixmap = None
        self._rotated_pixmap_size = None
        
        self._last_device_pixel_ratio = self.devicePixelRatio()
        
        self._device_canvas_tile_size = self._raw_canvas_tile_size / self._last_device_pixel_ratio
        
        self._is_rendered = False
        
    
    def _DrawBackground( self, painter, topLeftOffset = None ):
        
        if self._background_colour_generator.CanDoTransparencyCheckerboard() and self._media is not None and self._media.GetFileInfoManager().has_transparency:
            
            if CG.client_controller.new_options.GetBoolean( 'draw_transparency_checkerboard_as_greenscreen' ):
                
                neon_greenscreen = QG.QColor( 34, 255, 0 )
                
                painter.setBackground( QG.QBrush( neon_greenscreen ) )
                
                painter.eraseRect( painter.viewport() )
                
            else:
                
                light_grey = QG.QColor( 237, 237, 237 )
                dark_grey = QG.QColor( 222, 222, 222 )
                
                painter.setBackground( QG.QBrush( light_grey ) )
                
                painter.eraseRect( painter.viewport() )
                
                # 16x16 boxes, light grey in top right
                BOX_LENGTH = int( 16 * self.devicePixelRatio() )
                
                # there's a way to do this with viewports or transforms or something, but I don't know mate
                if topLeftOffset is None:
                    
                    rectTopLeftAdjust = QC.QPoint( 0, 0 )
                    
                else:
                    
                    x = topLeftOffset.x() % ( BOX_LENGTH * 2 )
                    y = topLeftOffset.y() % ( BOX_LENGTH * 2 )
                    
                    x_adjust = - x if x > 0 else 0
                    y_adjust = - y if y > 0 else 0
                    
                    rectTopLeftAdjust = QC.QPoint( x_adjust, y_adjust )
                    
                
                painter_width = painter.viewport().width() + abs( rectTopLeftAdjust.x() )
                painter_height = painter.viewport().height() + abs( rectTopLeftAdjust.y() )
                
                num_cols = painter_width // BOX_LENGTH
                
                if painter_width % BOX_LENGTH > 0:
                    
                    num_cols += 1
                    
                
                num_rows = painter_height // BOX_LENGTH
                
                if painter_height % BOX_LENGTH > 0:
                    
                    num_rows += 1
                    
                
                painter.setBrush( QG.QBrush( dark_grey ) )
                painter.setPen( QG.QPen( QC.Qt.PenStyle.NoPen ) )
                
                for y_index in range( num_rows ):
                    
                    for x_index in range( num_cols ):
                        
                        if ( x_index + y_index ) % 2 == 1:
                            
                            rect = QC.QRect( x_index * BOX_LENGTH, y_index * BOX_LENGTH, BOX_LENGTH, BOX_LENGTH )
                            
                            rect.moveTo( rect.topLeft() + rectTopLeftAdjust )
                            
                            if painter.viewport().intersects( rect ):
                                
                                painter.drawRect( rect )
                                
                            
                        
                    
                
            
            return
            
        
        colour = self._background_colour_generator.GetColour()
        
        painter.setBackground( QG.QBrush( colour ) )
        
        painter.eraseRect( painter.viewport() )
        
    
    def _DrawTile( self, tile_coordinate ):
        
        ( native_clip_rect, raw_canvas_clip_rect ) = self._GetRawClipRectsFromTileCoordinates( tile_coordinate )
        
        raw_width = raw_canvas_clip_rect.width()
        raw_height = raw_canvas_clip_rect.height()
        
        tile_pixmap = CG.client_controller.bitmap_manager.GetQtPixmap( raw_width, raw_height )
        
        painter = QG.QPainter( tile_pixmap )
        
        self._DrawBackground( painter, topLeftOffset = raw_canvas_clip_rect.topLeft() )
        
        tile = self._image_tiles_cache.GetTile( self._image_renderer, self._media.GetMediaResult(), native_clip_rect, raw_canvas_clip_rect.size() )
        
        painter.drawPixmap( 0, 0, tile.qt_pixmap )
        
        if HG.canvas_tile_outline_mode:
            
            painter.setPen( QG.QPen( QG.QColor( 0, 127, 255 ) ) )
            painter.setBrush( QC.Qt.BrushStyle.NoBrush )
            
            painter.drawRect( tile_pixmap.rect() )
            
        
        self._canvas_tiles[ tile_coordinate ] = ( tile_pixmap, raw_canvas_clip_rect.topLeft() )
        
    
    def _GetRawClipRectsFromTileCoordinates( self, tile_coordinate ) -> tuple[ QC.QRect, QC.QRect ]:
        
        ( tile_x, tile_y ) = tile_coordinate
        
        my_raw_size = self._GetRawPixelSize()
        
        my_raw_width = my_raw_size.width()
        my_raw_height = my_raw_size.height()
        
        ( normal_raw_canvas_width, normal_raw_canvas_height ) = ( self._raw_canvas_tile_size.width(), self._raw_canvas_tile_size.height() )
        
        ( media_width, media_height ) = self._media.GetResolution()
        
        raw_canvas_x = tile_x * self._raw_canvas_tile_size.width()
        raw_canvas_y = tile_y * self._raw_canvas_tile_size.height()
        
        raw_canvas_topLeft = QC.QPoint( raw_canvas_x, raw_canvas_y )
        
        raw_canvas_width = normal_raw_canvas_width
        
        if raw_canvas_x + normal_raw_canvas_width > my_raw_width:
            
            # this is the rightmost tile and should be shrunk
            
            raw_canvas_width = my_raw_width % normal_raw_canvas_width
            
        
        raw_canvas_height = normal_raw_canvas_height
        
        if raw_canvas_y + normal_raw_canvas_height > my_raw_height:
            
            # this is the bottommost tile and should be shrunk
            
            raw_canvas_height = my_raw_height % normal_raw_canvas_height
            
        
        raw_canvas_width = max( 1, raw_canvas_width )
        raw_canvas_height = max( 1, raw_canvas_height )
        
        # if we are the last row/column our size is not this!
        
        raw_canvas_size = QC.QSize( raw_canvas_width, raw_canvas_height )
        
        raw_canvas_clip_rect = QC.QRect( raw_canvas_topLeft, raw_canvas_size )
        
        native_clip_rect = QC.QRect( raw_canvas_topLeft / self._zoom, raw_canvas_size / self._zoom )
        
        # dealing with rounding errors with zoom calc
        if native_clip_rect.width() + native_clip_rect.x() > media_width:
            
            native_clip_rect.setWidth( media_width - native_clip_rect.x() )
            
        
        if native_clip_rect.height() + native_clip_rect.y() > media_height:
            
            native_clip_rect.setHeight( media_height - native_clip_rect.y() )
            
        
        if native_clip_rect.width() == 0:
            
            native_clip_rect.setX( max( native_clip_rect.x() - 1, 0 ) )
            native_clip_rect.setWidth( 1 )
            
        
        if native_clip_rect.height() == 0:
            
            native_clip_rect.setY( max( native_clip_rect.y() - 1, 0 ) )
            native_clip_rect.setHeight( 1 )
            
        
        return ( native_clip_rect, raw_canvas_clip_rect )
        
    
    def _GetRawPixelSize( self ) -> QC.QSize:
        
        return self.size() * self.devicePixelRatio()
        
    
    def _PaintRotated( self, painter: QG.QPainter ):
        
        my_dpr = self.devicePixelRatio()
        
        ( media_width, media_height ) = self._media.GetResolution()
        
        ( raw_width, raw_height ) = GetUnrotatedSizeInBoundingSize( self.width() * my_dpr, self.height() * my_dpr, media_width, media_height, self._rotation )
        
        raw_size = QC.QSize( max( 1, round( raw_width ) ), max( 1, round( raw_height ) ) )
        
        if self._rotated_pixmap is None or self._rotated_pixmap_size != raw_size:
            
            tile = self._image_tiles_cache.GetTile( self._image_renderer, self._media.GetMediaResult(), QC.QRect( 0, 0, media_width, media_height ), raw_size )
            
            self._rotated_pixmap = tile.qt_pixmap
            self._rotated_pixmap_size = raw_size
            
        
        # the corners the turned image leaves are the background colour
        painter.setBackground( QG.QBrush( self._background_colour_generator.GetColour() ) )
        
        painter.eraseRect( painter.viewport() )
        
        painter.setRenderHint( QG.QPainter.RenderHint.SmoothPixmapTransform, True )
        
        painter.translate( self.width() / 2, self.height() / 2 )
        painter.rotate( self._rotation )
        
        ( width, height ) = ( raw_size.width() / my_dpr, raw_size.height() / my_dpr )
        
        painter.drawPixmap( QC.QRectF( - width / 2, - height / 2, width, height ), self._rotated_pixmap, QC.QRectF( self._rotated_pixmap.rect() ) )
        
        if not self._is_rendered:
            
            self.readyForNeighbourPrefetch.emit()
            
            self._is_rendered = True
            
        
    
    def _GetTileCoordinateFromPoint( self, device_pos: QC.QPoint ):
        
        raw_pos = device_pos * self.devicePixelRatio()
        
        tile_x = raw_pos.x() // self._raw_canvas_tile_size.width()
        tile_y = raw_pos.y() // self._raw_canvas_tile_size.height()
        
        return ( tile_x, tile_y )
        
    
    def _GetTileCoordinatesInView( self, device_rect: QC.QRect ):
        
        if self.width() == 0 or self.height() == 0 or self._raw_canvas_tile_size.width() == 0 or self._raw_canvas_tile_size.height() == 0:
            
            return []
            
        
        topLeft_tile_coordinate = self._GetTileCoordinateFromPoint( device_rect.topLeft() )
        bottomRight_tile_coordinate = self._GetTileCoordinateFromPoint( device_rect.bottomRight() )
        
        i = itertools.product(
            range( topLeft_tile_coordinate[0], bottomRight_tile_coordinate[0] + 1 ),
            range( topLeft_tile_coordinate[1], bottomRight_tile_coordinate[1] + 1 )
    )
        
        return list( i )
        
    
    def ClearMedia( self ):
        
        self._media = None
        self._image_renderer = None
        
        self._ClearCanvasTileCache()
        
        self.update()
        
    
    def paintEvent( self, event ):
        
        try:
            
            if self.devicePixelRatio() != self._last_device_pixel_ratio:
                
                self._ClearCanvasTileCache()
                
            
            painter = QG.QPainter( self )
            
            if self._image_renderer is None or not self._image_renderer.IsReady():
                
                self._DrawBackground( painter )
                
                return
                
            
            if self._rotation != 0:
                
                self._PaintRotated( painter )
                
                return
                
            
            dirty_tile_coordinates = self._GetTileCoordinatesInView( event.rect() )
            
            for dirty_tile_coordinate in dirty_tile_coordinates:
                
                if dirty_tile_coordinate not in self._canvas_tiles:
                    
                    self._DrawTile( dirty_tile_coordinate )
                    
                
            
            my_dpr = self.devicePixelRatio()
            
            visible_bounding_rect = self.visibleRegion().boundingRect()
            visible_bounding_rect_topLeft = visible_bounding_rect.topLeft()
            
            for dirty_tile_coordinate in dirty_tile_coordinates:
                
                ( tile, raw_pos ) = self._canvas_tiles[ dirty_tile_coordinate ]
                
                raw_pos_f = QC.QPointF( raw_pos )
                
                device_pos_f = typing.cast( QC.QPointF, raw_pos_f / my_dpr )
                
                tile.setDevicePixelRatio( my_dpr )
                
                adjust_pos_f = QC.QPointF()
                
                if my_dpr % 1 != 0.0:
                    
                    #
                    #   ,ad8888ba,           88888888ba  88                       88
                    #  d8"'    `"8b    ,d    88      "8b ""                       88
                    # d8'        `8b   88    88      ,8P                          88
                    # 88          88 MM88MMM 88aaaaaa8P' 88 8b,     ,d8 ,adPPYba, 88 ,adPPYba,
                    # 88          88   88    88""""""'   88  `Y8, ,8P' a8P_____88 88 I8[    ""
                    # Y8,    "88,,8P   88    88          88   )888(   8PP""""""" 88  `"Y8ba,
                    #  Y8a.    Y88P    88,   88          88  ,d8" "8b, "8b,   ,aa 88 aa    ]8I
                    #   `"Y8888Y"Y8a   "Y888 88          88 8P'     `Y8 `"Ybbd8"' 88 `"YbbdP"'
                    #
                    
                    # Ok, what is going on here is that if you have an ugly UI scale, like 125%, when a bitmap has to be drawn starting offscreen, Qt rounds the starting coordinate down every n pixels of offset
                    # something gets cut off somewhere, I guess every 5 pixels for 125%, 3 for 150%, and you get a blank/white line on the first set of tiles to be stitched as you drag around, flickering every n pixels
                    # therefore, we engage in some sordid hexxing here: if the current tile starts offscreen, we move it on a real pixel
                    # I haven't seen massive warping here, but maybe it stands out on cleaner vectors on low res displays. if so, I'll revisit and try to determine the actual nth pixel to activate this
                    
                    if device_pos_f.x() < visible_bounding_rect_topLeft.x():
                        
                        adjust_pos_f.setX( 1 / my_dpr )
                        
                    
                    if device_pos_f.y() < visible_bounding_rect_topLeft.y():
                        
                        adjust_pos_f.setY( 1 / my_dpr )
                        
                    
                
                painter.drawPixmap( device_pos_f + adjust_pos_f, tile )
                
                tile.setDevicePixelRatio( 1.0 )
                
            
            all_visible_tile_coordinates = self._GetTileCoordinatesInView( visible_bounding_rect )
            
            deletee_tile_coordinates = set( self._canvas_tiles.keys() ).difference( all_visible_tile_coordinates )
            
            for deletee_tile_coordinate in deletee_tile_coordinates:
                
                del self._canvas_tiles[ deletee_tile_coordinate ]
                
            
            if not self._is_rendered:
                
                self.readyForNeighbourPrefetch.emit()
                
                self._is_rendered = True
                
            
        except Exception as e:
            
            ClientGUIExceptionHandling.HandlePaintEventException( self, e )
            
        
    
    def resizeEvent( self, event ):
        
        self._ClearCanvasTileCache()
        
    
    def showEvent( self, event ):
        
        self._ClearCanvasTileCache()
        
    
    def IsRendered( self ):
        
        return self._is_rendered
        
    
    def NotifyImageCacheCleared( self ):
        
        if self._media is not None:
            
            self._ClearCanvasTileCache()
            
            images_cache = CG.client_controller.images_cache
            
            self._image_renderer = images_cache.GetImageRenderer( self._media.GetMediaResult() )
            
            if not self._image_renderer.IsReady():
                
                CG.client_controller.gui.RegisterAnimationUpdateWindow( self )
                
            
            self.update()
            
        
    
    def NotifyImageTileCacheCleared( self ):
        
        if self._media is not None:
            
            self._ClearCanvasTileCache()
            
            self.update()
            
        
    
    def ProcessApplicationCommand( self, command: CAC.ApplicationCommand ) -> bool:
        
        command_matched = True
        
        if command.IsSimpleCommand():
            
            action = command.GetSimpleAction()
            
            if action == CAC.SIMPLE_CLOSE_MEDIA_VIEWER and self._canvas_type in CC.CANVAS_MEDIA_VIEWER_TYPES:
                
                self.window().close()
                
            elif action == CAC.SIMPLE_LAUNCH_MEDIA_VIEWER and self._canvas_type == CC.CANVAS_PREVIEW:
                
                self.launchMediaViewer.emit()
                
            else:
                
                command_matched = False
                
            
        else:
            
            command_matched = False
            
        
        return command_matched
        
    
    def SetBackgroundColourGenerator( self, background_colour_generator ):
        
        self._background_colour_generator = background_colour_generator
        
    
    def SetRotation( self, rotation: int ):
        
        if rotation == self._rotation:
            
            return
            
        
        self._rotation = rotation
        
        self._ClearCanvasTileCache()
        
        self.update()
        
    
    def SetMedia( self, media ):
        
        if media == self._media:
            
            return
            
        
        self._ClearCanvasTileCache()
        
        self._media = media
        
        images_cache = CG.client_controller.images_cache
        
        self._image_renderer = images_cache.GetImageRenderer( self._media.GetMediaResult() )
        
        if not self._image_renderer.IsReady():
            
            CG.client_controller.gui.RegisterAnimationUpdateWindow( self )
            
        
        self.update()
        
    
    def TIMERAnimationUpdate( self ):
        
        try:
            
            if self._image_renderer is None or self._image_renderer.IsReady():
                
                self.update()
                
                CG.client_controller.gui.UnregisterAnimationUpdateWindow( self )
                
            
        except Exception as e:
            
            CG.client_controller.gui.UnregisterAnimationUpdateWindow( self )
            
            raise
            
        
    

import os
import typing

from hydrus.core import HydrusExceptions
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientAPI
from hydrus.client import ClientGlobals as CG
from hydrus.client.media import ClientMediaPlaybackFreezes
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResources

# what the media viewer remembers for each file: how it is turned, zoomed, and panned, its position timestamps, playback skips, freezes, segments, scripted events, and the image drawn over it
# times are ms into the file. a center is [ x, y ], the point of the file in the middle of the window as a fraction of its width and height, and null means centered

def CheckCenter( name: str, center: typing.Any ) -> tuple[ float, float ] | None:
    
    if center is None:
        
        return None
        
    
    if not isinstance( center, list ) or len( center ) != 2:
        
        raise HydrusExceptions.BadRequestException( f'"{name}" has to be [ x, y ], or null for centered! "{center}" is not.' )
        
    
    return ( ClientLocalServerCore.CheckNumber( name, center[0] ), ClientLocalServerCore.CheckNumber( name, center[1] ) )
    

def CheckListOfObjects( name: str, value: typing.Any ) -> list[ dict ]:
    
    if not isinstance( value, list ) or False in ( isinstance( item, dict ) for item in value ):
        
        raise HydrusExceptions.BadRequestException( f'"{name}" has to be a list of Objects!' )
        
    
    return value
    

def CheckZoom( name: str, zoom: typing.Any ) -> float:
    
    zoom = ClientLocalServerCore.CheckNumber( name, zoom )
    
    if zoom <= 0:
        
        raise HydrusExceptions.BadRequestException( f'"{name}" has to be more than 0!' )
        
    
    return zoom
    

def ConvertCenterToJSON( center_x: float | None, center_y: float | None ) -> list[ float ] | None:
    
    if center_x is None or center_y is None:
        
        return None
        
    
    return [ center_x, center_y ]
    

def NormaliseRotation( rotation: float ) -> int:
    
    # whole degrees clockwise, 0 to 359, like the media viewer does it
    return int( round( rotation ) ) % 360
    

class HydrusResourceClientAPIRestrictedManageFileViewerData( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_EDIT_MEDIA_VIEWER_DATA )
        
    

class HydrusResourceClientAPIRestrictedManageFileViewerDataGetData( HydrusResourceClientAPIRestrictedManageFileViewerData ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hash = ClientLocalServerCore.ParseSingleHash( request )
        
        rotation = CG.client_controller.Read( 'file_viewer_rotation', hash )
        
        ( zoom, center ) = CG.client_controller.Read( 'file_viewer_zoom', hash )
        
        zoom_timestamp_rows = CG.client_controller.Read( 'file_zoom_timestamps', hash )
        
        playback_skips = CG.client_controller.Read( 'file_playback_skips', hash )
        
        playback_freezes = CG.client_controller.Read( 'file_playback_freezes', hash )

        segments = CG.client_controller.Read( 'file_segments', hash )
        
        scripted_events = CG.client_controller.Read( 'file_scripted_events', hash )
        
        image_overlay = CG.client_controller.Read( 'file_image_overlay', hash )
        
        if image_overlay is None:
            
            image_overlay_dict = None
            
        else:
            
            ( path, opacity, ( x, y, width, height ), locked, stretch ) = image_overlay
            
            image_overlay_dict = { 'path' : path, 'opacity' : opacity, 'x' : x, 'y' : y, 'width' : width, 'height' : height, 'locked' : locked, 'stretch' : stretch }
            
        
        body_dict = {
            'hash' : hash.hex(),
            'rotation' : NormaliseRotation( rotation ),
            'zoom' : {
                'zoom' : zoom,
                'center' : None if center is None else list( center )
            },
            # an old one, from before they were relative to the zoom that fits the file in the window, has zoom_is_relative false
            'position_timestamps' : [ { 'timestamp_ms' : timestamp_ms, 'zoom' : zoom, 'zoom_is_relative' : zoom_is_relative, 'center' : ConvertCenterToJSON( center_x, center_y ), 'rotation' : rotation } for ( timestamp_ms, zoom, zoom_is_relative, center_x, center_y, rotation ) in zoom_timestamp_rows ],
            'playback_skips' : [ { 'start_ms' : start_ms, 'end_ms' : end_ms } for ( start_ms, end_ms ) in playback_skips ],
            'playback_freezes' : [ { 'timestamp_ms' : timestamp_ms, 'duration_ms' : duration_ms } for ( timestamp_ms, duration_ms ) in sorted( playback_freezes ) ],
            'segments' : [ { 'timestamp_ms' : timestamp_ms, 'name' : name } for ( timestamp_ms, name ) in sorted( segments ) ],
            'scripted_events' : [ { 'timestamp_ms' : timestamp_ms, 'command' : command } for ( timestamp_ms, command ) in sorted( scripted_events ) ],
            'image_overlay' : image_overlay_dict
        }
        
        return ClientLocalServerCore.GenerateJSONResponse( request, body_dict )
        
    

class HydrusResourceClientAPIRestrictedManageFileViewerDataGetSavedZoomCounts( HydrusResourceClientAPIRestrictedManageFileViewerData ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        body_dict = {
            'num_files_with_saved_zoom' : CG.client_controller.Read( 'num_file_viewer_zooms' ),
            'num_files_with_position_timestamps' : CG.client_controller.Read( 'num_files_with_zoom_timestamps' )
        }
        
        return ClientLocalServerCore.GenerateJSONResponse( request, body_dict )
        
    

class HydrusResourceClientAPIRestrictedManageFileViewerDataResetAllZooms( HydrusResourceClientAPIRestrictedManageFileViewerData ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        # every file at once, like the 'reset all saved zooms' dialog
        clear_file_viewer_zooms = request.parsed_request_args.GetValue( 'saved_zooms', bool, default_value = False )
        clear_zoom_timestamps = request.parsed_request_args.GetValue( 'position_timestamps', bool, default_value = False )
        
        if not ( clear_file_viewer_zooms or clear_zoom_timestamps ):
            
            raise HydrusExceptions.BadRequestException( 'Please say what to reset, with "saved_zooms" and/or "position_timestamps" set to true!' )
            
        
        if clear_file_viewer_zooms:
            
            CG.client_controller.WriteSynchronous( 'clear_all_file_viewer_zooms' )
            
        
        if clear_zoom_timestamps:
            
            CG.client_controller.WriteSynchronous( 'clear_all_file_zoom_timestamps' )
            
        
        # open media viewers hold on to what they loaded for their current file
        CG.client_controller.pub( 'reset_all_file_zooms', clear_file_viewer_zooms, clear_zoom_timestamps )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, {} )
        
    

class HydrusResourceClientAPIRestrictedManageFileViewerDataSetImageOverlay( HydrusResourceClientAPIRestrictedManageFileViewerData ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hash = ClientLocalServerCore.ParseSingleHash( request )
        
        # null takes it away
        image_overlay_dict = request.parsed_request_args.GetValueOrNone( 'image_overlay', dict )
        
        if image_overlay_dict is None:
            
            image_overlay = None
            
        else:
            
            path = image_overlay_dict.get( 'path', None )
            
            if not isinstance( path, str ) or not os.path.isfile( path ):
                
                raise HydrusExceptions.BadRequestException( f'The image overlay needs a "path" to an image file on this computer! "{path}" is not one.' )
                
            
            opacity = ClientLocalServerCore.CheckNumber( 'opacity', image_overlay_dict.get( 'opacity', 1.0 ) )
            
            if not 0.0 <= opacity <= 1.0:
                
                raise HydrusExceptions.BadRequestException( '"opacity" has to be from 0 to 1!' )
                
            
            # fractions of the media viewer's size
            x = ClientLocalServerCore.CheckNumber( 'x', image_overlay_dict.get( 'x', 0.0 ) )
            y = ClientLocalServerCore.CheckNumber( 'y', image_overlay_dict.get( 'y', 0.0 ) )
            width = ClientLocalServerCore.CheckNumber( 'width', image_overlay_dict.get( 'width', 1.0 ) )
            height = ClientLocalServerCore.CheckNumber( 'height', image_overlay_dict.get( 'height', 1.0 ) )
            
            if width <= 0 or height <= 0:
                
                raise HydrusExceptions.BadRequestException( '"width" and "height" have to be more than 0!' )
                
            
            locked = image_overlay_dict.get( 'locked', False )
            stretch = image_overlay_dict.get( 'stretch', False )
            
            if not isinstance( locked, bool ) or not isinstance( stretch, bool ):
                
                raise HydrusExceptions.BadRequestException( '"locked" and "stretch" have to be true or false!' )
                
            
            image_overlay = ( path, opacity, ( x, y, width, height ), locked, stretch )
            
        
        CG.client_controller.WriteSynchronous( 'file_image_overlay', hash, image_overlay )
        
        # media viewers showing this file pick it up. none of them made the change
        CG.client_controller.pub( 'new_file_image_overlay', hash, image_overlay, None )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, {} )
        
    

class HydrusResourceClientAPIRestrictedManageFileViewerDataSetPlaybackFreezes( HydrusResourceClientAPIRestrictedManageFileViewerData ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hash = ClientLocalServerCore.ParseSingleHash( request )
        
        freeze_dicts = CheckListOfObjects( 'playback_freezes', request.parsed_request_args.GetValue( 'playback_freezes', list ) )
        
        freezes = []
        
        for freeze_dict in freeze_dicts:
            
            timestamp_ms = ClientLocalServerCore.CheckNonNegativeInt( 'timestamp_ms', freeze_dict.get( 'timestamp_ms', None ) )
            duration_ms = ClientLocalServerCore.CheckNonNegativeInt( 'duration_ms', freeze_dict.get( 'duration_ms', None ) )
            
            if not ClientMediaPlaybackFreezes.MIN_PLAYBACK_FREEZE_DURATION_MS <= duration_ms <= ClientMediaPlaybackFreezes.MAX_PLAYBACK_FREEZE_DURATION_MS:
                
                raise HydrusExceptions.BadRequestException( f'A freeze has to hold for {ClientMediaPlaybackFreezes.MIN_PLAYBACK_FREEZE_DURATION_MS}ms to {ClientMediaPlaybackFreezes.MAX_PLAYBACK_FREEZE_DURATION_MS}ms, not {duration_ms}ms!' )
                
            
            freezes.append( ( timestamp_ms, duration_ms ) )
            
        
        # one per point, and a later one for the same point wins, like the media viewer does it
        freezes = ClientMediaPlaybackFreezes.NormalisePlaybackFreezes( freezes )
        
        CG.client_controller.WriteSynchronous( 'file_playback_freezes', hash, freezes )
        
        CG.client_controller.pub( 'new_file_playback_freezes', hash, freezes )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'playback_freezes' : [ { 'timestamp_ms' : timestamp_ms, 'duration_ms' : duration_ms } for ( timestamp_ms, duration_ms ) in freezes ] } )
        


class HydrusResourceClientAPIRestrictedManageFileViewerDataSetPlaybackSkips( HydrusResourceClientAPIRestrictedManageFileViewerData ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        from hydrus.client.gui.canvas import ClientGUICanvasMedia
        
        hash = ClientLocalServerCore.ParseSingleHash( request )
        
        skip_dicts = CheckListOfObjects( 'playback_skips', request.parsed_request_args.GetValue( 'playback_skips', list ) )
        
        skips = []
        
        for skip_dict in skip_dicts:
            
            start_ms = ClientLocalServerCore.CheckNonNegativeInt( 'start_ms', skip_dict.get( 'start_ms', None ) )
            end_ms = ClientLocalServerCore.CheckNonNegativeInt( 'end_ms', skip_dict.get( 'end_ms', None ) )
            
            if start_ms >= end_ms:
                
                raise HydrusExceptions.BadRequestException( f'A playback skip has to start before it ends! {start_ms}ms is not before {end_ms}ms.' )
                
            
            skips.append( ( start_ms, end_ms ) )
            
        
        # overlapping or touching skips become one, like the media viewer does it
        skips = ClientGUICanvasMedia.MergePlaybackSkips( skips )
        
        CG.client_controller.WriteSynchronous( 'file_playback_skips', hash, skips )
        
        CG.client_controller.pub( 'new_file_playback_skips', hash, skips )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'playback_skips' : [ { 'start_ms' : start_ms, 'end_ms' : end_ms } for ( start_ms, end_ms ) in skips ] } )
        
    

class HydrusResourceClientAPIRestrictedManageFileViewerDataSetPositionTimestamps( HydrusResourceClientAPIRestrictedManageFileViewerData ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hash = ClientLocalServerCore.ParseSingleHash( request )
        
        position_timestamp_dicts = CheckListOfObjects( 'position_timestamps', request.parsed_request_args.GetValue( 'position_timestamps', list ) )
        
        timestamps_to_zoom_timestamps = {}
        
        for position_timestamp_dict in position_timestamp_dicts:
            
            timestamp_ms = ClientLocalServerCore.CheckNonNegativeInt( 'timestamp_ms', position_timestamp_dict.get( 'timestamp_ms', None ) )
            
            # relative to the zoom that fits the file in the window, so 1.0 is 'fit'
            zoom = CheckZoom( 'zoom', position_timestamp_dict.get( 'zoom', None ) )
            
            center = CheckCenter( 'center', position_timestamp_dict.get( 'center', None ) )
            
            ( center_x, center_y ) = ( None, None ) if center is None else center
            
            # null leaves the file turned however it is
            rotation = position_timestamp_dict.get( 'rotation', None )
            
            if rotation is not None:
                
                rotation = NormaliseRotation( ClientLocalServerCore.CheckNumber( 'rotation', rotation ) )
                
            
            # one per timestamp. a later one for the same time wins
            timestamps_to_zoom_timestamps[ timestamp_ms ] = ( timestamp_ms, zoom, center_x, center_y, rotation )
            
        
        zoom_timestamps = [ timestamps_to_zoom_timestamps[ timestamp_ms ] for timestamp_ms in sorted( timestamps_to_zoom_timestamps.keys() ) ]
        
        CG.client_controller.WriteSynchronous( 'file_zoom_timestamps', hash, zoom_timestamps )
        
        CG.client_controller.pub( 'new_file_zoom_timestamps', hash, zoom_timestamps )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, {} )
        
    

class HydrusResourceClientAPIRestrictedManageFileViewerDataSetRotation( HydrusResourceClientAPIRestrictedManageFileViewerData ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request )
        
        rotation = NormaliseRotation( ClientLocalServerCore.CheckNumber( 'rotation', request.parsed_request_args.GetValue( 'rotation', float ) ) )
        
        # a media viewer picks it up the next time it shows the file
        for hash in hashes:
            
            CG.client_controller.WriteSynchronous( 'file_viewer_rotation', hash, rotation )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'rotation' : rotation } )
        
    

class HydrusResourceClientAPIRestrictedManageFileViewerDataSetScriptedEvents( HydrusResourceClientAPIRestrictedManageFileViewerData ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        # these are shell commands that run on this computer, so they have a permission of their own, which 'permits everything' does not cover
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_EDIT_SCRIPTED_EVENTS )
        
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hash = ClientLocalServerCore.ParseSingleHash( request )
        
        scripted_event_dicts = CheckListOfObjects( 'scripted_events', request.parsed_request_args.GetValue( 'scripted_events', list ) )
        
        scripted_events = []
        
        for scripted_event_dict in scripted_event_dicts:
            
            timestamp_ms = ClientLocalServerCore.CheckNonNegativeInt( 'timestamp_ms', scripted_event_dict.get( 'timestamp_ms', None ) )
            
            command = scripted_event_dict.get( 'command', None )
            
            if not isinstance( command, str ) or command.strip() == '':
                
                raise HydrusExceptions.BadRequestException( 'A scripted event needs a "command"!' )
                
            
            scripted_events.append( ( timestamp_ms, command ) )
            
        
        scripted_events = sorted( scripted_events )
        
        CG.client_controller.WriteSynchronous( 'file_scripted_events', hash, scripted_events )
        
        # media viewers showing this file pick them up
        CG.client_controller.pub( 'new_file_scripted_events', hash, scripted_events )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, {} )
        
    

class HydrusResourceClientAPIRestrictedManageFileViewerDataSetSegments( HydrusResourceClientAPIRestrictedManageFileViewerData ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hash = ClientLocalServerCore.ParseSingleHash( request )
        
        segment_dicts = CheckListOfObjects( 'segments', request.parsed_request_args.GetValue( 'segments', list ) )
        
        segments = set()
        
        for segment_dict in segment_dicts:
            
            timestamp_ms = ClientLocalServerCore.CheckNonNegativeInt( 'timestamp_ms', segment_dict.get( 'timestamp_ms', None ) )
            
            name = segment_dict.get( 'name', None )
            
            if not isinstance( name, str ) or name.strip() == '':
                
                raise HydrusExceptions.BadRequestException( 'A segment needs a "name"!' )
                
            
            segments.add( ( timestamp_ms, name.strip() ) )
            
        
        # the media viewer loads them each time it shows the file
        CG.client_controller.WriteSynchronous( 'file_segments', hash, sorted( segments ) )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, {} )
        
    

class HydrusResourceClientAPIRestrictedManageFileViewerDataSetZoom( HydrusResourceClientAPIRestrictedManageFileViewerData ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request )
        
        # a null zoom is the normal default zoom, and a null center is centered. both null puts the file back to normal
        zoom = request.parsed_request_args.GetValueOrNone( 'zoom', float )
        
        if zoom is not None:
            
            zoom = CheckZoom( 'zoom', zoom )
            
        
        center = CheckCenter( 'center', request.parsed_request_args.GetValueOrNone( 'center', list ) )
        
        # a media viewer picks it up the next time it shows the file
        for hash in hashes:
            
            CG.client_controller.WriteSynchronous( 'file_viewer_zoom', hash, zoom, center )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, {} )
        
    

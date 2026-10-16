import json

from hydrus.core import HydrusExceptions
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientAPI
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientMediaViewerLayouts
from hydrus.client.media import ClientMediaSlideshows
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResources
from hydrus.client.networking.api import ClientLocalServerResourcesManagePlaylists

# opening media viewers, and saving where they are. these are windows in the client, so they go with 'manage pages', like get_media_viewers

class HydrusResourceClientAPIRestrictedManageMediaViewers( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_MANAGE_PAGES )
        
    

class HydrusResourceClientAPIRestrictedManageMediaViewersGetABRepeat( HydrusResourceClientAPIRestrictedManageMediaViewers ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        def do_it():
            
            from hydrus.client.gui import ClientGUIMediaViewerABRepeat
            
            return ClientGUIMediaViewerABRepeat.GetOpenMediaViewersABRepeat()
            
        
        media_viewers = CG.client_controller.CallBlockingToQtTLW( do_it )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'media_viewers' : media_viewers } )
        
    

class HydrusResourceClientAPIRestrictedManageMediaViewersSetABRepeatPingPong( HydrusResourceClientAPIRestrictedManageMediaViewers ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        ping_pong = request.parsed_request_args.GetValue( 'ping_pong', bool )
        
        # with no canvas_key, it is every media viewer that is open
        canvas_key = request.parsed_request_args.GetValueOrNone( 'canvas_key', bytes )
        
        def do_it():
            
            from hydrus.client.gui import ClientGUIMediaViewerABRepeat
            
            return ClientGUIMediaViewerABRepeat.SetOpenMediaViewersABRepeatPingPong( ping_pong, canvas_key = canvas_key )
            
        
        num_media_viewers = CG.client_controller.CallBlockingToQtTLW( do_it )
        
        if canvas_key is not None and num_media_viewers == 0:
            
            raise HydrusExceptions.NotFoundException( f'Did not find a media viewer for "{canvas_key.hex()}"!' )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'num_media_viewers' : num_media_viewers } )
        
    

class HydrusResourceClientAPIRestrictedManageMediaViewersGetScreens( HydrusResourceClientAPIRestrictedManageMediaViewers ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        def do_it():
            
            from hydrus.client.gui import ClientGUIMediaViewerScreens
            
            return ClientGUIMediaViewerScreens.GetScreensAPIInfo()
            
        
        # a copy, since the response adds to it
        body_dict = dict( CG.client_controller.CallBlockingToQtTLW( do_it ) )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, body_dict )
        
    

class HydrusResourceClientAPIRestrictedManageMediaViewersApplyScreenZoom( HydrusResourceClientAPIRestrictedManageMediaViewers ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        screen_name = request.parsed_request_args.GetValue( 'screen_name', str )
        
        # with no canvas_key, it is every media viewer that is open
        canvas_key = request.parsed_request_args.GetValueOrNone( 'canvas_key', bytes )
        
        def do_it():
            
            from hydrus.client.gui import ClientGUIMediaViewerScreens
            
            return ClientGUIMediaViewerScreens.ApplyOpenMediaViewersScreenZoom( screen_name, canvas_key = canvas_key )
            
        
        num_media_viewers = CG.client_controller.CallBlockingToQtTLW( do_it )
        
        if canvas_key is not None and num_media_viewers == 0:
            
            raise HydrusExceptions.NotFoundException( f'Did not find a media viewer for "{canvas_key.hex()}"!' )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'num_media_viewers' : num_media_viewers } )
        
    

class HydrusResourceClientAPIRestrictedManageMediaViewersGetSlideshows( HydrusResourceClientAPIRestrictedManageMediaViewers ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        def do_it():
            
            from hydrus.client.gui import ClientGUIMediaViewerSlideshows
            
            return ClientGUIMediaViewerSlideshows.GetOpenMediaViewersSlideshows()
            
        
        media_viewers = CG.client_controller.CallBlockingToQtTLW( do_it )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'media_viewers' : media_viewers } )
        
    

class HydrusResourceClientAPIRestrictedManageMediaViewersStartSlideshow( HydrusResourceClientAPIRestrictedManageMediaViewers ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        # seconds. 0 plays each file once through, and moves on as soon as it is done
        period = request.parsed_request_args.GetValue( 'period', float )
        
        if not ClientMediaSlideshows.SlideshowPeriodIsValid( period ):
            
            raise HydrusExceptions.BadRequestException( f'The slideshow period cannot be less than 0, but it was {period}!' )
            
        
        # with no canvas_key, it is every media viewer that is open
        canvas_key = request.parsed_request_args.GetValueOrNone( 'canvas_key', bytes )
        
        def do_it():
            
            from hydrus.client.gui import ClientGUIMediaViewerSlideshows
            
            return ClientGUIMediaViewerSlideshows.StartOpenMediaViewersSlideshow( period, canvas_key = canvas_key )
            
        
        num_media_viewers = CG.client_controller.CallBlockingToQtTLW( do_it )
        
        if canvas_key is not None and num_media_viewers == 0:
            
            raise HydrusExceptions.NotFoundException( f'Did not find a media viewer that can run a slideshow for "{canvas_key.hex()}"!' )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'num_media_viewers' : num_media_viewers } )
        
    

class HydrusResourceClientAPIRestrictedManageMediaViewersStopSlideshow( HydrusResourceClientAPIRestrictedManageMediaViewers ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        # with no canvas_key, it is every media viewer that is open
        canvas_key = request.parsed_request_args.GetValueOrNone( 'canvas_key', bytes )
        
        def do_it():
            
            from hydrus.client.gui import ClientGUIMediaViewerSlideshows
            
            return ClientGUIMediaViewerSlideshows.StopOpenMediaViewersSlideshow( canvas_key = canvas_key )
            
        
        num_media_viewers = CG.client_controller.CallBlockingToQtTLW( do_it )
        
        if canvas_key is not None and num_media_viewers == 0:
            
            raise HydrusExceptions.NotFoundException( f'Did not find a media viewer that can run a slideshow for "{canvas_key.hex()}"!' )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'num_media_viewers' : num_media_viewers } )
        
    

class HydrusResourceClientAPIRestrictedManageMediaViewersGetLayout( HydrusResourceClientAPIRestrictedManageMediaViewers ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        def do_it():
            
            from hydrus.client.gui import ClientGUIMediaViewerLayouts
            
            return ClientGUIMediaViewerLayouts.GetOpenMediaViewerLayouts()
            
        
        media_viewer_layouts = CG.client_controller.CallBlockingToQtTLW( do_it )
        
        # the same json as a saved media viewer layout file, so it can go to open_layout, or into a file, as it is
        layout = json.loads( ClientMediaViewerLayouts.ConvertMediaViewerLayoutsToJSON( media_viewer_layouts ) )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'layout' : layout } )
        
    

class HydrusResourceClientAPIRestrictedManageMediaViewersOpenLayout( HydrusResourceClientAPIRestrictedManageMediaViewers ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        layout = request.parsed_request_args.GetValue( 'layout', dict )
        
        try:
            
            media_viewer_layouts = ClientMediaViewerLayouts.ConvertJSONToMediaViewerLayouts( json.dumps( layout ) )
            
        except ValueError as e:
            
            raise HydrusExceptions.BadRequestException( f'Could not read that media viewer layout! {e}' )
            
        
        def do_it():
            
            from hydrus.client.gui import ClientGUIMediaViewerLayouts
            
            return ClientGUIMediaViewerLayouts.OpenMediaViewerLayouts( media_viewer_layouts )
            
        
        # a media viewer is skipped if none of its files can be shown any more
        ( num_opened, num_skipped ) = CG.client_controller.CallBlockingToQtTLW( do_it )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'num_opened' : num_opened, 'num_skipped' : num_skipped } )
        
    

class HydrusResourceClientAPIRestrictedManageMediaViewersOpenPlaylist( HydrusResourceClientAPIRestrictedManageMediaViewers ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        super()._CheckAPIPermissions( request )
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_MANAGE_PLAYLISTS )
        
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        ( playlist_id, name, num_items ) = ClientLocalServerResourcesManagePlaylists.GetPlaylistFromRequest( request )
        
        def do_it():
            
            return CG.client_controller.gui.OpenPlaylist( playlist_id )
            
        
        error = CG.client_controller.CallBlockingToQtTLW( do_it )
        
        if error is not None:
            
            raise HydrusExceptions.ConflictException( error )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, {} )
        
    

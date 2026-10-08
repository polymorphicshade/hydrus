import json

from hydrus.core import HydrusExceptions
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientAPI
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientMediaViewerLayouts
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResources
from hydrus.client.networking.api import ClientLocalServerResourcesManagePlaylists

# opening media viewers, and saving where they are. these are windows in the client, so they go with 'manage pages', like get_media_viewers

class HydrusResourceClientAPIRestrictedManageMediaViewers( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_MANAGE_PAGES )
        
    

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
        
    

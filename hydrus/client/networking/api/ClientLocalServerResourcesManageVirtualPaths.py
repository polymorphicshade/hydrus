from hydrus.core import HydrusExceptions
from hydrus.core import HydrusLists
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientAPI
from hydrus.client import ClientGlobals as CG
from hydrus.client.metadata import ClientVirtualPaths
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResources

# virtual paths are folder-like paths a file can have, like "collections/tv_shows/action", that system:path searches. a file can have several

def GetPathsFromRequest( request: HydrusServerRequest.HydrusRequest ) -> list[ str ]:
    
    paths = request.parsed_request_args.GetValue( 'paths', list, expected_list_type = str )
    
    # like tags, they are cleaned up the same way the client does it, so 'TV Shows\\Action' is 'tv_shows/action'
    paths = HydrusLists.DedupeList( [ ClientVirtualPaths.NormaliseVirtualPath( path ) for path in paths ] )
    
    for path in paths:
        
        error = ClientVirtualPaths.GetVirtualPathError( path )
        
        if error is not None:
            
            raise HydrusExceptions.BadRequestException( error )
            
        
    
    return paths
    

class HydrusResourceClientAPIRestrictedManageVirtualPaths( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_EDIT_VIRTUAL_PATHS )
        
    

class HydrusResourceClientAPIRestrictedManageVirtualPathsEditPaths( HydrusResourceClientAPIRestrictedManageVirtualPaths ):
    
    def _GetNewPaths( self, existing_paths: list[ str ], paths: list[ str ] ) -> list[ str ]:
        
        raise NotImplementedError()
        
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request )
        
        paths = GetPathsFromRequest( request )
        
        hashes_to_existing_paths = CG.client_controller.Read( 'file_virtual_paths', hashes )
        
        hashes_to_paths = { hash : self._GetNewPaths( hashes_to_existing_paths.get( hash, [] ), paths ) for hash in hashes }
        
        changed_hashes_to_paths = { hash : new_paths for ( hash, new_paths ) in hashes_to_paths.items() if set( new_paths ) != set( hashes_to_existing_paths.get( hash, [] ) ) }
        
        if len( changed_hashes_to_paths ) > 0:
            
            CG.client_controller.WriteSynchronous( 'file_virtual_paths', changed_hashes_to_paths )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'paths' : { hash.hex() : sorted( new_paths ) for ( hash, new_paths ) in hashes_to_paths.items() } } )
        
    

class HydrusResourceClientAPIRestrictedManageVirtualPathsAddPaths( HydrusResourceClientAPIRestrictedManageVirtualPathsEditPaths ):
    
    def _GetNewPaths( self, existing_paths: list[ str ], paths: list[ str ] ) -> list[ str ]:
        
        return HydrusLists.DedupeList( list( existing_paths ) + paths )
        
    

class HydrusResourceClientAPIRestrictedManageVirtualPathsGetAllPaths( HydrusResourceClientAPIRestrictedManageVirtualPaths ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        paths = CG.client_controller.Read( 'all_file_virtual_paths' )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'paths' : sorted( paths ) } )
        
    

class HydrusResourceClientAPIRestrictedManageVirtualPathsGetPaths( HydrusResourceClientAPIRestrictedManageVirtualPaths ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request )
        
        hashes_to_paths = CG.client_controller.Read( 'file_virtual_paths', hashes )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'paths' : { hash.hex() : sorted( hashes_to_paths.get( hash, [] ) ) for hash in hashes } } )
        
    

class HydrusResourceClientAPIRestrictedManageVirtualPathsRemovePaths( HydrusResourceClientAPIRestrictedManageVirtualPathsEditPaths ):
    
    def _GetNewPaths( self, existing_paths: list[ str ], paths: list[ str ] ) -> list[ str ]:
        
        return [ path for path in existing_paths if path not in paths ]
        
    

class HydrusResourceClientAPIRestrictedManageVirtualPathsSetPaths( HydrusResourceClientAPIRestrictedManageVirtualPathsEditPaths ):
    
    def _GetNewPaths( self, existing_paths: list[ str ], paths: list[ str ] ) -> list[ str ]:
        
        # exactly these, replacing what each file had. an empty list clears them
        return list( paths )
        
    

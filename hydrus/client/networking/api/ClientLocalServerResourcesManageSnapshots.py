import os

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusPaths
from hydrus.core import HydrusTemp
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientAPI
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientSnapshots
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResources

# snapshots are frames taken from a file in the media viewer. each is a png file of its own, in the snapshots file domain, and remembers the file it came from

class HydrusResourceClientAPIRestrictedManageSnapshots( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_MANAGE_SNAPSHOTS )
        
    

class HydrusResourceClientAPIRestrictedManageSnapshotsAddSnapshot( HydrusResourceClientAPIRestrictedManageSnapshots ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        # this imports a file from a path on this computer, so it needs what add_file needs too
        super()._CheckAPIPermissions( request )
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_ADD_FILES )
        
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hash = ClientLocalServerCore.ParseSingleHash( request )
        
        path = request.parsed_request_args.GetValue( 'path', str )
        
        timestamp_ms = request.parsed_request_args.GetValueOrNone( 'timestamp_ms', int )
        
        if timestamp_ms is not None:
            
            timestamp_ms = ClientLocalServerCore.CheckNonNegativeInt( 'timestamp_ms', timestamp_ms )
            
        
        if not os.path.exists( path ):
            
            raise HydrusExceptions.BadRequestException( f'Path "{path}" does not exist!' )
            
        
        if not os.path.isfile( path ):
            
            raise HydrusExceptions.BadRequestException( f'Path "{path}" is not a file!' )
            
        
        # like add_file, we import a copy. the server cleans it up when the request is done
        ( os_file_handle, temp_path ) = HydrusTemp.GetTempPath( 'client_api_snapshot' )
        
        request.temp_file_info = ( os_file_handle, temp_path )
        
        HydrusPaths.MirrorFile( path, temp_path )
        
        try:
            
            snapshot_hash = ClientSnapshots.ImportSnapshot( temp_path, hash, timestamp_ms )
            
        except HydrusExceptions.DBException:
            
            raise
            
        except Exception as e:
            
            raise HydrusExceptions.UnprocessableEntity( f'The snapshot did not import: {e}' )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'snapshot_hash' : snapshot_hash.hex() } )
        
    

class HydrusResourceClientAPIRestrictedManageSnapshotsGetSnapshots( HydrusResourceClientAPIRestrictedManageSnapshots ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request )
        
        location_context = ClientSnapshots.GetSnapshotsLocationContext()
        
        if location_context is None:
            
            # no snapshot has been taken yet, so there is no snapshots domain
            snapshots_file_service_key = None
            
            hashes_to_snapshot_hashes = { hash : [] for hash in hashes }
            
        else:
            
            snapshots_file_service_key = ClientSnapshots.GetSnapshotsServiceKey( create_if_missing = False )
            
            # each file's, in the order they come in the file
            hashes_to_snapshot_hashes = { hash : CG.client_controller.Read( 'file_snapshots', hash, location_context ) for hash in hashes }
            
        
        body_dict = {
            'snapshots_file_service_key' : None if snapshots_file_service_key is None else snapshots_file_service_key.hex(),
            'snapshots' : { hash.hex() : [ snapshot_hash.hex() for snapshot_hash in snapshot_hashes ] for ( hash, snapshot_hashes ) in hashes_to_snapshot_hashes.items() }
        }
        
        return ClientLocalServerCore.GenerateJSONResponse( request, body_dict )
        
    

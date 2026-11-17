import os

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusPaths
from hydrus.core import HydrusTemp
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientAPI
from hydrus.client import ClientCrops
from hydrus.client import ClientGlobals as CG
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResources

# crops are parts of a file cut out with an overlay's box in the media viewer. each is a png file of its own, in the crops file domain, and remembers the file it came from. they go with snapshots, and use their permission

class HydrusResourceClientAPIRestrictedManageCrops( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_MANAGE_SNAPSHOTS )
        
    

class HydrusResourceClientAPIRestrictedManageCropsAddCrop( HydrusResourceClientAPIRestrictedManageCrops ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        # this imports a file, so it needs what add_file needs too
        super()._CheckAPIPermissions( request )
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_ADD_FILES )
        
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hash = ClientLocalServerCore.ParseSingleHash( request )
        
        # an image that is the crop already, or the part of an image to cut out. with just a rect, it is cut out of the file itself
        path = request.parsed_request_args.GetValueOrNone( 'path', str )
        rect = request.parsed_request_args.GetValueOrNone( 'rect', list )
        
        timestamp_ms = request.parsed_request_args.GetValueOrNone( 'timestamp_ms', int )
        
        if timestamp_ms is not None:
            
            timestamp_ms = ClientLocalServerCore.CheckNonNegativeInt( 'timestamp_ms', timestamp_ms )
            
        
        if path is None and rect is None:
            
            raise HydrusExceptions.BadRequestException( 'Please give a "path" to an image, and/or a "rect" to cut out!' )
            
        
        if rect is not None:
            
            if len( rect ) != 4 or not all( isinstance( value, int ) and not isinstance( value, bool ) for value in rect ):
                
                raise HydrusExceptions.BadRequestException( 'The "rect" should be four whole numbers, [ x, y, width, height ], in the image\'s pixels!' )
                
            
            rect = tuple( rect )
            
        
        if path is None:
            
            media_results = CG.client_controller.Read( 'media_results', ( hash, ) )
            
            if len( media_results ) == 0:
                
                raise HydrusExceptions.NotFoundException( f'Did not find the file {hash.hex()}!' )
                
            
            mime = media_results[0].GetMime()
            
            try:
                
                path = CG.client_controller.client_files_manager.GetFilePath( hash, mime )
                
            except HydrusExceptions.FileMissingException:
                
                raise HydrusExceptions.NotFoundException( f'The file {hash.hex()} is not on this computer, so it cannot be cropped!' )
                
        else:
            
            if not os.path.exists( path ):
                
                raise HydrusExceptions.BadRequestException( f'Path "{path}" does not exist!' )
                
            
            if not os.path.isfile( path ):
                
                raise HydrusExceptions.BadRequestException( f'Path "{path}" is not a file!' )
                
            
        
        # like add_file, we import a copy. the server cleans it up when the request is done
        ( os_file_handle, temp_path ) = HydrusTemp.GetTempPath( 'client_api_crop', suffix = '.png' )
        
        request.temp_file_info = ( os_file_handle, temp_path )
        
        try:
            
            if rect is None:
                
                HydrusPaths.MirrorFile( path, temp_path )
                
            else:
                
                ClientCrops.CropRectFromImageFile( path, rect, temp_path )
                
            
            crop_hash = ClientCrops.ImportCrop( temp_path, hash, timestamp_ms )
            
        except HydrusExceptions.DBException:
            
            raise
            
        except Exception as e:
            
            raise HydrusExceptions.UnprocessableEntity( f'The crop did not import: {e}' )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'crop_hash' : crop_hash.hex() } )
        
    

class HydrusResourceClientAPIRestrictedManageCropsGetCrops( HydrusResourceClientAPIRestrictedManageCrops ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request )
        
        location_context = ClientCrops.GetCropsLocationContext()
        
        if location_context is None:
            
            # no crop has been taken yet, so there is no crops domain
            crops_file_service_key = None
            
            hashes_to_crop_hashes = { hash : [] for hash in hashes }
            
        else:
            
            crops_file_service_key = ClientCrops.GetCropsServiceKey( create_if_missing = False )
            
            # each file's, in the order they come in the file
            hashes_to_crop_hashes = { hash : CG.client_controller.Read( 'file_crops_for_files', [ hash ], location_context ) for hash in hashes }
            
        
        body_dict = {
            'crops_file_service_key' : None if crops_file_service_key is None else crops_file_service_key.hex(),
            'crops' : { hash.hex() : [ crop_hash.hex() for crop_hash in crop_hashes ] for ( hash, crop_hashes ) in hashes_to_crop_hashes.items() }
        }
        
        return ClientLocalServerCore.GenerateJSONResponse( request, body_dict )
        
        
        

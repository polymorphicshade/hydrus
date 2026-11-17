import os

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusPaths
from hydrus.core import HydrusTemp
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientFileReplace
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResourcesAddFiles

# replacing a file with another, like the media viewer's manage->replace with file. it imports and deletes files, so it is under add_files, with its permission

class HydrusResourceClientAPIRestrictedAddFilesReplaceFile( ClientLocalServerResourcesAddFiles.HydrusResourceClientAPIRestrictedAddFiles ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hash = ClientLocalServerCore.ParseSingleHash( request )
        
        path = request.parsed_request_args.GetValue( 'path', str )
        
        delete_old_file = request.parsed_request_args.GetValue( 'delete_old_file', bool, default_value = True )
        
        if not os.path.exists( path ):
            
            raise HydrusExceptions.BadRequestException( f'Path "{path}" does not exist!' )
            
        
        if not os.path.isfile( path ):
            
            raise HydrusExceptions.BadRequestException( f'Path "{path}" is not a file!' )
            
        
        # like add_file, we import a copy. the server cleans it up when the request is done
        ( os_file_handle, temp_path ) = HydrusTemp.GetTempPath( 'client_api_replace_file' )
        
        request.temp_file_info = ( os_file_handle, temp_path )
        
        HydrusPaths.MirrorFile( path, temp_path )
        
        try:
            
            ( new_hash, num_moved ) = ClientFileReplace.ReplaceFile( hash, temp_path, delete_old_file = delete_old_file )
            
        except HydrusExceptions.DBException:
            
            raise
            
        except HydrusExceptions.NotFoundException:
            
            raise
            
        except Exception as e:
            
            raise HydrusExceptions.UnprocessableEntity( f'The file was not replaced: {e}' )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'hash' : new_hash.hex(), 'num_moved' : num_moved } )
        
        

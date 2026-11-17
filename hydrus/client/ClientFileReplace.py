import os

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusExceptions

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientLocation
from hydrus.client.importing import ClientImportFiles
from hydrus.client.importing.options import FileFilteringImportOptions
from hydrus.client.importing.options import ImportOptionsConstants as IOC
from hydrus.client.importing.options import ImportOptionsContainer
from hydrus.client.importing.options import LocationImportOptions
from hydrus.client.media import ClientMediaResult

# replacing a file with another, say a better copy of a broken video. hydrus knows a file by its hash, so the bytes cannot just be swapped
# instead, the new file is imported, set as a better duplicate of the old one with the 'this is better' metadata merge, so it gets its tags, ratings, notes, and urls,
# then gets everything this fork remembers for the old file (its playlist places, counters, virtual paths, and media viewer data), and the old file is deleted

def GetMediaResult( hash: bytes ) -> ClientMediaResult.MediaResult:
    
    media_results = CG.client_controller.Read( 'media_results', ( hash, ) )
    
    if len( media_results ) == 0:
        
        raise HydrusExceptions.NotFoundException( f'Did not find the file {hash.hex()}!' )
        
    
    return media_results[0]
    

def GetReplacementLocationContext( media_result: ClientMediaResult.MediaResult ) -> ClientLocation.LocationContext | None:
    
    # the new file goes in the same local file domains as the old one. None means the normal import destination
    local_file_service_keys = set( CG.client_controller.services_manager.GetServiceKeys( ( HC.LOCAL_FILE_DOMAIN, ) ) )
    
    current_local_file_service_keys = media_result.GetLocationsManager().GetCurrent().intersection( local_file_service_keys )
    
    if len( current_local_file_service_keys ) == 0:
        
        return None
        
    
    return ClientLocation.LocationContext( current_service_keys = current_local_file_service_keys )
    

def ImportReplacementFile( path: str, old_media_result: ClientMediaResult.MediaResult ) -> bytes:
    
    # quietly, with no popups. this does db work, so it wants to be in a worker thread
    location_import_options = LocationImportOptions.LocationImportOptions()
    
    location_context = GetReplacementLocationContext( old_media_result )
    
    if location_context is not None:
        
        location_import_options.SetDestinationLocationContext( location_context )
        
    
    # if it is in the client already, it still goes where the old file was
    location_import_options.SetDoImportDestinationsOnAlreadyInDBFiles( True )
    
    file_filtering_import_options = FileFilteringImportOptions.FileFilteringImportOptions()
    
    # the user picked this file themselves, so it comes back even if they deleted it before
    file_filtering_import_options.SetExcludesDeleted( False )
    file_filtering_import_options.SetAllowsDecompressionBombs( True )
    
    import_options_container = ImportOptionsContainer.ImportOptionsContainer()
    
    import_options_container.SetImportOptions( location_import_options )
    import_options_container.SetImportOptions( file_filtering_import_options )
    
    full_import_options_container = CG.client_controller.import_options_manager.GenerateFullImportOptionsContainer( import_options_container, IOC.IMPORT_OPTIONS_CALLER_TYPE_LOCAL_IMPORT )
    
    file_import_job = ClientImportFiles.FileImportJob( path, full_import_options_container, human_file_description = 'replacement file' )
    
    file_import_status = file_import_job.DoWork()
    
    if file_import_status.status not in CC.SUCCESSFUL_IMPORT_STATES:
        
        raise HydrusExceptions.VetoException( f'The replacement file did not import: {file_import_status.ToString()}' )
        
    
    return file_import_status.hash
    

def ReplaceFile( old_hash: bytes, path: str, delete_old_file: bool = True ) -> tuple[ bytes, int ]:
    
    # returns the new file's hash, and how many rows of this fork's data moved to it. this does db work, so it wants to be in a worker thread
    if not os.path.isfile( path ):
        
        raise HydrusExceptions.VetoException( f'"{path}" is not a file!' )
        
    
    old_media_result = GetMediaResult( old_hash )
    
    new_hash = ImportReplacementFile( path, old_media_result )
    
    if new_hash == old_hash:
        
        raise HydrusExceptions.VetoException( 'That is the same file as the one it would replace!' )
        
    
    new_media_result = GetMediaResult( new_hash )
    
    # what this fork remembers for the old file goes over first, so a media viewer that swaps to the new file has it
    num_moved = CG.client_controller.WriteSynchronous( 'file_replace_move_data', old_hash, new_hash )
    
    # media viewers and pages showing the old file put the new one in its place. this goes before the delete below, so they still know where the old one was
    CG.client_controller.pub( 'notify_file_replaced', old_hash, new_media_result )
    
    # the new file is better than the old one, so it gets its metadata the way 'this is better' would merge it
    duplicate_content_merge_options = CG.client_controller.new_options.GetDuplicateContentMergeOptions( HC.DUPLICATE_BETTER )
    
    file_deletion_reason = f'Replaced by {new_hash.hex()}.'
    
    content_update_packages = duplicate_content_merge_options.ProcessPairIntoContentUpdatePackages( new_media_result, old_media_result, delete_b = delete_old_file, file_deletion_reason = file_deletion_reason )
    
    CG.client_controller.WriteSynchronous( 'duplicate_pair_status', [ ( HC.DUPLICATE_BETTER, new_hash, old_hash, content_update_packages ) ] )
    
    return ( new_hash, num_moved )
    

import threading

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusGlobals as HG

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientLocation
from hydrus.client import ClientServices
from hydrus.client.importing import ClientImportFiles
from hydrus.client.importing.options import FileFilteringImportOptions
from hydrus.client.importing.options import ImportOptionsConstants as IOC
from hydrus.client.importing.options import ImportOptionsContainer
from hydrus.client.importing.options import LocationImportOptions

# snapshots are frames the user takes in the media viewer. they go in a local file domain of their own, so they stay out of 'my files', and each one remembers the file it came from

SNAPSHOTS_SERVICE_NAME = 'snapshots'

SNAPSHOTS_SERVICE_KEY_OPTION = 'snapshots_file_service_key'

snapshots_service_lock = threading.Lock()

def GetUnusedServiceName( name: str, existing_names: set[ str ] ) -> str:
    
    existing_names = { existing_name.lower() for existing_name in existing_names }
    
    new_name = name
    
    i = 2
    
    while new_name.lower() in existing_names:
        
        new_name = f'{name} ({i})'
        
        i += 1
        
    
    return new_name
    

def GetSnapshotsServiceKey( create_if_missing = True ) -> bytes | None:
    
    # the user can rename the domain, so we remember it by key. if they deleted it, we make a new one
    with snapshots_service_lock:
        
        services_manager = CG.client_controller.services_manager
        new_options = CG.client_controller.new_options
        
        service_key = new_options.GetKey( SNAPSHOTS_SERVICE_KEY_OPTION )
        
        if len( service_key ) > 0 and services_manager.ServiceExists( service_key ) and services_manager.GetServiceType( service_key ) == HC.LOCAL_FILE_DOMAIN:
            
            return service_key
            
        
        if not create_if_missing:
            
            return None
            
        
        services = services_manager.GetServices()
        
        name = GetUnusedServiceName( SNAPSHOTS_SERVICE_NAME, { service.GetName() for service in services } )
        
        service_key = HydrusData.GenerateKey()
        
        service = ClientServices.GenerateService( service_key, HC.LOCAL_FILE_DOMAIN, name )
        
        # this is what manage services does when you add one, less restarting the client api, which a new file domain does not need
        with HG.dirty_object_lock:
            
            CG.client_controller.WriteSynchronous( 'update_services', services + [ service ] )
            
            services_manager.RefreshServices()
            
        
        new_options.SetKey( SNAPSHOTS_SERVICE_KEY_OPTION, service_key )
        
        CG.client_controller.Write( 'serialisable', new_options )
        
        return service_key
        
    

def GetSnapshotsLocationContext() -> ClientLocation.LocationContext | None:
    
    service_key = GetSnapshotsServiceKey( create_if_missing = False )
    
    if service_key is None:
        
        return None
        
    
    return ClientLocation.LocationContext.STATICCreateSimple( service_key )
    

def ImportSnapshot( path: str, hash: bytes, timestamp_ms: int | None ) -> bytes:
    
    # quietly, with no popups. this does db work, so it wants to be in a worker thread
    service_key = GetSnapshotsServiceKey()
    
    location_import_options = LocationImportOptions.LocationImportOptions()
    
    location_import_options.SetDestinationLocationContext( ClientLocation.LocationContext.STATICCreateSimple( service_key ) )
    
    # they are the user's own, so they do not need to go through the inbox. the same frame taken again still goes in the snapshots domain
    location_import_options.SetAutomaticallyArchives( True )
    location_import_options.SetDoAutomaticArchiveOnAlreadyInDBFiles( True )
    location_import_options.SetDoImportDestinationsOnAlreadyInDBFiles( True )
    
    file_filtering_import_options = FileFilteringImportOptions.FileFilteringImportOptions()
    
    # taking a frame again after deleting its snapshot is the user asking for it back
    file_filtering_import_options.SetExcludesDeleted( False )
    file_filtering_import_options.SetAllowsDecompressionBombs( True )
    
    import_options_container = ImportOptionsContainer.ImportOptionsContainer()
    
    import_options_container.SetImportOptions( location_import_options )
    import_options_container.SetImportOptions( file_filtering_import_options )
    
    full_import_options_container = CG.client_controller.import_options_manager.GenerateFullImportOptionsContainer( import_options_container, IOC.IMPORT_OPTIONS_CALLER_TYPE_LOCAL_IMPORT )
    
    file_import_job = ClientImportFiles.FileImportJob( path, full_import_options_container, human_file_description = 'snapshot' )
    
    file_import_status = file_import_job.DoWork()
    
    if file_import_status.status not in CC.SUCCESSFUL_IMPORT_STATES:
        
        raise Exception( f'The snapshot did not import: {file_import_status.ToString()}' )
        
    
    snapshot_hash = file_import_status.hash
    
    CG.client_controller.WriteSynchronous( 'file_snapshot_add', hash, snapshot_hash, timestamp_ms )
    
    return snapshot_hash
    

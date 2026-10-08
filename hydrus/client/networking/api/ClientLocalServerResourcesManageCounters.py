from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusSerialisable
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientAPI
from hydrus.client import ClientGlobals as CG
from hydrus.client.metadata import ClientCounters
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResources

# counters are tallies kept for each file. a counter is picked by 'counter_id' (hex) or 'counter_name' (not case-sensitive)

def ConvertCounterToDict( counter: HydrusSerialisable.IdAndName ) -> dict:
    
    return { 'counter_id' : counter.object_id.hex(), 'name' : counter.name }
    

def GetCounterFromRequest( request: HydrusServerRequest.HydrusRequest ) -> HydrusSerialisable.IdAndName:
    
    counters = CG.client_controller.new_options.GetCounters()
    
    counter_id = request.parsed_request_args.GetValueOrNone( 'counter_id', bytes )
    
    if counter_id is not None:
        
        for counter in counters:
            
            if counter.object_id == counter_id:
                
                return counter
                
            
        
        raise HydrusExceptions.NotFoundException( f'There is no counter with the id "{counter_id.hex()}"!' )
        
    
    counter_name = request.parsed_request_args.GetValueOrNone( 'counter_name', str )
    
    if counter_name is not None:
        
        for counter in counters:
            
            if counter.name.lower() == counter_name.strip().lower():
                
                return counter
                
            
        
        raise HydrusExceptions.NotFoundException( f'There is no counter called "{counter_name}"!' )
        
    
    raise HydrusExceptions.BadRequestException( 'Please say which counter, with counter_id or counter_name!' )
    

def SaveCounters( counters: list[ HydrusSerialisable.IdAndName ] ):
    
    new_options = CG.client_controller.new_options
    
    new_options.SetCounters( counters )
    
    CG.client_controller.WriteSynchronous( 'serialisable', new_options )
    

class HydrusResourceClientAPIRestrictedManageCounters( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_EDIT_COUNTERS )
        
    

class HydrusResourceClientAPIRestrictedManageCountersAddCounter( HydrusResourceClientAPIRestrictedManageCounters ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        name = request.parsed_request_args.GetValue( 'name', str )
        
        counters = CG.client_controller.new_options.GetCounters()
        
        error = ClientCounters.GetCounterNameError( name, [ counter.name for counter in counters ] )
        
        if error is not None:
            
            raise HydrusExceptions.BadRequestException( error )
            
        
        counter = HydrusSerialisable.IdAndName( HydrusData.GenerateKey(), name.strip() )
        
        counters.append( counter )
        
        SaveCounters( counters )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'counter' : ConvertCounterToDict( counter ) } )
        
    

class HydrusResourceClientAPIRestrictedManageCountersConvertTagsToCounters( HydrusResourceClientAPIRestrictedManageCounters ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        tag_service_key = request.parsed_request_args.GetValue( 'tag_service_key', bytes )
        tag_filter = request.parsed_request_args.GetValue( 'tag_filter', str )
        preview = request.parsed_request_args.GetValue( 'preview', bool, default_value = False )
        
        service = ClientLocalServerCore.CheckTagService( tag_service_key )
        
        # the tags are deleted as they are converted, so this is only for tags that are the user's own
        if service.GetServiceType() != HC.LOCAL_TAG:
            
            raise HydrusExceptions.BadRequestException( 'Tags can only be converted to counters on a local tag service!' )
            
        
        try:
            
            ( namespace_wildcard, subtag_wildcard ) = ClientCounters.ParseTagsToCountersFilter( tag_filter )
            
        except HydrusExceptions.VetoException as e:
            
            raise HydrusExceptions.BadRequestException( str( e ) )
            
        
        namespaces_to_numbers = CG.client_controller.Read( 'tags_to_counters_preview', tag_service_key, namespace_wildcard, subtag_wildcard )
        
        existing_names = { counter.name.lower() for counter in CG.client_controller.new_options.GetCounters() }
        
        namespaces_info = { namespace : { 'num_tags' : num_tags, 'num_files' : num_files, 'new_counter' : namespace.lower() not in existing_names } for ( namespace, ( num_tags, num_files ) ) in namespaces_to_numbers.items() }
        
        body_dict = { 'namespaces' : namespaces_info }
        
        if not preview and len( namespaces_to_numbers ) > 0:
            
            namespaces_to_counter_ids = ClientCounters.GetCounterIdsForNamespaces( namespaces_to_numbers.keys() )
            
            ( num_tags, num_files ) = CG.client_controller.WriteSynchronous( 'convert_tags_to_counters', tag_service_key, namespace_wildcard, subtag_wildcard, namespaces_to_counter_ids )
            
            body_dict[ 'num_tags' ] = num_tags
            body_dict[ 'num_files' ] = num_files
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, body_dict )
        
    

class HydrusResourceClientAPIRestrictedManageCountersDeleteCounter( HydrusResourceClientAPIRestrictedManageCounters ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        counter = GetCounterFromRequest( request )
        
        counters = [ c for c in CG.client_controller.new_options.GetCounters() if c.object_id != counter.object_id ]
        
        SaveCounters( counters )
        
        # its counts go with it
        CG.client_controller.WriteSynchronous( 'delete_file_counters', { counter.object_id } )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, {} )
        
    

class HydrusResourceClientAPIRestrictedManageCountersGetCounters( HydrusResourceClientAPIRestrictedManageCounters ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        counters = CG.client_controller.new_options.GetCounters()
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'counters' : [ ConvertCounterToDict( counter ) for counter in counters ] } )
        
    

class HydrusResourceClientAPIRestrictedManageCountersGetCounts( HydrusResourceClientAPIRestrictedManageCounters ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request )
        
        counters = CG.client_controller.new_options.GetCounters()
        
        counter_ids = { counter.object_id for counter in counters }
        
        counts = {}
        
        for hash in hashes:
            
            counter_ids_to_counts = CG.client_controller.Read( 'file_counters', hash )
            
            # a count is 0 when the file has none for that counter
            counts[ hash.hex() ] = { counter_id.hex() : count for ( counter_id, count ) in counter_ids_to_counts.items() if counter_id in counter_ids }
            
        
        body_dict = {
            'counters' : [ ConvertCounterToDict( counter ) for counter in counters ],
            'counts' : counts
        }
        
        return ClientLocalServerCore.GenerateJSONResponse( request, body_dict )
        
    

class HydrusResourceClientAPIRestrictedManageCountersIncrementCount( HydrusResourceClientAPIRestrictedManageCounters ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request )
        
        counter = GetCounterFromRequest( request )
        
        delta = request.parsed_request_args.GetValue( 'delta', int, default_value = 1 )
        
        if isinstance( delta, bool ):
            
            raise HydrusExceptions.BadRequestException( '"delta" has to be a whole number!' )
            
        
        # a count never goes below 0
        for hash in hashes:
            
            CG.client_controller.WriteSynchronous( 'file_counter_increment', hash, counter.object_id, delta )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, {} )
        
    

class HydrusResourceClientAPIRestrictedManageCountersRenameCounter( HydrusResourceClientAPIRestrictedManageCounters ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        counter = GetCounterFromRequest( request )
        
        new_name = request.parsed_request_args.GetValue( 'new_name', str )
        
        counters = CG.client_controller.new_options.GetCounters()
        
        error = ClientCounters.GetCounterNameError( new_name, [ c.name for c in counters if c.object_id != counter.object_id ] )
        
        if error is not None:
            
            raise HydrusExceptions.BadRequestException( error )
            
        
        # same id, so the counts stay with it
        renamed_counter = HydrusSerialisable.IdAndName( counter.object_id, new_name.strip() )
        
        counters = [ renamed_counter if c.object_id == counter.object_id else c for c in counters ]
        
        SaveCounters( counters )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'counter' : ConvertCounterToDict( renamed_counter ) } )
        
    

class HydrusResourceClientAPIRestrictedManageCountersSetCount( HydrusResourceClientAPIRestrictedManageCounters ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request )
        
        counter = GetCounterFromRequest( request )
        
        count = ClientLocalServerCore.CheckNonNegativeInt( 'count', request.parsed_request_args.GetValue( 'count', int ) )
        
        for hash in hashes:
            
            CG.client_controller.WriteSynchronous( 'file_counter_set', hash, counter.object_id, count )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, {} )
        
    

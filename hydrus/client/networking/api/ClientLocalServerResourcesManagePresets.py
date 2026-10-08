import typing

from hydrus.core import HydrusExceptions
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientAPI
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientScreenLocations
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResources
from hydrus.client.search import ClientSearchTagPresets

# tag presets are named lists of search entries that 'system:presets name' expands to. screen locations are named spots on a monitor that a media viewer can snap to
# both live in the options

def CheckTagPresetEntries( entries: typing.Any ) -> list[ str ]:
    
    if not isinstance( entries, list ) or False in ( isinstance( entry, str ) for entry in entries ):
        
        raise HydrusExceptions.BadRequestException( 'A tag preset\'s "entries" have to be a list of strings, like [ "blue eyes", "-red hair", "system:inbox" ]!' )
        
    
    entries = [ ClientSearchTagPresets.NormaliseTagPresetEntry( entry ) for entry in entries ]
    
    return ClientSearchTagPresets.DedupeEntries( [ entry for entry in entries if entry != '' ] )
    

def CheckTagPresetName( name: typing.Any ) -> str:
    
    if not isinstance( name, str ) or ClientSearchTagPresets.NormaliseTagPresetName( name ) == '':
        
        raise HydrusExceptions.BadRequestException( 'A tag preset needs a "name"!' )
        
    
    return ClientSearchTagPresets.NormaliseTagPresetName( name )
    

def ConvertScreenLocationToDict( screen_location: ClientScreenLocations.ScreenLocation ) -> dict:
    
    ( name, screen_name, x, y, width, height ) = screen_location
    
    return { 'name' : name, 'screen_name' : screen_name, 'x' : x, 'y' : y, 'width' : width, 'height' : height }
    

def ConvertTagPresetsToJSON( tag_presets: list[ ClientSearchTagPresets.TagPreset ] ) -> list[ dict ]:
    
    return [ { 'name' : name, 'entries' : list( entries ) } for ( name, entries ) in tag_presets ]
    

def SaveOptions():
    
    CG.client_controller.WriteSynchronous( 'serialisable', CG.client_controller.new_options )
    

class HydrusResourceClientAPIRestrictedManageTagPresets( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_MANAGE_TAG_PRESETS )
        
    

class HydrusResourceClientAPIRestrictedManageTagPresetsAddToTagPreset( HydrusResourceClientAPIRestrictedManageTagPresets ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        name = CheckTagPresetName( request.parsed_request_args.GetValue( 'name', str ) )
        
        entries = CheckTagPresetEntries( request.parsed_request_args.GetValue( 'entries', list ) )
        
        new_options = CG.client_controller.new_options
        
        # the preset is made if it does not exist yet, and entries it already has are skipped
        tag_presets = ClientSearchTagPresets.AddEntriesToTagPreset( new_options.GetTagPresets(), name, entries )
        
        new_options.SetTagPresets( tag_presets )
        
        SaveOptions()
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'tag_presets' : ConvertTagPresetsToJSON( tag_presets ) } )
        
    

class HydrusResourceClientAPIRestrictedManageTagPresetsDeleteTagPreset( HydrusResourceClientAPIRestrictedManageTagPresets ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        name = CheckTagPresetName( request.parsed_request_args.GetValue( 'name', str ) )
        
        new_options = CG.client_controller.new_options
        
        tag_presets = new_options.GetTagPresets()
        
        key = ClientSearchTagPresets.GetTagPresetLookupKey( name )
        
        kept_tag_presets = [ tag_preset for tag_preset in tag_presets if ClientSearchTagPresets.GetTagPresetLookupKey( tag_preset[0] ) != key ]
        
        if len( kept_tag_presets ) == len( tag_presets ):
            
            raise HydrusExceptions.NotFoundException( f'There is no tag preset called "{name}"!' )
            
        
        new_options.SetTagPresets( kept_tag_presets )
        
        SaveOptions()
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'tag_presets' : ConvertTagPresetsToJSON( kept_tag_presets ) } )
        
    

class HydrusResourceClientAPIRestrictedManageTagPresetsGetTagPresets( HydrusResourceClientAPIRestrictedManageTagPresets ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        tag_presets = CG.client_controller.new_options.GetTagPresets()
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'tag_presets' : ConvertTagPresetsToJSON( tag_presets ) } )
        
    

class HydrusResourceClientAPIRestrictedManageTagPresetsSetTagPresets( HydrusResourceClientAPIRestrictedManageTagPresets ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        tag_preset_dicts = request.parsed_request_args.GetValue( 'tag_presets', list )
        
        # all of them, replacing what there was
        tag_presets = []
        keys_seen = set()
        
        for tag_preset_dict in tag_preset_dicts:
            
            if not isinstance( tag_preset_dict, dict ):
                
                raise HydrusExceptions.BadRequestException( 'Each tag preset has to be an Object, like { "name" : "...", "entries" : [ ... ] }!' )
                
            
            name = CheckTagPresetName( tag_preset_dict.get( 'name', None ) )
            
            entries = CheckTagPresetEntries( tag_preset_dict.get( 'entries', [] ) )
            
            key = ClientSearchTagPresets.GetTagPresetLookupKey( name )
            
            # names are not case-sensitive, and underscores count as spaces
            if key in keys_seen:
                
                raise HydrusExceptions.BadRequestException( f'There is more than one tag preset called "{name}"!' )
                
            
            keys_seen.add( key )
            
            tag_presets.append( ( name, entries ) )
            
        
        CG.client_controller.new_options.SetTagPresets( tag_presets )
        
        SaveOptions()
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'tag_presets' : ConvertTagPresetsToJSON( tag_presets ) } )
        
    

class HydrusResourceClientAPIRestrictedManageScreenLocations( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_MANAGE_SCREEN_LOCATIONS )
        
    

class HydrusResourceClientAPIRestrictedManageScreenLocationsGetScreenLocations( HydrusResourceClientAPIRestrictedManageScreenLocations ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        screen_locations = CG.client_controller.new_options.GetScreenLocations()
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'screen_locations' : [ ConvertScreenLocationToDict( screen_location ) for screen_location in screen_locations ] } )
        
    

class HydrusResourceClientAPIRestrictedManageScreenLocationsSetScreenLocations( HydrusResourceClientAPIRestrictedManageScreenLocations ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        screen_location_dicts = request.parsed_request_args.GetValue( 'screen_locations', list )
        
        # all of them, replacing what there was. x and y are the window's top-left on that screen, and width and height are its inside size
        screen_locations = []
        
        for screen_location_dict in screen_location_dicts:
            
            if not isinstance( screen_location_dict, dict ):
                
                raise HydrusExceptions.BadRequestException( 'Each screen location has to be an Object, like { "name" : "...", "screen_name" : "...", "x" : 0, "y" : 0, "width" : 800, "height" : 600 }!' )
                
            
            name = screen_location_dict.get( 'name', None )
            screen_name = screen_location_dict.get( 'screen_name', None )
            
            if not isinstance( name, str ) or not isinstance( screen_name, str ):
                
                raise HydrusExceptions.BadRequestException( 'A screen location needs a "name" and a "screen_name"!' )
                
            
            numbers = []
            
            for key in ( 'x', 'y', 'width', 'height' ):
                
                value = screen_location_dict.get( key, None )
                
                if isinstance( value, bool ) or not isinstance( value, int ):
                    
                    raise HydrusExceptions.BadRequestException( f'"{key}" in a screen location has to be a whole number!' )
                    
                
                numbers.append( value )
                
            
            ( x, y, width, height ) = numbers
            
            screen_location = ( name.strip(), screen_name, x, y, width, height )
            
            error = ClientScreenLocations.GetScreenLocationError( screen_location, [ other[0] for other in screen_locations ] )
            
            if error is not None:
                
                raise HydrusExceptions.BadRequestException( error )
                
            
            screen_locations.append( screen_location )
            
        
        CG.client_controller.new_options.SetScreenLocations( screen_locations )
        
        SaveOptions()
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'screen_locations' : [ ConvertScreenLocationToDict( screen_location ) for screen_location in screen_locations ] } )
        
    

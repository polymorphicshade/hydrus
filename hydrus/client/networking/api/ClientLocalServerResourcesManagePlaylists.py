import typing

from hydrus.core import HydrusExceptions
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientAPI
from hydrus.client import ClientGlobals as CG
from hydrus.client.media import ClientMediaPlaylists
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResources

# a playlist is picked by 'playlist_id' or 'playlist_name' (not case-sensitive)
# an item is { "hash" : ..., "start_ms" : ..., "end_ms" : ..., "reverse" : ... } for a file, where no start and end means the whole file, or { "blank_ms" : ... } for a blank

def ConvertPlaylistItemToDict( item: tuple[ bytes | None, int | None, int | None, bool ] ) -> dict:
    
    ( hash, start_ms, end_ms, reverse ) = item
    
    if hash is None:
        
        # a blank's end_ms is how long it lasts
        return { 'blank_ms' : end_ms }
        
    
    return { 'hash' : hash.hex(), 'start_ms' : start_ms, 'end_ms' : end_ms, 'reverse' : reverse }
    

def ConvertDictToPlaylistItem( item_dict: typing.Any ) -> tuple[ bytes | None, int | None, int | None, bool ]:
    
    if not isinstance( item_dict, dict ):
        
        raise HydrusExceptions.BadRequestException( f'A playlist item has to be an Object, like {{ "hash" : "..." }} or {{ "blank_ms" : 1000 }}! "{item_dict}" is not.' )
        
    
    if 'blank_ms' in item_dict:
        
        duration_ms = ClientLocalServerCore.CheckNonNegativeInt( 'blank_ms', item_dict[ 'blank_ms' ] )
        
        CheckBlankDuration( duration_ms )
        
        return ClientMediaPlaylists.CreatePlaylistBlankItem( duration_ms )
        
    
    hash_hex = item_dict.get( 'hash', None )
    
    try:
        
        hash = bytes.fromhex( hash_hex )
        
    except Exception as e:
        
        raise HydrusExceptions.BadRequestException( f'A playlist item needs a "hash" or a "blank_ms"! "{item_dict}" does not have a good one.' )
        
    
    ClientLocalServerCore.CheckHashLength( [ hash ] )
    
    ( start_ms, end_ms ) = CheckSpan( item_dict.get( 'start_ms', None ), item_dict.get( 'end_ms', None ) )
    
    reverse = item_dict.get( 'reverse', False )
    
    if not isinstance( reverse, bool ):
        
        raise HydrusExceptions.BadRequestException( f'"reverse" has to be true or false! "{reverse}" is not.' )
        
    
    return ( hash, start_ms, end_ms, reverse )
    

def ConvertPlaylistSummaryToDict( playlist: ClientMediaPlaylists.PlaylistSummary ) -> dict:
    
    ( playlist_id, name, num_items ) = playlist
    
    return { 'playlist_id' : playlist_id, 'name' : name, 'num_items' : num_items }
    

def CheckBlankDuration( duration_ms: int ):
    
    if not ClientMediaPlaylists.PLAYLIST_BLANK_MIN_MS <= duration_ms <= ClientMediaPlaylists.PLAYLIST_BLANK_MAX_MS:
        
        raise HydrusExceptions.BadRequestException( f'A blank has to be from {ClientMediaPlaylists.PLAYLIST_BLANK_MIN_MS}ms to {ClientMediaPlaylists.PLAYLIST_BLANK_MAX_MS}ms long!' )
        
    

def CheckPlaylistName( name: str, other_names: list[ str ] ) -> str:
    
    name = ClientMediaPlaylists.NormalisePlaylistName( name )
    
    if name == '':
        
        raise HydrusExceptions.BadRequestException( 'A playlist needs a name!' )
        
    
    if name.lower() in { other_name.lower() for other_name in other_names }:
        
        raise HydrusExceptions.ConflictException( f'There is already a playlist called "{name}"!' )
        
    
    return name
    

def CheckSpan( start_ms: typing.Any, end_ms: typing.Any ) -> tuple[ int | None, int | None ]:
    
    # no start and no end is the whole file
    if start_ms is None and end_ms is None:
        
        return ( None, None )
        
    
    if start_ms is None or end_ms is None:
        
        raise HydrusExceptions.BadRequestException( 'A playlist item that is part of a file needs both a "start_ms" and an "end_ms"! Leave both out for the whole file.' )
        
    
    start_ms = ClientLocalServerCore.CheckNonNegativeInt( 'start_ms', start_ms )
    end_ms = ClientLocalServerCore.CheckNonNegativeInt( 'end_ms', end_ms )
    
    if start_ms >= end_ms:
        
        raise HydrusExceptions.BadRequestException( f'A playlist item has to start before it ends! {start_ms}ms is not before {end_ms}ms.' )
        
    
    return ( start_ms, end_ms )
    

def GetPlaylistFromRequest( request: HydrusServerRequest.HydrusRequest ) -> ClientMediaPlaylists.PlaylistSummary:
    
    playlists = CG.client_controller.Read( 'playlists' )
    
    playlist_id = request.parsed_request_args.GetValueOrNone( 'playlist_id', int )
    
    if playlist_id is not None:
        
        for playlist in playlists:
            
            if playlist[0] == playlist_id:
                
                return playlist
                
            
        
        raise HydrusExceptions.NotFoundException( f'There is no playlist with the id {playlist_id}!' )
        
    
    playlist_name = request.parsed_request_args.GetValueOrNone( 'playlist_name', str )
    
    if playlist_name is not None:
        
        playlist_name = ClientMediaPlaylists.NormalisePlaylistName( playlist_name )
        
        for playlist in playlists:
            
            if playlist[1].lower() == playlist_name.lower():
                
                return playlist
                
            
        
        raise HydrusExceptions.NotFoundException( f'There is no playlist called "{playlist_name}"!' )
        
    
    raise HydrusExceptions.BadRequestException( 'Please say which playlist, with playlist_id or playlist_name!' )
    

def GetPlaylistDict( playlist_id: int ) -> dict:
    
    for playlist in CG.client_controller.Read( 'playlists' ):
        
        if playlist[0] == playlist_id:
            
            return ConvertPlaylistSummaryToDict( playlist )
            
        
    
    raise HydrusExceptions.NotFoundException( f'There is no playlist with the id {playlist_id}!' )
    

class HydrusResourceClientAPIRestrictedManagePlaylists( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_MANAGE_PLAYLISTS )
        
    

class HydrusResourceClientAPIRestrictedManagePlaylistsAddBlank( HydrusResourceClientAPIRestrictedManagePlaylists ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        ( playlist_id, name, num_items ) = GetPlaylistFromRequest( request )
        
        duration_ms = ClientLocalServerCore.CheckNonNegativeInt( 'blank_ms', request.parsed_request_args.GetValue( 'blank_ms', int ) )
        
        CheckBlankDuration( duration_ms )
        
        CG.client_controller.WriteSynchronous( 'playlist_add_blank', playlist_id, duration_ms )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'playlist' : GetPlaylistDict( playlist_id ) } )
        
    

class HydrusResourceClientAPIRestrictedManagePlaylistsAddFiles( HydrusResourceClientAPIRestrictedManagePlaylists ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request )
        
        ( playlist_id, name, num_items ) = GetPlaylistFromRequest( request )
        
        ( start_ms, end_ms ) = CheckSpan( request.parsed_request_args.GetValueOrNone( 'start_ms', int ), request.parsed_request_args.GetValueOrNone( 'end_ms', int ) )
        
        # they go on the end, in the order given
        for hash in hashes:
            
            CG.client_controller.WriteSynchronous( 'playlist_add_item', playlist_id, hash, start_ms, end_ms )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'playlist' : GetPlaylistDict( playlist_id ) } )
        
    

class HydrusResourceClientAPIRestrictedManagePlaylistsDeletePlaylist( HydrusResourceClientAPIRestrictedManagePlaylists ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        ( playlist_id, name, num_items ) = GetPlaylistFromRequest( request )
        
        CG.client_controller.WriteSynchronous( 'playlist_delete', playlist_id )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, {} )
        
    

class HydrusResourceClientAPIRestrictedManagePlaylistsGetPlaylist( HydrusResourceClientAPIRestrictedManagePlaylists ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        playlist = GetPlaylistFromRequest( request )
        
        items = CG.client_controller.Read( 'playlist_items', playlist[0] )
        
        playlist_dict = ConvertPlaylistSummaryToDict( playlist )
        
        playlist_dict[ 'items' ] = [ ConvertPlaylistItemToDict( item ) for item in items ]
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'playlist' : playlist_dict } )
        
    

class HydrusResourceClientAPIRestrictedManagePlaylistsGetPlaylists( HydrusResourceClientAPIRestrictedManagePlaylists ):
    
    def _threadDoGETJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request, optional = True )
        
        if hashes is None:
            
            playlists = CG.client_controller.Read( 'playlists' )
            
            return ClientLocalServerCore.GenerateJSONResponse( request, { 'playlists' : [ ConvertPlaylistSummaryToDict( playlist ) for playlist in playlists ] } )
            
        
        # with a file, just the playlists it is in. num_items is then how many times it is in each
        if len( hashes ) != 1:
            
            raise HydrusExceptions.BadRequestException( 'Please give just one file to find the playlists it is in!' )
            
        
        playlists = CG.client_controller.Read( 'playlists_containing_file', hashes[0] )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'playlists' : [ ConvertPlaylistSummaryToDict( playlist ) for playlist in playlists ] } )
        
    

class HydrusResourceClientAPIRestrictedManagePlaylistsNewPlaylist( HydrusResourceClientAPIRestrictedManagePlaylists ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        name = request.parsed_request_args.GetValue( 'name', str )
        
        name = CheckPlaylistName( name, [ other_name for ( other_playlist_id, other_name, other_num_items ) in CG.client_controller.Read( 'playlists' ) ] )
        
        playlist_id = CG.client_controller.WriteSynchronous( 'playlist_new', name )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'playlist' : GetPlaylistDict( playlist_id ) } )
        
    

class HydrusResourceClientAPIRestrictedManagePlaylistsRemoveFiles( HydrusResourceClientAPIRestrictedManagePlaylists ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        hashes = ClientLocalServerCore.ParseHashes( request )
        
        ( playlist_id, name, num_items ) = GetPlaylistFromRequest( request )
        
        # every item of each file goes, whatever its span
        for hash in hashes:
            
            CG.client_controller.WriteSynchronous( 'playlist_remove_file', playlist_id, hash )
            
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'playlist' : GetPlaylistDict( playlist_id ) } )
        
    

class HydrusResourceClientAPIRestrictedManagePlaylistsRenamePlaylist( HydrusResourceClientAPIRestrictedManagePlaylists ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        ( playlist_id, name, num_items ) = GetPlaylistFromRequest( request )
        
        new_name = request.parsed_request_args.GetValue( 'new_name', str )
        
        new_name = CheckPlaylistName( new_name, [ other_name for ( other_playlist_id, other_name, other_num_items ) in CG.client_controller.Read( 'playlists' ) if other_playlist_id != playlist_id ] )
        
        CG.client_controller.WriteSynchronous( 'playlist_rename', playlist_id, new_name )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'playlist' : GetPlaylistDict( playlist_id ) } )
        
    

class HydrusResourceClientAPIRestrictedManagePlaylistsSetItems( HydrusResourceClientAPIRestrictedManagePlaylists ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        ( playlist_id, name, num_items ) = GetPlaylistFromRequest( request )
        
        item_dicts = request.parsed_request_args.GetValue( 'items', list )
        
        # the whole playlist, in order, replacing what it had
        items = [ ConvertDictToPlaylistItem( item_dict ) for item_dict in item_dicts ]
        
        CG.client_controller.WriteSynchronous( 'playlist_items', playlist_id, items )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'playlist' : GetPlaylistDict( playlist_id ) } )
        
    

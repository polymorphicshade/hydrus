import http.client
import json
import os
import shutil
import tempfile
import time
import unittest

from unittest import mock

from twisted.internet import reactor

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusSerialisable
from hydrus.core import HydrusStaticDir

from hydrus.client import ClientAPI
from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientLocation
from hydrus.client import ClientServices
from hydrus.client import ClientSnapshots
from hydrus.client.networking.api import ClientLocalServer

from hydrus import hydrus_cli

from hydrus.test import TestGlobals as TG

# this fork's own Client API endpoints. they get their own server, so they do not get in the way of the main Client API test

PORT = 45879

def api_call( method: str, path: str, api_permissions: ClientAPI.APIPermissions | None, params: dict | None = None ):
    
    connection = http.client.HTTPConnection( '127.0.0.1', PORT, timeout = 10 )
    
    headers = {}
    
    if api_permissions is not None:
        
        headers[ 'Hydrus-Client-API-Access-Key' ] = api_permissions.GetAccessKey().hex()
        
    
    if params is None:
        
        params = {}
        
    
    if method == 'GET':
        
        if len( params ) > 0:
            
            path += '?' + hydrus_cli.EncodeGETParams( params )
            
        
        connection.request( 'GET', path, headers = headers )
        
    else:
        
        headers[ 'Content-Type' ] = 'application/json'
        
        connection.request( 'POST', path, body = json.dumps( params ), headers = headers )
        
    
    response = connection.getresponse()
    
    data = response.read()
    
    connection.close()
    
    try:
        
        body = json.loads( data )
        
    except ValueError:
        
        body = str( data, 'utf-8' )
        
    
    # every json response says these
    if isinstance( body, dict ) and path.split( '?' )[0] != '/api_version':
        
        body.pop( 'version', None )
        body.pop( 'hydrus_version', None )
        
    
    return ( response.status, body )
    

def make_access( name: str, permits_everything: bool, basic_permissions: list[ int ] ) -> ClientAPI.APIPermissions:
    
    api_permissions = ClientAPI.APIPermissions( name = name, permits_everything = permits_everything, basic_permissions = basic_permissions )
    
    TG.test_controller.client_api_manager.AddAccess( api_permissions )
    
    return api_permissions
    

class TestClientAPIFork( unittest.TestCase ):
    
    @classmethod
    def setUpClass( cls ):
        
        cls.maxDiff = None
        
        client_api = ClientServices.GenerateService( CC.CLIENT_API_SERVICE_KEY, HC.CLIENT_API_SERVICE, 'client api' )
        
        def TWISTEDSetup():
            
            reactor.listenTCP( PORT, ClientLocalServer.HydrusServiceClientAPI( client_api, allow_non_local_connections = False ) )
            
        
        reactor.callFromThread( TWISTEDSetup )
        
        time.sleep( 1 )
        
        cls.everything = make_access( 'everything', True, [] )
        cls.everything_and_scripts = make_access( 'everything and scripts', True, [ ClientAPI.CLIENT_API_PERMISSION_EDIT_SCRIPTED_EVENTS ] )
        cls.counters_only = make_access( 'counters', False, [ ClientAPI.CLIENT_API_PERMISSION_EDIT_COUNTERS ] )
        cls.snapshots_only = make_access( 'snapshots', False, [ ClientAPI.CLIENT_API_PERMISSION_MANAGE_SNAPSHOTS ] )
        cls.pages_only = make_access( 'pages', False, [ ClientAPI.CLIENT_API_PERMISSION_MANAGE_PAGES ] )
        
    
    def test_permissions( self ):
        
        ( status, body ) = api_call( 'GET', '/api_version', None )
        
        self.assertEqual( status, 200 )
        self.assertEqual( body[ 'fork_api_version' ], HC.CLIENT_API_FORK_VERSION )
        
        # one permission does not give another
        ( status, body ) = api_call( 'GET', '/manage_counters/get_counters', self.counters_only )
        
        self.assertEqual( status, 200 )
        
        ( status, body ) = api_call( 'GET', '/manage_playlists/get_playlists', self.counters_only )
        
        self.assertEqual( status, 403 )
        
        # 'permits everything' covers the fork's permissions, but not editing scripted events
        self.assertTrue( self.everything.HasPermission( ClientAPI.CLIENT_API_PERMISSION_MANAGE_PLAYLISTS ) )
        self.assertFalse( self.everything.HasPermission( ClientAPI.CLIENT_API_PERMISSION_EDIT_SCRIPTED_EVENTS ) )
        self.assertTrue( self.everything_and_scripts.HasPermission( ClientAPI.CLIENT_API_PERMISSION_EDIT_SCRIPTED_EVENTS ) )
        
        with self.assertRaises( Exception ):
            
            self.everything.CheckAtLeastOnePermission( [ ClientAPI.CLIENT_API_PERMISSION_EDIT_SCRIPTED_EVENTS ] )
            
        
        self.everything.CheckAtLeastOnePermission( [ ClientAPI.CLIENT_API_PERMISSION_EDIT_SCRIPTED_EVENTS, ClientAPI.CLIENT_API_PERMISSION_EDIT_COUNTERS ] )
        
        self.assertEqual( self.everything.GetBasicPermissionsString(), 'can do anything' )
        self.assertIn( 'edit scripted events', self.everything_and_scripts.GetBasicPermissionsString() )
        
        ( status, body ) = api_call( 'GET', '/verify_access_key', self.everything )
        
        self.assertEqual( set( body[ 'basic_permissions' ] ), set( ClientAPI.PERMITS_EVERYTHING_PERMISSIONS ) )
        
        ( status, body ) = api_call( 'GET', '/verify_access_key', self.everything_and_scripts )
        
        self.assertEqual( set( body[ 'basic_permissions' ] ), set( ClientAPI.ALLOWED_PERMISSIONS ) )
        
        # the cli knows all the permission names
        self.assertEqual( set( hydrus_cli.PERMISSION_NAMES_TO_NUMBERS.values() ), set( ClientAPI.ALLOWED_PERMISSIONS ) )
        
    
    def test_counters( self ):
        
        new_options = TG.test_controller.new_options
        
        tally = HydrusSerialisable.IdAndName( os.urandom( 32 ), 'Tally' )
        watched = HydrusSerialisable.IdAndName( os.urandom( 32 ), 'watched' )
        
        new_options.SetCounters( [ tally, watched ] )
        
        ( status, body ) = api_call( 'GET', '/manage_counters/get_counters', self.counters_only )
        
        self.assertEqual( body[ 'counters' ], [ { 'counter_id' : tally.object_id.hex(), 'name' : 'Tally' }, { 'counter_id' : watched.object_id.hex(), 'name' : 'watched' } ] )
        
        # add. names are not case-sensitive
        TG.test_controller.ClearWrites( 'serialisable' )
        
        ( status, body ) = api_call( 'POST', '/manage_counters/add_counter', self.counters_only, { 'name' : 'tally' } )
        
        self.assertEqual( status, 400 )
        
        ( status, body ) = api_call( 'POST', '/manage_counters/add_counter', self.counters_only, { 'name' : ' likes ' } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( body[ 'counter' ][ 'name' ], 'likes' )
        
        likes_id = bytes.fromhex( body[ 'counter' ][ 'counter_id' ] )
        
        self.assertEqual( [ counter.name for counter in new_options.GetCounters() ], [ 'Tally', 'watched', 'likes' ] )
        self.assertEqual( len( TG.test_controller.GetWrite( 'serialisable' ) ), 1 )
        
        # rename, by name, keeping the id
        ( status, body ) = api_call( 'POST', '/manage_counters/rename_counter', self.counters_only, { 'counter_name' : 'LIKES', 'new_name' : 'watched' } )
        
        self.assertEqual( status, 400 )
        
        ( status, body ) = api_call( 'POST', '/manage_counters/rename_counter', self.counters_only, { 'counter_name' : 'LIKES', 'new_name' : 'hearts' } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( body[ 'counter' ], { 'counter_id' : likes_id.hex(), 'name' : 'hearts' } )
        
        # delete, by id. its counts go too
        TG.test_controller.ClearWrites( 'delete_file_counters' )
        
        ( status, body ) = api_call( 'POST', '/manage_counters/delete_counter', self.counters_only, { 'counter_id' : likes_id.hex() } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( [ counter.name for counter in new_options.GetCounters() ], [ 'Tally', 'watched' ] )
        self.assertEqual( TG.test_controller.GetWrite( 'delete_file_counters' ), [ ( ( { likes_id }, ), {} ) ] )
        
        ( status, body ) = api_call( 'POST', '/manage_counters/delete_counter', self.counters_only, { 'counter_name' : 'nope' } )
        
        self.assertEqual( status, 404 )
        
        # counts. ones for counters that are gone are left out
        hash_1 = os.urandom( 32 )
        hash_2 = os.urandom( 32 )
        
        TG.test_controller.SetRead( 'file_counters', { tally.object_id : 3, likes_id : 7 } )
        
        ( status, body ) = api_call( 'GET', '/manage_counters/get_counts', self.counters_only, { 'hashes' : [ hash_1.hex(), hash_2.hex() ] } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( body[ 'counts' ], { hash_1.hex() : { tally.object_id.hex() : 3 }, hash_2.hex() : { tally.object_id.hex() : 3 } } )
        
        # set and increment
        TG.test_controller.ClearWrites( 'file_counter_set' )
        
        ( status, body ) = api_call( 'POST', '/manage_counters/set_count', self.counters_only, { 'hashes' : [ hash_1.hex(), hash_2.hex() ], 'counter_name' : 'tally', 'count' : 5 } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( TG.test_controller.GetWrite( 'file_counter_set' ), [ ( ( hash_1, tally.object_id, 5 ), {} ), ( ( hash_2, tally.object_id, 5 ), {} ) ] )
        
        for bad_count in ( -1, 1.5, True ):
            
            ( status, body ) = api_call( 'POST', '/manage_counters/set_count', self.counters_only, { 'hash' : hash_1.hex(), 'counter_name' : 'tally', 'count' : bad_count } )
            
            self.assertEqual( status, 400, bad_count )
            
        
        TG.test_controller.ClearWrites( 'file_counter_increment' )
        
        ( status, body ) = api_call( 'POST', '/manage_counters/increment_count', self.counters_only, { 'hash' : hash_1.hex(), 'counter_id' : watched.object_id.hex() } )
        ( status, body ) = api_call( 'POST', '/manage_counters/increment_count', self.counters_only, { 'hash' : hash_1.hex(), 'counter_id' : watched.object_id.hex(), 'delta' : -2 } )
        
        self.assertEqual( TG.test_controller.GetWrite( 'file_counter_increment' ), [ ( ( hash_1, watched.object_id, 1 ), {} ), ( ( hash_1, watched.object_id, -2 ), {} ) ] )
        
        # converting tags. only on a local tag service
        TG.test_controller.SetRead( 'tags_to_counters_preview', { 'items' : ( 4, 3 ), 'tally' : ( 2, 2 ) } )
        
        ( status, body ) = api_call( 'POST', '/manage_counters/convert_tags_to_counters', self.counters_only, { 'tag_service_key' : CC.DEFAULT_LOCAL_TAG_SERVICE_KEY.hex(), 'tag_filter' : 'items:', 'preview' : True } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'namespaces' : { 'items' : { 'num_tags' : 4, 'num_files' : 3, 'new_counter' : True }, 'tally' : { 'num_tags' : 2, 'num_files' : 2, 'new_counter' : False } } } )
        self.assertEqual( len( new_options.GetCounters() ), 2 )
        
        ( status, body ) = api_call( 'POST', '/manage_counters/convert_tags_to_counters', self.counters_only, { 'tag_service_key' : CC.DEFAULT_LOCAL_TAG_SERVICE_KEY.hex(), 'tag_filter' : 'items:abc' } )
        
        self.assertEqual( status, 400 )
        
        with mock.patch.object( CG.client_controller, 'WriteSynchronous', return_value = ( 6, 4 ) ) as write_synchronous:
            
            ( status, body ) = api_call( 'POST', '/manage_counters/convert_tags_to_counters', self.counters_only, { 'tag_service_key' : CC.DEFAULT_LOCAL_TAG_SERVICE_KEY.hex(), 'tag_filter' : 'items:*' } )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( ( body[ 'num_tags' ], body[ 'num_files' ] ), ( 6, 4 ) )
        
        # the new counter was made for it
        names_to_ids = { counter.name : counter.object_id for counter in new_options.GetCounters() }
        
        self.assertEqual( set( names_to_ids.keys() ), { 'Tally', 'watched', 'items' } )
        
        write_synchronous.assert_called_once_with( 'convert_tags_to_counters', CC.DEFAULT_LOCAL_TAG_SERVICE_KEY, 'items', '*', { 'items' : names_to_ids[ 'items' ], 'tally' : tally.object_id } )
        
        new_options.SetCounters( [] )
        
    
    def test_playlists( self ):
        
        hash_1 = os.urandom( 32 )
        hash_2 = os.urandom( 32 )
        
        TG.test_controller.SetRead( 'playlists', [ ( 1, 'chill', 3 ), ( 2, 'Loud Stuff', 0 ) ] )
        
        ( status, body ) = api_call( 'GET', '/manage_playlists/get_playlists', self.everything )
        
        self.assertEqual( status, 200 )
        self.assertEqual( body[ 'playlists' ], [ { 'playlist_id' : 1, 'name' : 'chill', 'num_items' : 3 }, { 'playlist_id' : 2, 'name' : 'Loud Stuff', 'num_items' : 0 } ] )
        
        TG.test_controller.SetRead( 'playlists_containing_file', [ ( 1, 'chill', 2 ) ] )
        
        ( status, body ) = api_call( 'GET', '/manage_playlists/get_playlists', self.everything, { 'hash' : hash_1.hex() } )
        
        self.assertEqual( body[ 'playlists' ], [ { 'playlist_id' : 1, 'name' : 'chill', 'num_items' : 2 } ] )
        
        # a playlist by name is not case-sensitive, and blanks have their length
        TG.test_controller.SetRead( 'playlist_items', [ ( hash_1, None, None, False ), ( None, None, 1500, False ), ( hash_2, 1000, 5000, True ) ] )
        
        ( status, body ) = api_call( 'GET', '/manage_playlists/get_playlist', self.everything, { 'playlist_name' : 'loud   stuff' } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( body[ 'playlist' ][ 'playlist_id' ], 2 )
        self.assertEqual( body[ 'playlist' ][ 'items' ], [
            { 'hash' : hash_1.hex(), 'start_ms' : None, 'end_ms' : None, 'reverse' : False },
            { 'blank_ms' : 1500 },
            { 'hash' : hash_2.hex(), 'start_ms' : 1000, 'end_ms' : 5000, 'reverse' : True }
        ] )
        
        ( status, body ) = api_call( 'GET', '/manage_playlists/get_playlist', self.everything, { 'playlist_id' : 99 } )
        
        self.assertEqual( status, 404 )
        
        # new and rename. names have to be unique, not case-sensitive
        ( status, body ) = api_call( 'POST', '/manage_playlists/new_playlist', self.everything, { 'name' : 'CHILL' } )
        
        self.assertEqual( status, 409 )
        
        ( status, body ) = api_call( 'POST', '/manage_playlists/new_playlist', self.everything, { 'name' : '   ' } )
        
        self.assertEqual( status, 400 )
        
        with mock.patch.object( CG.client_controller, 'WriteSynchronous', return_value = 1 ) as write_synchronous:
            
            ( status, body ) = api_call( 'POST', '/manage_playlists/new_playlist', self.everything, { 'name' : '  morning   run ' } )
            
        
        self.assertEqual( status, 200 )
        write_synchronous.assert_called_once_with( 'playlist_new', 'morning run' )
        
        TG.test_controller.ClearWrites( 'playlist_rename' )
        
        ( status, body ) = api_call( 'POST', '/manage_playlists/rename_playlist', self.everything, { 'playlist_id' : 1, 'new_name' : 'loud stuff' } )
        
        self.assertEqual( status, 409 )
        
        # renaming to itself in other case is fine
        ( status, body ) = api_call( 'POST', '/manage_playlists/rename_playlist', self.everything, { 'playlist_id' : 1, 'new_name' : 'Chill' } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( TG.test_controller.GetWrite( 'playlist_rename' ), [ ( ( 1, 'Chill' ), {} ) ] )
        
        TG.test_controller.ClearWrites( 'playlist_delete' )
        
        ( status, body ) = api_call( 'POST', '/manage_playlists/delete_playlist', self.everything, { 'playlist_name' : 'chill' } )
        
        self.assertEqual( TG.test_controller.GetWrite( 'playlist_delete' ), [ ( ( 1, ), {} ) ] )
        
        # adding files, whole or part
        TG.test_controller.ClearWrites( 'playlist_add_item' )
        
        ( status, body ) = api_call( 'POST', '/manage_playlists/add_files', self.everything, { 'playlist_id' : 2, 'hashes' : [ hash_1.hex(), hash_2.hex() ] } )
        
        self.assertEqual( status, 200 )
        
        ( status, body ) = api_call( 'POST', '/manage_playlists/add_files', self.everything, { 'playlist_id' : 2, 'hash' : hash_1.hex(), 'start_ms' : 100, 'end_ms' : 200 } )
        
        self.assertEqual( TG.test_controller.GetWrite( 'playlist_add_item' ), [ ( ( 2, hash_1, None, None ), {} ), ( ( 2, hash_2, None, None ), {} ), ( ( 2, hash_1, 100, 200 ), {} ) ] )
        
        for ( start_ms, end_ms ) in ( ( 100, None ), ( 200, 100 ), ( -5, 100 ) ):
            
            ( status, body ) = api_call( 'POST', '/manage_playlists/add_files', self.everything, { 'playlist_id' : 2, 'hash' : hash_1.hex(), 'start_ms' : start_ms, 'end_ms' : end_ms } )
            
            self.assertEqual( status, 400, ( start_ms, end_ms ) )
            
        
        # blanks have limits
        TG.test_controller.ClearWrites( 'playlist_add_blank' )
        
        ( status, body ) = api_call( 'POST', '/manage_playlists/add_blank', self.everything, { 'playlist_id' : 2, 'blank_ms' : 0 } )
        
        self.assertEqual( status, 400 )
        
        ( status, body ) = api_call( 'POST', '/manage_playlists/add_blank', self.everything, { 'playlist_id' : 2, 'blank_ms' : 2500 } )
        
        self.assertEqual( TG.test_controller.GetWrite( 'playlist_add_blank' ), [ ( ( 2, 2500 ), {} ) ] )
        
        TG.test_controller.ClearWrites( 'playlist_remove_file' )
        
        ( status, body ) = api_call( 'POST', '/manage_playlists/remove_files', self.everything, { 'playlist_id' : 2, 'hash' : hash_2.hex() } )
        
        self.assertEqual( TG.test_controller.GetWrite( 'playlist_remove_file' ), [ ( ( 2, hash_2 ), {} ) ] )
        
        # setting the whole thing
        TG.test_controller.ClearWrites( 'playlist_items' )
        
        items = [ { 'hash' : hash_2.hex(), 'start_ms' : 0, 'end_ms' : 10, 'reverse' : True }, { 'blank_ms' : 300 }, { 'hash' : hash_1.hex() } ]
        
        ( status, body ) = api_call( 'POST', '/manage_playlists/set_items', self.everything, { 'playlist_id' : 2, 'items' : items } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( TG.test_controller.GetWrite( 'playlist_items' ), [ ( ( 2, [ ( hash_2, 0, 10, True ), ( None, None, 300, False ), ( hash_1, None, None, False ) ] ), {} ) ] )
        
        for bad_item in ( { 'hash' : 'abc' }, { 'nothing' : 1 }, 'hello', { 'hash' : hash_1.hex(), 'reverse' : 'yes' } ):
            
            ( status, body ) = api_call( 'POST', '/manage_playlists/set_items', self.everything, { 'playlist_id' : 2, 'items' : [ bad_item ] } )
            
            self.assertEqual( status, 400, bad_item )
            
        
        # playing one opens a media viewer
        with mock.patch.object( TG.test_controller.gui, 'OpenPlaylist', create = True, return_value = None ) as open_playlist:
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/open_playlist', self.everything, { 'playlist_name' : 'loud stuff' } )
            
        
        self.assertEqual( status, 200 )
        open_playlist.assert_called_once_with( 2 )
        
        with mock.patch.object( TG.test_controller.gui, 'OpenPlaylist', create = True, return_value = '"Loud Stuff" is empty!' ):
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/open_playlist', self.everything, { 'playlist_id' : 2 } )
            
        
        self.assertEqual( status, 409 )
        self.assertIn( 'is empty', body[ 'error' ] )
        
        # it needs the playlists permission as well as pages
        ( status, body ) = api_call( 'POST', '/manage_media_viewers/open_playlist', self.pages_only, { 'playlist_id' : 2 } )
        
        self.assertEqual( status, 403 )
        
    
    def test_virtual_paths( self ):
        
        hash_1 = os.urandom( 32 )
        hash_2 = os.urandom( 32 )
        
        TG.test_controller.SetRead( 'file_virtual_paths', { hash_1 : [ 'tv_shows/action', 'old' ] } )
        
        ( status, body ) = api_call( 'GET', '/manage_virtual_paths/get_paths', self.everything, { 'hashes' : [ hash_1.hex(), hash_2.hex() ] } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( body[ 'paths' ], { hash_1.hex() : [ 'old', 'tv_shows/action' ], hash_2.hex() : [] } )
        
        TG.test_controller.SetRead( 'all_file_virtual_paths', [ 'b', 'a' ] )
        
        ( status, body ) = api_call( 'GET', '/manage_virtual_paths/get_all_paths', self.everything )
        
        self.assertEqual( body[ 'paths' ], [ 'a', 'b' ] )
        
        # paths are cleaned up like the client does it
        TG.test_controller.ClearWrites( 'file_virtual_paths' )
        
        ( status, body ) = api_call( 'POST', '/manage_virtual_paths/add_paths', self.everything, { 'hashes' : [ hash_1.hex(), hash_2.hex() ], 'paths' : [ 'TV Shows\\\\Action', 'Movies//Comedy/' ] } )
        
        self.assertEqual( status, 200 )
        
        # the first file already had one of them
        [ ( ( hashes_to_paths, ), kwargs ) ] = TG.test_controller.GetWrite( 'file_virtual_paths' )
        
        self.assertEqual( { hash : set( paths ) for ( hash, paths ) in hashes_to_paths.items() }, { hash_1 : { 'tv_shows/action', 'old', 'movies/comedy' }, hash_2 : { 'tv_shows/action', 'movies/comedy' } } )
        
        ( status, body ) = api_call( 'POST', '/manage_virtual_paths/remove_paths', self.everything, { 'hashes' : [ hash_1.hex(), hash_2.hex() ], 'paths' : [ 'old' ] } )
        
        # the second file did not have it, so it is not changed
        [ ( ( hashes_to_paths, ), kwargs ) ] = TG.test_controller.GetWrite( 'file_virtual_paths' )
        
        self.assertEqual( hashes_to_paths, { hash_1 : [ 'tv_shows/action' ] } )
        
        ( status, body ) = api_call( 'POST', '/manage_virtual_paths/set_paths', self.everything, { 'hashes' : [ hash_1.hex(), hash_2.hex() ], 'paths' : [] } )
        
        [ ( ( hashes_to_paths, ), kwargs ) ] = TG.test_controller.GetWrite( 'file_virtual_paths' )
        
        self.assertEqual( hashes_to_paths, { hash_1 : [] } )
        
        # a path with a wildcard is for searching
        ( status, body ) = api_call( 'POST', '/manage_virtual_paths/set_paths', self.everything, { 'hash' : hash_1.hex(), 'paths' : [ 'tv/*' ] } )
        
        self.assertEqual( status, 400 )
        
    
    def test_snapshots( self ):
        
        hash_1 = os.urandom( 32 )
        snapshot_hash = os.urandom( 32 )
        
        snapshots_service_key = os.urandom( 32 )
        
        location_context = ClientLocation.LocationContext.STATICCreateSimple( snapshots_service_key )
        
        # no snapshots domain yet
        with mock.patch.object( ClientSnapshots, 'GetSnapshotsLocationContext', return_value = None ):
            
            ( status, body ) = api_call( 'GET', '/manage_snapshots/get_snapshots', self.snapshots_only, { 'hash' : hash_1.hex() } )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'snapshots_file_service_key' : None, 'snapshots' : { hash_1.hex() : [] } } )
        
        TG.test_controller.SetRead( 'file_snapshots', [ snapshot_hash ] )
        
        with mock.patch.object( ClientSnapshots, 'GetSnapshotsLocationContext', return_value = location_context ), mock.patch.object( ClientSnapshots, 'GetSnapshotsServiceKey', return_value = snapshots_service_key ):
            
            ( status, body ) = api_call( 'GET', '/manage_snapshots/get_snapshots', self.snapshots_only, { 'hash' : hash_1.hex() } )
            
        
        self.assertEqual( body, { 'snapshots_file_service_key' : snapshots_service_key.hex(), 'snapshots' : { hash_1.hex() : [ snapshot_hash.hex() ] } } )
        
        # importing one needs add files too
        image_path = HydrusStaticDir.GetStaticPath( 'hydrus.png' )
        
        ( status, body ) = api_call( 'POST', '/manage_snapshots/add_snapshot', self.snapshots_only, { 'hash' : hash_1.hex(), 'path' : image_path } )
        
        self.assertEqual( status, 403 )
        
        ( status, body ) = api_call( 'POST', '/manage_snapshots/add_snapshot', self.everything, { 'hash' : hash_1.hex(), 'path' : image_path + '_missing' } )
        
        self.assertEqual( status, 400 )
        
        with mock.patch.object( ClientSnapshots, 'ImportSnapshot', return_value = snapshot_hash ) as import_snapshot:
            
            ( status, body ) = api_call( 'POST', '/manage_snapshots/add_snapshot', self.everything, { 'hash' : hash_1.hex(), 'path' : image_path, 'timestamp_ms' : 2500 } )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'snapshot_hash' : snapshot_hash.hex() } )
        
        # it imports a copy
        ( ( imported_path, imported_hash, imported_timestamp_ms ), kwargs ) = import_snapshot.call_args
        
        self.assertNotEqual( imported_path, image_path )
        self.assertEqual( ( imported_hash, imported_timestamp_ms ), ( hash_1, 2500 ) )
        
        with mock.patch.object( ClientSnapshots, 'ImportSnapshot', side_effect = Exception( 'not an image' ) ):
            
            ( status, body ) = api_call( 'POST', '/manage_snapshots/add_snapshot', self.everything, { 'hash' : hash_1.hex(), 'path' : image_path } )
            
        
        self.assertEqual( status, 422 )
        self.assertIn( 'not an image', body[ 'error' ] )
        
    
    def test_exports( self ):
        
        from hydrus.client import ClientThreading
        from hydrus.client.exporting import ClientExportingAudio
        from hydrus.client.exporting import ClientExportingPlaylists
        from hydrus.client.exporting import ClientExportingVideo
        
        from hydrus.test import HelperFunctions as HF
        
        exporter = make_access( 'exporter', False, [ ClientAPI.CLIENT_API_PERMISSION_EXPORT_MEDIA ] )
        
        video_hash = os.urandom( 32 )
        
        video_media_result = HF.GetFakeMediaResult( video_hash, mime = HC.VIDEO_MP4 )
        
        video_media_result.GetFileInfoManager().duration_ms = 60000
        video_media_result.GetFileInfoManager().has_audio = True
        
        image_hash = os.urandom( 32 )
        
        image_media_result = HF.GetFakeMediaResult( image_hash, mime = HC.IMAGE_PNG )
        
        image_media_result.GetFileInfoManager().has_audio = False
        
        export_dir = tempfile.mkdtemp()
        
        try:
            
            job_status = ClientThreading.JobStatus()
            
            TG.test_controller.SetRead( 'media_result', video_media_result )
            
            # where it goes has to be a full path, in a folder that exists, and not over anything
            for bad_path in ( 'relative.mp4', os.path.join( export_dir, 'no_folder', 'x.mp4' ) ):
                
                ( status, body ) = api_call( 'POST', '/manage_exports/export_video', exporter, { 'hash' : video_hash.hex(), 'path' : bad_path } )
                
                self.assertEqual( status, 400, bad_path )
                
            
            existing_path = os.path.join( export_dir, 'already.mp4' )
            
            with open( existing_path, 'wb' ) as f:
                
                f.write( b'x' )
                
            
            ( status, body ) = api_call( 'POST', '/manage_exports/export_video', exporter, { 'hash' : video_hash.hex(), 'path' : existing_path } )
            
            self.assertEqual( status, 409 )
            
            # the extension goes on, and the popup's key comes back
            with mock.patch.object( ClientExportingVideo, 'StartVideoExport', return_value = job_status ) as start_video_export:
                
                ( status, body ) = api_call( 'POST', '/manage_exports/export_video', exporter, { 'hash' : video_hash.hex(), 'path' : os.path.join( export_dir, 'clip' ), 'start_ms' : 1000, 'end_ms' : 5000, 'resolution' : [ 1281, 721 ], 'quality' : 'best', 'audio_kbps' : None } )
                
            
            self.assertEqual( status, 200 )
            self.assertEqual( body, { 'path' : os.path.join( export_dir, 'clip.mp4' ), 'job_status_key' : job_status.GetKey().hex() } )
            
            ( ( media_result, settings, path ), kwargs ) = start_video_export.call_args
            
            self.assertEqual( settings, ClientExportingVideo.VideoExportSettings( export_format = ClientExportingVideo.VIDEO_EXPORT_FORMAT_MP4, resolution = ( 1280, 720 ), audio_kbps = None, quality_index = 0 ) )
            self.assertEqual( kwargs, { 'span_ms' : ( 1000, 5000 ) } )
            
            # part of a video cannot be the original file, and a target size has to fit
            ( status, body ) = api_call( 'POST', '/manage_exports/export_video', exporter, { 'hash' : video_hash.hex(), 'path' : os.path.join( export_dir, 'clip' ), 'start_ms' : 1000, 'end_ms' : 5000, 'format' : 'original' } )
            
            self.assertEqual( status, 400 )
            
            ( status, body ) = api_call( 'POST', '/manage_exports/export_video', exporter, { 'hash' : video_hash.hex(), 'path' : os.path.join( export_dir, 'tiny' ), 'target_size_bytes' : 10 } )
            
            self.assertEqual( status, 400 )
            
            for bad_params in ( { 'format' : 'gif' }, { 'quality' : 'amazing' }, { 'audio_kbps' : 7 }, { 'resolution' : [ 100 ] } ):
                
                ( status, body ) = api_call( 'POST', '/manage_exports/export_video', exporter, { 'hash' : video_hash.hex(), 'path' : os.path.join( export_dir, 'v' ), **bad_params } )
                
                self.assertEqual( status, 400, bad_params )
                
            
            with mock.patch.object( ClientExportingAudio, 'StartAudioExport', return_value = job_status ) as start_audio_export:
                
                ( status, body ) = api_call( 'POST', '/manage_exports/export_audio', exporter, { 'hash' : video_hash.hex(), 'path' : os.path.join( export_dir, 'sound' ), 'format' : 'wav', 'wav_bit_depth' : 24, 'channels' : 1 } )
                
            
            self.assertEqual( body[ 'path' ], os.path.join( export_dir, 'sound.wav' ) )
            
            ( ( media_result, settings, path ), kwargs ) = start_audio_export.call_args
            
            self.assertEqual( settings, ClientExportingAudio.AudioExportSettings( export_format = ClientExportingAudio.AUDIO_EXPORT_FORMAT_WAV, wav_bit_depth = 24, channels = 1 ) )
            self.assertEqual( kwargs, { 'span_ms' : None } )
            
            # an image is neither
            TG.test_controller.SetRead( 'media_result', image_media_result )
            
            ( status, body ) = api_call( 'POST', '/manage_exports/export_video', exporter, { 'hash' : image_hash.hex(), 'path' : os.path.join( export_dir, 'v' ) } )
            
            self.assertEqual( status, 400 )
            
            ( status, body ) = api_call( 'POST', '/manage_exports/export_audio', exporter, { 'hash' : image_hash.hex(), 'path' : os.path.join( export_dir, 'a' ) } )
            
            self.assertEqual( status, 400 )
            
            # a playlist, which needs the playlist permission too. a file that is gone is skipped, and blanks stay
            TG.test_controller.SetRead( 'playlists', [ ( 5, 'mix', 3 ) ] )
            TG.test_controller.SetRead( 'playlist_items', [ ( video_hash, 0, 2000, True ), ( None, None, 500, False ), ( os.urandom( 32 ), None, None, False ) ] )
            TG.test_controller.SetRead( 'media_results', [ video_media_result ] )
            
            ( status, body ) = api_call( 'POST', '/manage_exports/export_playlist', exporter, { 'playlist_id' : 5, 'path' : os.path.join( export_dir, 'mix' ) } )
            
            self.assertEqual( status, 403 )
            
            with mock.patch.object( ClientExportingPlaylists, 'StartPlaylistExport', return_value = job_status ) as start_playlist_export:
                
                ( status, body ) = api_call( 'POST', '/manage_exports/export_playlist', self.everything, { 'playlist_name' : 'MIX', 'path' : os.path.join( export_dir, 'mix' ) } )
                
            
            self.assertEqual( status, 200 )
            
            start_playlist_export.assert_called_once_with( 'mix', [ ( video_media_result, 0, 2000 ), ( None, None, 500 ) ], os.path.join( export_dir, 'mix.mp4' ) )
            
            TG.test_controller.SetRead( 'media_results', [] )
            
            ( status, body ) = api_call( 'POST', '/manage_exports/export_playlist', self.everything, { 'playlist_id' : 5, 'path' : os.path.join( export_dir, 'mix' ) } )
            
            self.assertEqual( status, 409 )
            
        finally:
            
            shutil.rmtree( export_dir )
            
        
    
    def test_file_viewer_data( self ):
        
        hash_1 = os.urandom( 32 )
        hash_2 = os.urandom( 32 )
        
        image_path = HydrusStaticDir.GetStaticPath( 'hydrus.png' )
        
        TG.test_controller.SetRead( 'file_viewer_rotation', 450.0 )
        TG.test_controller.SetRead( 'file_viewer_zoom', ( 2.0, ( 0.25, 0.75 ) ) )
        TG.test_controller.SetRead( 'file_viewer_screen_zooms', { '' : ( 2.0, ( 0.25, 0.75 ) ), 'DISPLAY2' : ( None, None ), 'DISPLAY1' : ( 0.5, ( 0.1, 0.2 ) ) } )
        TG.test_controller.SetRead( 'file_zoom_timestamps', [ ( 1000, 1.5, True, None, None, 90 ), ( 2000, 3.0, False, 0.5, 0.5, None ) ] )
        TG.test_controller.SetRead( 'file_playback_skips', [ ( 0, 500 ) ] )
        TG.test_controller.SetRead( 'file_playback_freezes', [ ( 3000, 2000 ), ( 100, 500 ) ] )
        TG.test_controller.SetRead( 'file_ab_loops', [ ( 9000, 12000 ), ( 0, 4500 ) ] )
        TG.test_controller.SetRead( 'file_segments', [ ( 9000, 'chorus' ), ( 100, 'intro' ) ] )
        TG.test_controller.SetRead( 'file_scripted_events', [ ( 50, 'echo hi' ) ] )
        TG.test_controller.SetRead( 'file_image_overlay', ( image_path, 0.5, ( 0.1, 0.2, 0.3, 0.4 ), True, False ) )
        
        ( status, body ) = api_call( 'GET', '/manage_file_viewer_data/get_data', self.everything, { 'hash' : hash_1.hex() } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, {
            'hash' : hash_1.hex(),
            'rotation' : 90,
            'zoom' : { 'zoom' : 2.0, 'center' : [ 0.25, 0.75 ] },
            # each screen's own. the one for any screen is 'zoom'
            'screen_zooms' : [
                { 'screen_name' : 'DISPLAY1', 'zoom' : 0.5, 'center' : [ 0.1, 0.2 ] },
                { 'screen_name' : 'DISPLAY2', 'zoom' : None, 'center' : None }
            ],
            'position_timestamps' : [
                { 'timestamp_ms' : 1000, 'zoom' : 1.5, 'zoom_is_relative' : True, 'center' : None, 'rotation' : 90 },
                { 'timestamp_ms' : 2000, 'zoom' : 3.0, 'zoom_is_relative' : False, 'center' : [ 0.5, 0.5 ], 'rotation' : None }
            ],
            'playback_skips' : [ { 'start_ms' : 0, 'end_ms' : 500 } ],
            'playback_freezes' : [ { 'timestamp_ms' : 100, 'duration_ms' : 500 }, { 'timestamp_ms' : 3000, 'duration_ms' : 2000 } ],
            'ab_loops' : [ { 'a_ms' : 0, 'b_ms' : 4500 }, { 'a_ms' : 9000, 'b_ms' : 12000 } ],
            'segments' : [ { 'timestamp_ms' : 100, 'name' : 'intro' }, { 'timestamp_ms' : 9000, 'name' : 'chorus' } ],
            'scripted_events' : [ { 'timestamp_ms' : 50, 'command' : 'echo hi' } ],
            'image_overlay' : { 'path' : image_path, 'opacity' : 0.5, 'x' : 0.1, 'y' : 0.2, 'width' : 0.3, 'height' : 0.4, 'locked' : True, 'stretch' : False }
        } )
        
        # one file at a time for this
        ( status, body ) = api_call( 'GET', '/manage_file_viewer_data/get_data', self.everything, { 'hashes' : [ hash_1.hex(), hash_2.hex() ] } )
        
        self.assertEqual( status, 400 )
        
        TG.test_controller.SetRead( 'num_file_viewer_zooms', 12 )
        TG.test_controller.SetRead( 'num_files_with_zoom_timestamps', 3 )
        
        ( status, body ) = api_call( 'GET', '/manage_file_viewer_data/get_saved_zoom_counts', self.everything )
        
        self.assertEqual( body, { 'num_files_with_saved_zoom' : 12, 'num_files_with_position_timestamps' : 3 } )
        
        # rotation and zoom, for many files
        TG.test_controller.ClearWrites( 'file_viewer_rotation' )
        
        ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_rotation', self.everything, { 'hashes' : [ hash_1.hex(), hash_2.hex() ], 'rotation' : -90 } )
        
        self.assertEqual( body, { 'rotation' : 270 } )
        self.assertEqual( TG.test_controller.GetWrite( 'file_viewer_rotation' ), [ ( ( hash_1, 270 ), {} ), ( ( hash_2, 270 ), {} ) ] )
        
        TG.test_controller.ClearWrites( 'file_viewer_zoom' )
        
        ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_zoom', self.everything, { 'hash' : hash_1.hex(), 'zoom' : 2, 'center' : [ 0.1, 0.9 ] } )
        ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_zoom', self.everything, { 'hash' : hash_1.hex() } )
        
        self.assertEqual( TG.test_controller.GetWrite( 'file_viewer_zoom' ), [ ( ( hash_1, 2.0, ( 0.1, 0.9 ), '' ), {} ), ( ( hash_1, None, None, '' ), {} ) ] )
        
        # just one screen's
        ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_zoom', self.everything, { 'hashes' : [ hash_1.hex(), hash_2.hex() ], 'zoom' : 0.5, 'screen_name' : 'DISPLAY2' } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( TG.test_controller.GetWrite( 'file_viewer_zoom' ), [ ( ( hash_1, 0.5, None, 'DISPLAY2' ), {} ), ( ( hash_2, 0.5, None, 'DISPLAY2' ), {} ) ] )
        
        for bad_params in ( { 'zoom' : 0 }, { 'center' : [ 0.5 ] }, { 'center' : [ 'a', 'b' ] } ):
            
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_zoom', self.everything, { 'hash' : hash_1.hex(), **bad_params } )
            
            self.assertEqual( status, 400, bad_params )
            
        
        # the ones that media viewers showing the file pick up straight away
        with mock.patch.object( CG.client_controller, 'pub' ) as pub:
            
            TG.test_controller.ClearWrites( 'file_zoom_timestamps' )
            
            position_timestamps = [ { 'timestamp_ms' : 2000, 'zoom' : 1 }, { 'timestamp_ms' : 500, 'zoom' : 2.5, 'center' : [ 0.5, 0.25 ], 'rotation' : 450 } ]
            
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_position_timestamps', self.everything, { 'hash' : hash_1.hex(), 'position_timestamps' : position_timestamps } )
            
            self.assertEqual( status, 200 )
            
            expected = [ ( 500, 2.5, 0.5, 0.25, 90 ), ( 2000, 1.0, None, None, None ) ]
            
            self.assertEqual( TG.test_controller.GetWrite( 'file_zoom_timestamps' ), [ ( ( hash_1, expected ), {} ) ] )
            pub.assert_called_with( 'new_file_zoom_timestamps', hash_1, expected )
            
            TG.test_controller.ClearWrites( 'file_playback_skips' )
            
            # overlapping ones become one
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_playback_skips', self.everything, { 'hash' : hash_1.hex(), 'playback_skips' : [ { 'start_ms' : 300, 'end_ms' : 900 }, { 'start_ms' : 0, 'end_ms' : 400 }, { 'start_ms' : 2000, 'end_ms' : 2100 } ] } )
            
            self.assertEqual( body, { 'playback_skips' : [ { 'start_ms' : 0, 'end_ms' : 900 }, { 'start_ms' : 2000, 'end_ms' : 2100 } ] } )
            self.assertEqual( TG.test_controller.GetWrite( 'file_playback_skips' ), [ ( ( hash_1, [ ( 0, 900 ), ( 2000, 2100 ) ] ), {} ) ] )
            pub.assert_called_with( 'new_file_playback_skips', hash_1, [ ( 0, 900 ), ( 2000, 2100 ) ] )
            
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_playback_skips', self.everything, { 'hash' : hash_1.hex(), 'playback_skips' : [ { 'start_ms' : 500, 'end_ms' : 500 } ] } )
            
            self.assertEqual( status, 400 )
            
            TG.test_controller.ClearWrites( 'file_playback_freezes' )
            
            # one per point, and the later one wins
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_playback_freezes', self.everything, { 'hash' : hash_1.hex(), 'playback_freezes' : [ { 'timestamp_ms' : 5000, 'duration_ms' : 1000 }, { 'timestamp_ms' : 0, 'duration_ms' : 2500 }, { 'timestamp_ms' : 5000, 'duration_ms' : 3000 } ] } )
            
            self.assertEqual( status, 200 )
            self.assertEqual( body, { 'playback_freezes' : [ { 'timestamp_ms' : 0, 'duration_ms' : 2500 }, { 'timestamp_ms' : 5000, 'duration_ms' : 3000 } ] } )
            self.assertEqual( TG.test_controller.GetWrite( 'file_playback_freezes' ), [ ( ( hash_1, [ ( 0, 2500 ), ( 5000, 3000 ) ] ), {} ) ] )
            pub.assert_called_with( 'new_file_playback_freezes', hash_1, [ ( 0, 2500 ), ( 5000, 3000 ) ] )
            
            for bad_freeze in ( { 'timestamp_ms' : 0, 'duration_ms' : 50 }, { 'timestamp_ms' : 0, 'duration_ms' : 3600001 }, { 'timestamp_ms' : -1, 'duration_ms' : 1000 }, { 'timestamp_ms' : 0 } ):
                
                ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_playback_freezes', self.everything, { 'hash' : hash_1.hex(), 'playback_freezes' : [ bad_freeze ] } )
                
                self.assertEqual( status, 400, bad_freeze )
                
            
            # clearing them
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_playback_freezes', self.everything, { 'hash' : hash_1.hex(), 'playback_freezes' : [] } )
            
            self.assertEqual( body, { 'playback_freezes' : [] } )
            pub.assert_called_with( 'new_file_playback_freezes', hash_1, [] )
            
            TG.test_controller.ClearWrites( 'file_ab_loops' )
            
            # in order, and the same one once
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_ab_loops', self.everything, { 'hash' : hash_1.hex(), 'ab_loops' : [ { 'a_ms' : 9000, 'b_ms' : 12000 }, { 'a_ms' : 0, 'b_ms' : 4500 }, { 'a_ms' : 9000, 'b_ms' : 12000 } ] } )
            
            self.assertEqual( status, 200 )
            self.assertEqual( body, { 'ab_loops' : [ { 'a_ms' : 0, 'b_ms' : 4500 }, { 'a_ms' : 9000, 'b_ms' : 12000 } ] } )
            self.assertEqual( TG.test_controller.GetWrite( 'file_ab_loops' ), [ ( ( hash_1, [ ( 0, 4500 ), ( 9000, 12000 ) ] ), {} ) ] )
            
            for bad_ab_loop in ( { 'a_ms' : 1000, 'b_ms' : 1050 }, { 'a_ms' : 5000, 'b_ms' : 1000 }, { 'a_ms' : -1, 'b_ms' : 1000 }, { 'b_ms' : 1000 }, { 'a_ms' : 0, 'b_ms' : 1.5 } ):
                
                ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_ab_loops', self.everything, { 'hash' : hash_1.hex(), 'ab_loops' : [ bad_ab_loop ] } )
                
                self.assertEqual( status, 400, bad_ab_loop )
                
            
            # clearing them
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_ab_loops', self.everything, { 'hash' : hash_1.hex(), 'ab_loops' : [] } )
            
            self.assertEqual( body, { 'ab_loops' : [] } )
            
            TG.test_controller.ClearWrites( 'file_image_overlay' )
            
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_image_overlay', self.everything, { 'hash' : hash_1.hex(), 'image_overlay' : { 'path' : image_path, 'opacity' : 0.75, 'width' : 0.5, 'height' : 0.5, 'stretch' : True } } )
            
            self.assertEqual( status, 200 )
            
            expected = ( image_path, 0.75, ( 0.0, 0.0, 0.5, 0.5 ), False, True )
            
            self.assertEqual( TG.test_controller.GetWrite( 'file_image_overlay' ), [ ( ( hash_1, expected ), {} ) ] )
            pub.assert_called_with( 'new_file_image_overlay', hash_1, expected, None )
            
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_image_overlay', self.everything, { 'hash' : hash_1.hex(), 'image_overlay' : None } )
            
            self.assertEqual( TG.test_controller.GetWrite( 'file_image_overlay' ), [ ( ( hash_1, None ), {} ) ] )
            
            for bad_overlay in ( { 'path' : image_path + '_missing' }, { 'path' : image_path, 'opacity' : 2 }, { 'path' : image_path, 'width' : 0 } ):
                
                ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_image_overlay', self.everything, { 'hash' : hash_1.hex(), 'image_overlay' : bad_overlay } )
                
                self.assertEqual( status, 400, bad_overlay )
                
            
            # scripted events run shell commands, so 'permits everything' is not enough
            scripted_events = [ { 'timestamp_ms' : 5000, 'command' : 'echo later' }, { 'timestamp_ms' : 0, 'command' : 'echo start' } ]
            
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_scripted_events', self.everything, { 'hash' : hash_1.hex(), 'scripted_events' : scripted_events } )
            
            self.assertEqual( status, 403 )
            
            TG.test_controller.ClearWrites( 'file_scripted_events' )
            
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_scripted_events', self.everything_and_scripts, { 'hash' : hash_1.hex(), 'scripted_events' : scripted_events } )
            
            self.assertEqual( status, 200 )
            
            expected = [ ( 0, 'echo start' ), ( 5000, 'echo later' ) ]
            
            self.assertEqual( TG.test_controller.GetWrite( 'file_scripted_events' ), [ ( ( hash_1, expected ), {} ) ] )
            pub.assert_called_with( 'new_file_scripted_events', hash_1, expected )
            
            # reset every file's zooms
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/reset_all_zooms', self.everything, {} )
            
            self.assertEqual( status, 400 )
            
            TG.test_controller.ClearWrites( 'clear_all_file_viewer_zooms' )
            TG.test_controller.ClearWrites( 'clear_all_file_zoom_timestamps' )
            
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/reset_all_zooms', self.everything, { 'position_timestamps' : True } )
            
            self.assertEqual( status, 200 )
            self.assertEqual( len( TG.test_controller.GetWrite( 'clear_all_file_zoom_timestamps' ) ), 1 )
            self.assertNotIn( 'clear_all_file_viewer_zooms', TG.test_controller._write_call_args )
            pub.assert_called_with( 'reset_all_file_zooms', False, True )
            
            # reset some files' positions
            TG.test_controller.ClearWrites( 'reset_file_viewer_positions' )
            
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/reset_positions', self.everything, { 'hashes' : [ hash_1.hex(), hash_2.hex() ] } )
            
            self.assertEqual( status, 200 )
            self.assertEqual( body, { 'num_files' : 2 } )
            self.assertEqual( TG.test_controller.GetWrite( 'reset_file_viewer_positions' ), [ ( ( { hash_1, hash_2 }, True, True, False ), {} ) ] )
            pub.assert_called_with( 'reset_file_viewer_positions', { hash_1, hash_2 }, True, True, False )
            
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/reset_positions', self.everything, { 'hash' : hash_1.hex(), 'saved_zooms' : False, 'rotations' : False, 'position_timestamps' : True } )
            
            self.assertEqual( TG.test_controller.GetWrite( 'reset_file_viewer_positions' ), [ ( ( { hash_1 }, False, False, True ), {} ) ] )
            
            # it has to reset something
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/reset_positions', self.everything, { 'hash' : hash_1.hex(), 'saved_zooms' : False, 'rotations' : False } )
            
            self.assertEqual( status, 400 )
            
            # or every file in a page, which needs the pages permission too
            page = mock.Mock()
            page.GetHashes.return_value = [ hash_2, hash_1 ]
            
            page_key = os.urandom( 32 )
            
            with mock.patch.object( TG.test_controller.gui, 'GetPageFromPageKey', create = True, side_effect = lambda key: page if key == page_key else None ):
                
                files_only = make_access( 'files only', False, [ ClientAPI.CLIENT_API_PERMISSION_EDIT_MEDIA_VIEWER_DATA ] )
                
                ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/reset_positions', files_only, { 'page_key' : page_key.hex() } )
                
                self.assertEqual( status, 403 )
                
                ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/reset_positions', self.everything, { 'page_key' : page_key.hex(), 'position_timestamps' : True } )
                
                self.assertEqual( status, 200 )
                self.assertEqual( body, { 'num_files' : 2 } )
                self.assertEqual( TG.test_controller.GetWrite( 'reset_file_viewer_positions' ), [ ( ( { hash_1, hash_2 }, True, True, True ), {} ) ] )
                
                ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/reset_positions', self.everything, { 'page_key' : os.urandom( 32 ).hex() } )
                
                self.assertEqual( status, 404 )
                
            
        
        # ignoring what is saved
        new_options = CG.client_controller.new_options
        
        ( status, body ) = api_call( 'GET', '/manage_file_viewer_data/get_ignore_saved_positions', self.everything )
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'ignore_saved_positions' : False } )
        
        with mock.patch.object( CG.client_controller, 'pub' ) as pub:
            
            ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_ignore_saved_positions', self.everything, { 'ignore_saved_positions' : True } )
            
            self.assertEqual( status, 200 )
            self.assertEqual( body, { 'ignore_saved_positions' : True } )
            self.assertTrue( new_options.GetBoolean( 'media_viewer_ignore_saved_positions' ) )
            pub.assert_called_with( 'media_viewer_ignore_saved_positions' )
            
        
        ( status, body ) = api_call( 'GET', '/manage_file_viewer_data/get_ignore_saved_positions', self.everything )
        
        self.assertEqual( body, { 'ignore_saved_positions' : True } )
        
        ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_ignore_saved_positions', self.everything, { 'ignore_saved_positions' : False } )
        
        self.assertEqual( status, 200 )
        self.assertFalse( new_options.GetBoolean( 'media_viewer_ignore_saved_positions' ) )
        
        ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_ignore_saved_positions', self.everything, {} )
        
        self.assertEqual( status, 400 )
        
        ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_ignore_saved_positions', self.counters_only, { 'ignore_saved_positions' : True } )
        
        self.assertEqual( status, 403 )
        self.assertFalse( new_options.GetBoolean( 'media_viewer_ignore_saved_positions' ) )
        
        # segments, which the media viewer loads each time, so there is no pub
        TG.test_controller.ClearWrites( 'file_segments' )
        
        ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_segments', self.everything, { 'hash' : hash_1.hex(), 'segments' : [ { 'timestamp_ms' : 900, 'name' : ' outro ' }, { 'timestamp_ms' : 10, 'name' : 'intro' }, { 'timestamp_ms' : 10, 'name' : 'intro' } ] } )
        
        self.assertEqual( TG.test_controller.GetWrite( 'file_segments' ), [ ( ( hash_1, [ ( 10, 'intro' ), ( 900, 'outro' ) ] ), {} ) ] )
        
        ( status, body ) = api_call( 'POST', '/manage_file_viewer_data/set_segments', self.everything, { 'hash' : hash_1.hex(), 'segments' : [ { 'timestamp_ms' : 10 } ] } )
        
        self.assertEqual( status, 400 )
        
    
    def test_presets( self ):
        
        new_options = TG.test_controller.new_options
        
        new_options.SetTagPresets( [ ( 'Cute Cats', [ 'cat', 'system:inbox' ] ) ] )
        
        ( status, body ) = api_call( 'GET', '/manage_tag_presets/get_tag_presets', self.everything )
        
        self.assertEqual( body, { 'tag_presets' : [ { 'name' : 'Cute Cats', 'entries' : [ 'cat', 'system:inbox' ] } ] } )
        
        # adding to one finds it by its lookup name, and skips what it has
        ( status, body ) = api_call( 'POST', '/manage_tag_presets/add_to_tag_preset', self.everything, { 'name' : 'cute_cats', 'entries' : [ 'CAT', '-dog' ] } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( new_options.GetTagPresets(), [ ( 'Cute Cats', [ 'cat', 'system:inbox', '-dog' ] ) ] )
        
        ( status, body ) = api_call( 'POST', '/manage_tag_presets/set_tag_presets', self.everything, { 'tag_presets' : [ { 'name' : 'a', 'entries' : [ ' Blue   Eyes ' ] }, { 'name' : 'A', 'entries' : [] } ] } )
        
        self.assertEqual( status, 400 )
        
        ( status, body ) = api_call( 'POST', '/manage_tag_presets/set_tag_presets', self.everything, { 'tag_presets' : [ { 'name' : 'a', 'entries' : [ ' Blue   Eyes ', 'blue eyes' ] }, { 'name' : 'b' } ] } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( new_options.GetTagPresets(), [ ( 'a', [ 'blue eyes' ] ), ( 'b', [] ) ] )
        
        ( status, body ) = api_call( 'POST', '/manage_tag_presets/delete_tag_preset', self.everything, { 'name' : 'B' } )
        
        self.assertEqual( new_options.GetTagPresets(), [ ( 'a', [ 'blue eyes' ] ) ] )
        
        ( status, body ) = api_call( 'POST', '/manage_tag_presets/delete_tag_preset', self.everything, { 'name' : 'B' } )
        
        self.assertEqual( status, 404 )
        
        # screen locations
        new_options.SetScreenLocations( [ ( 'left', 'DISPLAY1', 0, 0, 800, 600 ) ] )
        
        ( status, body ) = api_call( 'GET', '/manage_screen_locations/get_screen_locations', self.everything )
        
        self.assertEqual( body, { 'screen_locations' : [ { 'name' : 'left', 'screen_name' : 'DISPLAY1', 'x' : 0, 'y' : 0, 'width' : 800, 'height' : 600 } ] } )
        
        screen_locations = [ { 'name' : 'top', 'screen_name' : 'DISPLAY2', 'x' : -10, 'y' : 5, 'width' : 1920, 'height' : 540 } ]
        
        ( status, body ) = api_call( 'POST', '/manage_screen_locations/set_screen_locations', self.everything, { 'screen_locations' : screen_locations } )
        
        self.assertEqual( status, 200 )
        self.assertEqual( new_options.GetScreenLocations(), [ ( 'top', 'DISPLAY2', -10, 5, 1920, 540 ) ] )
        
        for bad_screen_locations in ( screen_locations * 2, [ { **screen_locations[0], 'width' : 0 } ], [ { **screen_locations[0], 'x' : 1.5 } ], [ { 'name' : 'top' } ] ):
            
            ( status, body ) = api_call( 'POST', '/manage_screen_locations/set_screen_locations', self.everything, { 'screen_locations' : bad_screen_locations } )
            
            self.assertEqual( status, 400, bad_screen_locations )
            
        
        new_options.SetTagPresets( [] )
        new_options.SetScreenLocations( [] )
        
    
    def test_media_viewers( self ):
        
        from hydrus.client import ClientMediaViewerLayouts
        from hydrus.client.gui import ClientGUIMediaViewerLayouts
        
        layout_json = json.loads( ClientMediaViewerLayouts.ConvertMediaViewerLayoutsToJSON( [] ) )
        
        with mock.patch.object( ClientGUIMediaViewerLayouts, 'GetOpenMediaViewerLayouts', return_value = [] ):
            
            ( status, body ) = api_call( 'GET', '/manage_media_viewers/get_layout', self.pages_only )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'layout' : layout_json } )
        
        ( status, body ) = api_call( 'POST', '/manage_media_viewers/open_layout', self.pages_only, { 'layout' : { 'not' : 'a layout' } } )
        
        self.assertEqual( status, 400 )
        
        with mock.patch.object( ClientGUIMediaViewerLayouts, 'OpenMediaViewerLayouts', return_value = ( 1, 2 ) ) as open_media_viewer_layouts:
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/open_layout', self.pages_only, { 'layout' : layout_json } )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'num_opened' : 1, 'num_skipped' : 2 } )
        open_media_viewer_layouts.assert_called_once()
        
        ( status, body ) = api_call( 'GET', '/manage_media_viewers/get_layout', self.counters_only )
        
        self.assertEqual( status, 403 )
        
        # a-b repeat
        
        from hydrus.client.gui import ClientGUIMediaViewerABRepeat
        
        canvas_key = b'\xab' * 32
        
        ab_repeat = [ { 'canvas_key' : canvas_key.hex(), 'a_ms' : None, 'b_ms' : 4500, 'ping_pong' : True } ]
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewersABRepeat', return_value = ab_repeat ):
            
            ( status, body ) = api_call( 'GET', '/manage_media_viewers/get_ab_repeat', self.pages_only )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'media_viewers' : ab_repeat } )
        
        # putting a loop on, like a saved A-B loop
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'SetOpenMediaViewersABRepeat', return_value = 2 ) as set_ab_repeat:
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/set_ab_repeat', self.pages_only, { 'a_ms' : 5250, 'b_ms' : 12000 } )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'num_media_viewers' : 2 } )
        set_ab_repeat.assert_called_once_with( 5250, 12000, canvas_key = None )
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'SetOpenMediaViewersABRepeat', return_value = 1 ) as set_ab_repeat:
            
            # from the start, just an A, and clearing
            for ( params, expected ) in ( ( { 'b_ms' : 4500 }, ( None, 4500 ) ), ( { 'a_ms' : 1000 }, ( 1000, None ) ), ( {}, ( None, None ) ) ):
                
                ( status, body ) = api_call( 'POST', '/manage_media_viewers/set_ab_repeat', self.pages_only, { **params, 'canvas_key' : canvas_key.hex() } )
                
                self.assertEqual( status, 200, params )
                set_ab_repeat.assert_called_with( *expected, canvas_key = canvas_key )
                
            
            for bad_params in ( { 'a_ms' : 1000, 'b_ms' : 1050 }, { 'b_ms' : 50 }, { 'a_ms' : -1 }, { 'a_ms' : 5000, 'b_ms' : 1000 } ):
                
                ( status, body ) = api_call( 'POST', '/manage_media_viewers/set_ab_repeat', self.pages_only, bad_params )
                
                self.assertEqual( status, 400, bad_params )
                
            
            self.assertEqual( set_ab_repeat.call_count, 3 )
            
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'SetOpenMediaViewersABRepeat', return_value = 0 ):
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/set_ab_repeat', self.pages_only, { 'b_ms' : 4500, 'canvas_key' : canvas_key.hex() } )
            
        
        self.assertEqual( status, 404 )
        
        ( status, body ) = api_call( 'POST', '/manage_media_viewers/set_ab_repeat', self.counters_only, { 'b_ms' : 4500 } )
        
        self.assertEqual( status, 403 )
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'SetOpenMediaViewersABRepeatPingPong', return_value = 3 ) as set_ping_pong:
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/set_ab_repeat_ping_pong', self.pages_only, { 'ping_pong' : True } )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'num_media_viewers' : 3 } )
        set_ping_pong.assert_called_once_with( True, canvas_key = None )
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'SetOpenMediaViewersABRepeatPingPong', return_value = 1 ) as set_ping_pong:
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/set_ab_repeat_ping_pong', self.pages_only, { 'ping_pong' : False, 'canvas_key' : canvas_key.hex() } )
            
        
        self.assertEqual( status, 200 )
        set_ping_pong.assert_called_once_with( False, canvas_key = canvas_key )
        
        # a media viewer that is not open
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'SetOpenMediaViewersABRepeatPingPong', return_value = 0 ):
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/set_ab_repeat_ping_pong', self.pages_only, { 'ping_pong' : True, 'canvas_key' : canvas_key.hex() } )
            
        
        self.assertEqual( status, 404 )
        
        ( status, body ) = api_call( 'POST', '/manage_media_viewers/set_ab_repeat_ping_pong', self.pages_only, {} )
        
        self.assertEqual( status, 400 )
        
        ( status, body ) = api_call( 'POST', '/manage_media_viewers/set_ab_repeat_ping_pong', self.counters_only, { 'ping_pong' : True } )
        
        self.assertEqual( status, 403 )
        
        # slideshows
        
        from hydrus.client.gui import ClientGUIMediaViewerSlideshows
        
        slideshows = [ { 'canvas_key' : canvas_key.hex(), 'supports_slideshow' : True, 'running' : True, 'period' : 0.0 } ]
        
        with mock.patch.object( ClientGUIMediaViewerSlideshows, 'GetOpenMediaViewersSlideshows', return_value = slideshows ):
            
            ( status, body ) = api_call( 'GET', '/manage_media_viewers/get_slideshows', self.pages_only )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'media_viewers' : slideshows } )
        
        # 0 plays each file once through
        with mock.patch.object( ClientGUIMediaViewerSlideshows, 'StartOpenMediaViewersSlideshow', return_value = 2 ) as start_slideshow:
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/start_slideshow', self.pages_only, { 'period' : 0 } )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'num_media_viewers' : 2 } )
        start_slideshow.assert_called_once_with( 0.0, canvas_key = None )
        
        with mock.patch.object( ClientGUIMediaViewerSlideshows, 'StartOpenMediaViewersSlideshow', return_value = 1 ) as start_slideshow:
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/start_slideshow', self.pages_only, { 'period' : 2.5, 'canvas_key' : canvas_key.hex() } )
            
        
        self.assertEqual( status, 200 )
        start_slideshow.assert_called_once_with( 2.5, canvas_key = canvas_key )
        
        with mock.patch.object( ClientGUIMediaViewerSlideshows, 'StartOpenMediaViewersSlideshow', return_value = 1 ) as start_slideshow:
            
            for bad_params in ( { 'period' : -1 }, {} ):
                
                ( status, body ) = api_call( 'POST', '/manage_media_viewers/start_slideshow', self.pages_only, bad_params )
                
                self.assertEqual( status, 400, bad_params )
                
            
            start_slideshow.assert_not_called()
            
        
        # a media viewer that is not open, or cannot run one
        with mock.patch.object( ClientGUIMediaViewerSlideshows, 'StartOpenMediaViewersSlideshow', return_value = 0 ):
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/start_slideshow', self.pages_only, { 'period' : 0, 'canvas_key' : canvas_key.hex() } )
            
        
        self.assertEqual( status, 404 )
        
        with mock.patch.object( ClientGUIMediaViewerSlideshows, 'StopOpenMediaViewersSlideshow', return_value = 3 ) as stop_slideshow:
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/stop_slideshow', self.pages_only, {} )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'num_media_viewers' : 3 } )
        stop_slideshow.assert_called_once_with( canvas_key = None )
        
        with mock.patch.object( ClientGUIMediaViewerSlideshows, 'StopOpenMediaViewersSlideshow', return_value = 0 ):
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/stop_slideshow', self.pages_only, { 'canvas_key' : canvas_key.hex() } )
            
        
        self.assertEqual( status, 404 )
        
        ( status, body ) = api_call( 'POST', '/manage_media_viewers/start_slideshow', self.counters_only, { 'period' : 0 } )
        
        self.assertEqual( status, 403 )
        
        # screens, and showing files how they are on another one
        
        from hydrus.client.gui import ClientGUIMediaViewerScreens
        
        screens_info = {
            'screens' : [ { 'screen_name' : 'DISPLAY1', 'x' : 0, 'y' : 0, 'width' : 1920, 'height' : 1080, 'primary' : True } ],
            'media_viewers' : [ { 'canvas_key' : canvas_key.hex(), 'screen_name' : 'DISPLAY1', 'hash' : None } ]
        }
        
        with mock.patch.object( ClientGUIMediaViewerScreens, 'GetScreensAPIInfo', return_value = screens_info ):
            
            ( status, body ) = api_call( 'GET', '/manage_media_viewers/get_screens', self.pages_only )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, screens_info )
        
        with mock.patch.object( ClientGUIMediaViewerScreens, 'ApplyOpenMediaViewersScreenZoom', return_value = 2 ) as apply_screen_zoom:
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/apply_screen_zoom', self.pages_only, { 'screen_name' : 'DISPLAY2' } )
            
        
        self.assertEqual( status, 200 )
        self.assertEqual( body, { 'num_media_viewers' : 2 } )
        apply_screen_zoom.assert_called_once_with( 'DISPLAY2', canvas_key = None )
        
        with mock.patch.object( ClientGUIMediaViewerScreens, 'ApplyOpenMediaViewersScreenZoom', return_value = 1 ) as apply_screen_zoom:
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/apply_screen_zoom', self.pages_only, { 'screen_name' : 'DISPLAY2', 'canvas_key' : canvas_key.hex() } )
            
        
        self.assertEqual( status, 200 )
        apply_screen_zoom.assert_called_once_with( 'DISPLAY2', canvas_key = canvas_key )
        
        # a media viewer that is not open
        with mock.patch.object( ClientGUIMediaViewerScreens, 'ApplyOpenMediaViewersScreenZoom', return_value = 0 ):
            
            ( status, body ) = api_call( 'POST', '/manage_media_viewers/apply_screen_zoom', self.pages_only, { 'screen_name' : 'DISPLAY2', 'canvas_key' : canvas_key.hex() } )
            
        
        self.assertEqual( status, 404 )
        
        ( status, body ) = api_call( 'POST', '/manage_media_viewers/apply_screen_zoom', self.pages_only, {} )
        
        self.assertEqual( status, 400 )
        
        ( status, body ) = api_call( 'GET', '/manage_media_viewers/get_screens', self.counters_only )
        
        self.assertEqual( status, 403 )
        
    
    
    def test_command_line( self ):
        
        # the whole way: the cli, to the Client API, to the client
        TG.test_controller.SetRead( 'playlists', [ ( 4, 'chill', 1 ) ] )
        
        api_permissions = make_access( 'cli', False, [ ClientAPI.CLIENT_API_PERMISSION_MANAGE_PLAYLISTS ] )
        
        class FakeStdout( object ):
            
            def __init__( self ):
                
                self.text = ''
                
            
            def write( self, text ):
                
                self.text += text
                
            
        
        stdout = FakeStdout()
        
        environ = { hydrus_cli.ENV_URL : f'http://127.0.0.1:{PORT}', hydrus_cli.ENV_KEY : api_permissions.GetAccessKey().hex() }
        
        config_dir = tempfile.mkdtemp()
        
        config_path = os.path.join( config_dir, 'config.json' )
        
        result = hydrus_cli.Run( [ '--config', config_path, 'playlists', 'list' ], stdout = stdout, environ = environ )
        
        self.assertEqual( result, 0 )
        self.assertEqual( json.loads( stdout.text ), { 'playlists' : [ { 'playlist_id' : 4, 'name' : 'chill', 'num_items' : 1 } ] } )
        
        # a permission it does not have
        result = hydrus_cli.Run( [ '--config', config_path, 'counters', 'list' ], stdout = stdout, environ = environ )
        
        self.assertEqual( result, 1 )
        
        # config saves the key
        result = hydrus_cli.Run( [ '--config', config_path, 'config', '--key', 'abcdef0123456789' ], stdout = stdout, environ = {} )
        
        self.assertEqual( result, 0 )
        self.assertEqual( hydrus_cli.LoadConfig( config_path ), { 'access_key' : 'abcdef0123456789' } )
        
        shutil.rmtree( config_dir )
        
class TestClientAPIForkCommandLine( unittest.TestCase ):
    
    def _GetRequest( self, argv ) -> hydrus_cli.APIRequest:
        
        args = hydrus_cli.GetArgumentParser().parse_args( argv )
        
        return hydrus_cli.BuildRequest( args )
        
    
    def test_requests( self ):
        
        hash_hex = 'ab' * 32
        
        self.assertEqual( self._GetRequest( [ 'version' ] ), hydrus_cli.APIRequest( 'GET', '/api_version', needs_key = False ) )
        
        # files are hashes or file_ids
        self.assertEqual( self._GetRequest( [ 'metadata', hash_hex.upper(), '12' ] ), hydrus_cli.APIRequest( 'GET', '/get_files/file_metadata', { 'hashes' : [ hash_hex ], 'file_ids' : [ 12 ] } ) )
        
        with self.assertRaises( hydrus_cli.CLIError ):
            
            self._GetRequest( [ 'metadata', 'not_a_file' ] )
            
        
        # counters are names or ids, and playlists are names or ids
        self.assertEqual( self._GetRequest( [ 'counters', 'set', 'tally', '5', '12' ] ), hydrus_cli.APIRequest( 'POST', '/manage_counters/set_count', { 'counter_name' : 'tally', 'count' : 5, 'file_ids' : [ 12 ] } ) )
        self.assertEqual( self._GetRequest( [ 'counters', 'inc', hash_hex, '12', '--by', '-2' ] ), hydrus_cli.APIRequest( 'POST', '/manage_counters/increment_count', { 'counter_id' : hash_hex, 'delta' : -2, 'file_ids' : [ 12 ] } ) )
        self.assertEqual( self._GetRequest( [ 'playlists', 'play', '3' ] ), hydrus_cli.APIRequest( 'POST', '/manage_media_viewers/open_playlist', { 'playlist_id' : 3 } ) )
        
        # a-b repeat
        self.assertEqual( self._GetRequest( [ 'viewers', 'ab-repeat' ] ), hydrus_cli.APIRequest( 'GET', '/manage_media_viewers/get_ab_repeat' ) )
        self.assertEqual( self._GetRequest( [ 'viewers', 'ping-pong', 'on' ] ), hydrus_cli.APIRequest( 'POST', '/manage_media_viewers/set_ab_repeat_ping_pong', { 'ping_pong' : True } ) )
        self.assertEqual( self._GetRequest( [ 'viewers', 'set-ab-repeat', '--a-ms', '5250', '--b-ms', '12000' ] ), hydrus_cli.APIRequest( 'POST', '/manage_media_viewers/set_ab_repeat', { 'a_ms' : 5250, 'b_ms' : 12000 } ) )
        self.assertEqual( self._GetRequest( [ 'viewers', 'set-ab-repeat', '--viewer', hash_hex.upper() ] ), hydrus_cli.APIRequest( 'POST', '/manage_media_viewers/set_ab_repeat', { 'a_ms' : None, 'b_ms' : None, 'canvas_key' : hash_hex } ) )
        self.assertEqual( self._GetRequest( [ 'viewer', 'ab-loops', '12', '[ { "a_ms" : 0, "b_ms" : 4500 } ]' ] ), hydrus_cli.APIRequest( 'POST', '/manage_file_viewer_data/set_ab_loops', { 'file_ids' : [ 12 ], 'ab_loops' : [ { 'a_ms' : 0, 'b_ms' : 4500 } ] } ) )
        self.assertEqual( self._GetRequest( [ 'viewers', 'ping-pong', 'off', '--viewer', hash_hex.upper() ] ), hydrus_cli.APIRequest( 'POST', '/manage_media_viewers/set_ab_repeat_ping_pong', { 'ping_pong' : False, 'canvas_key' : hash_hex } ) )
        self.assertEqual( self._GetRequest( [ 'viewers', 'slideshows' ] ), hydrus_cli.APIRequest( 'GET', '/manage_media_viewers/get_slideshows' ) )
        self.assertEqual( self._GetRequest( [ 'viewers', 'slideshow', 'start', '0' ] ), hydrus_cli.APIRequest( 'POST', '/manage_media_viewers/start_slideshow', { 'period' : 0.0 } ) )
        self.assertEqual( self._GetRequest( [ 'viewers', 'slideshow', 'start', '2.5', '--viewer', hash_hex.upper() ] ), hydrus_cli.APIRequest( 'POST', '/manage_media_viewers/start_slideshow', { 'period' : 2.5, 'canvas_key' : hash_hex } ) )
        self.assertEqual( self._GetRequest( [ 'viewers', 'slideshow', 'stop' ] ), hydrus_cli.APIRequest( 'POST', '/manage_media_viewers/stop_slideshow', {} ) )
        
        with self.assertRaises( hydrus_cli.CLIError ):
            
            self._GetRequest( [ 'viewers', 'slideshow', 'start' ] )
            
        self.assertEqual( self._GetRequest( [ 'viewers', 'screens' ] ), hydrus_cli.APIRequest( 'GET', '/manage_media_viewers/get_screens' ) )
        self.assertEqual( self._GetRequest( [ 'viewers', 'screen-zoom', '\\\\.\\DISPLAY2' ] ), hydrus_cli.APIRequest( 'POST', '/manage_media_viewers/apply_screen_zoom', { 'screen_name' : '\\\\.\\DISPLAY2' } ) )
        self.assertEqual( self._GetRequest( [ 'viewers', 'screen-zoom', 'DISPLAY2', '--viewer', hash_hex.upper() ] ), hydrus_cli.APIRequest( 'POST', '/manage_media_viewers/apply_screen_zoom', { 'screen_name' : 'DISPLAY2', 'canvas_key' : hash_hex } ) )
        self.assertEqual( self._GetRequest( [ 'viewer', 'zoom', '12', '--zoom', '2', '--screen', 'DISPLAY2' ] ), hydrus_cli.APIRequest( 'POST', '/manage_file_viewer_data/set_zoom', { 'zoom' : 2.0, 'center' : None, 'file_ids' : [ 12 ], 'screen_name' : 'DISPLAY2' } ) )
        self.assertEqual( self._GetRequest( [ 'playlists', 'add', 'chill', '12', '--start-ms', '0', '--end-ms', '500' ] ), hydrus_cli.APIRequest( 'POST', '/manage_playlists/add_files', { 'playlist_name' : 'chill', 'file_ids' : [ 12 ], 'start_ms' : 0, 'end_ms' : 500 } ) )
        self.assertEqual( self._GetRequest( [ 'playlists', 'set', 'chill', '[ { "blank_ms" : 100 } ]' ] ), hydrus_cli.APIRequest( 'POST', '/manage_playlists/set_items', { 'playlist_name' : 'chill', 'items' : [ { 'blank_ms' : 100 } ] } ) )
        self.assertEqual( self._GetRequest( [ 'paths', 'remove', '12', '--path', 'a/b', '--path', 'c' ] ), hydrus_cli.APIRequest( 'POST', '/manage_virtual_paths/remove_paths', { 'paths' : [ 'a/b', 'c' ], 'file_ids' : [ 12 ] } ) )
        self.assertEqual( self._GetRequest( [ 'viewer', 'zoom', '12', '--zoom', '2', '--center', '0.5', '0.25' ] ), hydrus_cli.APIRequest( 'POST', '/manage_file_viewer_data/set_zoom', { 'zoom' : 2.0, 'center' : [ 0.5, 0.25 ], 'file_ids' : [ 12 ] } ) )
        self.assertEqual( self._GetRequest( [ 'viewer', 'overlay', '12', 'none' ] ), hydrus_cli.APIRequest( 'POST', '/manage_file_viewer_data/set_image_overlay', { 'file_ids' : [ 12 ], 'image_overlay' : None } ) )
        self.assertEqual( self._GetRequest( [ 'viewer', 'freezes', '12', '[ { "timestamp_ms" : 3000, "duration_ms" : 2000 } ]' ] ), hydrus_cli.APIRequest( 'POST', '/manage_file_viewer_data/set_playback_freezes', { 'file_ids' : [ 12 ], 'playback_freezes' : [ { 'timestamp_ms' : 3000, 'duration_ms' : 2000 } ] } ) )
        self.assertEqual( self._GetRequest( [ 'viewer', 'reset-positions', '12', hash_hex, '--keep-rotations' ] ), hydrus_cli.APIRequest( 'POST', '/manage_file_viewer_data/reset_positions', { 'saved_zooms' : True, 'rotations' : False, 'position_timestamps' : False, 'hashes' : [ hash_hex ], 'file_ids' : [ 12 ] } ) )
        self.assertEqual( self._GetRequest( [ 'viewer', 'ignore-positions' ] ), hydrus_cli.APIRequest( 'GET', '/manage_file_viewer_data/get_ignore_saved_positions' ) )
        self.assertEqual( self._GetRequest( [ 'viewer', 'ignore-positions', 'on' ] ), hydrus_cli.APIRequest( 'POST', '/manage_file_viewer_data/set_ignore_saved_positions', { 'ignore_saved_positions' : True } ) )
        self.assertEqual( self._GetRequest( [ 'viewer', 'ignore-positions', 'off' ] ), hydrus_cli.APIRequest( 'POST', '/manage_file_viewer_data/set_ignore_saved_positions', { 'ignore_saved_positions' : False } ) )
        self.assertEqual( self._GetRequest( [ 'viewer', 'reset-positions', '--page', hash_hex.upper(), '--position-timestamps' ] ), hydrus_cli.APIRequest( 'POST', '/manage_file_viewer_data/reset_positions', { 'saved_zooms' : True, 'rotations' : True, 'position_timestamps' : True, 'page_key' : hash_hex } ) )
        
        # files or a page, not both or neither
        for argv in ( [ 'viewer', 'reset-positions' ], [ 'viewer', 'reset-positions', '12', '--page', hash_hex ] ):
            
            with self.assertRaises( hydrus_cli.CLIError ):
                
                self._GetRequest( argv )
                
            
        
        self.assertEqual( self._GetRequest( [ 'request-key', 'cli', '--permission', 'manage_playlists', '--permission', '107' ] ), hydrus_cli.APIRequest( 'GET', '/request_new_permissions', { 'name' : 'cli', 'permits_everything' : False, 'basic_permissions' : [ 101, 107 ] }, needs_key = False ) )
        
        self.assertEqual( self._GetRequest( [ 'export', 'video', '12', os.path.abspath( 'x' ), '--start-ms', '0', '--end-ms', '10', '--no-audio', '--quality', 'low' ] ), hydrus_cli.APIRequest( 'POST', '/manage_exports/export_video', { 'file_ids' : [ 12 ], 'path' : os.path.abspath( 'x' ), 'format' : 'mp4', 'start_ms' : 0, 'end_ms' : 10, 'quality' : 'low', 'audio_kbps' : None } ) )
        self.assertEqual( self._GetRequest( [ 'export', 'playlist', 'mix', os.path.abspath( 'x' ) ] ), hydrus_cli.APIRequest( 'POST', '/manage_exports/export_playlist', { 'playlist_name' : 'mix', 'path' : os.path.abspath( 'x' ) } ) )
        
        # anything else goes through call
        self.assertEqual( self._GetRequest( [ 'call', 'get', 'manage_pages/get_pages', '-p', 'simple=true', '-p', 'name=x' ] ), hydrus_cli.APIRequest( 'GET', '/manage_pages/get_pages', { 'simple' : True, 'name' : 'x' } ) )
        
        # get params are json where the Client API wants it
        self.assertEqual( hydrus_cli.EncodeGETParams( { 'hashes' : [ 'ab' ], 'playlist_id' : 3, 'name' : 'x y', 'flag' : True } ), 'hashes=%5B%22ab%22%5D&playlist_id=3&name=x+y&flag=true' )
class TestClientAPIForkBootArguments( unittest.TestCase ):
    
    def test_port_settings( self ):
        
        try:
            
            # nothing from the command line: the service's own settings
            self.assertEqual( ClientServices.GetLocalServerPortSettings( HC.CLIENT_API_SERVICE, None, False ), ( None, False ) )
            self.assertEqual( ClientServices.GetLocalServerPortSettings( HC.CLIENT_API_SERVICE, 45869, True ), ( 45869, True ) )
            
            # --client_api_port turns it on, or moves it
            CG.CLIENT_API_PORT_COMMAND_LINE = 50000
            
            self.assertEqual( ClientServices.GetLocalServerPortSettings( HC.CLIENT_API_SERVICE, None, False ), ( 50000, False ) )
            self.assertEqual( ClientServices.GetLocalServerPortSettings( HC.CLIENT_API_SERVICE, 45869, True ), ( 50000, True ) )
            
            # --client_api_allow_non_local_connections opens it up
            CG.CLIENT_API_ALLOW_NON_LOCAL_CONNECTIONS_COMMAND_LINE = True
            
            self.assertEqual( ClientServices.GetLocalServerPortSettings( HC.CLIENT_API_SERVICE, None, False ), ( 50000, True ) )
            
            # it is only for the Client API
            self.assertEqual( ClientServices.GetLocalServerPortSettings( HC.LOCAL_BOORU, 1234, False ), ( 1234, False ) )
            
        finally:
            
            CG.CLIENT_API_PORT_COMMAND_LINE = None
            CG.CLIENT_API_ALLOW_NON_LOCAL_CONNECTIONS_COMMAND_LINE = False
            
        
    

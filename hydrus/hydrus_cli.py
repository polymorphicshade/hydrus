# a command line tool for the client, through its Client API
# it only uses the standard library, so it runs with any python 3, without hydrus's own requirements
# the client has to be running with the Client API on. start it with --client_api_port 45869 to turn it on just for that session

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = 'http://127.0.0.1:45869'

ACCESS_KEY_HEADER = 'Hydrus-Client-API-Access-Key'

ENV_URL = 'HYDRUS_API_URL'
ENV_KEY = 'HYDRUS_API_KEY'

HEX_64_RE = re.compile( r'^[0-9a-fA-F]{64}$' )

# basic permission names, for request-key. the numbers are what the Client API uses
PERMISSION_NAMES_TO_NUMBERS = {
    'add_urls' : 0,
    'add_files' : 1,
    'add_tags' : 2,
    'search_files' : 3,
    'manage_pages' : 4,
    'manage_headers' : 5,
    'manage_database' : 6,
    'add_notes' : 7,
    'manage_file_relationships' : 8,
    'edit_ratings' : 9,
    'manage_popups' : 10,
    'edit_times' : 11,
    'commit_pending' : 12,
    'see_local_paths' : 13,
    'edit_counters' : 100,
    'manage_playlists' : 101,
    'edit_virtual_paths' : 102,
    'manage_snapshots' : 103,
    'edit_media_viewer_data' : 104,
    'manage_tag_presets' : 105,
    'manage_screen_locations' : 106,
    'edit_scripted_events' : 107,
    'export_media' : 108
}

class CLIError( Exception ):
    
    pass
    

class APIRequest( object ):
    
    # what one command asks the Client API for
    def __init__( self, method: str, path: str, params: dict | None = None, needs_key: bool = True ):
        
        self.method = method
        self.path = path
        self.params = {} if params is None else params
        self.needs_key = needs_key
        
    
    def __eq__( self, other ):
        
        return isinstance( other, APIRequest ) and ( self.method, self.path, self.params, self.needs_key ) == ( other.method, other.path, other.params, other.needs_key )
        
    
    def __repr__( self ):
        
        return f'APIRequest( {self.method} {self.path} {self.params} )'
        
    

def GetDefaultConfigPath() -> str:
    
    if sys.platform == 'win32' and 'APPDATA' in os.environ:
        
        base_dir = os.environ[ 'APPDATA' ]
        
    else:
        
        base_dir = os.environ.get( 'XDG_CONFIG_HOME', os.path.join( os.path.expanduser( '~' ), '.config' ) )
        
    
    return os.path.join( base_dir, 'hydrus_cli', 'config.json' )
    

def LoadConfig( path: str ) -> dict:
    
    if not os.path.exists( path ):
        
        return {}
        
    
    try:
        
        with open( path, 'r', encoding = 'utf-8' ) as f:
            
            config = json.load( f )
            
        
    except ( OSError, ValueError ) as e:
        
        raise CLIError( f'Could not read the config file at "{path}": {e}' )
        
    
    return config if isinstance( config, dict ) else {}
    

def SaveConfig( path: str, config: dict ):
    
    os.makedirs( os.path.dirname( path ), exist_ok = True )
    
    with open( path, 'w', encoding = 'utf-8' ) as f:
        
        json.dump( config, f, indent = 2 )
        
    
    # it has an access key in it
    if sys.platform != 'win32':
        
        os.chmod( path, 0o600 )
        
    

def ParseFiles( files: list[ str ] ) -> dict:
    
    # a file is its sha256 hash in hex, or its file_id
    hashes = []
    file_ids = []
    
    for file in files:
        
        if HEX_64_RE.match( file ) is not None:
            
            hashes.append( file.lower() )
            
        elif file.isdigit():
            
            file_ids.append( int( file ) )
            
        else:
            
            raise CLIError( f'"{file}" is not a file! Give a sha256 hash, in hex, or a file_id.' )
            
        
    
    params = {}
    
    if len( hashes ) > 0:
        
        params[ 'hashes' ] = hashes
        
    
    if len( file_ids ) > 0:
        
        params[ 'file_ids' ] = file_ids
        
    
    return params
    

def ParseCounter( counter: str ) -> dict:
    
    # a counter is its id, in hex, or its name
    if HEX_64_RE.match( counter ) is not None:
        
        return { 'counter_id' : counter.lower() }
        
    
    return { 'counter_name' : counter }
    

def ParsePlaylist( playlist: str ) -> dict:
    
    # a playlist is its id or its name
    if playlist.isdigit():
        
        return { 'playlist_id' : int( playlist ) }
        
    
    return { 'playlist_name' : playlist }
    

def ParseJSONArgument( text: str ):
    
    # some json, '@path' for the json in a file, or '-' for the json on stdin
    try:
        
        if text == '-':
            
            return json.load( sys.stdin )
            
        
        if text.startswith( '@' ):
            
            with open( text[ 1 : ], 'r', encoding = 'utf-8' ) as f:
                
                return json.load( f )
                
            
        
        return json.loads( text )
        
    except ( OSError, ValueError ) as e:
        
        raise CLIError( f'Could not read that json: {e}' )
        
    

def ParseKeyValueParams( key_values: list[ str ] ) -> dict:
    
    # name=value. a value that is json, like 5, true, or ["a"], goes in as that, and anything else is a string
    params = {}
    
    for key_value in key_values:
        
        if '=' not in key_value:
            
            raise CLIError( f'"{key_value}" is not name=value!' )
            
        
        ( key, value ) = key_value.split( '=', 1 )
        
        try:
            
            params[ key ] = json.loads( value )
            
        except ValueError:
            
            params[ key ] = value
            
        
    
    return params
    

def EncodeGETParams( params: dict ) -> str:
    
    # strings and numbers go as they are, and lists, objects, and bools go as json, like the Client API wants
    encoded = {}
    
    for ( key, value ) in params.items():
        
        if isinstance( value, ( list, dict, bool ) ) or value is None:
            
            encoded[ key ] = json.dumps( value )
            
        else:
            
            encoded[ key ] = str( value )
            
        
    
    return urllib.parse.urlencode( encoded )
    

def DoRequest( url: str, access_key: str | None, api_request: APIRequest, opener = urllib.request.urlopen ):
    
    headers = {}
    
    if api_request.needs_key:
        
        if access_key is None:
            
            raise CLIError( f'This needs an access key! Give one with --key, set {ENV_KEY}, or save one with "config --key".' )
            
        
        headers[ ACCESS_KEY_HEADER ] = access_key
        
    
    full_url = url.rstrip( '/' ) + api_request.path
    
    if api_request.method == 'GET':
        
        if len( api_request.params ) > 0:
            
            full_url += '?' + EncodeGETParams( api_request.params )
            
        
        data = None
        
    else:
        
        headers[ 'Content-Type' ] = 'application/json'
        
        data = json.dumps( api_request.params ).encode( 'utf-8' )
        
    
    request = urllib.request.Request( full_url, data = data, headers = headers, method = api_request.method )
    
    try:
        
        with opener( request ) as response:
            
            body = response.read()
            content_type = response.headers.get( 'Content-Type', '' )
            
        
    except urllib.error.HTTPError as e:
        
        text = e.read().decode( 'utf-8', errors = 'replace' )
        
        # errors are json with the message in them
        try:
            
            text = json.loads( text )[ 'error' ]
            
        except ( ValueError, TypeError, KeyError ):
            
            pass
            
        
        raise CLIError( f'The client said {e.code}: {text.strip()}' )
        
    except urllib.error.URLError as e:
        
        raise CLIError( f'Could not talk to the client at {url}: {e.reason}. Is it running, with the Client API on?' )
        
    
    if 'json' in content_type:
        
        return json.loads( body.decode( 'utf-8' ) ) if len( body ) > 0 else {}
        
    
    return body
    

#

def BuildRequest( args ) -> APIRequest:
    
    command = args.command
    sub = getattr( args, 'sub', None )
    
    if command == 'call':
        
        params = ParseKeyValueParams( args.param )
        
        if args.json is not None:
            
            body = ParseJSONArgument( args.json )
            
            if not isinstance( body, dict ):
                
                raise CLIError( 'The json for a call has to be an Object!' )
                
            
            params.update( body )
            
        
        path = args.path if args.path.startswith( '/' ) else '/' + args.path
        
        return APIRequest( args.method.upper(), path, params )
        
    
    if command == 'version':
        
        return APIRequest( 'GET', '/api_version', needs_key = False )
        
    
    if command == 'verify':
        
        return APIRequest( 'GET', '/verify_access_key' )
        
    
    if command == 'request-key':
        
        params = { 'name' : args.name, 'permits_everything' : args.everything }
        
        basic_permissions = []
        
        for permission in args.permission:
            
            if permission.isdigit():
                
                basic_permissions.append( int( permission ) )
                
            elif permission in PERMISSION_NAMES_TO_NUMBERS:
                
                basic_permissions.append( PERMISSION_NAMES_TO_NUMBERS[ permission ] )
                
            else:
                
                raise CLIError( f'"{permission}" is not a permission! These are: {", ".join( sorted( PERMISSION_NAMES_TO_NUMBERS.keys() ) )}' )
                
            
        
        if len( basic_permissions ) > 0:
            
            params[ 'basic_permissions' ] = basic_permissions
            
        
        return APIRequest( 'GET', '/request_new_permissions', params, needs_key = False )
        
    
    if command == 'services':
        
        return APIRequest( 'GET', '/get_services' )
        
    
    if command == 'search':
        
        params = { 'tags' : args.tags, 'return_hashes' : True, 'return_file_ids' : True }
        
        if args.file_service_key is not None:
            
            params[ 'file_service_key' ] = args.file_service_key
            
        
        return APIRequest( 'GET', '/get_files/search_files', params )
        
    
    if command == 'metadata':
        
        return APIRequest( 'GET', '/get_files/file_metadata', ParseFiles( args.files ) )
        
    
    if command == 'add-file':
        
        return APIRequest( 'POST', '/add_files/add_file', { 'path' : os.path.abspath( args.path ) } )
        
    
    if command == 'add-url':
        
        params = { 'url' : args.url }
        
        if args.page is not None:
            
            params[ 'destination_page_name' ] = args.page
            
        
        return APIRequest( 'POST', '/add_urls/add_url', params )
        
    
    if command == 'add-tags':
        
        params = ParseFiles( args.files )
        
        params[ 'service_keys_to_tags' ] = { args.service_key : args.tag }
        
        return APIRequest( 'POST', '/add_tags/add_tags', params )
        
    
    if command == 'counters':
        
        if sub == 'list':
            
            return APIRequest( 'GET', '/manage_counters/get_counters' )
            
        elif sub == 'add':
            
            return APIRequest( 'POST', '/manage_counters/add_counter', { 'name' : args.name } )
            
        elif sub == 'rename':
            
            return APIRequest( 'POST', '/manage_counters/rename_counter', { **ParseCounter( args.counter ), 'new_name' : args.new_name } )
            
        elif sub == 'delete':
            
            return APIRequest( 'POST', '/manage_counters/delete_counter', ParseCounter( args.counter ) )
            
        elif sub == 'get':
            
            return APIRequest( 'GET', '/manage_counters/get_counts', ParseFiles( args.files ) )
            
        elif sub == 'set':
            
            return APIRequest( 'POST', '/manage_counters/set_count', { **ParseCounter( args.counter ), 'count' : args.count, **ParseFiles( args.files ) } )
            
        elif sub == 'inc':
            
            return APIRequest( 'POST', '/manage_counters/increment_count', { **ParseCounter( args.counter ), 'delta' : args.by, **ParseFiles( args.files ) } )
            
        elif sub == 'convert':
            
            return APIRequest( 'POST', '/manage_counters/convert_tags_to_counters', { 'tag_service_key' : args.tag_service_key, 'tag_filter' : args.tag_filter, 'preview' : args.preview } )
            
        
    
    if command == 'playlists':
        
        if sub == 'list':
            
            params = {} if args.file is None else ParseFiles( [ args.file ] )
            
            return APIRequest( 'GET', '/manage_playlists/get_playlists', params )
            
        elif sub == 'show':
            
            return APIRequest( 'GET', '/manage_playlists/get_playlist', ParsePlaylist( args.playlist ) )
            
        elif sub == 'new':
            
            return APIRequest( 'POST', '/manage_playlists/new_playlist', { 'name' : args.name } )
            
        elif sub == 'rename':
            
            return APIRequest( 'POST', '/manage_playlists/rename_playlist', { **ParsePlaylist( args.playlist ), 'new_name' : args.new_name } )
            
        elif sub == 'delete':
            
            return APIRequest( 'POST', '/manage_playlists/delete_playlist', ParsePlaylist( args.playlist ) )
            
        elif sub == 'add':
            
            params = { **ParsePlaylist( args.playlist ), **ParseFiles( args.files ) }
            
            if args.start_ms is not None or args.end_ms is not None:
                
                params[ 'start_ms' ] = args.start_ms
                params[ 'end_ms' ] = args.end_ms
                
            
            return APIRequest( 'POST', '/manage_playlists/add_files', params )
            
        elif sub == 'add-blank':
            
            return APIRequest( 'POST', '/manage_playlists/add_blank', { **ParsePlaylist( args.playlist ), 'blank_ms' : args.blank_ms } )
            
        elif sub == 'remove':
            
            return APIRequest( 'POST', '/manage_playlists/remove_files', { **ParsePlaylist( args.playlist ), **ParseFiles( args.files ) } )
            
        elif sub == 'set':
            
            return APIRequest( 'POST', '/manage_playlists/set_items', { **ParsePlaylist( args.playlist ), 'items' : ParseJSONArgument( args.items ) } )
            
        elif sub == 'play':
            
            return APIRequest( 'POST', '/manage_media_viewers/open_playlist', ParsePlaylist( args.playlist ) )
            
        
    
    if command == 'paths':
        
        if sub == 'get':
            
            return APIRequest( 'GET', '/manage_virtual_paths/get_paths', ParseFiles( args.files ) )
            
        elif sub == 'all':
            
            return APIRequest( 'GET', '/manage_virtual_paths/get_all_paths' )
            
        elif sub in ( 'set', 'add', 'remove' ):
            
            return APIRequest( 'POST', f'/manage_virtual_paths/{sub}_paths', { 'paths' : args.path, **ParseFiles( args.files ) } )
            
        
    
    if command == 'snapshots':
        
        if sub == 'get':
            
            return APIRequest( 'GET', '/manage_snapshots/get_snapshots', ParseFiles( args.files ) )
            
        elif sub == 'add':
            
            params = { **ParseFiles( [ args.file ] ), 'path' : os.path.abspath( args.image_path ) }
            
            if args.timestamp_ms is not None:
                
                params[ 'timestamp_ms' ] = args.timestamp_ms
                
            
            return APIRequest( 'POST', '/manage_snapshots/add_snapshot', params )
            
        
    
    if command == 'viewer':
        
        if sub == 'get':
            
            return APIRequest( 'GET', '/manage_file_viewer_data/get_data', ParseFiles( [ args.file ] ) )
            
        elif sub == 'zoom-counts':
            
            return APIRequest( 'GET', '/manage_file_viewer_data/get_saved_zoom_counts' )
            
        elif sub == 'rotate':
            
            return APIRequest( 'POST', '/manage_file_viewer_data/set_rotation', { 'rotation' : args.degrees, **ParseFiles( args.files ) } )
            
        elif sub == 'zoom':
            
            params = { 'zoom' : args.zoom, 'center' : args.center, **ParseFiles( args.files ) }
            
            if args.screen is not None:
                
                params[ 'screen_name' ] = args.screen
                
            
            return APIRequest( 'POST', '/manage_file_viewer_data/set_zoom', params )
            
        elif sub == 'ignore-positions':
            
            if args.state is None:
                
                return APIRequest( 'GET', '/manage_file_viewer_data/get_ignore_saved_positions' )
                
            
            return APIRequest( 'POST', '/manage_file_viewer_data/set_ignore_saved_positions', { 'ignore_saved_positions' : args.state == 'on' } )
            
        elif sub == 'reset-zooms':
            
            return APIRequest( 'POST', '/manage_file_viewer_data/reset_all_zooms', { 'saved_zooms' : args.saved_zooms, 'position_timestamps' : args.position_timestamps } )
            
        elif sub == 'reset-positions':
            
            if ( args.page is None ) == ( len( args.files ) == 0 ):
                
                raise CLIError( 'Give some files, or a page with --page, but not both!' )
                
            
            params = { 'saved_zooms' : not args.keep_saved_zooms, 'rotations' : not args.keep_rotations, 'position_timestamps' : args.position_timestamps }
            
            if args.page is None:
                
                params.update( ParseFiles( args.files ) )
                
            else:
                
                params[ 'page_key' ] = args.page.lower()
                
            
            return APIRequest( 'POST', '/manage_file_viewer_data/reset_positions', params )
            
        elif sub in ( 'position-timestamps', 'skips', 'freezes', 'ab-loops', 'segments', 'scripted-events' ):
            
            ( path, key ) = {
                'position-timestamps' : ( 'set_position_timestamps', 'position_timestamps' ),
                'skips' : ( 'set_playback_skips', 'playback_skips' ),
                'freezes' : ( 'set_playback_freezes', 'playback_freezes' ),
                'ab-loops' : ( 'set_ab_loops', 'ab_loops' ),
                'segments' : ( 'set_segments', 'segments' ),
                'scripted-events' : ( 'set_scripted_events', 'scripted_events' )
            }[ sub ]
            
            return APIRequest( 'POST', f'/manage_file_viewer_data/{path}', { **ParseFiles( [ args.file ] ), key : ParseJSONArgument( args.json ) } )
            
        elif sub == 'overlay':
            
            image_overlay = None if args.json == 'none' else ParseJSONArgument( args.json )
            
            return APIRequest( 'POST', '/manage_file_viewer_data/set_image_overlay', { **ParseFiles( [ args.file ] ), 'image_overlay' : image_overlay } )
            
        
    
    if command == 'presets':
        
        if sub == 'list':
            
            return APIRequest( 'GET', '/manage_tag_presets/get_tag_presets' )
            
        elif sub == 'set':
            
            return APIRequest( 'POST', '/manage_tag_presets/set_tag_presets', { 'tag_presets' : ParseJSONArgument( args.json ) } )
            
        elif sub == 'add':
            
            return APIRequest( 'POST', '/manage_tag_presets/add_to_tag_preset', { 'name' : args.name, 'entries' : args.entries } )
            
        elif sub == 'delete':
            
            return APIRequest( 'POST', '/manage_tag_presets/delete_tag_preset', { 'name' : args.name } )
            
        
    
    if command == 'locations':
        
        if sub == 'list':
            
            return APIRequest( 'GET', '/manage_screen_locations/get_screen_locations' )
            
        elif sub == 'set':
            
            return APIRequest( 'POST', '/manage_screen_locations/set_screen_locations', { 'screen_locations' : ParseJSONArgument( args.json ) } )
            
        
    
    if command == 'export':
        
        path = os.path.abspath( args.path )
        
        if sub == 'playlist':
            
            return APIRequest( 'POST', '/manage_exports/export_playlist', { **ParsePlaylist( args.playlist ), 'path' : path } )
            
        
        params = { **ParseFiles( [ args.file ] ), 'path' : path, 'format' : args.format }
        
        if args.start_ms is not None or args.end_ms is not None:
            
            params[ 'start_ms' ] = args.start_ms
            params[ 'end_ms' ] = args.end_ms
            
        
        if sub == 'video':
            
            if args.resolution is not None:
                
                params[ 'resolution' ] = args.resolution
                
            
            for key in ( 'framerate', 'quality', 'target_size_bytes' ):
                
                if getattr( args, key ) is not None:
                    
                    params[ key ] = getattr( args, key )
                    
                
            
            if args.no_audio:
                
                params[ 'audio_kbps' ] = None
                
            elif args.audio_kbps is not None:
                
                params[ 'audio_kbps' ] = args.audio_kbps
                
            
            return APIRequest( 'POST', '/manage_exports/export_video', params )
            
        elif sub == 'audio':
            
            for key in ( 'mp3_kbps', 'wav_bit_depth', 'sample_rate', 'channels' ):
                
                if getattr( args, key ) is not None:
                    
                    params[ key ] = getattr( args, key )
                    
                
            
            return APIRequest( 'POST', '/manage_exports/export_audio', params )
            
        
    
    if command == 'viewers':
        
        if sub == 'list':
            
            return APIRequest( 'GET', '/manage_pages/get_media_viewers' )
            
        elif sub == 'layout':
            
            return APIRequest( 'GET', '/manage_media_viewers/get_layout' )
            
        elif sub == 'open-layout':
            
            layout = ParseJSONArgument( args.json )
            
            # a saved layout file is the layout itself
            if isinstance( layout, dict ) and 'layout' in layout and 'media_viewers' not in layout:
                
                layout = layout[ 'layout' ]
                
            
            return APIRequest( 'POST', '/manage_media_viewers/open_layout', { 'layout' : layout } )
            
        elif sub == 'ab-repeat':
            
            return APIRequest( 'GET', '/manage_media_viewers/get_ab_repeat' )
            
        elif sub == 'set-ab-repeat':
            
            params = { 'a_ms' : args.a_ms, 'b_ms' : args.b_ms }
            
            if args.viewer is not None:
                
                params[ 'canvas_key' ] = args.viewer.lower()
                
            
            return APIRequest( 'POST', '/manage_media_viewers/set_ab_repeat', params )
            
        elif sub == 'ping-pong':
            
            params = { 'ping_pong' : args.state == 'on' }
            
            if args.viewer is not None:
                
                params[ 'canvas_key' ] = args.viewer.lower()
                
            
            return APIRequest( 'POST', '/manage_media_viewers/set_ab_repeat_ping_pong', params )
            
        elif sub == 'slideshows':
            
            return APIRequest( 'GET', '/manage_media_viewers/get_slideshows' )
            
        elif sub == 'slideshow':
            
            params = {}
            
            if args.viewer is not None:
                
                params[ 'canvas_key' ] = args.viewer.lower()
                
            
            if args.action == 'stop':
                
                return APIRequest( 'POST', '/manage_media_viewers/stop_slideshow', params )
                
            
            if args.period is None:
                
                raise CLIError( 'Please say how many seconds each file stays up for! 0 plays each one once through.' )
                
            
            params[ 'period' ] = args.period
            
            return APIRequest( 'POST', '/manage_media_viewers/start_slideshow', params )
            
        elif sub == 'screens':
            
            return APIRequest( 'GET', '/manage_media_viewers/get_screens' )
            
        elif sub == 'screen-zoom':
            
            params = { 'screen_name' : args.screen }
            
            if args.viewer is not None:
                
                params[ 'canvas_key' ] = args.viewer.lower()
                
            
            return APIRequest( 'POST', '/manage_media_viewers/apply_screen_zoom', params )
            
        
    
    raise CLIError( f'Please say what to do with "{command}"! Try --help.' )
    

def GetArgumentParser() -> argparse.ArgumentParser:
    
    parser = argparse.ArgumentParser( prog = 'hydrus_cli', description = 'Use the hydrus client from the command line, through its Client API. The client has to be running with the Client API on, for instance started with --client_api_port 45869.' )
    
    parser.add_argument( '--url', help = f'the Client API\'s address. default: ${ENV_URL}, then the saved config, then {DEFAULT_URL}' )
    parser.add_argument( '--key', help = f'the access key. default: ${ENV_KEY}, then the saved config' )
    parser.add_argument( '--config', default = GetDefaultConfigPath(), help = 'where the url and key are saved. default: %(default)s' )
    
    files_help = 'files, by sha256 hash in hex or by file_id'
    json_help = 'json, "@path" for json in a file, or "-" for json on stdin'
    
    commands = parser.add_subparsers( dest = 'command', metavar = 'command' )
    
    commands.required = True
    
    p = commands.add_parser( 'config', help = 'save the url and access key to use from now on, and show them' )
    p.add_argument( '--url', dest = 'config_url', help = 'the url to save' )
    p.add_argument( '--key', dest = 'config_key', help = 'the access key to save' )
    
    commands.add_parser( 'version', help = 'the Client API version, hydrus version, and this fork\'s API version' )
    commands.add_parser( 'verify', help = 'check the access key, and show its permissions' )
    
    p = commands.add_parser( 'request-key', help = 'ask the client for a new access key. open services->review services->client api->add->from api request in the client first' )
    p.add_argument( 'name', help = 'what the key is called in the client' )
    p.add_argument( '--everything', action = 'store_true', help = 'ask for every permission. editing scripted events still has to be asked for by name' )
    p.add_argument( '--permission', action = 'append', default = [], help = 'a permission to ask for, by name or number. use it more than once for more. names: ' + ', '.join( sorted( PERMISSION_NAMES_TO_NUMBERS.keys() ) ) )
    p.add_argument( '--save', action = 'store_true', help = 'save the new key to the config' )
    
    p = commands.add_parser( 'call', help = 'call any Client API endpoint' )
    p.add_argument( 'method', choices = [ 'GET', 'POST', 'get', 'post' ] )
    p.add_argument( 'path', help = 'like /get_files/search_files' )
    p.add_argument( '-p', '--param', action = 'append', default = [], help = 'name=value. a value that is json goes in as json. use it more than once for more' )
    p.add_argument( '--json', help = 'the parameters as a json Object, which is ' + json_help )
    
    commands.add_parser( 'services', help = 'list the client\'s services, with their keys' )
    
    p = commands.add_parser( 'search', help = 'search for files, and get their hashes and file_ids' )
    p.add_argument( 'tags', nargs = '+', help = 'tags and system predicates, like "blue eyes" "system:inbox"' )
    p.add_argument( '--file-service-key', help = 'search this file domain' )
    
    p = commands.add_parser( 'metadata', help = 'files\' metadata' )
    p.add_argument( 'files', nargs = '+', help = files_help )
    
    p = commands.add_parser( 'add-file', help = 'import a file from a path on the client\'s computer' )
    p.add_argument( 'path' )
    
    p = commands.add_parser( 'add-url', help = 'send a url to the client to download' )
    p.add_argument( 'url' )
    p.add_argument( '--page', help = 'the name of the page to put it in' )
    
    p = commands.add_parser( 'add-tags', help = 'add tags to files' )
    p.add_argument( 'files', nargs = '+', help = files_help )
    p.add_argument( '--service-key', required = True, help = 'the tag service, from "services"' )
    p.add_argument( '--tag', action = 'append', required = True, help = 'a tag to add. use it more than once for more' )
    
    # this fork's own features
    
    counters = commands.add_parser( 'counters', help = 'counters, the tallies kept for each file' ).add_subparsers( dest = 'sub', metavar = 'action' )
    counters.required = True
    
    counters.add_parser( 'list', help = 'every counter' )
    p = counters.add_parser( 'add', help = 'make a counter' )
    p.add_argument( 'name' )
    p = counters.add_parser( 'rename', help = 'rename a counter. its counts stay' )
    p.add_argument( 'counter', help = 'its name, or its id' )
    p.add_argument( 'new_name' )
    p = counters.add_parser( 'delete', help = 'delete a counter, and all its counts' )
    p.add_argument( 'counter', help = 'its name, or its id' )
    p = counters.add_parser( 'get', help = 'files\' counts' )
    p.add_argument( 'files', nargs = '+', help = files_help )
    p = counters.add_parser( 'set', help = 'set files\' count for a counter' )
    p.add_argument( 'counter', help = 'its name, or its id' )
    p.add_argument( 'count', type = int )
    p.add_argument( 'files', nargs = '+', help = files_help )
    p = counters.add_parser( 'inc', help = 'add to files\' count for a counter' )
    p.add_argument( 'counter', help = 'its name, or its id' )
    p.add_argument( 'files', nargs = '+', help = files_help )
    p.add_argument( '--by', type = int, default = 1, help = 'how much. it can be less than 0. default: %(default)s' )
    p = counters.add_parser( 'convert', help = 'turn "namespace:number" tags into counters, deleting the tags' )
    p.add_argument( 'tag_service_key', help = 'a local tag service, from "services"' )
    p.add_argument( 'tag_filter', help = 'like "items:*"' )
    p.add_argument( '--preview', action = 'store_true', help = 'just say what would happen' )
    
    playlists = commands.add_parser( 'playlists', help = 'playlists' ).add_subparsers( dest = 'sub', metavar = 'action' )
    playlists.required = True
    
    p = playlists.add_parser( 'list', help = 'every playlist, or the ones a file is in' )
    p.add_argument( '--file', help = 'just the playlists this file is in' )
    p = playlists.add_parser( 'show', help = 'a playlist\'s items' )
    p.add_argument( 'playlist', help = 'its name, or its id' )
    p = playlists.add_parser( 'new', help = 'make an empty playlist' )
    p.add_argument( 'name' )
    p = playlists.add_parser( 'rename', help = 'rename a playlist' )
    p.add_argument( 'playlist', help = 'its name, or its id' )
    p.add_argument( 'new_name' )
    p = playlists.add_parser( 'delete', help = 'delete a playlist' )
    p.add_argument( 'playlist', help = 'its name, or its id' )
    p = playlists.add_parser( 'add', help = 'put files on the end of a playlist' )
    p.add_argument( 'playlist', help = 'its name, or its id' )
    p.add_argument( 'files', nargs = '+', help = files_help )
    p.add_argument( '--start-ms', type = int, help = 'just part of each file, from here' )
    p.add_argument( '--end-ms', type = int, help = 'just part of each file, to here' )
    p = playlists.add_parser( 'add-blank', help = 'put a stretch of nothing on the end of a playlist' )
    p.add_argument( 'playlist', help = 'its name, or its id' )
    p.add_argument( 'blank_ms', type = int )
    p = playlists.add_parser( 'remove', help = 'take files out of a playlist' )
    p.add_argument( 'playlist', help = 'its name, or its id' )
    p.add_argument( 'files', nargs = '+', help = files_help )
    p = playlists.add_parser( 'set', help = 'replace all of a playlist\'s items' )
    p.add_argument( 'playlist', help = 'its name, or its id' )
    p.add_argument( 'items', help = 'a list of items, which is ' + json_help )
    p = playlists.add_parser( 'play', help = 'play a playlist in a new media viewer' )
    p.add_argument( 'playlist', help = 'its name, or its id' )
    
    paths = commands.add_parser( 'paths', help = 'virtual paths, the folder-like paths files can have' ).add_subparsers( dest = 'sub', metavar = 'action' )
    paths.required = True
    
    p = paths.add_parser( 'get', help = 'files\' paths' )
    p.add_argument( 'files', nargs = '+', help = files_help )
    paths.add_parser( 'all', help = 'every path any file has' )
    
    for ( sub, sub_help ) in ( ( 'set', 'give files exactly these paths' ), ( 'add', 'add paths to files' ), ( 'remove', 'take paths off files' ) ):
        
        p = paths.add_parser( sub, help = sub_help )
        p.add_argument( 'files', nargs = '+', help = files_help )
        p.add_argument( '--path', action = 'append', default = [], help = 'a path, like "tv shows/action". use it more than once for more' )
        
    
    snapshots = commands.add_parser( 'snapshots', help = 'snapshots, frames taken from files' ).add_subparsers( dest = 'sub', metavar = 'action' )
    snapshots.required = True
    
    p = snapshots.add_parser( 'get', help = 'the snapshots taken from files' )
    p.add_argument( 'files', nargs = '+', help = files_help )
    p = snapshots.add_parser( 'add', help = 'import an image as a snapshot of a file' )
    p.add_argument( 'file', help = 'the file it was taken from' )
    p.add_argument( 'image_path', help = 'the image, on the client\'s computer' )
    p.add_argument( '--timestamp-ms', type = int, help = 'where in the file it was taken from' )
    
    viewer = commands.add_parser( 'viewer', help = 'what the media viewer remembers for files' ).add_subparsers( dest = 'sub', metavar = 'action' )
    viewer.required = True
    
    p = viewer.add_parser( 'get', help = 'everything it remembers for a file' )
    p.add_argument( 'file' )
    viewer.add_parser( 'zoom-counts', help = 'how many files have a saved zoom, and position timestamps' )
    p = viewer.add_parser( 'rotate', help = 'turn files' )
    p.add_argument( 'degrees', type = float, help = 'clockwise, like 90' )
    p.add_argument( 'files', nargs = '+', help = files_help )
    p = viewer.add_parser( 'zoom', help = 'set files\' saved zoom and pan. with neither, they go back to normal' )
    p.add_argument( 'files', nargs = '+', help = files_help )
    p.add_argument( '--zoom', type = float, help = 'like 2.0 for twice the size' )
    p.add_argument( '--center', type = float, nargs = 2, metavar = ( 'X', 'Y' ), help = 'the point in the middle of the window, as fractions of the file\'s width and height' )
    p.add_argument( '--screen', metavar = 'SCREEN_NAME', help = 'just on this screen, by its name from "viewers screens". default is for every screen without one of its own' )
    p = viewer.add_parser( 'ignore-positions', help = 'have the media viewer open every file at the default zoom, whatever zoom, pan, and position timestamps it has saved. with no state, says whether it is on' )
    p.add_argument( 'state', nargs = '?', choices = [ 'on', 'off' ] )
    p = viewer.add_parser( 'reset-zooms', help = 'clear saved zooms and/or position timestamps for every file' )
    p.add_argument( '--saved-zooms', action = 'store_true' )
    p.add_argument( '--position-timestamps', action = 'store_true' )
    p = viewer.add_parser( 'reset-positions', help = 'reset the saved zoom, pan, and turn of some files, or every file in a page' )
    p.add_argument( 'files', nargs = '*', help = files_help )
    p.add_argument( '--page', help = 'a page_key, from "call get manage_pages/get_pages", to reset every file in that page. needs the "manage_pages" permission' )
    p.add_argument( '--keep-saved-zooms', action = 'store_true', help = 'leave the zoom and pan as they are' )
    p.add_argument( '--keep-rotations', action = 'store_true', help = 'leave how they are turned as it is' )
    p.add_argument( '--position-timestamps', action = 'store_true', help = 'reset their position timestamps too' )
    
    for ( sub, sub_help ) in ( ( 'position-timestamps', 'set a file\'s position timestamps' ), ( 'skips', 'set a file\'s playback skips' ), ( 'freezes', 'set a file\'s freezes, the points where playback holds a frame for a while' ), ( 'ab-loops', 'set a file\'s saved A-B loops, which the media viewer\'s A-B menu puts back on' ), ( 'segments', 'set a file\'s segments' ), ( 'scripted-events', 'set a file\'s scripted events. needs the "edit_scripted_events" permission' ) ):
        
        p = viewer.add_parser( sub, help = sub_help )
        p.add_argument( 'file' )
        p.add_argument( 'json', help = 'a list, which is ' + json_help )
        
    
    p = viewer.add_parser( 'overlay', help = 'set the image drawn over a file' )
    p.add_argument( 'file' )
    p.add_argument( 'json', help = 'an Object, which is ' + json_help + ', or "none" to take it away' )
    
    presets = commands.add_parser( 'presets', help = 'tag presets' ).add_subparsers( dest = 'sub', metavar = 'action' )
    presets.required = True
    
    presets.add_parser( 'list', help = 'every tag preset' )
    p = presets.add_parser( 'set', help = 'replace every tag preset' )
    p.add_argument( 'json', help = 'a list, which is ' + json_help )
    p = presets.add_parser( 'add', help = 'add entries to a tag preset, making it if it is new' )
    p.add_argument( 'name' )
    p.add_argument( 'entries', nargs = '+', help = 'like "blue eyes" "-red hair" "system:inbox"' )
    p = presets.add_parser( 'delete', help = 'delete a tag preset' )
    p.add_argument( 'name' )
    
    locations = commands.add_parser( 'locations', help = 'screen locations' ).add_subparsers( dest = 'sub', metavar = 'action' )
    locations.required = True
    
    locations.add_parser( 'list', help = 'every screen location' )
    p = locations.add_parser( 'set', help = 'replace every screen location' )
    p.add_argument( 'json', help = 'a list, which is ' + json_help )
    
    export = commands.add_parser( 'export', help = "export videos, sound, and playlists, as new files on the client's computer" ).add_subparsers( dest = 'sub', metavar = 'action' )
    export.required = True
    
    p = export.add_parser( 'video', help = 'export a video as it is, or as an mp4 or webm' )
    p.add_argument( 'file' )
    p.add_argument( 'path', help = 'where to save it. the extension is added if it is missing' )
    p.add_argument( '--format', choices = [ 'mp4', 'webm', 'original' ], default = 'mp4' )
    p.add_argument( '--start-ms', type = int, help = 'just part of it, from here' )
    p.add_argument( '--end-ms', type = int, help = 'just part of it, to here' )
    p.add_argument( '--resolution', type = int, nargs = 2, metavar = ( 'WIDTH', 'HEIGHT' ) )
    p.add_argument( '--framerate', type = int )
    p.add_argument( '--quality', choices = [ 'best', 'high', 'medium', 'low', 'lowest' ] )
    p.add_argument( '--target-size-bytes', type = int, help = 'fit it in this size, rather than going by quality' )
    p.add_argument( '--audio-kbps', type = int )
    p.add_argument( '--no-audio', action = 'store_true' )
    
    p = export.add_parser( 'audio', help = 'export the sound of a file as an mp3 or wav' )
    p.add_argument( 'file' )
    p.add_argument( 'path', help = 'where to save it. the extension is added if it is missing' )
    p.add_argument( '--format', choices = [ 'mp3', 'wav' ], default = 'mp3' )
    p.add_argument( '--start-ms', type = int, help = 'just part of it, from here' )
    p.add_argument( '--end-ms', type = int, help = 'just part of it, to here' )
    p.add_argument( '--mp3-kbps', type = int )
    p.add_argument( '--wav-bit-depth', type = int, choices = [ 16, 24 ] )
    p.add_argument( '--sample-rate', type = int )
    p.add_argument( '--channels', type = int, choices = [ 1, 2 ] )
    
    p = export.add_parser( 'playlist', help = 'export a playlist as one mp4' )
    p.add_argument( 'playlist', help = 'its name, or its id' )
    p.add_argument( 'path', help = 'where to save it. .mp4 is added if it is missing' )
    
    viewers = commands.add_parser( 'viewers', help = 'media viewer windows' ).add_subparsers( dest = 'sub', metavar = 'action' )
    viewers.required = True
    
    viewers.add_parser( 'list', help = 'the open media viewers' )
    viewers.add_parser( 'layout', help = 'the open media viewers as a layout, the same json as a saved layout file' )
    p = viewers.add_parser( 'open-layout', help = 'open a layout\'s media viewers' )
    p.add_argument( 'json', help = 'a layout, which is ' + json_help )
    viewers.add_parser( 'ab-repeat', help = 'the A-B repeat points of the open media viewers, and whether ping-pong is on' )
    p = viewers.add_parser( 'set-ab-repeat', help = 'put the A-B repeat points on, like a saved A-B loop. with neither, they are cleared' )
    p.add_argument( '--a-ms', type = int, help = 'where the loop starts. default is the start of the file' )
    p.add_argument( '--b-ms', type = int, help = 'where the loop ends. without it, it is not looping' )
    p.add_argument( '--viewer', metavar = 'CANVAS_KEY', help = 'just this media viewer, by its canvas_key from "viewers list". Default is all that are open' )
    p = viewers.add_parser( 'ping-pong', help = 'make A-B repeat play backwards and forwards, rather than jumping from B back to A' )
    p.add_argument( 'state', choices = [ 'on', 'off' ] )
    p.add_argument( '--viewer', metavar = 'CANVAS_KEY', help = 'just this media viewer, by its canvas_key from "viewers list". Default is all that are open' )
    viewers.add_parser( 'screens', help = 'the screens, and which one each open media viewer is on' )
    p = viewers.add_parser( 'screen-zoom', help = 'zoom and pan the files in media viewers how they are on another screen, and keep them like that on the screen they are on' )
    p.add_argument( 'screen', help = 'the screen\'s name, from "viewers screens"' )
    p.add_argument( '--viewer', metavar = 'CANVAS_KEY', help = 'just this media viewer, by its canvas_key from "viewers list". Default is all that are open' )
    viewers.add_parser( 'slideshows', help = 'whether each open media viewer\'s slideshow is running, and its period' )
    p = viewers.add_parser( 'slideshow', help = 'start or stop media viewers\' slideshows' )
    p.add_argument( 'action', choices = [ 'start', 'stop' ] )
    p.add_argument( 'period', nargs = '?', type = float, help = 'for start, seconds each file stays up. 0 plays each file once through, without looping, and moves on when it is done' )
    p.add_argument( '--viewer', metavar = 'CANVAS_KEY', help = 'just this media viewer, by its canvas_key from "viewers list". Default is all that are open' )
    
    return parser
    

def Run( argv: list[ str ], opener = urllib.request.urlopen, stdout = None, environ = None ) -> int:
    
    stdout = sys.stdout if stdout is None else stdout
    environ = os.environ if environ is None else environ
    
    parser = GetArgumentParser()
    
    args = parser.parse_args( argv )
    
    try:
        
        config = LoadConfig( args.config )
        
        url = args.url or environ.get( ENV_URL ) or config.get( 'url' ) or DEFAULT_URL
        access_key = args.key or environ.get( ENV_KEY ) or config.get( 'access_key' )
        
        if args.command == 'config':
            
            if args.config_url is not None:
                
                config[ 'url' ] = args.config_url
                
            
            if args.config_key is not None:
                
                config[ 'access_key' ] = args.config_key
                
            
            if args.config_url is not None or args.config_key is not None:
                
                SaveConfig( args.config, config )
                
            
            saved_key = config.get( 'access_key' )
            
            # just enough of the key to tell which it is
            shown = { 'config' : args.config, 'url' : config.get( 'url', DEFAULT_URL ), 'access_key' : None if saved_key is None else saved_key[ : 8 ] + '...' }
            
            stdout.write( json.dumps( shown, indent = 2 ) + '\n' )
            
            return 0
            
        
        api_request = BuildRequest( args )
        
        result = DoRequest( url, access_key, api_request, opener = opener )
        
        # every json response says these, which is just noise unless you asked for them
        if isinstance( result, dict ) and args.command != 'version':
            
            result.pop( 'version', None )
            result.pop( 'hydrus_version', None )
            
        
        if args.command == 'request-key' and args.save:
            
            config[ 'access_key' ] = result[ 'access_key' ]
            
            SaveConfig( args.config, config )
            
        
    except CLIError as e:
        
        sys.stderr.write( f'{e}\n' )
        
        return 1
        
    
    if isinstance( result, bytes ):
        
        # not json, like a file. it goes out as it is
        if hasattr( stdout, 'buffer' ):
            
            stdout.buffer.write( result )
            
        else:
            
            stdout.write( result.decode( 'utf-8', errors = 'replace' ) )
            
        
    
    else:
        
        stdout.write( json.dumps( result, indent = 2 ) + '\n' )
        
    
    return 0
    

def main():
    
    sys.exit( Run( sys.argv[ 1 : ] ) )
    

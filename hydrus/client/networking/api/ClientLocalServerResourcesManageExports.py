import os
import typing

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusExceptions
from hydrus.core.networking import HydrusServerRequest

from hydrus.client import ClientAPI
from hydrus.client import ClientGlobals as CG
from hydrus.client.exporting import ClientExportingAudio
from hydrus.client.exporting import ClientExportingPlaylists
from hydrus.client.exporting import ClientExportingVideo
from hydrus.client.media import ClientMedia
from hydrus.client.media import ClientMediaResult
from hydrus.client.networking.api import ClientLocalServerCore
from hydrus.client.networking.api import ClientLocalServerResources
from hydrus.client.networking.api import ClientLocalServerResourcesManagePlaylists

# exports make a new file on this computer, in the background, with a popup in the client to follow along
# the job_status_key we give back is that popup, for /manage_popups/get_popups

VIDEO_FORMAT_NAMES = {
    'mp4' : ClientExportingVideo.VIDEO_EXPORT_FORMAT_MP4,
    'webm' : ClientExportingVideo.VIDEO_EXPORT_FORMAT_WEBM,
    'original' : ClientExportingVideo.VIDEO_EXPORT_FORMAT_RAW
}

AUDIO_FORMAT_NAMES = {
    'mp3' : ClientExportingAudio.AUDIO_EXPORT_FORMAT_MP3,
    'wav' : ClientExportingAudio.AUDIO_EXPORT_FORMAT_WAV
}

def CheckChoice( name: str, value: typing.Any, choices: typing.Collection ):
    
    if value not in choices:
        
        raise HydrusExceptions.BadRequestException( f'"{name}" has to be one of {", ".join( str( choice ) for choice in choices )}! "{value}" is not.' )
        
    
    return value
    

def GetExportMediaResult( request: HydrusServerRequest.HydrusRequest ) -> ClientMediaResult.MediaResult:
    
    hash = ClientLocalServerCore.ParseSingleHash( request )
    
    media_result = CG.client_controller.Read( 'media_result', hash )
    
    if not media_result.GetLocationsManager().IsLocal():
        
        raise HydrusExceptions.BadRequestException( 'That file is not on this computer, so it cannot be exported!' )
        
    
    return media_result
    

def GetExportPath( request: HydrusServerRequest.HydrusRequest, ext: str ) -> str:
    
    path = request.parsed_request_args.GetValue( 'path', str )
    
    if not os.path.isabs( path ):
        
        raise HydrusExceptions.BadRequestException( f'"{path}" is not a full path! Please give the whole path, from the drive or root.' )
        
    
    if not path.lower().endswith( ext ):
        
        path += ext
        
    
    if not os.path.isdir( os.path.dirname( path ) ):
        
        raise HydrusExceptions.BadRequestException( f'The folder "{os.path.dirname( path )}" does not exist!' )
        
    
    # we never write over anything
    if os.path.exists( path ):
        
        raise HydrusExceptions.ConflictException( f'"{path}" already exists!' )
        
    
    return path
    

def GetExportSpan( request: HydrusServerRequest.HydrusRequest ) -> tuple[ int, int ] | None:
    
    # just part of the file, like the media viewer's A-B repeat points
    ( start_ms, end_ms ) = ClientLocalServerResourcesManagePlaylists.CheckSpan( request.parsed_request_args.GetValueOrNone( 'start_ms', int ), request.parsed_request_args.GetValueOrNone( 'end_ms', int ) )
    
    if start_ms is None:
        
        return None
        
    
    return ( start_ms, end_ms )
    

def GetOptionalPositiveInt( request: HydrusServerRequest.HydrusRequest, name: str, max_value: int ) -> int | None:
    
    value = request.parsed_request_args.GetValueOrNone( name, int )
    
    if value is None:
        
        return None
        
    
    value = ClientLocalServerCore.CheckNonNegativeInt( name, value )
    
    if not 1 <= value <= max_value:
        
        raise HydrusExceptions.BadRequestException( f'"{name}" has to be from 1 to {max_value}!' )
        
    
    return value
    

class HydrusResourceClientAPIRestrictedManageExports( ClientLocalServerResources.HydrusResourceClientAPIRestricted ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_EXPORT_MEDIA )
        
    

class HydrusResourceClientAPIRestrictedManageExportsExportAudio( HydrusResourceClientAPIRestrictedManageExports ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        media_result = GetExportMediaResult( request )
        
        mime = media_result.GetMime()
        
        if not ( ( mime in HC.VIDEO or mime in HC.AUDIO ) and media_result.HasAudio() ):
            
            raise HydrusExceptions.BadRequestException( 'That file has no sound to export!' )
            
        
        span_ms = GetExportSpan( request )
        
        export_format = AUDIO_FORMAT_NAMES[ CheckChoice( 'format', request.parsed_request_args.GetValue( 'format', str, default_value = 'mp3' ), AUDIO_FORMAT_NAMES.keys() ) ]
        
        mp3_kbps = CheckChoice( 'mp3_kbps', request.parsed_request_args.GetValue( 'mp3_kbps', int, default_value = ClientExportingAudio.AUDIO_EXPORT_DEFAULT_MP3_KBPS ), ClientExportingAudio.AUDIO_EXPORT_MP3_BITRATES_KBPS )
        wav_bit_depth = CheckChoice( 'wav_bit_depth', request.parsed_request_args.GetValue( 'wav_bit_depth', int, default_value = ClientExportingAudio.AUDIO_EXPORT_DEFAULT_WAV_BIT_DEPTH ), [ bit_depth for ( bit_depth, codec ) in ClientExportingAudio.AUDIO_EXPORT_WAV_BIT_DEPTHS ] )
        
        # null is the file's own
        sample_rate = request.parsed_request_args.GetValueOrNone( 'sample_rate', int )
        
        if sample_rate is not None:
            
            CheckChoice( 'sample_rate', sample_rate, ClientExportingAudio.AUDIO_EXPORT_SAMPLE_RATES )
            
        
        channels = request.parsed_request_args.GetValueOrNone( 'channels', int )
        
        if channels is not None:
            
            CheckChoice( 'channels', channels, [ number for ( name, number ) in ClientExportingAudio.AUDIO_EXPORT_CHANNELS ] )
            
        
        settings = ClientExportingAudio.AudioExportSettings( export_format = export_format, mp3_kbps = mp3_kbps, wav_bit_depth = wav_bit_depth, sample_rate = sample_rate, channels = channels )
        
        path = GetExportPath( request, ClientExportingAudio.GetAudioExportExtension( export_format ) )
        
        job_status = ClientExportingAudio.StartAudioExport( media_result, settings, path, span_ms = span_ms )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'path' : path, 'job_status_key' : job_status.GetKey().hex() } )
        
    

class HydrusResourceClientAPIRestrictedManageExportsExportPlaylist( HydrusResourceClientAPIRestrictedManageExports ):
    
    def _CheckAPIPermissions( self, request: HydrusServerRequest.HydrusRequest ):
        
        super()._CheckAPIPermissions( request )
        
        request.client_api_permissions.CheckPermission( ClientAPI.CLIENT_API_PERMISSION_MANAGE_PLAYLISTS )
        
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        ( playlist_id, playlist_name, num_items ) = ClientLocalServerResourcesManagePlaylists.GetPlaylistFromRequest( request )
        
        items = CG.client_controller.Read( 'playlist_items', playlist_id )
        
        media_results = CG.client_controller.Read( 'media_results', { hash for ( hash, start_ms, end_ms, reverse ) in items if hash is not None } )
        
        # like playing it, a file that was deleted, or that cannot be shown, is skipped. the export always plays forwards, and blanks are black and silence
        hashes_to_media_results = { media_result.GetHash() : media_result for media_result in media_results if media_result.GetLocationsManager().IsLocal() and ClientMedia.CanDisplayMediaResult( media_result ) }
        
        playlist_items = [ ( None if hash is None else hashes_to_media_results[ hash ], start_ms, end_ms ) for ( hash, start_ms, end_ms, reverse ) in items if hash is None or hash in hashes_to_media_results ]
        
        if len( [ playlist_item for playlist_item in playlist_items if playlist_item[0] is not None ] ) == 0:
            
            raise HydrusExceptions.ConflictException( f'None of the files in "{playlist_name}" can be exported--it is empty, or they were deleted.' )
            
        
        path = GetExportPath( request, '.mp4' )
        
        job_status = ClientExportingPlaylists.StartPlaylistExport( playlist_name, playlist_items, path )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'path' : path, 'job_status_key' : job_status.GetKey().hex() } )
        
    

class HydrusResourceClientAPIRestrictedManageExportsExportVideo( HydrusResourceClientAPIRestrictedManageExports ):
    
    def _threadDoPOSTJob( self, request: HydrusServerRequest.HydrusRequest ):
        
        media_result = GetExportMediaResult( request )
        
        if media_result.GetMime() not in HC.VIDEO:
            
            raise HydrusExceptions.BadRequestException( 'That file is not a video!' )
            
        
        span_ms = GetExportSpan( request )
        
        export_format = VIDEO_FORMAT_NAMES[ CheckChoice( 'format', request.parsed_request_args.GetValue( 'format', str, default_value = 'mp4' ), VIDEO_FORMAT_NAMES.keys() ) ]
        
        if span_ms is not None and export_format == ClientExportingVideo.VIDEO_EXPORT_FORMAT_RAW:
            
            raise HydrusExceptions.BadRequestException( 'Part of a video has to be encoded, so it cannot be the original file! Use mp4 or webm.' )
            
        
        # null for these is the file's own
        resolution = request.parsed_request_args.GetValueOrNone( 'resolution', list )
        
        if resolution is not None:
            
            if len( resolution ) != 2 or False in ( isinstance( n, int ) and not isinstance( n, bool ) and 1 <= n <= 16384 for n in resolution ):
                
                raise HydrusExceptions.BadRequestException( '"resolution" has to be [ width, height ]!' )
                
            
            # the encoders want even sizes
            resolution = ClientExportingVideo.GetVideoExportEvenResolution( tuple( resolution ) )
            
        
        framerate = GetOptionalPositiveInt( request, 'framerate', 240 )
        
        # leaving it out is the usual bitrate, and null is no sound at all
        if 'audio_kbps' in request.parsed_request_args and request.parsed_request_args[ 'audio_kbps' ] is None:
            
            audio_kbps = None
            
        else:
            
            audio_kbps = CheckChoice( 'audio_kbps', request.parsed_request_args.GetValue( 'audio_kbps', int, default_value = ClientExportingVideo.VIDEO_EXPORT_DEFAULT_AUDIO_BITRATE_KBPS ), ClientExportingVideo.VIDEO_EXPORT_AUDIO_BITRATES_KBPS )
            
        
        if not media_result.HasAudio():
            
            audio_kbps = None
            
        
        quality_names = [ name for ( name, x264_crf, vp9_crf, bpp ) in ClientExportingVideo.VIDEO_EXPORT_QUALITIES ]
        
        default_quality_name = quality_names[ ClientExportingVideo.VIDEO_EXPORT_DEFAULT_QUALITY_INDEX ]
        
        quality_index = quality_names.index( CheckChoice( 'quality', request.parsed_request_args.GetValue( 'quality', str, default_value = default_quality_name ), quality_names ) )
        
        # a file size to fit in, rather than a quality
        target_size_bytes = request.parsed_request_args.GetValueOrNone( 'target_size_bytes', int )
        
        if target_size_bytes is None:
            
            size_mode = ClientExportingVideo.VIDEO_EXPORT_SIZE_MODE_QUALITY
            
        else:
            
            target_size_bytes = ClientLocalServerCore.CheckNonNegativeInt( 'target_size_bytes', target_size_bytes )
            
            size_mode = ClientExportingVideo.VIDEO_EXPORT_SIZE_MODE_TARGET
            
        
        settings = ClientExportingVideo.VideoExportSettings( export_format = export_format, resolution = resolution, framerate = framerate, audio_kbps = audio_kbps, size_mode = size_mode, quality_index = quality_index, target_size_bytes = target_size_bytes )
        
        duration_ms = media_result.GetDurationMS() if span_ms is None else span_ms[1] - span_ms[0]
        
        problem = ClientExportingVideo.GetVideoExportProblem( settings, duration_ms )
        
        if problem is not None:
            
            raise HydrusExceptions.BadRequestException( problem )
            
        
        path = GetExportPath( request, ClientExportingVideo.GetVideoExportExtension( export_format, media_result.GetMime() ) )
        
        job_status = ClientExportingVideo.StartVideoExport( media_result, settings, path, span_ms = span_ms )
        
        return ClientLocalServerCore.GenerateJSONResponse( request, { 'path' : path, 'job_status_key' : job_status.GetKey().hex() } )
        
    

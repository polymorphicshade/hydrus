import os

from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusPaths
from hydrus.core import HydrusTemp
from hydrus.core.files import HydrusFFMPEG

from hydrus.client import ClientData
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientThreading
from hydrus.client.exporting import ClientExportingPlaylists
from hydrus.client.exporting import ClientExportingSpans
from hydrus.client.media import ClientMediaResult

# an audio export is the sound of a video (or an audio file), on its own, as an mp3 or wav
# it can be just part of the file, between the media viewer's A-B repeat points

AUDIO_EXPORT_FORMAT_MP3 = 0
AUDIO_EXPORT_FORMAT_WAV = 1

audio_export_format_string_lookup = {
    AUDIO_EXPORT_FORMAT_MP3 : 'mp3',
    AUDIO_EXPORT_FORMAT_WAV : 'wav'
}

AUDIO_EXPORT_MP3_BITRATES_KBPS = [ 320, 256, 192, 160, 128, 96, 64 ]

AUDIO_EXPORT_DEFAULT_MP3_KBPS = 192

# ( bit depth, ffmpeg codec )
AUDIO_EXPORT_WAV_BIT_DEPTHS = [
    ( 16, 'pcm_s16le' ),
    ( 24, 'pcm_s24le' )
]

AUDIO_EXPORT_DEFAULT_WAV_BIT_DEPTH = 16

AUDIO_EXPORT_SAMPLE_RATES = [ 48000, 44100, 32000, 22050 ]

AUDIO_EXPORT_CHANNELS = [
    ( 'stereo', 2 ),
    ( 'mono', 1 )
]

class AudioExportSettings( object ):
    
    def __init__(
        self,
        export_format: int = AUDIO_EXPORT_FORMAT_MP3,
        mp3_kbps: int = AUDIO_EXPORT_DEFAULT_MP3_KBPS,
        wav_bit_depth: int = AUDIO_EXPORT_DEFAULT_WAV_BIT_DEPTH,
        sample_rate: int | None = None,
        channels: int | None = None
    ):
        
        self.export_format = export_format
        self.mp3_kbps = mp3_kbps
        self.wav_bit_depth = wav_bit_depth
        self.sample_rate = sample_rate # None means the file's own
        self.channels = channels # None means the file's own
        
    
    def __eq__( self, other ):
        
        if isinstance( other, AudioExportSettings ):
            
            return self.__dict__ == other.__dict__
            
        
        return NotImplemented
        
    
    def __repr__( self ):
        
        return f'AudioExportSettings({self.__dict__})'
        
    

def GetAudioExportExtension( export_format: int ) -> str:
    
    if export_format == AUDIO_EXPORT_FORMAT_WAV:
        
        return '.wav'
        
    
    return '.mp3'
    

def GetAudioExportWAVCodec( wav_bit_depth: int ) -> str:
    
    for ( bit_depth, codec ) in AUDIO_EXPORT_WAV_BIT_DEPTHS:
        
        if bit_depth == wav_bit_depth:
            
            return codec
            
        
    
    raise HydrusExceptions.UnsupportedFileException( f'{wav_bit_depth}-bit wav is not supported!' )
    

def EstimateAudioExportSize( settings: AudioExportSettings, duration_ms: int | None ) -> int | None:
    
    # roughly how big the file will come out. None if we can't say
    if duration_ms is None or duration_ms <= 0:
        
        return None
        
    
    duration_s = duration_ms / 1000
    
    if settings.export_format == AUDIO_EXPORT_FORMAT_MP3:
        
        return int( settings.mp3_kbps * 1000 * duration_s / 8 )
        
    
    # a wav is exactly samples x channels x bytes, but we don't know the file's own sample rate or channels
    if settings.sample_rate is None or settings.channels is None:
        
        return None
        
    
    return int( settings.sample_rate * settings.channels * ( settings.wav_bit_depth // 8 ) * duration_s )
    

def GetAudioExportFFMPEGCommand(
    ffmpeg_path: str,
    input_path: str,
    output_path: str,
    settings: AudioExportSettings,
    span_ms: tuple[ int, int ] | None = None
) -> list[ str ]:
    
    if settings.export_format == AUDIO_EXPORT_FORMAT_MP3:
        
        codec_args = [ '-c:a', 'libmp3lame', '-b:a', f'{settings.mp3_kbps}k' ]
        
    elif settings.export_format == AUDIO_EXPORT_FORMAT_WAV:
        
        codec_args = [ '-c:a', GetAudioExportWAVCodec( settings.wav_bit_depth ) ]
        
    else:
        
        raise HydrusExceptions.UnsupportedFileException( 'That format is not supported!' )
        
    
    if settings.sample_rate is not None:
        
        codec_args += [ '-ar', str( settings.sample_rate ) ]
        
    
    if settings.channels is not None:
        
        codec_args += [ '-ac', str( settings.channels ) ]
        
    
    start = ClientExportingPlaylists.GetPlaylistExportFFMPEGStart( ffmpeg_path ) + ClientExportingSpans.GetExportSpanFFMPEGInputArgs( span_ms ) + [ '-i', input_path ]
    
    # just the first audio stream. no video, cover art, subtitles, or data
    return start + [ '-map', '0:a:0', '-vn', '-sn', '-dn' ] + codec_args + [ output_path ]
    

def ExportAudio( job_status: ClientThreading.JobStatus, media_result: ClientMediaResult.MediaResult, settings: AudioExportSettings, output_path: str, span_ms: tuple[ int, int ] | None = None ):
    
    # this runs in a worker thread
    temp_dir = None
    
    try:
        
        hash = media_result.GetHash()
        mime = media_result.GetMime()
        
        source_path = CG.client_controller.client_files_manager.GetFilePath( hash, mime )
        
        ffmpeg_path = HydrusFFMPEG.GetCurrentFFMPEGPath()
        
        temp_dir = HydrusTemp.GetSubTempDir( 'audio_export' )
        
        stderr_path = os.path.join( temp_dir, 'ffmpeg_errors.txt' )
        
        duration_ms = ClientExportingSpans.GetExportSpanDurationMS( span_ms, media_result.GetDurationMS() )
        
        cmd = GetAudioExportFFMPEGCommand( ffmpeg_path, source_path, output_path, settings, span_ms = span_ms )
        
        total_ms = max( 1, 0 if duration_ms is None else duration_ms )
        
        job_status.SetStatusText( 'encoding' )
        
        def progress_callable( progress_ms ):
            
            job_status.SetGauge( min( progress_ms, total_ms ), total_ms )
            
        
        progress_callable( 0 )
        
        try:
            
            ClientExportingPlaylists.RunPlaylistExportFFMPEG( cmd, job_status, stderr_path, progress_callable )
            
        except Exception:
            
            # don't leave half a file behind
            if os.path.exists( output_path ):
                
                HydrusPaths.DeletePath( output_path )
                
            
            raise
            
        
        job_status.DeleteGauge()
        
        text = f'Exported to {output_path}'
        
        if os.path.exists( output_path ):
            
            text += f' ({ClientData.ToHumanBytes( os.path.getsize( output_path ) )})'
            
        
        text += '.'
        
        job_status.SetStatusText( text )
        
        call = HydrusData.Call( HydrusPaths.OpenFileLocation, output_path )
        
        call.SetLabel( 'show in folder' )
        
        job_status.SetUserCallable( call )
        
    except HydrusExceptions.CancelledException:
        
        job_status.DeleteGauge()
        
        job_status.SetStatusText( 'Cancelled!' )
        
    except Exception as e:
        
        job_status.DeleteGauge()
        
        job_status.SetErrorException( e )
        
        HydrusData.PrintException( e, do_wait = False )
        
    finally:
        
        if temp_dir is not None:
            
            HydrusPaths.DeletePath( temp_dir )
            
        
        job_status.Finish()
        
    

def StartAudioExport( media_result: ClientMediaResult.MediaResult, settings: AudioExportSettings, output_path: str, span_ms: tuple[ int, int ] | None = None ):
    
    job_status = ClientThreading.JobStatus( cancellable = True )
    
    job_status.SetStatusTitle( f'exporting audio {os.path.basename( output_path )}' )
    
    CG.client_controller.pub( 'message', job_status )
    
    CG.client_controller.CallToThread( ExportAudio, job_status, media_result, settings, output_path, span_ms )
    

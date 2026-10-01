import os
import shutil

from hydrus.core import HydrusConstants as HC
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

# a video export is one video file, either copied as it is, or encoded again to a smaller size, resolution, or framerate
# it can be just part of the file, a clip between the media viewer's A-B repeat points. a clip is always encoded

VIDEO_EXPORT_FORMAT_MP4 = 0 # h.264 and aac
VIDEO_EXPORT_FORMAT_WEBM = 1 # vp9 and opus
VIDEO_EXPORT_FORMAT_RAW = 2 # the original file, copied

video_export_format_string_lookup = {
    VIDEO_EXPORT_FORMAT_MP4 : 'mp4',
    VIDEO_EXPORT_FORMAT_WEBM : 'webm',
    VIDEO_EXPORT_FORMAT_RAW : 'original file'
}

VIDEO_EXPORT_SIZE_MODE_QUALITY = 0 # a quality level, and the file is as big as it comes out
VIDEO_EXPORT_SIZE_MODE_TARGET = 1 # a file size to fit in, and the quality is whatever fits

# ( name, x264 crf, vp9 crf, rough bits per pixel per frame it comes out at, for guessing the size )
VIDEO_EXPORT_QUALITIES = [
    ( 'best', 18, 24, 0.14 ),
    ( 'high', 21, 30, 0.09 ),
    ( 'medium', 24, 35, 0.06 ),
    ( 'low', 28, 41, 0.035 ),
    ( 'lowest', 32, 48, 0.02 )
]

VIDEO_EXPORT_DEFAULT_QUALITY_INDEX = 1

# vp9 looks about as good as h.264 at this much of the bitrate
VIDEO_EXPORT_WEBM_SIZE_FACTOR = 0.7

# the short side of the usual resolutions
VIDEO_EXPORT_SHORT_SIDES = [ 2160, 1440, 1080, 720, 480, 360, 240 ]

VIDEO_EXPORT_FRAMERATES = [ 60, 30, 24, 15, 10 ]

VIDEO_EXPORT_AUDIO_BITRATES_KBPS = [ 192, 128, 96, 64 ]

VIDEO_EXPORT_DEFAULT_AUDIO_BITRATE_KBPS = 128

VIDEO_EXPORT_DEFAULT_FRAMERATE = 30

# the container and the encoder not hitting its bitrate exactly take a little, so a target size aims a bit under
VIDEO_EXPORT_TARGET_SIZE_MARGIN = 0.96

# below this, a target size will not work at all
VIDEO_EXPORT_MIN_VIDEO_KBPS = 32

# below this many bits per pixel per frame, the video will be very blocky
VIDEO_EXPORT_LOW_BPP_WARNING = 0.02

# if the file is encoded again at a high quality, it can come out a bit bigger than it was, but not by a lot
VIDEO_EXPORT_SOURCE_SIZE_CAP_FACTOR = 1.25

class VideoExportSettings( object ):
    
    def __init__(
        self,
        export_format: int = VIDEO_EXPORT_FORMAT_MP4,
        resolution: tuple[ int, int ] | None = None,
        framerate: int | None = None,
        audio_kbps: int | None = VIDEO_EXPORT_DEFAULT_AUDIO_BITRATE_KBPS,
        size_mode: int = VIDEO_EXPORT_SIZE_MODE_QUALITY,
        quality_index: int = VIDEO_EXPORT_DEFAULT_QUALITY_INDEX,
        target_size_bytes: int | None = None
    ):
        
        self.export_format = export_format
        self.resolution = resolution # None means the file's own
        self.framerate = framerate # None means the file's own
        self.audio_kbps = audio_kbps # None means no audio
        self.size_mode = size_mode
        self.quality_index = quality_index
        self.target_size_bytes = target_size_bytes
        
    
    def __eq__( self, other ):
        
        if isinstance( other, VideoExportSettings ):
            
            return self.__dict__ == other.__dict__
            
        
        return NotImplemented
        
    
    def __repr__( self ):
        
        return f'VideoExportSettings({self.__dict__})'
        
    

def GetVideoExportExtension( export_format: int, mime: int ) -> str:
    
    if export_format == VIDEO_EXPORT_FORMAT_MP4:
        
        return '.mp4'
        
    elif export_format == VIDEO_EXPORT_FORMAT_WEBM:
        
        return '.webm'
        
    
    return HC.mime_ext_lookup.get( mime, '' )
    

def GetVideoExportEvenResolution( resolution: tuple[ int, int ] ) -> tuple[ int, int ]:
    
    # h.264 and vp9 in yuv420p want even numbers
    ( width, height ) = resolution
    
    return ( max( 2, int( width ) // 2 * 2 ), max( 2, int( height ) // 2 * 2 ) )
    

def GetVideoExportScaledResolution( resolution: tuple[ int, int ], short_side: int ) -> tuple[ int, int ]:
    
    # the same shape, with the short side this long. 720 is 1280x720 for a wide video and 720x1280 for a tall one
    ( width, height ) = resolution
    
    scale = short_side / min( width, height )
    
    # to the nearest even numbers
    return ( max( 2, round( width * scale / 2 ) * 2 ), max( 2, round( height * scale / 2 ) * 2 ) )
    

def GetVideoExportResolutionOptions( resolution: tuple[ int | None, int | None ] ) -> list[ tuple[ str, tuple[ int, int ] | None ] ]:
    
    # ( label, resolution ) choices, the file's own first, then the usual smaller ones. None means the file's own
    ( width, height ) = resolution
    
    if width is None or height is None or width <= 0 or height <= 0:
        
        return [ ( 'original', None ) ]
        
    
    options = [ ( f'original ({width}x{height})', None ) ]
    
    short_side = min( width, height )
    
    for option_short_side in VIDEO_EXPORT_SHORT_SIDES:
        
        if option_short_side < short_side:
            
            ( option_width, option_height ) = GetVideoExportScaledResolution( ( width, height ), option_short_side )
            
            options.append( ( f'{option_short_side}p ({option_width}x{option_height})', ( option_width, option_height ) ) )
            
        
    
    return options
    

def GetVideoExportFramerateOptions( framerate: float | None ) -> list[ tuple[ str, int | None ] ]:
    
    # ( label, framerate ) choices, the file's own first, then the usual slower ones. None means the file's own
    if framerate is None or framerate <= 0:
        
        return [ ( 'original', None ) ]
        
    
    options = [ ( f'original ({framerate:.3g} fps)', None ) ]
    
    for option_framerate in VIDEO_EXPORT_FRAMERATES:
        
        # 29.97 is not worth going down to 30 for
        if option_framerate < framerate - 0.5:
            
            options.append( ( f'{option_framerate} fps', option_framerate ) )
            
        
    
    return options
    

def GetVideoExportOutputResolution( settings: VideoExportSettings, source_resolution: tuple[ int | None, int | None ] ) -> tuple[ int, int ] | None:
    
    if settings.resolution is not None:
        
        return GetVideoExportEvenResolution( settings.resolution )
        
    
    ( width, height ) = source_resolution
    
    if width is None or height is None or width <= 0 or height <= 0:
        
        return None
        
    
    return GetVideoExportEvenResolution( ( width, height ) )
    

def GetVideoExportOutputFramerate( settings: VideoExportSettings, source_framerate: float | None ) -> float:
    
    if settings.framerate is not None:
        
        return settings.framerate
        
    
    if source_framerate is None or source_framerate <= 0:
        
        return VIDEO_EXPORT_DEFAULT_FRAMERATE
        
    
    return source_framerate
    

def GetVideoExportTargetVideoKBPS( target_size_bytes: int, duration_ms: int, audio_kbps: int | None ) -> int:
    
    # the video bitrate that fits the file in the target size, with the audio. zero or less means it cannot fit
    duration_s = duration_ms / 1000
    
    if duration_s <= 0:
        
        return 0
        
    
    total_kbps = ( target_size_bytes * 8 * VIDEO_EXPORT_TARGET_SIZE_MARGIN ) / duration_s / 1000
    
    if audio_kbps is not None:
        
        total_kbps -= audio_kbps
        
    
    return int( total_kbps )
    

def GetVideoExportBitsPerPixel( video_kbps: float, resolution: tuple[ int, int ], framerate: float ) -> float:
    
    ( width, height ) = resolution
    
    pixels_per_second = width * height * framerate
    
    if pixels_per_second <= 0:
        
        return 0.0
        
    
    return video_kbps * 1000 / pixels_per_second
    

def EstimateVideoExportSize(
    settings: VideoExportSettings,
    source_size: int,
    source_resolution: tuple[ int | None, int | None ],
    source_framerate: float | None,
    duration_ms: int | None
) -> int | None:
    
    # roughly how big the file will come out. None if we can't say
    if settings.export_format == VIDEO_EXPORT_FORMAT_RAW:
        
        return source_size
        
    
    if duration_ms is None or duration_ms <= 0:
        
        return None
        
    
    duration_s = duration_ms / 1000
    
    audio_bytes = 0 if settings.audio_kbps is None else settings.audio_kbps * 1000 * duration_s / 8
    
    if settings.size_mode == VIDEO_EXPORT_SIZE_MODE_TARGET:
        
        if settings.target_size_bytes is None:
            
            return None
            
        
        video_kbps = GetVideoExportTargetVideoKBPS( settings.target_size_bytes, duration_ms, settings.audio_kbps )
        
        if video_kbps < VIDEO_EXPORT_MIN_VIDEO_KBPS:
            
            return None
            
        
        return int( video_kbps * 1000 * duration_s / 8 + audio_bytes )
        
    
    resolution = GetVideoExportOutputResolution( settings, source_resolution )
    
    if resolution is None:
        
        return None
        
    
    ( width, height ) = resolution
    
    framerate = GetVideoExportOutputFramerate( settings, source_framerate )
    
    ( name, x264_crf, vp9_crf, bpp ) = VIDEO_EXPORT_QUALITIES[ settings.quality_index ]
    
    if settings.export_format == VIDEO_EXPORT_FORMAT_WEBM:
        
        bpp *= VIDEO_EXPORT_WEBM_SIZE_FACTOR
        
    
    video_bytes = bpp * width * height * framerate * duration_s / 8
    
    # a file that is already small does not get much bigger from being encoded again, so we don't guess much more than it, scaled to the new size and framerate
    ( source_width, source_height ) = source_resolution
    
    if source_size > 0 and source_width is not None and source_height is not None and source_width > 0 and source_height > 0:
        
        source_framerate = GetVideoExportOutputFramerate( VideoExportSettings(), source_framerate )
        
        scale = ( width * height * framerate ) / ( source_width * source_height * source_framerate )
        
        video_bytes = min( video_bytes, source_size * scale * VIDEO_EXPORT_SOURCE_SIZE_CAP_FACTOR )
        
    
    return int( video_bytes + audio_bytes )
    

def GetVideoExportProblem( settings: VideoExportSettings, duration_ms: int | None ) -> str | None:
    
    # a reason these settings cannot work, or None if they are fine
    if settings.export_format == VIDEO_EXPORT_FORMAT_RAW or settings.size_mode == VIDEO_EXPORT_SIZE_MODE_QUALITY:
        
        return None
        
    
    if duration_ms is None or duration_ms <= 0:
        
        return 'This file does not have a duration, so it cannot be fit to a file size.'
        
    
    if settings.target_size_bytes is None or settings.target_size_bytes <= 0:
        
        return 'Please set a file size.'
        
    
    video_kbps = GetVideoExportTargetVideoKBPS( settings.target_size_bytes, duration_ms, settings.audio_kbps )
    
    if video_kbps < VIDEO_EXPORT_MIN_VIDEO_KBPS:
        
        if settings.audio_kbps is not None:
            
            return 'That file size is too small for this video, even at the lowest quality. Try a bigger size, or less audio, or no audio.'
            
        
        return 'That file size is too small for this video, even at the lowest quality. Try a bigger size.'
        
    
    return None
    

def GetVideoExportWarning( settings: VideoExportSettings, source_resolution: tuple[ int | None, int | None ], source_framerate: float | None, duration_ms: int | None ) -> str | None:
    
    # something that will work, but not well
    if settings.export_format == VIDEO_EXPORT_FORMAT_RAW or settings.size_mode == VIDEO_EXPORT_SIZE_MODE_QUALITY:
        
        return None
        
    
    if GetVideoExportProblem( settings, duration_ms ) is not None:
        
        return None
        
    
    resolution = GetVideoExportOutputResolution( settings, source_resolution )
    
    if resolution is None:
        
        return None
        
    
    video_kbps = GetVideoExportTargetVideoKBPS( settings.target_size_bytes, duration_ms, settings.audio_kbps )
    
    framerate = GetVideoExportOutputFramerate( settings, source_framerate )
    
    bpp = GetVideoExportBitsPerPixel( video_kbps, resolution, framerate )
    
    if settings.export_format == VIDEO_EXPORT_FORMAT_WEBM:
        
        bpp /= VIDEO_EXPORT_WEBM_SIZE_FACTOR
        
    
    if bpp < VIDEO_EXPORT_LOW_BPP_WARNING:
        
        return 'At this size, the video will probably look blocky. A smaller resolution or framerate will look better.'
        
    
    return None
    

def GetVideoExportFFMPEGCommands(
    ffmpeg_path: str,
    input_path: str,
    output_path: str,
    settings: VideoExportSettings,
    source_resolution: tuple[ int | None, int | None ],
    has_audio: bool,
    duration_ms: int | None,
    passlog_path: str,
    span_ms: tuple[ int, int ] | None = None
) -> list[ list[ str ] ]:
    
    # one command for a quality level, or two for a target size, since the first pass works out where the bits should go
    # duration_ms is how long the export is, so for a clip it is the clip's length
    if settings.export_format not in ( VIDEO_EXPORT_FORMAT_MP4, VIDEO_EXPORT_FORMAT_WEBM ):
        
        raise HydrusExceptions.UnsupportedFileException( 'That format is not encoded!' )
        
    
    video_filters = []
    
    resolution = GetVideoExportOutputResolution( settings, source_resolution )
    
    if resolution is not None:
        
        ( width, height ) = resolution
        
        video_filters.append( f'scale={width}:{height}:flags=lanczos' )
        video_filters.append( 'setsar=1' )
        
    
    if settings.framerate is not None:
        
        video_filters.append( f'fps={settings.framerate}' )
        
    
    video_filters.append( 'format=yuv420p' )
    
    video_args = [ '-vf', ','.join( video_filters ) ]
    
    if settings.export_format == VIDEO_EXPORT_FORMAT_MP4:
        
        video_args += [ '-c:v', 'libx264', '-preset', 'medium', '-pix_fmt', 'yuv420p' ]
        
    else:
        
        video_args += [ '-c:v', 'libvpx-vp9', '-row-mt', '1', '-deadline', 'good', '-cpu-used', '2', '-pix_fmt', 'yuv420p' ]
        
    
    ( name, x264_crf, vp9_crf, bpp ) = VIDEO_EXPORT_QUALITIES[ settings.quality_index ]
    
    two_pass = settings.size_mode == VIDEO_EXPORT_SIZE_MODE_TARGET
    
    if two_pass:
        
        problem = GetVideoExportProblem( settings, duration_ms )
        
        if problem is not None:
            
            raise HydrusExceptions.VetoException( problem )
            
        
        video_kbps = GetVideoExportTargetVideoKBPS( settings.target_size_bytes, duration_ms, settings.audio_kbps )
        
        video_args += [ '-b:v', f'{video_kbps}k' ]
        
        if settings.export_format == VIDEO_EXPORT_FORMAT_MP4:
            
            # stops the odd busy moment going well over
            video_args += [ '-maxrate', f'{video_kbps * 2}k', '-bufsize', f'{video_kbps * 2}k' ]
            
        
    elif settings.export_format == VIDEO_EXPORT_FORMAT_MP4:
        
        video_args += [ '-crf', str( x264_crf ) ]
        
    else:
        
        # vp9 needs a zero bitrate to go by the crf alone
        video_args += [ '-crf', str( vp9_crf ), '-b:v', '0' ]
        
    
    keep_audio = has_audio and settings.audio_kbps is not None
    
    if keep_audio:
        
        audio_codec = 'aac' if settings.export_format == VIDEO_EXPORT_FORMAT_MP4 else 'libopus'
        
        audio_args = [ '-c:a', audio_codec, '-b:a', f'{settings.audio_kbps}k' ]
        
    else:
        
        audio_args = [ '-an' ]
        
    
    if settings.export_format == VIDEO_EXPORT_FORMAT_MP4:
        
        container_args = [ '-movflags', '+faststart' ]
        
    else:
        
        container_args = []
        
    
    # just the first video and audio, no subtitles or attachments or cover art
    maps = [ '-map', '0:v:0' ]
    
    if keep_audio:
        
        maps += [ '-map', '0:a:0' ]
        
    
    start = ClientExportingPlaylists.GetPlaylistExportFFMPEGStart( ffmpeg_path ) + ClientExportingSpans.GetExportSpanFFMPEGInputArgs( span_ms ) + [ '-i', input_path ]
    
    if two_pass:
        
        first_pass = start + [ '-map', '0:v:0' ] + video_args + [ '-pass', '1', '-passlogfile', passlog_path, '-an', '-f', 'null', os.devnull ]
        
        second_pass = start + maps + video_args + [ '-pass', '2', '-passlogfile', passlog_path ] + audio_args + container_args + [ output_path ]
        
        return [ first_pass, second_pass ]
        
    
    return [ start + maps + video_args + audio_args + container_args + [ output_path ] ]
    

def ExportVideo( job_status: ClientThreading.JobStatus, media_result: ClientMediaResult.MediaResult, settings: VideoExportSettings, output_path: str, span_ms: tuple[ int, int ] | None = None ):
    
    # this runs in a worker thread
    temp_dir = None
    
    try:
        
        hash = media_result.GetHash()
        mime = media_result.GetMime()
        
        source_path = CG.client_controller.client_files_manager.GetFilePath( hash, mime )
        
        if settings.export_format == VIDEO_EXPORT_FORMAT_RAW:
            
            if span_ms is not None:
                
                raise HydrusExceptions.VetoException( 'Part of a file cannot be copied as it is. It has to be encoded.' )
                
            
            job_status.SetStatusText( 'copying' )
            
            shutil.copyfile( source_path, output_path )
            
        else:
            
            ffmpeg_path = HydrusFFMPEG.GetCurrentFFMPEGPath()
            
            temp_dir = HydrusTemp.GetSubTempDir( 'video_export' )
            
            stderr_path = os.path.join( temp_dir, 'ffmpeg_errors.txt' )
            passlog_path = os.path.join( temp_dir, 'passlog' )
            
            duration_ms = ClientExportingSpans.GetExportSpanDurationMS( span_ms, media_result.GetDurationMS() )
            
            cmds = GetVideoExportFFMPEGCommands( ffmpeg_path, source_path, output_path, settings, media_result.GetResolution(), media_result.HasAudio(), duration_ms, passlog_path, span_ms = span_ms )
            
            total_ms = max( 1, 0 if duration_ms is None else duration_ms )
            
            try:
                
                for ( i, cmd ) in enumerate( cmds ):
                    
                    if len( cmds ) > 1:
                        
                        job_status.SetStatusText( f'encoding, pass {i + 1} of {len( cmds )}' )
                        
                    else:
                        
                        job_status.SetStatusText( 'encoding' )
                        
                    
                    done_ms = i * total_ms
                    
                    def progress_callable( progress_ms ):
                        
                        job_status.SetGauge( done_ms + min( progress_ms, total_ms ), total_ms * len( cmds ) )
                        
                    
                    progress_callable( 0 )
                    
                    ClientExportingPlaylists.RunPlaylistExportFFMPEG( cmd, job_status, stderr_path, progress_callable )
                    
                
            except Exception:
                
                # don't leave half a video behind
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
        
    

def StartVideoExport( media_result: ClientMediaResult.MediaResult, settings: VideoExportSettings, output_path: str, span_ms: tuple[ int, int ] | None = None ):
    
    job_status = ClientThreading.JobStatus( cancellable = True )
    
    job_status.SetStatusTitle( f'exporting video {os.path.basename( output_path )}' )
    
    CG.client_controller.pub( 'message', job_status )
    
    CG.client_controller.CallToThread( ExportVideo, job_status, media_result, settings, output_path, span_ms )
    

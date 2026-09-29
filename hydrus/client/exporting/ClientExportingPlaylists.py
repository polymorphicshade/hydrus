import os
import subprocess

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusGlobals as HG
from hydrus.core import HydrusNumbers
from hydrus.core import HydrusPaths
from hydrus.core import HydrusTemp
from hydrus.core.files import HydrusFFMPEG
from hydrus.core.files.images import HydrusImageHandling
from hydrus.core.processes import HydrusSubprocess

from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientThreading
from hydrus.client.media import ClientMediaResult

# a playlist export is one mp4 of everything in the playlist, one after another
# each item is encoded on its own to the same size, framerate, and codecs, and then those are joined together without encoding them again

# how each item goes into the video
PLAYLIST_EXPORT_KIND_MOTION = 0 # ffmpeg plays it, with its audio if it has some
PLAYLIST_EXPORT_KIND_AUDIO = 1 # the audio, over black
PLAYLIST_EXPORT_KIND_STILL = 2 # an image, held for a while, like the playlist player does
PLAYLIST_EXPORT_KIND_UNSUPPORTED = 3

# the animations ffmpeg can play. hydrus draws the others itself, so they go in as a still of their first frame
PLAYLIST_EXPORT_MOTION_MIMES = set( HC.VIDEO ) | { HC.ANIMATION_GIF, HC.ANIMATION_APNG }

PLAYLIST_EXPORT_DEFAULT_RESOLUTION = ( 1280, 720 )
PLAYLIST_EXPORT_MAX_RESOLUTION = ( 3840, 2160 )

PLAYLIST_EXPORT_DEFAULT_FRAMERATE = 30
PLAYLIST_EXPORT_MAX_FRAMERATE = 60

PLAYLIST_EXPORT_AUDIO_SAMPLE_RATE = 48000

# how long a file with no duration, like an image, stays up if there is no slideshow duration in the options to use. the same as the playlist player
PLAYLIST_EXPORT_DEFAULT_STILL_PERIOD_S = 5.0

def ConvertMSToFFMPEGSeconds( ms: int | float ) -> str:
    
    return f'{ms / 1000:.3f}'
    

def GetPlaylistExportConcatCommand( ffmpeg_path: str, concat_list_path: str, output_path: str ) -> list[ str ]:
    
    cmd = GetPlaylistExportFFMPEGStart( ffmpeg_path )
    
    cmd += [ '-f', 'concat', '-safe', '0', '-i', concat_list_path ]
    
    # every piece is already the same size, framerate, and codecs, so they just go one after another
    cmd += [ '-map', '0', '-c', 'copy', '-movflags', '+faststart' ]
    
    cmd.append( output_path )
    
    return cmd
    

def GetPlaylistExportConcatListText( segment_paths: list[ str ] ) -> str:
    
    lines = []
    
    for segment_path in segment_paths:
        
        # the concat list quotes paths with ', and a ' in a path is closed, escaped, and opened again
        escaped_path = segment_path.replace( '\\', '/' ).replace( "'", "'\\''" )
        
        lines.append( f"file '{escaped_path}'" )
        
    
    return '\n'.join( lines ) + '\n'
    

def GetPlaylistExportFFMPEGStart( ffmpeg_path: str ) -> list[ str ]:
    
    # progress comes out on stdout as key=value lines. errors come out on stderr
    return [ ffmpeg_path, '-hide_banner', '-nostdin', '-y', '-loglevel', 'error', '-progress', 'pipe:1', '-nostats' ]
    

def GetPlaylistExportFramerate( framerates: list[ float | None ] ) -> int:
    
    # the fastest thing in the playlist, so nothing drops frames, within reason
    framerates = [ framerate for framerate in framerates if framerate is not None and framerate > 0 ]
    
    if len( framerates ) == 0:
        
        return PLAYLIST_EXPORT_DEFAULT_FRAMERATE
        
    
    return max( 1, min( round( max( framerates ) ), PLAYLIST_EXPORT_MAX_FRAMERATE ) )
    

def GetPlaylistExportKind( mime: int ) -> int:
    
    if mime in PLAYLIST_EXPORT_MOTION_MIMES:
        
        return PLAYLIST_EXPORT_KIND_MOTION
        
    elif mime in HC.AUDIO:
        
        return PLAYLIST_EXPORT_KIND_AUDIO
        
    elif mime in HC.IMAGES or mime in HC.ANIMATIONS:
        
        return PLAYLIST_EXPORT_KIND_STILL
        
    
    return PLAYLIST_EXPORT_KIND_UNSUPPORTED
    

def GetPlaylistExportResolution( kinds_and_resolutions: list[ tuple[ int, tuple[ int | None, int | None ] ] ] ) -> tuple[ int, int ]:
    
    # the video is the size of the biggest video in it, or the biggest image if there are no videos. everything else fits inside, with black bars
    def is_good( resolution ):
        
        ( width, height ) = resolution
        
        return width is not None and height is not None and width > 0 and height > 0
        
    
    resolutions = [ resolution for ( kind, resolution ) in kinds_and_resolutions if kind == PLAYLIST_EXPORT_KIND_MOTION and is_good( resolution ) ]
    
    if len( resolutions ) == 0:
        
        resolutions = [ resolution for ( kind, resolution ) in kinds_and_resolutions if kind == PLAYLIST_EXPORT_KIND_STILL and is_good( resolution ) ]
        
    
    if len( resolutions ) == 0:
        
        return PLAYLIST_EXPORT_DEFAULT_RESOLUTION
        
    
    ( width, height ) = max( resolutions, key = lambda resolution: resolution[0] * resolution[1] )
    
    # a huge photo should not make a huge video
    ( max_width, max_height ) = PLAYLIST_EXPORT_MAX_RESOLUTION
    
    if width < height:
        
        ( max_width, max_height ) = ( max_height, max_width )
        
    
    scale = min( 1.0, max_width / width, max_height / height )
    
    # h.264 wants even numbers
    width = max( 2, int( width * scale ) // 2 * 2 )
    height = max( 2, int( height * scale ) // 2 * 2 )
    
    return ( width, height )
    

def GetPlaylistExportSegmentCommand(
    ffmpeg_path: str,
    kind: int,
    input_path: str,
    has_audio: bool,
    start_ms: int | None,
    length_ms: int | None,
    duration_ms: int | None,
    resolution: tuple[ int, int ],
    framerate: int,
    output_path: str
) -> list[ str ]:
    
    ( width, height ) = resolution
    
    cmd = GetPlaylistExportFFMPEGStart( ffmpeg_path )
    
    # fit it in, centered, with black bars, at the video's framerate
    video_filter = f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={framerate},format=yuv420p'
    
    silence = f'anullsrc=channel_layout=stereo:sample_rate={PLAYLIST_EXPORT_AUDIO_SAMPLE_RATE}'
    
    input_span = []
    
    if start_ms is not None and start_ms > 0:
        
        input_span += [ '-ss', ConvertMSToFFMPEGSeconds( start_ms ) ]
        
    
    if length_ms is not None:
        
        input_span += [ '-t', ConvertMSToFFMPEGSeconds( length_ms ) ]
        
    
    if kind == PLAYLIST_EXPORT_KIND_MOTION:
        
        cmd += input_span + [ '-i', input_path ]
        
        if has_audio:
            
            # the audio is padded with silence, in case it stops before the video does
            filter_complex = f'[0:v:0]{video_filter}[v];[0:a:0]apad[a]'
            
        else:
            
            cmd += [ '-f', 'lavfi', '-i', silence ]
            
            filter_complex = f'[0:v:0]{video_filter}[v];[1:a:0]anull[a]'
            
        
    elif kind == PLAYLIST_EXPORT_KIND_AUDIO:
        
        cmd += input_span + [ '-i', input_path ]
        cmd += [ '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:r={framerate}' ]
        
        # any cover art in the file is left out
        filter_complex = f'[1:v:0]{video_filter}[v];[0:a:0]anull[a]'
        
    elif kind == PLAYLIST_EXPORT_KIND_STILL:
        
        cmd += [ '-loop', '1', '-framerate', str( framerate ), '-i', input_path ]
        cmd += [ '-f', 'lavfi', '-i', silence ]
        
        filter_complex = f'[0:v:0]{video_filter}[v];[1:a:0]anull[a]'
        
    else:
        
        raise HydrusExceptions.UnsupportedFileException( 'That kind of file cannot go in a video!' )
        
    
    cmd += [ '-filter_complex', filter_complex, '-map', '[v]', '-map', '[a]' ]
    
    # the padding, silence, black, and looped image all go on forever, so the output stops with the real thing
    cmd += [ '-shortest' ]
    
    if length_ms is not None:
        
        cmd += [ '-t', ConvertMSToFFMPEGSeconds( length_ms ) ]
        
    elif duration_ms is not None and duration_ms > 0:
        
        # a whole file plays to its end, but in case the end is not where we think it is, we don't go on forever
        cmd += [ '-t', ConvertMSToFFMPEGSeconds( duration_ms + 1000 ) ]
        
    
    cmd += [ '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p' ]
    cmd += [ '-c:a', 'aac', '-b:a', '192k', '-ar', str( PLAYLIST_EXPORT_AUDIO_SAMPLE_RATE ), '-ac', '2' ]
    
    # the pieces need the same timebase to join cleanly
    cmd += [ '-video_track_timescale', '90000' ]
    
    cmd.append( output_path )
    
    return cmd
    

def GetPlaylistExportSpanMS( kind: int, start_ms: int | None, end_ms: int | None, duration_ms: int | None, still_period_ms: int ) -> tuple[ int | None, int | None ]:
    
    # ( where to start, how long to go on for ) for an item. None for the length means to the end of the file
    if kind == PLAYLIST_EXPORT_KIND_STILL:
        
        return ( None, still_period_ms )
        
    
    if start_ms is None:
        
        start_ms = 0
        
    
    if end_ms is not None:
        
        return ( start_ms, max( 0, end_ms - start_ms ) )
        
    
    if start_ms > 0 and duration_ms is not None:
        
        return ( start_ms, max( 0, duration_ms - start_ms ) )
        
    
    if start_ms == 0:
        
        return ( None, None )
        
    
    return ( start_ms, None )
    

def GetPlaylistExportStillPeriodMS() -> int:
    
    # the same as the playlist player
    slideshow_durations = CG.client_controller.new_options.GetSlideshowDurations()
    
    if len( slideshow_durations ) > 0:
        
        return int( slideshow_durations[0] * 1000 )
        
    
    return int( PLAYLIST_EXPORT_DEFAULT_STILL_PERIOD_S * 1000 )
    

def ParseFFMPEGProgressLineToMS( line: str ) -> int | None:
    
    # ffmpeg -progress gives out_time_us, and out_time_ms, which despite the name is also microseconds
    line = line.strip()
    
    for key in ( 'out_time_us=', 'out_time_ms=' ):
        
        if line.startswith( key ):
            
            value = line[ len( key ) : ]
            
            try:
                
                return max( 0, int( value ) // 1000 )
                
            except ValueError:
                
                # N/A before it gets going
                return None
                
            
        
    
    return None
    

def RunPlaylistExportFFMPEG( cmd: list[ str ], job_status: ClientThreading.JobStatus, stderr_path: str, progress_callable ):
    
    sbp_kwargs = HydrusSubprocess.GetSubprocessKWArgs( text = True )
    
    with open( stderr_path, 'w', encoding = 'utf-8' ) as stderr_file:
        
        process = subprocess.Popen( cmd, stdin = subprocess.DEVNULL, stdout = subprocess.PIPE, stderr = stderr_file, **sbp_kwargs )
        
        try:
            
            # ffmpeg writes progress every half second or so, so we get to check for a cancel often enough
            for line in process.stdout:
                
                if job_status.IsCancelled() or HG.model_shutdown:
                    
                    HydrusSubprocess.TerminateAndReapProcess( process )
                    
                    raise HydrusExceptions.CancelledException( 'Export cancelled!' )
                    
                
                progress_ms = ParseFFMPEGProgressLineToMS( line )
                
                if progress_ms is not None:
                    
                    progress_callable( progress_ms )
                    
                
            
            process.wait()
            
        except HydrusExceptions.CancelledException:
            
            raise
            
        except Exception:
            
            HydrusSubprocess.TerminateAndReapProcess( process )
            
            raise
            
        
    
    if process.returncode != 0:
        
        with open( stderr_path, 'r', encoding = 'utf-8', errors = 'replace' ) as f:
            
            stderr = f.read().strip()
            
        
        if len( stderr ) > 1000:
            
            stderr = '...' + stderr[ -1000 : ]
            
        
        raise Exception( f'ffmpeg failed (code {process.returncode}): {stderr}' )
        
    

def ExportPlaylistToMP4( job_status: ClientThreading.JobStatus, playlist_name: str, playlist_items: list[ tuple[ ClientMediaResult.MediaResult, int | None, int | None ] ], output_path: str ):
    
    # this runs in a worker thread
    ffmpeg_path = HydrusFFMPEG.GetCurrentFFMPEGPath()
    
    still_period_ms = GetPlaylistExportStillPeriodMS()
    
    # ( media_result, kind, start_ms, length_ms )
    plan = []
    
    skipped = []
    
    for ( media_result, start_ms, end_ms ) in playlist_items:
        
        kind = GetPlaylistExportKind( media_result.GetMime() )
        
        if kind == PLAYLIST_EXPORT_KIND_UNSUPPORTED:
            
            skipped.append( f'{media_result.GetHash().hex()}: {HC.mime_string_lookup.get( media_result.GetMime(), "that filetype" )} cannot go in a video' )
            
            continue
            
        
        ( item_start_ms, length_ms ) = GetPlaylistExportSpanMS( kind, start_ms, end_ms, media_result.GetDurationMS(), still_period_ms )
        
        plan.append( ( media_result, kind, item_start_ms, length_ms ) )
        
    
    if len( plan ) == 0:
        
        job_status.SetStatusText( 'Nothing in this playlist can go in a video!' )
        
        job_status.Finish()
        
        return
        
    
    resolution = GetPlaylistExportResolution( [ ( kind, media_result.GetResolution() ) for ( media_result, kind, start_ms, length_ms ) in plan ] )
    framerate = GetPlaylistExportFramerate( [ media_result.GetFileInfoManager().GetFramerate() for ( media_result, kind, start_ms, length_ms ) in plan if kind == PLAYLIST_EXPORT_KIND_MOTION ] )
    
    def get_estimated_length_ms( media_result, length_ms ):
        
        if length_ms is not None:
            
            return length_ms
            
        
        duration_ms = media_result.GetDurationMS()
        
        return 0 if duration_ms is None else duration_ms
        
    
    total_ms = max( 1, sum( ( get_estimated_length_ms( media_result, length_ms ) for ( media_result, kind, start_ms, length_ms ) in plan ) ) )
    
    temp_dir = HydrusTemp.GetSubTempDir( 'playlist_export' )
    
    try:
        
        stderr_path = os.path.join( temp_dir, 'ffmpeg_errors.txt' )
        
        segment_paths = []
        
        done_ms = 0
        
        for ( i, ( media_result, kind, start_ms, length_ms ) ) in enumerate( plan ):
            
            if job_status.IsCancelled() or HG.model_shutdown:
                
                raise HydrusExceptions.CancelledException( 'Export cancelled!' )
                
            
            job_status.SetStatusText( f'encoding {HydrusNumbers.ValueRangeToPrettyString( i + 1, len( plan ) )}' )
            
            estimated_length_ms = get_estimated_length_ms( media_result, length_ms )
            
            def progress_callable( progress_ms ):
                
                job_status.SetGauge( done_ms + min( progress_ms, estimated_length_ms ), total_ms )
                
            
            progress_callable( 0 )
            
            hash = media_result.GetHash()
            mime = media_result.GetMime()
            
            segment_path = os.path.join( temp_dir, f'{i:05}.mp4' )
            
            try:
                
                path = CG.client_controller.client_files_manager.GetFilePath( hash, mime )
                
                has_audio = False
                
                if kind == PLAYLIST_EXPORT_KIND_MOTION:
                    
                    has_audio = media_result.HasAudio()
                    
                elif kind == PLAYLIST_EXPORT_KIND_STILL:
                    
                    # hydrus can read more image formats than ffmpeg, so we draw it ourselves and give ffmpeg a png
                    numpy_image = HydrusImageHandling.GenerateNumPyImage( path, mime )
                    
                    png_path = os.path.join( temp_dir, f'{i:05}.png' )
                    
                    with open( png_path, 'wb' ) as f:
                        
                        f.write( HydrusImageHandling.GenerateFileBytesNumPy( numpy_image, '.png' ) )
                        
                    
                    path = png_path
                    
                
                cmd = GetPlaylistExportSegmentCommand( ffmpeg_path, kind, path, has_audio, start_ms, length_ms, media_result.GetDurationMS(), resolution, framerate, segment_path )
                
                RunPlaylistExportFFMPEG( cmd, job_status, stderr_path, progress_callable )
                
                segment_paths.append( segment_path )
                
            except HydrusExceptions.CancelledException:
                
                raise
                
            except Exception as e:
                
                # one bad file should not spoil the rest
                HydrusData.Print( f'Playlist export could not do {hash.hex()}:' )
                HydrusData.PrintException( e, do_wait = False )
                
                skipped.append( f'{hash.hex()}: {e}' )
                
            
            done_ms += estimated_length_ms
            
        
        if len( segment_paths ) == 0:
            
            raise Exception( 'None of the files in this playlist could be put in a video! Check the log for details.' )
            
        
        job_status.SetStatusText( 'joining it all together' )
        job_status.SetGauge( total_ms, total_ms )
        
        concat_list_path = os.path.join( temp_dir, 'concat.txt' )
        
        with open( concat_list_path, 'w', encoding = 'utf-8' ) as f:
            
            f.write( GetPlaylistExportConcatListText( segment_paths ) )
            
        
        cmd = GetPlaylistExportConcatCommand( ffmpeg_path, concat_list_path, output_path )
        
        try:
            
            RunPlaylistExportFFMPEG( cmd, job_status, stderr_path, lambda progress_ms: None )
            
        except Exception:
            
            # don't leave half a video behind
            if os.path.exists( output_path ):
                
                HydrusPaths.DeletePath( output_path )
                
            
            raise
            
        
        job_status.DeleteGauge()
        
        text = f'Exported {HydrusNumbers.ToHumanInt( len( segment_paths ) )} items to {output_path}.'
        
        if len( skipped ) > 0:
            
            text += '\n' * 2
            text += f'{HydrusNumbers.ToHumanInt( len( skipped ) )} items were left out:'
            text += '\n'
            text += '\n'.join( skipped[ : 10 ] )
            
            if len( skipped ) > 10:
                
                text += '\n'
                text += f'and {HydrusNumbers.ToHumanInt( len( skipped ) - 10 )} more (see the log)'
                
                for line in skipped[ 10 : ]:
                    
                    HydrusData.Print( f'Playlist export left out {line}' )
                    
                
            
        
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
        
        HydrusPaths.DeletePath( temp_dir )
        
        job_status.Finish()
        
    

def StartPlaylistExport( playlist_name: str, playlist_items: list[ tuple[ ClientMediaResult.MediaResult, int | None, int | None ] ], output_path: str ):
    
    job_status = ClientThreading.JobStatus( cancellable = True )
    
    job_status.SetStatusTitle( f'exporting playlist "{playlist_name}"' )
    
    CG.client_controller.pub( 'message', job_status )
    
    CG.client_controller.CallToThread( ExportPlaylistToMP4, job_status, playlist_name, playlist_items, output_path )
    

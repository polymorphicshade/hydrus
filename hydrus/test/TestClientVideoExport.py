import os
import unittest

from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusExceptions

from hydrus.client.exporting import ClientExportingVideo as V
from hydrus.client.gui.exporting import ClientGUIExportVideo

from hydrus.test import HelperFunctions as HF

def GetFakeVideoMediaResult( size = 50 * 1024 * 1024, width = 1920, height = 1080, duration_ms = 60000, num_frames = 1800, has_audio = True, mime = HC.VIDEO_MP4 ):
    
    media_result = HF.GetFakeMediaResult( os.urandom( 32 ), mime = mime )
    
    file_info_manager = media_result.GetFileInfoManager()
    
    file_info_manager.size = size
    file_info_manager.width = width
    file_info_manager.height = height
    file_info_manager.duration_ms = duration_ms
    file_info_manager.num_frames = num_frames
    file_info_manager.has_audio = has_audio
    
    return media_result
    

class TestVideoExport( unittest.TestCase ):
    
    def test_resolution_options( self ):
        
        options = V.GetVideoExportResolutionOptions( ( 1920, 1080 ) )
        
        self.assertEqual( options[0], ( 'original (1920x1080)', None ) )
        
        # just the smaller ones
        self.assertEqual( [ resolution for ( label, resolution ) in options[ 1 : ] ], [ ( 1280, 720 ), ( 854, 480 ), ( 640, 360 ), ( 426, 240 ) ] )
        
        # a tall video goes by its short side too
        options = V.GetVideoExportResolutionOptions( ( 720, 1280 ) )
        
        self.assertEqual( [ resolution for ( label, resolution ) in options[ 1 : ] ], [ ( 480, 854 ), ( 360, 640 ), ( 240, 426 ) ] )
        
        # always even
        self.assertEqual( V.GetVideoExportScaledResolution( ( 1001, 777 ), 480 ), ( 618, 480 ) )
        
        self.assertEqual( V.GetVideoExportResolutionOptions( ( None, None ) ), [ ( 'original', None ) ] )
        
    
    def test_framerate_options( self ):
        
        options = V.GetVideoExportFramerateOptions( 59.94 )
        
        self.assertEqual( [ framerate for ( label, framerate ) in options ], [ None, 30, 24, 15, 10 ] )
        
        # 29.97 is not worth going down to 30 for
        options = V.GetVideoExportFramerateOptions( 29.97 )
        
        self.assertEqual( [ framerate for ( label, framerate ) in options ], [ None, 24, 15, 10 ] )
        
        self.assertEqual( V.GetVideoExportFramerateOptions( None ), [ ( 'original', None ) ] )
        
    
    def test_target_bitrate( self ):
        
        # 10MB over 100 seconds is 800 kbps, less the margin, less the audio
        self.assertEqual( V.GetVideoExportTargetVideoKBPS( 10 * 1000 * 1000, 100000, 128 ), int( 800 * V.VIDEO_EXPORT_TARGET_SIZE_MARGIN - 128 ) )
        self.assertEqual( V.GetVideoExportTargetVideoKBPS( 10 * 1000 * 1000, 100000, None ), int( 800 * V.VIDEO_EXPORT_TARGET_SIZE_MARGIN ) )
        
        self.assertEqual( V.GetVideoExportTargetVideoKBPS( 10 * 1000 * 1000, 0, None ), 0 )
        
        # fits
        settings = V.VideoExportSettings( size_mode = V.VIDEO_EXPORT_SIZE_MODE_TARGET, target_size_bytes = 8 * 1024 * 1024 )
        
        self.assertIsNone( V.GetVideoExportProblem( settings, 60000 ) )
        
        estimate = V.EstimateVideoExportSize( settings, 50 * 1024 * 1024, ( 1920, 1080 ), 30.0, 60000 )
        
        self.assertLessEqual( estimate, 8 * 1024 * 1024 )
        self.assertGreater( estimate, 7 * 1024 * 1024 )
        
        # but it will not look good at 1080p
        self.assertIsNotNone( V.GetVideoExportWarning( settings, ( 1920, 1080 ), 30.0, 60000 ) )
        
        # at 480p it is fine
        settings.resolution = ( 854, 480 )
        
        self.assertIsNone( V.GetVideoExportWarning( settings, ( 1920, 1080 ), 30.0, 60000 ) )
        
        # the audio alone is too big
        settings = V.VideoExportSettings( size_mode = V.VIDEO_EXPORT_SIZE_MODE_TARGET, target_size_bytes = 100 * 1024, audio_kbps = 192 )
        
        self.assertIsNotNone( V.GetVideoExportProblem( settings, 60000 ) )
        self.assertIsNone( V.EstimateVideoExportSize( settings, 50 * 1024 * 1024, ( 1920, 1080 ), 30.0, 60000 ) )
        
        # nothing to fit without a duration
        settings = V.VideoExportSettings( size_mode = V.VIDEO_EXPORT_SIZE_MODE_TARGET, target_size_bytes = 8 * 1024 * 1024 )
        
        self.assertIsNotNone( V.GetVideoExportProblem( settings, None ) )
        
        # quality and raw always work
        self.assertIsNone( V.GetVideoExportProblem( V.VideoExportSettings(), None ) )
        self.assertIsNone( V.GetVideoExportProblem( V.VideoExportSettings( export_format = V.VIDEO_EXPORT_FORMAT_RAW ), None ) )
        
    
    def test_estimates( self ):
        
        source_size = 500 * 1024 * 1024
        
        # raw is the file
        self.assertEqual( V.EstimateVideoExportSize( V.VideoExportSettings( export_format = V.VIDEO_EXPORT_FORMAT_RAW ), source_size, ( 1920, 1080 ), 30.0, 60000 ), source_size )
        
        best = V.VideoExportSettings( quality_index = 0 )
        lowest = V.VideoExportSettings( quality_index = len( V.VIDEO_EXPORT_QUALITIES ) - 1 )
        
        best_estimate = V.EstimateVideoExportSize( best, source_size, ( 1920, 1080 ), 30.0, 60000 )
        lowest_estimate = V.EstimateVideoExportSize( lowest, source_size, ( 1920, 1080 ), 30.0, 60000 )
        
        self.assertGreater( best_estimate, lowest_estimate )
        
        # smaller resolution, smaller file
        small = V.VideoExportSettings( quality_index = 0, resolution = ( 1280, 720 ) )
        
        self.assertLess( V.EstimateVideoExportSize( small, source_size, ( 1920, 1080 ), 30.0, 60000 ), best_estimate )
        
        # webm is smaller than mp4 at the same quality
        webm = V.VideoExportSettings( export_format = V.VIDEO_EXPORT_FORMAT_WEBM, quality_index = 0 )
        
        self.assertLess( V.EstimateVideoExportSize( webm, source_size, ( 1920, 1080 ), 30.0, 60000 ), best_estimate )
        
        # a file that is already small is not guessed to get much bigger
        small_source_size = 1024 * 1024
        
        self.assertLessEqual( V.EstimateVideoExportSize( V.VideoExportSettings( quality_index = 0, audio_kbps = None ), small_source_size, ( 1920, 1080 ), 30.0, 60000 ), small_source_size * V.VIDEO_EXPORT_SOURCE_SIZE_CAP_FACTOR )
        
        # no duration, no guess
        self.assertIsNone( V.EstimateVideoExportSize( best, source_size, ( 1920, 1080 ), 30.0, None ) )
        
    
    def test_extensions( self ):
        
        self.assertEqual( V.GetVideoExportExtension( V.VIDEO_EXPORT_FORMAT_MP4, HC.VIDEO_MKV ), '.mp4' )
        self.assertEqual( V.GetVideoExportExtension( V.VIDEO_EXPORT_FORMAT_WEBM, HC.VIDEO_MKV ), '.webm' )
        self.assertEqual( V.GetVideoExportExtension( V.VIDEO_EXPORT_FORMAT_RAW, HC.VIDEO_MKV ), '.mkv' )
        
    
    def test_commands( self ):
        
        # a quality level is one pass
        settings = V.VideoExportSettings( resolution = ( 1280, 720 ), framerate = 24, audio_kbps = 96, quality_index = 2 )
        
        cmds = V.GetVideoExportFFMPEGCommands( 'ffmpeg', 'in.mkv', 'out.mp4', settings, ( 1920, 1080 ), True, 60000, 'passlog' )
        
        self.assertEqual( len( cmds ), 1 )
        
        cmd = cmds[0]
        
        self.assertEqual( cmd[ cmd.index( '-vf' ) + 1 ], 'scale=1280:720:flags=lanczos,setsar=1,fps=24,format=yuv420p' )
        self.assertEqual( cmd[ cmd.index( '-c:v' ) + 1 ], 'libx264' )
        self.assertEqual( cmd[ cmd.index( '-crf' ) + 1 ], str( V.VIDEO_EXPORT_QUALITIES[2][1] ) )
        self.assertEqual( cmd[ cmd.index( '-c:a' ) + 1 ], 'aac' )
        self.assertEqual( cmd[ cmd.index( '-b:a' ) + 1 ], '96k' )
        self.assertIn( '0:a:0', cmd )
        self.assertEqual( cmd[-1], 'out.mp4' )
        
        # an odd original size is made even, and no audio means no audio
        settings = V.VideoExportSettings( export_format = V.VIDEO_EXPORT_FORMAT_WEBM, audio_kbps = None )
        
        cmd = V.GetVideoExportFFMPEGCommands( 'ffmpeg', 'in.mkv', 'out.webm', settings, ( 1001, 777 ), True, 60000, 'passlog' )[0]
        
        self.assertEqual( cmd[ cmd.index( '-vf' ) + 1 ], 'scale=1000:776:flags=lanczos,setsar=1,format=yuv420p' )
        self.assertEqual( cmd[ cmd.index( '-c:v' ) + 1 ], 'libvpx-vp9' )
        self.assertEqual( cmd[ cmd.index( '-b:v' ) + 1 ], '0' )
        self.assertIn( '-an', cmd )
        self.assertNotIn( '0:a:0', cmd )
        
        # a file with no audio gets no audio, whatever the settings say
        settings = V.VideoExportSettings( audio_kbps = 128 )
        
        cmd = V.GetVideoExportFFMPEGCommands( 'ffmpeg', 'in.mkv', 'out.mp4', settings, ( 1920, 1080 ), False, 60000, 'passlog' )[0]
        
        self.assertIn( '-an', cmd )
        
        # a target size is two passes at a bitrate
        settings = V.VideoExportSettings( export_format = V.VIDEO_EXPORT_FORMAT_WEBM, size_mode = V.VIDEO_EXPORT_SIZE_MODE_TARGET, target_size_bytes = 10 * 1000 * 1000, audio_kbps = 64 )
        
        cmds = V.GetVideoExportFFMPEGCommands( 'ffmpeg', 'in.mkv', 'out.webm', settings, ( 1920, 1080 ), True, 100000, 'passlog' )
        
        self.assertEqual( len( cmds ), 2 )
        
        ( first_pass, second_pass ) = cmds
        
        video_kbps = V.GetVideoExportTargetVideoKBPS( 10 * 1000 * 1000, 100000, 64 )
        
        for cmd in cmds:
            
            self.assertEqual( cmd[ cmd.index( '-b:v' ) + 1 ], f'{video_kbps}k' )
            self.assertEqual( cmd[ cmd.index( '-passlogfile' ) + 1 ], 'passlog' )
            self.assertNotIn( '-crf', cmd )
            
        
        self.assertEqual( first_pass[ first_pass.index( '-pass' ) + 1 ], '1' )
        self.assertIn( '-an', first_pass )
        self.assertEqual( first_pass[-1], os.devnull )
        
        self.assertEqual( second_pass[ second_pass.index( '-pass' ) + 1 ], '2' )
        self.assertEqual( second_pass[ second_pass.index( '-c:a' ) + 1 ], 'libopus' )
        self.assertEqual( second_pass[-1], 'out.webm' )
        
        # a target size that cannot fit is refused
        settings = V.VideoExportSettings( size_mode = V.VIDEO_EXPORT_SIZE_MODE_TARGET, target_size_bytes = 1000 )
        
        with self.assertRaises( HydrusExceptions.VetoException ):
            
            V.GetVideoExportFFMPEGCommands( 'ffmpeg', 'in.mkv', 'out.mp4', settings, ( 1920, 1080 ), True, 100000, 'passlog' )
            
        
        # raw is not encoded
        with self.assertRaises( HydrusExceptions.UnsupportedFileException ):
            
            V.GetVideoExportFFMPEGCommands( 'ffmpeg', 'in.mkv', 'out.mkv', V.VideoExportSettings( export_format = V.VIDEO_EXPORT_FORMAT_RAW ), ( 1920, 1080 ), True, 100000, 'passlog' )
            
        
    
    def test_can_export_video( self ):
        
        self.assertTrue( ClientGUIExportVideo.CanExportVideo( GetFakeVideoMediaResult() ) )
        self.assertTrue( ClientGUIExportVideo.CanExportVideo( GetFakeVideoMediaResult( mime = HC.VIDEO_WEBM ) ) )
        
        # gifs and audio are not videos
        self.assertFalse( ClientGUIExportVideo.CanExportVideo( GetFakeVideoMediaResult( mime = HC.ANIMATION_GIF ) ) )
        self.assertFalse( ClientGUIExportVideo.CanExportVideo( GetFakeVideoMediaResult( mime = HC.AUDIO_MP3 ) ) )
        
    
    def test_panel( self ):
        
        dialog = QW.QDialog()
        
        media_result = GetFakeVideoMediaResult()
        
        panel = ClientGUIExportVideo.EditVideoExportPanel( dialog, media_result, None )
        
        # the defaults: an mp4 at the file's own size, at a quality
        settings = panel.GetValue()
        
        self.assertEqual( settings, V.VideoExportSettings( target_size_bytes = 8 * 1024 * 1024 ) )
        
        self.assertTrue( panel._quality.isEnabled() )
        self.assertFalse( panel._target_size_mb.isEnabled() )
        self.assertIn( 'approximate resulting file size', panel._estimate.text() )
        
        # fit a size
        panel._size_mode.SetValue( V.VIDEO_EXPORT_SIZE_MODE_TARGET )
        panel._UpdateControls()
        
        self.assertFalse( panel._quality.isEnabled() )
        self.assertTrue( panel._target_size_mb.isEnabled() )
        self.assertIn( 'kbps', panel._estimate.text() )
        
        panel._resolution.SetValue( ( 1280, 720 ) )
        panel._framerate.SetValue( 24 )
        panel._audio.SetValue( None )
        panel._target_size_mb.setValue( 5.0 )
        
        settings = panel.GetValue()
        
        self.assertEqual( settings, V.VideoExportSettings( resolution = ( 1280, 720 ), framerate = 24, audio_kbps = None, size_mode = V.VIDEO_EXPORT_SIZE_MODE_TARGET, target_size_bytes = 5 * 1024 * 1024 ) )
        
        # too small to fit is refused
        panel._target_size_mb.setValue( 0.1 )
        panel._audio.SetValue( 192 )
        
        self.assertFalse( panel._warning.isHidden() )
        
        with self.assertRaises( HydrusExceptions.VetoException ):
            
            panel.GetValue()
            
        
        # raw turns the encoding off
        panel._format.SetValue( V.VIDEO_EXPORT_FORMAT_RAW )
        panel._UpdateControls()
        
        self.assertFalse( panel._encode_box.isEnabled() )
        self.assertEqual( panel.GetValue().export_format, V.VIDEO_EXPORT_FORMAT_RAW )
        
        # the next one starts how this one was set
        panel = ClientGUIExportVideo.EditVideoExportPanel( dialog, media_result, settings )
        
        next_settings = panel.GetValue()
        
        self.assertEqual( next_settings.size_mode, V.VIDEO_EXPORT_SIZE_MODE_TARGET )
        self.assertEqual( next_settings.target_size_bytes, 5 * 1024 * 1024 )
        self.assertEqual( next_settings.audio_kbps, None )
        
        # but not its resolution or framerate, which were for that file
        self.assertEqual( next_settings.resolution, None )
        self.assertEqual( next_settings.framerate, None )
        
        # no audio, no duration: nothing to pick, and nothing to fit
        media_result = GetFakeVideoMediaResult( has_audio = False, duration_ms = None, num_frames = None )
        
        panel = ClientGUIExportVideo.EditVideoExportPanel( dialog, media_result, settings )
        
        self.assertEqual( panel._audio.count(), 1 )
        self.assertFalse( panel._size_mode.isEnabled() )
        
        next_settings = panel.GetValue()
        
        self.assertEqual( next_settings.audio_kbps, None )
        self.assertEqual( next_settings.size_mode, V.VIDEO_EXPORT_SIZE_MODE_QUALITY )
        
        dialog.deleteLater()
        
    

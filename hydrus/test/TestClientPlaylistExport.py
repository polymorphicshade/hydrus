import unittest

from hydrus.core import HydrusConstants as HC

from hydrus.client.exporting import ClientExportingPlaylists

class TestPlaylistExport( unittest.TestCase ):
    
    def test_kinds( self ):
        
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportKind( HC.VIDEO_MP4 ), ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_MOTION )
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportKind( HC.VIDEO_WEBM ), ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_MOTION )
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportKind( HC.ANIMATION_GIF ), ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_MOTION )
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportKind( HC.AUDIO_MP3 ), ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_AUDIO )
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportKind( HC.IMAGE_JPEG ), ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_STILL )
        
        # animations ffmpeg cannot play go in as a still
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportKind( HC.ANIMATION_UGOIRA ), ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_STILL )
        
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportKind( HC.APPLICATION_PDF ), ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_UNSUPPORTED )
        
    
    def test_spans( self ):
        
        motion = ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_MOTION
        still = ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_STILL
        
        # a whole file plays to its end
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportSpanMS( motion, None, None, 10000, 5000 ), ( None, None ) )
        
        # a part of a file is just that part
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportSpanMS( motion, 1000, 2500, 10000, 5000 ), ( 1000, 1500 ) )
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportSpanMS( motion, 0, 2500, 10000, 5000 ), ( 0, 2500 ) )
        
        # a start with no end goes to the end
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportSpanMS( motion, 4000, None, 10000, 5000 ), ( 4000, 6000 ) )
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportSpanMS( motion, 4000, None, None, 5000 ), ( 4000, None ) )
        
        # an image stays up for the still period
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportSpanMS( still, None, None, None, 5000 ), ( None, 5000 ) )
        
    
    def test_resolution_and_framerate( self ):
        
        motion = ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_MOTION
        still = ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_STILL
        audio = ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_AUDIO
        
        # the biggest video wins over a bigger image
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportResolution( [ ( motion, ( 640, 360 ) ), ( motion, ( 1280, 720 ) ), ( still, ( 2000, 2000 ) ) ] ), ( 1280, 720 ) )
        
        # with no videos, the biggest image, made even
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportResolution( [ ( still, ( 501, 333 ) ), ( audio, ( None, None ) ) ] ), ( 500, 332 ) )
        
        # a huge image is brought down to fit in 4k, either way round
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportResolution( [ ( still, ( 7680, 4320 ) ) ] ), ( 3840, 2160 ) )
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportResolution( [ ( still, ( 4320, 7680 ) ) ] ), ( 2160, 3840 ) )
        
        # just audio gets a default black frame
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportResolution( [ ( audio, ( None, None ) ) ] ), ClientExportingPlaylists.PLAYLIST_EXPORT_DEFAULT_RESOLUTION )
        
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportFramerate( [ 23.976, 29.97, None ] ), 30 )
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportFramerate( [ 144.0 ] ), ClientExportingPlaylists.PLAYLIST_EXPORT_MAX_FRAMERATE )
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportFramerate( [] ), ClientExportingPlaylists.PLAYLIST_EXPORT_DEFAULT_FRAMERATE )
        
    
    def test_commands( self ):
        
        motion = ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_MOTION
        audio = ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_AUDIO
        still = ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_STILL
        
        # a part of a video with audio
        cmd = ClientExportingPlaylists.GetPlaylistExportSegmentCommand( 'ffmpeg', motion, 'in.mp4', True, 1000, 1500, 10000, ( 1280, 720 ), 30, 'out.mp4' )
        
        self.assertEqual( cmd[0], 'ffmpeg' )
        self.assertEqual( cmd[ cmd.index( '-ss' ) + 1 ], '1.000' )
        self.assertEqual( cmd[ cmd.index( '-t' ) + 1 ], '1.500' )
        self.assertLess( cmd.index( '-ss' ), cmd.index( '-i' ) )
        self.assertIn( '[0:a:0]apad[a]', cmd[ cmd.index( '-filter_complex' ) + 1 ] )
        self.assertIn( 'scale=1280:720', cmd[ cmd.index( '-filter_complex' ) + 1 ] )
        self.assertIn( '-shortest', cmd )
        self.assertEqual( cmd[-1], 'out.mp4' )
        
        # a whole silent video gets silence, and is capped a little past its end
        cmd = ClientExportingPlaylists.GetPlaylistExportSegmentCommand( 'ffmpeg', motion, 'in.webm', False, None, None, 2000, ( 1280, 720 ), 30, 'out.mp4' )
        
        self.assertNotIn( '-ss', cmd )
        self.assertIn( '-f', cmd )
        self.assertTrue( any( arg.startswith( 'anullsrc' ) for arg in cmd ) )
        self.assertEqual( cmd[ cmd.index( '-t' ) + 1 ], '3.000' )
        
        # audio goes over black
        cmd = ClientExportingPlaylists.GetPlaylistExportSegmentCommand( 'ffmpeg', audio, 'in.mp3', False, None, None, None, ( 640, 360 ), 30, 'out.mp4' )
        
        self.assertTrue( any( arg.startswith( 'color=c=black:s=640x360' ) for arg in cmd ) )
        self.assertNotIn( '-t', cmd )
        
        # an image is looped for the still period
        cmd = ClientExportingPlaylists.GetPlaylistExportSegmentCommand( 'ffmpeg', still, 'in.png', False, None, 5000, None, ( 640, 360 ), 30, 'out.mp4' )
        
        self.assertEqual( cmd[ cmd.index( '-loop' ) + 1 ], '1' )
        self.assertEqual( cmd[ cmd.index( '-t' ) + 1 ], '5.000' )
        
        cmd = ClientExportingPlaylists.GetPlaylistExportConcatCommand( 'ffmpeg', 'list.txt', 'final.mp4' )
        
        self.assertEqual( cmd[ cmd.index( '-f' ) + 1 ], 'concat' )
        self.assertEqual( cmd[ cmd.index( '-c' ) + 1 ], 'copy' )
        self.assertEqual( cmd[-1], 'final.mp4' )
        
        # quotes in paths are escaped for the concat list
        self.assertEqual( ClientExportingPlaylists.GetPlaylistExportConcatListText( [ 'C:\\temp\\a.mp4', "/tmp/it's.mp4" ] ), "file 'C:/temp/a.mp4'\nfile '/tmp/it'\\''s.mp4'\n" )
        
    
    def test_progress( self ):
        
        self.assertEqual( ClientExportingPlaylists.ParseFFMPEGProgressLineToMS( 'out_time_us=1500000\n' ), 1500 )
        self.assertEqual( ClientExportingPlaylists.ParseFFMPEGProgressLineToMS( 'out_time_ms=2500000' ), 2500 )
        self.assertIsNone( ClientExportingPlaylists.ParseFFMPEGProgressLineToMS( 'out_time_us=N/A' ) )
        self.assertIsNone( ClientExportingPlaylists.ParseFFMPEGProgressLineToMS( 'frame=12' ) )
        
    

import unittest

from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.canvas import ClientGUIMPV

class TestPlaybackPoints( unittest.TestCase ):
    
    def _check_frames( self, frame_starts_ms: list[ float ], frame_durations_ms: list[ float ] ):
        
        num_frames = len( frame_starts_ms )
        
        def get_frame_start_ms( frame_index ):
            
            if frame_index == num_frames:
                
                return frame_starts_ms[-1] + frame_durations_ms[-1]
                
            
            return frame_starts_ms[ frame_index ]
            
        
        def frame_containing( timestamp_ms ):
            
            # how the native renderer and mpv see a point: the last frame that starts at or before it
            return max( i for i in range( num_frames ) if frame_starts_ms[ i ] <= timestamp_ms )
            
        
        for frame_index in range( num_frames ):
            
            frame_start_ms = frame_starts_ms[ frame_index ]
            frame_duration_ms = frame_durations_ms[ frame_index ]
            
            a_ms = ClientGUICanvasMedia.ConvertFrameStartToPlaybackPointMS( frame_start_ms )
            b_ms = ClientGUICanvasMedia.ConvertFrameToABLoopPointBMS( frame_start_ms, frame_duration_ms )
            
            self.assertIsInstance( a_ms, int )
            self.assertIsInstance( b_ms, int )
            
            # jumping back to A lands on the frame A was set on
            self.assertEqual( ClientGUICanvasMedia.GetFrameIndexAtPlaybackPoint( a_ms, num_frames, get_frame_start_ms ), frame_index )
            
            # the frame B was set on is the last one the loop shows
            self.assertEqual( frame_containing( b_ms ), frame_index )
            
            # mpv loops at the first frame that starts at or after B, so B must be strictly inside its frame
            self.assertLess( frame_start_ms, b_ms )
            self.assertLess( b_ms, get_frame_start_ms( frame_index + 1 ) )
            
            # a skip from A to B goes on to the frame after B's
            self.assertEqual( ClientGUICanvasMedia.GetFrameIndexAtPlaybackPoint( b_ms, num_frames, get_frame_start_ms ), frame_index + 1 )
            
            # a zoom timestamp comes in with its frame, not a frame early or late
            zoom_timestamps = [ ( a_ms, 1.5 ) ]
            
            self.assertEqual( ClientGUICanvasMedia.GetZoomTimestampAt( zoom_timestamps, frame_start_ms ), ( a_ms, 1.5 ) )
            
            if frame_index > 0:
                
                self.assertIsNone( ClientGUICanvasMedia.GetZoomTimestampAt( zoom_timestamps, frame_starts_ms[ frame_index - 1 ] ) )
                
            
        
    
    def test_constant_framerate( self ):
        
        # 23.976fps, where frames start partway through a ms
        frame_duration_ms = 1001 / 24
        
        num_frames = 500
        
        self._check_frames( [ frame_duration_ms * i for i in range( num_frames ) ], [ frame_duration_ms ] * num_frames )
        
        # 60fps, and 144fps for short frames
        for frame_duration_ms in ( 1000 / 60, 1000 / 144 ):
            
            self._check_frames( [ frame_duration_ms * i for i in range( num_frames ) ], [ frame_duration_ms ] * num_frames )
            
        
    
    def test_variable_framerate( self ):
        
        frame_durations_ms = [ 40, 100, 33.3, 20, 1000, 66.7, 16.66, 50 ] * 10
        
        frame_starts_ms = []
        
        so_far = 0.0
        
        for frame_duration_ms in frame_durations_ms:
            
            frame_starts_ms.append( so_far )
            
            so_far += frame_duration_ms
            
        
        self._check_frames( frame_starts_ms, frame_durations_ms )
        
    
    def test_float_fuzz( self ):
        
        # a frame start that should be a whole ms, but float maths puts it just under
        self.assertEqual( ClientGUICanvasMedia.ConvertFrameStartToPlaybackPointMS( 999.9999999999 ), 1000 )
        self.assertEqual( ClientGUICanvasMedia.ConvertFrameStartToPlaybackPointMS( 1042.7083333 ), 1042 )
        self.assertEqual( ClientGUICanvasMedia.ConvertFrameStartToPlaybackPointMS( 0.0 ), 0 )
        
        frame_starts_ms = [ 0.0, 499.9999999999, 1000.0000000001 ]
        
        get_frame_start_ms = lambda i: frame_starts_ms[ i ] if i < 3 else 1500.0
        
        self.assertEqual( ClientGUICanvasMedia.GetFrameIndexAtPlaybackPoint( 500, 3, get_frame_start_ms ), 1 )
        self.assertEqual( ClientGUICanvasMedia.GetFrameIndexAtPlaybackPoint( 1000, 3, get_frame_start_ms ), 2 )
        
        # past the start of the last frame is the end
        self.assertEqual( ClientGUICanvasMedia.GetFrameIndexAtPlaybackPoint( 1250, 3, get_frame_start_ms ), 3 )
        
    
    def test_no_frames( self ):
        
        # audio has no frames, so the points are just where playback is
        self.assertEqual( ClientGUICanvasMedia.ConvertFrameToABLoopPointBMS( 1234.5, 0.0 ), 1234 )
        
    
    def test_old_points( self ):
        
        # before this, points were the time rounded down, which is the same as a frame start rounded down, so old skips still end on the frame they did
        frame_duration_ms = 1001 / 24
        
        get_frame_start_ms = lambda i: frame_duration_ms * i
        
        for frame_index in range( 1, 200 ):
            
            old_point_ms = int( frame_duration_ms * frame_index )
            
            self.assertEqual( ClientGUICanvasMedia.GetFrameIndexAtPlaybackPoint( old_point_ms, 200, get_frame_start_ms ), frame_index )
            
        
    
    def test_mpv_start_option( self ):
        
        # a playlist item that starts part way in is loaded there, rather than seeked to after it starts
        self.assertEqual( ClientGUIMPV.ConvertStartMSToMPVLoadFileOptions( 12345 ), 'start=12.345' )
        self.assertEqual( ClientGUIMPV.ConvertStartMSToMPVLoadFileOptions( 1000 ), 'start=1.000' )
        
        # the start of the file needs no option
        self.assertEqual( ClientGUIMPV.ConvertStartMSToMPVLoadFileOptions( 0 ), '' )
        self.assertEqual( ClientGUIMPV.ConvertStartMSToMPVLoadFileOptions( None ), '' )
        
    

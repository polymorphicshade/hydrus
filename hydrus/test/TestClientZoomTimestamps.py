import unittest

from hydrus.client.gui.canvas import ClientGUICanvasMedia

class TestZoomTimestamps( unittest.TestCase ):
    
    def test_zoom_timestamp_at( self ):
        
        # at 5 seconds, zoom to 150%. at 13 seconds, zoom to 70%
        zoom_timestamps = [ ( 13000, 0.7 ), ( 5000, 1.5 ) ]
        
        def at( timestamp_ms ):
            
            return ClientGUICanvasMedia.GetZoomTimestampAt( zoom_timestamps, timestamp_ms )
            
        
        # before the first one, it is the zoom the file started at
        self.assertIsNone( at( 0 ) )
        self.assertIsNone( at( 4999.9 ) )
        
        # each one holds until the next
        self.assertEqual( at( 5000 ), ( 5000, 1.5 ) )
        self.assertEqual( at( 12999 ), ( 5000, 1.5 ) )
        self.assertEqual( at( 13000 ), ( 13000, 0.7 ) )
        self.assertEqual( at( 60000 ), ( 13000, 0.7 ) )
        
        self.assertIsNone( ClientGUICanvasMedia.GetZoomTimestampAt( [], 5000 ) )
        
        # one at the very start is in from the beginning
        self.assertEqual( ClientGUICanvasMedia.GetZoomTimestampAt( [ ( 0, 2.0 ) ], 0 ), ( 0, 2.0 ) )
        
    
    def test_relative_zoom_timestamps( self ):
        
        # the window fits the file at 50%. an old one at a plain 150% is three times that
        rows = [ ( 0, 1.0, True, 0.25, 0.75 ), ( 5000, 1.5, False, None, None ), ( 13000, 0.7, True, None, None ) ]
        
        ( zoom_timestamps, converted_some ) = ClientGUICanvasMedia.ConvertZoomTimestampRowsToRelative( rows, 0.5 )
        
        self.assertEqual( zoom_timestamps, [ ( 0, 1.0, 0.25, 0.75 ), ( 5000, 3.0, None, None ), ( 13000, 0.7, None, None ) ] )
        self.assertTrue( converted_some )
        
        # relative ones are left alone
        ( zoom_timestamps, converted_some ) = ClientGUICanvasMedia.ConvertZoomTimestampRowsToRelative( [ ( 5000, 1.5, True, 0.5, 0.5 ) ], 0.5 )
        
        self.assertEqual( zoom_timestamps, [ ( 5000, 1.5, 0.5, 0.5 ) ] )
        self.assertFalse( converted_some )
        
        self.assertEqual( ClientGUICanvasMedia.ConvertZoomTimestampRowsToRelative( [], 0.5 ), ( [], False ) )
        
    
    def test_zoom_timestamp_pan( self ):
        
        # a 1000x500 window, with a 2000x1000 file panned so its top left quarter is showing
        center = ClientGUICanvasMedia.GetZoomCenter( ( 1000, 500 ), ( 0, 0 ), ( 2000, 1000 ) )
        
        self.assertEqual( center, ( 0.25, 0.25 ) )
        
        # the same pan in that window puts it back
        self.assertEqual( ClientGUICanvasMedia.GetMediaPosForZoomCenter( ( 1000, 500 ), ( 2000, 1000 ), center ), ( 0, 0 ) )
        
        # in a window half the size, the file is half the size too, and the same part of it is in the middle
        self.assertEqual( ClientGUICanvasMedia.GetMediaPosForZoomCenter( ( 500, 250 ), ( 1000, 500 ), center ), ( 0, 0 ) )
        
        # a file that is centered is at the middle
        self.assertEqual( ClientGUICanvasMedia.GetZoomCenter( ( 1000, 500 ), ( -500, -250 ), ( 2000, 1000 ) ), ( 0.5, 0.5 ) )
        self.assertEqual( ClientGUICanvasMedia.GetMediaPosForZoomCenter( ( 1600, 900 ), ( 3200, 1800 ), ( 0.5, 0.5 ) ), ( -800, -450 ) )
        
        # a file smaller than the window, moved off to the right
        center = ClientGUICanvasMedia.GetZoomCenter( ( 1000, 500 ), ( 700, 100 ), ( 200, 300 ) )
        
        self.assertEqual( center, ( -1.0, 0.5 ) )
        self.assertEqual( ClientGUICanvasMedia.GetMediaPosForZoomCenter( ( 1000, 500 ), ( 200, 300 ), center ), ( 700, 100 ) )
        
        # no size, no pan
        self.assertEqual( ClientGUICanvasMedia.GetZoomCenter( ( 1000, 500 ), ( 0, 0 ), ( 0, 0 ) ), ( 0.5, 0.5 ) )
        
        # the pan does not get in the way of finding which one we are in
        self.assertEqual( ClientGUICanvasMedia.GetZoomTimestampAt( [ ( 5000, 1.5, 0.2, 0.3 ), ( 0, 1.0, None, None ) ], 6000 ), ( 5000, 1.5, 0.2, 0.3 ) )
        
    

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
        
    

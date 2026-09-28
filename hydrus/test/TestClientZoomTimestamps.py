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
        rows = [ ( 0, 1.0, True ), ( 5000, 1.5, False ), ( 13000, 0.7, True ) ]
        
        ( zoom_timestamps, converted_some ) = ClientGUICanvasMedia.ConvertZoomTimestampRowsToRelative( rows, 0.5 )
        
        self.assertEqual( zoom_timestamps, [ ( 0, 1.0 ), ( 5000, 3.0 ), ( 13000, 0.7 ) ] )
        self.assertTrue( converted_some )
        
        # relative ones are left alone
        ( zoom_timestamps, converted_some ) = ClientGUICanvasMedia.ConvertZoomTimestampRowsToRelative( [ ( 5000, 1.5, True ) ], 0.5 )
        
        self.assertEqual( zoom_timestamps, [ ( 5000, 1.5 ) ] )
        self.assertFalse( converted_some )
        
        self.assertEqual( ClientGUICanvasMedia.ConvertZoomTimestampRowsToRelative( [], 0.5 ), ( [], False ) )
        
    

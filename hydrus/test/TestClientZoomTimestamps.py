import unittest

from unittest import mock

from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.media import ClientGUIMediaZooms

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
        
        # the window fits the file at 50%. an old one at a plain 150% is three times that. the orientation comes through as it is
        rows = [ ( 0, 1.0, True, 0.25, 0.75, 90 ), ( 5000, 1.5, False, None, None, None ), ( 13000, 0.7, True, None, None, 0 ) ]
        
        ( zoom_timestamps, converted_some ) = ClientGUICanvasMedia.ConvertZoomTimestampRowsToRelative( rows, 0.5 )
        
        self.assertEqual( zoom_timestamps, [ ( 0, 1.0, 0.25, 0.75, 90 ), ( 5000, 3.0, None, None, None ), ( 13000, 0.7, None, None, 0 ) ] )
        self.assertTrue( converted_some )
        
        # relative ones are left alone
        ( zoom_timestamps, converted_some ) = ClientGUICanvasMedia.ConvertZoomTimestampRowsToRelative( [ ( 5000, 1.5, True, 0.5, 0.5, 180 ) ], 0.5 )
        
        self.assertEqual( zoom_timestamps, [ ( 5000, 1.5, 0.5, 0.5, 180 ) ] )
        self.assertFalse( converted_some )
        
        self.assertEqual( ClientGUICanvasMedia.ConvertZoomTimestampRowsToRelative( [], 0.5 ), ( [], False ) )
        
    
    def test_saved_pan_centered( self ):
        
        # within a pixel of the middle is centered, so there is nothing to save
        self.assertTrue( ClientGUICanvasMedia.PanCenterIsCentered( ( 0.5, 0.5 ), ( 1000, 500 ) ) )
        self.assertTrue( ClientGUICanvasMedia.PanCenterIsCentered( ( 0.5005, 0.499 ), ( 1000, 500 ) ) )
        
        self.assertFalse( ClientGUICanvasMedia.PanCenterIsCentered( ( 0.502, 0.5 ), ( 1000, 500 ) ) )
        self.assertFalse( ClientGUICanvasMedia.PanCenterIsCentered( ( 0.5, 0.25 ), ( 1000, 500 ) ) )
        
        # a tiny file is always about centered
        self.assertTrue( ClientGUICanvasMedia.PanCenterIsCentered( ( 0.9, 0.9 ), ( 1, 1 ) ) )
        
    
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
        
        # the pan and orientation do not get in the way of finding which one we are in
        self.assertEqual( ClientGUICanvasMedia.GetZoomTimestampAt( [ ( 5000, 1.5, 0.2, 0.3, 90 ), ( 0, 1.0, None, None, None ) ], 6000 ), ( 5000, 1.5, 0.2, 0.3, 90 ) )
        
    
    def test_position_timestamp_pretty( self ):
        
        self.assertEqual( ClientGUICanvasMedia.ConvertZoomTimestampToPrettyString( ( 5000, 1.5, 0.2, 0.3, 90 ) ), '0:05.000: 150% of fit, turned 90\u00b0' )
        
        # old ones are centered and leave the orientation alone
        self.assertEqual( ClientGUICanvasMedia.ConvertZoomTimestampToPrettyString( ( 5000, 1.5, None, None, None ) ), '0:05.000: 150% of fit, centered' )
        
    
    def test_position_timestamp_orientation( self ):
        
        # just enough of a media container to go to a position timestamp
        container = ClientGUICanvasMedia.MediaContainer.__new__( ClientGUICanvasMedia.MediaContainer )
        
        calls = []
        
        container._rotation = 0
        container._file_rotation = 0
        container._zoom_types_to_zooms = { ClientGUICanvasMedia.MEDIA_VIEWER_ZOOM_TYPE_CANVAS : 0.5 }
        
        def set_rotation( rotation ):
            
            calls.append( ( 'rotate', rotation ) )
            
            container._rotation = rotation
            
            # turned on its side, it fits the window at a different zoom
            container._zoom_types_to_zooms = { ClientGUICanvasMedia.MEDIA_VIEWER_ZOOM_TYPE_CANVAS : 0.25 if rotation in ( 90, 270 ) else 0.5 }
            
        
        with mock.patch.object( container, '_SetRotation', side_effect = set_rotation ), mock.patch.object( container, 'CanRotate', return_value = True ), mock.patch.object( container, 'ZoomReinit', side_effect = lambda: calls.append( ( 'reinit', ) ) ), mock.patch.object( container, 'ResetCenterPosition', side_effect = lambda: calls.append( ( 'center', ) ) ), mock.patch.object( container, '_GetZoomWithinMaxDimension', side_effect = lambda zoom: zoom ), mock.patch.object( container, '_SetZoom', side_effect = lambda zoom: calls.append( ( 'zoom', zoom ) ) ), mock.patch.object( container, '_MoveToZoomCenter', side_effect = lambda center: calls.append( ( 'pan', center ) ) ), mock.patch.object( container, 'update' ):
            
            # it is turned first, so the zoom is relative to how it fits once it is turned
            container._ZoomToZoomTimestamp( ( 5000, 2.0, 0.25, 0.75, 90 ) )
            
            self.assertEqual( calls, [ ( 'rotate', 90 ), ( 'zoom', 0.5 ), ( 'pan', ( 0.25, 0.75 ) ) ] )
            
            # the file's own orientation is not touched
            self.assertEqual( container._file_rotation, 0 )
            self.assertEqual( container._current_zoom_timestamp, ( 5000, 2.0, 0.25, 0.75, 90 ) )
            
            # one turned the same way does not turn it again
            calls.clear()
            
            container._ZoomToZoomTimestamp( ( 6000, 1.0, None, None, 90 ) )
            
            self.assertEqual( calls, [ ( 'zoom', 0.25 ), ( 'center', ) ] )
            
            # an old one with no orientation leaves it as it is
            calls.clear()
            
            container._ZoomToZoomTimestamp( ( 7000, 1.0, None, None, None ) )
            
            self.assertEqual( calls, [ ( 'zoom', 0.25 ), ( 'center', ) ] )
            
            # back to the start, it goes back to the file's own orientation and zoom
            calls.clear()
            
            container._ZoomToZoomTimestamp( None )
            
            self.assertEqual( calls, [ ( 'rotate', 0 ), ( 'reinit', ) , ( 'center', ) ] )
            self.assertIsNone( container._current_zoom_timestamp )
            
            # and when it is already turned its own way, it is not turned again
            calls.clear()
            
            container._ZoomToZoomTimestamp( None )
            
            self.assertEqual( calls, [ ( 'reinit', ), ( 'center', ) ] )
            
        
    
    def test_reset_saved_zooms_question( self ):
        
        # with positions and position timestamps, you can reset either or both. zooms, pans, and turns go together, like a page's reset
        ( message, yes_tuples ) = ClientGUIMediaZooms.GetResetSavedZoomsQuestion( 1234, 7, 5 )

        self.assertIn( '1,234 files open at a zoom', message )
        self.assertIn( '7 files are turned', message )
        self.assertIn( '5 files have position timestamps', message )

        self.assertEqual( [ value for ( label, value ) in yes_tuples ], [ ( True, True, True ), ( True, True, False ), ( False, False, True ) ] )

        # with just one kind, that is all that is offered
        ( message, yes_tuples ) = ClientGUIMediaZooms.GetResetSavedZoomsQuestion( 3, 0, 0 )

        self.assertNotIn( 'are turned', message )
        self.assertNotIn( 'position timestamps,', message )
        self.assertEqual( [ value for ( label, value ) in yes_tuples ], [ ( True, True, False ) ] )

        # just turns are positions too
        ( message, yes_tuples ) = ClientGUIMediaZooms.GetResetSavedZoomsQuestion( 0, 2, 0 )

        self.assertIn( '2 files are turned', message )
        self.assertEqual( [ value for ( label, value ) in yes_tuples ], [ ( True, True, False ) ] )

        ( message, yes_tuples ) = ClientGUIMediaZooms.GetResetSavedZoomsQuestion( 0, 0, 3 )

        self.assertNotIn( 'open at a zoom', message )
        self.assertEqual( [ value for ( label, value ) in yes_tuples ], [ ( False, False, True ) ] )


    def test_reset_all_saved_zooms_writes( self ):

        with mock.patch( 'hydrus.client.ClientGlobals.client_controller' ) as controller:

            ClientGUIMediaZooms.ResetAllSavedZooms( True, False, clear_rotations = True )

            self.assertEqual( [ call.args for call in controller.WriteSynchronous.call_args_list ], [ ( 'clear_all_file_viewer_zooms', ), ( 'clear_all_file_viewer_rotations', ) ] )
            controller.pub.assert_called_once_with( 'reset_all_file_zooms', True, False, clear_rotations = True )
        
    

import unittest

from unittest import mock

from qtpy import QtCore as QC

from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.media import ClientGUIMediaZooms

class TestResetPositions( unittest.TestCase ):
    
    def test_reset_positions_question( self ):
        
        # with positions and position timestamps, you can keep the timestamps
        ( message, yes_tuples ) = ClientGUIMediaZooms.GetResetFileViewerPositionsQuestion( 2000, 1234, 7, 5 )
        
        self.assertIn( '2,000 files in this page', message )
        self.assertIn( '1,234 open at a zoom and pan', message )
        self.assertIn( '7 are turned', message )
        self.assertIn( '5 have position timestamps', message )
        self.assertIn( 'Other files keep theirs', message )
        
        self.assertEqual( [ value for ( label, value ) in yes_tuples ], [ ( True, True, True ), ( True, True, False ) ] )
        
        # just turned files
        ( message, yes_tuples ) = ClientGUIMediaZooms.GetResetFileViewerPositionsQuestion( 10, 0, 3, 0 )
        
        self.assertNotIn( 'open at a zoom', message )
        self.assertNotIn( 'have position timestamps', message )
        self.assertEqual( [ value for ( label, value ) in yes_tuples ], [ ( True, True, False ) ] )
        
        # just position timestamps
        ( message, yes_tuples ) = ClientGUIMediaZooms.GetResetFileViewerPositionsQuestion( 10, 0, 0, 3 )
        
        self.assertNotIn( 'are turned', message )
        self.assertEqual( [ value for ( label, value ) in yes_tuples ], [ ( False, False, True ) ] )
        
    
    def test_reset_positions_writes( self ):
        
        hash_a = b'a' * 32
        hash_b = b'b' * 32
        
        with mock.patch( 'hydrus.client.ClientGlobals.client_controller' ) as controller:
            
            ClientGUIMediaZooms.ResetFileViewerPositions( [ hash_a, hash_b, hash_a ], True, True, False )
            
            controller.WriteSynchronous.assert_called_once_with( 'reset_file_viewer_positions', { hash_a, hash_b }, True, True, False )
            controller.pub.assert_called_once_with( 'reset_file_viewer_positions', { hash_a, hash_b }, True, True, False )
            
        
    
    def _GetContainer( self, hash ):
        
        # just enough of a media container to forget what it loaded
        container = ClientGUICanvasMedia.MediaContainer.__new__( ClientGUICanvasMedia.MediaContainer )
        
        container._media = mock.Mock()
        container._media.GetHash.return_value = hash
        
        container._rotation = 90
        container._file_rotation = 90
        container._rotation_load_id = 0
        
        container._remembers_file_zooms = True
        container._saved_zoom = 2.0
        container._saved_center = ( 0.25, 0.75 )
        container._saved_zoom_load_id = 0
        container._pan_save_id = 0
        container._screen_zooms = { '' : ( 2.0, ( 0.25, 0.75 ) ), 'DISPLAY2' : ( 0.5, None ) }
        
        container._does_zoom_timestamps = True
        container._zoom_timestamps = [ ( 0, 1.0, None, None, None ) ]
        container._zoom_timestamps_load_id = 0
        container._current_zoom_timestamp = ( 0, 1.0, None, None, None )
        
        container._standby_zoom_data = None
        container._standby_zoom_data_hash = None
        container._standby_zoom_data_load_id = 0
        
        return container
        
    
    def test_media_viewer_forgets( self ):
        
        hash_a = b'a' * 32
        hash_b = b'b' * 32
        hash_c = b'c' * 32
        
        container = self._GetContainer( hash_a )
        
        calls = []
        
        def set_rotation( rotation ):
            
            calls.append( ( 'rotate', rotation ) )
            
            container._rotation = rotation
            
        
        def set_zoom_timestamps( zoom_timestamps ):
            
            calls.append( ( 'zoom timestamps', zoom_timestamps ) )
            
            container._zoom_timestamps = zoom_timestamps
            
        
        with mock.patch.object( container, '_SetRotation', side_effect = set_rotation ), mock.patch.object( container, 'CanRotate', return_value = True ), mock.patch.object( container, 'IsZoomable', return_value = True ), mock.patch.object( container, 'ZoomReinit', side_effect = lambda: calls.append( ( 'reinit', ) ) ), mock.patch.object( container, 'ResetCenterPosition', side_effect = lambda: calls.append( ( 'center', ) ) ), mock.patch.object( container, '_SetZoomTimestamps', side_effect = set_zoom_timestamps ):
            
            # another page's files do nothing, but what we looked up ahead for one of them goes
            container._standby_zoom_data_hash = hash_c
            container._standby_zoom_data = ( hash_c, None, [] )
            
            container.NotifyFileViewerPositionsReset( { hash_b, hash_c }, True, True, True )
            
            self.assertEqual( calls, [] )
            self.assertIsNone( container._standby_zoom_data )
            self.assertEqual( container._saved_zoom, 2.0 )
            
            # ours goes back to normal, but keeps its position timestamps
            container.NotifyFileViewerPositionsReset( { hash_a, hash_b }, True, True, False )
            
            self.assertEqual( calls, [ ( 'rotate', 0 ), ( 'reinit', ), ( 'center', ) ] )
            self.assertEqual( container._file_rotation, 0 )
            self.assertIsNone( container._saved_zoom )
            self.assertIsNone( container._saved_center )
            # every screen's
            self.assertEqual( container._screen_zooms, {} )
            self.assertEqual( container._rotation_load_id, 1 )
            self.assertEqual( container._saved_zoom_load_id, 1 )
            self.assertEqual( container._zoom_timestamps, [ ( 0, 1.0, None, None, None ) ] )
            
            # and then the position timestamps
            calls.clear()
            
            container.NotifyFileViewerPositionsReset( { hash_a }, False, False, True )
            
            self.assertEqual( calls, [ ( 'zoom timestamps', [] ) ] )
            self.assertIsNone( container._current_zoom_timestamp )
            
            # one that is already normal is not touched again
            calls.clear()
            
            container.NotifyFileViewerPositionsReset( { hash_a }, True, True, False )

            self.assertEqual( calls, [] )



    def test_recenter_is_remembered( self ):

        container = self._GetContainer( b'a' * 32 )

        parent = mock.Mock()
        parent.size.return_value = QC.QSize( 1000, 800 )

        with mock.patch.object( container, 'parentWidget', return_value = parent ), mock.patch.object( container, 'sizeHint', return_value = QC.QSize( 400, 200 ) ), mock.patch.object( container, 'pos', return_value = QC.QPoint( 0, 0 ) ), mock.patch.object( container, 'move' ) as move, mock.patch.object( container, '_SavePanSoon' ) as save_pan_soon:

            # when we center it ourselves, like after a zoom, nothing is saved
            container.ResetCenterPosition()

            move.assert_called_once_with( QC.QPoint( 300, 300 ) )
            save_pan_soon.assert_not_called()

            # when the user recenters it, it is saved like a drag
            container.ResetCenterPosition( user_pan = True )

            save_pan_soon.assert_called_once_with()



    def test_media_viewer_forgets_all( self ):

        container = self._GetContainer( b'a' * 32 )

        calls = []

        def set_rotation( rotation ):

            calls.append( ( 'rotate', rotation ) )

            container._rotation = rotation


        with mock.patch.object( container, '_SetRotation', side_effect = set_rotation ), mock.patch.object( container, 'CanRotate', return_value = True ), mock.patch.object( container, 'IsZoomable', return_value = True ), mock.patch.object( container, 'ZoomReinit', side_effect = lambda: calls.append( ( 'reinit', ) ) ), mock.patch.object( container, 'ResetCenterPosition', side_effect = lambda: calls.append( ( 'center', ) ) ):

            # the old way, from the Client API, leaves the turn alone
            container.NotifyAllSavedZoomsReset( False, False )

            self.assertEqual( calls, [] )
            self.assertEqual( container._file_rotation, 90 )

            # resetting every file's positions turns it back too
            container.NotifyAllSavedZoomsReset( True, False, clear_rotations = True )

            self.assertEqual( calls, [ ( 'rotate', 0 ), ( 'reinit', ), ( 'center', ) ] )
            self.assertEqual( container._file_rotation, 0 )
            self.assertIsNone( container._saved_zoom )




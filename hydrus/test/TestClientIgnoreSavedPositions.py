import unittest

from unittest import mock

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.media import ClientGUIMediaZooms

OPTION_NAME = 'media_viewer_ignore_saved_positions'

DEFAULT_ZOOM = 0.5

class TestIgnoreSavedPositions( unittest.TestCase ):
    
    def setUp( self ):
        
        CG.client_controller.new_options.SetBoolean( OPTION_NAME, False )
        
    
    def tearDown( self ):
        
        CG.client_controller.new_options.SetBoolean( OPTION_NAME, False )
        
    
    def _GetContainer( self, calls, remembers_file_zooms = True ):
        
        # just enough of a media container to zoom a file
        container = ClientGUICanvasMedia.MediaContainer.__new__( ClientGUICanvasMedia.MediaContainer )
        
        container._media = mock.Mock()
        container._media.GetHash.return_value = b'a' * 32
        container._media.GetNumFrames.return_value = 250
        
        container._canvas_type = CC.CANVAS_MEDIA_VIEWER
        container._show_action = None
        
        container._rotation = 0
        container._file_rotation = 0
        
        container._remembers_file_zooms = remembers_file_zooms
        container._saved_zoom = None
        container._saved_center = None
        container._saved_zoom_load_id = 0
        container._pan_save_id = 0
        container._pan_save_pending_id = None
        container._holding_default_zoom = False
        container._screen_zooms = {}
        container._screen_name = ''
        
        container._does_zoom_timestamps = True
        container._zoom_timestamps = []
        container._current_zoom_timestamp = None
        container._current_zoom_timestamp_needs_reapply = False
        container._zoom_timestamps_last_check_was_playing = False
        container._zoom_timestamps_stopped_at_end = False
        container._zoom_timestamps_have_checked = False
        
        container._current_zoom = DEFAULT_ZOOM
        container._current_zoom_type = ClientGUICanvasMedia.MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE
        container._zoom_types_to_zooms = { ClientGUICanvasMedia.MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE : DEFAULT_ZOOM, ClientGUICanvasMedia.MEDIA_VIEWER_ZOOM_TYPE_CANVAS : DEFAULT_ZOOM }
        
        def set_zoom( zoom ):
            
            calls.append( ( 'zoom', zoom ) )
            
            container._current_zoom = zoom
            
        
        def set_rotation( rotation ):
            
            calls.append( ( 'rotate', rotation ) )
            
            container._rotation = rotation
            
        
        patches = [
            mock.patch.object( container, 'IsZoomable', return_value = True ),
            mock.patch.object( container, 'CanRotate', return_value = True ),
            mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ),
            mock.patch.object( container, 'parentWidget' ),
            mock.patch.object( container, 'devicePixelRatio', return_value = 1.0 ),
            mock.patch.object( container, 'update' ),
            mock.patch.object( container, '_GetDefaultZoomType', return_value = ClientGUICanvasMedia.MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE ),
            mock.patch.object( container, '_GetZoomWithinMaxDimension', side_effect = lambda zoom: zoom ),
            mock.patch.object( container, '_GetPanCenterToSave', return_value = ( 0.25, 0.75 ) ),
            mock.patch.object( container, '_SetZoom', side_effect = set_zoom ),
            mock.patch.object( container, '_SetRotation', side_effect = set_rotation ),
            mock.patch.object( container, '_MoveToZoomCenter', side_effect = lambda center: calls.append( ( 'pan', center ) ) ),
            mock.patch.object( container, 'ResetCenterPosition', side_effect = lambda: calls.append( ( 'center', ) ) ),
            mock.patch.object( ClientGUICanvasMedia, 'CalculateCanvasZooms', side_effect = lambda *args, **kwargs: dict( container._zoom_types_to_zooms ) )
        ]
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
        return container
        
    
    def test_setting_it( self ):
        
        with mock.patch.object( CG.client_controller, 'pub' ) as pub:
            
            ClientGUIMediaZooms.SetIgnoreSavedPositions( True )
            
            self.assertTrue( CG.client_controller.new_options.GetBoolean( OPTION_NAME ) )
            pub.assert_called_once_with( 'media_viewer_ignore_saved_positions' )
            
            ClientGUIMediaZooms.SetIgnoreSavedPositions( False )
            
            self.assertFalse( CG.client_controller.new_options.GetBoolean( OPTION_NAME ) )
            
        
    
    def test_which_viewers( self ):
        
        CG.client_controller.new_options.SetBoolean( OPTION_NAME, True )
        
        self.assertTrue( self._GetContainer( [] )._IgnoresSavedPositions() )
        
        # the preview and the duplicate filter never had saved zooms to ignore
        self.assertFalse( self._GetContainer( [], remembers_file_zooms = False )._IgnoresSavedPositions() )
        
        CG.client_controller.new_options.SetBoolean( OPTION_NAME, False )
        
        self.assertFalse( self._GetContainer( [] )._IgnoresSavedPositions() )
        
    
    def test_saved_zoom_is_not_shown( self ):
        
        calls = []
        
        container = self._GetContainer( calls )
        
        # normally, a file's saved zoom and pan go on when they load
        container._SetLoadedSavedZoom( ( 2.0, ( 0.1, 0.2 ) ) )
        
        self.assertEqual( calls, [ ( 'zoom', 2.0 ), ( 'pan', ( 0.1, 0.2 ) ) ] )
        
        # and a resize keeps the zoom
        calls.clear()
        
        container.ZoomReinit()
        
        self.assertEqual( calls, [ ( 'zoom', 2.0 ) ] )
        
        # when ignoring, they load, but the file stays at the default zoom
        CG.client_controller.new_options.SetBoolean( OPTION_NAME, True )
        
        calls = []
        
        container = self._GetContainer( calls )
        
        container._SetLoadedSavedZoom( ( 2.0, ( 0.1, 0.2 ) ) )
        
        self.assertEqual( calls, [] )
        self.assertEqual( ( container._saved_zoom, container._saved_center ), ( 2.0, ( 0.1, 0.2 ) ) )
        
        container.ZoomReinit()
        
        self.assertEqual( calls, [ ( 'zoom', DEFAULT_ZOOM ) ] )
        self.assertFalse( container._current_zoom_timestamp_needs_reapply )
        
    
    def test_nothing_is_saved( self ):
        
        container = self._GetContainer( [] )
        
        container._saved_zoom = 2.0
        container._saved_center = ( 0.1, 0.2 )
        container._current_zoom = 3.0
        
        with mock.patch.object( CG.client_controller, 'Write' ) as write, mock.patch.object( CG.client_controller, 'CallLaterQtSafe' ) as call_later:
            
            CG.client_controller.new_options.SetBoolean( OPTION_NAME, True )
            
            container._SaveZoom()
            container._SavePanSoon()
            
            write.assert_not_called()
            call_later.assert_not_called()
            
            # what the file has is still there for later
            self.assertEqual( ( container._saved_zoom, container._saved_center ), ( 2.0, ( 0.1, 0.2 ) ) )
            
            CG.client_controller.new_options.SetBoolean( OPTION_NAME, False )
            
            container._SaveZoom()
            
            write.assert_called_once_with( 'file_viewer_zoom', b'a' * 32, 3.0, ( 0.25, 0.75 ), '' )
            
            container._SavePanSoon()
            
            call_later.assert_called_once()
            
        
    
    def test_position_timestamps_are_not_followed( self ):
        
        calls = []
        
        container = self._GetContainer( calls )
        
        container._media_window = mock.Mock()
        container._media_window.GetAnimationBarStatus.return_value = ( 50, 2000, False, None )
        
        container._zoom_timestamps = [ ( 1000, 3.0, 0.3, 0.4, None ) ]
        
        CG.client_controller.new_options.SetBoolean( OPTION_NAME, True )
        
        container._CheckZoomTimestamps()
        
        self.assertEqual( calls, [] )
        
        # they are still loaded, so they can be looked at and edited
        self.assertEqual( container._zoom_timestamps, [ ( 1000, 3.0, 0.3, 0.4, None ) ] )
        
        CG.client_controller.new_options.SetBoolean( OPTION_NAME, False )
        
        container._CheckZoomTimestamps()
        
        self.assertEqual( calls, [ ( 'zoom', 3.0 * DEFAULT_ZOOM ), ( 'pan', ( 0.3, 0.4 ) ) ] )
        
    
    def test_open_media_viewers_change( self ):
        
        calls = []
        
        container = self._GetContainer( calls )
        
        container._saved_zoom = 2.0
        container._saved_center = ( 0.1, 0.2 )
        container._current_zoom = 2.0
        
        # in a position timestamp that turned it
        container._rotation = 90
        container._current_zoom_timestamp = ( 1000, 3.0, None, None, 90 )
        
        CG.client_controller.new_options.SetBoolean( OPTION_NAME, True )
        
        container.NotifyIgnoreSavedPositionsChanged()
        
        self.assertEqual( calls, [ ( 'rotate', 0 ), ( 'zoom', DEFAULT_ZOOM ), ( 'center', ) ] )
        self.assertIsNone( container._current_zoom_timestamp )
        self.assertEqual( container._pan_save_id, 1 )
        
        # and back to what it has saved
        calls.clear()
        
        CG.client_controller.new_options.SetBoolean( OPTION_NAME, False )
        
        container.NotifyIgnoreSavedPositionsChanged()
        
        self.assertEqual( calls, [ ( 'zoom', 2.0 ), ( 'center', ), ( 'zoom', 2.0 ), ( 'pan', ( 0.1, 0.2 ) ) ] )
        self.assertTrue( container._current_zoom_timestamp_needs_reapply )
        
        # a viewer that does not remember zooms does nothing
        calls = []
        
        container = self._GetContainer( calls, remembers_file_zooms = False )
        
        container.NotifyIgnoreSavedPositionsChanged()
        
        self.assertEqual( calls, [] )


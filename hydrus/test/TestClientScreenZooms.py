import unittest

from unittest import mock

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client import ClientScreenLocations
from hydrus.client.gui import ClientGUIMediaViewerABRepeat
from hydrus.client.gui import ClientGUIMediaViewerScreens
from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.media import ClientMediaScreenZooms

IGNORE_OPTION_NAME = 'media_viewer_ignore_saved_positions'

DEFAULT_ZOOM = 0.5

HASH = b'a' * 32

class TestScreenZoomFunctions( unittest.TestCase ):
    
    def test_get_screen_zoom( self ):
        
        screen_zooms = { '' : ( 2.0, ( 0.1, 0.2 ) ), 'DISPLAY1' : ( 0.5, None ), 'DISPLAY2' : ( None, None ) }
        
        # a screen's own
        self.assertEqual( ClientMediaScreenZooms.GetScreenZoom( screen_zooms, 'DISPLAY1' ), ( 0.5, None ) )
        
        # a screen at the default zoom has that, not the one for any screen
        self.assertEqual( ClientMediaScreenZooms.GetScreenZoom( screen_zooms, 'DISPLAY2' ), ( None, None ) )
        
        # a screen without one gets the one for any screen
        self.assertEqual( ClientMediaScreenZooms.GetScreenZoom( screen_zooms, 'DISPLAY3' ), ( 2.0, ( 0.1, 0.2 ) ) )
        
        # or else the default
        self.assertEqual( ClientMediaScreenZooms.GetScreenZoom( { 'DISPLAY1' : ( 0.5, None ) }, 'DISPLAY3' ), ( None, None ) )
        self.assertEqual( ClientMediaScreenZooms.GetScreenZoom( {}, '' ), ( None, None ) )
        
    
    def test_set_screen_zoom( self ):
        
        screen_zooms = { '' : ( 2.0, None ) }
        
        ClientMediaScreenZooms.SetScreenZoom( screen_zooms, 'DISPLAY1', ( 0.5, ( 0.1, 0.2 ) ) )
        
        self.assertEqual( screen_zooms, { '' : ( 2.0, None ), 'DISPLAY1' : ( 0.5, ( 0.1, 0.2 ) ) } )
        
        # a screen at the default keeps a row of its own, like the db
        ClientMediaScreenZooms.SetScreenZoom( screen_zooms, 'DISPLAY1', ( None, None ) )
        
        self.assertEqual( screen_zooms, { '' : ( 2.0, None ), 'DISPLAY1' : ( None, None ) } )
        
        # the one for any screen at the default is gone
        ClientMediaScreenZooms.SetScreenZoom( screen_zooms, '', ( None, None ) )
        
        self.assertEqual( screen_zooms, { 'DISPLAY1' : ( None, None ) } )
        
    
    def test_pretty( self ):
        
        self.assertEqual( ClientMediaScreenZooms.ConvertScreenZoomToPretty( ( None, None ) ), 'default zoom, centered' )
        self.assertEqual( ClientMediaScreenZooms.ConvertScreenZoomToPretty( ( 2.0, ( 0.1, 0.2 ) ) ), '200% zoom, panned' )
        self.assertEqual( ClientMediaScreenZooms.ConvertScreenZoomToPretty( ( None, ( 0.1, 0.2 ) ) ), 'default zoom, panned' )
        
    
    def test_choices( self ):
        
        screen_zooms = { '' : ( 2.0, None ), 'DISPLAY2' : ( 0.5, ( 0.1, 0.2 ) ), 'DISPLAY9' : ( 3.0, None ) }
        
        choices = ClientMediaScreenZooms.GetScreenZoomChoices( [ 'DISPLAY1', 'DISPLAY2' ], 'DISPLAY1', screen_zooms )
        
        # the connected screens, in order, and then ones the file has a zoom for that are not connected now
        self.assertEqual( choices, [
            ( 'DISPLAY1 (this screen): 200% zoom, centered', 'DISPLAY1' ),
            ( 'DISPLAY2: 50% zoom, panned', 'DISPLAY2' ),
            ( 'DISPLAY9 (not connected): 300% zoom, centered', 'DISPLAY9' )
        ] )
        
        # the one for any screen is not a screen
        self.assertEqual( ClientMediaScreenZooms.GetScreenZoomChoices( [], '', { '' : ( 2.0, None ) } ), [] )
        
    
    def test_target_screen_name( self ):
        
        screens = [ ( 'DISPLAY1', 0, 0, 1920, 1080 ), ( 'DISPLAY2', 1920, 0, 2560, 1440 ) ]
        
        self.assertEqual( ClientScreenLocations.GetTargetScreenName( ( 'right', 'DISPLAY2', 0, 0, 800, 600 ), screens ), 'DISPLAY2' )
        
        # a screen that is not connected goes to the first, which is the main one
        self.assertEqual( ClientScreenLocations.GetTargetScreenName( ( 'gone', 'DISPLAY7', 0, 0, 800, 600 ), screens ), 'DISPLAY1' )
        
    

class TestMediaContainerScreenZooms( unittest.TestCase ):
    
    def setUp( self ):
        
        CG.client_controller.new_options.SetBoolean( IGNORE_OPTION_NAME, False )
        
    
    def tearDown( self ):
        
        CG.client_controller.new_options.SetBoolean( IGNORE_OPTION_NAME, False )
        
    
    def _GetContainer( self, calls, screen_name = 'DISPLAY1', remembers_file_zooms = True, has_media = True ):
        
        # just enough of a media container to zoom a file on a screen
        container = ClientGUICanvasMedia.MediaContainer.__new__( ClientGUICanvasMedia.MediaContainer )
        
        if has_media:
            
            container._media = mock.Mock()
            container._media.GetHash.return_value = HASH
            
        else:
            
            container._media = None
            
        
        container._canvas_type = CC.CANVAS_MEDIA_VIEWER
        container._show_action = None
        
        container._rotation = 0
        
        container._remembers_file_zooms = remembers_file_zooms
        container._saved_zoom = None
        container._saved_center = None
        container._saved_zoom_load_id = 0
        container._saved_zoom_from_standby = None
        container._pan_save_id = 0
        container._pan_save_pending_id = None
        container._holding_default_zoom = False
        container._screen_zooms = {}
        container._screen_name = screen_name
        
        container._standby_zoom_data = None
        
        container._current_zoom_timestamp_needs_reapply = False
        
        container._current_zoom = DEFAULT_ZOOM
        container._current_zoom_type = ClientGUICanvasMedia.MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE
        container._zoom_types_to_zooms = { ClientGUICanvasMedia.MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE : DEFAULT_ZOOM, ClientGUICanvasMedia.MEDIA_VIEWER_ZOOM_TYPE_CANVAS : DEFAULT_ZOOM }
        
        def set_zoom( zoom ):
            
            calls.append( ( 'zoom', zoom ) )
            
            container._current_zoom = zoom
            
        
        patches = [
            mock.patch.object( container, 'IsZoomable', return_value = True ),
            mock.patch.object( container, 'parentWidget' ),
            mock.patch.object( container, 'devicePixelRatio', return_value = 1.0 ),
            mock.patch.object( container, '_GetScreenName', return_value = screen_name ),
            mock.patch.object( container, '_GetDefaultZoomType', return_value = ClientGUICanvasMedia.MEDIA_VIEWER_ZOOM_TYPE_DEFAULT_FOR_FILETYPE ),
            mock.patch.object( container, '_GetZoomWithinMaxDimension', side_effect = lambda zoom: zoom ),
            mock.patch.object( container, '_GetPanCenterToSave', return_value = ( 0.25, 0.75 ) ),
            mock.patch.object( container, '_SetZoom', side_effect = set_zoom ),
            mock.patch.object( container, '_MoveToZoomCenter', side_effect = lambda center: calls.append( ( 'pan', center ) ) ),
            mock.patch.object( container, 'ResetCenterPosition', side_effect = lambda: calls.append( ( 'center', ) ) ),
            mock.patch.object( ClientGUICanvasMedia, 'CalculateCanvasZooms', side_effect = lambda *args, **kwargs: dict( container._zoom_types_to_zooms ) )
        ]
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
        return container
        
    
    def test_opens_how_it_was_on_this_screen( self ):
        
        calls = []
        
        container = self._GetContainer( calls, screen_name = 'DISPLAY2' )
        
        screen_zooms = { '' : ( 2.0, None ), 'DISPLAY2' : ( 0.25, ( 0.1, 0.2 ) ) }
        
        # looked up ahead of time, like a playlist does
        container._standby_zoom_data = ( HASH, screen_zooms, [] )
        
        container._LoadSavedZoom()
        
        self.assertEqual( container._screen_name, 'DISPLAY2' )
        self.assertEqual( container._screen_zooms, screen_zooms )
        self.assertEqual( container._saved_zoom_from_standby, ( container._saved_zoom_load_id, ( 0.25, ( 0.1, 0.2 ) ) ) )
        
        # and from the db
        calls.clear()
        
        container = self._GetContainer( calls, screen_name = 'DISPLAY3' )
        
        jobs = []
        
        with mock.patch.object( ClientGUICanvasMedia.ClientGUIAsync, 'AsyncQtJob', side_effect = lambda win, work_callable, publish_callable: jobs.append( ( work_callable, publish_callable ) ) or mock.Mock() ), mock.patch.object( CG.client_controller, 'Read', return_value = screen_zooms ) as read:
            
            container._LoadSavedZoom()
            
            ( work_callable, publish_callable ) = jobs[0]
            
            publish_callable( work_callable() )
            
            read.assert_called_once_with( 'file_viewer_screen_zooms', HASH )
            
        
        # a screen it was never zoomed on gets the one for any screen
        self.assertEqual( calls, [ ( 'zoom', 2.0 ), ( 'center', ) ] )
        self.assertEqual( ( container._saved_zoom, container._saved_center ), ( 2.0, None ) )
        
    
    def test_moving_to_another_screen( self ):
        
        calls = []
        
        container = self._GetContainer( calls )
        
        container._screen_zooms = { 'DISPLAY1' : ( 2.0, None ), 'DISPLAY2' : ( 0.25, ( 0.1, 0.2 ) ) }
        ( container._saved_zoom, container._saved_center ) = ( 2.0, None )
        
        # the same screen does nothing
        container.NotifyScreenChanged( 'DISPLAY1' )
        
        self.assertEqual( calls, [] )
        
        # another one puts the file how it was there
        container.NotifyScreenChanged( 'DISPLAY2' )
        
        self.assertEqual( container._screen_name, 'DISPLAY2' )
        self.assertEqual( calls, [ ( 'zoom', 0.25 ), ( 'pan', ( 0.1, 0.2 ) ) ] )
        self.assertEqual( ( container._saved_zoom, container._saved_center ), ( 0.25, ( 0.1, 0.2 ) ) )
        self.assertTrue( container._current_zoom_timestamp_needs_reapply )
        
        # one it was never zoomed on is the default zoom, centered
        calls.clear()
        
        container.NotifyScreenChanged( 'DISPLAY3' )
        
        self.assertEqual( calls, [ ( 'zoom', DEFAULT_ZOOM ), ( 'center', ) ] )
        self.assertEqual( ( container._saved_zoom, container._saved_center ), ( None, None ) )
        
        # with no name, we ask the window
        calls.clear()
        
        container._GetScreenName.return_value = 'DISPLAY1'
        
        container.NotifyScreenChanged()
        
        self.assertEqual( container._screen_name, 'DISPLAY1' )
        self.assertEqual( calls, [ ( 'zoom', 2.0 ), ( 'center', ) ] )
        
    
    def test_moving_after_a_screen_location( self ):
        
        calls = []
        
        container = self._GetContainer( calls )
        
        container._screen_zooms = { 'DISPLAY2' : ( 0.25, None ) }
        
        # a move to a screen location holds the default zoom, but a new screen is a fresh start there
        container._holding_default_zoom = True
        
        container.NotifyScreenChanged( 'DISPLAY2' )
        
        self.assertFalse( container._holding_default_zoom )
        self.assertEqual( calls, [ ( 'zoom', 0.25 ), ( 'center', ) ] )
        
    
    def test_a_pan_waiting_to_save_goes_to_the_screen_it_was_made_on( self ):
        
        calls = []
        
        container = self._GetContainer( calls )
        
        container._screen_zooms = { 'DISPLAY2' : ( 0.25, None ) }
        container._current_zoom = 3.0
        
        with mock.patch.object( CG.client_controller, 'Write' ) as write, mock.patch.object( CG.client_controller, 'CallLaterQtSafe' ) as call_later:
            
            container._SavePanSoon()
            
            call_later.assert_called_once()
            
            container.NotifyScreenChanged( 'DISPLAY2' )
            
            write.assert_called_once_with( 'file_viewer_zoom', HASH, 3.0, ( 0.25, 0.75 ), 'DISPLAY1' )
            
            self.assertEqual( container._screen_zooms, { 'DISPLAY1' : ( 3.0, ( 0.25, 0.75 ) ), 'DISPLAY2' : ( 0.25, None ) } )
            
            # and the one that was waiting does not save again, on this screen
            do_it = call_later.call_args[0][3]
            
            write.reset_mock()
            
            do_it()
            
            write.assert_not_called()
            
        
        self.assertEqual( ( container._saved_zoom, container._saved_center ), ( 0.25, None ) )
        
    
    def test_moving_before_the_file_is_set_up( self ):
        
        calls = []
        
        container = self._GetContainer( calls )
        
        container._screen_zooms = { 'DISPLAY1' : ( 2.0, None ), 'DISPLAY2' : ( 0.25, None ) }
        container._saved_zoom_from_standby = ( 5, ( 2.0, None ) )
        
        container.NotifyScreenChanged( 'DISPLAY2' )
        
        # it goes on with this screen's when the file's zoom is set up
        self.assertEqual( calls, [] )
        self.assertEqual( container._saved_zoom_from_standby, ( 5, ( 0.25, None ) ) )
        
    
    def test_viewers_that_do_not_remember( self ):
        
        for ( remembers_file_zooms, has_media ) in ( ( False, True ), ( True, False ) ):
            
            calls = []
            
            container = self._GetContainer( calls, remembers_file_zooms = remembers_file_zooms, has_media = has_media )
            
            container._screen_zooms = { 'DISPLAY2' : ( 0.25, None ) }
            
            container.NotifyScreenChanged( 'DISPLAY2' )
            
            # it knows where it is for next time, but nothing moves
            self.assertEqual( container._screen_name, 'DISPLAY2' )
            self.assertEqual( calls, [] )
            
        
    
    def test_ignoring_saved_zooms( self ):
        
        calls = []
        
        container = self._GetContainer( calls )
        
        container._screen_zooms = { 'DISPLAY2' : ( 0.25, None ) }
        
        CG.client_controller.new_options.SetBoolean( IGNORE_OPTION_NAME, True )
        
        with mock.patch.object( CG.client_controller, 'Write' ) as write:
            
            container.NotifyScreenChanged( 'DISPLAY2' )
            
            container.ApplyScreenZoom( 'DISPLAY1' )
            
            self.assertEqual( calls, [] )
            write.assert_not_called()
            
        
    
    def test_saving_is_for_this_screen( self ):
        
        calls = []
        
        container = self._GetContainer( calls, screen_name = 'DISPLAY2' )
        
        container._screen_zooms = { '' : ( 2.0, None ), 'DISPLAY1' : ( 0.25, None ) }
        container._current_zoom = 3.0
        
        with mock.patch.object( CG.client_controller, 'Write' ) as write:
            
            container._SaveZoom()
            
            write.assert_called_once_with( 'file_viewer_zoom', HASH, 3.0, ( 0.25, 0.75 ), 'DISPLAY2' )
            
            self.assertEqual( container._screen_zooms, { '' : ( 2.0, None ), 'DISPLAY1' : ( 0.25, None ), 'DISPLAY2' : ( 3.0, ( 0.25, 0.75 ) ) } )
            
            # forgetting it is just for this screen too, which then stays at the default zoom, whatever there is for any screen
            write.reset_mock()
            
            container.ForgetSavedZoom()
            
            write.assert_called_once_with( 'file_viewer_zoom', HASH, None, None, 'DISPLAY2' )
            
            self.assertEqual( container._screen_zooms, { '' : ( 2.0, None ), 'DISPLAY1' : ( 0.25, None ), 'DISPLAY2' : ( None, None ) } )
            self.assertEqual( ( container._saved_zoom, container._saved_center ), ( None, None ) )
            
        
    
    def test_zoom_and_pan_as_on_another_screen( self ):
        
        calls = []
        
        container = self._GetContainer( calls, screen_name = 'DISPLAY2' )
        
        container._screen_zooms = { '' : ( 2.0, None ), 'DISPLAY1' : ( 0.25, ( 0.1, 0.2 ) ) }
        container._holding_default_zoom = True
        
        with mock.patch.object( CG.client_controller, 'Write' ) as write:
            
            container.ApplyScreenZoom( 'DISPLAY1' )
            
            # it goes like that, and is saved like that for this screen
            self.assertEqual( calls, [ ( 'zoom', 0.25 ), ( 'pan', ( 0.1, 0.2 ) ) ] )
            write.assert_called_once_with( 'file_viewer_zoom', HASH, 0.25, ( 0.1, 0.2 ), 'DISPLAY2' )
            
            self.assertFalse( container._holding_default_zoom )
            self.assertEqual( container._screen_zooms[ 'DISPLAY2' ], ( 0.25, ( 0.1, 0.2 ) ) )
            self.assertEqual( container._pan_save_id, 1 )
            
            # a screen it has nothing for is the one for any screen
            calls.clear()
            write.reset_mock()
            
            container.ApplyScreenZoom( 'DISPLAY3' )
            
            self.assertEqual( calls, [ ( 'zoom', 2.0 ), ( 'center', ) ] )
            write.assert_called_once_with( 'file_viewer_zoom', HASH, 2.0, None, 'DISPLAY2' )
            
        
        # a viewer that does not remember zooms does nothing
        calls = []
        
        container = self._GetContainer( calls, remembers_file_zooms = False )
        
        container._screen_zooms = { 'DISPLAY2' : ( 0.25, None ) }
        
        with mock.patch.object( CG.client_controller, 'Write' ) as write:
            
            container.ApplyScreenZoom( 'DISPLAY2' )
            
            write.assert_not_called()
            
        
        self.assertEqual( calls, [] )
        
    

class TestOpenMediaViewerScreens( unittest.TestCase ):
    
    def _GetCanvas( self, canvas_key, screen_name ):
        
        canvas = mock.Mock()
        
        canvas.GetCanvasKey.return_value = canvas_key
        canvas.GetScreenAPIInfo.return_value = { 'canvas_key' : canvas_key.hex(), 'screen_name' : screen_name, 'hash' : None }
        
        return canvas
        
    
    def test_apply( self ):
        
        canvas_1 = self._GetCanvas( b'\x01' * 32, 'DISPLAY1' )
        canvas_2 = self._GetCanvas( b'\x02' * 32, 'DISPLAY2' )
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = [ canvas_1, canvas_2 ] ):
            
            self.assertEqual( ClientGUIMediaViewerScreens.ApplyOpenMediaViewersScreenZoom( 'DISPLAY2' ), 2 )
            
            canvas_1.ApplyScreenZoom.assert_called_once_with( 'DISPLAY2' )
            canvas_2.ApplyScreenZoom.assert_called_once_with( 'DISPLAY2' )
            
            self.assertEqual( ClientGUIMediaViewerScreens.ApplyOpenMediaViewersScreenZoom( 'DISPLAY1', canvas_key = b'\x02' * 32 ), 1 )
            
            canvas_2.ApplyScreenZoom.assert_called_with( 'DISPLAY1' )
            self.assertEqual( canvas_1.ApplyScreenZoom.call_count, 1 )
            
            self.assertEqual( ClientGUIMediaViewerScreens.ApplyOpenMediaViewersScreenZoom( 'DISPLAY1', canvas_key = b'\x03' * 32 ), 0 )
            
        
    
    def test_info( self ):
        
        canvas_1 = self._GetCanvas( b'\x01' * 32, 'DISPLAY2' )
        
        screens = [ ( 'DISPLAY1', 0, 0, 1920, 1080 ), ( 'DISPLAY2', 1920, 0, 2560, 1440 ) ]
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = [ canvas_1 ] ), mock.patch.object( ClientGUIMediaViewerScreens.ClientGUIScreenLocations, 'GetCurrentScreenGeometries', return_value = screens ):
            
            info = ClientGUIMediaViewerScreens.GetScreensAPIInfo()
            
        
        self.assertEqual( info, {
            'screens' : [
                { 'screen_name' : 'DISPLAY1', 'x' : 0, 'y' : 0, 'width' : 1920, 'height' : 1080, 'primary' : True },
                { 'screen_name' : 'DISPLAY2', 'x' : 1920, 'y' : 0, 'width' : 2560, 'height' : 1440, 'primary' : False }
            ],
            'media_viewers' : [ { 'canvas_key' : ( b'\x01' * 32 ).hex(), 'screen_name' : 'DISPLAY2', 'hash' : None } ]
        } )
        
        

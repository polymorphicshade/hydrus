import unittest

from unittest import mock

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIMediaViewerABRepeat
from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.media import ClientMediaABLoops

HASH = b'a' * 32
OTHER_HASH = b'b' * 32

class TestABLoopFunctions( unittest.TestCase ):
    
    def test_from_ab_repeat( self ):
        
        self.assertEqual( ClientMediaABLoops.ConvertABRepeatToABLoop( 5250, 12000 ), ( 5250, 12000 ) )
        
        # no A loops from the start
        self.assertEqual( ClientMediaABLoops.ConvertABRepeatToABLoop( None, 12000 ), ( 0, 12000 ) )
        
        # no B is not looping yet
        self.assertIsNone( ClientMediaABLoops.ConvertABRepeatToABLoop( 5250, None ) )
        self.assertIsNone( ClientMediaABLoops.ConvertABRepeatToABLoop( None, None ) )
        
        # too short
        self.assertIsNone( ClientMediaABLoops.ConvertABRepeatToABLoop( 1000, 1050 ) )
        
    
    def test_valid( self ):
        
        self.assertTrue( ClientMediaABLoops.ABLoopIsValid( ( 0, ClientMediaABLoops.MIN_AB_LOOP_DURATION_MS ) ) )
        self.assertFalse( ClientMediaABLoops.ABLoopIsValid( ( 0, ClientMediaABLoops.MIN_AB_LOOP_DURATION_MS - 1 ) ) )
        self.assertFalse( ClientMediaABLoops.ABLoopIsValid( ( 5000, 1000 ) ) )
        self.assertFalse( ClientMediaABLoops.ABLoopIsValid( ( -100, 1000 ) ) )
        
        # the media viewer uses the same minimum
        self.assertEqual( ClientGUICanvasMedia.MIN_AB_LOOP_DURATION_MS, ClientMediaABLoops.MIN_AB_LOOP_DURATION_MS )
        
    
    def test_list( self ):
        
        ab_loops = ClientMediaABLoops.AddABLoop( [ ( 9000, 12000 ) ], ( 1000, 4500 ) )
        
        self.assertEqual( ab_loops, [ ( 1000, 4500 ), ( 9000, 12000 ) ] )
        
        # the same one is only saved once
        self.assertEqual( ClientMediaABLoops.AddABLoop( ab_loops, ( 1000, 4500 ) ), ab_loops )
        
        # the db gives back lists, sometimes
        self.assertEqual( ClientMediaABLoops.NormaliseABLoops( [ [ 9000, 12000 ], ( 1000, 4500 ), ( 9000, 12000 ) ] ), [ ( 1000, 4500 ), ( 9000, 12000 ) ] )
        
        self.assertEqual( ClientMediaABLoops.RemoveABLoop( ab_loops, ( 9000, 12000 ) ), [ ( 1000, 4500 ) ] )
        self.assertEqual( ClientMediaABLoops.RemoveABLoop( ab_loops, ( 1, 2 ) ), ab_loops )
        
    
    def test_pretty( self ):
        
        self.assertEqual( ClientGUICanvasMedia.ConvertABLoopToPrettyString( ( 5250, 72000 ) ), '0:05.250 - 1:12.000' )
        
    

class TestMediaContainerABLoops( unittest.TestCase ):
    
    def test_set_points( self ):
        
        container = ClientGUICanvasMedia.MediaContainer.__new__( ClientGUICanvasMedia.MediaContainer )
        
        container._media = mock.Mock()
        
        calls = []
        
        with mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ), mock.patch.object( container, '_SetABLoop', side_effect = lambda a_ms, b_ms: calls.append( ( 'loop', a_ms, b_ms ) ) ), mock.patch.object( container, 'SeekTo', side_effect = lambda timestamp_ms: calls.append( ( 'seek', timestamp_ms ) ) ):
            
            # a loop goes on, and plays from its start
            container.SetABLoopPoints( 5250, 12000 )
            
            self.assertEqual( calls, [ ( 'loop', 5250, 12000 ), ( 'seek', 5250 ) ] )
            
            # from the start of the file
            calls.clear()
            
            container.SetABLoopPoints( None, 12000 )
            
            self.assertEqual( calls, [ ( 'loop', None, 12000 ), ( 'seek', 0 ) ] )
            
            # just an A, or clearing, does not move playback
            calls.clear()
            
            container.SetABLoopPoints( 5250, None )
            container.SetABLoopPoints( None, None )
            
            self.assertEqual( calls, [ ( 'loop', 5250, None ), ( 'loop', None, None ) ] )
            
        
        # nothing to loop
        calls.clear()
        
        with mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = False ), mock.patch.object( container, '_SetABLoop', side_effect = lambda a_ms, b_ms: calls.append( ( 'loop', a_ms, b_ms ) ) ):
            
            container.SetABLoopPoints( 5250, 12000 )
            
        
        self.assertEqual( calls, [] )
        
    

class TestCanvasABLoops( unittest.TestCase ):
    
    def _GetCanvas( self, ab_repeat = ( None, None ) ):
        
        canvas = ClientGUICanvas.CanvasMediaListBrowser.__new__( ClientGUICanvas.CanvasMediaListBrowser )
        
        canvas._current_media = mock.Mock()
        canvas._current_media.GetHash.return_value = HASH
        
        canvas._media_container = mock.Mock()
        canvas._media_container.GetABLoop.return_value = ab_repeat
        
        return canvas
        
    
    def test_save_current( self ):
        
        canvas = self._GetCanvas( ab_repeat = ( None, 4500 ) )
        
        with mock.patch.object( CG.client_controller, 'Read', return_value = [ ( 9000, 12000 ) ] ) as read, mock.patch.object( CG.client_controller, 'Write' ) as write:
            
            canvas._SaveCurrentABLoop()
            
            read.assert_called_once_with( 'file_ab_loops', HASH )
            
            # no A is from the start, and they stay in order
            write.assert_called_once_with( 'file_ab_loops', HASH, [ ( 0, 4500 ), ( 9000, 12000 ) ] )
            
        
    
    def test_save_with_no_loop( self ):
        
        canvas = self._GetCanvas( ab_repeat = ( 5250, None ) )
        
        with mock.patch.object( CG.client_controller, 'Write' ) as write, mock.patch.object( ClientGUICanvas.ClientGUIDialogsMessage, 'ShowWarning' ) as show_warning:
            
            canvas._SaveCurrentABLoop()
            
            # it says how to mark one, and saves nothing
            show_warning.assert_called_once()
            write.assert_not_called()
            
        
    
    def test_apply( self ):
        
        canvas = self._GetCanvas()
        
        canvas._ApplyABLoop( HASH, ( 5250, 12000 ) )
        
        canvas._media_container.SetABLoopPoints.assert_called_once_with( 5250, 12000 )
        
        # the menu was for another file, and a slideshow moved us on
        canvas._ApplyABLoop( OTHER_HASH, ( 0, 1000 ) )
        
        self.assertEqual( canvas._media_container.SetABLoopPoints.call_count, 1 )
        
        # and the api's way in
        canvas.SetABRepeat( None, 3000 )
        
        canvas._media_container.SetABLoopPoints.assert_called_with( None, 3000 )
        
    
    def test_remove( self ):
        
        canvas = self._GetCanvas()
        
        with mock.patch.object( CG.client_controller, 'Read', return_value = [ ( 1000, 4500 ), ( 9000, 12000 ) ] ), mock.patch.object( CG.client_controller, 'Write' ) as write:
            
            canvas._RemoveABLoop( HASH, ( 1000, 4500 ) )
            
            write.assert_called_once_with( 'file_ab_loops', HASH, [ ( 9000, 12000 ) ] )
            
        
    
    def test_menu( self ):
        
        canvas = self._GetCanvas( ab_repeat = ( 9000, 12000 ) )
        
        items = []
        submenus = []
        
        def append_menu_item( menu, label, description, callable, *args, **kwargs ):
            
            items.append( ( menu, label, callable, args ) )
            
        
        def append_menu_check_item( menu, label, description, initial_value, callable, *args, **kwargs ):
            
            items.append( ( menu, label, callable, args, initial_value ) )
            
        
        def generate_menu( parent ):
            
            return mock.Mock( name = f'menu {len( submenus )}' )
            
        
        def append_menu( menu, submenu, label ):
            
            submenus.append( ( menu, submenu, label ) )
            
        
        menus = ClientGUICanvas.ClientGUIMenus
        
        with mock.patch.object( CG.client_controller, 'Read', return_value = [ ( 1000, 4500 ), ( 9000, 12000 ) ] ), mock.patch.object( menus, 'AppendMenuItem', side_effect = append_menu_item ), mock.patch.object( menus, 'AppendMenuCheckItem', side_effect = append_menu_check_item ), mock.patch.object( menus, 'GenerateMenu', side_effect = generate_menu ), mock.patch.object( menus, 'AppendMenu', side_effect = append_menu ), mock.patch.object( menus, 'AppendSeparator' ):
            
            top_menu = mock.Mock()
            
            canvas._AppendABLoopsMenu( top_menu )
            
        
        labels = [ item[1] for item in items ]
        
        self.assertEqual( labels, [ 'save current A-B', '0:01.000 - 0:04.500', '0:09.000 - 0:12.000', '0:01.000 - 0:04.500', '0:09.000 - 0:12.000', 'clear' ] )
        
        # the saved ones put the loop on, and the one that is on now is ticked
        ( menu, label, callable, args, initial_value ) = items[1]
        
        self.assertEqual( callable, canvas._ApplyABLoop )
        self.assertEqual( args, ( HASH, ( 1000, 4500 ) ) )
        self.assertFalse( initial_value )
        self.assertTrue( items[2][4] )
        
        # then the remove submenu, and clear
        self.assertEqual( items[3][2], canvas._RemoveABLoop )
        self.assertEqual( items[5][2:4], ( canvas._SaveABLoops, ( HASH, [] ) ) )
        
        self.assertEqual( [ label for ( menu, submenu, label ) in submenus ], [ 'remove', 'A-B (2)' ] )
        self.assertIs( submenus[-1][0], top_menu )
        
        # with none saved, it is just the save
        items.clear()
        submenus.clear()
        
        with mock.patch.object( CG.client_controller, 'Read', return_value = [] ), mock.patch.object( menus, 'AppendMenuItem', side_effect = append_menu_item ), mock.patch.object( menus, 'GenerateMenu', side_effect = generate_menu ), mock.patch.object( menus, 'AppendMenu', side_effect = append_menu ):
            
            canvas._AppendABLoopsMenu( mock.Mock() )
            
        
        self.assertEqual( [ item[1] for item in items ], [ 'save current A-B' ] )
        self.assertEqual( [ label for ( menu, submenu, label ) in submenus ], [ 'A-B' ] )
        
    

class TestOpenMediaViewersABRepeat( unittest.TestCase ):
    
    def test_set( self ):
        
        canvas_1 = mock.Mock()
        canvas_1.GetCanvasKey.return_value = b'\x01' * 32
        
        canvas_2 = mock.Mock()
        canvas_2.GetCanvasKey.return_value = b'\x02' * 32
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = [ canvas_1, canvas_2 ] ):
            
            self.assertEqual( ClientGUIMediaViewerABRepeat.SetOpenMediaViewersABRepeat( 1000, 4500 ), 2 )
            
            canvas_1.SetABRepeat.assert_called_once_with( 1000, 4500 )
            canvas_2.SetABRepeat.assert_called_once_with( 1000, 4500 )
            
            self.assertEqual( ClientGUIMediaViewerABRepeat.SetOpenMediaViewersABRepeat( None, None, canvas_key = b'\x02' * 32 ), 1 )
            
            canvas_2.SetABRepeat.assert_called_with( None, None )
            self.assertEqual( canvas_1.SetABRepeat.call_count, 1 )
            
            self.assertEqual( ClientGUIMediaViewerABRepeat.SetOpenMediaViewersABRepeat( 0, 1000, canvas_key = b'\x03' * 32 ), 0 )
            
            
            

import unittest

from unittest import mock

from hydrus.client import ClientApplicationCommand as CAC
from hydrus.client import ClientDefaults
from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIMediaViewerABRepeat
from hydrus.client.gui import ClientGUIMediaViewerText
from hydrus.client.gui import ClientGUIShortcuts
from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.gui.canvas import ClientGUICanvasHoverFrames

CTRL_F10 = ClientGUIShortcuts.Shortcut( ClientGUIShortcuts.SHORTCUT_TYPE_KEYBOARD_SPECIAL, ClientGUIShortcuts.SHORTCUT_KEY_SPECIAL_F10, ClientGUIShortcuts.SHORTCUT_PRESS_TYPE_PRESS, [ ClientGUIShortcuts.SHORTCUT_MODIFIER_CTRL ] )

class TestMediaViewerTextShortcut( unittest.TestCase ):
    
    def test_default( self ):
        
        # a new client has it
        ( media_viewer, ) = [ shortcut_set for shortcut_set in ClientDefaults.GetDefaultShortcuts() if shortcut_set.GetName() == 'media_viewer' ]
        
        self.assertEqual( media_viewer.GetCommand( CTRL_F10 ), CAC.ApplicationCommand.STATICCreateSimpleCommand( CAC.SIMPLE_MEDIA_VIEWER_FLIP_TEXT ) )
        
        self.assertIn( CAC.SIMPLE_MEDIA_VIEWER_FLIP_TEXT, ClientGUIShortcuts.SHORTCUTS_MEDIA_VIEWER_ACTIONS )
        self.assertIn( CAC.SIMPLE_MEDIA_VIEWER_FLIP_TEXT, CAC.simple_enum_to_str_lookup )
        self.assertEqual( ClientGUIMediaViewerText.GetDefaultFlipTextShortcut(), CTRL_F10 )
        
    
    def test_adding_it_to_an_existing_client( self ):
        
        media_viewer = ClientGUIShortcuts.ShortcutSet( 'media_viewer' )
        other = ClientGUIShortcuts.ShortcutSet( 'global' )
        
        self.assertIs( ClientGUIMediaViewerText.AddDefaultFlipTextShortcut( [ other, media_viewer ] ), media_viewer )
        
        self.assertEqual( media_viewer.GetCommand( CTRL_F10 ), ClientGUIMediaViewerText.GetFlipTextCommand() )
        self.assertIsNone( other.GetCommand( CTRL_F10 ) )
        
        # it has it already
        self.assertIsNone( ClientGUIMediaViewerText.AddDefaultFlipTextShortcut( [ media_viewer ] ) )
        
        # the user has it on another key
        media_viewer = ClientGUIShortcuts.ShortcutSet( 'media_viewer' )
        
        media_viewer.SetCommand( ClientGUIShortcuts.Shortcut( ClientGUIShortcuts.SHORTCUT_TYPE_KEYBOARD_CHARACTER, ord( 'T' ), ClientGUIShortcuts.SHORTCUT_PRESS_TYPE_PRESS, [] ), ClientGUIMediaViewerText.GetFlipTextCommand() )
        
        self.assertIsNone( ClientGUIMediaViewerText.AddDefaultFlipTextShortcut( [ media_viewer ] ) )
        self.assertIsNone( media_viewer.GetCommand( CTRL_F10 ) )
        
        # the user has something else on ctrl+f10
        media_viewer = ClientGUIShortcuts.ShortcutSet( 'media_viewer' )
        
        something_else = CAC.ApplicationCommand.STATICCreateSimpleCommand( CAC.SIMPLE_CLOSE_MEDIA_VIEWER )
        
        media_viewer.SetCommand( CTRL_F10, something_else )
        
        self.assertIsNone( ClientGUIMediaViewerText.AddDefaultFlipTextShortcut( [ media_viewer ] ) )
        self.assertEqual( media_viewer.GetCommand( CTRL_F10 ), something_else )
        
        # no media viewer set at all
        self.assertIsNone( ClientGUIMediaViewerText.AddDefaultFlipTextShortcut( [ other ] ) )
        
    
    def test_once( self ):
        
        new_options = CG.client_controller.new_options
        
        original_value = new_options.GetBoolean( ClientGUIMediaViewerText.FLIP_TEXT_SHORTCUT_ADDED_OPTION )
        
        self.addCleanup( new_options.SetBoolean, ClientGUIMediaViewerText.FLIP_TEXT_SHORTCUT_ADDED_OPTION, original_value )
        
        new_options.SetBoolean( ClientGUIMediaViewerText.FLIP_TEXT_SHORTCUT_ADDED_OPTION, False )
        
        media_viewer = ClientGUIShortcuts.ShortcutSet( 'media_viewer' )
        
        with mock.patch.object( CG.client_controller, 'Write' ) as write:
            
            ClientGUIMediaViewerText.AddDefaultFlipTextShortcutOnce( [ media_viewer ] )
            
            # the set is saved, and so is that it was done
            self.assertEqual( write.call_args_list, [ mock.call( 'serialisable', media_viewer ), mock.call( 'serialisable', new_options ) ] )
            self.assertTrue( new_options.GetBoolean( ClientGUIMediaViewerText.FLIP_TEXT_SHORTCUT_ADDED_OPTION ) )
            
            # the user took it out, so it stays out
            media_viewer = ClientGUIShortcuts.ShortcutSet( 'media_viewer' )
            
            write.reset_mock()
            
            ClientGUIMediaViewerText.AddDefaultFlipTextShortcutOnce( [ media_viewer ] )
            
            write.assert_not_called()
            self.assertIsNone( media_viewer.GetCommand( CTRL_F10 ) )
            
        
    

class TestMediaViewerTextHiding( unittest.TestCase ):
    
    def _GetCanvas( self ):
        
        canvas = ClientGUICanvas.CanvasWithHovers.__new__( ClientGUICanvas.CanvasWithHovers )
        
        canvas._text_hidden = False
        canvas._current_media = mock.Mock()
        canvas._hovers = [ mock.Mock(), mock.Mock() ]
        
        patch = mock.patch.object( canvas, 'update' )
        
        patch.start()
        
        self.addCleanup( patch.stop )
        
        return canvas
        
    
    def test_flipping( self ):
        
        canvas = self._GetCanvas()
        
        self.assertFalse( canvas.IsHidingText() )
        
        canvas.FlipTextHidden()
        
        self.assertTrue( canvas.IsHidingText() )
        
        # the hovers go straight away
        for hover in canvas._hovers:
            
            hover.DoRegularHideShow.assert_called_once_with()
            
        
        canvas.update.assert_called()
        
        # and the shortcut
        canvas.ProcessApplicationCommand( ClientGUIMediaViewerText.GetFlipTextCommand() )
        
        self.assertFalse( canvas.IsHidingText() )
        
        canvas.SetTextHidden( True )
        canvas.SetTextHidden( True )
        
        self.assertTrue( canvas.IsHidingText() )
        
    
    def test_background_text( self ):
        
        canvas = self._GetCanvas()
        
        canvas._text_hidden = True
        
        names = [ '_DrawTags', '_DrawTopMiddle', '_DrawTopRight', '_DrawNotes', '_DrawIndexAndZoom' ]
        
        patches = [ mock.patch.object( canvas, name, return_value = 0 ) for name in names ]
        patches.append( mock.patch.object( canvas, 'size' ) )
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
        canvas._DrawBackgroundDetails( mock.Mock() )
        
        for name in names:
            
            getattr( canvas, name ).assert_not_called()
            
        
        # shown again, it draws what the options say
        canvas._text_hidden = False
        
        with mock.patch.object( CG.client_controller.new_options, 'GetBoolean', return_value = True ):
            
            canvas._DrawBackgroundDetails( mock.Mock() )
            
        
        for name in names:
            
            getattr( canvas, name ).assert_called_once()
            
        
    
    def test_hovers( self ):
        
        self.assertTrue( ClientGUICanvasHoverFrames.CanvasHoverFrameTags.HIDES_WITH_MEDIA_VIEWER_TEXT )
        self.assertTrue( ClientGUICanvasHoverFrames.CanvasHoverFrameRightNotes.HIDES_WITH_MEDIA_VIEWER_TEXT )
        self.assertTrue( ClientGUICanvasHoverFrames.CanvasHoverFrameTopRight.HIDES_WITH_MEDIA_VIEWER_TEXT )
        
        # the top hover's buttons stay
        self.assertFalse( ClientGUICanvasHoverFrames.CanvasHoverFrameTop.HIDES_WITH_MEDIA_VIEWER_TEXT )
        
        hover = ClientGUICanvasHoverFrames.CanvasHoverFrameTags.__new__( ClientGUICanvasHoverFrames.CanvasHoverFrameTags )
        
        hover._my_canvas = mock.Mock()
        hover._my_canvas.IsHidingText.return_value = True
        
        with mock.patch.object( hover, 'parentWidget' ), mock.patch.object( hover, '_LowerHover' ) as lower_hover, mock.patch.object( hover, '_RaiseHover' ) as raise_hover, mock.patch.object( hover, '_IsAlwaysShown', return_value = True ):
            
            hover.DoRegularHideShow()
            
            # even one that is always shown
            lower_hover.assert_called_once_with()
            raise_hover.assert_not_called()
            
        
    
    def test_open_media_viewers( self ):
        
        ( canvas_1, canvas_2 ) = ( mock.Mock(), mock.Mock() )
        
        canvas_1.GetCanvasKey.return_value = b'\x01' * 32
        canvas_2.GetCanvasKey.return_value = b'\x02' * 32
        
        canvas_1.IsHidingText.return_value = True
        canvas_2.IsHidingText.return_value = False
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = [ canvas_1, canvas_2 ] ):
            
            self.assertEqual( ClientGUIMediaViewerText.GetOpenMediaViewersTextHidden(), [ { 'canvas_key' : ( b'\x01' * 32 ).hex(), 'text_hidden' : True }, { 'canvas_key' : ( b'\x02' * 32 ).hex(), 'text_hidden' : False } ] )
            
            self.assertEqual( ClientGUIMediaViewerText.SetOpenMediaViewersTextHidden( True ), 2 )
            self.assertEqual( ClientGUIMediaViewerText.SetOpenMediaViewersTextHidden( False, canvas_key = b'\x02' * 32 ), 1 )
            self.assertEqual( ClientGUIMediaViewerText.SetOpenMediaViewersTextHidden( False, canvas_key = b'\x03' * 32 ), 0 )
            
        
        canvas_1.SetTextHidden.assert_called_once_with( True )
        self.assertEqual( canvas_2.SetTextHidden.call_args_list, [ mock.call( True ), mock.call( False ) ] )
        
        
        

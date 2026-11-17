import unittest

from unittest import mock

from qtpy import QtGui as QG

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIMediaViewerABRepeat
from hydrus.client.gui import ClientGUIMediaViewerHighlight
from hydrus.client.gui.canvas import ClientGUICanvas

BOOLEAN_NAME = 'highlight_last_opened_media_viewer'
STRING_NAME = 'last_opened_media_viewer_highlight_colour'

NORMAL_COLOUR = QG.QColor( 52, 52, 52 )

class TestMediaViewerHighlight( unittest.TestCase ):
    
    def setUp( self ):
        
        new_options = CG.client_controller.new_options
        
        self._original_values = ( new_options.GetBoolean( BOOLEAN_NAME ), new_options.GetString( STRING_NAME ) )
        
        new_options.SetBoolean( BOOLEAN_NAME, False )
        new_options.SetString( STRING_NAME, '#FF00FF' )
        
    
    def tearDown( self ):
        
        new_options = CG.client_controller.new_options
        
        ( highlight_is_on, colour ) = self._original_values
        
        new_options.SetBoolean( BOOLEAN_NAME, highlight_is_on )
        new_options.SetString( STRING_NAME, colour )
        
    
    def _GetCanvas( self ):
        
        canvas = mock.Mock()
        
        canvas.GetColour.return_value = QG.QColor( NORMAL_COLOUR )
        
        return canvas
        
    
    def _PatchOpenCanvases( self, canvases ):
        
        patch = mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = canvases )
        
        patch.start()
        
        self.addCleanup( patch.stop )
        
    
    def test_defaults( self ):
        
        # off, and magenta, to start with
        from hydrus.client import ClientOptions
        
        new_options = ClientOptions.ClientOptions()
        
        self.assertFalse( new_options.GetBoolean( BOOLEAN_NAME ) )
        self.assertEqual( new_options.GetString( STRING_NAME ), '#FF00FF' )
        
    
    def test_colours( self ):
        
        for ( colour, expected ) in ( ( '#ff00ff', '#FF00FF' ), ( 'ff00ff', '#FF00FF' ), ( ' #12abEF ', '#12ABEF' ) ):
            
            self.assertEqual( ClientGUIMediaViewerHighlight.NormaliseHighlightColour( colour ), expected, colour )
            
        
        for colour in ( '', '#ff00f', '#ff00ff00', 'magenta', '#gg00ff', None, 5 ):
            
            self.assertIsNone( ClientGUIMediaViewerHighlight.NormaliseHighlightColour( colour ), colour )
            
        
        self.assertEqual( ClientGUIMediaViewerHighlight.ConvertQColourToHighlightColour( QG.QColor( 255, 0, 255 ) ), '#FF00FF' )
        self.assertEqual( ClientGUIMediaViewerHighlight.ConvertQColourToHighlightColour( QG.QColor( 1, 2, 3 ) ), '#010203' )
        
        # a broken option is magenta
        CG.client_controller.new_options.SetString( STRING_NAME, 'not a colour' )
        
        self.assertEqual( ClientGUIMediaViewerHighlight.GetHighlightColour(), '#FF00FF' )
        
        CG.client_controller.new_options.SetString( STRING_NAME, '#00ff00' )
        
        self.assertEqual( ClientGUIMediaViewerHighlight.GetHighlightColour(), '#00FF00' )
        self.assertEqual( ClientGUIMediaViewerHighlight.GetHighlightQColour(), QG.QColor( 0, 255, 0 ) )
        
    
    def test_which_one_is_highlighted( self ):
        
        ( first, second, third ) = ( self._GetCanvas(), self._GetCanvas(), self._GetCanvas() )
        
        self._PatchOpenCanvases( [ first, second, third ] )
        
        # off
        for canvas in ( first, second, third ):
            
            self.assertFalse( ClientGUIMediaViewerHighlight.CanvasIsHighlighted( canvas ) )
            
        
        CG.client_controller.new_options.SetBoolean( BOOLEAN_NAME, True )
        
        # just the one opened last
        self.assertFalse( ClientGUIMediaViewerHighlight.CanvasIsHighlighted( first ) )
        self.assertFalse( ClientGUIMediaViewerHighlight.CanvasIsHighlighted( second ) )
        self.assertTrue( ClientGUIMediaViewerHighlight.CanvasIsHighlighted( third ) )
        
        # the preview, or anything that is not a media viewer
        self.assertFalse( ClientGUIMediaViewerHighlight.CanvasIsHighlighted( self._GetCanvas() ) )
        self.assertFalse( ClientGUIMediaViewerHighlight.CanvasIsHighlighted( None ) )
        
    
    def test_closing_moves_it_back( self ):
        
        ( first, second ) = ( self._GetCanvas(), self._GetCanvas() )
        
        CG.client_controller.new_options.SetBoolean( BOOLEAN_NAME, True )
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = [ first, second ] ):
            
            self.assertIs( ClientGUIMediaViewerHighlight.GetLastOpenedMediaViewerCanvas(), second )
            
        
        # the second closes
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = [ first ] ):
            
            self.assertIs( ClientGUIMediaViewerHighlight.GetLastOpenedMediaViewerCanvas(), first )
            self.assertTrue( ClientGUIMediaViewerHighlight.CanvasIsHighlighted( first ) )
            
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = [] ):
            
            self.assertIsNone( ClientGUIMediaViewerHighlight.GetLastOpenedMediaViewerCanvas() )
            
        
    
    def test_background_colour( self ):
        
        ( first, second ) = ( self._GetCanvas(), self._GetCanvas() )
        
        self._PatchOpenCanvases( [ first, second ] )
        
        first_generator = ClientGUICanvas.CanvasBackgroundColourGenerator( first )
        second_generator = ClientGUICanvas.CanvasBackgroundColourGenerator( second )
        
        # off, they are both the normal colour
        self.assertEqual( first_generator.GetColour(), NORMAL_COLOUR )
        self.assertEqual( second_generator.GetColour(), NORMAL_COLOUR )
        
        CG.client_controller.new_options.SetBoolean( BOOLEAN_NAME, True )
        
        self.assertEqual( first_generator.GetColour(), NORMAL_COLOUR )
        self.assertEqual( second_generator.GetColour(), QG.QColor( 255, 0, 255 ) )
        
        CG.client_controller.new_options.SetString( STRING_NAME, '#123456' )
        
        self.assertEqual( second_generator.GetColour(), QG.QColor( 0x12, 0x34, 0x56 ) )
        
    
    def test_setting_it( self ):
        
        new_options = CG.client_controller.new_options
        
        with mock.patch.object( CG.client_controller, 'pub' ) as pub, mock.patch.object( CG.client_controller, 'Write' ) as write:
            
            ClientGUIMediaViewerHighlight.SetHighlight( highlight_is_on = True )
            
            self.assertTrue( new_options.GetBoolean( BOOLEAN_NAME ) )
            self.assertEqual( new_options.GetString( STRING_NAME ), '#FF00FF' )
            
            # saved, and open media viewers told
            write.assert_called_once_with( 'serialisable', new_options )
            pub.assert_called_once_with( 'notify_media_viewer_highlight_changed' )
            
            ClientGUIMediaViewerHighlight.SetHighlight( colour = 'abcdef' )
            
            self.assertTrue( new_options.GetBoolean( BOOLEAN_NAME ) )
            self.assertEqual( new_options.GetString( STRING_NAME ), '#ABCDEF' )
            
            ClientGUIMediaViewerHighlight.SetHighlight( highlight_is_on = False, colour = '#FF00FF' )
            
            self.assertFalse( new_options.GetBoolean( BOOLEAN_NAME ) )
            self.assertEqual( new_options.GetString( STRING_NAME ), '#FF00FF' )
            
            pub.reset_mock()
            
            with self.assertRaises( ValueError ):
                
                ClientGUIMediaViewerHighlight.SetHighlight( highlight_is_on = True, colour = 'magenta' )
                
            
            self.assertEqual( new_options.GetString( STRING_NAME ), '#FF00FF' )
            pub.assert_not_called()
            
        
    
    def test_api_info( self ):
        
        canvas = self._GetCanvas()
        
        canvas.GetCanvasKey.return_value = b'\xab' * 32
        
        CG.client_controller.new_options.SetBoolean( BOOLEAN_NAME, True )
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = [ canvas ] ):
            
            self.assertEqual( ClientGUIMediaViewerHighlight.GetHighlightAPIInfo(), { 'highlight_last_opened' : True, 'colour' : '#FF00FF', 'last_opened_canvas_key' : 'ab' * 32 } )
            
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = [] ):
            
            self.assertEqual( ClientGUIMediaViewerHighlight.GetHighlightAPIInfo()[ 'last_opened_canvas_key' ], None )
            
        
    
    def test_canvas_repaints( self ):
        
        canvas = ClientGUICanvas.Canvas.__new__( ClientGUICanvas.Canvas )
        
        canvas._media_container = mock.Mock()
        
        with mock.patch.object( canvas, 'update' ) as update:
            
            canvas.NotifyMediaViewerHighlightChanged()
            
            update.assert_called_once_with()
            
        
        canvas._media_container.update.assert_called_once_with()
        
    
    def test_options_panel( self ):
        
        from hydrus.client.gui.panels.options import MediaViewerPanel
        
        new_options = CG.client_controller.new_options
        
        new_options.SetBoolean( BOOLEAN_NAME, True )
        new_options.SetString( STRING_NAME, '#00FF00' )
        
        panel = MediaViewerPanel.MediaViewerPanel( None )
        
        try:
            
            self.assertTrue( panel._highlight_last_opened_media_viewer.isChecked() )
            self.assertEqual( panel._last_opened_media_viewer_highlight_colour.GetColour(), QG.QColor( 0, 255, 0 ) )
            self.assertTrue( panel._last_opened_media_viewer_highlight_colour.isEnabled() )
            
            panel._highlight_last_opened_media_viewer.setChecked( False )
            panel._UpdateHighlightEnabled()
            
            self.assertFalse( panel._last_opened_media_viewer_highlight_colour.isEnabled() )
            
            panel._last_opened_media_viewer_highlight_colour.SetColour( QG.QColor( 255, 0, 255 ) )
            
            with mock.patch.object( CG.client_controller, 'pub' ) as pub:
                
                panel.UpdateOptions()
                
                pub.assert_any_call( 'notify_media_viewer_highlight_changed' )
                
            
            self.assertFalse( new_options.GetBoolean( BOOLEAN_NAME ) )
            self.assertEqual( new_options.GetString( STRING_NAME ), '#FF00FF' )
            
        finally:
            
            panel.deleteLater()
            
            
            

import os
import unittest

from unittest import mock

from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC

from hydrus.client.gui import ClientGUIShortcuts
from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.gui.canvas import ClientGUICanvasHoverFrames

from hydrus.test import HelperFunctions as HF
from hydrus.test import TestGlobals as TG

class FakeShortcutsManager( object ):
    
    def GetNamesToShortcuts( self, simple_command ):
        
        return {}
        
    

class FakeMediaContainer( object ):
    
    def __init__( self ):
        
        self.paused = False
        
    
    def Pause( self ):
        
        self.paused = True
        
    

class FakeCanvas( QW.QWidget ):
    
    def __init__( self ):
        
        super().__init__()
        
        self.manual_navigation_is_allowed = True
        
    
    def ManualNavigationIsAllowed( self ) -> bool:
        
        return self.manual_navigation_is_allowed
        
    
    def SupportsSlideshow( self ) -> bool:
        
        return False
        
    

def GetPlaylistCanvas( num_items: int ):
    
    # just enough of a playing playlist to step through it, without a real media viewer. showing an item is recorded, not done
    canvas = ClientGUICanvas.CanvasPlaylist.__new__( ClientGUICanvas.CanvasPlaylist )
    
    canvas._canvas_key = os.urandom( 32 )
    canvas._playlist_name = 'test'
    canvas._playlist_items = [ ( HF.GetFakeMediaResult( os.urandom( 32 ), mime = HC.VIDEO_MP4 ), None, None ) for i in range( num_items ) ]
    canvas._playlist_loop = False
    canvas._playlist_index = 0
    canvas._playlist_shuffle_order = None
    canvas._playlist_shuffle_position = 0
    canvas._playlist_finished = False
    canvas._media_container = FakeMediaContainer()
    
    shown = []
    
    def show_playlist_item( index ):
        
        shown.append( index )
        
        canvas._playlist_index = index
        canvas._playlist_finished = False
        
    
    canvas._ShowPlaylistItem = show_playlist_item
    
    return ( canvas, shown )
    

class TestPlaylistNavigation( unittest.TestCase ):
    
    def test_no_manual_navigation_while_playing( self ):
        
        ( canvas, shown ) = GetPlaylistCanvas( 3 )
        
        canvas._playlist_index = 1
        
        self.assertFalse( canvas.ManualNavigationIsAllowed() )
        
        for show_call in ( canvas._ShowNext, canvas._ShowPrevious, canvas._ShowFirst, canvas._ShowLast, canvas._ShowRandom, canvas._UndoRandom ):
            
            show_call()
            
        
        # nothing moved
        self.assertEqual( shown, [] )
        self.assertEqual( canvas._playlist_index, 1 )
        
        # but the playlist still goes on by itself
        canvas._AdvancePlaylist()
        
        self.assertEqual( shown, [ 2 ] )
        
    
    def test_manual_navigation_once_finished( self ):
        
        ( canvas, shown ) = GetPlaylistCanvas( 3 )
        
        canvas._playlist_index = 2
        
        # off the end, not looping
        canvas._AdvancePlaylist()
        
        self.assertTrue( canvas._playlist_finished )
        self.assertTrue( canvas._media_container.paused )
        self.assertTrue( canvas.ManualNavigationIsAllowed() )
        self.assertTrue( canvas._GetIndexString().endswith( ' (finished)' ) )
        
        self.assertEqual( shown, [] )
        
        # going back plays on from there, and then it is locked again
        canvas._ShowPrevious()
        
        self.assertEqual( shown, [ 1 ] )
        self.assertFalse( canvas.ManualNavigationIsAllowed() )
        self.assertFalse( canvas._GetIndexString().endswith( ' (finished)' ) )
        
        canvas._ShowNext()
        
        self.assertEqual( shown, [ 1 ] )
        
        # the other ways around work once it is finished, too
        for ( show_call, expected_index ) in ( ( canvas._ShowFirst, 0 ), ( canvas._ShowLast, 2 ), ( canvas._ShowNext, 0 ) ):
            
            canvas._playlist_finished = True
            
            show_call()
            
            self.assertEqual( shown[-1], expected_index )
            
        
    
    def test_other_canvases_navigate( self ):
        
        canvas = ClientGUICanvas.CanvasMediaListBrowser.__new__( ClientGUICanvas.CanvasMediaListBrowser )
        
        self.assertTrue( canvas.ManualNavigationIsAllowed() )
        
    
    def _DoHoverButtonsTest( self ):
        
        canvas = FakeCanvas()
        
        canvas_key = os.urandom( 32 )
        
        # the harness has no shortcuts manager, which the buttons' tooltips ask. we just want the navigation buttons on the left, so the rest, which want a real media viewer, are left out
        with mock.patch.object( ClientGUIShortcuts, 'shortcuts_manager', return_value = FakeShortcutsManager() ):
            
            with mock.patch.object( ClientGUICanvasHoverFrames.CanvasHoverFrameTop, '_PopulateCenterButtons', lambda self: None ):
                
                with mock.patch.object( ClientGUICanvasHoverFrames.CanvasHoverFrameTop, '_PopulateRightButtons', lambda self: None ):
                    
                    hover = ClientGUICanvasHoverFrames.CanvasHoverFrameTopNavigableList( canvas, canvas, canvas_key )
                    
                
            
        
        
        buttons = [ hover._first_button, hover._previous_button, hover._next_button, hover._last_button, hover._random_button ]
        
        self.assertEqual( hover._GetNavigationButtons(), buttons )
        
        # a playing playlist
        canvas.manual_navigation_is_allowed = False
        
        hover.SetIndexString( canvas_key, 'test: 1/3' )
        
        self.assertEqual( hover._index_text.text(), 'test: 1/3' )
        self.assertTrue( all( not button.isEnabled() for button in buttons ) )
        
        # another canvas's index does not touch us
        canvas.manual_navigation_is_allowed = True
        
        hover.SetIndexString( os.urandom( 32 ), 'other: 5/9' )
        
        self.assertEqual( hover._index_text.text(), 'test: 1/3' )
        self.assertTrue( all( not button.isEnabled() for button in buttons ) )
        
        # finished
        hover.SetIndexString( canvas_key, 'test: 3/3 (finished)' )
        
        self.assertTrue( all( button.isEnabled() for button in buttons ) )
        
        canvas.deleteLater()
        
    
    def test_hover_buttons( self ):
        
        TG.test_controller.CallBlockingToQtTLW( self._DoHoverButtonsTest )
        
    

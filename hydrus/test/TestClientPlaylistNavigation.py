import os
import unittest

from unittest import mock

from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC

from hydrus.client import ClientGlobals as CG
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
    canvas._playlist_items = [ ( HF.GetFakeMediaResult( os.urandom( 32 ), mime = HC.VIDEO_MP4 ), None, None, False ) for i in range( num_items ) ]
    canvas._playlist_loop = False
    canvas._playlist_index = 0
    canvas._playlist_shuffle_order = None
    canvas._playlist_shuffle_position = 0
    canvas._playlist_finished = False
    canvas._playlist_lock_navigation = True
    canvas._media_container = FakeMediaContainer()
    
    shown = []
    
    def show_playlist_item( index ):
        
        shown.append( index )
        
        canvas._playlist_index = index
        canvas._playlist_finished = False
        
    
    canvas._ShowPlaylistItem = show_playlist_item
    
    return ( canvas, shown )
    

class TestPlaylistNavigation( unittest.TestCase ):
    
    def test_no_manual_navigation_when_locked( self ):
        
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
        
    
    def test_manual_navigation_when_unlocked( self ):
        
        ( canvas, shown ) = GetPlaylistCanvas( 3 )
        
        canvas._playlist_lock_navigation = False
        
        self.assertTrue( canvas.ManualNavigationIsAllowed() )
        
        for ( show_call, expected_index ) in ( ( canvas._ShowNext, 1 ), ( canvas._ShowPrevious, 0 ), ( canvas._ShowLast, 2 ), ( canvas._ShowFirst, 0 ), ( canvas._ShowPrevious, 2 ) ):
            
            show_call()
            
            self.assertEqual( shown[-1], expected_index )
            
        
    
    def test_finishing_does_not_unlock( self ):
        
        ( canvas, shown ) = GetPlaylistCanvas( 3 )
        
        canvas._playlist_index = 2
        
        # off the end, not looping
        canvas._AdvancePlaylist()
        
        self.assertTrue( canvas._playlist_finished )
        self.assertTrue( canvas._media_container.paused )
        self.assertFalse( canvas.ManualNavigationIsAllowed() )
        
        canvas._ShowPrevious()
        
        self.assertEqual( shown, [] )
        
    
    def test_lock_toggle( self ):
        
        ( canvas, shown ) = GetPlaylistCanvas( 3 )
        
        new_options = CG.client_controller.new_options
        
        original_value = new_options.GetBoolean( 'playlists_lock_navigation' )
        
        canvas._playlist_lock_navigation = original_value
        
        try:
            
            # it is saved, so the next playlist starts the same way
            canvas._FlipPlaylistLockNavigation()
            
            self.assertEqual( canvas._playlist_lock_navigation, not original_value )
            self.assertEqual( new_options.GetBoolean( 'playlists_lock_navigation' ), not original_value )
            self.assertEqual( canvas.ManualNavigationIsAllowed(), original_value )
            
            canvas._FlipPlaylistLockNavigation()
            
            self.assertEqual( canvas._playlist_lock_navigation, original_value )
            self.assertEqual( new_options.GetBoolean( 'playlists_lock_navigation' ), original_value )
            
        finally:
            
            new_options.SetBoolean( 'playlists_lock_navigation', original_value )
            
        
    
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
        
    

class FakeViewMediaContainer( object ):
    
    # just the zoom and pan, as ( relative_zoom, center )
    def __init__( self, media ):
        
        self.media = media
        self.view = ( 1.0, ( 0.5, 0.5 ) )
        self.ready = True
        
    
    def GetCurrentView( self ):
        
        return self.view
        
    
    def GetMedia( self ):
        
        return self.media
        
    
    def SetCurrentView( self, relative_zoom, center ):
        
        if not self.ready:
            
            return False
            
        
        self.view = ( relative_zoom, center )
        
        return True
        
    

class TestPlaylistLockPosition( unittest.TestCase ):
    
    def test_lock_position( self ):
        
        canvas = ClientGUICanvas.CanvasPlaylist.__new__( ClientGUICanvas.CanvasPlaylist )
        
        media = object()
        
        container = FakeViewMediaContainer( media )
        
        canvas._current_media = media
        canvas._media_container = container
        canvas._playlist_lock_position = False
        canvas._playlist_locked_view = None
        canvas._playlist_item_view_applied = False
        
        new_options = TG.test_controller.new_options
        
        old_value = new_options.GetBoolean( 'playlists_lock_position' )
        
        new_options.SetBoolean( 'playlists_lock_position', False )
        
        try:
            
            # turning it on takes what the item is at now
            container.view = ( 2.0, ( 0.25, 0.75 ) )
            
            canvas._FlipPlaylistLockPosition()
            
            self.assertTrue( canvas._playlist_lock_position )
            self.assertTrue( new_options.GetBoolean( 'playlists_lock_position' ) )
            self.assertEqual( canvas._playlist_locked_view, ( 2.0, ( 0.25, 0.75 ) ) )
            
            # the user zooms this item some more, and that is what the next one gets
            container.view = ( 3.0, ( 0.5, 0.5 ) )
            
            canvas._CapturePlaylistLockedView()
            
            self.assertEqual( canvas._playlist_locked_view, ( 3.0, ( 0.5, 0.5 ) ) )
            
            # the next item comes up at its own zoom
            next_media = object()
            
            canvas._current_media = next_media
            container.media = next_media
            container.view = ( 1.0, ( 0.5, 0.5 ) )
            
            canvas._playlist_item_view_applied = False
            
            # until it has gone to the locked view, its own zoom is not what the rest get
            canvas._CapturePlaylistLockedView()
            
            self.assertEqual( canvas._playlist_locked_view, ( 3.0, ( 0.5, 0.5 ) ) )
            
            # it is not ready to zoom yet, so we try again next time
            container.ready = False
            
            canvas._ApplyPlaylistLockedView()
            
            self.assertFalse( canvas._playlist_item_view_applied )
            self.assertEqual( container.view, ( 1.0, ( 0.5, 0.5 ) ) )
            
            container.ready = True
            
            canvas._ApplyPlaylistLockedView()
            
            self.assertTrue( canvas._playlist_item_view_applied )
            self.assertEqual( container.view, ( 3.0, ( 0.5, 0.5 ) ) )
            
            # turning it off forgets it
            canvas._FlipPlaylistLockPosition()
            
            self.assertFalse( canvas._playlist_lock_position )
            self.assertIsNone( canvas._playlist_locked_view )
            
            # on with nothing locked yet, the next item keeps its own zoom, and that is what the rest get
            canvas._playlist_lock_position = True
            canvas._playlist_item_view_applied = False
            
            canvas._ApplyPlaylistLockedView()
            
            self.assertTrue( canvas._playlist_item_view_applied )
            self.assertEqual( container.view, ( 3.0, ( 0.5, 0.5 ) ) )
            
        finally:
            
            new_options.SetBoolean( 'playlists_lock_position', old_value )
            
        
    

import unittest

from unittest import mock

from hydrus.core import HydrusExceptions
from hydrus.core import HydrusTime

from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.gui.panels import ClientGUIScrolledPanelsNumberEntry

from hydrus.test import TestGlobals as TG

class FakeMediaContainer( object ):
    
    def __init__( self, media = 'media' ):
        
        self.media = media
        self.paused = False
        self.visible = True
        
    
    def GetMedia( self ):
        
        return self.media
        
    
    def hide( self ):
        
        self.visible = False
        
    
    def IsPaused( self ):
        
        return self.paused
        
    
    def Pause( self ):
        
        self.paused = True
        
    
    def PausePlay( self ):
        
        self.paused = not self.paused
        
    
    def show( self ):
        
        self.visible = True
        
    

class FakeTimer( object ):
    
    def __init__( self ):
        
        self.active = False
        
    
    def start( self ):
        
        self.active = True
        
    
    def stop( self ):
        
        self.active = False
        
    

class FakeCore( object ):
    
    def __init__( self ):
        
        self.menu_is_open = False
        
    
    def MenuIsOpen( self ):
        
        return self.menu_is_open
        
    

def make_canvas( canvas_class = ClientGUICanvas.CanvasMediaListBrowser ):
    
    canvas = canvas_class.__new__( canvas_class )
    
    canvas._media_container = FakeMediaContainer()
    canvas._current_media = 'media'
    
    canvas._playback_gap_ms = 0
    canvas._playback_gap_random_range = None
    canvas._playback_gap_current_ms = 0
    canvas._playback_gap_move_on_callable = None
    canvas._playback_gap_time_s = 0.0
    canvas._playback_gap_last_tick_time = 0.0
    canvas._playback_gap_was_playing = False
    canvas._playback_gap_timer = FakeTimer()
    
    return canvas
    

class TestPlaybackGaps( unittest.TestCase ):
    
    def test_logic( self ):
        
        self.assertEqual( ClientGUICanvas.ConvertPlaybackGapToString( 0 ), 'none' )
        self.assertEqual( ClientGUICanvas.ConvertPlaybackGapToString( 1500 ), '1,500ms' )
        
        self.assertFalse( ClientGUICanvas.PlaybackGapIsDone( 500, 0.49 ) )
        self.assertTrue( ClientGUICanvas.PlaybackGapIsDone( 500, 0.5 ) )
        self.assertTrue( ClientGUICanvas.PlaybackGapIsDone( 0, 0.0 ) )
        
        self.assertEqual( ClientGUICanvas.ConvertPlaybackGapRangeToString( ( 500, 2000 ) ), 'random 500ms to 2,000ms' )
        
        self.assertEqual( ClientGUICanvas.PickPlaybackGapMs( 1500, None ), 1500 )
        self.assertEqual( ClientGUICanvas.PickPlaybackGapMs( 0, ( 700, 700 ) ), 700 )
        
        picks = { ClientGUICanvas.PickPlaybackGapMs( 0, ( 10, 12 ) ) for i in range( 500 ) }
        
        self.assertEqual( picks, { 10, 11, 12 } )
        
    
    def test_random_gap( self ):
        
        canvas = make_canvas()
        
        moves = []
        
        self.assertFalse( canvas._PlaybackGapIsSet() )
        self.assertEqual( canvas._GetPlaybackGapString(), 'none' )
        
        canvas._SetPlaybackGapRandom( 200, 400 )
        
        self.assertTrue( canvas._PlaybackGapIsSet() )
        self.assertEqual( canvas._playback_gap_ms, 0 )
        self.assertEqual( canvas._GetPlaybackGapString(), 'random 200ms to 400ms' )
        
        core = FakeCore()
        
        now = [ 100.0 ]
        
        picks = iter( [ 300, 250 ] )
        
        with mock.patch.object( HydrusTime, 'GetNowPrecise', side_effect = lambda: now[0] ), mock.patch.object( ClientGUICanvas.CGC, 'core', return_value = core ), mock.patch.object( canvas, '_SubWindowIsOpen', return_value = False ), mock.patch.object( ClientGUICanvas.random, 'randint', side_effect = lambda a, b: next( picks ) ) as randint:
            
            # each gap gets its own length, picked from the range when it starts
            canvas._MoveOnWithPlaybackGap( lambda: moves.append( 'first' ) )
            
            randint.assert_called_once_with( 200, 400 )
            
            self.assertTrue( canvas._PlaybackGapIsUp() )
            self.assertEqual( canvas._playback_gap_current_ms, 300 )
            
            now[0] = 100.29
            
            canvas._DoPlaybackGapWork()
            
            self.assertEqual( moves, [] )
            
            now[0] = 100.31
            
            canvas._DoPlaybackGapWork()
            
            self.assertEqual( moves, [ 'first' ] )
            
            canvas._MoveOnWithPlaybackGap( lambda: moves.append( 'second' ) )
            
            self.assertEqual( canvas._playback_gap_current_ms, 250 )
            
            now[0] = 100.57
            
            canvas._DoPlaybackGapWork()
            
            self.assertEqual( moves, [ 'first', 'second' ] )
            
        
        # a fixed gap takes over from a random one, and back
        canvas._SetPlaybackGap( 1000 )
        
        self.assertIsNone( canvas._playback_gap_random_range )
        self.assertEqual( canvas._GetPlaybackGapString(), '1,000ms' )
        
        canvas._SetPlaybackGapRandom( 50, 60 )
        
        self.assertEqual( canvas._playback_gap_ms, 0 )
        
        # 'no gap' clears a random gap too
        canvas._SetPlaybackGap( 0 )
        
        self.assertFalse( canvas._PlaybackGapIsSet() )
        
        canvas._MoveOnWithPlaybackGap( lambda: moves.append( 'straight on' ) )
        
        self.assertEqual( moves[-1], 'straight on' )
        self.assertFalse( canvas._PlaybackGapIsUp() )
        
    
    def test_random_gap_changed_while_up( self ):
        
        canvas = make_canvas()
        
        canvas._SetPlaybackGap( 5000 )
        
        canvas._MoveOnWithPlaybackGap( lambda: None )
        
        self.assertEqual( canvas._playback_gap_current_ms, 5000 )
        
        # picking a random gap while one is up gives the one that is up a new length from the range
        canvas._SetPlaybackGapRandom( 100, 100 )
        
        self.assertEqual( canvas._playback_gap_current_ms, 100 )
        
        # and 'no gap' ends it as soon as it can
        canvas._SetPlaybackGap( 0 )
        
        self.assertTrue( ClientGUICanvas.PlaybackGapIsDone( canvas._playback_gap_current_ms, 0.0 ) )
        
    
    def test_gap( self ):
        
        canvas = make_canvas()
        
        container = canvas._media_container
        
        moves = []
        
        # no gap: straight on
        canvas._MoveOnWithPlaybackGap( lambda: moves.append( 'moved' ) )
        
        self.assertEqual( moves, [ 'moved' ] )
        self.assertFalse( canvas._PlaybackGapIsUp() )
        
        # with a gap, the item goes out of sight and quiet first
        canvas._SetPlaybackGap( 500 )
        
        core = FakeCore()
        
        now = [ 100.0 ]
        
        with mock.patch.object( HydrusTime, 'GetNowPrecise', side_effect = lambda: now[0] ), mock.patch.object( ClientGUICanvas.CGC, 'core', return_value = core ), mock.patch.object( canvas, '_SubWindowIsOpen', return_value = False ):
            
            canvas._MoveOnWithPlaybackGap( lambda: moves.append( 'moved again' ) )
            
            self.assertEqual( moves, [ 'moved' ] )
            self.assertTrue( canvas._PlaybackGapIsUp() )
            self.assertFalse( container.visible )
            self.assertTrue( container.paused )
            self.assertTrue( canvas._playback_gap_timer.active )
            
            now[0] = 100.31
            
            canvas._DoPlaybackGapWork()
            
            self.assertEqual( moves, [ 'moved' ] )
            
            # a menu being open holds it
            core.menu_is_open = True
            
            now[0] = 105.0
            
            canvas._DoPlaybackGapWork()
            
            self.assertEqual( moves, [ 'moved' ] )
            
            core.menu_is_open = False
            
            now[0] = 105.1
            
            canvas._DoPlaybackGapWork()
            
            self.assertEqual( moves, [ 'moved' ] )
            
            now[0] = 105.25
            
            canvas._DoPlaybackGapWork()
            
            # done. the move on did not change the media, so it comes back on show, but stays paused
            self.assertEqual( moves, [ 'moved', 'moved again' ] )
            self.assertFalse( canvas._PlaybackGapIsUp() )
            self.assertTrue( container.visible )
            self.assertTrue( container.paused )
            self.assertFalse( canvas._playback_gap_timer.active )
            
        
    
    def test_set_media_ends_gap( self ):
        
        canvas = make_canvas()
        
        container = canvas._media_container
        
        canvas._SetPlaybackGap( 1000 )
        
        with mock.patch.object( ClientGUICanvas.CanvasMediaListNavigable, 'SetMedia', create = True ) as parent_set_media:
            
            # the user going to the same item during the gap: it comes back and plays on, since it was playing before
            canvas._MoveOnWithPlaybackGap( lambda: None )
            
            self.assertFalse( container.visible )
            
            canvas.SetMedia( 'media' )
            
            self.assertFalse( canvas._PlaybackGapIsUp() )
            self.assertTrue( container.visible )
            self.assertFalse( container.paused )
            
            parent_set_media.assert_called_once_with( 'media', start_paused = None )
            
            # going to another item leaves the new one to play as it would
            canvas._MoveOnWithPlaybackGap( lambda: None )
            
            canvas.SetMedia( 'other media' )
            
            self.assertFalse( canvas._PlaybackGapIsUp() )
            self.assertTrue( container.visible )
            self.assertTrue( container.paused )
            
            # and with no gap up, it is just a normal SetMedia
            canvas.SetMedia( 'more media' )
            
            self.assertEqual( parent_set_media.call_count, 3 )
            
        
    
    def test_slideshow_stop_ends_gap( self ):
        
        canvas = make_canvas()
        
        container = canvas._media_container
        
        container.StopForSlideshow = lambda value: None
        
        canvas._slideshow_is_running = True
        
        canvas._SetPlaybackGap( 1000 )
        
        canvas._MoveOnWithPlaybackGap( lambda: None )
        
        canvas._StopSlideshow()
        
        # we stay where we were, playing like before
        self.assertFalse( canvas._PlaybackGapIsUp() )
        self.assertTrue( container.visible )
        self.assertFalse( container.paused )
        
    
    def test_playlist( self ):
        
        canvas = make_canvas( ClientGUICanvas.CanvasPlaylist )
        
        canvas._playlist_items = [ 'a', 'b', 'c' ]
        canvas._playlist_index = 1
        canvas._playlist_loop = False
        canvas._playlist_shuffle_order = None
        canvas._playlist_shuffle_position = 0
        
        self.assertFalse( canvas._PlaylistIsAtTheEnd() )
        
        canvas._playlist_index = 2
        
        self.assertTrue( canvas._PlaylistIsAtTheEnd() )
        
        canvas._playlist_loop = True
        
        self.assertFalse( canvas._PlaylistIsAtTheEnd() )
        
        canvas._playlist_loop = False
        canvas._playlist_shuffle_order = [ 2, 0, 1 ]
        canvas._playlist_shuffle_position = 1
        
        self.assertFalse( canvas._PlaylistIsAtTheEnd() )
        
        canvas._playlist_shuffle_position = 2
        
        self.assertTrue( canvas._PlaylistIsAtTheEnd() )
        
        # at the end, it holds on the last item with no gap first
        canvas._SetPlaybackGap( 1000 )
        
        with mock.patch.object( canvas, '_GoToNextPlaylistItem' ) as go_to_next:
            
            canvas._AdvancePlaylist()
            
            go_to_next.assert_called_once()
            
            self.assertFalse( canvas._PlaybackGapIsUp() )
            
            # otherwise, there is a gap before the next item
            canvas._playlist_shuffle_position = 0
            
            canvas._AdvancePlaylist()
            
            go_to_next.assert_called_once()
            
            self.assertTrue( canvas._PlaybackGapIsUp() )
            
        
    
    def test_range_panel( self ):
        
        def qt_code():
            
            with ClientGUITopLevelWindowsPanels.DialogEdit( None, 'range test' ) as dlg:
                
                panel = ClientGUIScrolledPanelsNumberEntry.EditNumberRangePanel( dlg, 'test', default_min = 500, default_max = 2000, min_value = 1, max_value = ClientGUICanvas.PLAYBACK_GAP_MAX_MS )
                
                self.assertEqual( panel.GetValue(), ( 500, 2000 ) )
                
                # min and max can be the same
                panel._min_spinbox.setValue( 2000 )
                
                self.assertEqual( panel.GetValue(), ( 2000, 2000 ) )
                
                # but min cannot be more than max
                panel._min_spinbox.setValue( 2001 )
                
                with self.assertRaises( HydrusExceptions.VetoException ):
                    
                    panel.GetValue()
                    
                
                # the limits hold
                panel._min_spinbox.setValue( 0 )
                panel._max_spinbox.setValue( ClientGUICanvas.PLAYBACK_GAP_MAX_MS + 1 )
                
                self.assertEqual( panel.GetValue(), ( 1, ClientGUICanvas.PLAYBACK_GAP_MAX_MS ) )
                
            
        
        TG.test_controller.CallBlockingToQtTLW( qt_code )
        
    

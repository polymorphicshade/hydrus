import inspect
import unittest

from unittest import mock

from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.media import ClientMediaPlaylists
from hydrus.client.media import ClientMediaPlaylists as P

from hydrus.test import TestGlobals as TG

class FakeSeekingMediaContainer( object ):
    
    def __init__( self ):
        
        self.seeks = []
        
    
    def SeekTo( self, timestamp_ms ):
        
        self.seeks.append( timestamp_ms )
        
    

class TestPlaylistItemLooping( unittest.TestCase ):
    
    def test_logic( self ):
        
        # once: never again
        self.assertFalse( P.PlaylistItemShouldPlayAgain( P.PLAYLIST_ITEM_LOOP_ONCE, 3, 1 ) )
        
        # n times: again until the nth time through has ended
        self.assertTrue( P.PlaylistItemShouldPlayAgain( P.PLAYLIST_ITEM_LOOP_TIMES, 3, 1 ) )
        self.assertTrue( P.PlaylistItemShouldPlayAgain( P.PLAYLIST_ITEM_LOOP_TIMES, 3, 2 ) )
        self.assertFalse( P.PlaylistItemShouldPlayAgain( P.PLAYLIST_ITEM_LOOP_TIMES, 3, 3 ) )
        self.assertFalse( P.PlaylistItemShouldPlayAgain( P.PLAYLIST_ITEM_LOOP_TIMES, 1, 1 ) )
        
        # for a time: round and round, until the time is up
        self.assertTrue( P.PlaylistItemShouldPlayAgain( P.PLAYLIST_ITEM_LOOP_SECONDS, 3, 50 ) )
        
        self.assertFalse( P.PlaylistItemTimeIsUp( P.PLAYLIST_ITEM_LOOP_SECONDS, 10.0, 9.9 ) )
        self.assertTrue( P.PlaylistItemTimeIsUp( P.PLAYLIST_ITEM_LOOP_SECONDS, 10.0, 10.0 ) )
        
        # the others do not have a time
        self.assertFalse( P.PlaylistItemTimeIsUp( P.PLAYLIST_ITEM_LOOP_ONCE, 10.0, 1000.0 ) )
        self.assertFalse( P.PlaylistItemTimeIsUp( P.PLAYLIST_ITEM_LOOP_TIMES, 10.0, 1000.0 ) )
        
        self.assertEqual( P.ConvertPlaylistItemLoopToString( P.PLAYLIST_ITEM_LOOP_ONCE, 3, 10.0 ), 'once' )
        self.assertEqual( P.ConvertPlaylistItemLoopToString( P.PLAYLIST_ITEM_LOOP_TIMES, 3, 10.0 ), '3 times' )
        self.assertTrue( P.ConvertPlaylistItemLoopToString( P.PLAYLIST_ITEM_LOOP_SECONDS, 3, 10.0 ).startswith( 'for 10' ) )
        
    
    def test_canvas( self ):
        
        canvas = ClientGUICanvas.CanvasPlaylist.__new__( ClientGUICanvas.CanvasPlaylist )
        
        container = FakeSeekingMediaContainer()
        
        canvas._media_container = container
        
        # going round again goes back to the start of the part, and checks it got there
        canvas._playlist_item_seek_confirmed = True
        canvas._playlist_item_last_timestamp_ms = 5000
        canvas._playlist_item_last_frame_end_time = 123.0
        canvas._playlist_item_had_played_once_at_start = False
        
        canvas._RestartPlaylistItemPass( 1000, 50.0 )
        
        self.assertEqual( container.seeks, [ 1000 ] )
        self.assertFalse( canvas._playlist_item_seek_confirmed )
        self.assertEqual( canvas._playlist_item_seek_attempts, 0 )
        self.assertEqual( canvas._playlist_item_seek_time, 50.0 )
        self.assertIsNone( canvas._playlist_item_last_timestamp_ms )
        self.assertIsNone( canvas._playlist_item_last_frame_end_time )
        self.assertTrue( canvas._playlist_item_had_played_once_at_start )
        
        # a whole file goes back to the very start
        canvas._RestartPlaylistItemPass( None, 60.0 )
        
        self.assertEqual( container.seeks, [ 1000, 0 ] )
        
        # images stay up for the looping time, if there is one
        canvas._playlist_item_loop_type = P.PLAYLIST_ITEM_LOOP_SECONDS
        canvas._playlist_item_loop_times = 2
        canvas._playlist_item_loop_seconds = 42.0
        
        self.assertEqual( canvas._GetPlaylistStillPeriod(), 42.0 )
        
        canvas._playlist_item_loop_type = P.PLAYLIST_ITEM_LOOP_TIMES
        
        self.assertEqual( canvas._GetPlaylistStillPeriod(), TG.test_controller.new_options.GetSlideshowDurations()[0] )
        
        # and the setting is remembered
        new_options = TG.test_controller.new_options
        
        old_values = ( new_options.GetInteger( 'playlists_item_loop_type' ), new_options.GetInteger( 'playlists_item_loop_times' ), new_options.GetFloat( 'playlists_item_loop_seconds' ) )
        
        try:
            
            canvas._SetPlaylistItemLooping( P.PLAYLIST_ITEM_LOOP_TIMES, 4, 15.0 )
            
            self.assertEqual( ( new_options.GetInteger( 'playlists_item_loop_type' ), new_options.GetInteger( 'playlists_item_loop_times' ), new_options.GetFloat( 'playlists_item_loop_seconds' ) ), ( P.PLAYLIST_ITEM_LOOP_TIMES, 4, 15.0 ) )
            
            self.assertEqual( ( canvas._playlist_item_loop_type, canvas._playlist_item_loop_times, canvas._playlist_item_loop_seconds ), ( P.PLAYLIST_ITEM_LOOP_TIMES, 4, 15.0 ) )
            
        finally:
            
            ( loop_type, loop_times, loop_seconds ) = old_values
            
            new_options.SetInteger( 'playlists_item_loop_type', loop_type )
            new_options.SetInteger( 'playlists_item_loop_times', loop_times )
            new_options.SetFloat( 'playlists_item_loop_seconds', loop_seconds )
            
        
    

class TestPlaylistKeepsGoing( unittest.TestCase ):
    
    def test_a_bit_short_audio( self ):
        
        # the file says it is 3:30, but the player goes round at 3:24
        self.assertTrue( ClientMediaPlaylists.PlaylistItemIsDone( None, 210000, 40, 204000, False, False ) )
        
        # a user seeking back from late in it to a few seconds in is not the end
        self.assertFalse( ClientMediaPlaylists.PlaylistItemIsDone( None, 210000, 5000, 204000, False, False ) )
        
        # or from earlier on to the very start
        self.assertFalse( ClientMediaPlaylists.PlaylistItemIsDone( None, 210000, 40, 150000, False, False ) )
        
        # a short file still gets a second's slack
        self.assertTrue( ClientMediaPlaylists.PlaylistItemIsDone( None, 5000, 10, 4100, False, False ) )
        
        # a span to the end of the file goes round to the start of the file too. how far out the duration can be goes with the file, not the span
        self.assertTrue( ClientMediaPlaylists.PlaylistItemIsDone( 210000, 210000, 40, 204000, False, False ) )
        
    
    def test_errors_do_not_stop_it( self ):
        
        canvas = ClientGUICanvas.CanvasPlaylist.__new__( ClientGUICanvas.CanvasPlaylist )
        
        canvas._playlist_work_error_reported = False
        
        calls = []
        
        def do_playlist_work():
            
            calls.append( 'work' )
            
            if len( calls ) <= 2:
                
                raise Exception( 'player was busy' )
                
            
        
        with mock.patch.object( canvas, '_DoPlaylistWork', side_effect = do_playlist_work ), mock.patch.object( ClientGUICanvas.HydrusData, 'ShowText' ) as show_text, mock.patch.object( ClientGUICanvas.HydrusData, 'ShowException' ) as show_exception:
            
            for i in range( 4 ):
                
                canvas.TIMERAnimationUpdate()
                
            
            # it kept going, and said so once
            self.assertEqual( calls, [ 'work' ] * 4 )
            
            show_text.assert_called_once()
            show_exception.assert_called_once()
            
        
    
    def test_own_timer( self ):
        
        # it does not wait on the main window's animation timer, which stops when the client is hidden to the system tray
        source = inspect.getsource( ClientGUICanvas.CanvasPlaylist.__init__ )
        
        self.assertNotIn( 'RegisterAnimationUpdateWindow', source )
        self.assertIn( '_playlist_timer', source )
        
        self.assertLessEqual( ClientGUICanvas.PLAYLIST_TICK_MS, 20 )
        
        
        

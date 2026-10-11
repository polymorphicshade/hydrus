import unittest

from unittest import mock

from hydrus.client.gui import ClientGUIMediaViewerABRepeat
from hydrus.client.gui.canvas import ClientGUICanvasMedia

FRAME_DURATION_MS = 40

class FakeVideoContainer( object ):
    
    def IsInitialised( self ):
        
        return True
        
    
    def GetTimestampMS( self, frame_index ):
        
        return frame_index * FRAME_DURATION_MS
        
    
    def GetDurationMS( self, frame_index ):
        
        return FRAME_DURATION_MS
        
    
    def GetReadyForFrame( self, frame_index ):
        
        pass
        
    
    def GetTimesToPlayAnimation( self ):
        
        return 0
        
    
    def HasFrame( self, frame_index ):
        
        return True
        
    

class FakeMPVWidget( object ):
    
    def __init__( self ):
        
        self.timestamp_ms = 0.0
        self.paused = False
        self.reversed = False
        self.calls = []
        
    
    def GetAnimationBarStatus( self ):
        
        return ( 0, self.timestamp_ms, self.paused, None )
        
    
    def IsPlaybackReversed( self ):
        
        return self.reversed
        
    
    def Seek( self, timestamp_ms ):
        
        self.calls.append( ( 'seek', timestamp_ms ) )
        
        self.timestamp_ms = timestamp_ms
        
    
    def SetABLoop( self, a_ms, b_ms ):
        
        self.calls.append( ( 'ab loop', a_ms, b_ms ) )
        
    
    def SetPlaybackReversed( self, reverse ):
        
        self.calls.append( ( 'reverse', reverse ) )
        
        self.reversed = reverse
        
    

class TestABRepeatPingPong( unittest.TestCase ):
    
    def test_wants_to_turn_forwards( self ):
        
        wants_to_turn = ClientGUICanvasMedia.ABLoopPingPongWantsToTurn
        
        # B is inside its frame, which starts at 4000
        ( a_ms, b_ms ) = ( 1000, 4020 )
        
        # the first check has nothing to go on
        self.assertFalse( wants_to_turn( a_ms, b_ms, False, None, 4000, 40 ) )
        
        # playing up to B
        self.assertFalse( wants_to_turn( a_ms, b_ms, False, 2000, 2040, 40 ) )
        self.assertFalse( wants_to_turn( a_ms, b_ms, False, 3920, 3960, 40 ) )
        
        # B's frame comes up
        self.assertTrue( wants_to_turn( a_ms, b_ms, False, 3960, 4000, 40 ) )
        
        # and if we missed it, the one after
        self.assertTrue( wants_to_turn( a_ms, b_ms, False, 4000, 4040, 40 ) )
        
        # a seek to after B plays on, like a normal loop
        self.assertFalse( wants_to_turn( a_ms, b_ms, False, 2000, 8000, 40 ) )
        self.assertFalse( wants_to_turn( a_ms, b_ms, False, 8000, 8040, 40 ) )
        
        # and so does going round from the end of the file to the start
        self.assertFalse( wants_to_turn( a_ms, b_ms, False, 9960, 0, 40 ) )
        
        # with no A, the loop is from the start
        self.assertTrue( wants_to_turn( None, b_ms, False, 3960, 4000, 40 ) )
        
        # audio has no frames
        self.assertFalse( wants_to_turn( a_ms, b_ms, False, 4010, 4018, 0.0 ) )
        self.assertTrue( wants_to_turn( a_ms, b_ms, False, 4015, 4020, 0.0 ) )
        
    
    def test_wants_to_turn_backwards( self ):
        
        wants_to_turn = ClientGUICanvasMedia.ABLoopPingPongWantsToTurn
        
        ( a_ms, b_ms ) = ( 1000, 4020 )
        
        self.assertFalse( wants_to_turn( a_ms, b_ms, True, None, 1000, 40 ) )
        
        # playing back to A
        self.assertFalse( wants_to_turn( a_ms, b_ms, True, 4000, 3960, 40 ) )
        self.assertFalse( wants_to_turn( a_ms, b_ms, True, 1080, 1040.5, 40 ) )
        
        # A's frame comes up. frame starts are not whole ms
        self.assertTrue( wants_to_turn( a_ms, b_ms, True, 1040.5, 1000.5, 40 ) )
        
        # a seek to before A turns round too, rather than playing back off the start of the file
        self.assertTrue( wants_to_turn( a_ms, b_ms, True, 3000, 200, 40 ) )
        
        # a seek to after B plays back down through it
        self.assertFalse( wants_to_turn( a_ms, b_ms, True, 3000, 8000, 40 ) )
        
        # with no A, it turns round on the first frame
        self.assertFalse( wants_to_turn( None, b_ms, True, 80, 40, 40 ) )
        self.assertTrue( wants_to_turn( None, b_ms, True, 40, 0, 40 ) )
        
        # and if the player ran off the start of the file and went round to the end before we saw that
        self.assertTrue( wants_to_turn( None, b_ms, True, 40, 9960, 40 ) )
        
    
    def _GetAnimation( self, num_frames ):
        
        # just enough of the native animation player to step through frames
        animation = ClientGUICanvasMedia.Animation.__new__( ClientGUICanvasMedia.Animation )
        
        animation._media = mock.Mock()
        animation._media.GetNumFrames.return_value = num_frames
        
        animation._num_frames = num_frames
        animation._video_container = FakeVideoContainer()
        
        animation._current_frame_index = 0
        animation._current_frame_drawn = True
        animation._current_timestamp_ms = 0
        animation._next_frame_due_at = 0
        animation._paused = False
        animation._playthrough_count = 0
        animation._stop_for_slideshow = False
        
        animation._ab_loop_a_ms = None
        animation._ab_loop_b_ms = None
        animation._ab_loop_ping_pong = False
        animation._ab_loop_playing_backwards = False
        
        return animation
        
    
    def _PlayAnimation( self, animation, num_steps ):
        
        frame_indices = []
        
        with mock.patch.object( animation, 'isVisible', return_value = True ), mock.patch.object( animation, 'update' ), mock.patch.object( ClientGUICanvasMedia.CG, 'client_controller' ) as controller:
            
            controller.new_options.GetBoolean.return_value = True
            
            for i in range( num_steps ):
                
                animation._current_frame_drawn = True
                animation._next_frame_due_at = 0
                
                animation.TIMERAnimationUpdate()
                
                frame_indices.append( animation._current_frame_index )
                
            
        
        return frame_indices
        
    
    def test_animation( self ):
        
        animation = self._GetAnimation( 10 )
        
        # frames 2 to 5
        a_ms = ClientGUICanvasMedia.ConvertFrameStartToPlaybackPointMS( 2 * FRAME_DURATION_MS )
        b_ms = ClientGUICanvasMedia.ConvertFrameToABLoopPointBMS( 5 * FRAME_DURATION_MS, FRAME_DURATION_MS )
        
        animation.SetABLoop( a_ms, b_ms )
        
        # a normal loop jumps back to A
        self.assertEqual( self._PlayAnimation( animation, 12 ), [ 1, 2, 3, 4, 5, 2, 3, 4, 5, 2, 3, 4 ] )
        
        # ping-pong plays back to it, and neither end is shown twice
        animation._current_frame_index = 0
        
        animation.SetABLoopPingPong( True )
        
        self.assertEqual( self._PlayAnimation( animation, 14 ), [ 1, 2, 3, 4, 5, 4, 3, 2, 3, 4, 5, 4, 3, 2 ] )
        
        self.assertEqual( animation._current_timestamp_ms, 2 * FRAME_DURATION_MS )
        
        # turning it off part way back plays forwards from there
        self._PlayAnimation( animation, 4 )
        
        self.assertEqual( animation._current_frame_index, 4 )
        self.assertTrue( animation._ab_loop_playing_backwards )
        
        animation.SetABLoopPingPong( False )
        
        self.assertEqual( self._PlayAnimation( animation, 3 ), [ 5, 2, 3 ] )
        
        # and so does clearing the loop
        animation.SetABLoopPingPong( True )
        
        self._PlayAnimation( animation, 3 )
        
        self.assertEqual( animation._current_frame_index, 4 )
        self.assertTrue( animation._ab_loop_playing_backwards )
        
        animation.SetABLoop( None, None )
        
        self.assertEqual( self._PlayAnimation( animation, 7 ), [ 5, 6, 7, 8, 9, 0, 1 ] )
        
    
    def test_animation_edges( self ):
        
        # with no A, and B on the last frame, it is the whole file
        animation = self._GetAnimation( 4 )
        
        animation.SetABLoopPingPong( True )
        animation.SetABLoop( None, ClientGUICanvasMedia.ConvertFrameToABLoopPointBMS( 3 * FRAME_DURATION_MS, FRAME_DURATION_MS ) )
        
        self.assertEqual( self._PlayAnimation( animation, 9 ), [ 1, 2, 3, 2, 1, 0, 1, 2, 3 ] )
        
        # a loop of one frame stays on it
        animation = self._GetAnimation( 10 )
        
        animation.SetABLoopPingPong( True )
        animation.SetABLoop( 4 * FRAME_DURATION_MS, ClientGUICanvasMedia.ConvertFrameToABLoopPointBMS( 4 * FRAME_DURATION_MS, FRAME_DURATION_MS ) )
        
        animation._current_frame_index = 3
        
        self.assertEqual( self._PlayAnimation( animation, 5 ), [ 4, 4, 4, 4, 4 ] )
        
        # a seek to before A, while playing backwards, turns round
        animation = self._GetAnimation( 10 )
        
        animation.SetABLoopPingPong( True )
        animation.SetABLoop( 4 * FRAME_DURATION_MS, ClientGUICanvasMedia.ConvertFrameToABLoopPointBMS( 7 * FRAME_DURATION_MS, FRAME_DURATION_MS ) )
        
        animation._current_frame_index = 6
        animation._ab_loop_playing_backwards = True
        
        self.assertEqual( self._PlayAnimation( animation, 1 ), [ 5 ] )
        
        animation._current_frame_index = 1
        
        self.assertEqual( self._PlayAnimation( animation, 3 ), [ 2, 3, 4 ] )
        self.assertFalse( animation._ab_loop_playing_backwards )
        
    
    def _GetContainer( self, media_window, num_frames = 250, duration_ms = 10000 ):
        
        # just enough of a media container to run an A-B repeat
        container = ClientGUICanvasMedia.MediaContainer.__new__( ClientGUICanvasMedia.MediaContainer )
        
        container._media = mock.Mock()
        container._media.GetNumFrames.return_value = num_frames
        container._media.GetDurationMS.return_value = duration_ms
        
        container._media_window = media_window
        
        container._ab_loop_a_ms = None
        container._ab_loop_b_ms = None
        container._ab_loop_ping_pong = False
        container._ab_loop_ping_pong_last_timestamp_ms = None
        container._ab_loop_ping_pong_turned_playback_backwards = False
        
        return container
        
    
    def test_mpv( self ):
        
        mpv_widget = FakeMPVWidget()
        
        container = self._GetContainer( mpv_widget )
        
        ab_loop_changes = []
        ping_pong_changes = []
        
        def play_to( timestamps_ms ):
            
            for timestamp_ms in timestamps_ms:
                
                mpv_widget.timestamp_ms = timestamp_ms
                
                container._CheckABLoopPingPong()
                
            
        
        with mock.patch.object( ClientGUICanvasMedia.ClientGUIMPV, 'MPVWidget', FakeMPVWidget ), mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopChanged' ) as ab_loop_changed, mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopPingPongChanged' ) as ping_pong_changed:
            
            ab_loop_changed.emit.side_effect = lambda a_ms, b_ms: ab_loop_changes.append( ( a_ms, b_ms ) )
            ping_pong_changed.emit.side_effect = ping_pong_changes.append
            
            # a normal loop is mpv's own
            container._SetABLoop( 1000, 4020 )
            
            self.assertEqual( mpv_widget.calls, [ ( 'ab loop', 1000, 4020 ) ] )
            self.assertEqual( ab_loop_changes, [ ( 1000, 4020 ) ] )
            
            play_to( [ 3960, 4000, 1000 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'ab loop', 1000, 4020 ) ] )
            
            # with ping-pong, mpv's is off, and we turn it round at each end
            mpv_widget.calls.clear()
            
            container.FlipABLoopPingPong()
            
            self.assertTrue( container.GetABLoopPingPong() )
            self.assertEqual( ping_pong_changes, [ True ] )
            self.assertEqual( mpv_widget.calls, [ ( 'ab loop', None, None ) ] )
            
            mpv_widget.calls.clear()
            
            play_to( [ 3920, 3960 ] )
            
            self.assertEqual( mpv_widget.calls, [] )
            
            play_to( [ 4000 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', True ) ] )
            
            play_to( [ 4000, 3960, 3920, 1080, 1040 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', True ) ] )
            
            play_to( [ 1000 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', True ), ( 'reverse', False ) ] )
            
            play_to( [ 1000, 1040, 1080, 3960, 4000 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', True ), ( 'reverse', False ), ( 'reverse', True ) ] )
            
            # while paused, nothing turns round
            mpv_widget.calls.clear()
            mpv_widget.paused = True
            
            play_to( [ 3000, 500, 3000 ] )
            
            self.assertEqual( mpv_widget.calls, [] )
            
            mpv_widget.paused = False
            
            # turning ping-pong off part way back plays forwards again, with mpv's own loop
            play_to( [ 3000, 2960 ] )
            
            container.SetABLoopPingPong( False )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', False ), ( 'ab loop', 1000, 4020 ) ] )
            self.assertEqual( ping_pong_changes, [ True, False ] )
            
            # it stays on for the next file, whose loop starts with nothing set
            container.SetABLoopPingPong( True )
            
            play_to( [ 3960, 4000, 3960 ] )
            
            self.assertTrue( mpv_widget.reversed )
            
            mpv_widget.calls.clear()
            
            container._SetABLoop( None, None )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', False ), ( 'ab loop', None, None ) ] )
            self.assertTrue( container.GetABLoopPingPong() )
            
            # with no A, mpv can run back off the start of the file and go round to the end. we put it back at the start
            container._SetABLoop( None, 4020 )
            
            play_to( [ 3960, 4000, 3960, 80, 40 ] )
            
            self.assertTrue( mpv_widget.reversed )
            
            mpv_widget.calls.clear()
            
            play_to( [ 9960 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', False ), ( 'seek', 0 ) ] )
            
            # a loop that is all one frame is left to mpv
            mpv_widget.calls.clear()
            
            container._SetABLoop( 1000, 1020 )
            
            self.assertEqual( mpv_widget.calls, [ ( 'ab loop', 1000, 1020 ) ] )
            
        
    
    def test_other_players( self ):
        
        # a player that cannot play backwards loops as normal
        media_window = mock.Mock()
        
        container = self._GetContainer( media_window )
        
        with mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopChanged' ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopPingPongChanged' ):
            
            container.SetABLoopPingPong( True )
            container._SetABLoop( 1000, 4020 )
            
            media_window.SetABLoop.assert_called_with( 1000, 4020 )
            media_window.SetPlaybackReversed.assert_not_called()
            
            container._CheckABLoopPingPong()
            
            media_window.GetAnimationBarStatus.assert_not_called()
            
        
        # the native animation player does its own
        animation = mock.Mock( spec = ClientGUICanvasMedia.Animation )
        
        container = self._GetContainer( animation )
        
        with mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopChanged' ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopPingPongChanged' ):
            
            container.SetABLoopPingPong( True )
            
            animation.SetABLoopPingPong.assert_called_with( True )
            
            container._SetABLoop( 1000, 4020 )
            
            animation.SetABLoop.assert_called_with( 1000, 4020 )
            
        
    
    def test_open_media_viewers( self ):
        
        def get_canvas_frame( canvas_key, visible = True ):
            
            canvas_frame = mock.Mock()
            
            canvas_frame.isVisible.return_value = visible
            canvas_frame.GetCanvas.return_value.GetCanvasKey.return_value = canvas_key
            canvas_frame.GetCanvas.return_value.GetABRepeatAPIInfo.return_value = { 'canvas_key' : canvas_key.hex() }
            
            return canvas_frame
            
        
        canvas_frames = [ get_canvas_frame( b'a' * 32 ), get_canvas_frame( b'b' * 32 ), get_canvas_frame( b'c' * 32, visible = False ) ]
        
        # one that is still opening
        canvas_frames.append( mock.Mock() )
        canvas_frames[-1].GetCanvas.return_value = None
        
        with mock.patch( 'hydrus.client.ClientGlobals.client_controller' ) as controller:
            
            controller.gui.GetCanvasFrames.return_value = canvas_frames
            
            self.assertEqual( ClientGUIMediaViewerABRepeat.GetOpenMediaViewersABRepeat(), [ { 'canvas_key' : ( b'a' * 32 ).hex() }, { 'canvas_key' : ( b'b' * 32 ).hex() } ] )
            
            self.assertEqual( ClientGUIMediaViewerABRepeat.SetOpenMediaViewersABRepeatPingPong( True ), 2 )
            
            canvas_frames[0].GetCanvas.return_value.SetABLoopPingPong.assert_called_once_with( True )
            canvas_frames[1].GetCanvas.return_value.SetABLoopPingPong.assert_called_once_with( True )
            canvas_frames[2].GetCanvas.return_value.SetABLoopPingPong.assert_not_called()
            
            self.assertEqual( ClientGUIMediaViewerABRepeat.SetOpenMediaViewersABRepeatPingPong( False, canvas_key = b'b' * 32 ), 1 )
            
            canvas_frames[0].GetCanvas.return_value.SetABLoopPingPong.assert_called_once_with( True )
            canvas_frames[1].GetCanvas.return_value.SetABLoopPingPong.assert_called_with( False )
            
            # one that is closing, or not there at all
            self.assertEqual( ClientGUIMediaViewerABRepeat.SetOpenMediaViewersABRepeatPingPong( True, canvas_key = b'c' * 32 ), 0 )
            self.assertEqual( ClientGUIMediaViewerABRepeat.SetOpenMediaViewersABRepeatPingPong( True, canvas_key = b'd' * 32 ), 0 )




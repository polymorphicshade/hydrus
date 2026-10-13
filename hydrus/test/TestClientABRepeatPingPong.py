import unittest

from unittest import mock

from hydrus.client.gui import ClientGUIMediaViewerABRepeat
from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.canvas import ClientGUIMPV

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
        
        self.can_play_ping_pong_loop_from_memory = False
        self.ping_pong_loop_points = None
        
    
    def GetAnimationBarStatus( self ):
        
        return ( 0, self.timestamp_ms, self.paused, None )
        
    
    def GetPingPongLoopPoints( self ):
        
        return self.ping_pong_loop_points
        
    
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
        
    
    def StartPingPongLoop( self, a_ms, b_ms ):
        
        if not self.can_play_ping_pong_loop_from_memory:
            
            return False
            
        
        self.calls.append( ( 'start ping-pong loop', a_ms, b_ms ) )
        
        self.ping_pong_loop_points = ( a_ms, b_ms )
        
        return True
        
    
    def StopPingPongLoop( self ):
        
        if self.ping_pong_loop_points is None:
            
            return
            
        
        self.calls.append( ( 'stop ping-pong loop', ) )
        
        self.ping_pong_loop_points = None
        
    

class FakeMPVMediator( object ):
    
    def __init__( self ):
        
        self.time_s = 0.0
        self.properties = { 'vid' : 1, 'aid' : 1, 'container-fps' : 25.0, 'hwdec-current' : 'no', 'video-params/pixelformat' : 'yuv420p' }
        self.calls = []
        
    
    def GetPlaybackTime( self ):
        
        return self.time_s
        
    
    def GetProperty( self, name ):
        
        return self.properties.get( name )
        
    
    def GotoPreviousOrNextFrame( self, direction ):
        
        self.calls.append( ( 'frame step', direction ) )
        
    
    def Seek( self, time_pos, precise = True ):
        
        self.calls.append( ( 'seek', time_pos ) )
        
    
    def SetComplexFilterGraph( self, graph ):
        
        self.calls.append( ( 'graph', graph ) )
        
    
    def SetPaused( self, value ):

        self.calls.append( ( 'paused', value ) )


    def SetPlayDirection( self, reverse ):

        self.calls.append( ( 'direction', reverse ) )


    def SetTracks( self, video_track, audio_track ):
        
        self.calls.append( ( 'tracks', video_track, audio_track ) )
        
    

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
        
        container._playback_skips = []
        container._zoom_timestamps = []
        container._scripted_events = []
        container._playback_freezes = []
        
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
                
            
        
        with mock.patch.object( ClientGUICanvasMedia.ClientGUIMPV, 'MPVWidget', FakeMPVWidget ), mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopChanged' ) as ab_loop_changed, mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopPingPongChanged' ) as ping_pong_changed, mock.patch.object( ClientGUICanvasMedia.CG, 'client_controller' ) as controller:
            
            gui = controller.gui
            
            ab_loop_changed.emit.side_effect = lambda a_ms, b_ms: ab_loop_changes.append( ( a_ms, b_ms ) )
            ping_pong_changed.emit.side_effect = ping_pong_changes.append
            
            # a normal loop is mpv's own
            container._SetABLoop( 1000, 4020 )
            
            self.assertEqual( mpv_widget.calls, [ ( 'ab loop', 1000, 4020 ) ] )
            self.assertEqual( ab_loop_changes, [ ( 1000, 4020 ) ] )
            
            # so we do not need to watch playback
            gui.RegisterAnimationUpdateWindow.assert_not_called()
            gui.UnregisterAnimationUpdateWindow.assert_called_with( container )
            
            play_to( [ 3960, 4000, 1000 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'ab loop', 1000, 4020 ) ] )
            
            # with ping-pong, mpv's is off, and we turn it round at each end
            mpv_widget.calls.clear()
            
            container.FlipABLoopPingPong()
            
            self.assertTrue( container.GetABLoopPingPong() )
            self.assertEqual( ping_pong_changes, [ True ] )
            self.assertEqual( mpv_widget.calls, [ ( 'ab loop', None, None ) ] )
            
            gui.RegisterAnimationUpdateWindow.assert_called_once_with( container )
            
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
            
            gui.RegisterAnimationUpdateWindow.assert_called_once_with( container )
            
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
            
        
    
    def test_mpv_loop_from_memory( self ):
        
        # mpv stalls every time it turns round, so once the loop is back at A, it plays it round from memory, where it can
        mpv_widget = FakeMPVWidget()
        mpv_widget.can_play_ping_pong_loop_from_memory = True
        
        container = self._GetContainer( mpv_widget )
        
        def play_to( timestamps_ms ):
            
            for timestamp_ms in timestamps_ms:
                
                mpv_widget.timestamp_ms = timestamp_ms
                
                container._CheckABLoopPingPong()
                
            
        
        with mock.patch.object( ClientGUICanvasMedia.ClientGUIMPV, 'MPVWidget', FakeMPVWidget ), mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopChanged' ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopPingPongChanged' ), mock.patch.object( ClientGUICanvasMedia.CG, 'client_controller' ):
            
            container.SetABLoopPingPong( True )
            container._SetABLoop( 1000, 4020 )
            
            mpv_widget.calls.clear()
            
            # the first time to B and back is turned round the slow way
            play_to( [ 3960, 4000, 3960, 1080, 1040 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', True ) ] )
            
            play_to( [ 1000 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', True ), ( 'reverse', False ), ( 'start ping-pong loop', 1000, 4020 ) ] )
            self.assertFalse( container._ab_loop_ping_pong_turned_playback_backwards )
            
            # and now mpv goes round by itself, and we leave it alone
            mpv_widget.calls.clear()
            
            play_to( [ 1040, 3960, 4000, 3960, 1040, 1000, 1040, 4000 ] )
            
            self.assertEqual( mpv_widget.calls, [] )
            
            # setting the same loop again does not disturb it
            container._SetABLoop( 1000, 4020 )
            
            self.assertEqual( mpv_widget.calls, [] )
            
            # a different loop is a different set of frames, so it starts over
            container._SetABLoop( 1000, 3020 )
            
            self.assertEqual( mpv_widget.calls, [ ( 'stop ping-pong loop', ), ( 'ab loop', None, None ) ] )
            
            mpv_widget.calls.clear()
            
            play_to( [ 2000, 2960, 3000, 2960, 1040, 1000 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', True ), ( 'reverse', False ), ( 'start ping-pong loop', 1000, 3020 ) ] )
            
            # a seek takes mpv out of the loop, and then we are turning it round again until it is next at A
            mpv_widget.calls.clear()
            mpv_widget.ping_pong_loop_points = None
            
            play_to( [ 2000, 2960, 3000 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', True ) ] )
            
            play_to( [ 2960, 1040, 1000 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', True ), ( 'reverse', False ), ( 'start ping-pong loop', 1000, 3020 ) ] )
            
            # turning ping-pong off goes back to mpv's own loop
            mpv_widget.calls.clear()
            
            container.SetABLoopPingPong( False )
            
            self.assertEqual( mpv_widget.calls, [ ( 'stop ping-pong loop', ), ( 'ab loop', 1000, 3020 ) ] )
            
            # with no A, a loop that ran off the start of the file is started from memory rather than seeked back
            container.SetABLoopPingPong( True )
            container._SetABLoop( None, 4020 )
            
            play_to( [ 3960, 4000, 3960, 80, 40 ] )
            
            mpv_widget.calls.clear()
            
            play_to( [ 9960 ] )
            
            self.assertEqual( mpv_widget.calls, [ ( 'reverse', False ), ( 'start ping-pong loop', None, 4020 ) ] )
            
        
    
    def _GetMPVWidget( self, num_frames = 250, duration_ms = 10000, resolution = ( 1920, 1080 ) ):
        
        # just enough of an mpv widget to run a ping-pong loop
        mpv_widget = ClientGUIMPV.MPVWidget.__new__( ClientGUIMPV.MPVWidget )
        
        mpv_widget._media = mock.Mock()
        mpv_widget._media.GetNumFrames.return_value = num_frames
        mpv_widget._media.GetDurationMS.return_value = duration_ms
        mpv_widget._media.GetResolution.return_value = resolution
        
        mpv_widget._mpv_mediator = FakeMPVMediator()
        
        mpv_widget._currently_in_media_load_error_state = False
        mpv_widget._file_header_is_loaded = True
        mpv_widget._disallow_seek_on_this_file = False
        mpv_widget._number_of_restarts_this_second = 0
        
        mpv_widget._playback_reversed = False
        
        mpv_widget._ping_pong_loop = None
        mpv_widget._ping_pong_loop_points = None
        mpv_widget._ping_pong_loop_tracks = ( 1, None )
        mpv_widget._tracks_are_set_by_hand = False
        mpv_widget._ping_pong_loop_time_hold = None
        
        return mpv_widget
        
    
    def test_mpv_loop_from_memory_helpers( self ):
        
        # whatever the frame rate, the A and B we make from a frame come back as that frame
        for fps in ( 23.976024, 25.0, 29.97003, 30.0, 59.94006, 60.0 ):
            
            frame_duration_ms = 1000 / fps
            
            for ( first_frame_index, last_frame_index ) in ( ( 0, 1 ), ( 1, 2 ), ( 7, 300 ), ( 301, 400 ), ( 100000, 100123 ) ):
                
                a_ms = ClientGUICanvasMedia.ConvertFrameStartToPlaybackPointMS( first_frame_index * frame_duration_ms )
                b_ms = ClientGUICanvasMedia.ConvertFrameToABLoopPointBMS( last_frame_index * frame_duration_ms, frame_duration_ms )
                
                self.assertEqual( ClientGUIMPV.GetPingPongLoopFrameRange( a_ms, b_ms, fps ), ( first_frame_index, last_frame_index ) )
                
            
        
        self.assertEqual( ClientGUIMPV.GetPingPongLoopFrameRange( None, 4020, 25.0 ), ( 0, 100 ) )
        
        # a B that is the very start of a frame is in that frame
        self.assertEqual( ClientGUIMPV.GetPingPongLoopFrameRange( 1000, 4000, 25.0 ), ( 25, 100 ) )
        self.assertEqual( ClientGUIMPV.GetPingPongLoopFrameRange( 1000, 3999, 25.0 ), ( 25, 99 ) )
        
        # the graph plays every frame from A to B, and then the ones in between on the way back, with audio that is exactly as long
        graph = ClientGUIMPV.GetPingPongLoopFilterGraph( 25, 100, 25.0, 1, 2 )
        
        self.assertEqual( graph, ';'.join( (
            '[vid1]fps=25.000000,trim=start=0.980000:end=4.020000,split[forwards][to_reverse]',
            "[to_reverse]trim=start=1.020000,reverse,select='gt(n\\,0)'[backwards]",
            '[forwards][backwards]concat=n=2:v=1:a=0,loop=loop=-1:size=32767,setpts=(N+25)/(25.000000*TB)[vo]',
            '[aid2]atrim=start=1.000000:end=4.000000,asplit[forwards_audio][to_reverse_audio]',
            '[to_reverse_audio]areverse[backwards_audio]',
            '[forwards_audio][backwards_audio]concat=n=2:v=0:a=1,aloop=loop=-1:size=2147480000,asetpts=(N/SR+1.000000)/TB[ao]'
        ) ) )
        
        graph = ClientGUIMPV.GetPingPongLoopFilterGraph( 0, 100, 25.0, 1, None )
        
        self.assertTrue( graph.startswith( '[vid1]fps=25.000000,trim=start=0.000000:end=4.020000,' ) )
        self.assertTrue( graph.endswith( '[vo]' ) )
        self.assertNotIn( 'aid', graph )
        
        # mpv's time goes up and up, and the file's goes back and forth. frames 25 to 100 are 1s to 4s
        for ( time_s, expected_time_s ) in ( ( 1.0, 1.0 ), ( 2.52, 2.52 ), ( 4.0, 4.0 ), ( 4.04, 3.96 ), ( 6.96, 1.04 ), ( 7.0, 1.0 ), ( 7.04, 1.04 ), ( 10.0, 4.0 ), ( 10.04, 3.96 ), ( 601.0, 1.0 ), ( 602.0, 2.0 ) ):
            
            self.assertAlmostEqual( ClientGUIMPV.ConvertPingPongLoopTimeToPlaybackTime( time_s, 25, 100, 25.0 ), expected_time_s, places = 6 )
            
        
        # a time from just before the loop started is still in it
        self.assertAlmostEqual( ClientGUIMPV.ConvertPingPongLoopTimeToPlaybackTime( 0.96, 25, 100, 25.0 ), 1.04, places = 6 )
        
        self.assertEqual( ClientGUIMPV.ConvertPingPongLoopTimeToPlaybackTime( 5.0, 25, 25, 25.0 ), 1.0 )
        
        self.assertEqual( ClientGUIMPV.EstimatePingPongLoopBufferBytes( 10, 1920, 1080, 'yuv420p' ), 10 * 1920 * 1080 * 1.5 )
        self.assertEqual( ClientGUIMPV.EstimatePingPongLoopBufferBytes( 10, 1920, 1080, 'nv12' ), 10 * 1920 * 1080 * 1.5 )
        self.assertEqual( ClientGUIMPV.EstimatePingPongLoopBufferBytes( 10, 1920, 1080, 'yuv420p10le' ), 10 * 1920 * 1080 * 3 )
        self.assertEqual( ClientGUIMPV.EstimatePingPongLoopBufferBytes( 10, 1920, 1080, 'yuv422p' ), 10 * 1920 * 1080 * 2 )
        self.assertEqual( ClientGUIMPV.EstimatePingPongLoopBufferBytes( 10, 1920, 1080, 'yuv444p' ), 10 * 1920 * 1080 * 3 )
        self.assertEqual( ClientGUIMPV.EstimatePingPongLoopBufferBytes( 10, 1920, 1080, 'rgba' ), 10 * 1920 * 1080 * 4 )
        self.assertEqual( ClientGUIMPV.EstimatePingPongLoopBufferBytes( 10, 1920, 1080, None ), 10 * 1920 * 1080 * 3 )
        
    
    def test_mpv_widget_loop_from_memory( self ):
        
        mpv_widget = self._GetMPVWidget()
        
        mediator = mpv_widget._mpv_mediator
        
        self.assertIsNone( mpv_widget.GetPingPongLoopPoints() )
        
        self.assertTrue( mpv_widget.StartPingPongLoop( 1000, 4020 ) )
        
        self.assertEqual( mpv_widget.GetPingPongLoopPoints(), ( 1000, 4020 ) )
        self.assertEqual( mediator.calls, [ ( 'graph', ClientGUIMPV.GetPingPongLoopFilterGraph( 25, 100, 25.0, 1, 1 ) ), ( 'seek', 1.0 ) ] )
        
        # where we are in the file goes back and forth as mpv's time goes up
        for ( time_s, expected_time_s ) in ( ( 1.0, 1.0 ), ( 4.0, 4.0 ), ( 4.04, 3.96 ), ( 7.04, 1.04 ) ):
            
            mediator.time_s = time_s
            
            self.assertAlmostEqual( mpv_widget._GetPlaybackTime(), expected_time_s, places = 6 )
            
        
        # a seek leaves the loop, and puts back the tracks that the graph took
        mediator.calls.clear()
        
        mpv_widget.Seek( 2000 )
        
        self.assertIsNone( mpv_widget.GetPingPongLoopPoints() )
        self.assertEqual( mediator.calls, [ ( 'graph', '' ), ( 'tracks', 'no', 'no' ), ( 'tracks', '1', '1' ), ( 'seek', 2.0 ) ] )
        
        # until mpv gets there, its time is still the loop's, so we give out where it is going
        self.assertEqual( mpv_widget._GetPlaybackTime(), 2.0 )
        
        mediator.time_s = 2.04
        
        self.assertEqual( mpv_widget._GetPlaybackTime(), 2.04 )
        
        mediator.time_s = 9.0
        
        self.assertEqual( mpv_widget._GetPlaybackTime(), 9.0 )
        
        # and if it never gets there, we do not wait forever
        self.assertTrue( mpv_widget.StartPingPongLoop( 1000, 4020 ) )
        
        mpv_widget.Seek( 2000 )
        
        mediator.time_s = 9.0
        
        self.assertEqual( mpv_widget._GetPlaybackTime(), 2.0 )
        
        with mock.patch.object( ClientGUIMPV.HydrusTime, 'TimeHasPassedFloat', return_value = True ):
            
            self.assertEqual( mpv_widget._GetPlaybackTime(), 9.0 )
            
        
        # stopping it carries on from where the loop had got to
        mediator.time_s = 1.0
        
        self.assertTrue( mpv_widget.StartPingPongLoop( 1000, 4020 ) )
        
        self.assertEqual( mpv_widget._GetPlaybackTime(), 1.0 )

        mediator.time_s = 4.52
        mediator.calls.clear()
        
        mpv_widget.StopPingPongLoop()
        
        self.assertEqual( [ call[0] for call in mediator.calls ], [ 'graph', 'tracks', 'tracks', 'seek' ] )
        self.assertAlmostEqual( mediator.calls[-1][1], 3.48, places = 6 )
        
        mediator.calls.clear()
        
        mpv_widget.StopPingPongLoop()
        
        self.assertEqual( mediator.calls, [] )
        
        # a frame step and a change of direction leave it too
        mediator.time_s = 1.0
        
        self.assertTrue( mpv_widget.StartPingPongLoop( 1000, 4020 ) )
        
        mediator.calls.clear()
        
        self.assertEqual( mpv_widget._GetPlaybackTime(), 1.0 )

        # this is the way back, at frame 99. mpv cannot step until it is out of the loop, so we pause it on the frame we want with a seek
        mediator.time_s = 4.04

        mpv_widget.GotoPreviousOrNextFrame( 1 )

        self.assertIsNone( mpv_widget.GetPingPongLoopPoints() )
        self.assertEqual( [ call[0] for call in mediator.calls ], [ 'paused', 'graph', 'tracks', 'tracks', 'seek' ] )
        self.assertAlmostEqual( mediator.calls[-1][1], 99.5 / 25, places = 6 )

        mediator.time_s = 1.0

        self.assertTrue( mpv_widget.StartPingPongLoop( 1000, 4020 ) )

        self.assertEqual( mpv_widget._GetPlaybackTime(), 1.0 )

        mediator.time_s = 4.04
        mediator.calls.clear()

        mpv_widget.GotoPreviousOrNextFrame( -1 )

        self.assertAlmostEqual( mediator.calls[-1][1], 97.5 / 25, places = 6 )

        # outside the loop, it is mpv's own frame step
        mediator.calls.clear()

        mpv_widget.GotoPreviousOrNextFrame( -1 )

        self.assertEqual( mediator.calls, [ ( 'frame step', -1 ) ] )

        mediator.time_s = 1.0

        self.assertTrue( mpv_widget.StartPingPongLoop( 1000, 4020 ) )
        
        mediator.calls.clear()
        
        mpv_widget.SetPlaybackReversed( True )
        
        self.assertIsNone( mpv_widget.GetPingPongLoopPoints() )
        self.assertEqual( [ call[0] for call in mediator.calls ], [ 'graph', 'tracks', 'tracks', 'seek', 'direction' ] )
        
        # starting it from playing backwards turns playback round first
        mediator.calls.clear()
        
        self.assertTrue( mpv_widget.StartPingPongLoop( None, 4020 ) )
        
        self.assertFalse( mpv_widget.IsPlaybackReversed() )
        self.assertEqual( mediator.calls, [ ( 'direction', False ), ( 'graph', ClientGUIMPV.GetPingPongLoopFilterGraph( 0, 100, 25.0, 1, 1 ) ), ( 'seek', 0.0 ) ] )
        
    
    def test_mpv_widget_loop_from_memory_limits( self ):
        
        # no audio track means no audio in the graph, and nothing to put back
        mpv_widget = self._GetMPVWidget()
        
        mediator = mpv_widget._mpv_mediator
        
        mediator.properties[ 'aid' ] = False
        
        self.assertTrue( mpv_widget.StartPingPongLoop( 1000, 4020 ) )
        
        self.assertEqual( mediator.calls[0], ( 'graph', ClientGUIMPV.GetPingPongLoopFilterGraph( 25, 100, 25.0, 1, None ) ) )
        
        mediator.calls.clear()
        
        mpv_widget.StopPingPongLoop()
        
        self.assertEqual( mediator.calls[1:3], [ ( 'tracks', 'no', 'no' ), ( 'tracks', '1', 'no' ) ] )
        
        # a container frame rate that is nonsense is not used
        mpv_widget = self._GetMPVWidget()
        
        mpv_widget._mpv_mediator.properties[ 'container-fps' ] = 1000.0
        
        self.assertTrue( mpv_widget.StartPingPongLoop( 1000, 4020 ) )
        
        self.assertEqual( mpv_widget._mpv_mediator.calls[0], ( 'graph', ClientGUIMPV.GetPingPongLoopFilterGraph( 25, 100, 25.0, 1, 1 ) ) )
        
        # one that is close is, since it is exact
        mpv_widget = self._GetMPVWidget( num_frames = 300, duration_ms = 10010 )
        
        mpv_widget._mpv_mediator.properties[ 'container-fps' ] = 30000 / 1001
        
        self.assertTrue( mpv_widget.StartPingPongLoop( 1000, 4020 ) )
        
        self.assertEqual( mpv_widget._ping_pong_loop, ( 30, 120, 29.97003 ) )
        
        # the things we cannot do it for
        def assert_refuses( mpv_widget, a_ms = 1000, b_ms = 4020 ):
            
            self.assertFalse( mpv_widget.StartPingPongLoop( a_ms, b_ms ) )
            
            self.assertIsNone( mpv_widget.GetPingPongLoopPoints() )
            self.assertEqual( mpv_widget._mpv_mediator.calls, [] )
            
        
        # audio, or anything else with no video track
        mpv_widget = self._GetMPVWidget()
        mpv_widget._mpv_mediator.properties[ 'vid' ] = False
        
        assert_refuses( mpv_widget )
        
        mpv_widget = self._GetMPVWidget( num_frames = None )
        
        assert_refuses( mpv_widget )
        
        # hardware decoding that keeps the frames on the graphics card
        mpv_widget = self._GetMPVWidget()
        mpv_widget._mpv_mediator.properties[ 'hwdec-current' ] = 'd3d11va'
        
        assert_refuses( mpv_widget )
        
        mpv_widget._mpv_mediator.properties[ 'hwdec-current' ] = 'd3d11va-copy'
        
        self.assertTrue( mpv_widget.StartPingPongLoop( 1000, 4020 ) )
        
        # a loop that is too much to hold in memory. this is 226 frames of 4k
        mpv_widget = self._GetMPVWidget( resolution = ( 3840, 2160 ) )
        
        assert_refuses( mpv_widget, a_ms = None, b_ms = 9020 )
        
        self.assertTrue( mpv_widget.StartPingPongLoop( 1000, 2020 ) )
        
        # a loop of one frame
        mpv_widget = self._GetMPVWidget()
        
        assert_refuses( mpv_widget, a_ms = 1000, b_ms = 1020 )
        
        # and a file that is not playing
        mpv_widget = self._GetMPVWidget()
        mpv_widget._file_header_is_loaded = False
        
        assert_refuses( mpv_widget )
        
        mpv_widget = self._GetMPVWidget()
        mpv_widget._currently_in_media_load_error_state = True
        
        assert_refuses( mpv_widget )
        
    
    def test_other_players( self ):
        
        # a player that cannot play backwards loops as normal
        media_window = mock.Mock()
        
        container = self._GetContainer( media_window )
        
        with mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopChanged' ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopPingPongChanged' ), mock.patch.object( ClientGUICanvasMedia.CG, 'client_controller' ):
            
            container.SetABLoopPingPong( True )
            container._SetABLoop( 1000, 4020 )
            
            media_window.SetABLoop.assert_called_with( 1000, 4020 )
            media_window.SetPlaybackReversed.assert_not_called()
            
            container._CheckABLoopPingPong()
            
            media_window.GetAnimationBarStatus.assert_not_called()
            
        
        # the native animation player does its own
        animation = mock.Mock( spec = ClientGUICanvasMedia.Animation )
        
        container = self._GetContainer( animation )
        
        with mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopChanged' ), mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'abLoopPingPongChanged' ), mock.patch.object( ClientGUICanvasMedia.CG, 'client_controller' ):
            
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




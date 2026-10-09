import unittest

from unittest import mock

from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions

from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.media import ClientGUIMediaPlaybackFreezes
from hydrus.client.media import ClientMediaPlaybackFreezes

class FakeMediaWindow( object ):
    
    def __init__( self ):
        
        self.timestamp_ms = 0
        self.paused = False
        self.calls = []
        
    
    def GetAnimationBarStatus( self ):
        
        return ( 0, self.timestamp_ms, self.paused, None )
        
    
    def IsPaused( self ):
        
        return self.paused
        
    
    def Pause( self ):
        
        self.paused = True
        
        self.calls.append( 'pause' )
        
    
    def Play( self ):
        
        self.paused = False
        
        self.calls.append( 'play' )
        
    
    def PausePlay( self ):
        
        self.paused = not self.paused
        
        self.calls.append( 'pauseplay' )
        
    

class TestPlaybackFreezes( unittest.TestCase ):
    
    def test_freeze_to_hold( self ):
        
        freezes = [ ( 13000, 500 ), ( 0, 1000 ), ( 5000, 2000 ), ( 59900, 3000 ) ]
        
        def hold( last_timestamp_ms, current_timestamp_ms, duration_ms = 60000 ):
            
            return ClientMediaPlaybackFreezes.GetPlaybackFreezeToHold( freezes, last_timestamp_ms, current_timestamp_ms, duration_ms )
            
        
        # the first look at playback, at the start
        self.assertEqual( hold( None, 0 ), ( 0, 1000 ) )
        self.assertEqual( hold( None, 30000 ), None )
        
        # normal playback holds at what it goes past
        self.assertEqual( hold( 0, 40 ), None )
        self.assertEqual( hold( 4990, 5010 ), ( 5000, 2000 ) )
        self.assertEqual( hold( 5000, 5040 ), None )
        
        # a big jump is the user seeking
        self.assertEqual( hold( 1000, 20000 ), None )
        
        # looping round from the end catches the end first
        self.assertEqual( hold( 59880, 20 ), ( 59900, 3000 ) )
        self.assertEqual( hold( 59900, 20 ), ( 0, 1000 ) )
        
        self.assertEqual( ClientMediaPlaybackFreezes.GetPlaybackFreezeToHold( [], 0, 40, 60000 ), None )
        
    
    def test_normalise( self ):
        
        # one per point, the later one wins, in order
        self.assertEqual( ClientMediaPlaybackFreezes.NormalisePlaybackFreezes( [ ( 5000, 1000 ), ( 0, 500 ), ( 5000, 2500 ) ] ), [ ( 0, 500 ), ( 5000, 2500 ) ] )
        self.assertEqual( ClientMediaPlaybackFreezes.NormalisePlaybackFreezes( [] ), [] )
        
        self.assertEqual( ClientMediaPlaybackFreezes.ConvertPlaybackFreezeDurationToString( 2500 ), '2.5s' )
        self.assertEqual( ClientMediaPlaybackFreezes.ConvertPlaybackFreezeDurationToString( 60000 ), '60s' )
        
    
    def _GetContainer( self, freezes ):
        
        container = ClientGUICanvasMedia.MediaContainer.__new__( ClientGUICanvasMedia.MediaContainer )
        
        container._media = mock.Mock()
        container._media.GetDurationMS.return_value = 60000
        container._media_window = FakeMediaWindow()
        container._playback_freezes = ClientMediaPlaybackFreezes.NormalisePlaybackFreezes( freezes )
        container._playback_freezes_last_timestamp_ms = None
        container._playback_freeze_hold = None
        
        return container
        
    
    def test_hold_and_play_on( self ):
        
        container = self._GetContainer( [ ( 5000, 2000 ), ( 5010, 1000 ) ] )
        
        window = container._media_window
        
        now = [ 1000.0 ]
        
        with mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ), mock.patch( 'hydrus.core.HydrusTime.GetNowFloat', side_effect = lambda: now[0] ):
            
            for timestamp_ms in ( 4900, 4950 ):
                
                window.timestamp_ms = timestamp_ms
                
                container._CheckPlaybackFreezes()
                
            
            self.assertEqual( window.calls, [] )
            
            # playback goes past both. it holds for the first
            window.timestamp_ms = 5020
            
            container._CheckPlaybackFreezes()
            
            self.assertEqual( window.calls, [ 'pause' ] )
            self.assertTrue( container.IsHoldingPlaybackFreeze() )
            
            now[0] += 1.9
            
            container._CheckPlaybackFreezes()
            
            self.assertTrue( window.paused )
            
            # and plays on by itself after it
            now[0] += 0.2
            
            container._CheckPlaybackFreezes()
            
            self.assertEqual( window.calls, [ 'pause', 'play' ] )
            self.assertFalse( container.IsHoldingPlaybackFreeze() )
            
            # then the second one, which playback also went past, holds
            window.timestamp_ms = 5040
            
            container._CheckPlaybackFreezes()
            
            self.assertEqual( window.calls, [ 'pause', 'play', 'pause' ] )
            
            # hitting play while it holds plays on straight away, and it does not hold again
            container.PausePlay()
            
            self.assertFalse( container.IsHoldingPlaybackFreeze() )
            
            window.timestamp_ms = 5080
            
            container._CheckPlaybackFreezes()
            
            now[0] += 5
            
            container._CheckPlaybackFreezes()
            
            self.assertEqual( window.calls, [ 'pause', 'play', 'pause', 'pauseplay' ] )
            self.assertFalse( window.paused )
            
        
    
    def test_paused_and_other_pauses( self ):
        
        container = self._GetContainer( [ ( 5000, 2000 ) ] )
        
        window = container._media_window
        
        now = [ 1000.0 ]
        
        with mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ), mock.patch( 'hydrus.core.HydrusTime.GetNowFloat', side_effect = lambda: now[0] ):
            
            window.timestamp_ms = 4000
            
            container._CheckPlaybackFreezes()
            
            # scanning through it while paused does not hold
            window.paused = True
            
            for timestamp_ms in ( 4500, 5000, 5500 ):
                
                window.timestamp_ms = timestamp_ms
                
                container._CheckPlaybackFreezes()
                
            
            window.paused = False
            
            window.timestamp_ms = 5520
            
            container._CheckPlaybackFreezes()
            
            self.assertEqual( window.calls, [] )
            
            # going back before it and playing through it again holds
            window.timestamp_ms = 4990
            
            container._CheckPlaybackFreezes()
            
            window.timestamp_ms = 5010
            
            container._CheckPlaybackFreezes()
            
            self.assertEqual( window.calls, [ 'pause' ] )
            
            # something else pausing it while it holds means it stays paused
            container.Pause()
            
            now[0] += 10
            
            container._CheckPlaybackFreezes()
            
            self.assertTrue( window.paused )
            self.assertNotIn( 'play', window.calls )
            
        
    
    def test_freeze_panels( self ):
        
        dialog = QW.QDialog()
        
        # adding one at 1:00
        
        panel = ClientGUIMediaPlaybackFreezes.EditPlaybackFreezePanel( dialog, ( 60000, ClientGUIMediaPlaybackFreezes.DEFAULT_PLAYBACK_FREEZE_DURATION_MS ), 120000 )
        
        self.assertEqual( panel._timestamp.text(), '1:00.000' )
        
        self.assertEqual( panel.GetValue(), ( 60000, 2000 ) )
        
        panel._timestamp.setText( '1:30.5' )
        panel._freeze_duration_s.setValue( 0.75 )
        
        self.assertEqual( panel.GetValue(), ( 90500, 750 ) )
        
        # the spinbox keeps it in range
        panel._freeze_duration_s.setValue( 0 )
        
        self.assertEqual( panel.GetValue(), ( 90500, ClientMediaPlaybackFreezes.MIN_PLAYBACK_FREEZE_DURATION_MS ) )
        
        # and a point that is in the file
        for bad_text in ( 'soon', '2:00.001' ):
            
            panel._timestamp.setText( bad_text )
            
            with self.assertRaises( HydrusExceptions.VetoException ):
                
                panel.GetValue()
                
            
        
        # managing
        
        panel = ClientGUIMediaPlaybackFreezes.ManagePlaybackFreezesPanel( dialog, [ ( 5000, 1000 ), ( 0, 2500 ), ( 13000, 500 ) ], 120000 )
        
        freezes_list = panel._freezes_list
        
        self.assertEqual( [ freezes_list.item( index ).text() for index in range( freezes_list.count() ) ], [ '0:00.000: hold for 2.5s', '0:05.000: hold for 1s', '0:13.000: hold for 0.5s' ] )
        
        freezes_list.item( 1 ).setSelected( True )
        
        panel._Remove()
        
        self.assertEqual( panel.GetValue(), [ ( 0, 2500 ), ( 13000, 500 ) ] )
        
        dialog.deleteLater()
        
    

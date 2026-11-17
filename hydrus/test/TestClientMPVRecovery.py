import unittest

from unittest import mock

from qtpy import QtCore as QC

from hydrus.core import HydrusData

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUI
from hydrus.client.gui.canvas import ClientGUICanvasMedia
from hydrus.client.gui.canvas import ClientGUIMPV

HASH = b'\x01' * 32
OTHER_HASH = b'\x02' * 32

class TestMPVRecoveryRecords( unittest.TestCase ):
    
    def setUp( self ):
        
        self._original_damaged = set( ClientGUIMPV.damaged_file_hashes )
        self._original_times = dict( ClientGUIMPV.mpv_core_death_times_for_files )
        self._original_num = ClientGUIMPV.num_mpv_core_death_recoveries
        
        ClientGUIMPV.damaged_file_hashes.clear()
        ClientGUIMPV.mpv_core_death_times_for_files.clear()
        
    
    def tearDown( self ):
        
        ClientGUIMPV.damaged_file_hashes.clear()
        ClientGUIMPV.damaged_file_hashes.update( self._original_damaged )
        
        ClientGUIMPV.mpv_core_death_times_for_files.clear()
        ClientGUIMPV.mpv_core_death_times_for_files.update( self._original_times )
        
        ClientGUIMPV.num_mpv_core_death_recoveries = self._original_num
        
    
    def test_giving_up( self ):
        
        num_recoveries = ClientGUIMPV.num_mpv_core_death_recoveries
        
        # the first time, it is loaded again
        self.assertFalse( ClientGUIMPV.NotifyMPVCoreDiedForFile( HASH, now = 1000.0 ) )
        self.assertNotIn( HASH, ClientGUIMPV.damaged_file_hashes )
        
        # another file is its own thing
        self.assertFalse( ClientGUIMPV.NotifyMPVCoreDiedForFile( OTHER_HASH, now = 1010.0 ) )
        
        # again, soon after, and we give up on it
        self.assertTrue( ClientGUIMPV.NotifyMPVCoreDiedForFile( HASH, now = 1030.0 ) )
        self.assertIn( HASH, ClientGUIMPV.damaged_file_hashes )
        
        self.assertEqual( ClientGUIMPV.num_mpv_core_death_recoveries, num_recoveries + 2 )
        
        # a long time after is a fresh start
        self.assertFalse( ClientGUIMPV.NotifyMPVCoreDiedForFile( OTHER_HASH, now = 1010.0 + ClientGUIMPV.MPV_CORE_DEATH_GIVE_UP_PERIOD_S + 1 ) )
        
        self.assertEqual( ClientGUIMPV.GetMPVRecoveryStatus(), { 'num_recoveries' : num_recoveries + 3, 'damaged_hashes' : [ HASH.hex() ] } )
        
        # the user forgives it
        self.assertEqual( ClientGUIMPV.ForgetDamagedFiles(), 1 )
        
        self.assertEqual( ClientGUIMPV.damaged_file_hashes, set() )
        self.assertFalse( ClientGUIMPV.NotifyMPVCoreDiedForFile( HASH, now = 1040.0 ) )
        
    

class TestMPVWidgetCoreDeath( unittest.TestCase ):
    
    def _GetWidget( self ):
        
        widget = ClientGUIMPV.MPVWidget.__new__( ClientGUIMPV.MPVWidget )
        
        widget._core_is_dead = False
        widget._currently_in_media_load_error_state = False
        widget._current_mpv_player_state = ClientGUIMPV.MPV_WIDGET_STATE_WORKING
        widget._media = mock.Mock()
        widget._mpv_mediator = mock.Mock()
        
        self._media_container = mock.Mock()
        
        patches = [
            mock.patch.object( widget, 'parentWidget', return_value = self._media_container ),
            mock.patch.object( widget, 'setVisible' ),
            mock.patch.object( CG.client_controller, 'CallAfterQtSafe', side_effect = lambda qobject, func, *args, **kwargs: func( *args, **kwargs ) )
        ]
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
        return widget
        
    
    def test_core_dies( self ):
        
        widget = self._GetWidget()
        
        self.assertFalse( widget.IsCoreDead() )
        
        widget._NotifyCoreDied()
        
        self.assertTrue( widget.IsCoreDead() )
        
        # the media container is told, once
        self._media_container.NotifyMPVCoreDied.assert_called_once_with( widget )
        
        widget._NotifyCoreDied()
        
        self._media_container.NotifyMPVCoreDied.assert_called_once_with( widget )
        
        # nothing goes to the dead mpv after that
        widget._mpv_mediator.reset_mock()
        
        widget.SetMedia( mock.Mock() )
        widget.SetAudioFilterGraph( 'lowpass' )
        
        self.assertIsNone( widget._media )
        self.assertEqual( widget._mpv_mediator.mock_calls, [] )
        
    
    def test_shutdown_event( self ):
        
        widget = self._GetWidget()
        
        # a shutdown we asked for is fine
        widget._current_mpv_player_state = ClientGUIMPV.MPV_WIDGET_STATE_CLEANING_UP
        
        widget.eventFilter( widget, ClientGUIMPV.MPVShutdownEvent() )
        
        self.assertFalse( widget.IsCoreDead() )
        
        # one we did not is not
        widget._current_mpv_player_state = ClientGUIMPV.MPV_WIDGET_STATE_WORKING
        
        widget.eventFilter( widget, ClientGUIMPV.MPVShutdownEvent() )
        
        self.assertTrue( widget.IsCoreDead() )
        
        self._media_container.NotifyMPVCoreDied.assert_called_once_with( widget )
        
    

class TestMPVWidgetPool( unittest.TestCase ):
    
    def _GetGUI( self, persistent_widgets ):
        
        gui = ClientGUI.FrameGUI.__new__( ClientGUI.FrameGUI )
        
        gui._persistent_mpv_widgets = list( persistent_widgets )
        gui._isolated_mpv_widgets = []
        
        return gui
        
    
    def _GetMPVWidget( self, dead ):
        
        mpv_widget = mock.Mock()
        
        mpv_widget.IsCoreDead.return_value = dead
        
        return mpv_widget
        
    
    def test_dead_players_are_set_aside( self ):
        
        ( alive, dead ) = ( self._GetMPVWidget( False ), self._GetMPVWidget( True ) )
        
        gui = self._GetGUI( [ alive, dead ] )
        
        # the dead one at the end of the pool is skipped
        self.assertIs( gui.GetMPVWidget( mock.Mock() ), alive )
        
        self.assertEqual( gui._persistent_mpv_widgets, [] )
        self.assertEqual( gui._isolated_mpv_widgets, [ dead ] )
        dead.hide.assert_called()
        
        # and one that dies while it is out does not go back in
        another_dead = self._GetMPVWidget( True )
        
        gui.ReleaseMPVWidget( another_dead )
        gui.ReleaseMPVWidget( alive )
        
        self.assertEqual( gui._persistent_mpv_widgets, [ alive ] )
        self.assertEqual( gui._isolated_mpv_widgets, [ dead, another_dead ] )
        
    
    def test_all_dead( self ):
        
        dead = self._GetMPVWidget( True )
        
        gui = self._GetGUI( [ dead ] )
        
        new_widget = self._GetMPVWidget( False )
        
        with mock.patch.object( ClientGUI.ClientGUIMPV, 'MPVWidget', return_value = new_widget ) as make_widget:
            
            parent = mock.Mock()
            
            self.assertIs( gui.GetMPVWidget( parent ), new_widget )
            
            make_widget.assert_called_once_with( parent )
            
        
        self.assertEqual( gui._isolated_mpv_widgets, [ dead ] )
        
    

class TestMediaContainerMPVRecovery( unittest.TestCase ):
    
    def setUp( self ):
        
        self._original_damaged = set( ClientGUIMPV.damaged_file_hashes )
        self._original_times = dict( ClientGUIMPV.mpv_core_death_times_for_files )
        self._original_num = ClientGUIMPV.num_mpv_core_death_recoveries
        
        ClientGUIMPV.mpv_core_death_times_for_files.clear()
        
    
    def tearDown( self ):
        
        ClientGUIMPV.damaged_file_hashes.clear()
        ClientGUIMPV.damaged_file_hashes.update( self._original_damaged )
        
        ClientGUIMPV.mpv_core_death_times_for_files.clear()
        ClientGUIMPV.mpv_core_death_times_for_files.update( self._original_times )
        
        ClientGUIMPV.num_mpv_core_death_recoveries = self._original_num
        
    
    def _GetContainer( self ):
        
        container = ClientGUICanvasMedia.MediaContainer.__new__( ClientGUICanvasMedia.MediaContainer )
        
        self._mpv_widget = mock.Mock()
        self._media = mock.Mock()
        self._media.GetHash.return_value = HASH
        
        container._media_window = self._mpv_widget
        container._media = self._media
        container._standby_mpv_widget = None
        
        self._calls = []
        
        def destroy( media_window ):
            
            self._calls.append( ( 'destroy', media_window ) )
            
        
        def set_media( media, maintain_zoom, maintain_zoom_type, maintain_pan, start_paused = None, start_muted = False ):
            
            self._calls.append( ( 'set media', media, maintain_zoom, maintain_zoom_type, maintain_pan, start_paused ) )
            
        
        patches = [
            mock.patch.object( container, '_DestroyOrHideThisMediaWindow', side_effect = destroy ),
            mock.patch.object( container, 'SetMedia', side_effect = set_media ),
            mock.patch.object( container, 'SetNextMediaStartMS', side_effect = lambda media, start_ms: self._calls.append( ( 'start at', media, start_ms ) ) ),
            mock.patch.object( container, '_GetCurrentPlaybackTimestampMS', return_value = 65000 ),
            mock.patch.object( container, '_ReleaseStandbyMPVWidget' ),
            mock.patch.object( HydrusData, 'ShowText' )
        ]
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
        return container
        
    
    def test_recovering( self ):
        
        container = self._GetContainer()
        
        container.NotifyMPVCoreDied( self._mpv_widget )
        
        # the dead player comes out, and the file goes back in a new one, where it was, playing
        self.assertEqual( self._calls, [
            ( 'destroy', self._mpv_widget ),
            ( 'start at', self._media, 65000 ),
            ( 'set media', self._media, True, True, True, False )
        ] )
        
        self.assertIsNone( container._media_window )
        
        ( message, ) = HydrusData.ShowText.call_args.args
        
        self.assertIn( 'a new mpv player has taken over', message )
        self.assertNotIn( HASH, ClientGUIMPV.damaged_file_hashes )
        
    
    def test_giving_up( self ):
        
        container = self._GetContainer()
        
        container.NotifyMPVCoreDied( self._mpv_widget )
        
        # the new player dies on it too
        container._media_window = self._mpv_widget
        container._media = self._media
        
        container.NotifyMPVCoreDied( self._mpv_widget )
        
        ( message, ) = HydrusData.ShowText.call_args.args
        
        self.assertIn( 'will not be played in mpv again', message )
        self.assertIn( HASH, ClientGUIMPV.damaged_file_hashes )
        
    
    def test_other_players( self ):
        
        container = self._GetContainer()
        
        # a standby player just goes
        standby = mock.Mock()
        
        container._standby_mpv_widget = standby
        
        container.NotifyMPVCoreDied( standby )
        
        container._ReleaseStandbyMPVWidget.assert_called_once_with()
        
        # one we are not using any more is not our problem
        container.NotifyMPVCoreDied( mock.Mock() )
        
        self.assertEqual( self._calls, [] )
        
        
        

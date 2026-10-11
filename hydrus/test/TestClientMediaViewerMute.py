import unittest

from unittest import mock

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientGlobals as CG
from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.gui.canvas import ClientGUICanvasDuplicates
from hydrus.client.gui.canvas import ClientGUICanvasMedia

class TestMediaViewerMute( unittest.TestCase ):
    
    def _GetContainer( self, canvas_type = CC.CANVAS_MEDIA_VIEWER ):
        
        # just enough of a media container to mute it
        container = ClientGUICanvasMedia.MediaContainer.__new__( ClientGUICanvasMedia.MediaContainer )
        
        container._canvas_type = canvas_type
        container._media = None
        container._media_window = mock.Mock( spec = ClientGUICanvasMedia.ClientGUIMPV.MPVWidget )
        container._deferred_set_media_call = None
        
        container._has_per_player_mute_state = False
        container._per_player_mute_state = False
        
        return container
        
    
    def test_which_files_start_muted( self ):
        
        media = mock.Mock()
        
        # the media viewer and the archive/delete filter: every file
        for canvas_class in ( ClientGUICanvas.CanvasMediaListBrowser, ClientGUICanvas.CanvasMediaListFilterArchiveDelete ):
            
            canvas = canvas_class.__new__( canvas_class )
            
            canvas._slideshow_is_running = False
            
            self.assertIn( canvas.CANVAS_TYPE, CC.CANVAS_MEDIA_VIEWER_TYPES )
            
            self.assertTrue( canvas._ShouldStartMediaMuted( None ) )
            self.assertTrue( canvas._ShouldStartMediaMuted( media ) )
            
        
        # but not while a slideshow is running
        canvas = ClientGUICanvas.CanvasMediaListBrowser.__new__( ClientGUICanvas.CanvasMediaListBrowser )
        
        canvas._slideshow_is_running = True
        
        self.assertFalse( canvas._ShouldStartMediaMuted( None ) )
        self.assertFalse( canvas._ShouldStartMediaMuted( media ) )
        
        canvas._slideshow_is_running = False
        
        self.assertTrue( canvas._ShouldStartMediaMuted( media ) )
        
        # or in a playlist
        canvas = ClientGUICanvas.CanvasPlaylist.__new__( ClientGUICanvas.CanvasPlaylist )
        
        canvas._slideshow_is_running = False
        
        self.assertFalse( canvas._ShouldStartMediaMuted( None ) )
        self.assertFalse( canvas._ShouldStartMediaMuted( media ) )
        
        # the duplicate filter goes back and forth between files, so it is just the first
        canvas = ClientGUICanvasDuplicates.CanvasFilterDuplicates.__new__( ClientGUICanvasDuplicates.CanvasFilterDuplicates )
        
        self.assertTrue( canvas._ShouldStartMediaMuted( None ) )
        self.assertFalse( canvas._ShouldStartMediaMuted( media ) )
        
        # the preview follows the options
        canvas = ClientGUICanvas.CanvasPanel.__new__( ClientGUICanvas.CanvasPanel )
        
        self.assertEqual( canvas.CANVAS_TYPE, CC.CANVAS_PREVIEW )
        
        self.assertFalse( canvas._ShouldStartMediaMuted( None ) )
        self.assertFalse( canvas._ShouldStartMediaMuted( media ) )
        
    
    def test_start_muted( self ):
        
        container = self._GetContainer()
        
        with mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'muteStateChanged' ) as mute_state_changed, mock.patch.object( ClientGUICanvasMedia.ClientGUIMediaVolume, 'GetCorrectCurrentMute', return_value = False ):
            
            # the options say not muted, and nothing is set yet
            self.assertFalse( container.GetCurrentMuteState() )
            
            container._StartMuted()
            
            self.assertTrue( container.GetCurrentMuteState() )
            self.assertTrue( container.HasPerPlayerMuteState() )
            container._media_window.SetMute.assert_called_once_with( True )
            mute_state_changed.emit.assert_called_once_with()
            
            # the user unmutes this file
            container.FlipPerPlayerMuteState()
            
            self.assertFalse( container.GetCurrentMuteState() )
            container._media_window.SetMute.assert_called_with( False )
            
            # and the next one is muted again
            container._StartMuted()
            
            self.assertTrue( container.GetCurrentMuteState() )
            container._media_window.SetMute.assert_called_with( True )
            self.assertEqual( mute_state_changed.emit.call_count, 3 )
            
            # one that was left muted has nothing to change
            container._media_window.SetMute.reset_mock()
            
            container._StartMuted()
            
            self.assertTrue( container.GetCurrentMuteState() )
            container._media_window.SetMute.assert_not_called()
            self.assertEqual( mute_state_changed.emit.call_count, 3 )
            
        
    
    def test_start_muted_over_the_options( self ):
        
        # the options already mute media viewers, but the user could unmute those, so we still set our own
        container = self._GetContainer()
        
        with mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'muteStateChanged' ) as mute_state_changed, mock.patch.object( ClientGUICanvasMedia.ClientGUIMediaVolume, 'GetCorrectCurrentMute', return_value = True ):
            
            container._StartMuted()
            
            self.assertTrue( container.HasPerPlayerMuteState() )
            self.assertTrue( container.GetPerPlayerMuteState() )
            mute_state_changed.emit.assert_not_called()
            
        
    
    def test_set_media( self ):
        
        media = mock.Mock()
        
        # the file is muted before anything is made to play it
        container = self._GetContainer()
        
        calls = []
        
        with mock.patch.object( container, 'ReadyToSwitchMedia', return_value = True ), mock.patch.object( container, '_StartMuted', side_effect = lambda: calls.append( 'mute' ) ), mock.patch.object( ClientGUICanvasMedia.ClientMedia, 'GetShowAction', side_effect = Exception( 'far enough' ) ):
            
            with self.assertRaises( Exception ):
                
                container.SetMedia( media, False, False, False, start_muted = True )
                
            
            self.assertEqual( calls, [ 'mute' ] )
            
            # a playlist or slideshow leaves the sound as it is
            with self.assertRaises( Exception ):
                
                container.SetMedia( media, False, False, False )
                
            
            self.assertEqual( calls, [ 'mute' ] )
            
        
        # if we cannot switch yet, it is muted when we do
        container = self._GetContainer()
        
        with mock.patch.object( container, 'ReadyToSwitchMedia', return_value = False ), mock.patch.object( container, '_StartMuted' ) as start_muted:
            
            container.SetMedia( media, False, False, False, start_paused = True, start_muted = True )
            
            start_muted.assert_not_called()
            
            self.assertEqual( container._deferred_set_media_call._kwargs, { 'start_paused' : True, 'start_muted' : True } )
            
        
    
    def test_mute_is_not_remembered( self ):
        
        container = self._GetContainer()
        
        with mock.patch.object( ClientGUICanvasMedia.MediaContainer, 'muteStateChanged' ), mock.patch.object( CG.client_controller.new_options, 'SetNoneableInteger' ) as set_noneable_integer:
            
            container.SetPerPlayerMuteState( False )
            
            self.assertFalse( container.GetCurrentMuteState() )
            
            container.SetPerPlayerMuteState( True )
            container.SetPerPlayerMuteState( None )
            
            self.assertFalse( container.HasPerPlayerMuteState() )
            
            # nothing goes to the options for the next media viewer to pick up
            set_noneable_integer.assert_not_called()
            
        
        self.assertNotIn( 'media_viewer_last_mute', CG.client_controller.new_options._dictionary[ 'noneable_integers' ] )
        
        # the volume still is
        self.assertIn( 'media_viewer_last_volume', CG.client_controller.new_options._dictionary[ 'noneable_integers' ] )


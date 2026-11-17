import unittest

from unittest import mock

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIMediaViewerABRepeat
from hydrus.client.gui import ClientGUIMediaViewerSync
from hydrus.client.gui import ClientGUIMenus
from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.gui.canvas import ClientGUICanvasMedia

def GetCanvas( canvas_key: bytes, can_sync = True ):
    
    canvas = mock.Mock()
    
    canvas.CanSyncPlayback.return_value = can_sync
    canvas.GetCanvasKey.return_value = canvas_key
    
    return canvas
    

class TestMediaViewerSync( unittest.TestCase ):
    
    def setUp( self ):
        
        self._later_calls = []
        
        def call_later( window, delay, label, func, *args, **kwargs ):
            
            self._later_calls.append( ( delay, func ) )
            
        
        patches = [
            mock.patch.object( CG.client_controller, 'CallLaterQtSafe', side_effect = call_later ),
            mock.patch.object( ClientGUIMediaViewerSync.QP, 'isValid', return_value = True )
        ]
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
    
    def test_syncing( self ):
        
        ( first, second, image ) = ( GetCanvas( b'\x01' * 32 ), GetCanvas( b'\x02' * 32 ), GetCanvas( b'\x03' * 32, can_sync = False ) )
        
        num_synced = ClientGUIMediaViewerSync.SyncMediaViewersPlayback( [ first, second, image ] )
        
        self.assertEqual( num_synced, 2 )
        
        # they all go back to the start, paused, and do not play yet
        for canvas in ( first, second ):
            
            canvas.PrepareSyncedPlayback.assert_called_once_with()
            canvas.StartSyncedPlayback.assert_not_called()
            
        
        image.PrepareSyncedPlayback.assert_not_called()
        
        self.assertEqual( len( self._later_calls ), 1 )
        
        ( delay, start_them ) = self._later_calls[0]
        
        self.assertEqual( delay, ClientGUIMediaViewerSync.SYNC_START_DELAY_S )
        
        # and then they play together
        start_them()
        
        for canvas in ( first, second ):
            
            canvas.StartSyncedPlayback.assert_called_once_with()
            
        
        image.StartSyncedPlayback.assert_not_called()
        
    
    def test_one_closes_in_the_meantime( self ):
        
        ( first, second ) = ( GetCanvas( b'\x01' * 32 ), GetCanvas( b'\x02' * 32 ) )
        
        ClientGUIMediaViewerSync.SyncMediaViewersPlayback( [ first, second ] )
        
        ( delay, start_them ) = self._later_calls[0]
        
        with mock.patch.object( ClientGUIMediaViewerSync.QP, 'isValid', side_effect = lambda canvas: canvas is first ):
            
            start_them()
            
        
        first.StartSyncedPlayback.assert_called_once_with()
        second.StartSyncedPlayback.assert_not_called()
        
    
    def test_nothing_to_sync( self ):
        
        self.assertEqual( ClientGUIMediaViewerSync.SyncMediaViewersPlayback( [ GetCanvas( b'\x01' * 32, can_sync = False ) ] ), 0 )
        self.assertEqual( ClientGUIMediaViewerSync.SyncMediaViewersPlayback( [] ), 0 )
        
        self.assertEqual( self._later_calls, [] )
        
    
    def test_open_media_viewers( self ):
        
        ( first, second, third, image ) = ( GetCanvas( b'\x01' * 32 ), GetCanvas( b'\x02' * 32 ), GetCanvas( b'\x03' * 32 ), GetCanvas( b'\x04' * 32, can_sync = False ) )
        
        with mock.patch.object( ClientGUIMediaViewerABRepeat, 'GetOpenMediaViewerCanvases', return_value = [ first, second, third, image ] ):
            
            self.assertEqual( ClientGUIMediaViewerSync.GetSyncableMediaViewerCanvases(), [ first, second, third ] )
            
            # all of them
            self.assertEqual( ClientGUIMediaViewerSync.SyncOpenMediaViewersPlayback(), 3 )
            
            # just these
            self.assertEqual( ClientGUIMediaViewerSync.SyncOpenMediaViewersPlayback( canvas_keys = [ b'\x01' * 32, b'\x03' * 32, b'\x04' * 32 ] ), 2 )
            
        
        self.assertEqual( first.PrepareSyncedPlayback.call_count, 2 )
        self.assertEqual( second.PrepareSyncedPlayback.call_count, 1 )
        self.assertEqual( third.PrepareSyncedPlayback.call_count, 2 )
        
    
    def test_label( self ):
        
        canvas = GetCanvas( b'\x01' * 32 )
        
        canvas.GetMedia.return_value.GetDurationMS.return_value = 200000
        
        with mock.patch.object( ClientGUIMediaViewerSync.ClientMedia, 'GetMediasFiletypeSummaryString', return_value = 'mp4' ):
            
            label = ClientGUIMediaViewerSync.GetMediaViewerSyncLabel( 1, canvas )
            
        
        self.assertTrue( label.startswith( '2: mp4, ' ), label )
        
    
    def test_canvas( self ):
        
        canvas = ClientGUICanvas.Canvas.__new__( ClientGUICanvas.Canvas )
        
        canvas._current_media = mock.Mock()
        canvas._media_container = mock.Mock()
        
        canvas._media_container.CurrentlyPresentingMediaWithDuration.return_value = True
        
        self.assertTrue( canvas.CanSyncPlayback() )
        
        # paused, at the start
        canvas.PrepareSyncedPlayback()
        
        self.assertEqual( [ c for c in canvas._media_container.mock_calls if c[0] in ( 'Pause', 'SeekTo', 'Play' ) ], [ mock.call.Pause(), mock.call.SeekTo( 0 ) ] )
        
        canvas.StartSyncedPlayback()
        
        canvas._media_container.Play.assert_called_once_with()
        
        # an image, or nothing
        canvas._media_container.CurrentlyPresentingMediaWithDuration.return_value = False
        
        self.assertFalse( canvas.CanSyncPlayback() )
        
        canvas.StartSyncedPlayback()
        
        canvas._media_container.Play.assert_called_once_with()
        
        canvas._media_container.CurrentlyPresentingMediaWithDuration.return_value = True
        canvas._current_media = None
        
        self.assertFalse( canvas.CanSyncPlayback() )
        
    
    def test_media_container_play( self ):
        
        container = ClientGUICanvasMedia.MediaContainer.__new__( ClientGUICanvasMedia.MediaContainer )
        
        container._media = mock.Mock()
        
        with mock.patch.object( container, 'CurrentlyPresentingMediaWithDuration', return_value = True ), mock.patch.object( container, 'PausePlay' ) as pause_play:
            
            with mock.patch.object( container, 'IsPaused', return_value = True ):
                
                container.Play()
                
                pause_play.assert_called_once_with()
                
            
            # playing already, so it stays playing
            with mock.patch.object( container, 'IsPaused', return_value = False ):
                
                container.Play()
                
                pause_play.assert_called_once_with()
                
            
        
    
    def test_menu( self ):
        
        canvas = ClientGUICanvas.Canvas.__new__( ClientGUICanvas.Canvas )
        
        canvas._current_media = mock.Mock()
        canvas._media_container = mock.Mock()
        
        canvas._media_container.CurrentlyPresentingMediaWithDuration.return_value = True
        
        ( first, second ) = ( GetCanvas( b'\x01' * 32 ), GetCanvas( b'\x02' * 32 ) )
        
        menu_items = []
        
        def append_menu_item( menu, label, description, callable, *args, **kwargs ):
            
            menu_items.append( ( label, callable, args ) )
            
        
        patches = [
            mock.patch.object( ClientGUIMenus, 'GenerateMenu' ),
            mock.patch.object( ClientGUIMenus, 'AppendMenu' ),
            mock.patch.object( ClientGUIMenus, 'AppendSeparator' ),
            mock.patch.object( ClientGUIMenus, 'AppendMenuLabel', side_effect = lambda menu, label, *args, **kwargs: menu_items.append( ( label, None, () ) ) ),
            mock.patch.object( ClientGUIMenus, 'AppendMenuItem', side_effect = append_menu_item ),
            mock.patch.object( ClientGUIMediaViewerSync, 'GetMediaViewerSyncLabel', side_effect = lambda index, canvas_window: str( index + 1 ) )
        ]
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
        # just this one
        with mock.patch.object( ClientGUIMediaViewerSync, 'GetSyncableMediaViewerCanvases', return_value = [ canvas ] ):
            
            canvas._AppendSyncPlaybackMenu( mock.Mock() )
            
        
        self.assertEqual( [ label for ( label, callable, args ) in menu_items ], [ 'no other media viewer is playing anything' ] )
        
        menu_items.clear()
        
        # it is the second of three
        with mock.patch.object( ClientGUIMediaViewerSync, 'GetSyncableMediaViewerCanvases', return_value = [ first, canvas, second ] ):
            
            canvas._AppendSyncPlaybackMenu( mock.Mock() )
            
        
        self.assertEqual( [ label for ( label, callable, args ) in menu_items ], [ '1', '3', 'all of them' ] )
        self.assertEqual( [ args for ( label, callable, args ) in menu_items ], [ ( [ first ], ), ( [ second ], ), ( [ first, second ], ) ] )
        
        # clicking one syncs this one and that one
        with mock.patch.object( ClientGUIMediaViewerSync, 'SyncMediaViewersPlayback' ) as sync:
            
            ( label, callable, args ) = menu_items[1]
            
            callable( *args )
            
            sync.assert_called_once_with( [ canvas, second ] )
            
        
        # an image has no menu
        menu_items.clear()
        
        canvas._media_container.CurrentlyPresentingMediaWithDuration.return_value = False
        
        canvas._AppendSyncPlaybackMenu( mock.Mock() )
        
        self.assertEqual( menu_items, [] )
        
        
        

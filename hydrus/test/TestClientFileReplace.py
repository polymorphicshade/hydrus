import os
import tempfile
import unittest

from unittest import mock

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusExceptions

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientFileReplace
from hydrus.client import ClientGlobals as CG
from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.gui.pages import ClientGUIMediaResultsPanel

OLD_HASH = b'\x01' * 32
NEW_HASH = b'\x02' * 32
OTHER_HASH = b'\x03' * 32

def GetMedia( hash ):
    
    media = mock.Mock()
    
    media.GetHash.return_value = hash
    
    return media
    

class TestReplaceFile( unittest.TestCase ):
    
    def setUp( self ):
        
        ( os_file_handle, self._path ) = tempfile.mkstemp()
        
        os.close( os_file_handle )
        
        self.addCleanup( os.remove, self._path )
        
    
    def _PatchReplace( self, new_hash = NEW_HASH ):
        
        # one mock watches everything, so we can see what order it happens in
        manager = mock.Mock()
        
        manager.ImportReplacementFile.return_value = new_hash
        manager.WriteSynchronous.return_value = 3
        
        hashes_to_media_results = { OLD_HASH : manager.old_media_result, NEW_HASH : manager.new_media_result }
        
        manager.GetMediaResult.side_effect = lambda hash: hashes_to_media_results[ hash ]
        
        merge_options = manager.merge_options
        
        merge_options.ProcessPairIntoContentUpdatePackages.return_value = [ 'content update package' ]
        
        patches = [
            mock.patch.object( ClientFileReplace, 'ImportReplacementFile', manager.ImportReplacementFile ),
            mock.patch.object( ClientFileReplace, 'GetMediaResult', manager.GetMediaResult ),
            mock.patch.object( CG.client_controller, 'WriteSynchronous', manager.WriteSynchronous ),
            mock.patch.object( CG.client_controller, 'pub', manager.pub ),
            mock.patch.object( CG.client_controller.new_options, 'GetDuplicateContentMergeOptions', return_value = merge_options )
        ]
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
        return manager
        
    
    def test_replacing( self ):
        
        manager = self._PatchReplace()
        
        result = ClientFileReplace.ReplaceFile( OLD_HASH, self._path )
        
        self.assertEqual( result, ( NEW_HASH, 3 ) )
        
        manager.ImportReplacementFile.assert_called_once_with( self._path, manager.old_media_result )
        
        # 'this is better', the new file first, and the old one deleted
        CG.client_controller.new_options.GetDuplicateContentMergeOptions.assert_called_once_with( HC.DUPLICATE_BETTER )
        
        manager.merge_options.ProcessPairIntoContentUpdatePackages.assert_called_once_with( manager.new_media_result, manager.old_media_result, delete_b = True, file_deletion_reason = f'Replaced by {NEW_HASH.hex()}.' )
        
        # the fork's data moves, then media viewers hear about it while the old file is still there, then the duplicate merge and delete
        calls = [ c for c in manager.mock_calls if c[0] in ( 'WriteSynchronous', 'pub' ) ]
        
        self.assertEqual( calls, [
            mock.call.WriteSynchronous( 'file_replace_move_data', OLD_HASH, NEW_HASH ),
            mock.call.pub( 'notify_file_replaced', OLD_HASH, manager.new_media_result ),
            mock.call.WriteSynchronous( 'duplicate_pair_status', [ ( HC.DUPLICATE_BETTER, NEW_HASH, OLD_HASH, [ 'content update package' ] ) ] )
        ] )
        
    
    def test_keeping_the_old_file( self ):
        
        manager = self._PatchReplace()
        
        ClientFileReplace.ReplaceFile( OLD_HASH, self._path, delete_old_file = False )
        
        self.assertFalse( manager.merge_options.ProcessPairIntoContentUpdatePackages.call_args.kwargs[ 'delete_b' ] )
        
    
    def test_the_same_file( self ):
        
        manager = self._PatchReplace( new_hash = OLD_HASH )
        
        with self.assertRaises( HydrusExceptions.VetoException ):
            
            ClientFileReplace.ReplaceFile( OLD_HASH, self._path )
            
        
        manager.WriteSynchronous.assert_not_called()
        manager.pub.assert_not_called()
        
    
    def test_not_a_file( self ):
        
        manager = self._PatchReplace()
        
        with self.assertRaises( HydrusExceptions.VetoException ):
            
            ClientFileReplace.ReplaceFile( OLD_HASH, os.path.dirname( self._path ) )
            
        
        manager.ImportReplacementFile.assert_not_called()
        
    
    def test_import_location( self ):
        
        my_files_key = CC.LOCAL_FILE_SERVICE_KEY
        other_domain_key = b'\x09' * 32
        
        media_result = mock.Mock()
        
        services_manager = CG.client_controller.services_manager
        
        with mock.patch.object( services_manager, 'GetServiceKeys', return_value = [ my_files_key, other_domain_key ] ):
            
            # it goes where the old one is
            media_result.GetLocationsManager.return_value.GetCurrent.return_value = { my_files_key, CC.COMBINED_LOCAL_FILE_DOMAINS_SERVICE_KEY }
            
            location_context = ClientFileReplace.GetReplacementLocationContext( media_result )
            
            self.assertEqual( set( location_context.current_service_keys ), { my_files_key } )
            
            media_result.GetLocationsManager.return_value.GetCurrent.return_value = { my_files_key, other_domain_key }
            
            location_context = ClientFileReplace.GetReplacementLocationContext( media_result )
            
            self.assertEqual( set( location_context.current_service_keys ), { my_files_key, other_domain_key } )
            
            # in no local file domain, it goes wherever imports normally go
            media_result.GetLocationsManager.return_value.GetCurrent.return_value = set()
            
            self.assertIsNone( ClientFileReplace.GetReplacementLocationContext( media_result ) )
            
        
    

class TestReplaceFileInMediaViewers( unittest.TestCase ):
    
    def _GetCanvas( self, current_hash ):
        
        canvas = ClientGUICanvas.CanvasMediaList.__new__( ClientGUICanvas.CanvasMediaList )
        
        canvas._canvas_key = b'\xab' * 32
        
        old_media = GetMedia( OLD_HASH )
        other_media = GetMedia( OTHER_HASH )
        new_media = GetMedia( NEW_HASH )
        
        canvas._current_media = { OLD_HASH : old_media, OTHER_HASH : other_media }[ current_hash ]
        
        media_list = mock.Mock()
        
        media_list.GetMediaByHashes.side_effect = lambda hashes: [ media for media in ( old_media, other_media ) if media.GetHash() in hashes ]
        media_list.AddMediaResults.return_value = [ new_media ]
        media_list.HasMedia.return_value = True
        media_list.IndexOf.return_value = 4
        
        canvas._media_list = media_list
        
        patches = [
            mock.patch.object( canvas, 'SetMedia' ),
            mock.patch.object( canvas, '_GetIndexString', return_value = '' ),
            mock.patch.object( CG.client_controller, 'pub' )
        ]
        
        for patch in patches:
            
            patch.start()
            
            self.addCleanup( patch.stop )
            
        
        return ( canvas, old_media, new_media )
        
    
    def test_showing_the_old_file( self ):
        
        ( canvas, old_media, new_media ) = self._GetCanvas( OLD_HASH )
        
        new_media_result = mock.Mock()
        
        canvas.NotifyFileReplaced( OLD_HASH, new_media_result )
        
        # just after the old one, and shown
        canvas._media_list.AddMediaResults.assert_called_once_with( [ new_media_result ] )
        canvas._media_list.MoveMedia.assert_called_once_with( [ new_media ], 5 )
        
        canvas.SetMedia.assert_called_once_with( new_media )
        
    
    def test_showing_another_file( self ):
        
        ( canvas, old_media, new_media ) = self._GetCanvas( OTHER_HASH )
        
        canvas.NotifyFileReplaced( OLD_HASH, mock.Mock() )
        
        canvas._media_list.MoveMedia.assert_called_once_with( [ new_media ], 5 )
        
        canvas.SetMedia.assert_not_called()
        
    
    def test_not_our_file( self ):
        
        ( canvas, old_media, new_media ) = self._GetCanvas( OLD_HASH )
        
        canvas._media_list.GetMediaByHashes.side_effect = lambda hashes: []
        
        canvas.NotifyFileReplaced( OLD_HASH, mock.Mock() )
        
        canvas._media_list.AddMediaResults.assert_not_called()
        canvas.SetMedia.assert_not_called()
        
    
    def test_playlist( self ):
        
        canvas = ClientGUICanvas.CanvasPlaylist.__new__( ClientGUICanvas.CanvasPlaylist )
        
        canvas._canvas_key = b'\xab' * 32
        
        old_media = GetMedia( OLD_HASH )
        other_media = GetMedia( OTHER_HASH )
        new_media = GetMedia( NEW_HASH )
        
        canvas._playlist_items = [ ( other_media, None, None, False ), ( old_media, 1000, 2000, True ), ( None, None, 3000, False ), ( old_media, None, None, False ) ]
        canvas._playlist_index = 1
        canvas._playlist_item_preload_done = True
        
        with mock.patch.object( canvas, '_ShowPlaylistItem' ) as show_playlist_item:
            
            canvas._SwapToReplacementMedia( old_media, new_media )
            
            # every place it had, with their spans, and the one playing now starts again
            self.assertEqual( canvas._playlist_items, [ ( other_media, None, None, False ), ( new_media, 1000, 2000, True ), ( None, None, 3000, False ), ( new_media, None, None, False ) ] )
            self.assertFalse( canvas._playlist_item_preload_done )
            
            show_playlist_item.assert_called_once_with( 1 )
            
        
        canvas._playlist_index = 0
        
        with mock.patch.object( canvas, '_ShowPlaylistItem' ) as show_playlist_item, mock.patch.object( canvas, '_GetIndexString', return_value = '' ), mock.patch.object( CG.client_controller, 'pub' ):
            
            # a file that is not playing now
            canvas._SwapToReplacementMedia( GetMedia( b'\x04' * 32 ), GetMedia( b'\x05' * 32 ) )
            
            show_playlist_item.assert_not_called()
            
        
    
    def test_page( self ):
        
        panel = ClientGUIMediaResultsPanel.MediaResultsPanel.__new__( ClientGUIMediaResultsPanel.MediaResultsPanel )
        
        panel._page_key = b'\xcd' * 32
        
        old_media = GetMedia( OLD_HASH )
        other_media = GetMedia( OTHER_HASH )
        new_media = GetMedia( NEW_HASH )
        
        panel._hashes_to_singleton_media = { OLD_HASH : old_media, OTHER_HASH : other_media }
        panel._sorted_media = [ other_media, old_media ]
        
        new_media_result = mock.Mock()
        
        new_media_result.GetHash.return_value = NEW_HASH
        
        def add_media_results( page_key, media_results ):
            
            panel._hashes_to_singleton_media[ NEW_HASH ] = new_media
            panel._sorted_media.append( new_media )
            
        
        with mock.patch.object( panel, 'AddMediaResults', side_effect = add_media_results ) as add, mock.patch.object( panel, 'MoveMedia' ) as move:
            
            panel.NotifyFileReplaced( OLD_HASH, new_media_result )
            
            add.assert_called_once_with( panel._page_key, [ new_media_result ] )
            move.assert_called_once_with( [ new_media ], 2 )
            
        
        # a page without the old file leaves it alone
        with mock.patch.object( panel, 'AddMediaResults' ) as add:
            
            panel.NotifyFileReplaced( b'\x05' * 32, new_media_result )
            
            add.assert_not_called()
            
            
            
            

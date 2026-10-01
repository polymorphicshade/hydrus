import unittest

from unittest import mock

from qtpy import QtWidgets as QW

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIPlaylists
from hydrus.client.media import ClientMediaPlaylists

class TestPlaylistItems( unittest.TestCase ):
    
    def test_edit_playlist_items_panel( self ):
        
        hash_a = b'a' * 32
        hash_b = b'b' * 32
        hash_c = b'c' * 32
        
        items = [ ( hash_a, None, None, False ), ( hash_b, 1000, 5000, False ), ( hash_c, None, None, False ) ]
        
        hashes_to_names = { hash_a : 'apple', hash_b : 'banana', hash_c : 'cherry' }
        
        dialog = QW.QDialog()
        
        panel = ClientGUIPlaylists.EditPlaylistItemsPanel( dialog, items, hashes_to_names )
        
        items_list = panel._items_list
        
        def texts():
            
            return [ items_list.item( index ).text() for index in range( items_list.count() ) ]
            
        
        self.assertEqual( texts(), [ '1. apple', '2. banana (0:01.000 - 0:05.000)', '3. cherry' ] )
        
        # moving up
        
        items_list.item( 2 ).setSelected( True )
        
        panel._Move( -1 )
        
        self.assertEqual( panel.GetValue(), [ ( hash_a, None, None, False ), ( hash_c, None, None, False ), ( hash_b, 1000, 5000, False ) ] )
        self.assertEqual( texts(), [ '1. apple', '2. cherry', '3. banana (0:01.000 - 0:05.000)' ] )
        
        # a selection at the top does not move up any further
        
        items_list.clearSelection()
        
        items_list.item( 0 ).setSelected( True )
        items_list.item( 1 ).setSelected( True )
        
        panel._Move( -1 )
        
        self.assertEqual( panel.GetValue(), [ ( hash_a, None, None, False ), ( hash_c, None, None, False ), ( hash_b, 1000, 5000, False ) ] )
        
        # but moves down together
        
        panel._Move( 1 )
        
        self.assertEqual( panel.GetValue(), [ ( hash_b, 1000, 5000, False ), ( hash_a, None, None, False ), ( hash_c, None, None, False ) ] )
        self.assertEqual( sorted( panel._items_list.GetSelectedIndices() ), [ 1, 2 ] )
        
        # duplicating puts each copy after its original, and selects the copies
        
        items_list.clearSelection()
        
        items_list.item( 0 ).setSelected( True )
        items_list.item( 2 ).setSelected( True )
        
        panel._Duplicate()
        
        self.assertEqual( panel.GetValue(), [ ( hash_b, 1000, 5000, False ), ( hash_b, 1000, 5000, False ), ( hash_a, None, None, False ), ( hash_c, None, None, False ), ( hash_c, None, None, False ) ] )
        self.assertEqual( sorted( panel._items_list.GetSelectedIndices() ), [ 1, 4 ] )
        self.assertEqual( texts()[4], '5. cherry' )
        
        # the copies are their own rows, so removing one leaves the other
        
        panel._Remove()
        
        self.assertEqual( panel.GetValue(), [ ( hash_b, 1000, 5000, False ), ( hash_a, None, None, False ), ( hash_c, None, None, False ) ] )
        self.assertEqual( texts(), [ '1. banana (0:01.000 - 0:05.000)', '2. apple', '3. cherry' ] )
        
        # reverse: if any selected are forwards, they all go in reverse
        
        items_list.clearSelection()
        
        items_list.item( 0 ).setSelected( True )
        
        panel._FlipReverse()
        
        items_list.item( 1 ).setSelected( True )
        
        panel._FlipReverse()
        
        self.assertEqual( panel.GetValue(), [ ( hash_b, 1000, 5000, True ), ( hash_a, None, None, True ), ( hash_c, None, None, False ) ] )
        self.assertEqual( texts(), [ '1. banana (0:01.000 - 0:05.000) (in reverse)', '2. apple (in reverse)', '3. cherry' ] )
        
        # and when they are all in reverse, they all go back
        
        panel._FlipReverse()
        
        self.assertEqual( panel.GetValue(), [ ( hash_b, 1000, 5000, False ), ( hash_a, None, None, False ), ( hash_c, None, None, False ) ] )
        
        # reverse goes with an item when it moves or is duplicated
        
        items_list.clearSelection()
        
        items_list.item( 0 ).setSelected( True )
        
        panel._FlipReverse()
        panel._Duplicate()
        panel._Move( 1 )
        
        self.assertEqual( panel.GetValue(), [ ( hash_b, 1000, 5000, True ), ( hash_a, None, None, False ), ( hash_b, 1000, 5000, True ), ( hash_c, None, None, False ) ] )
        
        dialog.deleteLater()
        
    
    def test_view_playlist_items( self ):
        
        hash_a = b'a' * 32
        hash_b = b'b' * 32
        hash_c = b'c' * 32
        
        items = [ ( hash_a, None, None, False ), ( hash_b, 1000, 5000, True ), ( hash_c, None, None, False ) ]
        
        hashes_to_names = { hash_a : 'apple', hash_b : 'banana', hash_c : 'cherry' }
        
        dialog = QW.QDialog()
        
        panel = ClientGUIPlaylists.EditPlaylistItemsPanel( dialog, items, hashes_to_names )
        
        items_list = panel._items_list
        
        # nothing selected, nothing to view
        self.assertFalse( panel._view_button.isEnabled() )
        
        items_list.item( 2 ).setSelected( True )
        items_list.item( 1 ).setSelected( True )
        
        self.assertTrue( panel._view_button.isEnabled() )
        
        # the selected items, in playlist order
        with mock.patch.object( ClientGUIPlaylists, 'ViewPlaylistItems' ) as view_playlist_items:
            
            panel._View()
            
            view_playlist_items.assert_called_once_with( panel, [ ( hash_b, 1000, 5000, True ), ( hash_c, None, None, False ) ] )
            
        
        # files that cannot be shown are a warning, not a media viewer
        with mock.patch.object( CG.client_controller, 'Read', return_value = [] ):
            
            with mock.patch.object( ClientGUIDialogsMessage, 'ShowWarning' ) as show_warning:
                
                ClientGUIPlaylists.ViewPlaylistItems( panel, [ ( hash_a, None, None, False ) ] )
                
                show_warning.assert_called_once()
                
            
        
        dialog.deleteLater()
        
    
    def test_reversed_playlist_items( self ):
        
        # where an item starts: its start, or for one in reverse, its end
        self.assertEqual( ClientMediaPlaylists.GetPlaylistItemEntryMS( None, None, 10000, 40.0, False ), 0 )
        self.assertEqual( ClientMediaPlaylists.GetPlaylistItemEntryMS( 1000, 5000, 10000, 40.0, False ), 1000 )
        self.assertEqual( ClientMediaPlaylists.GetPlaylistItemEntryMS( 1000, 5000, 10000, 40.0, True ), 5000 )
        
        # a whole file in reverse starts on its last frame, not after it
        self.assertEqual( ClientMediaPlaylists.GetPlaylistItemEntryMS( None, None, 10000, 40.0, True ), 9960 )
        self.assertEqual( ClientMediaPlaylists.GetPlaylistItemEntryMS( None, None, None, 40.0, True ), 0 )
        
        # a seek in reverse lands when playback is at or just before where we sent it
        self.assertTrue( ClientMediaPlaylists.PlaylistSeekHasLanded( 4800, 5000, reverse = True ) )
        self.assertTrue( ClientMediaPlaylists.PlaylistSeekHasLanded( 5100, 5000, reverse = True ) )
        self.assertFalse( ClientMediaPlaylists.PlaylistSeekHasLanded( 5500, 5000, reverse = True ) )
        self.assertFalse( ClientMediaPlaylists.PlaylistSeekHasLanded( 3000, 5000, reverse = True ) )
        
        # forwards is as it was
        self.assertTrue( ClientMediaPlaylists.PlaylistSeekHasLanded( 5500, 5000 ) )
        self.assertFalse( ClientMediaPlaylists.PlaylistSeekHasLanded( 4500, 5000 ) )
        
        # done when it runs back past its start
        self.assertFalse( ClientMediaPlaylists.PlaylistReversedItemIsDone( 1000, 3000, 3100 ) )
        self.assertTrue( ClientMediaPlaylists.PlaylistReversedItemIsDone( 1000, 990, 1100 ) )
        
        # or when the player loops round from near its start to the end
        self.assertTrue( ClientMediaPlaylists.PlaylistReversedItemIsDone( None, 9900, 100 ) )
        
        # but a jump forward from the middle is the user seeking
        self.assertFalse( ClientMediaPlaylists.PlaylistReversedItemIsDone( None, 9900, 5000 ) )
        
        # the last frame in reverse is the one at the start
        self.assertIsNone( ClientMediaPlaylists.GetPlaylistReversedItemLastFrameTimeLeftMS( 1000, 2000, 40.0 ) )
        self.assertEqual( ClientMediaPlaylists.GetPlaylistReversedItemLastFrameTimeLeftMS( 1000, 1030, 40.0 ), 30 )
        self.assertEqual( ClientMediaPlaylists.GetPlaylistReversedItemLastFrameTimeLeftMS( None, 33, 40.0 ), 33 )
        self.assertEqual( ClientMediaPlaylists.GetPlaylistReversedItemLastFrameTimeLeftMS( 1000, 990, 40.0 ), 0.0 )
        
    

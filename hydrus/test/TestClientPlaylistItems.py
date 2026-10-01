import unittest

from unittest import mock

from qtpy import QtWidgets as QW

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui import ClientGUIDialogsMessage
from hydrus.client.gui import ClientGUIPlaylists

class TestPlaylistItems( unittest.TestCase ):
    
    def test_edit_playlist_items_panel( self ):
        
        hash_a = b'a' * 32
        hash_b = b'b' * 32
        hash_c = b'c' * 32
        
        items = [ ( hash_a, None, None ), ( hash_b, 1000, 5000 ), ( hash_c, None, None ) ]
        
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
        
        self.assertEqual( panel.GetValue(), [ ( hash_a, None, None ), ( hash_c, None, None ), ( hash_b, 1000, 5000 ) ] )
        self.assertEqual( texts(), [ '1. apple', '2. cherry', '3. banana (0:01.000 - 0:05.000)' ] )
        
        # a selection at the top does not move up any further
        
        items_list.clearSelection()
        
        items_list.item( 0 ).setSelected( True )
        items_list.item( 1 ).setSelected( True )
        
        panel._Move( -1 )
        
        self.assertEqual( panel.GetValue(), [ ( hash_a, None, None ), ( hash_c, None, None ), ( hash_b, 1000, 5000 ) ] )
        
        # but moves down together
        
        panel._Move( 1 )
        
        self.assertEqual( panel.GetValue(), [ ( hash_b, 1000, 5000 ), ( hash_a, None, None ), ( hash_c, None, None ) ] )
        self.assertEqual( sorted( panel._items_list.GetSelectedIndices() ), [ 1, 2 ] )
        
        # duplicating puts each copy after its original, and selects the copies
        
        items_list.clearSelection()
        
        items_list.item( 0 ).setSelected( True )
        items_list.item( 2 ).setSelected( True )
        
        panel._Duplicate()
        
        self.assertEqual( panel.GetValue(), [ ( hash_b, 1000, 5000 ), ( hash_b, 1000, 5000 ), ( hash_a, None, None ), ( hash_c, None, None ), ( hash_c, None, None ) ] )
        self.assertEqual( sorted( panel._items_list.GetSelectedIndices() ), [ 1, 4 ] )
        self.assertEqual( texts()[4], '5. cherry' )
        
        # the copies are their own rows, so removing one leaves the other
        
        panel._Remove()
        
        self.assertEqual( panel.GetValue(), [ ( hash_b, 1000, 5000 ), ( hash_a, None, None ), ( hash_c, None, None ) ] )
        self.assertEqual( texts(), [ '1. banana (0:01.000 - 0:05.000)', '2. apple', '3. cherry' ] )
        
        dialog.deleteLater()
        
    
    def test_view_playlist_items( self ):
        
        hash_a = b'a' * 32
        hash_b = b'b' * 32
        hash_c = b'c' * 32
        
        items = [ ( hash_a, None, None ), ( hash_b, 1000, 5000 ), ( hash_c, None, None ) ]
        
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
            
            view_playlist_items.assert_called_once_with( panel, [ ( hash_b, 1000, 5000 ), ( hash_c, None, None ) ] )
            
        
        # files that cannot be shown are a warning, not a media viewer
        with mock.patch.object( CG.client_controller, 'Read', return_value = [] ):
            
            with mock.patch.object( ClientGUIDialogsMessage, 'ShowWarning' ) as show_warning:
                
                ClientGUIPlaylists.ViewPlaylistItems( panel, [ ( hash_a, None, None ) ] )
                
                show_warning.assert_called_once()
                
            
        
        dialog.deleteLater()
        
    

import unittest

from unittest import mock

from qtpy import QtWidgets as QW

from hydrus.client.exporting import ClientExportingPlaylists
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUIPlaylists
from hydrus.client.gui.canvas import ClientGUICanvas
from hydrus.client.media import ClientMediaPlaylists

class FakeMedia( object ):
    
    def __init__( self, name ):
        
        self.name = name
        
    
    def GetMediaResult( self ):
        
        return self.name
        
    

class TestPlaylistBlanks( unittest.TestCase ):
    
    def test_logic( self ):
        
        self.assertEqual( ClientMediaPlaylists.CreatePlaylistBlankItem( 1500 ), ( None, None, 1500, False ) )
        
        # it is kept to something sensible
        self.assertEqual( ClientMediaPlaylists.CreatePlaylistBlankItem( 0 ), ( None, None, ClientMediaPlaylists.PLAYLIST_BLANK_MIN_MS, False ) )
        self.assertEqual( ClientMediaPlaylists.CreatePlaylistBlankItem( 10 ** 12 ), ( None, None, ClientMediaPlaylists.PLAYLIST_BLANK_MAX_MS, False ) )
        
        self.assertEqual( ClientMediaPlaylists.ConvertPlaylistBlankToString( 1500 ), 'blank for 1,500ms' )
        
        self.assertFalse( ClientMediaPlaylists.PlaylistBlankIsDone( 1500, 1.4 ) )
        self.assertTrue( ClientMediaPlaylists.PlaylistBlankIsDone( 1500, 1.5 ) )
        
    
    def test_editor( self ):
        
        hash_a = b'a' * 32
        hash_b = b'b' * 32
        
        items = [ ( hash_a, None, None, False ), ( hash_b, 1000, 5000, False ) ]
        
        hashes_to_names = { hash_a : 'apple', hash_b : 'banana' }
        
        dialog = QW.QDialog()
        
        panel = ClientGUIPlaylists.EditPlaylistItemsPanel( dialog, items, hashes_to_names )
        
        items_list = panel._items_list
        
        def texts():
            
            return [ items_list.item( index ).text() for index in range( items_list.count() ) ]
            
        
        # nothing selected, so it goes on the end
        with mock.patch.object( ClientGUIDialogsQuick, 'EnterNumber', return_value = 2000 ):
            
            panel._AddBlank()
            
        
        self.assertEqual( panel.GetValue(), [ ( hash_a, None, None, False ), ( hash_b, 1000, 5000, False ), ( None, None, 2000, False ) ] )
        self.assertEqual( texts()[2], '3. blank for 2,000ms' )
        
        # and it is selected, so blank-only selections have nothing to view or reverse
        self.assertEqual( panel._items_list.GetSelectedIndices(), [ 2 ] )
        self.assertFalse( panel._view_button.isEnabled() )
        self.assertFalse( panel._reverse_button.isEnabled() )
        self.assertTrue( panel._remove_button.isEnabled() )
        
        # with a selection, it goes after it
        items_list.clearSelection()
        
        items_list.item( 0 ).setSelected( True )
        
        with mock.patch.object( ClientGUIDialogsQuick, 'EnterNumber', return_value = 500 ):
            
            panel._AddBlank()
            
        
        self.assertEqual( panel.GetValue(), [ ( hash_a, None, None, False ), ( None, None, 500, False ), ( hash_b, 1000, 5000, False ), ( None, None, 2000, False ) ] )
        self.assertEqual( texts(), [ '1. apple', '2. blank for 500ms', '3. banana (0:01.000 - 0:05.000)', '4. blank for 2,000ms' ] )
        
        # backing out adds nothing
        from hydrus.core import HydrusExceptions
        
        with mock.patch.object( ClientGUIDialogsQuick, 'EnterNumber', side_effect = HydrusExceptions.CancelledException() ):
            
            panel._AddBlank()
            
        
        self.assertEqual( len( panel.GetValue() ), 4 )
        
        # reverse leaves blanks alone
        items_list.clearSelection()
        
        for index in range( 4 ):
            
            items_list.item( index ).setSelected( True )
            
        
        self.assertTrue( panel._reverse_button.isEnabled() )
        
        panel._FlipReverse()
        
        self.assertEqual( panel.GetValue(), [ ( hash_a, None, None, True ), ( None, None, 500, False ), ( hash_b, 1000, 5000, True ), ( None, None, 2000, False ) ] )
        
        # view leaves blanks out
        with mock.patch.object( ClientGUIPlaylists, 'ViewPlaylistItems' ) as view_playlist_items:
            
            panel._View()
            
            view_playlist_items.assert_called_once_with( panel, [ ( hash_a, None, None, True ), ( hash_b, 1000, 5000, True ) ] )
            
        
        # double-clicking a blank changes how long it is, and double-clicking a file views it
        with mock.patch.object( ClientGUIDialogsQuick, 'EnterNumber', return_value = 750 ):
            
            panel._ItemDoubleClicked( items_list.item( 1 ) )
            
        
        self.assertEqual( panel.GetValue()[1], ( None, None, 750, False ) )
        self.assertEqual( texts()[1], '2. blank for 750ms' )
        
        with mock.patch.object( ClientGUIPlaylists, 'ViewPlaylistItems' ) as view_playlist_items:
            
            items_list.clearSelection()
            
            items_list.item( 0 ).setSelected( True )
            
            panel._ItemDoubleClicked( items_list.item( 0 ) )
            
            view_playlist_items.assert_called_once_with( panel, [ ( hash_a, None, None, True ) ] )
            
        
        # blanks move and duplicate like anything else
        items_list.clearSelection()
        
        items_list.item( 1 ).setSelected( True )
        
        panel._Duplicate()
        panel._Move( 1 )
        
        self.assertEqual( panel.GetValue(), [ ( hash_a, None, None, True ), ( None, None, 750, False ), ( hash_b, 1000, 5000, True ), ( None, None, 750, False ), ( None, None, 2000, False ) ] )
        
        # a view of only blanks does nothing
        with mock.patch.object( ClientGUIPlaylists.CG.client_controller, 'Read' ) as read:
            
            ClientGUIPlaylists.ViewPlaylistItems( panel, [ ( None, None, 750, False ) ] )
            
            read.assert_not_called()
            
        
        dialog.deleteLater()
        
    
    def test_export( self ):
        
        blank = ClientExportingPlaylists.PLAYLIST_EXPORT_KIND_BLANK
        
        cmd = ClientExportingPlaylists.GetPlaylistExportSegmentCommand( 'ffmpeg', blank, '', False, None, 1500, None, ( 640, 360 ), 30, 'out.mp4' )
        
        # black and silence, for as long as the blank, and no file
        self.assertIn( 'color=c=black:s=640x360:r=30', cmd )
        self.assertTrue( any( arg.startswith( 'anullsrc' ) for arg in cmd ) )
        self.assertEqual( cmd[ cmd.index( '-t' ) + 1 ], '1.500' )
        self.assertNotIn( '', cmd )
        self.assertEqual( cmd[-1], 'out.mp4' )
        
    
    def test_canvas( self ):
        
        canvas = ClientGUICanvas.CanvasPlaylist.__new__( ClientGUICanvas.CanvasPlaylist )
        
        media_a = FakeMedia( 'a' )
        media_b = FakeMedia( 'b' )
        
        canvas._playlist_items = [ ( media_a, None, None, False ), ( None, None, 1000, False ), ( media_b, None, None, False ) ]
        canvas._playlist_index = 1
        canvas._playlist_item_still_time_s = 0.0
        
        self.assertTrue( canvas._PlaylistIsOnBlank() )
        
        advances = []
        
        with mock.patch.object( canvas, '_PlaylistIsHeld', return_value = False ), mock.patch.object( canvas, '_MaintainPlaylistPreload' ) as maintain_preload, mock.patch.object( canvas, '_AdvancePlaylist', side_effect = lambda: advances.append( True ) ):
            
            canvas._DoPlaylistBlankWork( 1000, 0.6 )
            
            self.assertEqual( advances, [] )
            
            # the next file gets ready while the blank is up
            maintain_preload.assert_called()
            
            canvas._DoPlaylistBlankWork( 1000, 0.6 )
            
            self.assertEqual( advances, [ True ] )
            
        
        # it holds still while the user is doing something
        canvas._playlist_item_still_time_s = 0.0
        
        with mock.patch.object( canvas, '_PlaylistIsHeld', return_value = True ), mock.patch.object( canvas, '_AdvancePlaylist', side_effect = lambda: advances.append( True ) ):
            
            canvas._DoPlaylistBlankWork( 1000, 5.0 )
            
        
        self.assertEqual( canvas._playlist_item_still_time_s, 0.0 )
        self.assertEqual( advances, [ True ] )
        
        # blanks have nothing to prefetch
        canvas._current_media = media_a
        canvas._playlist_index = 0
        canvas._playlist_shuffle_order = None
        
        with mock.patch.object( ClientGUICanvas.CG.client_controller.new_options, 'GetInteger', return_value = 2 ):
            
            self.assertEqual( canvas._GetPrefetchNeighboursInPreferenceOrder(), [ 'b' ] )
            
        
        # removing a file keeps the blanks, but blanks on their own are not worth keeping the window open for
        canvas._playlist_index = 1
        canvas._playlist_item_preload_done = True
        canvas._canvas_key = b'key'
        canvas._playlist_name = 'test'
        
        closes = []
        
        with mock.patch.object( canvas, '_TryToCloseWindow', side_effect = lambda: closes.append( True ) ), mock.patch.object( ClientGUICanvas.CG.client_controller, 'pub' ):
            
            canvas._RemovePlaylistItemsForMedias( { media_a } )
            
            self.assertEqual( canvas._playlist_items, [ ( None, None, 1000, False ), ( media_b, None, None, False ) ] )
            self.assertEqual( canvas._playlist_index, 0 )
            self.assertEqual( closes, [] )
            
            canvas._RemovePlaylistItemsForMedias( { media_b } )
            
            self.assertEqual( closes, [ True ] )
            
        
    

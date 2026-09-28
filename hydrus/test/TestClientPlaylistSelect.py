import unittest

from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions

from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUIPlaylists

class TestPlaylistSelect( unittest.TestCase ):
    
    def test_new_playlist_from_select( self ):
        
        playlists = [ ( 1, 'chill', 3 ), ( 2, 'Road Trip', 0 ) ]
        
        dialog = QW.QDialog()
        
        original_enter_text = ClientGUIDialogsQuick.EnterText
        
        try:
            
            # only adding offers a new playlist
            
            panel = ClientGUIPlaylists.SelectPlaylistPanel( dialog, playlists )
            
            self.assertTrue( panel._new_playlist_button.isHidden() )
            
            panel = ClientGUIPlaylists.SelectPlaylistPanel( dialog, playlists, allow_new_playlist = True )
            
            self.assertFalse( panel._new_playlist_button.isHidden() )
            
            oks = []
            
            panel.okSignal.connect( lambda: oks.append( True ) )
            
            # picking one as normal
            
            self.assertEqual( panel.GetValue(), 1 )
            
            # a new one. what was typed in the filter is a good start for the name
            
            panel._filter.setText( 'work' )
            
            entered_defaults = []
            
            def enter_text( win, message, default = '', **kwargs ):
                
                entered_defaults.append( default )
                
                return '  work   out '
                
            
            ClientGUIDialogsQuick.EnterText = enter_text
            
            panel._NewPlaylist()
            
            self.assertEqual( entered_defaults, [ 'work' ] )
            self.assertEqual( oks, [ True ] )
            self.assertEqual( panel.GetValue(), 'work out' )
            
            # a name we already have just picks that one
            
            panel = ClientGUIPlaylists.SelectPlaylistPanel( dialog, playlists, allow_new_playlist = True )
            
            panel.okSignal.connect( lambda: oks.append( True ) )
            
            panel._filter.setText( 'chill' )
            
            ClientGUIDialogsQuick.EnterText = lambda win, message, **kwargs: 'road trip'
            
            panel._NewPlaylist()
            
            self.assertEqual( oks, [ True, True ] )
            self.assertEqual( panel.GetValue(), 2 )
            
            # backing out, or no name, does nothing
            
            panel = ClientGUIPlaylists.SelectPlaylistPanel( dialog, playlists, allow_new_playlist = True )
            
            def cancel( win, message, **kwargs ):
                
                raise HydrusExceptions.CancelledException()
                
            
            for enter_text in ( cancel, lambda win, message, **kwargs: '   ' ):
                
                ClientGUIDialogsQuick.EnterText = enter_text
                
                panel._NewPlaylist()
                
                self.assertEqual( panel.GetValue(), 1 )
                
            
        finally:
            
            ClientGUIDialogsQuick.EnterText = original_enter_text
            
            dialog.deleteLater()
            
        
    

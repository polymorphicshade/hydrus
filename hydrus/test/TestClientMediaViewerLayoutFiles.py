import os
import tempfile
import unittest

from unittest import mock

from qtpy import QtWidgets as QW

from hydrus.client import ClientMediaViewerLayouts as L
from hydrus.client.gui import ClientGUIMediaViewerLayouts

class TestMediaViewerLayoutFiles( unittest.TestCase ):
    
    def test_save_and_load_files( self ):
        
        hash = os.urandom( 32 )
        
        layouts = [ L.MediaViewerLayout( [ hash ], hash, 'DISPLAY1', 10, 20, 800, 600, fullscreen = True, relative_zoom = 3.0, center = ( 0.1, 0.9 ), playback_ms = 5000 ) ]
        
        win = QW.QWidget()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            
            # saving adds the .json if it was left off
            path = os.path.join( temp_dir, 'my layout' )
            
            with mock.patch.object( ClientGUIMediaViewerLayouts, 'GetOpenMediaViewerLayouts', return_value = layouts ):
                
                with mock.patch.object( QW.QFileDialog, 'getSaveFileName', return_value = ( path, '' ) ):
                    
                    ClientGUIMediaViewerLayouts.SaveMediaViewerLayoutToFile( win )
                    
                
            
            with open( path + '.json', 'r', encoding = 'utf-8' ) as f:
                
                self.assertEqual( L.ConvertJSONToMediaViewerLayouts( f.read() ), layouts )
                
            
            # the next one starts in the same folder
            self.assertEqual( ClientGUIMediaViewerLayouts.LAST_MEDIA_VIEWER_LAYOUT_DIR, temp_dir )
            
            with mock.patch.object( QW.QFileDialog, 'getOpenFileName', return_value = ( path + '.json', '' ) ):
                
                with mock.patch.object( ClientGUIMediaViewerLayouts, 'OpenMediaViewerLayouts', return_value = ( 1, 0 ) ) as open_layouts:
                    
                    ClientGUIMediaViewerLayouts.LoadMediaViewerLayoutFromFile( win )
                    
                    open_layouts.assert_called_once_with( layouts )
                    
                
            
            # backing out of the file dialog does nothing
            with mock.patch.object( QW.QFileDialog, 'getOpenFileName', return_value = ( '', '' ) ):
                
                with mock.patch.object( ClientGUIMediaViewerLayouts, 'OpenMediaViewerLayouts' ) as open_layouts:
                    
                    ClientGUIMediaViewerLayouts.LoadMediaViewerLayoutFromFile( win )
                    
                    open_layouts.assert_not_called()
                    
                
            
        
        win.deleteLater()
        
    

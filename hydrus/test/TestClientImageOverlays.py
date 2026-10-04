import os
import tempfile
import unittest

from unittest import mock

from qtpy import QtCore as QC
from qtpy import QtGui as QG
from qtpy import QtWidgets as QW

from hydrus.core import HydrusExceptions

from hydrus.client import ClientGlobals as CG
from hydrus.client.gui.canvas import ClientGUICanvasOverlays as O

from hydrus.test import TestClientCanvasOverlays
from hydrus.test import TestGlobals as TG

class FakeAsyncJob( object ):
    
    # does the work there and then, rather than in another thread
    
    def __init__( self, win, work_callable, publish_callable ):
        
        self._work_callable = work_callable
        self._publish_callable = publish_callable
        
    
    def start( self ):
        
        self._publish_callable( self._work_callable() )
        
    

class FakeMedia( object ):
    
    def __init__( self, hash ):
        
        self._hash = hash
        
    
    def GetHash( self ):
        
        return self._hash
        
    

def MakeImage( dir_path: str, name: str, size: tuple[ int, int ] ) -> str:
    
    path = os.path.join( dir_path, name )
    
    image = QG.QImage( size[0], size[1], QG.QImage.Format.Format_ARGB32 )
    
    # half see-through red
    image.fill( QG.QColor( 255, 0, 0, 128 ) )
    
    image.save( path, 'PNG' )
    
    return path
    

class TestImageOverlays( unittest.TestCase ):
    
    def test_target_rect( self ):
        
        # it keeps its shape, as big as fits, in the middle
        self.assertEqual( O.GetImageOverlayTargetRect( ( 100, 50 ), ( 400, 400 ), False ), ( 0, 100, 400, 200 ) )
        self.assertEqual( O.GetImageOverlayTargetRect( ( 50, 100 ), ( 400, 400 ), False ), ( 100, 0, 200, 400 ) )
        self.assertEqual( O.GetImageOverlayTargetRect( ( 400, 300 ), ( 800, 600 ), False ), ( 0, 0, 800, 600 ) )
        
        # unless it is stretched
        self.assertEqual( O.GetImageOverlayTargetRect( ( 100, 50 ), ( 400, 400 ), True ), ( 0, 0, 400, 400 ) )
        
        # nonsense sizes just fill the box
        self.assertEqual( O.GetImageOverlayTargetRect( ( 0, 0 ), ( 400, 300 ), False ), ( 0, 0, 400, 300 ) )
        
    
    def test_panel( self ):
        
        with tempfile.TemporaryDirectory() as temp_dir:
            
            image_path = MakeImage( temp_dir, 'frame.png', ( 40, 20 ) )
            
            not_an_image_path = os.path.join( temp_dir, 'notes.txt' )
            
            with open( not_an_image_path, 'w' ) as f:
                
                f.write( 'hello' )
                
            
            dialog = QW.QDialog()
            
            fractions = ( 0.1, 0.2, 0.3, 0.4 )
            
            panel = O.EditImageOverlayPanel( dialog, ( '', 0.5, fractions, True, False ) )
            
            self.assertEqual( panel._opacity.value(), 50 )
            
            # it needs an image
            with self.assertRaises( HydrusExceptions.VetoException ):
                
                panel.GetValue()
                
            
            panel._path.SetPath( not_an_image_path )
            
            with self.assertRaises( HydrusExceptions.VetoException ):
                
                panel.GetValue()
                
            
            panel._path.SetPath( os.path.join( temp_dir, 'missing.png' ) )
            
            with self.assertRaises( HydrusExceptions.VetoException ):
                
                panel.GetValue()
                
            
            panel._path.SetPath( image_path )
            panel._opacity.setValue( 80 )
            panel._stretch.setChecked( True )
            
            # the box and lock come through as they were
            self.assertEqual( panel.GetValue(), ( image_path, 0.8, fractions, True, True ) )
            
            # never all the way see-through
            panel._opacity.setValue( 0 )
            
            self.assertEqual( panel.GetValue()[1], O.OVERLAY_MIN_OPACITY_PERCENT / 100 )
            
            dialog.deleteLater()
            
        
    
    def _DoManagerTest( self ):
        
        # the windows are closed even if a check fails, or they hang the test run
        windows = []
        
        try:
            
            self._DoManagerTestWithWindows( windows )
            
        finally:
            
            for window in windows:
                
                window.close()
                window.deleteLater()
                
            
            QW.QApplication.processEvents()
            
        
    
    def _DoManagerTestWithWindows( self, windows: list ):
        
        with tempfile.TemporaryDirectory() as temp_dir:
            
            image_path = MakeImage( temp_dir, 'frame.png', ( 40, 20 ) )
            other_image_path = MakeImage( temp_dir, 'other.png', ( 20, 20 ) )
            
            window = QW.QWidget()
            
            windows.append( window )
            
            layout = QW.QVBoxLayout( window )
            layout.setContentsMargins( 20, 20, 20, 20 )
            
            canvas = QW.QWidget( window )
            
            layout.addWidget( canvas )
            
            window.resize( 1040, 840 )
            window.show()
            
            QW.QApplication.processEvents()
            
            hash_a = os.urandom( 32 )
            hash_b = os.urandom( 32 )
            
            manager = O.CanvasImageOverlayManager( canvas )
            other_manager = O.CanvasImageOverlayManager( canvas )
            
            self.assertFalse( manager.HasMedia() )
            
            with mock.patch.object( CG.client_controller, 'Write' ) as write, mock.patch.object( CG.client_controller, 'pub' ) as pub, mock.patch.object( CG.client_controller, 'Read', return_value = None ):
                
                # pretend hash_a is up, and its saved image came back from the db
                manager._hash = hash_a
                
                image_overlay = ( image_path, 0.75, ( 0.25, 0.25, 0.5, 0.5 ), False, False )
                
                manager._ApplyImageOverlay( image_overlay )
                
                QW.QApplication.processEvents()
                
                overlay_window = manager.GetOverlayWindow()
                
                self.assertTrue( overlay_window.isVisible() )
                self.assertEqual( overlay_window.GetImageOverlay(), image_overlay )
                
                # it sits over its part of the canvas, like a box overlay
                top_left = canvas.mapToGlobal( QC.QPoint( 250, 200 ) )
                
                self.assertEqual( overlay_window.geometry(), QC.QRect( top_left.x(), top_left.y(), 500, 400 ) )
                
                # but it is not one of the boxes, so 'remove all' leaves it alone
                self.assertEqual( O.GetOverlays( canvas ), [] )
                
                # it draws
                self.assertFalse( overlay_window.grab().isNull() )
                
                # dragging it saves where it went, for this file, and tells other media viewers
                start_global = overlay_window.mapToGlobal( QC.QPoint( 250, 200 ) )
                
                MouseEvent = TestClientCanvasOverlays.MouseEvent
                
                overlay_window.mousePressEvent( MouseEvent( QC.QEvent.Type.MouseButtonPress, QC.QPoint( 250, 200 ), start_global ) )
                overlay_window.mouseMoveEvent( MouseEvent( QC.QEvent.Type.MouseMove, QC.QPoint( 350, 150 ), start_global + QC.QPoint( 100, -50 ) ) )
                overlay_window.mouseReleaseEvent( MouseEvent( QC.QEvent.Type.MouseButtonRelease, QC.QPoint( 350, 150 ), start_global + QC.QPoint( 100, -50 ) ) )
                
                ( path, opacity, fractions, locked, stretch ) = manager.GetImageOverlay()
                
                self.assertEqual( O.ConvertFractionsToRect( fractions, ( 1000, 800 ) ), ( 350, 150, 500, 400 ) )
                
                write.assert_called_once_with( 'file_image_overlay', hash_a, manager.GetImageOverlay() )
                pub.assert_called_once_with( 'new_file_image_overlay', hash_a, manager.GetImageOverlay(), manager )
                
                # a move is done on the same window
                self.assertIs( manager.GetOverlayWindow(), overlay_window )
                
                # a click that does not move it does not save anything
                overlay_window.mousePressEvent( MouseEvent( QC.QEvent.Type.MouseButtonPress, QC.QPoint( 10, 10 ), overlay_window.mapToGlobal( QC.QPoint( 100, 100 ) ) ) )
                overlay_window.mouseReleaseEvent( MouseEvent( QC.QEvent.Type.MouseButtonRelease, QC.QPoint( 10, 10 ), overlay_window.mapToGlobal( QC.QPoint( 100, 100 ) ) ) )
                
                self.assertEqual( write.call_count, 1 )
                
                # locking it makes a new window that clicks go through
                manager.FlipLocked()
                
                QW.QApplication.processEvents()
                
                self.assertTrue( overlay_window.IsRemoved() )
                
                overlay_window = manager.GetOverlayWindow()
                
                self.assertTrue( manager.GetImageOverlay()[3] )
                self.assertTrue( overlay_window.windowFlags() & QC.Qt.WindowType.WindowTransparentForInput )
                self.assertTrue( overlay_window.isVisible() )
                
                manager.FlipLocked()
                
                overlay_window = manager.GetOverlayWindow()
                
                self.assertFalse( overlay_window.windowFlags() & QC.Qt.WindowType.WindowTransparentForInput )
                
                # stretch and fill
                manager.FlipStretch()
                manager.FillMediaViewer()
                
                self.assertEqual( manager.GetImageOverlay()[2], O.IMAGE_OVERLAY_FILL_FRACTIONS )
                self.assertTrue( manager.GetImageOverlay()[4] )
                self.assertEqual( overlay_window.geometry().size(), QC.QSize( 1000, 800 ) )
                
                # another media viewer on the same file follows a change from elsewhere, and ignores files it is not showing
                other_manager._hash = hash_a
                
                other_manager.NotifyNewImageOverlay( hash_a, ( other_image_path, 0.5, O.OVERLAY_DEFAULT_FRACTIONS, True, False ), manager )
                
                self.assertEqual( other_manager.GetImageOverlay()[0], other_image_path )
                
                other_manager.NotifyNewImageOverlay( hash_b, None, manager )
                
                self.assertEqual( other_manager.GetImageOverlay()[0], other_image_path )
                
                # and the one that made the change does not redo it
                manager.NotifyNewImageOverlay( hash_a, None, manager )
                
                self.assertIsNotNone( manager.GetImageOverlay() )
                
                # the menu
                menu = QW.QMenu( window )
                
                overlays_menu = O.AppendOverlaysMenu( menu, canvas, image_overlay_manager = manager )
                
                self.assertEqual( menu.actions()[-1].text(), 'overlays (and an image)' )
                
                texts = [ action.text() for action in overlays_menu.actions() ]
                
                self.assertIn( 'remove this file\'s image', texts )
                
                # a missing image still draws, with a note
                manager.SetImageOverlay( ( os.path.join( temp_dir, 'gone.png' ), 1.0, O.OVERLAY_DEFAULT_FRACTIONS, False, False ) )
                
                self.assertFalse( manager.GetOverlayWindow().grab().isNull() )
                
                # removing it forgets it for the file
                write.reset_mock()
                
                manager.RemoveImageOverlay()
                
                self.assertIsNone( manager.GetImageOverlay() )
                self.assertIsNone( manager.GetOverlayWindow() )
                
                write.assert_called_once_with( 'file_image_overlay', hash_a, None )
                
                menu = QW.QMenu( window )
                
                overlays_menu = O.AppendOverlaysMenu( menu, canvas, image_overlay_manager = manager )
                
                self.assertEqual( menu.actions()[-1].text(), 'overlays' )
                self.assertIn( 'set image for this file' + O.HC.UNICODE_ELLIPSIS, [ action.text() for action in overlays_menu.actions() ] )
                
                # with no file up, there is nothing to set it for
                manager._ApplyImageOverlay( image_overlay )
                
                manager.ClearMedia()
                
                self.assertFalse( manager.HasMedia() )
                self.assertIsNone( manager.GetOverlayWindow() )
                
                manager.SetImageOverlay( image_overlay )
                
                self.assertIsNone( manager.GetImageOverlay() )
                
            
            # going to a file looks up its image
            saved_image_overlay = ( image_path, 0.5, O.OVERLAY_DEFAULT_FRACTIONS, False, False )
            
            with mock.patch.object( CG.client_controller, 'Read', side_effect = lambda name, hash: saved_image_overlay if hash == hash_b else None ) as read, mock.patch.object( O.ClientGUIAsync, 'AsyncQtJob', FakeAsyncJob ):
                
                manager.SetMedia( FakeMedia( hash_b ) )
                
                read.assert_called_once_with( 'file_image_overlay', hash_b )
                
                self.assertTrue( manager.HasMedia() )
                self.assertEqual( manager.GetImageOverlay(), saved_image_overlay )
                self.assertTrue( manager.GetOverlayWindow().isVisible() )
                
                # the same file again does not look it up again
                manager.SetMedia( FakeMedia( hash_b ) )
                
                self.assertEqual( read.call_count, 1 )
                
                # a file with no image has none
                manager.SetMedia( FakeMedia( hash_a ) )
                
                self.assertIsNone( manager.GetImageOverlay() )
                self.assertIsNone( manager.GetOverlayWindow() )
                
            
        
    
    def test_manager( self ):
        
        # showing windows and processing their events has to happen in the Qt thread
        TG.test_controller.CallBlockingToQtTLW( self._DoManagerTest )
        
    
